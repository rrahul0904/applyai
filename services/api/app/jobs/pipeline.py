import hashlib
import json
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.jobs.connectors import JobSourceConnector, NormalizedJob
from app.models import (
    Company,
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


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())


class JobIngestionPipeline:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(self, connector: JobSourceConnector) -> dict[str, int]:
        counts = {"fetched": 0, "created": 0, "updated": 0, "unchanged": 0}
        for payload in connector.fetch(None):
            counts["fetched"] += 1
            normalized = connector.normalize(payload)
            result = self.ingest_one(connector.key, normalized)
            counts[result] += 1
        self.session.commit()
        return counts

    def ingest_one(self, connector_key: str, item: NormalizedJob) -> str:
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
            )
            self.session.add(source)
            self.session.flush()

        serialized = json.dumps(item.raw_payload, sort_keys=True, default=str)
        content_hash = hashlib.sha256(serialized.encode()).hexdigest()
        existing_raw = self.session.scalar(
            select(RawJobPosting).where(
                RawJobPosting.job_source_id == source.id,
                RawJobPosting.content_hash == content_hash,
            )
        )
        if existing_raw is not None:
            return "unchanged"

        raw = RawJobPosting(
            job_source_id=source.id,
            payload=item.raw_payload,
            content_hash=content_hash,
            normalization_status="NORMALIZED",
        )
        self.session.add(raw)

        company_name = normalize_text(item.company_name)
        company = self.session.scalar(
            select(Company).where(Company.normalized_name == company_name)
        )
        if company is None:
            company = Company(
                canonical_name=item.company_name,
                normalized_name=company_name,
            )
            self.session.add(company)
            self.session.flush()

        link = self.session.scalar(
            select(JobSourceLink).where(JobSourceLink.job_source_id == source.id)
        )
        created = link is None
        if link is not None:
            job = self.session.get(Job, link.job_id)
            if job is None:
                raise RuntimeError("Job source link points to a missing canonical job")
        else:
            primary_location = item.locations[0] if item.locations else "Location not specified"
            job = self.session.scalar(
                select(Job)
                .join(JobLocation, JobLocation.job_id == Job.id)
                .where(
                    Job.company_id == company.id,
                    Job.normalized_title == normalize_text(item.title),
                    JobLocation.location_text == primary_location,
                    Job.status.in_(["ACTIVE", "POSSIBLY_CLOSED"]),
                )
            )
            if job is None:
                search_document = " ".join(
                    [
                        item.title,
                        item.company_name,
                        item.description,
                        *item.skills,
                        *item.requirements,
                    ]
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
                    dedup_confidence=1,
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
                self.session.add(
                    JobVersion(
                        job_id=job.id,
                        version_number=1,
                        snapshot=item.raw_payload,
                    )
                )
            self.session.add(
                JobSourceLink(job_id=job.id, job_source_id=source.id, is_primary=True)
            )

        source.source_url = item.application_url
        if item.posted_at:
            job.posted_at = item.posted_at
        self.session.flush()
        self.session.execute(
            text(
                "UPDATE jobs SET search_vector = "
                "to_tsvector('english', coalesce(search_document, '')) WHERE id = :job_id"
            ),
            {"job_id": job.id},
        )
        return "created" if created else "updated"
