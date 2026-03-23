resource "aws_elasticache_subnet_group" "redis" {
  name       = "${local.name_prefix}-redis-subnets"
  subnet_ids = [for s in aws_subnet.public : s.id]

  tags = {
    Name = "${local.name_prefix}-redis-subnets"
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.name_prefix}-redis"
  description                = "Baseline Redis for Lambda state"
  engine                     = "redis"
  engine_version             = var.redis_engine_version
  node_type                  = var.redis_node_type
  num_cache_clusters         = 1
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
  automatic_failover_enabled = false
  multi_az_enabled           = false
  at_rest_encryption_enabled = true
  transit_encryption_enabled = false
  apply_immediately          = true
  snapshot_retention_limit   = 0

  tags = {
    Name = "${local.name_prefix}-redis"
  }
}
