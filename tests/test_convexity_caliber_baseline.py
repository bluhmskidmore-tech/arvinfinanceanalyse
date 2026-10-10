"""凸性口径基线：仓库内只允许存在**一套**凸性口径，且必须是标准现金流凸性。

历史沿革：

* W-fi-2026-08 P3 之前并存两套久期型近似——口径 A
  ``bond_analytics.common.estimate_convexity`` = ``D(D+1)/(1+y/f)²``（零息近似族），
  口径 B ``bond_duration.estimate_convexity_bond`` = ``[D² + D(1+1/f)]/(1+y/f)²``
  （无出处，等价于强行假设付息时点方差 ``M² = D``）。P3 删除了 B、收敛到 A。
* W-fi-2026-08 P4（本次）把仅存的口径 A 升级为标准现金流凸性
  ``C = Σ[CF_k·k(k+1)/(1+y/f)^(k+2)] / (P·f²)``（``k`` 为期数，``C`` 单位年²）。
  口径 A 是零息近似族：单笔现金流且 ``f=1`` 时精确，付息债系统性低估
  ``M²/(1+y/f)²``（实测 par 3% 网格 −20.4%），而分子 ``D(D+1)`` 与 ``f`` 无关，
  零息恒等式要求 ``D² + D/f``，所以 ``f=2`` 短端又高估 ``D/2``（实测 +33.2%）。

折现的复利口径**未变**，仍为 ``(1 + y/f)``：源字段「到期收益率」是名义年利率、
按付息频率复利，已由 ``.tmp-agent/ytm-compounding-empirical.md`` 实证
（63 只半年付券按 f 复利 RMSE 0.0100 vs 年复利 0.2621，63/63 全胜）。
恒等式 ``C_std = (D² + D/f + M²)/(1+y/f)²`` 本来就按 f 复利书写，与之一致。

本文件的三层护栏：

1. ``test_convexity_matches_standard_cash_flow_definition``：在用实现必须逐位等于
   独立写出的标准定义（偏差冻结在 ``STANDARD_MATCH_TOLERANCE`` 以内，只留
   Decimal 末位噪声）。
2. ``test_single_caliber_shared_between_entrypoints``：两个入口同值，防止第二套
   口径回流。
3. ``test_retired_caliber_a_approximation_is_not_restored`` /
   ``test_retired_caliber_b_formula_is_not_restored``：显式钉死两套已下线的
   久期型近似不得复活。
"""
from __future__ import annotations

from decimal import Decimal, localcontext

import pytest

from backend.app.core_finance.bond_analytics.common import estimate_convexity
from backend.app.core_finance.bond_duration import estimate_convexity_bond

# 在用实现与独立标准定义之间只允许 Decimal 末位噪声（prec=28 下实测 ≤8e-28）。
STANDARD_MATCH_TOLERANCE = Decimal("1e-24")
# 已下线的两套久期型近似当年相对标准式的偏差区间，仅作历史记录。
RETIRED_CALIBER_A_DEVIATION_RANGE = (Decimal("-0.205"), Decimal("0.332"))
RETIRED_CALIBER_B_DEVIATION_RANGE = (Decimal("-0.234"), Decimal("0.666"))


def _cash_flow_duration_and_convexity(
    *,
    years: int,
    coupon_frequency: int,
    coupon_rate: Decimal,
    ytm: Decimal,
) -> tuple[Decimal, Decimal]:
    """独立写出的标准定义：Macaulay 久期（年）与标准现金流凸性（年²）。

    刻意按**期数** ``k`` 展开 ``C = Σ CF_k·k(k+1)/(1+y/f)^(k+2) / (P·f²)``，
    而在用实现按**年** ``t`` 展开 ``C = Σ t(t+1/f)·PV / P / (1+y/f)²``。两式代数
    等价（``k(k+1)/f² = t(t+1/f)``），用不同写法交叉验证可以捕捉实现里的
    单位/指数错误，而不只是把同一段代码抄两遍。
    """
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


