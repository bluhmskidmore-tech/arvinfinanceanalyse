"""
USD/CNY 汇率解析（自 MOSS-V2 core_finance 迁入，纯函数）。

rows: (trade_date, usdcny) 可无序，内部排序。
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple

from .decimal_utils import to_decimal


def get_usd_cny_rate(
    rows: List[Tuple[date, Optional[Decimal]]],
    target_date: date,
) -> Tuple[Decimal, Optional[date], List[str]]:
    warnings: List[str] = []
    default_rate = Decimal("7.25")

    valid = [(d, to_decimal(v)) for d, v in rows if v is not None and to_decimal(v) > 0]
    if not valid:
        warnings.append("USD/CNY 无输入行：使用默认 7.25")
        return default_rate, None, warnings

    valid.sort(key=lambda x: x[0])

    for d, r in valid:
        if d == target_date:
            return r, d, warnings

    start = target_date - timedelta(days=30)
    before = [(d, r) for d, r in valid if start <= d < target_date]
    if before:
        d, r = before[-1]
        warnings.append(f"USD/CNY 未找到 {target_date} 当天数据：使用最近日期 {d}")
        return r, d, warnings

    d, r = valid[-1]
    warnings.append(f"USD/CNY 未找到近30天数据：使用库内最新日期 {d}")
    return r, d, warnings
