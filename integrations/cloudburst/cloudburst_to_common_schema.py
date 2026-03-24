#!/usr/bin/env python3

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Dict, List

_INTEGRATIONS = Path(__file__).resolve().parent.parent
if str(_INTEGRATIONS) not in sys.path:
    sys.path.insert(0, str(_INTEGRATIONS))

from common_schema.io import write_csv, write_jsonl  # noqa: E402


def sec_to_ms(value):
    if value is None:
        return None
    return float(value) * 1000.0


def metric_value(values, metadata, key):
    if key in values:
        return values.get(key)
    return metadata.get(key)


def normalize_record(input_path: str, payload: dict) -> List[Dict]:
    metadata = payload.get("metadata", {})
    metrics = payload.get("metrics", {})

    system = payload.get("system", "cloudburst")
    consistency_model = metadata.get("consistency_model", "unknown")
    deployment_mode = metadata.get("deployment_mode", "cloudburst-local")
    benchmark_name = metadata.get("benchmark_name", "unknown")
    num_requests = metadata.get("num_requests")
    total_time = payload.get("total_computation_time_sec")

    out: List[Dict] = []
    for scope, values in metrics.items():
        throughput = values.get("throughput_ops_per_sec")
        throughput_per_resource = None
        if throughput is not None:
            # Placeholder resource unit proxy: one local runtime instance.
            throughput_per_resource = float(throughput)

        out.append(
            {
                "system": system,
                "system_variant": "cloudburst",
                "consistency_model": consistency_model,
                "deployment_mode": deployment_mode,
                "benchmark_name": benchmark_name,
                "metric_scope": scope,
                "num_requests": num_requests,
                "sample_size": values.get("sample_size"),
                "throughput_ops_per_sec": throughput,
                "latency_mean_ms": sec_to_ms(values.get("mean")),
                "latency_p50_ms": sec_to_ms(values.get("p50")),
                "latency_p95_ms": sec_to_ms(values.get("p95")),
                "latency_p99_ms": sec_to_ms(values.get("p99")),
                "latency_min_ms": sec_to_ms(values.get("min")),
                "latency_max_ms": sec_to_ms(values.get("max")),
                "total_computation_time_sec": total_time,
                "cost_per_million_ops_usd": metric_value(values, metadata, "cost_per_million_ops_usd"),
                "throughput_per_resource_unit": throughput_per_resource,
                "resource_cpu_avg": metric_value(values, metadata, "resource_cpu_avg"),
                "resource_memory_avg_mb": metric_value(values, metadata, "resource_memory_avg_mb"),
                "state_size_kb": metric_value(values, metadata, "state_size_kb"),
                "state_placement": metric_value(values, metadata, "state_placement"),
                "convergence_time_ms": metric_value(values, metadata, "convergence_time_ms"),
                "error_rate": metric_value(values, metadata, "error_rate"),
                "timeout_rate": metric_value(values, metadata, "timeout_rate"),
                "failed_requests": metric_value(values, metadata, "failed_requests"),
                "http_2xx_count": metric_value(values, metadata, "http_2xx_count"),
                "http_4xx_count": metric_value(values, metadata, "http_4xx_count"),
                "http_5xx_count": metric_value(values, metadata, "http_5xx_count"),
                "http_other_count": metric_value(values, metadata, "http_other_count"),
                "cold_start_latency_worker_ms": metric_value(values, metadata, "cold_start_latency_worker_ms"),
                "cold_start_latency_server_ms": metric_value(values, metadata, "cold_start_latency_server_ms"),
                "scale_up_time_ms": metric_value(values, metadata, "scale_up_time_ms"),
                "scale_down_time_ms": metric_value(values, metadata, "scale_down_time_ms"),
                "scaling_scope": metric_value(values, metadata, "scaling_scope"),
                "scale_to_zero_supported": metric_value(values, metadata, "scale_to_zero_supported"),
                "scale_to_zero_reactivation_ms": metric_value(values, metadata, "scale_to_zero_reactivation_ms"),
                "scaling_granularity": metric_value(values, metadata, "scaling_granularity"),
                "instrumented_provisioning": metric_value(values, metadata, "instrumented_provisioning"),
                "scaling_group_placement": metric_value(values, metadata, "scaling_group_placement"),
                "key_id": metric_value(values, metadata, "key_id"),
                "key_group": metric_value(values, metadata, "key_group"),
                "keys_count": metric_value(values, metadata, "keys_count"),
                "key_skew_ratio": metric_value(values, metadata, "key_skew_ratio"),
                "state_units_per_function_n": metric_value(values, metadata, "state_units_per_function_n"),
                "concurrent_functions_per_state_unit_n": metric_value(
                    values, metadata, "concurrent_functions_per_state_unit_n"
                ),
                "txn_abort_rate": metric_value(values, metadata, "txn_abort_rate"),
                "txn_conflict_rate": metric_value(values, metadata, "txn_conflict_rate"),
                "txn_retry_count": metric_value(values, metadata, "txn_retry_count"),
                "txn_commit_latency_ms": metric_value(values, metadata, "txn_commit_latency_ms"),
                "stale_read_rate": metric_value(values, metadata, "stale_read_rate"),
                "read_after_write_violation_rate": metric_value(
                    values, metadata, "read_after_write_violation_rate"
                ),
                "source_file": str(Path(input_path).resolve()),
            }
        )
    return out


def main():
    parser = argparse.ArgumentParser(description="Convert Cloudburst collected metrics to common schema JSONL/CSV.")
    parser.add_argument(
        "--input-glob",
        required=True,
        help="Glob pattern for collected_metrics.json files",
    )
    parser.add_argument("--output-jsonl", required=True, help="Output JSONL path")
    parser.add_argument("--output-csv", required=True, help="Output CSV path")
    args = parser.parse_args()

    files = sorted(glob.glob(args.input_glob))
    if not files:
        raise RuntimeError(f"No files matched glob: {args.input_glob}")

    rows: List[Dict] = []
    for f in files:
        payload = json.loads(Path(f).read_text(encoding="utf-8"))
        rows.extend(normalize_record(f, payload))

    write_jsonl(Path(args.output_jsonl), rows)
    write_csv(Path(args.output_csv), rows)

    print(f"Normalized {len(files)} run files into {len(rows)} rows")
    print(f"JSONL: {args.output_jsonl}")
    print(f"CSV:   {args.output_csv}")


if __name__ == "__main__":
    main()
