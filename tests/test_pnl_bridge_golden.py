"""PnL 桥封闭数值黄金测试（backend/app/core_finance/pnl_bridge.py）。

与既有 `test_pnl_bridge_*.py` 的分工：那些用例多为结构断言（分项等于某个入参、
标记等于某个字符串）或依赖仓储夹具自洽；本文件只做一件事——**用独立手算锁死
`build_pnl_bridge_rows` 的分解口径**。每个期望值都在注释里给出可复算的推导，
断言使用精确 `Decimal` 相等（`Decimal.__eq__` 按数值比较，忽略标度差异）。

被锁定的互斥分解恒等式（pnl_bridge.py:251-263）::

    explained_pnl = carry + roll_down + treasury_curve + credit_spread
                    + fx_translation + realized_trading + manual_adjustment
    residual      = actual_pnl - explained_pnl

`unrealized_fv`（516）**不在** explained 内：市场效应本身就是对 516 的解释，
两者同时相加会让 residual 退化为市场效应之和的相反数（审计 PNL-01）。

曲线取值为何可以手算
--------------------
`_curve_rate` 走 `build_full_curve` → `build_curve_points` → 自然三次样条。
`build_full_curve` 恒定输出 13 个期限节点（3M/6M/9M/1Y/2Y/3Y/4Y/5Y/6Y/7Y/10Y/20Y/30Y），
缺失节点由插值/端点钳制补齐，因此节点集与输入无关。若输入曲线在这 13 个节点上
**恰好线性**（r(t) = base + slope·t），则自然三次样条精确复现该直线：
每段 alpha_i = (3/h_i)(slope·h_i) − (3/h_{i-1})(slope·h_{i-1}) = 0 ⇒ c ≡ 0、d ≡ 0、
b_i ≡ slope，于是 S(t) ≡ base + slope·t。本文件所有曲线都用 `_linear_curve`
构造（slope=0 即平坦曲线），故 `_curve_rate(curve, t)` 的期望值可直接手算为
`base + slope·t`，无需复现样条实现。斜率取 0.125（=1/8）、节点年限均为二进制
可精确表示的值，保证浮点中间量无误差。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext

import pytest

from backend.app.core_finance.accounting_basis_constants import ACCOUNTING_BASIS_FVTPL
from backend.app.core_finance.pnl_bridge import (
    _curve_market_value,
    _dirty_market_value,
    _fx_currency_code,
    _modified_duration,
    build_pnl_bridge_rows,
)

# build_full_curve 的固定输出节点及其年限（backend/app/core_finance/bond_analytics/common.py）
_TENOR_YEARS: dict[str, Decimal] = {
    "3M": Decimal("0.25"),
    "6M": Decimal("0.5"),
    "9M": Decimal("0.75"),
    "1Y": Decimal("1"),
    "2Y": Decimal("2"),
    "3Y": Decimal("3"),
    "4Y": Decimal("4"),
    "5Y": Decimal("5"),
    "6Y": Decimal("6"),
    "7Y": Decimal("7"),
    "10Y": Decimal("10"),
    "20Y": Decimal("20"),
    "30Y": Decimal("30"),
}


def _linear_curve(base: str, slope: str = "0") -> dict[str, Decimal]:
    """构造在 build_full_curve 全部节点上精确线性的曲线：r(t) = base + slope·t。

    见模块 docstring：自然三次样条精确复现线性数据，故 `_curve_rate(curve, t)`
    的手算值就是 `Decimal(base) + Decimal(slope) * t`（曲线值为百分数口径）。
    """
    return {
        tenor: Decimal(base) + Decimal(slope) * years for tenor, years in _TENOR_YEARS.items()
    }


def _fact_row(**overrides: object) -> dict:
    """FVTPL 债券 PnL 事实行；金额字段默认 0，由用例按需覆盖。"""
    row: dict = {
        "report_date": "2026-12-31",
        "instrument_code": "GOLDEN-01",
        "portfolio_name": "FI Desk",
        "cost_center": "CC100",
        "accounting_basis": ACCOUNTING_BASIS_FVTPL,
        # PnL 事实的 currency_basis 只有 CNY/CNX 报告口径（pnl.CurrencyBasis）
        "currency_basis": "CNY",
        "interest_income_514": "0",
        "fair_value_change_516": "0",
        "capital_gain_517": "0",
        "manual_adjustment": "0",
        "total_pnl": "0",
    }
    row.update(overrides)
    return row


def _balance_row(report_date: str, **overrides: object) -> dict:
    """利率债余额行；物化 years_to_maturity / modified_duration 以隔离久期估计路径。"""
    row: dict = {
        "report_date": report_date,
        "instrument_code": "GOLDEN-01",
        "portfolio_name": "FI Desk",
        "cost_center": "CC100",
        "currency_basis": "CNY",
        "currency_code": "CNY",
        "accounting_basis": ACCOUNTING_BASIS_FVTPL,
        "years_to_maturity": "5",
        "modified_duration": "4",
        "market_value_amount": "10000000",
        "accrued_interest_amount": "250000",
        "asset_class": "rate",
        "bond_type": "国债",
        "instrument_name": "Golden Treasury Bond",
    }
    row.update(overrides)
    return row


def _credit_balance_row(report_date: str, **overrides: object) -> dict:
    """信用债余额行：classify_asset_class 命中「企业债」→ credit，才会计算利差效应。

    同时保证 infer_curve_type 不命中 CDB 关键词，基准曲线仍走 treasury。
    """
    return _balance_row(
        report_date,
        **{
            "asset_class": "credit",
            "bond_type": "企业债",
            "instrument_name": "Golden Credit Bond",
            **overrides,
        },
    )


# ---------------------------------------------------------------------------
# 1. carry：会计确认利息（514）
# ---------------------------------------------------------------------------


def test_golden_carry_equals_hand_computed_accrual_and_is_a_verbatim_514_passthrough():
    """carry 口径 = 会计确认的利息收入 514 原值，桥不重算应计。

    手算应计（ACT/365，与 fact 表的 514 对齐的经济锚）：
        面值 10,000,000 × 票息 3.65% × 92/365 天
      = 10,000,000 × 0.0365 = 365,000（年息）
      = 365,000 × 92 / 365 = 1,000 × 92 = 92,000.00

    第二个断言把余额行的票息改成 5.00%（若桥自行重算应计将得到 126,027.40），
    carry 仍为 92,000 —— 锁定「carry 取 514、不由持仓字段派生」这一口径。
    """
    face_value = Decimal("10000000")
    coupon_rate = Decimal("0.0365")
    holding_days = Decimal("92")
    day_count_basis = Decimal("365")
    hand_computed_accrual = face_value * coupon_rate * holding_days / day_count_basis
    assert hand_computed_accrual == Decimal("92000")

    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row(interest_income_514="92000", total_pnl="92000")],
        balance_rows_current=[_balance_row("2026-12-31", coupon_rate="5.00")],
        balance_rows_prior=[_balance_row("2025-12-31", coupon_rate="5.00")],
    )

    row = rows[0]
    assert row.carry == hand_computed_accrual
    assert row.carry == Decimal("92000")
    # 无曲线/FX 输入时市场效应为 0，explained 只剩 carry，残差精确闭合。
    assert row.explained_pnl == Decimal("92000")
    assert row.residual == Decimal("0")


# ---------------------------------------------------------------------------
# 2. roll_down：沿当期曲线向下滚动
# ---------------------------------------------------------------------------


def test_golden_roll_down_matches_hand_computed_minus_duration_times_dy_times_mv():
    """roll_down = (r(T) − r(T − 持有年数)) / 100 × D × MV（+D×Δy 形态，与曲线效应反号）。

    输入：当期曲线 r(t) = 2.00 + 0.125·t（百分数）；两期余额行相隔
    2025-12-31 → 2026-12-31 = 365 天；剩余期限 T = 5；修正久期 D = 4；
    市值 MV = 10,000,000（期末净价，见 _curve_market_value）。

    手算：
        rolled_years = 5 − 365/365 = 4
        r(5) = 2.00 + 0.125×5 = 2.625
        r(4) = 2.00 + 0.125×4 = 2.500
        Δy   = (2.625 − 2.500) / 100 = 0.00125
        roll_down = +0.00125 × 4 × 10,000,000 = 50,000

    符号校验：上斜曲线下滚 ⇒ 到期收益率下行 ⇒ 价格上行 ⇒ 正贡献。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[_balance_row("2026-12-31")],
        # 期初市值特意设成 1，证明滚动效应不使用期初口径。
        balance_rows_prior=[_balance_row("2025-12-31", market_value_amount="1")],
        treasury_curve_current=_linear_curve("2.00", "0.125"),
        # 曲线效应需要两期曲线；此处给同一条曲线以隔离出纯滚动效应。
        treasury_curve_prior=_linear_curve("2.00", "0.125"),
    )

    row = rows[0]
    assert row.roll_down == Decimal("50000")
    assert row.treasury_curve == Decimal("0")
    assert row.credit_spread == Decimal("0")
    assert row.explained_pnl == Decimal("50000")


