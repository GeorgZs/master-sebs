import concurrent.futures
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sebs.faas.function import ExecutionResult, Function, FunctionConfig, Trigger


class LibraryTrigger(Trigger):
    """
    Cloudburst trigger using CloudburstConnection (ZMQ).

    The function is pre-registered with the scheduler. Each sync_invoke()
    calls the function via call_dag() and parses the result into
    ExecutionResult format.
    """

    def __init__(self, scheduler_ip: str, client_ip: str, local: bool, cloudburst_path: str):
        super().__init__()
        self._scheduler_ip = scheduler_ip
        self._client_ip = client_ip
        self._local = local
        self._cloudburst_path = cloudburst_path
        self._connection = None
        self._registered = False

    def _ensure_connection(self):
        if self._connection is not None:
            return

        # Add master-cloudburst to import path
        if self._cloudburst_path and self._cloudburst_path not in sys.path:
            sys.path.insert(0, self._cloudburst_path)

        try:
            from cloudburst.client.client import CloudburstConnection
        except ImportError:
            raise RuntimeError(
                f"Cannot import CloudburstConnection. "
                f"Ensure master-cloudburst is at: {self._cloudburst_path}"
            )

        self.logging.info(
            f"Connecting to Cloudburst scheduler at {self._scheduler_ip} "
            f"(local={self._local})"
        )
        self._connection = CloudburstConnection(
            self._scheduler_ip, self._client_ip, local=self._local
        )

    def _ensure_registered(self):
        if self._registered:
            return

        self._ensure_connection()

        # Import the benchmark function from the cloudburst server module
        from cloudburst.server.benchmarks.stateful import stateful_bench

        self.logging.info("Registering stateful_bench function with Cloudburst scheduler")
        cloud_fn = self._connection.register(stateful_bench, "stateful_bench")
        if cloud_fn is None:
            raise RuntimeError("Failed to register stateful_bench with Cloudburst scheduler")

        success, error = self._connection.register_dag(
            "stateful_dag", ["stateful_bench"], []
        )
        if not success:
            raise RuntimeError(f"Failed to register stateful_dag: {error}")

        self._registered = True
        self.logging.info("Cloudburst function and DAG registered successfully")

    @staticmethod
    def typename() -> str:
        return "Cloudburst.LibraryTrigger"

    @staticmethod
    def trigger_type() -> Trigger.TriggerType:
        # Report as HTTP so perf_cost.py's trigger lookup finds us.
        # The actual invocation uses ZMQ via CloudburstConnection.
        return Trigger.TriggerType.HTTP

    def sync_invoke(self, payload: dict) -> ExecutionResult:
        self._ensure_registered()

        request_id = payload.get("request_id", uuid.uuid4().hex)

        begin = datetime.now()
        result = self._connection.call_dag(
            "stateful_dag",
            {"stateful_bench": [request_id]},
            direct_response=True,
        )
        end = datetime.now()

        exec_result = ExecutionResult.from_times(begin, end)

        if isinstance(result, dict):
            exec_result.request_id = result.get("request_id", request_id)
            exec_result.parse_benchmark_output(result)
        else:
            # If result is not a dict, treat as opaque output
            exec_result.request_id = request_id
            exec_result.output = {"raw_result": str(result)}

        return exec_result

    def async_invoke(self, payload: dict) -> concurrent.futures.Future:
        pool = concurrent.futures.ThreadPoolExecutor()
        fut = pool.submit(self.sync_invoke, payload)
        return fut

    def serialize(self) -> dict:
        return {
            "type": "Library",
            "scheduler_ip": self._scheduler_ip,
            "client_ip": self._client_ip,
            "local": self._local,
            "cloudburst_path": self._cloudburst_path,
        }

    @staticmethod
    def deserialize(obj: dict) -> Trigger:
        return LibraryTrigger(
            obj["scheduler_ip"],
            obj["client_ip"],
            obj.get("local", True),
            obj.get("cloudburst_path", ""),
        )


class CloudburstFunction(Function):
    def __init__(
        self,
        scheduler_ip: str,
        function_name: str,
        benchmark: str,
        code_package_hash: str,
        config: FunctionConfig,
    ):
        super().__init__(benchmark, function_name, code_package_hash, config)
        self._scheduler_ip = scheduler_ip
        self._function_name = function_name

    @property
    def scheduler_ip(self) -> str:
        return self._scheduler_ip

    @property
    def function_name(self) -> str:
        return self._function_name

    @staticmethod
    def typename() -> str:
        return "Cloudburst.CloudburstFunction"

    def serialize(self) -> dict:
        return {
            **super().serialize(),
            "scheduler_ip": self._scheduler_ip,
            "function_name": self._function_name,
        }

    @staticmethod
    def deserialize(cached_config: dict) -> "CloudburstFunction":
        cfg = FunctionConfig.deserialize(cached_config["config"])
        return CloudburstFunction(
            cached_config["scheduler_ip"],
            cached_config["function_name"],
            cached_config["benchmark"],
            cached_config["hash"],
            cfg,
        )

    def stop(self):
        pass
