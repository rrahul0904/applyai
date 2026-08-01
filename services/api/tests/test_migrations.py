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
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        resume_indexes = {index["name"] for index in inspector.get_indexes("resumes")}
        extraction_indexes = {
            index["name"] for index in inspector.get_indexes("resume_extractions")
        }
        application_indexes = {
            index["name"] for index in inspector.get_indexes("applications")
        }
        source_link_indexes = {
            index["name"] for index in inspector.get_indexes("job_source_links")
        }
        outbox_indexes = {
            index["name"] for index in inspector.get_indexes("task_outbox")
        }
    engine.dispose()
    assert current == expected_head
    assert {
        "users",
        "candidate_profiles",
        "resumes",
        "resume_versions",
        "resume_extractions",
        "resume_processing_attempts",
        "task_outbox",
        "companies",
        "company_sources",
        "jobs",
        "job_sources",
        "raw_job_postings",
        "job_ingestion_runs",
        "saved_jobs",
        "applications",
        "application_events",
    }.issubset(tables)
    assert "uq_resumes_one_master_per_user" in resume_indexes
    assert "uq_resume_extractions_version_parser" in extraction_indexes
    assert "ix_applications_user_updated_id" in application_indexes
    assert "ix_job_source_links_job_source_id" in source_link_indexes
    assert "ix_task_outbox_claim" in outbox_indexes
