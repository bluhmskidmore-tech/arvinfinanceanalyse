"""凸性口径基线：记录仓库内还剩几套凸性口径、各自相对标准现金流凸性的偏差。

W-fi-2026-08 P3 之前仓库内并存两套久期型凸性近似：

* 口径 A ``bond_analytics.common.estimate_convexity`` = ``D(D+1)/(1+y/f)²``（零息近似族）。
* 口径 B ``bond_duration.estimate_convexity_bond`` = ``[D² + D(1+1/f)]/(1+y/f)²``（无出处，
  等价于强行假设付息时点方差 ``M² = D``），相对标准现金流凸性偏差 −23.4% ~ +66.6%。

口径 B 已删除并收敛到口径 A，本文件因此从"冻结两套口径"改为：

1. 冻结**仅存一套**久期型口径相对标准现金流凸性的数值与偏差区间；
2. 用 ``test_single_duration_based_caliber_remains`` 守住"两个入口同值"，防止第二套口径回流；
3. 用 ``test_retired_caliber_b_formula_is_not_restored`` 显式钉死已下线的 B 式不得复活。

口径 A 自身相对标准式仍有 −26.1% ~ +33.2% 偏差（付息债系统性低估 ``M²/(1+y/f)²``），
该项待独立的 rule_version 升级 + 全史重述处理，不在本文件的收敛范围内。
"""
from __future__ import annotations

from decimal import Decimal, localcontext

import pytest

from backend.app.core_finance.bond_analytics.common import estimate_convexity
from backend.app.core_finance.bond_duration import estimate_convexity_bond


# 仅存的久期型凸性口径（A）相对标准现金流凸性的偏差区间。
DURATION_CALIBER_DEVIATION_RANGE = (Decimal("-0.261"), Decimal("0.332"))
# 已下线的口径 B 曾经的偏差区间，仅作历史记录，不再有实现与之对应。
RETIRED_CALIBER_B_DEVIATION_RANGE = (Decimal("-0.234"), Decimal("0.666"))


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


def _retired_caliber_b(
    duration: Decimal, ytm: Decimal, coupon_frequency: int
) -> Decimal:
    """已删除的 ``estimate_convexity_bond`` 原式，仅用于证明它没有回流。"""
    n = Decimal(str(coupon_frequency))
    numerator = duration * duration + duration * (Decimal("1") + Decimal("1") / n)
    if ytm <= 0:
        return numerator * Decimal("1.1")
    return numerator / ((Decimal("1") + ytm / n) ** 2)


CALIBER_CASES = [
    pytest.param(
        10,
        1,
        "87.0660047192138070165286558",
        "81.04611076350523478694439936",
        id="10y-annual-par",
    ),
    pytest.param(
        5,
        2,
        "24.42840732053911541560405511",
        "25.80512003221635031238375820",
        id="5y-semiannual-par",
    ),
    pytest.param(
        1,
        2,
        "1.441647868064594909500734392",
        "1.919859362798060945517878306",
        id="1y-semiannual-par",
    ),
    pytest.param(
        30,
        1,
        "506.7217996425028607898179944",
        "403.2068558022276887879664424",
        id="30y-annual-par",
    ),
]


@pytest.mark.parametrize(
    ("years", "coupon_frequency", "expected_standard", "expected_duration_caliber"),
    CALIBER_CASES,
)
def test_single_duration_based_caliber_remains(
    years: int,
    coupon_frequency: int,
    expected_standard: str,
    expected_duration_caliber: str,
) -> None:
    """两个凸性入口必须同值，且与标准现金流凸性的偏差落在冻结区间内。"""
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
        deviation = common_convexity / standard_convexity - Decimal("1")

    assert standard_convexity == Decimal(expected_standard)
    assert common_convexity == Decimal(expected_duration_caliber)
    # 单一口径护栏：新增第二套凸性实现会在此失败。
    assert bond_duration_convexity == common_convexity
    assert (
        DURATION_CALIBER_DEVIATION_RANGE[0]
        <= deviation
        <= DURATION_CALIBER_DEVIATION_RANGE[1]
    )


@pytest.mark.parametrize(
    ("years", "coupon_frequency", "expected_standard", "expected_duration_caliber"),
    CALIBER_CASES,
)
def test_retired_caliber_b_formula_is_not_restored(
    years: int,
    coupon_frequency: int,
    expected_standard: str,
    expected_duration_caliber: str,
) -> None:
    """已下线的 ``[D² + D(1+1/f)]/(1+y/f)²`` 不得重新出现在 ``estimate_convexity_bond``。"""
    with localcontext() as context:
        context.prec = 28
        macaulay_duration, standard_convexity = _cash_flow_duration_and_convexity(
            years=years,
            coupon_frequency=coupon_frequency,
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        retired = _retired_caliber_b(
            macaulay_duration, Decimal("0.03"), coupon_frequency
        )
        actual = estimate_convexity_bond(
            macaulay_duration,
            Decimal("0.03"),
            coupon_frequency=coupon_frequency,
        )
        retired_deviation = retired / standard_convexity - Decimal("1")

    assert actual != retired
    # 记录被移除的口径当年的偏差量级（本区间不再对应任何在用实现）。
    assert (
        RETIRED_CALIBER_B_DEVIATION_RANGE[0]
        <= retired_deviation
        <= RETIRED_CALIBER_B_DEVIATION_RANGE[1]
    )


def test_non_positive_yield_branch_is_shared() -> None:
    """``y<=0`` 分支同样收敛到口径 A 的 ``D²``，无 1.1 系数。"""
    duration = Decimal("5")
    for ytm in (Decimal("0"), Decimal("-0.01")):
        shared = estimate_convexity(duration, ytm, coupon_frequency=2)
        assert estimate_convexity_bond(duration, ytm, coupon_frequency=2) == shared
        assert shared == duration * duration
