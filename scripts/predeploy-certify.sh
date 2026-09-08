#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p artifacts/predeploy

echo "==> ApplyAI predeploy certification"
echo "    Vercel deployment: NOT PERFORMED — intentionally excluded from this phase."

python3 scripts/verify_full_functional_contract.py

echo "==> Running clean-room repository certification"
bash scripts/local-certify.sh

echo "==> Recording real-inventory gate boundary"
if [[ "${REQUIRE_REAL_INVENTORY:-1}" == "1" ]]; then
  if [[ -z "${REAL_INVENTORY_GATE_CMD:-}" ]]; then
    cat >&2 <<'EOF'
FAIL: REQUIRE_REAL_INVENTORY=1 but REAL_INVENTORY_GATE_CMD is not configured.

This gate is intentionally fail-closed. Set REAL_INVENTORY_GATE_CMD to the
persisted production certification command that proves:
  eligible_real_jobs >= 2_000_000
while excluding synthetic/demo/development/test/fixture/seed/benchmark/generated rows.

Do not point this variable at a benchmark or --allow-blocked command.
EOF
    exit 3
  fi

  echo "==> Running strict real-job production inventory certification"
  bash -lc "$REAL_INVENTORY_GATE_CMD"
else
  cat > artifacts/predeploy/real-inventory-gate.json <<EOF
{
  "status": "EXTERNAL_GATE_NOT_EXECUTED",
  "reason": "Repository-controlled CI mode; production inventory evidence is evaluated separately.",
  "required_real_jobs": 2000000,
  "synthetic_scale_may_satisfy_gate": false,
  "vercel_deployment": "NOT_PERFORMED_INTENTIONALLY_EXCLUDED"
}
EOF
  echo "INFO: strict 2M real-job gate not executed in repository-only CI mode."
fi

echo
echo "PASS: repo-controlled predeploy certification completed."
echo "Vercel deployment: NOT PERFORMED — intentionally excluded from this phase."
