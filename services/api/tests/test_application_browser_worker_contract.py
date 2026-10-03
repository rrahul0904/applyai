from pathlib import Path


WORKER = Path(__file__).resolve().parents[1] / "scripts" / "application-browser-worker.mjs"


def _source() -> str:
    return WORKER.read_text(encoding="utf-8")


def test_read_back_verification_happens_before_navigation_or_submit() -> None:
    source = _source()
    verification = source.index("const verification = await verifyPageFields(page, pageFillResults);")
    action = source.index("const action = await nextAction(page);")

    assert verification < action
    assert '"PRE_SUBMIT_VERIFICATION_FAILED"' in source
    assert "pre_submit_verified: true" in source
    assert "verified_field_ids" in source
    assert "verification_pages" in source


def test_legal_attestation_is_a_human_only_boundary() -> None:
    source = _source()

    assert 'field.canonical_key !== "legal_attestation"' in source
    assert 'field.canonical_key === "legal_attestation"' in source
    assert '"LEGAL_ATTESTATION_REQUIRED"' in source
    assert "ApplyAI will not sign or attest on the candidate's behalf." in source


def test_security_challenges_remain_human_only() -> None:
    source = _source()

    assert '"SECURITY_CHALLENGE"' in source
    assert "ApplyAI will not bypass access controls." in source
    assert 'iframe[src*="recaptcha"]' in source
    assert 'iframe[src*="hcaptcha"]' in source
