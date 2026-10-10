"""B-class ratio callers must declare pct raw scale explicitly (raw_scale="ratio").

Covers callers whose pct raw inputs are verified decimal ratios. Under the
legacy "auto" heuristic in ``backend.app.schemas.common_numeric``, a genuine
ratio above 1 (e.g. 1.5 == 150%) would be mis-divided by 100 and rendered as
"1.50%". Declaring ``raw_scale="ratio"`` removes that residual risk while
keeping in-contract values (<= 1) rendered exactly as before.

Sibling of ``tests/test_pct_raw_scale_migrated_callers.py`` (percent-point callers).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from backend.app.services.cashflow_projection_service import _ratio_pct_numeric_json
from backend.app.services.risk_scenario_stress_service import _liquidity_scenario


class TestCashflowReinvestmentRiskRatioNumeric:
    def test_ratio_below_one_unchanged(self) -> None:
        out = _ratio_pct_numeric_json(Decimal("0.4"))
        assert out["raw"] == pytest.approx(0.4)
        assert out["unit"] == "pct"
        assert out["display"] == "40.00%"

    def test_ratio_above_one_stays_ratio(self) -> None:
        # 1.5 means 150% of assets maturing within 12m — must not become 1.50%.
        out = _ratio_pct_numeric_json(Decimal("1.5"))
        assert out["raw"] == pytest.approx(1.5)
        assert out["display"] == "150.00%"

    def test_zero(self) -> None:
        out = _ratio_pct_numeric_json(Decimal("0"))
        assert out["raw"] == pytest.approx(0.0)
        assert out["display"] == "0.00%"

    def test_none_is_null_numeric(self) -> None:
        out = _ratio_pct_numeric_json(None)
        assert out["raw"] is None
        assert out["display"] == "—"


def _tensor_result(
    *,
    asset: float | None,
    liability: float | None,
    gap: float | None,
    market_value: float | None,
) -> dict[str, Any]:
    return {
        "asset_cashflow_30d": {"raw": asset},
        "liability_cashflow_30d": {"raw": liability},
        "liquidity_gap_30d": {"raw": gap},
        "total_market_value": {"raw": market_value},
    }


class TestRiskScenarioStressLiquidityRatios:
    def test_shock_pct_is_decimal_ratio(self) -> None:
        row = _liquidity_scenario(_tensor_result(asset=100.0, liability=50.0, gap=40.0, market_value=100.0))
        assert row["shock"]["raw"] == pytest.approx(0.10)
        assert row["shock"]["display"] == "+10.0%"

    def test_baseline_ratio_below_one_unchanged(self) -> None:
        row = _liquidity_scenario(_tensor_result(asset=100.0, liability=50.0, gap=40.0, market_value=100.0))
        assert row["baseline_ratio"]["raw"] == pytest.approx(0.4)
        assert row["baseline_ratio"]["display"] == "+40.0%"

    def test_baseline_ratio_above_one_stays_ratio(self) -> None:
        # A 30d gap of 150% of market value must render 150.0%, not 1.5%.
        row = _liquidity_scenario(_tensor_result(asset=100.0, liability=50.0, gap=150.0, market_value=100.0))
        assert row["baseline_ratio"]["raw"] == pytest.approx(1.5)
        assert row["baseline_ratio"]["display"] == "+150.0%"

    def test_stressed_ratio_above_one_stays_ratio(self) -> None:
        # stressed gap = 300 * 0.9 - 100 * 1.1 = 160 → ratio 1.6.
        row = _liquidity_scenario(_tensor_result(asset=300.0, liability=100.0, gap=100.0, market_value=100.0))
        assert row["stressed_ratio"]["raw"] == pytest.approx(1.6)
        assert row["stressed_ratio"]["display"] == "+160.0%"

    def test_zero_gap(self) -> None:
        row = _liquidity_scenario(_tensor_result(asset=100.0, liability=50.0, gap=0.0, market_value=100.0))
        assert row["baseline_ratio"]["raw"] == pytest.approx(0.0)
        assert row["baseline_ratio"]["display"] == "+0.0%"

    def test_missing_market_value_yields_null_ratios(self) -> None:
        row = _liquidity_scenario(_tensor_result(asset=100.0, liability=50.0, gap=40.0, market_value=None))
        assert row["baseline_ratio"]["raw"] is None
        assert row["baseline_ratio"]["display"] == "—"
        assert row["stressed_ratio"]["raw"] is None
