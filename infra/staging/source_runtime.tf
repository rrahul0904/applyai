variable "lever_site_names" {
  description = "Reviewed public Lever site names available to the staging source registry."
  type        = list(string)
  default     = []
}

variable "ashby_board_names" {
  description = "Reviewed public Ashby board names available to the staging source registry."
  type        = list(string)
  default     = []
}

variable "source_worker_desired_count" {
  description = "Dedicated source ingestion/discovery/verification worker tasks."
  type        = number
  default     = 0

  validation {
    condition     = var.source_worker_desired_count >= 0 && var.source_worker_desired_count <= 10
    error_message = "source_worker_desired_count must be between 0 and 10."
  }
}

variable "source_outbox_desired_count" {
  description = "Source-aware transactional outbox publisher tasks."
  type        = number
  default     = 0

  validation {
    condition     = var.source_outbox_desired_count >= 0 && var.source_outbox_desired_count <= 3
    error_message = "source_outbox_desired_count must be between 0 and 3."
  }
}

variable "source_worker_cpu" {
  type    = number
  default = 512
}

variable "source_worker_memory" {
  type    = number
  default = 1024
}

variable "source_outbox_cpu" {
  type    = number
  default = 256
}

variable "source_outbox_memory" {
  type    = number
  default = 512
}

variable "source_dispatcher_cpu" {
  type    = number
  default = 256
}

variable "source_dispatcher_memory" {
  type    = number
  default = 512
}

variable "source_sqs_visibility_timeout_seconds" {
  type    = number
  default = 900
}

variable "source_sqs_visibility_heartbeat_seconds" {
  type    = number
  default = 300

  validation {
    condition     = var.source_sqs_visibility_heartbeat_seconds < var.source_sqs_visibility_timeout_seconds
    error_message = "Source SQS heartbeat must be shorter than its visibility timeout."
  }
}

variable "source_sqs_max_receive_count" {
  type    = number
  default = 5
}

variable "source_dispatch_schedule_expression" {
  description = "EventBridge schedule for the bounded source dispatcher."
  type        = string
  default     = "rate(15 minutes)"
}

variable "source_dispatch_schedule_enabled" {
  description = "Enable the bounded source dispatcher after manual source validation."
  type        = bool
  default     = false
}

variable "source_queue_depth_alarm_threshold" {
  type    = number
  default = 25
}

variable "source_queue_age_alarm_seconds" {
  type    = number
  default = 900
}

locals {
  source_runtime_environment = concat(
    local.common_environment,
    [
      { name = "SOURCE_SQS_QUEUE_URL", value = aws_sqs_queue.source.id },
      { name = "SOURCE_SQS_DLQ_URL", value = aws_sqs_queue.source_dlq.id },
      { name = "SOURCE_SQS_VISIBILITY_TIMEOUT_SECONDS", value = tostring(var.source_sqs_visibility_timeout_seconds) },
      { name = "SOURCE_SQS_VISIBILITY_HEARTBEAT_SECONDS", value = tostring(var.source_sqs_visibility_heartbeat_seconds) },
      { name = "SOURCE_SQS_MAX_RECEIVE_COUNT", value = tostring(var.source_sqs_max_receive_count) },
      { name = "LEVER_SITE_NAMES", value = jsonencode(var.lever_site_names) },
      { name = "ASHBY_BOARD_NAMES", value = jsonencode(var.ashby_board_names) },
      { name = "JOB_SOURCE_DISPATCH_BATCH_SIZE", value = "25" },
      { name = "JOB_SOURCE_MAX_INFLIGHT", value = "250" },
      { name = "JOB_SOURCE_LEASE_SECONDS", value = tostring(var.source_sqs_visibility_timeout_seconds) },
      { name = "APPLY_URL_CHECK_BATCH_SIZE", value = "50" },
      { name = "RAW_JOB_PAYLOAD_RETENTION_DAYS", value = "90" },
    ]
  )
}

resource "aws_sqs_queue" "source_dlq" {
  name                       = "${local.name}-source-tasks-dlq"
  message_retention_seconds  = 1209600
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = var.source_sqs_visibility_timeout_seconds
}

resource "aws_sqs_queue" "source" {
  name                       = "${local.name}-source-tasks"
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = var.source_sqs_visibility_timeout_seconds
}

resource "aws_sqs_queue_redrive_policy" "source" {
  queue_url = aws_sqs_queue.source.id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.source_dlq.arn
    maxReceiveCount     = var.source_sqs_max_receive_count
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "source_dlq" {
  queue_url = aws_sqs_queue.source_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.source.arn]
  })
}

resource "aws_cloudwatch_log_group" "source_runtime" {
  for_each = toset(["source-worker", "source-dispatcher", "outbox-v2"])

  name              = "/applyai/${var.environment}/${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role_policy" "ecs_task_source_queues" {
  name = "source-queue-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SourceQueues"
        Effect = "Allow"
        Action = [
          "sqs:ChangeMessageVisibility",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ReceiveMessage",
          "sqs:SendMessage"
        ]
        Resource = [
          aws_sqs_queue.source.arn,
          aws_sqs_queue.source_dlq.arn
        ]
      }
    ]
  })
}

