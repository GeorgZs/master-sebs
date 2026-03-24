# Cloudburst Integration Track

This folder runs Cloudburst as a native runtime track, separate from SeBS Lambda deployment.

## Why separate

Cloudburst has its own scheduler/executor/runtime model. Running it only as a Lambda wrapper can be useful for smoke tests, but not for faithful runtime evaluation.

## Contents

- `deploy_cloudburst.sh`: start/stop/status local Cloudburst runtime from `base_systems/cloudburst`.
- `deploy_cloudburst_aws.sh`: Terraform wrapper for AWS native Cloudburst infrastructure in `aws/`.
- `run_cloudburst_bench.sh`: execute Cloudburst benchmark client and capture raw logs + metadata.
- `collect_cloudburst_results.py`: parse benchmark logs into structured JSON metrics.
- `cloudburst_to_common_schema.py`: convert collected metrics into common JSONL/CSV for cross-system comparisons.
- `common_schema_columns.md`: normalization field contract (canonical list: [`../COMMON_SCHEMA.md`](../COMMON_SCHEMA.md)).
- `results/raw/.gitkeep`: raw run outputs.
- `results/normalized/.gitkeep`: normalized outputs.

## Paths

Default Cloudburst source root:

- `../base_systems/cloudburst` relative to `master-sebs/`

Override with:

- `CB_ROOT=/absolute/path/to/cloudburst`

## Quickstart

From `master-sebs/`:

```bash
./integrations/cloudburst/deploy_cloudburst.sh start
./integrations/cloudburst/run_cloudburst_bench.sh composition 200
./integrations/cloudburst/deploy_cloudburst.sh status
./integrations/cloudburst/deploy_cloudburst.sh stop
```

Optional sidecar ingestion (for CRDT/disaggregation/elasticity enrichments):

```bash
CB_EVENTS_JSONL='/path/to/cloudburst-events.jsonl' \
CB_TELEMETRY_JSON='/path/to/cloudburst-telemetry.json' \
CB_EXTRA_METRICS_JSON='/path/to/cloudburst-extra-metrics.json' \
./integrations/cloudburst/run_cloudburst_bench.sh composition 200
```

AWS infrastructure track:

```bash
./integrations/cloudburst/deploy_cloudburst_aws.sh init
./integrations/cloudburst/deploy_cloudburst_aws.sh plan
./integrations/cloudburst/deploy_cloudburst_aws.sh apply
./integrations/cloudburst/deploy_cloudburst_aws.sh output
```

Normalize all collected runs:

```bash
python3 integrations/cloudburst/cloudburst_to_common_schema.py \
  --input-glob "integrations/cloudburst/results/raw/*/collected_metrics.json" \
  --output-jsonl integrations/cloudburst/results/normalized/cloudburst_common.jsonl \
  --output-csv integrations/cloudburst/results/normalized/cloudburst_common.csv
```

## Notes

- This scaffold assumes local-mode Cloudburst execution.
- Cost/resource columns are left empty unless you enrich with external telemetry.
- Consistency mode is tracked via metadata (`CONSISTENCY_MODEL` env var in runner).
