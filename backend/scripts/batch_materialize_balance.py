"""
批量物化脚本 — 将 zqtz/tyw 快照表中所有 report_date 物化到 fact_formal_* 正式表。

用法:
  cd f:\MOSS-V3
  python -m backend.scripts.batch_materialize_balance [--dry-run] [--start 2026-01-01] [--end 2026-05-03] [--audit]

选项:
  --dry-run   只列出待物化日期，不执行
  --start     仅物化 >= start 的日期
  --end       仅物化 <= end 的日期
  --audit     物化后对比快照与正式表的总额差异
"""
from __future__ import annotations

import argparse
import sys
import time
from decimal import Decimal
from pathlib import Path

import duckdb


def _resolve_duckdb_path() -> Path:
    """与 Settings 一致的 DuckDB 路径解析。"""
    try:
        from backend.app.governance.settings import get_settings
        return Path(get_settings().duckdb_path)
    except Exception:
        # 回退: 从项目根目录推算
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "data" / "moss.duckdb"


def list_snapshot_dates(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """获取快照表中所有不重复的 report_date（ZQTZ ∪ TYW）。"""
    dates: set[str] = set()
    for table in ("zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"):
        try:
            rows = conn.execute(
                f"SELECT DISTINCT cast(report_date AS varchar) FROM {table} ORDER BY 1"
            ).fetchall()
            dates.update(str(r[0]) for r in rows if r[0])
        except duckdb.Error:
            pass
    return sorted(dates)


def list_formal_dates(conn: duckdb.DuckDBPyConnection) -> set[str]:
    """获取正式表中已物化的 report_date 集合。"""
    dates: set[str] = set()
    for table in ("fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"):
        try:
            rows = conn.execute(
                f"SELECT DISTINCT cast(report_date AS varchar) FROM {table}"
            ).fetchall()
            dates.update(str(r[0]) for r in rows if r[0])
        except duckdb.Error:
            pass
    return dates


def materialize_single_date(report_date: str, duckdb_path: str) -> dict:
    """调用已有的物化流程处理单个日期。"""
    from backend.app.tasks.balance_analysis_materialize import (
        _execute_balance_analysis_materialization,
    )
    from backend.app.governance.settings import get_settings

    settings = get_settings()
    db_path = Path(duckdb_path)
    result = _execute_balance_analysis_materialization(
        report_date=report_date,
        duckdb_file=db_path,
        governance_dir=str(settings.governance_path),
        data_root=str(settings.data_input_root),
    )
    return {
        "source_version": result.source_version,
        "zqtz_rows": result.payload.get("zqtz_rows", 0),
        "tyw_rows": result.payload.get("tyw_rows", 0),
    }


def audit_date(conn: duckdb.DuckDBPyConnection, report_date: str) -> dict:
    """比对单个日期的快照总额 vs formal 总额。"""
    result = {"report_date": report_date}

    # ZQTZ 快照: 资产 market_value_native 总和
    try:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN NOT is_issuance_like THEN market_value_native ELSE 0 END) as snap_asset,
                SUM(CASE WHEN is_issuance_like THEN market_value_native ELSE 0 END) as snap_liab,
                COUNT(*) as snap_rows
            FROM zqtz_bond_daily_snapshot
            WHERE report_date = ?
            """,
            [report_date],
        ).fetchone()
        result["zqtz_snap_asset"] = float(row[0] or 0)
        result["zqtz_snap_liab"] = float(row[1] or 0)
        result["zqtz_snap_rows"] = int(row[2] or 0)
    except duckdb.Error:
        result["zqtz_snap_asset"] = 0
        result["zqtz_snap_liab"] = 0
        result["zqtz_snap_rows"] = 0

    # ZQTZ formal: CNY asset market_value_amount 总和
    try:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN position_scope = 'asset' THEN market_value_amount ELSE 0 END) as formal_asset,
                SUM(CASE WHEN position_scope = 'liability' THEN market_value_amount ELSE 0 END) as formal_liab,
                COUNT(*) as formal_rows
            FROM fact_formal_zqtz_balance_daily
            WHERE report_date = ? AND currency_basis = 'CNY'
            """,
            [report_date],
        ).fetchone()
        result["zqtz_formal_asset"] = float(row[0] or 0)
        result["zqtz_formal_liab"] = float(row[1] or 0)
        result["zqtz_formal_rows"] = int(row[2] or 0)
    except duckdb.Error:
        result["zqtz_formal_asset"] = 0
        result["zqtz_formal_liab"] = 0
        result["zqtz_formal_rows"] = 0

    # TYW 快照
    try:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN position_side = 'asset' THEN principal_native ELSE 0 END) as snap_asset,
                SUM(CASE WHEN position_side = 'liability' THEN principal_native ELSE 0 END) as snap_liab,
                COUNT(*) as snap_rows
            FROM tyw_interbank_daily_snapshot
            WHERE report_date = ?
            """,
            [report_date],
        ).fetchone()
        result["tyw_snap_asset"] = float(row[0] or 0)
        result["tyw_snap_liab"] = float(row[1] or 0)
        result["tyw_snap_rows"] = int(row[2] or 0)
    except duckdb.Error:
        result["tyw_snap_asset"] = 0
        result["tyw_snap_liab"] = 0
        result["tyw_snap_rows"] = 0

    # TYW formal
    try:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN position_scope = 'asset' THEN principal_amount ELSE 0 END) as formal_asset,
                SUM(CASE WHEN position_scope = 'liability' THEN principal_amount ELSE 0 END) as formal_liab,
                COUNT(*) as formal_rows
            FROM fact_formal_tyw_balance_daily
            WHERE report_date = ? AND currency_basis = 'CNY'
            """,
            [report_date],
        ).fetchone()
        result["tyw_formal_asset"] = float(row[0] or 0)
        result["tyw_formal_liab"] = float(row[1] or 0)
        result["tyw_formal_rows"] = int(row[2] or 0)
    except duckdb.Error:
        result["tyw_formal_asset"] = 0
        result["tyw_formal_liab"] = 0
        result["tyw_formal_rows"] = 0

    # 差异
    result["zqtz_asset_diff"] = result["zqtz_formal_asset"] - result["zqtz_snap_asset"]
    result["zqtz_liab_diff"] = result["zqtz_formal_liab"] - result["zqtz_snap_liab"]
    result["tyw_asset_diff"] = result["tyw_formal_asset"] - result["tyw_snap_asset"]
    result["tyw_liab_diff"] = result["tyw_formal_liab"] - result["tyw_snap_liab"]

    return result


