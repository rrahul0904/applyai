from app.core.database import SessionLocal
from app.jobs.connectors import DevelopmentSeedConnector
from app.jobs.dataset import build_seed_records
from app.jobs.pipeline import JobIngestionPipeline


def main() -> None:
    with SessionLocal() as session:
        result = JobIngestionPipeline(session).run(
            DevelopmentSeedConnector(build_seed_records())
        )
    print(result)


if __name__ == "__main__":
    main()
