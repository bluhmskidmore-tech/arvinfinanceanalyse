"""W3.1 migration tests: all governed numeric fields now accept both legacy
float and new Numeric shapes; legacy floats are coerced to display-only Numerics.
"""
from __future__ import annotations

from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.pnl_attribution import (
    AdvancedAttributionSummary,
    CampisiAttributionItem,
    CampisiAttributionPayload,
    CarryRollDownItem,
    CarryRollDownPayload,
    KRDAttributionBucket,
    KRDAttributionPayload,
    PnlAttributionAnalysisSummary,
    PnlCompositionItem,
    PnlCompositionPayload,
    PnlCompositionTrendItem,
    SpreadAttributionItem,
    SpreadAttributionPayload,
    TPLMarketCorrelationPayload,
    TPLMarketDataPoint,
    VolumeRateAttributionItem,
    VolumeRateAttributionPayload,
)


class TestVolumeRateLegacyFloat:
    def test_item_accepts_legacy_float(self) -> None:
        item = VolumeRateAttributionItem(
            category="TPL",
            category_type="asset",
            level=1,
            current_scale=100.0,
            current_pnl=12.5,
            current_yield_pct=0.03,
            previous_scale=90.0,
            previous_pnl=10.0,
            previous_yield_pct=0.028,
            pnl_change=2.5,
            pnl_change_pct=0.25,
            volume_effect=1.0,
            rate_effect=1.5,
            interaction_effect=0.0,
            attrib_sum=2.5,
            recon_error=0.0,
            volume_contribution_pct=0.4,
            rate_contribution_pct=0.6,
        )
        assert isinstance(item.current_scale, Numeric)
        assert item.current_scale.raw == 100.0
        assert item.current_scale.unit == "yuan"
        assert item.current_scale.sign_aware is False
        assert isinstance(item.current_pnl, Numeric)
        assert item.current_pnl.sign_aware is True
        assert isinstance(item.current_yield_pct, Numeric)
        assert item.current_yield_pct.unit == "pct"

    def test_item_accepts_native_numeric(self) -> None:
        native = Numeric(raw=12.5, unit="yuan", display="+12.50 亿", precision=2, sign_aware=True)
        item = VolumeRateAttributionItem(
            category="TPL",
            category_type="asset",
            level=1,
            current_scale=100.0,
            current_pnl=native,
            current_yield_pct=None,
            previous_scale=None,
            previous_pnl=None,
            previous_yield_pct=None,
            pnl_change=None,
            pnl_change_pct=None,
            volume_effect=None,
            rate_effect=None,
            interaction_effect=None,
            attrib_sum=None,
            recon_error=None,
            volume_contribution_pct=None,
            rate_contribution_pct=None,
        )
        assert item.current_pnl.raw == 12.5
        assert item.current_pnl.display == "+12.50 亿"

    def test_item_null_optional_fields_stay_none(self) -> None:
        item = VolumeRateAttributionItem(
            category="TPL",
            category_type="asset",
            level=1,
            current_scale=100.0,
            current_pnl=12.5,
            current_yield_pct=None,
            previous_scale=None,
            previous_pnl=None,
            previous_yield_pct=None,
            pnl_change=None,
            pnl_change_pct=None,
            volume_effect=None,
            rate_effect=None,
            interaction_effect=None,
            attrib_sum=None,
            recon_error=None,
            volume_contribution_pct=None,
            rate_contribution_pct=None,
        )
        assert item.volume_effect is None
        assert item.recon_error is None

    def test_payload_accepts_legacy_float_totals(self) -> None:
        payload = VolumeRateAttributionPayload(
            current_period="202504",
            previous_period="202503",
            compare_type="mom",
            total_current_pnl=32.1,
            total_previous_pnl=30.0,
            total_pnl_change=2.1,
            total_volume_effect=1.0,
            total_rate_effect=1.1,
            total_interaction_effect=0.0,
            items=[],
            has_previous_data=True,
        )
        assert isinstance(payload.total_current_pnl, Numeric)
        assert payload.total_current_pnl.raw == 32.1


class TestTPLMarket:
    def test_accepts_legacy_float(self) -> None:
        point = TPLMarketDataPoint(
            period="202504",
            period_label="2025年04月",
            tpl_fair_value_change=1.2,
            tpl_total_pnl=3.4,
            tpl_scale=100.0,
            treasury_10y=2.55,
            treasury_10y_change=-0.05,
            dr007=1.8,
        )
        assert isinstance(point.tpl_fair_value_change, Numeric)
        assert isinstance(point.tpl_scale, Numeric)
        assert point.tpl_scale.sign_aware is False


class TestComposition:
    def test_item_accepts_legacy_float(self) -> None:
        item = PnlCompositionItem(
            category="TPL",
            category_type="asset",
            level=1,
            total_pnl=10.0,
            interest_income=5.0,
            fair_value_change=3.0,
            capital_gain=1.5,
            other_income=0.5,
            interest_pct=0.5,
            fair_value_pct=0.3,
            capital_gain_pct=0.15,
            other_pct=0.05,
        )
        assert isinstance(item.total_pnl, Numeric)
        assert item.total_pnl.sign_aware is True

    def test_payload_roundtrip(self) -> None:
        payload = PnlCompositionPayload(
            report_period="202504",
            report_date="2025-04-30",
            total_pnl=10.0,
            total_interest_income=5.0,
            total_fair_value_change=3.0,
            total_capital_gain=1.5,
            total_other_income=0.5,
            interest_pct=0.5,
            fair_value_pct=0.3,
            capital_gain_pct=0.15,
            other_pct=0.05,
            items=[],
            trend_data=[],
        )
        dumped = payload.model_dump(mode="json")
        assert isinstance(dumped["total_pnl"], dict)
        assert set(dumped["total_pnl"].keys()) == {"raw", "unit", "display", "precision", "sign_aware"}
        restored = PnlCompositionPayload.model_validate(dumped)
        assert restored.total_pnl.raw == 10.0


