from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class ShardConfig:
    count: int
    index: int

    @classmethod
    def from_environment(cls) -> "ShardConfig":
        count = max(1, int(os.getenv("JOB_SOURCE_SHARD_COUNT", "1")))
        index = int(os.getenv("JOB_SOURCE_SHARD_INDEX", "0"))
        if index < 0 or index >= count:
            raise ValueError("JOB_SOURCE_SHARD_INDEX must be between 0 and JOB_SOURCE_SHARD_COUNT - 1")
        return cls(count=count, index=index)


def source_shard(source_id: uuid.UUID | str, shard_count: int) -> int:
    if shard_count <= 1:
        return 0
    value = str(source_id).encode("utf-8")
    digest = hashlib.blake2b(value, digest_size=8).digest()
    return int.from_bytes(digest, "big") % shard_count


def belongs_to_shard(source_id: uuid.UUID | str, config: ShardConfig) -> bool:
    return source_shard(source_id, config.count) == config.index


def recommended_interval_seconds(
    *,
    base_seconds: int,
    minimum_seconds: int,
    maximum_seconds: int,
    priority: int,
    job_count: int,
    change_count: int,
    consecutive_failures: int,
) -> int:
    """Adaptive refresh policy for large source universes.

    The policy intentionally keeps source-specific configured intervals as the base,
    then adjusts within explicit min/max bounds. It never converts a disabled/policy-
    blocked source into an active crawler.
    """

    minimum = max(300, int(minimum_seconds))
    maximum = max(minimum, int(maximum_seconds))
    base = min(max(int(base_seconds), minimum), maximum)
    priority = max(0, min(int(priority), 100))
    job_count = max(0, int(job_count))
    change_count = max(0, int(change_count))
    failures = max(0, int(consecutive_failures))

    if failures:
        return min(maximum, base * (2 ** min(failures, 8)))

    # Very active sources and high-priority employers should move toward 1-3 hour
    # refresh windows while respecting a stricter configured minimum.
    change_ratio = change_count / max(job_count, 1)
    if priority >= 90 and (change_count >= 10 or job_count >= 250):
        return max(minimum, min(base, 3 * 60 * 60))
    if change_count >= 25 or change_ratio >= 0.10:
        return max(minimum, int(base * 0.5))
    if change_count > 0 or job_count >= 1_000:
        return max(minimum, int(base * 0.75))

    # Repeatedly empty/quiet boards progressively consume less crawl budget.
    if job_count == 0:
        return min(maximum, max(24 * 60 * 60, base * 2))
    if change_count == 0:
        return min(maximum, max(base, 12 * 60 * 60))
    return base
