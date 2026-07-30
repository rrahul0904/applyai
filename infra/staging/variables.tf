variable "project_name" {
  description = "Short application name used in AWS resource names."
  type        = string
  default     = "applyai"
}

variable "environment" {
  description = "Deployment environment. This stack is intentionally staging-only."
  type        = string
  default     = "staging"

  validation {
    condition     = var.environment == "staging"
    error_message = "infra/staging may only be used with environment=staging."
  }
}

variable "aws_region" {
  description = "AWS Region for the staging stack."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR for the staging VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Two public subnets used by the internet-facing ALB and NAT gateway."
  type        = list(string)
  default     = ["10.42.0.0/24", "10.42.1.0/24"]

  validation {
    condition     = length(var.public_subnet_cidrs) == 2
    error_message = "Exactly two public subnet CIDRs are required."
  }
}

variable "app_subnet_cidrs" {
  description = "Two private subnets for ECS/Fargate tasks."
  type        = list(string)
  default     = ["10.42.10.0/24", "10.42.11.0/24"]

  validation {
    condition     = length(var.app_subnet_cidrs) == 2
    error_message = "Exactly two application subnet CIDRs are required."
  }
}

variable "db_subnet_cidrs" {
  description = "Two isolated private subnets for Aurora."
  type        = list(string)
  default     = ["10.42.20.0/24", "10.42.21.0/24"]

  validation {
    condition     = length(var.db_subnet_cidrs) == 2
    error_message = "Exactly two database subnet CIDRs are required."
  }
}

variable "web_origin" {
  description = "Exact HTTPS Vercel staging origin allowed by API CORS and S3 upload CORS."
  type        = string

  validation {
    condition     = startswith(var.web_origin, "https://") && var.web_origin != "https://*"
    error_message = "web_origin must be an exact HTTPS origin."
  }
}

variable "api_certificate_arn" {
  description = "ACM certificate ARN for the staging API HTTPS listener."
  type        = string
}

variable "clerk_issuer" {
  description = "Clerk staging JWT issuer."
  type        = string
}

variable "clerk_jwks_url" {
  description = "Clerk staging JWKS endpoint."
  type        = string
}

variable "clerk_audience" {
  description = "Optional Clerk audience. Empty means issuer/signature validation without an audience constraint."
  type        = string
  default     = ""
}

variable "greenhouse_board_tokens" {
  description = "Explicit public Greenhouse board tokens ingested by the staging scheduled task."
  type        = list(string)
  default     = []
}

variable "database_name" {
  description = "Initial Aurora database name."
  type        = string
  default     = "applyai"
}

variable "database_master_username" {
  description = "Aurora master username; password is managed by RDS in Secrets Manager."
  type        = string
  default     = "applyai_admin"
}

variable "aurora_min_acu" {
  description = "Minimum Aurora Serverless v2 capacity for staging."
  type        = number
  default     = 0.5
}

variable "aurora_max_acu" {
  description = "Maximum Aurora Serverless v2 capacity for staging."
  type        = number
  default     = 2

  validation {
    condition     = var.aurora_max_acu >= var.aurora_min_acu
    error_message = "aurora_max_acu must be greater than or equal to aurora_min_acu."
  }
}

variable "image_tag" {
  description = "ECR image tag used by API, worker, outbox publisher, and ingestion task definitions."
  type        = string
  default     = "staging"
}

variable "api_desired_count" {
  description = "API service tasks. Keep zero until the staging image has been pushed to ECR."
  type        = number
  default     = 0
}

variable "worker_desired_count" {
  description = "Resume worker tasks. Keep zero until the staging image has been pushed to ECR."
  type        = number
  default     = 0
}

variable "outbox_desired_count" {
  description = "Transactional outbox publisher tasks. Keep zero until the staging image has been pushed to ECR."
  type        = number
  default     = 0
}

variable "api_cpu" {
  type    = number
  default = 512
}

variable "api_memory" {
  type    = number
  default = 1024
}

variable "worker_cpu" {
  type    = number
  default = 512
}

variable "worker_memory" {
  type    = number
  default = 1024
}

variable "outbox_cpu" {
  type    = number
  default = 256
}

variable "outbox_memory" {
  type    = number
  default = 512
}

variable "ingestion_cpu" {
  type    = number
  default = 512
}

variable "ingestion_memory" {
  type    = number
  default = 1024
}

variable "sqs_visibility_timeout_seconds" {
  type    = number
  default = 300
}

variable "sqs_visibility_heartbeat_seconds" {
  type    = number
  default = 120

  validation {
    condition     = var.sqs_visibility_heartbeat_seconds < var.sqs_visibility_timeout_seconds
    error_message = "SQS heartbeat must be shorter than visibility timeout."
  }
}

variable "sqs_max_receive_count" {
  type    = number
  default = 5
}

variable "resume_processing_timeout_seconds" {
  type    = number
  default = 900

  validation {
    condition     = var.resume_processing_timeout_seconds >= var.sqs_visibility_timeout_seconds
    error_message = "Resume processing timeout must be at least the SQS visibility timeout."
  }
}

variable "ingestion_schedule_expression" {
  description = "EventBridge schedule for Greenhouse ingestion after staging is activated."
  type        = string
  default     = "rate(15 minutes)"
}

variable "ingestion_schedule_enabled" {
  description = "Enable scheduled Greenhouse ingestion only after the image and staging services are ready."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "alarm_sns_topic_arn" {
  description = "Optional existing SNS topic ARN for CloudWatch alarm actions."
  type        = string
  default     = null
}
