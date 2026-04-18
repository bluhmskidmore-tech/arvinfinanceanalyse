"""W5.6 migration tests for ``risk_tensor`` Numeric schema upgrades."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.risk_tensor import PortfolioRiskTensor
from backend.app.schemas.common_numeric import Numeric
from backend.app.schemas.risk_tensor import RiskTensorPayload


class TestRiskTensorNumericMigration:
    def test_accepts_legacy_decimal(self) -> None:
        payload = RiskTensorPayload(
            report_date=date(2026, 3, 31),
            portfolio_dv01=Decimal("3.50000000"),
            krd_1y=Decimal("0.50000000"),
            krd_3y=Decimal("0.60000000"),
            krd_5y=Decimal("0.70000000"),
            krd_7y=Decimal("0.80000000"),
            krd_10y=Decimal("0.90000000"),
            krd_30y=Decimal("0.00000000"),
            cs01=Decimal("1.25000000"),
            portfolio_convexity=Decimal("0.22000000"),
            portfolio_modified_duration=Decimal("3.10000000"),
            issuer_concentration_hhi=Decimal("0.33000000"),
            issuer_top5_weight=Decimal("1.00000000"),
            asset_cashflow_30d=Decimal("14.00000000"),
            asset_cashflow_90d=Decimal("14.00000000"),
            liability_cashflow_30d=Decimal("0.00000000"),
            liability_cashflow_90d=Decimal("0.00000000"),
            liquidity_gap_30d=Decimal("14.00000000"),
            liquidity_gap_90d=Decimal("14.00000000"),
            liquidity_gap_30d_ratio=Decimal("0.03260000"),
            total_market_value=Decimal("429.00000000"),
            bond_count=3,
            quality_flag="ok",
            warnings=[],
        )
        assert isinstance(payload.portfolio_dv01, Numeric)
        assert payload.portfolio_dv01.unit == "dv01"
        assert payload.total_market_value.sign_aware is False

    def test_accepts_native_numeric(self) -> None:
        payload = RiskTensorPayload(
            report_date=date(2026, 3, 31),
            portfolio_dv01=Numeric(raw=3.5, unit="dv01", display="3.50", precision=2, sign_aware=False),
            krd_1y=Numeric(raw=0.5, unit="ratio", display="+0.50", precision=2, sign_aware=True),
            krd_3y=Numeric(raw=0.6, unit="ratio", display="+0.60", precision=2, sign_aware=True),
            krd_5y=Numeric(raw=0.7, unit="ratio", display="+0.70", precision=2, sign_aware=True),
            krd_7y=Numeric(raw=0.8, unit="ratio", display="+0.80", precision=2, sign_aware=True),
            krd_10y=Numeric(raw=0.9, unit="ratio", display="+0.90", precision=2, sign_aware=True),
            krd_30y=Numeric(raw=0.0, unit="ratio", display="+0.00", precision=2, sign_aware=True),
            cs01=Numeric(raw=1.25, unit="dv01", display="1.25", precision=2, sign_aware=False),
            portfolio_convexity=Numeric(raw=0.22, unit="ratio", display="0.22", precision=2, sign_aware=False),
            portfolio_modified_duration=Numeric(raw=3.1, unit="ratio", display="3.10", precision=2, sign_aware=False),
            issuer_concentration_hhi=Numeric(raw=0.33, unit="ratio", display="0.33", precision=2, sign_aware=False),
            issuer_top5_weight=Numeric(raw=1.0, unit="ratio", display="1.00", precision=2, sign_aware=False),
            asset_cashflow_30d=Numeric(raw=14.0, unit="yuan", display="14.00", precision=2, sign_aware=False),
            asset_cashflow_90d=Numeric(raw=14.0, unit="yuan", display="14.00", precision=2, sign_aware=False),
            liability_cashflow_30d=Numeric(raw=0.0, unit="yuan", display="0.00", precision=2, sign_aware=False),
            liability_cashflow_90d=Numeric(raw=0.0, unit="yuan", display="0.00", precision=2, sign_aware=False),
            liquidity_gap_30d=Numeric(raw=14.0, unit="yuan", display="+14.00", precision=2, sign_aware=True),
            liquidity_gap_90d=Numeric(raw=14.0, unit="yuan", display="+14.00", precision=2, sign_aware=True),
            liquidity_gap_30d_ratio=Numeric(raw=0.0326, unit="ratio", display="+0.03", precision=2, sign_aware=True),
            total_market_value=Numeric(raw=429.0, unit="yuan", display="429.00", precision=2, sign_aware=False),
            bond_count=3,
            quality_flag="ok",
            warnings=[],
        )
        assert payload.cs01.raw == 1.25
        assert payload.krd_1y.sign_aware is True

    def test_roundtrip_and_from_tensor(self) -> None:
        payload = RiskTensorPayload(
            report_date=date(2026, 3, 31),
            portfolio_dv01=Decimal("3.50000000"),
            krd_1y=Decimal("0.50000000"),
            krd_3y=Decimal("0.60000000"),
            krd_5y=Decimal("0.70000000"),
            krd_7y=Decimal("0.80000000"),
            krd_10y=Decimal("0.90000000"),
            krd_30y=Decimal("0.00000000"),
            cs01=Decimal("1.25000000"),
            portfolio_convexity=Decimal("0.22000000"),
            portfolio_modified_duration=Decimal("3.10000000"),
            issuer_concentration_hhi=Decimal("0.33000000"),
            issuer_top5_weight=Decimal("1.00000000"),
            asset_cashflow_30d=Decimal("14.00000000"),
            asset_cashflow_90d=Decimal("14.00000000"),
            liability_cashflow_30d=Decimal("0.00000000"),
            liability_cashflow_90d=Decimal("0.00000000"),
            liquidity_gap_30d=Decimal("14.00000000"),
            liquidity_gap_90d=Decimal("14.00000000"),
            liquidity_gap_30d_ratio=Decimal("0.03260000"),
            total_market_value=Decimal("429.00000000"),
            bond_count=3,
            quality_flag="ok",
            warnings=[],
        )
        dumped = payload.model_dump(mode="json")
        assert isinstance(dumped["portfolio_dv01"], dict)
        restored = RiskTensorPayload.model_validate(dumped)
        assert restored.total_market_value.raw == 429.0

        tensor = PortfolioRiskTensor(
            report_date=date(2026, 3, 31),
            portfolio_dv01=Decimal("3.50000000"),
            krd_1y=Decimal("0.50000000"),
            krd_3y=Decimal("0.60000000"),
            krd_5y=Decimal("0.70000000"),
            krd_7y=Decimal("0.80000000"),
            krd_10y=Decimal("0.90000000"),
            krd_30y=Decimal("0.00000000"),
            cs01=Decimal("1.25000000"),
            portfolio_convexity=Decimal("0.22000000"),
            portfolio_modified_duration=Decimal("3.10000000"),
            issuer_concentration_hhi=Decimal("0.33000000"),
            issuer_top5_weight=Decimal("1.00000000"),
            asset_cashflow_30d=Decimal("14.00000000"),
            asset_cashflow_90d=Decimal("14.00000000"),
            liability_cashflow_30d=Decimal("0.00000000"),
            liability_cashflow_90d=Decimal("0.00000000"),
            liquidity_gap_30d=Decimal("14.00000000"),
            liquidity_gap_90d=Decimal("14.00000000"),
            liquidity_gap_30d_ratio=Decimal("0.03260000"),
            total_market_value=Decimal("429.00000000"),
            bond_count=3,
            quality_flag="ok",
            warnings=(),
        )
        from_tensor = RiskTensorPayload.from_tensor(tensor)
        assert from_tensor.portfolio_dv01.raw == 3.5