def _retired_caliber_a(
    duration: Decimal, ytm: Decimal, coupon_frequency: int
) -> Decimal:
    """W-fi-2026-08 P4 之前的 ``estimate_convexity`` 原式，仅用于证明它没有回流。"""
    if ytm <= 0:
        return duration * duration
    n = Decimal(str(coupon_frequency))
    return (duration * (duration + Decimal("1"))) / ((Decimal("1") + ytm / n) ** 2)


def _retired_caliber_b(
    duration: Decimal, ytm: Decimal, coupon_frequency: int
) -> Decimal:
    """W-fi-2026-08 P3 删除的 ``estimate_convexity_bond`` 原式，同上。"""
    n = Decimal(str(coupon_frequency))
    numerator = duration * duration + duration * (Decimal("1") + Decimal("1") / n)
    if ytm <= 0:
        return numerator * Decimal("1.1")
    return numerator / ((Decimal("1") + ytm / n) ** 2)


CALIBER_CASES = [
    pytest.param(10, 1, "87.0660047192138070165286558", id="10y-annual-par"),
    pytest.param(5, 2, "24.42840732053911541560405511", id="5y-semiannual-par"),
    pytest.param(1, 2, "1.441647868064594909500734392", id="1y-semiannual-par"),
    pytest.param(30, 1, "506.7217996425028607898179944", id="30y-annual-par"),
]


