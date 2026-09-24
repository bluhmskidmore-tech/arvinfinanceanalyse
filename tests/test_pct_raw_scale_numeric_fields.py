"""_NUMERIC_FIELDS promote paths must honor per-field pct ``raw_scale`` declarations.

Round-4 hardening: ``explicit_numeric.numeric_json`` and the schema-side
``_apply_numeric_coercion`` validators used to always ride the legacy
``abs(raw) > 1`` auto heuristic for ``unit="pct"`` fields. Migrated fields now
declare the producing raw scale via an optional third tuple element
``(unit, sign_aware, raw_scale)``; 2-tuples keep the legacy behavior.

Sibling of ``tests/test_pct_raw_scale_migrated_callers.py`` (percent-point
helpers) and ``tests/test_pct_raw_scale_ratio_callers.py`` (ratio helpers).
"""
from __future__ import annotations

from typing import Any, ClassVar

import pytest

from backend.app.schemas.cashflow_projection import CashflowProjectionResponse
from backend.app.schemas.liability_analytics import (
    LiabilitiesMonthlyPayload,
    LiabilityMonthlyBreakdownRow,
    LiabilityMonthlyItem,
    LiabilityYieldKpi,
)
from backend.app.services.explicit_numeric import numeric_json, promote_flat_payload
from backend.app.services.pnl_attribution_service import _promote_flat


class TestNumericJsonRawScale:
    def test_default_auto_keeps_legacy_heuristic(self) -> None:
        above_one = numeric_json(2.38, "pct", True)
        assert above_one["raw"] == pytest.approx(0.0238)
        assert above_one["display"] == "+2.38%"
        # Legacy ambiguity: sub-1 values are kept as ratio under "auto".
        sub_one = numeric_json(0.4, "pct", True)
        assert sub_one["raw"] == pytest.approx(0.4)
        assert sub_one["display"] == "+40.00%"

    def test_percent_scale_divides_sub_one_percent_points(self) -> None:
        out = numeric_json(0.85, "pct", True, "percent")
        assert out["raw"] == pytest.approx(0.0085)
        assert out["display"] == "+0.85%"

    def test_ratio_scale_keeps_values_above_one(self) -> None:
        out = numeric_json(1.5, "pct", False, "ratio")
        assert out["raw"] == pytest.approx(1.5)
        assert out["display"] == "150.00%"

    def test_none_is_null_numeric(self) -> None:
        out = numeric_json(None, "pct", True, "percent")
        assert out["raw"] is None
        assert out["display"] == "—"

    def test_raw_scale_is_ignored_for_non_pct_units(self) -> None:
        out = numeric_json(5, "yuan", True, "percent")
        assert out["raw"] == pytest.approx(5.0)


class _FieldSpecModel:
    """Minimal _NUMERIC_FIELDS carrier mixing 2-tuple and 3-tuple specs."""

    _NUMERIC_FIELDS: ClassVar[dict[str, Any]] = {
        "legacy_auto_pct": ("pct", True),
        "ratio_pct": ("pct", True, "ratio"),
        "percent_pct": ("pct", True, "percent"),
        "amount": ("yuan", False),
    }


class TestPromoteFlatPayloadFieldSpec:
    def test_two_tuple_keeps_auto_heuristic(self) -> None:
        out = promote_flat_payload({"legacy_auto_pct": 2.38}, _FieldSpecModel)
        assert out["legacy_auto_pct"]["raw"] == pytest.approx(0.0238)

    def test_three_tuple_ratio_keeps_values_above_one(self) -> None:
        out = promote_flat_payload({"ratio_pct": 1.5}, _FieldSpecModel)
        assert out["ratio_pct"]["raw"] == pytest.approx(1.5)
        assert out["ratio_pct"]["display"] == "+150.00%"

    def test_three_tuple_percent_divides_sub_one_values(self) -> None:
        out = promote_flat_payload({"percent_pct": 0.85}, _FieldSpecModel)
        assert out["percent_pct"]["raw"] == pytest.approx(0.0085)
        assert out["percent_pct"]["display"] == "+0.85%"

    def test_existing_numeric_json_passes_through(self) -> None:
        existing = numeric_json(1.5, "pct", True, "ratio")
        out = promote_flat_payload({"ratio_pct": existing}, _FieldSpecModel)
        assert out["ratio_pct"] is existing

    def test_non_pct_field_unaffected(self) -> None:
        out = promote_flat_payload({"amount": 1000.0}, _FieldSpecModel)
        assert out["amount"]["raw"] == pytest.approx(1000.0)
        assert out["amount"]["unit"] == "yuan"


