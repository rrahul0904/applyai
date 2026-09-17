from __future__ import annotations

import argparse
import json
import sys

from app.core.database import SessionLocal
from app.core.operator_bootstrap import OperatorBootstrapError, bootstrap_operator_role


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Grant operator/admin access to an existing ApplyAI user that has already "
            "authenticated through Supabase Auth."
        )
    )
    parser.add_argument("--email", required=True, help="Exact email of the existing ApplyAI user")
    parser.add_argument(
        "--role",
        choices=("operator", "admin"),
        default="operator",
        help="Privileged role to grant (default: operator)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        with SessionLocal() as session:
            result = bootstrap_operator_role(
                session,
                email=args.email,
                role_name=args.role,
            )
    except OperatorBootstrapError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "ok": True,
                "user_id": result.user_id,
                "email": result.email,
                "role": result.role,
                "created_assignment": result.created_assignment,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
