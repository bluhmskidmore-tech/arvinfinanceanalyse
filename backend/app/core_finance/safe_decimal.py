"""
安全 Decimal 转换（自 MOSS-V2 core_finance 迁入）。
"""
from __future__ import annotations

import logging
import math
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)

# 中文 Excel 导出常见的千分位分组，如 "1,234.56" / "-1,234,567.89"。仅严格匹配
# 三位分组才去逗号解析；"1,2" / "1,23" 这类非三位分组语义存疑，不在此放行，
# 维持既有 warning + default 降级路径。
_THOUSANDS_SEPARATOR_RE = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")


def safe_decimal(
    value: Any,
    default: Decimal = Decimal("0"),
    precision: str | None = None,
) -> Decimal:
    if value is None:
        return default

    try:
        if isinstance(value, Decimal):
            result = value
        elif isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return default
            result = Decimal(str(value))
        elif isinstance(value, str):
            value = value.strip()
            if not value or value.lower() in ("nan", "inf", "-inf", "none", "null", ""):
                return default
            if _THOUSANDS_SEPARATOR_RE.match(value):
                result = Decimal(value.replace(",", ""))
            else:
                result = Decimal(value)
        elif hasattr(value, "item"):
            py_value = value.item()
            if isinstance(py_value, float) and (math.isnan(py_value) or math.isinf(py_value)):
                return default
            result = Decimal(str(py_value))
        else:
            result = Decimal(str(value))

        # Decimal("NaN") / Decimal("Infinity") 输入（或字符串等转换产物）不得静默传播。
        if not result.is_finite():
            return default

        if precision:
            result = result.quantize(Decimal(precision), rounding=ROUND_HALF_UP)

        return result

    except (InvalidOperation, ValueError, TypeError, AttributeError) as e:
        # 转换失败会静默把业务金额压成 default（通常是 0），debug 级在生产日志里
        # 不可见，等于放行一次静默降级；按 warning 级披露。
        logger.warning(
            "[safe_decimal] Conversion failed for value=%r type=%s: %s",
            value,
            type(value).__name__,
            e,
        )
        return default
