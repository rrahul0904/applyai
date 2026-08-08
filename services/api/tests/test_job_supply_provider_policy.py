from app.jobs.source_capabilities import PROVIDER_CAPABILITY_SEEDS, SourceAccessMode


def by_key(key: str):
    return next(seed for seed in PROVIDER_CAPABILITY_SEEDS if seed.provider_key == key)


def test_employer_origin_sources_are_automatable_but_policy_bounded():
    greenhouse = by_key("greenhouse")
    workday = by_key("workday")
    assert greenhouse.access_mode == SourceAccessMode.PUBLIC_ATS
    assert greenhouse.allowed_for_automated_ingestion is True
    assert greenhouse.supports_closure_detection is True
    assert workday.access_mode == SourceAccessMode.EMPLOYER_CAREER_SITE
    assert workday.allowed_for_automated_ingestion is True
    assert "ROBOTS" in workday.robots_policy


def test_major_marketplaces_remain_partnership_gated():
    for key in ("indeed", "linkedin", "dice", "monster", "ziprecruiter", "glassdoor"):
        provider = by_key(key)
        assert provider.access_mode == SourceAccessMode.PARTNERSHIP_REQUIRED
        assert provider.requires_partnership is True
        assert provider.allowed_for_automated_ingestion is False
        assert provider.trust_level == "AUTHORIZED_AGGREGATOR_FEED"
