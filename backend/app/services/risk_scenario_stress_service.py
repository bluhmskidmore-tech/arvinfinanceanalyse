from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from backend.app.schemas.common_numeric import numeric_from_raw
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.risk_tensor_service import risk_tensor_envelope

RULE_VERSION = "rv_risk_tensor_scenario_stress_v1"
CACHE_VERSION = "cv_risk_tensor_scenario_stress_v1"


def risk_scenario_stress_envelope(
    duckdb_path: str,
    governance_dir: str,
    report_date: str | date,
) -> dict[str, object]:
    report_date_text = _coerce_report_date(report_date).isoformat()
    tensor_envelope = risk_tensor_envelope(
        duckdb_path=duckdb_path,
        governance_dir=governance_dir,
        report_date=report_date_text,
    )
    tensor_result = dict(tensor_envelope["result"])
    tensor_meta = dict(tensor_envelope["result_meta"])
    scenarios = _scenario_rows(tensor_result)
    source_warnings = [str(item) for item in tensor_result.get("warnings") or []]

    return build_result_envelope(
        basis="scenario",
        trace_id=_trace_id(),
        result_kind="risk.tensor.scenario_stress",
        cache_version=CACHE_VERSION,
        source_version=str(tensor_meta.get("source_version") or "sv_risk_tensor_scenario_stress"),
        rule_version=RULE_VERSION,
        quality_flag="warning",
        vendor_version=str(tensor_meta.get("vendor_version") or "vv_none"),
        vendor_status=str(tensor_meta.get("vendor_status") or "ok"),
        fallback_mode=str(tensor_meta.get("fallback_mode") or "none"),
        filters_applied={"report_date": report_date_text},
        tables_used=["fact_formal_risk_tensor_daily"],
        evidence_rows=1,
        source_surface="risk_tensor",
        requested_report_date=report_date_text,
        resolved_report_date=report_date_text,
        as_of_date=report_date_text,
        date_basis="formal_snapshot_scenario_overlay",
        result_payload={
            "basis": "scenario",
            "report_date": report_date_text,
            "scenario_set_id": "standard_risk_tensor_scenario_v1",
            "rule_version": RULE_VERSION,
            "source": {
                "result_kind": str(tensor_meta.get("result_kind") or "risk.tensor"),
                "trace_id": tensor_meta.get("trace_id"),
                "source_version": tensor_meta.get("source_version"),
                "rule_version": tensor_meta.get("rule_version"),
                "cache_version": tensor_meta.get("cache_version"),
                "quality_flag": tensor_meta.get("quality_flag"),
            },
            "summary": _scenario_summary(scenarios),
            "scenarios": scenarios,
            "warnings": [
                "Scenario stress is a review-only overlay on the materialized formal Risk Tensor; "
                "it is not a formal PnL, limit decision, or trading instruction."
            ],
            "source_warnings": source_warnings,
        },
    )


def _scenario_rows(tensor_result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _rate_scenario(tensor_result),
        _credit_scenario(tensor_result),
        _liquidity_scenario(tensor_result),
        _fx_scenario(),
    ]


def _rate_scenario(tensor_result: dict[str, Any]) -> dict[str, Any]:
    shock_bp = 10.0
    regulatory_dv01 = _numeric_raw(tensor_result.get("regulatory_dv01"))
    impact = None if regulatory_dv01 is None else -regulatory_dv01 * shock_bp
    return {
        "category": "rate",
        "scenario_key": "parallel_rate_up_10bp",
        "label": "利率平行上行 10bp",
        "source_field": "regulatory_dv01",
        "shock": numeric_from_raw(
            raw=shock_bp,
            unit="bp",
            precision=0,
            sign_aware=True,
        ).model_dump(mode="json"),
        "estimated_impact": numeric_from_raw(
            raw=impact,
            unit="yuan",
            precision=2,
            sign_aware=True,
        ).model_dump(mode="json"),
        "measure": "estimated_pnl_impact",
        "calculation": "-regulatory_dv01 * shock_bp",
        "interpretation": "利率上行时，按已物化监管口径 DV01 估算组合价格影响。",
        "data_status": "available" if regulatory_dv01 is not None else "source_missing",
        "human_review_required": True,
    }


def _credit_scenario(tensor_result: dict[str, Any]) -> dict[str, Any]:
    cs01 = _numeric_raw(tensor_result.get("cs01"))
    impact = None if cs01 is None else -cs01 * 10.0
    return {
        "category": "credit",
        "scenario_key": "credit_spread_up_10bp",
        "label": "信用利差走阔 10bp",
        "source_field": "cs01",
        "shock": numeric_from_raw(raw=10.0, unit="bp", precision=0, sign_aware=True).model_dump(mode="json"),
        "estimated_impact": numeric_from_raw(
            raw=impact,
            unit="yuan",
            precision=2,
            sign_aware=True,
        ).model_dump(mode="json"),
        "measure": "estimated_pnl_impact",
        "calculation": "-cs01 * shock_bp",
        "interpretation": "信用利差走阔时，按已物化 CS01 估算信用敏感度影响。",
        "data_status": "available" if cs01 is not None else "source_missing",
        "human_review_required": True,
    }


