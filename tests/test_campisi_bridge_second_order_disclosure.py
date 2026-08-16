"""formal-bridge 路径二阶项的**未拆分披露**契约。

背景：`/api/pnl-attribution/campisi/enhanced` 在 formal-bridge 路径上把
`convexity_effect / cross_effect / reinvestment_effect` 硬编码为 0
（`campisi_attribution_service._formal_bridge_bond_rows`）。owner 已裁定金额侧
不补算——bridge 只对 FVTPL 计市场效应，二阶项按亿元展示不可见，且
`selection_effect` 的语义就是"未解释残差"，含未拆分项可接受。

但"未拆分的 0"和"观测到二阶贡献为零"长得完全一样。本文件只锁**披露信号**，
不锁金额：

1. bridge 路径三项恒为精确 0，且 `effect_availability` 必须给出
   `status="not_decomposed"` 条目 + 一条 diagnostics；
2. four-effects 形状根本没有这三个金额，因此不得凭空多出三个条目；
3. model 路径（`core_finance.campisi.campisi_enhanced`）不受影响：它真的拆这
   三项，`effect_availability` 里不出现任何 `not_decomposed`；
4. 加了披露以后金额一字未改（分量之和仍等于 `total_return`）。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from backend.app.core_finance.campisi import EFFECT_STATUS_OK, campisi_enhanced
from backend.app.services import campisi_attribution_service as campisi_svc

_START = date(2026, 1, 1)
_END = date(2026, 1, 31)

_SECOND_ORDER_KEYS = ("convexity_effect", "cross_effect", "reinvestment_effect")


def _bridge_row(**overrides: Any) -> dict[str, Any]:
    """一行闭合的桥行：residual 与服务端重算的 selection 必须一致。"""
    row: dict[str, Any] = {
        "instrument_code": "BRIDGE-01.IB",
        "portfolio_name": "FIOA",
        "cost_center": "5010",
        "accounting_basis": "FVTPL",
        "beginning_dirty_mv": {"raw": 1000.0},
        "ending_dirty_mv": {"raw": 1100.0},
        "carry": {"raw": 5.0},
        "roll_down": {"raw": 1.0},
        "treasury_curve": {"raw": 2.0},
        "credit_spread": {"raw": 3.0},
        "fx_translation": {"raw": 4.0},
        "realized_trading": {"raw": 6.0},
        "manual_adjustment": {"raw": 0.0},
        "unrealized_fv": {"raw": 14.0},
        "actual_pnl": {"raw": 35.0},
        # selection = 35 − (5 + 3 + 3 + 6 + 0 + 4) = 14
        "residual": {"raw": 14.0},
        "quality_flag": "ok",
    }
    row.update(overrides)
    return row


def _bridge_envelope(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "result_meta": {"quality_flag": "ok", "vendor_status": "ok", "fallback_mode": "none"},
        "result": {
            "summary": {"total_actual_pnl": {"raw": 35.0}},
            "rows": rows if rows is not None else [_bridge_row()],
        },
    }


def _positions() -> list[dict[str, Any]]:
    return [
        {
            "instrument_code": "BRIDGE-01.IB",
            "portfolio_name": "FIOA",
            "cost_center": "5010",
            "market_value_start": 1000.0,
            "mod_duration": 2.7,
            "asset_class_start": "政策性金融债",
            "maturity_date_start": date(2029, 1, 1),
            "accrued_interest_start": 3.0,
        }
    ]


def _enhanced_result() -> dict[str, Any]:
    return campisi_svc._formal_bridge_to_enhanced_result(
        bridge_envelope=_bridge_envelope(),
        positions=_positions(),
        start_date=_START,
        end_date=_END,
    )


# ---------------------------------------------------------------------------
# 1. bridge 路径：三项恒 0，且必须带 not_decomposed 披露
# ---------------------------------------------------------------------------


def test_bridge_second_order_effects_are_exactly_zero() -> None:
    result = _enhanced_result()

    for key in _SECOND_ORDER_KEYS:
        assert result["totals"][key] == 0.0
        assert result["by_bond"][0][key] == 0.0
        assert result["by_asset_class"][0][key] == 0.0


@pytest.mark.parametrize("key", _SECOND_ORDER_KEYS)
def test_bridge_second_order_effect_carries_not_decomposed_entry(key: str) -> None:
    """没有这个条目，页面拿到的就是一个与真实观测零无法区分的 0。"""
    availability = _enhanced_result()["effect_availability"]

    entry = availability[key]
    assert entry["status"] == campisi_svc.EFFECT_STATUS_NOT_DECOMPOSED
    assert entry["reason"] == campisi_svc.BRIDGE_SECOND_ORDER_NOT_DECOMPOSED_REASON
    # 未拆分是整期、全人口的框架事实，不是逐券输入缺失。
    assert entry["unavailable_bonds"] == availability["bonds"] == 1
    assert entry["unavailable_market_value_start"] == pytest.approx(1000.0)


def test_bridge_second_order_status_is_distinct_from_input_unavailability() -> None:
    """`not_decomposed` 不得与"有这一步但输入缺失"的 unavailable 混为一谈。"""
    availability = _enhanced_result()["effect_availability"]

    assert availability["convexity_effect"]["status"] != "unavailable"
    assert availability["treasury_effect"]["status"] == EFFECT_STATUS_OK


def test_bridge_enhanced_result_emits_not_decomposed_diagnostic() -> None:
    diagnostics = _enhanced_result()["diagnostics"]

    assert campisi_svc.BRIDGE_SECOND_ORDER_NOT_DECOMPOSED_DIAGNOSTIC in diagnostics


def test_bridge_decomposition_basis_states_the_folding_into_selection() -> None:
    basis = campisi_svc.FORMAL_BRIDGE_DECOMPOSITION_BASIS

    assert "not decomposed on this" in basis
    assert "folded into" in basis
    assert "selection_effect" in basis


# ---------------------------------------------------------------------------
# 2. 金额一字未改：披露只加状态，不动数值
# ---------------------------------------------------------------------------


def test_bridge_totals_still_close_to_total_return() -> None:
    totals = _enhanced_result()["totals"]

    components = (
        "income_return",
        "treasury_effect",
        "spread_effect",
        "realized_trading",
        "manual_adjustment",
        "fx_translation",
        *_SECOND_ORDER_KEYS,
        "selection_effect",
    )
    assert sum(totals[key] for key in components) == pytest.approx(totals["total_return"])
    assert totals["total_return"] == pytest.approx(35.0)
    assert totals["selection_effect"] == pytest.approx(14.0)


# ---------------------------------------------------------------------------
# 3. four-effects 形状没有这三个金额，就不该多出三个条目
# ---------------------------------------------------------------------------


def test_four_effects_bridge_availability_has_no_second_order_entries() -> None:
    result = campisi_svc._formal_bridge_to_campisi_result(
        bridge_envelope=_bridge_envelope(),
        positions=_positions(),
        start_date=_START,
        end_date=_END,
    )

    availability = result.effect_availability
    assert set(availability) == {"bonds", "treasury_effect", "spread_effect", "accrued_interest"}
    assert campisi_svc.BRIDGE_SECOND_ORDER_NOT_DECOMPOSED_DIAGNOSTIC not in result.diagnostics


# ---------------------------------------------------------------------------
# 4. model 路径不受影响：它真的拆二阶项
# ---------------------------------------------------------------------------


def _model_position() -> dict[str, Any]:
    return {
        "bond_code": "MODEL-01.IB",
        "instrument_id": "MODEL-01.IB",
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


_MODEL_CURVE_START = {
    "treasury_1y": 2.00,
    "treasury_3y": 2.30,
    "treasury_5y": 2.60,
    "treasury_7y": 2.80,
    "treasury_10y": 3.00,
    "treasury_30y": 3.50,
}
_MODEL_CURVE_END = {key: value + 0.10 for key, value in _MODEL_CURVE_START.items()}


def test_model_path_availability_has_no_not_decomposed_status() -> None:
    result = campisi_enhanced(
        positions_merged=[_model_position()],
        market_start={**_MODEL_CURVE_START, "credit_spread_aaa_3y": 60.0},
        market_end={**_MODEL_CURVE_END, "credit_spread_aaa_3y": 65.0},
        start_date=date(2026, 6, 30),
        end_date=date(2026, 7, 31),
    )

    availability = result["effect_availability"]
    statuses = {
        key: entry["status"]
        for key, entry in availability.items()
        if isinstance(entry, dict)
    }
    assert campisi_svc.EFFECT_STATUS_NOT_DECOMPOSED not in statuses.values()
    assert not set(availability) & set(_SECOND_ORDER_KEYS)
    assert campisi_svc.BRIDGE_SECOND_ORDER_NOT_DECOMPOSED_DIAGNOSTIC not in result.get(
        "diagnostics", []
    )


def test_model_path_decomposes_convexity_as_a_real_number() -> None:
    """model 路径的 convexity 是算出来的，不是框架产物——它不能被本次改动顶成 0。"""
    result = campisi_enhanced(
        positions_merged=[_model_position()],
        market_start={**_MODEL_CURVE_START, "credit_spread_aaa_3y": 60.0},
        market_end={**_MODEL_CURVE_END, "credit_spread_aaa_3y": 65.0},
        start_date=date(2026, 6, 30),
        end_date=date(2026, 7, 31),
    )

    assert isinstance(Decimal(str(result["totals"]["convexity_effect"])), Decimal)
    assert result["totals"]["convexity_effect"] != 0.0
