import uuid

import pytest

from app.jobs.adaptive_schedule import ShardConfig, belongs_to_shard, recommended_interval_seconds, source_shard


def test_source_sharding_is_stable_and_partitioned():
    source_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert source_shard(source_id, 8) == source_shard(source_id, 8)
    shard = source_shard(source_id, 8)
    assert belongs_to_shard(source_id, ShardConfig(count=8, index=shard))
    assert not belongs_to_shard(source_id, ShardConfig(count=8, index=(shard + 1) % 8))


def test_invalid_shard_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("JOB_SOURCE_SHARD_COUNT", "4")
    monkeypatch.setenv("JOB_SOURCE_SHARD_INDEX", "4")
    with pytest.raises(ValueError):
        ShardConfig.from_environment()


def test_high_priority_changing_source_refreshes_within_three_hours():
    interval = recommended_interval_seconds(
        base_seconds=21_600,
        minimum_seconds=900,
        maximum_seconds=604_800,
        priority=95,
        job_count=500,
        change_count=50,
        consecutive_failures=0,
    )
    assert 900 <= interval <= 10_800


def test_empty_source_backs_off_to_at_least_daily():
    interval = recommended_interval_seconds(
        base_seconds=21_600,
        minimum_seconds=900,
        maximum_seconds=604_800,
        priority=50,
        job_count=0,
        change_count=0,
        consecutive_failures=0,
    )
    assert interval >= 86_400


def test_failures_use_bounded_exponential_backoff():
    first = recommended_interval_seconds(
        base_seconds=21_600,
        minimum_seconds=900,
        maximum_seconds=604_800,
        priority=50,
        job_count=10,
        change_count=0,
        consecutive_failures=1,
    )
    later = recommended_interval_seconds(
        base_seconds=21_600,
        minimum_seconds=900,
        maximum_seconds=604_800,
        priority=50,
        job_count=10,
        change_count=0,
        consecutive_failures=5,
    )
    assert first == 43_200
    assert later > first
    assert later <= 604_800
