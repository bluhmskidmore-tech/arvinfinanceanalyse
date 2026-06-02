"""
Campisi 完整归因桥接层 — 将 V3 的 DuckDB 数据转换为 campisi.py 纯函数所需的输入格式。

提供两个入口：
- campisi_four_effects_envelope: 四效应（income/treasury/spread/selection）
- campisi_enhanced_envelope: 六效应（+ convexity/cross/reinvestment）
- campisi_maturity_bucket_envelope: 按到期桶分解

数据来源：
- bond_rows: BondAnalyticsRepository.fetch_bond_analytics_rows（期初+期末）
- market: YieldCurveRepository.fetch_curve（国债曲线 + 信用利差）
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import duckdb
from backend.app.core_finance.campisi import (
    CampisiResult,
    campisi_attribution,
    campisi_enhanced,
    infer_credit_rating_from_asset_class,
    maturity_bucket_attribution,
)
from backend.app.core_finance.campisi_decision_grade import (
    compute_decision_grade_row,
    decimal_value as campisi_decision_decimal,
    normalize_accounting_basis,
    primary_driver,
)
from backend.app.core_finance.rate_units import normalize_annual_rate_to_decimal
from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.yield_curve_repo import YieldCurveRepository
from backend.app.services.formal_result_runtime import (
    build_formal_result_envelope,
    build_formal_result_meta,
)

RULE_VERSION = "rv_campisi_full_v1"
CACHE_VERSION = "cv_campisi_full_v1"
SOURCE_VERSION = "sv_campisi_formal_fi_v1"
SOURCE_EMPTY = "sv_campisi_empty_v1"
TABLES_CAMPISI = [
    "fact_formal_pnl_fi",
    "fact_formal_zqtz_balance_daily",
    "fact_formal_bond_analytics_daily",
    "yield_curve_daily",
    "fact_choice_macro_daily",
    "choice_market_snapshot",
]
TABLES_CAMPISI_DECISION_GRADE = [
    "fact_formal_pnl_fi",
    "fact_formal_zqtz_balance_daily",
    "fact_formal_bond_analytics_daily",
    "fact_formal_yield_curve_daily",
    "fact_formal_risk_tensor_daily",
]
FORMAL_REPORT_BASIS = "formal_report_pnl_bridge"
_MATURITY_BUCKET_LABELS = ("0-1Y", "1-3Y", "3-5Y", "5-7Y", "7-10Y", "10Y+")

_TREASURY_TENOR_MAP = {
    "1Y": "treasury_1y",
    "3Y": "treasury_3y",
    "5Y": "treasury_5y",
    "7Y": "treasury_7y",
    "10Y": "treasury_10y",
    "30Y": "treasury_30y",
}

_SPREAD_TENOR_MAP = {
    "credit_spread_aaa_3y": ("AAA", "3Y"),
    "credit_spread_aa_plus_3y": ("AA+", "3Y"),
    "credit_spread_aa_3y": ("AA", "3Y"),
}

_SPREAD_FIELD_BY_RATING = {
    "AAA": "credit_spread_aaa_3y",
    "AA+": "credit_spread_aa_plus_3y",
    "AA": "credit_spread_aa_3y",
}

_FORMAL_CREDIT_CURVE_TYPES = {
    "AAA": "aaa_credit",
    "AA+": "aa_plus_credit",
    "AA": "aa_credit",
}

_CHOICE_CREDIT_3Y_SERIES = {
    "EMM00166657": "AAA",
    "EMM00166681": "AA",
}

_POSITION_KEY_FIELDS = (
    "instrument_code",
    "portfolio_name",
    "cost_center",
    "accounting_class",
    "currency_code",
)

_QUALITY_MISSING_FIELDS = (
    "ytm",
    "maturity_date",
    "rating",
    "portfolio_name",
    "cost_center",
)


def _trace_id() -> str:
    return f"tr_campisi_{uuid.uuid4().hex[:12]}"


def _meta_ok(
    result_kind: str,
    *,
    filters_applied: dict[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    as_of_date: str | None = None,
):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=CACHE_VERSION,
        source_version=SOURCE_VERSION,
        rule_version=RULE_VERSION,
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        source_surface="formal_attribution",
        as_of_date=as_of_date,
    )


def _meta_warn(
    result_kind: str,
    *,
    source_version: str = SOURCE_EMPTY,
    filters_applied: dict[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    as_of_date: str | None = None,
):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        source_version=source_version,
        rule_version=RULE_VERSION,
        cache_version=CACHE_VERSION,
        quality_flag="warning",
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        source_surface="formal_attribution",
        as_of_date=as_of_date,
    )


def curve_to_market_dict(curve: dict[str, Any]) -> dict[str, Any]:
    """将 YieldCurveRepository.fetch_curve 的 {tenor: rate_pct} 转为 campisi.py 需要的 market dict。"""
    market: dict[str, Any] = {}
    for tenor, field in _TREASURY_TENOR_MAP.items():
        val = curve.get(tenor) or curve.get(tenor.lower()) or curve.get(tenor.replace("Y", "y"))
        if val is not None:
            market[field] = float(val)
    return market


# Private alias kept for backward compatibility with existing internal callers.
_curve_to_market_dict = curve_to_market_dict


def fetch_credit_spread_market(curve_repo: YieldCurveRepository, trade_date: str) -> dict[str, Any]:
    """Fetch AAA/AA+/AA 3Y credit spreads in bp for Campisi.

    Returns a dict with keys like ``credit_spread_aaa_3y``, ``credit_spread_aa_plus_3y``,
    ``credit_spread_aa_3y`` (values in BP). Safe to merge with a treasury curve dict.
    """
    spread = _fetch_legacy_spread_curve_data(curve_repo, trade_date)
    spread.update(_derive_spreads_from_yield_sources(curve_repo, trade_date))
    return spread


# Keep the private alias so internal callers don't break.
_fetch_spread_data = fetch_credit_spread_market


def _fetch_legacy_spread_curve_data(curve_repo: YieldCurveRepository, trade_date: str) -> dict[str, Any]:
    spread: dict[str, Any] = {}
    for curve_type in ("credit_spread_aaa", "credit_spread_aa_plus", "credit_spread_aa"):
        data = curve_repo.fetch_curve(trade_date, curve_type)
        if data:
            for tenor, rate in data.items():
                key = f"{curve_type}_{tenor.lower()}"
                spread[key] = float(rate)
    return spread


def _derive_spreads_from_yield_sources(curve_repo: YieldCurveRepository, trade_date: str) -> dict[str, Any]:
    treasury_3y = _curve_3y_on_or_before(curve_repo, trade_date, "treasury")
    if treasury_3y is None:
        return {}
    spread: dict[str, Any] = {}
    for rating, curve_type in _FORMAL_CREDIT_CURVE_TYPES.items():
        credit_3y = _curve_3y_on_or_before(curve_repo, trade_date, curve_type)
        if credit_3y is not None:
            spread[_SPREAD_FIELD_BY_RATING[rating]] = float((credit_3y - treasury_3y) * Decimal("100"))
    for rating, credit_3y in _choice_credit_3y_yields_on_or_before(curve_repo.path, trade_date).items():
        spread[_SPREAD_FIELD_BY_RATING[rating]] = float((credit_3y - treasury_3y) * Decimal("100"))
    return spread


def _curve_3y_on_or_before(
    curve_repo: YieldCurveRepository,
    trade_date: str,
    curve_type: str,
) -> Decimal | None:
    exact = curve_repo.fetch_curve(trade_date, curve_type)
    if exact.get("3Y") is not None:
        return Decimal(str(exact["3Y"]))
    latest = curve_repo.fetch_latest_trade_date_on_or_before(curve_type, trade_date)
    if latest is None or latest == trade_date:
        return None
    fallback = curve_repo.fetch_curve(latest, curve_type)
    value = fallback.get("3Y")
    return None if value is None else Decimal(str(value))


def _choice_credit_3y_yields_on_or_before(duckdb_path: str, trade_date: str) -> dict[str, Decimal]:
    try:
        conn = duckdb.connect(duckdb_path, read_only=True)
    except duckdb.Error:
        return {}
    try:
        rows: list[tuple[object, object, object]] = []
        has_catalog = _relation_exists(conn, "phase1_macro_vendor_catalog")
        if _relation_exists(conn, "fact_choice_macro_daily"):
            rows.extend(_choice_rows_for_relation(conn, "fact_choice_macro_daily", "fact", trade_date, has_catalog))
        if _relation_exists(conn, "choice_market_snapshot"):
            rows.extend(_choice_rows_for_relation(conn, "choice_market_snapshot", "snap", trade_date, has_catalog))
    finally:
        conn.close()

    out: dict[str, Decimal] = {}
    for series_id, series_name, value in rows:
        rating = _choice_credit_rating_for_3y(series_id, series_name)
        if rating is not None:
            out[rating] = Decimal(str(value))
    return out


def _choice_rows_for_relation(
    conn: duckdb.DuckDBPyConnection,
    relation_name: str,
    alias: str,
    trade_date: str,
    has_catalog: bool,
) -> list[tuple[object, object, object]]:
    if has_catalog:
        return conn.execute(
            f"""
            select {alias}.series_id, coalesce(nullif(cat.series_name, ''), {alias}.series_name), {alias}.value_numeric
            from {relation_name} as {alias}
            left join phase1_macro_vendor_catalog as cat
              on cat.series_id = {alias}.series_id
            where {alias}.trade_date = (
              select max(trade_date)
              from {relation_name}
              where trade_date <= ?
            )
              and {alias}.value_numeric is not null
            """,
            [trade_date],
        ).fetchall()
    return conn.execute(
        f"""
        select series_id, series_name, value_numeric
        from {relation_name}
        where trade_date = (
          select max(trade_date)
          from {relation_name}
          where trade_date <= ?
        )
          and value_numeric is not null
        """,
        [trade_date],
    ).fetchall()


def _choice_credit_rating_for_3y(series_id: object, series_name: object) -> str | None:
    rating = _CHOICE_CREDIT_3Y_SERIES.get(str(series_id or "").strip())
    if rating is not None:
        return rating
    text = str(series_name or "").upper().replace(" ", "")
    if ":3Y" not in text and ":3" not in text:
        return None
    if "(AA+)" in text:
        return "AA+"
    if "(AAA)" in text:
        return "AAA"
    if "(AA)" in text:
        return "AA"
    return None


def _relation_exists(conn: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_name = ?
        union all
        select 1
        from information_schema.views
        where table_name = ?
        limit 1
        """,
        [relation_name, relation_name],
    ).fetchone()
    return row is not None


