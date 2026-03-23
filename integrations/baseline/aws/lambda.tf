data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_package"
  output_path = "${path.module}/lambda_bundle.zip"
}

resource "aws_lambda_function" "baseline" {
  function_name = "${local.name_prefix}-fn"
  role          = aws_iam_role.lambda.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = var.lambda_timeout_seconds
  memory_size   = var.lambda_memory_mb

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  vpc_config {
    subnet_ids         = [for s in aws_subnet.public : s.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      REDIS_HOST = aws_elasticache_replication_group.redis.primary_endpoint_address
      REDIS_PORT = tostring(aws_elasticache_replication_group.redis.port)
    }
  }

  reserved_concurrent_executions = var.lambda_reserved_concurrent_executions >= 0 ? var.lambda_reserved_concurrent_executions : null

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy_attachment.lambda_vpc,
    aws_elasticache_replication_group.redis,
  ]

  tags = {
    Name = "${local.name_prefix}-fn"
  }
}
