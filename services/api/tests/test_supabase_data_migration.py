from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from scripts.migrate_postgres_to_supabase import (
    load_identity_map,
    normalize_migrated_row,
    normalize_postgres_url,
)


def test_normalize_postgres_url_uses_psycopg3() -> None:
    assert normalize_postgres_url("postgresql://user:pass@db.example/applyai").startswith(
        "postgresql+psycopg://"
    )


def test_identity_map_accepts_explicit_email_mapping(tmp_path) -> None:
    expected = uuid.uuid4()
    path = tmp_path / "identity-map.json"
    path.write_text(
        json.dumps(
            [
                {
                    "email": "Candidate@Example.com",
                    "supabase_auth_user_id": str(expected),
                }
            ]
        )
    )
    assert load_identity_map(path) == {"candidate@example.com": expected}


def test_identity_map_rejects_duplicate_email(tmp_path) -> None:
    path = tmp_path / "identity-map.json"
    path.write_text(
        json.dumps(
            [
                {"email": "same@example.com", "supabase_auth_user_id": str(uuid.uuid4())},
                {"email": "SAME@example.com", "supabase_auth_user_id": str(uuid.uuid4())},
            ]
        )
    )
    with pytest.raises(ValueError, match="Duplicate identity-map email"):
        load_identity_map(path)


def test_user_identity_link_preserves_internal_id() -> None:
    internal_id = uuid.uuid4()
    auth_id = uuid.uuid4()
    row, changes = normalize_migrated_row(
        "users",
        {
            "id": internal_id,
            "email": "candidate@example.com",
            "auth_user_id": None,
            "auth_provider": "clerk",
        },
        identity_map={"candidate@example.com": auth_id},
        now=datetime.now(UTC),
    )
    assert row["id"] == internal_id
    assert row["auth_user_id"] == auth_id
    assert row["auth_provider"] == "supabase"
    assert changes == ["linked_supabase_identity"]


def test_running_task_lease_is_reset_for_cutover() -> None:
    now = datetime.now(UTC)
    row, changes = normalize_migrated_row(
        "postgres_tasks",
        {
            "status": "RUNNING",
            "available_at": now - timedelta(minutes=5),
            "lease_owner": "railway-worker",
            "leased_at": now - timedelta(minutes=1),
            "lease_expires_at": now - timedelta(seconds=1),
            "last_error": None,
        },
        identity_map={},
        now=now,
    )
    assert row["status"] == "RETRY_WAIT"
    assert row["available_at"] == now
    assert row["lease_owner"] is None
    assert row["leased_at"] is None
    assert row["lease_expires_at"] is None
    assert row["last_error"] == "MIGRATION_LEASE_RESET"
    assert changes == ["reset_expired_task_lease"]


def test_expired_source_lease_is_cleared() -> None:
    now = datetime.now(UTC)
    row, changes = normalize_migrated_row(
        "job_source_registry",
        {
            "locked_at": now - timedelta(minutes=10),
            "locked_by": "railway-source-worker",
            "lease_expires_at": now - timedelta(seconds=1),
        },
        identity_map={},
        now=now,
    )
    assert row["locked_at"] is None
    assert row["locked_by"] is None
    assert row["lease_expires_at"] is None
    assert changes == ["clear_expired_source_lease"]
