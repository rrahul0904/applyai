from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect


def test_database_is_at_alembic_head(database_url):
    root = Path(__file__).resolve().parents[1]
    config = Config(root / "alembic.ini")
    config.set_main_option("script_location", str(root / "alembic"))
    script = ScriptDirectory.from_config(config)
    expected_head = script.get_current_head()
    engine = create_engine(database_url)
    with engine.connect() as connection:
        current = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
        tables = set(inspect(connection).get_table_names())
    engine.dispose()
    assert current == expected_head
    assert {
        "users",
        "candidate_profiles",
        "resumes",
        "resume_versions",
        "companies",
        "jobs",
        "job_sources",
        "raw_job_postings",
        "saved_jobs",
        "applications",
        "application_events",
    }.issubset(tables)
