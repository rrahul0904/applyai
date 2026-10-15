from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import asdict, dataclass
from datetime import date
from enum import StrEnum
from typing import Iterable, Mapping, Protocol


class FilingType(StrEnum):
    LCA = "LCA"
    PERM = "PERM"


class EmployerResolutionState(StrEnum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class HumanReviewState(StrEnum):
    NOT_REVIEWED = "NOT_REVIEWED"
    REVIEWED = "REVIEWED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class PostingSponsorshipSignal(StrEnum):
    EXPLICIT_SUPPORT = "EXPLICIT_SUPPORT"
    EXPLICIT_RESTRICTION = "EXPLICIT_RESTRICTION"
    SILENT = "SILENT"
    AMBIGUOUS = "AMBIGUOUS"


class SponsorshipConclusion(StrEnum):
    POSTING_SUPPORTS = "POSTING_SUPPORTS"
    POSTING_RESTRICTS = "POSTING_RESTRICTS"
    HISTORICAL_EVIDENCE_ONLY = "HISTORICAL_EVIDENCE_ONLY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class EvidenceConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class RoleMatchStrength(StrEnum):
    EXACT = "EXACT"
    SIMILAR = "SIMILAR"
    UNRELATED = "UNRELATED"
    UNKNOWN = "UNKNOWN"


class CapExemptCategory(StrEnum):
    HIGHER_EDUCATION = "HIGHER_EDUCATION"
    AFFILIATED_NONPROFIT = "AFFILIATED_NONPROFIT"
    NONPROFIT_RESEARCH = "NONPROFIT_RESEARCH"
    GOVERNMENT_RESEARCH = "GOVERNMENT_RESEARCH"


class CorrectionReviewStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class EmployerIdentityResolution:
    resolution_id: str
    canonical_employer_id: str | None
    public_brand_name: str
    legal_entities: tuple[str, ...]
    aliases: tuple[str, ...]
    match_method: str
    confidence: float
    human_review_state: HumanReviewState
    state: EmployerResolutionState

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("Employer identity confidence must be between 0 and 1")
        if self.state is EmployerResolutionState.RESOLVED:
            if not self.canonical_employer_id or not self.legal_entities:
                raise ValueError("Resolved employer identity requires a canonical id and legal entity")
        elif self.canonical_employer_id is not None:
            raise ValueError("Ambiguous or unresolved identities cannot select a canonical employer")


@dataclass(frozen=True)
class ImmigrationEvidenceReceipt:
    receipt_id: str
    source_agency: str
    dataset: str
    dataset_version: str
    as_of_date: date
    employer_resolution_id: str
    filing_type: FilingType
    fiscal_year: int
    determination_date: date | None
    role_title: str | None
    soc_code: str | None
    worksite_city: str | None
    worksite_region: str | None
    source_worksite_city: str | None
    source_worksite_region: str | None
    source_row_id: str
    source_row_hash: str
    provenance: str

    def __post_init__(self) -> None:
        if len(self.source_row_hash) != 64:
            raise ValueError("Source row hash must be a SHA-256 hex digest")


@dataclass(frozen=True)
class PostingSponsorshipEvidence:
    evidence_id: str
    signal: PostingSponsorshipSignal
    rule_version: str
    source_receipt_id: str
    evidence_span: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        explicit = self.signal in {
            PostingSponsorshipSignal.EXPLICIT_SUPPORT,
            PostingSponsorshipSignal.EXPLICIT_RESTRICTION,
        }
        if explicit and not self.evidence_span:
            raise ValueError("Explicit posting sponsorship evidence requires an evidence span")
        if self.evidence_span is not None:
            if self.start_offset is None or self.end_offset is None:
                raise ValueError("Evidence span offsets must be recorded together")
            if self.start_offset < 0 or self.end_offset <= self.start_offset:
                raise ValueError("Posting evidence offsets are invalid")


@dataclass(frozen=True)
class CapExemptEvidence:
    evidence_id: str
    employer_resolution_id: str
    verified: bool
    category: CapExemptCategory | None
    evidence_source: str | None
    effective_from: date | None
    effective_to: date | None

    def __post_init__(self) -> None:
        if self.verified and (self.category is None or not self.evidence_source):
            raise ValueError("Verified cap-exempt evidence requires category and source")
        if not self.verified and self.category is not None:
            raise ValueError("Unverified evidence cannot assert a cap-exempt category")
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValueError("Cap-exempt effective dates are invalid")


@dataclass(frozen=True)
class EvidenceCorrection:
    correction_id: str
    target_type: str
    target_id: str
    source_receipt_id: str
    review_status: CorrectionReviewStatus
    created_at: str
    note: str | None = None


@dataclass(frozen=True)
class SponsorshipAssessment:
    assessment_id: str
    employer_resolution_id: str
    conclusion: SponsorshipConclusion
    confidence: EvidenceConfidence
    supporting_evidence_ids: tuple[str, ...]
    role_match_strength: RoleMatchStrength
    location_evidence: tuple[str, ...]
    most_recent_filing_year: int | None
    recent_filing_volume: int
    cap_exempt_verified: bool
    as_of_date: date
    caveats: tuple[str, ...]
    policy_version: str = "immigration-evidence-phase-a-v1"


def append_correction(
    history: tuple[EvidenceCorrection, ...],
    correction: EvidenceCorrection,
) -> tuple[EvidenceCorrection, ...]:
    for existing in history:
        if existing.correction_id != correction.correction_id:
            continue
        if existing == correction:
            return history
        raise ValueError("Correction history is immutable; append a new correction id")
    return (*history, correction)


def _normalized_entity(value: str) -> str:
    return " ".join(value.casefold().replace(",", " ").replace(".", " ").split())


def _parse_iso_date(value: str | None) -> date | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    return date.fromisoformat(cleaned[:10])


def _fiscal_year(value: str | None, determination: date | None, fallback: int) -> int:
    cleaned = (value or "").strip()
    if cleaned.isdigit():
        return int(cleaned)
    if determination is not None:
        return determination.year
    return fallback


LCA_LAYOUT_FIELDS = {
    "case": "CASE_NUMBER",
    "employer": "EMPLOYER_NAME",
    "determination": "DECISION_DATE",
    "fiscal_year": "FISCAL_YEAR",
    "role": "SOC_TITLE",
    "soc": "SOC_CODE",
    "city": "WORKSITE_CITY",
    "region": "WORKSITE_STATE",
}

PERM_LAYOUT_FIELDS = {
    "case": "CASE_NUMBER",
    "employer": "EMPLOYER_NAME",
    "determination": "DECISION_DATE",
    "fiscal_year": "FISCAL_YEAR",
    "role": "JOB_TITLE",
    "soc": "SOC_CODE",
    "city": "WORKSITE_CITY",
    "region": "WORKSITE_STATE",
}


class DolDisclosureAdapter(Protocol):
    def parse_rows(
        self,
        rows: Iterable[Mapping[str, str]],
        *,
        filing_type: FilingType,
        dataset: str,
        dataset_version: str,
        as_of_date: date,
        employer: EmployerIdentityResolution,
    ) -> tuple[ImmigrationEvidenceReceipt, ...]: ...


class SyntheticDolDisclosureAdapter:
    """Tiny record-layout adapter for rights-safe synthetic DOL-shaped fixtures."""

    agency = "U.S. Department of Labor OFLC"

    def parse_csv(
        self,
        value: str,
        *,
        filing_type: FilingType,
        dataset: str,
        dataset_version: str,
        as_of_date: date,
        employer: EmployerIdentityResolution,
    ) -> tuple[ImmigrationEvidenceReceipt, ...]:
        return self.parse_rows(
            csv.DictReader(io.StringIO(value)),
            filing_type=filing_type,
            dataset=dataset,
            dataset_version=dataset_version,
            as_of_date=as_of_date,
            employer=employer,
        )

    def parse_rows(
        self,
        rows: Iterable[Mapping[str, str]],
        *,
        filing_type: FilingType,
        dataset: str,
        dataset_version: str,
        as_of_date: date,
        employer: EmployerIdentityResolution,
    ) -> tuple[ImmigrationEvidenceReceipt, ...]:
        if employer.state is not EmployerResolutionState.RESOLVED:
            return ()

        layout = LCA_LAYOUT_FIELDS if filing_type is FilingType.LCA else PERM_LAYOUT_FIELDS
        accepted_names = {
            _normalized_entity(value)
            for value in (*employer.legal_entities, *employer.aliases)
            if value.strip()
        }
        receipts: list[ImmigrationEvidenceReceipt] = []
        seen_hashes: set[str] = set()
        for row in rows:
            employer_name = str(row.get(layout["employer"]) or "").strip()
            if _normalized_entity(employer_name) not in accepted_names:
                continue

            safe_fields = {
                key: str(row.get(column) or "").strip()
                for key, column in layout.items()
            }
            canonical = "|".join(f"{key}={safe_fields[key]}" for key in sorted(safe_fields))
            row_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if row_hash in seen_hashes:
                continue
            seen_hashes.add(row_hash)

            determination = _parse_iso_date(safe_fields["determination"])
            city_raw = safe_fields["city"] or None
            region_raw = safe_fields["region"] or None
            city = city_raw.title() if city_raw else None
            region = region_raw.upper() if region_raw else None
            source_row_id = safe_fields["case"] or f"sha256:{row_hash[:20]}"
            fiscal_year = _fiscal_year(
                safe_fields["fiscal_year"],
                determination,
                as_of_date.year,
            )
            receipt_id = hashlib.sha256(
                f"{filing_type.value}|{dataset_version}|{row_hash}".encode("utf-8")
            ).hexdigest()[:32]
            receipts.append(
                ImmigrationEvidenceReceipt(
                    receipt_id=receipt_id,
                    source_agency=self.agency,
                    dataset=dataset,
                    dataset_version=dataset_version,
                    as_of_date=as_of_date,
                    employer_resolution_id=employer.resolution_id,
                    filing_type=filing_type,
                    fiscal_year=fiscal_year,
                    determination_date=determination,
                    role_title=safe_fields["role"] or None,
                    soc_code=safe_fields["soc"] or None,
                    worksite_city=city,
                    worksite_region=region,
                    source_worksite_city=city_raw,
                    source_worksite_region=region_raw,
                    source_row_id=source_row_id,
                    source_row_hash=row_hash,
                    provenance="synthetic-dol-layout-fixture",
                )
            )
        return tuple(receipts)


def assess_sponsorship(
    *,
    assessment_id: str,
    employer: EmployerIdentityResolution,
    posting: PostingSponsorshipEvidence,
    filings: tuple[ImmigrationEvidenceReceipt, ...],
    cap_exempt: CapExemptEvidence | None,
    role_match_strength: RoleMatchStrength,
    location_evidence: tuple[str, ...],
    as_of_date: date,
) -> SponsorshipAssessment:
    matching_filings = tuple(
        receipt for receipt in filings if receipt.employer_resolution_id == employer.resolution_id
    )
    filing_years = [receipt.fiscal_year for receipt in matching_filings]
    most_recent = max(filing_years, default=None)
    recent_floor = as_of_date.year - 2
    recent_volume = sum(1 for year in filing_years if recent_floor <= year <= as_of_date.year)
    evidence_ids = [posting.evidence_id, *(receipt.receipt_id for receipt in matching_filings)]

    verified_cap_exempt = bool(
        cap_exempt
        and cap_exempt.verified
        and cap_exempt.employer_resolution_id == employer.resolution_id
    )
    if verified_cap_exempt and cap_exempt is not None:
        evidence_ids.append(cap_exempt.evidence_id)

    caveats = [
        "Evidence describes employer/posting history, not candidate immigration eligibility.",
        "Public filing releases can lag current employer policy.",
    ]

    if posting.signal is PostingSponsorshipSignal.EXPLICIT_RESTRICTION:
        conclusion = SponsorshipConclusion.POSTING_RESTRICTS
        confidence = EvidenceConfidence.HIGH
        caveats.append("Current posting restriction overrides historical filing activity.")
    elif posting.signal is PostingSponsorshipSignal.EXPLICIT_SUPPORT:
        conclusion = SponsorshipConclusion.POSTING_SUPPORTS
        confidence = EvidenceConfidence.HIGH
        caveats.append("Posting support language does not determine candidate-specific eligibility.")
    elif employer.state is not EmployerResolutionState.RESOLVED:
        conclusion = SponsorshipConclusion.INSUFFICIENT_DATA
        confidence = EvidenceConfidence.NONE
        evidence_ids = [posting.evidence_id]
        most_recent = None
        recent_volume = 0
        verified_cap_exempt = False
        caveats.append("Employer legal entity is ambiguous or unresolved.")
    elif matching_filings:
        conclusion = SponsorshipConclusion.HISTORICAL_EVIDENCE_ONLY
        confidence = EvidenceConfidence.MEDIUM if recent_volume else EvidenceConfidence.LOW
    else:
        conclusion = SponsorshipConclusion.INSUFFICIENT_DATA
        confidence = EvidenceConfidence.LOW
        caveats.append("No matching filing evidence was found in the supplied disclosure slice.")

    return SponsorshipAssessment(
        assessment_id=assessment_id,
        employer_resolution_id=employer.resolution_id,
        conclusion=conclusion,
        confidence=confidence,
        supporting_evidence_ids=tuple(dict.fromkeys(evidence_ids)),
        role_match_strength=role_match_strength,
        location_evidence=location_evidence,
        most_recent_filing_year=most_recent,
        recent_filing_volume=recent_volume,
        cap_exempt_verified=verified_cap_exempt,
        as_of_date=as_of_date,
        caveats=tuple(caveats),
    )


def public_assessment_projection(
    assessment: SponsorshipAssessment,
    employer: EmployerIdentityResolution,
) -> dict[str, object]:
    """Candidate-facing evidence only; candidate work-authorization data never enters this DTO."""

    return {
        "assessment_id": assessment.assessment_id,
        "employer": employer.public_brand_name,
        "conclusion": assessment.conclusion.value,
        "confidence": assessment.confidence.value,
        "supporting_evidence_ids": list(assessment.supporting_evidence_ids),
        "role_match_strength": assessment.role_match_strength.value,
        "location_evidence": list(assessment.location_evidence),
        "most_recent_filing_year": assessment.most_recent_filing_year,
        "recent_filing_volume": assessment.recent_filing_volume,
        "cap_exempt_verified": assessment.cap_exempt_verified,
        "as_of_date": assessment.as_of_date.isoformat(),
        "candidate_eligibility": "NOT_ASSESSED",
        "caveats": list(assessment.caveats),
        "disclaimer": "Evidence summary only; not legal advice or a visa outcome prediction.",
    }


def correction_projection(correction: EvidenceCorrection) -> dict[str, object]:
    return asdict(correction)