def main():
    parser = argparse.ArgumentParser(description="批量物化 balance_analysis formal 表")
    parser.add_argument("--dry-run", action="store_true", help="仅列出待物化日期，不执行")
    parser.add_argument("--start", default=None, help="起始日期 (含)")
    parser.add_argument("--end", default=None, help="结束日期 (含)")
    parser.add_argument("--audit", action="store_true", help="物化后执行快照-formal 差额审计")
    parser.add_argument("--audit-only", action="store_true", help="仅审计已有的 formal 数据，不物化")
    parser.add_argument("--force", action="store_true", help="强制重新物化已存在的日期")
    args = parser.parse_args()

    duckdb_path = str(_resolve_duckdb_path())
    print(f"[INFO] DuckDB: {duckdb_path}")

    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
        all_snapshot_dates = list_snapshot_dates(conn)
        existing_formal_dates = list_formal_dates(conn)
    finally:
        conn.close()

    # 按范围过滤
    target_dates = all_snapshot_dates
    if args.start:
        target_dates = [d for d in target_dates if d >= args.start]
    if args.end:
        target_dates = [d for d in target_dates if d <= args.end]

    print(f"[INFO] 快照表日期总数: {len(all_snapshot_dates)}")
    print(f"[INFO] 已物化日期数:   {len(existing_formal_dates)}")
    print(f"[INFO] 目标范围日期数: {len(target_dates)}")

    if not args.force:
        pending_dates = [d for d in target_dates if d not in existing_formal_dates]
    else:
        pending_dates = target_dates

    print(f"[INFO] 待物化日期数:   {len(pending_dates)}")

    if args.audit_only:
        print("\n=== 审计模式（仅对比已有数据）===")
        conn = duckdb.connect(duckdb_path, read_only=True)
        try:
            audit_dates = [d for d in target_dates if d in existing_formal_dates]
            if not audit_dates:
                print("[WARN] 目标范围内无已物化日期")
                return
            _run_audit(conn, audit_dates)
        finally:
            conn.close()
        return

    if args.dry_run:
        print("\n=== DRY RUN — 将物化以下日期 ===")
        for d in pending_dates[:20]:
            status = "已存在(将跳过)" if d in existing_formal_dates else "待物化"
            if args.force and d in existing_formal_dates:
                status = "已存在(将重建)"
            print(f"  {d}  [{status}]")
        if len(pending_dates) > 20:
            print(f"  ... 共 {len(pending_dates)} 个日期")
        return

    if not pending_dates:
        print("[INFO] 所有日期已物化，无需操作")
        if args.audit:
            conn = duckdb.connect(duckdb_path, read_only=True)
            try:
                _run_audit(conn, target_dates[:5])
            finally:
                conn.close()
        return

    # 执行物化
    print(f"\n=== 开始批量物化 {len(pending_dates)} 个日期 ===")
    success = 0
    failed = []
    for i, report_date in enumerate(pending_dates, 1):
        t0 = time.time()
        try:
            result = materialize_single_date(report_date, duckdb_path)
            elapsed = time.time() - t0
            print(
                f"  [{i}/{len(pending_dates)}] {report_date} ✓ "
                f"zqtz={result['zqtz_rows']} tyw={result['tyw_rows']} ({elapsed:.1f}s)"
            )
            success += 1
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"  [{i}/{len(pending_dates)}] {report_date} ✗ {exc} ({elapsed:.1f}s)")
            failed.append((report_date, str(exc)))

    print(f"\n=== 完成: {success} 成功, {len(failed)} 失败 ===")
    if failed:
        print("\n失败日期:")
        for d, err in failed:
            print(f"  {d}: {err}")

    # 审计
    if args.audit:
        conn = duckdb.connect(duckdb_path, read_only=True)
        try:
            _run_audit(conn, pending_dates[:10])
        finally:
            conn.close()


