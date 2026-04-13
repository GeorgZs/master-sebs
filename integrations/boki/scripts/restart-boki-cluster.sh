#!/usr/bin/env bash
# Restart the full Boki cluster: Gateway → Engine → Launcher/Worker
# Run this ON the gateway node (or via: ssh gateway "bash /opt/boki/restart-all.sh")
#
# Startup order matters:
#   1. Gateway (engine connects TO gateway on startup)
#   2. Engine  (connects to gateway, registers in ZooKeeper)
#   3. Launcher + Worker (connects to engine via IPC)
#
# Prerequisites:
#   - ZooKeeper, Controller, Sequencer, Storage already running
#   - /faas/cmd/start already issued to controller (creates initial view)
#   - SSH key at $KEY for engine node access
#   - func_config.json at /opt/boki/func_config.json on gateway + engine
#   - Go benchmark binary at /opt/boki/benchmarks/stateful_bench on engine

set -euo pipefail

KEY="${BOKI_SSH_KEY:-/tmp/thesis-key.pem}"
ENGINE_IP="${BOKI_ENGINE_IP:-10.40.1.5}"
ZK_HOST="${BOKI_ZK_HOST:-10.40.1.82:2181}"
FUNC_CONFIG="${BOKI_FUNC_CONFIG:-/opt/boki/func_config.json}"
IPC_PATH="${BOKI_IPC_PATH:-/dev/shm/faas_ipc}"

echo '=== Killing everything ==='
ssh -i "$KEY" -o StrictHostKeyChecking=no "ec2-user@$ENGINE_IP" \
  'pkill -9 engine; pkill -9 launcher; pkill -9 stateful_bench' 2>/dev/null || true
pkill -9 gateway 2>/dev/null || true
sudo fuser -k 8080/tcp 2>/dev/null || true
sleep 2

echo '=== 1. Starting Gateway ==='
/opt/boki/boki/bin/release/gateway \
  --listen_iface=ens5 \
  --http_port=8080 \
  --grpc_port=50051 \
  --func_config_file="$FUNC_CONFIG" \
  --zookeeper_host="$ZK_HOST" \
  --zookeeper_root_path=/faas \
  --listen_addr=0.0.0.0 \
  </dev/null > /tmp/gateway.log 2>&1 & disown
sleep 5
pgrep gateway && echo 'GATEWAY_OK' || { echo 'GATEWAY_DEAD'; cat /tmp/gateway.log; exit 1; }

echo '=== 2. Starting Engine ==='
ssh -i "$KEY" "ec2-user@$ENGINE_IP" "mkdir -p $IPC_PATH; \
  /opt/boki/boki/bin/release/engine \
    --listen_iface=ens5 \
    --node_id=301 \
    --enable_shared_log=true \
    --root_path_for_ipc=$IPC_PATH \
    --func_config_file=$FUNC_CONFIG \
    --zookeeper_host=$ZK_HOST \
    --zookeeper_root_path=/faas \
    --listen_addr=$ENGINE_IP \
    </dev/null > /tmp/engine.log 2>&1 & disown"
sleep 5
ssh -i "$KEY" "ec2-user@$ENGINE_IP" \
  'pgrep engine && echo ENGINE_OK || { echo ENGINE_DEAD; tail -5 /tmp/engine.log; exit 1; }'

echo '=== 3. Starting Launcher + Worker ==='
ssh -i "$KEY" "ec2-user@$ENGINE_IP" "rm -f /tmp/boki-worker-output/*; \
  /opt/boki/boki/bin/release/launcher \
    --func_id=1 \
    --fprocess=/opt/boki/benchmarks/stateful_bench \
    --fprocess_mode=go \
    --root_path_for_ipc=$IPC_PATH \
    --fprocess_output_dir=/tmp/boki-worker-output \
    </dev/null > /tmp/launcher.log 2>&1 & disown"
sleep 5
ssh -i "$KEY" "ec2-user@$ENGINE_IP" \
  'pgrep launcher && echo LAUNCHER_OK || { echo LAUNCHER_DEAD; tail -5 /tmp/launcher.log; exit 1; }'
ssh -i "$KEY" "ec2-user@$ENGINE_IP" \
  'pgrep stateful_bench && echo WORKER_OK || { echo WORKER_DEAD; cat /tmp/boki-worker-output/statefulBench_worker_0.stderr 2>/dev/null; exit 1; }'

echo '=== All services up. Smoke test... ==='
curl -s http://127.0.0.1:8080/function/statefulBench \
  -H 'Content-Type: application/json' \
  -d '{"state_key":"test","state_size_kb":1,"ops":1}' \
  --max-time 15 -w '\nHTTP:%{http_code}\n' 2>&1
echo ''
echo '=== Worker log ==='
ssh -i "$KEY" "ec2-user@$ENGINE_IP" \
  'tail -5 /tmp/boki-worker-output/statefulBench_worker_0.stderr 2>/dev/null || echo "no log"'
