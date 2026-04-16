from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from backend.app.core_finance.adb_interbank_labels import map_ib_category
from backend.app.core_finance.adb_rate_normalize import normalize_rate_series_pd

_OTHER_LABEL = "\u5176\u4ed6"
_INTERBANK_PREFIX = "\u540c\u4e1a-"
_ISSUANCE_PREFIX = "\u53d1\u884c\u503a\u5238-"
ADB_SINGLE_SNAPSHOT_DETAIL = "Average balances are simulated from a single snapshot; treat deltas as indicative only."


def _stable_factor(key: str, low: Decimal = Decimal("0.85"), high: Decimal = Decimal("1.15")) -> Decimal:
    raw = (key or "").encode("utf-8", errors="ignore")
    digest = hashlib.md5(raw).hexdigest()
    number = int(digest[:8], 16)
    uniform = Decimal(number) / Decimal(0xFFFFFFFF)
    return low + (high - low) * uniform


def _clean_cat(value: object) -> str:
    if value is None:
        return _OTHER_LABEL
    text = str(value).strip()
    return text if text else _OTHER_LABEL


def _issued_mask(bonds_df: pd.DataFrame) -> pd.Series:
    if bonds_df.empty:
        return pd.Series(dtype=bool)
    issued_mask = (
        bonds_df["is_issuance_like"].fillna(False).astype(bool)
        if "is_issuance_like" in bonds_df.columns
        else pd.Series(False, index=bonds_df.index)
    )
    if "asset_class" in bonds_df.columns:
        issued_mask = issued_mask | bonds_df["asset_class"].astype(str).str.contains("\u53d1\u884c", na=False)
    return issued_mask


