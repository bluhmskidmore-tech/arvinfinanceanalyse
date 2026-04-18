"""W5.5 migration tests for ``liability_analytics`` Numeric schema upgrades."""
from __future__ import annotations

from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.liability_analytics import (
    LiabilitiesMonthlyPayload,
    LiabilityCounterpartyPayload,
    LiabilityMonthlyBreakdownRow,
    LiabilityNameAmountItem,
    LiabilityRiskBucketsPayload,
    LiabilityYieldKpi,
    LiabilityYieldMetricsPayload,
)


class TestLiabilityRiskBucketsNumericMigration:
    def test_name_amount_item_accepts_legacy_float(self) -> None:
        item = LiabilityNameAmountItem(name="Interbank", amount=1000000.0, amount_yi=0.01)
        assert isinstance(item.amount, Numeric)
        assert item.amount.unit == "yuan"
        assert item.amount_yi is not None
        assert item.amount_yi.unit == "yi"

    def test_payload_roundtrip(self) -> None:
        payload = LiabilityRiskBucketsPayload(
            report_date="2026-01-31",
            liabilities_structure=[{"name": "Interbank", "amount": 1000000.0, "amount_yi": 0.01}],
            liabilities_term_buckets=[{"bucket": "0-3M", "amount": 1000000.0, "amount_yi": 0.01}],
        )
        dumped = payload.model_dump(mode="json")
        assert isinstance(dumped["liabilities_structure"][0]["amount"], dict)
        restored = LiabilityRiskBucketsPayload.model_validate(dumped)
        assert restored.liabilities_term_buckets[0].amount_yi is not None


class TestLiabilityYieldNumericMigration:
    def test_kpi_accepts_legacy_float(self) -> None:
        kpi = LiabilityYieldKpi(
            asset_yield=0.031,
            liability_cost=0.018,
            market_liability_cost=0.02,
            nim=0.011,
        )
        assert isinstance(kpi.asset_yield, Numeric)
        assert kpi.nim.unit == "pct"

    def test_payload_accepts_native_numeric(self) -> None:
        payload = LiabilityYieldMetricsPayload(
            report_date="2026-01-31",
            kpi=LiabilityYieldKpi(
                asset_yield=Numeric(raw=0.031, unit="pct", display="+0.03", precision=2, sign_aware=True),
                liability_cost=Numeric(raw=0.018, unit="pct", display="+0.02", precision=2, sign_aware=True),
                market_liability_cost=None,
                nim=Numeric(raw=0.011, unit="pct", display="+0.01", precision=2, sign_aware=True),
            ),
        )
        assert payload.kpi.liability_cost is not None
        assert payload.kpi.liability_cost.raw == 0.018


class TestLiabilityCounterpartyNumericMigration:
    def test_payload_accepts_legacy_float_nested_items(self) -> None:
        payload = LiabilityCounterpartyPayload(
            report_date="2026-01-31",
            total_value=1200000.0,
            top_10=[{"name": "Bank A", "value": 1000000.0, "type": "Bank", "weighted_cost": 0.025}],
            by_type=[{"name": "Bank", "value": 1000000.0}],
        )
        assert isinstance(payload.total_value, Numeric)
        assert payload.top_10[0].value is not None
        assert payload.top_10[0].value.unit == "yuan"
        assert payload.top_10[0].weighted_cost is not None
        assert payload.top_10[0].weighted_cost.unit == "pct"

    def test_roundtrip(self) -> None:
        payload = LiabilityCounterpartyPayload(
            report_date="2026-01-31",
            total_value=1200000.0,
            top_10=[{"name": "Bank A", "value": 1000000.0, "type": "Bank", "weighted_cost": 0.025}],
            by_type=[{"name": "Bank", "value": 1000000.0}],
        )
        dumped = payload.model_dump(mode="json")
        assert isinstance(dumped["top_10"][0]["value"], dict)
        restored = LiabilityCounterpartyPayload.model_validate(dumped)
        assert restored.by_type[0].value is not None


class TestLiabilitiesMonthlyNumericMigration:
    def test_month_rows_accept_legacy_float(self) -> None:
        payload = LiabilitiesMonthlyPayload(
            year=2026,
            months=[
                {
                    "month": "2026-01",
                    "month_label": "2026-01",
                    "avg_total_liabilities": 1000000.0,
                    "avg_interbank_liabilities": 400000.0,
                    "avg_issued_liabilities": 600000.0,
                    "avg_liability_cost": 0.018,
                    "mom_change": 50000.0,
                    "mom_change_pct": 5.0,
                    "counterparty_top10": [
                        {
                            "name": "Bank A",
                            "avg_value": 300000.0,
                            "proportion": 30.0,
                            "amount": 300000.0,
                            "pct": 30.0,
                            "weighted_cost": 0.025,
                            "type": "Bank",
                        }
                    ],
                    "by_institution_type": [],
                    "structure_overview": [],
                    "term_buckets": [],
                    "interbank_by_type": [],
                    "interbank_term_buckets": [],
                    "issued_by_type": [],
                    "issued_term_buckets": [],
                    "counterparty_details": [],
                    "num_days": 31,
                }
            ],
            ytd_avg_total_liabilities=1000000.0,
            ytd_avg_liability_cost=0.018,
        )
        month = payload.months[0]
        assert month.avg_total_liabilities is not None
        assert month.avg_total_liabilities.unit == "yuan"
        assert month.counterparty_top10[0].weighted_cost is not None
        assert month.counterparty_top10[0].weighted_cost.unit == "pct"

    def test_breakdown_row_accepts_native_numeric(self) -> None:
        row = LiabilityMonthlyBreakdownRow(
            name="Bank A",
            avg_value=Numeric(raw=300000.0, unit="yuan", display="300,000.00", precision=2, sign_aware=False),
            proportion=Numeric(raw=30.0, unit="pct", display="30.00", precision=2, sign_aware=False),
            amount=Numeric(raw=300000.0, unit="yuan", display="300,000.00", precision=2, sign_aware=False),
            pct=Numeric(raw=30.0, unit="pct", display="30.00", precision=2, sign_aware=False),
            weighted_cost=Numeric(raw=0.025, unit="pct", display="+0.03", precision=2, sign_aware=True),
        )
        assert row.avg_value is not None
        assert row.avg_value.raw == 300000.0
