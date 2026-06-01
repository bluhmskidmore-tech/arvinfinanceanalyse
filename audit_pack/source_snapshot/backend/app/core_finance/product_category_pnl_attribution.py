from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Any

ZERO = Decimal("0")
DAYS_IN_YEAR = Decimal("365")
TOTAL_CATEGORY_IDS = {"asset_total", "liability_total", "grand_total"}


def build_product_category_attribution_payload(
    *,
    current_rows: list[object],
    prior_rows: list[object],
    current_report_date: str,
    prior_report_date: str,
    compare: str = "mom",
) -> dict[str, object]:
    current_days = _days_in_month(current_report_date)
    prior_days = _days_in_month(prior_report_date)
    current_by_id = {_field(row, "category_id"): row for row in current_rows}
    prior_by_id = {_field(row, "category_id"): row for row in prior_rows}
    ordered_ids = [
        _field(row, "category_id")
        for row in current_rows
        if _field(row, "category_id") not in TOTAL_CATEGORY_IDS
    ]
    ordered_ids.extend(
        category_id
        for category_id in prior_by_id
        if category_id not in TOTAL_CATEGORY_IDS and category_id not in ordered_ids
    )

    rows = [
        _build_row(
            category_id=category_id,
            current=current_by_id.get(category_id),
            prior=prior_by_id.get(category_id),
            current_days=current_days,
            prior_days=prior_days,
        )
        for category_id in ordered_ids
    ]
    totals = _build_totals(
        rows=rows,
        current_by_id=current_by_id,
        prior_by_id=prior_by_id,
        current_days=current_days,
        prior_days=prior_days,
    )
    return {
        "report_date": current_report_date,
        "compare": compare,
        "current_report_date": current_report_date,
        "prior_report_date": prior_report_date,
        "state": "complete",
        "reason": None,
        "rows": rows,
        "totals": totals,
    }


def build_incomplete_product_category_attribution_payload(
    *,
    current_report_date: str,
    prior_report_date: str,
    compare: str = "mom",
    reason: str = "no_prior_month",
) -> dict[str, object]:
    return {
        "report_date": current_report_date,
        "compare": compare,
        "current_report_date": current_report_date,
        "prior_report_date": prior_report_date,
        "state": "incomplete",
        "reason": reason,
        "rows": [],
        "totals": None,
    }


def _build_row(
    *,
    category_id: str,
    current: object | None,
    prior: object | None,
    current_days: int,
    prior_days: int,
) -> dict[str, object]:
    source = current or prior
    if source is None:
        raise ValueError(f"Missing current and prior row for category_id={category_id}")

    effects = _build_effects(
        current=current,
        prior=prior,
        current_days=current_days,
        prior_days=prior_days,
    )
    return {
        "category_id": category_id,
        "category_name": _field(source, "category_name"),
        "side": _field(source, "side"),
        "level": int(_field(source, "level") or 0),
        "state": "complete" if current is not None and prior is not None else "partial",
        "current": _point(current, current_days) if current is not None else None,
        "prior": _point(prior, prior_days) if prior is not None else None,
        "effects": effects,
    }


def _build_effects(
    *,
    current: object | None,
    prior: object | None,
    current_days: int,
    prior_days: int,
) -> dict[str, Decimal]:
    if current is None and prior is None:
        return _effect_dict()

    current_net = _amount(current, "business_net_income") if current is not None else ZERO
    prior_net = _amount(prior, "business_net_income") if prior is not None else ZERO
    delta = current_net - prior_net

    if current is None or prior is None:
        direct_effect = delta if _is_direct_row(current or prior) else ZERO
        unexplained = ZERO if direct_effect else delta
        return _effect_dict(
            direct_effect=direct_effect,
            unexplained_effect=unexplained,
            explained_effect=direct_effect,
            delta_business_net_income=delta,
        )

    if _is_direct_row(current) and _is_direct_row(prior):
        return _effect_dict(
            direct_effect=delta,
            explained_effect=delta,
            delta_business_net_income=delta,
        )

    current_scale = _amount(current, "cnx_scale")
    prior_scale = _amount(prior, "cnx_scale")
    current_cash_rate = _cash_rate(current, current_days)
    prior_cash_rate = _cash_rate(prior, prior_days)
    current_ftp_rate = _amount(current, "baseline_ftp_rate_pct") / Decimal("100")
    prior_ftp_rate = _amount(prior, "baseline_ftp_rate_pct") / Decimal("100")

    cash_effects = _three_factor_effects(
        prior_scale=prior_scale,
        current_scale=current_scale,
        prior_rate=prior_cash_rate,
        current_rate=current_cash_rate,
        prior_days=Decimal(prior_days),
        current_days=Decimal(current_days),
    )
    ftp_effects = _three_factor_effects(
        prior_scale=prior_scale,
        current_scale=current_scale,
        prior_rate=prior_ftp_rate,
        current_rate=current_ftp_rate,
        prior_days=Decimal(prior_days),
        current_days=Decimal(current_days),
    )

    scale_effect = cash_effects["scale"] - ftp_effects["scale"]
    rate_effect = cash_effects["rate"]
    day_effect = cash_effects["day"] - ftp_effects["day"]
    ftp_effect = -ftp_effects["rate"]
    explained = scale_effect + rate_effect + day_effect + ftp_effect
    unexplained = delta - explained
    closure_error = delta - explained - unexplained
    return _effect_dict(
        day_effect=day_effect,
        scale_effect=scale_effect,
        rate_effect=rate_effect,
        ftp_effect=ftp_effect,
        unexplained_effect=unexplained,
        explained_effect=explained,
        delta_business_net_income=delta,
        closure_error=closure_error,
    )


