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
import pandas as pd

from backend.app.core_finance.adb_interbank_labels import map_ib_category
from backend.app.core_finance.adb_rate_normalize import normalize_rate_series_pd, normalize_rate_values
from backend.app.governance.settings import get_settings
from backend.app.services.formal_result_runtime import build_result_envelope

IB_ASSET_PRED = (
    "(instr(lower(coalesce(position_side, '')), 'asset') > 0 "
    "OR instr(coalesce(position_side, ''), '资产') > 0)"
)
ADB_CACHE_VERSION = "cv_adb_analysis_v1"
ADB_EMPTY_SOURCE_VERSION = "sv_adb_empty"
ADB_RULE_VERSION = "rv_adb_analysis_v1"


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


def _merge_versions(values: list[str], default: str) -> str:
    merged = sorted({str(value or "").strip() for value in values if str(value or "").strip()})
    return "__".join(merged) or default


def _issued_mask(bonds_df: pd.DataFrame) -> pd.Series:
    if bonds_df.empty:
        return pd.Series(dtype=bool)
    issued_mask = (
        bonds_df["is_issuance_like"].fillna(False).astype(bool)
        if "is_issuance_like" in bonds_df.columns
        else pd.Series(False, index=bonds_df.index)
    )
    if "asset_class" in bonds_df.columns:
        issued_mask = issued_mask | bonds_df["asset_class"].astype(str).str.contains("发行", na=False)
    return issued_mask


def _build_analytical_envelope(
    *,
    result_kind: str,
    result_payload: dict[str, Any],
    source_versions: list[str],
    rule_versions: list[str],
) -> dict[str, Any]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_{result_kind.replace('.', '_')}",
        result_kind=result_kind,
        cache_version=ADB_CACHE_VERSION,
        source_version=_merge_versions(source_versions, ADB_EMPTY_SOURCE_VERSION),
        rule_version=_merge_versions(rule_versions, ADB_RULE_VERSION),
        quality_flag="ok",
        vendor_version="vv_none",
        result_payload=result_payload,
    )


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


