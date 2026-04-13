#!/usr/bin/env python3
"""
Latency drilldown: decompose client-side latency into components.

For each invocation, breaks down:
    ClientLatency = NetworkRTT + FunctionExecution + ServerlessOverhead

Where:
    NetworkRTT         = http_startup (pycurl PRETRANSFER_TIME, TCP SYN-ACK roundtrip)
    FunctionExecution  = benchmark    (end - begin from function response)
    ServerlessOverhead = client - benchmark - http_startup
                         (API GW routing, container dispatch, ZMQ/ZK overhead, serialization)

Usage:
    uv run python3 scripts/latency_drilldown.py results/run2/
    uv run python3 scripts/latency_drilldown.py results/run2/ --csv drilldown.csv
    uv run python3 scripts/latency_drilldown.py results/run2/lambda/latency-dist.json
"""

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


# ── Helpers ──────────────────────────────────────────────────────────────────

def percentile(values: list, p: float) -> float:
    s = sorted(values)
    idx = int(p / 100.0 * len(s))
    return s[min(idx, len(s) - 1)]


def fmt_us(val_us: float) -> str:
    """Format microseconds as human-readable string."""
    if val_us >= 1_000_000:
        return f"{val_us / 1_000_000:.2f}s"
    elif val_us >= 1_000:
        return f"{val_us / 1_000:.1f}ms"
    else:
        return f"{val_us:.0f}us"


# ── Data extraction ──────────────────────────────────────────────────────────

SYSTEM_NAMES = {
    "lambda": "Lambda",
    "boki": "Boki",
    "cloudburst": "Cloudburst",
}


def detect_system(path: str) -> str:
    """Detect system name from file path."""
    path_lower = path.lower()
    for key in SYSTEM_NAMES:
        if key in path_lower:
            return SYSTEM_NAMES[key]
    return "Unknown"


def detect_experiment(path: str) -> str:
    """Detect experiment type from filename."""
    basename = Path(path).stem
    return basename


def extract_drilldown(path: str) -> List[dict]:
    """Extract per-invocation latency decomposition from a results JSON."""
    with open(path) as f:
        data = json.load(f)

    inv_key = "_invocations" if "_invocations" in data else "invocations"
    invocations = data.get(inv_key, {})

    system = detect_system(path)
    experiment = detect_experiment(path)
    entries = []

    for func_name, func_invocations in invocations.items():
        for req_id, result in func_invocations.items():
            times = result.get("times", {})
            stats = result.get("stats", {})

            client_us = times.get("client", 0)
            benchmark_us = times.get("benchmark", 0)
            http_startup_s = times.get("http_startup", 0)

            # Convert http_startup from seconds to microseconds
            network_rtt_us = http_startup_s * 1_000_000

            # Serverless overhead = everything not network or function execution
            overhead_us = client_us - benchmark_us - network_rtt_us

            # Sanity: overhead should be positive; if not, flag it
            if overhead_us < 0:
                overhead_us = 0

            entries.append({
                "system": system,
                "experiment": experiment,
                "request_id": req_id,
                "is_cold": stats.get("cold_start", False),
                "client_us": client_us,
                "network_rtt_us": round(network_rtt_us, 1),
                "function_exec_us": benchmark_us,
                "overhead_us": round(overhead_us, 1),
                # Percentages
                "pct_network": round(network_rtt_us / client_us * 100, 1) if client_us > 0 else 0,
                "pct_function": round(benchmark_us / client_us * 100, 1) if client_us > 0 else 0,
                "pct_overhead": round(overhead_us / client_us * 100, 1) if client_us > 0 else 0,
            })

    return entries


# ── Summary statistics ───────────────────────────────────────────────────────

def summarize(entries: List[dict]) -> dict:
    """Compute P50 summary for a group of entries."""
    if not entries:
        return {}

    warm = [e for e in entries if not e["is_cold"]]
    if not warm:
        warm = entries  # fallback if all cold

    return {
        "count": len(warm),
        "cold_starts": sum(1 for e in entries if e["is_cold"]),
        "client_p50": percentile([e["client_us"] for e in warm], 50),
        "network_rtt_p50": percentile([e["network_rtt_us"] for e in warm], 50),
        "function_exec_p50": percentile([e["function_exec_us"] for e in warm], 50),
        "overhead_p50": percentile([e["overhead_us"] for e in warm], 50),
        "pct_network_p50": percentile([e["pct_network"] for e in warm], 50),
        "pct_function_p50": percentile([e["pct_function"] for e in warm], 50),
        "pct_overhead_p50": percentile([e["pct_overhead"] for e in warm], 50),
    }


# ── Reporting ────────────────────────────────────────────────────────────────

