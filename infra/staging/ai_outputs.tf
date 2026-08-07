output "ai_worker_service_name" {
  value = aws_ecs_service.ai_worker.name
}

output "ai_outbox_service_name" {
  value = aws_ecs_service.universal_outbox.name
}

output "ai_worker_log_group_name" {
  value = aws_cloudwatch_log_group.ai_runtime["ai-worker"].name
}

output "ai_outbox_log_group_name" {
  value = aws_cloudwatch_log_group.ai_runtime["outbox-v3"].name
}
