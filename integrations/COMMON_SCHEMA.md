# Cross-integration common metric schema

All integration normalizers (`*_to_common_schema.py`) emit the same column set so outputs can be concatenated and compared across Cloudburst, Boki, baseline, and orchestrator paths.

## Canonical columns

Defined in [`common_schema/fields.py`](common_schema/fields.py).

### Core performance

- `system`, `system_variant`, `consistency_model`, `deployment_mode`, `benchmark_name`, `metric_scope`
- `num_requests`, `sample_size`
- `throughput_ops_per_sec`, `throughput_per_resource_unit`
- `latency_mean_ms`, `latency_p50_ms`, `latency_p95_ms`, `latency_p99_ms`, `latency_min_ms`, `latency_max_ms`
- `total_computation_time_sec`, `cost_per_million_ops_usd`
- `source_file`

### Resource + state dimensions

- `resource_cpu_avg`, `resource_memory_avg_mb`
- `state_size_kb`, `state_placement`
- `convergence_time_ms`

### Reliability

- `error_rate`, `timeout_rate`, `failed_requests`
- `http_2xx_count`, `http_4xx_count`, `http_5xx_count`, `http_other_count`

### Elasticity

- `cold_start_latency_worker_ms`, `cold_start_latency_server_ms`
- `scale_up_time_ms`, `scale_down_time_ms`
- `scaling_scope`
- `scale_to_zero_supported`, `scale_to_zero_reactivation_ms`
- `scaling_granularity`
- `instrumented_provisioning`
- `scaling_group_placement`

### Per-key + disaggregation + consistency probes

- `key_id`, `key_group`, `keys_count`, `key_skew_ratio`
- `state_units_per_function_n`, `concurrent_functions_per_state_unit_n`
- `txn_abort_rate`, `txn_conflict_rate`, `txn_retry_count`, `txn_commit_latency_ms`
- `stale_read_rate`, `read_after_write_violation_rate`

## Nullability and units

- Latencies are in **milliseconds** in normalized outputs.
- Throughput is **operations per second**.
- Rates are fractions in `[0, 1]`.
- Any metric unavailable from a system or run remains `null` (do not invent values).

## Adapter pattern

Each integration owns:

1. Raw artifacts in `integrations/<name>/results/raw/` (or custom run dir).
2. A collector that builds `collected_metrics.json`.
3. A normalizer `<name>_to_common_schema.py` that emits JSONL/CSV using [`common_schema/io.py`](common_schema/io.py).

Shared HTTP helpers:

- [`common_schema/http_latency_bench.py`](common_schema/http_latency_bench.py)
- [`common_schema/collect_http_run.py`](common_schema/collect_http_run.py)
- [`common_schema/latency_stats.py`](common_schema/latency_stats.py)
- [`common_schema/event_metrics.py`](common_schema/event_metrics.py) for optional `events.jsonl` sidecars.

### Lightweight event sidecar (optional)

Collectors may ingest `events.jsonl` from run directories. Minimal envelope:

- required: `schema_version`, `run_id`, `system`, `ts_ms`, `event_type`, `ok`
- optional: `function_id`, `state_unit_id`, `key_id`, `request_id`, `latency_ms`, `error_code`, `attributes`

System-specific extensions should live under `attributes` (for example `attributes.crdt.*` in Cloudburst).

## Limitations and possible issues

- Detailed per-system notes: [`OBSERVABILITY_LIMITS.md`](OBSERVABILITY_LIMITS.md).
- **Cloudburst observability**: internal scheduler/placement events are not always exposed in benchmark logs; some elasticity fields require sidecar telemetry or Cloudburst code changes.
- **Boki observability**: scaling-group and worker/server split metrics may require additional gateway/runtime instrumentation; HTTP logs alone are insufficient.
- **Baseline observability**: Lambda/Redis resource and scaling metrics typically require CloudWatch joins and careful time-window alignment.
- **Cross-system comparability**: same field names can still represent different collection methods; keep per-integration method notes to avoid misleading comparisons.
- **Probe overhead**: additional consistency/per-key instrumentation can change latency distributions and must be reported in experiment metadata.

## Adding or changing columns

1. Update this file and [`common_schema/fields.py`](common_schema/fields.py) together.
2. Update all adapters (`baseline`, `boki`, `cloudburst`, `orchestrator`) so output shape stays identical.
3. Run schema validation on produced JSONL/CSV before merging runs.
