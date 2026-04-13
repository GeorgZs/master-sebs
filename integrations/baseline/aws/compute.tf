# SeBS benchmark client — lightweight EC2 for running batch_invoke.py
# inside the Lambda VPC for cloud-to-cloud latency measurement.
# Invokes Lambda via API Gateway (HTTPS, intra-region).

resource "aws_instance" "client" {
  count                  = var.deploy_sebs_client ? 1 : 0
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.client_instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.client[0].id]
  iam_instance_profile   = aws_iam_instance_profile.client[0].name
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data/client.sh.tftpl", {
    api_endpoint = aws_apigatewayv2_stage.default.invoke_url
  })

  tags = {
    Name = "${local.name_prefix}-sebs-client"
    Role = "sebs-benchmark-client"
  }
}
