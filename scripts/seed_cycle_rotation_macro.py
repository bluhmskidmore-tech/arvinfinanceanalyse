#!/usr/bin/env python3
"""CLI wrapper for cycle-rotation macro fixture seeding (dev/test)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.app.tasks.cycle_rotation_macro_seed import materialize_cycle_rotation_macro_fixture


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Seed PMI / social-financing rows for cycle MacroScore (fixture only)."
    )
    parser.add_argument("--duckdb-path", required=True)
    parser.add_argument(
        "--fixture",
        default=str(_REPO_ROOT / "tests" / "fixtures" / "cycle_rotation_macro_monthly.json"),
    )
    parser.add_argument(
        "--force-fixture-overwrite",
        action="store_true",
        help="Overwrite existing rows for the same series/date with fixture values.",
    )
    args = parser.parse_args()
    payload = materialize_cycle_rotation_macro_fixture(
        duckdb_path=args.duckdb_path,
        fixture_path=Path(args.fixture),
        overwrite_existing=args.force_fixture_overwrite,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
