"""
安全 Decimal 转换（自 MOSS-V2 core_finance 迁入）。
"""
from __future__ import annotations

import logging
import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional

logger = logging.getLogger(__name__)


def safe_decimal(
    value: Any,
    default: Decimal = Decimal("0"),
    precision: Optional[str] = None,
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
            result = Decimal(value)
        elif hasattr(value, "item"):
            py_value = value.item()
            if isinstance(py_value, float) and (math.isnan(py_value) or math.isinf(py_value)):
                return default
            result = Decimal(str(py_value))
        else:
            result = Decimal(str(value))

        if precision:
            result = result.quantize(Decimal(precision), rounding=ROUND_HALF_UP)

        return result

    except (InvalidOperation, ValueError, TypeError, AttributeError) as e:
        logger.debug(
            "[safe_decimal] Conversion failed for value=%r type=%s: %s",
            value,
            type(value).__name__,
            e,
        )
        return default
