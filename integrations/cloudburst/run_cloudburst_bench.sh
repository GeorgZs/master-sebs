#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_SEBS_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CB_ROOT="${CB_ROOT:-${MASTER_SEBS_ROOT}/../base_systems/cloudburst}"
OUT_ROOT="${OUT_ROOT:-${SCRIPT_DIR}/results/raw}"

BENCHMARK_NAME="${1:-composition}"
NUM_REQUESTS="${2:-100}"
FUNCTION_ELB="${FUNCTION_ELB:-127.0.0.1}"
SCHEDULER_IP="${SCHEDULER_IP:-127.0.0.1}"
CONSISTENCY_MODEL="${CONSISTENCY_MODEL:-normal}"
DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-cloudburst-local}"
CB_EVENTS_JSONL="${CB_EVENTS_JSONL:-}"
CB_TELEMETRY_JSON="${CB_TELEMETRY_JSON:-}"
CB_EXTRA_METRICS_JSON="${CB_EXTRA_METRICS_JSON:-}"

if [[ ! -d "${CB_ROOT}" ]]; then
  echo "Cloudburst root not found: ${CB_ROOT}" >&2
  exit 1
fi

mkdir -p "${OUT_ROOT}"

RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID="cloudburst-${BENCHMARK_NAME}-n${NUM_REQUESTS}-${RUN_TS}"
RUN_DIR="${OUT_ROOT}/${RUN_ID}"
mkdir -p "${RUN_DIR}"

cat > "${RUN_DIR}/metadata.json" <<EOF
{
  "run_id": "${RUN_ID}",
  "system": "cloudburst",
  "benchmark_name": "${BENCHMARK_NAME}",
  "num_requests": ${NUM_REQUESTS},
  "function_elb": "${FUNCTION_ELB}",
  "scheduler_ip": "${SCHEDULER_IP}",
  "consistency_model": "${CONSISTENCY_MODEL}",
  "deployment_mode": "${DEPLOYMENT_MODE}",
  "cloudburst_root": "${CB_ROOT}",
  "started_at_utc": "${RUN_TS}"
}
EOF

echo "Running Cloudburst benchmark '${BENCHMARK_NAME}' (${NUM_REQUESTS} requests)"
echo "Run dir: ${RUN_DIR}"

(
  cd "${CB_ROOT}"
  export PYTHONPATH="${CB_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
  python3 cloudburst/client/run_benchmark.py \
    "${BENCHMARK_NAME}" \
    "${FUNCTION_ELB}" \
    "${NUM_REQUESTS}" \
    "${SCHEDULER_IP}"
) 2>&1 | tee "${RUN_DIR}/client_stdout.log"

for f in log_benchmark.txt log_trigger.txt; do
  if [[ -f "${CB_ROOT}/${f}" ]]; then
    cp -f "${CB_ROOT}/${f}" "${RUN_DIR}/${f}"
  fi
done

# Optional: ingest runtime-emitted sidecars from Cloudburst/Anna deployment.
if [[ -n "${CB_EVENTS_JSONL}" && -f "${CB_EVENTS_JSONL}" ]]; then
  cp -f "${CB_EVENTS_JSONL}" "${RUN_DIR}/events.jsonl"
  echo "Copied Cloudburst events sidecar: ${CB_EVENTS_JSONL}"
fi
if [[ -n "${CB_TELEMETRY_JSON}" && -f "${CB_TELEMETRY_JSON}" ]]; then
  cp -f "${CB_TELEMETRY_JSON}" "${RUN_DIR}/telemetry.json"
  echo "Copied Cloudburst telemetry sidecar: ${CB_TELEMETRY_JSON}"
fi
if [[ -n "${CB_EXTRA_METRICS_JSON}" && -f "${CB_EXTRA_METRICS_JSON}" ]]; then
  cp -f "${CB_EXTRA_METRICS_JSON}" "${RUN_DIR}/extra_metrics.json"
  echo "Copied Cloudburst extra metrics sidecar: ${CB_EXTRA_METRICS_JSON}"
fi

python3 "${SCRIPT_DIR}/collect_cloudburst_results.py" \
  --run-dir "${RUN_DIR}" \
  --out "${RUN_DIR}/collected_metrics.json"

echo "Completed Cloudburst run: ${RUN_ID}"
echo "Collected metrics: ${RUN_DIR}/collected_metrics.json"
