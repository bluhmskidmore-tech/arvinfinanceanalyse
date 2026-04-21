"""W-liability-compat-2026-04-21 caliber migration: canonical hat_mapping parity checks.

Exercises ``zqtz_asset_yield_weight`` and ``is_interest_bearing_bond_asset`` after
delegation to ``classification_rules.infer_invest_type``, including v1 shim branches
documented in-module (human ``caliber-hat_mapping-justified`` notes).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.liability_analytics_compat import (
    is_interest_bearing_bond_asset,
    zqtz_asset_amount,
    zqtz_asset_yield_weight,
)


@pytest.mark.parametrize(
    ("asset_class", "amortized", "market", "face", "expected"),
    [
        ("持有至到期类资产", "100", "200", "150", Decimal("100")),
        ("持有至到期投资", None, "200", "150", Decimal("200")),
        ("可供出售债券", "100", "200", "150", Decimal("200")),
        ("交易性金融资产", "100", "200", "150", Decimal("200")),
        ("", None, "200", "150", Decimal("200")),
        ("未知资产类别", None, "200", "150", Decimal("200")),
    ],
)
def test_zqtz_asset_yield_weight_h_a_t_and_fallbacks(
    asset_class: str,
    amortized: str | None,
    market: str,
    face: str,
    expected: Decimal,
) -> None:
    row = {
        "asset_class": asset_class,
        "amortized_cost_native": amortized,
        "market_value_native": market,
        "face_value_native": face,
    }
    assert zqtz_asset_yield_weight(row) == expected
    assert zqtz_asset_amount(row) == Decimal(market)


@pytest.mark.parametrize(
    ("asset_class", "expected"),
    [
        ("持有至到期类资产", True),
        ("可供出售债券", True),
        ("应收投资款项", True),
        ("应收投资", True),
        ("交易性金融资产", False),
        ("", False),
        ("其他应收", False),
        ("可供出售金融资产交易专用", False),
    ],
)
def test_is_interest_bearing_bond_asset_h_a_t_and_shim(asset_class: str, expected: bool) -> None:
    row = {"is_issuance_like": False, "asset_class": asset_class}
    assert is_interest_bearing_bond_asset(row) is expected


def test_is_interest_bearing_bond_asset_issuance_like_false() -> None:
    row = {"is_issuance_like": True, "asset_class": "持有至到期类资产"}
    assert is_interest_bearing_bond_asset(row) is False
