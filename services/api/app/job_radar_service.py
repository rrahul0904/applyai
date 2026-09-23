from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.job_radar_models import JobScan, JobScanMatch, JobSearchProfile
from app.models import Company, Job, JobCompensation, JobLocation, JobSkill, JobSource, JobSourceLink

SCORING_VERSION = "job-radar-deterministic-v1"
PROVIDER_NAME = "canonical-store-v1"
SCORE_WEIGHTS = {"title": 0.40, "skills": 0.30, "experience": 0.15, "location": 0.10, "salary": 0.05}
_TRACKING_KEYS = {"source", "ref", "referrer", "tracking", "trk"}


@dataclass(frozen=True)
class SalaryRange:
    minimum: int | None
    maximum: int | None
    currency: str
    interval: str
    raw: str


@dataclass(frozen=True)
class ProviderSearchRequest:
    query: str
    location: str | None = None
    work_mode: str | None = None
    limit: int = 25


@dataclass(frozen=True)
class ProviderJobCandidate:
    provider: str
    provider_job_id: str | None
    application_url: str
    title: str
    company: str
    description: str
    canonical_job_id: uuid.UUID | None = None
    location: str | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    skills: tuple[str, ...] = ()
    salary_text: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_interval: str | None = None
    posted_at: datetime | None = None


@dataclass(frozen=True)
class NormalizedJobCandidate:
    provider: str
    provider_job_id: str | None
    application_url: str
    title: str
    company: str
    description: str
    canonical_job_id: uuid.UUID | None
    location: str | None
    work_mode: str | None
    employment_type: str | None
    seniority: str | None
    skills: tuple[str, ...]
    salary: SalaryRange | None
    posted_at: datetime | None


class JobRadarProvider(Protocol):
    name: str

    def search(self, request: ProviderSearchRequest) -> list[ProviderJobCandidate]: ...


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split()).strip()
    return value or None


def _tokens(value: str | None) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.]+", (value or "").lower()))


def canonicalize_application_url(value: str) -> str | None:
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", urlencode(query), "")
    )


def _salary_numbers(text: str) -> list[int]:
    values: list[int] = []
    for match in re.finditer(r"(?<!\w)(\d+(?:\.\d+)?)\s*(K|M|LPA|LAKH|L)?\b", text.upper().replace(",", "")):
        number = float(match.group(1))
        suffix = match.group(2)
        multiplier = {"K": 1_000, "M": 1_000_000, "L": 100_000, "LPA": 100_000, "LAKH": 100_000}.get(suffix, 1)
        values.append(int(round(number * multiplier)))
    return values[:2]


def parse_salary_text(value: str | None, *, default_currency: str = "USD") -> SalaryRange | None:
    raw = _clean(value)
    if raw is None:
        return None
    values = _salary_numbers(raw)
    if not values:
        return None
    lowered = raw.lower()
    if "up to" in lowered or "upto" in lowered:
        minimum, maximum = None, values[-1]
    elif lowered.startswith("from ") or " from " in lowered:
        minimum, maximum = values[0], None
    elif len(values) == 1:
        minimum = maximum = values[0]
    else:
        minimum, maximum = values
        if minimum > maximum:
            return None
    upper = raw.upper()
    currency = (
        "INR" if any(token in upper for token in ("INR", "₹", "LPA", "LAKH"))
        else "GBP" if "GBP" in upper or "£" in raw
        else "EUR" if "EUR" in upper or "€" in raw
        else "USD" if "USD" in upper or "$" in raw
        else default_currency.upper()
    )
    interval = (
        "HOUR" if re.search(r"(?:/|PER\s*)?(?:HR|HOUR)\b|HOURLY", upper)
        else "MONTH" if re.search(r"(?:/|PER\s*)?(?:MO|MONTH)\b|MONTHLY", upper)
        else "YEAR"
    )
    return SalaryRange(minimum, maximum, currency, interval, raw)


