from app.jobs.source_capabilities import (
    PROVIDER_CAPABILITY_SEEDS,
    ProviderImplementationStatus,
    SourceAccessMode,
    trust_weight,
)


def capability(provider_key: str):
    return next(item for item in PROVIDER_CAPABILITY_SEEDS if item.provider_key == provider_key)


def test_official_sources_are_implemented_without_overclaiming_marketplaces():
    assert capability("greenhouse").access_mode == SourceAccessMode.PUBLIC_ATS
    assert capability("lever").implementation_status == ProviderImplementationStatus.SOURCE_TESTED
    assert capability("ashby").implementation_status == ProviderImplementationStatus.SOURCE_TESTED
    assert capability("usajobs").access_mode == SourceAccessMode.DIRECT_PUBLIC_API
    assert capability("reliefweb").implementation_status == ProviderImplementationStatus.SOURCE_TESTED

    for provider in (
        "indeed",
        "linkedin",
        "dice",
        "monster",
        "ziprecruiter",
        "glassdoor",
        "careerbuilder",
        "wellfound",
        "builtin",
        "higheredjobs",
        "handshake",
        "idealist",
        "devex",
    ):
        record = capability(provider)
        assert record.access_mode == SourceAccessMode.PARTNERSHIP_REQUIRED
        assert record.implementation_status == ProviderImplementationStatus.PARTNERSHIP_REQUIRED


def test_original_employer_sources_outrank_aggregators_and_imports():
    assert trust_weight("APPLYAI_FIRST_PARTY") > trust_weight("OFFICIAL_ATS")
    assert trust_weight("OFFICIAL_ATS") > trust_weight("AUTHORIZED_AGGREGATOR_FEED")
    assert trust_weight("EMPLOYER_CAREER_SITE") > trust_weight("AUTHORIZED_AGGREGATOR_FEED")
    assert trust_weight("AUTHORIZED_AGGREGATOR_FEED") > trust_weight("CANDIDATE_IMPORTED")
    assert trust_weight("CANDIDATE_IMPORTED") > trust_weight("UNVERIFIED_PUBLIC_SOURCE")
