from typing import cast, Dict, List, Optional, Type, Tuple

import docker

from sebs.cache import Cache
from sebs.config import SeBSConfig
from sebs.storage.resources import SelfHostedSystemResources
from sebs.utils import LoggingHandlers
from sebs.cloudburst_provider.config import CloudburstConfig
from sebs.cloudburst_provider.function import CloudburstFunction, LibraryTrigger
from sebs.faas.function import Function, FunctionConfig, ExecutionResult, Trigger
from sebs.faas.system import System
from sebs.faas.config import Resources
from sebs.benchmark import Benchmark


class Cloudburst(System):
    """
    Cloudburst provider for SeBS.

    Cloudburst functions are pre-deployed on EC2 executors. This provider
    connects to the Cloudburst scheduler via ZMQ (CloudburstConnection),
    registers benchmark functions, and invokes them through the DAG API.
    It does NOT manage Cloudburst's lifecycle.
    """

    @staticmethod
    def name():
        return "cloudburst"

    @staticmethod
    def typename():
        return "Cloudburst"

    @staticmethod
    def function_type() -> "Type[Function]":
        return CloudburstFunction

    @property
    def config(self) -> CloudburstConfig:
        return self._config

    def __init__(
        self,
        sebs_config: SeBSConfig,
        config: CloudburstConfig,
        cache_client: Cache,
        docker_client: docker.client,
        logger_handlers: LoggingHandlers,
    ):
        super().__init__(
            sebs_config,
            cache_client,
            docker_client,
            SelfHostedSystemResources(
                "cloudburst", config, cache_client, docker_client, logger_handlers
            ),
        )
        self.logging_handlers = logger_handlers
        self._config = config

    def shutdown(self):
        super().shutdown()

    # Cloudburst functions are pre-deployed: packaging is a no-op

    def package_code(
        self,
        directory: str,
        language_name: str,
        language_version: str,
        architecture: str,
        benchmark: str,
        is_cached: bool,
        container_deployment: bool,
    ) -> Tuple[str, int, str]:
        return directory, 0, ""

    def create_function(
        self,
        code_package: Benchmark,
        func_name: str,
        container_deployment: bool,
        container_uri: str,
    ) -> "CloudburstFunction":
        function_cfg = FunctionConfig.from_benchmark(code_package)
        return CloudburstFunction(
            self._config.scheduler_ip,
            "stateful_bench",
            code_package.benchmark,
            code_package.hash,
            function_cfg,
        )

    def cached_function(self, function: Function):
        pass

    def update_function(
        self,
        function: Function,
        code_package: Benchmark,
        container_deployment: bool,
        container_uri: str,
    ):
        pass

    def update_function_configuration(self, function: Function, code_package: Benchmark):
        pass

    def create_trigger(self, func: Function, trigger_type: Trigger.TriggerType) -> Trigger:
        function = cast(CloudburstFunction, func)
        # perf_cost.py always requests HTTP triggers; we return a LibraryTrigger
        # that wraps CloudburstConnection via ZMQ. The trigger_type parameter is
        # accepted but ignored

        trigger = LibraryTrigger(
            self._config.scheduler_ip,
            self._config.client_ip,
            self._config.local,
            self._config.cloudburst_path,
        )
        trigger.logging_handlers = self.logging_handlers
        function.add_trigger(trigger)
        return trigger

    def download_metrics(
        self,
        function_name: str,
        start_time: int,
        end_time: int,
        requests: Dict[str, ExecutionResult],
        metrics: dict,
    ):
        pass

    def enforce_cold_start(self, functions: List[Function], code_package: Benchmark):
        raise NotImplementedError(
            "Cloudburst cold start requires restarting executor processes. "
            "Use SSH to restart executors manually."
        )

    @staticmethod
    def default_function_name(
        code_package: Benchmark, resources: Optional[Resources] = None
    ) -> str:
        return "cloudburst-{}-{}".format(
            code_package.benchmark,
            code_package.language_name,
        )

    def get_function(self, code_package: Benchmark, func_name: Optional[str] = None) -> Function:
        """
        Override to skip the code packaging/building pipeline.
        Cloudburst functions are pre-deployed on executors.
        """
        if not func_name:
            func_name = self.default_function_name(code_package)

        # Check cache for existing function
        functions = code_package.functions
        if functions and func_name in functions:
            try:
                function = self.function_type().deserialize(functions[func_name])
                self.cached_function(function)
                self.logging.info(f"Using cached Cloudburst function: {func_name}")
                return function
            except RuntimeError:
                self.logging.warning(f"Cached function {func_name} not available, recreating")

        # Create new function. Skip cache — no code package was built, so cache has no config.
        self.logging.info(
            f"Creating Cloudburst function {func_name} -> {self._config.scheduler_ip}"
        )
        function = self.create_function(code_package, func_name, False, "")
        return function
