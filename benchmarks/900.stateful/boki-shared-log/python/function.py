"""
DEAD CODE — This Python stub is NOT deployed to Boki.

Boki's shared log API (BokiStore, BokiQueue in slib/lib.go) is Go-only.
The real Boki benchmark is a Go binary registered with the Boki Launcher
and lives in master-boki/benchmarks/stateful/.  SeBS sends HTTP requests
to the Boki gateway; the Go function handles log operations and returns
a JSON response matching the SeBS ExecutionResult format.

This file exists only as a SeBS directory placeholder.  Do not fix its
response format — it will never be invoked.
"""

import hashlib
import time


def _to_bytes(value):
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return str(value).encode("utf-8")


def handler(event):
    raise NotImplementedError(
        "Boki functions are Go binaries, not Python. "
        "See master-boki/benchmarks/stateful/ for the real implementation."
    )

    begin = time.perf_counter_ns()

    payload = event.get("payload", "")
    payload_hash = hashlib.sha256(_to_bytes(payload)).hexdigest()
    ops = max(1, int(event.get("ops", 1)))
    state_size_kb = max(0, int(event.get("state_size_kb", 0)))

    # Lightweight synthetic workload placeholder for custom stateful systems.
    acc = 0
    for idx in range(min(ops * 64, 20000)):
        acc = (acc + idx + state_size_kb + len(payload_hash)) % 1000003

    duration_us = int((time.perf_counter_ns() - begin) / 1000)

    return {
        "result": {
            "ok": True,
            "system": event.get("system", "unknown"),
            "workload": event.get("workload", "default"),
            "payload_sha256": payload_hash,
            "accumulator": acc,
        },
        "measurement": {
            "compute_time": duration_us,
            "workload_ops": ops,
            "state_size_kb": state_size_kb,
        },
    }