def _load_adb_raw_data(
    duckdb_path: str,
    start_date: date,
    end_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str]]:
    if not Path(duckdb_path).exists():
        return pd.DataFrame(), pd.DataFrame(), [], []

    zqtz_asset_rows: list[dict[str, object]] = []
    zqtz_liability_rows: list[dict[str, object]] = []
    tyw_asset_rows: list[dict[str, object]] = []
    tyw_liability_rows: list[dict[str, object]] = []

    conn = _conn_ro(duckdb_path)
    try:
        if _table_exists(conn, "fact_formal_zqtz_balance_daily"):
            zqtz_rows = [
                _dict_from_row(description, row)
                for description, row in _fetch_formal_zqtz_rows(conn, start_date, end_date)
            ]
            concrete_zqtz_rows = [
                row for row in zqtz_rows if str(row.get("position_scope") or "") in {"asset", "liability"}
            ]
            scoped_zqtz_rows = concrete_zqtz_rows if concrete_zqtz_rows else zqtz_rows
            for row in scoped_zqtz_rows:
                if str(row.get("position_scope") or "") == "liability" or bool(row.get("is_issuance_like")):
                    zqtz_liability_rows.append(row)
                else:
                    zqtz_asset_rows.append(row)

        if _table_exists(conn, "fact_formal_tyw_balance_daily"):
            tyw_rows = [
                _dict_from_row(description, row)
                for description, row in _fetch_formal_tyw_rows(conn, start_date, end_date)
            ]
            concrete_tyw_rows = [
                row for row in tyw_rows if str(row.get("position_scope") or "") in {"asset", "liability"}
            ]
            scoped_tyw_rows = concrete_tyw_rows if concrete_tyw_rows else tyw_rows
            for row in scoped_tyw_rows:
                position_scope = str(row.get("position_scope") or "").lower()
                position_side = str(row.get("position_side") or "").lower()
                is_asset = position_scope == "asset" or (
                    position_scope not in {"asset", "liability"} and "asset" in position_side
                )
                if is_asset:
                    tyw_asset_rows.append(row)
                else:
                    tyw_liability_rows.append(row)
    finally:
        conn.close()

    source_versions = [
        *[str(row.get("source_version") or "") for row in zqtz_asset_rows],
        *[str(row.get("source_version") or "") for row in zqtz_liability_rows],
        *[str(row.get("source_version") or "") for row in tyw_asset_rows],
        *[str(row.get("source_version") or "") for row in tyw_liability_rows],
    ]
    rule_versions = [
        *[str(row.get("rule_version") or "") for row in zqtz_asset_rows],
        *[str(row.get("rule_version") or "") for row in zqtz_liability_rows],
        *[str(row.get("rule_version") or "") for row in tyw_asset_rows],
        *[str(row.get("rule_version") or "") for row in tyw_liability_rows],
    ]

    bonds_df = pd.DataFrame(
        [
            {
                "report_date": row["report_date"],
                "market_value": row["market_value_amount"],
                "yield_to_maturity": row["ytm_value"],
                "coupon_rate": row["coupon_rate"],
                "interest_rate": 0.0,
                "asset_class": row.get("asset_class") or "",
                "sub_type": row.get("bond_type") or "",
                "is_issuance_like": False,
            }
            for row in zqtz_asset_rows
        ]
        + [
            {
                "report_date": row["report_date"],
                "market_value": row["market_value_amount"],
                "yield_to_maturity": row["ytm_value"],
                "coupon_rate": row["coupon_rate"],
                "interest_rate": 0.0,
                "asset_class": row.get("asset_class") or "",
                "sub_type": row.get("bond_type") or "",
                "is_issuance_like": True,
            }
            for row in zqtz_liability_rows
        ]
    )
    ib_df = pd.DataFrame(
        [
            {
                "report_date": row["report_date"],
                "amount": row["principal_amount"],
                "interest_rate": row["funding_cost_rate"],
                "product_type": row["product_type"],
                "direction": "ASSET",
            }
            for row in tyw_asset_rows
        ]
        + [
            {
                "report_date": row["report_date"],
                "amount": row["principal_amount"],
                "interest_rate": row["funding_cost_rate"],
                "product_type": row["product_type"],
                "direction": "LIABILITY",
            }
            for row in tyw_liability_rows
        ]
    )

    bonds_df = _normalize_adb_frame(
        bonds_df,
        date_columns=("report_date",),
        numeric_columns=("market_value", "yield_to_maturity", "coupon_rate", "interest_rate"),
    )
    ib_df = _normalize_adb_frame(
        ib_df,
        date_columns=("report_date",),
        numeric_columns=("amount", "interest_rate"),
    )

    return bonds_df, ib_df, source_versions, rule_versions


def _dict_from_row(description: list[tuple], row: tuple) -> dict[str, object]:
    return {str(column[0]): value for column, value in zip(description, row, strict=True)}


def _decimal_or_zero(value: object) -> Decimal:
    return Decimal(str(value or 0))


def _frame_unique_dates(frame: pd.DataFrame) -> set[date]:
    if frame.empty:
        return set()
    return {
        row.report_date.date()
        for row in frame.itertuples(index=False)
        if getattr(row, "report_date", None) is not None
    }


def _frame_sum_by_date(frame: pd.DataFrame, amount_attr: str) -> dict[date, Decimal]:
    totals: dict[date, Decimal] = {}
    if frame.empty:
        return totals
    for row in frame.itertuples(index=False):
        report_date = getattr(row, "report_date", None)
        if report_date is None:
            continue
        day = report_date.date()
        totals[day] = totals.get(day, Decimal("0")) + _decimal_or_zero(getattr(row, amount_attr))
    return totals


def _frame_total_amounts(frame: pd.DataFrame, amount_attr: str) -> tuple[float, float]:
    total_amount = 0.0
    total_weighted = 0.0
    if frame.empty:
        return total_amount, total_weighted
    for row in frame.itertuples(index=False):
        total_amount += float(getattr(row, amount_attr) or 0)
        total_weighted += float(getattr(row, "weighted", 0) or 0)
    return total_amount, total_weighted


