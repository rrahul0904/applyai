from scripts.audit_provider_dependencies import is_runtime_path


def test_runtime_path_classification_covers_apps_api_and_workflows() -> None:
    assert is_runtime_path("apps/web/lib/auth/session.ts")
    assert is_runtime_path("services/api/app/core/auth.py")
    assert is_runtime_path(".github/workflows/deploy-vercel-applyai.yml")
    assert is_runtime_path("pnpm-lock.yaml")
    assert not is_runtime_path("docs/VERCEL_SUPABASE_MIGRATION_GAP_MATRIX.md")
