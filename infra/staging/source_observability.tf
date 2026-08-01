resource "aws_cloudwatch_log_metric_filter" "source_postings_fetched" {
  name           = "${local.name}-source-postings-fetched"
  log_group_name = aws_cloudwatch_log_group.runtime["ingestion"].name
  pattern        = "{ $.event = \"source_ingest_completed\" && $.counts.fetched = * }"

  metric_transformation {
    name      = "SourcePostingsFetched"
    namespace = "ApplyAI/${var.environment}"
    value     = "$.counts.fetched"
  }
}

resource "aws_cloudwatch_log_metric_filter" "source_canonical_changes" {
  name           = "${local.name}-source-canonical-changes"
  log_group_name = aws_cloudwatch_log_group.runtime["ingestion"].name
  pattern        = "{ $.event = \"source_ingest_completed\" && $.counts = * }"

  metric_transformation {
    name      = "SourceIngestionRuns"
    namespace = "ApplyAI/${var.environment}"
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "source_health_failures" {
  name           = "${local.name}-source-health-failures"
  log_group_name = aws_cloudwatch_log_group.runtime["ingestion"].name
  pattern        = "{ $.event = \"job_ingestion_failed\" || $.event = \"source_ingest_failed\" }"

  metric_transformation {
    name      = "SourceHealthFailures"
    namespace = "ApplyAI/${var.environment}"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "source_health_failures" {
  alarm_name          = "${local.name}-source-health-failures"
  alarm_description   = "Source health/ingestion failures exceeded the initial staging threshold."
  namespace           = "ApplyAI/${var.environment}"
  metric_name         = "SourceHealthFailures"
  statistic           = "Sum"
  period              = 900
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.alarm_actions
}
