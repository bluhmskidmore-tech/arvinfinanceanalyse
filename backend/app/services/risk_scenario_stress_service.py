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
            "source_result_kind": str(tensor_meta.get("result_kind") or "risk.tensor"),
            "scenarios": _scenario_rows(tensor_result),
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
    controls = dict(tensor_result.get("dv01_controls") or {})
    stress_scenarios = list(controls.get("stress_scenarios") or [])
    ten_bp = dict(stress_scenarios[0]) if stress_scenarios else {}
    return {
        "category": "rate",
        "scenario_key": "parallel_rate_up_10bp",
        "description": "+10bp parallel rate shock using regulatory DV01.",
        "shock": ten_bp.get("shock_bp") or numeric_from_raw(raw=10.0, unit="bp", precision=0, sign_aware=True).model_dump(mode="json"),
        "estimated_pnl_impact": ten_bp.get("estimated_pnl_impact"),
        "human_review_required": True,
    }


def _credit_scenario(tensor_result: dict[str, Any]) -> dict[str, Any]:
    cs01 = _numeric_raw(tensor_result.get("cs01"))
    impact = None if cs01 is None else -cs01 * 10.0
    return {
        "category": "credit",
        "scenario_key": "credit_spread_up_10bp",
        "description": "+10bp credit spread shock using CS01.",
        "shock": numeric_from_raw(raw=10.0, unit="bp", precision=0, sign_aware=True).model_dump(mode="json"),
        "estimated_pnl_impact": numeric_from_raw(
            raw=impact,
            unit="yuan",
            precision=2,
            sign_aware=True,
        ).model_dump(mode="json"),
        "human_review_required": True,
    }


def _liquidity_scenario(tensor_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": "liquidity",
        "scenario_key": "cashflow_gap_review",
        "description": "Review 30d and 90d liquidity gaps under stressed funding assumptions.",
        "liquidity_gap_30d": tensor_result.get("liquidity_gap_30d"),
        "liquidity_gap_90d": tensor_result.get("liquidity_gap_90d"),
        "human_review_required": True,
    }


def _fx_scenario() -> dict[str, Any]:
    return {
        "category": "fx",
        "scenario_key": "fx_parallel_move_review",
        "description": "FX stress requires currency exposure input outside the current risk tensor fact.",
        "data_status": "exposure_input_required",
        "human_review_required": True,
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