def normalize_candidate(candidate: ProviderJobCandidate) -> NormalizedJobCandidate | None:
    url = canonicalize_application_url(candidate.application_url)
    title, company = _clean(candidate.title), _clean(candidate.company)
    if url is None or title is None or company is None:
        return None
    salary = None
    if candidate.salary_min is not None or candidate.salary_max is not None:
        salary = SalaryRange(
            candidate.salary_min,
            candidate.salary_max,
            (candidate.salary_currency or "USD").upper(),
            (candidate.salary_interval or "YEAR").upper(),
            candidate.salary_text or "provider-structured",
        )
    elif candidate.salary_text:
        salary = parse_salary_text(candidate.salary_text, default_currency=candidate.salary_currency or "USD")
    skills = tuple(dict.fromkeys(value.lower() for raw in candidate.skills if (value := _clean(raw))))
    work_mode = _clean(candidate.work_mode)
    employment_type = _clean(candidate.employment_type)
    seniority = _clean(candidate.seniority)
    return NormalizedJobCandidate(
        provider=candidate.provider.strip().lower(),
        provider_job_id=_clean(candidate.provider_job_id),
        application_url=url,
        title=title,
        company=company,
        description=_clean(candidate.description) or "",
        canonical_job_id=candidate.canonical_job_id,
        location=_clean(candidate.location),
        work_mode=work_mode.upper() if work_mode else None,
        employment_type=employment_type.upper() if employment_type else None,
        seniority=seniority.upper() if seniority else None,
        skills=skills,
        salary=salary,
        posted_at=candidate.posted_at,
    )


def deduplicate_candidates(candidates: list[NormalizedJobCandidate]) -> list[NormalizedJobCandidate]:
    provider_ids: set[str] = set()
    urls: set[str] = set()
    fallbacks: set[str] = set()
    result: list[NormalizedJobCandidate] = []
    for item in candidates:
        provider_key = f"{item.provider}:{item.provider_job_id}" if item.provider_job_id else None
        posted = item.posted_at.date().isoformat() if item.posted_at else "unknown"
        fallback = "|".join((item.company.lower(), item.title.lower(), (item.location or "").lower(), posted))
        if (provider_key and provider_key in provider_ids) or item.application_url in urls or fallback in fallbacks:
            continue
        if provider_key:
            provider_ids.add(provider_key)
        urls.add(item.application_url)
        fallbacks.add(fallback)
        result.append(item)
    return result


def _title_score(profile: JobSearchProfile, job: NormalizedJobCandidate) -> int | None:
    job_tokens = _tokens(job.title)
    scores = [len(_tokens(title) & job_tokens) / len(_tokens(title)) for title in profile.target_titles if _tokens(title)]
    return round(max(scores) * 100) if scores else None


def _skills_score(profile: JobSearchProfile, job: NormalizedJobCandidate) -> int | None:
    wanted = {value.strip().lower() for value in profile.skills if value.strip()}
    if not wanted:
        return None
    evidence = set(job.skills) | _tokens(job.description)
    matched = sum(1 for skill in wanted if skill in evidence or _tokens(skill) <= evidence)
    return round(100 * matched / len(wanted))


def _experience_score(profile: JobSearchProfile, job: NormalizedJobCandidate) -> int | None:
    if profile.years_experience is None or not job.seniority:
        return None
    thresholds = {"INTERN": 0, "ENTRY": 0, "JUNIOR": 1, "MID": 3, "SENIOR": 5, "LEAD": 7, "STAFF": 8, "PRINCIPAL": 10, "DIRECTOR": 10}
    required = next((years for label, years in thresholds.items() if label in job.seniority), None)
    if required is None or required == 0:
        return None if required is None else 100
    return min(100, round(100 * profile.years_experience / required))


def _location_score(profile: JobSearchProfile, job: NormalizedJobCandidate) -> int | None:
    policy = (profile.remote_policy or "ANY").upper()
    if policy == "REMOTE":
        return None if job.work_mode is None else (100 if job.work_mode == "REMOTE" else 0)
    locations = [value.strip().lower() for value in profile.preferred_locations if value.strip()]
    if not locations or job.location is None:
        return None
    current = job.location.lower()
    return 100 if any(value in current or current in value for value in locations) else 0


