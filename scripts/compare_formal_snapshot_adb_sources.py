#!/usr/bin/env python3
"""
只读对比：同一区间内 ZQTZ / TYW 的 formal 事实表 vs 快照表（各表独立 SQL 的 WHERE 与 ADB 读数分支对齐；
若库中已存在 formal 表，ADB 服务侧只读 formal CNY，不回退 snapshot）。

按 report_date 对齐：每日行数、金额合计；再输出全局汇总与「有差异的日期」列表。

用法:
  python scripts/compare_formal_snapshot_adb_sources.py --duckdb path/to/moss.duckdb --start 2025-01-01 --end 2025-03-31
  python scripts/compare_formal_snapshot_adb_sources.py --start 2025-01-01 --end 2025-03-31
    （未指定 --duckdb 时使用 MOSS_DUCKDB_PATH；再缺省则 data/moss.duckdb 相对仓库根）
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "select 1 from information_schema.tables where table_name = ? limit 1",
        [name],
    ).fetchone()
    return row is not None


def _resolve_duckdb(arg: str) -> Path:
    p = (arg or "").strip()
    if p:
        return Path(p)
    env = (os.environ.get("MOSS_DUCKDB_PATH") or "").strip()
    if env:
        return Path(env)
    return (ROOT / "data" / "moss.duckdb").resolve()


def _daily_diff_sql(
    *,
    formal_table: str,
    formal_amount: str,
    formal_currency: str,
    formal_curr_val: str,
    snap_table: str,
    snap_amount: str,
    snap_currency_sql: str,
) -> str:
    """snap_currency_sql 为 snapshot WHERE 里对 currency 的条件片段（已含 and）。"""
    return f"""
WITH f AS (
  SELECT cast(report_date as date) AS d,
         count(*)::bigint AS n,
         sum(cast({formal_amount} as double)) AS s
  FROM {formal_table}
  WHERE cast(report_date as date) BETWEEN ? AND ?
    AND {formal_currency} = '{formal_curr_val}'
  GROUP BY 1
),
s AS (
  SELECT cast(report_date as date) AS d,
         count(*)::bigint AS n,
         sum(cast({snap_amount} as double)) AS s
  FROM {snap_table}
  WHERE cast(report_date as date) BETWEEN ? AND ?
    {snap_currency_sql}
  GROUP BY 1
)
SELECT
  coalesce(f.d, s.d) AS d,
  f.n AS formal_n,
  s.n AS snap_n,
  f.s AS formal_sum,
  s.s AS snap_sum,
  (coalesce(f.n, 0) - coalesce(s.n, 0))::bigint AS dn,
  (coalesce(f.s, 0) - coalesce(s.s, 0)) AS ds
FROM f
FULL OUTER JOIN s ON f.d = s.d
ORDER BY 1
"""


def _run_compare(conn, label: str, sql: str, start: date, end: date, *, sum_tol: float) -> None:
    rows = conn.execute(sql, [start, end, start, end]).fetchall()
    diff_days = []
    formal_n_tot = snap_n_tot = 0
    formal_s_tot = snap_s_tot = 0.0
    for d, fn, sn, fs, ss, dn, ds in rows:
        fn = int(fn or 0)
        sn = int(sn or 0)
        fs = float(fs or 0)
        ss = float(ss or 0)
        formal_n_tot += fn
        snap_n_tot += sn
        formal_s_tot += fs
        snap_s_tot += ss
        if dn != 0 or abs(ds) > sum_tol:
            diff_days.append((str(d), fn, sn, dn, fs, ss, ds))

    print(f"\n======== {label} ========")
    print(f"  区间内按日合并后: formal 行数合计={formal_n_tot} snapshot 行数合计={snap_n_tot} 差(formal-snap)={formal_n_tot - snap_n_tot}")
    print(f"  金额合计(元): formal={formal_s_tot:.2f} snapshot={snap_s_tot:.2f} 差={formal_s_tot - snap_s_tot:.2f}")
    if not diff_days:
        print("  按日: 行数与金额合计与 snapshot 完全一致（在容差内）。")
        return
    print(f"  按日有差异的日期数: {len(diff_days)}（仅列前 30 行，其余请缩小区间或导出自行分析）")
    print(f"  {'date':<12} {'f_n':>8} {'s_n':>8} {'dn':>8} {'f_sum(亿)':>14} {'s_sum(亿)':>14} {'d_sum(亿)':>12}")
    yi = 1e8
    for tup in diff_days[:30]:
        d, fn, sn, dn, fs, ss, ds = tup
        print(f"  {d:<12} {fn:>8} {sn:>8} {dn:>8} {fs/yi:>14.4f} {ss/yi:>14.4f} {ds/yi:>12.4f}")
    if len(diff_days) > 30:
        print(f"  ... 另有 {len(diff_days) - 30} 个有差异的日期未显示")


def main() -> int:
    p = argparse.ArgumentParser(description="Formal vs Snapshot（ZQTZ/TYW）只读对比")
    p.add_argument("--duckdb", default="", help="DuckDB 路径；默认 MOSS_DUCKDB_PATH 或 data/moss.duckdb")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument(
        "--sum-tol",
        type=float,
        default=1e-3,
        help="每日金额合计视为相同的容差（元），默认 1e-3",
    )
    args = p.parse_args()

    db_path = _resolve_duckdb(args.duckdb)
    if not db_path.exists():
        print(f"错误: 找不到 DuckDB: {db_path}", file=sys.stderr)
        return 2

    start, end = _parse_date(args.start), _parse_date(args.end)
    if start > end:
        start, end = end, start

    import duckdb

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        print(f"DuckDB: {db_path}")
        print(f"区间: {start} .. {end}")

        need = (
            "fact_formal_zqtz_balance_daily",
            "zqtz_bond_daily_snapshot",
            "fact_formal_tyw_balance_daily",
            "tyw_interbank_daily_snapshot",
        )
        missing = [t for t in need if not _table_exists(conn, t)]
        if missing:
            print(f"错误: 缺少表: {missing}", file=sys.stderr)
            return 2

        zqtz_sql = _daily_diff_sql(
            formal_table="fact_formal_zqtz_balance_daily",
            formal_amount="market_value_amount",
            formal_currency="currency_basis",
            formal_curr_val="CNY",
            snap_table="zqtz_bond_daily_snapshot",
            snap_amount="market_value_native",
            snap_currency_sql="AND upper(trim(coalesce(currency_code, ''))) IN ('CNY', 'CNX')",
        )
        tyw_sql = _daily_diff_sql(
            formal_table="fact_formal_tyw_balance_daily",
            formal_amount="principal_amount",
            formal_currency="currency_basis",
            formal_curr_val="CNY",
            snap_table="tyw_interbank_daily_snapshot",
            snap_amount="principal_native",
            snap_currency_sql="AND upper(trim(coalesce(currency_code, ''))) IN ('CNY', 'CNX')",
        )

        _run_compare(conn, "ZQTZ（formal CNY vs snapshot CNY/CNX）", zqtz_sql, start, end, sum_tol=args.sum_tol)
        _run_compare(conn, "TYW（formal CNY vs snapshot CNY/CNX）", tyw_sql, start, end, sum_tol=args.sum_tol)

        print(
            "\n说明: 与 ADB 一致，formal 非空时界面用 formal；本脚本只做「同区间两套表」对照，"
            "不包含 bonds_df 的 position_scope Python 过滤。"
        )
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