def test_golden_roll_down_scales_with_balance_row_day_count_not_the_fact_report_date():
    """持有天数取自两期余额行 report_date 之差（_period_days），天数翻倍则滚动效应翻倍。

    2024-12-31 → 2026-12-31 = 730 天（2025、2026 均非闰年）：
        rolled_years = 5 − 730/365 = 3
        r(5) − r(3) = 2.625 − 2.375 = 0.25
        Δy = 0.0025；roll_down = 0.0025 × 4 × 10,000,000 = 100,000
    正好是 365 天情形（50,000）的两倍。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[_balance_row("2026-12-31")],
        balance_rows_prior=[_balance_row("2024-12-31", market_value_amount="1")],
        treasury_curve_current=_linear_curve("2.00", "0.125"),
        treasury_curve_prior=_linear_curve("2.00", "0.125"),
    )

    assert rows[0].roll_down == Decimal("100000")


def test_golden_roll_down_requires_prior_balance_while_curve_shift_does_not():
    """口径不对称（如实锁定）：缺期初余额行时 roll_down 归零，但曲线效应照算。

    `_calculate_roll_down` 在 prior_balance is None 或 period_days <= 0 时返回 0；
    `_calculate_curve_shift` 只依赖期末余额行与两期曲线，因此同一行会出现
    「有曲线效应、无滚动效应」的半截分解，残差把缺口全部吸收。

    手算曲线效应（当期 2.00+0.125t，上期 1.90+0.125t）：
        r_cur(5) − r_pri(5) = 2.625 − 2.525 = 0.10
        treasury_curve = −(0.10/100 × 4 × 10,000,000) = −40,000
    """
    curves = {
        "treasury_curve_current": _linear_curve("2.00", "0.125"),
        "treasury_curve_prior": _linear_curve("1.90", "0.125"),
    }

    missing_prior = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[_balance_row("2026-12-31")],
        balance_rows_prior=[],
        **curves,
    )[0]
    assert missing_prior.roll_down == Decimal("0")
    assert missing_prior.treasury_curve == Decimal("-40000")

    same_day_prior = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[_balance_row("2026-12-31")],
        # 期初与期末同日 ⇒ period_days = 0 ⇒ 滚动效应归零。
        balance_rows_prior=[_balance_row("2026-12-31")],
        **curves,
    )[0]
    assert same_day_prior.roll_down == Decimal("0")
    assert same_day_prior.treasury_curve == Decimal("-40000")

    # 口径不对称本身不改（业务裁决），但半截分解必须可感知：两种情形都要有
    # 专门的行级诊断，而不只是通用的 "Missing prior balance row"。
    for row in (missing_prior, same_day_prior):
        assert any(
            "ROLL_DOWN_WINDOW_MISSING" in message for message in row.balance_diagnostics
        )
    assert any("prior balance row unavailable" in m for m in missing_prior.balance_diagnostics)
    assert any("period_days=0" in m for m in same_day_prior.balance_diagnostics)


# ---------------------------------------------------------------------------
# 3. treasury_curve：基准曲线平移
# ---------------------------------------------------------------------------


def test_golden_treasury_curve_shift_matches_hand_computed_minus_duration_times_dy_times_mv():
    """treasury_curve = −(r_cur(T) − r_pri(T)) / 100 × D × MV。

    两期均用平坦曲线以彻底消除滚动效应（同一条平坦曲线上 r(T) ≡ r(T−1)）：
        当期 3.20%、上期 2.95%，T = 5，D = 4.5，MV = 20,000,000
        Δy = (3.20 − 2.95) / 100 = 0.0025
        treasury_curve = −(0.0025 × 4.5 × 20,000,000) = −225,000

    符号校验：收益率上行 25bp ⇒ 价格下跌 ⇒ 负贡献。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[
            _balance_row("2026-12-31", modified_duration="4.5", market_value_amount="20000000")
        ],
        balance_rows_prior=[
            _balance_row("2025-12-31", modified_duration="4.5", market_value_amount="20000000")
        ],
        treasury_curve_current=_linear_curve("3.20"),
        treasury_curve_prior=_linear_curve("2.95"),
    )

    row = rows[0]
    assert row.roll_down == Decimal("0")
    assert row.treasury_curve == Decimal("-225000")
    assert row.credit_spread == Decimal("0")


