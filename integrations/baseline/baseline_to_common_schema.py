#!/usr/bin/env python3
"""
Normalize baseline collected metrics (same JSON shape as Cloudburst collector) to common schema.
"""

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


def normalize_record(input_path: str, payload: dict) -> List[Dict]:
    metadata = payload.get("metadata", {})
    metrics = payload.get("metrics", {})

    system = payload.get("system", "baseline")
    consistency_model = metadata.get("consistency_model", "unknown")
    deployment_mode = metadata.get("deployment_mode", "aws-lambda-redis")
    benchmark_name = metadata.get("benchmark_name", "unknown")
    num_requests = metadata.get("num_requests")
    total_time = payload.get("total_computation_time_sec")
    system_variant = metadata.get("system_variant", "lambda-redis")

    out: List[Dict] = []
    for scope, values in metrics.items():
        throughput = values.get("throughput_ops_per_sec")
        throughput_per_resource = None
        if throughput is not None:
            throughput_per_resource = float(throughput)

        out.append(
            {
                "system": system,
                "system_variant": system_variant,
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
                "cost_per_million_ops_usd": None,
                "throughput_per_resource_unit": throughput_per_resource,
                "resource_cpu_avg": None,
                "resource_memory_avg_mb": None,
                "state_size_kb": None,
                "state_placement": None,
                "convergence_time_ms": None,
                "source_file": str(Path(input_path).resolve()),
            }
        )
    return out


def main():
    parser = argparse.ArgumentParser(description="Convert baseline collected metrics to common schema JSONL/CSV.")
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
