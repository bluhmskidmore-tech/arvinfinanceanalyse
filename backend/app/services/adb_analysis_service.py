"""
日均资产负债（ADB）分析 — DuckDB 读模型，口径对齐 V1 `adb_service` / `analysis_service.get_adb_comparison`。

- 债券：ZQTZ `zqtz_bond_daily_snapshot`，资产=非发行类（`NOT is_issuance_like`），负债=发行类。
- 同业：TYWL `tyw_interbank_daily_snapshot`，`position_side` 含「资产」/ asset 为资产端，否则负债端。
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from backend.app.core_finance.adb_interbank_labels import map_ib_category
from backend.app.core_finance.adb_rate_normalize import normalize_rate_series_pd
from backend.app.governance.settings import get_settings

IB_ASSET_PRED = (
    "(instr(lower(coalesce(position_side, '')), 'asset') > 0 "
    "OR instr(coalesce(position_side, ''), '资产') > 0)"
)


def _conn_ro(path: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(path, read_only=True)


def _table_exists(conn: duckdb.DuckDBPyConnection, name: str) -> bool:
    row = conn.execute(
        """
        select 1 from information_schema.tables
        where table_name = ? limit 1
        """,
        [name],
    ).fetchone()
    return row is not None


def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _stable_factor(key: str, low: Decimal = Decimal("0.85"), high: Decimal = Decimal("1.15")) -> Decimal:
    raw = (key or "").encode("utf-8", errors="ignore")
    h = hashlib.md5(raw).hexdigest()
    n = int(h[:8], 16)
    u = Decimal(n) / Decimal(0xFFFFFFFF)
    return low + (high - low) * u


def _clean_cat(v: object) -> str:
    if v is None:
        return "其它"
    s = str(v).strip()
    return s if s else "其它"


def calculate_adb(duckdb_path: str, start_date: date, end_date: date) -> dict[str, Any]:
    if not Path(duckdb_path).exists():
        return _empty_adb_response()

    num_days = (end_date - start_date).days + 1
    all_days = [start_date + timedelta(days=i) for i in range(num_days)]

    conn = _conn_ro(duckdb_path)
    try:
        has_bonds = _table_exists(conn, "zqtz_bond_daily_snapshot")
        has_ib = _table_exists(conn, "tyw_interbank_daily_snapshot")
        if not has_bonds and not has_ib:
            return _empty_adb_response()

        bonds_assets: dict[date, Decimal] = {}
        bonds_liab: dict[date, Decimal] = {}
        ib_assets: dict[date, Decimal] = {}
        ib_liab: dict[date, Decimal] = {}

        if has_bonds:
            for rd, mv in conn.execute(
                f"""
                select report_date, sum(coalesce(market_value_native, 0))
                from zqtz_bond_daily_snapshot
                where report_date between ? and ?
                  and not coalesce(is_issuance_like, false)
                group by 1
                """,
                [start_date, end_date],
            ).fetchall():
                bonds_assets[rd] = Decimal(str(mv or 0))

            for rd, mv in conn.execute(
                f"""
                select report_date, sum(coalesce(market_value_native, 0))
                from zqtz_bond_daily_snapshot
                where report_date between ? and ?
                  and coalesce(is_issuance_like, false)
                group by 1
                """,
                [start_date, end_date],
            ).fetchall():
                bonds_liab[rd] = Decimal(str(mv or 0))

        if has_ib:
            for rd, amt in conn.execute(
                f"""
                select report_date, sum(coalesce(principal_native, 0))
                from tyw_interbank_daily_snapshot
                where report_date between ? and ?
                  and {IB_ASSET_PRED}
                group by 1
                """,
                [start_date, end_date],
            ).fetchall():
                ib_assets[rd] = Decimal(str(amt or 0))

            for rd, amt in conn.execute(
                f"""
                select report_date, sum(coalesce(principal_native, 0))
                from tyw_interbank_daily_snapshot
                where report_date between ? and ?
                  and not ({IB_ASSET_PRED})
                group by 1
                """,
                [start_date, end_date],
            ).fetchall():
                ib_liab[rd] = Decimal(str(amt or 0))
    finally:
        conn.close()

    daily_assets: dict[date, Decimal] = {}
    daily_liab: dict[date, Decimal] = {}
    daily_total_assets_sum = Decimal("0")
    daily_total_liab_sum = Decimal("0")

    for d in all_days:
        a = bonds_assets.get(d, Decimal("0")) + ib_assets.get(d, Decimal("0"))
        l = bonds_liab.get(d, Decimal("0")) + ib_liab.get(d, Decimal("0"))
        daily_assets[d] = a
        daily_liab[d] = l
        daily_total_assets_sum += a
        daily_total_liab_sum += l

    nd = Decimal(str(num_days)) if num_days else Decimal("0")
    total_avg_assets = (daily_total_assets_sum / nd) if nd else Decimal("0")
    total_avg_liab = (daily_total_liab_sum / nd) if nd else Decimal("0")
    end_spot_assets = daily_assets.get(end_date, Decimal("0"))
    end_spot_liab = daily_liab.get(end_date, Decimal("0"))

    trend: list[dict[str, float]] = []
    window: list[Decimal] = []
    window_sum = Decimal("0")
    for d in all_days:
        spot = daily_assets[d]
        window.append(spot)
        window_sum += spot
        if len(window) > 30:
            window_sum -= window.pop(0)
        wn = len(window)
        ma = (window_sum / Decimal(str(wn))) if wn else Decimal("0")
        trend.append(
            {
                "date": d.strftime("%Y-%m-%d"),
                "daily_balance": float(spot),
                "moving_average_30d": float(ma),
            }
        )

    breakdown = _adb_breakdown(duckdb_path, start_date, end_date, num_days)
    return {
        "summary": {
            "total_avg_assets": float(total_avg_assets),
            "total_avg_liabilities": float(total_avg_liab),
            "end_spot_assets": float(end_spot_assets),
            "end_spot_liabilities": float(end_spot_liab),
        },
        "trend": trend,
        "breakdown": breakdown,
    }


def _adb_breakdown(duckdb_path: str, start_date: date, end_date: date, num_days: int) -> list[dict[str, Any]]:
    if not Path(duckdb_path).exists() or num_days <= 0:
        return []
    conn = _conn_ro(duckdb_path)
    breakdown_sum: dict[tuple[str, str], Decimal] = {}
    try:
        if _table_exists(conn, "zqtz_bond_daily_snapshot"):
            for _, sub, mv in conn.execute(
                """
                select report_date,
                       coalesce(nullif(trim(cast(bond_type as varchar)), ''), '债券-其他') as sub_type,
                       sum(coalesce(market_value_native, 0))
                from zqtz_bond_daily_snapshot
                where report_date between ? and ?
                  and not coalesce(is_issuance_like, false)
                group by report_date, sub_type
                """,
                [start_date, end_date],
            ).fetchall():
                cat = str(sub or "债券-其他")
                k = (cat, "Asset")
                breakdown_sum[k] = breakdown_sum.get(k, Decimal("0")) + Decimal(str(mv or 0))

            for _, sub, mv in conn.execute(
                """
                select report_date,
                       coalesce(nullif(trim(cast(bond_type as varchar)), ''), '其他') as sub_type,
                       sum(coalesce(market_value_native, 0))
                from zqtz_bond_daily_snapshot
                where report_date between ? and ?
                  and coalesce(is_issuance_like, false)
                group by report_date, sub_type
                """,
                [start_date, end_date],
            ).fetchall():
                cat = f"发行债券-{(sub or '其他')}"
                k = (cat, "Liability")
                breakdown_sum[k] = breakdown_sum.get(k, Decimal("0")) + Decimal(str(mv or 0))

        if _table_exists(conn, "tyw_interbank_daily_snapshot"):
            for _, pt, amt in conn.execute(
                f"""
                select report_date, product_type, sum(coalesce(principal_native, 0))
                from tyw_interbank_daily_snapshot
                where report_date between ? and ? and {IB_ASSET_PRED}
                group by report_date, product_type
                """,
                [start_date, end_date],
            ).fetchall():
                side = "Asset"
                cat = map_ib_category(str(pt) if pt is not None else None, side)
                k = (cat, side)
                breakdown_sum[k] = breakdown_sum.get(k, Decimal("0")) + Decimal(str(amt or 0))

            for _, pt, amt in conn.execute(
                f"""
                select report_date, product_type, sum(coalesce(principal_native, 0))
                from tyw_interbank_daily_snapshot
                where report_date between ? and ? and not ({IB_ASSET_PRED})
                group by report_date, product_type
                """,
                [start_date, end_date],
            ).fetchall():
                side = "Liability"
                cat = map_ib_category(str(pt) if pt is not None else None, side)
                k = (cat, side)
                breakdown_sum[k] = breakdown_sum.get(k, Decimal("0")) + Decimal(str(amt or 0))
    finally:
        conn.close()

    nd = Decimal(str(num_days))
    out: list[dict[str, Any]] = []
    for (cat, side), total in sorted(breakdown_sum.items(), key=lambda x: float(x[1] or 0), reverse=True):
        avg_val = (total / nd) if nd else Decimal("0")
        out.append({"category": cat, "side": side, "avg_balance": float(avg_val)})
    return out


def _empty_adb_response() -> dict[str, Any]:
    return {
        "summary": {
            "total_avg_assets": 0.0,
            "total_avg_liabilities": 0.0,
            "end_spot_assets": 0.0,
            "end_spot_liabilities": 0.0,
        },
        "trend": [],
        "breakdown": [],
    }


def get_adb_comparison(
    duckdb_path: str,
    start_date: date,
    end_date: date,
    top_n: int = 20,
    simulate_if_single_snapshot: bool = True,
) -> dict[str, Any]:
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    num_days = int((end_date - start_date).days) + 1
    num_days_dec = Decimal(str(max(num_days, 1)))

    def empty_response(detail: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "report_date": end_date.strftime("%Y-%m-%d"),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "num_days": num_days,
            "simulated": False,
            "total_spot_assets": 0.0,
            "total_avg_assets": 0.0,
            "total_spot_liabilities": 0.0,
            "total_avg_liabilities": 0.0,
            "asset_yield": None,
            "liability_cost": None,
            "net_interest_margin": None,
            "assets_breakdown": [],
            "liabilities_breakdown": [],
            "assets": [],
            "liabilities": [],
        }
        if detail:
            payload["detail"] = detail
        return payload

    if not Path(duckdb_path).exists():
        return empty_response()

    conn = _conn_ro(duckdb_path)
    spot_assets: dict[str, Decimal] = {}
    spot_liab: dict[str, Decimal] = {}
    sum_assets: dict[str, Decimal] = {}
    sum_liab: dict[str, Decimal] = {}

    def add(m: dict[str, Decimal], k: str, v: object) -> None:
        kk = _clean_cat(k)
        vv = Decimal(str(v or 0))
        m[kk] = m.get(kk, Decimal("0")) + vv

    try:
        has_bonds = _table_exists(conn, "zqtz_bond_daily_snapshot")
        has_ib = _table_exists(conn, "tyw_interbank_daily_snapshot")

        if has_bonds:
            for cat, mv in conn.execute(
                """
                select coalesce(nullif(trim(cast(bond_type as varchar)), ''), '其它'),
                       sum(coalesce(market_value_native, 0))
                from zqtz_bond_daily_snapshot
                where report_date = ?
                  and not coalesce(is_issuance_like, false)
                group by 1
                """,
                [end_date],
            ).fetchall():
                add(spot_assets, str(cat), mv)

            for cat, mv in conn.execute(
                """
                select coalesce(nullif(trim(cast(bond_type as varchar)), ''), '其它'),
                       sum(coalesce(market_value_native, 0))
                from zqtz_bond_daily_snapshot
                where report_date = ?
                  and coalesce(is_issuance_like, false)
                group by 1
                """,
                [end_date],
            ).fetchall():
                add(spot_liab, str(cat), mv)

            for _, cat, mv in conn.execute(
                """
                select report_date,
                       coalesce(nullif(trim(cast(bond_type as varchar)), ''), '其它'),
                       sum(coalesce(market_value_native, 0))
                from zqtz_bond_daily_snapshot
                where report_date between ? and ?
                  and not coalesce(is_issuance_like, false)
                group by 1, 2
                """,
                [start_date, end_date],
            ).fetchall():
                add(sum_assets, str(cat), mv)

            for _, cat, mv in conn.execute(
                """
                select report_date,
                       coalesce(nullif(trim(cast(bond_type as varchar)), ''), '其它'),
                       sum(coalesce(market_value_native, 0))
                from zqtz_bond_daily_snapshot
                where report_date between ? and ?
                  and coalesce(is_issuance_like, false)
                group by 1, 2
                """,
                [start_date, end_date],
            ).fetchall():
                add(sum_liab, str(cat), mv)

        if has_ib:
            for cat, amt in conn.execute(
                f"""
                select coalesce(nullif(trim(cast(product_type as varchar)), ''), '其它'),
                       sum(coalesce(principal_native, 0))
                from tyw_interbank_daily_snapshot
                where report_date = ? and {IB_ASSET_PRED}
                group by 1
                """,
                [end_date],
            ).fetchall():
                add(spot_assets, str(cat), amt)

            for cat, amt in conn.execute(
                f"""
                select coalesce(nullif(trim(cast(product_type as varchar)), ''), '其它'),
                       sum(coalesce(principal_native, 0))
                from tyw_interbank_daily_snapshot
                where report_date = ? and not ({IB_ASSET_PRED})
                group by 1
                """,
                [end_date],
            ).fetchall():
                add(spot_liab, str(cat), amt)

            for _, cat, amt in conn.execute(
                f"""
                select report_date,
                       coalesce(nullif(trim(cast(product_type as varchar)), ''), '其它'),
                       sum(coalesce(principal_native, 0))
                from tyw_interbank_daily_snapshot
                where report_date between ? and ? and {IB_ASSET_PRED}
                group by 1, 2
                """,
                [start_date, end_date],
            ).fetchall():
                add(sum_assets, str(cat), amt)

            for _, cat, amt in conn.execute(
                f"""
                select report_date,
                       coalesce(nullif(trim(cast(product_type as varchar)), ''), '其它'),
                       sum(coalesce(principal_native, 0))
                from tyw_interbank_daily_snapshot
                where report_date between ? and ? and not ({IB_ASSET_PRED})
                group by 1, 2
                """,
                [start_date, end_date],
            ).fetchall():
                add(sum_liab, str(cat), amt)
    finally:
        conn.close()

    simulated = bool(simulate_if_single_snapshot and num_days <= 1)

    def build(side: str, spot_map: dict[str, Decimal], sum_map: dict[str, Decimal]) -> list[dict[str, float]]:
        cats = set(spot_map.keys()) | set(sum_map.keys())
        out: list[dict[str, float]] = []
        for cat in cats:
            c = _clean_cat(cat)
            spot_v = spot_map.get(c, Decimal("0")) or Decimal("0")
            if simulated:
                f = _stable_factor(f"{side}:{end_date}:{c}")
                avg_v = spot_v * f
            else:
                avg_v = (sum_map.get(c, Decimal("0")) or Decimal("0")) / num_days_dec
            dev = spot_v - avg_v
            if spot_v == 0 and avg_v == 0:
                continue
            out.append(
                {
                    "category": c,
                    "spot": float(spot_v),
                    "avg": float(avg_v),
                    "deviation": float(dev),
                }
            )
        out.sort(key=lambda x: (abs(x.get("deviation") or 0.0), x.get("spot") or 0.0), reverse=True)
        return out[: max(int(top_n), 0)]

    assets = build("Asset", spot_assets, sum_assets)
    liabilities = build("Liability", spot_liab, sum_liab)
    total_spot_assets = float(sum(item["spot"] for item in assets))
    total_avg_assets = float(sum(item["avg"] for item in assets))
    total_spot_liabilities = float(sum(item["spot"] for item in liabilities))
    total_avg_liabilities = float(sum(item["avg"] for item in liabilities))

    asset_rate_map: dict[str, float | None] = {}
    liability_rate_map: dict[str, float | None] = {}
    asset_yield: float | None = None
    liability_cost: float | None = None

    conn2 = _conn_ro(duckdb_path)
    try:
        bonds_df, interbank_df = _get_adb_raw_data(conn2, start_date, end_date)
    finally:
        conn2.close()

    asset_frames: list[pd.DataFrame] = []
    liability_frames: list[pd.DataFrame] = []

    if not bonds_df.empty:
        issued_mask = (
            bonds_df["is_issuance_like"].fillna(False).astype(bool)
            if "is_issuance_like" in bonds_df.columns
            else pd.Series(False, index=bonds_df.index)
        )
        if "asset_class" in bonds_df.columns:
            issued_mask = issued_mask | bonds_df["asset_class"].astype(str).str.contains("发行", na=False)

        bonds_assets_df = bonds_df[~issued_mask].copy()
        if not bonds_assets_df.empty:
            bonds_assets_df["category"] = bonds_assets_df["sub_type"].apply(_clean_cat)
            bonds_assets_df["balance"] = pd.to_numeric(bonds_assets_df["market_value"], errors="coerce").fillna(0.0)
            bonds_assets_df["rate_decimal"] = np.where(
                pd.notna(bonds_assets_df["yield_to_maturity"]) & (bonds_assets_df["yield_to_maturity"] != 0),
                normalize_rate_series_pd(bonds_assets_df["yield_to_maturity"], "yield_to_maturity"),
                np.where(
                    pd.notna(bonds_assets_df["coupon_rate"]) & (bonds_assets_df["coupon_rate"] != 0),
                    normalize_rate_series_pd(bonds_assets_df["coupon_rate"], "coupon_rate"),
                    np.where(
                        pd.notna(bonds_assets_df["interest_rate"]) & (bonds_assets_df["interest_rate"] != 0),
                        normalize_rate_series_pd(bonds_assets_df["interest_rate"], "interest_rate"),
                        0.0,
                    ),
                ),
            )
            bonds_assets_df["weighted"] = bonds_assets_df["balance"] * bonds_assets_df["rate_decimal"]
            asset_frames.append(bonds_assets_df[["category", "balance", "weighted"]])

        bonds_liab_df = bonds_df[issued_mask].copy()
        if not bonds_liab_df.empty:
            bonds_liab_df["category"] = bonds_liab_df["sub_type"].apply(_clean_cat)
            bonds_liab_df["balance"] = pd.to_numeric(bonds_liab_df["market_value"], errors="coerce").fillna(0.0)
            bonds_liab_df["rate_decimal"] = np.where(
                pd.notna(bonds_liab_df["coupon_rate"]) & (bonds_liab_df["coupon_rate"] != 0),
                normalize_rate_series_pd(bonds_liab_df["coupon_rate"], "coupon_rate"),
                np.where(
                    pd.notna(bonds_liab_df["interest_rate"]) & (bonds_liab_df["interest_rate"] != 0),
                    normalize_rate_series_pd(bonds_liab_df["interest_rate"], "interest_rate"),
                    0.0,
                ),
            )
            bonds_liab_df["weighted"] = bonds_liab_df["balance"] * bonds_liab_df["rate_decimal"]
            liability_frames.append(bonds_liab_df[["category", "balance", "weighted"]])

    if not interbank_df.empty:
        ib_assets_df = interbank_df[interbank_df["direction"] == "ASSET"].copy()
        if not ib_assets_df.empty:
            ib_assets_df["category"] = ib_assets_df["product_type"].apply(_clean_cat)
            ib_assets_df["balance"] = pd.to_numeric(ib_assets_df["amount"], errors="coerce").fillna(0.0)
            ib_assets_df["rate_decimal"] = normalize_rate_series_pd(ib_assets_df["interest_rate"], "interbank_interest_rate")
            ib_assets_df["weighted"] = ib_assets_df["balance"] * ib_assets_df["rate_decimal"]
            asset_frames.append(ib_assets_df[["category", "balance", "weighted"]])

        ib_liab_df = interbank_df[interbank_df["direction"] == "LIABILITY"].copy()
        if not ib_liab_df.empty:
            ib_liab_df["category"] = ib_liab_df["product_type"].apply(_clean_cat)
            ib_liab_df["balance"] = pd.to_numeric(ib_liab_df["amount"], errors="coerce").fillna(0.0)
            ib_liab_df["rate_decimal"] = normalize_rate_series_pd(ib_liab_df["interest_rate"], "interbank_interest_rate")
            ib_liab_df["weighted"] = ib_liab_df["balance"] * ib_liab_df["rate_decimal"]
            liability_frames.append(ib_liab_df[["category", "balance", "weighted"]])

    def build_rate_map(
        frames: list[pd.DataFrame],
    ) -> tuple[dict[str, float | None], float | None]:
        if not frames:
            return {}, None
        merged = pd.concat(frames, ignore_index=True)
        if merged.empty:
            return {}, None
        grouped = (
            merged.groupby("category", dropna=False)[["balance", "weighted"]]
            .sum()
            .reset_index()
        )
        rate_map: dict[str, float | None] = {}
        total_balance = float(grouped["balance"].sum())
        total_weighted = float(grouped["weighted"].sum())
        for _, row in grouped.iterrows():
            category = _clean_cat(row["category"])
            balance = float(row["balance"])
            weighted = float(row["weighted"])
            rate_map[category] = round(weighted / balance * 100, 4) if balance > 0 else None
        total_rate = round(total_weighted / total_balance * 100, 4) if total_balance > 0 else None
        return rate_map, total_rate

    asset_rate_map, asset_yield = build_rate_map(asset_frames)
    liability_rate_map, liability_cost = build_rate_map(liability_frames)
    net_interest_margin = (
        round(asset_yield - liability_cost, 4)
        if asset_yield is not None and liability_cost is not None
        else None
    )

    def enrich_breakdown(
        rows: list[dict[str, float]],
        total_avg: float,
        rate_map: dict[str, float | None],
    ) -> list[dict[str, Any]]:
        breakdown: list[dict[str, Any]] = []
        for row in rows:
            avg_balance = float(row["avg"])
            breakdown.append(
                {
                    "category": row["category"],
                    "spot_balance": float(row["spot"]),
                    "avg_balance": avg_balance,
                    "deviation": float(row["deviation"]),
                    "proportion": round(avg_balance / total_avg * 100, 2) if total_avg > 0 else 0.0,
                    "weighted_rate": rate_map.get(row["category"]),
                }
            )
        return breakdown

    return {
        "report_date": end_date.strftime("%Y-%m-%d"),
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "num_days": num_days,
        "simulated": simulated,
        "total_spot_assets": total_spot_assets,
        "total_avg_assets": total_avg_assets,
        "total_spot_liabilities": total_spot_liabilities,
        "total_avg_liabilities": total_avg_liabilities,
        "asset_yield": asset_yield,
        "liability_cost": liability_cost,
        "net_interest_margin": net_interest_margin,
        "assets_breakdown": enrich_breakdown(assets, total_avg_assets, asset_rate_map),
        "liabilities_breakdown": enrich_breakdown(liabilities, total_avg_liabilities, liability_rate_map),
        "assets": assets,
        "liabilities": liabilities,
    }


def _get_adb_raw_data(conn: duckdb.DuckDBPyConnection, start_date: date, end_date: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    bonds_df = pd.DataFrame()
    ib_df = pd.DataFrame()
    if _table_exists(conn, "zqtz_bond_daily_snapshot"):
        bonds_df = conn.execute(
            """
            select report_date,
                   market_value_native as market_value,
                   ytm_value as yield_to_maturity,
                   coupon_rate,
                   cast(0.0 as double) as interest_rate,
                   asset_class,
                   bond_type as sub_type,
                   is_issuance_like
            from zqtz_bond_daily_snapshot
            where report_date between ? and ?
            """,
            [start_date, end_date],
        ).df()

    if _table_exists(conn, "tyw_interbank_daily_snapshot"):
        ib_df = conn.execute(
            f"""
            select report_date,
                   principal_native as amount,
                   funding_cost_rate as interest_rate,
                   product_type,
                   case when {IB_ASSET_PRED} then 'ASSET' else 'LIABILITY' end as direction
            from tyw_interbank_daily_snapshot
            where report_date between ? and ?
            """,
            [start_date, end_date],
        ).df()

    if not bonds_df.empty:
        bonds_df["report_date"] = pd.to_datetime(bonds_df["report_date"])
        for col in ("market_value", "yield_to_maturity", "coupon_rate", "interest_rate"):
            bonds_df[col] = pd.to_numeric(bonds_df[col], errors="coerce").fillna(0)

    if not ib_df.empty:
        ib_df["report_date"] = pd.to_datetime(ib_df["report_date"])
        ib_df["amount"] = pd.to_numeric(ib_df["amount"], errors="coerce").fillna(0)
        ib_df["interest_rate"] = pd.to_numeric(ib_df["interest_rate"], errors="coerce").fillna(0)

    return bonds_df, ib_df


def calculate_monthly_adb(duckdb_path: str, year: int) -> dict[str, Any]:
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    today = date.today()
    if end_date > today:
        end_date = today

    empty = {
        "year": year,
        "months": [],
        "ytd_avg_assets": 0.0,
        "ytd_avg_liabilities": 0.0,
        "ytd_asset_yield": None,
        "ytd_liability_cost": None,
        "ytd_net_interest_margin": None,
        "unit": "percent",
    }

    if not Path(duckdb_path).exists():
        return empty

    conn = _conn_ro(duckdb_path)
    try:
        bonds_df, interbank_df = _get_adb_raw_data(conn, start_date, end_date)
    finally:
        conn.close()

    if bonds_df.empty and interbank_df.empty:
        return empty

    bonds_assets_df = pd.DataFrame()
    bonds_liab_df = pd.DataFrame()

    if not bonds_df.empty:
        issued_mask = (
            bonds_df["is_issuance_like"].fillna(False).astype(bool)
            if "is_issuance_like" in bonds_df.columns
            else pd.Series(False, index=bonds_df.index)
        )
        if "asset_class" in bonds_df.columns:
            issued_mask = issued_mask | bonds_df["asset_class"].astype(str).str.contains("发行", na=False)

        bonds_assets_df = bonds_df[~issued_mask].copy()
        bonds_assets_df["rate_decimal"] = np.where(
            pd.notna(bonds_assets_df["yield_to_maturity"]) & (bonds_assets_df["yield_to_maturity"] != 0),
            normalize_rate_series_pd(bonds_assets_df["yield_to_maturity"], "yield_to_maturity"),
            np.where(
                pd.notna(bonds_assets_df["coupon_rate"]) & (bonds_assets_df["coupon_rate"] != 0),
                normalize_rate_series_pd(bonds_assets_df["coupon_rate"], "coupon_rate"),
                np.where(
                    pd.notna(bonds_assets_df["interest_rate"]) & (bonds_assets_df["interest_rate"] != 0),
                    normalize_rate_series_pd(bonds_assets_df["interest_rate"], "interest_rate"),
                    0.0,
                ),
            ),
        )
        bonds_assets_df["weighted"] = bonds_assets_df["market_value"] * bonds_assets_df["rate_decimal"]

        bonds_liab_df = bonds_df[issued_mask].copy()
        bonds_liab_df["rate_decimal"] = np.where(
            pd.notna(bonds_liab_df["coupon_rate"]) & (bonds_liab_df["coupon_rate"] != 0),
            normalize_rate_series_pd(bonds_liab_df["coupon_rate"], "coupon_rate"),
            np.where(
                pd.notna(bonds_liab_df["interest_rate"]) & (bonds_liab_df["interest_rate"] != 0),
                normalize_rate_series_pd(bonds_liab_df["interest_rate"], "interest_rate"),
                0.0,
            ),
        )
        bonds_liab_df["weighted"] = bonds_liab_df["market_value"] * bonds_liab_df["rate_decimal"]

    ib_assets_df = pd.DataFrame()
    ib_liab_df = pd.DataFrame()
    if not interbank_df.empty:
        ib_assets_df = interbank_df[interbank_df["direction"] == "ASSET"].copy()
        ib_assets_df["rate_decimal"] = normalize_rate_series_pd(ib_assets_df["interest_rate"], "interbank_interest_rate")
        ib_assets_df["weighted"] = ib_assets_df["amount"] * ib_assets_df["rate_decimal"]

        ib_liab_df = interbank_df[interbank_df["direction"] == "LIABILITY"].copy()
        ib_liab_df["rate_decimal"] = normalize_rate_series_pd(ib_liab_df["interest_rate"], "interbank_interest_rate")
        ib_liab_df["weighted"] = ib_liab_df["amount"] * ib_liab_df["rate_decimal"]

    all_dates: set[date] = set()
    if not bonds_df.empty:
        all_dates.update(bonds_df["report_date"].dt.date.unique())
    if not interbank_df.empty:
        all_dates.update(interbank_df["report_date"].dt.date.unique())

    if not all_dates:
        return empty

    all_dates_series = pd.Series(sorted(all_dates))
    all_dates_series = pd.to_datetime(all_dates_series)
    all_dates_df = pd.DataFrame({"report_date": all_dates_series})
    all_dates_df["year_month"] = all_dates_df["report_date"].dt.to_period("M")
    available_months = sorted(all_dates_df["year_month"].unique())

    months_data: list[dict[str, Any]] = []
    prev_avg_assets: float | None = None
    prev_avg_liabilities: float | None = None

    ytd_total_assets = Decimal("0")
    ytd_total_liabilities = Decimal("0")
    ytd_assets_weighted = Decimal("0")
    ytd_liab_weighted = Decimal("0")
    ytd_days = 0

    conn2 = _conn_ro(duckdb_path)
    try:
        for month_period in available_months:
            month = month_period.month
            month_start = month_period.start_time.date()
            month_end = month_period.end_time.date()
            if month_start > today:
                continue
            if month_end > today:
                month_end = today

            mb_a = (
                bonds_assets_df[
                    (bonds_assets_df["report_date"].dt.date >= month_start)
                    & (bonds_assets_df["report_date"].dt.date <= month_end)
                ].copy()
                if not bonds_assets_df.empty
                else pd.DataFrame()
            )
            mb_l = (
                bonds_liab_df[
                    (bonds_liab_df["report_date"].dt.date >= month_start)
                    & (bonds_liab_df["report_date"].dt.date <= month_end)
                ].copy()
                if not bonds_liab_df.empty
                else pd.DataFrame()
            )
            m_ib_a = (
                ib_assets_df[
                    (ib_assets_df["report_date"].dt.date >= month_start)
                    & (ib_assets_df["report_date"].dt.date <= month_end)
                ].copy()
                if not ib_assets_df.empty
                else pd.DataFrame()
            )
            m_ib_l = (
                ib_liab_df[
                    (ib_liab_df["report_date"].dt.date >= month_start)
                    & (ib_liab_df["report_date"].dt.date <= month_end)
                ].copy()
                if not ib_liab_df.empty
                else pd.DataFrame()
            )

            all_month_dates: set[date] = set()
            if not mb_a.empty:
                all_month_dates.update(mb_a["report_date"].dt.date.unique())
            if not mb_l.empty:
                all_month_dates.update(mb_l["report_date"].dt.date.unique())
            if not m_ib_a.empty:
                all_month_dates.update(m_ib_a["report_date"].dt.date.unique())
            if not m_ib_l.empty:
                all_month_dates.update(m_ib_l["report_date"].dt.date.unique())

            if len(all_month_dates) == 0:
                continue

            num_days = len(all_month_dates)

            daily_assets_data: list[pd.DataFrame] = []
            if not mb_a.empty:
                bonds_assets_daily = mb_a.groupby("report_date").agg({"market_value": "sum", "weighted": "sum"}).reset_index()
                bonds_assets_daily["type"] = "bonds"
                daily_assets_data.append(bonds_assets_daily[["report_date", "market_value", "weighted", "type"]])

            if not m_ib_a.empty:
                ib_a_daily = m_ib_a.groupby("report_date").agg({"amount": "sum", "weighted": "sum"}).reset_index()
                ib_a_daily.rename(columns={"amount": "market_value"}, inplace=True)
                ib_a_daily["type"] = "interbank"
                daily_assets_data.append(ib_a_daily[["report_date", "market_value", "weighted", "type"]])

            if daily_assets_data:
                daily_a = pd.concat(daily_assets_data, ignore_index=True)
                daily_a_agg = daily_a.groupby("report_date").agg({"market_value": "sum", "weighted": "sum"}).reset_index()
                total_assets = float(daily_a_agg["market_value"].sum())
                total_assets_weighted = float(daily_a_agg["weighted"].sum())
            else:
                total_assets = 0.0
                total_assets_weighted = 0.0

            daily_liab_data: list[pd.DataFrame] = []
            if not mb_l.empty:
                bonds_l_daily = mb_l.groupby("report_date").agg({"market_value": "sum", "weighted": "sum"}).reset_index()
                bonds_l_daily["type"] = "bonds"
                daily_liab_data.append(bonds_l_daily[["report_date", "market_value", "weighted", "type"]])

            if not m_ib_l.empty:
                ib_l_daily = m_ib_l.groupby("report_date").agg({"amount": "sum", "weighted": "sum"}).reset_index()
                ib_l_daily.rename(columns={"amount": "market_value"}, inplace=True)
                ib_l_daily["type"] = "interbank"
                daily_liab_data.append(ib_l_daily[["report_date", "market_value", "weighted", "type"]])

            if daily_liab_data:
                daily_l = pd.concat(daily_liab_data, ignore_index=True)
                daily_l_agg = daily_l.groupby("report_date").agg({"market_value": "sum", "weighted": "sum"}).reset_index()
                total_liab = float(daily_l_agg["market_value"].sum())
                total_liab_weighted = float(daily_l_agg["weighted"].sum())
            else:
                total_liab = 0.0
                total_liab_weighted = 0.0

            if total_assets == 0 and total_liab == 0:
                continue

            avg_assets = total_assets / num_days if num_days > 0 else 0.0
            avg_liab = total_liab / num_days if num_days > 0 else 0.0

            breakdown_assets_dict: dict[str, dict[str, float]] = {}
            if not mb_a.empty:
                bonds_subtype_daily = mb_a.groupby(["report_date", "sub_type"]).agg(
                    {"market_value": "sum", "weighted": "sum"}
                ).reset_index()
                bonds_subtype_agg = bonds_subtype_daily.groupby("sub_type").agg(
                    {"market_value": "sum", "weighted": "sum"}
                ).reset_index()
                for _, row in bonds_subtype_agg.iterrows():
                    cat = row["sub_type"] if pd.notna(row["sub_type"]) else "债券-其他"
                    breakdown_assets_dict.setdefault(cat, {"total_mv": 0.0, "total_weighted": 0.0})
                    breakdown_assets_dict[cat]["total_mv"] += float(row["market_value"])
                    breakdown_assets_dict[cat]["total_weighted"] += float(row["weighted"])

            if not m_ib_a.empty:
                ib_type_daily = m_ib_a.groupby(["report_date", "product_type"]).agg(
                    {"amount": "sum", "weighted": "sum"}
                ).reset_index()
                ib_type_agg = ib_type_daily.groupby("product_type").agg({"amount": "sum", "weighted": "sum"}).reset_index()
                for _, row in ib_type_agg.iterrows():
                    pt = row["product_type"] if pd.notna(row["product_type"]) else "其他"
                    cat = f"同业-{pt}"
                    breakdown_assets_dict.setdefault(cat, {"total_mv": 0.0, "total_weighted": 0.0})
                    breakdown_assets_dict[cat]["total_mv"] += float(row["amount"])
                    breakdown_assets_dict[cat]["total_weighted"] += float(row["weighted"])

            breakdown_liab_dict: dict[str, dict[str, float]] = {}
            if not m_ib_l.empty:
                ib_lt_daily = m_ib_l.groupby(["report_date", "product_type"]).agg(
                    {"amount": "sum", "weighted": "sum"}
                ).reset_index()
                ib_lt_agg = ib_lt_daily.groupby("product_type").agg({"amount": "sum", "weighted": "sum"}).reset_index()
                for _, row in ib_lt_agg.iterrows():
                    pt = row["product_type"] if pd.notna(row["product_type"]) else "其他"
                    cat = f"同业-{pt}"
                    breakdown_liab_dict.setdefault(cat, {"total_mv": 0.0, "total_weighted": 0.0})
                    breakdown_liab_dict[cat]["total_mv"] += float(row["amount"])
                    breakdown_liab_dict[cat]["total_weighted"] += float(row["weighted"])

            if not mb_l.empty:
                bl_daily = mb_l.groupby(["report_date", "sub_type"]).agg(
                    {"market_value": "sum", "weighted": "sum"}
                ).reset_index()
                bl_agg = bl_daily.groupby("sub_type").agg({"market_value": "sum", "weighted": "sum"}).reset_index()
                for _, row in bl_agg.iterrows():
                    sub = row["sub_type"] if pd.notna(row["sub_type"]) else "其他"
                    cat = f"发行债券-{sub}"
                    breakdown_liab_dict.setdefault(cat, {"total_mv": 0.0, "total_weighted": 0.0})
                    breakdown_liab_dict[cat]["total_mv"] += float(row["market_value"])
                    breakdown_liab_dict[cat]["total_weighted"] += float(row["weighted"])

            breakdown_assets_list: list[dict[str, Any]] = []
            for cat, data in breakdown_assets_dict.items():
                total_mv = data["total_mv"]
                total_w = data["total_weighted"]
                avg_balance = total_mv / num_days if num_days > 0 else 0.0
                weighted_rate = (total_w / total_mv * 100) if total_mv > 0 else None
                breakdown_assets_list.append(
                    {
                        "category": cat,
                        "avg_balance": avg_balance,
                        "weighted_rate": weighted_rate,
                    }
                )

            breakdown_liab_list: list[dict[str, Any]] = []
            for cat, data in breakdown_liab_dict.items():
                total_mv = data["total_mv"]
                total_w = data["total_weighted"]
                avg_balance = total_mv / num_days if num_days > 0 else 0.0
                weighted_rate = (total_w / total_mv * 100) if total_mv > 0 else None
                breakdown_liab_list.append(
                    {
                        "category": cat,
                        "avg_balance": avg_balance,
                        "weighted_rate": weighted_rate,
                    }
                )

            for item in breakdown_assets_list:
                item["proportion"] = round(item["avg_balance"] / avg_assets * 100, 2) if avg_assets > 0 else 0
                item["side"] = "Asset"

            for item in breakdown_liab_list:
                item["proportion"] = round(item["avg_balance"] / avg_liab * 100, 2) if avg_liab > 0 else 0
                item["side"] = "Liability"

            breakdown_assets_list.sort(key=lambda x: x["avg_balance"], reverse=True)
            breakdown_liab_list.sort(key=lambda x: x["avg_balance"], reverse=True)

            last_data_date = max(all_month_dates) if all_month_dates else month_end

            end_spot_assets = 0.0
            end_spot_liab = 0.0
            if _table_exists(conn2, "zqtz_bond_daily_snapshot"):
                r1 = conn2.execute(
                    """
                    select coalesce(sum(market_value_native), 0)
                    from zqtz_bond_daily_snapshot
                    where report_date = ? and not coalesce(is_issuance_like, false)
                    """,
                    [last_data_date],
                ).fetchone()
                r2 = conn2.execute(
                    """
                    select coalesce(sum(market_value_native), 0)
                    from zqtz_bond_daily_snapshot
                    where report_date = ? and coalesce(is_issuance_like, false)
                    """,
                    [last_data_date],
                ).fetchone()
                end_spot_assets += float(r1[0] or 0)
                end_spot_liab += float(r2[0] or 0)
            if _table_exists(conn2, "tyw_interbank_daily_snapshot"):
                r3 = conn2.execute(
                    f"""
                    select coalesce(sum(principal_native), 0)
                    from tyw_interbank_daily_snapshot
                    where report_date = ? and {IB_ASSET_PRED}
                    """,
                    [last_data_date],
                ).fetchone()
                r4 = conn2.execute(
                    f"""
                    select coalesce(sum(principal_native), 0)
                    from tyw_interbank_daily_snapshot
                    where report_date = ? and not ({IB_ASSET_PRED})
                    """,
                    [last_data_date],
                ).fetchone()
                end_spot_assets += float(r3[0] or 0)
                end_spot_liab += float(r4[0] or 0)

            ytd_total_assets += Decimal(str(total_assets))
            ytd_total_liabilities += Decimal(str(total_liab))
            ytd_assets_weighted += Decimal(str(total_assets_weighted))
            ytd_liab_weighted += Decimal(str(total_liab_weighted))
            ytd_days += num_days

            assets_mom = None
            liab_mom = None
            if prev_avg_assets is not None and prev_avg_assets != 0:
                assets_mom = round((avg_assets - prev_avg_assets) / prev_avg_assets * 100, 2)
            if prev_avg_liabilities is not None and prev_avg_liabilities != 0:
                liab_mom = round((avg_liab - prev_avg_liabilities) / prev_avg_liabilities * 100, 2)

            asset_yield = round(float(total_assets_weighted / total_assets * 100), 4) if total_assets > 0 else None
            liab_cost = round(float(total_liab_weighted / total_liab * 100), 4) if total_liab > 0 else None
            nim = round(asset_yield - liab_cost, 4) if asset_yield is not None and liab_cost is not None else None

            months_data.append(
                {
                    "month": f"{year}-{month:02d}",
                    "month_label": f"{month}月",
                    "avg_assets": avg_assets,
                    "avg_liabilities": avg_liab,
                    "end_spot_assets": end_spot_assets,
                    "end_spot_liabilities": end_spot_liab,
                    "assets_mom_change": assets_mom,
                    "liabilities_mom_change": liab_mom,
                    "asset_yield": asset_yield,
                    "liability_cost": liab_cost,
                    "net_interest_margin": nim,
                    "breakdown_assets": breakdown_assets_list,
                    "breakdown_liabilities": breakdown_liab_list,
                    "num_days": num_days,
                }
            )
            prev_avg_assets = avg_assets
            prev_avg_liabilities = avg_liab
    finally:
        conn2.close()

    ytd_avg_assets = float(ytd_total_assets / ytd_days) if ytd_days > 0 else 0.0
    ytd_avg_liab = float(ytd_total_liabilities / ytd_days) if ytd_days > 0 else 0.0
    ytd_asset_yield = (
        round(float(ytd_assets_weighted / ytd_total_assets * 100), 4) if ytd_total_assets > 0 else None
    )
    ytd_liab_cost = (
        round(float(ytd_liab_weighted / ytd_total_liabilities * 100), 4) if ytd_total_liabilities > 0 else None
    )
    ytd_nim = (
        round(ytd_asset_yield - ytd_liab_cost, 4)
        if ytd_asset_yield is not None and ytd_liab_cost is not None
        else None
    )

    return {
        "year": year,
        "months": months_data,
        "ytd_avg_assets": ytd_avg_assets,
        "ytd_avg_liabilities": ytd_avg_liab,
        "ytd_asset_yield": ytd_asset_yield,
        "ytd_liability_cost": ytd_liab_cost,
        "ytd_net_interest_margin": ytd_nim,
        "unit": "percent",
    }


def adb_envelope_for_dates(start_date: str, end_date: str) -> dict[str, Any]:
    settings = get_settings()
    sd, ed = _parse_date(start_date), _parse_date(end_date)
    return calculate_adb(settings.duckdb_path, sd, ed)


def adb_comparison_envelope(
    start_date: str,
    end_date: str,
    top_n: int = 20,
) -> dict[str, Any]:
    settings = get_settings()
    sd, ed = _parse_date(start_date), _parse_date(end_date)
    return get_adb_comparison(settings.duckdb_path, sd, ed, top_n=top_n)


def adb_monthly_envelope(year: int) -> dict[str, Any]:
    settings = get_settings()
    return calculate_monthly_adb(settings.duckdb_path, year)
