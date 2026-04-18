"""W5.2 migration tests for ``cashflow_projection`` top-level Numeric fields."""
from __future__ import annotations

from datetime import date

from backend.app.schemas.cashflow_projection import CashflowProjectionResponse
from backend.app.schemas.common_numeric import Numeric


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
        assert payload.duration_gap.unit == "ratio"
        assert payload.rate_sensitivity_1bp.unit == "yuan"
        assert payload.asset_duration.sign_aware is False

    def test_accepts_native_numeric(self) -> None:
        payload = CashflowProjectionResponse(
            report_date=date(2026, 1, 1),
            duration_gap=Numeric(raw=2.0, unit="ratio", display="+2.00", precision=2, sign_aware=True),
            asset_duration=Numeric(raw=3.5, unit="ratio", display="3.50", precision=2, sign_aware=False),
            liability_duration=Numeric(raw=1.5, unit="ratio", display="1.50", precision=2, sign_aware=False),
            equity_duration=Numeric(raw=4.0, unit="ratio", display="+4.00", precision=2, sign_aware=True),
            rate_sensitivity_1bp=Numeric(raw=0.08, unit="yuan", display="+0.08", precision=2, sign_aware=True),
            reinvestment_risk_12m=Numeric(raw=0.25, unit="ratio", display="0.25", precision=2, sign_aware=False),
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
