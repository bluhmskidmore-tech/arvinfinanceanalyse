# MANUAL WRITE SCRIPT：默认 dry-run 只读；--execute 时 read_only=False
# 直删 livermore_candidate_execution_history 重复行（人工维护窗口执行）。
# 保留规则直接复用写入侧 _execution_history_row_priority（避免两套口径漂移）。
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.tasks.livermore_candidate_history_materialize import (  # noqa: E402
    _execution_history_row_priority,
)

TABLE_NAME = "livermore_candidate_execution_history"
KEY_COLUMNS = ("signal_date", "stock_code", "signal_kind")
KEEP_RULE = "write_side_execution_history_row_priority"
KEEP_RULE_REASON = (
    "Keep the row that maximizes the write-side _execution_history_row_priority "
    "(backend.app.tasks.livermore_candidate_history_materialize): populated *_net_adj "
    "return count desc, then candidate_rank asc, then run_id lexicographically desc; "
    "remaining ties keep the lowest physical rowid. Importing the writer's function "
    "keeps this cleanup aligned with governed insert-time deduplication."
)
_NET_ADJ_RETURN_COLUMNS = (
    "return_1d_net_adj",
    "return_5d_net_adj",
    "return_10d_net_adj",
    "return_20d_net_adj",
)
REQUIRED_COLUMNS = {
    *KEY_COLUMNS,
    *_NET_ADJ_RETURN_COLUMNS,
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
    record_columns = (
        "physical_rowid",
        *KEY_COLUMNS,
        "candidate_rank",
        "entry_date",
        "formula_version",
        "run_id",
        *_NET_ADJ_RETURN_COLUMNS,
        "physical_count",
    )
    rows = conn.execute(
        f"""
        with counted as (
          select rowid as physical_rowid,
                 {", ".join(KEY_COLUMNS)},
                 candidate_rank,
                 entry_date,
                 formula_version,
                 run_id,
                 {", ".join(_NET_ADJ_RETURN_COLUMNS)},
                 count(*) over (
                   partition by {", ".join(KEY_COLUMNS)}
                 ) as physical_count
          from {TABLE_NAME}
        )
        select {", ".join(record_columns)}
        from counted
        where physical_count > 1
        order by signal_date, stock_code, signal_kind, physical_rowid
        """
    ).fetchall()

    records_by_key: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        record = dict(zip(record_columns, row, strict=True))
        key = (
            str(record["signal_date"]),
            str(record["stock_code"]),
            str(record["signal_kind"]),
        )
        records_by_key.setdefault(key, []).append(record)

    plans: list[dict[str, Any]] = []
    for key, records in records_by_key.items():
        # 与写入侧 _deduplicate_execution_history_rows 同口径取最大 priority；
        # priority 完全相同的行退回保留最小 rowid（确定性平手规则）。
        keep_record = max(
            records,
            key=lambda record: (
                _execution_history_row_priority(record),
                -int(record["physical_rowid"]),
            ),
        )
        plans.append(
            {
                "key": dict(zip(KEY_COLUMNS, key, strict=True)),
                "physical_row_count": int(records[0]["physical_count"]),
                "keep": _row_ref(keep_record),
                "delete": [
                    _row_ref(record)
                    for record in records
                    if record["physical_rowid"] != keep_record["physical_rowid"]
                ],
            }
        )
    return plans


def _row_ref(record: dict[str, Any]) -> dict[str, Any]:
    """dry-run/execute 输出的行引用：包含保留规则三个排序键，便于人工核对选择依据。"""
    return {
        "physical_rowid": int(record["physical_rowid"]),
        "run_id": record["run_id"],
        "formula_version": record["formula_version"],
        "candidate_rank": record["candidate_rank"],
        "entry_date": record["entry_date"],
        "populated_net_adj_return_count": sum(
            record[column] is not None for column in _NET_ADJ_RETURN_COLUMNS
        ),
    }


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
            "keep_rule_reason": KEEP_RULE_REASON,
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
            "but the highest write-side-priority row per key (populated *_net_adj return count, "
            "candidate_rank, run_id; ties keep the first physical row)."
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
