"""Equivalence tests for caliber trial migration (hat_mapping → canonical infer_invest_type)."""

from __future__ import annotations

import itertools
from decimal import Decimal

import pytest

from backend.app.core_finance.config.classification_rules import infer_invest_type
from backend.app.core_finance.pnl_yield_display import (
    apply_v1_invest_type_to_fi_yield_row,
    infer_invest_type_v1,
)

_PORTFOLIOS = (None, "PortA")
_ASSET_TYPES = (None, "A", "T", "H", "TestT")
_ASSET_CLASSES = (
    None,
    "可供出售",
    "持有至到期",
    "交易性金融资产",
    "AFS",
    "HTM",
    "TRADING",
    "Trading",
    "trading",
    "OCI",
    "其他债权",
)
_IS_NONSTD = (False, True)

_MATRIX = list(
    itertools.product(_PORTFOLIOS, _ASSET_TYPES, _ASSET_CLASSES, _IS_NONSTD),
)


@pytest.mark.parametrize(
    ("portfolio", "asset_type", "asset_class", "is_nonstd"),
    _MATRIX,
)
def test_v1_delegate_matches_canonical_for_all_hat_inputs(
    portfolio: str | None,
    asset_type: str | None,
    asset_class: str | None,
    is_nonstd: bool,
) -> None:
    expected = infer_invest_type(
        portfolio,
        asset_type,
        asset_class,
        interest_income=None,
        is_nonstd=is_nonstd,
    )
    assert (
        infer_invest_type_v1(
            portfolio,
            asset_type,
            asset_class,
            interest_income=None,
            is_nonstd=is_nonstd,
        )
        == expected
    )

    if not is_nonstd:
        return

    base_kw = dict(
        portfolio=portfolio,
        asset_type=asset_type,
        asset_class=asset_class,
        is_nonstd=True,
    )
    assert infer_invest_type_v1(**base_kw, interest_income=1.5) == "H"
    assert infer_invest_type(**base_kw, interest_income=Decimal("1.5")) == "H"

    assert infer_invest_type_v1(**base_kw, interest_income=-1.0) == "T"
    assert infer_invest_type(**base_kw, interest_income=Decimal("-1.0")) == "T"

    assert infer_invest_type_v1(**base_kw, interest_income=0) == "T"
    assert infer_invest_type(**base_kw, interest_income=Decimal("0")) == "T"


@pytest.mark.parametrize("asset_class", ("TRADING", "trading", "Trading"))
def test_v1_now_recognizes_uppercase_TRADING(asset_class: str) -> None:
    assert infer_invest_type_v1(None, None, asset_class) == "T"


def test_v1_interest_income_float_to_decimal_conversion_preserves_semantics() -> None:
    v1 = infer_invest_type_v1(None, None, None, interest_income=0.1, is_nonstd=True)
    canon = infer_invest_type(
        None,
        None,
        None,
        interest_income=Decimal("0.1"),
        is_nonstd=True,
    )
    assert v1 == canon == "H"


def test_apply_v1_invest_type_to_fi_yield_row_uses_canonical_logic() -> None:
    row: dict = {"source": "FI", "asset_class": "TRADING"}
    apply_v1_invest_type_to_fi_yield_row(row)
    assert row["invest_type"] == "T"


def test_apply_v1_invest_type_skips_non_FI_source() -> None:
    row: dict = {"source": "GL", "asset_class": "TRADING"}
    snapshot = dict(row)
    apply_v1_invest_type_to_fi_yield_row(row)
    assert row == snapshot
    assert "invest_type" not in row


def test_apply_v1_invest_type_falls_back_from_portfolio_label_to_portfolio() -> None:
    row: dict = {
        "source": "FI",
        "portfolio_label": None,
        "portfolio": "PortB",
        "asset_class": "HTM",
    }
    apply_v1_invest_type_to_fi_yield_row(row)
    assert row["invest_type"] == "H"
