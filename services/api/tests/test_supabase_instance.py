from app.core.supabase_instance import supabase_instance_fingerprint


def test_supabase_instance_fingerprint_normalizes_project_hostname() -> None:
    expected = "579ad99e95a603e1"
    assert supabase_instance_fingerprint("https://applyai-test.supabase.co") == expected
    assert supabase_instance_fingerprint("https://APPLYAI-TEST.SUPABASE.CO/") == expected


def test_supabase_instance_fingerprint_fails_closed_without_hostname() -> None:
    assert supabase_instance_fingerprint(None) == ""
    assert supabase_instance_fingerprint("") == ""
