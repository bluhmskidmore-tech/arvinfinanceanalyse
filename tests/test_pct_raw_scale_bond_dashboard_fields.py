"""Pct raw-scale coverage for bond-dashboard schema fields."""
from __future__ import annotations

import pytest

from backend.app.schemas.bond_dashboard import (
    BondDashboardAssetStructureItem,
    BondDashboardHeadlineKpiBlock,
    BondDashboardIndustryDistributionItem,
    BondDashboardMaturityStructureItem,
    BondDashboardPortfolioComparisonItem,
    BondDashboardSpreadAnalysisItem,
    BondDashboardYieldDistributionPayload,
)


@pytest.mark.parametrize(
    ("model_cls", "payload", "field_name"),
    [
        (
            BondDashboardHeadlineKpiBlock,
            {
                "weighted_ytm": 0.0085,
                "weighted_coupon": 0.0085,
                "credit_spread_median": 0.0085,
            },
            "weighted_ytm",
        ),
        (
            BondDashboardAssetStructureItem,
            {"category": "rate", "percentage": 0.0085},
            "percentage",
        ),
        (
            BondDashboardYieldDistributionPayload,
            {"report_date": "2026-07-20", "weighted_ytm": 0.0085},
            "weighted_ytm",
        ),
        (
            BondDashboardPortfolioComparisonItem,
            {"portfolio_name": "P1", "weighted_ytm": 0.0085},
            "weighted_ytm",
        ),
        (
            BondDashboardSpreadAnalysisItem,
            {"bond_type": "credit", "median_yield": 0.0085},
            "median_yield",
        ),
        (
            BondDashboardMaturityStructureItem,
            {"maturity_bucket": "1-3Y", "percentage": 0.0085},
            "percentage",
        ),
        (
            BondDashboardIndustryDistributionItem,
            {"industry_name": "bank", "percentage": 0.0085},
            "percentage",
        ),
    ],
)
def test_ratio_pct_fields_keep_sub_one_decimal_ratio(
    model_cls: type,
    payload: dict[str, object],
    field_name: str,
) -> None:
    model = model_cls.model_validate(payload)
    value = getattr(model, field_name)

    assert value.raw == pytest.approx(0.0085)
    expected_display = "+0.85%" if value.sign_aware else "0.85%"
    assert value.display == expected_display


def test_ratio_pct_field_above_one_is_not_rescaled() -> None:
    item = BondDashboardAssetStructureItem.model_validate(
        {"category": "levered", "percentage": 1.5}
    )

    assert item.percentage is not None
    assert item.percentage.raw == pytest.approx(1.5)
    assert item.percentage.display == "150.00%"


def test_existing_numeric_json_passes_through() -> None:
    existing = {
        "raw": 0.0085,
        "unit": "pct",
        "display": "0.85%",
        "precision": 2,
        "sign_aware": False,
    }
    item = BondDashboardAssetStructureItem.model_validate(
        {"category": "rate", "percentage": existing}
    )

    assert item.percentage is not None
    assert item.percentage.model_dump(mode="json") == existing
