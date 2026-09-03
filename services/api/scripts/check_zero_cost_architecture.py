"""Static release guard for accidental paid-path regressions."""

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    settings = Settings(
        app_env="production",
        deployment_profile="lean",
        database_url="postgresql://user:pass@free.example.test/applyai",
        auth_provider="clerk",
        clerk_issuer="https://clerk.example.test",
        clerk_jwks_url="https://clerk.example.test/.well-known/jwks.json",
        object_storage_provider="postgres",
        task_queue_provider="postgres",
        request_triggered_tasks_enabled=True,
        ai_provider="deterministic",
        billing_enabled=False,
        web_origin="https://applyai-preview.vercel.app",
    )
    assert settings.billing_enabled is False
    assert settings.ai_provider == "deterministic"
    assert settings.object_storage_hard_limit_bytes == 250 * 1024 * 1024
    assert settings.request_triggered_tasks_enabled is True

    workflow = (ROOT / ".github/workflows/zero-cost-maintenance.yml").read_text()
    assert "runs-on: ubuntu-24.04" in workflow
    assert "timeout-minutes: 10" in workflow
    assert "upload-artifact" not in workflow
    assert "OBJECT_STORAGE_PROVIDER: postgres" in workflow

    shell = (ROOT / "apps/web/components/candidate-shell.tsx").read_text()
    billing = (ROOT / "apps/web/components/platform-workspaces.tsx").read_text()
    assert 'href="/billing"' not in shell
    assert "Upgrade to Pro" not in billing
    assert "Team plan" not in billing

    print("PASS ApplyAI zero-cost architecture guard")


if __name__ == "__main__":
    main()