def _three_factor_effects(
    *,
    prior_scale: Decimal,
    current_scale: Decimal,
    prior_rate: Decimal,
    current_rate: Decimal,
    prior_days: Decimal,
    current_days: Decimal,
) -> dict[str, Decimal]:
    return {
        "scale": (current_scale - prior_scale) * prior_rate * prior_days / DAYS_IN_YEAR,
        "rate": current_scale * (current_rate - prior_rate) * prior_days / DAYS_IN_YEAR,
        "day": current_scale * current_rate * (current_days - prior_days) / DAYS_IN_YEAR,
    }


def _build_totals(
    *,
    rows: list[dict[str, object]],
    current_by_id: dict[str, object],
    prior_by_id: dict[str, object],
    current_days: int,
    prior_days: int,
) -> dict[str, object]:
    asset_rows = [row for row in rows if row["side"] == "asset"]
    liability_rows = [row for row in rows if row["side"] == "liability"]
    asset_total = _build_total(
        category_id="asset_total",
        rows=asset_rows,
        current_by_id=current_by_id,
        prior_by_id=prior_by_id,
        current=current_by_id.get("asset_total"),
        prior=prior_by_id.get("asset_total"),
        current_days=current_days,
        prior_days=prior_days,
        fallback_name="资产端合计",
        fallback_side="asset",
    )
    liability_total = _build_total(
        category_id="liability_total",
        rows=liability_rows,
        current_by_id=current_by_id,
        prior_by_id=prior_by_id,
        current=current_by_id.get("liability_total"),
        prior=prior_by_id.get("liability_total"),
        current_days=current_days,
        prior_days=prior_days,
        fallback_name="负债端合计",
        fallback_side="liability",
    )
    grand_total = _build_grand_total(
        category_id="grand_total",
        side_totals=[asset_total, liability_total],
        current=current_by_id.get("grand_total"),
        prior=prior_by_id.get("grand_total"),
        current_days=current_days,
        prior_days=prior_days,
        fallback_name="grand_total",
        fallback_side="all",
    )
    return {
        "asset_total": asset_total,
        "liability_total": liability_total,
        "grand_total": grand_total,
    }


def _build_total(
    *,
    category_id: str,
    rows: list[dict[str, object]],
    current_by_id: dict[str, object],
    prior_by_id: dict[str, object],
    current: object | None,
    prior: object | None,
    current_days: int,
    prior_days: int,
    fallback_name: str,
    fallback_side: str,
) -> dict[str, object]:
    leaf_rows = [
        row
        for row in rows
        if isinstance(row.get("effects"), dict)
        and not (
            _has_children(current_by_id.get(str(row["category_id"])))
            or _has_children(prior_by_id.get(str(row["category_id"])))
        )
    ]
    effect_rows = leaf_rows or rows
    effects = _sum_effects(
        [row["effects"] for row in effect_rows if isinstance(row.get("effects"), dict)]
    )
    source = current or prior
    if source is not None:
        _reconcile_effects_to_actual_delta(effects, current, prior)
    return {
        "category_id": category_id,
        "category_name": _field(source, "category_name") if source is not None else fallback_name,
        "side": _field(source, "side") if source is not None else fallback_side,
        "level": int(_field(source, "level") or 0) if source is not None else 0,
        "state": "complete" if current is not None and prior is not None else "partial",
        "current": _point(current, current_days) if current is not None else None,
        "prior": _point(prior, prior_days) if prior is not None else None,
        "effects": effects,
    }


