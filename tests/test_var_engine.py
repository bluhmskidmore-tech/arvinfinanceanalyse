from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance import var_engine
from backend.app.core_finance.var_engine import compute_portfolio_var, compute_position_var


def test_single_position_var_matches_dv01_volatility_formula() -> None:
    result = compute_position_var(
        dv01=Decimal("-100"),
        annual_yield_vol_bp=Decimal("80"),
    )

    # |-100| × (80 / sqrt(252)) × z，10 日结果再乘 sqrt(10)，均按分四舍五入。
    assert result == {
        "var_1d_95": Decimal("828.95"),
        "var_1d_99": Decimal("1172.35"),
        "var_10d_99": Decimal("3707.28"),
    }


def test_portfolio_var_nets_equal_and_opposite_dv01_to_zero() -> None:
    result = compute_portfolio_var(
        [{"dv01": Decimal("100")}, {"dv01": Decimal("-100")}],
        annual_yield_vol_bp=Decimal("80"),
    )

    assert result == {
        "var_1d_95": Decimal("0.00"),
        "var_1d_99": Decimal("0.00"),
        "var_10d_99": Decimal("0.00"),
    }


def test_portfolio_var_adds_same_direction_positions() -> None:
    portfolio = compute_portfolio_var(
        [{"dv01": Decimal("100")}, {"dv01": Decimal("100")}],
        annual_yield_vol_bp=Decimal("80"),
    )

    assert portfolio == compute_position_var(
        dv01=Decimal("200"),
        annual_yield_vol_bp=Decimal("80"),
    )


@pytest.mark.parametrize(
    "annual_yield_vol_bp",
    [Decimal("-0.01"), float("nan"), float("inf")],
    ids=["negative", "nan", "infinity"],
)
def test_position_var_rejects_negative_or_non_finite_volatility(
    annual_yield_vol_bp: Decimal | float,
) -> None:
    with pytest.raises(ValueError, match="annual_yield_vol_bp"):
        compute_position_var(
            dv01=Decimal("100"),
            annual_yield_vol_bp=annual_yield_vol_bp,
        )


@pytest.mark.parametrize(
    "invalid_z_score",
    [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")],
    ids=["zero", "negative", "nan", "infinity"],
)
@pytest.mark.parametrize("z_name", ["_Z_95", "_Z_99"], ids=["95pct", "99pct"])
def test_position_var_rejects_non_positive_or_non_finite_configured_z_score(
    monkeypatch: pytest.MonkeyPatch,
    invalid_z_score: Decimal,
    z_name: str,
) -> None:
    monkeypatch.setattr(var_engine, z_name, invalid_z_score)

    with pytest.raises(ValueError, match="z_score"):
        compute_position_var(dv01=Decimal("100"))


def test_empty_portfolio_returns_zero_var() -> None:
    assert compute_portfolio_var([]) == {
        "var_1d_95": Decimal("0.00"),
        "var_1d_99": Decimal("0.00"),
        "var_10d_99": Decimal("0.00"),
    }