def print_system_summary(system: str, experiments: Dict[str, List[dict]]):
    """Print a summary table for one system across all experiments."""
    print(f"\n{'=' * 72}")
    print(f"  {system}")
    print(f"{'=' * 72}")
    print(f"  {'Experiment':<28} {'Client P50':>12} {'Network':>12} {'Function':>12} {'Overhead':>12}")
    print(f"  {'-' * 28} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 12}")

    for exp_name in sorted(experiments.keys()):
        entries = experiments[exp_name]
        s = summarize(entries)
        if not s:
            continue

        print(
            f"  {exp_name:<28} "
            f"{fmt_us(s['client_p50']):>12} "
            f"{fmt_us(s['network_rtt_p50']):>12} "
            f"{fmt_us(s['function_exec_p50']):>12} "
            f"{fmt_us(s['overhead_p50']):>12}"
        )

    # Print percentage breakdown for latency-dist (the canonical experiment)
    if "latency-dist" in experiments:
        s = summarize(experiments["latency-dist"])
        if s:
            print(f"\n  Latency-dist breakdown (P50, warm only):")
            print(f"    Network RTT:         {s['pct_network_p50']:5.1f}%  ({fmt_us(s['network_rtt_p50'])})")
            print(f"    Function execution:  {s['pct_function_p50']:5.1f}%  ({fmt_us(s['function_exec_p50'])})")
            print(f"    Serverless overhead: {s['pct_overhead_p50']:5.1f}%  ({fmt_us(s['overhead_p50'])})")


def print_comparison_table(all_entries: Dict[str, Dict[str, List[dict]]]):
    """Print a cross-system comparison table for latency-dist."""
    print(f"\n{'=' * 72}")
    print(f"  Cross-System Comparison (latency-dist, P50, warm invocations)")
    print(f"{'=' * 72}")
    print(f"  {'Component':<22} {'Lambda':>14} {'Boki':>14} {'Cloudburst':>14}")
    print(f"  {'-' * 22} {'-' * 14} {'-' * 14} {'-' * 14}")

    summaries = {}
    for system in ["Lambda", "Boki", "Cloudburst"]:
        if system in all_entries and "latency-dist" in all_entries[system]:
            summaries[system] = summarize(all_entries[system]["latency-dist"])

    if not summaries:
        print("  No latency-dist data found.")
        return

    rows = [
        ("Client E2E", "client_p50"),
        ("Network RTT", "network_rtt_p50"),
        ("Function execution", "function_exec_p50"),
        ("Serverless overhead", "overhead_p50"),
    ]
    for label, key in rows:
        vals = []
        for sys in ["Lambda", "Boki", "Cloudburst"]:
            if sys in summaries:
                vals.append(fmt_us(summaries[sys][key]))
            else:
                vals.append("—")
        print(f"  {label:<22} {vals[0]:>14} {vals[1]:>14} {vals[2]:>14}")

    # Percentage row
    print()
    pct_rows = [
        ("% Network", "pct_network_p50"),
        ("% Function", "pct_function_p50"),
        ("% Overhead", "pct_overhead_p50"),
    ]
    for label, key in pct_rows:
        vals = []
        for sys in ["Lambda", "Boki", "Cloudburst"]:
            if sys in summaries:
                vals.append(f"{summaries[sys][key]:.1f}%")
            else:
                vals.append("—")
        print(f"  {label:<22} {vals[0]:>14} {vals[1]:>14} {vals[2]:>14}")

    print(f"\n  Samples: ", end="")
    for sys in ["Lambda", "Boki", "Cloudburst"]:
        if sys in summaries:
            print(f"{sys}={summaries[sys]['count']} ", end="")
    print()


# ── CSV export ───────────────────────────────────────────────────────────────

def write_csv(all_flat: List[dict], output_path: str):
    """Write per-invocation drilldown to CSV."""
    if not all_flat:
        return

    fieldnames = [
        "system", "experiment", "request_id", "is_cold",
        "client_us", "network_rtt_us", "function_exec_us", "overhead_us",
        "pct_network", "pct_function", "pct_overhead",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_flat)

    print(f"\nCSV written to {output_path} ({len(all_flat)} rows)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Decompose client latency into Network RTT + Function Execution + Serverless Overhead"
    )
    parser.add_argument("path", help="Results JSON file or directory tree")
    parser.add_argument("--csv", help="Output CSV path")
    parser.add_argument(
        "--skip-placement", action="store_true",
        help="Skip placement-* experiments (Cloudburst-specific)"
    )
    args = parser.parse_args()

    path = Path(args.path)

    # Collect all JSON files
    json_files = []
    if path.is_file():
        json_files = [path]
    elif path.is_dir():
        json_files = sorted(path.glob("**/*.json"))
    else:
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    # Group: system -> experiment -> [entries]
    all_entries: Dict[str, Dict[str, List[dict]]] = {}
    all_flat: List[dict] = []

    for jf in json_files:
        if args.skip_placement and "placement" in jf.name:
            continue
        # Skip threaded duplicates (use the threaded version as canonical)
        if "-threaded" not in jf.name:
            threaded = jf.parent / (jf.stem + "-threaded.json")
            if threaded.exists():
                continue  # skip non-threaded, will process threaded version

        entries = extract_drilldown(str(jf))
        if not entries:
            continue

        system = entries[0]["system"]
        experiment = entries[0]["experiment"]

        if system not in all_entries:
            all_entries[system] = {}
        all_entries[system][experiment] = entries
        all_flat.extend(entries)

    # Print per-system summaries
    for system in ["Lambda", "Boki", "Cloudburst"]:
        if system in all_entries:
            print_system_summary(system, all_entries[system])

    # Print cross-system comparison
    print_comparison_table(all_entries)

    # CSV export
    if args.csv:
        write_csv(all_flat, args.csv)


if __name__ == "__main__":
    main()
