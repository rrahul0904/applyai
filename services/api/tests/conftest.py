import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://applyai:applyai@localhost:55432/applyai_test",
    ),
)

from app.core.auth import AuthClaims, get_auth_claims  # noqa: E402
from app.core.database import get_session  # noqa: E402
from app.core.queue import InMemoryTaskQueue, get_task_queue  # noqa: E402
from app.core.storage import ObjectStorageProvider, get_object_storage  # noqa: E402
from app.main import app  # noqa: E402


class MemoryStorage(ObjectStorageProvider):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, *, key: str, content, content_type: str) -> None:
        del content_type
        self.objects[key] = content.read()

    def delete(self, *, key: str) -> None:
        self.objects.pop(key, None)

    def get(self, *, key: str) -> bytes:
        return self.objects[key]


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.environ["DATABASE_URL"]


@pytest.fixture()
def client(database_url: str) -> Generator[TestClient, None, None]:
    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    claims = {
        "value": AuthClaims(
            subject="clerk_user_a",
            email="a@example.com",
            first_name="A",
        )
    }
    storage = MemoryStorage()
    queue = InMemoryTaskQueue()

    def session_override() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    def claims_override() -> AuthClaims:
        return claims["value"]

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_auth_claims] = claims_override
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_task_queue] = lambda: queue

    with TestClient(app) as test_client:
        test_client.claims = claims  # type: ignore[attr-defined]
        test_client.storage = storage  # type: ignore[attr-defined]
        test_client.queue = queue  # type: ignore[attr-defined]
        yield test_client

    app.dependency_overrides.clear()
    table_names = [
        row[0]
        for row in engine.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
    ] if hasattr(engine, "execute") else []
    with engine.begin() as connection:
        if not table_names:
            table_names = [
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname='public' AND tablename <> 'alembic_version'"
                    )
                )
            ]
        if table_names:
            quoted = ", ".join(f'"{name}"' for name in table_names)
            connection.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    engine.dispose()


@pytest.fixture()
def switch_user(client: TestClient):
    def switch(subject: str, email: str) -> None:
        client.claims["value"] = AuthClaims(subject=subject, email=email)  # type: ignore[attr-defined]

    return switch
