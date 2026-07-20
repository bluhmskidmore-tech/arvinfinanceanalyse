from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 每个进程内对同一原始取值只披露一次，避免大批量行情/余额行刷屏。
_FALLBACK_DISCLOSED_VALUES: set[str] = set()


def classify_interest_payment_frequency(value: object) -> str:
    normalized, compact = _normalize_value(value)
    if compact in {"bullet", "maturitybullet", "到期一次还本付息", "到期还本付息", "到期付息"}:
        return "bullet"
    if "quarter" in normalized or "季" in normalized:
        return "quarterly"
    if "semi" in compact or "半年" in normalized:
        return "semi-annual"
    # 注意不要把"3个月"/"6个月"这类数字月份表述误判为按月付息，
    # 因此只匹配明确的按月表述，而不是裸"月"字。
    if "monthly" in compact or any(token in normalized for token in ("按月", "每月", "月付")):
        return "monthly"
    if "annual" in compact or "yearly" in compact or "年" in normalized:
        return "annual"
    return "unknown"


def classify_interest_rate_style(value: object) -> str:
    normalized, compact = _normalize_value(value)
    if any(token in normalized or token in compact for token in ("固定", "fixed", "fix")):
        return "fixed"
    if any(token in normalized or token in compact for token in ("浮动", "floating", "float", "浮息")):
        return "floating"
    return "unknown"


def resolve_interest_payment_frequency(value: object) -> tuple[str, bool]:
    frequency = classify_interest_payment_frequency(value)
    if frequency != "unknown":
        return frequency, False
    # 多数调用方（coupon_frequency_per_year / coupon_interval_months /
    # is_bullet_repayment / engine）会丢弃 fallback 标志，因此在源头做一次
    # 去重披露。"固定"/"浮动"是仅声明利率风格的合法遗留取值，按既有口径
    # 静默回退年付，不告警（与 risk_tensor 的 unsupported 判定一致）。
    raw = str(value or "").strip()
    if raw and classify_interest_rate_style(raw) == "unknown" and raw not in _FALLBACK_DISCLOSED_VALUES:
        _FALLBACK_DISCLOSED_VALUES.add(raw)
        logger.warning(
            "resolve_interest_payment_frequency: unrecognized interest_mode=%r fell back to annual coupon frequency (first occurrence per process).",
            raw,
        )
    return "annual", True


def coupon_frequency_per_year(value: object) -> int:
    frequency, _used_fallback = resolve_interest_payment_frequency(value)
    if frequency == "monthly":
        return 12
    if frequency == "quarterly":
        return 4
    if frequency == "semi-annual":
        return 2
    return 1


def coupon_interval_months(value: object) -> int:
    frequency, _used_fallback = resolve_interest_payment_frequency(value)
    if frequency == "monthly":
        return 1
    if frequency == "quarterly":
        return 3
    if frequency == "semi-annual":
        return 6
    return 12


def is_bullet_repayment(value: object) -> bool:
    frequency, _used_fallback = resolve_interest_payment_frequency(value)
    return frequency == "bullet"


def _normalize_value(value: object) -> tuple[str, str]:
    normalized = str(value or "").strip().lower().replace("_", "-")
    compact = normalized.replace(" ", "")
    return normalized, compact
