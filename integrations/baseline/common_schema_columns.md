# Common schema columns (Baseline)

**Pipeline**

1. [`run_baseline_bench.sh`](run_baseline_bench.sh) (set `BASELINE_API_URL`) → `results/raw/<run>/latency_samples.jsonl`, `timing.json`, `metadata.json`.
2. [`collect_baseline_results.py`](collect_baseline_results.py) → `collected_metrics.json` (Cloudburst-compatible shape).
3. [`baseline_to_common_schema.py`](baseline_to_common_schema.py) → common JSONL/CSV.

**Canonical definitions:** [`../COMMON_SCHEMA.md`](../COMMON_SCHEMA.md) and [`../common_schema/fields.py`](../common_schema/fields.py).

Baseline-specific notes:

- Default `system_variant` in metadata: `lambda-redis` (override via `metadata.system_variant`).
- Default metric scope key: `HTTP_INVOKE`.
- Throughput uses successful samples only (`ok: true` in JSONL) over `timing.json` wall time.
