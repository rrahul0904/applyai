from app.jobs.source_completeness import (
    SourceCompleteness,
    closure_authoritative,
    connector_completeness,
    observed_completeness,
)


class Connector:
    key = "greenhouse"


class PaginatedConnector:
    key = "lever"


class PartialConnector:
    key = "career-site"
    authoritative_snapshot = False


class TruncatedConnector:
    key = "custom"
    source_completeness = "TRUNCATED"


def test_known_full_connectors_are_classified_explicitly():
    assert connector_completeness(Connector()) == SourceCompleteness.FULL_SNAPSHOT
    assert connector_completeness(PaginatedConnector()) == SourceCompleteness.PAGINATED_FULL_SNAPSHOT


def test_partial_or_truncated_sources_are_never_closure_authority():
    assert connector_completeness(PartialConnector()) == SourceCompleteness.PARTIAL
    assert connector_completeness(TruncatedConnector()) == SourceCompleteness.TRUNCATED
    assert closure_authoritative(SourceCompleteness.PARTIAL) is False
    assert closure_authoritative(SourceCompleteness.TRUNCATED) is False
    assert closure_authoritative(SourceCompleteness.FULL_SNAPSHOT) is True


def test_record_failures_downgrade_observed_completeness_to_partial():
    result = observed_completeness(
        Connector(),
        {"fetched": 10, "valid": 9, "failed": 1},
    )
    assert result == SourceCompleteness.PARTIAL
