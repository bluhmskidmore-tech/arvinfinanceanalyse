"""缺到期日时,三条久期路径必须给出同一个答案(W-fi-2026-08 P2 回归护栏)。

## 修的是什么

2026-07-31 有 127 笔持仓 / 433.9955 亿元 / 占债券组合 12.6786% 市值缺 ``maturity_date``。
同一批持仓在三条路径上拿到三个不同的久期::

    事实表物化 (bond_analytics.engine)          -> 0
    bond_duration.estimate_duration            -> 0.25   (``SA``/``SCP`` 前缀短路)
    bond_analytics.common.estimate_duration    -> 3.0    (硬编码占位)

折合组合加权久期(全量分母口径)差 ``(3.0 − 0.25) × 12.6786% = 0.3487`` 年,
比同期修掉的整期截断 bug(0.0249 年)大一个数量级。

## 这 127 笔根本不是债券

只读副本 ``data/moss.duckdb.bak-20260812-1920-presnapshot`` 实测(2026-08-12)::

    fact_formal_bond_analytics_daily where instrument_code like 'SA%'
      -> 57,115 行; 到期日 0 行有值; 票息 0 行非零; 应计利息 0 行非零;
         券名 57,115/57,115 全是纯 6 位数字
    2026-07-31 的 127 笔: bond_type='其他', asset_class='交易性资产',
         issuer_name 是基金全称(010607 新沃安鑫87个月定开 / 006925 永赢中债1-3政策金融债
         / 008028 申万菱信安泰广利63个月定开 …), 场外开放式 119 笔 + 场内 ETF 8 笔
    SCP 前缀: fact / snapshot / balance 三张表各 0 行 —— 那个分支是死代码

也就是说 ``bond_duration`` 的 ``SA``/``SCP`` 短路把"短融"的假设套在了基金上。

## 现在的口径

缺到期日 -> ``common.resolve_missing_maturity_duration``(唯一常数出处) ->
``DURATION_UNAVAILABLE``(0) + 显式告警。0 不是"久期为 0 的债",是"久期不适用"
的标记;需要区分二者的调用方用 ``estimate_duration_with_status``,它返回
``(None, maturity_unavailable)``。
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance import bond_duration
from backend.app.core_finance.bond_analytics import common
from backend.app.core_finance.bond_analytics.engine import (
    DURATION_QUALITY_MATURITY_UNAVAILABLE,
    DURATION_QUALITY_NO_REMAINING_TERM,
    compute_bond_analytics_rows,
)

REPORT_DATE = date(2026, 7, 31)

# 生产实测代码 + 前缀短路曾覆盖到的代码形状 + 兜底空值。
_INSTRUMENT_CODES = [
    "SA0106070101",  # 新沃安鑫87个月定开, 缺到期日样本里市值最大的一只
    "SA5110300101",  # 场内 ETF 511030
    "SCP123456",     # 本套账 0 行匹配的死分支
    "sa_lowercase",  # 原短路按 .upper() 匹配, 小写同样会被吞掉
    "123456.IB",     # 普通银行间债券代码
    "",              # 代码缺失
]


def _engine_row(instrument_code: str, maturity_date: date | None):
    return compute_bond_analytics_rows(
        [
            {
                "report_date": REPORT_DATE,
                "instrument_code": instrument_code,
                "instrument_name": "010607",
                "currency_code": "CNY",
                "face_value_native": Decimal("100"),
                "market_value_native": Decimal("100"),
                "amortized_cost_native": Decimal("100"),
                "accrued_interest_native": Decimal("0"),
                "coupon_rate": Decimal("0"),
                "ytm_value": Decimal("0"),
                "maturity_date": maturity_date,
                "bond_type": "其他",
                "asset_class": "交易性资产",
                "interest_mode": "固定",
                "is_issuance_like": False,
            }
        ],
        REPORT_DATE,
    )[0]


@pytest.mark.parametrize("instrument_code", _INSTRUMENT_CODES)
def test_three_paths_agree_when_maturity_date_is_missing(instrument_code: str) -> None:
    """三条路径对同一输入必须返回同一个 Decimal。这正是本次要防止再次分裂的东西。"""
    via_bond_duration = bond_duration.estimate_duration(
        None, REPORT_DATE, Decimal("0"), bond_code=instrument_code, ytm=Decimal("0")
    )
    via_common = common.estimate_duration(
        None, REPORT_DATE, coupon_rate=Decimal("0"), ytm=Decimal("0"), bond_code=instrument_code
    )
    via_engine = _engine_row(instrument_code, None).macaulay_duration

    assert via_bond_duration == via_common == via_engine == common.DURATION_UNAVAILABLE
    # 旧的三个答案都不得复活。
    assert via_bond_duration not in (Decimal("0.25"), Decimal("3"))


@pytest.mark.parametrize("instrument_code", _INSTRUMENT_CODES)
def test_three_paths_agree_when_maturity_date_is_present(instrument_code: str) -> None:
    """有到期日时三条路径也必须一致 —— 前缀短路曾让 ``SA``/``SCP`` 券即便有真实
    到期日也照样返回 0.25(短路排在到期日判断之前)。"""
    maturity = date(2031, 7, 31)
    coupon = Decimal("0.03")
    ytm = Decimal("0.03")

    via_bond_duration = bond_duration.estimate_duration(
        maturity, REPORT_DATE, coupon, bond_code=instrument_code, ytm=ytm
    )
    via_common = common.estimate_duration(
        maturity, REPORT_DATE, coupon_rate=coupon, ytm=ytm, bond_code=instrument_code
    )

    assert via_bond_duration == via_common
    assert via_bond_duration > Decimal("4")  # 5 年 3% 平价券 ≈ 4.72 年, 不是 0.25


def test_instrument_code_prefix_never_changes_the_answer() -> None:
    """代码前缀不再影响任何取值 —— ``SA``/``SCP`` 专属分支已删除。"""
    missing = {
        code: bond_duration.estimate_duration(
            None, REPORT_DATE, Decimal("0"), bond_code=code, ytm=Decimal("0")
        )
        for code in _INSTRUMENT_CODES
    }
    present = {
        code: bond_duration.estimate_duration(
            date(2031, 7, 31), REPORT_DATE, Decimal("0.03"), bond_code=code, ytm=Decimal("0.03")
        )
        for code in _INSTRUMENT_CODES
    }

    assert len(set(missing.values())) == 1, missing
    assert len(set(present.values())) == 1, present


def test_scp_prefix_has_zero_rows_in_this_book() -> None:
    """记录 ``SCP`` 分支是死代码这一事实(取证见模块 docstring)。

    只读副本 ``moss.duckdb.bak-20260812-1920-presnapshot`` 三张表各 0 行匹配::

        select count(*) from fact_formal_bond_analytics_daily where instrument_code like 'SCP%'  -> 0
        select count(*) from zqtz_bond_daily_snapshot          where instrument_code like 'SCP%'  -> 0
        select count(*) from fact_formal_zqtz_balance_daily    where instrument_code like 'SCP%'  -> 0

    因此 ``SCP`` 不得再有任何专属分支;它必须与任意其它代码走完全相同的路径。
    """
    maturity = date(2027, 1, 31)
    coupon = Decimal("0.03")

    scp = bond_duration.estimate_duration(maturity, REPORT_DATE, coupon, bond_code="SCP123456")
    plain = bond_duration.estimate_duration(maturity, REPORT_DATE, coupon, bond_code="123456.IB")

    assert scp == plain
    assert scp != Decimal("0.25")


def test_unavailable_status_is_shared_vocabulary_across_paths() -> None:
    """三条路径的"不可用"状态字面量必须同源,消费方只认一套词表。"""
    _, common_status = common.estimate_duration_with_status(None, REPORT_DATE)
    _, bond_duration_status = bond_duration.estimate_duration_with_status(
        None, REPORT_DATE, Decimal("0")
    )
    engine_flag = _engine_row("SA0106070101", None).duration_quality_flag

    assert (
        common_status
        == bond_duration_status
        == engine_flag
        == common.DURATION_TERM_MATURITY_UNAVAILABLE
        == DURATION_QUALITY_MATURITY_UNAVAILABLE
    )


def test_matured_is_distinguishable_from_unavailable_on_every_path() -> None:
    """已到期(久期真的是 0)与缺到期日(久期不适用)数值同为 0,状态必须可区分。"""
    matured_on = date(2026, 1, 31)

    assert common.estimate_duration_with_status(matured_on, REPORT_DATE) == (
        Decimal("0"),
        common.DURATION_TERM_NO_REMAINING_TERM,
    )
    assert bond_duration.estimate_duration_with_status(matured_on, REPORT_DATE, Decimal("0")) == (
        Decimal("0"),
        common.DURATION_TERM_NO_REMAINING_TERM,
    )
    assert (
        _engine_row("123456.IB", matured_on).duration_quality_flag
        == DURATION_QUALITY_NO_REMAINING_TERM
    )
    assert DURATION_QUALITY_NO_REMAINING_TERM != DURATION_QUALITY_MATURITY_UNAVAILABLE


def test_missing_maturity_constant_lives_in_exactly_one_place() -> None:
    """占位取值只此一处。两条函数路径都必须经过 ``resolve_missing_maturity_duration``。"""
    sentinel = Decimal("-99")
    original = common.resolve_missing_maturity_duration
    try:
        common.resolve_missing_maturity_duration = lambda **_kwargs: sentinel  # type: ignore[assignment]
        bond_duration.resolve_missing_maturity_duration = lambda **_kwargs: sentinel  # type: ignore[assignment]

        assert common.estimate_duration(None, REPORT_DATE) == sentinel
        assert bond_duration.estimate_duration(None, REPORT_DATE, Decimal("0")) == sentinel
    finally:
        common.resolve_missing_maturity_duration = original  # type: ignore[assignment]
        bond_duration.resolve_missing_maturity_duration = original  # type: ignore[assignment]


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(
            lambda: common.estimate_duration(None, REPORT_DATE, bond_code="SA0106070101"),
            id="common",
        ),
        pytest.param(
            lambda: bond_duration.estimate_duration(
                None, REPORT_DATE, Decimal("0"), bond_code="SA0106070101"
            ),
            id="bond_duration",
        ),
    ],
)
def test_both_function_paths_warn_with_rule_id(call, caplog: pytest.LogCaptureFixture) -> None:
    """缺到期日必须显式告警(带 rule_id 与代码),不得静默返回占位值。"""
    with caplog.at_level(logging.WARNING):
        call()

    assert any(
        common.MISSING_MATURITY_RULE_ID in record.message
        and "SA0106070101" in record.message
        for record in caplog.records
    )
