#!/usr/bin/env python3
"""Aggregate baseline HTTP bench outputs into collected_metrics.json (Cloudburst-compatible shape)."""

import argparse
import json
import sys
from pathlib import Path

_INTEGRATIONS = Path(__file__).resolve().parent.parent
if str(_INTEGRATIONS) not in sys.path:
    sys.path.insert(0, str(_INTEGRATIONS))

from common_schema.collect_http_run import build_collected_metrics_from_run_dir  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect baseline benchmark metrics from a run directory.")
    parser.add_argument("--run-dir", type=Path, required=True, help="Run directory with metadata + latency_samples")
    parser.add_argument("--out", type=Path, required=True, help="Output collected_metrics.json path")
    parser.add_argument(
        "--metric-scope",
        default="HTTP_INVOKE",
        help="Metric scope key for the aggregated block (default HTTP_INVOKE)",
    )
    args = parser.parse_args()

    payload = build_collected_metrics_from_run_dir(
        args.run_dir,
        system="baseline",
        metric_scope=args.metric_scope,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote collected metrics to {args.out}")


if __name__ == "__main__":
    main()
