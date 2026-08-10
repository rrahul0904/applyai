output "agent_queue_url" {
  description = "Dedicated governed Agent Runtime SQS queue URL."
  value       = aws_sqs_queue.agent.id
}

output "agent_dlq_url" {
  description = "Dedicated governed Agent Runtime dead-letter queue URL."
  value       = aws_sqs_queue.agent_dlq.id
}

output "agent_worker_service_name" {
  description = "Governed Agent Worker ECS service."
  value       = aws_ecs_service.agent_worker.name
}
