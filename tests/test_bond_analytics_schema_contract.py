from __future__ import annotations

from datetime import date

from backend.app.schemas.bond_analytics import (
    ACTION_TYPE_NAMES,
    AccountingClassAuditItem,
    AccountingClassAuditResponse,
    ActionAttributionResponse,
    ActionDetail,
    ActionTypeSummary,
    AssetClassBreakdown,
    AssetClassRiskSummary,
    BenchmarkExcessResponse,
    BondLevelDecomposition,
    ConcentrationItem,
    ConcentrationMetrics,
    CreditSpreadMigrationResponse,
    ExcessSourceBreakdown,
    KRDBucket,
    KRDCurveRiskResponse,
    MigrationScenarioResult,
    PeriodType,
    ReturnDecompositionResponse,
    ScenarioResult,
    SpreadScenarioResult,
)
from tests.helpers import load_module


def test_period_type_enum_values():
    assert PeriodType.MOM.value == "MoM"
    assert PeriodType.YTD.value == "YTD"
    assert PeriodType.TTM.value == "TTM"


def test_action_type_names_contains_core_keys():
    for key in ("ADD_DURATION", "REDUCE_DURATION", "SWITCH", "HEDGE"):
        assert key in ACTION_TYPE_NAMES


def test_asset_class_breakdown_defaults():
    schema_module = load_module(
        "backend.app.schemas.bond_analytics",
        "backend/app/schemas/bond_analytics.py",
    )
    row = schema_module.AssetClassBreakdown(asset_class="rate")
    assert row.carry == "0"
    assert row.roll_down == "0"
    assert row.convexity_effect == "0"
    assert row.bond_count == 0
    assert row.market_value == "0"


def test_bond_level_decomposition_defaults_and_optional():
    row = BondLevelDecomposition(
        bond_code="B1",
        asset_class="rate",
        accounting_class="AC",
        market_value="100",
    )
    assert row.carry == "0"
    assert row.convexity_effect == "0"
    assert row.bond_name is None


def test_return_decomposition_response_nested_defaults():
    d0 = date(2026, 3, 31)
    resp = ReturnDecompositionResponse(
        report_date=d0,
        period_type="MoM",
        period_start=d0,
        period_end=d0,
        carry="1",
        roll_down="2",
        rate_effect="3",
        spread_effect="4",
        trading="5",
        explained_pnl="15",
        actual_pnl="15",
        recon_error="0",
        recon_error_pct="0",
    )
    assert resp.fx_effect == "0"
    assert resp.convexity_effect == "0"
    assert resp.by_asset_class == []
    assert resp.bond_details == []
    assert resp.warnings == []


def test_benchmark_excess_response_defaults_and_nested():
    d0 = date(2026, 3, 31)
    resp = BenchmarkExcessResponse(
        report_date=d0,
        period_type="MoM",
        period_start=d0,
        period_end=d0,
        benchmark_id="b1",
        benchmark_name="B",
        portfolio_return="1",
        benchmark_return="0.5",
        excess_return="50",
        explained_excess="50",
        recon_error="0",
        portfolio_duration="3",
        benchmark_duration="3",
        duration_diff="0",
    )
    assert resp.duration_effect == "0"
    assert resp.excess_sources == []
    assert resp.warnings == []


def test_krd_curve_risk_nested_defaults():
    d0 = date(2026, 3, 31)
    krd = KRDBucket(tenor="1Y", krd="0.1", dv01="100", market_value_weight="0.2")
    scen = ScenarioResult(
        scenario_name="s",
        scenario_description="d",
        shocks={"1Y": 50.0},
        pnl_economic="1",
        pnl_oci="0",
        pnl_tpl="0",
        rate_contribution="1",
        convexity_contribution="0",
    )
    ac = AssetClassRiskSummary(
        asset_class="rate",
        market_value="100",
        duration="3",
        dv01="10",
        weight="0.5",
    )
    resp = KRDCurveRiskResponse(
        report_date=d0,
        portfolio_duration="3",
        portfolio_modified_duration="3",
        portfolio_dv01="10",
        portfolio_convexity="0",
        krd_buckets=[krd],
        scenarios=[scen],
        by_asset_class=[ac],
    )
    assert resp.krd_buckets[0].tenor == "1Y"
    assert resp.scenarios[0].by_asset_class == {}
    assert resp.warnings == []


def test_credit_spread_migration_defaults_and_nested():
    d0 = date(2026, 3, 31)
    spread = SpreadScenarioResult(
        scenario_name="+25bp",
        spread_change_bp=25.0,
        pnl_impact="1",
        oci_impact="0",
        tpl_impact="0",
    )
    mig = MigrationScenarioResult(
        scenario_name="down",
        from_rating="AA",
        to_rating="A",
        affected_bonds=2,
        affected_market_value="10",
        pnl_impact="0",
    )
    conc = ConcentrationMetrics(
        dimension="issuer",
        hhi="0.2",
        top5_concentration="0.4",
        top_items=[ConcentrationItem(name="I1", weight="0.2", market_value="10")],
    )
    resp = CreditSpreadMigrationResponse(
        report_date=d0,
        credit_bond_count=10,
        credit_market_value="100",
        credit_weight="0.5",
        spread_dv01="10",
        weighted_avg_spread="100",
        weighted_avg_spread_duration="4",
        spread_scenarios=[spread],
        migration_scenarios=[mig],
        concentration_by_issuer=conc,
    )
    assert resp.oci_credit_exposure == "0"
    assert resp.concentration_by_industry is None
    assert resp.warnings == []


def test_action_attribution_defaults_and_nested():
    d0 = date(2026, 3, 31)
    detail = ActionDetail(
        action_id="a1",
        action_type="SWITCH",
        action_date="2026-03-15",
        bonds_involved=["B1"],
        description="d",
        pnl_economic="1",
        pnl_accounting="1",
        delta_duration="0",
        delta_dv01="0",
        delta_spread_dv01="0",
    )
    summary = ActionTypeSummary(
        action_type="SWITCH",
        action_type_name="换券",
        action_count=1,
        total_pnl_economic="1",
        total_pnl_accounting="1",
        avg_pnl_per_action="1",
    )
    resp = ActionAttributionResponse(
        report_date=d0,
        period_type="MoM",
        period_start=d0,
        period_end=d0,
        total_actions=1,
        total_pnl_from_actions="1",
        by_action_type=[summary],
        action_details=[detail],
        period_start_duration="3",
        period_end_duration="3",
        duration_change_from_actions="0",
        period_start_dv01="10",
        period_end_dv01="10",
    )
    assert detail.opportunity_cost is None
    assert resp.warnings == []


def test_accounting_class_audit_defaults():
    d0 = date(2026, 3, 31)
    item = AccountingClassAuditItem(
        asset_class="rate",
        position_count=2,
        market_value="10",
        market_value_weight="0.2",
        infer_accounting_class="AC",
        map_accounting_class="AC",
        infer_rule_id="r1",
        map_rule_id="r2",
    )
    resp = AccountingClassAuditResponse(report_date=d0, rows=[item])
    assert resp.total_positions == 0
    assert resp.total_market_value == "0"
    assert item.is_divergent is False
    assert resp.warnings == []


def test_excess_source_breakdown_minimal():
    row = ExcessSourceBreakdown(source="duration", contribution="10", description="d")
    assert row.source == "duration"
