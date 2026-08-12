# MANUAL WRITE SCRIPT：默认 dry-run 只读；--execute 时 read_only=False
# 直删 livermore_candidate_execution_history 重复行（人工维护窗口执行）。
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
TABLE_NAME = "livermore_candidate_execution_history"
KEY_COLUMNS = ("signal_date", "stock_code", "signal_kind")
KEEP_RULE = "first_physical_row"
REQUIRED_COLUMNS = {
    *KEY_COLUMNS,
    "candidate_rank",
    "entry_date",
    "formula_version",
    "run_id",
}


def _resolve_workspace_path(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _table_columns(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {
        str(row[1]).lower()
        for row in conn.execute(f"pragma table_info('{TABLE_NAME}')").fetchall()
    }


def _validate_target(conn: duckdb.DuckDBPyConnection) -> None:
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    if TABLE_NAME not in tables:
        raise ValueError(f"Table not found: {TABLE_NAME}")
    missing = sorted(REQUIRED_COLUMNS - _table_columns(conn))
    if missing:
        raise ValueError(f"{TABLE_NAME} is missing required columns: {', '.join(missing)}")


def _scan_summary(conn: duckdb.DuckDBPyConnection) -> dict[str, int]:
    physical_row_count = int(conn.execute(f"select count(*) from {TABLE_NAME}").fetchone()[0])
    logical_key_count = int(
        conn.execute(
            f"""
            select count(*)
            from (
              select distinct {", ".join(KEY_COLUMNS)}
              from {TABLE_NAME}
            )
            """
        ).fetchone()[0]
    )
    duplicate_key_count, duplicate_physical_row_count, excess_row_count = conn.execute(
        f"""
        with duplicate_keys as (
          select {", ".join(KEY_COLUMNS)}, count(*) as physical_count
          from {TABLE_NAME}
          group by {", ".join(KEY_COLUMNS)}
          having count(*) > 1
        )
        select count(*)::integer,
               coalesce(sum(physical_count), 0)::integer,
               coalesce(sum(physical_count - 1), 0)::integer
        from duplicate_keys
        """
    ).fetchone()
    return {
        "physical_row_count": physical_row_count,
        "logical_key_count": logical_key_count,
        "duplicate_key_count": int(duplicate_key_count),
        "duplicate_physical_row_count": int(duplicate_physical_row_count),
        "excess_row_count": int(excess_row_count),
    }


def _dedupe_plan(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""
        with ranked as (
          select rowid as physical_rowid,
                 {", ".join(KEY_COLUMNS)},
                 candidate_rank,
                 entry_date,
                 formula_version,
                 run_id,
                 row_number() over (
                   partition by {", ".join(KEY_COLUMNS)}
                   order by rowid
                 ) as keep_rank,
                 count(*) over (
                   partition by {", ".join(KEY_COLUMNS)}
                 ) as physical_count
          from {TABLE_NAME}
        )
        select physical_rowid,
               {", ".join(KEY_COLUMNS)},
               candidate_rank,
               entry_date,
               formula_version,
               run_id,
               keep_rank,
               physical_count
        from ranked
        where physical_count > 1
        order by signal_date, stock_code, signal_kind, keep_rank
        """
    ).fetchall()

    plans_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        (
            physical_rowid,
            signal_date,
            stock_code,
            signal_kind,
            candidate_rank,
            entry_date,
            formula_version,
            run_id,
            keep_rank,
            physical_count,
        ) = row
        key = (str(signal_date), str(stock_code), str(signal_kind))
        plan = plans_by_key.setdefault(
            key,
            {
                "key": dict(zip(KEY_COLUMNS, key, strict=True)),
                "physical_row_count": int(physical_count),
                "keep": None,
                "delete": [],
            },
        )
        row_ref = {
            "physical_rowid": int(physical_rowid),
            "run_id": run_id,
            "formula_version": formula_version,
            "candidate_rank": candidate_rank,
            "entry_date": entry_date,
        }
        if int(keep_rank) == 1:
            plan["keep"] = row_ref
        else:
            plan["delete"].append(row_ref)
    return list(plans_by_key.values())


def inspect_or_execute(duckdb_path: Path, *, execute: bool) -> dict[str, Any]:
    if not duckdb_path.is_file():
        raise FileNotFoundError(f"DuckDB file not found: {duckdb_path}")

    conn = duckdb.connect(str(duckdb_path), read_only=not execute)
    transaction_started = False
    try:
        _validate_target(conn)
        if execute:
            conn.execute("begin transaction")
            transaction_started = True

        before = _scan_summary(conn)
        plans = _dedupe_plan(conn)
        delete_rowids = [
            int(row["physical_rowid"])
            for plan in plans
            for row in plan["delete"]
        ]

        after = before
        if execute and delete_rowids:
            conn.executemany(
                f"delete from {TABLE_NAME} where rowid = ?",
                [(rowid,) for rowid in delete_rowids],
            )
            after = _scan_summary(conn)
            if after["duplicate_key_count"] != 0:
                raise RuntimeError("Duplicate execution-history keys remain after planned deletion.")

        if execute:
            conn.execute("commit")
            transaction_started = False

        return {
            "status": "ok",
            "mode": "execute" if execute else "dry_run",
            "duckdb_path": str(duckdb_path),
            "table": TABLE_NAME,
            "key_columns": list(KEY_COLUMNS),
            "keep_rule": KEEP_RULE,
            "keep_rule_reason": (
                "Keep the lowest DuckDB rowid within each logical key. The current duplicates share "
                "one run_id and the table has no sortable insertion timestamp, so retaining the first "
                "physical row is deterministic and minimizes mutation."
            ),
            "before": before,
            "planned_delete_row_count": len(delete_rowids),
            "deleted_row_count": len(delete_rowids) if execute else 0,
            "after": after if execute else None,
            "plans": plans,
        }
    except Exception:
        if transaction_started:
            conn.execute("rollback")
        raise
    finally:
        conn.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preview duplicate Livermore execution-history keys; pass --execute to delete all "
            "but the first physical row per key."
        )
    )
    parser.add_argument("--duckdb-path", default="data/moss.duckdb", help="Target DuckDB file path.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply the displayed deletion plan transactionally. Omit for read-only dry-run.",
    )
    args = parser.parse_args(argv)

    try:
        payload = inspect_or_execute(
            _resolve_workspace_path(args.duckdb_path),
            execute=bool(args.execute),
        )
    except Exception as exc:
        payload = {
            "status": "error",
            "mode": "execute" if args.execute else "dry_run",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
