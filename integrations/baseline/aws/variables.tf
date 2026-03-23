variable "project_name" {
  type        = string
  description = "Name prefix for all resources."
  default     = "master-sebs-baseline"
}

variable "aws_region" {
  type        = string
  description = "AWS region for deployment."
  default     = "eu-north-1"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block."
  default     = "10.50.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs (at least two AZs for ElastiCache subnet group)."
  default     = ["10.50.1.0/24", "10.50.2.0/24"]
}

variable "redis_node_type" {
  type        = string
  description = "ElastiCache Redis node type."
  default     = "cache.t4g.micro"
}

variable "redis_engine_version" {
  type        = string
  description = "Redis engine version for ElastiCache."
  default     = "7.1"
}

variable "lambda_timeout_seconds" {
  type        = number
  description = "Lambda timeout."
  default     = 30
}

variable "lambda_memory_mb" {
  type        = number
  description = "Lambda memory size (MB)."
  default     = 256
}

variable "lambda_reserved_concurrent_executions" {
  type        = number
  description = "Reserved concurrency (-1 = omit, use account default / elastic scaling)."
  default     = -1
}
