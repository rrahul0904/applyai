from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from app.jobs.remote_eligibility import (
    RemoteSourceEvidence,
    assess_remote_eligibility,
    assess_remote_sources,
)
from app.jobs.opportunity_lifecycle import (
    OpportunityEvidence,
    OpportunityLifecycle,
    advance_lifecycle,
    decide_opportunity,
    sanitized_match_evidence,
)

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_synthetic_ats_restriction_wins_over_worldwide_aggregator_alias():
    fixture = json.loads((Path(__file__).parent / "fixtures/remote/ats_aggregator_synthetic.json").read_text())
    assert fixture["fixture_type"] == "APPLYAI_AUTHORED_SYNTHETIC"
    sources = tuple(RemoteSourceEvidence(**item) for item in fixture["sources"])
    result = assess_remote_sources(canonical_job_id=fixture["canonical_job_id"], sources=sources, candidate_country="CA")
    assert result.decision == "INELIGIBLE"
    assert result.eligible_countries == ("US",)
    assert result.selected_source_url == "https://ats.example/roles/123"
    assert result.conflicting_source_urls == ("https://aggregator.example/jobs/alias-789",)
    assert "LOWER_AUTHORITY_CONFLICT_IGNORED" in result.reason_codes
    # Arrival order cannot change authority, restrictions or the chosen public provenance.
    assert assess_remote_sources(canonical_job_id=fixture["canonical_job_id"], sources=sources[::-1], candidate_country="CA") == result


def source(**overrides):
    values = dict(canonical_job_id="job", source_url="https://ats.example/123", authority="ATS", work_mode="REMOTE", scope="COUNTRY_RESTRICTED", countries=("US",))
    values.update(overrides)
    return RemoteSourceEvidence(**values)


def test_conflicting_equal_authority_fails_closed():
    result = assess_remote_sources(canonical_job_id="job", sources=(source(), source(authority="EMPLOYER", source_url="https://employer.example/123", scope="WORLDWIDE", countries=())), candidate_country="US")
    assert result.decision == "INCONCLUSIVE"
    assert result.remote_scope == "UNKNOWN"
    assert result.reason_codes == ("CONFLICTING_AUTHORITATIVE_SOURCES",)
    assert len(result.conflicting_source_urls) == 2


def test_unknown_employer_scope_cannot_be_filled_from_aggregator_worldwide_claim():
    result = assess_remote_sources(canonical_job_id="job", sources=(source(scope=None, countries=()), source(authority="AGGREGATOR", source_url="https://aggregate.example/123", scope="WORLDWIDE", countries=())), candidate_country="CA")
    assert result.decision == "INCONCLUSIVE"
    assert result.source_authority == "ATS"
    assert "REMOTE_SCOPE_UNKNOWN" in result.reason_codes


def test_unverified_source_authority_cannot_assert_eligibility():
    result = assess_remote_sources(canonical_job_id="job", sources=(source(authority="made-up", scope="WORLDWIDE", countries=()),))
    assert result.reason_codes == ("UNVERIFIED_SOURCE_AUTHORITY",)
    assert result.decision == "INCONCLUSIVE"


def test_different_job_identity_and_credentialed_url_are_not_alias_evidence():
    result = assess_remote_sources(canonical_job_id="job", sources=(source(canonical_job_id="other"), source(source_url="https://user:secret@ats.example/123")))
    assert result.reason_codes == ("NO_CANONICAL_SOURCE_EVIDENCE",)


def test_equal_authority_known_vs_unknown_work_mode_is_a_conflict():
    result = assess_remote_sources(canonical_job_id="job", sources=(source(scope="WORLDWIDE", countries=()), source(source_url="https://ats2.example/123", scope="WORLDWIDE", countries=(), work_mode=None)))
    assert result.decision == "INCONCLUSIVE"
    assert "CONFLICTING_AUTHORITATIVE_SOURCES" in result.reason_codes


@pytest.mark.parametrize("location,scope,countries", [
    ("Remote US only", "WORLDWIDE", ()),
    ("Remote worldwide", "COUNTRY_RESTRICTED", ("US",)),
    ("Remote US only", "COUNTRY_RESTRICTED", ("CA",)),
])
def test_location_and_structured_scope_conflict_is_inconclusive(location, scope, countries):
    result = assess_remote_eligibility(work_mode="REMOTE", location=location, scope=scope, countries=countries, candidate_country="CA")
    assert result.decision == "INCONCLUSIVE"
    assert result.reason_codes == ("CONFLICTING_REMOTE_SCOPE_EVIDENCE",)


@pytest.mark.parametrize("location", ["Remote", "Global company", "Remote Europe", "Remote US", "Remote with occasional travel"])
def test_ambiguous_location_does_not_invent_worldwide_scope(location):
    result = assess_remote_eligibility(work_mode="REMOTE", location=location, candidate_country="US")
    assert result.remote_scope == "UNKNOWN"
    assert result.decision == "INCONCLUSIVE"


