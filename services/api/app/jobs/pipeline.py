import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.durability_models import JobIngestionRun
from app.jobs.connectors import JobSourceConnector, NormalizedJob
from app.models import (
    Company,
    CompanySource,
    Job,
    JobCompensation,
    JobLocation,
    JobRequirement,
    JobSkill,
    JobSource,
    JobSourceLink,
    JobStatusHistory,
    JobVersion,
    RawJobPosting,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


def material_payload(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "_applyai_fetched_at"}


def payload_hash(payload: dict) -> str:
    serialized = json.dumps(material_payload(payload), sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def description_fingerprint(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode()).hexdigest()


MAX_JOB_LOCATION_TEXT_LENGTH = 280


def bounded_job_location(value: str) -> str:
    """Keep a provider's primary location compatible with the canonical column."""
    normalized = " ".join(value.split())
    if len(normalized) <= MAX_JOB_LOCATION_TEXT_LENGTH:
        return normalized
    return f"{normalized[: MAX_JOB_LOCATION_TEXT_LENGTH - 1].rstrip()}…"


def bounded_job_locations(locations: list[str]) -> list[str]:
    bounded: list[str] = []
    for location in locations:
        value = bounded_job_location(location)
        if value and value not in bounded:
            bounded.append(value)
    return bounded


class JobIngestionPipeline:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    def run(self, connector: JobSourceConnector) -> dict[str, int]:
        source_company = connector.source_company_identity()
        run = JobIngestionRun(
            connector=connector.key,
            source_company=source_company,
            status="RUNNING",
        )
        self.session.add(run)
        self.session.commit()

        counts = {
            "fetched": 0,
            "created": 0,
            "updated": 0,
            "unchanged": 0,
            "failed": 0,
            "stale": 0,
            "closed": 0,
        }
        try:
            payloads = connector.fetch(None)
        except Exception:
            run.status = "FAILED"
            run.failed = 1
            run.completed_at = utcnow()
            self.session.commit()
            raise

        seen: set[str] = set()
        for payload in payloads:
            counts["fetched"] += 1
            try:
                with self.session.begin_nested():
                    normalized = connector.normalize(payload)
                    seen.add(normalized.external_job_id)
                    result = self.ingest_one(
                        connector.key,
                        normalized,
                        source_company=source_company,
                    )
                    counts[result] += 1
            except Exception:
                counts["failed"] += 1

        if counts["failed"] == 0 and connector.key == "greenhouse":
            freshness = self.apply_freshness(
                connector_key=connector.key,
                source_company=source_company,
                seen_external_ids=seen,
            )
            counts["stale"] += freshness["stale"]
            counts["closed"] += freshness["closed"]
            run.status = "COMPLETED"
        else:
            run.status = "PARTIAL" if counts["failed"] else "COMPLETED"

        run.fetched = counts["fetched"]
        run.created = counts["created"]
        run.updated = counts["updated"]
        run.unchanged = counts["unchanged"]
        run.failed = counts["failed"]
        run.stale = counts["stale"]
        run.closed = counts["closed"]
        run.completed_at = utcnow()
        self.session.commit()
        return counts

    def resolve_company(
        self,
        *,
        connector_key: str,
        source_company: str,
        item: NormalizedJob,
    ) -> Company:
        source_name = connector_key.upper()
        company_source = self.session.scalar(
            select(CompanySource).where(
                CompanySource.source_name == source_name,
                CompanySource.external_company_id == source_company,
            )
        )
        now = utcnow()
        if company_source is not None:
            company_source.last_seen_at = now
            company_source.source_url = item.raw_payload.get("_applyai_company_source_url")
            company = self.session.get(Company, company_source.company_id)
            if company is None:
                raise RuntimeError("Company source points to a missing company")
            return company

        normalized_name = normalize_text(item.company_name)
        company = self.session.scalar(
            select(Company).where(Company.normalized_name == normalized_name)
        )
        if company is None:
            company = Company(
                canonical_name=item.company_name,
                normalized_name=normalized_name,
            )
            self.session.add(company)
            self.session.flush()
        self.session.add(
            CompanySource(
                company_id=company.id,
                source_name=source_name,
                external_company_id=source_company,
                source_url=item.raw_payload.get("_applyai_company_source_url"),
                last_seen_at=now,
            )
        )
        self.session.flush()
        return company

    def source_checkpoint(
        self,
        *,
        item: NormalizedJob,
        existing: dict | None,
        dedup_reason: str | None = None,
        miss_count: int = 0,
    ) -> dict:
        checkpoint = dict(existing or {})
        checkpoint.update(
            {
                "board_token": item.raw_payload.get("_applyai_board_token"),
                "greenhouse_post_id": item.raw_payload.get("_applyai_greenhouse_post_id"),
                "internal_job_id": item.raw_payload.get("_applyai_internal_job_id"),
                "source_updated_at": item.raw_payload.get("_applyai_source_updated_at"),
                "fetched_at": item.raw_payload.get("_applyai_fetched_at"),
                "miss_count": miss_count,
            }
        )
        if dedup_reason:
            checkpoint["dedup_reason"] = dedup_reason
        return checkpoint

    def find_dedup_candidate(
        self,
        *,
        connector_key: str,
        company: Company,
        item: NormalizedJob,
    ) -> tuple[Job | None, str | None, Decimal | None]:
        if item.application_url:
            link = self.session.scalar(
                select(JobSourceLink)
                .join(JobSource, JobSource.id == JobSourceLink.job_source_id)
                .where(JobSource.source_url == item.application_url)
                .limit(1)
            )
            if link is not None:
                return self.session.get(Job, link.job_id), "APPLICATION_URL", Decimal("1.0000")

        internal_job_id = item.raw_payload.get("_applyai_internal_job_id")
        board_token = item.raw_payload.get("_applyai_board_token")
        if internal_job_id and board_token:
            source = self.session.scalar(
                select(JobSource).where(
                    JobSource.connector_key == connector_key,
                    JobSource.checkpoint["board_token"].astext == str(board_token),
                    JobSource.checkpoint["internal_job_id"].astext == str(internal_job_id),
                )
            )
            if source is not None:
                link = self.session.scalar(
                    select(JobSourceLink).where(JobSourceLink.job_source_id == source.id)
                )
                if link is not None:
                    return self.session.get(Job, link.job_id), "INTERNAL_JOB_ID", Decimal("1.0000")

        primary_location = item.locations[0] if item.locations else "Location not specified"
        candidates = list(
            self.session.scalars(
                select(Job)
                .join(JobLocation, JobLocation.job_id == Job.id)
                .where(
                    Job.company_id == company.id,
                    Job.normalized_title == normalize_text(item.title),
                    JobLocation.location_text == primary_location,
                    Job.status.in_(["ACTIVE", "UNKNOWN", "STALE"]),
                )
            ).unique()
        )
        target_fingerprint = description_fingerprint(item.description)
        for candidate in candidates:
            if description_fingerprint(candidate.description) == target_fingerprint:
                return candidate, "COMPANY_TITLE_LOCATION_DESCRIPTION", Decimal("0.8500")
        return None, None, None

    def create_job(self, *, company: Company, item: NormalizedJob) -> Job:
        primary_location = item.locations[0] if item.locations else "Location not specified"
        search_document = " ".join(
            [item.title, item.company_name, item.description, *item.skills, *item.requirements]
        )
        job = Job(
            company_id=company.id,
            title=item.title,
            normalized_title=normalize_text(item.title),
            description=item.description,
            search_document=search_document,
            employment_type=item.employment_type,
            seniority=item.seniority,
            status="ACTIVE",
            posted_at=item.posted_at,
            data_origin=str(item.raw_payload.get("data_origin", "DEVELOPMENT_SEED")),
        )
        self.session.add(job)
        self.session.flush()
        self.session.add(
            JobLocation(
                job_id=job.id,
                location_text=primary_location,
                work_mode=item.work_mode,
            )
        )
        if item.salary_min is not None or item.salary_max is not None:
            self.session.add(
                JobCompensation(
                    job_id=job.id,
                    minimum=item.salary_min,
                    maximum=item.salary_max,
                    provenance=item.salary_provenance or "UNKNOWN",
                )
            )
        self.session.add_all(
            [
                JobSkill(
                    job_id=job.id,
                    name=skill,
                    normalized_name=normalize_text(skill),
                    required=True,
                )
                for skill in item.skills
            ]
        )
        self.session.add_all(
            [
                JobRequirement(
                    job_id=job.id,
                    category="GENERAL",
                    text=requirement,
                    required=True,
                )
                for requirement in item.requirements
            ]
        )
        self.session.add(
            JobStatusHistory(
                job_id=job.id,
                from_status=None,
                to_status="ACTIVE",
                reason="INGESTED",
            )
        )
        self.session.add(JobVersion(job_id=job.id, version_number=1, snapshot=item.raw_payload))
        self.session.flush()
        self.refresh_search(job)
        return job

    def canonical_changed(self, job: Job, item: NormalizedJob) -> bool:
        primary_location = item.locations[0] if item.locations else "Location not specified"
        current_location = self.session.scalar(
            select(JobLocation).where(JobLocation.job_id == job.id).order_by(JobLocation.id).limit(1)
        )
        if job.title != item.title or job.description != item.description:
            return True
        if item.employment_type != "UNKNOWN" and job.employment_type != item.employment_type:
            return True
        if item.seniority != "UNKNOWN" and job.seniority != item.seniority:
            return True
        if current_location is None or current_location.location_text != primary_location:
            return True
        if current_location.work_mode != item.work_mode:
            return True
        if item.posted_at and job.posted_at != item.posted_at:
            return True
        if item.salary_min is not None or item.salary_max is not None:
            compensation = self.session.scalar(
                select(JobCompensation).where(JobCompensation.job_id == job.id).limit(1)
            )
            if compensation is None or compensation.minimum != item.salary_min or compensation.maximum != item.salary_max:
                return True
        if item.skills:
            skills = set(
                self.session.scalars(select(JobSkill.normalized_name).where(JobSkill.job_id == job.id))
            )
            if skills != {normalize_text(skill) for skill in item.skills}:
                return True
        if item.requirements:
            requirements = set(
                self.session.scalars(select(JobRequirement.text).where(JobRequirement.job_id == job.id))
            )
            if requirements != set(item.requirements):
                return True
        return False

    def apply_canonical_update(self, job: Job, item: NormalizedJob) -> None:
        job.title = item.title
        job.normalized_title = normalize_text(item.title)
        job.description = item.description
        if item.employment_type != "UNKNOWN":
            job.employment_type = item.employment_type
        if item.seniority != "UNKNOWN":
            job.seniority = item.seniority
        if item.posted_at:
            job.posted_at = item.posted_at

        primary_location = item.locations[0] if item.locations else "Location not specified"
        location = self.session.scalar(
            select(JobLocation).where(JobLocation.job_id == job.id).order_by(JobLocation.id).limit(1)
        )
        if location is None:
            self.session.add(JobLocation(job_id=job.id, location_text=primary_location, work_mode=item.work_mode))
        else:
            location.location_text = primary_location
            location.work_mode = item.work_mode

        if item.salary_min is not None or item.salary_max is not None:
            compensation = self.session.scalar(
                select(JobCompensation).where(JobCompensation.job_id == job.id).limit(1)
            )
            if compensation is None:
                self.session.add(
                    JobCompensation(
                        job_id=job.id,
                        minimum=item.salary_min,
                        maximum=item.salary_max,
                        provenance=item.salary_provenance or "UNKNOWN",
                    )
                )
            else:
                compensation.minimum = item.salary_min
                compensation.maximum = item.salary_max
                compensation.provenance = item.salary_provenance or compensation.provenance

        if item.skills:
            self.session.execute(delete(JobSkill).where(JobSkill.job_id == job.id))
            self.session.add_all(
                [
                    JobSkill(
                        job_id=job.id,
                        name=skill,
                        normalized_name=normalize_text(skill),
                        required=True,
                    )
                    for skill in item.skills
                ]
            )
        if item.requirements:
            self.session.execute(delete(JobRequirement).where(JobRequirement.job_id == job.id))
            self.session.add_all(
                [
                    JobRequirement(
                        job_id=job.id,
                        category="GENERAL",
                        text=requirement,
                        required=True,
                    )
                    for requirement in item.requirements
                ]
            )
        self.session.flush()
        self.refresh_search(job)

    def refresh_search(self, job: Job) -> None:
        company_name = self.session.scalar(select(Company.canonical_name).where(Company.id == job.company_id)) or ""
        skills = list(self.session.scalars(select(JobSkill.name).where(JobSkill.job_id == job.id)))
        requirements = list(
            self.session.scalars(select(JobRequirement.text).where(JobRequirement.job_id == job.id))
        )
        job.search_document = " ".join(
            [job.title, company_name, job.description, *skills, *requirements]
        )
        self.session.flush()
        self.session.execute(
            text(
                "UPDATE jobs SET search_document = :document, "
                "search_vector = to_tsvector('english', :document) WHERE id = :job_id"
            ),
            {"document": job.search_document, "job_id": job.id},
        )

    def add_version(self, job: Job, item: NormalizedJob) -> None:
        next_version = (
            self.session.scalar(
                select(func.coalesce(func.max(JobVersion.version_number), 0)).where(JobVersion.job_id == job.id)
            )
            or 0
        ) + 1
        self.session.add(JobVersion(job_id=job.id, version_number=next_version, snapshot=item.raw_payload))

    def ingest_one(
        self,
        connector_key: str,
        item: NormalizedJob,
        *,
        source_company: str,
    ) -> str:
        item = replace(item, locations=bounded_job_locations(item.locations))
        now = utcnow()
        company = self.resolve_company(
            connector_key=connector_key,
            source_company=source_company,
            item=item,
        )
        source = self.session.scalar(
            select(JobSource).where(
                JobSource.connector_key == connector_key,
                JobSource.external_job_id == item.external_job_id,
            )
        )
        if source is None:
            source = JobSource(
                connector_key=connector_key,
                external_job_id=item.external_job_id,
                source_url=item.application_url,
                checkpoint=self.source_checkpoint(item=item, existing=None),
            )
            self.session.add(source)
            self.session.flush()
        else:
            source.source_url = item.application_url
            source.last_seen_at = now
            source.checkpoint = self.source_checkpoint(item=item, existing=source.checkpoint)

        link = self.session.scalar(select(JobSourceLink).where(JobSourceLink.job_source_id == source.id))
        dedup_reason: str | None = None
        dedup_confidence: Decimal | None = None
        created_job = False
        if link is not None:
            job = self.session.get(Job, link.job_id)
            if job is None:
                raise RuntimeError("Job source link points to a missing canonical job")
            dedup_reason = "SOURCE_IDENTITY"
            dedup_confidence = Decimal("1.0000")
        else:
            job, dedup_reason, dedup_confidence = self.find_dedup_candidate(
                connector_key=connector_key,
                company=company,
                item=item,
            )
            if job is None:
                job = self.create_job(company=company, item=item)
                created_job = True
                dedup_reason = "NEW_CANONICAL_JOB"
            elif dedup_confidence is not None:
                job.dedup_confidence = dedup_confidence
            self.session.add(JobSourceLink(job_id=job.id, job_source_id=source.id, is_primary=created_job))

        source.checkpoint = self.source_checkpoint(
            item=item,
            existing=source.checkpoint,
            dedup_reason=dedup_reason,
            miss_count=0,
        )
        source.last_seen_at = now
        job.last_seen_at = now
        if job.status in {"UNKNOWN", "STALE", "CLOSED"}:
            previous = job.status
            job.status = "ACTIVE"
            job.closed_at = None
            self.session.add(
                JobStatusHistory(
                    job_id=job.id,
                    from_status=previous,
                    to_status="ACTIVE",
                    reason="SOURCE_SEEN_AGAIN",
                )
            )

        content_hash = payload_hash(item.raw_payload)
        existing_raw = self.session.scalar(
            select(RawJobPosting).where(
                RawJobPosting.job_source_id == source.id,
                RawJobPosting.content_hash == content_hash,
            )
        )
        if existing_raw is not None:
            return "created" if created_job else "unchanged"

        self.session.add(
            RawJobPosting(
                job_source_id=source.id,
                payload=item.raw_payload,
                content_hash=content_hash,
                normalization_status="NORMALIZED",
            )
        )
        changed = False if created_job else self.canonical_changed(job, item)
        if changed:
            self.apply_canonical_update(job, item)
            self.add_version(job, item)
        if created_job:
            return "created"
        return "updated" if changed else "unchanged"

    def canonical_status_from_sources(self, job_id, current_status: str) -> str:
        sources = list(
            self.session.scalars(
                select(JobSource)
                .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
                .where(JobSourceLink.job_id == job_id)
            )
        )
        if not sources:
            return current_status
        checkpoints = [dict(source.checkpoint or {}) for source in sources]
        if all(bool(checkpoint.get("confirmed_closed")) for checkpoint in checkpoints):
            return "CLOSED"
        misses = [int(checkpoint.get("miss_count") or 0) for checkpoint in checkpoints]
        if any(miss < self.settings.job_unknown_after_misses for miss in misses):
            return "ACTIVE"
        if all(miss >= self.settings.job_stale_after_misses for miss in misses):
            return "STALE"
        return "UNKNOWN"

    def apply_freshness(
        self,
        *,
        connector_key: str,
        source_company: str,
        seen_external_ids: set[str],
    ) -> dict[str, int]:
        counts = {"stale": 0, "closed": 0}
        sources = list(
            self.session.scalars(
                select(JobSource).where(
                    JobSource.connector_key == connector_key,
                    JobSource.checkpoint["board_token"].astext == source_company,
                )
            )
        )
        affected_job_ids = set()
        for source in sources:
            if source.external_job_id in seen_external_ids:
                continue
            checkpoint = dict(source.checkpoint or {})
            checkpoint["miss_count"] = int(checkpoint.get("miss_count") or 0) + 1
            source.checkpoint = checkpoint
            link = self.session.scalar(select(JobSourceLink).where(JobSourceLink.job_source_id == source.id))
            if link is not None:
                affected_job_ids.add(link.job_id)

        for job_id in affected_job_ids:
            job = self.session.get(Job, job_id)
            if job is None:
                continue
            target_status = self.canonical_status_from_sources(job.id, job.status)
            if target_status == job.status:
                continue
            previous = job.status
            job.status = target_status
            if target_status == "CLOSED":
                job.closed_at = utcnow()
                counts["closed"] += 1
            elif target_status == "STALE":
                counts["stale"] += 1
            else:
                job.closed_at = None
            self.session.add(
                JobStatusHistory(
                    job_id=job.id,
                    from_status=previous,
                    to_status=target_status,
                    reason="SOURCE_FRESHNESS_EVALUATED",
                )
            )
        return counts