# ---------------------------------------------------------------------------
# 4. credit_spread：AAA 企业曲线相对基准曲线的利差变动
# ---------------------------------------------------------------------------


def test_golden_credit_spread_matches_hand_computed_minus_duration_times_dspread_times_mv():
    """credit_spread = −((AAA_cur − 基准_cur) − (AAA_pri − 基准_pri)) / 100 × D × MV。

    两期基准曲线均为平坦 3.00%（消除滚动与曲线效应），AAA 曲线 3.80% → 3.50%
    倒推为：当期利差 0.80%、上期利差 0.50%，T = 5，D = 3，MV = 5,000,000。

    手算：
        当期利差 = 3.80 − 3.00 = 0.80
        上期利差 = 3.50 − 3.00 = 0.50
        Δspread  = (0.80 − 0.50) / 100 = 0.003
        credit_spread = −(0.003 × 3 × 5,000,000) = −45,000

    符号校验：利差走阔 30bp ⇒ 信用债价格下跌 ⇒ 负贡献。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[
            _credit_balance_row(
                "2026-12-31", modified_duration="3", market_value_amount="5000000"
            )
        ],
        balance_rows_prior=[
            _credit_balance_row(
                "2025-12-31", modified_duration="3", market_value_amount="5000000"
            )
        ],
        treasury_curve_current=_linear_curve("3.00"),
        treasury_curve_prior=_linear_curve("3.00"),
        aaa_credit_curve_current=_linear_curve("3.80"),
        aaa_credit_curve_prior=_linear_curve("3.50"),
    )

    row = rows[0]
    assert row.roll_down == Decimal("0")
    assert row.treasury_curve == Decimal("0")
    assert row.credit_spread == Decimal("-45000")


def test_golden_credit_spread_is_zero_for_rate_rows_even_with_aaa_curves_supplied():
    """利率债行（classify_asset_class != credit）即便提供了 AAA 曲线也不产生利差效应。"""
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[
            _balance_row("2026-12-31", modified_duration="3", market_value_amount="5000000")
        ],
        balance_rows_prior=[
            _balance_row("2025-12-31", modified_duration="3", market_value_amount="5000000")
        ],
        treasury_curve_current=_linear_curve("3.00"),
        treasury_curve_prior=_linear_curve("3.00"),
        aaa_credit_curve_current=_linear_curve("3.80"),
        aaa_credit_curve_prior=_linear_curve("3.50"),
    )

    assert rows[0].credit_spread == Decimal("0")


# ---------------------------------------------------------------------------
# 5. 市值口径：期末净价（审计 Medium — 与四效应的期初口径不一致，如实锁定）
# ---------------------------------------------------------------------------


def test_golden_curve_effects_use_ending_clean_market_value_not_beginning_or_dirty():
    """如实锁定审计 Medium 指出的口径偏差。

    `_curve_market_value` 只取**期末**余额行的 `market_value_amount`（净价，不含
    应计），而 bond_four_effects 等四效应模块以**期初**市值为基数。本用例把
    期初市值设为期末的 10 倍、期末应计设为 5,000,000，三项效应的基数仍严格是
    期末净价 10,000,000：

        期末净价 MV     = 10,000,000  → 效应基数（实际口径）
        期末脏价        = 15,000,000  → 未被采用（ending_dirty_mv 字段仅用于展示）
        期初净价        = 100,000,000 → 未被采用（四效应口径会用到）

    手算（当期 2.00+0.125t / 上期 1.90+0.125t，T=5，D=4，365 天）：
        roll_down      = +(2.625 − 2.500)/100 × 4 × 10,000,000 = +50,000
        treasury_curve = −(2.625 − 2.525)/100 × 4 × 10,000,000 = −40,000
    若误用期末脏价将得到 +75,000 / −60,000；误用期初净价将得到 +500,000 / −400,000。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[
            _balance_row(
                "2026-12-31",
                market_value_amount="10000000",
                accrued_interest_amount="5000000",
            )
        ],
        balance_rows_prior=[
            _balance_row(
                "2025-12-31",
                market_value_amount="100000000",
                accrued_interest_amount="0",
            )
        ],
        treasury_curve_current=_linear_curve("2.00", "0.125"),
        treasury_curve_prior=_linear_curve("1.90", "0.125"),
    )

    row = rows[0]
    assert row.roll_down == Decimal("50000")
    assert row.treasury_curve == Decimal("-40000")
    # 展示口径仍是脏价，与效应基数（净价）不是同一个数。
    assert row.ending_dirty_mv == Decimal("15000000")
    assert row.beginning_dirty_mv == Decimal("100000000")


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        # 1. 首选键有值 → 直接采用，不看后续级别
        ({"market_value_amount": "7", "market_value_native": "99"}, "7"),
        # 2. 首选键值为 None（可空列落 NULL）→ 回退到第二级
        ({"market_value_amount": None, "market_value": "1000000"}, "1000000"),
        # 3. 前两级都是 None → 回退到第三级
        (
            {"market_value_amount": None, "market_value": None, "market_value_native": "1000000"},
            "1000000",
        ),
        # 4. 首选键值为空串（同属 NULL 语义）→ 继续回退
        ({"market_value_amount": "", "market_value_native": "1000000"}, "1000000"),
        # 5. 键真正缺失 → 回退（修复前唯一生效的分支）
        ({"market_value_native": "1000000"}, "1000000"),
        # 6. 三级全空 → 归零（真回退链走到底）
        ({"market_value_amount": None, "market_value": None, "market_value_native": None}, "0"),
        # 7. 键全缺失 → 归零
        ({}, "0"),
        # 8. 首选键为真实 0（无持仓）→ 采用 0，不得误回退到后续级别
        ({"market_value_amount": "0", "market_value_native": "1000000"}, "0"),
    ],
)
def test_golden_curve_market_value_falls_back_through_null_valued_keys(row, expected):
    """`_curve_market_value` 的三级回退必须对 None/空串生效，而不只是对缺键生效。

    修复前写成 `row.get("market_value_amount", row.get("market_value",
    row.get("market_value_native", 0)))`：`dict.get(key, default)` 只在**键缺失**时
    返回 default，键存在而值为 None 时直接返回 None。`market_value_amount` 是可空列，
    生产中落 NULL 即让回退链失效，市值基数取 0，三项市场效应静默归零。
    第 8 个用例锁定反向边界：真实 0 是"无持仓"，不是"不可用"，不得继续回退。
    """
    assert _curve_market_value(row) == Decimal(expected)


