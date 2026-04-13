output "vpc_id" {
  value       = aws_vpc.this.id
  description = "VPC ID."
}

output "redis_primary_endpoint" {
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
  description = "Redis primary endpoint (hostname)."
}

output "redis_port" {
  value       = aws_elasticache_replication_group.redis.port
  description = "Redis port."
}

output "lambda_function_name" {
  value       = aws_lambda_function.baseline.function_name
  description = "Lambda function name."
}

output "lambda_function_arn" {
  value       = aws_lambda_function.baseline.arn
  description = "Lambda function ARN."
}

output "http_api_endpoint" {
  value       = aws_apigatewayv2_stage.default.invoke_url
  description = "HTTP API base URL (POST or GET /)."
}

output "client_public_ip" {
  value       = var.deploy_sebs_client ? aws_instance.client[0].public_ip : null
  description = "SeBS benchmark client public IP (SSH access)."
}
