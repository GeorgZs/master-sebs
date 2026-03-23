resource "aws_apigatewayv2_api" "http" {
  name          = "${local.name_prefix}-http"
  protocol_type = "HTTP"

  tags = {
    Name = "${local.name_prefix}-http"
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id = aws_apigatewayv2_api.http.id

  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.baseline.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "post_default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "get_default" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_lambda_permission" "http_api" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.baseline.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}
