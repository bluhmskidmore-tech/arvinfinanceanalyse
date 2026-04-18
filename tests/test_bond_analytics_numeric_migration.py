"""W5.1 migration tests for ``bond_analytics`` Numeric schema upgrades."""
from __future__ import annotations

from datetime import date

from backend.app.schemas.bond_analytics import (
    AccountingClassAuditItem,
    ActionAttributionResponse,
    ActionDetail,
    ActionTypeSummary,
    AssetClassBreakdown,
    BenchmarkExcessResponse,
    BondTopHoldingItem,
    BondTopHoldingsResponse,
    ConcentrationItem,
    ConcentrationMetrics,
    CreditSpreadMigrationResponse,
    ExcessSourceBreakdown,
    KRDBucket,
    KRDCurveRiskResponse,
    PortfolioHeadlinesResponse,
    ReturnDecompositionResponse,
    ScenarioResult,
    SpreadScenarioResult,
)
from backend.app.schemas.common_numeric import Numeric


class TestReturnDecompositionNumericMigration:
    def test_asset_class_breakdown_accepts_legacy_str(self) -> None:
        item = AssetClassBreakdown(
            asset_class="rates",
            carry="12.50",
            roll_down="2.10",
            rate_effect="-4.30",
            spread_effect="0",
            convexity_effect="0.20",
            trading="1.10",
            total="11.60",
            bond_count=3,
            market_value="1200.00",
        )
        assert isinstance(item.carry, Numeric)
        assert item.carry.unit == "yuan"
        assert item.market_value.sign_aware is False
        assert item.bond_count == 3

    def test_return_response_accepts_native_numeric(self) -> None:
        payload = ReturnDecompositionResponse(
            report_date=date(2026, 3, 31),
            period_type="MoM",
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            carry=Numeric(raw=12.5, unit="yuan", display="+12.50", precision=2, sign_aware=True),
            roll_down=Numeric(raw=2.1, unit="yuan", display="+2.10", precision=2, sign_aware=True),
            rate_effect=Numeric(raw=-4.3, unit="yuan", display="-4.30", precision=2, sign_aware=True),
            spread_effect=Numeric(raw=0.0, unit="yuan", display="+0.00", precision=2, sign_aware=True),
            trading=Numeric(raw=1.1, unit="yuan", display="+1.10", precision=2, sign_aware=True),
            explained_pnl=Numeric(raw=11.4, unit="yuan", display="+11.40", precision=2, sign_aware=True),
            actual_pnl=Numeric(raw=11.4, unit="yuan", display="+11.40", precision=2, sign_aware=True),
            recon_error=Numeric(raw=0.0, unit="yuan", display="+0.00", precision=2, sign_aware=True),
            recon_error_pct=Numeric(raw=0.0, unit="pct", display="+0.00", precision=2, sign_aware=True),
        )
        assert payload.carry.raw == 12.5
        assert payload.recon_error_pct.unit == "pct"

    def test_return_response_roundtrip(self) -> None:
        payload = ReturnDecompositionResponse(
            report_date=date(2026, 3, 31),
            period_type="MoM",
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            carry="12.50",
            roll_down="2.10",
            rate_effect="-4.30",
            spread_effect="0.00",
            trading="1.10",
            explained_pnl="11.40",
            actual_pnl="11.40",
            recon_error="0.00",
            recon_error_pct="0.00",
            total_market_value="1200.00",
        )
        dumped = payload.model_dump(mode="json")
        assert isinstance(dumped["carry"], dict)
        restored = ReturnDecompositionResponse.model_validate(dumped)
        assert restored.total_market_value.raw == 1200.0


