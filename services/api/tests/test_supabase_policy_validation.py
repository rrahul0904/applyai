from pathlib import Path

from scripts.validate_supabase_policies import repository_root, validate_policy_sql


def test_repository_supabase_policies_match_current_orm_schema() -> None:
    sql = (repository_root() / "supabase" / "policies.sql").read_text()
    report = validate_policy_sql(sql)
    assert report["status"] == "PASS", report["failures"]


def test_role_mutation_grant_is_rejected() -> None:
    sql = (
        (repository_root() / "supabase" / "policies.sql").read_text()
        + "\ngrant update on public.user_roles to authenticated;"
    )
    report = validate_policy_sql(sql)
    assert report["status"] == "BLOCKED"
    assert any(
        failure["code"] == "PUBLIC_APPLICATION_TABLE_GRANTED_TO_BROWSER_ROLE"
        for failure in report["failures"]
    )
    assert any(
        failure["code"] == "ROLE_TABLE_MUTATION_GRANTED_TO_AUTHENTICATED"
        for failure in report["failures"]
    )


def test_read_grant_to_browser_role_is_rejected() -> None:
    sql = (
        (repository_root() / "supabase" / "policies.sql").read_text()
        + "\ngrant select on public.jobs to anon;"
    )
    report = validate_policy_sql(sql)
    assert report["status"] == "BLOCKED"
    assert any(
        failure["code"] == "PUBLIC_APPLICATION_TABLE_GRANTED_TO_BROWSER_ROLE"
        for failure in report["failures"]
    )


def test_global_data_api_lockdown_is_required() -> None:
    sql = (repository_root() / "supabase" / "policies.sql").read_text().replace(
        "revoke all privileges on all tables in schema public from anon, authenticated;",
        "",
    )
    report = validate_policy_sql(sql)
    assert report["status"] == "BLOCKED"
    assert any(
        failure["code"] == "REQUIRED_SECURITY_INVARIANTS_MISSING"
        and "global_public_table_revoke" in failure["invariants"]
        for failure in report["failures"]
    )
