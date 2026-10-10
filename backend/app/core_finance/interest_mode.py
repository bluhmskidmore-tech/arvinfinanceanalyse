from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 每个进程内对同一原始取值只披露一次，避免大批量行情/余额行刷屏。
_FALLBACK_DISCLOSED_VALUES: set[str] = set()
# 空值没有可去重的原始字面量，用一个不会与真实取值冲突的哨兵占位。
_EMPTY_VALUE_DISCLOSURE_KEY = "<empty>"


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
    # 去重披露。"固定"/"浮动" 只声明利率风格、同样推不出付息频率，回退年付
    # 与任何未知取值等价，因此不再豁免告警：正式表 1750/1750 行都走这条分支，
    # 豁免会让 100% 的回退看起来像"没有回退"（2026-08 审计）。
    raw = str(value or "").strip()
    disclosure_key = raw or _EMPTY_VALUE_DISCLOSURE_KEY
    if disclosure_key not in _FALLBACK_DISCLOSED_VALUES:
        _FALLBACK_DISCLOSED_VALUES.add(disclosure_key)
        logger.warning(
            "resolve_interest_payment_frequency: interest_mode=%r carries no payment frequency "
            "(rate_style=%s) and fell back to annual coupon frequency; the annual result is a "
            "fallback, not an observed frequency (first occurrence per process per value).",
            raw,
            classify_interest_rate_style(raw),
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
