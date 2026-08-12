#!/usr/bin/env python3
"""列出资产端 ADB「其它」的明细来源（与 /average-balance 同源 _load_adb_raw_data + 分类逻辑）。

用法:
  python scripts/list_adb_asset_other_breakdown.py <moss.duckdb> <开始日> <结束日>
  例: python scripts/list_adb_asset_other_breakdown.py D:/data/moss.duckdb 2025-11-01 2025-11-30

需在仓库根目录执行，或已安装并把 MOSS 根加入 PYTHONPATH。
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from backend.app.services.adb_analysis_service import (
    _clean_cat,
    _issued_mask,
    _load_adb_raw_data,
    get_adb_comparison,
)


def main() -> None:
    if len(sys.argv) < 4:
        print(
            "用法: python scripts/list_adb_asset_other_breakdown.py <moss.duckdb> YYYY-MM-DD YYYY-MM-DD",
            file=sys.stderr,
        )
        sys.exit(2)
    db_path = sys.argv[1]
    d0 = date.fromisoformat(sys.argv[2])
    d1 = date.fromisoformat(sys.argv[3])
    if not Path(db_path).exists():
        print(f"找不到库文件: {db_path}", file=sys.stderr)
        sys.exit(1)

    payload, *_ = get_adb_comparison(db_path, d0, d1, top_n=500)
    assets = payload.get("assets_breakdown") or []
    other_api = next((r for r in assets if r.get("category") == "其它"), None)

    print("=== 接口 assets_breakdown·其它（与页面一致）===")
    if other_api:
        for k in sorted(other_api.keys()):
            print(f"  {k}: {other_api[k]}")
    else:
        print("  （本区间无「其它」行）")

    bonds_df, ib_df, *_ = _load_adb_raw_data(db_path, d0, d1)
    issued = _issued_mask(bonds_df)
    ab = bonds_df[~issued]
    other_b = ab[ab["bond_category"].eq("其它")].copy()
    ia = ib_df[ib_df["direction"].eq("ASSET")]
    other_i = ia[ia["product_type"].map(_clean_cat).eq("其它")].copy()

    cal = (d1 - d0).days + 1

    print("\n=== ZQTZ 资产 · bond_category=其它（逐日观测，最多 200 行）===")
    if other_b.empty:
        print("  （无）")
    else:
        show_cols = [
            c
            for c in (
                "report_date",
                "instrument_code",
                "instrument_name",
                "sub_type",
                "business_type_primary",
                "business_type_final",
                "bond_type",
                "market_value",
            )
            if c in other_b.columns
        ]
        print(other_b[show_cols].head(200).to_string(index=False))
        print(f"\n  观测行数: {len(other_b)}")
        print(f"  各日余额加总(元): {pd.to_numeric(other_b['market_value'], errors='coerce').fillna(0).sum():,.2f}")

        g = (
            other_b.groupby(["instrument_code", "sub_type", "bond_type"], dropna=False)
            .agg(obs_days=("report_date", "nunique"), sum_mv=("market_value", "sum"))
            .reset_index()
            .sort_values("sum_mv", ascending=False)
        )
        print("\n=== ZQTZ「其它」按 债券代号 + sub_type + bond_type 汇总 ===")
        print(g.to_string(index=False))

    print("\n=== 同业资产 · product_type 经 _clean_cat 为「其它」===")
    if other_i.empty:
        print("  （无）")
    else:
        show_i = [c for c in ("report_date", "product_type", "amount") if c in other_i.columns]
        print(other_i[show_i].head(200).to_string(index=False))
        print(f"\n  观测行数: {len(other_i)}")
        print(f"  本金加总(元): {pd.to_numeric(other_i['amount'], errors='coerce').fillna(0).sum():,.2f}")

    print(
        f"\n说明: 区间日历天数={cal}；页面「日均」含样本补齐等，和「加总÷天数」可能不完全相等，以接口 avg_balance 为准。"
    )


if __name__ == "__main__":
    main()
