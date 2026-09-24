from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.product_category_pnl import (
    ProductCategoryInterestSpreadPayload,
    ProductCategoryLiabilityCostDecompositionPayload,
)


def _metric(*, unit: str) -> dict[str, str]:
    return {"raw": "1.45", "display": "1.5 bp", "unit": unit}


@pytest.mark.parametrize(
    "field_name",
    [
        "all_currency_asset_yield_pct",
        "all_currency_liability_yield_pct",
        "all_currency_spread_pct",
        "cny_asset_yield_pct",
        "cny_liability_yield_pct",
        "cny_spread_pct",
    ],
)
def test_interest_spread_fields_reject_bp_units(field_name: str) -> None:
    with pytest.raises(ValidationError, match="unit='percent'"):
        ProductCategoryInterestSpreadPayload.model_validate(
            {field_name: _metric(unit="bp")}
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "liability_yield_pct",
        "liability_yield_ex_cln_pct",
        "cln_yield_pct",
    ],
)
def test_liability_rate_fields_reject_bp_units(field_name: str) -> None:
    with pytest.raises(ValidationError, match="unit='percent'"):
        ProductCategoryLiabilityCostDecompositionPayload.model_validate(
            {field_name: _metric(unit="bp")}
        )


def test_cln_drag_rejects_percent_units() -> None:
    with pytest.raises(ValidationError, match="unit='bp'"):
        ProductCategoryLiabilityCostDecompositionPayload.model_validate(
            {"cln_drag_bp": _metric(unit="percent")}
        )


def test_liability_decomposition_accepts_field_specific_units() -> None:
    payload = ProductCategoryLiabilityCostDecompositionPayload.model_validate(
        {
            "liability_yield_pct": {
                "raw": "1.58",
                "display": "1.58%",
                "unit": "percent",
            },
            "cln_drag_bp": _metric(unit="bp"),
        }
    )

    assert payload.liability_yield_pct is not None
    assert payload.liability_yield_pct.unit == "percent"
    assert payload.cln_drag_bp is not None
    assert payload.cln_drag_bp.unit == "bp"
