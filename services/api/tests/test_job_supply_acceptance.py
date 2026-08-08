from scripts.job_supply_acceptance import REPRESENTATIVE_PROVIDER_TYPES, evaluate_acceptance


def evidence(**overrides):
    value = {
        "organizations_total": 10,
        "active_real_sources": 5,
        "successful_real_source_runs": 5,
        "real_canonical_jobs": 100,
        "representative_providers_verified": sorted(REPRESENTATIVE_PROVIDER_TYPES),
    }
    value.update(overrides)
    return value


def test_acceptance_fails_closed_without_real_organization_and_source_evidence():
    result = evaluate_acceptance(
        evidence(
            organizations_total=0,
            active_real_sources=0,
            successful_real_source_runs=0,
            real_canonical_jobs=0,
            representative_providers_verified=[],
        ),
        app_env="staging",
    )
    assert result["status"] == "BLOCKED_EXTERNAL_CONFIGURATION"
    assert result["claim"] == "SOURCE_IMPLEMENTED_NOT_LIVE_VERIFIED"
    assert len(result["blocking_dependencies"]) == 4


def test_real_runtime_evidence_outside_staging_does_not_claim_staging_verification():
    result = evaluate_acceptance(evidence(), app_env="development")
    assert result["status"] == "RUNTIME_EVIDENCE_AVAILABLE"
    assert result["claim"] == "LIVE_PUBLIC_SOURCE_EVIDENCE_AVAILABLE_NOT_STAGING_VERIFIED"
    assert result["is_staging_environment"] is False


def test_staging_requires_representative_provider_coverage():
    result = evaluate_acceptance(
        evidence(representative_providers_verified=["GREENHOUSE", "LEVER"]),
        app_env="staging",
    )
    assert result["status"] == "PARTIAL_STAGING_ACCEPTANCE"
    assert "USAJOBS" in result["missing_representative_providers"]


def test_staging_pass_requires_all_measured_evidence_and_representative_sources():
    result = evaluate_acceptance(evidence(), app_env="staging")
    assert result["status"] == "PASS"
    assert result["claim"] == "LIVE_STAGING_VERIFIED"
    assert result["blocking_dependencies"] == []
    assert result["missing_representative_providers"] == []
