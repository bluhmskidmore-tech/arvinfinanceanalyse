from __future__ import annotations

from decimal import Decimal, InvalidOperation
from hashlib import sha256

PRODUCT_CATEGORY_RULE_VERSION = "rv_product_category_pnl_v2"
PRODUCT_CATEGORY_FORMAL_CACHE_VERSION = (
    f"cv_product_category_pnl_formal__{PRODUCT_CATEGORY_RULE_VERSION}"
)
PRODUCT_CATEGORY_SCENARIO_CACHE_VERSION = (
    f"cv_product_category_pnl_scenario__{PRODUCT_CATEGORY_RULE_VERSION}"
)


def _scenario_profile_hash(scenario_rate_pct: object) -> str:
    if scenario_rate_pct is None:
        raise ValueError("scenario_rate_pct is required for a scenario cache version")
    try:
        rate = Decimal(str(scenario_rate_pct))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid scenario_rate_pct={scenario_rate_pct!r}") from exc
    if not rate.is_finite():
        raise ValueError(f"Invalid scenario_rate_pct={scenario_rate_pct!r}")
    normalized_rate = format(rate.normalize(), "f")
    if normalized_rate == "-0":
        normalized_rate = "0"
    profile = f"scenario_rate_pct={normalized_rate}"
    return sha256(profile.encode("utf-8")).hexdigest()[:12]


def product_category_cache_version(
    basis: str,
    *,
    scenario_rate_pct: object | None = None,
) -> str:
    if basis == "formal":
        if scenario_rate_pct is not None:
            raise ValueError("scenario_rate_pct is not allowed for a formal cache version")
        return PRODUCT_CATEGORY_FORMAL_CACHE_VERSION
    if basis == "scenario":
        return (
            f"{PRODUCT_CATEGORY_SCENARIO_CACHE_VERSION}"
            f"__ph_{_scenario_profile_hash(scenario_rate_pct)}"
        )
    raise ValueError(f"Unsupported product-category cache basis={basis!r}")
