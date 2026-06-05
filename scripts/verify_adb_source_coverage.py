#!/usr/bin/env python3
"""
只读核对：区间内 ZQTZ/TYW 在 DuckDB 中的覆盖 vs ADB 服务实际加载的 bonds_df / ib_df。

与 backend/app/services/adb_analysis_service.py::_load_adb_raw_data 的表选择、WHERE 条件对齐；
并提示 formal 非空时 snapshot 不会被合并读入。

用法（仓库根目录）:
  python scripts/verify_adb_source_coverage.py --duckdb path/to/db.duckdb --start 2025-01-01 --end 2025-03-31

未传 --duckdb 时尝试环境变量 MOSS_DUCKDB_PATH。
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


def _count_band(conn, sql: str, start: date, end: date) -> tuple[int, int | None, str | None]:
    """返回 (行数, distinct_report_date 数, min..max 日期串)。"""
    cur = conn.execute(sql, [start, end])
    row = cur.fetchone()
    if row is None:
        return 0, None, None
    n_rows = int(row[0] or 0)
    n_dist = int(row[1]) if row[1] is not None else None
    span = str(row[2]) if len(row) > 2 and row[2] is not None else None
    return n_rows, n_dist, span


def main() -> int:
    p = argparse.ArgumentParser(description="ADB ZQTZ/TYW 源表覆盖核对（只读）")
    p.add_argument("--duckdb", default=os.environ.get("MOSS_DUCKDB_PATH", ""), help="DuckDB 文件路径，默认 MOSS_DUCKDB_PATH")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    args = p.parse_args()
    path = (args.duckdb or "").strip()
    if not path:
        print("错误: 请指定 --duckdb 或设置 MOSS_DUCKDB_PATH", file=sys.stderr)
        return 2
    if not Path(path).exists():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        return 2

    start, end = _parse_date(args.start), _parse_date(args.end)
    if start > end:
        start, end = end, start
    calendar_days = (end - start).days + 1

    import duckdb

    conn = duckdb.connect(path, read_only=True)
    try:
        print(f"DuckDB: {path}")
        print(f"区间: {start.isoformat()} .. {end.isoformat()}  （日历含首尾 {calendar_days} 天）\n")

        # --- 与 _load_adb_raw_data 一致的 SQL 统计 ---
        zqtz_formal_sql = """
            select
              count(*)::bigint,
              count(distinct cast(report_date as date))::bigint,
              min(cast(report_date as date))::varchar || ' .. ' || max(cast(report_date as date))::varchar
            from fact_formal_zqtz_balance_daily
            where cast(report_date as date) between ? and ?
              and currency_basis = 'CNY'
        """
        tyw_formal_sql = """
            select
              count(*)::bigint,
              count(distinct cast(report_date as date))::bigint,
              min(cast(report_date as date))::varchar || ' .. ' || max(cast(report_date as date))::varchar
            from fact_formal_tyw_balance_daily
            where cast(report_date as date) between ? and ?
              and currency_basis = 'CNY'
        """
        zqtz_snap_sql = """
            select
              count(*)::bigint,
              count(distinct cast(report_date as date))::bigint,
              min(cast(report_date as date))::varchar || ' .. ' || max(cast(report_date as date))::varchar
            from zqtz_bond_daily_snapshot
            where cast(report_date as date) between ? and ?
              and upper(trim(coalesce(currency_code, ''))) in ('CNY', 'CNX')
        """
        tyw_snap_sql = """
            select
              count(*)::bigint,
              count(distinct cast(report_date as date))::bigint,
              min(cast(report_date as date))::varchar || ' .. ' || max(cast(report_date as date))::varchar
            from tyw_interbank_daily_snapshot
            where cast(report_date as date) between ? and ?
              and upper(trim(coalesce(currency_code, ''))) in ('CNY', 'CNX')
        """

        has_zf = _table_exists(conn, "fact_formal_zqtz_balance_daily")
        has_tf = _table_exists(conn, "fact_formal_tyw_balance_daily")
        has_zs = _table_exists(conn, "zqtz_bond_daily_snapshot")
        has_ts = _table_exists(conn, "tyw_interbank_daily_snapshot")

        zf_rows = zf_dist = zs_rows = zs_dist = None
        tf_rows = tf_dist = ts_rows = ts_dist = None
        zf_span = zs_span = tf_span = ts_span = None

        if has_zf:
            zf_rows, zf_dist, zf_span = _count_band(conn, zqtz_formal_sql, start, end)
        if has_tf:
            tf_rows, tf_dist, tf_span = _count_band(conn, tyw_formal_sql, start, end)
        if has_zs:
            zs_rows, zs_dist, zs_span = _count_band(conn, zqtz_snap_sql, start, end)
        if has_ts:
            ts_rows, ts_dist, ts_span = _count_band(conn, tyw_snap_sql, start, end)

        print("【表存在】")
        print(f"  fact_formal_zqtz_balance_daily: {has_zf}")
        print(f"  fact_formal_tyw_balance_daily: {has_tf}")
        print(f"  zqtz_bond_daily_snapshot: {has_zs}")
        print(f"  tyw_interbank_daily_snapshot: {has_ts}")

        print("\n【区间内行数 / distinct(report_date) / 日期跨度】（原始 SQL，与 ADB 拉数 WHERE 一致）")
        if has_zf:
            print(f"  formal ZQTZ: rows={zf_rows} distinct_dates={zf_dist} span={zf_span}")
        if has_tf:
            print(f"  formal TYW: rows={tf_rows} distinct_dates={tf_dist} span={tf_span}")
        if has_zs:
            print(f"  snapshot ZQTZ: rows={zs_rows} distinct_dates={zs_dist} span={zs_span}")
        if has_ts:
            print(f"  snapshot TYW: rows={ts_rows} distinct_dates={ts_dist} span={ts_span}")

        print("\n【ADB 读数（与 _load_adb_raw_data 一致：仅 formal CNY；不读 snapshot）】")
        print(f"  ZQTZ: {'fact_formal_zqtz_balance_daily' if has_zf else '（无表，ADB 债券侧为空）'}")
        print(f"  TYW: {'fact_formal_tyw_balance_daily' if has_tf else '（无表，ADB 同业侧为空）'}")
        if has_zs and not has_zf:
            print("  提示: 仅有 zqtz_bond_daily_snapshot 时 ADB 仍不读快照；需创建/物化 formal 表。")
        if has_ts and not has_tf:
            print("  提示: 仅有 tyw_interbank_daily_snapshot 时 ADB 仍不读快照；需创建/物化 formal 表。")
    finally:
        conn.close()

    from backend.app.services.adb_analysis_service import _adb_distinct_snapshot_days, _load_adb_raw_data

    bonds_df, ib_df, _, _, adb_basis, _tables = _load_adb_raw_data(path, start, end)
    adb_union = _adb_distinct_snapshot_days(bonds_df, ib_df)
    print("\n【服务加载后的 DataFrame（含 position_scope 等 Python 过滤后）】")
    print(f"  bonds_df 行数: {len(bonds_df)}")
    print(f"  ib_df   行数: {len(ib_df)}")
    if not bonds_df.empty and "report_date" in bonds_df.columns:
        bd = bonds_df["report_date"].dt.normalize().dt.date
        print(f"  bonds distinct_dates: {bd.nunique()}  min={bd.min()} max={bd.max()}")
    if not ib_df.empty and "report_date" in ib_df.columns:
        idt = ib_df["report_date"].dt.normalize().dt.date
        print(f"  ib_df distinct_dates: {idt.nunique()}  min={idt.min()} max={idt.max()}")
    print(f"  ADB 分母（ZQTZ∪TYW distinct 日）: {adb_union}")
    print(f"  对比日历天数: {calendar_days}  （若 adb_union < calendar_days，无快照的日历日不会进分子）")
    print(f"  adb_denominator_basis（与 comparison 载荷）: {adb_basis}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
