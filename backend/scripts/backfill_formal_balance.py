"""
批量物化脚本 — 将快照表中所有日期批量物化到 fact_formal 表。

用法:
  cd f:\MOSS-V3
  python -m backend.scripts.backfill_formal_balance

功能:
  1. 扫描 zqtz_bond_daily_snapshot / tyw_interbank_daily_snapshot 中所有 distinct report_date
  2. 检查 fact_formal_zqtz_balance_daily / fact_formal_tyw_balance_daily 中已有哪些日期
  3. 对所有缺失日期执行 materialize_balance_analysis_facts
  4. 输出摘要

注意:
  - 这会修改 moss.duckdb，建议先备份
  - 物化是幂等的（replace），已有日期重跑会覆盖
"""
from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

import duckdb

# Ensure backend modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _resolve_duckdb_path() -> Path:
    try:
        from backend.app.governance.settings import get_settings
        return Path(get_settings().duckdb_path)
    except Exception:
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "data" / "moss.duckdb"


def _get_snapshot_dates(conn: duckdb.DuckDBPyConnection) -> set[str]:
    """Get all distinct report_dates from snapshot tables."""
    dates: set[str] = set()
    for table in ("zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"):
        try:
            rows = conn.execute(
                f"SELECT DISTINCT cast(report_date as varchar) FROM {table}"
            ).fetchall()
            dates.update(str(r[0]) for r in rows if r[0])
        except duckdb.Error:
            pass
    return dates


def _get_formal_dates(conn: duckdb.DuckDBPyConnection) -> set[str]:
    """Get all distinct report_dates already in formal tables."""
    dates: set[str] = set()
    for table in ("fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"):
        try:
            rows = conn.execute(
                f"SELECT DISTINCT cast(report_date as varchar) FROM {table}"
            ).fetchall()
            dates.update(str(r[0]) for r in rows if r[0])
        except duckdb.Error:
            pass
    return dates


def _get_snapshot_row_counts(conn: duckdb.DuckDBPyConnection, report_date: str) -> tuple[int, int]:
    """Return (zqtz_count, tyw_count) for a given date."""
    zqtz = 0
    tyw = 0
    try:
        zqtz = conn.execute(
            "SELECT count(*) FROM zqtz_bond_daily_snapshot WHERE cast(report_date as varchar) = ?",
            [report_date],
        ).fetchone()[0]
    except duckdb.Error:
        pass
    try:
        tyw = conn.execute(
            "SELECT count(*) FROM tyw_interbank_daily_snapshot WHERE cast(report_date as varchar) = ?",
            [report_date],
        ).fetchone()[0]
    except duckdb.Error:
        pass
    return zqtz, tyw


def main():
    duckdb_path = _resolve_duckdb_path()
    print(f"[INFO] DuckDB: {duckdb_path}")

    if not duckdb_path.exists():
        print("[ERROR] DuckDB file not found")
        sys.exit(1)

    # Step 1: Analyze coverage
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        snapshot_dates = _get_snapshot_dates(conn)
        formal_dates = _get_formal_dates(conn)
    finally:
        conn.close()

    missing_dates = sorted(snapshot_dates - formal_dates)
    already_dates = sorted(snapshot_dates & formal_dates)

    print(f"\n{'=' * 60}")
    print(f"  快照表中共有 {len(snapshot_dates)} 个不同日期")
    print(f"  已物化日期:   {len(already_dates)}")
    print(f"  缺失日期:     {len(missing_dates)}")
    print(f"{'=' * 60}")

    if already_dates:
        print(f"\n  已物化: {', '.join(already_dates[:10])}")
        if len(already_dates) > 10:
            print(f"          ... 共 {len(already_dates)} 个")

    if not missing_dates:
        print("\n  ✅ 所有日期都已物化，无需操作。")
        return

    print(f"\n  ⚠️  缺失日期: {', '.join(missing_dates[:20])}")
    if len(missing_dates) > 20:
        print(f"          ... 共 {len(missing_dates)} 个")

    # Step 2: Show snapshot row counts for missing dates
    print(f"\n  快照行数概览（缺失日期）:")
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        for d in missing_dates[:10]:
            zqtz, tyw = _get_snapshot_row_counts(conn, d)
            print(f"    {d}: ZQTZ={zqtz}, TYW={tyw}")
        if len(missing_dates) > 10:
            print(f"    ... 共 {len(missing_dates)} 个日期")
    finally:
        conn.close()

    # Step 3: Materialize missing dates
    print(f"\n{'=' * 60}")
    print(f"  开始批量物化 {len(missing_dates)} 个日期...")
    print(f"{'=' * 60}")

    from backend.app.tasks.balance_analysis_materialize import (
        _execute_balance_analysis_materialization,
    )
    from backend.app.governance.settings import get_settings

    settings = get_settings()
    success = 0
    errors = 0

    for i, report_date in enumerate(missing_dates, 1):
        t0 = time.time()
        try:
            result = _execute_balance_analysis_materialization(
                report_date=report_date,
                duckdb_file=duckdb_path,
                governance_dir=str(settings.governance_path),
            )
            elapsed = time.time() - t0
            payload = result.payload or {}
            zqtz_rows = payload.get("zqtz_rows", "?")
            tyw_rows = payload.get("tyw_rows", "?")
            print(f"  [{i}/{len(missing_dates)}] {report_date} ✅ "
                  f"(zqtz={zqtz_rows}, tyw={tyw_rows}, {elapsed:.1f}s)")
            success += 1
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"  [{i}/{len(missing_dates)}] {report_date} ❌ {exc} ({elapsed:.1f}s)")
            errors += 1

    # Step 4: Verify
    print(f"\n{'=' * 60}")
    print(f"  物化完成: 成功={success}, 失败={errors}")
    print(f"{'=' * 60}")

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        final_formal = _get_formal_dates(conn)
        final_missing = sorted(snapshot_dates - final_formal)
        print(f"\n  物化后: 快照日期={len(snapshot_dates)}, 已物化={len(final_formal)}, 仍缺失={len(final_missing)}")
        if final_missing:
            print(f"  仍缺失: {', '.join(final_missing[:10])}")
        else:
            print("  ✅ 所有日期覆盖完整，ADB 页面日均计算将使用完整数据。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
