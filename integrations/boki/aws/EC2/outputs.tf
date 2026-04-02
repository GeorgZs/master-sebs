output "vpc_id" {
  value       = aws_vpc.this.id
  description = "VPC ID."
}

output "infra_public_ip" {
  value       = aws_instance.infra.public_ip
  description = "Infrastructure node public IP (SSH + Gateway)."
}

output "infra_private_ip" {
  value       = aws_instance.infra.private_ip
  description = "Infrastructure node private IP (ZK endpoint for engines)."
}

output "gateway_url" {
  value       = "http://${aws_instance.infra.public_ip}:${var.gateway_http_port}"
  description = "Boki gateway HTTP URL."
}

output "engine_asg_name" {
  value       = aws_autoscaling_group.engines.name
  description = "Engine ASG name (use with aws autoscaling set-desired-capacity)."
}
