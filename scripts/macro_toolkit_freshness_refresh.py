"""Operator CLI for macro-toolkit price/commodity freshness refresh."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks.macro_toolkit_freshness_refresh import (  # noqa: E402
    refresh_macro_toolkit_freshness,
    refresh_macro_toolkit_freshness_actor,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true", help="Plan steps without vendor writes.")
    modes.add_argument("--enqueue", action="store_true", help="Enqueue the canonical Dramatiq actor.")
    modes.add_argument("--run-once", action="store_true", help="Run synchronously in the current environment.")
    parser.add_argument(
        "--skip-cffex",
        action="store_true",
        help="Skip CFFEX member-rank step (still runs commodity + public headlines).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    include_cffex = not args.skip_cffex
    if args.dry_run:
        result = refresh_macro_toolkit_freshness(dry_run=True, include_cffex=include_cffex)
    elif args.enqueue:
        message = refresh_macro_toolkit_freshness_actor.send(include_cffex=include_cffex)
        result = {
            "status": "queued",
            "actor": refresh_macro_toolkit_freshness_actor.actor_name,
            "message_id": message.message_id,
        }
    else:
        result = refresh_macro_toolkit_freshness_actor.fn(include_cffex=include_cffex)
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result.get("status") in {"success", "dry_run", "queued"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
