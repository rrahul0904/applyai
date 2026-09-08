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
        failure["code"] == "ROLE_TABLE_MUTATION_GRANTED_TO_AUTHENTICATED"
        for failure in report["failures"]
    )
