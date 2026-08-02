locals {
  image_uri = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"

  common_environment = [
    { name = "ENVIRONMENT", value = var.environment },
    { name = "AUTH_PROVIDER", value = "clerk" },
    { name = "CLERK_ISSUER", value = var.clerk_issuer },
    { name = "CLERK_JWKS_URL", value = var.clerk_jwks_url },
    { name = "CLERK_AUDIENCE", value = var.clerk_audience },
    { name = "DATABASE_HOST", value = aws_rds_cluster.database.endpoint },
    { name = "DATABASE_PORT", value = tostring(aws_rds_cluster.database.port) },
    { name = "DATABASE_NAME", value = var.database_name },
    { name = "DATABASE_POOL_SIZE", value = "10" },
    { name = "DATABASE_MAX_OVERFLOW", value = "20" },
    { name = "DATABASE_POOL_TIMEOUT_SECONDS", value = "30" },
    { name = "DATABASE_POOL_RECYCLE_SECONDS", value = "1800" },
    { name = "OBJECT_STORAGE_PROVIDER", value = "s3" },
    { name = "S3_BUCKET", value = aws_s3_bucket.resumes.id },
    { name = "S3_REGION", value = var.aws_region },
    { name = "S3_UPLOAD_EXPIRATION_SECONDS", value = "900" },
    { name = "TASK_QUEUE_PROVIDER", value = "sqs" },
    { name = "SQS_QUEUE_URL", value = aws_sqs_queue.resume.id },
    { name = "SQS_DLQ_URL", value = aws_sqs_queue.resume_dlq.id },
    { name = "SQS_REGION", value = var.aws_region },
    { name = "SQS_VISIBILITY_TIMEOUT_SECONDS", value = tostring(var.sqs_visibility_timeout_seconds) },
    { name = "SQS_VISIBILITY_HEARTBEAT_SECONDS", value = tostring(var.sqs_visibility_heartbeat_seconds) },
    { name = "SQS_WAIT_TIME_SECONDS", value = "20" },
    { name = "SQS_MAX_RECEIVE_COUNT", value = tostring(var.sqs_max_receive_count) },
    { name = "RESUME_PROCESSING_TIMEOUT_SECONDS", value = tostring(var.resume_processing_timeout_seconds) },
    { name = "OUTBOX_BATCH_SIZE", value = "25" },
    { name = "OUTBOX_RETRY_BASE_SECONDS", value = "5" },
    { name = "OUTBOX_LOCK_TIMEOUT_SECONDS", value = "300" },
    { name = "GREENHOUSE_BOARD_TOKENS", value = jsonencode(var.greenhouse_board_tokens) },
    { name = "JOB_UNKNOWN_AFTER_MISSES", value = "1" },
    { name = "JOB_STALE_AFTER_MISSES", value = "3" },
    { name = "WEB_ORIGIN", value = var.web_origin },
    { name = "SEED_DEVELOPMENT_JOBS", value = "false" },
  ]

  database_secrets = [
    {
      name      = "DATABASE_USER"
      valueFrom = "${aws_rds_cluster.database.master_user_secret[0].secret_arn}:username::"
    },
    {
      name      = "DATABASE_PASSWORD"
      valueFrom = "${aws_rds_cluster.database.master_user_secret[0].secret_arn}:password::"
    },
  ]
}

resource "aws_cloudwatch_log_group" "runtime" {
  for_each = toset(["api", "worker", "outbox", "ingestion", "migration"])

  name              = "/applyai/${var.environment}/${each.key}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "ecs_execution" {
  name = "${local.name}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_database_secret" {
  name = "database-secret"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_rds_cluster.database.master_user_secret[0].secret_arn
      }
    ]
  })
}

resource "aws_ecs_cluster" "main" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  cpu                      = tostring(var.api_cpu)
  memory                   = tostring(var.api_memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.api_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = local.image_uri
      essential = true
      command   = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]
      environment = local.common_environment
      secrets     = local.database_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.runtime["api"].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  cpu                      = tostring(var.worker_cpu)
  memory                   = tostring(var.worker_memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.resume_worker_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "worker"
      image       = local.image_uri
      essential   = true
      command     = ["python", "-m", "app.workers.resume"]
      environment = local.common_environment
      secrets     = local.database_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.runtime["worker"].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "outbox" {
  family                   = "${local.name}-outbox"
  cpu                      = tostring(var.outbox_cpu)
  memory                   = tostring(var.outbox_memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.resume_outbox_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "outbox"
      image       = local.image_uri
      essential   = true
      command     = ["python", "-m", "app.core.outbox"]
      environment = local.common_environment
      secrets     = local.database_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.runtime["outbox"].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "outbox"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "ingestion" {
  family                   = "${local.name}-ingestion"
  cpu                      = tostring(var.ingestion_cpu)
  memory                   = tostring(var.ingestion_memory)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.database_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "ingestion"
      image       = local.image_uri
      essential   = true
      command     = ["python", "-m", "app.jobs.ingest"]
      environment = local.common_environment
      secrets     = local.database_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.runtime["ingestion"].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ingestion"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "${local.name}-migration"
  cpu                      = "256"
  memory                   = "512"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.database_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name        = "migration"
      image       = local.image_uri
      essential   = true
      command     = ["alembic", "upgrade", "head"]
      environment = local.common_environment
      secrets     = local.database_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.runtime["migration"].name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "migration"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "${local.name}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 60

  network_configuration {
    subnets          = aws_subnet.app[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https]
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.app[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}

resource "aws_ecs_service" "outbox" {
  name            = "${local.name}-outbox"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.outbox.arn
  desired_count   = var.outbox_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.app[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}

resource "aws_iam_role" "eventbridge" {
  name = "${local.name}-eventbridge"

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

resource "aws_iam_role_policy" "eventbridge" {
  name = "run-ingestion-task"
  role = aws_iam_role.eventbridge.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = [aws_ecs_task_definition.ingestion.arn]
      },
      {
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.ecs_execution.arn,
          aws_iam_role.database_task.arn
        ]
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "greenhouse_ingestion" {
  name                = "${local.name}-greenhouse-ingestion"
  description         = "Run public Greenhouse ingestion on a bounded staging schedule"
  schedule_expression = var.ingestion_schedule_expression
  state               = var.ingestion_schedule_enabled ? "ENABLED" : "DISABLED"
}

resource "aws_cloudwatch_event_target" "greenhouse_ingestion" {
  rule     = aws_cloudwatch_event_rule.greenhouse_ingestion.name
  arn      = aws_ecs_cluster.main.arn
  role_arn = aws_iam_role.eventbridge.arn

  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.ingestion.arn
    launch_type         = "FARGATE"

    network_configuration {
      subnets          = aws_subnet.app[*].id
      security_groups  = [aws_security_group.ecs.id]
      assign_public_ip = false
    }
  }
}
