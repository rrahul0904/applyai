from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import uuid

from sqlalchemy import Numeric, Select, and_, cast, func, or_, select

from app.models import Company, Job, JobCompensation, JobLocation


@dataclass(frozen=True)
class JobSearchQuery:
    keyword: str | None = None
    location: str | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    company: str | None = None
    minimum_salary: int | None = None
    posted_within_days: int | None = None
    target_role: str | None = None
    cursor_rank: Decimal | None = None
    cursor_at: datetime | None = None
    cursor_id: uuid.UUID | None = None


def relevance_expression(keyword: str):
    query = func.websearch_to_tsquery("english", keyword.strip())
    # Numeric rounding gives the cursor a stable serialized rank rather than relying
    # on binary float equality across requests.
    return cast(func.ts_rank_cd(Job.search_vector, query), Numeric(12, 8))


class SearchProvider(ABC):
    @abstractmethod
    def jobs(self, query: JobSearchQuery) -> Select:
        raise NotImplementedError


class PostgresSearchProvider(SearchProvider):
    def jobs(self, query: JobSearchQuery) -> Select:
        statement = (
            select(Job)
            .join(Company, Company.id == Job.company_id)
            .where(Job.status == "ACTIVE")
        )
        rank = None
        if query.keyword:
            ts_query = func.websearch_to_tsquery("english", query.keyword.strip())
            rank = relevance_expression(query.keyword)
            statement = statement.where(Job.search_vector.op("@@")(ts_query))
        if query.location:
            statement = statement.where(
                select(1)
                .where(
                    JobLocation.job_id == Job.id,
                    JobLocation.location_text.ilike(f"%{query.location}%"),
                )
                .exists()
            )
        if query.work_mode:
            statement = statement.where(
                select(1)
                .where(
                    JobLocation.job_id == Job.id,
                    JobLocation.work_mode == query.work_mode.upper(),
                )
                .exists()
            )
        if query.employment_type:
            statement = statement.where(Job.employment_type == query.employment_type.upper())
        if query.seniority:
            statement = statement.where(Job.seniority == query.seniority.upper())
        if query.company:
            statement = statement.where(Company.canonical_name.ilike(f"%{query.company}%"))
        if query.minimum_salary is not None:
            statement = statement.where(
                select(1)
                .where(
                    JobCompensation.job_id == Job.id,
                    JobCompensation.maximum >= query.minimum_salary,
                )
                .exists()
            )
        if query.posted_within_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=query.posted_within_days)
            statement = statement.where(Job.posted_at >= cutoff)
        if query.target_role:
            statement = statement.where(Job.title.ilike(f"%{query.target_role}%"))

        sort_at = func.coalesce(Job.posted_at, Job.first_seen_at)
        if query.cursor_at and query.cursor_id:
            if rank is not None and query.cursor_rank is not None:
                statement = statement.where(
                    or_(
                        rank < query.cursor_rank,
                        and_(rank == query.cursor_rank, sort_at < query.cursor_at),
                        and_(
                            rank == query.cursor_rank,
                            sort_at == query.cursor_at,
                            Job.id < query.cursor_id,
                        ),
                    )
                )
            else:
                statement = statement.where(
                    or_(
                        sort_at < query.cursor_at,
                        and_(sort_at == query.cursor_at, Job.id < query.cursor_id),
                    )
                )

        if rank is not None:
            return statement.order_by(rank.desc(), sort_at.desc(), Job.id.desc())
        return statement.order_by(sort_at.desc(), Job.id.desc())
