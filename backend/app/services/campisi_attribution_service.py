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
from datetime import date, timedelta
from typing import Any

from backend.app.core_finance.campisi import (
    CampisiResult,
    campisi_attribution,
    campisi_enhanced,
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
    """获取信用利差数据（AAA/AA+/AA 3Y）。"""
    spread: dict[str, Any] = {}
    for curve_type in ("credit_spread_aaa", "credit_spread_aa_plus", "credit_spread_aa"):
        data = curve_repo.fetch_curve(trade_date, curve_type)
        if data:
            for tenor, rate in data.items():
                key = f"{curve_type}_{tenor.lower()}"
                spread[key] = float(rate)
    return spread


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
    start_by_code: dict[str, dict[str, Any]] = {}
    for r in rows_start:
        code = str(r.get("instrument_code") or "")
        if code:
            start_by_code[code] = r

    end_by_code: dict[str, dict[str, Any]] = {}
    for r in rows_end:
        code = str(r.get("instrument_code") or "")
        if code:
            end_by_code[code] = r

    all_codes = set(start_by_code.keys()) | set(end_by_code.keys())
    merged: list[dict[str, Any]] = []

    for code in all_codes:
        s = start_by_code.get(code, {})
        e = end_by_code.get(code, {})

        coupon_raw = s.get("coupon_rate") or e.get("coupon_rate")
        coupon_dec = normalize_annual_rate_to_decimal(coupon_raw) if coupon_raw is not None else None

        ytm_raw = s.get("ytm") or e.get("ytm")
        ytm_dec = normalize_annual_rate_to_decimal(ytm_raw) if ytm_raw is not None else None

        merged.append({
            "bond_code": code,
            "instrument_id": code,
            "market_value_start": float(s.get("market_value") or 0),
            "market_value_end": float(e.get("market_value") or 0),
            "face_value_start": float(s.get("face_value") or 0),
            "coupon_rate_start": coupon_dec or 0.0,
            "yield_to_maturity_start": ytm_dec or 0.0,
            "asset_class_start": str(s.get("asset_class_std") or e.get("asset_class_std") or ""),
            "maturity_date_start": s.get("maturity_date") or e.get("maturity_date"),
        })

    return merged


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
) -> dict[str, Any]:
    return {
        "report_date": end,
        "period_start": start,
        "period_end": end,
        "num_days": result.num_days,
        "totals": result.totals,
        "by_asset_class": result.by_asset_class,
        "by_bond": result.by_bond,
    }


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

    result = campisi_attribution(
        positions_merged=positions,
        market_start=market_start,
        market_end=market_end,
        start_date=date.fromisoformat(anchor_start),
        end_date=date.fromisoformat(anchor_end),
    )

    payload = _result_to_payload(result, anchor_start, anchor_end)
    return build_formal_result_envelope(
        result_meta=_meta_ok("campisi.four_effects"),
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
    return build_formal_result_envelope(
        result_meta=_meta_ok("campisi.enhanced"),
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

    buckets = maturity_bucket_attribution(
        positions_merged=positions,
        market_start=market_start,
        market_end=market_end,
        start_date=date.fromisoformat(anchor_start),
        end_date=date.fromisoformat(anchor_end),
    )

    return build_formal_result_envelope(
        result_meta=_meta_ok("campisi.maturity_buckets"),
        result_payload={
            "period_start": anchor_start,
            "period_end": anchor_end,
            "buckets": buckets,
        },
    )
