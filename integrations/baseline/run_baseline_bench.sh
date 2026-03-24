#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_ROOT="${OUT_ROOT:-${SCRIPT_DIR}/results/raw}"
COMMON_DIR="${SCRIPT_DIR}/../common_schema"

NUM_REQUESTS="${1:-50}"
BASELINE_API_URL="${BASELINE_API_URL:-}"
HTTP_METHOD="${HTTP_METHOD:-POST}"
BODY_JSON="${BODY_JSON:-{\"key\":\"baseline:bench\"}}"
BENCHMARK_NAME="${BENCHMARK_NAME:-http-redis-counter}"
CONSISTENCY_MODEL="${CONSISTENCY_MODEL:-normal}"
DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-aws-lambda-redis}"
BASELINE_EVENTS_JSONL="${BASELINE_EVENTS_JSONL:-}"
BASELINE_TELEMETRY_JSON="${BASELINE_TELEMETRY_JSON:-}"

if [[ -z "${BASELINE_API_URL}" ]]; then
  echo "Set BASELINE_API_URL to your API Gateway invoke URL (terraform output http_api_endpoint)." >&2
  exit 1
fi

mkdir -p "${OUT_ROOT}"
RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="baseline-${BENCHMARK_NAME}-n${NUM_REQUESTS}-${RUN_TS}"
RUN_DIR="${OUT_ROOT}/${RUN_ID}"
mkdir -p "${RUN_DIR}"

cat > "${RUN_DIR}/metadata.json" <<EOF
{
  "run_id": "${RUN_ID}",
  "system": "baseline",
  "system_variant": "lambda-redis",
  "benchmark_name": "${BENCHMARK_NAME}",
  "num_requests": ${NUM_REQUESTS},
  "baseline_api_url": "${BASELINE_API_URL}",
  "consistency_model": "${CONSISTENCY_MODEL}",
  "deployment_mode": "${DEPLOYMENT_MODE}",
  "started_at_utc": "${RUN_TS}"
}
EOF

echo "Baseline HTTP bench: ${NUM_REQUESTS} requests to ${BASELINE_API_URL}"
echo "Run dir: ${RUN_DIR}"

python3 "${COMMON_DIR}/http_latency_bench.py" \
  --run-dir "${RUN_DIR}" \
  --url "${BASELINE_API_URL}" \
  --count "${NUM_REQUESTS}" \
  --method "${HTTP_METHOD}" \
  --body-json "${BODY_JSON}"

# Optional: ingest sidecars (if external collectors emit them).
if [[ -n "${BASELINE_EVENTS_JSONL}" && -f "${BASELINE_EVENTS_JSONL}" ]]; then
  cp -f "${BASELINE_EVENTS_JSONL}" "${RUN_DIR}/events.jsonl"
  echo "Copied baseline events sidecar: ${BASELINE_EVENTS_JSONL}"
fi
if [[ -n "${BASELINE_TELEMETRY_JSON}" && -f "${BASELINE_TELEMETRY_JSON}" ]]; then
  cp -f "${BASELINE_TELEMETRY_JSON}" "${RUN_DIR}/telemetry.json"
  echo "Copied baseline telemetry sidecar: ${BASELINE_TELEMETRY_JSON}"
fi

python3 "${SCRIPT_DIR}/collect_baseline_results.py" \
  --run-dir "${RUN_DIR}" \
  --out "${RUN_DIR}/collected_metrics.json"

echo "Completed baseline run: ${RUN_ID}"
echo "Collected metrics: ${RUN_DIR}/collected_metrics.json"
