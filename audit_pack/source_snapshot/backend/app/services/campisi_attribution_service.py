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


def _meta_ok(result_kind: str):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=CACHE_VERSION,
        source_version=SOURCE_VERSION,
        rule_version=RULE_VERSION,
    )


def _meta_warn(result_kind: str):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        source_version=SOURCE_EMPTY,
        rule_version=RULE_VERSION,
        cache_version=CACHE_VERSION,
        quality_flag="warning",
    )


def _curve_to_market_dict(curve: dict[str, Any]) -> dict[str, Any]:
    """将 YieldCurveRepository.fetch_curve 的 {tenor: rate_pct} 转为 campisi.py 需要的 market dict。"""
    market: dict[str, Any] = {}
    for tenor, field in _TREASURY_TENOR_MAP.items():
        val = curve.get(tenor) or curve.get(tenor.lower()) or curve.get(tenor.replace("Y", "y"))
        if val is not None:
            market[field] = float(val)
    return market


def _fetch_spread_data(curve_repo: YieldCurveRepository, trade_date: str) -> dict[str, Any]:
    """Fetch AAA/AA+/AA 3Y credit spreads in bp for Campisi."""
    spread = _fetch_legacy_spread_curve_data(curve_repo, trade_date)
    spread.update(_derive_spreads_from_yield_sources(curve_repo, trade_date))
    return spread


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


def _merge_positions(
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


def _result_to_payload(
    result: CampisiResult,
    start: str,
    end: str,
    input_quality: dict[str, Any] | None = None,
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
    if input_quality is not None:
        payload["input_quality"] = input_quality
        payload["warnings"] = input_quality["warnings"]
    return payload


def _meta_with_quality(result_kind: str, input_quality: dict[str, Any]):
    return build_formal_result_meta(
        trace_id=_trace_id(),
        result_kind=result_kind,
        cache_version=CACHE_VERSION,
        source_version=SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag="warning" if input_quality["warnings"] else None,
    )


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

    if not positions:
        payload = _empty_campisi_payload(anchor_start, anchor_end)
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.four_effects"),
            result_payload=payload,
        )

    treasury_start = _curve_to_market_dict(curve_repo.fetch_curve(anchor_start, "treasury"))
    treasury_end = _curve_to_market_dict(curve_repo.fetch_curve(anchor_end, "treasury"))
    spread_start = _fetch_spread_data(curve_repo, anchor_start)
    spread_end = _fetch_spread_data(curve_repo, anchor_end)
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

    payload = _result_to_payload(result, anchor_start, anchor_end, input_quality)
    return build_formal_result_envelope(
        result_meta=_meta_with_quality("campisi.four_effects", input_quality),
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

    if not positions:
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.enhanced"),
            result_payload=_empty_campisi_payload(anchor_start, anchor_end),
        )

    treasury_start = _curve_to_market_dict(curve_repo.fetch_curve(anchor_start, "treasury"))
    treasury_end = _curve_to_market_dict(curve_repo.fetch_curve(anchor_end, "treasury"))
    spread_start = _fetch_spread_data(curve_repo, anchor_start)
    spread_end = _fetch_spread_data(curve_repo, anchor_end)
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

    result["report_date"] = anchor_end
    result["period_start"] = anchor_start
    result["period_end"] = anchor_end
    result["input_quality"] = input_quality
    result["warnings"] = input_quality["warnings"]
    return build_formal_result_envelope(
        result_meta=_meta_with_quality("campisi.enhanced", input_quality),
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

    if not positions:
        return build_formal_result_envelope(
            result_meta=_meta_warn("campisi.maturity_buckets"),
            result_payload={"buckets": {}, "period_start": anchor_start, "period_end": anchor_end},
        )

    treasury_start = _curve_to_market_dict(curve_repo.fetch_curve(anchor_start, "treasury"))
    treasury_end = _curve_to_market_dict(curve_repo.fetch_curve(anchor_end, "treasury"))
    spread_start = _fetch_spread_data(curve_repo, anchor_start)
    spread_end = _fetch_spread_data(curve_repo, anchor_end)
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
        result_meta=_meta_with_quality("campisi.maturity_buckets", input_quality),
        result_payload={
            "period_start": anchor_start,
            "period_end": anchor_end,
            "buckets": buckets,
            "input_quality": input_quality,
            "warnings": input_quality["warnings"],
        },
    )
