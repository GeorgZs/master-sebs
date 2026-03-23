# Baseline AWS (Lambda + Redis)

## Topology

- 1x VPC, 2x public subnets (Lambda ENIs + ElastiCache subnet group)
- 1x ElastiCache Redis replication group (single node)
- 1x Lambda function (VPC)
- 1x HTTP API (API Gateway v2) → Lambda

## Files

- `network.tf`, `security.tf`, `redis.tf`, `lambda.tf`, `apigateway.tf`, `iam.tf`, `outputs.tf`
- `lambda/handler.py`, `build_lambda.sh`

## Configuration

See `terraform.tfvars.example`.
