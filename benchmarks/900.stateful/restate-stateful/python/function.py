# REFERENCE ONLY — The deployed function lives in:
#   integrations/restate/aws/lambda_package/handler.py
#
# This file documents the benchmark function pattern for Restate.
# The actual handler uses Restate's Virtual Object API with
# ctx.set() / ctx.get() for state management.
#
# State mechanism: Restate embedded KV (journal-backed, no external store)
# Deployment: Lambda function behind Restate server (FaaS model)
# Invocation: POST http://<restate-server>:8080/statefulBench/<key>/run
#
# Response format: SeBS-compatible JSON (same as all other systems).

raise NotImplementedError(
    "This is a reference stub. "
    "The deployed function is in integrations/restate/aws/lambda_package/handler.py"
)
