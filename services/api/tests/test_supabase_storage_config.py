import pytest

from app.core.config import Settings
from app.core.storage import SupabaseObjectStorageProvider, get_object_storage


def test_supabase_storage_requires_server_credentials():
    with pytest.raises(ValueError, match="SUPABASE_S3_ACCESS_KEY_ID"):
        Settings(
            object_storage_provider="supabase",
            supabase_url="https://applyai-test.supabase.co",
        )


def test_supabase_storage_builds_private_s3_endpoint(monkeypatch):
    captured = {}

    class FakeS3:
        pass

    def fake_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return FakeS3()

    monkeypatch.setattr("app.core.storage.boto3.client", fake_client)
    settings = Settings(
        object_storage_provider="supabase",
        supabase_url="https://applyai-test.supabase.co",
        supabase_storage_bucket="resumes",
        supabase_s3_access_key_id="server-access-key",
        supabase_s3_secret_access_key="server-secret-key",
    )

    provider = get_object_storage(settings)
    assert isinstance(provider, SupabaseObjectStorageProvider)
    assert provider.bucket == "resumes"
    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == (
        "https://applyai-test.storage.supabase.co/storage/v1/s3"
    )
