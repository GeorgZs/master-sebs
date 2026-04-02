resource "aws_security_group" "cluster" {
  name        = "${local.name_prefix}-cluster-sg"
  description = "Boki all-in-one node security group"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "SSH admin access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  ingress {
    description = "Gateway HTTP"
    from_port   = var.gateway_http_port
    to_port     = var.gateway_http_port
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  egress {
    description = "Allow all egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-cluster-sg"
  }
}
