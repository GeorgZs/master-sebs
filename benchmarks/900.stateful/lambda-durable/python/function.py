# REFERENCE ONLY — The deployed function lives in:
#   integrations/baseline/aws/lambda_durable_package/handler.py
#
# This file documents the benchmark function pattern for Lambda Durable.
# The actual handler uses @durable_execution and @durable_step decorators
# from the AWS Durable Execution SDK.
#
# State mechanism: DynamoDB (fully serverless, no Redis/VPC)
# Each state operation (write/read) is wrapped in a @durable_step,
# which creates a checkpoint in the Lambda durable execution log.
# On replay (after failure/pause), completed steps return cached results
# without re-executing.
#
# Response format: SeBS-compatible JSON (same as baseline Lambda).

raise NotImplementedError(
    "This is a reference stub. "
    "The deployed function is in integrations/baseline/aws/lambda_durable_package/handler.py"
)
