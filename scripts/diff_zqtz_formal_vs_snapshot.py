#!/usr/bin/env python3
"""
ZQTZ：formal vs snapshot 差异跑到底（只读）。

默认 snapshot 侧与 ADB 回退读法一致：只聚合 currency_code in (CNY, CNX)。
formal 侧为物化后的 currency_basis='CNY'（外币已折算）。因此「仅 formal 有」常表示：
snapshot 里同 (日, 券) 存在 **外币** 行（如 USD），而不是 snapshot 缺行。

按 (report_date, instrument_code) 聚合市值后：
- 仅 formal 有（相对 CNY/CNX snapshot 聚合）
- 仅 snapshot 有
- 双边都有但金额不一致（|差|>容差）

用法:
  python scripts/diff_zqtz_formal_vs_snapshot.py --duckdb f:/MOSS-V3/data/moss.duckdb --start 2025-01-01 --end 2025-03-31
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


def _resolve_duckdb(arg: str) -> Path:
    p = (arg or "").strip()
    if p:
        return Path(p)
    env = (os.environ.get("MOSS_DUCKDB_PATH") or "").strip()
    if env:
        return Path(env)
    return (ROOT / "data" / "moss.duckdb").resolve()


AGG_CTE = """
WITH f AS (
  SELECT
    cast(report_date as date) AS d,
    upper(trim(coalesce(instrument_code, ''))) AS ic,
    sum(cast(market_value_amount as double)) AS mv,
    max(trim(coalesce(bond_type, ''))) AS bond_type_f,
    max(trim(coalesce(asset_class, ''))) AS asset_class_f
  FROM fact_formal_zqtz_balance_daily
  WHERE cast(report_date as date) BETWEEN ? AND ?
    AND currency_basis = 'CNY'
  GROUP BY 1, 2
),
s AS (
  SELECT
    cast(report_date as date) AS d,
    upper(trim(coalesce(instrument_code, ''))) AS ic,
    sum(cast(market_value_native as double)) AS mv,
    max(trim(coalesce(bond_type, ''))) AS bond_type_s,
    max(trim(coalesce(asset_class, ''))) AS asset_class_s
  FROM zqtz_bond_daily_snapshot
  WHERE cast(report_date as date) BETWEEN ? AND ?
    AND upper(trim(coalesce(currency_code, ''))) IN ('CNY', 'CNX')
  GROUP BY 1, 2
)
"""


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--duckdb", default="", help="默认 MOSS_DUCKDB_PATH 或 data/moss.duckdb")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--tol", type=float, default=0.01, help="双边金额视为相同的容差（元）")
    p.add_argument("--sample", type=int, default=25, help="每类最多打印多少条样本")
    args = p.parse_args()

    db = _resolve_duckdb(args.duckdb)
    if not db.exists():
        print(f"错误: 找不到 {db}", file=sys.stderr)
        return 2

    start, end = _parse_date(args.start), _parse_date(args.end)
    if start > end:
        start, end = end, start

    import duckdb

    conn = duckdb.connect(str(db), read_only=True)
    try:
        params = [start, end, start, end]

        only_f = conn.execute(
            AGG_CTE
            + """
SELECT count(*)::bigint FROM f
LEFT JOIN s ON f.d = s.d AND f.ic = s.ic
WHERE s.ic IS NULL
""",
            params,
        ).fetchone()[0]

        only_s = conn.execute(
            AGG_CTE
            + """
SELECT count(*)::bigint FROM s
LEFT JOIN f ON f.d = s.d AND f.ic = s.ic
WHERE f.ic IS NULL
""",
            params,
        ).fetchone()[0]

        both_diff = conn.execute(
            AGG_CTE
            + f"""
SELECT count(*)::bigint
FROM f
INNER JOIN s ON f.d = s.d AND f.ic = s.ic
WHERE abs(f.mv - s.mv) > {args.tol}
""",
            params,
        ).fetchone()[0]

        both_match = conn.execute(
            AGG_CTE
            + f"""
SELECT count(*)::bigint
FROM f
INNER JOIN s ON f.d = s.d AND f.ic = s.ic
WHERE abs(f.mv - s.mv) <= {args.tol}
""",
            params,
        ).fetchone()[0]

        sum_only_f = conn.execute(
            AGG_CTE
            + """
SELECT coalesce(sum(f.mv), 0)::double
FROM f
LEFT JOIN s ON f.d = s.d AND f.ic = s.ic
WHERE s.ic IS NULL
""",
            params,
        ).fetchone()[0]

        sum_only_s = conn.execute(
            AGG_CTE
            + """
SELECT coalesce(sum(s.mv), 0)::double
FROM s
LEFT JOIN f ON f.d = s.d AND f.ic = s.ic
WHERE f.ic IS NULL
""",
            params,
        ).fetchone()[0]

        sum_diff_both = conn.execute(
            AGG_CTE
            + f"""
SELECT coalesce(sum(f.mv - s.mv), 0)::double
FROM f
INNER JOIN s ON f.d = s.d AND f.ic = s.ic
WHERE abs(f.mv - s.mv) > {args.tol}
""",
            params,
        ).fetchone()[0]

        print(f"DuckDB: {db}")
        print(f"区间: {start} .. {end}  (instrument 粒度: 按日+券代码聚合后比较)")
        print(f"金额容差: {args.tol} 元\n")

        print("【汇总】（键 = report_date + instrument_code 聚合一行）")
        print(f"  仅 formal 有、snapshot 无: {only_f} 键, 市值合计(元) ≈ {sum_only_f:,.2f}")
        print(f"  仅 snapshot 有、formal 无: {only_s} 键, 市值合计(元) ≈ {sum_only_s:,.2f}")
        print(f"  双边都有但市值差 > {args.tol}: {both_diff} 键, (formal-snap) 合计差(元) ≈ {sum_diff_both:,.2f}")
        print(f"  双边都有且市值一致(<=容差): {both_match} 键")

        cls = conn.execute(
            """
