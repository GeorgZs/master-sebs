Shared Python package:

- `fields.py` — `COMMON_FIELDS`
- `io.py` — JSONL/CSV writers
- `latency_stats.py` — aggregate latency samples (seconds) into metric blocks
- `collect_http_run.py` — build `collected_metrics.json` from `http_latency_bench.py` run dirs
- `http_latency_bench.py` — CLI: repeated HTTP requests → `latency_samples.jsonl` + `timing.json`
- `event_metrics.py` — optional `events.jsonl` sidecar parsing (reliability/disaggregation/CRDT convergence rollups)

Minimal sidecar event envelope (`events.jsonl`, optional):

`schema_version`, `run_id`, `system`, `ts_ms`, `event_type`, `ok` (+ optional `function_id`, `state_unit_id`, `key_id`, `latency_ms`, `error_code`, `attributes`).

Spec: [`../COMMON_SCHEMA.md`](../COMMON_SCHEMA.md).