class TestPnlAttributionPromoteFlatFieldSpec:
    """pnl_attribution keeps percent-point semantics for legacy 2-tuples; a
    3-tuple "ratio" declaration must route through the ratio-preserving path."""

    def test_two_tuple_pct_stays_percent_points(self) -> None:
        # Legacy behavior: 0.85 means 0.85 percent-points, divided to 0.0085.
        out = _promote_flat({"legacy_auto_pct": 0.85}, _FieldSpecModel)
        assert out["legacy_auto_pct"]["raw"] == pytest.approx(0.0085)
        assert out["legacy_auto_pct"]["display"] == "+0.85%"

    def test_three_tuple_ratio_keeps_values_above_one(self) -> None:
        out = _promote_flat({"ratio_pct": 1.5}, _FieldSpecModel)
        assert out["ratio_pct"]["raw"] == pytest.approx(1.5)
        assert out["ratio_pct"]["display"] == "+150.00%"

    def test_three_tuple_percent_divides_percent_points(self) -> None:
        out = _promote_flat({"percent_pct": 0.85}, _FieldSpecModel)
        assert out["percent_pct"]["raw"] == pytest.approx(0.0085)
        assert out["percent_pct"]["display"] == "+0.85%"

    def test_non_pct_field_unaffected(self) -> None:
        out = _promote_flat({"amount": 1000.0}, _FieldSpecModel)
        assert out["amount"]["raw"] == pytest.approx(1000.0)
        assert out["amount"]["unit"] == "yuan"


class TestLiabilityYieldKpiRatioScale:
    def test_ratio_above_one_is_not_rescaled(self) -> None:
        # A genuine 150% funding cost must not be auto-divided into 1.50%.
        kpi = LiabilityYieldKpi.model_validate({"asset_yield": 1.5})
        assert kpi.asset_yield is not None
        assert kpi.asset_yield.raw == pytest.approx(1.5)
        assert kpi.asset_yield.display == "+150.00%"

    def test_sub_one_ratio_unchanged(self) -> None:
        kpi = LiabilityYieldKpi.model_validate({"nim": 0.0185})
        assert kpi.nim is not None
        assert kpi.nim.raw == pytest.approx(0.0185)
        assert kpi.nim.display == "+1.85%"


class TestLiabilityMonthlyRatioScale:
    def test_breakdown_share_above_one_is_not_rescaled(self) -> None:
        row = LiabilityMonthlyBreakdownRow.model_validate({"name": "cpty", "pct": 1.2, "proportion": 1.2})
        assert row.pct is not None
        assert row.pct.raw == pytest.approx(1.2)
        assert row.proportion is not None
        assert row.proportion.raw == pytest.approx(1.2)

    def test_ytd_cost_ratio_scale(self) -> None:
        payload = LiabilitiesMonthlyPayload.model_validate(
            {"year": 2026, "months": [], "ytd_avg_liability_cost": 0.0231}
        )
        assert payload.ytd_avg_liability_cost is not None
        assert payload.ytd_avg_liability_cost.raw == pytest.approx(0.0231)
        assert payload.ytd_avg_liability_cost.display == "+2.31%"

    def test_ytd_cost_above_one_is_not_rescaled(self) -> None:
        # A genuine 120% weighted cost must not be auto-divided into 1.20%.
        payload = LiabilitiesMonthlyPayload.model_validate(
            {"year": 2026, "months": [], "ytd_avg_liability_cost": 1.2}
        )
        assert payload.ytd_avg_liability_cost is not None
        assert payload.ytd_avg_liability_cost.raw == pytest.approx(1.2)
        assert payload.ytd_avg_liability_cost.display == "+120.00%"

    def test_month_avg_cost_above_one_is_not_rescaled(self) -> None:
        item = LiabilityMonthlyItem.model_validate(
            {
                "month": "2026-06",
                "month_label": "2026年6月",
                "avg_liability_cost": 1.05,
                "num_days": 30,
            }
        )
        assert item.avg_liability_cost is not None
        assert item.avg_liability_cost.raw == pytest.approx(1.05)
        assert item.avg_liability_cost.display == "+105.00%"


class TestCashflowReinvestmentRiskRatioScale:
    def test_ratio_above_one_is_not_rescaled(self) -> None:
        # 150% of assets maturing within 12m must stay 1.5, not become 0.015.
        response = CashflowProjectionResponse.model_validate(
            {
                "report_date": "2026-06-30",
                "duration_gap": 1.2,
                "asset_duration": 3.4,
                "liability_duration": 2.2,
                "equity_duration": 8.0,
                "rate_sensitivity_1bp": -12345.0,
                "reinvestment_risk_12m": 1.5,
                "monthly_buckets": [],
                "top_maturing_assets_12m": [],
                "warnings": [],
                "computed_at": "2026-06-30T00:00:00Z",
            }
        )
        assert response.reinvestment_risk_12m.raw == pytest.approx(1.5)
        assert response.reinvestment_risk_12m.display == "150.00%"
