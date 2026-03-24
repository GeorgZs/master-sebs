# Boki Integration Track

This folder provides a native Boki integration path under `master-sebs/integrations/`.
It is separate from the SeBS Lambda deployment path in `benchmarks/900.stateful/boki-shared-log`.

## Contents

- `deploy_boki.sh`: local Boki build/start/stop/status wrapper using `base_systems/boki`.
- `deploy_boki_aws.sh`: Terraform wrapper for Boki AWS infrastructure in `aws/`.
- `aws/`: EC2/VPC/IAM scaffold for Boki roles (`zookeeper`, `controller`, `sequencer`, `storage`, `engine`, `gateway`, `client`).
- `common_schema_columns.md`: shared schema contract for Boki metrics.
- `run_boki_bench.sh`: HTTP repeat client + `collect_boki_results.py` (set `BOKI_HTTP_URL`).
- `collect_boki_results.py` / `boki_to_common_schema.py`: raw run → `collected_metrics.json` → common JSONL/CSV.

## Paths

Default Boki source root:

- `../base_systems/boki` relative to `master-sebs/`

Override with:

- `BOKI_ROOT=/absolute/path/to/boki`

## Quickstart (Local)

From `master-sebs/`:

```bash
./integrations/boki/deploy_boki.sh build
./integrations/boki/deploy_boki.sh start
./integrations/boki/deploy_boki.sh status
./integrations/boki/deploy_boki.sh stop
```

Common local overrides:

```bash
ZK_HOST=127.0.0.1:2181 \
SEQUENCER_IDS=101,102 \
STORAGE_IDS=201,202 \
ENGINE_IDS=301,302 \
FUNC_CONFIG_FILE=/abs/path/to/func_config.json \
./integrations/boki/deploy_boki.sh start
```

## Quickstart (AWS Terraform)

```bash
./integrations/boki/deploy_boki_aws.sh init
./integrations/boki/deploy_boki_aws.sh plan
./integrations/boki/deploy_boki_aws.sh apply
./integrations/boki/deploy_boki_aws.sh output
```

Destroy:

```bash
./integrations/boki/deploy_boki_aws.sh destroy
```

## HTTP bench → common schema

After the gateway is reachable, set the full URL (including path if needed):

```bash
BOKI_HTTP_URL='http://GATEWAY_IP:8080/' HTTP_METHOD=GET ./integrations/boki/run_boki_bench.sh 50
python3 integrations/boki/boki_to_common_schema.py \
  --input-glob 'integrations/boki/results/raw/*/collected_metrics.json' \
  --output-jsonl integrations/boki/results/normalized/boki_common.jsonl \
  --output-csv integrations/boki/results/normalized/boki_common.csv
```

Optional sidecar ingestion (for disaggregation/runtime metrics):

```bash
BOKI_HTTP_URL='http://GATEWAY_IP:8080/' \
BOKI_EVENTS_JSONL='/path/to/boki-events.jsonl' \
BOKI_TELEMETRY_JSON='/path/to/boki-telemetry.json' \
./integrations/boki/run_boki_bench.sh 50
```

## Notes

- Terraform is a deployment scaffold for repeatable Boki-native experiments, not a full production hardening profile.
- User-data templates generate role start scripts at `/opt/boki/start-<role>.sh` and can auto-build/auto-start if enabled.
- ZooKeeper is provisioned on a dedicated EC2 node via Docker (`zookeeper:3.9`) by default.
