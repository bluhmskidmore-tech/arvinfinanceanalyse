"""W5.4 migration tests for ``pnl_bridge`` Numeric schema upgrades."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.pnl_bridge import (
    PnlBridgePayload,
    PnlBridgeRowSchema,
    PnlBridgeSummarySchema,
)


class TestPnlBridgeNumericMigration:
    def test_row_accepts_legacy_decimal(self) -> None:
        row = PnlBridgeRowSchema(
            report_date=date(2025, 12, 31),
            instrument_code="240001.IB",
            portfolio_name="book-a",
            cost_center="cc-1",
            accounting_basis="FI",
            beginning_dirty_mv=Decimal("91.00000000"),
            ending_dirty_mv=Decimal("102.00000000"),
            carry=Decimal("12.50000000"),
            roll_down=Decimal("0"),
            treasury_curve=Decimal("0"),
            credit_spread=Decimal("0"),
            fx_translation=Decimal("0"),
            realized_trading=Decimal("1.75000000"),
            unrealized_fv=Decimal("-3.25000000"),
            manual_adjustment=Decimal("0.50000000"),
            explained_pnl=Decimal("11.50000000"),
            actual_pnl=Decimal("11.50000000"),
            residual=Decimal("0"),
            residual_ratio=Decimal("0.20"),
            quality_flag="ok",
            current_balance_found=True,
            prior_balance_found=True,
            balance_diagnostics=[],
        )
        assert isinstance(row.carry, Numeric)
        assert row.beginning_dirty_mv.unit == "yuan"
        assert row.residual_ratio.unit == "ratio"

    def test_summary_accepts_native_numeric(self) -> None:
        summary = PnlBridgeSummarySchema(
            row_count=1,
            ok_count=1,
            warning_count=0,
            error_count=0,
            total_beginning_dirty_mv=Numeric(raw=91.0, unit="yuan", display="91.00", precision=2, sign_aware=False),
            total_ending_dirty_mv=Numeric(raw=102.0, unit="yuan", display="102.00", precision=2, sign_aware=False),
            total_carry=Numeric(raw=12.5, unit="yuan", display="+12.50", precision=2, sign_aware=True),
            total_roll_down=Numeric(raw=0.0, unit="yuan", display="+0.00", precision=2, sign_aware=True),
            total_treasury_curve=Numeric(raw=0.0, unit="yuan", display="+0.00", precision=2, sign_aware=True),
            total_credit_spread=Numeric(raw=0.0, unit="yuan", display="+0.00", precision=2, sign_aware=True),
            total_fx_translation=Numeric(raw=0.0, unit="yuan", display="+0.00", precision=2, sign_aware=True),
            total_realized_trading=Numeric(raw=1.75, unit="yuan", display="+1.75", precision=2, sign_aware=True),
            total_unrealized_fv=Numeric(raw=-3.25, unit="yuan", display="-3.25", precision=2, sign_aware=True),
            total_manual_adjustment=Numeric(raw=0.5, unit="yuan", display="+0.50", precision=2, sign_aware=True),
            total_explained_pnl=Numeric(raw=11.5, unit="yuan", display="+11.50", precision=2, sign_aware=True),
            total_actual_pnl=Numeric(raw=11.5, unit="yuan", display="+11.50", precision=2, sign_aware=True),
            total_residual=Numeric(raw=0.0, unit="yuan", display="+0.00", precision=2, sign_aware=True),
            quality_flag="ok",
        )
        assert summary.total_carry.raw == 12.5
        assert summary.total_beginning_dirty_mv.sign_aware is False

    def test_payload_roundtrip(self) -> None:
        payload = PnlBridgePayload(
            report_date="2025-12-31",
            rows=[],
            summary=PnlBridgeSummarySchema(
                row_count=0,
                ok_count=0,
                warning_count=0,
                error_count=0,
                total_beginning_dirty_mv=Decimal("0"),
                total_ending_dirty_mv=Decimal("0"),
                total_carry=Decimal("0"),
                total_roll_down=Decimal("0"),
                total_treasury_curve=Decimal("0"),
                total_credit_spread=Decimal("0"),
                total_fx_translation=Decimal("0"),
                total_realized_trading=Decimal("0"),
                total_unrealized_fv=Decimal("0"),
                total_manual_adjustment=Decimal("0"),
                total_explained_pnl=Decimal("0"),
                total_actual_pnl=Decimal("0"),
                total_residual=Decimal("0"),
                quality_flag="ok",
            ),
            warnings=[],
        )
        dumped = payload.model_dump(mode="json")
        assert isinstance(dumped["summary"]["total_carry"], dict)
        restored = PnlBridgePayload.model_validate(dumped)
        assert restored.summary.total_residual.raw == 0.0