def _position_key(row: dict[str, Any]) -> tuple[str, ...] | None:
    key = tuple(_text_value(row.get(field)) for field in _POSITION_KEY_FIELDS)
    if not key[0]:
        return None
    return key


def _aggregate_position_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, ...], dict[str, Any]]:
    grouped_rows: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _position_key(row)
        if key is not None:
            grouped_rows[key].append(row)
    return {key: _aggregate_position_bucket(bucket_rows) for key, bucket_rows in grouped_rows.items()}


def _aggregate_position_bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = rows[0]
    return {
        "instrument_code": _text_value(first.get("instrument_code")),
        "portfolio_name": _text_value(first.get("portfolio_name")),
        "cost_center": _text_value(first.get("cost_center")),
        "accounting_class": _text_value(first.get("accounting_class")),
        "currency_code": _text_value(first.get("currency_code")),
        "market_value": _sum_decimal(rows, "market_value"),
        "face_value": _sum_decimal(rows, "face_value"),
        "accrued_interest": _sum_optional_decimal(rows, "accrued_interest"),
        "coupon_rate": _weighted_row_value(rows, "coupon_rate", "face_value"),
        "ytm": _weighted_row_value(rows, "ytm", "market_value"),
        "asset_class_std": _dominant_value(rows, "asset_class_std"),
        "rating": _dominant_value(rows, "rating"),
        "maturity_date": _dominant_value(rows, "maturity_date"),
    }


def _weighted_row_value(rows: list[dict[str, Any]], value_field: str, weight_field: str) -> float | None:
    numerator = Decimal("0")
    denominator = Decimal("0")
    equal_weight_sum = Decimal("0")
    equal_weight_count = 0
    for row in rows:
        value = normalize_annual_rate_to_decimal(row.get(value_field))
        if value is None:
            continue
        value_dec = Decimal(str(value))
        weight = abs(_decimal_value(row.get(weight_field)))
        if weight == 0 and weight_field != "market_value":
            weight = abs(_decimal_value(row.get("market_value")))
        if weight > 0:
            numerator += value_dec * weight
            denominator += weight
        equal_weight_sum += value_dec
        equal_weight_count += 1
    if denominator > 0:
        return float(numerator / denominator)
    if equal_weight_count:
        return float(equal_weight_sum / Decimal(equal_weight_count))
    return None


def _campisi_asset_class(s: dict[str, Any], e: dict[str, Any]) -> str:
    s_asset = _text_value(s.get("asset_class_std"))
    e_asset = _text_value(e.get("asset_class_std"))
    asset_class = e_asset if _is_generic_asset_class(s_asset) and e_asset else s_asset or e_asset
    rating = _text_value(s.get("rating") or e.get("rating")).upper().replace(" ", "")
    if rating and rating not in asset_class.upper().replace(" ", ""):
        return f"{asset_class} {rating}".strip()
    return asset_class


def _sum_decimal(rows: list[dict[str, Any]], field: str) -> Decimal:
    return sum((_decimal_value(row.get(field)) for row in rows), Decimal("0"))


