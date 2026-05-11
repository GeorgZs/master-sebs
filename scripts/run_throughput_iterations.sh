#!/usr/bin/env bash
set -euo pipefail

SEBS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_BASE="${SEBS_DIR}/results/throughput_runs"
KEY="/home/georg/Documents/KTH Studies/Master_Thesis/thesis-key.pem"
MODE="${1:-edge}"
N_RUNS=10
REPS=200
STATE_KB=64

# Edge endpoints
EDGE_LAMBDA="https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/"
EDGE_DURABLE="https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/durable"
EDGE_BOKI="http://13.62.19.126:8080/function/statefulBench"
EDGE_CLOUDBURST="http://13.51.167.107:8088/function/stateful_bench"
EDGE_RESTATE="http://51.21.220.121:8080/statefulBench/{key}/run"

# Cloud private endpoints
CLOUD_LAMBDA="https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/"
CLOUD_DURABLE="https://r8ea9hwc5i.execute-api.eu-north-1.amazonaws.com/durable"
CLOUD_BOKI="http://10.41.1.237:8080/function/statefulBench"
CLOUD_CLOUDBURST="http://10.30.1.32:8088/function/stateful_bench"
CLOUD_RESTATE="http://10.70.1.10:8080/statefulBench/{key}/run"

# Cloud SSH clients
SSH_BASELINE="ec2-user@51.20.91.32"
SSH_BOKI="ubuntu@13.53.71.50"
SSH_CLOUDBURST="ec2-user@16.171.55.22"
SSH_RESTATE="ubuntu@13.53.207.42"
SSH_OPTS="-i '$KEY' -o StrictHostKeyChecking=no -o ConnectTimeout=15"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

run_edge_system() {
    local system="$1" url="$2" run_n="$3"
    local out_dir="${RESULTS_BASE}/edge/run_${run_n}/${system}"
    mkdir -p "$out_dir"
    for c in 1 10 50 100; do
        local f="${out_dir}/throughput-c${c}.json"
        if [ -f "$f" ]; then continue; fi
        log "  edge $system c=$c run_$run_n"
        cd "$SEBS_DIR" && uv run python3 scripts/batch_invoke.py "$url" \
            --reps "$REPS" --concurrency "$c" --state-size-kb "$STATE_KB" \
            --output "$f" 2>/dev/null
    done
}

run_cloud_system() {
    local user_host="$1" system="$2" url="$3" run_n="$4" extra_env="${5:-}"
    local remote_dir="/tmp/tp_runs/run_${run_n}/${system}"
    local local_dir="${RESULTS_BASE}/cloud/run_${run_n}/${system}"
    mkdir -p "$local_dir"
    local existing; existing=$(ls "${local_dir}"/throughput-c*.json 2>/dev/null | wc -l) || true
    if [ "$existing" -ge 4 ]; then log "  skip cloud $system run_$run_n (done)"; return; fi

    log "  cloud $system run_$run_n"
    # sync batch_invoke.py
    scp -i "$KEY" -o StrictHostKeyChecking=no \
        "$SEBS_DIR/scripts/batch_invoke.py" "${user_host}:~/batch_invoke.py" > /dev/null 2>&1

    local remote_cmds="${extra_env}mkdir -p $remote_dir"
    for c in 1 10 50 100; do
        remote_cmds+=" && ${extra_env}python3 ~/batch_invoke.py '$url' --reps $REPS --concurrency $c --state-size-kb $STATE_KB --output $remote_dir/throughput-c${c}.json"
    done
    ssh -i "$KEY" -o StrictHostKeyChecking=no "$user_host" "$remote_cmds" > /dev/null 2>&1

    for c in 1 10 50 100; do
        scp -i "$KEY" -o StrictHostKeyChecking=no \
            "${user_host}:${remote_dir}/throughput-c${c}.json" \
            "${local_dir}/throughput-c${c}.json" > /dev/null 2>&1
    done
    log "  collected cloud $system run_$run_n"
}

run_edge() {
    for run_n in $(seq 1 $N_RUNS); do
        log "=== EDGE run $run_n/$N_RUNS ==="
        run_edge_system "lambda"        "$EDGE_LAMBDA"      "$run_n"
        run_edge_system "lambda-durable" "$EDGE_DURABLE"    "$run_n"
        run_edge_system "boki"          "$EDGE_BOKI"        "$run_n"
        run_edge_system "cloudburst"    "$EDGE_CLOUDBURST"  "$run_n"
        run_edge_system "restate"       "$EDGE_RESTATE"     "$run_n"
    done
}

run_cloud() {
    local CB_ENV='PYTHONPATH=/home/ec2-user/.local/lib/python3.9/site-packages '
    for run_n in $(seq 1 $N_RUNS); do
        run_cloud_system "$SSH_BASELINE" "lambda"         "$CLOUD_LAMBDA"      "$run_n" &
        run_cloud_system "$SSH_BASELINE" "lambda-durable" "$CLOUD_DURABLE"     "$run_n" &
        run_cloud_system "$SSH_BOKI"     "boki"           "$CLOUD_BOKI"        "$run_n" &
        run_cloud_system "$SSH_CLOUDBURST" "cloudburst"   "$CLOUD_CLOUDBURST"  "$run_n" "$CB_ENV" &
        run_cloud_system "$SSH_RESTATE"  "restate"        "$CLOUD_RESTATE"     "$run_n" &
        wait
        log "=== CLOUD run $run_n/$N_RUNS done ==="
    done
}

case "$MODE" in
    edge)  log "Running EDGE 10-run iterations"; run_edge ;;
    cloud) log "Running CLOUD 10-run iterations"; run_cloud ;;
    *) echo "Usage: $0 [edge|cloud]"; exit 1 ;;
esac
log "Done. Results in ${RESULTS_BASE}/${MODE}/"
