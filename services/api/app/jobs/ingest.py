import json
import logging

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.jobs.connectors import GreenhouseJobBoardConnector
from app.jobs.pipeline import JobIngestionPipeline


logger = logging.getLogger("applyai.job_ingestion")


def ingest_greenhouse_boards(settings: Settings | None = None) -> dict[str, dict[str, int]]:
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


def main() -> None:
    results = ingest_greenhouse_boards()
    logger.info("greenhouse_ingestion_completed", extra={"results": results})
    print(json.dumps(results, sort_keys=True))


if __name__ == "__main__":
    main()
