"""从 market_data_livermore_service 拆出的输入新鲜度降级口径。

门面模块逐名 re-export；行为与拆分前完全一致。
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date

from backend.app.core_finance.data_freshness import (
    FRESHNESS_TIER_EXPIRED,
    FRESHNESS_TIER_FRESH,
    FRESHNESS_TIER_STALE,
)

INPUT_FRESHNESS_DEGRADED_DIAGNOSTIC_CODE = "LIVERMORE_INPUT_FRESHNESS_DEGRADED"
INPUT_FRESHNESS_LOOK_AHEAD_STATUS = "look_ahead"
INPUT_FRESHNESS_DEGRADED_TIERS = frozenset({FRESHNESS_TIER_STALE, FRESHNESS_TIER_EXPIRED})
_INPUT_FRESHNESS_TIER_RANK = {
    FRESHNESS_TIER_EXPIRED: 3,
    FRESHNESS_TIER_STALE: 2,
    FRESHNESS_TIER_FRESH: 1,
}


_INPUT_FRESHNESS_NOTE_CATEGORY_BY_FAMILY = {
    "PMI": "宏观输入",
    "credit_impulse": "宏观输入",
    "price_spread": "宏观输入",
    "turnover_persistence": "股票日线输入",
    "valuation_percentile_history": "因子快照输入",
}


def _cycle_input_freshness_date(business_date: str, *, cadence: str) -> str:
    """Use month-end for provider rows keyed to the first day of their statistical month."""
    if cadence != "monthly":
        return business_date
    try:
        parsed = date.fromisoformat(business_date)
    except ValueError:
        return business_date
    if parsed.day != 1:
        return business_date
    return parsed.replace(day=monthrange(parsed.year, parsed.month)[1]).isoformat()


def _input_freshness_severity(entry: dict[str, object]) -> tuple[int, int]:
    tier_rank = _INPUT_FRESHNESS_TIER_RANK.get(str(entry.get("tier") or ""), 0)
    age_days = entry.get("age_days")
    return tier_rank, age_days if isinstance(age_days, int) else -(10**9)


def _merge_input_freshness_into_data_gaps(
    *,
    data_gaps: list[dict[str, object]],
    input_freshness: list[dict[str, object]],
) -> None:
    """Extend existing data_gaps entries with freshness evidence; flag look-ahead-dated inputs."""
    worst_by_family: dict[str, dict[str, object]] = {}
    for entry in input_freshness:
        family = str(entry.get("input_family") or "")
        current = worst_by_family.get(family)
        if current is None or _input_freshness_severity(entry) > _input_freshness_severity(current):
            worst_by_family[family] = entry
    for gap in data_gaps:
        entry = worst_by_family.get(str(gap.get("input_family") or ""))
        if entry is None:
            continue
        gap["input"] = str(entry.get("input") or "")
        gap["business_date"] = str(entry.get("business_date") or "")
        gap["age_days"] = entry.get("age_days")
        gap["tier"] = str(entry.get("tier") or "")
    for entry in input_freshness:
        age_days = entry.get("age_days")
        if isinstance(age_days, int) and age_days < 0:
            data_gaps.append(
                {
                    "input_family": str(entry.get("input_family") or ""),
                    "input": str(entry.get("input") or ""),
                    "status": INPUT_FRESHNESS_LOOK_AHEAD_STATUS,
                    "evidence": (
                        f"{entry.get('input')} business_date {entry.get('business_date')} is later than the "
                        f"resolved trade_date (age_days={age_days}); flagged as a look-ahead risk."
                    ),
                    "business_date": str(entry.get("business_date") or ""),
                    "age_days": age_days,
                    "tier": str(entry.get("tier") or ""),
                }
            )


def _input_freshness_degradation_notes(
    input_freshness: list[dict[str, object]],
) -> list[dict[str, str | None]]:
    notes: list[dict[str, str | None]] = []
    for entry in input_freshness:
        tier = str(entry.get("tier") or "")
        if tier not in INPUT_FRESHNESS_DEGRADED_TIERS:
            continue
        family = str(entry.get("input_family") or "")
        category = _INPUT_FRESHNESS_NOTE_CATEGORY_BY_FAMILY.get(family, "关键输入")
        notes.append(
            {
                "severity": "warning",
                "code": INPUT_FRESHNESS_DEGRADED_DIAGNOSTIC_CODE,
                "message": (
                    f"{category} {entry.get('input')} 数据滞后 {entry.get('age_days')} 天（{tier}），信号质量降级"
                ),
                "input_family": family,
            }
        )
    return notes


def _degrade_quality_flag_for_input_freshness(
    quality_flag: str,
    input_freshness: list[dict[str, object]],
) -> str:
    """Any stale/expired key input downgrades an otherwise-ok result to warning; never upgrades."""
    if quality_flag != "ok":
        return quality_flag
    has_lagging_input = any(str(entry.get("tier") or "") in INPUT_FRESHNESS_DEGRADED_TIERS for entry in input_freshness)
    return "warning" if has_lagging_input else quality_flag
