import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.auth import DevTestAuthProvider
from app.core.config import Settings


def request_with_headers(headers: dict[str, str]) -> Request:
    encoded = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    return Request({"type": "http", "headers": encoded})


def test_dev_auth_requires_explicit_secret():
    with pytest.raises(ValueError):
        Settings(auth_provider="dev-test", dev_auth_enabled=True, dev_auth_secret="short")


def test_dev_auth_is_impossible_in_production():
    with pytest.raises(ValueError, match="cannot run in production"):
        Settings(
            app_env="production",
            auth_provider="dev-test",
            dev_auth_enabled=True,
            dev_auth_secret="development-secret-value",
        )


def test_dev_auth_creates_stable_claims():
    provider = DevTestAuthProvider(
        Settings(
            auth_provider="dev-test",
            dev_auth_enabled=True,
            dev_auth_secret="development-secret-value",
        )
    )
    claims = provider.authenticate(
        request_with_headers(
            {
                "x-applyai-dev-user": "alex.candidate@example.test",
                "x-applyai-dev-secret": "development-secret-value",
            }
        )
    )
    assert claims.subject == "dev:alex.candidate@example.test"
    assert claims.email == "alex.candidate@example.test"


def test_dev_auth_rejects_wrong_secret():
    provider = DevTestAuthProvider(
        Settings(
            auth_provider="dev-test",
            dev_auth_enabled=True,
            dev_auth_secret="development-secret-value",
        )
    )
    with pytest.raises(HTTPException) as exc:
        provider.authenticate(
            request_with_headers(
                {
                    "x-applyai-dev-user": "candidate@example.test",
                    "x-applyai-dev-secret": "wrong",
                }
            )
        )
    assert exc.value.status_code == 401
