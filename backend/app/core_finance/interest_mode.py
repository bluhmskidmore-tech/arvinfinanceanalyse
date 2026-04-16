from __future__ import annotations


def classify_interest_payment_frequency(value: object) -> str:
    normalized, compact = _normalize_value(value)
    if compact in {"bullet", "maturitybullet", "到期一次还本付息", "到期还本付息", "到期付息"}:
        return "bullet"
    if "quarter" in normalized or "季" in normalized:
        return "quarterly"
    if "semi" in compact or "半年" in normalized:
        return "semi-annual"
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
    return "annual", True


def coupon_interval_months(value: object) -> int:
    frequency, _used_fallback = resolve_interest_payment_frequency(value)
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
