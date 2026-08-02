locals {
  ecs_task_assume_role_policy = jsonencode({
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

resource "aws_iam_role" "api_task" {
  name               = "${local.name}-api-task"
  assume_role_policy = local.ecs_task_assume_role_policy
}

resource "aws_iam_role_policy" "api_resume_objects" {
  name = "resume-object-access"
  role = aws_iam_role.api_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ResumeObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.resumes.arn}/*"
      }
    ]
  })
}

resource "aws_iam_role" "resume_worker_task" {
  name               = "${local.name}-resume-worker-task"
  assume_role_policy = local.ecs_task_assume_role_policy
}

resource "aws_iam_role_policy" "resume_worker_runtime" {
  name = "resume-worker-access"
  role = aws_iam_role.resume_worker_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadResumeObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.resumes.arn}/*"
      },
      {
        Sid    = "ConsumeResumeQueue"
        Effect = "Allow"
        Action = [
          "sqs:ChangeMessageVisibility",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ReceiveMessage"
        ]
        Resource = aws_sqs_queue.resume.arn
      }
    ]
  })
}

resource "aws_iam_role" "resume_outbox_task" {
  name               = "${local.name}-resume-outbox-task"
  assume_role_policy = local.ecs_task_assume_role_policy
}

resource "aws_iam_role_policy" "resume_outbox_queue" {
  name = "resume-queue-publish"
  role = aws_iam_role.resume_outbox_task.id

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
        Resource = aws_sqs_queue.resume.arn
      }
    ]
  })
}

resource "aws_iam_role" "source_worker_task" {
  name               = "${local.name}-source-worker-task"
  assume_role_policy = local.ecs_task_assume_role_policy
}

resource "aws_iam_role_policy" "source_worker_queue" {
  name = "source-queue-consume"
  role = aws_iam_role.source_worker_task.id

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
        Resource = aws_sqs_queue.source.arn
      }
    ]
  })
}

resource "aws_iam_role" "source_outbox_task" {
  name               = "${local.name}-source-outbox-task"
  assume_role_policy = local.ecs_task_assume_role_policy
}

resource "aws_iam_role_policy" "source_outbox_queues" {
  name = "task-queue-publish"
  role = aws_iam_role.source_outbox_task.id

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
        Resource = [
          aws_sqs_queue.resume.arn,
          aws_sqs_queue.source.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role" "database_task" {
  name               = "${local.name}-database-task"
  assume_role_policy = local.ecs_task_assume_role_policy
}
