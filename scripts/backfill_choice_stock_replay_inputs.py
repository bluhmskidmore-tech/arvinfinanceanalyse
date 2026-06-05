from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb

from backend.app.services.livermore_candidate_history_service import (
    livermore_candidate_history_backtest_window_summary,
)
from backend.app.tasks.choice_stock_materialize import (
    load_choice_stock_materialization_coverage,
    materialize_choice_stock_inputs,
)


FIXABLE_REASON_CODES = {"missing_required_source_table", "missing_daily_limit_flags"}


def backfill_choice_stock_replay_inputs(
    *,
    duckdb_path: str | Path,
    max_dates: int | None = None,
    dates: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    resolved_path = _resolve_duckdb_path(duckdb_path)
    row_stats = load_replay_row_stats(duckdb_path=str(resolved_path))
    if dates:
        selected_dates = _normalize_dates(dates)
    else:
        summary = livermore_candidate_history_backtest_window_summary(
            duckdb_path=str(resolved_path),
            stock_code=None,
            snapshot_from=None,
            snapshot_to=None,
        )
        selected_dates = select_replay_input_backfill_dates(
            summary=summary,
            row_stats=row_stats,
            max_dates=max_dates,
        )

    if dry_run:
        return {
            "status": "dry_run",
            "duckdb_path": str(resolved_path),
            "selected_dates": selected_dates,
            "completed": [],
            "skipped": [],
            "failed": [],
        }

    completed: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []
    for as_of_date in selected_dates:
        coverage = load_choice_stock_materialization_coverage(
            duckdb_path=str(resolved_path),
            as_of_date=as_of_date,
        )
        if bool(getattr(coverage, "full_coverage", False)):
            skipped.append({"as_of_date": as_of_date, "reason": "coverage_ready"})
            continue
        try:
            payload = materialize_choice_stock_inputs(
                as_of_date=as_of_date,
                duckdb_path=str(resolved_path),
            )
        except Exception as exc:
            failed.append({"as_of_date": as_of_date, "error": _summarize_error(exc)})
            continue
        completed.append(
            {
                "as_of_date": as_of_date,
                "status": payload.get("status"),
                "row_count": payload.get("row_count"),
                "stock_code_count": payload.get("stock_code_count"),
                "source_version": payload.get("source_version"),
                "vendor_version": payload.get("vendor_version"),
            }
        )

    if failed and (completed or skipped):
        status = "partial"
    elif failed:
        status = "failed"
    elif completed or skipped:
        status = "completed"
    else:
        status = "noop"
    return {
        "status": status,
        "duckdb_path": str(resolved_path),
        "selected_dates": selected_dates,
        "completed": completed,
        "skipped": skipped,
        "failed": failed,
    }


def select_replay_input_backfill_dates(
    *,
    summary: dict[str, Any],
    row_stats: dict[str, dict[str, int]],
    max_dates: int | None = None,
) -> list[str]:
    candidates: set[str] = set()
    for reason in summary.get("date_reasons", []):
        if not isinstance(reason, dict):
            continue
        if str(reason.get("status") or "").strip() != "unsupported":
            continue
        if str(reason.get("reason_code") or "").strip() not in FIXABLE_REASON_CODES:
            continue
        trade_date = str(reason.get("trade_date") or "").strip()[:10]
        if trade_date:
            candidates.add(trade_date)

    ordered = sorted(
        candidates,
        key=lambda trade_date: (
            -int(row_stats.get(trade_date, {}).get("non_proxy_rows", 0)),
            -int(row_stats.get(trade_date, {}).get("row_count", 0)),
            trade_date,
        ),
    )
    if max_dates is not None:
        return ordered[: max(0, int(max_dates))]
    return ordered


def load_replay_row_stats(*, duckdb_path: str | Path) -> dict[str, dict[str, int]]:
    path = Path(duckdb_path)
    if not path.exists():
        return {}
    conn = duckdb.connect(str(path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        if "livermore_candidate_history" not in tables:
            return {}
        rows = conn.execute(
            """
            select
              snapshot_as_of_date,
              count(*) as row_count,
              sum(
                case
                  when signal_kind = 'theme_breakout'
                   and coalesce(theme_source_kind, '') = 'proxy'
                  then 1 else 0
                end
              ) as proxy_theme_rows,
              sum(
                case
                  when signal_kind != 'theme_breakout'
                    or coalesce(theme_source_kind, '') != 'proxy'
                  then 1 else 0
                end
              ) as non_proxy_rows
            from livermore_candidate_history
            group by snapshot_as_of_date
            """
        ).fetchall()
    finally:
        conn.close()
    return {
        str(trade_date)[:10]: {
            "row_count": int(row_count or 0),
            "proxy_theme_rows": int(proxy_theme_rows or 0),
            "non_proxy_rows": int(non_proxy_rows or 0),
        }
        for trade_date, row_count, proxy_theme_rows, non_proxy_rows in rows
        if str(trade_date or "").strip()
    }


def _resolve_duckdb_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    return path


def _normalize_dates(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()[:10]
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def _summarize_error(exc: Exception) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else exc.__class__.__name__


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Choice stock inputs needed by Livermore replay dates.")
    parser.add_argument("--duckdb-path", default="data/moss.duckdb")
    parser.add_argument("--max-dates", type=int, default=None)
    parser.add_argument("--dates", default="", help="Comma-separated explicit YYYY-MM-DD dates.")
    parser.add_argument("--dry-run", action="store_true", help="Select dates without writing Choice stock inputs.")
    args = parser.parse_args()

    explicit_dates = [item.strip() for item in args.dates.split(",") if item.strip()]
    try:
        result = backfill_choice_stock_replay_inputs(
            duckdb_path=args.duckdb_path,
            max_dates=args.max_dates,
            dates=explicit_dates or None,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
