variable "ai_provider" {
  description = "AI runtime provider. Keep deterministic until the reviewed model credential is configured."
  type        = string
  default     = "deterministic"

  validation {
    condition     = contains(["deterministic", "openai"], var.ai_provider)
    error_message = "ai_provider must be deterministic or openai."
  }
}

variable "openai_api_key_secret_arn" {
  description = "Optional Secrets Manager ARN containing the OpenAI API key for the AI worker."
  type        = string
  default     = null
}

variable "openai_model" {
  description = "Reviewed OpenAI model identifier used by the AI worker when ai_provider=openai."
  type        = string
  default     = "gpt-5.6-luna"
}

variable "openai_reasoning_effort" {
  type    = string
  default = "low"

  validation {
    condition     = contains(["none", "low", "medium", "high", "xhigh", "max"], var.openai_reasoning_effort)
    error_message = "openai_reasoning_effort is invalid."
  }
}

variable "ai_worker_desired_count" {
  description = "Career intelligence worker tasks. Keep zero until AI staging acceptance is enabled."
  type        = number
  default     = 0

  validation {
    condition     = var.ai_worker_desired_count >= 0 && var.ai_worker_desired_count <= 10
    error_message = "ai_worker_desired_count must be between 0 and 10."
  }
}

variable "ai_worker_cpu" {
  type    = number
  default = 512
}

variable "ai_worker_memory" {
  type    = number
  default = 1024
}

variable "ai_sqs_visibility_timeout_seconds" {
  type    = number
  default = 600
}

variable "ai_sqs_visibility_heartbeat_seconds" {
  type    = number
  default = 240

  validation {
    condition     = var.ai_sqs_visibility_heartbeat_seconds < var.ai_sqs_visibility_timeout_seconds
    error_message = "AI SQS heartbeat must be shorter than its visibility timeout."
  }
}

variable "ai_sqs_max_receive_count" {
  type    = number
  default = 5
}

variable "ai_queue_depth_alarm_threshold" {
  type    = number
  default = 25
}

variable "ai_queue_age_alarm_seconds" {
  type    = number
  default = 600
}

resource "aws_sqs_queue" "ai_dlq" {
  name                       = "${local.name}-ai-tasks-dlq"
  message_retention_seconds  = 1209600
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = var.ai_sqs_visibility_timeout_seconds
}

resource "aws_sqs_queue" "ai" {
  name                       = "${local.name}-ai-tasks"
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = var.ai_sqs_visibility_timeout_seconds
}

resource "aws_sqs_queue_redrive_policy" "ai" {
  queue_url = aws_sqs_queue.ai.id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ai_dlq.arn
    maxReceiveCount     = var.ai_sqs_max_receive_count
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "ai_dlq" {
  queue_url = aws_sqs_queue.ai_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.ai.arn]
  })
}

resource "aws_cloudwatch_log_group" "ai_worker" {
  name              = "/applyai/${var.environment}/ai-worker"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "ai_worker_task" {
  name               = "${local.name}-ai-worker-task"
  assume_role_policy = local.ecs_task_assume_role_policy
}

resource "aws_iam_role_policy" "ai_worker_queue" {
  name = "ai-queue-consume"
  role = aws_iam_role.ai_worker_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ChangeMessageVisibility",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ReceiveMessage"
        ]
        Resource = aws_sqs_queue.ai.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "ecs_execution_openai_secret" {
  count = var.openai_api_key_secret_arn == null ? 0 : 1

  name = "openai-api-key-secret"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = var.openai_api_key_secret_arn
      }
    ]
  })
}

locals {
  ai_worker_secrets = concat(
    local.database_secrets,
    var.openai_api_key_secret_arn == null ? [] : [
      {
        name      = "OPENAI_API_KEY"
        valueFrom = var.openai_api_key_secret_arn
      }
    ]
  )
}

resource "aws_ecs_task_definition" "ai_worker" {
  family                   = "${local.name}-ai-worker"
  cpu                      = tostring(var.ai_worker_cpu)
  memory                   = tostring(var.ai_worker_memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ai_worker_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "ai-worker"
      image       = local.image_uri
      essential   = true
      command     = ["python", "-m", "app.workers.ai"]
      environment = local.common_environment
      secrets     = local.ai_worker_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ai_worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ai-worker"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "ai_worker" {
  name            = "${local.name}-ai-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.ai_worker.arn
  desired_count   = var.ai_worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.app[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}

resource "aws_cloudwatch_metric_alarm" "ai_queue_visible" {
  alarm_name          = "${local.name}-ai-queue-depth"
  alarm_description   = "Career intelligence queue depth remained above the staging threshold."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = var.ai_queue_depth_alarm_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.ai.name
  }
}

resource "aws_cloudwatch_metric_alarm" "ai_queue_age" {
  alarm_name          = "${local.name}-ai-oldest-message"
  alarm_description   = "Oldest visible AI task exceeded the configured processing-age threshold."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 5
  threshold           = var.ai_queue_age_alarm_seconds
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.ai.name
  }
}

resource "aws_cloudwatch_metric_alarm" "ai_dlq_visible" {
  alarm_name          = "${local.name}-ai-dlq-nonempty"
  alarm_description   = "At least one career intelligence task reached the DLQ."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.ai_dlq.name
  }
}

output "ai_queue_url" {
  value = aws_sqs_queue.ai.id
}

output "ai_dlq_url" {
  value = aws_sqs_queue.ai_dlq.id
}
