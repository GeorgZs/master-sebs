resource "aws_security_group" "cluster" {
  name        = "${local.name_prefix}-cluster-sg"
  description = "Boki experimental cluster - all intra-cluster traffic allowed"
  vpc_id      = aws_vpc.this.id

  # SSH from admin
  ingress {
    description = "SSH admin access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  # Gateway HTTP from admin
  ingress {
    description = "Gateway HTTP"
    from_port   = var.gateway_http_port
    to_port     = var.gateway_http_port
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  # All traffic within the cluster (ZK, Engine<->Gateway, Sequencer, Storage)
  ingress {
    description = "Intra-cluster traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
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
