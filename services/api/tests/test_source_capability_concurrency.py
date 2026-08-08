from __future__ import annotations

import threading

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.global_job_supply_models import JobSourceCapability
from app.jobs.source_capabilities import (
    PROVIDER_CAPABILITY_SEEDS,
    SourceAccessMode,
    seed_source_capabilities,
)


def _seed_in_two_sessions(database_url: str) -> None:
    engine = create_engine(database_url, pool_size=4, max_overflow=0)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []
    errors_lock = threading.Lock()

    def worker() -> None:
        try:
            with session_factory() as session:
                barrier.wait(timeout=10)
                seed_source_capabilities(session)
                session.commit()
        except BaseException as exc:  # pragma: no cover - surfaced below with original error
            with errors_lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    try:
        assert all(not thread.is_alive() for thread in threads), "capability seeding deadlocked"
        assert errors == []
    finally:
        engine.dispose()


def test_provider_capability_seed_is_concurrency_safe_and_preserves_overrides(database_url: str):
    _seed_in_two_sessions(database_url)

    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with session_factory() as session:
            provider_keys = list(
                session.scalars(
                    select(JobSourceCapability.provider_key).order_by(
                        JobSourceCapability.provider_key
                    )
                )
            )
            assert len(provider_keys) == len(PROVIDER_CAPABILITY_SEEDS)
            assert len(provider_keys) == len(set(provider_keys))

            greenhouse = session.scalar(
                select(JobSourceCapability).where(
                    JobSourceCapability.provider_key == "greenhouse"
                )
            )
            assert greenhouse is not None
            greenhouse.access_mode = SourceAccessMode.BLOCKED_BY_POLICY.value
            metadata = dict(greenhouse.metadata_json or {})
            metadata.update(
                {
                    "operator_override": True,
                    "operator_override_at": "test",
                    "reason": "operator-reviewed test policy",
                }
            )
            greenhouse.metadata_json = metadata
            session.commit()
    finally:
        engine.dispose()

    _seed_in_two_sessions(database_url)

    engine = create_engine(database_url)
    try:
        with sessionmaker(bind=engine, expire_on_commit=False)() as session:
            greenhouse = session.scalar(
                select(JobSourceCapability).where(
                    JobSourceCapability.provider_key == "greenhouse"
                )
            )
            assert greenhouse is not None
            assert greenhouse.access_mode == SourceAccessMode.BLOCKED_BY_POLICY.value
            assert greenhouse.metadata_json["operator_override"] is True
            assert greenhouse.metadata_json["reason"] == "operator-reviewed test policy"

            provider_keys = list(session.scalars(select(JobSourceCapability.provider_key)))
            assert len(provider_keys) == len(PROVIDER_CAPABILITY_SEEDS)
            assert len(provider_keys) == len(set(provider_keys))
    finally:
        engine.dispose()
