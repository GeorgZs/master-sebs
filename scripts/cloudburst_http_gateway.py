#!/usr/bin/env python3
"""
HTTP→ZMQ gateway for Cloudburst.

Runs on the Cloudburst scheduler/client node and translates HTTP POST
requests into CloudburstConnection.call_dag() calls over ZMQ.

This enables uniform HTTP invocation across all 3 systems:
  - Lambda:     POST https://<api-gw>/
  - Boki:       POST http://<gateway>:8080/function/statefulBench
  - Cloudburst: POST http://<this-gateway>:8088/function/stateful_bench

Usage (on the scheduler/client EC2 node):
    export PYTHONPATH=/opt/cloudburst/cloudburst
    python3 cloudburst_http_gateway.py --scheduler-ip 10.30.1.117 --port 8088

Or with auto-detection:
    python3 cloudburst_http_gateway.py --port 8088
"""

import argparse
import json
import os
import sys
import time
import uuid
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# CloudburstConnection is imported lazily on first request
_connection = None
_registered = False


def get_connection(scheduler_ip, client_ip, local):
    global _connection
    if _connection is None:
        from cloudburst.client.client import CloudburstConnection
        print(f"Connecting to Cloudburst scheduler at {scheduler_ip} (local={local})")
        _connection = CloudburstConnection(scheduler_ip, client_ip, local=local)
    return _connection


def _make_stateful_bench():
    """Create the benchmark function to register with Cloudburst."""
    import os
    import time as _time
    import uuid as _uuid

    def stateful_bench(cloudburst, request_id):
        state_size_kb = int(os.environ.get("STATE_SIZE_KB", "64"))
        state_key = os.environ.get("STATE_KEY", "bench:state")
        ops = int(os.environ.get("OPS", "1"))

        begin = _time.time()
        blob = os.urandom(state_size_kb * 1024)

        write_start = _time.time()
        cloudburst.put(state_key, blob)
        write_end = _time.time()

        read_start = _time.time()
        result = cloudburst.get(state_key)
        read_end = _time.time()

        # Lightweight compute
        acc = 0
        for i in range(1000):
            acc += i
        compute_end = _time.time()

        end = _time.time()
        return {
            "request_id": request_id if request_id else _uuid.uuid4().hex,
            "is_cold": False,
            "begin": begin,
            "end": end,
            "measurement": {
                "compute_time_us": int((compute_end - read_end) * 1e6),
                "state_read_lat_us": int((read_end - read_start) * 1e6),
                "state_write_lat_us": int((write_end - write_start) * 1e6),
                "state_size_kb": state_size_kb,
                "state_ops": ops,
                "accumulator": acc,
            },
        }

    return stateful_bench


def ensure_registered(scheduler_ip, client_ip, local):
    global _registered
    if _registered:
        return
    conn = get_connection(scheduler_ip, client_ip, local)

    bench_fn = _make_stateful_bench()
    print("Registering stateful_bench function...")
    cloud_fn = conn.register(bench_fn, "stateful_bench")
    if cloud_fn is None:
        raise RuntimeError("Failed to register stateful_bench")

    success, error = conn.register_dag("stateful_dag", ["stateful_bench"], [])
    if not success:
        raise RuntimeError(f"Failed to register DAG: {error}")

    _registered = True
    print("Function and DAG registered successfully")


class CloudburstHandler(BaseHTTPRequestHandler):
    scheduler_ip = None
    client_ip = None
    local = True

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            payload = json.loads(body)

            request_id = payload.get("request_id", uuid.uuid4().hex)

            ensure_registered(self.scheduler_ip, self.client_ip, self.local)
            conn = get_connection(self.scheduler_ip, self.client_ip, self.local)

            begin = time.time()
            result = conn.call_dag(
                "stateful_dag",
                {"stateful_bench": [request_id]},
                direct_response=True,
            )
            end = time.time()

            if isinstance(result, dict):
                response = result
            else:
                response = {
                    "request_id": request_id,
                    "is_cold": False,
                    "begin": begin,
                    "end": end,
                    "result": str(result),
                }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            error_msg = json.dumps({"error": str(e), "traceback": traceback.format_exc()})
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(error_msg.encode())

    def do_GET(self):
        """Health check endpoint."""
        parsed = urlparse(self.path)
        if parsed.path in ("/health", "/alive", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "registered": _registered,
                "scheduler_ip": self.scheduler_ip,
            }).encode())
        else:
            # Treat GET with query params as invocation (like Boki gateway)
            parsed_qs = parse_qs(parsed.query)
            payload = {k: v[0] for k, v in parsed_qs.items()}
            self.headers["Content-Length"] = "0"
            # Rewrite as POST
            self.rfile = type("FakeBody", (), {"read": lambda self, n=0: json.dumps(payload).encode()})()
            self.headers["Content-Length"] = str(len(json.dumps(payload)))
            self.do_POST()

    def log_message(self, format, *args):
        # Quieter logging — only errors
        if args and "500" in str(args[0]):
            super().log_message(format, *args)


def main():
    parser = argparse.ArgumentParser(description="Cloudburst HTTP→ZMQ gateway")
    parser.add_argument("--scheduler-ip", default=None,
                        help="Scheduler IP (default: auto-detect from hostname)")
    parser.add_argument("--client-ip", default=None,
                        help="This machine's IP for ZMQ responses (default: auto-detect)")
    parser.add_argument("--port", type=int, default=8088, help="HTTP port (default: 8088)")
    parser.add_argument("--local", action="store_true", default=True,
                        help="Use Anna local mode (default: true)")
    args = parser.parse_args()

    scheduler_ip = args.scheduler_ip
    client_ip = args.client_ip

    if not scheduler_ip:
        import socket
        scheduler_ip = socket.gethostbyname(socket.gethostname())
        # Fallback: read from config
        try:
            import yaml
            with open("/opt/cloudburst/cloudburst/conf/cloudburst-aws.yml") as f:
                cfg = yaml.safe_load(f)
                scheduler_ip = cfg.get("ip", scheduler_ip)
        except Exception:
            pass

    if not client_ip:
        import subprocess
        client_ip = subprocess.check_output(
            "hostname -I | awk '{print $1}'", shell=True
        ).decode().strip()

    CloudburstHandler.scheduler_ip = scheduler_ip
    CloudburstHandler.client_ip = client_ip
    CloudburstHandler.local = args.local

    server = HTTPServer(("0.0.0.0", args.port), CloudburstHandler)
    print(f"Cloudburst HTTP gateway listening on 0.0.0.0:{args.port}")
    print(f"  Scheduler: {scheduler_ip}")
    print(f"  Client IP: {client_ip}")
    print(f"  Local mode: {args.local}")
    print(f"  Invoke: curl -X POST http://localhost:{args.port}/function/stateful_bench -d '{{\"request_id\":\"test\"}}'")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
        server.server_close()


if __name__ == "__main__":
    main()
