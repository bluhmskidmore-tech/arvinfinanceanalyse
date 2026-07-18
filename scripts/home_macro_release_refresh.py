"""Operator CLI for the homepage macro release source refresh."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks.home_macro_release_refresh import (  # noqa: E402
    refresh_home_macro_release_sources,
    refresh_home_macro_release_sources_actor,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true", help="Plan without vendor fetches or writes.")
    modes.add_argument("--enqueue", action="store_true", help="Enqueue the canonical Dramatiq actor.")
    modes.add_argument("--run-once", action="store_true", help="Run synchronously in the current environment.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.dry_run:
        result = refresh_home_macro_release_sources(dry_run=True)
    elif args.enqueue:
        message = refresh_home_macro_release_sources_actor.send()
        result = {
            "status": "queued",
            "actor": refresh_home_macro_release_sources_actor.actor_name,
            "message_id": message.message_id,
        }
    else:
        result = refresh_home_macro_release_sources_actor.fn()
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result.get("status") in {"success", "dry_run", "queued"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