def test_country_and_region_constraints_are_not_silently_discarded():
    result = assess_remote_eligibility(work_mode="REMOTE", scope="COUNTRY_RESTRICTED", countries=("US",), regions=("US Eastern",), candidate_country="US")
    assert result.decision == "INCONCLUSIVE"
    assert "MULTIPLE_GEOGRAPHIC_CONSTRAINTS_UNRESOLVED" in result.reason_codes


@pytest.mark.parametrize("country", [None, "", "USA", "unknown"])
def test_missing_or_invalid_candidate_country_stays_inconclusive(country):
    result = assess_remote_eligibility(work_mode="REMOTE", scope="COUNTRY_RESTRICTED", countries=("US",), candidate_country=country)
    assert result.decision == "INCONCLUSIVE"
    assert "CANDIDATE_COUNTRY_UNKNOWN" in result.reason_codes


def test_explicit_region_with_candidate_evidence_is_explainable():
    result = assess_remote_eligibility(work_mode="REMOTE", scope="REGION_RESTRICTED", regions=("EEA",), candidate_regions=("EEA",))
    assert result.decision == "ELIGIBLE"
    assert result.reason_codes == ("REGION_ALLOWED",)
    assert assess_remote_eligibility(work_mode="REMOTE", scope="REGION_RESTRICTED", regions=("EEA",)).decision == "INCONCLUSIVE"


def test_stale_open_observation_does_not_reopen_more_recent_closure():
    current = OpportunityLifecycle("CLOSED", NOW - timedelta(days=4), NOW - timedelta(days=3), closed_at=NOW)
    stale = OpportunityEvidence(NOW - timedelta(days=1), "https://ats.example/123", "OPEN", "COMPLETE", True)
    assert advance_lifecycle(current, stale) == current


def test_aggregator_observation_cannot_reopen_authoritative_closed_listing():
    current = OpportunityLifecycle("CLOSED", NOW - timedelta(days=4), NOW - timedelta(days=3), closed_at=NOW)
    incoming = OpportunityEvidence(NOW + timedelta(days=1), "https://aggregate.example/123", "OPEN", "COMPLETE", False)
    updated = advance_lifecycle(current, incoming)
    assert updated.state == "CLOSED"
    assert updated.closed_at == NOW
    assert updated.last_seen == current.last_seen
    assert updated.reason_codes == ("NON_AUTHORITATIVE_REOPEN_IGNORED",)


@pytest.mark.parametrize("coverage", ["COMPLETE", "PARTIAL", "INCONCLUSIVE", "FAILED"])
def test_search_absence_never_closes_even_complete_source(coverage):
    result = decide_opportunity(OpportunityEvidence(NOW, "https://ats.example/123", "SEARCH_ABSENT", coverage, True))
    assert result.state == "INCONCLUSIVE"
    assert result.reason_codes == ("SEARCH_ABSENCE_NOT_CLOSURE",)


def test_public_projection_removes_nested_private_fields_and_malformed_provenance():
    out = sanitized_match_evidence({
        "remote_eligibility": {"decision": {"email": "private"}, "reason_codes": ["REMOTE_SCOPE_UNKNOWN", {"token": "private"}], "selected_source_url": "https://ats.example/123?token=private", "conflicting_source_urls": ["https://aggregate.example/123?token=private"], "raw_payload": "private"},
        "provenance": {"canonical_sources": {"token": "private"}, "aggregator_sources": [123, "https://aggregate.example/123?token=private"]},
    })
    assert "decision" not in out["remote_eligibility"]
    assert out["remote_eligibility"]["reason_codes"] == ["REMOTE_SCOPE_UNKNOWN"]
    assert out["remote_eligibility"]["selected_source_url"] == "https://ats.example/123"
    assert out["remote_eligibility"]["conflicting_source_urls"] == ["https://aggregate.example/123"]
    assert out["provenance"]["canonical_sources"] == []
    assert "private" not in json.dumps(out)


def test_invalid_country_evidence_cannot_be_dropped_to_assert_worldwide_scope():
    result = assess_remote_eligibility(work_mode="REMOTE", scope="WORLDWIDE", countries=("USA",))
    assert result.decision == "INCONCLUSIVE"
    assert result.reason_codes == ("INVALID_COUNTRY_EVIDENCE",)


def test_salary_projection_does_not_publish_nested_payloads_or_boolean_amounts():
    output = sanitized_match_evidence({"salary": {"minimum": True, "maximum": {"secret": "private"}, "raw": {"email": "private"}, "currency": "USD", "interval": "YEAR", "provenance": {"token": "private"}}})
    assert output["salary"] == {"currency": "USD", "interval": "YEAR"}
