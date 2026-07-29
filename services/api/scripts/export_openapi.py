import json

from app.main import app


def main() -> None:
    print(json.dumps(app.openapi(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
