data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

resource "aws_ecr_repository" "api" {
  name                 = "${local.name}-api"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the 20 most recent staging images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 20
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_s3_bucket" "resumes" {
  bucket = "${local.name}-resumes-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_public_access_block" "resumes" {
  bucket = aws_s3_bucket.resumes.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "resumes" {
  bucket = aws_s3_bucket.resumes.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "resumes" {
  bucket = aws_s3_bucket.resumes.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "resumes" {
  bucket = aws_s3_bucket.resumes.id

  cors_rule {
    allowed_headers = ["Content-Type", "x-amz-server-side-encryption"]
    allowed_methods = ["PUT", "HEAD"]
    allowed_origins = [var.web_origin]
    expose_headers  = ["ETag"]
    max_age_seconds = 300
  }
}

resource "aws_sqs_queue" "resume_dlq" {
  name                       = "${local.name}-resume-processing-dlq"
  message_retention_seconds  = 1209600
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = var.sqs_visibility_timeout_seconds
}

resource "aws_sqs_queue" "resume" {
  name                       = "${local.name}-resume-processing"
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true
  visibility_timeout_seconds = var.sqs_visibility_timeout_seconds
}

resource "aws_sqs_queue_redrive_policy" "resume" {
  queue_url = aws_sqs_queue.resume.id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.resume_dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "resume_dlq" {
  queue_url = aws_sqs_queue.resume_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.resume.arn]
  })
}

resource "aws_db_subnet_group" "database" {
  name       = "${local.name}-database"
  subnet_ids = aws_subnet.db[*].id

  tags = {
    Name = "${local.name}-database-subnets"
  }
}

resource "aws_rds_cluster" "database" {
  cluster_identifier = "${local.name}-postgres"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  database_name      = var.database_name
  master_username    = var.database_master_username

  manage_master_user_password = true
  storage_encrypted           = true

  db_subnet_group_name   = aws_db_subnet_group.database.name
  vpc_security_group_ids = [aws_security_group.database.id]

  backup_retention_period = 7
  copy_tags_to_snapshot   = true
  deletion_protection     = false
  skip_final_snapshot     = true

  serverlessv2_scaling_configuration {
    min_capacity = var.aurora_min_acu
    max_capacity = var.aurora_max_acu
  }
}

resource "aws_rds_cluster_instance" "database" {
  identifier         = "${local.name}-postgres-1"
  cluster_identifier = aws_rds_cluster.database.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.database.engine
  engine_version     = aws_rds_cluster.database.engine_version

  db_subnet_group_name = aws_db_subnet_group.database.name
  publicly_accessible  = false
}
