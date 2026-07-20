"""
Decimal 工具（自 MOSS-V2 core_finance 迁入）。
"""
from __future__ import annotations

import logging
import math
import sys
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

logger = logging.getLogger(__name__)

YI = Decimal("100000000")
_ZERO_FALLBACK_WARNING_KEYS: set[tuple[str, str, str, str]] = set()


def _warn_to_decimal_zero_fallback(reason: str, value: Any) -> None:
    try:
        frame = sys._getframe(2)
        while frame is not None and frame.f_code.co_filename == __file__:
            frame = frame.f_back
        if frame is None:
            caller = "unknown"
        else:
            caller = f"{frame.f_code.co_filename}:{frame.f_lineno}:{frame.f_code.co_name}"
    except ValueError:
        caller = "unknown"
    input_type = type(value).__name__
    warning_bucket = reason
    if reason == "non_finite" and isinstance(value, float):
        warning_bucket = "nan" if math.isnan(value) else "inf"
    warning_key = (reason, warning_bucket, input_type, caller)
    if warning_key in _ZERO_FALLBACK_WARNING_KEYS:
        return
    _ZERO_FALLBACK_WARNING_KEYS.add(warning_key)
    logger.warning(
        "to_decimal coerced %s to Decimal('0'); reason=%s bucket=%s caller=%s first_occurrence=true",
        input_type,
        reason,
        warning_bucket,
        caller,
    )


def to_decimal(x: Any) -> Decimal:
    """宽松转换：None/NaN/异常 → Decimal("0")。新代码优先用 to_decimal_strict。"""
    if x is None:
        _warn_to_decimal_zero_fallback("missing", x)
        return Decimal("0")
    if isinstance(x, Decimal):
        if not x.is_finite():
            _warn_to_decimal_zero_fallback("non_finite", x)
            return Decimal("0")
        return x
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            _warn_to_decimal_zero_fallback("non_finite", x)
            return Decimal("0")
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        result = Decimal(str(x))
    except (TypeError, ValueError, ArithmeticError):
        _warn_to_decimal_zero_fallback("invalid", x)
        return Decimal("0")
    if not result.is_finite():
        # 例如字符串 "nan"/"inf" 能被 Decimal 构造成功但会静默传播。
        _warn_to_decimal_zero_fallback("non_finite", x)
        return Decimal("0")
    return result


def to_decimal_strict(x: Any) -> Decimal:
    """严格转换：None 抛 TypeError，NaN/Inf 抛 ValueError。金融计算应使用此版本。"""
    if x is None:
        raise TypeError("Cannot convert None to Decimal — use explicit default at call site")
    if isinstance(x, Decimal):
        if not x.is_finite():
            raise ValueError(f"Cannot convert non-finite Decimal {x} to Decimal")
        return x
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            raise ValueError(f"Cannot convert {x} to Decimal")
    result = Decimal(str(x))
    if not result.is_finite():
        raise ValueError(f"Cannot convert {x!r} to a finite Decimal")
    return result


def fmt_yuan(amount_yuan: Decimal) -> str:
    return format(to_decimal(amount_yuan), "f")


def fmt_yi(amount_yuan: Decimal) -> str:
    yi = (to_decimal(amount_yuan) / YI).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return format(yi, "f")


def fmt_money(amount_yuan: Decimal) -> dict:
    return {"yuan": fmt_yuan(amount_yuan), "yi": fmt_yi(amount_yuan)}


def safe_float(x: Any) -> float:
    try:
        f = float(x)
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return f
    except (TypeError, ValueError, OverflowError):
        logger.exception("safe_float: failed to convert %r", type(x).__name__)
        return 0.0
