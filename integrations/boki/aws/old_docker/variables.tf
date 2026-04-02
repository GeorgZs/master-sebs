variable "project_name" {
  type        = string
  description = "Name prefix for all resources."
  default     = "master-sebs-boki"
}

variable "aws_region" {
  type        = string
  description = "AWS region for deployment."
  default     = "eu-north-1"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block."
  default     = "10.40.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs."
  default     = ["10.40.1.0/24"]
}

variable "admin_cidr" {
  type        = string
  description = "CIDR allowed for SSH and gateway ingress."
  default     = "0.0.0.0/0"
}

variable "key_pair_name" {
  type        = string
  description = "EC2 key pair name for SSH access."
  default     = ""
}

variable "gateway_http_port" {
  type        = number
  description = "Gateway HTTP port."
  default     = 8080
}

variable "boki_instance_type" {
  type        = string
  description = "EC2 instance type for the all-in-one Boki node."
  default     = "c5.2xlarge"
}

variable "boki_repo_url" {
  type        = string
  description = "Boki source repository URL."
  default     = "https://github.com/GeorgZs/master-boki.git"
}

variable "boki_repo_ref" {
  type        = string
  description = "Git branch/tag/commit to checkout."
  default     = "master"
}
