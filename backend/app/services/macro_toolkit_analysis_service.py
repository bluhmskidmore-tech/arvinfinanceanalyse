"""Macro toolkit analysis formatting.

Crisis-commodity shadow/admission evaluation plus capability and signal card
rendering for the macro toolkit analytical surface.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pandas as pd
from backend.app.core_finance.macro.crisis_commodity_shadow import (
    CRISIS_COMMODITY_SHADOW_MIN_SAMPLES as _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES,
)
from backend.app.services.macro_toolkit_presentation import (
    _SOURCE_BACKFILL_TARGETS,
    _latest_source_check_date,
)

_DAILY_SOURCE_CHECK_ALIASES = {
    "sh000300",
    "CU0",
    "DR007.IB",
    "M0067855",
    "S0059747",
    "S0059749",
    "S0059760",
    "M0041813",
}

_CRISIS_COMMODITY_FIELD_TO_PRODUCT = {
    "rebar": "RB",
    "iron_ore": "I",
    "copper": "CU",
    "aluminum": "AL",
    "crude_oil": "SC",
    "gold": "AU",
}


_CRISIS_COMMODITY_SHADOW_FORMULA_VERSION = "rv_macro_crisis_score_shadow_commodity_v1"


_CRISIS_COMMODITY_SHADOW_WEIGHT = 0.05


_CRISIS_COMMODITY_ADMISSION_RULE_VERSION = "rv_macro_crisis_commodity_admission_v1"


_CRISIS_COMMODITY_APPROVAL_PACK_VERSION = "rv_macro_crisis_commodity_approval_pack_v1"


_CRISIS_COMMODITY_ADMISSION_MIN_CRISIS_SAMPLES = 5


_CRISIS_COMMODITY_ADMISSION_MIN_CORRELATION = 0.2


def _unique_texts(values: list[object]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _crisis_commodity_candidate_summary(items: list[dict[str, object]]) -> dict[str, object]:
    statuses = [
        str(decision.get("status") or "")
        for item in items
        if isinstance(decision := item.get("candidate_decision"), dict)
    ]
    shadow_statuses = [
        str(shadow.get("status") or "")
        for item in items
        if isinstance(shadow := item.get("shadow_evaluation"), dict)
    ]
    shadow_ready_count = shadow_statuses.count("review_ready")
    shadow_short_count = shadow_statuses.count("history_short")
    shadow_short_items = [
        {
            "field": str(item.get("field") or ""),
            "label": str(item.get("label") or item.get("field") or ""),
            "sample_count": int(shadow.get("sample_count") or 0),
            "minimum_sample_count": int(
                shadow.get("minimum_sample_count") or _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES
            ),
            "sample_gap": int(shadow.get("sample_gap") or 0),
            "latest_date": item.get("latest_date"),
        }
        for item in items
        if isinstance(shadow := item.get("shadow_evaluation"), dict)
        and shadow.get("status") == "history_short"
    ]
    suggested_refresh_products = _unique_texts(
        [
            _CRISIS_COMMODITY_FIELD_TO_PRODUCT.get(str(item.get("field") or ""))
            for item in shadow_short_items
        ]
    )
    return {
        "shadow_review_ready_count": statuses.count("shadow_review_ready"),
        "needs_current_data_count": statuses.count("needs_current_data"),
        "missing_data_count": statuses.count("missing_data"),
        "shadow_evaluation_ready_count": shadow_ready_count,
        "shadow_evaluation_short_count": shadow_short_count,
        "shadow_evaluation_status_counts": {
            status: shadow_statuses.count(status)
            for status in sorted(set(shadow_statuses))
            if status
        },
        "shadow_evaluation_short_items": shadow_short_items,
        "suggested_refresh_products": suggested_refresh_products,
        "shadow_evaluation_next_step": _crisis_commodity_shadow_next_step(
            ready_count=shadow_ready_count,
            short_count=shadow_short_count,
        ),
        "formula_change_required": True,
        "approval_required": True,
        "next_step": "商品旁证进入 Crisis Score 公式前，需要先完成历史回测、相关性检验、权重审批和版本记录。",
    }


def _crisis_commodity_shadow_next_step(*, ready_count: int, short_count: int) -> str:
    if ready_count > 0 and short_count == 0:
        return f"{ready_count} 个商品候选可进入人工复核；进入公式前仍需历史回测、相关性检验、权重审批和版本记录。"
    if ready_count > 0:
        return (
            f"{ready_count} 个商品候选可读，{short_count} 个样本不足；"
            "先补齐样本不足品种的历史数据，再做人工复核和权重审批。"
        )
    return "商品候选影子评估样本不足；先补齐历史数据，再做历史回测、相关性检验和权重审批。"


def _crisis_commodity_shadow_impact(
    *,
    current_score: float | None,
    coverage: dict[str, object],
) -> dict[str, object]:
    items = [item for item in coverage.get("items", []) if isinstance(item, dict)]
    contributions = [
        contribution
        for item in items
        if (contribution := _crisis_commodity_shadow_contribution(item)) is not None
    ]
    delta = round(sum(float(item["contribution"]) for item in contributions), 4) if contributions else 0.0
    shadow_score = round(current_score + delta, 4) if current_score is not None else None
    return {
        "formula_version": _CRISIS_COMMODITY_SHADOW_FORMULA_VERSION,
        "scope": "commodity_shadow_v2_read_only",
        "current_score": round(current_score, 4) if current_score is not None else None,
        "shadow_score": shadow_score,
        "delta": delta,
        "direction": _crisis_commodity_shadow_direction(delta),
        "included_candidates": [str(item["field"]) for item in contributions],
        "candidate_count": len(contributions),
        "candidate_contributions": contributions,
        "weights": {
            "official_crisis_score": 1.0,
            "commodity_shadow": _CRISIS_COMMODITY_SHADOW_WEIGHT,
        },
        "warnings": ["SHADOW_SCORE_READ_ONLY", "APPROVAL_REQUIRED_BEFORE_FORMULA_USE"],
        "approval_required": True,
        "official_score_unchanged": True,
        "next_step": "先复核商品候选相关性和命中率，再确认 v2 权重；审批前不改变正式 Crisis Score。",
    }


def _crisis_commodity_shadow_contribution(item: dict[str, object]) -> dict[str, object] | None:
    shadow = item.get("shadow_evaluation")
    if not isinstance(shadow, dict) or shadow.get("status") != "review_ready":
        return None
    sample_count = int(shadow.get("sample_count") or 0)
    if sample_count < _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES:
        return None
    candidate_return_z = _float_or_none(shadow.get("latest_return_z"))
    if candidate_return_z is None:
        return None
    contribution = round(candidate_return_z * _CRISIS_COMMODITY_SHADOW_WEIGHT, 4)
    return {
        "field": str(item.get("field") or ""),
        "label": str(item.get("label") or item.get("field") or ""),
        "series_id": item.get("series_id"),
        "source": item.get("source"),
        "latest_date": item.get("latest_date"),
        "sample_count": sample_count,
        "candidate_metric": "daily_return_z",
        "candidate_value": round(candidate_return_z, 4),
        "weight": _CRISIS_COMMODITY_SHADOW_WEIGHT,
        "contribution": contribution,
        "used_in_official_score": False,
        "status": "shadow_only",
    }


def _crisis_commodity_shadow_direction(delta: float) -> str:
    if delta > 0.01:
        return "higher_stress"
    if delta < -0.01:
        return "lower_stress"
    return "unchanged"


def _crisis_commodity_candidate_admission(*, coverage: dict[str, object]) -> dict[str, object]:
    items = [item for item in coverage.get("items", []) if isinstance(item, dict)]
    admission_items = [_crisis_commodity_candidate_admission_item(item) for item in items]
    decision_counts = {
        "recommend_include": sum(1 for item in admission_items if item["decision"] == "recommend_include"),
        "watch": sum(1 for item in admission_items if item["decision"] == "watch"),
        "do_not_include": sum(1 for item in admission_items if item["decision"] == "do_not_include"),
    }
    return {
        "rule_version": _CRISIS_COMMODITY_ADMISSION_RULE_VERSION,
        "scope": "commodity_candidate_admission_read_only",
        "decision_counts": decision_counts,
        "items": admission_items,
        "warnings": ["CANDIDATE_ADMISSION_READ_ONLY", "APPROVAL_REQUIRED_BEFORE_FORMULA_USE"],
        "approval_required": True,
        "official_score_unchanged": True,
        "next_step": _crisis_commodity_admission_next_step(decision_counts),
    }


def _crisis_commodity_candidate_admission_item(item: dict[str, object]) -> dict[str, object]:
    shadow = item.get("shadow_evaluation")
    shadow = shadow if isinstance(shadow, dict) else {}
    sample_count = _int_or_none(shadow.get("sample_count"))
    minimum_sample_count = _int_or_none(shadow.get("minimum_sample_count")) or _CRISIS_COMMODITY_SHADOW_MIN_SAMPLES
    crisis_sample_count = _int_or_none(shadow.get("crisis_sample_count"))
    crisis_hit_rate = _float_or_none(shadow.get("crisis_hit_rate"))
    max_abs_correlation = _crisis_commodity_max_abs_correlation(shadow)
    decision, reason, next_step = _crisis_commodity_admission_decision(
        shadow_status=str(shadow.get("status") or ""),
        sample_count=sample_count,
        minimum_sample_count=minimum_sample_count,
        crisis_sample_count=crisis_sample_count,
        crisis_hit_rate=crisis_hit_rate,
        max_abs_correlation=max_abs_correlation,
    )
    return {
        "field": str(item.get("field") or ""),
        "label": str(item.get("label") or item.get("field") or ""),
        "decision": decision,
        "decision_label": _crisis_commodity_admission_decision_label(decision),
        "reason": reason,
        "next_step": next_step,
        "sample_count": sample_count,
        "minimum_sample_count": minimum_sample_count,
        "crisis_sample_count": crisis_sample_count,
        "minimum_crisis_sample_count": _CRISIS_COMMODITY_ADMISSION_MIN_CRISIS_SAMPLES,
        "crisis_hit_rate": crisis_hit_rate,
        "max_abs_correlation": max_abs_correlation,
        "correlation_threshold": _CRISIS_COMMODITY_ADMISSION_MIN_CORRELATION,
        "latest_date": item.get("latest_date"),
        "series_id": item.get("series_id"),
        "source": item.get("source"),
        "used_in_official_score": False,
    }


def _crisis_commodity_admission_decision(
    *,
    shadow_status: str,
    sample_count: int | None,
    minimum_sample_count: int,
    crisis_sample_count: int | None,
    crisis_hit_rate: float | None,
    max_abs_correlation: float | None,
) -> tuple[str, str, str]:
    if (
        shadow_status != "review_ready"
        or sample_count is None
        or sample_count < minimum_sample_count
        or crisis_sample_count is None
        or crisis_sample_count < _CRISIS_COMMODITY_ADMISSION_MIN_CRISIS_SAMPLES
        or crisis_hit_rate is None
    ):
        return (
            "do_not_include",
            "样本不足，先补齐历史数据。",
            "先补齐历史样本和危机期样本，再重新生成准入评估。",
        )
    if max_abs_correlation is None or max_abs_correlation < _CRISIS_COMMODITY_ADMISSION_MIN_CORRELATION:
        return (
            "watch",
            "相关性偏弱，需人工复核。",
            "复核相关性与危机期命中率，并检查异常点后再决定是否提交审批。",
        )
    return (
        "recommend_include",
        "影子指标满足准入检查，仍需审批确认。",
        "提交人工复核、历史回测和 v2 权重审批。",
    )


def _crisis_commodity_admission_decision_label(decision: str) -> str:
    if decision == "recommend_include":
        return "建议纳入"
    if decision == "watch":
        return "继续观察"
    return "暂不纳入"


def _crisis_commodity_admission_next_step(decision_counts: dict[str, int]) -> str:
    recommend_count = decision_counts["recommend_include"]
    watch_count = decision_counts["watch"]
    reject_count = decision_counts["do_not_include"]
    if recommend_count == 0 and watch_count > 0 and reject_count == 0:
        return f"{watch_count} 个商品候选继续观察；先复核相关性、危机期命中率和异常点，再提交 v2 权重审批。"
    parts: list[str] = []
    if recommend_count:
        parts.append(f"{recommend_count} 个商品候选可提交人工复核和 v2 权重审批")
    if watch_count:
        parts.append(f"{watch_count} 个商品候选继续观察")
    if reject_count:
        parts.append(f"{reject_count} 个商品候选先补齐历史样本")
    if not parts:
        return "暂无可用商品候选；先补齐商品期货历史数据。"
    return "；".join(parts) + "；审批前不改变正式 Crisis Score。"


def _crisis_commodity_max_abs_correlation(shadow: dict[str, object]) -> float | None:
    values = [
        abs(value)
        for key in ("same_day_correlation", "lead_1d_correlation", "lag_1d_correlation")
        if (value := _float_or_none(shadow.get(key))) is not None
    ]
    return round(max(values), 4) if values else None


def _crisis_commodity_candidate_approval_pack(
    *,
    admission: dict[str, object],
    shadow_impact: dict[str, object],
) -> dict[str, object]:
    items = [item for item in admission.get("items", []) if isinstance(item, dict)]
    decision_counts = admission.get("decision_counts") if isinstance(admission.get("decision_counts"), dict) else {}
    recommended_fields = [str(item.get("field") or "") for item in items if item.get("decision") == "recommend_include"]
    watch_fields = [str(item.get("field") or "") for item in items if item.get("decision") == "watch"]
    rejected_fields = [str(item.get("field") or "") for item in items if item.get("decision") == "do_not_include"]
    summary = (
        f"审批材料：建议纳入 {int(decision_counts.get('recommend_include') or 0)}，"
        f"继续观察 {int(decision_counts.get('watch') or 0)}，"
        f"暂不纳入 {int(decision_counts.get('do_not_include') or 0)}；"
        "审批前不改变正式 Crisis Score。"
    )
    copy_text = _crisis_commodity_approval_copy_text(
        summary=summary,
        admission=admission,
        shadow_impact=shadow_impact,
        items=items,
    )
    return {
        "pack_version": _CRISIS_COMMODITY_APPROVAL_PACK_VERSION,
        "scope": "commodity_candidate_approval_read_only",
        "source_rule_version": admission.get("rule_version"),
        "shadow_formula_version": shadow_impact.get("formula_version"),
        "decision_counts": {
            "recommend_include": int(decision_counts.get("recommend_include") or 0),
            "watch": int(decision_counts.get("watch") or 0),
            "do_not_include": int(decision_counts.get("do_not_include") or 0),
        },
        "recommended_fields": recommended_fields,
        "watch_fields": watch_fields,
        "rejected_fields": rejected_fields,
        "summary": summary,
        "copy_text": copy_text,
        "warnings": ["APPROVAL_PACK_READ_ONLY", "APPROVAL_REQUIRED_BEFORE_FORMULA_USE"],
        "approval_required": True,
        "official_score_unchanged": True,
    }


def _crisis_commodity_approval_copy_text(
    *,
    summary: str,
    admission: dict[str, object],
    shadow_impact: dict[str, object],
    items: list[dict[str, object]],
) -> str:
    lines = [
        "Crisis Score 商品候选审批材料",
        summary,
        f"规则版本 {admission.get('rule_version')}",
        f"影子公式 {shadow_impact.get('formula_version')}",
        f"正式 Crisis Score {_format_approval_number(shadow_impact.get('current_score'))}",
        f"shadow score {_format_approval_number(shadow_impact.get('shadow_score'))}",
        f"shadow delta {_format_approval_signed_number(shadow_impact.get('delta'))}",
        "边界：审批前不改变正式 Crisis Score，不改变正式权重，不写入数据库。",
        "候选明细：",
    ]
    lines.extend(_crisis_commodity_approval_item_line(item) for item in items)
    return "\n".join(lines)


def _crisis_commodity_approval_item_line(item: dict[str, object]) -> str:
    return (
        f"{item.get('label') or item.get('field')} · {item.get('decision_label')} · {item.get('reason')} · "
        f"样本 {_format_approval_count(item.get('sample_count'))}/{_format_approval_count(item.get('minimum_sample_count'))} · "
        f"危机样本 {_format_approval_count(item.get('crisis_sample_count'))}/"
        f"{_format_approval_count(item.get('minimum_crisis_sample_count'))} · "
        f"命中率 {_format_approval_percent(item.get('crisis_hit_rate'))} · "
        f"最大相关 {_format_approval_number(item.get('max_abs_correlation'))}/"
        f"{_format_approval_number(item.get('correlation_threshold'))} · "
        f"source {item.get('source') or '缺失'} · series {item.get('series_id') or '缺失'} · "
        "审批前不改变正式 Crisis Score"
    )


def _format_approval_count(value: object) -> str:
    number = _int_or_none(value)
    return str(number) if number is not None else "缺失"


def _format_approval_percent(value: object) -> str:
    number = _float_or_none(value)
    return f"{number * 100:.1f}%" if number is not None else "缺失"


def _format_approval_number(value: object) -> str:
    number = _float_or_none(value)
    return f"{number:.2f}" if number is not None else "缺失"


def _format_approval_signed_number(value: object) -> str:
    number = _float_or_none(value)
    if number is None:
        return "缺失"
    return f"{number:+.2f}"


def _crisis_commodity_candidate_decision(*, available: bool, date_alignment_status: str) -> dict[str, object]:
    if not available:
        return {
            "status": "missing_data",
            "label": "缺少数据",
            "reason": "商品旁证未命中，不能进入影子评估。",
            "next_step": "先完成商品期货刷新或源映射修复。",
        }
    if date_alignment_status != "aligned":
        return {
            "status": "needs_current_data",
            "label": "需要补齐当日数据",
            "reason": "商品旁证已命中但与分析日不一致；当前仍作为 supplemental_observation。",
            "next_step": "补齐到分析日后，再进入历史回测、相关性检验和权重审批。",
        }
    return {
        "status": "shadow_review_ready",
        "label": "影子评估就绪",
        "reason": "数据已命中且与分析日同日；当前仍作为 supplemental_observation，不改变 Crisis Score 公式。",
        "next_step": "完成历史回测、相关性检验、权重审批后，才能作为公式候选提交。",
    }


def _unique_sorted_texts(values: Iterable[object]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return sorted(out)


def _capability_result_card(
    definition: dict[str, object],
    result: dict[str, object] | None,
) -> dict[str, object]:
    raw_result = result or {}
    status = _capability_result_status(str(definition["key"]), raw_result)
    tone = _capability_result_tone(str(definition["key"]), raw_result, status)
    return {
        "key": definition["key"],
        "legacy_module": definition["legacy_module"],
        "label": definition["label"],
        "group": definition["group"],
        "status": status,
        "tone": tone,
        "score": _capability_result_score(str(definition["key"]), raw_result),
        "headline": _capability_result_headline(str(definition["key"]), raw_result),
        "primary_metric": _capability_primary_metric(str(definition["key"]), raw_result),
        "input_evidence": raw_result.get("input_evidence"),
        "evidence": _capability_result_evidence(str(definition["key"]), raw_result),
        "warnings": [str(item) for item in raw_result.get("warnings", []) if item],
        "result": raw_result,
    }


def _unavailable_capability_result(
    definition: dict[str, object],
    reason: str,
) -> dict[str, object]:
    return {
        "key": definition["key"],
        "legacy_module": definition["legacy_module"],
        "label": definition["label"],
        "group": definition["group"],
        "status": "unavailable",
        "tone": "missing",
        "score": None,
        "headline": reason,
        "primary_metric": None,
        "evidence": [],
        "warnings": [reason],
        "result": {"data_status": "unavailable", "warnings": [reason]},
    }


def _capability_result_status(key: str, result: dict[str, object]) -> str:
    data_status = str(result.get("data_status") or "").lower()
    if data_status in {"complete", "degraded", "unavailable"}:
        return data_status
    if key == "yield_curve_shape" and result.get("shape") == "Unavailable":
        return "unavailable"
    if key == "credit_spread_risk" and result.get("risk_level") == "UNAVAILABLE":
        return "unavailable"
    warnings = result.get("warnings")
    if isinstance(warnings, list) and warnings:
        return "degraded"
    return "complete" if result else "unavailable"


def _capability_result_tone(key: str, result: dict[str, object], status: str) -> str:
    if status == "unavailable":
        return "missing"
    if key == "monetary_policy_stance":
        stance = str(result.get("stance_label") or "")
        if stance == "accommodative":
            return "positive"
        if stance == "tight":
            return "negative"
    if key == "credit_spread_risk":
        risk = str(result.get("risk_level") or "")
        if risk in {"HIGH", "CRITICAL"}:
            return "negative"
        if risk == "LOW":
            return "positive"
    if key == "liquidity_stress":
        stress = str(result.get("stress_level") or "")
        if stress in {"HIGH", "CRITICAL"}:
            return "negative"
        if stress == "LOW":
            return "positive"
    if key == "crisis_score_cn":
        score = _float_or_none(result.get("crisis_score"))
        if score is None:
            return "missing"
        if score >= 1:
            return "negative"
        if score < 0:
            return "positive"
        return "neutral"
    if key == "cross_market_linkage":
        risk = str(result.get("overall_risk") or "")
        if risk == "HIGH":
            return "negative"
        if risk == "LOW":
            return "positive"
        # UNKNOWN / MEDIUM：不给出方向性 tone，避免无相关腿时伪装成积极信号
        return "neutral"
    if key == "economic_cycle":
        phase = str(result.get("cycle_phase") or "")
        if phase == "recovery":
            return "positive"
        if phase in {"stagflation", "recession"}:
            return "negative"
    if key == "merrill_clock_cn":
        regime = str(result.get("regime_label") or "")
        if regime == "复苏":
            return "positive"
        if regime in {"滞胀", "衰退"}:
            return "negative"
    if key == "cta_trend_cn":
        avg = _float_or_none(result.get("avg_composite"))
        if avg is not None and avg > 0.2:
            return "positive"
        if avg is not None and avg < -0.2:
            return "negative"
    if key == "dcc_garch_cn":
        warning = str(result.get("warning_level") or "")
        if warning == "红色预警":
            return "negative"
        if warning == "正常":
            return "positive"
    if key == "risk_parity_cn":
        return "neutral"
    if key == "macro_portfolio_impact":
        worst = _worst_portfolio_scenario(result)
        pnl_pct = _float_or_none(worst.get("pnl_pct")) if worst else None
        if pnl_pct is not None and pnl_pct <= -0.5:
            return "negative"
        if pnl_pct is not None and pnl_pct >= 0:
            return "positive"
    return "neutral"


def _capability_result_score(key: str, result: dict[str, object]) -> float | None:
    score_fields = {
        "monetary_policy_stance": "stance_score",
        "credit_spread_risk": "risk_score",
        "crisis_score_cn": "crisis_score",
        "leading_indicator": "lei_index",
        "liquidity_stress": "stress_score",
        "rate_turning_point": "percentile_1y",
        "economic_cycle": "growth_score",
        "merrill_clock_cn": "top_asset_score",
        "cta_trend_cn": "avg_composite",
        "dcc_garch_cn": "avg_correlation",
        "risk_parity_cn": "portfolio_vol_rp_pct",
    }
    if key in score_fields:
        return _round_float(_float_or_none(result.get(score_fields[key])))
    if key == "yield_curve_shape":
        spreads = result.get("spreads") if isinstance(result.get("spreads"), dict) else {}
        return _round_float(_float_or_none(spreads.get("10Y-1Y") if isinstance(spreads, dict) else None))
    if key == "cross_market_linkage":
        risk_score = {"LOW": 25.0, "MEDIUM": 55.0, "HIGH": 85.0}.get(str(result.get("overall_risk")), None)
        return risk_score
    if key == "macro_portfolio_impact":
        worst = _worst_portfolio_scenario(result)
        return _round_float(_float_or_none(worst.get("pnl_pct")) if worst else None)
    return None


def _capability_result_headline(key: str, result: dict[str, object]) -> str:
    for field in ("headline", "interpretation", "recommendation"):
        value = result.get(field)
        if value:
            return str(value)
    if key == "leading_indicator":
        return f"LEI {result.get('lei_index', 'n/a')} · {result.get('economic_state', 'unknown')} · {result.get('trend', 'flat')}"
    if key == "economic_cycle":
        return f"周期位置：{result.get('cycle_phase_cn', 'unknown')}"
    if key == "merrill_clock_cn":
        regime = result.get("regime_label") or "unknown"
        top_asset = result.get("top_asset")
        if top_asset:
            return f"美林时钟：{regime} · 偏好{top_asset}"
        return f"美林时钟：{regime}"
    if key == "macro_portfolio_impact":
        worst = _worst_portfolio_scenario(result)
        if worst:
            return f"压力最大情景：{worst.get('name_cn') or worst.get('name')}，PnL {worst.get('pnl_pct')}%"
    return "暂无可解释结果"


def _capability_primary_metric(
    key: str,
    result: dict[str, object],
) -> dict[str, object] | None:
    if key == "monetary_policy_stance":
        return _metric("立场得分", result.get("stance_score"), "")
    if key == "yield_curve_shape":
        spreads = result.get("spreads") if isinstance(result.get("spreads"), dict) else {}
        return _metric("10Y-1Y", spreads.get("10Y-1Y") if isinstance(spreads, dict) else None, "bp")
    if key == "credit_spread_risk":
        return _metric("AAA利差", result.get("aaa_spread_bp"), "bp")
    if key == "leading_indicator":
        return _metric("LEI", result.get("lei_index"), "")
    if key == "liquidity_stress":
        return _metric("压力分", result.get("stress_score"), "")
    if key == "crisis_score_cn":
        return _metric("Crisis Score", result.get("crisis_score"), "")
    if key == "cross_market_linkage":
        return _metric("联动风险", result.get("overall_risk"), "")
    if key == "rate_turning_point":
        return _metric("10Y国债", result.get("current_10y"), "%")
    if key == "economic_cycle":
        return _metric("周期", result.get("cycle_phase_cn"), "")
    if key == "merrill_clock_cn":
        return _metric("象限", result.get("regime_label"), "")
    if key == "cta_trend_cn":
        return _metric("合成信号", result.get("avg_composite"), "")
    if key == "dcc_garch_cn":
        return _metric("平均相关", result.get("avg_correlation"), "")
    if key == "risk_parity_cn":
        return _metric("组合波动", result.get("portfolio_vol_rp_pct"), "%")
    if key == "macro_portfolio_impact":
        worst = _worst_portfolio_scenario(result)
        return _metric("最差PnL", worst.get("pnl_pct") if worst else None, "%")
    return None


def _capability_result_evidence(key: str, result: dict[str, object]) -> list[str]:
    if not result:
        return []
    if key == "monetary_policy_stance":
        metrics = result.get("key_metrics") if isinstance(result.get("key_metrics"), dict) else {}
        return _compact_evidence(
            [
                _format_evidence("DR007", metrics.get("dr007"), "%") if isinstance(metrics, dict) else None,
                _format_evidence("10Y-1Y", metrics.get("gov_slope_10y_1y_bp"), "bp") if isinstance(metrics, dict) else None,
                _format_evidence("AAA spread", metrics.get("aaa_spread_bp"), "bp") if isinstance(metrics, dict) else None,
                f"as_of={result.get('as_of_date')}",
            ]
        )
    if key == "yield_curve_shape":
        spreads = result.get("spreads") if isinstance(result.get("spreads"), dict) else {}
        return _compact_evidence(
            [
                f"shape={result.get('shape')}",
                _format_evidence("10Y-1Y", spreads.get("10Y-1Y") if isinstance(spreads, dict) else None, "bp"),
                _format_evidence("percentile", result.get("percentile_1y"), "%"),
            ]
        )
    if key == "credit_spread_risk":
        return _compact_evidence(
            [
                f"risk={result.get('risk_level')}",
                _format_evidence("AAA", result.get("aaa_spread_bp"), "bp"),
                _format_evidence("AA-AAA", result.get("aa_minus_aaa_bp"), "bp"),
                f"as_of={result.get('as_of_date')}",
            ]
        )
    if key == "leading_indicator":
        return _compact_evidence(
            [
                _format_evidence("LEI", result.get("lei_index"), ""),
                f"state={result.get('economic_state')}",
                f"trend={result.get('trend')}",
            ]
        )
    if key == "liquidity_stress":
        return _compact_evidence(
            [
                _format_evidence("stress", result.get("stress_score"), ""),
                _format_evidence("short_gap_ratio", result.get("short_term_gap_ratio"), ""),
                _format_evidence("negative_buckets", result.get("negative_bucket_count"), ""),
            ]
        )
    if key == "crisis_score_cn":
        return _compact_evidence(
            [
                _format_evidence("score", result.get("crisis_score"), ""),
                f"regime={result.get('regime')}",
                _format_evidence("percentile", result.get("percentile"), "%"),
            ]
        )
    if key == "cross_market_linkage":
        return _compact_evidence(
            [
                f"risk={result.get('overall_risk')}",
                _format_evidence("bond_fx_corr", result.get("bond_fx_corr"), ""),
                _format_evidence("bond_oil_corr", result.get("bond_commodity_corr"), ""),
            ]
        )
    if key == "rate_turning_point":
        return _compact_evidence(
            [
                f"direction={result.get('direction')}",
                _format_evidence("10Y", result.get("current_10y"), "%"),
                _format_evidence("5d", result.get("change_5d_bp"), "bp"),
            ]
        )
    if key == "economic_cycle":
        return _compact_evidence(
            [
                f"phase={result.get('cycle_phase_cn')}",
                _format_evidence("growth", result.get("growth_score"), ""),
                _format_evidence("inflation", result.get("inflation_score"), ""),
            ]
        )
    if key == "merrill_clock_cn":
        return _compact_evidence(
            [
                f"regime={result.get('regime_label')}",
                _format_evidence("growth", result.get("growth_momentum"), ""),
                _format_evidence("inflation", result.get("inflation_momentum"), ""),
                _format_evidence("liquidity", result.get("liquidity_momentum"), ""),
                f"top={result.get('top_asset')}",
            ]
        )
    if key == "cta_trend_cn":
        return _compact_evidence(
            [
                f"trend={result.get('trend_label')}",
                _format_evidence("avg", result.get("avg_composite"), ""),
                f"bullish={result.get('bullish_count')}",
                f"bearish={result.get('bearish_count')}",
            ]
        )
    if key == "dcc_garch_cn":
        return _compact_evidence(
            [
                f"warning={result.get('warning_level')}",
                _format_evidence("avg_corr", result.get("avg_correlation"), ""),
                _format_evidence("assets", result.get("asset_count"), ""),
            ]
        )
    if key == "risk_parity_cn":
        return _compact_evidence(
            [
                f"phase={result.get('clock_phase')}",
                f"shadow={result.get('shadow')}",
                _format_evidence("vol", result.get("portfolio_vol_rp_pct"), "%"),
                f"top={result.get('top_asset')}",
            ]
        )
    if key == "macro_portfolio_impact":
        portfolio = result.get("portfolio") if isinstance(result.get("portfolio"), dict) else {}
        worst = _worst_portfolio_scenario(result)
        return _compact_evidence(
            [
                _format_evidence("total_mv", portfolio.get("total_mv") if isinstance(portfolio, dict) else None, ""),
                _format_evidence("duration", portfolio.get("weighted_duration") if isinstance(portfolio, dict) else None, ""),
                _format_evidence("worst_pnl", worst.get("pnl_pct") if worst else None, "%"),
            ]
        )
    return []


def _metric(label: str, value: object, unit: str) -> dict[str, object] | None:
    if value is None:
        return None
    rounded = _round_float(_float_or_none(value))
    return {
        "label": label,
        "value": rounded if rounded is not None else value,
        "unit": unit,
    }


def _worst_portfolio_scenario(result: dict[str, object]) -> dict[str, object] | None:
    scenarios = result.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        return None
    scenario_dicts = [item for item in scenarios if isinstance(item, dict)]
    if not scenario_dicts:
        return None
    return min(scenario_dicts, key=lambda item: _float_or_none(item.get("pnl_pct")) or 0.0)


def _compact_evidence(items: list[str | None]) -> list[str]:
    return [item for item in items if item and "None" not in item and "nan" not in item.lower()]


def _format_evidence(label: str, value: object, unit: str) -> str | None:
    if value is None:
        return None
    rounded = _round_float(_float_or_none(value))
    display = rounded if rounded is not None else value
    return f"{label}={display}{unit}"


def _round_float(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 2)


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _int_or_none(value: object) -> int | None:
    number = _float_or_none(value)
    return int(number) if number is not None else None


def _a_share_stampede_risk_card(a_share_risk: dict[str, object] | None) -> dict[str, object]:
    if not a_share_risk or a_share_risk.get("status") == "unavailable":
        warnings = a_share_risk.get("warnings") if isinstance(a_share_risk, dict) else []
        return _signal_card(
            "a_share_stampede_risk",
            "市场踩踏风险",
            "数据不足",
            "missing",
            None,
            [str(item) for item in warnings[:3]] if isinstance(warnings, list) else ["股票日线读面未命中"],
        )
    level = str(a_share_risk.get("risk_level") or "unknown")
    tone_by_level = {
        "green": "positive",
        "yellow": "neutral",
        "orange": "negative",
        "red": "negative",
        "unknown": "missing",
    }
    score = _float_or_none(a_share_risk.get("risk_score"))
    triggered = a_share_risk.get("triggered_rules") if isinstance(a_share_risk.get("triggered_rules"), list) else []
    warnings = a_share_risk.get("warnings") if isinstance(a_share_risk.get("warnings"), list) else []
    evidence = [str(item) for item in [*triggered[:2], *warnings[:1]]]
    if not evidence and a_share_risk.get("summary"):
        evidence = [str(a_share_risk["summary"])]
    return _signal_card(
        "a_share_stampede_risk",
        "市场踩踏风险",
        str(a_share_risk.get("risk_name") or level),
        tone_by_level.get(level, "missing"),
        round(score, 2) if score is not None else None,
        evidence,
    )


PRIMARY_SIGNAL_RULE_VERSION = "rv_macro_primary_signal_risk_first_v1"

# 风险闸门档位。Crisis 是 z-score、A股踩踏是 0-100 分，两者不可直接比较，
# 因此先各自映射成同一套严重度档，再比档而不是比分。
_CRISIS_SEVERITY_CRISIS_REGIME = 4
_CRISIS_SEVERITY_HIGH_RISK = 3
_A_SHARE_SEVERITY_BY_LEVEL = {"red": 4, "orange": 3}
_RISK_GATE_MIN_SEVERITY = 3

# 方向卡中性档分值，必须与 _liquidity_card / _risk_appetite_card / _credit_card 保持一致；
# 三张卡都是同一套 0-100 离散状态分，偏离各自中性档的幅度即方向信号强度。
_DIRECTION_NEUTRAL_SCORE = {"liquidity": 55, "risk_appetite": 52, "credit": 55}
# 强度并列时的固定顺序：流动性对宏观传导最直接，其次信用，最后风险偏好。
_DIRECTION_TIE_BREAK = ("liquidity", "credit", "risk_appetite")


def _primary_signal(
    key: str | None,
    selection_status: str,
    reason_code: str,
) -> dict[str, object]:
    return {
        "key": key,
        "selection_status": selection_status,
        "reason_code": reason_code,
        "rule_version": PRIMARY_SIGNAL_RULE_VERSION,
    }


def _crisis_risk_severity(capability_results: list[dict[str, object]]) -> int:
    crisis = next((item for item in capability_results if item.get("key") == "crisis_score_cn"), None)
    if crisis is None:
        return 0
    result = crisis.get("result") if isinstance(crisis.get("result"), dict) else {}
    score = _float_or_none(result.get("crisis_score"))
    if score is None:
        score = _float_or_none(crisis.get("score"))
    if score is None:
        return 0
    if score >= 3:
        return _CRISIS_SEVERITY_CRISIS_REGIME
    if score >= 2:
        return _CRISIS_SEVERITY_HIGH_RISK
    return 0


def _a_share_risk_severity(a_share_risk: dict[str, object] | None) -> int:
    if not a_share_risk or a_share_risk.get("status") == "unavailable":
        return 0
    level = str(a_share_risk.get("risk_level") or "unknown")
    return _A_SHARE_SEVERITY_BY_LEVEL.get(level, 0)


def _has_signal_card(signal_cards: list[dict[str, object]], key: str) -> bool:
    return any(card.get("key") == key for card in signal_cards)


def _strongest_direction_signal(signal_cards: list[dict[str, object]]) -> str | None:
    strongest_key: str | None = None
    strongest_strength = -1.0
    for key in _DIRECTION_TIE_BREAK:
        card = next((item for item in signal_cards if item.get("key") == key), None)
        if card is None or card.get("tone") == "missing":
            continue
        score = _float_or_none(card.get("score"))
        if score is None:
            continue
        strength = abs(score - _DIRECTION_NEUTRAL_SCORE[key])
        if strength > strongest_strength:
            strongest_key, strongest_strength = key, strength
    return strongest_key


def select_primary_signal(
    signal_cards: list[dict[str, object]],
    *,
    a_share_risk: dict[str, object] | None,
    capability_results: list[dict[str, object]],
    capabilities_deferred: bool,
) -> dict[str, object]:
    """风险优先主信号选择（业务规则 rv_macro_primary_signal_risk_first_v1）。

    先看风险闸门：Crisis 高风险/危机档或 A股 orange/red 档压过一切方向信号，
    两侧同档时取 Crisis（系统性风险优先于单市场踩踏）。未触发风险闸门时，
    才在同量纲方向卡里取偏离中性最远的一张。

    core 首屏尚未加载 Crisis 与 A股风险，缺少风险候选就无法执行该规则，
    因此一律返回 deferred，绝不用方向信号临时顶替。
    """
    if capabilities_deferred:
        return _primary_signal(None, "deferred", "core_scope_risk_candidates_deferred")

    # 主信号 key 必须能在同一份载荷里取到卡，否则前端会拿到悬空 key。
    crisis_severity = (
        _crisis_risk_severity(capability_results)
        if _has_signal_card(signal_cards, "crisis_score_cn")
        else 0
    )
    a_share_severity = (
        _a_share_risk_severity(a_share_risk)
        if _has_signal_card(signal_cards, "a_share_stampede_risk")
        else 0
    )
    if max(crisis_severity, a_share_severity) >= _RISK_GATE_MIN_SEVERITY:
        if crisis_severity >= a_share_severity:
            return _primary_signal("crisis_score_cn", "selected", "risk_gate_crisis_score")
        return _primary_signal("a_share_stampede_risk", "selected", "risk_gate_a_share_stampede")

    direction_key = _strongest_direction_signal(signal_cards)
    if direction_key is None:
        return _primary_signal(None, "unavailable", "no_eligible_signal")
    return _primary_signal(direction_key, "selected", "strongest_direction_signal")


def _crisis_score_card(capability_results: list[dict[str, object]], *, deferred: bool = False) -> dict[str, object]:
    crisis = next((item for item in capability_results if item.get("key") == "crisis_score_cn"), None)
    if crisis is None:
        if deferred:
            return _signal_card(
                "crisis_score_cn",
                "Crisis Score",
                "完整结果待加载",
                "neutral",
                None,
                ["首屏未运行完整 Crisis Score，打开完整分析后显示分数"],
            )
        return _signal_card("crisis_score_cn", "Crisis Score", "数据不足", "missing", None, ["Crisis Score 未接入"])
    result = crisis.get("result") if isinstance(crisis.get("result"), dict) else {}
    score = _float_or_none(crisis.get("score"))
    regime = str(result.get("regime") or crisis.get("headline") or "数据不足")
    evidence = crisis.get("evidence") if isinstance(crisis.get("evidence"), list) else []
    warnings = crisis.get("warnings") if isinstance(crisis.get("warnings"), list) else []
    return _signal_card(
        "crisis_score_cn",
        "Crisis Score",
        regime,
        str(crisis.get("tone") or "neutral"),
        round(score, 2) if score is not None else None,
        [str(item) for item in (evidence or warnings)[:3]],
    )


def _liquidity_card(indicator_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
    dr007 = _number(indicator_by_key.get("dr007"), "latest_value")
    ncd = _number(indicator_by_key.get("ncd_3m"), "latest_value")
    if dr007 is None and ncd is None:
        return _signal_card("liquidity", "流动性", "数据不足", "missing", None, ["DR007 / 3M NCD 未命中"])
    anchor = dr007 if dr007 is not None else ncd
    assert anchor is not None
    if anchor <= 1.9:
        stance, tone, score = "偏松", "positive", 78
    elif anchor >= 2.3:
        stance, tone, score = "偏紧", "negative", 32
    else:
        stance, tone, score = "中性", "neutral", 55
    evidence = []
    if dr007 is not None:
        evidence.append(f"DR007 {dr007:.2f}%")
    if ncd is not None:
        evidence.append(f"3M NCD {ncd:.2f}%")
    return _signal_card("liquidity", "流动性", stance, tone, score, evidence)


def _risk_appetite_card(indicator_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
    hs300_change = _number(indicator_by_key.get("hs300"), "change_pct")
    copper_change = _number(indicator_by_key.get("copper"), "change_pct")
    values = [item for item in (hs300_change, copper_change) if item is not None]
    if not values:
        return _signal_card("risk_appetite", "风险偏好", "数据不足", "missing", None, ["权益 / 工业品缺少可比较序列"])
    average = sum(values) / len(values)
    if average > 0.5:
        stance, tone, score = "改善", "positive", 72
    elif average < -0.5:
        stance, tone, score = "转弱", "negative", 35
    else:
        stance, tone, score = "震荡", "neutral", 52
    evidence = []
    if hs300_change is not None:
        evidence.append(f"沪深300 {hs300_change:+.2f}%")
    if copper_change is not None:
        evidence.append(f"铜主力 {copper_change:+.2f}%")
    return _signal_card("risk_appetite", "风险偏好", stance, tone, score, evidence)


def _credit_card(indicator_by_key: dict[str, dict[str, object]]) -> dict[str, object]:
    gov_5y = _number(indicator_by_key.get("gov_5y"), "latest_value")
    aa_5y = _number(indicator_by_key.get("aa_5y"), "latest_value")
    if gov_5y is None or aa_5y is None:
        return _signal_card("credit", "信用利差", "数据不足", "missing", None, ["5Y 国债 / 5Y AA 信用债未同时命中"])
    spread_bp = (aa_5y - gov_5y) * 100
    if spread_bp >= 90:
        stance, tone, score = "偏宽", "negative", 38
    elif spread_bp <= 45:
        stance, tone, score = "偏窄", "positive", 70
    else:
        stance, tone, score = "中性", "neutral", 55
    return _signal_card("credit", "信用利差", stance, tone, score, [f"AA-国债 5Y {spread_bp:.1f}bp"])


def _script_output_card(output_files: list[dict[str, object]]) -> dict[str, object]:
    if output_files:
        latest = max(output_files, key=lambda item: str(item["modified_at"]))
        return _signal_card(
            "outputs",
            "脚本产物",
            "已生成",
            "positive",
            min(100, 45 + len(output_files) * 5),
            [f"{len(output_files)} 个输出文件", str(latest["name"])],
        )
    return _signal_card(
        "outputs",
        "脚本产物",
        "待生成",
        "neutral",
        45,
        ["尚未在 data/macro_toolkit/output 发现输出文件"],
    )


def _signal_card(
    key: str,
    title: str,
    stance: str,
    tone: str,
    score: int | None,
    evidence: list[str],
) -> dict[str, object]:
    return {
        "key": key,
        "title": title,
        "stance": stance,
        "tone": tone,
        "score": score,
        "evidence": evidence,
    }


def _number(item: dict[str, object] | None, field: str) -> float | None:
    if item is None or item.get(field) is None:
        return None
    return float(item[field])


def _analysis_data_health(
    *,
    indicators: list[dict[str, object]],
    source_checks: list[dict[str, object]],
    capability_results: list[dict[str, object]],
    capabilities: list[dict[str, object]],
    runtime_status: dict[str, object],
    warnings: list[str],
    reference_date: str | None,
) -> dict[str, object]:
    deferred_sections = [
        str(section["key"])
        for section in runtime_status.get("deferred_sections", [])
        if isinstance(section, dict) and section.get("key")
    ]
    analysis_scope = str(runtime_status.get("analysis_scope") or "")
    return {
        "analysis_scope": runtime_status.get("analysis_scope"),
        "indicator_coverage": _indicator_data_health(indicators),
        "source_coverage": _source_data_health(
            source_checks,
            deferred="source_checks" in deferred_sections,
        ),
        "capability_results": _capability_result_data_health(
            capability_results,
            deferred="capability_results" in deferred_sections,
        ),
        "capability_plan": _capability_plan_data_health(
            capabilities,
            deferred="capabilities" in deferred_sections,
        ),
        "deferred_sections": deferred_sections,
        "repair_items": _analysis_repair_items(
            indicators=indicators,
            source_checks=source_checks,
            capability_results=capability_results,
            deferred_sections=deferred_sections,
            analysis_scope=analysis_scope,
            reference_date=reference_date,
        ),
        "warnings": warnings,
    }


def _analysis_repair_items(
    *,
    indicators: list[dict[str, object]],
    source_checks: list[dict[str, object]],
    capability_results: list[dict[str, object]],
    deferred_sections: list[str],
    analysis_scope: str,
    reference_date: str | None,
) -> list[dict[str, object]]:
    missing_indicator_aliases = {
        str(item.get("alias"))
        for item in indicators
        if item.get("alias") and item.get("latest_value") is None
    }
    items: list[dict[str, object]] = [
        _missing_indicator_repair_item(item, analysis_scope=analysis_scope, reference_date=reference_date)
        for item in indicators
        if item.get("latest_value") is None
    ]

    if "source_checks" not in deferred_sections:
        items.extend(
            _source_repair_item(check, analysis_scope=analysis_scope, reference_date=reference_date)
            for check in source_checks
            if _source_check_needs_repair(check, reference_date)
            and str(check.get("alias") or "") not in missing_indicator_aliases
        )

    if "capability_results" not in deferred_sections:
        items.extend(
            _capability_repair_item(item, analysis_scope=analysis_scope, reference_date=reference_date)
            for item in capability_results
            if str(item.get("status") or "") in {"degraded", "unavailable"}
        )

    items.extend(
        _deferred_repair_item(section, analysis_scope=analysis_scope, reference_date=reference_date)
        for section in deferred_sections
        if section in {"source_checks", "capability_results", "capabilities"}
    )
    return sorted(items, key=_repair_item_sort_key)


def _missing_indicator_repair_item(
    item: dict[str, object],
    *,
    analysis_scope: str,
    reference_date: str | None,
) -> dict[str, object]:
    alias = str(item.get("alias") or "")
    label = str(item.get("label") or item.get("key") or alias)
    return {
        "type": "missing",
        "scope": analysis_scope,
        "priority": "high",
        "key": f"indicator:{item.get('key')}",
        "alias": alias or None,
        "label": label,
        "source_table": None,
        "latest_date": None,
        "reference_date": reference_date,
        "stale_days": None,
        "suggested_action": f"补齐 {alias or label} 后重新运行完整宏观分析；缺失项不能按 0 处理。",
        "action": _source_backfill_action("需要补齐来源数据", alias=alias),
        "tags": ["indicator"],
    }


def _source_check_needs_repair(check: dict[str, object], reference_date: str | None) -> bool:
    if int(check.get("row_count") or 0) <= 0:
        return True
    latest = check.get("latest")
    if not isinstance(latest, dict):
        return True
    if str(check.get("alias") or "") not in _DAILY_SOURCE_CHECK_ALIASES:
        return False
    return _stale_days(latest.get("date"), reference_date) is not None


def _source_repair_item(
    check: dict[str, object],
    *,
    analysis_scope: str,
    reference_date: str | None,
) -> dict[str, object]:
    alias = str(check.get("alias") or "")
    latest = check.get("latest") if isinstance(check.get("latest"), dict) else None
    latest_date = str(latest.get("date"))[:10] if isinstance(latest, dict) and latest.get("date") else None
    stale_days = _stale_days(latest_date, reference_date)
    if int(check.get("row_count") or 0) <= 0 or latest is None:
        return {
            "type": "missing",
            "scope": analysis_scope,
            "priority": "high",
            "key": f"source:{alias}",
            "alias": alias or None,
            "label": alias,
            "source_table": "system_macro_sources",
            "latest_date": None,
            "reference_date": reference_date,
            "stale_days": None,
            "suggested_action": f"补齐 {alias} 来源数据后重新运行完整宏观分析；缺失项不能按 0 处理。",
            "action": _source_backfill_action("需要补齐来源数据", alias=alias),
            "tags": ["source"],
        }
    return {
        "type": "stale",
        "scope": analysis_scope,
        "priority": "medium",
        "key": f"source:{alias}",
        "alias": alias or None,
        "label": alias,
        "source_table": "system_macro_sources",
        "latest_date": latest_date,
        "reference_date": reference_date,
        "stale_days": stale_days,
        "suggested_action": (
            f"{alias} 最新 {latest_date}，落后分析日 {reference_date} {stale_days} 天；"
            "刷新 Choice/Tushare 后再确认。"
        ),
        "action": _source_backfill_action("需要刷新来源", alias=alias),
        "tags": ["source"],
    }


def _capability_repair_item(
    item: dict[str, object],
    *,
    analysis_scope: str,
    reference_date: str | None,
) -> dict[str, object]:
    key = str(item.get("key") or "")
    status = str(item.get("status") or "")
    warnings = [str(warning) for warning in item.get("warnings", []) if warning]
    priority = "high" if status == "unavailable" else "medium"
    label = str(item.get("label") or key)
    warning_text = " / ".join(warnings[:3])
    reason = warning_text or status
    return {
        "type": "missing" if status == "unavailable" else "degraded",
        "scope": analysis_scope,
        "priority": priority,
        "key": f"capability:{key}",
        "alias": None,
        "label": label,
        "source_table": None,
        "latest_date": None,
        "reference_date": reference_date,
        "stale_days": None,
        "suggested_action": f"{label} 当前 {status}：{reason}；补齐输入证据后重新运行完整宏观分析。",
        "action": _full_analysis_action(
            label="重新完整分析",
            reason="补齐输入证据后重新运行完整分析确认状态。",
        ),
        "tags": ["capability"],
    }


def _deferred_repair_item(
    section: str,
    *,
    analysis_scope: str,
    reference_date: str | None,
) -> dict[str, object]:
    return {
        "type": "deferred",
        "scope": analysis_scope,
        "priority": "low",
        "key": f"deferred:{section}",
        "alias": None,
        "label": section,
        "source_table": None,
        "latest_date": None,
        "reference_date": reference_date,
        "stale_days": None,
        "suggested_action": f"打开完整分析后确认 {section}，不把首屏延后加载当作缺失。",
        "action": _full_analysis_action(
            label="查看完整分析",
            reason="首屏延后加载，完整分析可确认。",
        ),
        "tags": ["deferred"],
    }


def _source_backfill_action(label: str, *, alias: str | None = None) -> dict[str, object]:
    enabled = str(alias or "").strip().lower() in _SOURCE_BACKFILL_TARGETS
    return {
        "kind": "source_backfill_required",
        "label": label,
        "enabled": enabled,
        "reason": (
            "可触发宏观来源补齐；完成后重新运行完整分析确认。"
            if enabled
            else "当前没有已接入的一键宏观序列刷新接口。"
        ),
        "analysis_detail": "full",
    }


def _full_analysis_action(*, label: str, reason: str) -> dict[str, object]:
    return {
        "kind": "load_full_analysis",
        "label": label,
        "enabled": True,
        "reason": reason,
        "analysis_detail": "full",
    }


def _stale_days(latest_date: object, reference_date: str | None) -> int | None:
    if not latest_date or not reference_date:
        return None
    try:
        latest = date.fromisoformat(str(latest_date)[:10])
        reference = date.fromisoformat(str(reference_date)[:10])
    except ValueError:
        return None
    days = (reference - latest).days
    return days if days > 1 else None


def _repair_item_sort_key(item: dict[str, object]) -> tuple[int, str, str]:
    priority_order = {"high": 0, "medium": 1, "low": 2}
    type_order = {"missing": 0, "stale": 1, "degraded": 2, "deferred": 3}
    return (
        priority_order.get(str(item.get("priority")), 9),
        str(type_order.get(str(item.get("type")), 9)),
        str(item.get("key") or ""),
    )


def _indicator_data_health(indicators: list[dict[str, object]]) -> dict[str, object]:
    hit_count = sum(1 for item in indicators if item.get("latest_value") is not None)
    missing = [
        {
            "key": item.get("key"),
            "alias": item.get("alias"),
            "label": item.get("label"),
        }
        for item in indicators
        if item.get("latest_value") is None
    ]
    return {
        "hit_count": hit_count,
        "total_count": len(indicators),
        "hit_rate": round(hit_count / len(indicators), 4) if indicators else None,
        "missing_count": len(missing),
        "missing": missing,
    }


def _source_data_health(
    source_checks: list[dict[str, object]],
    *,
    deferred: bool,
) -> dict[str, object]:
    hit_count = sum(1 for item in source_checks if int(item.get("row_count") or 0) > 0)
    missing_aliases = [
        str(item["alias"])
        for item in source_checks
        if item.get("alias") and int(item.get("row_count") or 0) <= 0
    ]
    return {
        "hit_count": hit_count,
        "total_count": len(source_checks),
        "hit_rate": round(hit_count / len(source_checks), 4) if source_checks else None,
        "latest_date": _latest_source_check_date(source_checks),
        "deferred": deferred,
        "missing_aliases": missing_aliases,
    }


def _capability_result_data_health(
    capability_results: list[dict[str, object]],
    *,
    deferred: bool,
) -> dict[str, object]:
    return {
        "complete": sum(1 for item in capability_results if item.get("status") == "complete"),
        "degraded": sum(1 for item in capability_results if item.get("status") == "degraded"),
        "unavailable": sum(1 for item in capability_results if item.get("status") == "unavailable"),
        "total_count": len(capability_results),
        "deferred": deferred,
    }


def _capability_plan_data_health(
    capabilities: list[dict[str, object]],
    *,
    deferred: bool,
) -> dict[str, object]:
    ready_count = sum(1 for item in capabilities if str(item.get("data_status")) == "ready")
    wired_count = sum(
        1
        for item in capabilities
        if str(item.get("route_status")) == "wired" and str(item.get("frontend_status")) == "visible"
    )
    return {
        "ready_count": ready_count,
        "wired_count": wired_count,
        "total_count": len(capabilities),
        "deferred": deferred,
    }
