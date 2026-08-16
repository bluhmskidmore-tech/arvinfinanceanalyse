from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks.livermore_candidate_history_materialize import (  # noqa: E402
    repair_livermore_candidate_execution_gaps,
)


def _resolve_workspace_path(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()



def _validate_signal_kind(signal_kind: str) -> str:
    normalized_signal_kind = signal_kind.strip()
    if not normalized_signal_kind:
        raise ValueError("signal_kind cannot be blank.")
    if normalized_signal_kind != "stock_candidate":
        raise ValueError("execution-gap repair only supports signal_kind='stock_candidate'.")
    return normalized_signal_kind

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview or repair exact logical-key gaps in Livermore execution history."
    )
    parser.add_argument("--duckdb-path", default="data/moss.duckdb", help="Target DuckDB file path.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Read-only preview (also the default when no mode is specified).",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Apply the repair; requires an independent byte-identical backup.",
    )
    parser.add_argument(
        "--target-backup-path",
        default=None,
        help="Independent byte-identical backup required for a live repair.",
    )
    parser.add_argument(
        "--signal-kind",
        default="stock_candidate",
        help="Execution-history signal kind to inspect (default: stock_candidate).",
    )
    args = parser.parse_args(argv)

    try:
        signal_kind = _validate_signal_kind(args.signal_kind)
    except Exception as exc:
        payload = {
            "status": "partial",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    duckdb_path = _resolve_workspace_path(args.duckdb_path)
    target_backup_path = (
        str(_resolve_workspace_path(args.target_backup_path))
        if args.target_backup_path
        else None
    )
    try:
        payload = repair_livermore_candidate_execution_gaps(
            str(duckdb_path),
            dry_run=not bool(args.apply),
            target_backup_path=target_backup_path,
            signal_kind=signal_kind,
        )
    except Exception as exc:
        payload = {
            "status": "partial",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
