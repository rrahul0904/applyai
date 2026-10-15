from app.core.config import Settings
from app.readiness import build_readiness_response


def configured_settings() -> Settings:
    return Settings(
        app_env="development",
        auth_provider="clerk",
        clerk_issuer="https://applyai.clerk.accounts.dev",
        clerk_jwks_url="https://applyai.clerk.accounts.dev/.well-known/jwks.json",
        object_storage_provider="postgres",
        task_queue_provider="postgres",
        worker_drain_secret="a-long-enough-worker-drain-secret",
        operator_emails="ops@example.test",
    )


def readiness(**overrides):
    values = {
        "database_reachable": True,
        "database_migrations_current": True,
        "storage_reachable": True,
        "operator_auth_configured": True,
        "task_queue_configured": True,
        "background_worker_healthy": True,
        "deployed_sha": "a" * 40,
    }
    values.update(overrides)
    return build_readiness_response(configured_settings(), **values)


def test_readiness_requires_every_runtime_dependency():
    response = readiness()

    assert response.status == "ready"
    assert response.auth_configured is True
    assert response.auth_instance_match is True
    assert response.background_worker_configured is True
    assert response.deployment_sha == "a" * 40


def test_readiness_is_not_ready_when_any_runtime_dependency_is_missing():
    required_checks = (
        "database_reachable",
        "database_migrations_current",
        "storage_reachable",
        "operator_auth_configured",
        "task_queue_configured",
        "background_worker_healthy",
    )
    for check in required_checks:
        assert readiness(**{check: False}).status == "not_ready"

    assert readiness(deployed_sha="").status == "not_ready"


def test_readiness_rejects_dev_auth_and_unconfigured_worker():
    dev_settings = Settings(
        app_env="development",
        auth_provider="dev-test",
        dev_auth_enabled=True,
        dev_auth_secret="development-secret-value",
        object_storage_provider="postgres",
        task_queue_provider="postgres",
        worker_drain_secret="a-long-enough-worker-drain-secret",
        operator_emails="ops@example.test",
    )
    response = build_readiness_response(
        dev_settings,
        database_reachable=True,
        database_migrations_current=True,
        storage_reachable=True,
        operator_auth_configured=True,
        task_queue_configured=True,
        background_worker_healthy=True,
        deployed_sha="b" * 40,
    )

    assert response.status == "not_ready"
    assert response.auth_configured is False

    workerless_settings = configured_settings().model_copy(
        update={"worker_drain_secret": None}
    )
    response = build_readiness_response(
        workerless_settings,
        database_reachable=True,
        database_migrations_current=True,
        storage_reachable=True,
        operator_auth_configured=True,
        task_queue_configured=True,
        background_worker_healthy=True,
        deployed_sha="c" * 40,
    )
    assert response.status == "not_ready"
    assert response.background_worker_configured is False