def _salary_score(profile: JobSearchProfile, job: NormalizedJobCandidate) -> int | None:
    if profile.salary_min is None or job.salary is None:
        return None
    salary = job.salary
    if salary.interval != "YEAR" or salary.currency != profile.salary_currency.upper():
        return None
    if salary.maximum is not None and salary.maximum < profile.salary_min:
        return 0
    if salary.minimum is not None and salary.minimum >= profile.salary_min:
        return 100
    return 60 if salary.maximum is None or salary.maximum >= profile.salary_min else 0


def deterministic_score(profile: JobSearchProfile, job: NormalizedJobCandidate) -> tuple[int, dict]:
    signals = {
        "title": _title_score(profile, job),
        "skills": _skills_score(profile, job),
        "experience": _experience_score(profile, job),
        "location": _location_score(profile, job),
        "salary": _salary_score(profile, job),
    }
    contributions = {key: round((value or 0) * SCORE_WEIGHTS[key], 2) for key, value in signals.items()}
    score = round(sum(contributions.values()))
    return score, {
        "version": SCORING_VERSION,
        "score": score,
        "signals": signals,
        "weights": SCORE_WEIGHTS,
        "contributions": contributions,
        "missing_signals": [key for key, value in signals.items() if value is None],
    }


def build_query_plan(profile: JobSearchProfile, *, max_queries: int, per_query_limit: int) -> list[dict]:
    titles = [value.strip() for value in profile.target_titles if value.strip()]
    if not titles:
        raise ValueError("SEARCH_PROFILE_REQUIRES_TARGET_TITLE")
    locations = [value.strip() for value in profile.preferred_locations if value.strip()]
    return [
        {
            "query": title,
            "location": locations[0] if locations else None,
            "work_mode": "REMOTE" if profile.remote_policy.upper() == "REMOTE" else None,
            "limit": per_query_limit,
        }
        for title in titles[:max_queries]
    ]


class CanonicalStoreJobProvider:
    name = PROVIDER_NAME

    def __init__(self, session: Session):
        self.session = session

    def search(self, request: ProviderSearchRequest) -> list[ProviderJobCandidate]:
        statement = select(Job).where(
            Job.status == "ACTIVE",
            or_(Job.title.ilike(f"%{request.query}%"), Job.description.ilike(f"%{request.query}%")),
        )
        if request.location:
            statement = statement.where(
                select(1).where(
                    JobLocation.job_id == Job.id,
                    JobLocation.location_text.ilike(f"%{request.location}%"),
                ).exists()
            )
        if request.work_mode:
            statement = statement.where(
                select(1).where(
                    JobLocation.job_id == Job.id,
                    JobLocation.work_mode == request.work_mode.upper(),
                ).exists()
            )
        jobs = list(self.session.scalars(
            statement.order_by(Job.posted_at.desc().nullslast(), Job.first_seen_at.desc(), Job.id.desc()).limit(request.limit)
        ))
        if not jobs:
            return []
        ids = [job.id for job in jobs]
        companies = {item.id: item for item in self.session.scalars(select(Company).where(Company.id.in_({job.company_id for job in jobs})))}
        locations: dict[uuid.UUID, JobLocation] = {}
        for item in self.session.scalars(select(JobLocation).where(JobLocation.job_id.in_(ids)).order_by(JobLocation.id)):
            locations.setdefault(item.job_id, item)
        skills: dict[uuid.UUID, list[str]] = {}
        for item in self.session.scalars(select(JobSkill).where(JobSkill.job_id.in_(ids)).order_by(JobSkill.id)):
            skills.setdefault(item.job_id, []).append(item.normalized_name or item.name)
        compensation: dict[uuid.UUID, JobCompensation] = {}
        for item in self.session.scalars(select(JobCompensation).where(JobCompensation.job_id.in_(ids)).order_by(JobCompensation.id)):
            compensation.setdefault(item.job_id, item)
        sources: dict[uuid.UUID, JobSource] = {}
        rows = self.session.execute(
            select(JobSourceLink, JobSource)
            .join(JobSource, JobSource.id == JobSourceLink.job_source_id)
            .where(JobSourceLink.job_id.in_(ids))
            .order_by(JobSourceLink.is_primary.desc(), JobSourceLink.id)
        )
        for link, source in rows:
            sources.setdefault(link.job_id, source)

        result: list[ProviderJobCandidate] = []
        for job in jobs:
            company, source = companies.get(job.company_id), sources.get(job.id)
            if company is None or source is None:
                continue
            location, pay = locations.get(job.id), compensation.get(job.id)
            result.append(ProviderJobCandidate(
                provider=self.name,
                provider_job_id=source.external_job_id,
                application_url=source.source_url,
                title=job.title,
                company=company.canonical_name,
                description=job.description,
                canonical_job_id=job.id,
                location=location.location_text if location else None,
                work_mode=location.work_mode if location else None,
                employment_type=job.employment_type,
                seniority=job.seniority,
                skills=tuple(skills.get(job.id, [])),
                salary_min=pay.minimum if pay else None,
                salary_max=pay.maximum if pay else None,
                salary_currency=pay.currency if pay else None,
                salary_interval=pay.interval if pay else None,
                posted_at=job.posted_at,
            ))
        return result


