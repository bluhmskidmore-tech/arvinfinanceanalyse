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

from backend.app.core_finance.adb_analytics import (
    aggregate_daily_totals,
    build_comparison_rows,
    build_rate_map,
    compute_adb_trend,
    compute_mom_changes,
    compute_nim,
    compute_weighted_rate,
    enrich_breakdown,
    month_date_range,
)
from backend.app.core_finance.adb_interbank_labels import map_ib_category
from backend.app.core_finance.adb_rate_normalize import normalize_rate_values
from backend.app.governance.settings import get_settings
from backend.app.services.formal_result_runtime import build_result_envelope

IB_ASSET_PRED = (
    "(instr(lower(coalesce(position_side, '')), 'asset') > 0 "
    "OR instr(coalesce(position_side, ''), '资产') > 0)"
)
ADB_CACHE_VERSION = "cv_adb_analysis_v1"
ADB_EMPTY_SOURCE_VERSION = "sv_adb_empty"
ADB_RULE_VERSION = "rv_adb_analysis_v1"
ACCOUNTING_BASIS_CURRENCY = "CNX"
ACCOUNTING_BASIS_BUCKETS = (
    ("AC", ("142%", "143%")),
    ("OCI", ("1440101%",)),
    ("TPL", ("141%",)),
)
ACCOUNTING_BASIS_EXCLUDED_CONTROLS = ("144020%",)


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
    filters_applied: dict[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
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
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
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


def _classify_zqtz_rows(
    rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Split raw ZQTZ rows into (asset_rows, liability_rows) using position_scope + is_issuance_like."""
    concrete = [r for r in rows if str(r.get("position_scope") or "") in {"asset", "liability"}]
    scoped = concrete if concrete else rows
    assets, liabilities = [], []
    for row in scoped:
        if str(row.get("position_scope") or "") == "liability" or bool(row.get("is_issuance_like")):
            liabilities.append(row)
        else:
            assets.append(row)
    return assets, liabilities


def _classify_tyw_rows(
    rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Split raw TYW rows into (asset_rows, liability_rows) using position_scope + position_side."""
    concrete = [r for r in rows if str(r.get("position_scope") or "") in {"asset", "liability"}]
    scoped = concrete if concrete else rows
    assets, liabilities = [], []
    for row in scoped:
        scope = str(row.get("position_scope") or "").lower()
        side = str(row.get("position_side") or "").lower()
        is_asset = scope == "asset" or (scope not in {"asset", "liability"} and "asset" in side)
        (assets if is_asset else liabilities).append(row)
    return assets, liabilities


def _build_bonds_df(
    asset_rows: list[dict[str, object]],
    liability_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Construct normalised bonds DataFrame from classified ZQTZ row dicts."""
    def _bond_record(row: dict[str, object], is_issuance: bool) -> dict[str, object]:
        return {
            "report_date": row["report_date"],
            "market_value": row["market_value_amount"],
            "yield_to_maturity": row["ytm_value"],
            "coupon_rate": row["coupon_rate"],
            "interest_rate": 0.0,
            "asset_class": row.get("asset_class") or "",
            "sub_type": row.get("bond_type") or "",
            "is_issuance_like": is_issuance,
        }

    records = [_bond_record(r, False) for r in asset_rows] + [_bond_record(r, True) for r in liability_rows]
    df = pd.DataFrame(records)
    return _normalize_adb_frame(
        df,
        date_columns=("report_date",),
        numeric_columns=("market_value", "yield_to_maturity", "coupon_rate", "interest_rate"),
    )


def _build_ib_df(
    asset_rows: list[dict[str, object]],
    liability_rows: list[dict[str, object]],
) -> pd.DataFrame:
    """Construct normalised interbank DataFrame from classified TYW row dicts."""
    def _ib_record(row: dict[str, object], direction: str) -> dict[str, object]:
        return {
            "report_date": row["report_date"],
            "amount": row["principal_amount"],
            "interest_rate": row["funding_cost_rate"],
            "product_type": row["product_type"],
            "direction": direction,
        }

    records = [_ib_record(r, "ASSET") for r in asset_rows] + [_ib_record(r, "LIABILITY") for r in liability_rows]
    df = pd.DataFrame(records)
    return _normalize_adb_frame(
        df,
        date_columns=("report_date",),
        numeric_columns=("amount", "interest_rate"),
    )


def _collect_version_strings(
    *row_lists: list[dict[str, object]],
    field: str,
) -> list[str]:
    return [str(row.get(field) or "") for rows in row_lists for row in rows]


def _accounting_basis_bucket(account_code: object) -> str | None:
    code = str(account_code or "").strip()
    if code.startswith("141"):
        return "TPL"
    if code.startswith(("142", "143")):
        return "AC"
    if code.startswith("1440101"):
        return "OCI"
    return None


def _load_accounting_basis_daily_average(
    duckdb_path: str,
    report_date: date,
    currency_basis: str = ACCOUNTING_BASIS_CURRENCY,
) -> tuple[dict[str, Any], list[str], list[str], int]:
    empty = {
        "report_date": report_date.strftime("%Y-%m-%d"),
        "currency_basis": currency_basis,
        "daily_avg_total": 0.0,
        "rows": [
            {
                "basis_bucket": bucket,
                "daily_avg_balance": 0.0,
                "daily_avg_pct": None,
                "source_account_patterns": list(patterns),
            }
            for bucket, patterns in ACCOUNTING_BASIS_BUCKETS
        ],
        "accounting_controls": [
            pattern for _bucket, patterns in ACCOUNTING_BASIS_BUCKETS for pattern in patterns
        ],
        "excluded_controls": list(ACCOUNTING_BASIS_EXCLUDED_CONTROLS),
    }
    if not Path(duckdb_path).exists():
        return empty, [], [], 0

    conn = _conn_ro(duckdb_path)
    try:
        if not _table_exists(conn, "product_category_pnl_canonical_fact"):
            return empty, [], [], 0
        cursor = conn.execute(
            """
            select
              account_code,
              daily_avg_balance,
              source_version,
              rule_version
            from product_category_pnl_canonical_fact
            where report_date = ?
              and currency = ?
              and (
                account_code like '141%'
                or account_code like '142%'
                or account_code like '143%'
                or account_code like '1440101%'
                or account_code like '144020%'
              )
            """,
            [report_date.strftime("%Y-%m-%d"), currency_basis],
        )
        rows = [_dict_from_row(list(cursor.description or []), row) for row in cursor.fetchall()]
    finally:
        conn.close()

    totals = {bucket: Decimal("0") for bucket, _patterns in ACCOUNTING_BASIS_BUCKETS}
    source_versions: list[str] = []
    rule_versions: list[str] = []
    evidence_rows = 0
    for row in rows:
        bucket = _accounting_basis_bucket(row.get("account_code"))
        if bucket is None:
            continue
        totals[bucket] += _decimal_or_zero(row.get("daily_avg_balance"))
        source_versions.append(str(row.get("source_version") or ""))
        rule_versions.append(str(row.get("rule_version") or ""))
        evidence_rows += 1

    daily_avg_total = sum(totals.values(), Decimal("0"))
    payload = {
        **empty,
        "daily_avg_total": float(daily_avg_total),
        "rows": [
            {
                "basis_bucket": bucket,
                "daily_avg_balance": float(totals[bucket]),
                "daily_avg_pct": (
                    float(totals[bucket] / daily_avg_total * Decimal("100"))
                    if daily_avg_total != Decimal("0")
                    else None
                ),
                "source_account_patterns": list(patterns),
            }
            for bucket, patterns in ACCOUNTING_BASIS_BUCKETS
        ],
    }
    return payload, source_versions, rule_versions, evidence_rows


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
            raw = [_dict_from_row(d, r) for d, r in _fetch_formal_zqtz_rows(conn, start_date, end_date)]
            zqtz_asset_rows, zqtz_liability_rows = _classify_zqtz_rows(raw)

        if _table_exists(conn, "fact_formal_tyw_balance_daily"):
            raw = [_dict_from_row(d, r) for d, r in _fetch_formal_tyw_rows(conn, start_date, end_date)]
            tyw_asset_rows, tyw_liability_rows = _classify_tyw_rows(raw)
    finally:
        conn.close()

    all_row_lists = (zqtz_asset_rows, zqtz_liability_rows, tyw_asset_rows, tyw_liability_rows)
    source_versions = _collect_version_strings(*all_row_lists, field="source_version")
    rule_versions = _collect_version_strings(*all_row_lists, field="rule_version")

    bonds_df = _build_bonds_df(zqtz_asset_rows, zqtz_liability_rows)
    ib_df = _build_ib_df(tyw_asset_rows, tyw_liability_rows)

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


def _split_bonds_ib_by_side(
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
) -> tuple[dict[date, Decimal], dict[date, Decimal], dict[date, Decimal], dict[date, Decimal]]:
    """Return (bonds_assets, bonds_liabilities, ib_assets, ib_liabilities) as date→Decimal maps."""
    bonds_assets: dict[date, Decimal] = {}
    bonds_liabilities: dict[date, Decimal] = {}
    ib_assets: dict[date, Decimal] = {}
    ib_liabilities: dict[date, Decimal] = {}

    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        bonds_assets = _frame_sum_by_date(bonds_df[~issued_mask], "market_value")
        bonds_liabilities = _frame_sum_by_date(bonds_df[issued_mask], "market_value")

    if not interbank_df.empty:
        ib_assets = _frame_sum_by_date(interbank_df[interbank_df["direction"] == "ASSET"], "amount")
        ib_liabilities = _frame_sum_by_date(interbank_df[interbank_df["direction"] == "LIABILITY"], "amount")

    return bonds_assets, bonds_liabilities, ib_assets, ib_liabilities


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

    bonds_assets, bonds_liabilities, ib_assets, ib_liabilities = _split_bonds_ib_by_side(bonds_df, interbank_df)
    daily_assets, daily_liabilities, total_assets_sum, total_liabilities_sum = aggregate_daily_totals(
        all_days, bonds_assets, bonds_liabilities, ib_assets, ib_liabilities
    )

    nd = Decimal(str(num_days)) if num_days else Decimal("0")
    avg_assets = (total_assets_sum / nd) if nd else Decimal("0")
    avg_liabilities = (total_liabilities_sum / nd) if nd else Decimal("0")

    payload = {
        "summary": {
            "total_avg_assets": float(avg_assets),
            "total_avg_liabilities": float(avg_liabilities),
            "end_spot_assets": float(daily_assets.get(end_date, Decimal("0"))),
            "end_spot_liabilities": float(daily_liabilities.get(end_date, Decimal("0"))),
        },
        "trend": compute_adb_trend(all_days, daily_assets),
        "breakdown": _adb_breakdown_from_frames(bonds_df, interbank_df, num_days),
    }
    return payload, source_versions, rule_versions


def _build_comparison_spot_sum_maps(
    bonds_df: pd.DataFrame,
    interbank_df: pd.DataFrame,
    end_date: date,
) -> tuple[dict[str, Decimal], dict[str, Decimal], dict[str, Decimal], dict[str, Decimal]]:
    """Accumulate spot (end_date) and period-sum maps for assets and liabilities."""
    spot_assets: dict[str, Decimal] = {}
    spot_liabilities: dict[str, Decimal] = {}
    sum_assets: dict[str, Decimal] = {}
    sum_liabilities: dict[str, Decimal] = {}

    if not bonds_df.empty:
        issued_mask = _issued_mask(bonds_df)
        _accumulate_spot_and_sum_maps(
            bonds_df[~issued_mask],
            amount_attr="market_value",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "sub_type", None),
            spot_map=spot_assets,
            sum_map=sum_assets,
        )
        _accumulate_spot_and_sum_maps(
            bonds_df[issued_mask],
            amount_attr="market_value",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "sub_type", None),
            spot_map=spot_liabilities,
            sum_map=sum_liabilities,
        )

    if not interbank_df.empty:
        _accumulate_spot_and_sum_maps(
            interbank_df[interbank_df["direction"] == "ASSET"],
            amount_attr="amount",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "product_type", None),
            spot_map=spot_assets,
            sum_map=sum_assets,
        )
        _accumulate_spot_and_sum_maps(
            interbank_df[interbank_df["direction"] == "LIABILITY"],
            amount_attr="amount",
            end_date=end_date,
            category_resolver=lambda row: getattr(row, "product_type", None),
            spot_map=spot_liabilities,
            sum_map=sum_liabilities,
        )

    return spot_assets, spot_liabilities, sum_assets, sum_liabilities


def _empty_comparison_response(
    start_date: date,
    end_date: date,
    num_days: int,
    detail: str | None = None,
) -> dict[str, Any]:
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

    bonds_df, interbank_df, source_versions, rule_versions = _load_adb_raw_data(duckdb_path, start_date, end_date)
    if bonds_df.empty and interbank_df.empty:
        return _empty_comparison_response(start_date, end_date, num_days), source_versions, rule_versions

    spot_assets, spot_liabilities, sum_assets, sum_liabilities = _build_comparison_spot_sum_maps(
        bonds_df, interbank_df, end_date
    )

    simulated = bool(simulate_if_single_snapshot and num_days <= 1)
    assets = build_comparison_rows(
        "Asset", spot_assets, sum_assets, num_days_dec, top_n, simulated, end_date, _stable_factor
    )
    liabilities = build_comparison_rows(
        "Liability", spot_liabilities, sum_liabilities, num_days_dec, top_n, simulated, end_date, _stable_factor
    )

    total_spot_assets = float(sum(item["spot"] for item in assets))
    total_avg_assets = float(sum(item["avg"] for item in assets))
    total_spot_liabilities = float(sum(item["spot"] for item in liabilities))
    total_avg_liabilities = float(sum(item["avg"] for item in liabilities))

    asset_frames, liability_frames, *_ = _split_rate_frames(bonds_df, interbank_df)
    asset_rate_map, asset_yield = build_rate_map(asset_frames)
    liability_rate_map, liability_cost = build_rate_map(liability_frames)

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
        "net_interest_margin": compute_nim(asset_yield, liability_cost),
        "assets_breakdown": enrich_breakdown(assets, total_avg_assets, asset_rate_map),
        "liabilities_breakdown": enrich_breakdown(liabilities, total_avg_liabilities, liability_rate_map),
    }
    return payload, source_versions, rule_versions


def _build_month_breakdowns(
    month_bonds_assets: pd.DataFrame,
    month_bonds_liab: pd.DataFrame,
    month_ib_assets: pd.DataFrame,
    month_ib_liab: pd.DataFrame,
    num_days: int,
    avg_assets: float,
    avg_liabilities: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build and annotate asset/liability breakdown rows for a single month."""
    breakdown_assets = _frame_breakdown_rows(
        month_bonds_assets, category_attr="sub_type", amount_attr="market_value", num_days=num_days
    )
    breakdown_assets.extend(
        _frame_breakdown_rows(
            month_ib_assets, category_attr="product_type", amount_attr="amount", num_days=num_days, prefix="同业-"
        )
    )
    breakdown_liabilities = _frame_breakdown_rows(
        month_ib_liab, category_attr="product_type", amount_attr="amount", num_days=num_days, prefix="同业-"
    )
    breakdown_liabilities.extend(
        _frame_breakdown_rows(
            month_bonds_liab, category_attr="sub_type", amount_attr="market_value", num_days=num_days, prefix="发行债券-"
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
    return breakdown_assets, breakdown_liabilities


def _process_single_month(
    month_year: int,
    month_number: int,
    bonds_assets_df: pd.DataFrame,
    bonds_liab_df: pd.DataFrame,
    ib_assets_df: pd.DataFrame,
    ib_liab_df: pd.DataFrame,
    prev_avg_assets: float | None,
    prev_avg_liabilities: float | None,
) -> dict[str, Any] | None:
    """Process a single month's ADB data; return None if no data for that month."""
    month_start, month_end = month_date_range(month_year, month_number)
    if month_start > date.today():
        return None

    month_bonds_assets = _filter_frame_between_dates(bonds_assets_df, month_start, month_end)
    month_bonds_liab = _filter_frame_between_dates(bonds_liab_df, month_start, month_end)
    month_ib_assets = _filter_frame_between_dates(ib_assets_df, month_start, month_end)
    month_ib_liab = _filter_frame_between_dates(ib_liab_df, month_start, month_end)

    all_month_dates: set[date] = set()
    for frame in (month_bonds_assets, month_bonds_liab, month_ib_assets, month_ib_liab):
        all_month_dates.update(_frame_unique_dates(frame))
    if not all_month_dates:
        return None

    num_days = len(all_month_dates)
    total_assets, total_assets_weighted = 0.0, 0.0
    for frame, col in ((month_bonds_assets, "market_value"), (month_ib_assets, "amount")):
        ft, fw = _frame_total_amounts(frame, col)
        total_assets += ft
        total_assets_weighted += fw

    total_liabilities, total_liabilities_weighted = 0.0, 0.0
    for frame, col in ((month_bonds_liab, "market_value"), (month_ib_liab, "amount")):
        ft, fw = _frame_total_amounts(frame, col)
        total_liabilities += ft
        total_liabilities_weighted += fw

    if total_assets == 0 and total_liabilities == 0:
        return None

    avg_assets = total_assets / num_days if num_days > 0 else 0.0
    avg_liabilities = total_liabilities / num_days if num_days > 0 else 0.0

    breakdown_assets, breakdown_liabilities = _build_month_breakdowns(
        month_bonds_assets, month_bonds_liab, month_ib_assets, month_ib_liab,
        num_days, avg_assets, avg_liabilities,
    )

    last_data_date = max(all_month_dates)
    end_spot_assets = (
        _frame_spot_total_for_date(month_bonds_assets, "market_value", last_data_date)
        + _frame_spot_total_for_date(month_ib_assets, "amount", last_data_date)
    )
    end_spot_liabilities = (
        _frame_spot_total_for_date(month_bonds_liab, "market_value", last_data_date)
        + _frame_spot_total_for_date(month_ib_liab, "amount", last_data_date)
    )

    assets_mom, assets_mom_pct, liabilities_mom, liabilities_mom_pct = compute_mom_changes(
        avg_assets, avg_liabilities, prev_avg_assets, prev_avg_liabilities
    )
    asset_yield = compute_weighted_rate(total_assets_weighted, total_assets)
    liability_cost = compute_weighted_rate(total_liabilities_weighted, total_liabilities)

    return {
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
        "net_interest_margin": compute_nim(asset_yield, liability_cost),
        "breakdown_assets": breakdown_assets,
        "breakdown_liabilities": breakdown_liabilities,
        "num_days": num_days,
        # YTD accumulators — stripped by caller before appending to months_data
        "total_assets": total_assets,
        "total_assets_weighted": total_assets_weighted,
        "total_liabilities": total_liabilities,
        "total_liabilities_weighted": total_liabilities_weighted,
    }


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
        bonds_df, interbank_df
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
        month_result = _process_single_month(
            month_year,
            month_number,
            bonds_assets_df,
            bonds_liab_df,
            ib_assets_df,
            ib_liab_df,
            prev_avg_assets,
            prev_avg_liabilities,
        )
        if month_result is None:
            continue

        ytd_total_assets += Decimal(str(month_result["total_assets"]))
        ytd_total_liabilities += Decimal(str(month_result["total_liabilities"]))
        ytd_assets_weighted += Decimal(str(month_result["total_assets_weighted"]))
        ytd_liabilities_weighted += Decimal(str(month_result["total_liabilities_weighted"]))
        ytd_days += month_result["num_days"]

        month_result.pop("total_assets")
        month_result.pop("total_assets_weighted")
        month_result.pop("total_liabilities")
        month_result.pop("total_liabilities_weighted")

        months_data.append(month_result)
        prev_avg_assets = month_result["avg_assets"]
        prev_avg_liabilities = month_result["avg_liabilities"]

    ytd_asset_yield = compute_weighted_rate(float(ytd_assets_weighted), float(ytd_total_assets))
    ytd_liability_cost = compute_weighted_rate(float(ytd_liabilities_weighted), float(ytd_total_liabilities))

    payload = {
        "year": year,
        "months": months_data,
        "ytd_avg_assets": float(ytd_total_assets / ytd_days) if ytd_days > 0 else 0.0,
        "ytd_avg_liabilities": float(ytd_total_liabilities / ytd_days) if ytd_days > 0 else 0.0,
        "ytd_asset_yield": ytd_asset_yield,
        "ytd_liability_cost": ytd_liability_cost,
        "ytd_nim": compute_nim(ytd_asset_yield, ytd_liability_cost),
        "unit": "percent",
    }
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
        filters_applied={"start_date": start_date, "end_date": end_date},
        tables_used=["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
    )


def adb_comparison_envelope(start_date: str, end_date: str, top_n: int = 20) -> dict[str, Any]:
    settings = get_settings()
    parsed_end_date = _parse_date(end_date)
    payload, source_versions, rule_versions = get_adb_comparison(
        str(settings.duckdb_path),
        _parse_date(start_date),
        parsed_end_date,
        top_n=top_n,
    )
    accounting_basis, basis_source_versions, basis_rule_versions, _basis_evidence_rows = (
        _load_accounting_basis_daily_average(str(settings.duckdb_path), parsed_end_date)
    )
    payload["accounting_basis_daily_avg"] = accounting_basis
    return _build_analytical_envelope(
        result_kind="adb.comparison",
        result_payload=payload,
        source_versions=source_versions + basis_source_versions,
        rule_versions=rule_versions + basis_rule_versions,
        filters_applied={
            "start_date": start_date,
            "end_date": end_date,
            "accounting_basis_currency": ACCOUNTING_BASIS_CURRENCY,
        },
        tables_used=[
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "product_category_pnl_canonical_fact",
        ],
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
        filters_applied={"year": year},
        tables_used=["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
    )
