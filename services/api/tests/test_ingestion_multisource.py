from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.jobs.pipeline import JobIngestionPipeline
from app.models import Job, JobSource
from tests.test_ingestion_lifecycle import MutableGreenhouseConnector, posting


def test_one_missing_source_does_not_stale_job_seen_by_another_source(database_url):
    engine = create_engine(database_url)
    settings = Settings(job_unknown_after_misses=1, job_stale_after_misses=2)
    board_a = MutableGreenhouseConnector("board-a", [
        posting(board="board-a", post_id=1, internal_job_id=101, url="https://jobs.example.test/a")
    ])
    board_b = MutableGreenhouseConnector("board-b", [
        posting(board="board-b", post_id=2, internal_job_id=202, url="https://jobs.example.test/b")
    ])

    with Session(engine) as session:
        JobIngestionPipeline(session, settings).run(board_a)
        JobIngestionPipeline(session, settings).run(board_b)
        assert session.scalar(select(func.count(Job.id))) == 1

        board_a.records = []
        JobIngestionPipeline(session, settings).run(board_a)
        JobIngestionPipeline(session, settings).run(board_a)

        job = session.scalar(select(Job))
        sources = list(session.scalars(select(JobSource).order_by(JobSource.external_job_id)))
        assert job is not None and job.status == "ACTIVE"
        assert len(sources) == 2
        assert max(int(source.checkpoint.get("miss_count") or 0) for source in sources) >= 2
        assert min(int(source.checkpoint.get("miss_count") or 0) for source in sources) == 0

    engine.dispose()