def _run_audit(conn: duckdb.DuckDBPyConnection, dates: list[str]):
    """执行差额审计并输出报告。"""
    print(f"\n=== 快照 vs formal 差额审计 (取样 {len(dates)} 个日期) ===")
    YI = 1e8
    header = f"{'日期':>12} | {'ZQTZ资产差额(亿)':>16} | {'ZQTZ负债差额(亿)':>16} | {'TYW资产差额(亿)':>15} | {'TYW负债差额(亿)':>15} | {'快照行':>6} | {'formal行':>8}"
    print(header)
    print("-" * len(header))

    has_diff = False
    for d in dates:
        a = audit_date(conn, d)
        snap_total = a["zqtz_snap_rows"] + a["tyw_snap_rows"]
        formal_total = a["zqtz_formal_rows"] + a["tyw_formal_rows"]
        z_a = a["zqtz_asset_diff"] / YI
        z_l = a["zqtz_liab_diff"] / YI
        t_a = a["tyw_asset_diff"] / YI
        t_l = a["tyw_liab_diff"] / YI

        flag = ""
        if abs(z_a) > 0.01 or abs(z_l) > 0.01 or abs(t_a) > 0.01 or abs(t_l) > 0.01:
            flag = " ⚠️"
            has_diff = True

        print(
            f"{d:>12} | {z_a:>16.4f} | {z_l:>16.4f} | {t_a:>15.4f} | {t_l:>15.4f} | {snap_total:>6} | {formal_total:>8}{flag}"
        )

    if has_diff:
        print("\n[WARN] 存在差额！可能原因:")
        print("  1. 非 CNY 持仓的 FX 汇率转换（快照用原币，formal 用 CNY）")
        print("  2. is_issuance_like 分类导致 position_scope 过滤")
        print("  3. invest_type_raw 无法映射 → project 返回 None（ZQTZ 资产会被跳过）")
        print("  4. formal 表写入 native + CNY 两行，审计只比了 CNY 行")
    else:
        print("\n[OK] 快照与 formal 总额一致")


if __name__ == "__main__":
    main()
