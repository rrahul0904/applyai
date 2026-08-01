output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "app_subnet_ids" {
  value = aws_subnet.app[*].id
}

output "db_subnet_ids" {
  value = aws_subnet.db[*].id
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "ecs_security_group_id" {
  value = aws_security_group.ecs.id
}

output "api_alb_dns_name" {
  value = aws_lb.api.dns_name
}

output "api_alb_zone_id" {
  value = aws_lb.api.zone_id
}

output "api_target_group_arn" {
  value = aws_lb_target_group.api.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "resume_bucket_name" {
  value = aws_s3_bucket.resumes.id
}

output "resume_queue_url" {
  value = aws_sqs_queue.resume.id
}

output "resume_queue_arn" {
  value = aws_sqs_queue.resume.arn
}

output "resume_dlq_url" {
  value = aws_sqs_queue.resume_dlq.id
}

output "resume_dlq_arn" {
  value = aws_sqs_queue.resume_dlq.arn
}

output "aurora_endpoint" {
  value = aws_rds_cluster.database.endpoint
}

output "aurora_port" {
  value = aws_rds_cluster.database.port
}

output "aurora_master_secret_arn" {
  value = aws_rds_cluster.database.master_user_secret[0].secret_arn
}

output "api_task_definition_arn" {
  value = aws_ecs_task_definition.api.arn
}

output "worker_task_definition_arn" {
  value = aws_ecs_task_definition.worker.arn
}

output "outbox_task_definition_arn" {
  value = aws_ecs_task_definition.outbox.arn
}

output "ingestion_task_definition_arn" {
  value = aws_ecs_task_definition.ingestion.arn
}

output "migration_task_definition_arn" {
  value = aws_ecs_task_definition.migration.arn
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "worker_service_name" {
  value = aws_ecs_service.worker.name
}

output "outbox_service_name" {
  value = aws_ecs_service.outbox.name
}
