"""
M10: 宏观经济领先指标（纯函数，自 V1 macro_analysis.leading_indicator 迁入）。

对齐策略：最新 6/6 共同可计算经济月；主窗 12 个月完整日历月；24 个月 shadow。
observation_only / formal_use_allowed=false；不改权重、公式、阈值。
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from backend.app.core_finance.macro.helpers import coerce_date as _coerce_date
from backend.app.core_finance.macro.helpers import to_decimal_or_none as _dn
from backend.app.core_finance.macro.helpers import to_rounded_float as _f

# 与 V1 config.M10_* 对齐
_M10_WEIGHTS = {
    "pmi": Decimal("0.20"),
    "m2_yoy": Decimal("0.15"),
    "social_financing_yoy": Decimal("0.15"),
    "term_spread": Decimal("0.20"),
    "credit_spread": Decimal("0.15"),
    "commodity": Decimal("0.15"),
}
_M10_LEI_THRESHOLDS = {
    "strong_expansion": 70,
    "moderate_expansion": 55,
    "neutral_high": 50,
    "neutral_low": 45,
    "moderate_contraction": 30,
}

_OBSERVATION_FLAGS = {
    "observation_only": True,
    "formal_use_allowed": False,
}

_PRIMARY_LOOKBACK_MONTHS = 12
_SHADOW_LOOKBACK_MONTHS = 24

# component_key -> (wide field, unit, unit_status)
# 单位合同未冻结：社融 provisional；信用利差 unfrozen。
_COMPONENT_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("pmi", "pmi", "index", "provisional"),
    ("m2_yoy", "m2_yoy", "percentage_points", "provisional"),
    ("social_financing_yoy", "social_financing_yoy", "percentage_points", "provisional"),
    ("term_spread", "term_spread_10y_1y", "bp", "provisional"),
    ("credit_spread", "credit_spread_aaa_3y", "bp", "unfrozen"),
    ("commodity", "brent_oil", "USD/bbl", "provisional"),
)


def _month_key(d: date) -> tuple[int, int]:
    return d.year, d.month


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def _format_month(month_key: tuple[int, int]) -> str:
    return f"{month_key[0]:04d}-{month_key[1]:02d}"


def _alignment_lag_months(report_date: date, as_of: tuple[int, int]) -> int:
    return (report_date.year * 12 + report_date.month) - (as_of[0] * 12 + as_of[1])


def _row_fallback_date(row: dict[str, Any]) -> date | None:
    return _coerce_date(row.get("trade_date") or row.get("biz_date"))


def _build_component_observations(
    wide_rows_desc: list[dict[str, Any]],
    report_date: date,
) -> dict[str, dict[tuple[int, int], tuple[date, Decimal]]]:
    """按真实 source_date 归属月份；ffill 副本按 source_date 去重；每月保留最后一个真实观测。"""
    observations: dict[str, dict[tuple[int, int], tuple[date, Decimal]]] = {
        key: {} for key, _, _, _ in _COMPONENT_SPECS
    }

    for row in wide_rows_desc:
        fallback = _row_fallback_date(row)
        for component_key, field, _, _ in _COMPONENT_SPECS:
            value = _dn(row.get(field))
            if value is None:
                continue
            source_date = _coerce_date(row.get(f"{field}_source_date")) or fallback
            if source_date is None or source_date > report_date:
                continue
            month = _month_key(source_date)
            if source_date > _month_end(*month):
                continue
            existing = observations[component_key].get(month)
            # 同月保留最晚 source_date；相同 source_date 的 ffill 副本被去重覆盖。
            if existing is None or source_date >= existing[0]:
                observations[component_key][month] = (source_date, value)

    return observations


def _latest_common_month(
    observations: dict[str, dict[tuple[int, int], tuple[date, Decimal]]],
) -> tuple[int, int] | None:
    month_sets = [set(observations[key]) for key, _, _, _ in _COMPONENT_SPECS]
    if not month_sets or any(not s for s in month_sets):
        return None
    common = set.intersection(*month_sets)
    if not common:
        return None
    return max(common)


def _history_month_keys(as_of: tuple[int, int], lookback_months: int) -> list[tuple[int, int]]:
    """as_of 之前的 lookback 个完整日历月，newest-first。"""
    keys: list[tuple[int, int]] = []
    for delta in range(1, lookback_months + 1):
        keys.append(_shift_month(as_of[0], as_of[1], -delta))
    return keys


def _monthly_series(
    wide_rows_desc: list[dict[str, Any]],
    *,
    report_date: date | None = None,
    as_of_month: tuple[int, int] | None = None,
    lookback_months: int = _PRIMARY_LOOKBACK_MONTHS,
    observations: dict[str, dict[tuple[int, int], tuple[date, Decimal]]] | None = None,
) -> dict[str, list[Decimal | None]]:
    """返回 as_of_month 之前 lookback 个完整月的分项序列（newest-first）；缺月为 None。"""
    if observations is None:
        if report_date is None:
            report_date = date.max
            for row in wide_rows_desc:
                row_date = _row_fallback_date(row)
                if row_date is not None and row_date < report_date:
                    report_date = row_date
            if report_date is date.max:
                report_date = date.today()
        observations = _build_component_observations(wide_rows_desc, report_date)
    if as_of_month is None:
        as_of_month = _latest_common_month(observations)
    if as_of_month is None:
        return {alias: [] for alias in ("pmi", "m2", "sf", "term", "credit", "oil")}

    field_alias = {
        "pmi": "pmi",
        "m2_yoy": "m2",
        "social_financing_yoy": "sf",
        "term_spread": "term",
        "credit_spread": "credit",
        "commodity": "oil",
    }
    month_keys = _history_month_keys(as_of_month, lookback_months)
    out: dict[str, list[Decimal | None]] = {alias: [] for alias in field_alias.values()}
    for component_key, alias in field_alias.items():
        series: list[Decimal | None] = []
        for month in month_keys:
            obs = observations[component_key].get(month)
            series.append(obs[1] if obs is not None else None)
        out[alias] = series
    return out


def _history_mean(values: list[Decimal | None]) -> tuple[Decimal | None, int, int]:
    """只对可用月求均值（缺失月跳过）；返回 (均值, 有效样本数, 总月数)。"""
    total = len(values)
    available = [v for v in values if v is not None]
    if not available:
        return None, 0, total
    return sum(available) / len(available), len(available), total


def _score_components(
    *,
    pmi_val: Decimal | None,
    m2_cur: Decimal | None,
    m2_hist: list[Decimal | None],
    sf_cur: Decimal | None,
    sf_hist: list[Decimal | None],
    term_val: Decimal | None,
    credit_val: Decimal | None,
    oil_cur: Decimal | None,
    oil_hist: list[Decimal | None],
) -> tuple[dict[str, Decimal | None], dict[str, dict[str, int]]]:
    if pmi_val is not None:
        pmi_score = (pmi_val - Decimal("30")) / Decimal("0.4")
        pmi_score = max(Decimal("0"), min(Decimal("100"), pmi_score))
    else:
        pmi_score = None

    m2_avg, m2_used, m2_total = _history_mean(m2_hist)
    if m2_avg is not None and m2_cur is not None:
        m2_score = Decimal("50") + (m2_cur - m2_avg) * Decimal("5")
        m2_score = max(Decimal("0"), min(Decimal("100"), m2_score))
    elif m2_cur is None:
        m2_score = None
    else:
        m2_score = Decimal("50")

    sf_avg, sf_used, sf_total = _history_mean(sf_hist)
    if sf_avg is not None and sf_cur is not None:
        sf_score = Decimal("50") + (sf_cur - sf_avg) * Decimal("5")
        sf_score = max(Decimal("0"), min(Decimal("100"), sf_score))
    elif sf_cur is None:
        sf_score = None
    else:
        sf_score = Decimal("50")

    if term_val is not None:
        term_score = Decimal("50") + term_val / Decimal("2")
        term_score = max(Decimal("0"), min(Decimal("100"), term_score))
    else:
        term_score = None

    if credit_val is not None:
        credit_score = Decimal("100") - credit_val
        credit_score = max(Decimal("0"), min(Decimal("100"), credit_score))
    else:
        credit_score = None

    oil_avg, oil_used, oil_total = _history_mean(oil_hist)
    if oil_avg is not None and oil_avg != 0 and oil_cur is not None:
        commodity_score = Decimal("50") + (oil_cur - oil_avg) / oil_avg * Decimal("500")
        commodity_score = max(Decimal("0"), min(Decimal("100"), commodity_score))
    elif oil_cur is None:
        commodity_score = None
    else:
        commodity_score = Decimal("50")

    scores = {
        "pmi": pmi_score,
        "m2_yoy": m2_score,
        "social_financing_yoy": sf_score,
        "term_spread": term_score,
        "credit_spread": credit_score,
        "commodity": commodity_score,
    }
    samples = {
        "m2_yoy": {"used": m2_used, "total": m2_total},
        "social_financing_yoy": {"used": sf_used, "total": sf_total},
        "commodity": {"used": oil_used, "total": oil_total},
    }
    return scores, samples


def _weighted_lei(component_scores: dict[str, Decimal | None]) -> Decimal | None:
    available_weight = sum(
        _M10_WEIGHTS[name] for name, score in component_scores.items() if score is not None
    )
    if available_weight <= 0:
        return None
    lei = sum(
        score * _M10_WEIGHTS[name]
        for name, score in component_scores.items()
        if score is not None
    ) / available_weight
    return lei.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _economic_state(lei: Decimal | None) -> str:
    if lei is None:
        return "数据不足"
    fv = float(lei)
    thresholds = _M10_LEI_THRESHOLDS
    if fv >= thresholds["strong_expansion"]:
        return "强劲扩张"
    if fv >= thresholds["moderate_expansion"]:
        return "温和扩张"
    if fv >= thresholds["neutral_high"]:
        return "中性"
    if fv >= thresholds["neutral_low"]:
        return "中性"
    if fv >= thresholds["moderate_contraction"]:
        return "温和收缩"
    return "显著收缩"


def _trend_from_pmi(
    observations: dict[str, dict[tuple[int, int], tuple[date, Decimal]]],
    as_of: tuple[int, int],
) -> tuple[str, bool]:
    pmi_cur = observations["pmi"].get(as_of)
    if pmi_cur is None:
        return "数据不足", False
    prev = _shift_month(as_of[0], as_of[1], -1)
    pmi_prev = observations["pmi"].get(prev)
    if pmi_prev is None:
        return "数据不足", True
    if pmi_cur[1] > pmi_prev[1]:
        return "上升", False
    if pmi_cur[1] < pmi_prev[1]:
        return "下降", False
    return "平稳", False


def _evidence_entry(
    component_key: str,
    field: str,
    unit: str,
    unit_status: str,
    obs: tuple[date, Decimal] | None,
    *,
    used: bool,
) -> dict[str, Any]:
    if obs is None:
        return {
            "component": component_key,
            "field": field,
            "source_date": None,
            "source_month": None,
            "value": None,
            "unit": unit,
            "unit_status": unit_status,
            "used": used,
        }
    source_date, value = obs
    return {
        "component": component_key,
        "field": field,
        "source_date": source_date.isoformat(),
        "source_month": _format_month(_month_key(source_date)),
        "value": _f(value),
        "unit": unit,
        "unit_status": unit_status,
        "used": used,
    }


def _component_evidence_lists(
    observations: dict[str, dict[tuple[int, int], tuple[date, Decimal]]],
    as_of: tuple[int, int] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
    component_evidence: list[dict[str, Any]] = []
    latest_available: list[dict[str, Any]] = []
    newer_excluded = False
    for component_key, field, unit, unit_status in _COMPONENT_SPECS:
        by_month = observations[component_key]
        used_obs = by_month.get(as_of) if as_of is not None else None
        component_evidence.append(
            _evidence_entry(component_key, field, unit, unit_status, used_obs, used=used_obs is not None)
        )
        if by_month:
            latest_month = max(by_month)
            latest_obs = by_month[latest_month]
            latest_available.append(
                _evidence_entry(
                    component_key,
                    field,
                    unit,
                    unit_status,
                    latest_obs,
                    used=as_of is not None and latest_month == as_of,
                )
            )
            if as_of is not None and latest_month > as_of:
                newer_excluded = True
        else:
            latest_available.append(
                _evidence_entry(component_key, field, unit, unit_status, None, used=False)
            )
    return component_evidence, latest_available, newer_excluded


def _history_window_meta(as_of: tuple[int, int], lookback_months: int) -> dict[str, Any]:
    end = _shift_month(as_of[0], as_of[1], -1)
    start = _shift_month(as_of[0], as_of[1], -lookback_months)
    return {
        "start_month": _format_month(start),
        "end_month": _format_month(end),
        "governed": True,
        "lookback_months": lookback_months,
    }


def _scores_as_floats(scores: dict[str, Decimal | None]) -> dict[str, float | None]:
    return {name: _f(score) if score is not None else None for name, score in scores.items()}


def _unavailable_payload(
    report_date: date,
    *,
    warnings: list[str],
    headline: str,
    component_evidence: list[dict[str, Any]] | None = None,
    latest_available: list[dict[str, Any]] | None = None,
    alignment_lag_months: int | None = None,
) -> dict[str, Any]:
    return {
        "report_date": report_date.isoformat(),
        **_OBSERVATION_FLAGS,
        "data_status": "unavailable",
        "lei_index": None,
        "economic_state": "数据不足",
        "trend": "数据不足",
        "headline": headline,
        "pmi_score": None,
        "m2_score": None,
        "social_financing_score": None,
        "term_spread_score": None,
        "credit_spread_score": None,
        "commodity_score": None,
        "available_component_count": 0,
        "component_count": len(_M10_WEIGHTS),
        "component_coverage_pct": 0.0,
        "history_samples": {
            "m2_yoy": {"used": 0, "total": 0},
            "social_financing_yoy": {"used": 0, "total": 0},
            "commodity": {"used": 0, "total": 0},
        },
        "lookback_months": _PRIMARY_LOOKBACK_MONTHS,
        "history_window": {
            "start_month": None,
            "end_month": None,
            "governed": True,
            "lookback_months": _PRIMARY_LOOKBACK_MONTHS,
        },
        "as_of_month": None,
        "alignment_policy": "latest_common_computable_month",
        "alignment_lag_months": alignment_lag_months,
        "component_evidence": component_evidence or [],
        "latest_available_component_evidence": latest_available or [],
        "shadow_24m": {
            "shadow": True,
            "lookback_months": _SHADOW_LOOKBACK_MONTHS,
            "lei_index": None,
            "economic_state": "数据不足",
            "component_scores": {
                "pmi": None,
                "m2_yoy": None,
                "social_financing_yoy": None,
                "term_spread": None,
                "credit_spread": None,
                "commodity": None,
            },
            "history_samples": {
                "m2_yoy": {"used": 0, "total": 0},
                "social_financing_yoy": {"used": 0, "total": 0},
                "commodity": {"used": 0, "total": 0},
            },
        },
        "warnings": warnings,
    }


def compute_leading_indicator(
    wide_rows_desc: list[dict[str, Any]],
    report_date: date,
) -> dict[str, Any]:
    if not wide_rows_desc:
        return _unavailable_payload(
            report_date,
            warnings=["NO_MACRO_ROWS"],
            headline="暂无可用宏观数据，无法计算领先指标。",
        )

    observations = _build_component_observations(wide_rows_desc, report_date)
    as_of = _latest_common_month(observations)
    component_evidence, latest_available, newer_excluded = _component_evidence_lists(
        observations, as_of
    )

    if as_of is None:
        warnings = [
            "LEI_NO_COMMON_COMPUTABLE_MONTH",
            "LEI_UNIT_CONTRACT_UNFROZEN",
            "PIT_METADATA_UNAVAILABLE",
        ]
        return _unavailable_payload(
            report_date,
            warnings=warnings,
            headline="无 6/6 共同可计算月，无法形成领先指标主结论。",
            component_evidence=component_evidence,
            latest_available=latest_available,
        )

    # Current legs: only the common as_of month.
    currents = {
        key: observations[key][as_of][1]
        for key, _, _, _ in _COMPONENT_SPECS
    }
    pmi_val = currents["pmi"]
    m2_cur = currents["m2_yoy"]
    sf_cur = currents["social_financing_yoy"]
    term_val = currents["term_spread"]
    credit_val = currents["credit_spread"]
    oil_cur = currents["commodity"]

    primary_hist = _monthly_series(
        wide_rows_desc,
        report_date=report_date,
        as_of_month=as_of,
        lookback_months=_PRIMARY_LOOKBACK_MONTHS,
        observations=observations,
    )
    shadow_hist = _monthly_series(
        wide_rows_desc,
        report_date=report_date,
        as_of_month=as_of,
        lookback_months=_SHADOW_LOOKBACK_MONTHS,
        observations=observations,
    )

    primary_scores, primary_samples = _score_components(
        pmi_val=pmi_val,
        m2_cur=m2_cur,
        m2_hist=primary_hist["m2"],
        sf_cur=sf_cur,
        sf_hist=primary_hist["sf"],
        term_val=term_val,
        credit_val=credit_val,
        oil_cur=oil_cur,
        oil_hist=primary_hist["oil"],
    )
    shadow_scores, shadow_samples = _score_components(
        pmi_val=pmi_val,
        m2_cur=m2_cur,
        m2_hist=shadow_hist["m2"],
        sf_cur=sf_cur,
        sf_hist=shadow_hist["sf"],
        term_val=term_val,
        credit_val=credit_val,
        oil_cur=oil_cur,
        oil_hist=shadow_hist["oil"],
    )

    # 成功计分要求 6/6；共同月已保证当前腿齐全，不再做部分重归一主结论。
    lei = _weighted_lei(primary_scores)
    shadow_lei = _weighted_lei(shadow_scores)
    available_component_count = 6
    component_count = 6
    component_coverage_pct = Decimal("100")

    economic_state = _economic_state(lei)
    trend, pmi_history_missing = _trend_from_pmi(observations, as_of)
    headline = f"LEI 基于全部 {component_count} 个分项计算（as_of_month={_format_month(as_of)}）。"

    lag = _alignment_lag_months(report_date, as_of)
    warnings: list[str] = [
        "LEI_UNIT_CONTRACT_UNFROZEN",
        "PIT_METADATA_UNAVAILABLE",
    ]
    if lag > 0:
        warnings.append("LEI_AS_OF_MONTH_LAGGED")
    if newer_excluded:
        warnings.append("LEI_NEWER_COMPONENT_DATA_EXCLUDED")
    if pmi_history_missing:
        warnings.append("PMI_HISTORY_MISSING_MONTHS")

    m2_used = primary_samples["m2_yoy"]["used"]
    m2_total = primary_samples["m2_yoy"]["total"]
    sf_used = primary_samples["social_financing_yoy"]["used"]
    sf_total = primary_samples["social_financing_yoy"]["total"]
    oil_used = primary_samples["commodity"]["used"]
    oil_total = primary_samples["commodity"]["total"]
    if m2_used < m2_total:
        warnings.append("M2_HISTORY_MISSING_MONTHS")
    if sf_used < sf_total:
        warnings.append("SOCIAL_FINANCING_HISTORY_MISSING_MONTHS")
    if oil_used < oil_total:
        warnings.append("COMMODITY_HISTORY_MISSING_MONTHS")

    history_window = _history_window_meta(as_of, _PRIMARY_LOOKBACK_MONTHS)

    return {
        "report_date": report_date.isoformat(),
        **_OBSERVATION_FLAGS,
        "data_status": "degraded",
        "lei_index": _f(lei) if lei is not None else None,
        "economic_state": economic_state,
        "trend": trend,
        "headline": headline,
        "pmi_score": _f(primary_scores["pmi"]) if primary_scores["pmi"] is not None else None,
        "m2_score": _f(primary_scores["m2_yoy"]) if primary_scores["m2_yoy"] is not None else None,
        "social_financing_score": (
            _f(primary_scores["social_financing_yoy"])
            if primary_scores["social_financing_yoy"] is not None
            else None
        ),
        "term_spread_score": (
            _f(primary_scores["term_spread"]) if primary_scores["term_spread"] is not None else None
        ),
        "credit_spread_score": (
            _f(primary_scores["credit_spread"])
            if primary_scores["credit_spread"] is not None
            else None
        ),
        "commodity_score": (
            _f(primary_scores["commodity"]) if primary_scores["commodity"] is not None else None
        ),
        "available_component_count": available_component_count,
        "component_count": component_count,
        "component_coverage_pct": _f(component_coverage_pct),
        "history_samples": primary_samples,
        "lookback_months": _PRIMARY_LOOKBACK_MONTHS,
        "history_window": history_window,
        "as_of_month": _format_month(as_of),
        "alignment_policy": "latest_common_computable_month",
        "alignment_lag_months": lag,
        "component_evidence": component_evidence,
        "latest_available_component_evidence": latest_available,
        "shadow_24m": {
            "shadow": True,
            "lookback_months": _SHADOW_LOOKBACK_MONTHS,
            "lei_index": _f(shadow_lei) if shadow_lei is not None else None,
            "economic_state": _economic_state(shadow_lei),
            "component_scores": _scores_as_floats(shadow_scores),
            "history_samples": shadow_samples,
            "history_window": _history_window_meta(as_of, _SHADOW_LOOKBACK_MONTHS),
        },
        "warnings": warnings,
    }
