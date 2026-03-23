# Baseline Integration Track

Minimal **stateful serverless baseline** on AWS: **Lambda** (automatic scaling) plus **ElastiCache for Redis**. Separate from Boki, Cloudburst, CRDT, and from SeBS benchmark definitions under `benchmarks/`.

## Contents

- `deploy_baseline_aws.sh`: Terraform wrapper for `aws/`.
- `aws/`: VPC, Redis, Lambda in VPC, HTTP API for invokes.
- `aws/build_lambda.sh`: installs `redis` into `lambda_package/` and copies the handler. Run before `terraform plan` / `apply`.
- `run_baseline_bench.sh`: drive HTTP invokes against `BASELINE_API_URL` (API Gateway), then collect metrics.
- `collect_baseline_results.py`: `latency_samples.jsonl` → `collected_metrics.json`.
- `baseline_to_common_schema.py`: → common JSONL/CSV ([`common_schema_columns.md`](common_schema_columns.md), [`../COMMON_SCHEMA.md`](../COMMON_SCHEMA.md)).

## Quickstart

From `master-sebs/`:

```bash
cd integrations/baseline/aws && ./build_lambda.sh && cd - 
./integrations/baseline/deploy_baseline_aws.sh init
./integrations/baseline/deploy_baseline_aws.sh apply
./integrations/baseline/deploy_baseline_aws.sh output
```

Copy `aws/terraform.tfvars.example` to `aws/terraform.tfvars` if you want non-defaults.

## Benchmark → common schema

After deploy, set `BASELINE_API_URL` to the `http_api_endpoint` output and run:

```bash
BASELINE_API_URL='https://....amazonaws.com/' ./integrations/baseline/run_baseline_bench.sh 100
python3 integrations/baseline/baseline_to_common_schema.py \
  --input-glob 'integrations/baseline/results/raw/*/collected_metrics.json' \
  --output-jsonl integrations/baseline/results/normalized/baseline_common.jsonl \
  --output-csv integrations/baseline/results/normalized/baseline_common.csv
```

## Notes

- Redis creation can take several minutes.
- This is a research scaffold, not a production hardening profile.
