from app.jobs.organization_datasets import (
    parse_cms_hospital_rows,
    parse_government_rows,
    parse_ipeds_rows,
    parse_irs_nonprofit_rows,
    parse_sec_company_payload,
)
from app.jobs.organization_universe import validate_record


def test_sec_payload_maps_public_company_identity():
    records = parse_sec_company_payload(
        {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"]],
        }
    )
    assert len(records) == 1
    record = validate_record(records[0])
    assert record.organization_type == "PUBLIC_COMPANY"
    assert record.external_ids["SEC_CIK"] == "0000320193"
    assert record.metadata["ticker"] == "AAPL"


def test_ipeds_maps_domain_and_institution_identity():
    records = parse_ipeds_rows(
        [
            {
                "UNITID": "166027",
                "INSTNM": "Example University",
                "WEBADDR": "www.example.edu",
                "STABBR": "MA",
                "ICLEVEL": "1",
            }
        ]
    )
    record = validate_record(records[0])
    assert record.organization_type == "UNIVERSITY"
    assert record.domain == "example.edu"
    assert record.external_ids == {"IPEDS_UNITID": "166027"}


def test_cms_maps_hospital_without_forcing_health_system_parent():
    records = parse_cms_hospital_rows(
        [
            {
                "Facility ID": "220001",
                "Facility Name": "Example Medical Center",
                "City/Town": "Boston",
                "State": "MA",
                "Hospital Type": "Acute Care Hospitals",
                "Hospital Ownership": "Voluntary non-profit - Private",
            }
        ]
    )
    record = validate_record(records[0])
    assert record.organization_type == "HOSPITAL"
    assert record.external_ids["CMS_PROVIDER_ID"] == "220001"
    assert record.parent_domain is None


def test_irs_maps_nonprofit_identity_and_low_default_priority():
    record = validate_record(
        parse_irs_nonprofit_rows(
            [
                {
                    "EIN": "12-3456789",
                    "NAME": "Example Foundation",
                    "CITY": "Boston",
                    "STATE": "MA",
                    "NTEE_CD": "T20",
                }
            ]
        )[0]
    )
    assert record.organization_type == "NONPROFIT"
    assert record.external_ids["IRS_EIN"] == "123456789"
    assert record.priority == 35


def test_government_loader_distinguishes_levels():
    records = parse_government_rows(
        [
            {"agency_id": "fed-1", "agency_name": "Federal Example", "level": "federal"},
            {"agency_id": "state-1", "agency_name": "State Example", "level": "state"},
            {"agency_id": "local-1", "agency_name": "City Example", "level": "local"},
        ]
    )
    assert [validate_record(record).organization_type for record in records] == [
        "FEDERAL_AGENCY",
        "STATE_AGENCY",
        "LOCAL_GOVERNMENT",
    ]