def _split_rate_frames(
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
) -> tuple[list[pd.DataFrame], list[pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    asset_frames: list[pd.DataFrame] = []
    liability_frames: list[pd.DataFrame] = []

    bonds_assets_df = pd.DataFrame()
    bonds_liab_df = pd.DataFrame()
    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_assets_df = bonds_df[~issued_mask].copy()
        if not bonds_assets_df.empty:
            bonds_assets_df["category"] = bonds_assets_df["sub_type"].apply(_clean_cat)
            bonds_assets_df["balance"] = pd.to_numeric(bonds_assets_df["market_value"], errors="coerce").fillna(0.0)
            bonds_assets_df["rate_decimal"] = normalize_rate_series_pd(
                bonds_assets_df["yield_to_maturity"],
                "yield_to_maturity",
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
                0.0,
            )
            bonds_liab_df["weighted"] = bonds_liab_df["balance"] * bonds_liab_df["rate_decimal"]
            liability_frames.append(bonds_liab_df[["category", "balance", "weighted"]])

    ib_assets_df = pd.DataFrame()
    ib_liab_df = pd.DataFrame()
    if not interbank_df.empty:
        ib_assets_df = interbank_df[interbank_df["direction"] == "ASSET"].copy()
        if not ib_assets_df.empty:
            ib_assets_df["category"] = ib_assets_df["product_type"].apply(_clean_cat)
            ib_assets_df["balance"] = pd.to_numeric(ib_assets_df["amount"], errors="coerce").fillna(0.0)
            ib_assets_df["rate_decimal"] = normalize_rate_series_pd(
                ib_assets_df["interest_rate"],
                "interbank_interest_rate",
            )
            ib_assets_df["weighted"] = ib_assets_df["balance"] * ib_assets_df["rate_decimal"]
            asset_frames.append(ib_assets_df[["category", "balance", "weighted"]])

        ib_liab_df = interbank_df[interbank_df["direction"] == "LIABILITY"].copy()
        if not ib_liab_df.empty:
            ib_liab_df["category"] = ib_liab_df["product_type"].apply(_clean_cat)
            ib_liab_df["balance"] = pd.to_numeric(ib_liab_df["amount"], errors="coerce").fillna(0.0)
            ib_liab_df["rate_decimal"] = normalize_rate_series_pd(
                ib_liab_df["interest_rate"],
                "interbank_interest_rate",
            )
            ib_liab_df["weighted"] = ib_liab_df["balance"] * ib_liab_df["rate_decimal"]
            liability_frames.append(ib_liab_df[["category", "balance", "weighted"]])

    return asset_frames, liability_frames, bonds_assets_df, bonds_liab_df, ib_assets_df, ib_liab_df


def _build_rate_map(frames: list[pd.DataFrame]) -> tuple[dict[str, float | None], float | None]:
    if not frames:
        return {}, None
    merged = pd.concat(frames, ignore_index=True)
    if merged.empty:
        return {}, None
    grouped = merged.groupby("category", dropna=False)[["balance", "weighted"]].sum().reset_index()
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


def _adb_breakdown_from_frames(
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
    num_days: int,
) -> list[dict[str, Any]]:
    if num_days <= 0:
        return []

    breakdown_sum: dict[tuple[str, str], Decimal] = {}
    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_assets_df = bonds_df[~issued_mask].copy()
        bonds_liab_df = bonds_df[issued_mask].copy()
        for _, row in bonds_assets_df.iterrows():
            key = (_clean_cat(row.get("sub_type")), "Asset")
            breakdown_sum[key] = breakdown_sum.get(key, Decimal("0")) + Decimal(str(row.get("market_value") or 0))
        for _, row in bonds_liab_df.iterrows():
            key = (f"Issuance-{_clean_cat(row.get('sub_type'))}", "Liability")
            breakdown_sum[key] = breakdown_sum.get(key, Decimal("0")) + Decimal(str(row.get("market_value") or 0))

    if not interbank_df.empty:
        for _, row in interbank_df.iterrows():
            side = "Asset" if str(row.get("direction") or "").upper() == "ASSET" else "Liability"
            category = map_ib_category(
                str(row.get("product_type")) if row.get("product_type") is not None else None,
                side,
            )
            key = (category, side)
            breakdown_sum[key] = breakdown_sum.get(key, Decimal("0")) + Decimal(str(row.get("amount") or 0))

    nd = Decimal(str(num_days))
    output: list[dict[str, Any]] = []
    for (category, side), total in sorted(breakdown_sum.items(), key=lambda item: float(item[1] or 0), reverse=True):
        avg_balance = (total / nd) if nd else Decimal("0")
        output.append({"category": category, "side": side, "avg_balance": float(avg_balance)})
    return output


def build_adb_daily_payload(
    *,
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    num_days = (end_date - start_date).days + 1
    all_days = [start_date + timedelta(days=offset) for offset in range(num_days)]
    if bonds_df.empty and interbank_df.empty:
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

    bonds_assets: dict[date, Decimal] = {}
    bonds_liabilities: dict[date, Decimal] = {}
    ib_assets: dict[date, Decimal] = {}
    ib_liabilities: dict[date, Decimal] = {}

    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_assets_df = bonds_df[~issued_mask].copy()
        bonds_liab_df = bonds_df[issued_mask].copy()
        if not bonds_assets_df.empty:
            grouped = bonds_assets_df.groupby("report_date")["market_value"].sum().reset_index()
            for _, row in grouped.iterrows():
                bonds_assets[row["report_date"].date()] = Decimal(str(row["market_value"] or 0))
        if not bonds_liab_df.empty:
            grouped = bonds_liab_df.groupby("report_date")["market_value"].sum().reset_index()
            for _, row in grouped.iterrows():
                bonds_liabilities[row["report_date"].date()] = Decimal(str(row["market_value"] or 0))

    if not interbank_df.empty:
        ib_assets_df = interbank_df[interbank_df["direction"] == "ASSET"].copy()
        ib_liab_df = interbank_df[interbank_df["direction"] == "LIABILITY"].copy()
        if not ib_assets_df.empty:
            grouped = ib_assets_df.groupby("report_date")["amount"].sum().reset_index()
            for _, row in grouped.iterrows():
                ib_assets[row["report_date"].date()] = Decimal(str(row["amount"] or 0))
        if not ib_liab_df.empty:
            grouped = ib_liab_df.groupby("report_date")["amount"].sum().reset_index()
            for _, row in grouped.iterrows():
                ib_liabilities[row["report_date"].date()] = Decimal(str(row["amount"] or 0))

    daily_assets: dict[date, Decimal] = {}
    daily_liabilities: dict[date, Decimal] = {}
    total_assets_sum = Decimal("0")
    total_liabilities_sum = Decimal("0")
    for current_day in all_days:
        assets_amount = bonds_assets.get(current_day, Decimal("0")) + ib_assets.get(current_day, Decimal("0"))
        liabilities_amount = bonds_liabilities.get(current_day, Decimal("0")) + ib_liabilities.get(current_day, Decimal("0"))
        daily_assets[current_day] = assets_amount
        daily_liabilities[current_day] = liabilities_amount
        total_assets_sum += assets_amount
        total_liabilities_sum += liabilities_amount

    nd = Decimal(str(num_days)) if num_days else Decimal("0")
    avg_assets = (total_assets_sum / nd) if nd else Decimal("0")
    avg_liabilities = (total_liabilities_sum / nd) if nd else Decimal("0")
    end_spot_assets = daily_assets.get(end_date, Decimal("0"))
    end_spot_liabilities = daily_liabilities.get(end_date, Decimal("0"))

    trend: list[dict[str, float]] = []
    window: list[Decimal] = []
    window_sum = Decimal("0")
    for current_day in all_days:
        spot = daily_assets[current_day]
        window.append(spot)
        window_sum += spot
        if len(window) > 30:
            window_sum -= window.pop(0)
        moving_average = (window_sum / Decimal(str(len(window)))) if window else Decimal("0")
        trend.append(
            {
                "date": current_day.strftime("%Y-%m-%d"),
                "daily_balance": float(spot),
                "moving_average_30d": float(moving_average),
            }
        )

    return {
        "summary": {
            "total_avg_assets": float(avg_assets),
            "total_avg_liabilities": float(avg_liabilities),
            "end_spot_assets": float(end_spot_assets),
            "end_spot_liabilities": float(end_spot_liabilities),
        },
        "trend": trend,
        "breakdown": _adb_breakdown_from_frames(bonds_df, interbank_df, num_days),
    }


def build_adb_comparison_payload(
    *,
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
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
        }
        if detail:
            payload["detail"] = detail
        return payload

    if bonds_df.empty and interbank_df.empty:
        return empty_response()

    spot_assets: dict[str, Decimal] = {}
    spot_liabilities: dict[str, Decimal] = {}
    sum_assets: dict[str, Decimal] = {}
    sum_liabilities: dict[str, Decimal] = {}

    def add(target: dict[str, Decimal], key: str, value: object) -> None:
        clean_key = _clean_cat(key)
        amount = Decimal(str(value or 0))
        target[clean_key] = target.get(clean_key, Decimal("0")) + amount

    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_assets_df = bonds_df[~issued_mask].copy()
        bonds_liab_df = bonds_df[issued_mask].copy()
        if not bonds_assets_df.empty:
            for category, value in (
                bonds_assets_df[bonds_assets_df["report_date"].dt.date == end_date]
                .groupby("sub_type")["market_value"]
                .sum()
                .items()
            ):
                add(spot_assets, str(category), value)
            grouped = bonds_assets_df.groupby(["report_date", "sub_type"])["market_value"].sum().reset_index()
            for _, row in grouped.iterrows():
                add(sum_assets, str(row["sub_type"]), row["market_value"])
        if not bonds_liab_df.empty:
            for category, value in (
                bonds_liab_df[bonds_liab_df["report_date"].dt.date == end_date]
                .groupby("sub_type")["market_value"]
                .sum()
                .items()
            ):
                add(spot_liabilities, str(category), value)
            grouped = bonds_liab_df.groupby(["report_date", "sub_type"])["market_value"].sum().reset_index()
            for _, row in grouped.iterrows():
                add(sum_liabilities, str(row["sub_type"]), row["market_value"])

    if not interbank_df.empty:
        ib_assets_df = interbank_df[interbank_df["direction"] == "ASSET"].copy()
        ib_liab_df = interbank_df[interbank_df["direction"] == "LIABILITY"].copy()
        if not ib_assets_df.empty:
            for category, value in (
                ib_assets_df[ib_assets_df["report_date"].dt.date == end_date]
                .groupby("product_type")["amount"]
                .sum()
                .items()
            ):
                add(spot_assets, str(category), value)
            grouped = ib_assets_df.groupby(["report_date", "product_type"])["amount"].sum().reset_index()
            for _, row in grouped.iterrows():
                add(sum_assets, str(row["product_type"]), row["amount"])
        if not ib_liab_df.empty:
            for category, value in (
                ib_liab_df[ib_liab_df["report_date"].dt.date == end_date]
                .groupby("product_type")["amount"]
                .sum()
                .items()
            ):
                add(spot_liabilities, str(category), value)
            grouped = ib_liab_df.groupby(["report_date", "product_type"])["amount"].sum().reset_index()
            for _, row in grouped.iterrows():
                add(sum_liabilities, str(row["product_type"]), row["amount"])

    simulated = bool(simulate_if_single_snapshot and num_days <= 1)

    def build_rows(side: str, spot_map: dict[str, Decimal], sum_map: dict[str, Decimal]) -> list[dict[str, float]]:
        categories = set(spot_map.keys()) | set(sum_map.keys())
        rows: list[dict[str, float]] = []
        for category in categories:
            clean_key = _clean_cat(category)
            spot_value = spot_map.get(clean_key, Decimal("0")) or Decimal("0")
            if simulated:
                avg_value = spot_value * _stable_factor(f"{side}:{end_date}:{clean_key}")
            else:
                avg_value = (sum_map.get(clean_key, Decimal("0")) or Decimal("0")) / num_days_dec
            deviation = spot_value - avg_value
            if spot_value == 0 and avg_value == 0:
                continue
            rows.append(
                {
                    "category": clean_key,
                    "spot": float(spot_value),
                    "avg": float(avg_value),
                    "deviation": float(deviation),
                }
            )
        rows.sort(key=lambda row: (abs(row.get("deviation") or 0.0), row.get("spot") or 0.0), reverse=True)
        return rows[: max(int(top_n), 0)]

    assets = build_rows("Asset", spot_assets, sum_assets)
    liabilities = build_rows("Liability", spot_liabilities, sum_liabilities)
    total_spot_assets = float(sum(item["spot"] for item in assets))
    total_avg_assets = float(sum(item["avg"] for item in assets))
    total_spot_liabilities = float(sum(item["spot"] for item in liabilities))
    total_avg_liabilities = float(sum(item["avg"] for item in liabilities))

    asset_frames, liability_frames, *_ = _split_rate_frames(bonds_df, interbank_df)
    asset_rate_map, asset_yield = _build_rate_map(asset_frames)
    liability_rate_map, liability_cost = _build_rate_map(liability_frames)
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
        return [
            {
                "category": row["category"],
                "spot_balance": float(row["spot"]),
                "avg_balance": float(row["avg"]),
                "proportion": round(float(row["avg"]) / total_avg * 100, 2) if total_avg > 0 else 0.0,
                "weighted_rate": rate_map.get(row["category"]),
            }
            for row in rows
        ]

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
    }


def build_adb_monthly_payload(
    *,
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
    year: int | None = None,
    as_of_date: date,
) -> dict[str, Any]:
    year = year or as_of_date.year
    empty = {
        "year": year,
        "months": [],
        "ytd_avg_assets": 0.0,
        "ytd_avg_liabilities": 0.0,
        "ytd_asset_yield": None,
        "ytd_liability_cost": None,
        "ytd_nim": None,
        "unit": "percent",
    }

    if bonds_df.empty and interbank_df.empty:
        return empty

    asset_frames, liability_frames, bonds_assets_df, bonds_liab_df, ib_assets_df, ib_liab_df = _split_rate_frames(
        bonds_df,
        interbank_df,
    )
    all_dates: set[date] = set()
    if not bonds_df.empty:
        all_dates.update(d for d in bonds_df["report_date"].dt.date.unique() if d <= as_of_date)
    if not interbank_df.empty:
        all_dates.update(d for d in interbank_df["report_date"].dt.date.unique() if d <= as_of_date)
    if not all_dates:
        return empty

    all_dates_df = pd.DataFrame({"report_date": pd.to_datetime(pd.Series(sorted(all_dates)))})
    all_dates_df["year_month"] = all_dates_df["report_date"].dt.to_period("M")
    available_months = sorted(all_dates_df["year_month"].unique())

    months_data: list[dict[str, Any]] = []
    prev_avg_assets: float | None = None
    prev_avg_liabilities: float | None = None
    ytd_total_assets = Decimal("0")
    ytd_total_liabilities = Decimal("0")
    ytd_assets_weighted = Decimal("0")
    ytd_liabilities_weighted = Decimal("0")
    ytd_days = 0

    for month_period in available_months:
        month_start = month_period.start_time.date()
        month_end = min(month_period.end_time.date(), as_of_date)
        if month_start > as_of_date:
            continue

        month_bonds_assets = (
            bonds_assets_df[
                (bonds_assets_df["report_date"].dt.date >= month_start)
                & (bonds_assets_df["report_date"].dt.date <= month_end)
            ].copy()
            if not bonds_assets_df.empty
            else pd.DataFrame()
        )
        month_bonds_liab = (
            bonds_liab_df[
                (bonds_liab_df["report_date"].dt.date >= month_start)
                & (bonds_liab_df["report_date"].dt.date <= month_end)
            ].copy()
            if not bonds_liab_df.empty
            else pd.DataFrame()
        )
        month_ib_assets = (
            ib_assets_df[
                (ib_assets_df["report_date"].dt.date >= month_start)
                & (ib_assets_df["report_date"].dt.date <= month_end)
            ].copy()
            if not ib_assets_df.empty
            else pd.DataFrame()
        )
        month_ib_liab = (
            ib_liab_df[
                (ib_liab_df["report_date"].dt.date >= month_start)
                & (ib_liab_df["report_date"].dt.date <= month_end)
            ].copy()
            if not ib_liab_df.empty
            else pd.DataFrame()
        )

        all_month_dates: set[date] = set()
        for frame in (month_bonds_assets, month_bonds_liab, month_ib_assets, month_ib_liab):
            if not frame.empty:
                all_month_dates.update(frame["report_date"].dt.date.unique())
        if not all_month_dates:
            continue

        num_days = len(all_month_dates)

        def _daily_totals(frame: pd.DataFrame, amount_col: str) -> pd.DataFrame:
            grouped = frame.groupby("report_date").agg({amount_col: "sum", "weighted": "sum"}).reset_index()
            if amount_col != "market_value":
                grouped.rename(columns={amount_col: "market_value"}, inplace=True)
            return grouped

        asset_daily_frames: list[pd.DataFrame] = []
        liability_daily_frames: list[pd.DataFrame] = []
        if not month_bonds_assets.empty:
            asset_daily_frames.append(_daily_totals(month_bonds_assets, "market_value"))
        if not month_ib_assets.empty:
            asset_daily_frames.append(_daily_totals(month_ib_assets, "amount"))
        if not month_bonds_liab.empty:
            liability_daily_frames.append(_daily_totals(month_bonds_liab, "market_value"))
        if not month_ib_liab.empty:
            liability_daily_frames.append(_daily_totals(month_ib_liab, "amount"))

        total_assets = 0.0
        total_assets_weighted = 0.0
        if asset_daily_frames:
            grouped = pd.concat(asset_daily_frames, ignore_index=True).groupby("report_date").agg(
                {"market_value": "sum", "weighted": "sum"}
            ).reset_index()
            total_assets = float(grouped["market_value"].sum())
            total_assets_weighted = float(grouped["weighted"].sum())

        total_liabilities = 0.0
        total_liabilities_weighted = 0.0
        if liability_daily_frames:
            grouped = pd.concat(liability_daily_frames, ignore_index=True).groupby("report_date").agg(
                {"market_value": "sum", "weighted": "sum"}
            ).reset_index()
            total_liabilities = float(grouped["market_value"].sum())
            total_liabilities_weighted = float(grouped["weighted"].sum())

        if total_assets == 0 and total_liabilities == 0:
            continue

        avg_assets = total_assets / num_days if num_days > 0 else 0.0
        avg_liabilities = total_liabilities / num_days if num_days > 0 else 0.0

        def _build_breakdown(frame: pd.DataFrame, key_col: str, amount_col: str, prefix: str = "") -> list[dict[str, Any]]:
            if frame.empty:
                return []
            grouped = (
                frame.groupby(["report_date", key_col]).agg({amount_col: "sum", "weighted": "sum"}).reset_index()
                .groupby(key_col)
                .agg({amount_col: "sum", "weighted": "sum"})
                .reset_index()
            )
            rows: list[dict[str, Any]] = []
            for _, row in grouped.iterrows():
                category = f"{prefix}{row[key_col] if pd.notna(row[key_col]) else 'Other'}"
                total_mv = float(row[amount_col])
                rows.append(
                    {
                        "category": category,
                        "avg_balance": total_mv / num_days if num_days > 0 else 0.0,
                        "weighted_rate": (float(row["weighted"]) / total_mv * 100) if total_mv > 0 else None,
                    }
                )
            return rows

        breakdown_assets = _build_breakdown(month_bonds_assets, "sub_type", "market_value")
        breakdown_assets.extend(_build_breakdown(month_ib_assets, "product_type", "amount", prefix=_INTERBANK_PREFIX))
        breakdown_liabilities = _build_breakdown(month_ib_liab, "product_type", "amount", prefix=_INTERBANK_PREFIX)
        breakdown_liabilities.extend(
            _build_breakdown(month_bonds_liab, "sub_type", "market_value", prefix=_ISSUANCE_PREFIX)
        )
        for item in breakdown_assets:
            item["proportion"] = round(item["avg_balance"] / avg_assets * 100, 2) if avg_assets > 0 else 0
            item["side"] = "Asset"
        for item in breakdown_liabilities:
            item["proportion"] = round(item["avg_balance"] / avg_liabilities * 100, 2) if avg_liabilities > 0 else 0
            item["side"] = "Liability"
        breakdown_assets.sort(key=lambda row: row["avg_balance"], reverse=True)
        breakdown_liabilities.sort(key=lambda row: row["avg_balance"], reverse=True)

        last_data_date = max(all_month_dates)
        end_spot_assets = 0.0
        end_spot_liabilities = 0.0
        if not month_bonds_assets.empty:
            end_spot_assets += float(
                month_bonds_assets[month_bonds_assets["report_date"].dt.date == last_data_date]["market_value"].sum()
            )
        if not month_ib_assets.empty:
            end_spot_assets += float(
                month_ib_assets[month_ib_assets["report_date"].dt.date == last_data_date]["amount"].sum()
            )
        if not month_bonds_liab.empty:
            end_spot_liabilities += float(
                month_bonds_liab[month_bonds_liab["report_date"].dt.date == last_data_date]["market_value"].sum()
            )
        if not month_ib_liab.empty:
            end_spot_liabilities += float(
                month_ib_liab[month_ib_liab["report_date"].dt.date == last_data_date]["amount"].sum()
            )

        ytd_total_assets += Decimal(str(total_assets))
        ytd_total_liabilities += Decimal(str(total_liabilities))
        ytd_assets_weighted += Decimal(str(total_assets_weighted))
        ytd_liabilities_weighted += Decimal(str(total_liabilities_weighted))
        ytd_days += num_days

        assets_mom = None
        assets_mom_pct = None
        liabilities_mom = None
        liabilities_mom_pct = None
        if prev_avg_assets is not None and prev_avg_assets != 0:
            assets_mom = round(avg_assets - prev_avg_assets, 2)
            assets_mom_pct = round((avg_assets - prev_avg_assets) / prev_avg_assets * 100, 2)
        if prev_avg_liabilities is not None and prev_avg_liabilities != 0:
            liabilities_mom = round(avg_liabilities - prev_avg_liabilities, 2)
            liabilities_mom_pct = round((avg_liabilities - prev_avg_liabilities) / prev_avg_liabilities * 100, 2)

        asset_yield = round(float(total_assets_weighted / total_assets * 100), 4) if total_assets > 0 else None
        liability_cost = round(float(total_liabilities_weighted / total_liabilities * 100), 4) if total_liabilities > 0 else None
        net_interest_margin = (
            round(asset_yield - liability_cost, 4)
            if asset_yield is not None and liability_cost is not None
            else None
        )

        months_data.append(
            {
                "month": f"{year}-{month_period.month:02d}",
                "month_label": f"{year}\u5e74{month_period.month}\u6708",
                "avg_assets": avg_assets,
                "avg_liabilities": avg_liabilities,
                "end_spot_assets": end_spot_assets,
                "end_spot_liabilities": end_spot_liabilities,
                "mom_change_assets": assets_mom,
                "mom_change_pct_assets": assets_mom_pct,
                "mom_change_liabilities": liabilities_mom,
                "mom_change_pct_liabilities": liabilities_mom_pct,
                "asset_yield": asset_yield,
                "liability_cost": liability_cost,
                "net_interest_margin": net_interest_margin,
                "breakdown_assets": breakdown_assets,
                "breakdown_liabilities": breakdown_liabilities,
                "num_days": num_days,
            }
        )
        prev_avg_assets = avg_assets
        prev_avg_liabilities = avg_liabilities

    payload = {
        "year": year,
        "months": months_data,
        "ytd_avg_assets": float(ytd_total_assets / ytd_days) if ytd_days > 0 else 0.0,
        "ytd_avg_liabilities": float(ytd_total_liabilities / ytd_days) if ytd_days > 0 else 0.0,
        "ytd_asset_yield": round(float(ytd_assets_weighted / ytd_total_assets * 100), 4) if ytd_total_assets > 0 else None,
        "ytd_liability_cost": round(float(ytd_liabilities_weighted / ytd_total_liabilities * 100), 4)
        if ytd_total_liabilities > 0
        else None,
        "ytd_nim": None,
        "unit": "percent",
    }
    if payload["ytd_asset_yield"] is not None and payload["ytd_liability_cost"] is not None:
        payload["ytd_nim"] = round(payload["ytd_asset_yield"] - payload["ytd_liability_cost"], 4)
    return payload
