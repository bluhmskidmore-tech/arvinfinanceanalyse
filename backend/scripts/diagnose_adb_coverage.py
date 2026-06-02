"""
诊断 ADB 日均余额页面数据覆盖率。

用法:
  cd f:\MOSS-V3
  python -m backend.scripts.diagnose_adb_coverage

输出:
  1. 快照表（zqtz / tyw）有多少个 distinct report_date
  2. 正式表（fact_formal_*）有多少个 distinct report_date
  3. 缺失日期列表
  4. 最近 30 天的覆盖情况
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _resolve_duckdb_path() -> Path:
    try:
        from backend.app.governance.settings import get_settings
        return Path(get_settings().duckdb_path)
    except Exception:
        return Path(__file__).resolve().parents[2] / "data" / "moss.duckdb"


def _distinct_dates(conn, table: str) -> list[str]:
    try:
        rows = conn.execute(
            f"SELECT DISTINCT cast(report_date AS varchar) AS d FROM {table} ORDER BY d"
        ).fetchall()
        return [r[0] for r in rows if r[0]]
    except duckdb.Error as e:
        print(f"  [WARN] {table}: {e}")
        return []


def main():
    db = _resolve_duckdb_path()
    print(f"DuckDB: {db}")
    print(f"Exists: {db.exists()}\n")

    if not db.exists():
        print("[ERROR] DuckDB file not found!")
        return

    conn = duckdb.connect(str(db), read_only=True)

    # 1. Snapshot dates
    print("=" * 60)
    print("  快照表 (snapshot)")
    print("=" * 60)
    zqtz_snap = _distinct_dates(conn, "zqtz_bond_daily_snapshot")
    tyw_snap = _distinct_dates(conn, "tyw_interbank_daily_snapshot")
    snap_all = sorted(set(zqtz_snap) | set(tyw_snap))
    print(f"  zqtz_bond_daily_snapshot:       {len(zqtz_snap)} 个日期")
    print(f"  tyw_interbank_daily_snapshot:    {len(tyw_snap)} 个日期")
    print(f"  合并去重:                        {len(snap_all)} 个日期")
    if snap_all:
        print(f"  范围: {snap_all[0]} ~ {snap_all[-1]}")

    # 2. Formal dates
    print()
    print("=" * 60)
    print("  正式表 (fact_formal)")
    print("=" * 60)
    zqtz_formal = _distinct_dates(conn, "fact_formal_zqtz_balance_daily")
    tyw_formal = _distinct_dates(conn, "fact_formal_tyw_balance_daily")
    formal_all = sorted(set(zqtz_formal) | set(tyw_formal))
    print(f"  fact_formal_zqtz_balance_daily:  {len(zqtz_formal)} 个日期")
    print(f"  fact_formal_tyw_balance_daily:   {len(tyw_formal)} 个日期")
    print(f"  合并去重:                        {len(formal_all)} 个日期")
    if formal_all:
        print(f"  范围: {formal_all[0]} ~ {formal_all[-1]}")
        print(f"  日期: {formal_all}")

    # 3. Coverage gap
    print()
    print("=" * 60)
    print("  覆盖缺口")
    print("=" * 60)
    missing = sorted(set(snap_all) - set(formal_all))
    print(f"  快照有、formal 无:  {len(missing)} 个日期")
    if missing:
        for d in missing[:30]:
            print(f"    ❌ {d}")
        if len(missing) > 30:
            print(f"    ... 共 {len(missing)} 个")

    # 4. Recent 30-day window
    print()
    print("=" * 60)
    print("  最近 30 天覆盖")
    print("=" * 60)
    today = date.today()
    recent_start = today - timedelta(days=29)
    formal_set = set(formal_all)
    snap_set = set(snap_all)
    recent_covered = 0
    recent_snap = 0
    for i in range(30):
        d = (recent_start + timedelta(days=i)).isoformat()
        has_snap = d in snap_set
        has_formal = d in formal_set
        if has_snap:
            recent_snap += 1
        if has_formal:
            recent_covered += 1
        marker = "✅" if has_formal else ("⚠️ 快照有formal无" if has_snap else "— 无数据")
        print(f"    {d}  {marker}")

    print(f"\n  最近30天: 快照={recent_snap}天, formal={recent_covered}天")
    if recent_snap > 0 and recent_covered < recent_snap:
        print(f"\n  ⚠️  覆盖不足！需要运行批量物化:")
        print(f"     cd f:\\MOSS-V3")
        print(f"     python -m backend.scripts.batch_materialize_balance")
        print(f"     或:")
        print(f"     python -m backend.scripts.backfill_formal_balance")
    elif recent_covered == 0 and recent_snap == 0:
        print(f"\n  ⚠️  最近30天无快照数据，需先导入快照")
    else:
        print(f"\n  ✅ 覆盖完整")

    conn.close()


if __name__ == "__main__":
    main()