def _sum_optional_decimal(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [_decimal_value(row.get(field)) for row in rows if not _is_missing(row.get(field))]
    if not values:
        return None
    return float(sum(values, Decimal("0")))


def _dominant_value(rows: list[dict[str, Any]], field: str) -> Any:
    best_value: Any = None
    best_weight = Decimal("-1")
    for row in rows:
        value = row.get(field)
        if _is_missing(value):
            continue
        weight = abs(_decimal_value(row.get("market_value")))
        if best_value is None or weight > best_weight:
            best_value = value
            best_weight = weight
    return best_value


def _is_generic_asset_class(value: str) -> bool:
    return value.strip().lower() in {"", "other", "unknown"}


def _decimal_value(value: Any) -> Decimal:
    if _is_missing(value):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _numeric_raw(value: Any) -> Decimal:
    if isinstance(value, dict):
        return _decimal_value(value.get("raw"))
    return _decimal_value(value)


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(value != value)
    except Exception:
        return False


def merge_positions(
    rows_start: list[dict[str, Any]],
    rows_end: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    将期初和期末的 bond_analytics_rows 合并为 campisi_attribution 需要的 positions_merged 格式。

    campisi.py 需要每行包含：
    - market_value_start/end, face_value_start, coupon_rate_start,
    - yield_to_maturity_start, asset_class_start, maturity_date_start, bond_code
    """
    start_by_key = _aggregate_position_rows(rows_start)
    end_by_key = _aggregate_position_rows(rows_end)
    all_codes = set(start_by_key.keys()) | set(end_by_key.keys())
    merged: list[dict[str, Any]] = []

    for key in sorted(all_codes):
        s = start_by_key.get(key, {})
        e = end_by_key.get(key, {})
        code = str(s.get("instrument_code") or e.get("instrument_code") or "")

        coupon_raw = s.get("coupon_rate") or e.get("coupon_rate")
        coupon_dec = normalize_annual_rate_to_decimal(coupon_raw) if coupon_raw is not None else None

        ytm_raw = s.get("ytm") or e.get("ytm")
        ytm_dec = normalize_annual_rate_to_decimal(ytm_raw) if ytm_raw is not None else None

        merged.append({
            "bond_code": code,
            "instrument_id": code,
            "position_key": "|".join(key),
            "portfolio_name": key[1],
            "cost_center": key[2],
            "accounting_class": key[3],
            "currency_code": key[4],
            "market_value_start": float(s.get("market_value") or 0),
            "market_value_end": float(e.get("market_value") or 0),
            "face_value_start": float(s.get("face_value") or 0),
            "accrued_interest_start": s.get("accrued_interest"),
            "accrued_interest_end": e.get("accrued_interest"),
            "coupon_rate_start": coupon_dec or 0.0,
            "yield_to_maturity_start": ytm_dec or 0.0,
            "asset_class_start": _campisi_asset_class(s, e),
            "rating_start": s.get("rating") or e.get("rating") or "",
            "maturity_date_start": s.get("maturity_date") or e.get("maturity_date"),
        })

    return merged


# Private alias kept for backward compatibility with existing internal callers.
_merge_positions = merge_positions


def _build_input_quality(
    *,
    rows_start: list[dict[str, Any]],
    rows_end: list[dict[str, Any]],
    positions: list[dict[str, Any]],
) -> dict[str, Any]:
    start_quality = _side_input_quality(rows_start)
    end_quality = _side_input_quality(rows_end)
    warnings: list[str] = []
    if _has_missing_fields(start_quality) or _has_missing_fields(end_quality):
        warnings.append("Campisi input has missing pricing or classification fields.")
    if start_quality["duplicate_instrument_codes"]["instrument_codes"] or end_quality["duplicate_instrument_codes"]["instrument_codes"]:
        warnings.append(
            "Campisi input has duplicate instrument_code rows; aggregation uses the business position key."
        )
    if start_quality["duplicate_position_keys"]["position_keys"] or end_quality["duplicate_position_keys"]["position_keys"]:
        warnings.append("Campisi input has duplicate position keys; rows were aggregated before attribution.")
    return {
        "position_key_fields": list(_POSITION_KEY_FIELDS),
        "start_rows": len(rows_start),
        "end_rows": len(rows_end),
        "merged_positions": len(positions),
        "missing_fields": {
            "start": start_quality["missing_fields"],
            "end": end_quality["missing_fields"],
        },
        "duplicate_instrument_codes": {
            "start": start_quality["duplicate_instrument_codes"],
            "end": end_quality["duplicate_instrument_codes"],
        },
        "duplicate_position_keys": {
            "start": start_quality["duplicate_position_keys"],
            "end": end_quality["duplicate_position_keys"],
        },
        "warnings": warnings,
    }


def _add_market_curve_quality(
    input_quality: dict[str, Any],
    *,
    positions: list[dict[str, Any]],
    market_start: dict[str, Any],
    market_end: dict[str, Any],
) -> dict[str, Any]:
    coverage = _market_curve_coverage(positions=positions, market_start=market_start, market_end=market_end)
    input_quality["market_curve_coverage"] = coverage
    missing = coverage["missing_credit_spread_3y"]
    if missing:
        ratings = ", ".join(item["rating"] for item in missing)
        input_quality["warnings"].append(
            "Campisi credit spread curve coverage is incomplete for ratings "
            f"{ratings}; spread effect may be understated because missing spread inputs are unavailable."
        )
    return input_quality


def _market_curve_coverage(
    *,
    positions: list[dict[str, Any]],
    market_start: dict[str, Any],
    market_end: dict[str, Any],
) -> dict[str, Any]:
    required: dict[str, dict[str, Any]] = {}
    for position in positions:
        rating = infer_credit_rating_from_asset_class(position.get("asset_class_start"))
        field = _SPREAD_FIELD_BY_RATING.get(rating)
        if field is None:
            continue
        bucket = required.setdefault(
            rating,
            {
                "rating": rating,
                "field": field,
                "positions": 0,
                "market_value_start": Decimal("0"),
            },
        )
        bucket["positions"] += 1
        bucket["market_value_start"] += _decimal_value(position.get("market_value_start"))

    required_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    for rating in ("AAA", "AA+", "AA"):
        row = required.get(rating)
        if row is None:
            continue
        field = row["field"]
        start_available = _market_has_field(market_start, field)
        end_available = _market_has_field(market_end, field)
        out = {
            "rating": rating,
            "field": field,
            "positions": row["positions"],
            "market_value_start": float(row["market_value_start"]),
            "start_available": start_available,
            "end_available": end_available,
        }
        required_rows.append(out)
        missing_sides = [
            side
            for side, available in (("start", start_available), ("end", end_available))
            if not available
        ]
        if missing_sides:
            missing_rows.append({**out, "missing_sides": missing_sides})

    return {
        "required_credit_spread_3y": required_rows,
        "missing_credit_spread_3y": missing_rows,
    }


def _market_has_field(market: dict[str, Any], field: str) -> bool:
    return field in market and not _is_missing(market.get(field))


def _side_input_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    missing: dict[str, dict[str, int | float]] = {}
    for field in _QUALITY_MISSING_FIELDS:
        missing_rows = [row for row in rows if _is_missing(row.get(field))]
        count = len(missing_rows)
        if count:
            missing[field] = {"rows": count, "market_value": float(_sum_decimal(missing_rows, "market_value"))}
    return {
        "missing_fields": missing,
        "duplicate_instrument_codes": _duplicate_value_summary(rows, "instrument_code", "instrument_codes"),
        "duplicate_position_keys": _duplicate_position_key_summary(rows),
    }


def _duplicate_value_summary(rows: list[dict[str, Any]], field_name: str, label: str) -> dict[str, int | float]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = _text_value(row.get(field_name))
        if not value:
            continue
        grouped[value].append(row)
    duplicate_rows = [row for bucket in grouped.values() if len(bucket) > 1 for row in bucket]
    return {
        label: sum(1 for bucket in grouped.values() if len(bucket) > 1),
        "rows": len(duplicate_rows),
        "market_value": float(_sum_decimal(duplicate_rows, "market_value")),
    }


def _duplicate_position_key_summary(rows: list[dict[str, Any]]) -> dict[str, int | float]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = _position_key(row)
        if key is not None:
            grouped[key].append(row)
    duplicate_rows = [row for bucket in grouped.values() if len(bucket) > 1 for row in bucket]
    return {
        "position_keys": sum(1 for bucket in grouped.values() if len(bucket) > 1),
        "rows": len(duplicate_rows),
        "market_value": float(_sum_decimal(duplicate_rows, "market_value")),
    }


def _has_missing_fields(side_quality: dict[str, Any]) -> bool:
    return any(summary["rows"] for summary in side_quality["missing_fields"].values())


def _anchor_on_or_before(dates: list[str], day: str) -> str | None:
    eligible = [d for d in dates if d <= day]
    return max(eligible) if eligible else None


def _empty_campisi_payload(start: str, end: str) -> dict[str, Any]:
    return {
        "report_date": end,
        "period_start": start,
        "period_end": end,
        "num_days": 0,
        "totals": {
            "income_return": 0.0,
            "treasury_effect": 0.0,
            "spread_effect": 0.0,
            "selection_effect": 0.0,
            "total_return": 0.0,
            "market_value_start": 0.0,
        },
        "by_asset_class": [],
        "by_bond": [],
        "warnings": ["缺债券持仓事实，Campisi 分解为空。"],
    }


def _fetch_formal_bridge(*, settings: Any, report_date: str) -> dict[str, Any]:
    from backend.app.services.pnl_bridge_service import pnl_bridge_envelope

    return pnl_bridge_envelope(
        duckdb_path=str(settings.duckdb_path),
        governance_dir=str(settings.governance_path),
        report_date=report_date,
    )


def _try_fetch_formal_bridge(*, settings: Any, report_date: str) -> dict[str, Any] | None:
    try:
        return _fetch_formal_bridge(settings=settings, report_date=report_date)
    except Exception:
        return None


def _formal_bridge_rows(bridge_envelope: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not bridge_envelope:
        return []
    rows = ((bridge_envelope.get("result") or {}).get("rows") or [])
    return [row for row in rows if isinstance(row, dict)]


def _bridge_position_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _text_value(row.get("instrument_code") or row.get("bond_code") or row.get("instrument_id")),
        _text_value(row.get("portfolio_name")),
        _text_value(row.get("cost_center")),
    )


def _position_lookup(positions: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for position in positions:
        key = _bridge_position_key(position)
        if not key[0]:
            continue
        existing = out.get(key)
        if existing is None or abs(_decimal_value(position.get("market_value_start"))) > abs(
            _decimal_value(existing.get("market_value_start"))
        ):
            out[key] = position
    return out


def _formal_bridge_has_position_overlap(
    bridge_envelope: dict[str, Any] | None,
    positions: list[dict[str, Any]],
) -> bool:
    position_keys = set(_position_lookup(positions))
    if not position_keys:
        return False
    return any(_bridge_position_key(row) in position_keys for row in _formal_bridge_rows(bridge_envelope))


def _formal_asset_class(row: dict[str, Any], position: dict[str, Any] | None) -> str:
    asset_class = _text_value((position or {}).get("asset_class_start"))
    accounting_basis = _text_value(row.get("accounting_basis"))
    if asset_class and accounting_basis and accounting_basis.upper() not in asset_class.upper():
        return f"{asset_class} {accounting_basis}"
    return asset_class or accounting_basis or "unclassified"


def _coerce_date(value: Any) -> date | None:
    if hasattr(value, "date"):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text_value(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _formal_maturity_bucket(position: dict[str, Any] | None, start_date: date) -> str:
    maturity = _coerce_date((position or {}).get("maturity_date_start"))
    if maturity is None:
        return "UNKNOWN"
    years = max((maturity - start_date).days / 365.0, 0.01)
    if years <= 1:
        return _MATURITY_BUCKET_LABELS[0]
    if years <= 3:
        return _MATURITY_BUCKET_LABELS[1]
    if years <= 5:
        return _MATURITY_BUCKET_LABELS[2]
    if years <= 7:
        return _MATURITY_BUCKET_LABELS[3]
    if years <= 10:
        return _MATURITY_BUCKET_LABELS[4]
    return _MATURITY_BUCKET_LABELS[5]


def _formal_bridge_bond_rows(
    *,
    bridge_envelope: dict[str, Any],
    positions: list[dict[str, Any]],
    start_date: date,
    enhanced: bool = False,
) -> list[dict[str, Any]]:
    position_by_key = _position_lookup(positions)
    rows: list[dict[str, Any]] = []
    for bridge_row in _formal_bridge_rows(bridge_envelope):
        position = position_by_key.get(_bridge_position_key(bridge_row))
        income = _numeric_raw(bridge_row.get("carry"))
        treasury = _numeric_raw(bridge_row.get("roll_down")) + _numeric_raw(bridge_row.get("treasury_curve"))
        spread = _numeric_raw(bridge_row.get("credit_spread"))
        convexity = Decimal("0")
        cross = Decimal("0")
        reinvestment = Decimal("0")
        total = _numeric_raw(bridge_row.get("actual_pnl"))
        selection = total - income - treasury - spread - convexity - cross - reinvestment
        record = {
            "bond_code": _text_value(bridge_row.get("instrument_code")),
            "asset_class": _formal_asset_class(bridge_row, position),
            "maturity_bucket": _formal_maturity_bucket(position, start_date),
            "market_value_start": float(
                _numeric_raw(bridge_row.get("beginning_dirty_mv"))
                or _decimal_value((position or {}).get("market_value_start"))
            ),
            "income_return": float(income),
            "treasury_effect": float(treasury),
            "spread_effect": float(spread),
            "selection_effect": float(selection),
            "total_return": float(total),
            "mod_duration": float(_decimal_value((position or {}).get("mod_duration"))),
            "has_accrued_interest": not _is_missing((position or {}).get("accrued_interest_start")),
        }
        if enhanced:
            record.update(
                {
                    "convexity_effect": float(convexity),
                    "cross_effect": float(cross),
                    "reinvestment_effect": float(reinvestment),
                }
            )
        rows.append(record)
    return rows


def _formal_amount_keys(*, enhanced: bool = False) -> list[str]:
    keys = ["income_return", "treasury_effect", "spread_effect"]
    if enhanced:
        keys.extend(["convexity_effect", "cross_effect", "reinvestment_effect"])
    keys.extend(["selection_effect", "total_return"])
    return keys


def _aggregate_formal_rows(rows: list[dict[str, Any]], *, enhanced: bool = False) -> list[dict[str, Any]]:
    amount_keys = _formal_amount_keys(enhanced=enhanced)
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        asset_class = _text_value(row.get("asset_class")) or "unclassified"
        bucket = buckets.setdefault(
            asset_class,
            {
                "asset_class": asset_class,
                "market_value_start": Decimal("0"),
                **{key: Decimal("0") for key in amount_keys},
            },
        )
        bucket["market_value_start"] += _decimal_value(row.get("market_value_start"))
        for key in amount_keys:
            bucket[key] += _decimal_value(row.get(key))
    total_mv = sum((_decimal_value(row["market_value_start"]) for row in buckets.values()), Decimal("0"))
    out: list[dict[str, Any]] = []
    for bucket in buckets.values():
        market_value = _decimal_value(bucket["market_value_start"])
        row = {key: float(value) if isinstance(value, Decimal) else value for key, value in bucket.items()}
        row["weight_pct"] = float(market_value / total_mv * Decimal("100")) if total_mv else 0.0
        out.append(row)
    return sorted(out, key=lambda row: -abs(float(row.get("total_return") or 0)))


def _formal_totals(rows: list[dict[str, Any]], *, enhanced: bool = False) -> dict[str, float]:
    keys = [*_formal_amount_keys(enhanced=enhanced), "market_value_start"]
    return {
        key: float(sum((_decimal_value(row.get(key)) for row in rows), Decimal("0")))
        for key in keys
    }


def _formal_bridge_to_campisi_result(
    *,
    bridge_envelope: dict[str, Any],
    positions: list[dict[str, Any]],
    start_date: date,
    end_date: date,
) -> CampisiResult:
    by_bond = _formal_bridge_bond_rows(
        bridge_envelope=bridge_envelope,
        positions=positions,
        start_date=start_date,
    )
    return CampisiResult(
        num_days=max((end_date - start_date).days, 1),
        totals=_formal_totals(by_bond),
        by_asset_class=_aggregate_formal_rows(by_bond),
        by_bond=by_bond,
        diagnostics=[],
    )


def _formal_bridge_to_enhanced_result(
    *,
    bridge_envelope: dict[str, Any],
    positions: list[dict[str, Any]],
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    by_bond = _formal_bridge_bond_rows(
        bridge_envelope=bridge_envelope,
        positions=positions,
        start_date=start_date,
        enhanced=True,
    )
    return {
        "num_days": max((end_date - start_date).days, 1),
        "totals": _formal_totals(by_bond, enhanced=True),
        "by_asset_class": _aggregate_formal_rows(by_bond, enhanced=True),
        "by_bond": by_bond,
        "diagnostics": [],
        "basis": FORMAL_REPORT_BASIS,
    }


def _formal_bridge_to_maturity_buckets(
    *,
    bridge_envelope: dict[str, Any],
    positions: list[dict[str, Any]],
    start_date: date,
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {
        label: {
            "market_value_start": 0.0,
            "income_return": 0.0,
            "treasury_effect": 0.0,
            "spread_effect": 0.0,
            "selection_effect": 0.0,
            "total_return": 0.0,
        }
        for label in _MATURITY_BUCKET_LABELS
    }
    for row in _formal_bridge_bond_rows(
        bridge_envelope=bridge_envelope,
        positions=positions,
        start_date=start_date,
    ):
        bucket_name = _text_value(row.get("maturity_bucket")) or "UNKNOWN"
        bucket = out.setdefault(
            bucket_name,
            {
                "market_value_start": 0.0,
                "income_return": 0.0,
                "treasury_effect": 0.0,
                "spread_effect": 0.0,
                "selection_effect": 0.0,
                "total_return": 0.0,
            },
        )
        for key in bucket:
            bucket[key] += float(row.get(key) or 0.0)
    return out


def _build_formal_closure(
    *,
    report_date: str,
    campisi_total_return: Decimal,
    bridge_envelope: dict[str, Any],
) -> dict[str, Any]:
    summary = (bridge_envelope.get("result") or {}).get("summary") or {}
    meta = bridge_envelope.get("result_meta") or {}
    formal_actual_pnl = _decimal_value((summary.get("total_actual_pnl") or {}).get("raw"))
    residual = formal_actual_pnl - campisi_total_return
    residual_ratio = (
        abs(residual) / abs(formal_actual_pnl)
        if formal_actual_pnl != 0
        else (Decimal("0") if residual == 0 else None)
    )
    status = "closed" if abs(residual) <= Decimal("1.00") else "warning"
    message = (
        "Campisi total return does not close to formal PnL; "
        "residual_to_formal_pnl is required."
        if status == "warning"
        else "Campisi total return closes to formal PnL."
    )
    return {
        "basis": "pnl.bridge.total_actual_pnl",
        "report_date": report_date,
        "status": status,
        "campisi_total_return": float(campisi_total_return),
        "formal_actual_pnl": float(formal_actual_pnl),
        "residual_to_formal_pnl": float(residual),
        "residual_ratio": float(residual_ratio) if residual_ratio is not None else None,
        "bridge_quality_flag": meta.get("quality_flag"),
        "bridge_vendor_status": meta.get("vendor_status"),
        "bridge_fallback_mode": meta.get("fallback_mode"),
        "message": message,
    }


def _formal_closure_unavailable(
    *,
    report_date: str,
    campisi_total_return: Decimal,
    reason: str,
) -> dict[str, Any]:
    return {
        "basis": "pnl.bridge.total_actual_pnl",
        "report_date": report_date,
        "status": "unavailable",
        "campisi_total_return": float(campisi_total_return),
        "formal_actual_pnl": None,
        "residual_to_formal_pnl": None,
        "residual_ratio": None,
        "bridge_quality_flag": None,
        "bridge_vendor_status": None,
        "bridge_fallback_mode": None,
        "message": f"Formal PnL bridge unavailable for Campisi closure: {reason}",
    }


def _fetch_formal_closure(
    *,
    settings: Any,
    report_date: str,
    campisi_total_return: Decimal,
) -> dict[str, Any]:
    try:
        bridge = _fetch_formal_bridge(settings=settings, report_date=report_date)
    except Exception as exc:  # pragma: no cover - formal bridge availability is data/runtime dependent.
        return _formal_closure_unavailable(
            report_date=report_date,
            campisi_total_return=campisi_total_return,
            reason=str(exc),
        )
    return _build_formal_closure(
        report_date=report_date,
        campisi_total_return=campisi_total_return,
        bridge_envelope=bridge,
    )


def _result_to_payload(
    result: CampisiResult,
    start: str,
    end: str,
    input_quality: dict[str, Any] | None = None,
    formal_closure: dict[str, Any] | None = None,
    basis: str | None = None,
) -> dict[str, Any]:
    payload = {
        "report_date": end,
        "period_start": start,
        "period_end": end,
        "num_days": result.num_days,
        "totals": result.totals,
        "by_asset_class": result.by_asset_class,
        "by_bond": result.by_bond,
    }
    if basis is not None:
        payload["basis"] = basis
    if input_quality is not None:
        payload["input_quality"] = input_quality
        warnings = list(input_quality["warnings"])
        if formal_closure is not None and formal_closure.get("status") != "closed":
            warnings.append(str(formal_closure.get("message") or "Campisi formal closure warning."))
        payload["warnings"] = warnings
    if formal_closure is not None:
        payload["formal_closure"] = formal_closure
    payload["diagnostics"] = list(result.diagnostics)
    return payload


def _meta_with_quality(
    result_kind: str,
    input_quality: dict[str, Any],
    formal_closure: dict[str, Any] | None = None,
    *,
    filters_applied: dict[str, object] | None = None,
    tables_used: list[str] | None = None,
    evidence_rows: int | None = None,
    as_of_date: str | None = None,
):
    has_closure_warning = formal_closure is not None and formal_closure.get("status") != "closed"
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=CACHE_VERSION,
        source_version=SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag="warning" if input_quality["warnings"] or has_closure_warning else None,
        filters_applied=filters_applied,
        tables_used=tables_used,
        evidence_rows=evidence_rows,
        source_surface="formal_attribution",
        as_of_date=as_of_date,
    )


_DECISION_EFFECT_LABELS = {
    "carry": ("票息/Carry", "自然持有收益，不直接算主动能力"),
    "rate_level_effect": ("利率水平", "市场利率 beta / 久期仓位贡献"),
    "curve_shape_effect": ("曲线形态", "期限结构策略能力代理"),
    "credit_spread_effect": ("信用利差", "信用 beta，需结合同类比较"),
    "convexity_effect": ("凸性", "二阶市场敏感性贡献"),
    "realized_trading": ("已实现交易", "交易实现贡献，不等同实名交易员评价"),
    "manual_adjustment": ("手工调整", "治理调整，不算能力"),
    "selection_proxy": ("剩余/选券代理", "组合/成本中心主动管理代理，不是交易员能力"),
    "residual_noise": ("残差/噪音", "缺曲线、估值噪音或数据质量问题，不算能力"),
}


def _empty_decision_grade_payload(start: str, end: str, warnings: list[str] | None = None) -> dict[str, Any]:
    zero_components = {key: 0.0 for key in _DECISION_EFFECT_LABELS}
    return {
        "basis": "campisi_decision_grade_v1",
        "report_date": end,
        "period_start": start,
        "period_end": end,
        "num_days": 0,
        "summary": {
            "formal_actual_pnl": 0.0,
            "explained_pnl": 0.0,
            "residual_noise": 0.0,
            "residual_ratio": 0.0,
            "valuation_change_516": 0.0,
            "fvoci_valuation_change_516": 0.0,
            "fvtpl_valuation_change_516": 0.0,
            "main_driver": "none",
            "quality_flag": "warning",
            "bond_scope_row_count": 0,
            "out_of_scope_pnl_row_count": 0,
        },
        "formal_pnl_view": {
            "total_actual_pnl": 0.0,
            "explained_pnl": 0.0,
            "residual_noise": 0.0,
            "components": zero_components,
        },
        "valuation_oci_view": {
            "total_valuation_change_516": 0.0,
            "fvoci_valuation_change_516": 0.0,
            "fvtpl_valuation_change_516": 0.0,
            "rows_by_accounting_basis": [],
        },
        "effects": [],
        "accounting_matrix": {},
        "ability_matrix": [],
            "residual_diagnostics": {
                "missing_curve_count": 0,
                "missing_spread_count": 0,
                "duplicate_position_keys": 0,
                "aggregated_position_groups": 0,
                "unmatched_pnl_rows": 0,
                "stale_curve_fallback_count": 0,
                "warnings": list(warnings or []),
        },
        "warnings": list(warnings or []),
    }


def _duckdb_rows(conn: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cursor = conn.execute(sql, params)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def _decision_table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    try:
        return bool(
            conn.execute(
                "select count(*) from information_schema.tables where table_name = ?",
                [table_name],
            ).fetchone()[0]
        )
    except Exception:
        return False


def _decision_table_dates(conn: duckdb.DuckDBPyConnection, table_name: str, date_col: str) -> list[str]:
    if not _decision_table_exists(conn, table_name):
        return []
    rows = conn.execute(
        f"""
        select distinct cast({date_col} as varchar) as report_date
        from {table_name}
        where {date_col} is not null
        order by report_date desc
        """
    ).fetchall()
    return [str(row[0])[:10] for row in rows]


def _resolve_decision_dates(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str | None,
    end_date: str | None,
    lookback_days: int,
) -> tuple[str | None, str | None, str, str]:
    pnl_dates = _decision_table_dates(conn, "fact_formal_pnl_fi", "report_date")
    position_dates = sorted(
        set(
            _decision_table_dates(conn, "fact_formal_bond_analytics_daily", "report_date")
            + _decision_table_dates(conn, "fact_formal_zqtz_balance_daily", "report_date")
        ),
        reverse=True,
    )
    all_dates = sorted(set(pnl_dates + position_dates), reverse=True)
    rd_end = end_date or (pnl_dates[0] if pnl_dates else (all_dates[0] if all_dates else ""))
    rd_start = start_date or (
        (date.fromisoformat(rd_end) - timedelta(days=max(1, lookback_days))).isoformat() if rd_end else ""
    )
    anchor_end = (rd_end if rd_end in pnl_dates else _anchor_on_or_before(pnl_dates, rd_end)) or _anchor_on_or_before(
        all_dates,
        rd_end,
    )
    anchor_start = _anchor_on_or_before(position_dates, rd_start) or _anchor_on_or_before(position_dates, anchor_end or "")
    return anchor_start, anchor_end, rd_start, rd_end


def _decision_key(row: dict[str, Any], *, accounting_field: str, currency_field: str) -> tuple[str, str, str, str, str]:
    return (
        _text_value(row.get("instrument_code")),
        _text_value(row.get("portfolio_name")),
        _text_value(row.get("cost_center")),
        normalize_accounting_basis(row.get(accounting_field)),
        _text_value(row.get(currency_field) or row.get("currency_basis") or row.get("currency_code") or "CNY"),
    )


def _decision_loose_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _text_value(row.get("instrument_code")),
        _text_value(row.get("portfolio_name")),
        _text_value(row.get("cost_center")),
    )


def _lookup_unique(loose: dict[tuple[str, str, str], list[dict[str, Any]]], row: dict[str, Any]) -> dict[str, Any] | None:
    matches = loose.get(_decision_loose_key(row), [])
    return matches[0] if len(matches) == 1 else None


def _fetch_decision_pnl_rows(conn: duckdb.DuckDBPyConnection, report_date: str) -> list[dict[str, Any]]:
    if not _decision_table_exists(conn, "fact_formal_pnl_fi"):
        return []
    return _duckdb_rows(
        conn,
        """
        select
            instrument_code,
            portfolio_name,
            cost_center,
            max(invest_type_std) as invest_type_std,
            accounting_basis,
            currency_basis,
            sum(coalesce(interest_income_514, 0)) as interest_income_514,
            sum(coalesce(fair_value_change_516, 0)) as fair_value_change_516,
            sum(coalesce(capital_gain_517, 0)) as capital_gain_517,
            sum(coalesce(manual_adjustment, 0)) as manual_adjustment,
            sum(coalesce(total_pnl, 0)) as total_pnl,
            count(*) as source_row_count
        from fact_formal_pnl_fi
        where cast(report_date as date) = cast(? as date)
        group by instrument_code, portfolio_name, cost_center, accounting_basis, currency_basis
        """,
        [report_date],
    )


def _fetch_decision_analytics_rows(conn: duckdb.DuckDBPyConnection, report_date: str) -> list[dict[str, Any]]:
    if not _decision_table_exists(conn, "fact_formal_bond_analytics_daily"):
        return []
    return _duckdb_rows(
        conn,
        """
        select
            instrument_code,
            max(instrument_name) as instrument_name,
            portfolio_name,
            cost_center,
            max(asset_class_std) as asset_class_std,
            max(bond_type) as bond_type,
            max(rating) as rating,
            accounting_class,
            currency_code,
            sum(coalesce(face_value, 0)) as face_value,
            sum(coalesce(market_value, 0)) as market_value,
            sum(coalesce(amortized_cost, 0)) as amortized_cost,
            sum(coalesce(accrued_interest, 0)) as accrued_interest,
            case
                when sum(abs(coalesce(market_value, 0))) = 0 then avg(coupon_rate)
                else sum(coalesce(coupon_rate, 0) * abs(coalesce(market_value, 0))) / sum(abs(coalesce(market_value, 0)))
            end as coupon_rate,
            case
                when sum(abs(coalesce(market_value, 0))) = 0 then avg(ytm)
                else sum(coalesce(ytm, 0) * abs(coalesce(market_value, 0))) / sum(abs(coalesce(market_value, 0)))
            end as ytm,
            min(maturity_date) as maturity_date,
            case
                when sum(abs(coalesce(market_value, 0))) = 0 then avg(years_to_maturity)
                else sum(coalesce(years_to_maturity, 0) * abs(coalesce(market_value, 0))) / sum(abs(coalesce(market_value, 0)))
            end as years_to_maturity,
            max(tenor_bucket) as tenor_bucket,
            case
                when sum(abs(coalesce(market_value, 0))) = 0 then avg(modified_duration)
                else sum(coalesce(modified_duration, 0) * abs(coalesce(market_value, 0))) / sum(abs(coalesce(market_value, 0)))
            end as modified_duration,
            case
                when sum(abs(coalesce(market_value, 0))) = 0 then avg(convexity)
                else sum(coalesce(convexity, 0) * abs(coalesce(market_value, 0))) / sum(abs(coalesce(market_value, 0)))
            end as convexity,
            sum(coalesce(dv01, 0)) as dv01,
            max(case when coalesce(is_credit, false) then 1 else 0 end) as is_credit,
            sum(coalesce(spread_dv01, 0)) as spread_dv01,
            count(*) as source_row_count
        from fact_formal_bond_analytics_daily
        where cast(report_date as date) = cast(? as date)
        group by instrument_code, portfolio_name, cost_center, accounting_class, currency_code
        """,
        [report_date],
    )


def _fetch_decision_balance_rows(conn: duckdb.DuckDBPyConnection, report_date: str) -> list[dict[str, Any]]:
    if not _decision_table_exists(conn, "fact_formal_zqtz_balance_daily"):
        return []
    return _duckdb_rows(
        conn,
        """
        select
            instrument_code,
            max(instrument_name) as instrument_name,
            portfolio_name,
            cost_center,
            max(asset_class) as asset_class,
            max(bond_type) as bond_type,
            max(rating) as rating,
            max(invest_type_std) as invest_type_std,
            accounting_basis,
            currency_code,
            sum(coalesce(face_value_amount, 0)) as face_value_amount,
            sum(coalesce(market_value_amount, 0)) as market_value_amount,
            sum(coalesce(amortized_cost_amount, 0)) as amortized_cost_amount,
            sum(coalesce(accrued_interest_amount, 0)) as accrued_interest_amount,
            case
                when sum(abs(coalesce(market_value_amount, 0))) = 0 then avg(coupon_rate)
                else sum(coalesce(coupon_rate, 0) * abs(coalesce(market_value_amount, 0))) / sum(abs(coalesce(market_value_amount, 0)))
            end as coupon_rate,
            case
                when sum(abs(coalesce(market_value_amount, 0))) = 0 then avg(ytm_value)
                else sum(coalesce(ytm_value, 0) * abs(coalesce(market_value_amount, 0))) / sum(abs(coalesce(market_value_amount, 0)))
            end as ytm_value,
            min(maturity_date) as maturity_date,
            count(*) as source_row_count
        from fact_formal_zqtz_balance_daily
        where cast(report_date as date) = cast(? as date)
          and lower(coalesce(position_scope, 'asset')) = 'asset'
          and coalesce(is_issuance_like, false) = false
        group by instrument_code, portfolio_name, cost_center, accounting_basis, currency_code
        """,
        [report_date],
    )


def _index_decision_rows(
    rows: list[dict[str, Any]],
    *,
    accounting_field: str,
    currency_field: str,
) -> tuple[dict[tuple[str, str, str, str, str], dict[str, Any]], dict[tuple[str, str, str], list[dict[str, Any]]]]:
    strict: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    loose: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        strict[_decision_key(row, accounting_field=accounting_field, currency_field=currency_field)] = row
        loose[_decision_loose_key(row)].append(row)
    return strict, loose


def _fetch_decision_curve(
    conn: duckdb.DuckDBPyConnection,
    *,
    requested_date: str,
    curve_type: str,
) -> tuple[dict[str, Decimal], str | None]:
    if not _decision_table_exists(conn, "fact_formal_yield_curve_daily"):
        return {}, None
    row = conn.execute(
        """
        select max(cast(trade_date as date))
        from fact_formal_yield_curve_daily
        where curve_type = ?
          and cast(trade_date as date) <= cast(? as date)
        """,
        [curve_type, requested_date],
    ).fetchone()
    resolved = str(row[0])[:10] if row and row[0] is not None else None
    if not resolved:
        return {}, None
    records = _duckdb_rows(
        conn,
        """
        select tenor, rate_pct
        from fact_formal_yield_curve_daily
        where curve_type = ?
          and cast(trade_date as date) = cast(? as date)
        """,
        [curve_type, resolved],
    )
    return {str(record["tenor"]).upper(): _decimal_value(record.get("rate_pct")) for record in records}, resolved


def _fetch_decision_curves(
    conn: duckdb.DuckDBPyConnection,
    *,
    anchor_start: str,
    anchor_end: str,
) -> tuple[dict[str, Any], list[str], int]:
    warnings: list[str] = []
    fallback_count = 0
    treasury_start, treasury_start_date = _fetch_decision_curve(
        conn,
        requested_date=anchor_start,
        curve_type="treasury",
    )
    treasury_end, treasury_end_date = _fetch_decision_curve(
        conn,
        requested_date=anchor_end,
        curve_type="treasury",
    )
    for label, requested, resolved in (
        ("期初国债曲线", anchor_start, treasury_start_date),
        ("期末国债曲线", anchor_end, treasury_end_date),
    ):
        if not resolved:
            warnings.append(f"{label}缺失，相关利率影响进入残差噪音。")
        elif resolved != requested:
            fallback_count += 1
            warnings.append(f"{label}使用 {resolved} 只读 fallback，目标日期为 {requested}。")

    credit_start_by_rating: dict[str, dict[str, Decimal]] = {}
    credit_end_by_rating: dict[str, dict[str, Decimal]] = {}
    for rating, curve_type in _FORMAL_CREDIT_CURVE_TYPES.items():
        start_curve, start_resolved = _fetch_decision_curve(
            conn,
            requested_date=anchor_start,
            curve_type=curve_type,
        )
        end_curve, end_resolved = _fetch_decision_curve(
            conn,
            requested_date=anchor_end,
            curve_type=curve_type,
        )
        if start_curve:
            credit_start_by_rating[rating] = start_curve
        if end_curve:
            credit_end_by_rating[rating] = end_curve
        for label, requested, resolved in (
            (f"期初{rating}信用曲线", anchor_start, start_resolved),
            (f"期末{rating}信用曲线", anchor_end, end_resolved),
        ):
            if resolved and resolved != requested:
                fallback_count += 1
                warnings.append(f"{label}使用 {resolved} 只读 fallback，目标日期为 {requested}。")

    return (
        {
            "treasury_start": treasury_start,
            "treasury_end": treasury_end,
            "credit_start_by_rating": credit_start_by_rating,
            "credit_end_by_rating": credit_end_by_rating,
        },
        warnings,
        fallback_count,
    )


def _fetch_decision_risk_tensor_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    component_dv01: Decimal,
    component_cs01: Decimal,
) -> dict[str, Any]:
    if not _decision_table_exists(conn, "fact_formal_risk_tensor_daily"):
        return {
            "available": False,
            "message": "fact_formal_risk_tensor_daily 不可用，无法做组合级 DV01/CS01 校验。",
        }
    rows = _duckdb_rows(
        conn,
        """
        select
            sum(coalesce(portfolio_dv01, 0)) as portfolio_dv01,
            sum(coalesce(cs01, 0)) as cs01,
            sum(coalesce(total_market_value, 0)) as total_market_value,
            sum(coalesce(bond_count, 0)) as bond_count,
            max(quality_flag) as quality_flag
        from fact_formal_risk_tensor_daily
        where cast(report_date as date) = cast(? as date)
        """,
        [report_date],
    )
    row = rows[0] if rows else {}
    portfolio_dv01 = _decimal_value(row.get("portfolio_dv01"))
    cs01 = _decimal_value(row.get("cs01"))
    return {
        "available": bool(rows),
        "portfolio_dv01": float(portfolio_dv01),
        "component_dv01": float(component_dv01),
        "dv01_difference": float(component_dv01 - portfolio_dv01),
        "portfolio_cs01": float(cs01),
        "component_cs01": float(component_cs01),
        "cs01_difference": float(component_cs01 - cs01),
        "quality_flag": row.get("quality_flag") or "unknown",
        "total_market_value": float(_decimal_value(row.get("total_market_value"))),
        "bond_count": int(_decimal_value(row.get("bond_count"))),
    }


def _decision_float_components(components: dict[str, Decimal]) -> dict[str, float]:
    return {key: float(components.get(key, Decimal("0"))) for key in _DECISION_EFFECT_LABELS}


def _decision_effect_rows(components: dict[str, Decimal]) -> list[dict[str, Any]]:
    rows = []
    for key, amount in components.items():
        label, ability_treatment = _DECISION_EFFECT_LABELS[key]
        rows.append(
            {
                "key": key,
                "label": label,
                "amount": float(amount),
                "ability_treatment": ability_treatment,
            }
        )
    return rows


def _accounting_interpretation(accounting_basis: str) -> str:
    if accounting_basis == "AC":
        return "主要看票息/摊余成本收益；公允价值变动不作为本视图核心解释项。"
    if accounting_basis == "FVOCI":
        return "516 不进入正式 PnL，但进入估值/OCI 解释视图。"
    if accounting_basis == "FVTPL":
        return "516 进入正式 PnL，也进入估值解释视图。"
    return "会计分类未标准化，需结合源数据确认。"


def _decision_ability_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (_text_value(row.get("portfolio_name")) or "未分组合", _text_value(row.get("cost_center")) or "未分成本中心")
        bucket = grouped.setdefault(
            key,
            {
                "portfolio_name": key[0],
                "cost_center": key[1],
                "carry": Decimal("0"),
                "market_beta": Decimal("0"),
                "strategy_proxy": Decimal("0"),
                "credit_proxy": Decimal("0"),
                "selection_proxy": Decimal("0"),
                "residual_noise": Decimal("0"),
                "total_actual_pnl": Decimal("0"),
                "warnings": [],
            },
        )
        components = row["components"]
        bucket["carry"] += components["carry"]
        bucket["market_beta"] += (
            components["rate_level_effect"]
            + components["credit_spread_effect"]
            + components["convexity_effect"]
        )
        bucket["strategy_proxy"] += components["curve_shape_effect"]
        bucket["credit_proxy"] += components["credit_spread_effect"]
        bucket["selection_proxy"] += components["selection_proxy"]
        bucket["residual_noise"] += components["residual_noise"]
        bucket["total_actual_pnl"] += row["actual_pnl"]
        bucket["warnings"].extend(row.get("diagnostics") or [])

    out: list[dict[str, Any]] = []
    for bucket in grouped.values():
        residual = bucket["residual_noise"]
        confidence = "low" if abs(residual) > Decimal("0.01") or bucket["warnings"] else "medium"
        out.append(
            {
                "portfolio_name": bucket["portfolio_name"],
                "cost_center": bucket["cost_center"],
                "carry": float(bucket["carry"]),
                "market_beta": float(bucket["market_beta"]),
                "strategy_proxy": float(bucket["strategy_proxy"]),
                "credit_proxy": float(bucket["credit_proxy"]),
                "selection_proxy": float(bucket["selection_proxy"]),
                "residual_noise": float(bucket["residual_noise"]),
                "total_actual_pnl": float(bucket["total_actual_pnl"]),
                "confidence": confidence,
                "notes": "组合/成本中心代理，不是实名交易员评价；票息和残差不算主动能力。",
            }
        )
    return sorted(out, key=lambda item: abs(float(item["total_actual_pnl"])), reverse=True)


def campisi_decision_grade_envelope(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int = 30,
) -> dict[str, object]:
    settings = get_settings()
    filters: dict[str, object] = {
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "lookback_days": lookback_days,
        "scope": "bond_investment_assets_only",
    }
    try:
        conn = duckdb.connect(str(settings.duckdb_path), read_only=True)
    except Exception as exc:
        payload = _empty_decision_grade_payload("", "", [f"DuckDB 只读连接失败：{exc}"])
        return build_formal_result_envelope(
            result_meta=_meta_warn(
                "campisi.decision_grade",
                filters_applied=filters,
                tables_used=TABLES_CAMPISI_DECISION_GRADE,
                evidence_rows=0,
            ),
            result_payload=payload,
        )

    try:
        anchor_start, anchor_end, rd_start, rd_end = _resolve_decision_dates(
            conn,
            start_date=start_date,
            end_date=end_date,
            lookback_days=lookback_days,
        )
        filters.update(
            {
                "resolved_start_date": anchor_start,
                "resolved_end_date": anchor_end,
            }
        )
        if not anchor_start or not anchor_end:
            payload = _empty_decision_grade_payload(rd_start, rd_end, ["缺少正式 PnL 或债券持仓/analytics 日期。"])
            return build_formal_result_envelope(
                result_meta=_meta_warn(
                    "campisi.decision_grade",
                    filters_applied=filters,
                    tables_used=TABLES_CAMPISI_DECISION_GRADE,
                    evidence_rows=0,
                    as_of_date=anchor_end,
                ),
                result_payload=payload,
            )

        pnl_rows = _fetch_decision_pnl_rows(conn, anchor_end)
        analytics_rows = _fetch_decision_analytics_rows(conn, anchor_start)
        balance_rows = _fetch_decision_balance_rows(conn, anchor_start)
        analytics_by_key, analytics_loose = _index_decision_rows(
            analytics_rows,
            accounting_field="accounting_class",
            currency_field="currency_code",
        )
        balance_by_key, balance_loose = _index_decision_rows(
            balance_rows,
            accounting_field="accounting_basis",
            currency_field="currency_code",
        )
        curves, curve_warnings, stale_curve_fallback_count = _fetch_decision_curves(
            conn,
            anchor_start=anchor_start,
            anchor_end=anchor_end,
        )

        computed_rows: list[dict[str, Any]] = []
        warnings: list[str] = list(curve_warnings)
        out_of_scope_rows = 0
        duplicate_position_keys = 0
        aggregated_position_groups = 0
        accounting_matrix: dict[str, dict[str, Any]] = {}

        for pnl_row in pnl_rows:
            strict_key = _decision_key(
                pnl_row,
                accounting_field="accounting_basis",
                currency_field="currency_basis",
            )
            analytics = analytics_by_key.get(strict_key) or _lookup_unique(analytics_loose, pnl_row)
            balance = balance_by_key.get(strict_key) or _lookup_unique(balance_loose, pnl_row)
            if analytics is None and balance is None:
                out_of_scope_rows += 1
                continue

            accounting_basis = normalize_accounting_basis(pnl_row.get("accounting_basis"))
            matrix_row = accounting_matrix.setdefault(
                accounting_basis,
                {
                    "accounting_basis": accounting_basis,
                    "formal_pnl": Decimal("0"),
                    "valuation_or_oci_516": Decimal("0"),
                    "interpretation": _accounting_interpretation(accounting_basis),
                },
            )
            matrix_row["formal_pnl"] += _decimal_value(pnl_row.get("total_pnl"))
            matrix_row["valuation_or_oci_516"] += _decimal_value(pnl_row.get("fair_value_change_516"))

            duplicate_key = (
                _decimal_value((analytics or {}).get("source_row_count")) > 1
                or _decimal_value((balance or {}).get("source_row_count")) > 1
            )
            if duplicate_key:
                aggregated_position_groups += 1
            market_value = (analytics or {}).get("market_value")
            if _is_missing(market_value):
                market_value = (balance or {}).get("market_value_amount")
            row_input = {
                "actual_pnl": pnl_row.get("total_pnl"),
                "carry": pnl_row.get("interest_income_514"),
                "realized_trading": pnl_row.get("capital_gain_517"),
                "manual_adjustment": pnl_row.get("manual_adjustment"),
                "market_value": market_value,
                "modified_duration": (analytics or {}).get("modified_duration"),
                "convexity": (analytics or {}).get("convexity"),
                "spread_dv01": (analytics or {}).get("spread_dv01"),
                "years_to_maturity": (analytics or balance or {}).get("years_to_maturity"),
                "rating": (analytics or balance or {}).get("rating"),
                "is_credit": bool((analytics or {}).get("is_credit"))
                or "credit" in _text_value((analytics or balance or {}).get("asset_class_std") or (balance or {}).get("asset_class")).lower(),
                "duplicate_position_key": duplicate_key,
                "duplicate_position_key_is_ambiguous": False,
                "missing_analytics": analytics is None,
                "include_market_effects_in_formal_pnl": accounting_basis == "FVTPL",
            }
            computed = compute_decision_grade_row(
                row_input,
                treasury_start=curves["treasury_start"],
                treasury_end=curves["treasury_end"],
                credit_start_by_rating=curves["credit_start_by_rating"],
                credit_end_by_rating=curves["credit_end_by_rating"],
            )
            computed.update(
                {
                    "instrument_code": pnl_row.get("instrument_code"),
                    "portfolio_name": pnl_row.get("portfolio_name"),
                    "cost_center": pnl_row.get("cost_center"),
                    "accounting_basis": accounting_basis,
                    "fair_value_change_516": _decimal_value(pnl_row.get("fair_value_change_516")),
                    "market_value": campisi_decision_decimal(market_value),
                }
            )
            warnings.extend(computed.get("diagnostics") or [])
            computed_rows.append(computed)

        totals = {key: Decimal("0") for key in _DECISION_EFFECT_LABELS}
        formal_actual_pnl = Decimal("0")
        explained_pnl = Decimal("0")
        valuation_total = Decimal("0")
        fvoci_valuation = Decimal("0")
        fvtpl_valuation = Decimal("0")
        component_dv01 = Decimal("0")
        component_cs01 = Decimal("0")
        missing_curve_count = 0
        missing_spread_count = 0
        for row in computed_rows:
            formal_actual_pnl += row["actual_pnl"]
            explained_pnl += row["explained_pnl"]
            valuation = row["fair_value_change_516"]
            valuation_total += valuation
            if row["accounting_basis"] == "FVOCI":
                fvoci_valuation += valuation
            if row["accounting_basis"] == "FVTPL":
                fvtpl_valuation += valuation
            for key in totals:
                totals[key] += row["components"][key]
            reasons = set(row.get("residual_reasons") or [])
            if {"missing_treasury_curve", "missing_convexity_curve"} & reasons:
                missing_curve_count += 1
            if "missing_credit_curve" in reasons:
                missing_spread_count += 1
            component_dv01 += abs(_decimal_value(row.get("market_value"))) * Decimal("0")

        for row in analytics_rows:
            component_dv01 += _decimal_value(row.get("dv01"))
            component_cs01 += _decimal_value(row.get("spread_dv01"))

        residual_noise = totals["residual_noise"]
        residual_ratio = float(abs(residual_noise) / abs(formal_actual_pnl)) if formal_actual_pnl else 0.0
        quality_flag = "warning" if warnings or abs(residual_noise) > Decimal("0.01") else "ok"
        risk_tensor_check = _fetch_decision_risk_tensor_check(
            conn,
            report_date=anchor_end,
            component_dv01=component_dv01,
            component_cs01=component_cs01,
        )

        rows_by_accounting = []
        accounting_matrix_json: dict[str, dict[str, Any]] = {}
        for accounting_basis, row in sorted(accounting_matrix.items()):
            formatted = {
                "accounting_basis": accounting_basis,
                "formal_pnl": float(row["formal_pnl"]),
                "valuation_or_oci_516": float(row["valuation_or_oci_516"]),
                "interpretation": row["interpretation"],
            }
            rows_by_accounting.append(formatted)
            accounting_matrix_json[accounting_basis] = formatted

        payload = {
            "basis": "campisi_decision_grade_v1",
            "report_date": anchor_end,
            "period_start": anchor_start,
            "period_end": anchor_end,
            "num_days": max((date.fromisoformat(anchor_end) - date.fromisoformat(anchor_start)).days, 0),
            "summary": {
                "formal_actual_pnl": float(formal_actual_pnl),
                "explained_pnl": float(explained_pnl),
                "residual_noise": float(residual_noise),
                "residual_ratio": residual_ratio,
                "valuation_change_516": float(valuation_total),
                "fvoci_valuation_change_516": float(fvoci_valuation),
                "fvtpl_valuation_change_516": float(fvtpl_valuation),
                "main_driver": primary_driver(totals),
                "quality_flag": quality_flag,
                "bond_scope_row_count": len(computed_rows),
                "out_of_scope_pnl_row_count": out_of_scope_rows,
            },
            "formal_pnl_view": {
                "total_actual_pnl": float(formal_actual_pnl),
                "explained_pnl": float(explained_pnl),
                "residual_noise": float(residual_noise),
                "components": _decision_float_components(totals),
                "closure": {
                    "status": "closed" if abs(explained_pnl - formal_actual_pnl) <= Decimal("0.01") else "warning",
                    "difference": float(explained_pnl - formal_actual_pnl),
                    "basis": "fact_formal_pnl_fi.total_pnl",
                },
            },
            "valuation_oci_view": {
                "total_valuation_change_516": float(valuation_total),
                "fvoci_valuation_change_516": float(fvoci_valuation),
                "fvtpl_valuation_change_516": float(fvtpl_valuation),
                "rows_by_accounting_basis": rows_by_accounting,
                "reinvestment": {
                    "implemented": False,
                    "message": "数据源不足：缺少稳定短端再投资数据，v1 不伪造为 0 贡献。",
                },
            },
            "effects": _decision_effect_rows(totals),
            "accounting_matrix": accounting_matrix_json,
            "ability_matrix": _decision_ability_matrix(computed_rows),
            "risk_tensor_check": risk_tensor_check,
            "residual_diagnostics": {
                "missing_curve_count": missing_curve_count,
                "missing_spread_count": missing_spread_count,
                "duplicate_position_keys": duplicate_position_keys,
                "aggregated_position_groups": aggregated_position_groups,
                "unmatched_pnl_rows": out_of_scope_rows,
                "stale_curve_fallback_count": stale_curve_fallback_count,
                "warnings": sorted(set(warnings)),
            },
            "warnings": sorted(set(warnings)),
            "method_notes": [
                "carry = interest_income_514。",
                "FVOCI 的 516 不进入正式 PnL，但进入估值/OCI 解释视图。",
                "selection_proxy 是组合/成本中心代理指标，不是实名交易员能力。",
                "residual_noise 专门承接缺曲线、重复 key、估值噪音和数据质量问题。",
            ],
        }
        return build_formal_result_envelope(
            result_meta=build_formal_result_meta(
                trace_id=_trace_id(),
                result_kind="campisi.decision_grade",
                cache_version=CACHE_VERSION,
                source_version=SOURCE_VERSION,
                rule_version=RULE_VERSION,
                quality_flag=quality_flag,
                vendor_status="vendor_stale" if stale_curve_fallback_count else "ok",
                fallback_mode="latest_snapshot" if stale_curve_fallback_count else "none",
                filters_applied=filters,
                tables_used=TABLES_CAMPISI_DECISION_GRADE,
                evidence_rows=len(pnl_rows) + len(analytics_rows) + len(balance_rows),
                source_surface="formal_attribution",
                as_of_date=anchor_end,
            ),
            result_payload=payload,
        )
    finally:
        conn.close()


def campisi_four_effects_envelope(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int = 30,
) -> dict[str, object]:
    """Campisi 四效应归因（income/treasury/spread/selection）。"""
    settings = get_settings()
    bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
    curve_repo = YieldCurveRepository(str(settings.duckdb_path))
    dates = bond_repo.list_report_dates()

    if not dates:
        payload = _empty_campisi_payload("", "")
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.four_effects"),
            result_payload=payload,
        )

    rd_end = end_date or dates[0]
    if start_date:
        rd_start = start_date
    else:
        rd_start = (date.fromisoformat(rd_end) - timedelta(days=max(1, lookback_days))).isoformat()

    anchor_start = _anchor_on_or_before(dates, rd_start)
    anchor_end = rd_end if rd_end in dates else _anchor_on_or_before(dates, rd_end)

    if not anchor_start or not anchor_end:
        payload = _empty_campisi_payload(rd_start, rd_end)
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.four_effects"),
            result_payload=payload,
        )

    rows_start = bond_repo.fetch_bond_analytics_rows(report_date=anchor_start)
    rows_end = bond_repo.fetch_bond_analytics_rows(report_date=anchor_end)
    positions = _merge_positions(rows_start, rows_end)
    input_quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)
    filters = {
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "resolved_start_date": anchor_start,
        "resolved_end_date": anchor_end,
        "lookback_days": lookback_days,
    }
    evidence_rows = len(rows_start) + len(rows_end)

    if not positions:
        payload = _empty_campisi_payload(anchor_start, anchor_end)
        return build_formal_result_envelope(
            result_meta=_meta_warn(
                "campisi.four_effects",
                source_version=SOURCE_VERSION if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload=payload,
        )

    formal_bridge = _try_fetch_formal_bridge(settings=settings, report_date=anchor_end)
    if _formal_bridge_has_position_overlap(formal_bridge, positions):
        result = _formal_bridge_to_campisi_result(
            bridge_envelope=formal_bridge,
            positions=positions,
            start_date=date.fromisoformat(anchor_start),
            end_date=date.fromisoformat(anchor_end),
        )
        formal_closure = _build_formal_closure(
            report_date=anchor_end,
            campisi_total_return=Decimal(str(result.totals.get("total_return") or 0)),
            bridge_envelope=formal_bridge,
        )
        payload = _result_to_payload(
            result,
            anchor_start,
            anchor_end,
            input_quality,
            formal_closure,
            basis=FORMAL_REPORT_BASIS,
        )
        return build_formal_result_envelope(
            result_meta=_meta_with_quality(
                "campisi.four_effects",
                input_quality,
                formal_closure,
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload=payload,
        )

    treasury_start = _curve_to_market_dict(curve_repo.fetch_curve(anchor_start, "treasury"))
    treasury_end = _curve_to_market_dict(curve_repo.fetch_curve(anchor_end, "treasury"))
    spread_start = fetch_credit_spread_market(curve_repo, anchor_start)
    spread_end = fetch_credit_spread_market(curve_repo, anchor_end)
    market_start = {**treasury_start, **spread_start}
    market_end = {**treasury_end, **spread_end}
    _add_market_curve_quality(
        input_quality,
        positions=positions,
        market_start=market_start,
        market_end=market_end,
    )

    result = campisi_attribution(
        positions_merged=positions,
        market_start=market_start,
        market_end=market_end,
        start_date=date.fromisoformat(anchor_start),
        end_date=date.fromisoformat(anchor_end),
    )
    if result.diagnostics:
        input_quality["warnings"] = [*input_quality["warnings"], *result.diagnostics]

    formal_closure = _fetch_formal_closure(
        settings=settings,
        report_date=anchor_end,
        campisi_total_return=Decimal(str(result.totals.get("total_return") or 0)),
    )
    payload = _result_to_payload(result, anchor_start, anchor_end, input_quality, formal_closure)
    return build_formal_result_envelope(
        result_meta=_meta_with_quality(
            "campisi.four_effects",
            input_quality,
            formal_closure,
            filters_applied=filters,
            tables_used=TABLES_CAMPISI,
            evidence_rows=evidence_rows,
            as_of_date=anchor_end,
        ),
        result_payload=payload,
    )


def campisi_enhanced_envelope(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int = 30,
) -> dict[str, object]:
    """Campisi 六效应归因（+ convexity/cross/reinvestment）。"""
    settings = get_settings()
    bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
    curve_repo = YieldCurveRepository(str(settings.duckdb_path))
    dates = bond_repo.list_report_dates()

    if not dates:
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.enhanced"),
            result_payload=_empty_campisi_payload("", ""),
        )

    rd_end = end_date or dates[0]
    rd_start = start_date or (date.fromisoformat(rd_end) - timedelta(days=max(1, lookback_days))).isoformat()
    anchor_start = _anchor_on_or_before(dates, rd_start)
    anchor_end = rd_end if rd_end in dates else _anchor_on_or_before(dates, rd_end)

    if not anchor_start or not anchor_end:
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.enhanced"),
            result_payload=_empty_campisi_payload(rd_start, rd_end),
        )

    rows_start = bond_repo.fetch_bond_analytics_rows(report_date=anchor_start)
    rows_end = bond_repo.fetch_bond_analytics_rows(report_date=anchor_end)
    positions = _merge_positions(rows_start, rows_end)
    input_quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)
    filters = {
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "resolved_start_date": anchor_start,
        "resolved_end_date": anchor_end,
        "lookback_days": lookback_days,
    }
    evidence_rows = len(rows_start) + len(rows_end)

    if not positions:
        return build_formal_result_envelope(
            result_meta=_meta_warn(
                "campisi.enhanced",
                source_version=SOURCE_VERSION if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload=_empty_campisi_payload(anchor_start, anchor_end),
        )

    formal_bridge = _try_fetch_formal_bridge(settings=settings, report_date=anchor_end)
    if _formal_bridge_has_position_overlap(formal_bridge, positions):
        result = _formal_bridge_to_enhanced_result(
            bridge_envelope=formal_bridge,
            positions=positions,
            start_date=date.fromisoformat(anchor_start),
            end_date=date.fromisoformat(anchor_end),
        )
        result["report_date"] = anchor_end
        result["period_start"] = anchor_start
        result["period_end"] = anchor_end
        result["input_quality"] = input_quality
        result["warnings"] = list(input_quality["warnings"])
        return build_formal_result_envelope(
            result_meta=_meta_with_quality(
                "campisi.enhanced",
                input_quality,
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload=result,
        )

    treasury_start = _curve_to_market_dict(curve_repo.fetch_curve(anchor_start, "treasury"))
    treasury_end = _curve_to_market_dict(curve_repo.fetch_curve(anchor_end, "treasury"))
    spread_start = fetch_credit_spread_market(curve_repo, anchor_start)
    spread_end = fetch_credit_spread_market(curve_repo, anchor_end)
    market_start = {**treasury_start, **spread_start}
    market_end = {**treasury_end, **spread_end}
    _add_market_curve_quality(
        input_quality,
        positions=positions,
        market_start=market_start,
        market_end=market_end,
    )

    result = campisi_enhanced(
        positions_merged=positions,
        market_start=market_start,
        market_end=market_end,
        start_date=date.fromisoformat(anchor_start),
        end_date=date.fromisoformat(anchor_end),
    )
    if result.get("diagnostics"):
        input_quality["warnings"] = [*input_quality["warnings"], *result["diagnostics"]]

    result["report_date"] = anchor_end
    result["period_start"] = anchor_start
    result["period_end"] = anchor_end
    result["input_quality"] = input_quality
    result["warnings"] = list(input_quality["warnings"])
    return build_formal_result_envelope(
        result_meta=_meta_with_quality(
            "campisi.enhanced",
            input_quality,
            filters_applied=filters,
            tables_used=TABLES_CAMPISI,
            evidence_rows=evidence_rows,
            as_of_date=anchor_end,
        ),
        result_payload=result,
    )


def campisi_maturity_bucket_envelope(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    lookback_days: int = 30,
) -> dict[str, object]:
    """Campisi 按到期桶分解。"""
    settings = get_settings()
    bond_repo = BondAnalyticsRepository(str(settings.duckdb_path))
    curve_repo = YieldCurveRepository(str(settings.duckdb_path))
    dates = bond_repo.list_report_dates()

    if not dates:
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.maturity_buckets"),
            result_payload={"buckets": {}, "period_start": "", "period_end": ""},
        )

    rd_end = end_date or dates[0]
    rd_start = start_date or (date.fromisoformat(rd_end) - timedelta(days=max(1, lookback_days))).isoformat()
    anchor_start = _anchor_on_or_before(dates, rd_start)
    anchor_end = rd_end if rd_end in dates else _anchor_on_or_before(dates, rd_end)

    if not anchor_start or not anchor_end:
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.maturity_buckets"),
            result_payload={"buckets": {}, "period_start": rd_start, "period_end": rd_end},
        )

    rows_start = bond_repo.fetch_bond_analytics_rows(report_date=anchor_start)
    rows_end = bond_repo.fetch_bond_analytics_rows(report_date=anchor_end)
    positions = _merge_positions(rows_start, rows_end)
    input_quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)
    filters = {
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "resolved_start_date": anchor_start,
        "resolved_end_date": anchor_end,
        "lookback_days": lookback_days,
    }
    evidence_rows = len(rows_start) + len(rows_end)

    if not positions:
        return build_formal_result_envelope(
            result_meta=_meta_warn(
                "campisi.maturity_buckets",
                source_version=SOURCE_VERSION if evidence_rows else SOURCE_EMPTY,
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload={"buckets": {}, "period_start": anchor_start, "period_end": anchor_end},
        )

    formal_bridge = _try_fetch_formal_bridge(settings=settings, report_date=anchor_end)
    if _formal_bridge_has_position_overlap(formal_bridge, positions):
        buckets = _formal_bridge_to_maturity_buckets(
            bridge_envelope=formal_bridge,
            positions=positions,
            start_date=date.fromisoformat(anchor_start),
        )
        return build_formal_result_envelope(
            result_meta=_meta_with_quality(
                "campisi.maturity_buckets",
                input_quality,
                filters_applied=filters,
                tables_used=TABLES_CAMPISI,
                evidence_rows=evidence_rows,
                as_of_date=anchor_end,
            ),
            result_payload={
                "period_start": anchor_start,
                "period_end": anchor_end,
                "basis": FORMAL_REPORT_BASIS,
                "buckets": buckets,
                "input_quality": input_quality,
                "warnings": input_quality["warnings"],
            },
        )

    treasury_start = _curve_to_market_dict(curve_repo.fetch_curve(anchor_start, "treasury"))
    treasury_end = _curve_to_market_dict(curve_repo.fetch_curve(anchor_end, "treasury"))
    spread_start = fetch_credit_spread_market(curve_repo, anchor_start)
    spread_end = fetch_credit_spread_market(curve_repo, anchor_end)
    market_start = {**treasury_start, **spread_start}
    market_end = {**treasury_end, **spread_end}
    _add_market_curve_quality(
        input_quality,
        positions=positions,
        market_start=market_start,
        market_end=market_end,
    )

    buckets = maturity_bucket_attribution(
        positions_merged=positions,
        market_start=market_start,
        market_end=market_end,
        start_date=date.fromisoformat(anchor_start),
        end_date=date.fromisoformat(anchor_end),
    )

    return build_formal_result_envelope(
        result_meta=_meta_with_quality(
            "campisi.maturity_buckets",
            input_quality,
            filters_applied=filters,
            tables_used=TABLES_CAMPISI,
            evidence_rows=evidence_rows,
            as_of_date=anchor_end,
        ),
        result_payload={
            "period_start": anchor_start,
            "period_end": anchor_end,
            "buckets": buckets,
            "input_quality": input_quality,
            "warnings": input_quality["warnings"],
        },
    )
