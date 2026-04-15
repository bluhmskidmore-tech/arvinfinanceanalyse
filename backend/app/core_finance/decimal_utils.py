"""
Decimal 工具（自 MOSS-V2 core_finance 迁入）。
"""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

YI = Decimal("100000000")


def to_decimal(x: Any) -> Decimal:
    if x is None:
        return Decimal("0")
    if isinstance(x, Decimal):
        return x
    try:
        if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
            return Decimal("0")
    except Exception:
        pass
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal("0")


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
    except Exception:
        return 0.0