WITH f AS (
  SELECT cast(report_date as date) AS d,
         upper(trim(coalesce(instrument_code, ''))) AS ic,
         sum(cast(market_value_amount as double)) AS mv
  FROM fact_formal_zqtz_balance_daily
  WHERE cast(report_date as date) BETWEEN ? AND ? AND currency_basis = 'CNY'
  GROUP BY 1, 2
),
s_cny AS (
  SELECT cast(report_date as date) AS d,
         upper(trim(coalesce(instrument_code, ''))) AS ic,
         sum(cast(market_value_native as double)) AS mv
  FROM zqtz_bond_daily_snapshot
  WHERE cast(report_date as date) BETWEEN ? AND ?
    AND upper(trim(coalesce(currency_code, ''))) IN ('CNY', 'CNX')
  GROUP BY 1, 2
),
s_any AS (
  SELECT cast(report_date as date) AS d,
         upper(trim(coalesce(instrument_code, ''))) AS ic,
         max(upper(trim(coalesce(currency_code, '')))) AS any_ccy,
         count(*)::bigint AS n_raw
  FROM zqtz_bond_daily_snapshot
  WHERE cast(report_date as date) BETWEEN ? AND ?
  GROUP BY 1, 2
)
SELECT
  count(*)::bigint AS only_f_vs_cny_snap,
  count(*) FILTER (WHERE s_any.ic IS NOT NULL)::bigint AS only_f_but_snap_has_row_any_ccy,
  count(*) FILTER (WHERE s_any.ic IS NULL)::bigint AS only_f_and_snap_truly_missing
FROM f
LEFT JOIN s_cny ON f.d = s_cny.d AND f.ic = s_cny.ic
LEFT JOIN s_any ON f.d = s_any.d AND f.ic = s_any.ic
WHERE s_cny.ic IS NULL
""",
            [start, end, start, end, start, end],
        ).fetchone()
        print("\n【口径核对】「仅 formal」相对 snapshot(CNY/CNX 聚合)时：")
        print(f"  此类键数: {cls[0]}")
        print(f"  其中 snapshot 仍有同键行（任意币种）: {cls[1]}  （多为外币原币，与 formal CNY 不应直接比原币金额）")
        print(f"  其中 snapshot 完全无同键行: {cls[2]}")

        yi = 1e8
        lim = max(0, int(args.sample))

        def dump(title: str, sql: str) -> None:
            rows = conn.execute(sql, params).fetchall()
            print(f"\n—— {title}（最多 {lim} 条）——")
            if not rows:
                print("  (无)")
                return
            for row in rows[:lim]:
                print("  " + " | ".join(str(x) for x in row))
            if len(rows) > lim:
                print(f"  ... 共 {len(rows)} 条，省略 {len(rows) - lim} 条")

        dump(
            "仅 formal（样例: 日期, 券代码, formal亿, bond_type, asset_class）",
            AGG_CTE
            + """
SELECT f.d, f.ic, f.mv / 1e8, f.bond_type_f, f.asset_class_f
FROM f
LEFT JOIN s ON f.d = s.d AND f.ic = s.ic
WHERE s.ic IS NULL
ORDER BY abs(f.mv) DESC
""",
        )

        dump(
            "仅 snapshot（样例: 日期, 券代码, snap亿, bond_type, asset_class）",
            AGG_CTE
            + """
SELECT s.d, s.ic, s.mv / 1e8, s.bond_type_s, s.asset_class_s
FROM s
LEFT JOIN f ON f.d = s.d AND f.ic = s.ic
WHERE f.ic IS NULL
ORDER BY abs(s.mv) DESC
""",
        )

        dump(
            f"双边有、市值差>容差（样例: 日期, 券代码, formal亿, snap亿, 差亿）",
            AGG_CTE
            + f"""
SELECT f.d, f.ic, f.mv / 1e8, s.mv / 1e8, (f.mv - s.mv) / 1e8
FROM f
INNER JOIN s ON f.d = s.d AND f.ic = s.ic
WHERE abs(f.mv - s.mv) > {args.tol}
ORDER BY abs(f.mv - s.mv) DESC
""",
        )

        # 若「仅 formal」条数很少，再按 bond_type 汇总仅 formal 的金额
        by_bt = conn.execute(
            AGG_CTE
            + """
SELECT coalesce(nullif(trim(f.bond_type_f), ''), '(空)') AS bt,
       count(*)::bigint AS n_keys,
       sum(f.mv)::double AS sum_mv
FROM f
LEFT JOIN s ON f.d = s.d AND f.ic = s.ic
WHERE s.ic IS NULL
GROUP BY 1
ORDER BY sum_mv DESC
LIMIT 20
""",
            params,
        ).fetchall()
        print("\n—— 仅 formal 键：按 bond_type 汇总 Top20 ——")
        for bt, n, sm in by_bt:
            print(f"  {bt}: keys={n}, sum={sm/1e8:.4f}亿")

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