def _liquidity_scenario(tensor_result: dict[str, Any]) -> dict[str, Any]:
    shock_pct = 0.10
    asset_cashflow = _numeric_raw(tensor_result.get("asset_cashflow_30d"))
    liability_cashflow = _numeric_raw(tensor_result.get("liability_cashflow_30d"))
    baseline_gap = _numeric_raw(tensor_result.get("liquidity_gap_30d"))
    total_market_value = _numeric_raw(tensor_result.get("total_market_value"))
    available = (
        asset_cashflow is not None
        and liability_cashflow is not None
        and baseline_gap is not None
    )
    if asset_cashflow is None or liability_cashflow is None:
        stressed_gap = None
    else:
        stressed_gap = (
            asset_cashflow * (1 - shock_pct)
            - liability_cashflow * (1 + shock_pct)
        )
    impact = stressed_gap - baseline_gap if stressed_gap is not None and baseline_gap is not None else None
    baseline_ratio = (
        baseline_gap / total_market_value
        if baseline_gap is not None
        and total_market_value is not None
        and total_market_value != 0
        else None
    )
    stressed_ratio = (
        stressed_gap / total_market_value
        if stressed_gap is not None
        and total_market_value is not None
        and total_market_value != 0
        else None
    )
    return {
        "category": "liquidity",
        "scenario_key": "liquidity_30d_cashflow_10pct",
        "label": "30 天现金流压力 10%",
        "source_field": "asset_cashflow_30d/liability_cashflow_30d/liquidity_gap_30d",
        # shock_pct / gap ratios are decimal ratios (0.10 == 10%); ratios can
        # legitimately exceed 1, so bypass the legacy "auto" rescale heuristic.
        "shock": numeric_from_raw(raw=shock_pct, unit="pct", precision=1, sign_aware=True, raw_scale="ratio").model_dump(mode="json"),
        "estimated_impact": numeric_from_raw(raw=impact, unit="yuan", precision=2, sign_aware=True).model_dump(mode="json"),
        "measure": "stressed_30d_liquidity_gap_delta",
        "calculation": (
            "asset_cashflow_30d * (1 - shock_pct) - "
            "liability_cashflow_30d * (1 + shock_pct) - liquidity_gap_30d"
        ),
        "interpretation": "现金流压力下的 30 天流动性缺口变化；负值表示缓冲收窄。",
        "data_status": "available" if available else "source_missing",
        "human_review_required": True,
        "baseline_value": numeric_from_raw(raw=baseline_gap, unit="yuan", precision=2, sign_aware=True).model_dump(mode="json"),
        "stressed_value": numeric_from_raw(raw=stressed_gap, unit="yuan", precision=2, sign_aware=True).model_dump(mode="json"),
        "baseline_ratio": numeric_from_raw(raw=baseline_ratio, unit="pct", precision=1, sign_aware=True, raw_scale="ratio").model_dump(mode="json"),
        "stressed_ratio": numeric_from_raw(raw=stressed_ratio, unit="pct", precision=1, sign_aware=True, raw_scale="ratio").model_dump(mode="json"),
    }


def _fx_scenario() -> dict[str, Any]:
    return {
        "category": "fx",
        "scenario_key": "fx_parallel_move_review",
        "label": "汇率波动情景",
        "source_field": "fx_exposure",
        "shock": numeric_from_raw(raw=None, unit="pct", precision=1, sign_aware=True, raw_scale="ratio").model_dump(mode="json"),
        "estimated_impact": numeric_from_raw(raw=None, unit="yuan", precision=2, sign_aware=True).model_dump(mode="json"),
        "measure": "estimated_pnl_impact",
        "calculation": "fx_exposure * fx_shock",
        "interpretation": "当前风险张量未提供汇率敞口，接入 FX exposure 后方可估算。",
        "data_status": "source_missing",
        "human_review_required": True,
    }


def _scenario_summary(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    available = [row for row in scenarios if row.get("data_status") == "available"]
    impacts = [
        (raw, str(row["scenario_key"]))
        for row in available
        if (raw := _numeric_raw(row.get("estimated_impact"))) is not None
    ]
    worst_impact, worst_key = min(impacts, key=lambda item: item[0]) if impacts else (None, None)
    return {
        "scenario_count": len(scenarios),
        "available_count": len(available),
        "review_required_count": sum(bool(row.get("human_review_required")) for row in scenarios),
        "worst_estimated_impact": numeric_from_raw(
            raw=worst_impact,
            unit="yuan",
            precision=2,
            sign_aware=True,
        ).model_dump(mode="json"),
        "worst_scenario_key": worst_key,
        "message": "已基于物化风险张量生成标准压力情景；所有结果均需人工复核。",
    }


def _numeric_raw(value: object) -> float | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("raw")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError, ArithmeticError):
        return None


def _coerce_report_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"
