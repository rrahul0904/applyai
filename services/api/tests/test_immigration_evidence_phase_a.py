from datetime import date
from pathlib import Path

import pytest

from app.immigration_evidence import (
    CapExemptCategory,
    CapExemptEvidence,
    CorrectionReviewStatus,
    EmployerIdentityResolution,
    EmployerResolutionState,
    EvidenceConfidence,
    EvidenceCorrection,
    FilingType,
    HumanReviewState,
    PostingSponsorshipEvidence,
    PostingSponsorshipSignal,
    RoleMatchStrength,
    SponsorshipConclusion,
    SyntheticDolDisclosureAdapter,
    append_correction,
    assess_sponsorship,
    public_assessment_projection,
)


FIXTURES = Path(__file__).parent / "fixtures" / "dol"


def resolved_employer() -> EmployerIdentityResolution:
    return EmployerIdentityResolution(
        resolution_id="employer-resolution-1",
        canonical_employer_id="employer-1",
        public_brand_name="Example Analytics",
        legal_entities=("Example Analytics LLC",),
        aliases=("Example Analytics",),
        match_method="reviewed-legal-entity-alias",
        confidence=0.99,
        human_review_state=HumanReviewState.REVIEWED,
        state=EmployerResolutionState.RESOLVED,
    )


def unresolved_employer() -> EmployerIdentityResolution:
    return EmployerIdentityResolution(
        resolution_id="employer-resolution-unresolved",
        canonical_employer_id=None,
        public_brand_name="Example Analytics",
        legal_entities=(),
        aliases=("Example Analytics",),
        match_method="insufficient-public-evidence",
        confidence=0.2,
        human_review_state=HumanReviewState.NEEDS_REVIEW,
        state=EmployerResolutionState.UNRESOLVED,
    )


def posting(signal: PostingSponsorshipSignal) -> PostingSponsorshipEvidence:
    span = {
        PostingSponsorshipSignal.EXPLICIT_RESTRICTION: (
            "This position is not eligible for employment visa sponsorship."
        ),
        PostingSponsorshipSignal.EXPLICIT_SUPPORT: (
            "Employment visa sponsorship is available for this position."
        ),
    }.get(signal)
    return PostingSponsorshipEvidence(
        evidence_id=f"posting-{signal.value.lower()}",
        signal=signal,
        rule_version="posting-language-v1",
        source_receipt_id="job-source-receipt-1",
        evidence_span=span,
        start_offset=10 if span else None,
        end_offset=10 + len(span) if span else None,
    )


def filings():
    adapter = SyntheticDolDisclosureAdapter()
    lca = adapter.parse_csv(
        (FIXTURES / "fy2026_q3_lca_synthetic.csv").read_text(),
        filing_type=FilingType.LCA,
        dataset="LCA Disclosure Data",
        dataset_version="FY2026-Q3-synthetic-layout",
        as_of_date=date(2026, 6, 30),
        employer=resolved_employer(),
    )
    perm = adapter.parse_csv(
        (FIXTURES / "fy2026_perm_synthetic.csv").read_text(),
        filing_type=FilingType.PERM,
        dataset="PERM Disclosure Data",
        dataset_version="FY2026-synthetic-layout",
        as_of_date=date(2026, 6, 30),
        employer=resolved_employer(),
    )
    return lca + perm


def test_synthetic_dol_layout_is_idempotent_and_preserves_location_provenance():
    receipts = filings()

    assert len(receipts) == 3
    assert len({receipt.source_row_hash for receipt in receipts}) == 3
    first = next(receipt for receipt in receipts if receipt.source_row_id == "SYN-LCA-0001")
    assert first.worksite_city == "Boston"
    assert first.worksite_region == "MA"
    assert first.source_worksite_city == "boston"
    assert first.provenance == "synthetic-dol-layout-fixture"


def test_posting_restriction_overrides_strong_historical_filing_evidence():
    assessment = assess_sponsorship(
        assessment_id="assessment-restriction",
        employer=resolved_employer(),
        posting=posting(PostingSponsorshipSignal.EXPLICIT_RESTRICTION),
        filings=filings(),
        cap_exempt=None,
        role_match_strength=RoleMatchStrength.EXACT,
        location_evidence=("Boston, MA",),
        as_of_date=date(2026, 9, 30),
    )

    assert assessment.conclusion is SponsorshipConclusion.POSTING_RESTRICTS
    assert assessment.confidence is EvidenceConfidence.HIGH
    assert assessment.recent_filing_volume >= 2
    assert any("overrides" in caveat for caveat in assessment.caveats)


def test_explicit_support_is_preserved_without_fabricating_candidate_eligibility():
    assessment = assess_sponsorship(
        assessment_id="assessment-support",
        employer=resolved_employer(),
        posting=posting(PostingSponsorshipSignal.EXPLICIT_SUPPORT),
        filings=filings(),
        cap_exempt=None,
        role_match_strength=RoleMatchStrength.SIMILAR,
        location_evidence=("Boston, MA",),
        as_of_date=date(2026, 9, 30),
    )
    projection = public_assessment_projection(assessment, resolved_employer())

    assert assessment.conclusion is SponsorshipConclusion.POSTING_SUPPORTS
    assert projection["candidate_eligibility"] == "NOT_ASSESSED"
    assert "prediction" in str(projection["disclaimer"]).lower()