def test_golden_curve_effects_fall_back_to_native_market_value_when_amount_is_null():
    """端到端：`market_value_amount` 落 NULL 时，效应基数回退到 `market_value_native`。

    与 test_golden_curve_effects_use_ending_clean_market_value_not_beginning_or_dirty
    同一组曲线与久期，仅把期末市值从 `market_value_amount` 挪到 `market_value_native`，
    手算结果必须完全一致：
        roll_down      = +(2.625 − 2.500)/100 × 4 × 10,000,000 = +50,000
        treasury_curve = −(2.625 − 2.525)/100 × 4 × 10,000,000 = −40,000
    修复前两项均为 0（缺陷现场），且无任何诊断。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[
            _balance_row("2026-12-31", market_value_amount=None, market_value_native="10000000")
        ],
        balance_rows_prior=[_balance_row("2025-12-31")],
        treasury_curve_current=_linear_curve("2.00", "0.125"),
        treasury_curve_prior=_linear_curve("1.90", "0.125"),
    )

    row = rows[0]
    assert row.roll_down == Decimal("50000")
    assert row.treasury_curve == Decimal("-40000")
    # 基数可用 ⇒ 不得报"市值基数缺失"。
    assert not any("MARKET_VALUE_BASE_MISSING" in message for message in row.balance_diagnostics)


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        # 首选键均有值：脏价 = 净价 + 应计
        ({"market_value_amount": "100", "accrued_interest_amount": "5"}, "105"),
        # 两条链的首选键都落 NULL → 各自回退到 native
        (
            {
                "market_value_amount": None,
                "market_value_native": "100",
                "accrued_interest_amount": None,
                "accrued_interest_native": "5",
            },
            "105",
        ),
        # 只有市值链落 NULL，应计链正常取首选键
        (
            {
                "market_value_amount": None,
                "market_value": "100",
                "accrued_interest_amount": "5",
                "accrued_interest_native": "999",
            },
            "105",
        ),
        # 两条链全空 → 归零
        ({"market_value_amount": None, "accrued_interest_amount": None}, "0"),
    ],
)
def test_golden_dirty_market_value_falls_back_through_null_valued_keys(row, expected):
    """`_dirty_market_value`（FX 敞口/展示口径用）与 `_curve_market_value` 同一写法、同一风险。

    市值链与应计链都必须在键存在但值为 None 时继续回退，否则期初/期末脏市值
    在可空列落 NULL 时被低估（展示口径失真），且返回类型仍须是 Decimal。
    """
    assert _dirty_market_value(row) == Decimal(expected)


# ---------------------------------------------------------------------------
# 5b. 静默归零的行级诊断（与 FX_RATE_MISSING 同一机制：balance_diagnostics）
# ---------------------------------------------------------------------------


def test_golden_market_effects_zeroed_by_missing_market_value_base_are_diagnosed():
    """三级市值全空 ⇒ 市场效应归零，且必须报出 MARKET_VALUE_BASE_MISSING。

    这是任务 A 修完真回退链之后仍然存在的归零路径：余额行的
    market_value_amount / market_value / market_value_native 全部缺失或为 NULL 时
    效应基数为 0，缺口被残差吸收。若无诊断则与"本期确实没有曲线效应"无法区分。

    输入行仍然满足其余全部前提（期末余额行存在、基准曲线存在、T=5>0、D=4≠0），
    所以归零的唯一原因就是市值基数不可用。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row(fair_value_change_516="-40000", total_pnl="-40000")],
        balance_rows_current=[
            _credit_balance_row(
                "2026-12-31",
                market_value_amount=None,
                market_value=None,
                market_value_native=None,
            )
        ],
        balance_rows_prior=[_credit_balance_row("2025-12-31")],
        treasury_curve_current=_linear_curve("2.00", "0.125"),
        treasury_curve_prior=_linear_curve("1.90", "0.125"),
        aaa_credit_curve_current=_linear_curve("2.80", "0.125"),
        aaa_credit_curve_prior=_linear_curve("2.60", "0.125"),
    )

    row = rows[0]
    assert row.roll_down == Decimal("0")
    assert row.treasury_curve == Decimal("0")
    assert row.credit_spread == Decimal("0")
    diagnostic = next(
        message for message in row.balance_diagnostics if "MARKET_VALUE_BASE_MISSING" in message
    )
    # 诊断必须点名三个来源字段与被归零的三项效应，运维才能定位到落库列。
    for token in (
        "market_value_amount",
        "market_value_native",
        "roll_down",
        "treasury_curve",
        "credit_spread",
    ):
        assert token in diagnostic
    # 缺口如实落在残差里，与诊断互为印证。
    assert row.residual == Decimal("-40000")


