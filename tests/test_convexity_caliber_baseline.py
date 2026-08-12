from __future__ import annotations

from decimal import Decimal, localcontext

import pytest

from backend.app.core_finance.bond_analytics.common import estimate_convexity
from backend.app.core_finance.bond_duration import estimate_convexity_bond


COMMON_DEVIATION_RANGE = (Decimal("-0.261"), Decimal("0.332"))
BOND_DURATION_DEVIATION_RANGE = (Decimal("-0.234"), Decimal("0.666"))


def _cash_flow_duration_and_convexity(
    *,
    years: int,
    coupon_frequency: int,
    coupon_rate: Decimal,
    ytm: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return Macaulay duration and standard cash-flow convexity."""
    face_value = Decimal("100")
    frequency = Decimal(coupon_frequency)
    periodic_coupon = face_value * coupon_rate / frequency
    one_plus_periodic_yield = Decimal("1") + ytm / frequency
    periods = years * coupon_frequency

    price = Decimal("0")
    duration_numerator = Decimal("0")
    convexity_numerator = Decimal("0")
    for period in range(1, periods + 1):
        k = Decimal(period)
        cash_flow = periodic_coupon
        if period == periods:
            cash_flow += face_value
        discount = one_plus_periodic_yield**period
        price += cash_flow / discount
        duration_numerator += cash_flow * k / discount
        convexity_numerator += (
            cash_flow
            * k
            * (k + Decimal("1"))
            / (one_plus_periodic_yield ** (period + 2))
        )

    macaulay_duration = duration_numerator / price / frequency
    standard_convexity = convexity_numerator / (price * frequency * frequency)
    return macaulay_duration, standard_convexity


@pytest.mark.parametrize(
    (
        "years",
        "coupon_frequency",
        "expected_standard",
        "expected_common",
        "expected_bond_duration",
    ),
    [
        pytest.param(
            10,
            1,
            "87.0660047192138070165286558",
            "81.04611076350523478694439936",
            "89.32786109047205960511022733",
            id="10y-annual-par",
        ),
        pytest.param(
            5,
            2,
            "24.42840732053911541560405511",
            "25.80512003221635031238375820",
            "28.07659405976670361042497334",
            id="5y-semiannual-par",
        ),
        pytest.param(
            1,
            2,
            "1.441647868064594909500734392",
            "1.919859362798060945517878306",
            "2.401604048395102196370942949",
            id="1y-semiannual-par",
        ),
        pytest.param(
            30,
            1,
            "506.7217996425028607898179944",
            "403.2068558022276887879664424",
            "422.2364105104507730473369780",
            id="30y-annual-par",
        ),
    ],
)
def test_current_convexity_calibers_against_cash_flow_standard(
    years: int,
    coupon_frequency: int,
    expected_standard: str,
    expected_common: str,
    expected_bond_duration: str,
) -> None:
    with localcontext() as context:
        context.prec = 28
        macaulay_duration, standard_convexity = _cash_flow_duration_and_convexity(
            years=years,
            coupon_frequency=coupon_frequency,
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        common_convexity = estimate_convexity(
            macaulay_duration,
            Decimal("0.03"),
            coupon_frequency=coupon_frequency,
        )
        bond_duration_convexity = estimate_convexity_bond(
            macaulay_duration,
            Decimal("0.03"),
            coupon_frequency=coupon_frequency,
        )
        common_deviation = common_convexity / standard_convexity - Decimal("1")
        bond_duration_deviation = (
            bond_duration_convexity / standard_convexity - Decimal("1")
        )

    assert standard_convexity == Decimal(expected_standard)
    assert common_convexity == Decimal(expected_common)
    assert bond_duration_convexity == Decimal(expected_bond_duration)
    assert COMMON_DEVIATION_RANGE[0] <= common_deviation <= COMMON_DEVIATION_RANGE[1]
    assert (
        BOND_DURATION_DEVIATION_RANGE[0]
        <= bond_duration_deviation
        <= BOND_DURATION_DEVIATION_RANGE[1]
    )
