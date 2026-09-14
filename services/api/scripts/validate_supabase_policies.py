from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from app.core.database import Base
from app import (  # noqa: F401
    agent_models,
    agent_policy_models,
    application_agent_models,
    career_memory_models,
    career_models,
    durability_models,
    global_job_supply_models,
    job_quality_models,
    job_source_models,
    models,
    operations_models,
    platform_models,
    postgres_queue_models,
    privacy_models,
    resume_share_models,
    zero_cost_models,
)

PUBLIC_REFERENCE = re.compile(r"\bpublic\.([a-zA-Z_][a-zA-Z0-9_]*)\b")

SENSITIVE_TABLES = {
    "users",
    "candidate_profiles",
    "candidate_preferences",
    "candidate_target_roles",
    "candidate_experiences",
    "candidate_education",
    "candidate_skills",
    "resumes",
    "resume_versions",
    "saved_jobs",
    "applications",
    "application_documents",
    "application_answers",
    "application_notes",
    "resume_share_links",
    "user_roles",
    "roles",
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def orm_table_names() -> set[str]:
    return {table.name for table in Base.metadata.sorted_tables}


def public_references(sql: str) -> set[str]:
    return set(PUBLIC_REFERENCE.findall(sql))


def validate_policy_sql(sql: str) -> dict[str, object]:
    tables = orm_table_names()
    refs = public_references(sql)
    table_refs = refs & tables

    unknown_public_references = sorted(refs - tables)
    stale_expected_tables = sorted(SENSITIVE_TABLES - tables)
    missing_policy_coverage = sorted(SENSITIVE_TABLES - table_refs)

    dangerous_role_grants: list[str] = []
    direct_data_api_grants: list[str] = []
    for statement in re.split(r";\s*", sql):
        normalized = " ".join(statement.lower().split())
        if not normalized.startswith("grant "):
            continue

        targets_browser_role = (
            " to authenticated" in normalized or " to anon" in normalized
        )
        if not targets_browser_role:
            continue

        if " on public." in normalized and any(
            normalized.startswith(f"grant {action} ")
            for action in ("select", "insert", "update", "delete", "all")
        ):
            direct_data_api_grants.append(statement.strip())

        if " to authenticated" in normalized and any(
            action in normalized for action in (" insert ", " update ", " delete ", " all ")
        ):
            if "user_roles" in normalized or "roles" in normalized:
                dangerous_role_grants.append(statement.strip())

    required_fragments = {
        "private_identity_helper": "create or replace function private.applyai_current_user_id()",
        "private_helper_lockdown": "revoke all on function private.applyai_current_user_id() from public",
        "private_helper_authenticated_execute": "grant execute on function private.applyai_current_user_id() to authenticated",
        "global_public_rls": "where schemaname = 'public'",
        "global_public_table_revoke": "revoke all privileges on all tables in schema public from anon, authenticated",
        "global_public_sequence_revoke": "revoke all privileges on all sequences in schema public from anon, authenticated",
        "global_public_function_revoke": "revoke execute on all functions in schema public from public, anon, authenticated",
        "future_table_grant_lockdown": "revoke all on tables from anon, authenticated",
        "future_sequence_grant_lockdown": "revoke all on sequences from anon, authenticated",
        "future_function_grant_lockdown": "revoke execute on functions from public, anon, authenticated",
        "users_rls": "alter table public.users enable row level security",
        "user_roles_rls": "alter table public.user_roles enable row level security",
        "resumes_rls": "alter table public.resumes enable row level security",
        "private_resumes_bucket": "values ('resumes', 'resumes', false)",
        "storage_select_policy": 'create policy "applyai resume objects select own"',
        "storage_insert_policy": 'create policy "applyai resume objects insert own"',
        "storage_update_policy": 'create policy "applyai resume objects update own"',
        "storage_delete_policy": 'create policy "applyai resume objects delete own"',
        "auth_uid_mapping": "where u.auth_user_id = (select auth.uid())",
    }
    normalized_sql = " ".join(sql.lower().split())
    missing_fragments = [
        name
        for name, fragment in required_fragments.items()
        if " ".join(fragment.lower().split()) not in normalized_sql
    ]

    failures: list[dict[str, object]] = []
    if unknown_public_references:
        failures.append(
            {
                "code": "POLICY_REFERENCES_UNKNOWN_PUBLIC_OBJECTS",
                "objects": unknown_public_references,
            }
        )
    if stale_expected_tables:
        failures.append(
            {"code": "EXPECTED_SENSITIVE_TABLES_MISSING_FROM_ORM", "tables": stale_expected_tables}
        )
    if missing_policy_coverage:
        failures.append(
            {"code": "SENSITIVE_TABLES_MISSING_POLICY_COVERAGE", "tables": missing_policy_coverage}
        )
    if direct_data_api_grants:
        failures.append(
            {
                "code": "PUBLIC_APPLICATION_TABLE_GRANTED_TO_BROWSER_ROLE",
                "statements": direct_data_api_grants,
            }
        )
    if dangerous_role_grants:
        failures.append(
            {"code": "ROLE_TABLE_MUTATION_GRANTED_TO_AUTHENTICATED", "statements": dangerous_role_grants}
        )
    if missing_fragments:
        failures.append(
            {"code": "REQUIRED_SECURITY_INVARIANTS_MISSING", "invariants": missing_fragments}
        )

    return {
        "orm_tables": sorted(tables),
        "public_references": sorted(refs),
        "sensitive_tables": sorted(SENSITIVE_TABLES),
        "unknown_public_references": unknown_public_references,
        "missing_policy_coverage": missing_policy_coverage,
        "direct_data_api_grants": direct_data_api_grants,
        "dangerous_role_grants": dangerous_role_grants,
        "missing_security_invariants": missing_fragments,
        "status": "PASS" if not failures else "BLOCKED",
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Supabase RLS/storage SQL against current ApplyAI ORM metadata."
    )
    parser.add_argument(
        "--policies",
        default=str(repository_root() / "supabase" / "policies.sql"),
    )
    parser.add_argument("--report")
    args = parser.parse_args()

    sql = Path(args.policies).read_text()
    report = validate_policy_sql(sql)
    output = json.dumps(report, indent=2)
    print(output)
    if args.report:
        path = Path(args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output + "\n")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