def test_unresolved_entity_fails_closed_to_insufficient_data():
    assessment = assess_sponsorship(
        assessment_id="assessment-unresolved",
        employer=unresolved_employer(),
        posting=posting(PostingSponsorshipSignal.SILENT),
        filings=(),
        cap_exempt=None,
        role_match_strength=RoleMatchStrength.UNKNOWN,
        location_evidence=(),
        as_of_date=date(2026, 9, 30),
    )

    assert assessment.conclusion is SponsorshipConclusion.INSUFFICIENT_DATA
    assert assessment.confidence is EvidenceConfidence.NONE
    assert assessment.most_recent_filing_year is None


def test_old_one_off_and_recent_repeated_activity_remain_distinguishable():
    recent = assess_sponsorship(
        assessment_id="assessment-recent",
        employer=resolved_employer(),
        posting=posting(PostingSponsorshipSignal.SILENT),
        filings=filings(),
        cap_exempt=None,
        role_match_strength=RoleMatchStrength.EXACT,
        location_evidence=("Boston, MA",),
        as_of_date=date(2026, 9, 30),
    )
    old_only = tuple(receipt for receipt in filings() if receipt.fiscal_year == 2024)
    old = assess_sponsorship(
        assessment_id="assessment-old",
        employer=resolved_employer(),
        posting=posting(PostingSponsorshipSignal.SILENT),
        filings=old_only,
        cap_exempt=None,
        role_match_strength=RoleMatchStrength.UNRELATED,
        location_evidence=("Cambridge, MA",),
        as_of_date=date(2029, 9, 30),
    )

    assert recent.recent_filing_volume > 0
    assert recent.confidence is EvidenceConfidence.MEDIUM
    assert old.recent_filing_volume == 0
    assert old.confidence is EvidenceConfidence.LOW
    assert recent.role_match_strength is RoleMatchStrength.EXACT
    assert old.role_match_strength is RoleMatchStrength.UNRELATED


def test_cap_exempt_cannot_be_inferred_from_university_or_nonprofit_name():
    with pytest.raises(ValueError, match="Unverified evidence cannot assert"):
        CapExemptEvidence(
            evidence_id="cap-name-only",
            employer_resolution_id="employer-resolution-unresolved",
            verified=False,
            category=CapExemptCategory.HIGHER_EDUCATION,
            evidence_source=None,
            effective_from=None,
            effective_to=None,
        )

    unverified = CapExemptEvidence(
        evidence_id="cap-unverified",
        employer_resolution_id=resolved_employer().resolution_id,
        verified=False,
        category=None,
        evidence_source=None,
        effective_from=None,
        effective_to=None,
    )
    assessment = assess_sponsorship(
        assessment_id="assessment-cap-unverified",
        employer=resolved_employer(),
        posting=posting(PostingSponsorshipSignal.SILENT),
        filings=filings(),
        cap_exempt=unverified,
        role_match_strength=RoleMatchStrength.SIMILAR,
        location_evidence=(),
        as_of_date=date(2026, 9, 30),
    )
    assert assessment.cap_exempt_verified is False


def test_correction_history_is_append_only_and_immutable():
    original = EvidenceCorrection(
        correction_id="correction-1",
        target_type="employer-identity",
        target_id="employer-resolution-1",
        source_receipt_id="user-report-1",
        review_status=CorrectionReviewStatus.PENDING,
        created_at="2026-09-30T12:00:00Z",
        note="Legal entity may be incorrect",
    )
    history = append_correction((), original)
    assert append_correction(history, original) == history

    changed_same_id = EvidenceCorrection(
        correction_id="correction-1",
        target_type=original.target_type,
        target_id=original.target_id,
        source_receipt_id=original.source_receipt_id,
        review_status=CorrectionReviewStatus.ACCEPTED,
        created_at=original.created_at,
        note="Silently rewritten",
    )
    with pytest.raises(ValueError, match="immutable"):
        append_correction(history, changed_same_id)


def test_public_projection_has_no_candidate_work_authorization_or_personal_fields():
    assessment = assess_sponsorship(
        assessment_id="assessment-public",
        employer=resolved_employer(),
        posting=posting(PostingSponsorshipSignal.SILENT),
        filings=filings(),
        cap_exempt=None,
        role_match_strength=RoleMatchStrength.SIMILAR,
        location_evidence=("Boston, MA",),
        as_of_date=date(2026, 9, 30),
    )
    projection = public_assessment_projection(assessment, resolved_employer())

    forbidden = {
        "work_authorization",
        "visa_status",
        "candidate_id",
        "candidate_email",
        "email",
        "resume_id",
    }
    assert forbidden.isdisjoint(projection)
    assert projection["as_of_date"] == "2026-09-30"
