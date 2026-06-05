"""
一次性诊断：同日 ZQTZ 正式余额事实表 CNY 合计 vs 债券分析事实表市值合计。

用法:
  cd F:/MOSS-V3
  python -m backend.scripts.diagnose_balance_calibration --report-date 2025-12-31
  python -m backend.scripts.diagnose_balance_calibration --duckdb path/to/moss.duckdb

说明:
  - 不修改数据；仅打印对比结果。
  - 若差额绝对值 > 0.01，打印 WARNING 与可能原因提示。
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

import duckdb

ZQTZ_FACT = "fact_formal_zqtz_balance_daily"
BOND_FACT = "fact_formal_bond_analytics_daily"


def _resolve_duckdb_path(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    try:
        from backend.app.governance.settings import get_settings

        return Path(get_settings().duckdb_path)
    except Exception:
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "data" / "moss.duckdb"


def _table_exists(conn: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = conn.execute(
        """
        select count(*) from information_schema.tables
        where table_schema = 'main' and table_name = ?
        """,
        [name],
    ).fetchone()
    return bool(row and row[0])


def _sum_zqtz_cny(conn: duckdb.DuckDBPyConnection, report_date: str) -> Decimal:
    row = conn.execute(
        f"""
        select coalesce(sum(market_value_amount), 0)
        from {ZQTZ_FACT}
        where cast(report_date as varchar) = ?
          and currency_basis = 'CNY'
        """,
        [report_date],
    ).fetchone()
    if row is None or row[0] is None:
        return Decimal("0")
    return Decimal(str(row[0]))


def _sum_bond_analytics_mv(conn: duckdb.DuckDBPyConnection, report_date: str) -> Decimal:
    row = conn.execute(
        f"""
        select coalesce(sum(market_value), 0)
        from {BOND_FACT}
        where cast(report_date as varchar) = ?
        """,
        [report_date],
    ).fetchone()
    if row is None or row[0] is None:
        return Decimal("0")
    return Decimal(str(row[0]))


def _latest_shared_date(conn: duckdb.DuckDBPyConnection) -> str | None:
    if not _table_exists(conn, ZQTZ_FACT) or not _table_exists(conn, BOND_FACT):
        return None
    row = conn.execute(
        f"""
        select max(d) from (
          select cast(report_date as varchar) as d from {ZQTZ_FACT}
          intersect
          select cast(report_date as varchar) as d from {BOND_FACT}
        )
        """
    ).fetchone()
    if not row or row[0] is None:
        return None
    return str(row[0])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Compare ZQTZ balance vs bond analytics fact totals.")
    parser.add_argument("--report-date", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--duckdb", type=str, default=None, help="Path to moss.duckdb")
    args = parser.parse_args(argv)

    path = _resolve_duckdb_path(args.duckdb)
    if not path.is_file():
        print(f"ERROR: DuckDB file not found: {path}")
        return 2

    conn = duckdb.connect(str(path), read_only=True)
    try:
        if not _table_exists(conn, ZQTZ_FACT):
            print(f"ERROR: table missing: {ZQTZ_FACT}")
            return 3
        if not _table_exists(conn, BOND_FACT):
            print(f"ERROR: table missing: {BOND_FACT}")
            return 3

        report_date = args.report_date
        if not report_date:
            report_date = _latest_shared_date(conn)
            if not report_date:
                print("ERROR: no shared report_date in both fact tables; pass --report-date explicitly.")
                return 4
            print(f"(auto) using latest shared report_date: {report_date}")

        z = _sum_zqtz_cny(conn, report_date)
        b = _sum_bond_analytics_mv(conn, report_date)
        diff = z - b
        print(f"report_date: {report_date}")
        print(f"SUM({ZQTZ_FACT}.market_value_amount) [currency_basis=CNY]: {z}")
        print(f"SUM({BOND_FACT}.market_value): {b}")
        print(f"difference (zqtz_cny - bond_analytics): {diff}")

        threshold = Decimal("0.01")
        if abs(diff) > threshold:
            print("\nWARNING: |difference| > 0.01 — totals are not aligned for this diagnostic slice.")
            print("Possible reasons (non-exhaustive):")
            print("  - Scope: zqtz formal balance rows vs bond analytics row filters (e.g. issuance-like, invest type).")
            print("  - TYW: balance-analysis page can include interbank (TYW); bond dashboard facts are zqtz-only.")
            print("  - FX: CNY basis conversion path differs between project_zqtz_formal_balance_row vs bond analytics engine.")
            return 1
        print("\nOK: |difference| <= 0.01 for this slice.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
