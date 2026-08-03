from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.jobs.demo import write_demo_artifact


def test_job_source_demo_builds_real_pipeline_evidence(database_url, tmp_path):
    engine = create_engine(database_url)
    output_dir = tmp_path / "job-source-demo"

    with Session(engine, expire_on_commit=False) as session:
        report = write_demo_artifact(session, output_dir)

    assert report["totals"] == {
        "provider_sources": 3,
        "source_postings": 6,
        "canonical_jobs": 4,
        "deduplicated_postings": 2,
        "invalid_quarantined": 1,
        "shared_job_sources": 3,
    }
    assert all(report["assertions"].values())
    assert report["shared_job"]["status"] == "ACTIVE"
    assert sum(
        1 for source in report["shared_job"]["sources"] if source["is_primary"]
    ) == 1
    assert next(
        source
        for source in report["shared_job"]["sources"]
        if source["is_primary"]
    )["provider"] == "GREENHOUSE"
    assert report["scope"] == {
        "real_pipeline": True,
        "real_postgresql": True,
        "live_provider_calls": False,
        "aws_required": False,
        "external_accounts_required": False,
    }
    assert (output_dir / "index.html").is_file()
    assert (output_dir / "report.json").is_file()
    assert "One trusted job catalog" in (output_dir / "index.html").read_text()