def _frame_spot_total_for_date(frame: pd.DataFrame, amount_attr: str, target_date: date) -> float:
    if frame.empty:
        return 0.0
    total = 0.0
    for row in frame.itertuples(index=False):
        report_date = getattr(row, "report_date", None)
        if report_date is not None and report_date.date() == target_date:
            total += float(getattr(row, amount_attr) or 0)
    return total


def _frame_breakdown_rows(
    frame: pd.DataFrame,
    *,
    category_attr: str,
    amount_attr: str,
    num_days: int,
    prefix: str = "",
) -> list[dict[str, Any]]:
    if frame.empty or num_days <= 0:
        return []
    totals: dict[str, tuple[float, float]] = {}
    for row in frame.itertuples(index=False):
        category = f"{prefix}{_clean_cat(getattr(row, category_attr, None))}"
        amount = float(getattr(row, amount_attr) or 0)
        weighted = float(getattr(row, "weighted", 0) or 0)
        current_amount, current_weighted = totals.get(category, (0.0, 0.0))
        totals[category] = (current_amount + amount, current_weighted + weighted)

    rows: list[dict[str, Any]] = []
    for category, (total_amount, total_weighted) in totals.items():
        rows.append(
            {
                "category": category,
                "avg_balance": total_amount / num_days if num_days > 0 else 0.0,
                "weighted_rate": (total_weighted / total_amount * 100) if total_amount > 0 else None,
            }
        )
    return rows


def _accumulate_spot_and_sum_maps(
    frame: pd.DataFrame,
    *,
    amount_attr: str,
    end_date: date,
    category_resolver,
    spot_map: dict[str, Decimal],
    sum_map: dict[str, Decimal],
) -> None:
    if frame.empty:
        return
    for row in frame.itertuples(index=False):
        category = _clean_cat(category_resolver(row))
        amount = _decimal_or_zero(getattr(row, amount_attr))
        sum_map[category] = sum_map.get(category, Decimal("0")) + amount
        report_date = getattr(row, "report_date", None)
        if report_date is not None and report_date.date() == end_date:
            spot_map[category] = spot_map.get(category, Decimal("0")) + amount


def _normalize_adb_frame(
    frame: pd.DataFrame,
    *,
    date_columns: tuple[str, ...],
    numeric_columns: tuple[str, ...],
) -> pd.DataFrame:
    if frame.empty:
        return frame
    normalized = frame.copy()
    for column in date_columns:
        if column in normalized.columns:
            normalized[column] = pd.to_datetime(normalized[column], errors="coerce")
    for column in numeric_columns:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce").fillna(0)
    return normalized


