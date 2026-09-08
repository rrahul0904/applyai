from scripts.migrate_resume_objects_to_supabase import (
    normalize_content_type,
    project_ref_from_url,
    storage_endpoint,
)


def test_project_ref_and_storage_endpoint_are_derived_from_hosted_url() -> None:
    url = "https://applyai123.supabase.co"
    assert project_ref_from_url(url) == "applyai123"
    assert storage_endpoint(url) == (
        "https://applyai123.storage.supabase.co/storage/v1/s3"
    )


def test_project_ref_rejects_non_hosted_url() -> None:
    try:
        project_ref_from_url("https://example.com")
    except ValueError as exc:
        assert "*.supabase.co" in str(exc)
    else:
        raise AssertionError("non-Supabase URL should be rejected")


def test_content_type_normalization_ignores_parameters() -> None:
    assert normalize_content_type("application/pdf; charset=binary") == "application/pdf"
    assert normalize_content_type(None) == "application/octet-stream"
