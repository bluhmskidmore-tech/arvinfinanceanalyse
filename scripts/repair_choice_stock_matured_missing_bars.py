from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks.choice_stock_matured_bar_repair import (  # noqa: E402
    repair_choice_stock_matured_missing_bars,
)


def _workspace_path(path_value: str) -> Path:
    path = Path(path_value)
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview or apply the exact approved 2026-07/08 stock outcome input repair."
    )
    parser.add_argument("--duckdb-path", default="data/moss.duckdb")
    parser.add_argument("--bars-receipt", required=True)
    parser.add_argument("--suspension-receipt", required=True)
    parser.add_argument("--factor-receipt", required=True)
    parser.add_argument("--receipt-path", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--target-backup-path")
    args = parser.parse_args(argv)
    if args.apply and not args.expected_plan_sha256:
        parser.error("--apply requires --expected-plan-sha256 from a reviewed dry-run receipt")
    if args.apply and not args.target_backup_path:
        parser.error("--apply requires --target-backup-path")
    try:
        result = repair_choice_stock_matured_missing_bars(
            _workspace_path(args.duckdb_path),
            bars_receipt_path=_workspace_path(args.bars_receipt),
            suspension_receipt_path=_workspace_path(args.suspension_receipt),
            factor_receipt_path=_workspace_path(args.factor_receipt),
            receipt_path=_workspace_path(args.receipt_path),
            apply_changes=bool(args.apply),
            expected_plan_sha256=args.expected_plan_sha256,
            target_backup_path=(
                _workspace_path(args.target_backup_path)
                if args.target_backup_path
                else None
            ),
        )
    except Exception as exc:
        resolved_receipt = _workspace_path(args.receipt_path)
        try:
            persisted = json.loads(resolved_receipt.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            persisted = None
        result = (
            persisted
            if isinstance(persisted, dict) and persisted.get("status") == "failed"
            else {
                "schema": "choice_stock_matured_bar_repair/v1",
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": " ".join(str(exc).split())[:1000],
                "receipt_path": str(resolved_receipt),
                "commit_state": "check_task_receipt_or_target_before_retry",
            }
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") in {"dry_run", "completed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
