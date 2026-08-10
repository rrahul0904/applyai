variable "agent_worker_desired_count" {
  description = "Governed Agent Worker tasks. Keep zero until staging agent acceptance is intentionally enabled."
  type        = number
  default     = 0

  validation {
    condition     = var.agent_worker_desired_count >= 0 && var.agent_worker_desired_count <= 10
    error_message = "agent_worker_desired_count must be between 0 and 10."
  }
}

variable "agent_worker_max_count" {
  description = "Maximum governed Agent Worker tasks during staging autoscaling."
  type        = number
  default     = 10

  validation {
    condition     = var.agent_worker_max_count >= 1 && var.agent_worker_max_count <= 50
    error_message = "agent_worker_max_count must be between 1 and 50."
  }
}

variable "agent_worker_cpu" {
  type    = number
  default = 512
}

variable "agent_worker_memory" {
  type    = number
  default = 1024
}

variable "agent_sqs_visibility_timeout_seconds" {
  type    = number
  default = 600
}

variable "agent_sqs_visibility_heartbeat_seconds" {
  type    = number
  default = 240

  validation {
    condition     = var.agent_sqs_visibility_heartbeat_seconds < var.agent_sqs_visibility_timeout_seconds
    error_message = "Agent SQS heartbeat must be shorter than its visibility timeout."
  }
}

variable "agent_sqs_max_receive_count" {
  type    = number
  default = 5
}

variable "agent_queue_depth_alarm_threshold" {
  type    = number
  default = 25
}

resource "aws_sqs_queue" "agent_dlq" {
  name                       = "${local.name}-agent-tasks-dlq"
  message_retention_seconds  = 1209600
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = var.agent_sqs_visibility_timeout_seconds
}

resource "aws_sqs_queue" "agent" {
  name                       = "${local.name}-agent-tasks"
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = var.agent_sqs_visibility_timeout_seconds
}

resource "aws_sqs_queue_redrive_policy" "agent" {
  queue_url = aws_sqs_queue.agent.id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.agent_dlq.arn
    maxReceiveCount     = var.agent_sqs_max_receive_count
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "agent_dlq" {
  queue_url = aws_sqs_queue.agent_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.agent.arn]
  })
}

resource "aws_cloudwatch_log_group" "agent_runtime" {
  name              = "/applyai/${var.environment}/agent-worker"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "agent_worker_task" {
  name               = "${local.name}-agent-worker-task"
  assume_role_policy = local.ecs_task_assume_role_policy
}

resource "aws_iam_role_policy" "agent_worker_queue" {
  name = "agent-queue-consume"
  role = aws_iam_role.agent_worker_task.id

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
        Resource = aws_sqs_queue.agent.arn
      }
    ]
  })
}

# The universal transactional-outbox publisher already owns all job/resume/AI routing.
# Add only the governed-agent queue permission here rather than creating a second publisher.
resource "aws_iam_role_policy" "universal_outbox_agent_queue" {
  name = "agent-task-queue-publish"
  role = aws_iam_role.universal_outbox_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.agent.arn
      }
    ]
  })
}

resource "aws_ecs_task_definition" "agent_worker" {
  family                   = "${local.name}-agent-worker"
  cpu                      = tostring(var.agent_worker_cpu)
  memory                   = tostring(var.agent_worker_memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.agent_worker_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "agent-worker"
      image       = local.image_uri
      essential   = true
      command     = ["python", "-m", "app.workers.agent"]
      environment = concat(
        local.ai_worker_environment,
        [
          { name = "AGENT_SQS_QUEUE_URL", value = aws_sqs_queue.agent.id },
          { name = "AGENT_SQS_DLQ_URL", value = aws_sqs_queue.agent_dlq.id },
          { name = "AGENT_SQS_VISIBILITY_TIMEOUT_SECONDS", value = tostring(var.agent_sqs_visibility_timeout_seconds) },
          { name = "AGENT_SQS_VISIBILITY_HEARTBEAT_SECONDS", value = tostring(var.agent_sqs_visibility_heartbeat_seconds) },
          { name = "AGENT_SQS_MAX_RECEIVE_COUNT", value = tostring(var.agent_sqs_max_receive_count) },
        ]
      )
      secrets     = local.ai_worker_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.agent_runtime.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "agent-worker"
        }
      }
    }
  ])

  depends_on = [terraform_data.ai_runtime_guardrails]
}

resource "aws_ecs_service" "agent_worker" {
  name            = "${local.name}-agent-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.agent_worker.arn
  desired_count   = var.agent_worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.app[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}

resource "aws_appautoscaling_target" "agent_worker" {
  max_capacity       = var.agent_worker_max_count
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.agent_worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "agent_worker_cpu" {
  name               = "${local.name}-agent-worker-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.agent_worker.resource_id
  scalable_dimension = aws_appautoscaling_target.agent_worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.agent_worker.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 55
    scale_in_cooldown  = 120
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "agent_queue_depth" {
  alarm_name          = "${local.name}-agent-queue-depth"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Average"
  threshold           = var.agent_queue_depth_alarm_threshold
  alarm_description   = "Governed Agent Runtime queue depth is elevated."

  dimensions = {
    QueueName = aws_sqs_queue.agent.name
  }
}

resource "aws_cloudwatch_metric_alarm" "agent_dlq_visible" {
  alarm_name          = "${local.name}-agent-dlq-visible"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "Governed Agent Runtime DLQ contains failed messages."

  dimensions = {
    QueueName = aws_sqs_queue.agent_dlq.name
  }
}
