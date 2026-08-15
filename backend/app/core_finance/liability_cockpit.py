"""Cockpit warnings + asset-liability contribution split for the liability analytics page.

Derives threshold-based alerts and contribution rows from the same ZQTZ/TYW
position data already consumed by ``compute_liability_risk_buckets`` and
``compute_liability_yield_metrics``.  No new data sources are required.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.liability_analytics_compat import (
    ONE_HUNDRED_MILLION,
    ZERO,
    clean_text,
    compute_liability_yield_metrics,
    is_interbank_cd,
    is_interest_bearing_bond_asset,
    monthly_v1_bucket_name,
    normalize_bond_rate_decimal,
    normalize_interbank_rate_decimal,
    to_decimal,
    to_float,
    zqtz_asset_amount,
    zqtz_liability_amount,
)

# ---------------------------------------------------------------------------
# Alert / warning thresholds (business-calibrated defaults)
# ---------------------------------------------------------------------------
NIM_WARNING_THRESHOLD = Decimal("0")         # NIM ≤ 0 → warning
NIM_WATCH_THRESHOLD = Decimal("0.005")       # NIM ≤ 50bp → watch
CONCENTRATION_WARNING_PCT = Decimal("0.30")  # top-1 counterparty ≥ 30% → warning
SHORT_TERM_PRESSURE_YI = Decimal("100")      # 1Y maturity > 100亿 → warning
LIABILITY_COST_HIGH_THRESHOLD = Decimal("0.035")  # cost ≥ 3.5% → watch


def _kpi_decimal(value: float | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def compute_cockpit_warnings(
    report_date: str,
    zqtz_rows: list[dict[str, Any]],
    tyw_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return ``{ report_date, watch_items: [...], alert_events: [...] }``.

    NIM 与负债成本直接复用 ``compute_liability_yield_metrics``（calc_rules §12.6
    钉住的正式 KPI 口径）：NIM = 资产收益率 − 市场化负债成本（市场化负债缺失时
    回退整体负债成本），避免同页出现「KPI 为正、告警净息差为负」的口径矛盾。
    """
    report_dt = date.fromisoformat(report_date)

    # --- NIM / 负债成本：与页面收益-成本 KPI 完全同源（同一函数计算） ---
    kpi = compute_liability_yield_metrics(report_date, zqtz_rows, tyw_rows)["kpi"]
    liability_cost = _kpi_decimal(kpi["liability_cost"])
    nim = _kpi_decimal(kpi["nim"])

    # --- Rebuild lightweight aggregates from the same data as risk_buckets ---
    total_liability = ZERO
    short_term_liability = ZERO  # ≤1Y bucket

    for row in zqtz_rows:
        if not bool(row.get("is_issuance_like")):
            continue
        amount = zqtz_liability_amount(row)
        if amount > ZERO:
            total_liability += amount
            bucket = monthly_v1_bucket_name(report_dt, row.get("maturity_date"))
            if bucket in ("0-3M", "3-6M", "6-12M", "Matured"):
                short_term_liability += amount

    counterparty_totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in tyw_rows:
        if bool(row.get("is_asset_side")):
            continue
        amount = to_decimal(row.get("principal_native"))
        if amount > ZERO:
            total_liability += amount
            bucket = monthly_v1_bucket_name(report_dt, row.get("maturity_date"))
            if bucket in ("0-3M", "3-6M", "6-12M", "Matured"):
                short_term_liability += amount
            cp = clean_text(row.get("counterparty_name"), "其他")
            counterparty_totals[cp] += amount

    short_term_yi = short_term_liability / ONE_HUNDRED_MILLION

    # Top counterparty concentration
    top_cp_share: Decimal | None = None
    top_cp_name: str = ""
    if total_liability > ZERO and counterparty_totals:
        top_cp_name, top_cp_val = max(counterparty_totals.items(), key=lambda x: x[1])
        top_cp_share = top_cp_val / total_liability

    # --- Build watch items ---
    watch_items: list[dict[str, Any]] = []
    alert_events: list[dict[str, Any]] = []

    # NIM warning（与收益-成本 KPI 同口径：市场化负债成本，缺失时回退整体成本）
    if nim is not None and nim <= NIM_WARNING_THRESHOLD:
        alert_events.append({
            "id": "alert_nim_negative",
            "severity": "high",
            "title": "净息差为负",
            "occurred_at": report_date,
            "detail": f"NIM = {to_float(nim):.4%}，市场化口径负债成本已不低于资产收益率（与收益-成本 KPI 同口径）。",
        })
    elif nim is not None and nim <= NIM_WATCH_THRESHOLD:
        watch_items.append({
            "id": "watch_nim_thin",
            "label": "净息差偏窄",
            "level": "watch",
            "detail": f"NIM = {to_float(nim):.4%}，低于 50bp 关注线。",
        })

    # Counterparty concentration
    if top_cp_share is not None and top_cp_share >= CONCENTRATION_WARNING_PCT:
        watch_items.append({
            "id": "watch_concentration",
            "label": "对手方集中度偏高",
            "level": "warning",
            "detail": f"{top_cp_name} 占比 {to_float(top_cp_share):.1%}，超过 30% 关注线。",
        })

    # Short-term pressure
    if short_term_yi >= SHORT_TERM_PRESSURE_YI:
        alert_events.append({
            "id": "alert_short_term_maturity",
            "severity": "medium",
            "title": "1年内到期负债偏高",
            "occurred_at": report_date,
            "detail": f"1年内到期负债 {to_float(short_term_yi):.0f} 亿元，存在再融资压力。",
        })
    elif short_term_yi > ZERO:
        watch_items.append({
            "id": "watch_short_term_maturity",
            "label": "短期到期关注",
            "level": "watch",
            "detail": f"1年内到期负债 {to_float(short_term_yi):.0f} 亿元。",
        })

    # High liability cost
    if liability_cost is not None and liability_cost >= LIABILITY_COST_HIGH_THRESHOLD:
        watch_items.append({
            "id": "watch_liability_cost_high",
            "label": "负债成本偏高",
            "level": "watch",
            "detail": f"加权负债成本 {to_float(liability_cost):.4%}，超过 3.5% 关注线。",
        })

    return {
        "report_date": report_date,
        "watch_items": watch_items,
        "alert_events": alert_events,
    }