resource "aws_ecs_task_definition" "source_worker" {
  family                   = "${local.name}-source-worker"
  cpu                      = tostring(var.source_worker_cpu)
  memory                   = tostring(var.source_worker_memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "source-worker"
      image       = local.image_uri
      essential   = true
      command     = ["python", "-m", "app.workers.source"]
      environment = local.source_runtime_environment
      secrets     = local.database_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.source_runtime["source-worker"].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "source-worker"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "source_worker" {
  name            = "${local.name}-source-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.source_worker.arn
  desired_count   = var.source_worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.app[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}

resource "aws_ecs_task_definition" "source_outbox" {
  family                   = "${local.name}-outbox-v2"
  cpu                      = tostring(var.source_outbox_cpu)
  memory                   = tostring(var.source_outbox_memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "outbox-v2"
      image       = local.image_uri
      essential   = true
      command     = ["python", "-m", "app.core.outbox"]
      environment = local.source_runtime_environment
      secrets     = local.database_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.source_runtime["outbox-v2"].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "outbox-v2"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "source_outbox" {
  name            = "${local.name}-outbox-v2"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.source_outbox.arn
  desired_count   = var.source_outbox_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.app[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}

resource "aws_ecs_task_definition" "source_dispatcher" {
  family                   = "${local.name}-source-dispatcher"
  cpu                      = tostring(var.source_dispatcher_cpu)
  memory                   = tostring(var.source_dispatcher_memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "source-dispatcher"
      image       = local.image_uri
      essential   = true
      command     = ["python", "-m", "app.jobs.dispatcher"]
      environment = local.source_runtime_environment
      secrets     = local.database_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.source_runtime["source-dispatcher"].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "source-dispatcher"
        }
      }
    }
  ])
}

resource "aws_iam_role" "source_eventbridge" {
  name = "${local.name}-source-eventbridge"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "source_eventbridge" {
  name = "run-source-dispatcher"
  role = aws_iam_role.source_eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = [aws_ecs_task_definition.source_dispatcher.arn]
      },
      {
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.ecs_execution.arn,
          aws_iam_role.ecs_task.arn
        ]
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "source_dispatch" {
  name                = "${local.name}-source-dispatch"
  description         = "Run the bounded durable job-source dispatcher."
  schedule_expression = var.source_dispatch_schedule_expression
  state               = var.source_dispatch_schedule_enabled ? "ENABLED" : "DISABLED"
}

resource "aws_cloudwatch_event_target" "source_dispatch" {
  rule     = aws_cloudwatch_event_rule.source_dispatch.name
  arn      = aws_ecs_cluster.main.arn
  role_arn = aws_iam_role.source_eventbridge.arn

  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.source_dispatcher.arn
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = aws_subnet.app[*].id
      security_groups  = [aws_security_group.ecs.id]
      assign_public_ip = false
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "source_queue_visible" {
  alarm_name          = "${local.name}-source-queue-depth"
  alarm_description   = "Source task queue depth remained above the staging threshold."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = var.source_queue_depth_alarm_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.source.name
  }
}

resource "aws_cloudwatch_metric_alarm" "source_queue_age" {
  alarm_name          = "${local.name}-source-oldest-message"
  alarm_description   = "Oldest visible source task exceeded the configured age threshold."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 5
  threshold           = var.source_queue_age_alarm_seconds
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions

  dimensions = {
    QueueName = aws_sqs_queue.source.name
  }
}

resource "aws_cloudwatch_metric_alarm" "source_dlq_visible" {
  alarm_name          = "${local.name}-source-dlq-not-empty"
  alarm_description   = "At least one source-platform task reached the DLQ."
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
    QueueName = aws_sqs_queue.source_dlq.name
  }
}

output "source_queue_url" {
  value = aws_sqs_queue.source.id
}

output "source_queue_arn" {
  value = aws_sqs_queue.source.arn
}

output "source_dlq_url" {
  value = aws_sqs_queue.source_dlq.id
}

output "source_dlq_arn" {
  value = aws_sqs_queue.source_dlq.arn
}

output "source_worker_service_name" {
  value = aws_ecs_service.source_worker.name
}

output "source_worker_task_definition_arn" {
  value = aws_ecs_task_definition.source_worker.arn
}

output "source_outbox_service_name" {
  value = aws_ecs_service.source_outbox.name
}

output "source_outbox_task_definition_arn" {
  value = aws_ecs_task_definition.source_outbox.arn
}

output "source_dispatch_task_family" {
  value = aws_ecs_task_definition.source_dispatcher.family
}

output "source_dispatch_rule_name" {
  value = aws_cloudwatch_event_rule.source_dispatch.name
}

output "migration_task_family" {
  value = aws_ecs_task_definition.migration.family
}

output "aurora_cluster_endpoint" {
  value = aws_rds_cluster.database.endpoint
}