def test_golden_zero_market_value_is_not_reported_as_missing_base():
    """反向边界：市值真实为 0（无持仓）不是"基数不可用"，不得产生诊断。

    否则清仓行会在每期刷屏，诊断退化为噪音。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[_balance_row("2026-12-31", market_value_amount="0")],
        balance_rows_prior=[_balance_row("2025-12-31")],
        treasury_curve_current=_linear_curve("2.00", "0.125"),
        treasury_curve_prior=_linear_curve("1.90", "0.125"),
    )

    row = rows[0]
    assert row.roll_down == Decimal("0")
    assert row.treasury_curve == Decimal("0")
    assert row.balance_diagnostics == ()


def test_golden_roll_down_window_diagnostic_is_scoped_to_actually_zeroed_rows():
    """滚动窗口诊断只在 roll_down 确实"本可非零却被窗口归零"时出现。

    三个负向场景各自锁定一个前置条件，避免诊断泛滥：
    - 窗口完整（相隔 365 天）⇒ roll_down 非零，无诊断
    - 无基准曲线 ⇒ 三项效应本就全零，窗口不是原因，无诊断
    - 非 FVTPL 行 ⇒ 市场效应整体不适用（审计 PNL-02），无诊断
    - 市值基数不可用 ⇒ 归零主因已由 MARKET_VALUE_BASE_MISSING 报出，不重复报
    """
    curves = {
        "treasury_curve_current": _linear_curve("2.00", "0.125"),
        "treasury_curve_prior": _linear_curve("1.90", "0.125"),
    }

    healthy = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[_balance_row("2026-12-31")],
        balance_rows_prior=[_balance_row("2025-12-31")],
        **curves,
    )[0]
    assert healthy.roll_down == Decimal("50000")
    assert healthy.balance_diagnostics == ()

    no_curve = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[_balance_row("2026-12-31")],
        balance_rows_prior=[],
    )[0]
    assert no_curve.roll_down == Decimal("0")
    assert not any("ROLL_DOWN_WINDOW_MISSING" in m for m in no_curve.balance_diagnostics)

    non_fvtpl = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row(accounting_basis="AC")],
        balance_rows_current=[_balance_row("2026-12-31", accounting_basis="AC")],
        balance_rows_prior=[],
        **curves,
    )[0]
    assert non_fvtpl.roll_down == Decimal("0")
    assert not any("ROLL_DOWN_WINDOW_MISSING" in m for m in non_fvtpl.balance_diagnostics)

    # 窗口与市值基数同时缺失：只报主因，两条诊断不叠加成噪音。
    no_base_no_window = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[_balance_row("2026-12-31", market_value_amount=None)],
        balance_rows_prior=[],
        **curves,
    )[0]
    assert no_base_no_window.roll_down == Decimal("0")
    assert any("MARKET_VALUE_BASE_MISSING" in m for m in no_base_no_window.balance_diagnostics)
    assert not any(
        "ROLL_DOWN_WINDOW_MISSING" in m for m in no_base_no_window.balance_diagnostics
    )


# ---------------------------------------------------------------------------
# 6. fx_translation：外币折算
# ---------------------------------------------------------------------------


def test_golden_fx_translation_matches_hand_computed_native_exposure_times_rate_delta():
    """外币行（currency_basis=CNY + currency_code=USD）折算损益 = 原币敞口 × Δ中间价。

    余额行来自 CNY 口径投影，`market_value_amount` 已折 CNY，不能再乘汇率差；
    原币敞口取服务层富集的 market_value_native + accrued_interest_native。

    手算：
        原币脏敞口 = 1,200,000 + 50,000 = 1,250,000 USD
        Δ中间价    = 7.1234 − 7.0834 = 0.0400
        fx_translation = 1,250,000 × 0.0400 = 50,000.00000000 CNY
    误用折 CNY 市值（8,904,250）会得到 356,170，放大约一个汇率倍数。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row(total_pnl="50000")],
        balance_rows_current=[
            _balance_row(
                "2026-12-31",
                currency_code="USD",
                market_value_amount="8904250",
                accrued_interest_amount="0",
                market_value_native="1200000",
                accrued_interest_native="50000",
                face_value_native="1100000",
            )
        ],
        balance_rows_prior=[],
        fx_rates_current={"USD": Decimal("7.1234")},
        fx_rates_prior={"USD": Decimal("7.0834")},
    )

    row = rows[0]
    assert row.fx_translation == Decimal("50000")
    assert row.explained_pnl == Decimal("50000")
    assert row.residual == Decimal("0")
    assert not any("FX_RATE_MISSING" in message for message in row.balance_diagnostics)
    # 残差闭合（ratio=0）本身给出 "ok"，但本用例没喂曲线，而这是一行 FVTPL、
    # 剩余期限 5 年、久期 4 的可计算行：它的 treasury_curve=0 是"没有曲线"而不是
    # "利率没动"，因此标记被升级为 warning 并附带原因。
    assert row.residual_ratio == Decimal("0")
    assert row.quality_flag == "warning"
    assert any(
        message.startswith("TREASURY_CURVE_UNAVAILABLE") for message in row.balance_diagnostics
    )


