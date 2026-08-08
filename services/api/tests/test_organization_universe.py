import json

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.global_job_supply_models import OrganizationProfile
from app.jobs.organization_universe import (
    OrganizationRecord,
    import_organizations,
    load_organization_records,
    normalize_domain,
    validate_record,
)
from app.models import Company


def test_domain_and_record_validation_normalizes_public_organization_identity():
    assert normalize_domain("https://www.Example.ORG/careers") == "example.org"
    record = validate_record(
        OrganizationRecord(
            canonical_name="  Example University  ",
            domain="www.example.edu",
            organization_type="university",
            country_code="us",
            priority=120,
        )
    )
    assert record.canonical_name == "Example University"
    assert record.domain == "example.edu"
    assert record.organization_type == "UNIVERSITY"
    assert record.country_code == "US"
    assert record.priority == 100


def test_jsonl_loader_preserves_dataset_provenance(tmp_path):
    path = tmp_path / "organizations.jsonl"
    path.write_text(
        json.dumps(
            {
                "name": "Example Health System",
                "domain": "examplehealth.org",
                "organization_type": "HEALTH_SYSTEM",
                "aliases": ["Example Health"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    records = load_organization_records(path, dataset="test-public-dataset")
    assert len(records) == 1
    assert records[0].dataset == "test-public-dataset"
    assert records[0].aliases == ("Example Health",)


def test_import_uses_per_record_savepoints_and_domain_dedup(database_url):
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            counts = import_organizations(
                session,
                [
                    OrganizationRecord(
                        canonical_name="Example Research Institute",
                        domain="research.example.org",
                        organization_type="RESEARCH_INSTITUTE",
                        dataset="fixture-a",
                    ),
                    OrganizationRecord(canonical_name="", domain="invalid.example"),
                    OrganizationRecord(
                        canonical_name="Example Research Institute Renamed",
                        domain="research.example.org",
                        organization_type="RESEARCH_INSTITUTE",
                        aliases=("ERI",),
                        dataset="fixture-b",
                    ),
                ],
            )
            assert counts == {
                "created": 1,
                "updated": 1,
                "failed": 1,
                "review_required": 0,
            }
            assert session.scalar(select(func.count(Company.id))) == 1
            profile = session.scalar(select(OrganizationProfile))
            assert profile is not None
            assert profile.canonical_domain == "research.example.org"
            assert profile.dataset_provenance == ["fixture-a", "fixture-b"]
    finally:
        engine.dispose()
