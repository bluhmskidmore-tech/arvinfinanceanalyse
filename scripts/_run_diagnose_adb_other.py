"""Run diagnose_adb_liabilities_other.sql against a DuckDB file (read-only).

用法:
  python scripts/_run_diagnose_adb_other.py <moss.duckdb> [d_start] [d_end]

环境变量（可选）:
  MOSS_DUCKDB_PATH — 未传第一个参数时使用
  DIAGNOSE_D_START / DIAGNOSE_D_END — 覆盖 SQL 内默认日期（YYYY-MM-DD）
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "scripts" / "diagnose_adb_liabilities_other.sql"


def _inject_dates(sql: str, d_start: str, d_end: str) -> str:
    out = sql
    out, n1 = re.subn(
        r"date '\d{4}-\d{2}-\d{2}' AS d_start",
        f"date '{d_start}' AS d_start",
        out,
        count=1,
    )
    out, n2 = re.subn(
        r"date '\d{4}-\d{2}-\d{2}' AS d_end",
        f"date '{d_end}' AS d_end",
        out,
        count=1,
    )
    if n1 != 1 or n2 != 1:
        raise ValueError(f"日期替换失败 (d_start={n1}, d_end={n2})，请检查 diagnose_adb_liabilities_other.sql")
    return out


def main() -> None:
    db = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("MOSS_DUCKDB_PATH", "")
    if not db or not Path(db).exists():
        print("请提供库路径: python scripts/_run_diagnose_adb_other.py <moss.duckdb> [YYYY-MM-DD开始] [YYYY-MM-DD结束]", file=sys.stderr)
        print("或设置 MOSS_DUCKDB_PATH", file=sys.stderr)
        sys.exit(2)

    d_start = os.environ.get("DIAGNOSE_D_START") or (sys.argv[2] if len(sys.argv) > 2 else None)
    d_end = os.environ.get("DIAGNOSE_D_END") or (sys.argv[3] if len(sys.argv) > 3 else None)
    if not d_start:
        d_start = "2025-12-31"
    if not d_end:
        d_end = d_start

    raw_sql = SQL_PATH.read_text(encoding="utf-8")
    sql = _inject_dates(raw_sql, d_start, d_end)
    con = duckdb.connect(db, read_only=True)
    try:
        df = con.execute(sql).fetchdf()
        print(df.to_string(index=False))
    finally:
        con.close()


if __name__ == "__main__":
    main()
