"""
Campisi treasury/spread 分项独立手算黄金测试（B4）。

背景：tests/test_campisi_formula_golden.py 中的 selection 断言按
``selection = total - income - treasury - spread`` 构造，是残差定义的恒真式；
SYS-P0-01 类缺陷（国债曲线贡献被静默归零、差额被 selection 吸收）无法被该
恒等式捕获。本文件为 treasury effect 与 spread effect 提供**独立手算**的黄金
字面量（期望值不由实现或结果字段推导），并在同一 fixture 下断言 selection
等于手算残差字面量——若任一分项被静默归零，分项断言与 selection 断言会
同时失败，不再恒真。

fixture 设计原则（保证黄金值可精确手算、无舍入不确定性）：

1. 曲线快照采用真实仓储形状 ``dict[tenor, Decimal]``（构造方式参考
   tests/test_pnl_bridge_with_curve.py），六个关键期限全备、向上倾斜，
   全部取 1/8 的整数倍（二进制可精确表示的浮点），期初→期末平行 +50bp，
   使节点差在 float 减法下严格等于 0.50（百分数点）。
2. 债券到期日使剩余天数恰为 365 的整数倍（1095 天 = 3.0y、1825 天 = 5.0y），
   正好落在曲线 3Y/5Y 关键期限节点上。三次样条严格过节点（分段连续性
   恒等式 S_i(x_{i+1}) = y_{i+1} 对任意二阶导解代数成立；实现求值后
   round(·, 8) 吸收 ~1e-15 浮点噪声），故 Δy 精确等于节点差 0.50pp/100。
3. 两只债均为零息（贴现）债：Macaulay 久期 = 剩余年限（整数年），绕开
   compute_macaulay_duration 闭式幂运算及其 0.0001 quantize；票息为 0 也
   使 income_return = 0，面值不进入任何分项。ytm 取 4.8%（与 4.5%~5.25%
   的曲线水平自洽），使修正久期除数 1 + 0.048/2 = 1.024 = 2^10/10^3，
   十进制整除，修正久期为有限小数。
4. 应计利息期初/期末均为 0（贴现债无票息应计），走全价（dirty）主线；
   曲线全 tenor、利差双侧为正——本文件不依赖任何脏输入 fallback 行为，
   并以 ``diagnostics == []`` 锁定主线路径。

口径确认（先读 backend/app/core_finance/campisi.py 与 bond_four_effects.py）：

- treasury_effect = -修正久期(期初) × Δy(小数) × 期初市值
- spread_effect   = -修正久期(期初) × Δ利差(小数) × 期初市值
- 四效应线性口径只使用期初修正久期（report_date = start_date）；期末久期
  不进入线性公式（二阶项在六效应中另行拆分），故 fixture 的“期末久期”
  仅由期末曲线/市值隐含体现。
- Δy = (期末插值% - 期初插值%) / 100；Δ利差 = (期末bp - 期初bp) / 10000；
  国债（GOV 评级）的利差变动按口径恒为 0。
- 容差 abs=1e-4 对齐实现内的 quantize 精度（compute_macaulay_duration 的
  Decimal("0.0001")；样条求值 round(·, 8)）。本 fixture 各步十进制整除，
  理论偏差为 0，容差仅是上界。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.bond_four_effects import compute_bond_four_effects
from backend.app.core_finance.campisi import (
    benchmark_yield_change_decimal,
    campisi_attribution,
    credit_spread_change_decimal,
)

START_DATE = date(2026, 1, 1)
END_DATE = date(2026, 1, 31)  # num_days = 30

# ---------------------------------------------------------------------------
# 曲线快照 fixture（仓储形状：dict[tenor, Decimal]，单位：百分数）
# 期初→期末平行 +50bp；所有值为 1/8 的整数倍（二进制精确浮点），
# 保证任意节点的期末-期初差在 float 下严格等于 0.50。
# ---------------------------------------------------------------------------
TREASURY_CURVE_START: dict[str, Decimal] = {
    "1Y": Decimal("4.25"),
    "3Y": Decimal("4.50"),
    "5Y": Decimal("4.75"),
    "7Y": Decimal("4.875"),
    "10Y": Decimal("5.00"),
    "30Y": Decimal("5.25"),
}
TREASURY_CURVE_END: dict[str, Decimal] = {
    "1Y": Decimal("4.75"),
    "3Y": Decimal("5.00"),
    "5Y": Decimal("5.25"),
    "7Y": Decimal("5.375"),
    "10Y": Decimal("5.50"),
    "30Y": Decimal("5.75"),
}

_TENOR_TO_MARKET_KEY = {
    "1Y": "treasury_1y",
    "3Y": "treasury_3y",
    "5Y": "treasury_5y",
    "7Y": "treasury_7y",
    "10Y": "treasury_10y",
    "30Y": "treasury_30y",
}


def _campisi_market(curve: dict[str, Decimal], aaa_spread_bp: Decimal) -> dict[str, Decimal]:
    """把 tenor 曲线快照映射为 campisi 的 market 字典（treasury_* 为百分数，利差为 BP）。"""
    market = {_TENOR_TO_MARKET_KEY[tenor]: value for tenor, value in curve.items()}
    market["credit_spread_aaa_3y"] = aaa_spread_bp
    return market


# AAA 3Y 信用利差：期初 50bp → 期末 75bp（走阔 +25bp）
MARKET_START = _campisi_market(TREASURY_CURVE_START, Decimal("50"))
MARKET_END = _campisi_market(TREASURY_CURVE_END, Decimal("75"))


# ---------------------------------------------------------------------------
# 手算过程（国债贴现债 GOV_ZC_3Y）——期望值全部为独立字面量：
#
# 1) 剩余天数：2026-01-01 → 2028-12-31
#      2026-01-01→2027-01-01 = 365（2026 平年）
#      2027-01-01→2028-01-01 = 365（2027 平年）
#      2028-01-01→2028-12-31 = 365（2028 闰年 366 天，1 月 1 日 + 365 天 = 12 月 31 日）
#    合计 1095 天；年限 = 1095/365 = 3.0（精确，落在 3Y 节点）
# 2) 零息 Macaulay 久期 = 剩余年限 = 3
#    期初修正久期 = 3 / (1 + 0.048/2) = 3 / 1.024 = 3000/1024 = 2.9296875（十进制整除）
# 3) Δy：期初 3Y 节点 4.50% → 期末 5.00%（样条严格过节点）
#    Δy = (5.00 - 4.50) / 100 = 0.005
# 4) treasury_effect = -2.9296875 × 0.005 × 1_000_000 = -2.9296875 × 5_000
#                    = -14_648.4375（利率上行 → 为负）
# 5) spread_effect = 0（国债评级 GOV，利差变动按口径恒为 0）
# 6) income_return = 0（零息票）；面值 1_150_000 只进 income 公式，×0 票息后无贡献
# 7) total_return（全价基准，AI 双侧为 0）
#      = (985_600 + 0) - (1_000_000 + 0) + (0 - (0 - 0)) = -14_400
# 8) selection = -14_400 - 0 - (-14_648.4375) - 0 = +248.4375
#    （手算残差字面量。若曲线贡献被静默归零（SYS-P0-01 类），treasury 变为 0、
#      selection 变为 -14_400，两处断言同时失败——此断言不再恒真。）
# ---------------------------------------------------------------------------
def _gov_zc_3y(**overrides: object) -> dict[str, object]:
    row = {
        "bond_code": "GOV_ZC_3Y",
        "asset_class_start": "国债",
        "market_value_start": 1_000_000.0,
        "market_value_end": 985_600.0,
        "face_value_start": 1_150_000.0,
        "coupon_rate_start": 0.0,
        "yield_to_maturity_start": 0.048,
        "maturity_date_start": date(2028, 12, 31),
        "accrued_interest_start": 0.0,
        "accrued_interest_end": 0.0,
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# 手算过程（零息 AAA 信用债 AAA_ZC_5Y）：
#
# 1) 剩余天数：2026-01-01 → 2030-12-31
#      365(2026) + 365(2027) + 366(2028 闰) + 365(2029) + 364(2030-01-01→12-31)
#    合计 1825 天；年限 = 1825/365 = 5.0（精确，落在 5Y 节点）
# 2) 零息 Macaulay = 5；期初修正久期 = 5 / 1.024 = 5000/1024 = 4.8828125（精确）
# 3) Δy：期初 5Y 节点 4.75% → 期末 5.25% → Δy = 0.005
#    treasury_effect = -4.8828125 × 0.005 × 800_000 = -4.8828125 × 4_000
#                    = -19_531.25（利率上行 → 为负）
# 4) Δ利差：AAA 3Y 50bp → 75bp → (75 - 50)/10000 = 0.0025
#    spread_effect = -4.8828125 × 0.0025 × 800_000 = -4.8828125 × 2_000
#                  = -9_765.625（利差走阔 → 为负）
# 5) income = 0（零息）；total_return = 771_000 - 800_000 = -29_000
# 6) selection = -29_000 - 0 - (-19_531.25) - (-9_765.625) = +296.875
#    （手算残差字面量；若 spread 被静默归零，selection 变为 -9_468.75，断言失败。）
# ---------------------------------------------------------------------------
def _aaa_zc_5y(**overrides: object) -> dict[str, object]:
    row = {
        "bond_code": "AAA_ZC_5Y",
        "asset_class_start": "AAA 信用债",
        "market_value_start": 800_000.0,
        "market_value_end": 771_000.0,
        "face_value_start": 1_015_000.0,
        "coupon_rate_start": 0.0,
        "yield_to_maturity_start": 0.048,
        "maturity_date_start": date(2030, 12, 31),
        "accrued_interest_start": 0.0,
        "accrued_interest_end": 0.0,
    }
    row.update(overrides)
    return row


def test_benchmark_and_spread_change_legs_match_hand_values() -> None:
    """曲线→Δy 与 BP→Δ利差 两条腿的独立手算对照（分项黄金值的输入前提）。

    3.0y / 5.0y 恰为样条节点，节点差 0.50pp 手算即为 0.005 小数；
    利差 (75-50)bp / 10000 = 0.0025。fixture 数值经二进制精确性设计，
    两条腿均无浮点尾差，可做精确相等断言。
    """
    assert benchmark_yield_change_decimal(MARKET_START, MARKET_END, 3.0) == Decimal("0.005")
    assert benchmark_yield_change_decimal(MARKET_START, MARKET_END, 5.0) == Decimal("0.005")
    assert credit_spread_change_decimal(MARKET_START, MARKET_END, "AAA") == Decimal("0.0025")
    # 国债评级无利差腿（口径定义）
    assert credit_spread_change_decimal(MARKET_START, MARKET_END, "GOV") == Decimal("0")


def test_treasury_effect_gov_bond_matches_hand_calculated_golden() -> None:
    """国债 treasury effect 独立手算黄金值：-14_648.4375（推导见 _gov_zc_3y 注释）。"""
    result = campisi_attribution(
        positions_merged=[_gov_zc_3y()],
        market_start=MARKET_START,
        market_end=MARKET_END,
        start_date=START_DATE,
        end_date=END_DATE,
    )
    (row,) = result.by_bond

    # 非零 + 符号：收益率上行，利率效应必须为负（若曲线贡献被静默归零则此处失败）
    assert row["treasury_effect"] < 0
    assert row["treasury_effect"] == pytest.approx(-14_648.4375, abs=1e-4)
    # 期初修正久期手算值 3/1.024
    assert row["mod_duration"] == pytest.approx(2.9296875, abs=1e-4)
    # 国债无利差项；零息无票息收益
    assert row["spread_effect"] == pytest.approx(0.0, abs=1e-12)
    assert row["income_return"] == pytest.approx(0.0, abs=1e-12)
    assert row["total_return"] == pytest.approx(-14_400.0, abs=1e-4)
    # selection 等于手算残差字面量（非由结果字段回算，不是恒真式）
    assert row["selection_effect"] == pytest.approx(248.4375, abs=1e-4)
    # 全价主线：AI 双侧齐备，无 fallback 诊断
    assert row["has_accrued_interest"] is True
    assert result.diagnostics == []


def test_spread_and_treasury_effects_credit_bond_match_hand_calculated_goldens() -> None:
    """AAA 信用债 spread/treasury 独立手算黄金值（推导见 _aaa_zc_5y 注释）。"""
    result = campisi_attribution(
        positions_merged=[_aaa_zc_5y()],
        market_start=MARKET_START,
        market_end=MARKET_END,
        start_date=START_DATE,
        end_date=END_DATE,
    )
    (row,) = result.by_bond

    # 非零 + 符号：利差走阔 → spread 为负；利率上行 → treasury 为负
    assert row["spread_effect"] < 0
    assert row["treasury_effect"] < 0
    assert row["spread_effect"] == pytest.approx(-9_765.625, abs=1e-4)
    assert row["treasury_effect"] == pytest.approx(-19_531.25, abs=1e-4)
    assert row["mod_duration"] == pytest.approx(4.8828125, abs=1e-4)
    assert row["income_return"] == pytest.approx(0.0, abs=1e-12)
    assert row["total_return"] == pytest.approx(-29_000.0, abs=1e-4)
    # selection 手算残差字面量
    assert row["selection_effect"] == pytest.approx(296.875, abs=1e-4)
    assert row["has_accrued_interest"] is True
    assert result.diagnostics == []


def test_component_signs_flip_when_rates_fall_and_spreads_tighten() -> None:
    """市场方向反转（期初/期末互换）：Δy = -0.005、Δ利差 = -0.0025，
    分项应精确取相反数且为正——锁定符号约定的双向正确性。
    市值终值换成价格上涨情形以保持情景自洽（分项与终值市值无关，不另行断言）。
    """
    result = campisi_attribution(
        positions_merged=[
            _gov_zc_3y(market_value_end=1_014_600.0),
            _aaa_zc_5y(market_value_end=829_300.0),
        ],
        market_start=MARKET_END,
        market_end=MARKET_START,
        start_date=START_DATE,
        end_date=END_DATE,
    )
    gov_row, aaa_row = result.by_bond

    assert gov_row["treasury_effect"] > 0
    assert gov_row["treasury_effect"] == pytest.approx(14_648.4375, abs=1e-4)
    assert gov_row["spread_effect"] == pytest.approx(0.0, abs=1e-12)

    assert aaa_row["treasury_effect"] > 0
    assert aaa_row["treasury_effect"] == pytest.approx(19_531.25, abs=1e-4)
    assert aaa_row["spread_effect"] > 0
    assert aaa_row["spread_effect"] == pytest.approx(9_765.625, abs=1e-4)


def test_portfolio_totals_match_hand_summed_component_goldens() -> None:
    """组合合计等于逐券手算黄金值之和（合计亦为独立字面量，非回算）：

    treasury  = -14_648.4375 + (-19_531.25) = -34_179.6875
    spread    = 0 + (-9_765.625)            = -9_765.625
    income    = 0 + 0                       = 0
    selection = 248.4375 + 296.875          = 545.3125
    total     = -14_400 + (-29_000)         = -43_400
    期初市值   = 1_000_000 + 800_000         = 1_800_000
    """
    result = campisi_attribution(
        positions_merged=[_gov_zc_3y(), _aaa_zc_5y()],
        market_start=MARKET_START,
        market_end=MARKET_END,
        start_date=START_DATE,
        end_date=END_DATE,
    )

    assert result.num_days == 30
    assert result.totals["treasury_effect"] == pytest.approx(-34_179.6875, abs=1e-4)
    assert result.totals["spread_effect"] == pytest.approx(-9_765.625, abs=1e-4)
    assert result.totals["income_return"] == pytest.approx(0.0, abs=1e-12)
    assert result.totals["selection_effect"] == pytest.approx(545.3125, abs=1e-4)
    assert result.totals["total_return"] == pytest.approx(-43_400.0, abs=1e-4)
    assert result.totals["market_value_start"] == pytest.approx(1_800_000.0, abs=1e-6)


def test_four_effect_decimal_domain_components_match_hand_goldens() -> None:
    """绕开曲线层，直接以手算 Δy/Δ利差喂 compute_bond_four_effects，
    在 Decimal 域锁定分项黄金值——与经曲线层的组合测试互为定位：
    若本测试过而曲线层测试挂，问题在曲线→Δ 的插值/单位腿；反之在四效应公式。
    本 fixture 全链路十进制整除，Decimal 域无任何舍入。
    """
    gov = compute_bond_four_effects(
        _gov_zc_3y(),
        num_days=30,
        benchmark_yield_change=Decimal("0.005"),
        spread_change=Decimal("0"),
        report_date=START_DATE,
    )
    assert gov["treasury_effect"] == pytest.approx(Decimal("-14648.4375"), abs=Decimal("0.0001"))
    assert gov["mod_duration"] == pytest.approx(Decimal("2.9296875"), abs=Decimal("0.0001"))
    assert gov["spread_effect"] == pytest.approx(Decimal("0"), abs=Decimal("1E-12"))
    assert gov["selection_effect"] == pytest.approx(Decimal("248.4375"), abs=Decimal("0.0001"))

    aaa = compute_bond_four_effects(
        _aaa_zc_5y(),
        num_days=30,
        benchmark_yield_change=Decimal("0.005"),
        spread_change=Decimal("0.0025"),
        report_date=START_DATE,
    )
    assert aaa["treasury_effect"] == pytest.approx(Decimal("-19531.25"), abs=Decimal("0.0001"))
    assert aaa["spread_effect"] == pytest.approx(Decimal("-9765.625"), abs=Decimal("0.0001"))
    assert aaa["mod_duration"] == pytest.approx(Decimal("4.8828125"), abs=Decimal("0.0001"))
    assert aaa["selection_effect"] == pytest.approx(Decimal("296.875"), abs=Decimal("0.0001"))
