from __future__ import annotations

import json

from app.core.database import SessionLocal
from app.jobs.source_capabilities import seed_source_capabilities


def main() -> None:
    with SessionLocal() as session:
        records = seed_source_capabilities(session)
        session.commit()
        result = {
            "providers": len(records),
            "implemented": sum(1 for item in records if item.implementation_status == "SOURCE_IMPLEMENTED"),
            "partnership_required": sum(
                1 for item in records if item.implementation_status == "PARTNERSHIP_REQUIRED"
            ),
        }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
