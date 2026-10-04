"""W5.3 migration tests for ``bond_dashboard`` Numeric schema upgrades."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.schemas.bond_dashboard import (
    BondDashboardAssetStructureItem,
    BondDashboardBusinessTypeMetricItem,
    BondDashboardHeadlineKpiBlock,
    BondDashboardHeadlinePayload,
    BondDashboardIndustryDistributionPayload,
    BondDashboardMaturityStructurePayload,
    BondDashboardPortfolioComparisonItem,
    BondDashboardRiskIndicatorsPayload,
    BondDashboardSpreadAnalysisItem,
    BondDashboardYieldDistributionPayload,
)
from backend.app.schemas.common_numeric import Numeric
from tests.helpers import load_module


class TestBondDashboardHeadlineNumericMigration:
    def test_large_decimal_market_value_serializes_lossless_raw_text(self) -> None:
        raw = Decimal("12345678901234567890.12345678")
        block = BondDashboardHeadlineKpiBlock(total_market_value=raw)

        dumped = block.model_dump(mode="json")

        assert dumped["total_market_value"]["raw_text"] == str(raw)

    def test_kpi_block_accepts_legacy_strings(self) -> None:
        block = BondDashboardHeadlineKpiBlock(
            total_market_value="100000000.00",
            unrealized_pnl="-1200000.00",
            weighted_ytm="0.02850000",
            weighted_duration="3.25000000",
            weighted_coupon="0.02600000",
            credit_spread_median="0.03100000",
            total_dv01="15000.00",
            bond_count=8,
        )
        assert isinstance(block.total_market_value, Numeric)
        assert block.total_market_value.unit == "yuan"
        assert block.unrealized_pnl.sign_aware is True
        assert block.weighted_duration.unit == "ratio"
        assert block.total_dv01.unit == "dv01"
        assert block.bond_count == 8

    def test_headline_payload_roundtrip(self) -> None:
        payload = BondDashboardHeadlinePayload(
            report_date="2026-03-31",
            prev_report_date="2026-03-30",
            kpis={
                "total_market_value": "100000000.00",
                "unrealized_pnl": "-1200000.00",
                "weighted_ytm": "0.02850000",
                "weighted_duration": "3.25000000",
                "weighted_coupon": "0.02600000",
                "credit_spread_median": "0.03100000",
                "total_dv01": "15000.00",
                "bond_count": 8,
            },
            prev_kpis={
                "total_market_value": "99000000.00",
                "unrealized_pnl": "-1000000.00",
                "weighted_ytm": "0.02800000",
                "weighted_duration": "3.20000000",
                "weighted_coupon": "0.02550000",
                "credit_spread_median": "0.03050000",
                "total_dv01": "14900.00",
                "bond_count": 8,
            },
        )
        dumped = payload.model_dump(mode="json")
        assert isinstance(dumped["kpis"]["total_market_value"], dict)
        restored = BondDashboardHeadlinePayload.model_validate(dumped)
        assert restored.prev_kpis is not None
        assert restored.prev_kpis.total_dv01.unit == "dv01"


class TestBondDashboardBreakdownNumericMigration:
    @pytest.mark.parametrize(
        ("raw_ytm", "legacy_pct"),
        [
            (None, ""),
            (Decimal("0"), "0.00000000"),
            (Decimal("0.0255"), "2.55000000"),
            (Decimal("-0.0255"), "-2.55000000"),
            (Decimal("0.02550000005"), "2.55000001"),
            (Decimal("-0.02550000005"), "-2.55000001"),
            (Decimal("0.025500000049999999999"), "2.55000000"),
        ],
    )
    def test_business_type_legacy_pct_preserves_decimal_precision_and_missing_values(
        self, monkeypatch, raw_ytm, legacy_pct,
    ) -> None:
        service = load_module(
            "tests._bond_dashboard_business_type_legacy_pct",
            "backend/app/services/bond_dashboard_service.py",
        )
        monkeypatch.setattr(
            service,
            "_repo",
            lambda: SimpleNamespace(fetch_business_type_metrics=lambda _rd: [{
                "name": "synthetic",
                "market_value": Decimal("100"),
                "weighted_avg_ytm": raw_ytm,
                "weighted_avg_duration": None,
            }]),
        )

        item = service._bond_dashboard_business_type_payload("2026-03-31")["items"][0]

        assert item["weighted_avg_ytm_pct"] == legacy_pct
        assert item["weighted_avg_ytm"]["unit"] == "pct"
        assert item["weighted_avg_ytm"]["raw"] == (None if raw_ytm is None else float(raw_ytm))
        if raw_ytm is None:
            assert item["weighted_avg_ytm"]["display"] == "—"
        elif raw_ytm == 0:
            assert item["weighted_avg_ytm"]["display"] == "+0.00%"

    def test_business_type_legacy_pct_is_required_and_deprecated(self) -> None:
        schema = BondDashboardBusinessTypeMetricItem.model_json_schema()

        assert "weighted_avg_ytm_pct" in schema["required"]
        assert schema["properties"]["weighted_avg_ytm_pct"]["type"] == "string"
        assert schema["properties"]["weighted_avg_ytm_pct"]["deprecated"] is True

    def test_business_type_missing_ytm_stays_missing_while_explicit_zero_is_preserved(self) -> None:
        missing = BondDashboardBusinessTypeMetricItem(
            name="未覆盖",
            market_value="100.00",
            weighted_avg_ytm_pct="",
            weighted_avg_duration="",
        )
        explicit_zero = BondDashboardBusinessTypeMetricItem(
            name="真实零",
            market_value="100.00",
            weighted_avg_ytm=0,
            weighted_avg_ytm_pct="0.00000000",
            weighted_avg_duration="0.00000000",
        )

        assert missing.weighted_avg_ytm.raw is None
        assert missing.weighted_avg_ytm.display == "—"
        assert missing.weighted_avg_ytm.unit == "pct"
        assert missing.model_dump()["weighted_avg_ytm_pct"] == ""
        assert explicit_zero.weighted_avg_ytm.raw == 0
        assert explicit_zero.weighted_avg_ytm.display == "+0.00%"
        assert explicit_zero.model_dump()["weighted_avg_ytm_pct"] == "0.00000000"

    def test_asset_and_spread_items_accept_legacy_strings(self) -> None:
        asset_item = BondDashboardAssetStructureItem(
            category="国债",
            total_market_value="120000000.00",
            bond_count=3,
            percentage="60.00",
        )
        spread_item = BondDashboardSpreadAnalysisItem(
            bond_type="信用债",
            median_yield="0.03200000",
            bond_count=2,
            total_market_value="80000000.00",
        )
        assert isinstance(asset_item.total_market_value, Numeric)
        assert asset_item.percentage is not None
        assert asset_item.percentage.unit == "pct"
        assert spread_item.median_yield is not None
        assert spread_item.median_yield.unit == "pct"

    def test_yield_maturity_and_industry_payload_roundtrip(self) -> None:
        yield_payload = BondDashboardYieldDistributionPayload(
            report_date="2026-03-31",
            items=[
                {
                    "yield_bucket": "2.5%-3.0%",
                    "total_market_value": "90000000.00",
                    "bond_count": 4,
                }
            ],
            weighted_ytm="0.02850000",
        )
        maturity_payload = BondDashboardMaturityStructurePayload(
            report_date="2026-03-31",
            items=[
                {
                    "maturity_bucket": "1-3年",
                    "total_market_value": "90000000.00",
                    "bond_count": 4,
                    "percentage": "45.00",
                }
            ],
            total_market_value="200000000.00",
        )
        industry_payload = BondDashboardIndustryDistributionPayload(
            report_date="2026-03-31",
            items=[
                {
                    "industry_name": "银行",
                    "total_market_value": "70000000.00",
                    "bond_count": 3,
                    "percentage": "35.00",
                }
            ],
        )

        dumped = {
            "yield": yield_payload.model_dump(mode="json"),
            "maturity": maturity_payload.model_dump(mode="json"),
            "industry": industry_payload.model_dump(mode="json"),
        }
        assert isinstance(dumped["yield"]["weighted_ytm"], dict)
        assert isinstance(dumped["maturity"]["items"][0]["percentage"], dict)
        assert isinstance(dumped["industry"]["items"][0]["total_market_value"], dict)


class TestBondDashboardPortfolioAndRiskNumericMigration:
    def test_portfolio_item_accepts_native_numeric(self) -> None:
        item = BondDashboardPortfolioComparisonItem(
            portfolio_name="book-a",
            total_market_value=Numeric(raw=120000000.0, unit="yuan", display="120,000,000.00", precision=2, sign_aware=False),
            weighted_ytm=Numeric(raw=0.0285, unit="pct", display="2.85%", precision=2, sign_aware=True),
            weighted_duration=Numeric(raw=3.25, unit="ratio", display="3.25 年", precision=2, sign_aware=False),
            total_dv01=Numeric(raw=15000.0, unit="dv01", display="15,000.00", precision=2, sign_aware=False),
            bond_count=8,
        )
        assert item.weighted_ytm.raw == 0.0285
        assert item.total_market_value.sign_aware is False

    def test_risk_payload_roundtrip(self) -> None:
        payload = BondDashboardRiskIndicatorsPayload(
            report_date="2026-03-31",
            total_market_value="200000000.00",
            total_dv01="15000.00",
            weighted_duration="3.25000000",
            credit_ratio="0.35000000",
            weighted_convexity="0.22000000",
            total_spread_dv01="4000.00",
            reinvestment_ratio_1y="0.18000000",
        )
        dumped = payload.model_dump(mode="json")
        assert isinstance(dumped["credit_ratio"], dict)
        restored = BondDashboardRiskIndicatorsPayload.model_validate(dumped)
        assert restored.total_spread_dv01.unit == "dv01"
        assert restored.credit_ratio.unit == "ratio"
