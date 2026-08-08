from __future__ import annotations

import uuid
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.global_job_supply_models import JobDedupCandidate
from app.jobs.contracts import normalize_title
from app.jobs.pipeline import normalize_text
from app.models import Job, JobLocation


def _ordered_pair(left: uuid.UUID, right: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    return (left, right) if str(left) < str(right) else (right, left)


def build_dedup_candidates(
    session: Session,
    *,
    limit_jobs: int = 5_000,
    minimum_similarity: float = 0.85,
    automatic_merge_threshold: float = 0.94,
) -> dict[str, int]:
    """Persist borderline same-employer job pairs for operator review.

    Pairs above the automatic threshold are handled by the canonical ingestion pipeline;
    this review queue deliberately captures only the ambiguous middle band.
    """

    rows = list(
        session.execute(
            select(Job, JobLocation.location_text)
            .join(JobLocation, JobLocation.job_id == Job.id)
            .where(Job.status.in_(["ACTIVE", "UNKNOWN", "STALE"]))
            .order_by(Job.last_seen_at.desc(), Job.id)
            .limit(max(1, min(int(limit_jobs), 100_000)))
        ).all()
    )
    buckets: dict[tuple[uuid.UUID, str, str], list[Job]] = {}
    for job, location in rows:
        key = (job.company_id, normalize_title(job.title), str(location or ""))
        buckets.setdefault(key, []).append(job)

    counts = {"compared": 0, "created": 0, "existing": 0}
    for jobs in buckets.values():
        if len(jobs) < 2:
            continue
        for left_index in range(len(jobs) - 1):
            left = jobs[left_index]
            left_text = normalize_text(left.description)[:20_000]
            for right in jobs[left_index + 1 :]:
                counts["compared"] += 1
                ratio = SequenceMatcher(
                    None,
                    left_text,
                    normalize_text(right.description)[:20_000],
                    autojunk=False,
                ).ratio()
                if ratio < minimum_similarity or ratio >= automatic_merge_threshold:
                    continue
                left_id, right_id = _ordered_pair(left.id, right.id)
                existing = session.scalar(
                    select(JobDedupCandidate).where(
                        JobDedupCandidate.left_job_id == left_id,
                        JobDedupCandidate.right_job_id == right_id,
                    )
                )
                if existing is not None:
                    counts["existing"] += 1
                    continue
                session.add(
                    JobDedupCandidate(
                        left_job_id=left_id,
                        right_job_id=right_id,
                        reason="SAME_COMPANY_TITLE_LOCATION_DESCRIPTION_SIMILARITY",
                        confidence_bps=int(round(ratio * 10_000)),
                        evidence={
                            "description_similarity": round(ratio, 6),
                            "automatic_merge_threshold": automatic_merge_threshold,
                            "minimum_review_threshold": minimum_similarity,
                        },
                        status="PENDING",
                    )
                )
                counts["created"] += 1
    session.commit()
    return counts
