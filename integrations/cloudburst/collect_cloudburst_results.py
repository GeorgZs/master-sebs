#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_INTEGRATIONS = Path(__file__).resolve().parent.parent
if str(_INTEGRATIONS) not in sys.path:
    sys.path.insert(0, str(_INTEGRATIONS))

from common_schema.event_metrics import derive_event_metrics, load_event_records, merge_metric_overrides  # noqa: E402


LATENCY_BLOCK_RE = re.compile(
    r"(?P<ident>[A-Z0-9_]+)\s+LATENCY:\n"
    r"\tsample size:\s+(?P<sample_size>\d+)\n"
    r"\tTHROUGHPUT:\s+(?P<throughput>[0-9.]+)\n"
    r"\tmean:\s+(?P<mean>[0-9.]+),\s+median:\s+(?P<median>[0-9.]+)\n"
    r"\tmin/max:\s+\((?P<min>[0-9.]+),\s+(?P<max>[0-9.]+)\)\n"
    r"\tp25/p75:\s+\((?P<p25>[0-9.]+),\s+(?P<p75>[0-9.]+)\)\n"
    r"\tp5/p95:\s+\((?P<p5>[0-9.]+),\s+(?P<p95>[0-9.]+)\)\n"
    r"\tp1/p99:\s+\((?P<p1>[0-9.]+),\s+(?P<p99>[0-9.]+)\)",
    re.MULTILINE,
)

TOTAL_TIME_RE = re.compile(r"Total computation time:\s*(?P<total>[0-9.]+)")


def parse_total_computation_time(text: str) -> Optional[float]:
    match = TOTAL_TIME_RE.search(text)
    if not match:
        return None
    return float(match.group("total"))


def parse_latency_blocks(text: str) -> Dict[str, dict]:
    metrics: Dict[str, dict] = {}
    for match in LATENCY_BLOCK_RE.finditer(text):
        ident = match.group("ident")
        metrics[ident] = {
            "sample_size": int(match.group("sample_size")),
            "throughput_ops_per_sec": float(match.group("throughput")),
            "mean": float(match.group("mean")),
            "p50": float(match.group("median")),
            "p95": float(match.group("p95")),
            "p99": float(match.group("p99")),
            "min": float(match.group("min")),
            "max": float(match.group("max")),
            "p25": float(match.group("p25")),
            "p75": float(match.group("p75")),
            "p5": float(match.group("p5")),
            "p1": float(match.group("p1")),
        }
    return metrics


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_optional_telemetry(run_dir: Path) -> Dict[str, Any]:
    for name in ("telemetry.json", "extra_metrics.json"):
        p = run_dir / name
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
            if isinstance(raw, dict):
                return raw
    return {}


def _enrich_metrics(metrics: Dict[str, dict], metadata: Dict[str, Any], telemetry: Dict[str, Any]) -> None:
    fields = {**metadata, **telemetry}
    for scope in metrics:
        block = metrics[scope]
        block["error_rate"] = _safe_float(fields.get("error_rate"))
        block["timeout_rate"] = _safe_float(fields.get("timeout_rate"))
        block["failed_requests"] = _safe_int(fields.get("failed_requests"))
        block["http_2xx_count"] = _safe_int(fields.get("http_2xx_count"))
        block["http_4xx_count"] = _safe_int(fields.get("http_4xx_count"))
        block["http_5xx_count"] = _safe_int(fields.get("http_5xx_count"))
        block["http_other_count"] = _safe_int(fields.get("http_other_count"))
        block["state_size_kb"] = _safe_float(fields.get("state_size_kb"))
        block["state_placement"] = fields.get("state_placement")
        block["convergence_time_ms"] = _safe_float(fields.get("convergence_time_ms"))
        block["resource_cpu_avg"] = _safe_float(fields.get("resource_cpu_avg"))
        block["resource_memory_avg_mb"] = _safe_float(fields.get("resource_memory_avg_mb"))
        block["cost_per_million_ops_usd"] = _safe_float(fields.get("cost_per_million_ops_usd"))
        block["cold_start_latency_worker_ms"] = _safe_float(fields.get("cold_start_latency_worker_ms"))
        block["cold_start_latency_server_ms"] = _safe_float(fields.get("cold_start_latency_server_ms"))
        block["scale_up_time_ms"] = _safe_float(fields.get("scale_up_time_ms"))
        block["scale_down_time_ms"] = _safe_float(fields.get("scale_down_time_ms"))
        block["scaling_scope"] = fields.get("scaling_scope")
        block["scale_to_zero_supported"] = fields.get("scale_to_zero_supported")
        block["scale_to_zero_reactivation_ms"] = _safe_float(fields.get("scale_to_zero_reactivation_ms"))
        block["scaling_granularity"] = fields.get("scaling_granularity")
        block["instrumented_provisioning"] = fields.get("instrumented_provisioning")
        block["scaling_group_placement"] = fields.get("scaling_group_placement")
        block["keys_count"] = _safe_int(fields.get("keys_count"))
        block["key_skew_ratio"] = _safe_float(fields.get("key_skew_ratio"))
        block["key_id"] = fields.get("key_id")
        block["key_group"] = fields.get("key_group")
        block["state_units_per_function_n"] = _safe_int(fields.get("state_units_per_function_n"))
        block["concurrent_functions_per_state_unit_n"] = _safe_int(fields.get("concurrent_functions_per_state_unit_n"))
        block["txn_abort_rate"] = _safe_float(fields.get("txn_abort_rate"))
        block["txn_conflict_rate"] = _safe_float(fields.get("txn_conflict_rate"))
        block["txn_retry_count"] = _safe_int(fields.get("txn_retry_count"))
        block["txn_commit_latency_ms"] = _safe_float(fields.get("txn_commit_latency_ms"))
        block["stale_read_rate"] = _safe_float(fields.get("stale_read_rate"))
        block["read_after_write_violation_rate"] = _safe_float(fields.get("read_after_write_violation_rate"))


def main():
    parser = argparse.ArgumentParser(description="Collect Cloudburst benchmark metrics from run logs.")
    parser.add_argument("--run-dir", required=True, help="Run directory containing metadata.json and client_stdout.log")
    parser.add_argument("--out", required=True, help="Output JSON file path")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    metadata_file = run_dir / "metadata.json"
    stdout_file = run_dir / "client_stdout.log"

    if not metadata_file.exists():
        raise RuntimeError(f"Missing metadata file: {metadata_file}")
    if not stdout_file.exists():
        raise RuntimeError(f"Missing client log file: {stdout_file}")

    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    stdout_text = stdout_file.read_text(encoding="utf-8", errors="replace")

    telemetry = _load_optional_telemetry(run_dir)
    metrics = parse_latency_blocks(stdout_text)
    _enrich_metrics(metrics, metadata, telemetry)
    event_metrics = derive_event_metrics(load_event_records(run_dir))
    for scope in metrics:
        merge_metric_overrides(metrics[scope], event_metrics)

    parsed = {
        "system": "cloudburst",
        "metadata": metadata,
        "source": {
            "run_dir": str(run_dir.resolve()),
            "client_stdout_log": str(stdout_file.resolve()),
        },
        "unit_assumptions": {
            "latency_time_unit": "seconds",
            "throughput_unit": "operations/second",
        },
        "total_computation_time_sec": parse_total_computation_time(stdout_text),
        "metrics": metrics,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote collected metrics to {out_path}")


if __name__ == "__main__":
    main()
