from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, select

from app.agent_models import AgentRun
from app.core.database import SessionLocal
from app.models import Company, Job, User


EVIDENCE_TYPE = "SYNTHETIC_SCALE_EVIDENCE"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fixture() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as session:
        user = User(
            clerk_user_id=f"agent-scale-{uuid.uuid4()}",
            email=f"agent-scale-{uuid.uuid4()}@example.invalid",
            onboarding_completed=True,
        )
        company = Company(
            canonical_name=f"Agent Scale {uuid.uuid4()}",
            normalized_name=f"agent scale {uuid.uuid4()}",
        )
        session.add_all([user, company])
        session.flush()
        job = Job(
            company_id=company.id,
            title="Synthetic Agent Scale Job",
            normalized_title="synthetic agent scale job",
            description="Synthetic benchmark fixture.",
            search_document="synthetic agent scale job",
            status="ACTIVE",
        )
        session.add(job)
        session.commit()
        return user.id, job.id


def _insert_runs(candidate_id: uuid.UUID, job_id: uuid.UUID, count: int) -> float:
    started = time.perf_counter()
    batch_size = 2_000
    for start in range(0, count, batch_size):
        size = min(batch_size, count - start)
        rows = []
        for offset in range(size):
            index = start + offset
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "candidate_id": candidate_id,
                    "job_id": job_id,
                    "agent_name": "job_scout",
                    "agent_version": "v1",
                    "trigger_type": "SYNTHETIC_SCALE",
                    "workflow_type": "SYNTHETIC_SCALE",
                    "workflow_id": uuid.uuid4(),
                    "status": "QUEUED",
                    "execution_class": "READ",
                    "queue_class": "agent-fast",
                    "priority": index % 100,
                    "idempotency_key": f"synthetic-agent-scale:{count}:{index}:{uuid.uuid4()}",
                    "input_json": {"synthetic": True, "index": index},
                    "max_steps": 6,
                    "timeout_seconds": 90,
                    "max_cost_usd": 0,
                    "attempt_count": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0,
                }
            )
        with SessionLocal() as session:
            session.execute(insert(AgentRun), rows)
            session.commit()
    return time.perf_counter() - started


def _claim_all(count: int) -> dict:
    claimed: set[uuid.UUID] = set()
    lease_owner = "benchmark-worker-a"
    lease_expires = utcnow() + timedelta(minutes=10)
    started = time.perf_counter()
    batch_size = 500
    while len(claimed) < count:
        with SessionLocal() as session:
            rows = list(
                session.scalars(
                    select(AgentRun)
                    .where(AgentRun.status == "QUEUED")
                    .order_by(AgentRun.priority.desc(), AgentRun.created_at, AgentRun.id)
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            )
            if not rows:
                break
            now = utcnow()
            for row in rows:
                row.status = "CLAIMED"
                row.lease_owner = lease_owner
                row.lease_acquired_at = now
                row.heartbeat_at = now
                row.lease_expires_at = lease_expires
                row.attempt_count += 1
                if row.id in claimed:
                    raise RuntimeError("DUPLICATE_AGENT_LEASE")
                claimed.add(row.id)
            session.commit()
    seconds = time.perf_counter() - started
    with SessionLocal() as session:
        second_worker_claimable = int(
            session.scalar(
                select(func.count()).select_from(AgentRun).where(
                    AgentRun.status == "QUEUED",
                )
            )
            or 0
        )
        claimed_count = int(
            session.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.status == "CLAIMED")) or 0
        )
    return {
        "claimed": claimed_count,
        "unique_claimed": len(claimed),
        "seconds": round(seconds, 4),
        "claims_per_second": round(claimed_count / seconds, 2) if seconds else None,
        "duplicate_claims": claimed_count - len(claimed),
        "second_worker_claimable": second_worker_claimable,
    }


def benchmark(count: int) -> dict:
    candidate_id, job_id = _fixture()
    insert_seconds = _insert_runs(candidate_id, job_id, count)
    claim = _claim_all(count)
    result = {
        "evidence_type": EVIDENCE_TYPE,
        "queued_runs": count,
        "insert_seconds": round(insert_seconds, 4),
        **claim,
    }
    if claim["claimed"] != count or claim["duplicate_claims"] != 0 or claim["second_worker_claimable"] != 0:
        raise RuntimeError(f"Agent runtime scale invariant failed: {result}")
    with SessionLocal() as session:
        session.execute(delete(AgentRun).where(AgentRun.candidate_id == candidate_id))
        session.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="1000,10000,50000")
    args = parser.parse_args()
    sizes = [int(item.strip()) for item in args.sizes.split(",") if item.strip()]
    results = [benchmark(size) for size in sizes]
    print(json.dumps({"evidence_type": EVIDENCE_TYPE, "results": results}, indent=2))


if __name__ == "__main__":
    main()