@pytest.mark.parametrize(("years", "coupon_frequency", "expected_standard"), CALIBER_CASES)
def test_convexity_matches_standard_cash_flow_definition(
    years: int,
    coupon_frequency: int,
    expected_standard: str,
) -> None:
    """在用实现必须等于独立写出的标准现金流凸性（偏差只剩 Decimal 末位噪声）。"""
    with localcontext() as context:
        context.prec = 28
        macaulay_duration, standard_convexity = _cash_flow_duration_and_convexity(
            years=years,
            coupon_frequency=coupon_frequency,
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        actual = estimate_convexity(
            macaulay_duration,
            Decimal("0.03"),
            coupon_frequency=coupon_frequency,
            coupon_rate=Decimal("0.03"),
            years_to_maturity=Decimal(years),
        )
        deviation = actual / standard_convexity - Decimal("1")

    assert standard_convexity == Decimal(expected_standard)
    assert abs(deviation) <= STANDARD_MATCH_TOLERANCE


@pytest.mark.parametrize(("years", "coupon_frequency", "expected_standard"), CALIBER_CASES)
def test_single_caliber_shared_between_entrypoints(
    years: int,
    coupon_frequency: int,
    expected_standard: str,
) -> None:
    """两个凸性入口必须同值——``estimate_convexity_bond`` 只是薄封装。

    现金流入参与回退入参两条路径都要同值，新增第二套实现会在此失败。
    """
    with localcontext() as context:
        context.prec = 28
        macaulay_duration, _standard = _cash_flow_duration_and_convexity(
            years=years,
            coupon_frequency=coupon_frequency,
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        kwargs = {
            "coupon_rate": Decimal("0.03"),
            "years_to_maturity": Decimal(years),
        }
        assert estimate_convexity_bond(
            macaulay_duration,
            Decimal("0.03"),
            coupon_frequency=coupon_frequency,
            **kwargs,
        ) == estimate_convexity(
            macaulay_duration,
            Decimal("0.03"),
            coupon_frequency=coupon_frequency,
            **kwargs,
        )
        assert estimate_convexity_bond(
            macaulay_duration,
            Decimal("0.03"),
            coupon_frequency=coupon_frequency,
        ) == estimate_convexity(
            macaulay_duration,
            Decimal("0.03"),
            coupon_frequency=coupon_frequency,
        )


@pytest.mark.parametrize(("years", "coupon_frequency", "expected_standard"), CALIBER_CASES)
def test_retired_caliber_a_approximation_is_not_restored(
    years: int,
    coupon_frequency: int,
    expected_standard: str,
) -> None:
    """已下线的久期型近似 ``D(D+1)/(1+y/f)²`` 不得重新出现在正式现金流路径。"""
    with localcontext() as context:
        context.prec = 28
        macaulay_duration, standard_convexity = _cash_flow_duration_and_convexity(
            years=years,
            coupon_frequency=coupon_frequency,
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        retired = _retired_caliber_a(
            macaulay_duration, Decimal("0.03"), coupon_frequency
        )
        actual = estimate_convexity(
            macaulay_duration,
            Decimal("0.03"),
            coupon_frequency=coupon_frequency,
            coupon_rate=Decimal("0.03"),
            years_to_maturity=Decimal(years),
        )
        retired_deviation = retired / standard_convexity - Decimal("1")

    assert actual != retired
    # 记录被移除的口径当年的偏差量级（本区间不再对应任何在用实现）。
    assert (
        RETIRED_CALIBER_A_DEVIATION_RANGE[0]
        <= retired_deviation
        <= RETIRED_CALIBER_A_DEVIATION_RANGE[1]
    )


@pytest.mark.parametrize(("years", "coupon_frequency", "expected_standard"), CALIBER_CASES)
def test_retired_caliber_b_formula_is_not_restored(
    years: int,
    coupon_frequency: int,
    expected_standard: str,
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
            coupon_rate=Decimal("0.03"),
            years_to_maturity=Decimal(years),
        )
        retired_deviation = retired / standard_convexity - Decimal("1")

    assert actual != retired
    assert (
        RETIRED_CALIBER_B_DEVIATION_RANGE[0]
        <= retired_deviation
        <= RETIRED_CALIBER_B_DEVIATION_RANGE[1]
    )


@pytest.mark.parametrize("coupon_frequency", [1, 2, 4])
def test_zero_coupon_fallback_equals_closed_form(coupon_frequency: int) -> None:
    """零息（单笔现金流）时闭式解 ``t(t+1/f)/(1+y/f)²`` 与遍历同值，且是精确解。

    注意分子是 ``t(t + 1/f)`` 而非旧式的 ``t(t + 1)``：旧式分子与 ``f`` 无关，
    ``f=2`` 时对短端高估 ``D/2``。
    """
    years = Decimal("5")
    ytm = Decimal("0.04")
    frequency = Decimal(coupon_frequency)
    closed_form = (
        years
        * (years + Decimal("1") / frequency)
        / ((Decimal("1") + ytm / frequency) ** 2)
    )
    assert (
        estimate_convexity(years, ytm, coupon_frequency=coupon_frequency)
        == closed_form
    )
    assert (
        estimate_convexity(
            years,
            ytm,
            coupon_frequency=coupon_frequency,
            coupon_rate=Decimal("0"),
            years_to_maturity=years,
        )
        == closed_form
    )


def test_non_positive_yield_no_longer_returns_duration_squared() -> None:
    """``y<=0`` 不再特判 ``D²``；标准式在 ``y=0`` 处连续，两个入口仍同值。

    旧实现在 ``y=0`` 有 ``D`` 大小的跳变（``y→0⁺`` 给 ``D(D+1)``、``y=0`` 给 ``D²``）。
    """
    duration = Decimal("5")
    for coupon_frequency in (1, 2):
        frequency = Decimal(coupon_frequency)
        for ytm in (Decimal("0"), Decimal("-0.01")):
            shared = estimate_convexity(
                duration, ytm, coupon_frequency=coupon_frequency
            )
            assert (
                estimate_convexity_bond(
                    duration, ytm, coupon_frequency=coupon_frequency
                )
                == shared
            )
            assert shared != duration * duration
            assert shared == (
                duration
                * (duration + Decimal("1") / frequency)
                / ((Decimal("1") + ytm / frequency) ** 2)
            )
        # y→0⁺ 与 y=0 连续：旧实现在此处跳变 D。
        limit = estimate_convexity(
            duration, Decimal("1e-12"), coupon_frequency=coupon_frequency
        )
        at_zero = estimate_convexity(
            duration, Decimal("0"), coupon_frequency=coupon_frequency
        )
        assert abs(limit - at_zero) < Decimal("1e-9")
