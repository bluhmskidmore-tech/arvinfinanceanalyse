"""
精确差额定位脚本 — 逐行对比快照与 formal 表，找出差异来源。

用法:
  cd f:\MOSS-V3
  python -m backend.scripts.diagnose_balance_diff --date 2026-04-30

输出:
  1. 行数差异统计
  2. 按币种分组的差额明细
  3. 按 asset_class/bond_type 分组的差额明细
  4. 具体被过滤/跳过的行列表
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

import duckdb


def _resolve_duckdb_path() -> Path:
    try:
        from backend.app.governance.settings import get_settings
        return Path(get_settings().duckdb_path)
    except Exception:
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "data" / "moss.duckdb"


def _get_latest_formal_date(conn: duckdb.DuckDBPyConnection) -> str | None:
    """获取 formal 表中最新的 report_date。"""
    for table in ("fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"):
        try:
            rows = conn.execute(
                f"SELECT MAX(cast(report_date as varchar)) FROM {table}"
            ).fetchall()
            if rows and rows[0][0]:
                return str(rows[0][0])
        except duckdb.Error:
            pass
    return None


def diagnose_zqtz(conn: duckdb.DuckDBPyConnection, report_date: str):
    """诊断 ZQTZ（债券投资）快照与 formal 的差异。"""
    print("\n" + "=" * 80)
    print(f"  ZQTZ（债券投资）差异诊断 — {report_date}")
    print("=" * 80)

    # 1. 快照行数和总额
    snap_rows = conn.execute("""
        SELECT
            currency_code,
            is_issuance_like,
            asset_class,
            account_category,
            bond_type,
            COUNT(*) as cnt,
            SUM(market_value_native) as mv_sum,
            SUM(face_value_native) as fv_sum
        FROM zqtz_bond_daily_snapshot
        WHERE report_date = ?
        GROUP BY currency_code, is_issuance_like, asset_class, account_category, bond_type
        ORDER BY currency_code, is_issuance_like, asset_class
    """, [report_date]).fetchall()

    if not snap_rows:
        print(f"  [WARN] 快照表中 {report_date} 无数据")
        return

    snap_total_rows = sum(r[5] for r in snap_rows)
    snap_total_mv = sum(float(r[6] or 0) for r in snap_rows)
    print(f"\n  快照行数: {snap_total_rows}")
    print(f"  快照市值总额(原币): {snap_total_mv / 1e8:.4f} 亿")

    # 2. formal 行数和总额 (CNY only)
    formal_rows = conn.execute("""
        SELECT
            currency_code,
            position_scope,
            asset_class,
            account_category,
            bond_type,
            currency_basis,
            COUNT(*) as cnt,
            SUM(market_value_amount) as mv_sum,
            SUM(face_value_amount) as fv_sum
        FROM fact_formal_zqtz_balance_daily
        WHERE report_date = ?
        GROUP BY currency_code, position_scope, asset_class, account_category, bond_type, currency_basis
        ORDER BY currency_basis, currency_code, position_scope
    """, [report_date]).fetchall()

    if not formal_rows:
        print(f"  [WARN] formal 表中 {report_date} 无数据 — 未物化！")
        return

    formal_native = [r for r in formal_rows if r[5] == "native"]
    formal_cny = [r for r in formal_rows if r[5] == "CNY"]

    formal_native_total = sum(float(r[7] or 0) for r in formal_native)
    formal_cny_total = sum(float(r[7] or 0) for r in formal_cny)
    formal_total_rows_native = sum(r[6] for r in formal_native)
    formal_total_rows_cny = sum(r[6] for r in formal_cny)

    print(f"  formal native 行数: {formal_total_rows_native}, 市值: {formal_native_total / 1e8:.4f} 亿")
    print(f"  formal CNY    行数: {formal_total_rows_cny}, 市值: {formal_cny_total / 1e8:.4f} 亿")

    # 3. 差额分析: 快照原币 vs formal native (应该完全一致)
    diff_native = formal_native_total - snap_total_mv
    print(f"\n  === 差额(快照原币 vs formal native): {diff_native / 1e8:.4f} 亿 ===")
    if abs(diff_native) > 1:
        print("  ⚠️  快照原币 ≠ formal native，可能有行被过滤")
    else:
        print("  ✅  一致 — 所有快照行都成功物化为 native 行")

    # 4. 差额分析: formal native vs formal CNY (FX 转换差)
    diff_fx = formal_cny_total - formal_native_total
    print(f"\n  === FX 转换差(formal native vs CNY): {diff_fx / 1e8:.4f} 亿 ===")
    if abs(diff_fx) > 1:
        print("  ⚠️  存在非 CNY 持仓的汇率转换差")
    else:
        print("  ✅  无 FX 差异 — 全部为 CNY 持仓或汇率一致")

    # 5. 按币种分组对比
    print("\n  --- 按币种分组 ---")
    YI = 1e8

    snap_by_ccy: dict[str, tuple[int, float]] = {}
    for r in snap_rows:
        ccy = str(r[0] or "CNY").upper()
        cnt, mv = snap_by_ccy.get(ccy, (0, 0.0))
        snap_by_ccy[ccy] = (cnt + r[5], mv + float(r[6] or 0))

    formal_by_ccy_native: dict[str, tuple[int, float]] = {}
    for r in formal_native:
        ccy = str(r[0] or "CNY").upper()
        cnt, mv = formal_by_ccy_native.get(ccy, (0, 0.0))
        formal_by_ccy_native[ccy] = (cnt + r[6], mv + float(r[7] or 0))

    formal_by_ccy_cny: dict[str, tuple[int, float]] = {}
    for r in formal_cny:
        ccy = str(r[0] or "CNY").upper()
        cnt, mv = formal_by_ccy_cny.get(ccy, (0, 0.0))
        formal_by_ccy_cny[ccy] = (cnt + r[6], mv + float(r[7] or 0))

    all_ccys = sorted(set(snap_by_ccy.keys()) | set(formal_by_ccy_native.keys()) | set(formal_by_ccy_cny.keys()))
    print(f"  {'币种':>6} | {'快照行':>6} | {'快照原币(亿)':>14} | {'native行':>8} | {'native(亿)':>12} | {'CNY行':>6} | {'CNY(亿)':>12} | {'FX差(亿)':>10}")
    for ccy in all_ccys:
        s_cnt, s_mv = snap_by_ccy.get(ccy, (0, 0.0))
        fn_cnt, fn_mv = formal_by_ccy_native.get(ccy, (0, 0.0))
        fc_cnt, fc_mv = formal_by_ccy_cny.get(ccy, (0, 0.0))
        fx_diff = fc_mv - fn_mv
        flag = " ⚠️" if abs(fx_diff) > 1 else ""
        row_flag = " ❌" if s_cnt != fn_cnt else ""
        print(
            f"  {ccy:>6} | {s_cnt:>6} | {s_mv / YI:>14.4f} | {fn_cnt:>8}{row_flag} | {fn_mv / YI:>12.4f} | {fc_cnt:>6} | {fc_mv / YI:>12.4f} | {fx_diff / YI:>10.4f}{flag}"
        )

    # 6. 按 asset_class 分组
    print("\n  --- 按 asset_class 分组 (快照原币) ---")
    snap_by_ac: dict[str, tuple[int, float, bool]] = {}
    for r in snap_rows:
        ac = str(r[2] or "未知")
        is_iss = bool(r[1])
        key = f"{ac} ({'负债' if is_iss else '资产'})"
        cnt, mv, _ = snap_by_ac.get(key, (0, 0.0, is_iss))
        snap_by_ac[key] = (cnt + r[5], mv + float(r[6] or 0), is_iss)

    formal_by_ac: dict[str, tuple[int, float]] = {}
    for r in formal_native:
        ac = str(r[2] or "未知")
        scope = str(r[1] or "all")
        key = f"{ac} ({'负债' if scope == 'liability' else '资产'})"
        cnt, mv = formal_by_ac.get(key, (0, 0.0))
        formal_by_ac[key] = (cnt + r[6], mv + float(r[7] or 0))

    all_acs = sorted(set(snap_by_ac.keys()) | set(formal_by_ac.keys()))
    print(f"  {'分类':>24} | {'快照行':>6} | {'快照(亿)':>12} | {'formal行':>8} | {'formal(亿)':>12} | {'差额(亿)':>10}")
    for ac in all_acs:
        s_cnt, s_mv, _ = snap_by_ac.get(ac, (0, 0.0, False))
        f_cnt, f_mv = formal_by_ac.get(ac, (0, 0.0))
        diff = f_mv - s_mv
        flag = " ⚠️" if abs(diff) > 1 else ""
        print(f"  {ac:>24} | {s_cnt:>6} | {s_mv / YI:>12.4f} | {f_cnt:>8} | {f_mv / YI:>12.4f} | {diff / YI:>10.4f}{flag}")

    # 7. 行数不对称时: 找出缺失的行
    if snap_total_rows != formal_total_rows_native:
        print(f"\n  ⚠️  行数不一致: 快照 {snap_total_rows} vs formal native {formal_total_rows_native}")
        print("  查找缺失的行...")

        snap_keys = conn.execute("""
            SELECT instrument_code, portfolio_name, cost_center, currency_code, is_issuance_like,
                   asset_class, account_category, market_value_native
            FROM zqtz_bond_daily_snapshot
            WHERE report_date = ?
            ORDER BY instrument_code
        """, [report_date]).fetchall()

        formal_keys = conn.execute("""
            SELECT instrument_code, portfolio_name, cost_center, currency_code, is_issuance_like,
                   asset_class, account_category, market_value_amount
            FROM fact_formal_zqtz_balance_daily
            WHERE report_date = ? AND currency_basis = 'native'
            ORDER BY instrument_code
        """, [report_date]).fetchall()

        snap_set = {(r[0], r[1], r[2], r[3]): r for r in snap_keys}
        formal_set = {(r[0], r[1], r[2], r[3]): r for r in formal_keys}

        missing_in_formal = set(snap_set.keys()) - set(formal_set.keys())
        extra_in_formal = set(formal_set.keys()) - set(snap_set.keys())

        if missing_in_formal:
            print(f"\n  在快照中但不在 formal 中 ({len(missing_in_formal)} 行):")
            for key in sorted(missing_in_formal)[:20]:
                r = snap_set[key]
                print(f"    {r[0]:>20} | 组合={r[1]} | 币种={r[3]} | is_iss={r[4]} | class={r[5]} | cat={r[6]} | mv={float(r[7] or 0) / 1e8:.4f}亿")

        if extra_in_formal:
            print(f"\n  在 formal 中但不在快照中 ({len(extra_in_formal)} 行):")
            for key in sorted(extra_in_formal)[:20]:
                r = formal_set[key]
                print(f"    {r[0]:>20} | 组合={r[1]} | 币种={r[3]} | is_iss={r[4]} | class={r[5]} | cat={r[6]} | mv={float(r[7] or 0) / 1e8:.4f}亿")


def diagnose_tyw(conn: duckdb.DuckDBPyConnection, report_date: str):
    """诊断 TYW（同业）快照与 formal 的差异。"""
    print("\n" + "=" * 80)
    print(f"  TYW（同业）差异诊断 — {report_date}")
    print("=" * 80)

    YI = 1e8

    # 快照
    snap_rows = conn.execute("""
        SELECT
            currency_code,
            position_side,
            product_type,
            COUNT(*) as cnt,
            SUM(principal_native) as p_sum
        FROM tyw_interbank_daily_snapshot
        WHERE report_date = ?
        GROUP BY currency_code, position_side, product_type
        ORDER BY currency_code, position_side
    """, [report_date]).fetchall()

    if not snap_rows:
        print(f"  [WARN] TYW 快照表中 {report_date} 无数据")
        return

    snap_total = sum(float(r[4] or 0) for r in snap_rows)
    snap_cnt = sum(r[3] for r in snap_rows)
    print(f"\n  快照行数: {snap_cnt}, 本金总额(原币): {snap_total / YI:.4f} 亿")

    # formal
    formal_rows = conn.execute("""
        SELECT
            currency_code,
            position_scope,
            product_type,
            currency_basis,
            COUNT(*) as cnt,
            SUM(principal_amount) as p_sum
        FROM fact_formal_tyw_balance_daily
        WHERE report_date = ?
        GROUP BY currency_code, position_scope, product_type, currency_basis
        ORDER BY currency_basis, currency_code, position_scope
    """, [report_date]).fetchall()

    if not formal_rows:
        print(f"  [WARN] TYW formal 表中 {report_date} 无数据 — 未物化！")
        return

    formal_native = [r for r in formal_rows if r[3] == "native"]
    formal_cny = [r for r in formal_rows if r[3] == "CNY"]
    formal_native_total = sum(float(r[5] or 0) for r in formal_native)
    formal_cny_total = sum(float(r[5] or 0) for r in formal_cny)
    fn_cnt = sum(r[4] for r in formal_native)
    fc_cnt = sum(r[4] for r in formal_cny)

    print(f"  formal native 行数: {fn_cnt}, 本金: {formal_native_total / YI:.4f} 亿")
    print(f"  formal CNY    行数: {fc_cnt}, 本金: {formal_cny_total / YI:.4f} 亿")
    print(f"\n  快照原币 vs formal native 差额: {(formal_native_total - snap_total) / YI:.4f} 亿")
    print(f"  FX 转换差(native vs CNY):       {(formal_cny_total - formal_native_total) / YI:.4f} 亿")

    # 按 position_side 分组
    print("\n  --- 按 position_side/scope 分组 ---")
    snap_by_side: dict[str, tuple[int, float]] = {}
    for r in snap_rows:
        side = str(r[1] or "all")
        cnt, total = snap_by_side.get(side, (0, 0.0))
        snap_by_side[side] = (cnt + r[3], total + float(r[4] or 0))

    formal_by_scope: dict[str, tuple[int, float]] = {}
    for r in formal_native:
        scope = str(r[1] or "all")
        cnt, total = formal_by_scope.get(scope, (0, 0.0))
        formal_by_scope[scope] = (cnt + r[4], total + float(r[5] or 0))

    all_sides = sorted(set(snap_by_side.keys()) | set(formal_by_scope.keys()))
    print(f"  {'方向':>12} | {'快照行':>6} | {'快照(亿)':>12} | {'formal行':>8} | {'formal(亿)':>12} | {'差额(亿)':>10}")
    for side in all_sides:
        s_cnt, s_mv = snap_by_side.get(side, (0, 0.0))
        f_cnt, f_mv = formal_by_scope.get(side, (0, 0.0))
        diff = f_mv - s_mv
        flag = " ⚠️" if abs(diff) > 1 else ""
        print(f"  {side:>12} | {s_cnt:>6} | {s_mv / YI:>12.4f} | {f_cnt:>8} | {f_mv / YI:>12.4f} | {diff / YI:>10.4f}{flag}")

    # 按币种分组
    snap_by_ccy: dict[str, float] = {}
    for r in snap_rows:
        ccy = str(r[0] or "CNY").upper()
        snap_by_ccy[ccy] = snap_by_ccy.get(ccy, 0) + float(r[4] or 0)

    formal_cny_by_ccy: dict[str, float] = {}
    for r in formal_cny:
        ccy = str(r[0] or "CNY").upper()
        formal_cny_by_ccy[ccy] = formal_cny_by_ccy.get(ccy, 0) + float(r[5] or 0)

    non_cny_ccys = [c for c in snap_by_ccy if c not in ("CNY", "CNH", "RMB")]
    if non_cny_ccys:
        print(f"\n  ⚠️  存在非 CNY 币种: {', '.join(non_cny_ccys)}")
        for ccy in non_cny_ccys:
            snap_v = snap_by_ccy.get(ccy, 0)
            formal_v = formal_cny_by_ccy.get(ccy, 0)
            print(f"    {ccy}: 快照原币={snap_v / YI:.4f}亿, formal CNY={formal_v / YI:.4f}亿, FX影响={(formal_v - snap_v) / YI:.4f}亿")


def diagnose_adb_read(conn: duckdb.DuckDBPyConnection, report_date: str):
    """模拟 ADB 服务的读取逻辑，显示最终看到的数据。"""
    print("\n" + "=" * 80)
    print(f"  ADB 服务读取模拟 — {report_date}")
    print("=" * 80)

    YI = 1e8

    # ADB 读的是 formal CNY, position_scope 为 asset 或 liability
    # ZQTZ: sub_type = bond_type 列
    try:
        zqtz_adb = conn.execute("""
            SELECT
                bond_type as sub_type,
                position_scope,
                SUM(market_value_amount) as mv
            FROM fact_formal_zqtz_balance_daily
            WHERE report_date = ? AND currency_basis = 'CNY'
            GROUP BY bond_type, position_scope
            ORDER BY position_scope, bond_type
        """, [report_date]).fetchall()
    except duckdb.Error:
        zqtz_adb = []

    try:
        tyw_adb = conn.execute("""
            SELECT
                product_type,
                position_scope,
                SUM(principal_amount) as amt
            FROM fact_formal_tyw_balance_daily
            WHERE report_date = ? AND currency_basis = 'CNY'
            GROUP BY product_type, position_scope
            ORDER BY position_scope, product_type
        """, [report_date]).fetchall()
    except duckdb.Error:
        tyw_adb = []

    total_assets = 0.0
    total_liab = 0.0

    print(f"\n  ZQTZ 资产端 (formal CNY):")
    for r in zqtz_adb:
        if r[1] == "asset":
            mv = float(r[2] or 0)
            total_assets += mv
            print(f"    {str(r[0] or '未知'):>20}: {mv / YI:>12.4f} 亿")

    print(f"\n  ZQTZ 负债端 (formal CNY):")
    for r in zqtz_adb:
        if r[1] == "liability":
            mv = float(r[2] or 0)
            total_liab += mv
            print(f"    {str(r[0] or '未知'):>20}: {mv / YI:>12.4f} 亿")

    print(f"\n  TYW 资产端 (formal CNY):")
    for r in tyw_adb:
        if r[1] == "asset":
            amt = float(r[2] or 0)
            total_assets += amt
            print(f"    {str(r[0] or '未知'):>20}: {amt / YI:>12.4f} 亿")

    print(f"\n  TYW 负债端 (formal CNY):")
    for r in tyw_adb:
        if r[1] == "liability":
            amt = float(r[2] or 0)
            total_liab += amt
            print(f"    {str(r[0] or '未知'):>20}: {amt / YI:>12.4f} 亿")

    print(f"\n  ────��────────────────────────────")
    print(f"  ADB 总资产: {total_assets / YI:.4f} 亿")
    print(f"  ADB 总负债: {total_liab / YI:.4f} 亿")

    # 对比快照简单求和
    try:
        snap_totals = conn.execute("""
            SELECT
                SUM(CASE WHEN NOT is_issuance_like THEN market_value_native ELSE 0 END) as asset,
                SUM(CASE WHEN is_issuance_like THEN market_value_native ELSE 0 END) as liab
            FROM zqtz_bond_daily_snapshot WHERE report_date = ?
        """, [report_date]).fetchone()
        tyw_snap = conn.execute("""
            SELECT
                SUM(CASE WHEN position_side = 'asset' THEN principal_native ELSE 0 END) as asset,
                SUM(CASE WHEN position_side = 'liability' THEN principal_native ELSE 0 END) as liab
            FROM tyw_interbank_daily_snapshot WHERE report_date = ?
        """, [report_date]).fetchone()
    except duckdb.Error:
        snap_totals = (0, 0)
        tyw_snap = (0, 0)

    snap_asset_total = float(snap_totals[0] or 0) + float(tyw_snap[0] or 0)
    snap_liab_total = float(snap_totals[1] or 0) + float(tyw_snap[1] or 0)

    print(f"\n  快照原币总资产: {snap_asset_total / YI:.4f} 亿")
    print(f"  快照原币总负债: {snap_liab_total / YI:.4f} 亿")
    print(f"\n  差额(资产): {(total_assets - snap_asset_total) / YI:.4f} 亿")
    print(f"  差额(负债): {(total_liab - snap_liab_total) / YI:.4f} 亿")

    if abs(total_assets - snap_asset_total) > 1 or abs(total_liab - snap_liab_total) > 1:
        print("\n  🔍 差额来源判断:")
        if abs(total_assets - snap_asset_total) > abs(total_liab - snap_liab_total):
            print("     → 差额主要在资产端")
        else:
            print("     → 差额主要在负债端")


def main():
    parser = argparse.ArgumentParser(description="快照 vs formal 精确差额定位")
    parser.add_argument("--date", default=None, help="要诊断的日期 (默认取 formal 表最新日期)")
    args = parser.parse_args()

    duckdb_path = str(_resolve_duckdb_path())
    print(f"[INFO] DuckDB: {duckdb_path}")

    conn = duckdb.connect(duckdb_path, read_only=True)
    try:
        if args.date:
            report_date = args.date
        else:
            report_date = _get_latest_formal_date(conn)
            if not report_date:
                print("[ERROR] formal 表中无数据，请先物化至少一个日期")
                sys.exit(1)
            print(f"[INFO] 使用 formal 最新日期: {report_date}")

        diagnose_zqtz(conn, report_date)
        diagnose_tyw(conn, report_date)
        diagnose_adb_read(conn, report_date)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
