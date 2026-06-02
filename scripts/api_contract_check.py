from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local API contract tooling entry points for FastAPI OpenAPI checks."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export-openapi",
        help="Export the FastAPI OpenAPI document to stdout or a file.",
    )
    export_parser.add_argument(
        "--output",
        default="-",
        help="Output path, or '-' for stdout.",
    )

    subparsers.add_parser(
        "schemathesis-command",
        help="Print the recommended local Schemathesis smoke command.",
    )
    return parser


def _export_openapi(output: str) -> int:
    from backend.app.main import app

    payload = app.openapi()
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    if output == "-":
        print(serialized)
        return 0

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialized + "\n", encoding="utf-8")
    return 0


def _print_schemathesis_command() -> int:
    print(
        "schemathesis run --url=http://127.0.0.1:8000/openapi.json "
        "--app=backend.app.main:app /openapi.json"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "export-openapi":
        return _export_openapi(args.output)
    if args.command == "schemathesis-command":
        return _print_schemathesis_command()
    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
