import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402


def main() -> None:
    print(json.dumps(app.openapi(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
