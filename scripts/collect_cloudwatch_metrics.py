#!/usr/bin/env python3
"""
Collect CloudWatch metrics for EC2 instances during an experiment window.

Usage:
    python3 scripts/collect_cloudwatch_metrics.py --start "2026-04-02T12:00:00Z" --end "2026-04-02T13:00:00Z" --output metrics.csv
    python3 scripts/collect_cloudwatch_metrics.py --last 30m --output metrics.csv
"""

import argparse
import csv
import json
import subprocess
from datetime import datetime, timedelta, timezone


NAMESPACE = "SeBS/StatefulBenchmark"
METRICS = ["cpu_usage_idle", "cpu_usage_user", "cpu_usage_system", "mem_used_percent", "mem_available", "net_bytes_sent", "net_bytes_recv"]
PERIOD = 10  # seconds (matches agent collection interval)
AWS_PROFILE = "sebs-admin"

# Instance ID to friendly name mapping
INSTANCE_NAMES = {
    # Boki
    "i-0e7abb3b37ecd1b40": "boki-infra",
    # Cloudburst
    "i-0e1fde6e88eee5e2b": "cb-scheduler",
    "i-0e12a41fe9274226b": "cb-anna",
    "i-0bfa86e6dbe9deeac": "cb-client",
}


def get_instance_ids():
    """Get all instance IDs reporting to our namespace."""
    cmd = [
        "aws", "--profile", AWS_PROFILE, "cloudwatch", "list-metrics",
        "--namespace", NAMESPACE,
        "--metric-name", "cpu_usage_idle",
        "--query", "Metrics[*].Dimensions[?Name=='InstanceId'].Value[]",
        "--output", "json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    ids = json.loads(result.stdout)
    # Flatten nested lists
    flat = set()
    for item in ids:
        if isinstance(item, list):
            flat.update(item)
        else:
            flat.add(item)
    return sorted(flat)


def get_metric(instance_id, metric_name, start, end):
    """Query a single metric for an instance."""
    cmd = [
        "aws", "--profile", AWS_PROFILE, "cloudwatch", "get-metric-statistics",
        "--namespace", NAMESPACE,
        "--metric-name", metric_name,
        "--dimensions", f"Name=InstanceId,Value={instance_id}",
        "--start-time", start.isoformat(),
        "--end-time", end.isoformat(),
        "--period", str(PERIOD),
        "--statistics", "Average",
        "--output", "json"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return {
        dp["Timestamp"]: dp["Average"]
        for dp in data.get("Datapoints", [])
    }


def main():
    parser = argparse.ArgumentParser(description="Collect CloudWatch metrics")
    parser.add_argument("--start", help="Start time (ISO 8601)")
    parser.add_argument("--end", help="End time (ISO 8601)")
    parser.add_argument("--last", help="Last N minutes (e.g., '30m', '1h')")
    parser.add_argument("--output", default="metrics.csv", help="Output CSV")
    args = parser.parse_args()

    if args.last:
        end = datetime.now(timezone.utc)
        val = args.last.rstrip("mh")
        if args.last.endswith("h"):
            start = end - timedelta(hours=int(val))
        else:
            start = end - timedelta(minutes=int(val))
    else:
        start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
        end = datetime.fromisoformat(args.end.replace("Z", "+00:00"))

    print(f"Collecting metrics from {start} to {end}")

    instance_ids = get_instance_ids()
    print(f"Found {len(instance_ids)} instances: {instance_ids}")

    rows = []
    for iid in instance_ids:
        name = INSTANCE_NAMES.get(iid, iid)
        print(f"  Querying {name} ({iid})...")
        for metric in METRICS:
            data = get_metric(iid, metric, start, end)
            for ts, val in sorted(data.items()):
                rows.append({
                    "timestamp": ts,
                    "instance_id": iid,
                    "instance_name": name,
                    "metric": metric,
                    "value": val,
                })

    if rows:
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "instance_id", "instance_name", "metric", "value"])
            writer.writeheader()
            writer.writerows(sorted(rows, key=lambda r: (r["timestamp"], r["instance_name"])))
        print(f"\n{len(rows)} data points written to {args.output}")
    else:
        print("No data points found")


if __name__ == "__main__":
    main()
