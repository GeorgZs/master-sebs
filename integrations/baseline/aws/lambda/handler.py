import json
import os

import redis


def _parse_body(event):
    if not isinstance(event, dict):
        return {}
    body_raw = event.get("body")
    if body_raw is None:
        return {k: v for k, v in event.items() if k not in ("requestContext", "headers", "rawPath")}
    if body_raw == "":
        return {}
    if isinstance(body_raw, str):
        try:
            return json.loads(body_raw)
        except json.JSONDecodeError:
            return {}
    if isinstance(body_raw, dict):
        return body_raw
    return {}


def handler(event, context):
    body = _parse_body(event)
    key = body.get("key", "baseline:counter")

    host = os.environ["REDIS_HOST"]
    port = int(os.environ.get("REDIS_PORT", "6379"))

    client = redis.Redis(
        host=host,
        port=port,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    val = client.incr(key)
    out = {"ok": True, "key": key, "value": val}

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(out),
    }
