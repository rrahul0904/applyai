from datetime import datetime, timedelta, timezone

from app.jobs.opportunity_lifecycle import (
    OpportunityEvidence,
    OpportunityLifecycle,
    advance_lifecycle,
    decide_opportunity,
    sanitized_match_evidence,
)
from app.jobs.remote_eligibility import assess_remote_eligibility


NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def evidence(observation: str, **overrides) -> OpportunityEvidence:
    values = dict(observed_at=NOW, source_url="https://jobs.example/role", observation=observation)
    values.update(overrides)
    return OpportunityEvidence(**values)


def test_remote_label_is_not_proof_of_worldwide_eligibility():
    result = assess_remote_eligibility(work_mode="REMOTE", location="Remote")
    assert result.remote_scope == "UNKNOWN"
    assert result.decision == "INCONCLUSIVE"
    assert "REMOTE_SCOPE_UNKNOWN" in result.reason_codes


def test_explicit_global_and_country_restrictions_are_explainable():
    worldwide = assess_remote_eligibility(work_mode="REMOTE", location="Remote worldwide")
    assert (worldwide.remote_scope, worldwide.decision) == ("WORLDWIDE", "ELIGIBLE")
    restricted = assess_remote_eligibility(work_mode="REMOTE", scope="COUNTRY_RESTRICTED", countries=("US",), candidate_country="CA")
    assert restricted.decision == "INELIGIBLE"
    assert restricted.reason_codes == ("COUNTRY_NOT_ALLOWED",)


def test_incomplete_search_absence_never_closes_or_expires_listing():
    current = OpportunityLifecycle("OPEN", NOW - timedelta(days=4), NOW - timedelta(days=1))
    for coverage in ("PARTIAL", "INCONCLUSIVE", "FAILED"):
        updated = advance_lifecycle(current, evidence("SEARCH_ABSENT", coverage=coverage))
        assert updated.state == "OPEN"
        assert updated.last_seen == current.last_seen
        assert updated.closed_at is None


def test_only_authoritative_explicit_closure_then_reopen_advances_state():
    closed = decide_opportunity(evidence("EXPLICIT_CLOSED", coverage="COMPLETE", authoritative=True))
    assert closed.state == "CLOSED"
    current = OpportunityLifecycle("OPEN", NOW - timedelta(days=2), NOW - timedelta(days=1))
    updated = advance_lifecycle(current, evidence("EXPLICIT_CLOSED", coverage="COMPLETE", authoritative=True))
    reopened = advance_lifecycle(updated, evidence("OPEN", coverage="COMPLETE", authoritative=True))
    assert reopened.state == "REOPENED"
    assert reopened.closed_at is None


def test_projections_strip_query_tokens_and_unknown_provider_payload_fields():
    output = sanitized_match_evidence({
        "provider": "fixture", "application_url": "https://jobs.example/role?token=secret#section",
        "private_payload": {"email": "candidate@example.com"},
        "provenance": {"canonical_sources": ["https://jobs.example/role?token=secret"], "aggregator_sources": []},
    })
    assert output["application_url"] == "https://jobs.example/role"
    assert "private_payload" not in output
    assert output["provenance"]["canonical_sources"] == ["https://jobs.example/role"]
