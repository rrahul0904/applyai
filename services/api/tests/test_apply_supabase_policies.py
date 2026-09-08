import pytest

from scripts.apply_supabase_policies import psycopg_dsn


def test_policy_dsn_strips_sqlalchemy_driver() -> None:
    dsn = psycopg_dsn(
        "postgresql+psycopg://applyai:secret@db.example.com:5432/postgres"
    )
    assert dsn.startswith("postgresql://")
    assert "db.example.com" in dsn


def test_policy_dsn_rejects_non_postgres() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        psycopg_dsn("sqlite:///applyai.db")