class TestBenchmarkExcessNumericMigration:
    def test_breakdown_accepts_legacy_str(self) -> None:
        row = ExcessSourceBreakdown(source="duration", contribution="12.50", description="dv01 diff")
        assert isinstance(row.contribution, Numeric)
        assert row.contribution.unit == "bp"

    def test_response_accepts_native_numeric(self) -> None:
        resp = BenchmarkExcessResponse(
            report_date=date(2026, 3, 31),
            period_type="MoM",
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            benchmark_id="bm1",
            benchmark_name="BM",
            portfolio_return=Numeric(raw=0.034, unit="pct", display="+0.03", precision=2, sign_aware=True),
            benchmark_return=Numeric(raw=0.029, unit="pct", display="+0.03", precision=2, sign_aware=True),
            excess_return=Numeric(raw=5.0, unit="bp", display="+5.00", precision=2, sign_aware=True),
            explained_excess=Numeric(raw=5.0, unit="bp", display="+5.00", precision=2, sign_aware=True),
            recon_error=Numeric(raw=0.0, unit="bp", display="+0.00", precision=2, sign_aware=True),
            portfolio_duration=Numeric(raw=3.2, unit="ratio", display="3.20", precision=2, sign_aware=False),
            benchmark_duration=Numeric(raw=3.0, unit="ratio", display="3.00", precision=2, sign_aware=False),
            duration_diff=Numeric(raw=0.2, unit="ratio", display="+0.20", precision=2, sign_aware=True),
        )
        assert resp.excess_return.unit == "bp"
        assert resp.duration_diff.sign_aware is True

    def test_response_roundtrip(self) -> None:
        resp = BenchmarkExcessResponse(
            report_date=date(2026, 3, 31),
            period_type="MoM",
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            benchmark_id="bm1",
            benchmark_name="BM",
            portfolio_return="0.034",
            benchmark_return="0.029",
            excess_return="5.00",
            explained_excess="5.00",
            recon_error="0.00",
            portfolio_duration="3.20",
            benchmark_duration="3.00",
            duration_diff="0.20",
        )
        dumped = resp.model_dump(mode="json")
        assert isinstance(dumped["portfolio_return"], dict)
        restored = BenchmarkExcessResponse.model_validate(dumped)
        assert restored.portfolio_duration.unit == "ratio"


class TestKRDNumericMigration:
    def test_bucket_accepts_legacy_str(self) -> None:
        bucket = KRDBucket(tenor="5Y", krd="0.80", dv01="12.50", market_value_weight="0.40")
        assert isinstance(bucket.krd, Numeric)
        assert bucket.dv01.unit == "dv01"
        assert bucket.market_value_weight.sign_aware is False

    def test_response_accepts_native_numeric(self) -> None:
        resp = KRDCurveRiskResponse(
            report_date=date(2026, 3, 31),
            portfolio_duration=Numeric(raw=3.2, unit="ratio", display="3.20", precision=2, sign_aware=False),
            portfolio_modified_duration=Numeric(raw=3.1, unit="ratio", display="3.10", precision=2, sign_aware=False),
            portfolio_dv01=Numeric(raw=18.5, unit="dv01", display="18.50", precision=2, sign_aware=False),
            portfolio_convexity=Numeric(raw=0.22, unit="ratio", display="0.22", precision=2, sign_aware=False),
            krd_buckets=[KRDBucket(tenor="5Y", krd="0.80", dv01="12.50", market_value_weight="0.40")],
            scenarios=[
                ScenarioResult(
                    scenario_name="parallel_up",
                    scenario_description="+50bp",
                    shocks={"5Y": 50.0},
                    pnl_economic="-10.00",
                    pnl_oci="-2.00",
                    pnl_tpl="-8.00",
                    rate_contribution="-9.50",
                    convexity_contribution="-0.50",
                )
            ],
        )
        assert resp.portfolio_dv01.unit == "dv01"
        assert resp.scenarios[0].pnl_economic.unit == "yuan"

    def test_response_roundtrip(self) -> None:
        resp = KRDCurveRiskResponse(
            report_date=date(2026, 3, 31),
            portfolio_duration="3.20",
            portfolio_modified_duration="3.10",
            portfolio_dv01="18.50",
            portfolio_convexity="0.22",
        )
        dumped = resp.model_dump(mode="json")
        assert isinstance(dumped["portfolio_duration"], dict)
        restored = KRDCurveRiskResponse.model_validate(dumped)
        assert restored.portfolio_convexity.unit == "ratio"


