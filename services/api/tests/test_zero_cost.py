import io

import pytest

from app.core.config import Settings
from app.core.storage import DatabaseObjectStorageProvider
from app.core.zero_cost import ResumeStorageUsage, resume_upload_block_reason


def usage(**overrides: int) -> ResumeStorageUsage:
    values = {
        "user_versions": 0,
        "user_pending_uploads": 0,
        "user_reserved_bytes": 0,
        "global_reserved_bytes": 0,
        "monthly_class_a_operations": 0,
        "monthly_class_b_operations": 0,
    }
    values.update(overrides)
    return ResumeStorageUsage(**values)


def test_zero_cost_resume_limits_leave_provider_headroom():
    settings = Settings()

    assert settings.max_resume_bytes == 5 * 1024 * 1024
    assert settings.max_resume_versions_per_user == 5
    assert settings.max_resume_storage_bytes_per_user == 25 * 1024 * 1024
    assert settings.max_r2_storage_bytes == 5 * 1024 * 1024 * 1024
    assert settings.max_monthly_r2_class_a_operations == 500_000
    assert settings.max_monthly_r2_class_b_operations == 5_000_000
    assert settings.max_database_object_storage_bytes == 250 * 1024 * 1024
    assert settings.billing_enabled is False
    assert settings.clerk_mru_warning_threshold == 40_000
    assert settings.clerk_mru_critical_threshold == 45_000
    assert settings.clerk_mru_review_threshold == 50_000


def test_fifth_retained_version_blocks_another_upload():
    blocked = resume_upload_block_reason(
        usage(user_versions=5),
        requested_bytes=1,
        settings=Settings(),
    )

    assert blocked is not None
    assert blocked[0] == "USER_VERSION_LIMIT"


def test_user_storage_is_hard_capped_at_25_mb():
    settings = Settings()
    blocked = resume_upload_block_reason(
        usage(user_reserved_bytes=settings.max_resume_storage_bytes_per_user),
        requested_bytes=1,
        settings=settings,
    )

    assert blocked is not None
    assert blocked[0] == "USER_STORAGE_LIMIT"


def test_global_storage_is_hard_capped_at_5_gb():
    settings = Settings()
    blocked = resume_upload_block_reason(
        usage(global_reserved_bytes=settings.object_storage_hard_limit_bytes),
        requested_bytes=1,
        settings=settings,
    )

    assert blocked is not None
    assert blocked[0] == "OBJECT_STORAGE_LIMIT"


def test_operation_limits_fail_closed():
    settings = Settings(object_storage_provider="s3", s3_bucket="applyai-resumes")

    class_a = resume_upload_block_reason(
        usage(monthly_class_a_operations=settings.max_monthly_r2_class_a_operations),
        requested_bytes=1,
        settings=settings,
    )
    class_b = resume_upload_block_reason(
        usage(monthly_class_b_operations=settings.max_monthly_r2_class_b_operations),
        requested_bytes=1,
        settings=settings,
    )

    assert class_a is not None and class_a[0] == "R2_CLASS_A_LIMIT"
    assert class_b is not None and class_b[0] == "R2_CLASS_B_LIMIT"


@pytest.mark.postgres
def test_database_object_storage_round_trip(database_url):
    del database_url
    storage = DatabaseObjectStorageProvider(Settings(object_storage_provider="postgres"))
    key = "zero-cost/test-resume.pdf"

    storage.put(
        key=key,
        content=io.BytesIO(b"%PDF zero cost"),
        content_type="application/pdf",
    )

    assert storage.get(key=key) == b"%PDF zero cost"
    assert storage.head(key=key).size == 14
    storage.delete(key=key)
    with pytest.raises(FileNotFoundError):
        storage.get(key=key)


@pytest.mark.postgres
def test_database_object_storage_fails_closed_at_hard_limit(database_url):
    del database_url
    storage = DatabaseObjectStorageProvider(Settings(object_storage_provider="postgres"))
    storage.hard_limit_bytes = 3

    with pytest.raises(RuntimeError, match="ZERO_COST_OBJECT_STORAGE_LIMIT"):
        storage.put(
            key="zero-cost/too-large.pdf",
            content=io.BytesIO(b"four"),
            content_type="application/pdf",
        )
