import json
import logging

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.jobs.connectors import GreenhouseJobBoardConnector
from app.jobs.pipeline import JobIngestionPipeline
from app.jobs.registry import run_due_sources, sync_configured_sources


logger = logging.getLogger("applyai.job_ingestion")


def ingest_greenhouse_boards(settings: Settings | None = None) -> dict[str, dict[str, int]]:
    """Compatibility entry point retained for existing Greenhouse regression tests/tools."""
    settings = settings or get_settings()
    if not settings.greenhouse_board_tokens:
        raise RuntimeError("GREENHOUSE_BOARD_TOKENS must contain at least one configured board token")

    results: dict[str, dict[str, int]] = {}
    with SessionLocal() as session:
        pipeline = JobIngestionPipeline(session)
        for board_token in settings.greenhouse_board_tokens:
            connector = GreenhouseJobBoardConnector(board_token)
            try:
                health = connector.health()
                if not health.healthy:
                    raise RuntimeError(f"Greenhouse board {board_token} is unavailable")
                results[board_token] = pipeline.run(connector)
            finally:
                connector.close()
    return results


def ensure_configured_sources(settings: Settings | None = None) -> int:
    settings = settings or get_settings()
    with SessionLocal() as session:
        return len(sync_configured_sources(session, settings))


def main() -> None:
    settings = get_settings()
    configured = ensure_configured_sources(settings)
    results = run_due_sources(settings)
    logger.info(
        "job_source_scheduler_completed",
        extra={"configured_sources": configured, "claimed_sources": len(results)},
    )
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