class TestCreditSpreadNumericMigration:
    def test_spread_scenario_accepts_legacy_float_and_str(self) -> None:
        row = SpreadScenarioResult(
            scenario_name="+25bp",
            spread_change_bp=25.0,
            pnl_impact="-12.50",
            oci_impact="-2.50",
            tpl_impact="-10.00",
        )
        assert isinstance(row.spread_change_bp, Numeric)
        assert row.spread_change_bp.unit == "bp"
        assert row.pnl_impact.unit == "yuan"

    def test_concentration_item_accepts_native_numeric(self) -> None:
        item = ConcentrationItem(
            name="issuer-a",
            weight=Numeric(raw=0.2, unit="ratio", display="0.20", precision=2, sign_aware=False),
            market_value=Numeric(raw=100.0, unit="yuan", display="100.00", precision=2, sign_aware=False),
        )
        assert item.weight.raw == 0.2
        assert item.market_value.sign_aware is False

    def test_response_roundtrip(self) -> None:
        resp = CreditSpreadMigrationResponse(
            report_date=date(2026, 3, 31),
            credit_bond_count=10,
            credit_market_value="200.00",
            credit_weight="0.40",
            spread_dv01="15.20",
            weighted_avg_spread="120.00",
            weighted_avg_spread_duration="3.50",
            spread_scenarios=[
                SpreadScenarioResult(
                    scenario_name="+25bp",
                    spread_change_bp=25.0,
                    pnl_impact="-12.50",
                    oci_impact="-2.50",
                    tpl_impact="-10.00",
                )
            ],
            migration_scenarios=[],
            concentration_by_issuer=ConcentrationMetrics(
                dimension="issuer",
                hhi="0.23",
                top5_concentration="0.57",
                top_items=[ConcentrationItem(name="issuer-a", weight="0.20", market_value="100.00")],
            ),
        )
        dumped = resp.model_dump(mode="json")
        assert isinstance(dumped["credit_market_value"], dict)
        restored = CreditSpreadMigrationResponse.model_validate(dumped)
        assert restored.spread_dv01.unit == "dv01"


class TestActionAuditAndHeadlinesNumericMigration:
    def test_action_detail_accepts_legacy_str(self) -> None:
        detail = ActionDetail(
            action_id="a1",
            action_type="SWITCH",
            action_date="2026-03-15",
            bonds_involved=["B1"],
            description="rebalance",
            pnl_economic="12.50",
            pnl_accounting="11.00",
            delta_duration="-0.20",
            delta_dv01="-2.50",
            delta_spread_dv01="-1.20",
            opportunity_cost="-0.80",
        )
        assert isinstance(detail.pnl_economic, Numeric)
        assert detail.delta_dv01.unit == "dv01"
        assert detail.opportunity_cost is not None

    def test_action_response_roundtrip(self) -> None:
        resp = ActionAttributionResponse(
            report_date=date(2026, 3, 31),
            period_type="MoM",
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            total_actions=1,
            total_pnl_from_actions="11.00",
            by_action_type=[
                ActionTypeSummary(
                    action_type="SWITCH",
                    action_type_name="Switch",
                    action_count=1,
                    total_pnl_economic="12.50",
                    total_pnl_accounting="11.00",
                    avg_pnl_per_action="11.00",
                )
            ],
            action_details=[],
            period_start_duration="3.20",
            period_end_duration="3.00",
            duration_change_from_actions="-0.20",
            period_start_dv01="15.20",
            period_end_dv01="12.70",
        )
        dumped = resp.model_dump(mode="json")
        assert isinstance(dumped["total_pnl_from_actions"], dict)
        restored = ActionAttributionResponse.model_validate(dumped)
        assert restored.period_start_duration.unit == "ratio"

    def test_audit_headlines_and_top_holdings_accept_legacy_str(self) -> None:
        audit = AccountingClassAuditItem(
            asset_class="credit",
            position_count=2,
            market_value="100.00",
            market_value_weight="0.20",
            infer_accounting_class="FVOCI",
            map_accounting_class="FVOCI",
            infer_rule_id="r1",
            map_rule_id="r2",
        )
        headlines = PortfolioHeadlinesResponse(
            report_date=date(2026, 3, 31),
            total_market_value="500.00",
            weighted_ytm="2.80",
            weighted_duration="3.20",
            weighted_coupon="2.60",
            total_dv01="15.20",
            bond_count=8,
            credit_weight="0.40",
            issuer_hhi="0.23",
            issuer_top5_weight="0.57",
        )
        top = BondTopHoldingsResponse(
            report_date=date(2026, 3, 31),
            top_n=10,
            items=[
                BondTopHoldingItem(
                    instrument_code="B1",
                    asset_class="credit",
                    market_value="100.00",
                    face_value="100.00",
                    ytm="2.90",
                    modified_duration="3.10",
                    weight="0.20",
                )
            ],
            total_market_value="500.00",
        )
        assert isinstance(audit.market_value, Numeric)
        assert headlines.total_dv01.unit == "dv01"
        assert top.items[0].weight.sign_aware is False
