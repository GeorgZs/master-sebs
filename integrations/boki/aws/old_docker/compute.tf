# Single all-in-one instance running Boki via Docker Compose.
#
# History: Originally deployed as 7 separate EC2 instances (ZooKeeper,
# Controller, Sequencer, Storage, Engine, Gateway, Client). Changed to
# single-node Docker Compose on 2026-04-01 because:
#
#   1. Boki's io_uring-based gateway HTTP dispatch hangs when gateway and
#      engine run on separate machines (ISSUES.md #10). The official
#      boki-benchmarks repo (ut-osa/boki-benchmarks) runs all components
#      on one host via Docker Compose/Swarm.
#
#   2. Reduces infrastructure complexity from 7 instances to 1.
#
#   3. Matches the SOSP '21 artifact evaluation setup exactly.
#
# The benchmark function (Go binary) is mounted into the container via
# a shared volume, not baked into the Docker image.

resource "aws_instance" "boki" {
  ami                    = data.aws_ami.ubuntu2004.id
  instance_type          = var.boki_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.cluster.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  root_block_device {
    volume_size = 100
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data/boki_aio.sh.tftpl", {
    boki_repo_url    = var.boki_repo_url
    boki_repo_ref    = var.boki_repo_ref
    gateway_http_port = var.gateway_http_port
  })

  tags = {
    Name = "${local.name_prefix}-aio"
    Role = "boki-all-in-one"
  }
}