class TestCarryRollDown:
    def test_accepts_legacy_float(self) -> None:
        item = CarryRollDownItem(
            category="TPL",
            category_type="asset",
            market_value=100.0,
            weight=0.5,
            coupon_rate=0.03,
            ytm=0.032,
            funding_cost=0.018,
            carry=0.01,
            carry_pnl=1.0,
            duration=3.5,
            curve_slope=0.002,
            rolldown=0.005,
            rolldown_pnl=0.5,
            static_return=0.015,
            static_pnl=1.5,
        )
        assert isinstance(item.carry, Numeric)
        assert item.carry.unit == "pct"


class TestSpread:
    def test_accepts_legacy_float(self) -> None:
        item = SpreadAttributionItem(
            category="CD",
            category_type="asset",
            market_value=100.0,
            duration=3.0,
            weight=0.3,
            yield_change=-0.01,
            treasury_change=-0.005,
            spread_change=-0.005,
            treasury_effect=1.5,
            spread_effect=1.5,
            total_price_effect=3.0,
            treasury_contribution_pct=0.5,
            spread_contribution_pct=0.5,
        )
        assert isinstance(item.treasury_effect, Numeric)
        assert item.treasury_effect.sign_aware is True


class TestKRD:
    def test_bucket_accepts_legacy_float(self) -> None:
        b = KRDAttributionBucket(
            tenor="1Y",
            tenor_years=1.0,
            market_value=100.0,
            weight=0.3,
            bond_count=10,
            bucket_duration=0.9,
            krd=0.9,
            yield_change=-0.01,
            duration_contribution=0.9,
            contribution_pct=0.3,
        )
        assert isinstance(b.krd, Numeric)
        assert b.bond_count == 10  # int stays int


class TestCampisi:
    def test_accepts_legacy_float(self) -> None:
        item = CampisiAttributionItem(
            category="TPL",
            market_value=100.0,
            weight=0.5,
            total_return=5.0,
            total_return_pct=0.05,
            income_return=3.0,
            income_return_pct=0.03,
            treasury_effect=1.0,
            treasury_effect_pct=0.01,
            spread_effect=0.5,
            spread_effect_pct=0.005,
            selection_effect=0.5,
            selection_effect_pct=0.005,
        )
        assert isinstance(item.income_return, Numeric)
        assert item.income_return.sign_aware is True


class TestPnlAttributionAnalysisSummary:
    def test_primary_driver_pct_coerces(self) -> None:
        s = PnlAttributionAnalysisSummary(
            report_date="2025-04-30",
            primary_driver="volume",
            primary_driver_pct=0.4,
            key_findings=[],
            tpl_market_aligned=True,
            tpl_market_note="ok",
        )
        assert isinstance(s.primary_driver_pct, Numeric)


class TestAdvancedAttributionSummary:
    def test_all_fields_coerce(self) -> None:
        s = AdvancedAttributionSummary(
            report_date="2025-04-30",
            portfolio_carry=0.01,
            portfolio_rolldown=0.005,
            static_return_annualized=0.04,
            treasury_effect_total=1.5,
            spread_effect_total=1.5,
            spread_driver="narrowing",
            max_krd_tenor="5Y",
            curve_shape_change="flattening",
            key_insights=[],
        )
        assert isinstance(s.portfolio_carry, Numeric)
        assert isinstance(s.spread_effect_total, Numeric)
        assert s.spread_effect_total.unit == "yuan"


class TestPayloadRoundTrip:
    def test_carry_roll_down_payload_roundtrip(self) -> None:
        payload = CarryRollDownPayload(
            report_date="2025-04-30",
            total_market_value=100.0,
            portfolio_carry=0.01,
            portfolio_rolldown=0.005,
            portfolio_static_return=0.015,
            total_carry_pnl=1.0,
            total_rolldown_pnl=0.5,
            total_static_pnl=1.5,
            ftp_rate=0.018,
            items=[],
        )
        dumped = payload.model_dump(mode="json")
        restored = CarryRollDownPayload.model_validate(dumped)
        assert restored.portfolio_carry.raw == 0.01
        assert restored.portfolio_carry.unit == "pct"

    def test_krd_payload_roundtrip(self) -> None:
        payload = KRDAttributionPayload(
            report_date="2025-04-30",
            start_date="2025-04-01",
            end_date="2025-04-30",
            total_market_value=100.0,
            portfolio_duration=3.0,
            portfolio_dv01=1500000.0,
            total_duration_effect=2.0,
            curve_shift_type="parallel",
            curve_interpretation="...",
            buckets=[],
            max_contribution_tenor="5Y",
            max_contribution_value=1.5,
        )
        dumped = payload.model_dump(mode="json")
        restored = KRDAttributionPayload.model_validate(dumped)
        assert restored.portfolio_dv01.unit == "dv01"
        assert restored.portfolio_duration.unit == "ratio"