def test_golden_fx_translation_quantizes_to_eight_decimals_half_up():
    """fx_translation 是唯一带量化的分项：8 位小数、ROUND_HALF_UP。

    手算：3 USD × (7.000000005 − 7.000000000) = 0.000000015
          → 8 位小数正好落在半档上，HALF_UP 进位为 0.00000002
    其余分项（carry/曲线三项/517/手工调整）不量化，保持入参精度。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[
            _balance_row(
                "2026-12-31",
                currency_code="USD",
                market_value_native="3",
                accrued_interest_native="0",
            )
        ],
        balance_rows_prior=[],
        fx_rates_current={"USD": Decimal("7.000000005")},
        fx_rates_prior={"USD": Decimal("7.000000000")},
    )

    assert rows[0].fx_translation == Decimal("0.00000002")


@pytest.mark.parametrize(
    ("row", "fallback", "expected"),
    [
        # 1. 余额行 currency_code 最高优先级，压过同一行的 currency_basis
        ({"currency_code": "USD", "currency_basis": "CNY"}, "JPY", "USD"),
        # 2. currency_code 为 None → 退到余额行 currency_basis
        ({"currency_code": None, "currency_basis": "EUR"}, "JPY", "EUR"),
        # 3. currency_code 为空串 → 同样退到余额行 currency_basis
        ({"currency_code": "", "currency_basis": "EUR"}, "JPY", "EUR"),
        # 4. currency_code 键缺失 → 退到余额行 currency_basis
        ({"currency_basis": "HKD"}, "JPY", "HKD"),
        # 5. 余额行两个币种字段都为空 → 退到 fact 行 currency_basis
        ({"currency_code": "", "currency_basis": ""}, "JPY", "JPY"),
        # 6. 余额行两个键都缺失 → 退到 fact 行 currency_basis
        ({}, "JPY", "JPY"),
        # 7. 余额行缺失 → 退到 fact 行 currency_basis
        (None, "JPY", "JPY"),
    ],
)
def test_golden_fx_currency_code_resolution_priority_chain(row, fallback, expected):
    """锁定 `_fx_currency_code` 的解析优先级链（近期 High 修复点）。

    余额行 currency_code → 余额行 currency_basis → fact 行 currency_basis。
    修复前直接用 fact 的 currency_basis，而它只有 CNY/CNX 报告口径
    （pnl.CurrencyBasis），永远识别不出外币，全部外币折算损益静默归零。
    """
    assert _fx_currency_code(row, fallback=fallback) == expected


def test_golden_fx_currency_code_fix_is_observable_end_to_end():
    """端到端锁定修复：fact 行 currency_basis=CNY，靠余额行 currency_code=USD 才有折算。

    同一组输入下：
    - currency_code="USD" → 1,000 × (7.10 − 7.00) = 100.00000000
    - currency_code="CNY" → 本币行，走完 FX 分支后为 0（修复前的塌缩行为）
    """
    def _run(currency_code: str) -> Decimal:
        rows = build_pnl_bridge_rows(
            pnl_fi_rows=[_fact_row()],
            balance_rows_current=[
                _balance_row(
                    "2026-12-31",
                    currency_code=currency_code,
                    market_value_native="1000",
                    accrued_interest_native="0",
                )
            ],
            balance_rows_prior=[],
            fx_rates_current={"USD": Decimal("7.10")},
            fx_rates_prior={"USD": Decimal("7.00")},
        )
        return rows[0].fx_translation

    assert _run("USD") == Decimal("100")
    assert _run("CNY") == Decimal("0")


# ---------------------------------------------------------------------------
# 7. 全分解闭合
# ---------------------------------------------------------------------------


def test_golden_full_decomposition_closes_exactly_on_a_self_consistent_credit_row():
    """综合黄金用例：七项分解 + 残差在自洽行上精确闭合。

    输入（FVTPL 信用债，2025-12-31 → 2026-12-31 共 365 天，T=5，D=4，期末净价 10,000,000）：
        基准曲线 当期 2.00+0.125t / 上期 1.90+0.125t
        AAA 曲线 当期 2.80+0.125t / 上期 2.60+0.125t
        514 = 92,000（= 10,000,000 × 3.65% × 92/365）
        516 = −26,000（被解释对象，不计入 explained）
        517 = 30,000；手工调整 = 4,000
        total_pnl = 92,000 + (−26,000) + 30,000 + 4,000 = 100,000（会计自洽）

    逐项手算：
        r_cur(5)=2.625  r_cur(4)=2.500  r_pri(5)=2.525
        aaa_cur(5)=3.425  aaa_pri(5)=3.225
        roll_down      = +(2.625−2.500)/100 × 4 × 10,000,000 = +50,000
        treasury_curve = −(2.625−2.525)/100 × 4 × 10,000,000 = −40,000
        当期利差 = 3.425 − 2.625 = 0.80；上期利差 = 3.225 − 2.525 = 0.70
        credit_spread  = −(0.80−0.70)/100 × 4 × 10,000,000  = −40,000
        fx_translation = 0（本币行）
        explained = 92,000 + 50,000 − 40,000 − 40,000 + 0 + 30,000 + 4,000 = 96,000
        residual  = 100,000 − 96,000 = 4,000
        residual_ratio = 4,000 / 100,000 = 0.04 < 0.05 ⇒ quality_flag = "ok"

    互斥分解交叉校验：residual 也应等于「516 − 市场效应之和」
        = −26,000 − (50,000 − 40,000 − 40,000) = −26,000 + 30,000 = 4,000 ✓
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            _fact_row(
                interest_income_514="92000",
                fair_value_change_516="-26000",
                capital_gain_517="30000",
                manual_adjustment="4000",
                total_pnl="100000",
            )
        ],
        balance_rows_current=[_credit_balance_row("2026-12-31")],
        balance_rows_prior=[
            _credit_balance_row(
                "2025-12-31", market_value_amount="9000000", accrued_interest_amount="200000"
            )
        ],
        treasury_curve_current=_linear_curve("2.00", "0.125"),
        treasury_curve_prior=_linear_curve("1.90", "0.125"),
        aaa_credit_curve_current=_linear_curve("2.80", "0.125"),
        aaa_credit_curve_prior=_linear_curve("2.60", "0.125"),
    )

    row = rows[0]
    assert row.carry == Decimal("92000")
    assert row.roll_down == Decimal("50000")
    assert row.treasury_curve == Decimal("-40000")
    assert row.credit_spread == Decimal("-40000")
    assert row.fx_translation == Decimal("0")
    assert row.realized_trading == Decimal("30000")
    assert row.manual_adjustment == Decimal("4000")
    assert row.unrealized_fv == Decimal("-26000")

    assert row.explained_pnl == Decimal("96000")
    assert row.actual_pnl == Decimal("100000")
    assert row.residual == Decimal("4000")
    assert row.residual_ratio == Decimal("0.04")
    assert row.quality_flag == "ok"

    market_effects = row.roll_down + row.treasury_curve + row.credit_spread + row.fx_translation
    assert market_effects == Decimal("-30000")
    assert row.residual == row.unrealized_fv - market_effects

    # 展示口径的脏市值与效应基数（期末净价）分别锁定。
    assert row.beginning_dirty_mv == Decimal("9200000")
    assert row.ending_dirty_mv == Decimal("10250000")
    assert row.balance_diagnostics == ()


