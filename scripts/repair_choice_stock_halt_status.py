from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks.choice_stock_halt_status_repair import (  # noqa: E402
    repair_choice_stock_halt_status,
)


def _workspace_path(value: str) -> Path:
    path = Path(value)
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview the ten disclosed 688432.SH halt statuses; apply only a reviewed plan with an identical backup."
    )
    parser.add_argument("--duckdb-path", default="data/moss.duckdb")
    parser.add_argument("--announcement-path", required=True)
    parser.add_argument("--expected-announcement-sha256", required=True)
    parser.add_argument("--receipt-path", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--target-backup-path")
    args = parser.parse_args(argv)
    if args.apply and (not args.expected_plan_sha256 or not args.target_backup_path):
        parser.error("--apply requires --expected-plan-sha256 and --target-backup-path")
    try:
        result = repair_choice_stock_halt_status(
            _workspace_path(args.duckdb_path),
            announcement_path=_workspace_path(args.announcement_path),
            expected_announcement_sha256=args.expected_announcement_sha256,
            receipt_path=_workspace_path(args.receipt_path),
            apply_changes=args.apply,
            expected_plan_sha256=args.expected_plan_sha256,
            target_backup_path=_workspace_path(args.target_backup_path)
            if args.target_backup_path
            else None,
        )
    except Exception as exc:
        # Never report a stale receipt from an earlier run as this invocation's outcome.
        result = {
            "schema": "choice_stock_halt_status_repair/v1",
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "commit_state": "check_current_task_receipt_before_retry",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["status"] in {"dry_run", "completed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
