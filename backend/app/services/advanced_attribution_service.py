from __future__ import annotations

from backend.app.schemas.advanced_attribution import AdvancedAttributionBundlePayload
from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
)

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


def advanced_attribution_bundle_envelope(*, report_date: str) -> dict[str, object]:
    """Slice A/B: analytical contract + structured not_ready; no DuckDB reads; no formal writes."""
    payload = AdvancedAttributionBundlePayload(
        report_date=report_date,
        status="not_ready",
        missing_inputs=list(_NOT_READY_MISSING_INPUTS),
        blocked_components=list(_NOT_READY_BLOCKED_COMPONENTS),
        warnings=list(_NOT_READY_WARNINGS),
    )
    meta = build_analytical_result_meta(
        trace_id=f"tr_balance_analysis_advanced_attribution_{report_date}",
        result_kind=ADVANCED_ATTRIBUTION_RESULT_KIND,
        cache_version=CACHE_VERSION_ADVANCED_ATTRIBUTION,
        source_version=SOURCE_VERSION_NOT_READY,
        rule_version=RULE_VERSION_ADVANCED_ATTRIBUTION,
        formal_use_allowed=False,
        scenario_flag=False,
        quality_flag="warning",
    )
    return build_formal_result_envelope(
        result_meta=meta,
        result_payload=payload.model_dump(mode="json"),
    )
