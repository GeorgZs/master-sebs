"""Build collected_metrics.json from http_latency_bench.py run directories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .event_metrics import derive_event_metrics, load_event_records, merge_metric_overrides
from .latency_stats import aggregate_latencies_seconds


def _load_sample_records(run_dir: Path) -> List[Dict[str, Any]]:
    path = run_dir / "latency_samples.jsonl"
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


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


def build_collected_metrics_from_run_dir(
    run_dir: Path,
    *,
    system: str,
    metric_scope: str = "HTTP_INVOKE",
) -> Dict[str, Any]:
    metadata_file = run_dir / "metadata.json"
    if not metadata_file.exists():
        raise RuntimeError(f"Missing metadata file: {metadata_file}")

    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    records = _load_sample_records(run_dir)
    ok_samples: List[float] = []
    status_2xx = 0
    status_4xx = 0
    status_5xx = 0
    status_other = 0
    timeout_count = 0
    failed_requests = 0
    for rec in records:
        ok = bool(rec.get("ok"))
        lat = _safe_float(rec.get("latency_sec"))
        if ok and lat is not None:
            ok_samples.append(lat)
        status = rec.get("http_status")
        if isinstance(status, int):
            if 200 <= status < 300:
                status_2xx += 1
            elif 400 <= status < 500:
                status_4xx += 1
            elif 500 <= status < 600:
                status_5xx += 1
            else:
                status_other += 1
        elif status is not None:
            status_other += 1
        if not ok:
            failed_requests += 1
            err = str(rec.get("error", "")).lower()
            if "timeout" in err:
                timeout_count += 1

    timing_file = run_dir / "timing.json"
    wall_sec: Optional[float] = None
    if timing_file.exists():
        timing = json.loads(timing_file.read_text(encoding="utf-8"))
        wall_sec = timing.get("wall_time_sec")
        if wall_sec is not None:
            wall_sec = float(wall_sec)

    metrics, _ = aggregate_latencies_seconds(ok_samples, wall_sec, scope=metric_scope)
    if metric_scope in metrics:
        block = metrics[metric_scope]
        total_n = len(records)
        block["failed_requests"] = failed_requests
        block["error_rate"] = (failed_requests / total_n) if total_n > 0 else None
        block["timeout_rate"] = (timeout_count / total_n) if total_n > 0 else None
        block["http_2xx_count"] = status_2xx
        block["http_4xx_count"] = status_4xx
        block["http_5xx_count"] = status_5xx
        block["http_other_count"] = status_other

        # Metadata-carried optional dimensions for elasticity/consistency/per-key axes.
        block["state_size_kb"] = _safe_float(metadata.get("state_size_kb"))
        block["state_placement"] = metadata.get("state_placement")
        block["convergence_time_ms"] = _safe_float(metadata.get("convergence_time_ms"))
        block["resource_cpu_avg"] = _safe_float(metadata.get("resource_cpu_avg"))
        block["resource_memory_avg_mb"] = _safe_float(metadata.get("resource_memory_avg_mb"))
        block["cost_per_million_ops_usd"] = _safe_float(metadata.get("cost_per_million_ops_usd"))
        block["cold_start_latency_worker_ms"] = _safe_float(metadata.get("cold_start_latency_worker_ms"))
        block["cold_start_latency_server_ms"] = _safe_float(metadata.get("cold_start_latency_server_ms"))
        block["scale_up_time_ms"] = _safe_float(metadata.get("scale_up_time_ms"))
        block["scale_down_time_ms"] = _safe_float(metadata.get("scale_down_time_ms"))
        block["scaling_scope"] = metadata.get("scaling_scope")
        block["scale_to_zero_supported"] = metadata.get("scale_to_zero_supported")
        block["scale_to_zero_reactivation_ms"] = _safe_float(metadata.get("scale_to_zero_reactivation_ms"))
        block["scaling_granularity"] = metadata.get("scaling_granularity")
        block["instrumented_provisioning"] = metadata.get("instrumented_provisioning")
        block["scaling_group_placement"] = metadata.get("scaling_group_placement")
        block["keys_count"] = _safe_int(metadata.get("keys_count"))
        block["key_skew_ratio"] = _safe_float(metadata.get("key_skew_ratio"))
        block["key_id"] = metadata.get("key_id")
        block["key_group"] = metadata.get("key_group")
        block["state_units_per_function_n"] = _safe_int(metadata.get("state_units_per_function_n"))
        block["concurrent_functions_per_state_unit_n"] = _safe_int(metadata.get("concurrent_functions_per_state_unit_n"))
        block["txn_abort_rate"] = _safe_float(metadata.get("txn_abort_rate"))
        block["txn_conflict_rate"] = _safe_float(metadata.get("txn_conflict_rate"))
        block["txn_retry_count"] = _safe_int(metadata.get("txn_retry_count"))
        block["txn_commit_latency_ms"] = _safe_float(metadata.get("txn_commit_latency_ms"))
        block["stale_read_rate"] = _safe_float(metadata.get("stale_read_rate"))
        block["read_after_write_violation_rate"] = _safe_float(metadata.get("read_after_write_violation_rate"))
        event_metrics = derive_event_metrics(load_event_records(run_dir))
        merge_metric_overrides(block, event_metrics)

    return {
        "system": system,
        "metadata": metadata,
        "source": {
            "run_dir": str(run_dir.resolve()),
            "latency_samples": str((run_dir / "latency_samples.jsonl").resolve()),
            "timing": str(timing_file.resolve()) if timing_file.exists() else None,
        },
        "unit_assumptions": {
            "latency_time_unit": "seconds",
            "throughput_unit": "operations/second",
        },
        "total_computation_time_sec": wall_sec,
        "metrics": metrics,
    }
