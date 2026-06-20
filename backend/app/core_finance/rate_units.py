"""
年利率口径归一（自 MOSS-V2 core_finance 迁入）。

显式单位转换函数，消灭散落的 / 100、* 100、/ 10000 等魔法数字。
"""
from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

_HUNDRED = Decimal("100")
_TEN_THOUSAND = Decimal("10000")


# ---------------------------------------------------------------------------
# 显式单位转换（无歧义，调用方明确知道输入单位）
# ---------------------------------------------------------------------------

def pct_to_decimal(value: Decimal | float | str) -> Decimal:
    """百分数 → 小数。2.55 → 0.0255"""
    return Decimal(str(value)) / _HUNDRED


def decimal_to_pct(value: Decimal | float | str) -> Decimal:
    """小数 → 百分数。0.0255 → 2.55"""
    return Decimal(str(value)) * _HUNDRED


def bp_to_decimal(value: Decimal | float | str) -> Decimal:
    """基点(BP) → 小数。50 → 0.005"""
    return Decimal(str(value)) / _TEN_THOUSAND


def decimal_to_bp(value: Decimal | float | str) -> Decimal:
    """小数 → 基点(BP)。0.005 → 50"""
    return Decimal(str(value)) * _TEN_THOUSAND


def pct_to_bp(value: Decimal | float | str) -> Decimal:
    """百分数 → 基点(BP)。2.55 → 255"""
    return Decimal(str(value)) * _HUNDRED


def bp_to_pct(value: Decimal | float | str) -> Decimal:
    """基点(BP) → 百分数。255 → 2.55"""
    return Decimal(str(value)) / _HUNDRED


# ---------------------------------------------------------------------------
# 启发式归一（输入单位不确定时使用，尽量少用）
# ---------------------------------------------------------------------------

def detect_percent_unit_from_curve(values: list[float]) -> bool:
    """
    启发式判断曲线值是否已为百分数形式（而非小数）。
    返回 True 表示"已是百分数"（2.55 形式），False 表示"是小数"（0.0255 形式，需 x100 转百分数）。

    规则：非空正值最大值 >= 0.5 则视为百分数（最低收益率 0.5%，覆盖中国 / 日本场景）；
    否则视为小数形式。

    边界：
    - 空输入 / 全零 / 全非正 → True（保守处理，不乘 100）
    - 触发 False（即需乘 100 修正）时记录 WARNING，便于发现上游单位错误
    """
    positives = [v for v in values if v and v > 0]
    if not positives:
        return True
    is_percent = max(positives) >= 0.5
    if not is_percent:
        logger.warning(
            "detect_percent_unit_from_curve: max positive %.6g < 0.5, "
            "treating as decimal form (will multiply by 100 upstream)",
            max(positives),
        )
    return is_percent


def normalize_annual_rate_to_decimal(raw: Any) -> float | None:
    """
    将存储的年利率统一为「小数形式」（0.035 表示 3.5%）。

    调用方应确保传入小数格式（position_bonds 的 coupon_rate / yield_to_maturity /
    interest_rate 均以小数存储，0.0255 = 2.55%）。本函数只做防御性处理。

    规则：
    - None / 负数 → None
    - > 20 → None（债券利率超过 20% 视为脏数据，原阈值 > 100 过宽）
    - > 2  → 除以 100 并 WARNING（仅修正明显误入的百分数，如 3.5 被误存为百分数；
              正常债券利率不超过 20%，但 1.5% 存为 0.015 不会触发此分支）
    - 其余按已是小数处理

    阈值选择依据：
    - 正常债券票面利率范围约 0.5%–10%，极端情况不超过 20%
    - 旧阈值 >= 1 会将 1.5%（存为 0.015）误判为百分数 → 0.00015，造成系统性低估
    - 新阈值 > 2 意味着只有 > 200% 才触发 /100，彻底消除对正常小数值的误判
    """
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v) or v < 0:
        return None
    if v > 20:
        logger.warning(
            "normalize_annual_rate_to_decimal: value %s > 20, treating as dirty data, returning None",
            v,
        )
        return None
    if v > 2:
        logger.warning(
            "normalize_annual_rate_to_decimal: value %s > 2, suspected percent-format input, dividing by 100",
            v,
        )
        return v / 100.0
    return v
