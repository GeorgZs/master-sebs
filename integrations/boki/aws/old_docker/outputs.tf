output "vpc_id" {
  value       = aws_vpc.this.id
  description = "VPC ID."
}

output "boki_public_ip" {
  value       = aws_instance.boki.public_ip
  description = "Boki all-in-one node public IP."
}

output "boki_private_ip" {
  value       = aws_instance.boki.private_ip
  description = "Boki all-in-one node private IP."
}

output "gateway_url" {
  value       = "http://${aws_instance.boki.public_ip}:${var.gateway_http_port}"
  description = "Boki gateway HTTP URL."
}
