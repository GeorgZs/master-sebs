# Multi-node Boki deployment for real elasticity benchmarking.
#
# Topology:
#   1x Infrastructure node  — ZK, Controller, 2x Sequencer, Storage, Gateway
#   Nx Engine nodes (ASG)   — each runs Engine + Launcher + Worker(s)
#
# This mirrors the Cloudburst topology (fixed infra + scalable compute).
# Engine nodes register with ZK on the infra node and are discovered by
# the Gateway for load-balanced function dispatch.
#
# Workers communicate with the Engine via IPC (shared tmpfs), so each
# Engine node is a self-contained compute unit. Scaling = more Engine EC2s.

# ---------- Infrastructure node ----------

resource "aws_instance" "infra" {
  ami                    = data.aws_ami.ubuntu2004.id
  instance_type          = var.infra_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  root_block_device {
    volume_size = 100
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data/infra.sh.tftpl", {
    gateway_http_port     = var.gateway_http_port
    metalog_replicas      = var.metalog_replicas
    zk_setup_wait_seconds = var.zk_setup_wait_seconds
  })

  tags = {
    Name = "${local.name_prefix}-infra"
    Role = "boki-infrastructure"
  }
}

# ---------- Engine ASG ----------

resource "aws_launch_template" "engine" {
  name_prefix   = "${local.name_prefix}-engine-"
  image_id      = data.aws_ami.ubuntu2004.id
  instance_type = var.engine_instance_type
  key_name      = var.key_pair_name != "" ? var.key_pair_name : null

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2.name
  }

  network_interfaces {
    security_groups             = [aws_security_group.cluster.id]
    associate_public_ip_address = true
  }

  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      volume_size = 50
      volume_type = "gp3"
    }
  }

  user_data = base64encode(templatefile("${path.module}/user_data/engine.sh.tftpl", {
    zk_host             = aws_instance.infra.private_ip
    gateway_http_port   = var.gateway_http_port
    bench_binary_s3_uri = var.bench_binary_s3_uri
  }))

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${local.name_prefix}-engine"
      Role = "boki-engine"
    }
  }
}

resource "aws_autoscaling_group" "engines" {
  name                = "${local.name_prefix}-engines"
  min_size            = var.engine_min_size
  desired_capacity    = var.engine_desired_capacity
  max_size            = var.engine_max_size
  vpc_zone_identifier = [for s in aws_subnet.public : s.id]
  health_check_type   = "EC2"

  launch_template {
    id      = aws_launch_template.engine.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${local.name_prefix}-engine-asg"
    propagate_at_launch = true
  }
}