def run_job_scan(session: Session, *, scan_id: uuid.UUID, provider: JobRadarProvider | None = None) -> bool:
    scan = session.get(JobScan, scan_id)
    if scan is None or scan.status == "COMPLETED":
        return True
    profile = session.get(JobSearchProfile, scan.profile_id)
    if profile is None or profile.user_id != scan.user_id:
        if scan is not None:
            scan.status, scan.error_code = "FAILED", "PROFILE_NOT_FOUND"
            scan.error_detail = "The persisted search profile is no longer available."
            scan.completed_at = datetime.now(timezone.utc)
            session.commit()
        return True

    scan.status = "RUNNING"
    scan.started_at = datetime.now(timezone.utc)
    scan.error_code = scan.error_detail = None
    session.commit()
    try:
        active = provider or CanonicalStoreJobProvider(session)
        raw: list[ProviderJobCandidate] = []
        for item in scan.query_plan_json:
            raw.extend(active.search(ProviderSearchRequest(
                query=str(item["query"]),
                location=item.get("location"),
                work_mode=item.get("work_mode"),
                limit=int(item.get("limit", 25)),
            )))
        normalized = [
            item for candidate in raw
            if (item := normalize_candidate(candidate)) is not None and item.canonical_job_id is not None
        ]
        unique = deduplicate_candidates(normalized)
        scored = [(deterministic_score(profile, item), item) for item in unique]
        scored.sort(key=lambda row: (-row[0][0], -(row[1].posted_at.timestamp() if row[1].posted_at else 0), str(row[1].canonical_job_id)))
        selected = scored[: max(1, min(50, int(scan.top_k)))]

        session.execute(delete(JobScanMatch).where(JobScanMatch.scan_id == scan.id))
        for rank, ((score, breakdown), item) in enumerate(selected, start=1):
            session.add(JobScanMatch(
                scan_id=scan.id,
                job_id=item.canonical_job_id,
                provider=item.provider,
                provider_job_id=item.provider_job_id,
                application_url=item.application_url,
                deterministic_score=score,
                score_breakdown=breakdown,
                source_evidence={
                    "provider": item.provider,
                    "provider_job_id": item.provider_job_id,
                    "application_url": item.application_url,
                },
                rank=rank,
            ))
        scan.jobs_seen = len(raw)
        scan.jobs_after_filter = len(unique)
        scan.jobs_ranked = len(selected)
        scan.status = "COMPLETED"
        scan.completed_at = datetime.now(timezone.utc)
        session.commit()
        return True
    except Exception as exc:
        session.rollback()
        failed = session.get(JobScan, scan_id)
        if failed is not None:
            failed.status = "FAILED"
            failed.error_code = type(exc).__name__[:80]
            failed.error_detail = str(exc)[:1000]
            failed.completed_at = datetime.now(timezone.utc)
            session.commit()
        return False
