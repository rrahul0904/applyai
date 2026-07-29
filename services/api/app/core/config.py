from functools import lru_cache
from pathlib import Path

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
    auth_provider: str = "clerk"
    dev_auth_enabled: bool = False
    dev_auth_secret: str | None = None
    clerk_issuer: str | None = None
    clerk_jwks_url: str | None = None
    clerk_audience: str | None = None
    object_storage_provider: str = "local"
    local_storage_path: Path = Field(default=Path(".data/resumes"))
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    web_origin: str = "http://localhost:3000"
    max_resume_bytes: int = 5 * 1024 * 1024
    seed_development_jobs: bool = False

    @model_validator(mode="after")
    def guard_development_auth(self) -> "Settings":
        environment = self.app_env.lower()
        if environment == "production" and (
            self.dev_auth_enabled or self.auth_provider == "dev-test"
        ):
            raise ValueError("Development authentication cannot run in production")
        if self.auth_provider == "dev-test":
            if not self.dev_auth_enabled:
                raise ValueError("AUTH_PROVIDER=dev-test requires DEV_AUTH_ENABLED=true")
            if not self.dev_auth_secret or len(self.dev_auth_secret) < 16:
                raise ValueError(
                    "Development authentication requires DEV_AUTH_SECRET with at least 16 characters"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
