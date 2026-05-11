#!/usr/bin/env python3
"""
Generate throughput CI plots for cloud and edge benchmark runs.
"""

import json
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy import stats

# --- Configuration ---
BASE_DIR = "/home/georg/Documents/KTH Studies/Master_Thesis/master-sebs/results/throughput_runs"
OUT_DIR  = "/home/georg/Documents/KTH Studies/Master_Thesis/master-sebs/docs/plots"

SYSTEMS = ["lambda", "lambda-durable", "boki", "cloudburst", "restate"]
LABELS  = {
    "lambda":         "Lambda + Redis",
    "lambda-durable": "Lambda Durable",
    "boki":           "Boki",
    "cloudburst":     "Cloudburst + Anna",
    "restate":        "Restate",
}
COLORS  = {
    "lambda":         "#FF8C00",
    "lambda-durable": "#FF4444",
    "boki":           "#2196F3",
    "cloudburst":     "#4CAF50",
    "restate":        "#9C27B0",
}
CONCURRENCIES = [1, 10, 50, 100]
N_RUNS = 10
# t-critical for 95% CI, n=10, df=9
T_CRIT = stats.t.ppf(0.975, df=9)   # 2.2622...

# ------------------------------------------------------------------

def load_throughput(env: str, system: str, concurrency: int) -> list[float]:
    """Return list of throughput values (one per run) for env/system/concurrency."""
    values = []
    for run_i in range(1, N_RUNS + 1):
        path = os.path.join(BASE_DIR, env, f"run_{run_i}", system,
                            f"throughput-c{concurrency}.json")
        if not os.path.exists(path):
            print(f"  WARNING: missing {path}")
            continue
        with open(path) as f:
            d = json.load(f)
        begin = d["begin_time"]
        end   = d["end_time"]
        total = sum(len(recs) for recs in d["_invocations"].values())
        throughput = total / (end - begin)
        values.append(throughput)
    return values


def compute_stats(values: list[float]):
    """Return (mean, ci_half) using t-distribution CI."""
    arr = np.array(values)
    n   = len(arr)
    m   = arr.mean()
    se  = arr.std(ddof=1) / np.sqrt(n)
    ci  = T_CRIT * se
    return m, ci


def make_plot(env: str, title: str, out_filename: str):
    fig, ax = plt.subplots(figsize=(8, 5))

    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(f"  {'System':<22} {'Conc':>5}  {'Mean (inv/s)':>14}  {'±CI':>10}")
    print(f"  {'-'*55}")

    for system in SYSTEMS:
        means = []
        cis   = []
        for c in CONCURRENCIES:
            vals = load_throughput(env, system, c)
            if not vals:
                means.append(np.nan)
                cis.append(np.nan)
                continue
            m, ci = compute_stats(vals)
            means.append(m)
            cis.append(ci)
            print(f"  {LABELS[system]:<22} {c:>5}  {m:>14.2f}  ±{ci:>9.2f}")

        means = np.array(means)
        cis   = np.array(cis)

        ax.errorbar(
            CONCURRENCIES, means, yerr=cis,
            label=LABELS[system],
            color=COLORS[system],
            marker="o",
            linewidth=2,
            capsize=4,
            elinewidth=1.5,
            capthick=1.5,
        )

    # Axes
    ax.set_xticks(CONCURRENCIES)
    ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
    ax.set_xlabel("Concurrency (parallel invocations)", fontsize=12)
    ax.set_ylabel("Throughput (invocations/sec)", fontsize=12)
    ax.set_ylim(bottom=0)
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.legend(loc="upper left", fontsize=10)
    ax.grid(True, alpha=0.3)

    # Caption
    caption = ("200 invocations per run, 10 independent runs, "
               "error bars = 95% CI (t-distribution, n=10)")
    fig.text(0.5, -0.02, caption, ha="center", fontsize=9, color="#555555")

    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, out_filename)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Saved: {out_path}")


# ------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    make_plot(
        env="cloud",
        title="Throughput Scaling — Cloud (EC2 in-VPC)",
        out_filename="throughput_ci_cloud.png",
    )
    make_plot(
        env="edge",
        title="Throughput Scaling — Edge (laptop)",
        out_filename="throughput_ci_edge.png",
    )

    print("\nDone.")
