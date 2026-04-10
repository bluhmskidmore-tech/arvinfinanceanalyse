"""Bond analytics service — orchestration layer between API and core_finance."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from backend.app.core_finance.bond_analytics.common import (
    STANDARD_SCENARIOS,
    classify_asset_class,
    decimal_to_str,
    estimate_convexity,
    estimate_duration,
    estimate_modified_duration,
    get_accounting_rule_trace,
    get_tenor_bucket,
    infer_accounting_class,
    map_accounting_class,
    resolve_period,
    safe_decimal,
)
from backend.app.schemas.bond_analytics import (
    AccountingClassAuditItem,
    AccountingClassAuditResponse,
    ActionAttributionResponse,
    ActionDetail,
    ActionTypeSummary,
    AssetClassBreakdown,
    AssetClassRiskSummary,
    BenchmarkExcessResponse,
    BondLevelDecomposition,
    CreditSpreadMigrationResponse,
    ExcessSourceBreakdown,
    KRDBucket,
    KRDCurveRiskResponse,
    MigrationScenarioResult,
    ReturnDecompositionResponse,
    ScenarioResult,
    SpreadScenarioResult,
)
from backend.app.schemas.analysis_service import AnalysisQuery
from backend.app.schemas.result_meta import ResultMeta
from backend.app.governance.settings import get_settings
from backend.app.services.analysis_service import (
    UnifiedAnalysisService,
    build_default_analysis_service,
)


def _trace_id() -> str:
    return f"tr_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_meta(result_kind: str) -> ResultMeta:
    return ResultMeta(
        trace_id=_trace_id(),
        basis="formal",
        result_kind=result_kind,
        source_version="sv_bond_analytics_v1",
        rule_version="rv_bond_analytics_v1",
        cache_version="cv_none",
    )


# ---------------------------------------------------------------------------
# 1. Return Decomposition
# ---------------------------------------------------------------------------

def get_return_decomposition(
    report_date: date,
    period_type: str = "MoM",
    asset_class: str = "all",
    accounting_class: str = "all",
) -> dict:
    period_start, period_end = resolve_period(report_date, period_type)
    warnings: list[str] = ["DuckDB fact tables not yet populated — returning empty decomposition"]

    response = ReturnDecompositionResponse(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        carry="0",
        roll_down="0",
        rate_effect="0",
        spread_effect="0",
        trading="0",
        explained_pnl="0",
        actual_pnl="0",
        recon_error="0",
        recon_error_pct="0",
        computed_at=_now_iso(),
        warnings=warnings,
    )
    return {
        "result_meta": _build_meta("bond_analytics.return_decomposition").model_dump(mode="json"),
        "result": response.model_dump(mode="json"),
    }


# ---------------------------------------------------------------------------
# 2. Benchmark Excess
# ---------------------------------------------------------------------------

BENCHMARK_NAMES = {
    "TREASURY_INDEX": "中债国债总指数",
    "CDB_INDEX": "中债国开债总指数",
    "AAA_CREDIT_INDEX": "中债AAA信用债指数",
}


def get_benchmark_excess(
    report_date: date,
    period_type: str = "MoM",
    benchmark_id: str = "CDB_INDEX",
) -> dict:
    period_start, period_end = resolve_period(report_date, period_type)
    warnings: list[str] = ["DuckDB fact tables not yet populated — returning empty excess"]

    response = BenchmarkExcessResponse(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        benchmark_id=benchmark_id,
        benchmark_name=BENCHMARK_NAMES.get(benchmark_id, benchmark_id),
        portfolio_return="0",
        benchmark_return="0",
        excess_return="0",
        duration_effect="0",
        curve_effect="0",
        spread_effect="0",
        selection_effect="0",
        allocation_effect="0",
        explained_excess="0",
        recon_error="0",
        portfolio_duration="0",
        benchmark_duration="0",
        duration_diff="0",
        computed_at=_now_iso(),
        warnings=warnings,
    )
    return {
        "result_meta": _build_meta("bond_analytics.benchmark_excess").model_dump(mode="json"),
        "result": response.model_dump(mode="json"),
    }


# ---------------------------------------------------------------------------
# 3. KRD Curve Risk
# ---------------------------------------------------------------------------

def get_krd_curve_risk(
    report_date: date,
    scenario_set: str = "standard",
) -> dict:
    warnings: list[str] = ["DuckDB fact tables not yet populated — returning empty KRD"]

    scenarios = []
    for s in STANDARD_SCENARIOS:
        scenarios.append(
            ScenarioResult(
                scenario_name=s["name"],
                scenario_description=s["description"],
                shocks=s["shocks"],
                pnl_economic="0",
                pnl_oci="0",
                pnl_tpl="0",
                rate_contribution="0",
                convexity_contribution="0",
            )
        )

    response = KRDCurveRiskResponse(
        report_date=report_date,
        portfolio_duration="0",
        portfolio_modified_duration="0",
        portfolio_dv01="0",
        portfolio_convexity="0",
        scenarios=scenarios,
        computed_at=_now_iso(),
        warnings=warnings,
    )
    return {
        "result_meta": _build_meta("bond_analytics.krd_curve_risk").model_dump(mode="json"),
        "result": response.model_dump(mode="json"),
    }


# ---------------------------------------------------------------------------
# 4. Credit Spread Migration
# ---------------------------------------------------------------------------

def get_credit_spread_migration(
    report_date: date,
    spread_scenarios: str = "10,25,50",
) -> dict:
    warnings: list[str] = ["DuckDB fact tables not yet populated — returning empty spread"]

    bp_values = [int(x.strip()) for x in spread_scenarios.split(",") if x.strip()]
    spread_results = []
    for bp in bp_values:
        for sign, label in [(1, "走阔"), (-1, "收窄")]:
            spread_results.append(
                SpreadScenarioResult(
                    scenario_name=f"利差{label} {bp}bp",
                    spread_change_bp=float(sign * bp),
                    pnl_impact="0",
                    oci_impact="0",
                    tpl_impact="0",
                )
            )

    response = CreditSpreadMigrationResponse(
        report_date=report_date,
        credit_bond_count=0,
        credit_market_value="0",
        credit_weight="0",
        spread_dv01="0",
        weighted_avg_spread="0",
        weighted_avg_spread_duration="0",
        spread_scenarios=spread_results,
        oci_credit_exposure="0",
        oci_spread_dv01="0",
        oci_sensitivity_25bp="0",
        computed_at=_now_iso(),
        warnings=warnings,
    )
    return {
        "result_meta": _build_meta("bond_analytics.credit_spread_migration").model_dump(mode="json"),
        "result": response.model_dump(mode="json"),
    }


# ---------------------------------------------------------------------------
# 5. Legacy Action Attribution Placeholder
# ---------------------------------------------------------------------------

def _legacy_get_action_attribution(
    report_date: date,
    period_type: str = "MoM",
) -> dict:
    period_start, period_end = resolve_period(report_date, period_type)
    warnings: list[str] = ["DuckDB fact tables not yet populated — returning empty attribution"]

    response = ActionAttributionResponse(
        report_date=report_date,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        total_actions=0,
        total_pnl_from_actions="0",
        period_start_duration="0",
        period_end_duration="0",
        duration_change_from_actions="0",
        period_start_dv01="0",
        period_end_dv01="0",
        computed_at=_now_iso(),
        warnings=warnings,
    )
    return {
        "result_meta": _build_meta("bond_analytics.action_attribution").model_dump(mode="json"),
        "result": response.model_dump(mode="json"),
    }


# ---------------------------------------------------------------------------
# 6. Accounting Class Audit
# ---------------------------------------------------------------------------

def get_accounting_class_audit(
    report_date: date,
) -> dict:
    warnings: list[str] = ["DuckDB fact tables not yet populated — returning empty audit"]

    response = AccountingClassAuditResponse(
        report_date=report_date,
        computed_at=_now_iso(),
        warnings=warnings,
    )
    return {
        "result_meta": _build_meta("bond_analytics.accounting_class_audit").model_dump(mode="json"),
        "result": response.model_dump(mode="json"),
    }


def build_analysis_service() -> UnifiedAnalysisService:
    return build_default_analysis_service(
        duckdb_path=str(get_settings().duckdb_path)
    )


def get_action_attribution(
    report_date: date,
    period_type: str = "MoM",
) -> dict:
    analysis_envelope = build_analysis_service().execute(
        AnalysisQuery(
            consumer="bond_analytics.action_attribution",
            analysis_key="bond_action_attribution",
            report_date=report_date.isoformat(),
            basis="formal",
            view=period_type,
        )
    )
    summary = analysis_envelope.result.summary
    response = ActionAttributionResponse(
        report_date=report_date,
        period_type=str(summary["period_type"]),
        period_start=date.fromisoformat(str(summary["period_start"])),
        period_end=date.fromisoformat(str(summary["period_end"])),
        total_actions=int(summary["total_actions"]),
        total_pnl_from_actions=str(summary["total_pnl_from_actions"]),
        by_action_type=[
            ActionTypeSummary.model_validate(item)
            for item in analysis_envelope.result.facets.get("by_action_type", [])
        ],
        action_details=[
            ActionDetail.model_validate(item)
            for item in analysis_envelope.result.facets.get("action_details", [])
        ],
        period_start_duration=str(summary["period_start_duration"]),
        period_end_duration=str(summary["period_end_duration"]),
        duration_change_from_actions=str(summary["duration_change_from_actions"]),
        period_start_dv01=str(summary["period_start_dv01"]),
        period_end_dv01=str(summary["period_end_dv01"]),
        computed_at=str(
            summary.get("computed_at")
            or analysis_envelope.result_meta.generated_at.isoformat()
        ),
        warnings=[warning.message for warning in analysis_envelope.result.warnings],
    )
    return {
        "result_meta": analysis_envelope.result_meta.model_dump(mode="json"),
        "result": response.model_dump(mode="json"),
    }
