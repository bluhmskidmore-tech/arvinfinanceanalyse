from __future__ import annotations

from datetime import date

from backend.app.schemas.advanced_attribution import AdvancedAttributionBundlePayload
from backend.app.services.bond_analytics_service import get_return_decomposition
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
    build_scenario_result_meta,
)
from backend.app.services.pnl_bridge_service import pnl_bridge_envelope

ADVANCED_ATTRIBUTION_RESULT_KIND = "balance-analysis.advanced_attribution_bundle"
RULE_VERSION_ADVANCED_ATTRIBUTION = "rv_advanced_attribution_bundle_v0"
SOURCE_VERSION_NOT_READY = "sv_advanced_attribution_not_ready"
CACHE_VERSION_ADVANCED_ATTRIBUTION = "cv_advanced_attribution_v0"

# Stable machine-oriented keys; align with bond-analytics Phase 3 boundary docs.
_NOT_READY_MISSING_INPUTS: tuple[str, ...] = (
    "phase3_yield_curves_aligned_to_instruments",
    "trade_level_position_and_cashflow_history",
    "benchmark_index_total_return_series",
    "pnl_actuals_aligned_to_attribution_window",
)

_NOT_READY_BLOCKED_COMPONENTS: tuple[str, ...] = (
    "roll_down",
    "rate_effect",
    "spread_effect",
    "treasury_curve",
    "credit_spread_migration",
    "realized_trading",
    "action_attribution",
)

_NOT_READY_WARNINGS: tuple[str, ...] = (
    "bond_analytics.phase3: roll_down / rate_effect / spread_effect / trading require Phase 3 curve and trade data",
    "balance-analysis.advanced_attribution_bundle: status=not_ready; no attribution figures are returned",
)


def _normalize_scenario_inputs(
    *,
    treasury_shift_bp: int | None = None,
    spread_shift_bp: int | None = None,
) -> dict[str, int]:
    inputs: dict[str, int] = {}
    if treasury_shift_bp not in (None, 0):
        inputs["treasury_shift_bp"] = int(treasury_shift_bp)
    if spread_shift_bp not in (None, 0):
        inputs["spread_shift_bp"] = int(spread_shift_bp)
    return inputs


def advanced_attribution_bundle_envelope(
    *,
    report_date: str,
    scenario_name: str | None = None,
    treasury_shift_bp: int | None = None,
    spread_shift_bp: int | None = None,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
) -> dict[str, object]:
    """Slice A/B: analytical or explicit-scenario not_ready contract; no DuckDB reads; no formal writes."""
    scenario_inputs = _normalize_scenario_inputs(
        treasury_shift_bp=treasury_shift_bp,
        spread_shift_bp=spread_shift_bp,
    )
    is_scenario = bool(scenario_inputs)
    upstream_summaries, upstream_warnings = (
        ({}, [])
        if is_scenario
        else _build_upstream_summaries(
            report_date=report_date,
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
        )
    )
    payload = AdvancedAttributionBundlePayload(
        report_date=report_date,
        mode="scenario" if is_scenario else "analytical",
        scenario_name=(scenario_name or "custom") if is_scenario else None,
        scenario_inputs=scenario_inputs,
        upstream_summaries=upstream_summaries,
        status="not_ready",
        missing_inputs=list(_NOT_READY_MISSING_INPUTS),
        blocked_components=list(_NOT_READY_BLOCKED_COMPONENTS),
        warnings=list(
            [
                *(
                    [
                        "balance-analysis.advanced_attribution_bundle: explicit scenario inputs requested; "
                        "returning scenario-scoped not_ready contract only"
                    ]
                    if is_scenario
                    else []
                ),
                *upstream_warnings,
                *_NOT_READY_WARNINGS,
            ]
        ),
    )
    meta_builder = build_scenario_result_meta if is_scenario else build_analytical_result_meta
    meta = meta_builder(
        trace_id=f"tr_balance_analysis_advanced_attribution_{report_date}",
        result_kind=ADVANCED_ATTRIBUTION_RESULT_KIND,
        cache_version=CACHE_VERSION_ADVANCED_ATTRIBUTION,
        source_version=SOURCE_VERSION_NOT_READY,
        rule_version=RULE_VERSION_ADVANCED_ATTRIBUTION,
        quality_flag="warning",
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )


def _build_upstream_summaries(
    *,
    report_date: str,
    duckdb_path: str | None,
    governance_dir: str | None,
) -> tuple[dict[str, dict[str, str | list[str]]], list[str]]:
    if not duckdb_path or not governance_dir:
        return {}, []

    summaries: dict[str, dict[str, str | list[str]]] = {}
    warnings: list[str] = []
    report_date_value = date.fromisoformat(report_date)

    try:
        return_env = get_return_decomposition(report_date_value, "MoM", "all", "all")
        return_result = dict(return_env.get("result", {}))
        summaries["return_decomposition"] = {
            "carry": str(return_result.get("carry") or ""),
            "roll_down": str(return_result.get("roll_down") or ""),
            "rate_effect": str(return_result.get("rate_effect") or ""),
            "spread_effect": str(return_result.get("spread_effect") or ""),
            "explained_pnl": str(return_result.get("explained_pnl") or ""),
            "warnings": [str(item) for item in list(return_result.get("warnings") or [])],
        }
    except Exception as exc:
        warnings.append(
            f"advanced_attribution_bundle: return_decomposition summary unavailable: {exc}"
        )

    try:
        bridge_env = pnl_bridge_envelope(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            report_date=report_date,
        )
        bridge_result = dict(bridge_env.get("result", {}))
        bridge_summary = dict(bridge_result.get("summary", {}))
        summaries["pnl_bridge"] = {
            "total_carry": str(bridge_summary.get("total_carry") or ""),
            "total_roll_down": str(bridge_summary.get("total_roll_down") or ""),
            "total_treasury_curve": str(bridge_summary.get("total_treasury_curve") or ""),
            "total_credit_spread": str(bridge_summary.get("total_credit_spread") or ""),
            "total_explained_pnl": str(bridge_summary.get("total_explained_pnl") or ""),
            "total_actual_pnl": str(bridge_summary.get("total_actual_pnl") or ""),
            "total_residual": str(bridge_summary.get("total_residual") or ""),
            "quality_flag": str(bridge_summary.get("quality_flag") or ""),
            "warnings": [str(item) for item in list(bridge_result.get("warnings") or [])],
        }
    except Exception as exc:
        warnings.append(
            f"advanced_attribution_bundle: pnl_bridge summary unavailable: {exc}"
        )

    return summaries, warnings