def test_golden_residual_closure_is_exact_at_eight_decimal_places():
    """残差恒等式在 8 位小数量级上精确成立，不引入浮点污染。

    手算（AC 行，市场效应全零，explained 只由会计分项构成）：
        explained = 12,345.67890123 + 456.78901234 + (−12.34567890) = 12,790.12223467
        residual  = 11,802.46791367 − 12,790.12223467 = −987.65432100
    交叉校验：AC 行 explained 不含 516，残差应恰好等于 516 = −987.65432100。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            _fact_row(
                accounting_basis="AC",
                interest_income_514="12345.67890123",
                fair_value_change_516="-987.65432100",
                capital_gain_517="456.78901234",
                manual_adjustment="-12.34567890",
                total_pnl="11802.46791367",
            )
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    row = rows[0]
    assert row.explained_pnl == Decimal("12790.12223467")
    assert row.residual == Decimal("-987.65432100")
    assert row.residual == row.unrealized_fv
    # 分解恒等式（pnl_bridge.py:251-263）逐字复算。
    assert row.explained_pnl == (
        row.carry
        + row.roll_down
        + row.treasury_curve
        + row.credit_spread
        + row.fx_translation
        + row.realized_trading
        + row.manual_adjustment
    )
    assert row.residual == row.actual_pnl - row.explained_pnl


def test_golden_explained_pnl_excludes_unrealized_fv_516():
    """互斥分解（审计 PNL-01）：516 永不进入 explained。

    514=100、516=1,000、517=0、手工=0、total=1,100：
        explained = 100（若错误纳入 516 则为 1,100，残差被抹平为 0）
        residual  = 1,100 − 100 = 1,000 = 516
        ratio     = 1,000 / 1,100 ≈ 0.909 ⇒ error（质量标记必须诚实报警）
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            _fact_row(
                interest_income_514="100",
                fair_value_change_516="1000",
                total_pnl="1100",
            )
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    row = rows[0]
    assert row.explained_pnl == Decimal("100")
    assert row.explained_pnl != row.explained_pnl + row.unrealized_fv
    assert row.residual == Decimal("1000")
    assert row.quality_flag == "error"


# ---------------------------------------------------------------------------
# 8. quality_flag 分级边界（5% / 10%）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("carry", "total_pnl", "expected_residual", "expected_ratio", "expected_flag"),
    [
        # |ratio| < 0.05 → ok（4.99/100 = 0.0499，紧贴边界内侧）
        ("95.01", "100.00", "4.99", "0.0499", "ok"),
        # |ratio| == 0.05 → warning（`< 0.05` 为假，落入下一档）
        ("95.00", "100.00", "5.00", "0.05", "warning"),
        # 0.05 <= |ratio| < 0.10 → warning
        ("91.00", "100.00", "9.00", "0.09", "warning"),
        # |ratio| == 0.10 → error（`< 0.10` 为假）
        ("90.00", "100.00", "10.00", "0.10", "error"),
        # 负残差按绝对值分级：−5/100 = −0.05 → warning
        ("105.00", "100.00", "-5.00", "-0.05", "warning"),
        # 负残差 −10/100 = −0.10 → error
        ("110.00", "100.00", "-10.00", "-0.10", "error"),
        # 实际损益为负时 ratio = 残差/实际，符号随分母翻转：−10/−100 = +0.10 → error
        ("-90.00", "-100.00", "-10.00", "0.10", "error"),
        # 实际损益为负、残差为正：5/−100 = −0.05 → warning
        ("-105.00", "-100.00", "5.00", "-0.05", "warning"),
    ],
)
def test_golden_quality_flag_threshold_boundaries(
    carry, total_pnl, expected_residual, expected_ratio, expected_flag
):
    """锁定 `_quality_flag` 的闭开区间：|ratio| ∈ [0,0.05) ok、[0.05,0.10) warning、[0.10,∞) error。

    阈值本身是**闭下开上**：恰好 5% 记 warning、恰好 10% 记 error，
    且分级取 |ratio|，与残差/实际损益的正负号无关。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            _fact_row(accounting_basis="AC", interest_income_514=carry, total_pnl=total_pnl)
        ],
        balance_rows_current=[],
        balance_rows_prior=[],
    )

    row = rows[0]
    assert row.residual == Decimal(expected_residual)
    assert row.residual_ratio == Decimal(expected_ratio)
    assert row.quality_flag == expected_flag


# ---------------------------------------------------------------------------
# 9. 非 FVTPL 行的市场效应归零分支
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("accounting_basis", ["AC", "FVOCI", "OCI", ""])
def test_golden_non_fvtpl_rows_zero_all_four_market_effects(accounting_basis):
    """非 FVTPL 行（审计 PNL-02）：四项市场效应全部归零，explained 只剩会计分项。

    喂入的曲线/FX 输入若参与计算会产生量级巨大的效应
    （曲线平移 −(0.25/100 × 4 × 10,000,000) = −100,000；
      利差走阔 −(0.30/100 × 4 × 10,000,000) = −120,000；
      折算 1,000 × 0.04 = 40），本用例断言它们一律为 0。

    手算 explained = 514 + 517 + 手工调整 = 1,000 + 200 + 50 = 1,250
        total_pnl = 1,250 ⇒ residual = 0 ⇒ quality_flag = "ok"
    （516 = −77 两侧都不出现：非 FVTPL 的 516 已在正式事实门控中剔除。）
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[
            _fact_row(
                accounting_basis=accounting_basis,
                interest_income_514="1000",
                fair_value_change_516="-77",
                capital_gain_517="200",
                manual_adjustment="50",
                total_pnl="1250",
            )
        ],
        balance_rows_current=[
            _credit_balance_row(
                "2026-12-31",
                accounting_basis=accounting_basis,
                currency_code="USD",
                market_value_native="1000",
                accrued_interest_native="0",
            )
        ],
        balance_rows_prior=[
            _credit_balance_row("2025-12-31", accounting_basis=accounting_basis)
        ],
        treasury_curve_current=_linear_curve("3.20"),
        treasury_curve_prior=_linear_curve("2.95"),
        aaa_credit_curve_current=_linear_curve("3.80"),
        aaa_credit_curve_prior=_linear_curve("3.50"),
        fx_rates_current={"USD": Decimal("7.10")},
        fx_rates_prior={"USD": Decimal("7.06")},
    )

    row = rows[0]
    assert row.roll_down == Decimal("0")
    assert row.treasury_curve == Decimal("0")
    assert row.credit_spread == Decimal("0")
    assert row.fx_translation == Decimal("0")
    assert row.explained_pnl == Decimal("1250")
    assert row.residual == Decimal("0")
    assert row.quality_flag == "ok"
    # 分支被整体跳过，FX 诊断也不会产生（见下一用例的口径说明）。
    assert not any("FX_RATE_MISSING" in message for message in row.balance_diagnostics)


