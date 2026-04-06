#!/usr/bin/env python3
"""
Generate thesis comparison plots for all three stateful serverless systems.

Usage:
    cd master-sebs
    uv run python3 docs/plots/generate_plots.py
"""

import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# Paths
SCRIPT_DIR = Path(__file__).parent
RESULTS_DIR = SCRIPT_DIR.parent.parent / "results" / "run2"
OUT_DIR = SCRIPT_DIR / "out"
OUT_DIR.mkdir(exist_ok=True)

# Style
COLORS = {"Lambda + Redis": "#FF9900", "Boki": "#2196F3", "Cloudburst + Anna": "#4CAF50"}
SYSTEMS = list(COLORS.keys())
SYSTEM_DIRS = {"Lambda + Redis": "lambda", "Boki": "boki", "Cloudburst + Anna": "cloudburst"}

plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "legend.fontsize": 10,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.15,
})


def load_results(system_dir, filename):
    path = RESULTS_DIR / system_dir / filename
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    inv_key = "_invocations"
    invocations = list(data.get(inv_key, {}).values())
    if not invocations:
        return None
    results = list(invocations[0].values())
    duration = data.get("end_time", 0) - data.get("begin_time", 1)
    return results, duration


def extract_client_latencies(results):
    return [r["times"]["client"] / 1000 for r in results if not r.get("stats", {}).get("failure")]


def extract_write_latencies(results):
    return [r["output"]["measurement"]["state_write_lat_us"]
            for r in results if "measurement" in r.get("output", {})]


def extract_read_latencies(results):
    return [r["output"]["measurement"]["state_read_lat_us"]
            for r in results if "measurement" in r.get("output", {})]


# ── Plot 1: Throughput Scaling Curve ──

def plot_throughput_scaling():
    fig, ax = plt.subplots(figsize=(7, 4.5))
    concurrencies = [1, 10, 50, 100]

    for name in SYSTEMS:
        sdir = SYSTEM_DIRS[name]
        throughputs = []
        concs_available = []
        for c in concurrencies:
            data = load_results(sdir, f"throughput-c{c}.json")
            if data:
                results, duration = data
                valid = [r for r in results if not r.get("stats", {}).get("failure")]
                tp = len(valid) / duration if duration > 0 else 0
                throughputs.append(tp)
                concs_available.append(c)
        ax.plot(concs_available, throughputs, "o-", color=COLORS[name], label=name,
                linewidth=2, markersize=7)

    ax.set_xlabel("Concurrency (number of parallel invocations)")
    ax.set_ylabel("Throughput (invocations/sec)")
    ax.set_title("Throughput Scaling (64KB state)")
    ax.set_xscale("log")
    ax.set_xticks(concurrencies)
    ax.get_xaxis().set_major_formatter(ticker.ScalarFormatter())
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.savefig(OUT_DIR / "01_throughput_scaling.png")
    plt.close(fig)
    print("  01_throughput_scaling.png")


# ── Plot 2: Latency CDF ──

def plot_latency_cdf():
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for name in SYSTEMS:
        sdir = SYSTEM_DIRS[name]
        data = load_results(sdir, "latency-dist.json")
        if not data:
            continue
        results, _ = data
        lats = sorted(extract_client_latencies(results))
        percentiles = np.arange(1, len(lats) + 1) / len(lats) * 100
        ax.plot(lats, percentiles, color=COLORS[name], label=name, linewidth=1.5)

    ax.set_xlabel("Client Latency (ms)")
    ax.set_ylabel("Percentile (%)")
    ax.set_title("Latency Distribution (CDF)")
    ax.set_ylim(0, 100)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(OUT_DIR / "02_latency_cdf.png")
    plt.close(fig)
    print("  02_latency_cdf.png")


# ── Plot 3: Latency Percentiles (Grouped Bar) ──

