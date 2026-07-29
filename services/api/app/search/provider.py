from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import Select, and_, func, or_, select

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
    cursor_at: datetime | None = None
    cursor_id: uuid.UUID | None = None


class SearchProvider(ABC):
    @abstractmethod
    def jobs(self, query: JobSearchQuery) -> Select:
        raise NotImplementedError


class PostgresSearchProvider(SearchProvider):
    def jobs(self, query: JobSearchQuery) -> Select:
        statement = (
            select(Job)
            .join(Company, Company.id == Job.company_id)
            .outerjoin(JobLocation, JobLocation.job_id == Job.id)
            .outerjoin(JobCompensation, JobCompensation.job_id == Job.id)
            .where(Job.status == "ACTIVE")
        )
        if query.keyword:
            statement = statement.where(
                Job.search_vector.op("@@")(
                    func.websearch_to_tsquery("english", query.keyword.strip())
                )
            )
        if query.location:
            statement = statement.where(JobLocation.location_text.ilike(f"%{query.location}%"))
        if query.work_mode:
            statement = statement.where(JobLocation.work_mode == query.work_mode.upper())
        if query.employment_type:
            statement = statement.where(Job.employment_type == query.employment_type.upper())
        if query.seniority:
            statement = statement.where(Job.seniority == query.seniority.upper())
        if query.company:
            statement = statement.where(Company.canonical_name.ilike(f"%{query.company}%"))
        if query.minimum_salary is not None:
            statement = statement.where(JobCompensation.maximum >= query.minimum_salary)
        if query.posted_within_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=query.posted_within_days)
            statement = statement.where(Job.posted_at >= cutoff)
        if query.target_role:
            statement = statement.where(Job.title.ilike(f"%{query.target_role}%"))
        sort_at = func.coalesce(Job.posted_at, Job.first_seen_at)
        if query.cursor_at and query.cursor_id:
            statement = statement.where(
                or_(
                    sort_at < query.cursor_at,
                    and_(sort_at == query.cursor_at, Job.id < query.cursor_id),
                )
            )
        return statement.order_by(sort_at.desc(), Job.id.desc())
