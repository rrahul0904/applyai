from app.core.clerk_instance import clerk_instance_fingerprint


def test_clerk_instance_fingerprint_normalizes_issuer_hostname() -> None:
    expected = "2f2a1c73d57179de"
    assert clerk_instance_fingerprint("https://demo.clerk.accounts.dev") == expected
    assert clerk_instance_fingerprint("https://DEMO.CLERK.ACCOUNTS.DEV/") == expected


def test_clerk_instance_fingerprint_fails_closed_without_hostname() -> None:
    assert clerk_instance_fingerprint(None) == ""
    assert clerk_instance_fingerprint("") == ""
