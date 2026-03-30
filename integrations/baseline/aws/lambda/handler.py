import json

from function import handler as benchmark_handler


def _parse_body(event):
    """Extract the benchmark payload from an API Gateway v2 event."""
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
    result = benchmark_handler(body)
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result),
    }