def test_golden_non_fvtpl_foreign_row_gets_no_fx_missing_diagnostic_even_without_rates():
    """如实锁定：非 FVTPL 外币行缺 FX 字典时也不会出 FX_RATE_MISSING 诊断。

    `_fx_rate_missing_diagnostic` 只在 include_market_effects 分支内调用，
    非 FVTPL 行直接置 None。对比同样缺 FX 字典的 FVTPL 外币行会被标记。
    该差异是「非 FVTPL 无市场效应」口径的自然结果，但意味着 AC/FVOCI 账簿上
    的外币敞口不会在桥的诊断里留下任何痕迹。
    """
    def _diagnostics(accounting_basis: str) -> tuple[str, ...]:
        rows = build_pnl_bridge_rows(
            pnl_fi_rows=[_fact_row(accounting_basis=accounting_basis)],
            balance_rows_current=[
                _balance_row(
                    "2026-12-31",
                    accounting_basis=accounting_basis,
                    currency_code="USD",
                    market_value_native="1000",
                    accrued_interest_native="0",
                )
            ],
            balance_rows_prior=[],
            fx_rates_current=None,
            fx_rates_prior=None,
        )
        return rows[0].balance_diagnostics

    assert any("FX_RATE_MISSING" in message and "USD" in message for message in _diagnostics("FVTPL"))
    assert not any("FX_RATE_MISSING" in message for message in _diagnostics("AC"))


# ---------------------------------------------------------------------------
# 10. _modified_duration 回退路径的百分数归一（近期 Critical 修复点）
# ---------------------------------------------------------------------------


def test_golden_modified_duration_fallback_normalizes_percent_rates_to_decimal():
    """余额行缺物化久期时回退重算，coupon/ytm 必须从百分数归一为小数。

    输入：report 2025-12-31、到期 2030-12-31、coupon = ytm = 2.38（落库百分数口径）。

    独立手算（平价券闭式，与实现的现金流循环相互独立）：
        剩余天数 = 1,826，years = 1826/365 = 5.00273972...，
        小数期 0.0027... ≤ 0.01 ⇒ compute_macaulay_duration 收敛到整 5 期年付。
        平价券（c = y）价格恒为 1，Macaulay 有闭式：
            D_mac = (1+y)/y × (1 − (1+y)^-n)，y = 0.0238，n = 5
                  = 43.0168067227 × (1 − 1.1248008247^-1)
                  = 43.0168067227 × 0.1109537104
                  = 4.7728743029...
            D_mod = D_mac / (1 + y) = 4.7728743029 / 1.0238 = 4.6619205929...
    实现返回 4.661920592874661174880811256，与闭式差 ~2.7e-17（Decimal 精度残差）。

    回归锚：未归一（把 2.38 当作 238%）时结果塌缩到约 0.42，断言 > 4 锁死该缺陷。
    """
    duration = _modified_duration(
        report_date=date(2025, 12, 31),
        row={
            "maturity_date": "2030-12-31",
            "coupon_rate": Decimal("2.38"),
            "ytm_value": Decimal("2.38"),
            "instrument_code": "GOLDEN-DUR.IB",
        },
    )

    with localcontext() as ctx:
        ctx.prec = 40
        ytm = Decimal("0.0238")
        periods = 5
        closed_form_macaulay = (
            (Decimal("1") + ytm) / ytm * (Decimal("1") - (Decimal("1") + ytm) ** -periods)
        )
        closed_form_modified = closed_form_macaulay / (Decimal("1") + ytm)

    assert abs(duration - closed_form_modified) < Decimal("1e-15")
    assert abs(duration - Decimal("4.6619205928746611")) < Decimal("1e-15")
    # 百分数塌缩回归锚：未归一实现约为 0.42，且绝不应回到未折算的 Macaulay 4.7729。
    assert Decimal("4") < duration < Decimal("4.7")


def test_golden_modified_duration_percent_normalization_drives_bridge_curve_effects():
    """端到端：回退久期归一后，曲线效应量级正确（塌缩缺陷会让效应缩水约 11 倍）。

    余额行不带 modified_duration，靠 coupon/ytm=2.38 回退得到 D ≈ 4.6619205929。
    平坦曲线 3.20% → 2.95%（Δy = 0.0025），期末净价 10,000,000：
        treasury_curve = −(0.0025 × 4.6619205929 × 10,000,000) ≈ −116,548.01
    塌缩久期（≈0.42）只会给出约 −10,500，量级完全不同。
    """
    rows = build_pnl_bridge_rows(
        pnl_fi_rows=[_fact_row()],
        balance_rows_current=[
            _balance_row(
                "2026-12-31",
                years_to_maturity=None,
                modified_duration=None,
                maturity_date="2031-12-31",
                coupon_rate="2.38",
                ytm_value="2.38",
                market_value_amount="10000000",
            )
        ],
        balance_rows_prior=[_balance_row("2025-12-31")],
        treasury_curve_current=_linear_curve("3.20"),
        treasury_curve_prior=_linear_curve("2.95"),
    )

    treasury_curve = rows[0].treasury_curve
    assert abs(treasury_curve - Decimal("-116548.0148")) < Decimal("0.01")
