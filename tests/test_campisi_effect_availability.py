"""Campisi 退化路径的**显式不可用**契约（2026-08 金融审计整改）。

背景：`fact_formal_yield_curve_daily` 在报告日 2026-07-31 无任何行，所有曲线停在
2026-06-30 或更早。后果是 `treasury_effect` 全 0（1829/1829 行），页面把它读成
"利率没动"，而真相是"没有曲线数据"。同期 1698/1750 行没有应计利息，整条归因链
一直跑在 `bond_four_effects` 的净价退化分支上，同样没有任何披露。

本文件只锁**信号**，不锁数值：每个退化用例都同时断言
1. 退化状态可被调用方分支（status / reason / 逐券布尔位 / 诊断串），且
2. 数值口径一字未改（退化时效应仍是 0，健康时四效应仍闭合）。

关键区分（本文件的核心）：曲线**存在但平坦** → status="ok" 且效应真为 0；
曲线**缺失或共同期限不足** → status="unavailable"。两者的 0 长得一样，
只有状态位能把它们分开。
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.campisi import (
    ACCRUED_INTEREST_FALLBACK_DIAGNOSTIC,
    ACCRUED_INTEREST_MISSING_REASON,
    BENCHMARK_CURVE_DEGENERATE_REASON,
    EFFECT_STATUS_OK,
    EFFECT_STATUS_PARTIAL,
    EFFECT_STATUS_UNAVAILABLE,
    SPREAD_EFFECT_UNAVAILABLE_DIAGNOSTIC,
    SPREAD_INPUT_MISSING_REASON,
    TREASURY_EFFECT_UNAVAILABLE_DIAGNOSTIC,
    _build_benchmark_change_evaluator,
    benchmark_yield_change_decimal,
    campisi_attribution,
    campisi_enhanced,
    credit_spread_change_available,
)

_START = date(2026, 6, 30)
_END = date(2026, 7, 31)

_FULL_CURVE_START = {
    "treasury_1y": 2.00,
    "treasury_3y": 2.30,
    "treasury_5y": 2.60,
    "treasury_7y": 2.80,
    "treasury_10y": 3.00,
    "treasury_30y": 3.50,
}
_FULL_CURVE_END = {key: value + 0.10 for key, value in _FULL_CURVE_START.items()}
# 6 个期限全在、两端完全相同：市场真的没动，效应为 0 是**观测结果**。
_FLAT_CURVE = dict(_FULL_CURVE_START)


def _position(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "bond_code": "AVAIL-01.IB",
        "instrument_id": "AVAIL-01.IB",
        "market_value_start": 10_000_000.0,
        "market_value_end": 10_050_000.0,
        "face_value_start": 10_000_000.0,
        "coupon_rate_start": 0.03,
        "yield_to_maturity_start": 0.032,
        "asset_class_start": "AAA企业债",
        "maturity_date_start": date(2031, 6, 30),
        "accrued_interest_start": 60_000.0,
        "accrued_interest_end": 85_000.0,
    }
    row.update(overrides)
    return row


def _spread(**overrides: float) -> dict[str, object]:
    market: dict[str, object] = {"credit_spread_aaa_3y": 60.0}
    market.update(overrides)
    return market


# ---------------------------------------------------------------------------
# 1. 求值器本身携带可用性
# ---------------------------------------------------------------------------


def test_benchmark_evaluator_reports_available_on_a_healthy_curve_pair():
    evaluator = _build_benchmark_change_evaluator(_FULL_CURVE_START, _FULL_CURVE_END)

    assert evaluator.available is True
    assert evaluator.reason is None
    assert evaluator.shared_tenor_count == 6
    # Δ10bp / 100 = 0.001，数值口径不变。
    assert evaluator(5.0) == pytest.approx(Decimal("0.001"), abs=Decimal("1e-9"))


def test_flat_curve_is_available_and_its_zero_is_an_observation():
    """平坦曲线的 0 必须留在 status=ok —— 否则真实的"利率没动"会被误报为缺数据。"""
    evaluator = _build_benchmark_change_evaluator(_FLAT_CURVE, _FLAT_CURVE)

    assert evaluator.available is True
    assert evaluator.reason is None
    assert evaluator(5.0) == Decimal("0")


@pytest.mark.parametrize(
    ("market_start", "market_end", "expected_shared"),
    [
        # fetch_curve 返回空（2026-07-31 的真实情形）
        ({}, _FULL_CURVE_END, 0),
        (_FULL_CURVE_START, {}, 0),
        (None, None, 0),
        # 两端各有期限但不相交
        ({"treasury_1y": 2.0}, {"treasury_30y": 3.5}, 0),
        # 只有 1 个共同期限，不足以拟合
        ({"treasury_1y": 2.0}, {"treasury_1y": 2.1}, 1),
    ],
)
def test_degenerate_evaluator_is_marked_unavailable_and_still_returns_zero(
    market_start, market_end, expected_shared
):
    evaluator = _build_benchmark_change_evaluator(market_start, market_end)

    assert evaluator.available is False
    assert evaluator.reason == BENCHMARK_CURVE_DEGENERATE_REASON
    assert evaluator.shared_tenor_count == expected_shared
    # 数值口径不变：仍是恒 0，本次整改只改信号。
    assert evaluator(3.0) == Decimal("0")
    assert benchmark_yield_change_decimal(market_start, market_end, 3.0) == Decimal("0")


def test_degenerate_curve_warning_is_logged_once_per_period_not_once_per_bond(caplog):
    """1829 只债券曾产生 1829 条同样的 WARNING；刷屏本身就是一种淹没。"""
    positions = [_position(bond_code=f"FLOOD-{index}") for index in range(25)]

    with caplog.at_level(logging.WARNING, logger="backend.app.core_finance.campisi"):
        campisi_attribution(positions, {}, {}, _START, _END)

    degenerate_logs = [
        record
        for record in caplog.records
        if "shared positive tenors" in record.getMessage()
    ]
    assert len(degenerate_logs) == 1


# ---------------------------------------------------------------------------
# 2. treasury_effect：不可用 vs 观测为零
# ---------------------------------------------------------------------------


def test_missing_curve_marks_treasury_effect_unavailable_without_changing_the_number():
    result = campisi_attribution([_position()], {}, {}, _START, _END)

    treasury = result.effect_availability["treasury_effect"]
    assert treasury["status"] == EFFECT_STATUS_UNAVAILABLE
    assert treasury["reason"] == BENCHMARK_CURVE_DEGENERATE_REASON
    assert treasury["shared_positive_tenors"] == 0
    assert treasury["min_required_shared_tenors"] == 2
    # 曲线退化是整期事实：受影响的是全部债券，而不是某几行。
    assert treasury["unavailable_bonds"] == 1
    assert treasury["unavailable_market_value_start"] == 10_000_000.0
    # 逐券位，供表格逐行渲染"不可用"而不是 0。
    assert [row["treasury_effect_available"] for row in result.by_bond] == [False]
    # 人读披露排在逐券诊断之前。
    assert result.diagnostics[0].startswith(TREASURY_EFFECT_UNAVAILABLE_DIAGNOSTIC)
    assert "0 shared positive tenors (need >= 2)" in result.diagnostics[0]
    assert 'must not be read as "rates did not move"' in result.diagnostics[0]
    # 数值不变。
    assert result.totals["treasury_effect"] == 0.0


def test_flat_curve_keeps_treasury_effect_ok_so_a_real_zero_stays_readable():
    market = {**_FLAT_CURVE, **_spread()}

    result = campisi_attribution([_position()], market, market, _START, _END)

    treasury = result.effect_availability["treasury_effect"]
    assert treasury["status"] == EFFECT_STATUS_OK
    assert treasury["reason"] is None
    assert treasury["shared_positive_tenors"] == 6
    assert [row["treasury_effect_available"] for row in result.by_bond] == [True]
    assert not any(
        message.startswith(TREASURY_EFFECT_UNAVAILABLE_DIAGNOSTIC)
        for message in result.diagnostics
    )
    assert result.totals["treasury_effect"] == pytest.approx(0.0, abs=1e-9)


def test_healthy_curve_pair_reports_ok_and_keeps_the_four_effects_closed():
    market_start = {**_FULL_CURVE_START, **_spread(credit_spread_aaa_3y=60.0)}
    market_end = {**_FULL_CURVE_END, **_spread(credit_spread_aaa_3y=70.0)}

    result = campisi_attribution([_position()], market_start, market_end, _START, _END)

    availability = result.effect_availability
    assert availability["treasury_effect"]["status"] == EFFECT_STATUS_OK
    assert availability["spread_effect"]["status"] == EFFECT_STATUS_OK
    assert availability["accrued_interest"]["status"] == EFFECT_STATUS_OK
    assert availability["accrued_interest"]["basis"] == "dirty_price"
    assert result.diagnostics == []
    # 归因恒等式不因新增信号而改变。
    totals = result.totals
    assert totals["income_return"] + totals["treasury_effect"] + totals["spread_effect"] + totals[
        "selection_effect"
    ] == pytest.approx(totals["total_return"], abs=1e-6)
    # 曲线真的动了：利率效应不应为 0，否则本用例失去对照意义。
    assert totals["treasury_effect"] != 0.0


# ---------------------------------------------------------------------------
# 3. spread_effect：缺利差输入 vs 利率债的结构性零
# ---------------------------------------------------------------------------


def test_gov_rating_spread_zero_is_structural_and_stays_available():
    assert credit_spread_change_available({}, {}, "GOV") is True
    assert credit_spread_change_available(_spread(), _spread(), "AAA") is True
    assert credit_spread_change_available(_spread(), {}, "AAA") is False
    assert credit_spread_change_available({}, {}, "AAA") is False


def test_missing_credit_spread_marks_spread_effect_unavailable():
    market_start = dict(_FULL_CURVE_START)
    market_end = dict(_FULL_CURVE_END)

    result = campisi_attribution([_position()], market_start, market_end, _START, _END)

    spread = result.effect_availability["spread_effect"]
    assert spread["status"] == EFFECT_STATUS_UNAVAILABLE
    assert spread["reason"] == SPREAD_INPUT_MISSING_REASON
    assert spread["unavailable_bonds"] == 1
    assert spread["unavailable_market_value_start"] == 10_000_000.0
    assert [row["spread_effect_available"] for row in result.by_bond] == [False]
    assert any(
        message.startswith(SPREAD_EFFECT_UNAVAILABLE_DIAGNOSTIC) for message in result.diagnostics
    )
    assert result.totals["spread_effect"] == 0.0


def test_mixed_book_reports_partial_spread_coverage():
    """利率债（结构性零）+ 缺利差的信用债 → partial，而不是把两者混成一个 0。"""
    positions = [
        _position(bond_code="GOV-01", asset_class_start="国债"),
        _position(bond_code="CREDIT-01", asset_class_start="AAA企业债"),
    ]

    result = campisi_attribution(positions, _FULL_CURVE_START, _FULL_CURVE_END, _START, _END)

    spread = result.effect_availability["spread_effect"]
    assert spread["status"] == EFFECT_STATUS_PARTIAL
    assert spread["unavailable_bonds"] == 1
    assert {row["bond_code"]: row["spread_effect_available"] for row in result.by_bond} == {
        "GOV-01": True,
        "CREDIT-01": False,
    }


# ---------------------------------------------------------------------------
# 4. 应计利息缺失：整条归因链跑在退化分支上必须可见
# ---------------------------------------------------------------------------


def test_missing_accrued_interest_is_counted_and_disclosed_at_the_chain_entry():
    """97% 的行没有应计，`selection_effect` 系统性吸收面值/市值差异。

    逐券 diagnostic 早已存在，但没有任何**统计**：使用者看不出"整条链一直没走过
    正常分支"。本用例锁住入口处的行数 / 市值口径与人读披露。
    """
    positions = [
        _position(bond_code="NO-AI-1", accrued_interest_start=None, accrued_interest_end=None),
        _position(
            bond_code="NO-AI-2",
            market_value_start=4_000_000.0,
            accrued_interest_start=None,
            accrued_interest_end=None,
        ),
        _position(bond_code="HAS-AI", market_value_start=1_000_000.0),
    ]
    market_start = {**_FULL_CURVE_START, **_spread()}
    market_end = {**_FULL_CURVE_END, **_spread(credit_spread_aaa_3y=70.0)}

    result = campisi_attribution(positions, market_start, market_end, _START, _END)

    accrued = result.effect_availability["accrued_interest"]
    assert accrued["status"] == EFFECT_STATUS_PARTIAL
    assert accrued["basis"] == "mixed"
    assert accrued["reason"] == ACCRUED_INTEREST_MISSING_REASON
    assert accrued["unavailable_bonds"] == 2
    assert accrued["unavailable_market_value_start"] == 14_000_000.0
    assert result.effect_availability["bonds"] == 3

    disclosure = next(
        message
        for message in result.diagnostics
        if message.startswith(ACCRUED_INTEREST_FALLBACK_DIAGNOSTIC)
    )
    assert "2/3 bonds" in disclosure
    assert "selection_effect" in disclosure
    # 逐券位仍在，页面可以逐行标注。
    assert {row["bond_code"]: row["has_accrued_interest"] for row in result.by_bond} == {
        "NO-AI-1": False,
        "NO-AI-2": False,
        "HAS-AI": True,
    }


def test_book_wide_accrued_interest_gap_is_reported_as_unavailable_basis():
    positions = [
        _position(bond_code=f"NO-AI-{index}", accrued_interest_start=None, accrued_interest_end=None)
        for index in range(3)
    ]

    result = campisi_attribution(positions, _FULL_CURVE_START, _FULL_CURVE_END, _START, _END)

    accrued = result.effect_availability["accrued_interest"]
    assert accrued["status"] == EFFECT_STATUS_UNAVAILABLE
    assert accrued["basis"] == "clean_price_fallback"
    assert accrued["unavailable_bonds"] == 3


def test_partial_accrued_interest_side_also_counts_as_clean_price_fallback():
    """只有一端有应计同样退化到净价基准，不能因为"有值"就算正常分支。"""
    positions = [_position(bond_code="HALF-AI", accrued_interest_end=None)]

    result = campisi_attribution(positions, _FULL_CURVE_START, _FULL_CURVE_END, _START, _END)

    accrued = result.effect_availability["accrued_interest"]
    assert accrued["status"] == EFFECT_STATUS_UNAVAILABLE
    assert accrued["unavailable_bonds"] == 1


# ---------------------------------------------------------------------------
# 5. 六效应入口共享同一披露
# ---------------------------------------------------------------------------


def test_campisi_enhanced_carries_the_same_availability_block():
    enhanced = campisi_enhanced([_position()], {}, {}, _START, _END)

    availability = enhanced["effect_availability"]
    assert availability["treasury_effect"]["status"] == EFFECT_STATUS_UNAVAILABLE
    assert availability["treasury_effect"]["reason"] == BENCHMARK_CURVE_DEGENERATE_REASON
    assert [row["treasury_effect_available"] for row in enhanced["by_bond"]] == [False]
    assert enhanced["diagnostics"][0].startswith(TREASURY_EFFECT_UNAVAILABLE_DIAGNOSTIC)
    assert enhanced["totals"]["treasury_effect"] == 0.0


def test_every_effect_block_shares_one_shape_so_the_page_needs_one_renderer():
    """三个效应块的公共键必须一致，formal-bridge 路径也复用同一个构造器。

    形状不一致会逼页面按"这份 payload 从哪条路径来"分支渲染，而这恰恰是使用者
    最不该关心、也最容易漏掉一条分支的地方。
    """
    result = campisi_attribution([_position()], {}, {}, _START, _END)

    common_keys = {"status", "reason", "unavailable_bonds", "unavailable_market_value_start"}
    for name in ("treasury_effect", "spread_effect", "accrued_interest"):
        entry = result.effect_availability[name]
        assert common_keys <= set(entry), name
        assert entry["status"] in {
            EFFECT_STATUS_OK,
            EFFECT_STATUS_PARTIAL,
            EFFECT_STATUS_UNAVAILABLE,
        }
        assert isinstance(entry["unavailable_bonds"], int)
        assert isinstance(entry["unavailable_market_value_start"], float)
        # status 与 reason 必须同进同退，否则"不可用但没说为什么"又是一次沉默。
        assert (entry["status"] == EFFECT_STATUS_OK) == (entry["reason"] is None), name


def test_empty_book_reports_ok_rather_than_a_phantom_degradation():
    """没有持仓时不应报"利差/应计不可用"——那是 0 只债券，不是退化。"""
    result = campisi_attribution([], _FULL_CURVE_START, _FULL_CURVE_END, _START, _END)

    availability = result.effect_availability
    assert availability["bonds"] == 0
    assert availability["spread_effect"]["status"] == EFFECT_STATUS_OK
    assert availability["accrued_interest"]["status"] == EFFECT_STATUS_OK
    assert availability["treasury_effect"]["status"] == EFFECT_STATUS_OK
