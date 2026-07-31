from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV"),
    )
    database_url: str = "postgresql+psycopg://applyai:applyai@localhost:55432/applyai"
    database_host: str | None = None
    database_port: int = Field(default=5432, ge=1, le=65_535)
    database_name: str | None = None
    database_user: str | None = None
    database_password: str | None = None
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=200)
    database_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    database_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86_400)

    auth_provider: str = "clerk"
    dev_auth_enabled: bool = False
    dev_auth_secret: str | None = None
    clerk_issuer: str | None = None
    clerk_jwks_url: str | None = None
    clerk_audience: str | None = None
    internal_api_token: str | None = None

    object_storage_provider: str = "local"
    local_storage_path: Path = Field(default=Path(".data/resumes"))
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    s3_upload_expiration_seconds: int = Field(default=900, ge=60, le=3600)

    task_queue_provider: str = "memory"
    sqs_queue_url: str | None = None
    sqs_dlq_url: str | None = None
    sqs_region: str = "us-east-1"
    sqs_visibility_timeout_seconds: int = Field(default=300, ge=30, le=43_200)
    sqs_visibility_heartbeat_seconds: int = Field(default=120, ge=10, le=3600)
    sqs_wait_time_seconds: int = Field(default=20, ge=1, le=20)
    sqs_max_receive_count: int = Field(default=5, ge=1, le=100)
    resume_processing_timeout_seconds: int = Field(default=900, ge=60, le=86_400)
    outbox_batch_size: int = Field(default=25, ge=1, le=100)
    outbox_retry_base_seconds: int = Field(default=5, ge=1, le=300)
    outbox_lock_timeout_seconds: int = Field(default=300, ge=30, le=3600)

    web_origin: str = "http://localhost:3000"
    max_resume_bytes: int = 5 * 1024 * 1024
    seed_development_jobs: bool = False

    greenhouse_board_tokens: list[str] = Field(default_factory=list)
    lever_site_names: list[str] = Field(default_factory=list)
    ashby_board_names: list[str] = Field(default_factory=list)
    job_unknown_after_misses: int = Field(default=1, ge=1, le=20)
    job_stale_after_misses: int = Field(default=3, ge=2, le=50)
    job_source_claim_batch_size: int = Field(default=10, ge=1, le=100)
    job_source_lease_seconds: int = Field(default=900, ge=60, le=43_200)
    job_source_default_interval_seconds: int = Field(default=21_600, ge=300, le=2_592_000)
    job_source_failure_max_backoff_seconds: int = Field(
        default=604_800, ge=3_600, le=2_592_000
    )
    job_source_request_timeout_seconds: float = Field(default=20.0, ge=1.0, le=120.0)
    job_source_max_pages: int = Field(default=20, ge=1, le=100)

    career_discovery_max_pages: int = Field(default=8, ge=2, le=40)
    career_discovery_max_bytes: int = Field(
        default=2 * 1024 * 1024,
        ge=64 * 1024,
        le=10 * 1024 * 1024,
    )
    career_discovery_max_redirects: int = Field(default=4, ge=0, le=10)
    career_discovery_timeout_seconds: float = Field(default=12.0, ge=1.0, le=60.0)
    career_discovery_min_source_confidence: float = Field(default=0.80, ge=0.0, le=1.0)
    career_discovery_refresh_interval_seconds: int = Field(
        default=604_800,
        ge=3_600,
        le=7_776_000,
    )

    @model_validator(mode="after")
    def guard_runtime_configuration(self) -> "Settings":
        database_components = {
            "DATABASE_HOST": self.database_host,
            "DATABASE_NAME": self.database_name,
            "DATABASE_USER": self.database_user,
            "DATABASE_PASSWORD": self.database_password,
        }
        supplied_database_components = [
            name for name, value in database_components.items() if value is not None
        ]
        if supplied_database_components and len(supplied_database_components) != len(
            database_components
        ):
            missing = [name for name, value in database_components.items() if value is None]
            raise ValueError(
                "Database component configuration is incomplete; missing "
                + ", ".join(missing)
            )
        if supplied_database_components:
            user = quote(self.database_user or "", safe="")
            password = quote(self.database_password or "", safe="")
            database_name = quote(self.database_name or "", safe="")
            self.database_url = (
                f"postgresql+psycopg://{user}:{password}@{self.database_host}:"
                f"{self.database_port}/{database_name}"
            )

        environment = self.app_env.lower()
        durable_environment = environment in {"staging", "production"}

        if self.web_origin == "*":
            raise ValueError("WEB_ORIGIN cannot be '*' when credentialed CORS is enabled")

        if environment == "production" and (
            self.dev_auth_enabled or self.auth_provider == "dev-test"
        ):
            raise ValueError("Development authentication cannot run in production")
        if durable_environment and self.auth_provider != "clerk":
            raise ValueError(f"{environment.title()} requires AUTH_PROVIDER=clerk")
        if self.auth_provider == "dev-test":
            if not self.dev_auth_enabled:
                raise ValueError("AUTH_PROVIDER=dev-test requires DEV_AUTH_ENABLED=true")
            if not self.dev_auth_secret or len(self.dev_auth_secret) < 16:
                raise ValueError(
                    "Development authentication requires DEV_AUTH_SECRET with at least 16 characters"
                )
        if self.internal_api_token is not None and len(self.internal_api_token) < 24:
            raise ValueError("INTERNAL_API_TOKEN must contain at least 24 characters")

        if self.object_storage_provider not in {"local", "s3"}:
            raise ValueError("OBJECT_STORAGE_PROVIDER must be local or s3")
        if self.object_storage_provider == "s3" and not self.s3_bucket:
            raise ValueError("S3_BUCKET is required when OBJECT_STORAGE_PROVIDER=s3")
        if durable_environment and self.object_storage_provider != "s3":
            raise ValueError(f"{environment.title()} requires OBJECT_STORAGE_PROVIDER=s3")

        if self.task_queue_provider not in {"memory", "sqs"}:
            raise ValueError("TASK_QUEUE_PROVIDER must be memory or sqs")
        if self.task_queue_provider == "sqs" and not self.sqs_queue_url:
            raise ValueError("SQS_QUEUE_URL is required when TASK_QUEUE_PROVIDER=sqs")
        if durable_environment and self.task_queue_provider != "sqs":
            raise ValueError(f"{environment.title()} requires TASK_QUEUE_PROVIDER=sqs")
        if durable_environment and not self.sqs_dlq_url:
            raise ValueError(f"{environment.title()} requires SQS_DLQ_URL")
        if self.sqs_visibility_heartbeat_seconds >= self.sqs_visibility_timeout_seconds:
            raise ValueError("SQS visibility heartbeat must be shorter than visibility timeout")
        if self.resume_processing_timeout_seconds < self.sqs_visibility_timeout_seconds:
            raise ValueError(
                "RESUME_PROCESSING_TIMEOUT_SECONDS must be at least SQS visibility timeout"
            )
        if self.job_stale_after_misses <= self.job_unknown_after_misses:
            raise ValueError(
                "JOB_STALE_AFTER_MISSES must be greater than JOB_UNKNOWN_AFTER_MISSES"
            )
        if self.career_discovery_max_pages < 2:
            raise ValueError("CAREER_DISCOVERY_MAX_PAGES must allow robots and one target page")

        if durable_environment:
            if not self.clerk_issuer or not self.clerk_jwks_url:
                raise ValueError(
                    f"{environment.title()} requires CLERK_ISSUER and CLERK_JWKS_URL"
                )
            if not self.web_origin.startswith("https://"):
                raise ValueError(f"{environment.title()} requires an HTTPS WEB_ORIGIN")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
