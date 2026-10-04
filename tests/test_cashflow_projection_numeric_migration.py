"""W5.2 migration tests for ``cashflow_projection`` top-level Numeric fields."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.schemas.cashflow_projection import CashflowProjectionResponse
from backend.app.schemas.common_numeric import Numeric, numeric_from_raw


class TestCashflowProjectionNumericMigration:
    def test_accepts_legacy_str_summary_fields(self) -> None:
        payload = CashflowProjectionResponse(
            report_date=date(2026, 1, 1),
            duration_gap="2.00000000",
            asset_duration="3.50000000",
            liability_duration="1.50000000",
            equity_duration="4.00000000",
            rate_sensitivity_1bp="0.08000000",
            reinvestment_risk_12m="0.25000000",
            monthly_buckets=[],
            top_maturing_assets_12m=[],
            computed_at="2026-01-01T00:00:00Z",
        )
        assert isinstance(payload.duration_gap, Numeric)
        assert payload.duration_gap.unit == "years"
        assert payload.asset_duration.unit == "years"
        assert payload.liability_duration.unit == "years"
        assert payload.equity_duration.unit == "years"
        assert payload.rate_sensitivity_1bp.unit == "yuan"
        assert payload.reinvestment_risk_12m.unit == "pct"
        assert payload.reinvestment_risk_12m.raw == 0.25
        assert payload.reinvestment_risk_12m.display == "25.00%"
        assert payload.asset_duration.sign_aware is False

    def test_accepts_native_numeric(self) -> None:
        payload = CashflowProjectionResponse(
            report_date=date(2026, 1, 1),
            duration_gap=Numeric(raw=2.0, unit="years", display="+2.00", precision=2, sign_aware=True),
            asset_duration=Numeric(raw=3.5, unit="years", display="3.50", precision=2, sign_aware=False),
            liability_duration=Numeric(raw=1.5, unit="years", display="1.50", precision=2, sign_aware=False),
            equity_duration=Numeric(raw=4.0, unit="years", display="+4.00", precision=2, sign_aware=True),
            rate_sensitivity_1bp=Numeric(raw=0.08, unit="yuan", display="+0.08", precision=2, sign_aware=True),
            reinvestment_risk_12m=Numeric(raw=0.25, unit="pct", display="25.00%", precision=2, sign_aware=False),
            monthly_buckets=[],
            top_maturing_assets_12m=[],
            computed_at="2026-01-01T00:00:00Z",
        )
        assert payload.duration_gap.raw == 2.0
        assert payload.equity_duration.sign_aware is True

    def test_roundtrip(self) -> None:
        payload = CashflowProjectionResponse(
            report_date=date(2026, 1, 1),
            duration_gap="2.00000000",
            asset_duration="3.50000000",
            liability_duration="1.50000000",
            equity_duration="4.00000000",
            rate_sensitivity_1bp="0.08000000",
            reinvestment_risk_12m="0.25000000",
            monthly_buckets=[],
            top_maturing_assets_12m=[],
            computed_at="2026-01-01T00:00:00Z",
        )
        dumped = payload.model_dump(mode="json")
        assert isinstance(dumped["duration_gap"], dict)
        restored = CashflowProjectionResponse.model_validate(dumped)
        assert restored.reinvestment_risk_12m.raw == 0.25

    def test_roundtrip_preserves_raw_text_for_nested_numeric_payloads(self) -> None:
        payload = CashflowProjectionResponse.model_validate(
            {
                "report_date": date(2026, 1, 1),
                "duration_gap": numeric_from_raw(
                    raw=Decimal("0.05000001"),
                    unit="years",
                    sign_aware=True,
                ).model_dump(mode="json"),
                "asset_duration": numeric_from_raw(
                    raw=Decimal("3.50000001"),
                    unit="years",
                    sign_aware=False,
                ).model_dump(mode="json"),
                "liability_duration": numeric_from_raw(
                    raw=Decimal("1.50000001"),
                    unit="years",
                    sign_aware=False,
                ).model_dump(mode="json"),
                "equity_duration": numeric_from_raw(
                    raw=Decimal("-2.00000001"),
                    unit="years",
                    sign_aware=True,
                ).model_dump(mode="json"),
                "rate_sensitivity_1bp": numeric_from_raw(
                    raw=Decimal("-0.01000001"),
                    unit="yuan",
                    sign_aware=True,
                ).model_dump(mode="json"),
                "reinvestment_risk_12m": numeric_from_raw(
                    raw=Decimal("1.25000001"),
                    unit="pct",
                    sign_aware=False,
                    raw_scale="ratio",
                ).model_dump(mode="json"),
                "floating_rate_proxy_market_value": numeric_from_raw(
                    raw=Decimal("1.00000001"),
                    unit="yuan",
                    sign_aware=False,
                ).model_dump(mode="json"),
                "payment_frequency_fallback_market_value": numeric_from_raw(
                    raw=Decimal("2.00000002"),
                    unit="yuan",
                    sign_aware=False,
                ).model_dump(mode="json"),
                "bullet_value_date_fallback_market_value": numeric_from_raw(
                    raw=Decimal("3.00000003"),
                    unit="yuan",
                    sign_aware=False,
                ).model_dump(mode="json"),
                "monthly_buckets": [
                    {
                        "year_month": "2026-01",
                        "asset_inflow": numeric_from_raw(
                            raw=Decimal("100.00000001"),
                            unit="yuan",
                            sign_aware=False,
                        ).model_dump(mode="json"),
                        "liability_outflow": numeric_from_raw(
                            raw=Decimal("100.00000002"),
                            unit="yuan",
                            sign_aware=False,
                        ).model_dump(mode="json"),
                        "net_cashflow": numeric_from_raw(
                            raw=Decimal("-0.01000001"),
                            unit="yuan",
                            sign_aware=True,
                        ).model_dump(mode="json"),
                        "cumulative_net": numeric_from_raw(
                            raw=Decimal("-0.01000001"),
                            unit="yuan",
                            sign_aware=True,
                        ).model_dump(mode="json"),
                    }
                ],
                "top_maturing_assets_12m": [
                    {
                        "instrument_code": "CF-BOND-001",
                        "instrument_name": "Cashflow Bond",
                        "maturity_date": "2026-06-01",
                        "face_value": numeric_from_raw(
                            raw=Decimal("100.00000001"),
                            unit="yuan",
                            sign_aware=False,
                        ).model_dump(mode="json"),
                        "market_value": numeric_from_raw(
                            raw=Decimal("99.99999999"),
                            unit="yuan",
                            sign_aware=False,
                        ).model_dump(mode="json"),
                        "currency_code": "CNY",
                    }
                ],
                "computed_at": "2026-01-01T00:00:00Z",
            }
        )

        dumped = payload.model_dump(mode="json")

        assert dumped["duration_gap"]["raw_text"] == "0.05000001"
        assert dumped["reinvestment_risk_12m"]["raw"] == 1.25000001
        assert dumped["reinvestment_risk_12m"]["raw_text"] == "1.25000001"
        assert dumped["reinvestment_risk_12m"]["display"] == "125.00%"
        assert dumped["floating_rate_proxy_market_value"]["raw_text"] == "1.00000001"
        assert dumped["payment_frequency_fallback_market_value"]["raw_text"] == "2.00000002"
        assert dumped["bullet_value_date_fallback_market_value"]["raw_text"] == "3.00000003"
        assert dumped["monthly_buckets"][0]["net_cashflow"]["raw_text"] == "-0.01000001"
        assert dumped["top_maturing_assets_12m"][0]["face_value"]["raw_text"] == "100.00000001"
