"""
年利率口径归一（自 MOSS-V2 core_finance 迁入）。

显式单位转换函数，消灭散落的 / 100、* 100、/ 10000 等魔法数字。
"""
from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# 显式单位转换（无歧义，调用方明确知道输入单位）
# ---------------------------------------------------------------------------

def pct_to_decimal(value: float) -> float:
    """百分数 → 小数。2.55 → 0.0255"""
    return value / 100.0


def decimal_to_pct(value: float) -> float:
    """小数 → 百分数。0.0255 → 2.55"""
    return value * 100.0


def bp_to_decimal(value: float) -> float:
    """基点(BP) → 小数。50 → 0.005"""
    return value / 10000.0


def decimal_to_bp(value: float) -> float:
    """小数 → 基点(BP)。0.005 → 50"""
    return value * 10000.0


def pct_to_bp(value: float) -> float:
    """百分数 → 基点(BP)。2.55 → 255"""
    return value * 100.0


def bp_to_pct(value: float) -> float:
    """基点(BP) → 百分数。255 → 2.55"""
    return value / 100.0


# ---------------------------------------------------------------------------
# 启发式归一（输入单位不确定时使用，尽量少用）
# ---------------------------------------------------------------------------

def normalize_annual_rate_to_decimal(raw: Any) -> float | None:
    """
    将存储的年利率统一为「小数形式」（0.035 表示 3.5%）。

    规则（与 import_v1_real_snapshot._normalize_rate 一致）：
    - None / 负数 → None
    - > 100 → None（视为脏数据）
    - > 1 → 除以 100（百分数）
    - 其余按已是小数处理
    """
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v) or v < 0:
        return None
    if v > 100:
        return None
    if v > 1:
        return v / 100.0
    return v