def _filter_frame_between_dates(frame: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows = [
        row._asdict()
        for row in frame.itertuples(index=False)
        if getattr(row, "report_date", None) is not None
        and start_date <= row.report_date.date() <= end_date
    ]
    return pd.DataFrame(rows, columns=frame.columns)


def _fetch_formal_zqtz_rows(
    conn: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
) -> list[tuple[list[tuple], tuple]]:
    cursor = conn.execute(
        """
        select
          report_date,
          position_scope,
          currency_basis,
          market_value_amount,
          ytm_value,
          coupon_rate,
          asset_class,
          bond_type,
          is_issuance_like,
          source_version,
          rule_version
        from fact_formal_zqtz_balance_daily
        where cast(report_date as date) between ? and ?
          and currency_basis = 'CNY'
        """,
        [start_date, end_date],
    )
    description = list(cursor.description or [])
    return [(description, row) for row in cursor.fetchall()]


def _fetch_formal_tyw_rows(
    conn: duckdb.DuckDBPyConnection,
    start_date: date,
    end_date: date,
) -> list[tuple[list[tuple], tuple]]:
    cursor = conn.execute(
        """
        select
          report_date,
          position_scope,
          position_side,
          currency_basis,
          principal_amount,
          funding_cost_rate,
          product_type,
          source_version,
          rule_version
        from fact_formal_tyw_balance_daily
        where cast(report_date as date) between ? and ?
          and currency_basis = 'CNY'
        """,
        [start_date, end_date],
    )
    description = list(cursor.description or [])
    return [(description, row) for row in cursor.fetchall()]


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
            bonds_assets_df["rate_decimal"] = normalize_rate_values(
                bonds_assets_df["yield_to_maturity"].tolist(),
                "yield_to_maturity",
            )
            bonds_assets_df["weighted"] = bonds_assets_df["balance"] * bonds_assets_df["rate_decimal"]
            asset_frames.append(bonds_assets_df[["category", "balance", "weighted"]])

        bonds_liab_df = bonds_df[issued_mask].copy()
        if not bonds_liab_df.empty:
            bonds_liab_df["category"] = bonds_liab_df["sub_type"].apply(_clean_cat)
            bonds_liab_df["balance"] = pd.to_numeric(bonds_liab_df["market_value"], errors="coerce").fillna(0.0)
            bonds_liab_df["rate_decimal"] = [
                rate if coupon not in (None, 0, 0.0) else 0.0
                for coupon, rate in zip(
                    bonds_liab_df["coupon_rate"].tolist(),
                    normalize_rate_values(bonds_liab_df["coupon_rate"].tolist(), "coupon_rate"),
                    strict=True,
                )
            ]
            bonds_liab_df["weighted"] = bonds_liab_df["balance"] * bonds_liab_df["rate_decimal"]
            liability_frames.append(bonds_liab_df[["category", "balance", "weighted"]])

    ib_assets_df = pd.DataFrame()
    ib_liab_df = pd.DataFrame()
    if not interbank_df.empty:
        ib_assets_df = interbank_df[interbank_df["direction"] == "ASSET"].copy()
        if not ib_assets_df.empty:
            ib_assets_df["category"] = ib_assets_df["product_type"].apply(_clean_cat)
            ib_assets_df["balance"] = pd.to_numeric(ib_assets_df["amount"], errors="coerce").fillna(0.0)
            ib_assets_df["rate_decimal"] = normalize_rate_values(
                ib_assets_df["interest_rate"].tolist(),
                "interbank_interest_rate",
            )
            ib_assets_df["weighted"] = ib_assets_df["balance"] * ib_assets_df["rate_decimal"]
            asset_frames.append(ib_assets_df[["category", "balance", "weighted"]])

        ib_liab_df = interbank_df[interbank_df["direction"] == "LIABILITY"].copy()
        if not ib_liab_df.empty:
            ib_liab_df["category"] = ib_liab_df["product_type"].apply(_clean_cat)
            ib_liab_df["balance"] = pd.to_numeric(ib_liab_df["amount"], errors="coerce").fillna(0.0)
            ib_liab_df["rate_decimal"] = normalize_rate_values(
                ib_liab_df["interest_rate"].tolist(),
                "interbank_interest_rate",
            )
            ib_liab_df["weighted"] = ib_liab_df["balance"] * ib_liab_df["rate_decimal"]
            liability_frames.append(ib_liab_df[["category", "balance", "weighted"]])

    return asset_frames, liability_frames, bonds_assets_df, bonds_liab_df, ib_assets_df, ib_liab_df


def _build_rate_map(frames: list[pd.DataFrame]) -> tuple[dict[str, float | None], float | None]:
    if not frames:
        return {}, None
    rate_map: dict[str, float | None] = {}
    totals: dict[str, tuple[float, float]] = {}
    total_balance = 0.0
    total_weighted = 0.0
    for frame in frames:
        if frame.empty:
            continue
        for row in frame.itertuples(index=False):
            category = _clean_cat(getattr(row, "category", None))
            balance = float(getattr(row, "balance", 0) or 0)
            weighted = float(getattr(row, "weighted", 0) or 0)
            current_balance, current_weighted = totals.get(category, (0.0, 0.0))
            totals[category] = (current_balance + balance, current_weighted + weighted)
            total_balance += balance
            total_weighted += weighted
    for category, (balance, weighted) in totals.items():
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
        for row in bonds_assets_df.itertuples(index=False):
            key = (_clean_cat(getattr(row, "sub_type", None)), "Asset")
            breakdown_sum[key] = breakdown_sum.get(key, Decimal("0")) + _decimal_or_zero(getattr(row, "market_value"))
        for row in bonds_liab_df.itertuples(index=False):
            key = (f"Issuance-{_clean_cat(getattr(row, 'sub_type', None))}", "Liability")
            breakdown_sum[key] = breakdown_sum.get(key, Decimal("0")) + _decimal_or_zero(getattr(row, "market_value"))

    if not interbank_df.empty:
        for row in interbank_df.itertuples(index=False):
            side = "Asset" if str(getattr(row, "direction", "") or "").upper() == "ASSET" else "Liability"
            category = map_ib_category(
                str(getattr(row, "product_type")) if getattr(row, "product_type", None) is not None else None,
                side,
            )
            key = (category, side)
            breakdown_sum[key] = breakdown_sum.get(key, Decimal("0")) + _decimal_or_zero(getattr(row, "amount"))

    nd = Decimal(str(num_days))
    out: list[dict[str, Any]] = []
    for (cat, side), total in sorted(breakdown_sum.items(), key=lambda item: float(item[1] or 0), reverse=True):
        avg_val = (total / nd) if nd else Decimal("0")
        out.append({"category": cat, "side": side, "avg_balance": float(avg_val)})
    return out


def calculate_adb(
    duckdb_path: str,
    start_date: date,
    end_date: date,
) -> tuple[dict[str, Any], list[str], list[str]]:
    if not Path(duckdb_path).exists():
        return _empty_adb_response(), [], []

    num_days = (end_date - start_date).days + 1
    all_days = [start_date + timedelta(days=i) for i in range(num_days)]
    bonds_df, interbank_df, source_versions, rule_versions = _load_adb_raw_data(duckdb_path, start_date, end_date)
    if bonds_df.empty and interbank_df.empty:
        return _empty_adb_response(), source_versions, rule_versions

    bonds_assets: dict[date, Decimal] = {}
    bonds_liabilities: dict[date, Decimal] = {}
    ib_assets: dict[date, Decimal] = {}
    ib_liabilities: dict[date, Decimal] = {}

    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_assets_df = bonds_df[~issued_mask].copy()
        bonds_liab_df = bonds_df[issued_mask].copy()
        bonds_assets = _frame_sum_by_date(bonds_assets_df, "market_value")
        bonds_liabilities = _frame_sum_by_date(bonds_liab_df, "market_value")

    if not interbank_df.empty:
        ib_assets_df = interbank_df[interbank_df["direction"] == "ASSET"].copy()
        ib_liab_df = interbank_df[interbank_df["direction"] == "LIABILITY"].copy()
        ib_assets = _frame_sum_by_date(ib_assets_df, "amount")
        ib_liabilities = _frame_sum_by_date(ib_liab_df, "amount")

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

    payload = {
        "summary": {
            "total_avg_assets": float(avg_assets),
            "total_avg_liabilities": float(avg_liabilities),
            "end_spot_assets": float(end_spot_assets),
            "end_spot_liabilities": float(end_spot_liabilities),
        },
        "trend": trend,
        "breakdown": _adb_breakdown_from_frames(bonds_df, interbank_df, num_days),
    }
    return payload, source_versions, rule_versions


def get_adb_comparison(
    duckdb_path: str,
    start_date: date,
    end_date: date,
    top_n: int = 20,
    simulate_if_single_snapshot: bool = True,
) -> tuple[dict[str, Any], list[str], list[str]]:
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

    bonds_df, interbank_df, source_versions, rule_versions = _load_adb_raw_data(duckdb_path, start_date, end_date)
    if bonds_df.empty and interbank_df.empty:
        return empty_response(), source_versions, rule_versions

    spot_assets: dict[str, Decimal] = {}
    spot_liabilities: dict[str, Decimal] = {}
    sum_assets: dict[str, Decimal] = {}
    sum_liabilities: dict[str, Decimal] = {}

    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_assets_df = bonds_df[~issued_mask].copy()
        bonds_liab_df = bonds_df[issued_mask].copy()
        _accumulate_spot_and_sum_maps(
            bonds_assets_df,
            amount_attr="market_value",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "sub_type", None),
            spot_map=spot_assets,
            sum_map=sum_assets,
        )
        _accumulate_spot_and_sum_maps(
            bonds_liab_df,
            amount_attr="market_value",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "sub_type", None),
            spot_map=spot_liabilities,
            sum_map=sum_liabilities,
        )

    if not interbank_df.empty:
        ib_assets_df = interbank_df[interbank_df["direction"] == "ASSET"].copy()
        ib_liab_df = interbank_df[interbank_df["direction"] == "LIABILITY"].copy()
        _accumulate_spot_and_sum_maps(
            ib_assets_df,
            amount_attr="amount",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "product_type", None),
            spot_map=spot_assets,
            sum_map=sum_assets,
        )
        _accumulate_spot_and_sum_maps(
            ib_liab_df,
            amount_attr="amount",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "product_type", None),
            spot_map=spot_liabilities,
            sum_map=sum_liabilities,
        )

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

    payload = {
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
    return payload, source_versions, rule_versions


def calculate_monthly_adb(duckdb_path: str, year: int) -> tuple[dict[str, Any], list[str], list[str]]:
    start_date = date(year, 1, 1)
    end_date = min(date(year, 12, 31), date.today())
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

    bonds_df, interbank_df, source_versions, rule_versions = _load_adb_raw_data(duckdb_path, start_date, end_date)
    if bonds_df.empty and interbank_df.empty:
        return empty, source_versions, rule_versions

    asset_frames, liability_frames, bonds_assets_df, bonds_liab_df, ib_assets_df, ib_liab_df = _split_rate_frames(
        bonds_df,
        interbank_df,
    )
    all_dates: set[date] = set()
    all_dates.update(_frame_unique_dates(bonds_df))
    all_dates.update(_frame_unique_dates(interbank_df))
    if not all_dates:
        return empty, source_versions, rule_versions

    available_months = sorted({(current_day.year, current_day.month) for current_day in all_dates})

    months_data: list[dict[str, Any]] = []
    prev_avg_assets: float | None = None
    prev_avg_liabilities: float | None = None
    ytd_total_assets = Decimal("0")
    ytd_total_liabilities = Decimal("0")
    ytd_assets_weighted = Decimal("0")
    ytd_liabilities_weighted = Decimal("0")
    ytd_days = 0

    for month_year, month_number in available_months:
        month_start = date(month_year, month_number, 1)
        if month_number == 12:
            month_end = date(month_year, 12, 31)
        else:
            month_end = date(month_year, month_number + 1, 1) - timedelta(days=1)
        month_end = min(month_end, date.today())
        if month_start > date.today():
            continue

        month_bonds_assets = _filter_frame_between_dates(bonds_assets_df, month_start, month_end)
        month_bonds_liab = _filter_frame_between_dates(bonds_liab_df, month_start, month_end)
        month_ib_assets = _filter_frame_between_dates(ib_assets_df, month_start, month_end)
        month_ib_liab = _filter_frame_between_dates(ib_liab_df, month_start, month_end)

        all_month_dates: set[date] = set()
        for frame in (month_bonds_assets, month_bonds_liab, month_ib_assets, month_ib_liab):
            all_month_dates.update(_frame_unique_dates(frame))
        if not all_month_dates:
            continue

        num_days = len(all_month_dates)
        total_assets = 0.0
        total_assets_weighted = 0.0
        for frame, amount_col in ((month_bonds_assets, "market_value"), (month_ib_assets, "amount")):
            frame_total, frame_weighted = _frame_total_amounts(frame, amount_col)
            total_assets += frame_total
            total_assets_weighted += frame_weighted

        total_liabilities = 0.0
        total_liabilities_weighted = 0.0
        for frame, amount_col in ((month_bonds_liab, "market_value"), (month_ib_liab, "amount")):
            frame_total, frame_weighted = _frame_total_amounts(frame, amount_col)
            total_liabilities += frame_total
            total_liabilities_weighted += frame_weighted

        if total_assets == 0 and total_liabilities == 0:
            continue

        avg_assets = total_assets / num_days if num_days > 0 else 0.0
        avg_liabilities = total_liabilities / num_days if num_days > 0 else 0.0

        breakdown_assets = _frame_breakdown_rows(
            month_bonds_assets,
            category_attr="sub_type",
            amount_attr="market_value",
            num_days=num_days,
        )
        breakdown_assets.extend(
            _frame_breakdown_rows(
                month_ib_assets,
                category_attr="product_type",
                amount_attr="amount",
                num_days=num_days,
                prefix="同业-",
            )
        )
        breakdown_liabilities = _frame_breakdown_rows(
            month_ib_liab,
            category_attr="product_type",
            amount_attr="amount",
            num_days=num_days,
            prefix="同业-",
        )
        breakdown_liabilities.extend(
            _frame_breakdown_rows(
                month_bonds_liab,
                category_attr="sub_type",
                amount_attr="market_value",
                num_days=num_days,
                prefix="发行债券-",
            )
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
        end_spot_assets = _frame_spot_total_for_date(month_bonds_assets, "market_value", last_data_date)
        end_spot_assets += _frame_spot_total_for_date(month_ib_assets, "amount", last_data_date)
        end_spot_liabilities = _frame_spot_total_for_date(month_bonds_liab, "market_value", last_data_date)
        end_spot_liabilities += _frame_spot_total_for_date(month_ib_liab, "amount", last_data_date)

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
        nim = round(asset_yield - liability_cost, 4) if asset_yield is not None and liability_cost is not None else None

        months_data.append(
            {
                "month": f"{month_year}-{month_number:02d}",
                "month_label": f"{month_year}年{month_number}月",
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
                "net_interest_margin": nim,
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
        "ytd_liability_cost": round(float(ytd_liabilities_weighted / ytd_total_liabilities * 100), 4) if ytd_total_liabilities > 0 else None,
        "ytd_nim": None,
        "unit": "percent",
    }
    if payload["ytd_asset_yield"] is not None and payload["ytd_liability_cost"] is not None:
        payload["ytd_nim"] = round(payload["ytd_asset_yield"] - payload["ytd_liability_cost"], 4)
    return payload, source_versions, rule_versions


def adb_envelope_for_dates(start_date: str, end_date: str) -> dict[str, Any]:
    settings = get_settings()
    payload, source_versions, rule_versions = calculate_adb(
        str(settings.duckdb_path),
        _parse_date(start_date),
        _parse_date(end_date),
    )
    return _build_analytical_envelope(
        result_kind="adb.daily",
        result_payload=payload,
        source_versions=source_versions,
        rule_versions=rule_versions,
    )


def adb_comparison_envelope(start_date: str, end_date: str, top_n: int = 20) -> dict[str, Any]:
    settings = get_settings()
    payload, source_versions, rule_versions = get_adb_comparison(
        str(settings.duckdb_path),
        _parse_date(start_date),
        _parse_date(end_date),
        top_n=top_n,
    )
    return _build_analytical_envelope(
        result_kind="adb.comparison",
        result_payload=payload,
        source_versions=source_versions,
        rule_versions=rule_versions,
    )


def adb_monthly_envelope(year: int) -> dict[str, Any]:
    settings = get_settings()
    payload, source_versions, rule_versions = calculate_monthly_adb(
        str(settings.duckdb_path),
        year,
    )
    return _build_analytical_envelope(
        result_kind="adb.monthly",
        result_payload=payload,
        source_versions=source_versions,
        rule_versions=rule_versions,
    )