def plot_latency_percentiles():
    fig, ax = plt.subplots(figsize=(7, 4.5))
    percentile_labels = ["P50", "P95", "P99"]
    percentile_vals = [50, 95, 99]
    x = np.arange(len(percentile_labels))
    width = 0.25

    for i, name in enumerate(SYSTEMS):
        sdir = SYSTEM_DIRS[name]
        data = load_results(sdir, "latency-dist.json")
        if not data:
            continue
        results, _ = data
        lats = sorted(extract_client_latencies(results))
        n = len(lats)
        vals = [lats[min(int(p / 100 * n), n - 1)] for p in percentile_vals]
        ax.bar(x + i * width, vals, width, label=name, color=COLORS[name])

    ax.set_xlabel("Percentile")
    ax.set_ylabel("Client Latency (ms)")
    ax.set_title("Client Latency Percentiles (64KB state)")
    ax.set_xticks(x + width)
    ax.set_xticklabels(percentile_labels)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.savefig(OUT_DIR / "03_latency_percentiles.png")
    plt.close(fig)
    print("  03_latency_percentiles.png")


# ── Plot 4: Write vs Read Latency Breakdown ──

def plot_write_read_breakdown():
    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(SYSTEMS))
    width = 0.35

    writes = []
    reads = []
    for name in SYSTEMS:
        sdir = SYSTEM_DIRS[name]
        data = load_results(sdir, "latency-dist.json")
        if not data:
            writes.append(0)
            reads.append(0)
            continue
        results, _ = data
        wl = sorted(extract_write_latencies(results))
        rl = sorted(extract_read_latencies(results))
        writes.append(wl[len(wl) // 2] / 1000)  # us -> ms
        reads.append(rl[len(rl) // 2] / 1000)

    bars1 = ax.bar(x - width / 2, writes, width, label="Write P50", color=[COLORS[s] for s in SYSTEMS], alpha=0.9)
    bars2 = ax.bar(x + width / 2, reads, width, label="Read P50", color=[COLORS[s] for s in SYSTEMS], alpha=0.5,
                   hatch="//")

    ax.set_ylabel("Latency (ms)")
    ax.set_title("State Write vs Read Latency (P50, 64KB)")
    ax.set_xticks(x)
    ax.set_xticklabels(SYSTEMS, fontsize=10)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    # Add value labels — show us for very small values
    for bar, raw_us in zip(bars1, [w * 1000 for w in writes]):
        h = bar.get_height()
        label = f"{h:.1f}ms" if h >= 0.1 else f"{raw_us:.0f}us"
        ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, max(h, 0.05)),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
    for bar, raw_us in zip(bars2, [r * 1000 for r in reads]):
        h = bar.get_height()
        label = f"{h:.1f}ms" if h >= 0.1 else f"{raw_us:.0f}us*"
        ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, max(h, 0.05)),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)

    # Caveat footnote for Boki read
    ax.annotate("* Engine-cached read latency.",
                xy=(0.5, -0.15), xycoords="axes fraction", ha="center", fontsize=7,
                style="italic", color="gray")

    fig.savefig(OUT_DIR / "04_write_read_breakdown.png")
    plt.close(fig)
    print("  04_write_read_breakdown.png")


# ── Plot 5: State Size Impact ──

def plot_state_size_impact():
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sizes = [1, 64, 512]
    size_files = {1: "statesize-1kb.json", 64: "statesize-64kb.json", 512: "statesize-512kb.json"}

    for name in SYSTEMS:
        sdir = SYSTEM_DIRS[name]
        write_p50s = []
        sizes_available = []
        for sz in sizes:
            data = load_results(sdir, size_files[sz])
            if not data:
                continue
            results, _ = data
            wl = sorted(extract_write_latencies(results))
            write_p50s.append(wl[len(wl) // 2] / 1000)  # us -> ms
            sizes_available.append(sz)
        ax.plot(sizes_available, write_p50s, "o-", color=COLORS[name], label=name,
                linewidth=2, markersize=7)

    ax.set_xlabel("State Size (KB)")
    ax.set_ylabel("Write Latency P50 (ms)")
    ax.set_title("State Size Impact on Write Latency")
    ax.set_xscale("log")
    ax.set_xticks(sizes)
    ax.get_xaxis().set_major_formatter(ticker.ScalarFormatter())
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(OUT_DIR / "05_state_size_impact.png")
    plt.close(fig)
    print("  05_state_size_impact.png")


# ── Plot 6: Cold Start Comparison ──

def plot_cold_start():
    fig, ax = plt.subplots(figsize=(6, 4))

    # Lambda: extract cold starts from latency-dist data
    lambda_cold = []
    data = load_results("lambda", "latency-dist.json")
    if data:
        results, _ = data
        for r in results:
            if r.get("stats", {}).get("cold_start"):
                lambda_cold.append(r["times"]["client"] / 1000)

    # Boki: from cold start CSV
    boki_cold = []
    csv_path = RESULTS_DIR / "cold_start" / "cold_start_boki_run2.csv"
    if csv_path.exists():
        with open(csv_path) as f:
            for line in f:
                if line.startswith("boki,"):
                    parts = line.strip().split(",")
                    boki_cold.append(float(parts[4]))

    # Cloudburst: executor bootstrap time (documented as ~180s for fresh instance)
    cb_cold = [180000]  # 3 minutes for ASG bootstrap

    labels = []
    values = []
    colors = []

    if lambda_cold:
        labels.append("Lambda\n(container)")
        values.append(np.median(lambda_cold))
        colors.append(COLORS["Lambda + Redis"])
    if boki_cold:
        labels.append("Boki\n(engine restart)")
        values.append(np.median(boki_cold))
        colors.append(COLORS["Boki"])
    labels.append("Cloudburst\n(executor bootstrap)")
    values.append(np.median(cb_cold))
    colors.append(COLORS["Cloudburst + Anna"])

    bars = ax.bar(labels, values, color=colors, width=0.5)
    ax.set_ylabel("Cold Start Latency (ms)")
    ax.set_title("Cold Start Latency Comparison")
    ax.set_yscale("log")
    ax.grid(True, alpha=0.3, axis="y")

    for bar, val in zip(bars, values):
        label = f"{val:.0f}ms" if val < 10000 else f"{val/1000:.0f}s"
        ax.annotate(label, xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 5), textcoords="offset points", ha="center", fontsize=9)

    fig.savefig(OUT_DIR / "06_cold_start.png")
    plt.close(fig)
    print("  06_cold_start.png")


# ── Plot 7: Cost per Invocation ──

def plot_cost():
    fig, ax = plt.subplots(figsize=(6, 4))

    # EC2 hourly rates (eu-north-1)
    # Boki: c5.2xlarge ($0.388/hr infra) + 2x c5.xlarge ($0.194/hr engine) = $0.776/hr
    # Cloudburst: t3.medium scheduler ($0.0464) + 3x t3.medium executor ($0.0464) + t3.medium anna ($0.0464) + t3.small client ($0.0232) = ~$0.255/hr
    boki_hourly = 0.776
    cb_hourly = 0.255
    lambda_per_invoke = 0.0000166667  # per GB-second, 256MB = 0.25GB

    # Get throughput at c=10 for fair comparison
    costs = {}
    for name, sdir, hourly in [("Boki", "boki", boki_hourly), ("Cloudburst + Anna", "cloudburst", cb_hourly)]:
        data = load_results(sdir, "throughput-c10.json")
        if data:
            results, duration = data
            valid = [r for r in results if not r.get("stats", {}).get("failure")]
            tp = len(valid) / duration if duration > 0 else 1
            cost_per_1k = (hourly / 3600 / tp) * 1000
            costs[name] = cost_per_1k

    # Lambda: use median execution time from latency-dist (~50ms = 0.05s at 256MB)
    lambda_data = load_results("lambda", "throughput-c10.json")
    if lambda_data:
        results, _ = lambda_data
        exec_times = [r["times"]["client"] / 1e6 for r in results if not r.get("stats", {}).get("failure")]
        median_exec_s = sorted(exec_times)[len(exec_times) // 2]
        lambda_cost_per_invoke = median_exec_s * 0.25 * lambda_per_invoke  # GB-seconds * price
        costs["Lambda + Redis"] = lambda_cost_per_invoke * 1000

    labels = list(costs.keys())
    vals = [costs[l] for l in labels]
    bar_colors = [COLORS[l] for l in labels]

    bars = ax.bar(labels, vals, color=bar_colors, width=0.5)
    ax.set_ylabel("Cost per 1000 Invocations (USD)")
    ax.set_title("Cost per Unit Work (at concurrency = 10)")
    ax.grid(True, alpha=0.3, axis="y")

    for bar, val in zip(bars, vals):
        ax.annotate(f"${val:.4f}", xy=(bar.get_x() + bar.get_width() / 2, val),
                    xytext=(0, 5), textcoords="offset points", ha="center", fontsize=9)

    fig.savefig(OUT_DIR / "07_cost_per_invocation.png")
    plt.close(fig)
    print("  07_cost_per_invocation.png")


# ── Plot 8: Resource Usage During Experiment ──

def plot_resource_usage():
    csv_path = RESULTS_DIR / "cloudwatch_metrics.csv"
    if not csv_path.exists():
        print("  08_resource_usage.png — SKIPPED (no cloudwatch_metrics.csv)")
        return

    import csv
    from datetime import datetime

    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        print("  08_resource_usage.png — SKIPPED (empty CSV)")
        return

    # Group by instance, use friendly names
    instances = {}
    for row in rows:
        iid = row["instance_name"] if row["instance_name"] != row["instance_id"] else row["instance_id"][:12]
        if iid not in instances:
            instances[iid] = {"cpu": [], "mem": []}
        metric = row["metric"]
        ts = row["timestamp"]
        val = float(row["value"])
        if metric == "cpu_usage_user":
            instances[iid]["cpu"].append((ts, val))
        elif metric == "mem_used_percent":
            instances[iid]["mem"].append((ts, val))

    # Select key instances: one per role
    priority = ["boki-infra", "boki-engine-1", "boki-engine-2",
                "cb-scheduler", "cb-anna", "cb-executor-1", "cb-executor-2", "cb-executor-3",
                "cb-client"]
    selected = [iid for iid in priority if iid in instances][:6]
    # Add any unnamed ones if we have space
    for iid in instances:
        if iid not in selected and len(selected) < 6:
            selected.append(iid)

    if not selected:
        print("  08_resource_usage.png — SKIPPED (no instances)")
        return

    # Distinct colors per instance — contrasting within each system group
    INSTANCE_COLORS = {
        "boki-infra":    "#1565C0",  # dark blue
        "boki-engine-1": "#42A5F5",  # medium blue
        "boki-engine-2": "#90CAF9",  # light blue
        "cb-scheduler":  "#2E7D32",  # dark green
        "cb-anna":       "#E65100",  # dark orange (stands out from green)
        "cb-executor-1": "#66BB6A",  # medium green
        "cb-executor-2": "#A5D6A7",  # light green
        "cb-executor-3": "#C8E6C9",  # very light green
        "cb-client":     "#FFC107",  # amber
    }

    def get_color(iid):
        return INSTANCE_COLORS.get(iid, "#999999")

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    for iid in selected:
        color = get_color(iid)
        ls = "-" if "infra" in iid or "scheduler" in iid or "anna" in iid else "--"

        cpu_data = sorted(instances[iid]["cpu"], key=lambda x: x[0])
        mem_data = sorted(instances[iid]["mem"], key=lambda x: x[0])

        if cpu_data:
            times = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t, _ in cpu_data]
            vals = [v for _, v in cpu_data]
            axes[0].plot(times, vals, label=iid, linewidth=1.2, alpha=0.8, color=color, linestyle=ls)

        if mem_data:
            times = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t, _ in mem_data]
            vals = [v for _, v in mem_data]
            axes[1].plot(times, vals, label=iid, linewidth=1.2, alpha=0.8, color=color, linestyle=ls)

    axes[0].set_ylabel("CPU User (%)")
    axes[0].set_title("Resource Usage over time (Boki = blue, Cloudburst = green)")
    axes[0].legend(fontsize=7, loc="upper right", ncol=2)
    axes[0].grid(True, alpha=0.3)

    axes[1].set_ylabel("Memory Used (%)")
    axes[1].set_xlabel("Time")
    axes[1].legend(fontsize=7, loc="upper right", ncol=2)
    axes[1].grid(True, alpha=0.3)

    fig.autofmt_xdate()
    fig.savefig(OUT_DIR / "08_resource_usage.png")
    plt.close(fig)
    print("  08_resource_usage.png")


# ── Plot 9: State Placement Impact ──

def plot_state_placement():
    fig, ax = plt.subplots(figsize=(7, 4.5))

    experiments = [
        ("Same key\n(1 Anna node)", "placement-same-key.json"),
        ("Unique keys\n(1 Anna node)", "placement-unique-keys.json"),
        ("Same key\n(2 Anna nodes)", "placement-same-key-multinode.json"),
        ("Unique keys\n(2 Anna nodes)", "placement-unique-keys-multinode.json"),
    ]

    labels = []
    write_vals = []
    read_vals = []

    for label, filename in experiments:
        data = load_results("cloudburst", filename)
        if not data:
            continue
        results, _ = data
        wl = sorted(extract_write_latencies(results))
        rl = sorted(extract_read_latencies(results))
        labels.append(label)
        write_vals.append(wl[len(wl) // 2] / 1000)
        read_vals.append(rl[len(rl) // 2] / 1000)

    if not labels:
        print("  09_state_placement.png — SKIPPED (no data)")
        return

    x = np.arange(len(labels))
    width = 0.35

    bars1 = ax.bar(x - width / 2, write_vals, width, label="Write P50",
                   color=COLORS["Cloudburst + Anna"], alpha=0.9)
    bars2 = ax.bar(x + width / 2, read_vals, width, label="Read P50",
                   color=COLORS["Cloudburst + Anna"], alpha=0.5, hatch="//")

    ax.set_ylabel("Latency (ms)")
    ax.set_title("State Placement Impact — Cloudburst + Anna KVS")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    for bar in bars1:
        h = bar.get_height()
        ax.annotate(f"{h:.1f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
    for bar in bars2:
        h = bar.get_height()
        ax.annotate(f"{h:.1f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)

    ax.annotate("No significant difference — Cloudburst does not cache state on executors.\n"
                "Co-location requires Anna replica placement near executors (not implemented).",
                xy=(0.5, -0.22), xycoords="axes fraction", ha="center", fontsize=7,
                style="italic", color="gray")

    fig.savefig(OUT_DIR / "09_state_placement.png")
    plt.close(fig)
    print("  09_state_placement.png")


# ── Main ──

if __name__ == "__main__":
    print(f"Generating plots from {RESULTS_DIR}")
    print(f"Output: {OUT_DIR}\n")

    plot_throughput_scaling()
    plot_latency_cdf()
    plot_latency_percentiles()
    plot_write_read_breakdown()
    plot_state_size_impact()
    plot_cold_start()
    plot_cost()
    plot_resource_usage()
    plot_state_placement()

    print(f"\nDone. {len(list(OUT_DIR.glob('*.png')))} plots generated.")