def _build_grand_total(
    *,
    category_id: str,
    side_totals: list[dict[str, object]],
    current: object | None,
    prior: object | None,
    current_days: int,
    prior_days: int,
    fallback_name: str,
    fallback_side: str,
) -> dict[str, object]:
    effects = _sum_effects(
        [row["effects"] for row in side_totals if isinstance(row.get("effects"), dict)]
    )
    source = current or prior
    if source is not None:
        _reconcile_effects_to_actual_delta(effects, current, prior)

    return {
        "category_id": category_id,
        "category_name": _field(source, "category_name") if source is not None else fallback_name,
        "side": _field(source, "side") if source is not None else fallback_side,
        "level": int(_field(source, "level") or 0) if source is not None else 0,
        "state": "complete" if current is not None and prior is not None else "partial",
        "current": _point(current, current_days) if current is not None else None,
        "prior": _point(prior, prior_days) if prior is not None else None,
        "effects": effects,
    }


def _sum_effects(items: list[dict[str, Any]]) -> dict[str, Decimal]:
    total = _effect_dict()
    for item in items:
        for key in total:
            total[key] += Decimal(str(item.get(key) or ZERO))
    total["closure_error"] = (
        total["delta_business_net_income"]
        - total["explained_effect"]
        - total["unexplained_effect"]
    )
    return total


def _reconcile_effects_to_actual_delta(
    effects: dict[str, Decimal],
    current: object | None,
    prior: object | None,
) -> None:
    actual_delta = _amount(current, "business_net_income") - _amount(prior, "business_net_income")
    unexplained_delta = actual_delta - effects["delta_business_net_income"]
    effects["unexplained_effect"] += unexplained_delta
    effects["delta_business_net_income"] = actual_delta
    effects["closure_error"] = (
        effects["delta_business_net_income"]
        - effects["explained_effect"]
        - effects["unexplained_effect"]
    )


def _point(row: object, days: int) -> dict[str, object]:
    return {
        "report_date": _field(row, "report_date"),
        "days": days,
        "scale": _amount(row, "cnx_scale"),
        "yield_pct": _field(row, "weighted_yield"),
        "cash": _amount(row, "cnx_cash"),
        "ftp": _amount(row, "cny_ftp") + _amount(row, "foreign_ftp"),
        "business_net_income": _amount(row, "business_net_income"),
    }


def _cash_rate(row: object, days: int) -> Decimal:
    weighted_yield = _field(row, "weighted_yield")
    if weighted_yield is not None:
        return Decimal(str(weighted_yield)) / Decimal("100")
    scale = _amount(row, "cnx_scale")
    if scale == ZERO or days <= 0:
        return ZERO
    return _amount(row, "cnx_cash") / Decimal(days) * DAYS_IN_YEAR / scale


def _is_direct_row(row: object | None) -> bool:
    if row is None:
        return True
    return _amount(row, "cnx_scale") == ZERO or _field(row, "weighted_yield") is None


def _has_children(row: object | None) -> bool:
    raw_children = _field(row, "children")
    if raw_children is None:
        raw_children = _field(row, "children_json")
    if raw_children is None:
        return False
    if isinstance(raw_children, str):
        return raw_children.strip() not in {"", "[]", "null"}
    return bool(raw_children)


def _effect_dict(
    *,
    day_effect: Decimal = ZERO,
    scale_effect: Decimal = ZERO,
    rate_effect: Decimal = ZERO,
    ftp_effect: Decimal = ZERO,
    direct_effect: Decimal = ZERO,
    unexplained_effect: Decimal = ZERO,
    explained_effect: Decimal = ZERO,
    delta_business_net_income: Decimal = ZERO,
    closure_error: Decimal = ZERO,
) -> dict[str, Decimal]:
    return {
        "day_effect": day_effect,
        "scale_effect": scale_effect,
        "rate_effect": rate_effect,
        "ftp_effect": ftp_effect,
        "direct_effect": direct_effect,
        "unexplained_effect": unexplained_effect,
        "explained_effect": explained_effect,
        "delta_business_net_income": delta_business_net_income,
        "closure_error": closure_error,
    }


def _amount(row: object | None, field_name: str) -> Decimal:
    if row is None:
        return ZERO
    value = _field(row, field_name)
    if value is None:
        return ZERO
    return Decimal(str(value))


def _field(row: object | None, field_name: str) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(field_name)
    return getattr(row, field_name)


def _days_in_month(report_date: str) -> int:
    parsed = date.fromisoformat(report_date)
    return monthrange(parsed.year, parsed.month)[1]
