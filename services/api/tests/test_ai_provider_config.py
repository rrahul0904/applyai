import pytest

from app.ai.provider import AIProviderError, OpenAIResponsesProvider
from app.core.config import Settings


def test_api_can_describe_openai_intent_without_holding_model_secret():
    settings = Settings(
        ai_provider="openai",
        task_queue_provider="memory",
        openai_api_key=None,
    )
    assert settings.ai_provider == "openai"
    assert settings.openai_api_key is None

    with pytest.raises(AIProviderError, match="OPENAI_API_KEY_MISSING"):
        OpenAIResponsesProvider(settings)


def test_staging_openai_requires_dedicated_ai_queues():
    with pytest.raises(ValueError, match="AI_SQS_QUEUE_URL and AI_SQS_DLQ_URL"):
        Settings(
            app_env="staging",
            auth_provider="clerk",
            clerk_issuer="https://example.clerk.accounts.dev",
            clerk_jwks_url="https://example.clerk.accounts.dev/.well-known/jwks.json",
            object_storage_provider="s3",
            s3_bucket="applyai-staging-resumes",
            task_queue_provider="sqs",
            sqs_queue_url="https://sqs.us-east-1.amazonaws.com/123/resume",
            sqs_dlq_url="https://sqs.us-east-1.amazonaws.com/123/resume-dlq",
            web_origin="https://staging.example.com",
            ai_provider="openai",
            ai_sqs_queue_url=None,
            ai_sqs_dlq_url=None,
        )
