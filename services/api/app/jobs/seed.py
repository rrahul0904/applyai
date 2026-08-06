from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app import job_source_models  # noqa: F401
from app.core.database import SessionLocal
from app.jobs.connectors import DevelopmentSeedConnector
from app.jobs.dataset import build_seed_records
from app.jobs.pipeline import JobIngestionPipeline, normalize_text


class CompanyDevelopmentSeedConnector(DevelopmentSeedConnector):
    """A deterministic non-production source scoped to one fictional employer."""

    def __init__(self, company_name: str, records: list[dict]) -> None:
        super().__init__(records)
        self.company_name = company_name

    def source_company_identity(self) -> str:
        return normalize_text(self.company_name)


def seed_development_jobs(
    session: Session,
    records: Iterable[dict] | None = None,
) -> dict[str, int]:
    """Seed fictional jobs through the real pipeline without merging employers."""

    records_by_company: defaultdict[str, list[dict]] = defaultdict(list)
    for record in records or build_seed_records():
        records_by_company[str(record["company_name"])].append(record)

    totals = {
        "fetched": 0,
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "failed": 0,
        "stale": 0,
        "closed": 0,
    }
    for company_name in sorted(records_by_company):
        result = JobIngestionPipeline(session).run(
            CompanyDevelopmentSeedConnector(
                company_name,
                records_by_company[company_name],
            )
        )
        for key in totals:
            totals[key] += result[key]
    return totals


def main() -> None:
    with SessionLocal() as session:
        result = seed_development_jobs(session)
    print(result)


if __name__ == "__main__":
    main()
