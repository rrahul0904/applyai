import pytest

from app.jobs.partner_access import (
    DEFAULT_PARTNER_ACCESS,
    PartnerAccessStatus,
    ProviderContractRights,
    partner_access_metadata,
    validate_partner_rights,
)


def test_linkedin_and_indeed_start_without_catalog_rights():
    for provider in ("linkedin", "indeed"):
        access = DEFAULT_PARTNER_ACCESS[provider]
        assert access.status == PartnerAccessStatus.NOT_REQUESTED
        assert access.production_approved is False
        assert access.credentials_received is False
        rights = access.rights
        assert rights.can_search is False
        assert rights.can_ingest is False
        assert rights.can_store is False
        assert rights.can_redistribute is False
        assert rights.can_display_remote is False
        assert rights.can_apply is False
        assert rights.can_post is False
        assert rights.can_update is False
        assert rights.can_close is False
        assert rights.retention_policy == "NOT_GRANTED"


def test_partner_access_metadata_does_not_infer_rights_from_provider_name():
    linkedin = partner_access_metadata("LinkedIn")
    indeed = partner_access_metadata("INDEED")
    assert linkedin["partner_access_status"] == "NOT_REQUESTED"
    assert indeed["partner_access_status"] == "NOT_REQUESTED"
    assert linkedin["contract_rights"]["can_ingest"] is False
    assert indeed["contract_rights"]["can_store"] is False


def test_privileged_rights_require_approval_and_credentials():
    rights = ProviderContractRights(can_display_remote=True).as_metadata()
    with pytest.raises(ValueError, match="approved sandbox or production"):
        validate_partner_rights(
            {
                "partner_access_status": "APPLICATION_SUBMITTED",
                "credentials_received": False,
                "production_approved": False,
                "contract_rights": rights,
            }
        )

    with pytest.raises(ValueError, match="provisioned credentials"):
        validate_partner_rights(
            {
                "partner_access_status": "APPROVED_SANDBOX",
                "credentials_received": False,
                "production_approved": False,
                "contract_rights": rights,
            }
        )

    validate_partner_rights(
        {
            "partner_access_status": "APPROVED_SANDBOX",
            "credentials_received": True,
            "production_approved": False,
            "contract_rights": rights,
        }
    )


def test_production_approval_state_is_consistent():
    with pytest.raises(ValueError, match="production_approved=true"):
        validate_partner_rights(
            {
                "partner_access_status": "APPROVED_PRODUCTION",
                "production_approved": False,
                "credentials_received": True,
                "contract_rights": {},
            }
        )

    with pytest.raises(ValueError, match="APPROVED_PRODUCTION status"):
        validate_partner_rights(
            {
                "partner_access_status": "UNDER_REVIEW",
                "production_approved": True,
                "credentials_received": True,
                "contract_rights": {},
            }
        )
