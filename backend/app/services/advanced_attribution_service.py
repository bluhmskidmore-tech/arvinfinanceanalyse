from __future__ import annotations

from datetime import date

import duckdb
from backend.app.schemas.advanced_attribution import AdvancedAttributionBundlePayload
from backend.app.schemas.common_numeric import Numeric
from backend.app.services.bond_analytics_service import get_return_decomposition
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
    build_scenario_result_meta,
)
from backend.app.services.pnl_bridge_service import pnl_bridge_envelope

ADVANCED_ATTRIBUTION_RESULT_KIND = "balance-analysis.advanced_attribution_bundle"
RULE_VERSION_ADVANCED_ATTRIBUTION = "rv_advanced_attribution_bundle_v1"
SOURCE_VERSION_NOT_READY = "sv_advanced_attribution_not_ready"
CACHE_VERSION_ADVANCED_ATTRIBUTION = "cv_advanced_attribution_v1"

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
_PARTIAL_WARNINGS: tuple[str, ...] = (
    "bond_analytics.phase3: realized_trading / action_attribution require trade-level history",
)


def _build_partial_summary(
    upstream_summaries: dict[str, dict[str, str | list[str]]],
) -> tuple[dict[str, str], list[str]]:
    return_summary = upstream_summaries.get("return_decomposition", {})
    bridge_summary = upstream_summaries.get("pnl_bridge", {})

    summary: dict[str, str] = {}
    if str(return_summary.get("carry") or "").strip():
        summary["carry"] = str(return_summary["carry"])
    if str(return_summary.get("roll_down") or "").strip():
        summary["roll_down"] = str(return_summary["roll_down"])
    if str(return_summary.get("rate_effect") or "").strip():
        summary["rate_effect"] = str(return_summary["rate_effect"])
    if str(return_summary.get("spread_effect") or "").strip():
        summary["spread_effect"] = str(return_summary["spread_effect"])
    if str(return_summary.get("explained_pnl") or "").strip():
        summary["explained_pnl"] = str(return_summary["explained_pnl"])
    if str(bridge_summary.get("total_treasury_curve") or "").strip():
        summary["treasury_curve"] = str(bridge_summary["total_treasury_curve"])
    if str(bridge_summary.get("total_credit_spread") or "").strip():
        summary["credit_spread"] = str(bridge_summary["total_credit_spread"])
    if str(bridge_summary.get("total_actual_pnl") or "").strip():
        summary["actual_pnl"] = str(bridge_summary["total_actual_pnl"])
    if str(bridge_summary.get("total_residual") or "").strip():
        summary["residual"] = str(bridge_summary["total_residual"])
    for field, components in (
        ("roll_down_availability", ("roll_down",)),
        ("treasury_curve_availability", ("treasury_curve", "rate_effect")),
        ("credit_spread_availability", ("credit_spread", "spread_effect")),
    ):
        if bridge_summary.get(field) not in ("ok", "not_applicable"):
            for component in components:
                summary.pop(component, None)
    return summary, sorted(summary.keys())


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
    partial_summary, available_components = (
        ({}, [])
        if is_scenario
        else _build_partial_summary(upstream_summaries)
    )
    is_partial = bool(partial_summary)
    payload = AdvancedAttributionBundlePayload(
        report_date=report_date,
        mode="scenario" if is_scenario else "analytical",
        scenario_name=(scenario_name or "custom") if is_scenario else None,
        scenario_inputs=scenario_inputs,
        upstream_summaries=upstream_summaries,
        status="partial" if is_partial else "not_ready",
        summary=partial_summary,
        available_components=available_components,
        missing_inputs=list(_NOT_READY_MISSING_INPUTS),
        blocked_components=sorted((set(_NOT_READY_BLOCKED_COMPONENTS) | {"credit_spread"}) - set(available_components)),
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
                *(
                    [
                        "balance-analysis.advanced_attribution_bundle: partial analytical output assembled from governed return_decomposition and pnl_bridge summaries"
                    ]
                    if is_partial
                    else []
                ),
                *upstream_warnings,
                *(_PARTIAL_WARNINGS if is_partial else _NOT_READY_WARNINGS),
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
        source_surface="formal_balance",
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
        return_env = get_return_decomposition(report_date_value, "MoM", "all", "all", duckdb_path=duckdb_path, governance_dir=governance_dir)
        return_result = dict(return_env.get("result", {}))
        return_summary: dict[str, str | list[str]] = {
            "warnings": [str(item) for item in list(return_result.get("warnings") or [])],
        }
        for field in ("carry", "roll_down", "rate_effect", "spread_effect", "explained_pnl"):
            return_summary[field] = (return_result.get(field) or "") if return_result.get("bond_count") != 0 else ""
        summaries["return_decomposition"] = return_summary
    except (RuntimeError, ValueError, OSError, duckdb.Error) as exc:
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
        bridge_out: dict[str, str | list[str]] = {
            "quality_flag": str(bridge_summary.get("quality_flag") or ""),
            "warnings": [str(item) for item in list(bridge_result.get("warnings") or [])],
        }
        for field in ("total_carry", "total_roll_down", "total_treasury_curve", "total_credit_spread", "total_explained_pnl", "total_actual_pnl", "total_residual"):
            bridge_out[field] = _amount_text(bridge_summary.get(field)) if bridge_summary.get("row_count") != 0 else ""
        for field in ("roll_down_availability", "treasury_curve_availability", "credit_spread_availability"):
            if field in bridge_summary:
                bridge_out[field] = bridge_summary[field]["status"]
                if bridge_out[field] in ("partial", "unavailable"):
                    warnings.append(f"advanced_attribution_bundle: {field}={bridge_out[field]}; component blocked")
        summaries["pnl_bridge"] = bridge_out
    except (RuntimeError, ValueError, OSError, duckdb.Error) as exc:
        warnings.append(
            f"advanced_attribution_bundle: pnl_bridge summary unavailable: {exc}"
        )

    return summaries, warnings


def _amount_text(value: object) -> str:
    if value is None:
        return ""
    numeric = Numeric.model_validate(value)
    return "" if numeric.raw is None else numeric.raw_text or str(numeric.raw)
