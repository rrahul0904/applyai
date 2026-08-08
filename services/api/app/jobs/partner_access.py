from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class PartnerAccessStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    APPLICATION_PREPARED = "APPLICATION_PREPARED"
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED_SANDBOX = "APPROVED_SANDBOX"
    APPROVED_PRODUCTION = "APPROVED_PRODUCTION"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


@dataclass(frozen=True)
class ProviderContractRights:
    """Rights granted by a provider contract, not inferred from technical reachability.

    All rights default closed. A public web page, an SDK, or an API reference must never
    be interpreted as permission to ingest/store/redistribute provider-owned catalog data.
    Operator-reviewed partner onboarding may explicitly grant the applicable capabilities.
    """

    can_search: bool = False
    can_ingest: bool = False
    can_store: bool = False
    can_redistribute: bool = False
    can_display_remote: bool = False
    can_apply: bool = False
    can_post: bool = False
    can_update: bool = False
    can_close: bool = False
    retention_policy: str = "NOT_GRANTED"
    attribution_required: bool = False

    def as_metadata(self) -> dict[str, bool | str]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderPartnerAccess:
    provider_key: str
    status: PartnerAccessStatus = PartnerAccessStatus.NOT_REQUESTED
    rights: ProviderContractRights = ProviderContractRights()
    sandbox_available: bool = False
    production_approved: bool = False
    credentials_received: bool = False
    agreement_reference: str | None = None
    reviewed_at: str | None = None

    def as_metadata(self) -> dict:
        return {
            "provider_key": self.provider_key,
            "partner_access_status": self.status.value,
            "sandbox_available": self.sandbox_available,
            "production_approved": self.production_approved,
            "credentials_received": self.credentials_received,
            "agreement_reference": self.agreement_reference,
            "reviewed_at": self.reviewed_at,
            "contract_rights": self.rights.as_metadata(),
        }


# These are intentionally fail-closed. They describe ApplyAI's current repository
# evidence boundary, not what a future contract might permit.
DEFAULT_PARTNER_ACCESS: dict[str, ProviderPartnerAccess] = {
    provider: ProviderPartnerAccess(provider_key=provider)
    for provider in (
        "linkedin",
        "indeed",
        "dice",
        "monster",
        "ziprecruiter",
        "glassdoor",
        "careerbuilder",
        "simplyhired",
        "wellfound",
        "builtin",
        "higheredjobs",
        "handshake",
        "idealist",
        "devex",
    )
}


def partner_access_metadata(provider_key: str) -> dict:
    access = DEFAULT_PARTNER_ACCESS.get(provider_key.casefold())
    if access is None:
        return {}
    return access.as_metadata()


def validate_partner_rights(metadata: dict) -> None:
    """Reject impossible approval metadata before a partner adapter can rely on it."""

    status = metadata.get("partner_access_status")
    rights = dict(metadata.get("contract_rights") or {})
    production_approved = bool(metadata.get("production_approved"))
    credentials_received = bool(metadata.get("credentials_received"))

    if status == PartnerAccessStatus.APPROVED_PRODUCTION.value and not production_approved:
        raise ValueError("APPROVED_PRODUCTION requires production_approved=true")
    if production_approved and status != PartnerAccessStatus.APPROVED_PRODUCTION.value:
        raise ValueError("production_approved=true requires APPROVED_PRODUCTION status")

    privileged = any(
        bool(rights.get(key))
        for key in (
            "can_ingest",
            "can_store",
            "can_redistribute",
            "can_display_remote",
            "can_apply",
            "can_post",
            "can_update",
            "can_close",
        )
    )
    if privileged and status not in {
        PartnerAccessStatus.APPROVED_SANDBOX.value,
        PartnerAccessStatus.APPROVED_PRODUCTION.value,
    }:
        raise ValueError("provider rights require approved sandbox or production status")
    if privileged and not credentials_received:
        raise ValueError("provider rights require provisioned credentials")
