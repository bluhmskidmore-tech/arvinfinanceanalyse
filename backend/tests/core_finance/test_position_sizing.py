"""position_size_hint 黄金样本：等权主参考 + risk_budget 实验参考。

覆盖：等权口径（门控敞口/候选数，含单票/多票/敞口边界）、主次声明字段、
ema10 stop_ref 正常、cap 截断、stop 缺失/非正 fallback、
覆盖率退化告警钩子、gate 串联语义与等权 shadow 说明文案。
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from backend.app.core_finance.position_sizing import (
    COVERAGE_DEGRADED_WARNING,
    EQUAL_WEIGHT_NOTE,
    EQUAL_WEIGHT_SHADOW_NOTE,
    GATE_EXPOSURE_NOTE,
    OOS_VALIDATION_EVIDENCE_REF,
    OOS_VALIDATION_NOTE,
    RISK_BUDGET_STATUS_EXPERIMENTAL_REFERENCE,
    STOP_BASIS_EMA10,
    STOP_BASIS_FALLBACK,
    build_stock_candidate_position_size_hint,
    compute_position_size_hint_item,
)
from backend.app.core_finance.strategy_policy import POLICY


def _item(stock_code: str, *, close: object, ema10: object) -> dict[str, object]:
    return {"stock_code": stock_code, "close": close, "ema10": ema10}


def test_hint_golden_sample_ema10_stop_ref() -> None:
    # stop = (100 - 96) / 100 = 0.04；raw = 0.005 / 0.04 = 0.125，未触 cap。
    hint = compute_position_size_hint_item(
        stock_code="600000.SH", close=100.0, ema10=96.0, policy=POLICY.sizing
    )
    assert hint == {
        "stock_code": "600000.SH",
        "raw_weight": 0.125,
        "stop_distance_pct": 0.04,
        "stop_basis": STOP_BASIS_EMA10,
        "capped": False,
    }


def test_hint_golden_sample_single_name_cap_clip() -> None:
    # stop = 0.01 -> raw 0.5 > cap 0.25，触发 cap 截断。
    hint = compute_position_size_hint_item(
        stock_code="000001.SZ", close=100.0, ema10=99.0, policy=POLICY.sizing
    )
    assert hint["raw_weight"] == 0.25
    assert hint["stop_distance_pct"] == 0.01
    assert hint["stop_basis"] == STOP_BASIS_EMA10
    assert hint["capped"] is True


@pytest.mark.parametrize(
    ("close", "ema10"),
    [
        (100.0, None),  # ema10 缺失
        (None, 96.0),  # close 缺失
        (100.0, 105.0),  # ema10 高于 close，stop 非正
        (100.0, 100.0),  # stop == 0
        (0.0, 96.0),  # close 非正
        (100.0, float("nan")),  # 非有限值
    ],
)
def test_hint_golden_sample_fallback_stop(close: object, ema10: object) -> None:
    # fallback stop = 0.08 -> raw = 0.005 / 0.08 = 0.0625。
    hint = compute_position_size_hint_item(
        stock_code="600519.SH", close=close, ema10=ema10, policy=POLICY.sizing
    )
    assert hint["raw_weight"] == 0.0625
    assert hint["stop_distance_pct"] == 0.08
    assert hint["stop_basis"] == STOP_BASIS_FALLBACK
    assert hint["capped"] is False


def test_hint_stop_distance_matches_backtest_engine() -> None:
    """hint 的 stop 距离口径必须与回测引擎 _risk_budget_stop_distance 一致。"""
    from backend.app.core_finance.portfolio_backtest import (
        _Candidate,
        _risk_budget_stop_distance,
    )

    cases = [
        (100.0, 96.0),
        (100.0, 99.0),
        (100.0, None),
        (100.0, 105.0),
        (None, 96.0),
    ]
    for close, ema10 in cases:
        candidate = _Candidate(
            signal_date="2026-08-11",
            stock_code="600000.SH",
            stock_name="测试",
            signal_kind="stock_candidate",
            candidate_rank=1,
            market_state="WARM",
            entry_date="2026-08-12",
            exit_date=None,
            return_net=None,
            entry_executable=True,
            entry_block_reason="",
            daily_amount=None,
            entry_price=close,
            signal_close=close,
            ema10_signal=ema10,
            signal_high=None,
        )
        engine_stop, engine_fallback = _risk_budget_stop_distance(
            candidate,
            fallback_stop_distance_pct=POLICY.sizing.fallback_stop_distance_pct,
        )
        hint = compute_position_size_hint_item(
            stock_code="600000.SH", close=close, ema10=ema10, policy=POLICY.sizing
        )
        assert hint["stop_distance_pct"] == round(engine_stop, 6), (close, ema10)
        assert (hint["stop_basis"] == STOP_BASIS_FALLBACK) is engine_fallback, (close, ema10)


def test_hint_block_primary_basis_equal_weight_single_candidate() -> None:
    # 单票：等权 = 门控敞口 / 1 = 0.75；主次声明来自 SizingPolicy 单一来源。
    block = build_stock_candidate_position_size_hint(
        [_item("600000.SH", close=100.0, ema10=96.0)],
        market_gate_exposure=0.75,
    )
    assert block["primary_basis"] == "equal_weight"
    assert block["primary_basis"] == POLICY.sizing.primary_basis
    assert block["risk_budget_status"] == RISK_BUDGET_STATUS_EXPERIMENTAL_REFERENCE
    assert block["risk_budget_status"] == "experimental_reference"
    assert block["equal_weight_gate_exposure"] == 0.75
    assert block["equal_weight_candidate_count"] == 1
    assert block["equal_weight_note"] == EQUAL_WEIGHT_NOTE
    assert "门控敞口" in EQUAL_WEIGHT_NOTE
    assert "候选数" in EQUAL_WEIGHT_NOTE
    item = block["items"][0]
    assert item["equal_weight"] == 0.75
    # risk_budget 实验参考字段保留不删（下游容错）。
    assert item["raw_weight"] == 0.125
    assert item["stop_basis"] == STOP_BASIS_EMA10


def test_hint_block_equal_weight_multi_candidate_split() -> None:
    # 多票：等权 = 0.75 / 3 = 0.25，逐票相同；与止损距离无关。
    block = build_stock_candidate_position_size_hint(
        [
            _item("600000.SH", close=100.0, ema10=96.0),
            _item("000001.SZ", close=100.0, ema10=99.0),
            _item("600519.SH", close=100.0, ema10=None),
        ],
        market_gate_exposure=0.75,
    )
    assert block["equal_weight_candidate_count"] == 3
    assert [item["equal_weight"] for item in block["items"]] == [0.25, 0.25, 0.25]
    # 各票 risk_budget 实验参考仍逐票不同。
    assert [item["raw_weight"] for item in block["items"]] == [0.125, 0.25, 0.0625]


@pytest.mark.parametrize(
    ("market_gate_exposure", "expected_exposure", "expected_equal_weight"),
    [
        (None, None, None),  # 门控敞口缺失：等权不可计算
        (float("nan"), None, None),  # 非有限值同缺失
        (0.0, 0.0, 0.0),  # 门控关闭：等权仓位为 0（当日不建仓）
        (1.2, 1.0, 0.5),  # 超界截取到 1.0（镜像引擎 [0,1] 口径）
        (-0.3, 0.0, 0.0),  # 负值截取到 0.0
    ],
)
def test_hint_block_equal_weight_gate_exposure_boundaries(
    market_gate_exposure: object,
    expected_exposure: float | None,
    expected_equal_weight: float | None,
) -> None:
    block = build_stock_candidate_position_size_hint(
        [
            _item("600000.SH", close=100.0, ema10=96.0),
            _item("000001.SZ", close=100.0, ema10=99.0),
        ],
        market_gate_exposure=market_gate_exposure,
    )
    assert block["equal_weight_gate_exposure"] == expected_exposure
    assert all(item["equal_weight"] == expected_equal_weight for item in block["items"])
    # 等权不可计算时 risk_budget 实验参考仍在（不删既有字段）。
    assert block["items"][0]["raw_weight"] == 0.125


def test_hint_block_default_call_keeps_equal_weight_null() -> None:
    # 未传门控敞口（老调用方）：equal_weight 为 None，其余输出不受影响。
    block = build_stock_candidate_position_size_hint(
        [_item("600000.SH", close=100.0, ema10=96.0)]
    )
    assert block["equal_weight_gate_exposure"] is None
    assert block["items"][0]["equal_weight"] is None
    assert block["items"][0]["raw_weight"] == 0.125


def test_hint_block_policy_metadata_and_notes() -> None:
    block = build_stock_candidate_position_size_hint(
        [_item("600000.SH", close=100.0, ema10=96.0)]
    )
    assert block["policy_version"] == "sizing_eqw_v2_stock_candidate"
    assert block["sizing_mode"] == "risk_budget"
    assert block["primary_basis"] == "equal_weight"
    assert block["risk_budget_status"] == "experimental_reference"
    assert block["signal_kind"] == "stock_candidate"
    assert block["risk_per_trade"] == 0.005
    assert block["single_name_cap"] == 0.25
    assert block["fallback_stop_distance_pct"] == 0.08
    assert block["stop_basis"] == "ema10_stop_ref"
    # 串联 gate 敞口语义必须在提示文案中说明，且声明不做实时敞口截断。
    assert block["gate_exposure_note"] == GATE_EXPOSURE_NOTE
    assert "串联" in GATE_EXPOSURE_NOTE
    assert "敞口" in GATE_EXPOSURE_NOTE
    assert "不做实时敞口截断" in GATE_EXPOSURE_NOTE
    # 等权 shadow 对照仍在回测输出的说明字段。
    assert block["equal_weight_shadow_note"] == EQUAL_WEIGHT_SHADOW_NOTE
    assert "等权" in EQUAL_WEIGHT_SHADOW_NOTE
    assert "回测" in EQUAL_WEIGHT_SHADOW_NOTE
    assert block["oos_validation"] == {
        "status": "not_supported_by_walk_forward",
        "note": OOS_VALIDATION_NOTE,
        "evidence_ref": OOS_VALIDATION_EVIDENCE_REF,
    }
    assert "0.25%~1%" in OOS_VALIDATION_NOTE
    assert "固定 0.5%" in OOS_VALIDATION_NOTE
    assert "等权 shadow" in OOS_VALIDATION_NOTE
    assert OOS_VALIDATION_EVIDENCE_REF == "docs/strategy-reports/walk-forward-first-run.md"

    custom_status = "test_walk_forward_status"
    custom_block = build_stock_candidate_position_size_hint(
        [_item("600000.SH", close=100.0, ema10=96.0)],
        policy=replace(POLICY.sizing, oos_validation_status=custom_status),
    )
    assert custom_block["oos_validation"] == {
        "status": custom_status,
        "note": OOS_VALIDATION_NOTE,
        "evidence_ref": OOS_VALIDATION_EVIDENCE_REF,
    }


def test_hint_block_coverage_degradation_hook() -> None:
    # 10 票中 2 票缺 ema10 -> 缺失率 0.2 > 0.1，标注降级。
    items = [_item(f"60000{i}.SH", close=100.0, ema10=96.0) for i in range(8)]
    items += [
        _item("600008.SH", close=100.0, ema10=None),
        _item("600009.SH", close=100.0, ema10=None),
    ]
    degraded = build_stock_candidate_position_size_hint(items)
    assert degraded["stop_ref_fallback_count"] == 2
    assert degraded["stop_ref_missing_ratio"] == 0.2
    assert degraded["coverage_degraded"] is True
    assert degraded["coverage_warning"] == COVERAGE_DEGRADED_WARNING

    # 10 票中 1 票缺失 -> 0.1 不超过阈值，不降级。
    ok = build_stock_candidate_position_size_hint(
        [_item(f"60001{i}.SH", close=100.0, ema10=96.0) for i in range(9)]
        + [_item("600019.SH", close=100.0, ema10=None)]
    )
    assert ok["stop_ref_missing_ratio"] == 0.1
    assert ok["coverage_degraded"] is False
    assert ok["coverage_warning"] is None


def test_hint_block_empty_items() -> None:
    block = build_stock_candidate_position_size_hint([], market_gate_exposure=0.75)
    assert block["items"] == []
    assert block["stop_ref_fallback_count"] == 0
    assert block["stop_ref_missing_ratio"] == 0.0
    assert block["coverage_degraded"] is False
    assert block["coverage_warning"] is None
    # 候选数为 0 时不做除法，敞口照实披露。
    assert block["equal_weight_candidate_count"] == 0
    assert block["equal_weight_gate_exposure"] == 0.75
