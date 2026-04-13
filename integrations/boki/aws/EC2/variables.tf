variable "project_name" {
  type        = string
  description = "Name prefix for all resources."
  default     = "boki-experimental"
}

variable "aws_region" {
  type        = string
  description = "AWS region for deployment."
  default     = "eu-north-1"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block."
  default     = "10.41.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "Public subnet CIDRs (one per AZ for engine spread)."
  default     = ["10.41.1.0/24", "10.41.2.0/24"]
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

# --- Infrastructure node ---

variable "infra_instance_type" {
  type        = string
  description = "EC2 instance type for the infrastructure node (ZK, Controller, Sequencers, Storage, Gateway)."
  default     = "c5.2xlarge"
}

# --- Engine nodes (scalable) ---

variable "engine_instance_type" {
  type        = string
  description = "EC2 instance type for each engine node."
  default     = "c5.xlarge"
}

variable "engine_min_size" {
  type        = number
  description = "Minimum number of engine instances in the ASG."
  default     = 1
}

variable "engine_desired_capacity" {
  type        = number
  description = "Desired number of engine instances."
  default     = 2
}

variable "engine_max_size" {
  type        = number
  description = "Maximum number of engine instances in the ASG."
  default     = 4
}

# --- Boki config ---

variable "gateway_http_port" {
  type        = number
  description = "Gateway HTTP port."
  default     = 8080
}

variable "boki_repo_url" {
  type        = string
  description = "Boki source repository URL (used if building from source on engine nodes)."
  default     = "https://github.com/GeorgZs/master-boki.git"
}

variable "boki_repo_ref" {
  type        = string
  description = "Git branch/tag/commit to checkout."
  default     = "master"
}

variable "metalog_replicas" {
  type        = number
  description = "Number of metalog replicas (must match number of sequencers)."
  default     = 2
}

variable "zk_setup_wait_seconds" {
  type        = number
  description = "Seconds the ZK setup container waits for nodes to register before issuing start."
  default     = 120
}

variable "bench_binary_s3_uri" {
  type        = string
  description = "Optional S3 URI for the stateful_bench Go binary (e.g. s3://bucket/stateful_bench). If empty, upload manually."
  default     = ""
}

# --- SeBS benchmark client ---

variable "deploy_sebs_client" {
  type        = bool
  description = "Deploy a SeBS benchmark client EC2 inside the Boki VPC for cloud-to-cloud latency measurements."
  default     = false
}

variable "client_instance_type" {
  type        = string
  description = "EC2 instance type for the SeBS benchmark client."
  default     = "t3.small"
}
