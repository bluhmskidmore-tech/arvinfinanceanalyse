"""
锁定 pnl_service 展示层 quantize 的舍入模式（2026-08 PnL 归因审计 M1）。

三个 quantize 函数（金额 0.01 / 比例 0.000001 / 收益率 0.000001）必须显式
ROUND_HALF_UP，与 core 层全库舍入口径一致（SHR-01，见 core_finance/pnl.py、
core_finance/var_engine.py 的同口径注释）。Decimal.quantize 默认是银行家舍入
（ROUND_HALF_EVEN），在 .005 类半分钱边界会向偶数位靠拢，与 core 层产生
方向性尾差，影响对账 delta（threshold_yuan=0.01）的判定方向。

用例全部取 HALF_UP 与 HALF_EVEN 结果不同的 tie 边界：
- 0.005  → HALF_UP 0.01   / HALF_EVEN 0.00
- 0.025  → HALF_UP 0.03   / HALF_EVEN 0.02
- -0.005 → HALF_UP -0.01  / HALF_EVEN -0.00（HALF_UP 平局远离零）
"""
from __future__ import annotations

from decimal import Decimal

from backend.app.services.pnl_service import (
    _quantize_decimal,
    _quantize_ratio,
    _quantize_yield_pct,
)


def test_quantize_decimal_rounds_half_cent_up_not_bankers() -> None:
    # 银行家舍入会给 0.00（向偶数 0 靠拢）——此断言锁定 HALF_UP。
    assert _quantize_decimal(Decimal("0.005")) == Decimal("0.01")
    # 银行家舍入会给 0.02（向偶数 2 靠拢）。
    assert _quantize_decimal(Decimal("0.025")) == Decimal("0.03")
    # 负数平局远离零：银行家舍入会给 -0.00。
    assert _quantize_decimal(Decimal("-0.005")) == Decimal("-0.01")
    # 非平局值不受舍入模式影响（回归保护）。
    assert _quantize_decimal(Decimal("1.014")) == Decimal("1.01")
    assert _quantize_decimal(Decimal("1.016")) == Decimal("1.02")


def test_quantize_ratio_rounds_millionth_tie_up_not_bankers() -> None:
    # 银行家舍入会给 0.000000。
    assert _quantize_ratio(Decimal("0.0000005")) == Decimal("0.000001")
    # 银行家舍入会给 0.000002（向偶数靠拢）。
    assert _quantize_ratio(Decimal("0.0000025")) == Decimal("0.000003")
    assert _quantize_ratio(Decimal("-0.0000005")) == Decimal("-0.000001")


def test_quantize_yield_pct_rounds_tie_up_and_preserves_none() -> None:
    assert _quantize_yield_pct(None) is None
    # 银行家舍入会给 0.000000。
    assert _quantize_yield_pct(Decimal("0.0000005")) == Decimal("0.000001")
    # 银行家舍入会给 0.000002。
    assert _quantize_yield_pct("0.0000025") == Decimal("0.000003")
    assert _quantize_yield_pct(Decimal("-0.0000005")) == Decimal("-0.000001")


def test_quantized_outputs_keep_expected_exponents() -> None:
    # 金额两位小数、比例/收益率六位小数（精度不因舍入模式改变）。
    assert _quantize_decimal(Decimal("0.005")).as_tuple().exponent == -2
    assert _quantize_ratio(Decimal("0.0000005")).as_tuple().exponent == -6
    assert _quantize_yield_pct(Decimal("0.0000005")).as_tuple().exponent == -6