# ---------------------------------------------------------------------------
# Asset / liability contribution split
# ---------------------------------------------------------------------------
def compute_contribution_split(
    report_date: str,
    zqtz_rows: list[dict[str, Any]],
    tyw_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return ``{ report_date, contributions: [...] }`` with per-category breakdown.

    Each contribution row contains:
      - category: '利率债', '信用债', '同业负债', '发行负债', ...
      - side: 'asset' | 'liability'
      - amount_yi: 金额（亿元）
      - yield_or_cost: 加权收益或成本（小数形式）
      - contribution_yi: amount_yi × yield_or_cost  (亿元贡献)
    """
    categories: dict[str, dict[str, Any]] = {}

    def _ensure(cat: str, side: str) -> dict[str, Any]:
        key = f"{side}|{cat}"
        if key not in categories:
            categories[key] = {
                "category": cat,
                "side": side,
                "amount": ZERO,
                "weighted_num": ZERO,
                "weighted_den": ZERO,
            }
        return categories[key]

    # -- ZQTZ: bonds --
    for row in zqtz_rows:
        if bool(row.get("is_issuance_like")):
            # liability side (issued bonds)
            amount = zqtz_liability_amount(row)
            if amount <= ZERO:
                continue
            rate = normalize_bond_rate_decimal(row.get("coupon_rate"))
            if rate is None:
                rate = normalize_bond_rate_decimal(row.get("interest_rate"))
            bond_type = clean_text(row.get("bond_type"), "发行债券")
            if is_interbank_cd(row):
                cat = "同业存单"
            else:
                cat = bond_type
            entry = _ensure(cat, "liability")
            entry["amount"] += amount
            if rate is not None:
                entry["weighted_num"] += amount * rate
                entry["weighted_den"] += amount
        elif is_interest_bearing_bond_asset(row):
            amount = zqtz_asset_amount(row)
            if amount <= ZERO:
                continue
            ytm = normalize_bond_rate_decimal(row.get("ytm_value"))
            coupon = normalize_bond_rate_decimal(row.get("coupon_rate"))
            # 同上：0 视为未采集，显式回退到下一候选，与
            # liability_analytics_compat.compute_liability_yield_metrics 保持一致。
            rate = ytm if ytm not in (None, ZERO) else coupon
            # Classify: 利率债 vs 信用债 (simplified)
            asset_class = str(row.get("asset_class") or "").strip()
            bond_type = str(row.get("bond_type") or "").strip()
            if any(k in bond_type for k in ("国债", "政金债", "政策性", "地方政府")) or "国债" in asset_class:
                cat = "利率债"
            elif any(k in bond_type for k in ("基金",)):
                cat = "基金类"
            else:
                cat = "信用债"
            entry = _ensure(cat, "asset")
            entry["amount"] += amount
            if rate is not None:
                entry["weighted_num"] += amount * rate
                entry["weighted_den"] += amount

    # -- TYW: interbank --
    for row in tyw_rows:
        amount = to_decimal(row.get("principal_native"))
        if amount <= ZERO:
            continue
        rate = normalize_interbank_rate_decimal(row.get("funding_cost_rate"))
        product_type = clean_text(row.get("product_type"), "同业其他")
        if bool(row.get("is_asset_side")):
            entry = _ensure(product_type, "asset")
        else:
            entry = _ensure(product_type, "liability")
        entry["amount"] += amount
        if rate is not None:
            entry["weighted_num"] += amount * rate
            entry["weighted_den"] += amount

    # -- Build payload rows --
    contributions: list[dict[str, Any]] = []
    for _key, entry in sorted(
        categories.items(),
        key=lambda x: (0 if x[1]["side"] == "asset" else 1, -x[1]["amount"]),
    ):
        amount_yi = entry["amount"] / ONE_HUNDRED_MILLION
        yield_or_cost = (
            entry["weighted_num"] / entry["weighted_den"]
            if entry["weighted_den"] > ZERO
            else None
        )
        contribution_yi = (
            amount_yi * yield_or_cost
            if yield_or_cost is not None
            else None
        )
        contributions.append({
            "category": entry["category"],
            "side": entry["side"],
            "amount_yi": to_float(amount_yi),
            "yield_or_cost": to_float(yield_or_cost),
            "contribution_yi": to_float(contribution_yi),
        })

    return {
        "report_date": report_date,
        "contributions": contributions,
    }
