"""Pure read-model calculations over materialized bond analytics fact rows."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.bond_analytics.common import (
    STANDARD_SCENARIOS,
    build_curve_points,
    build_full_curve,
    infer_curve_type,
    interpolate_rate,
)
from backend.app.core_finance.bond_analytics.engine import ENGINE_RULE_VERSION
from backend.app.core_finance.bond_analytics.common import safe_decimal

ZERO = Decimal("0")
BENCHMARK_DURATION_ASSUMPTIONS: dict[str, Decimal] = {
    "TREASURY_INDEX": Decimal("6"),
    "CDB_INDEX": Decimal("5"),
    "AAA_CREDIT_INDEX": Decimal("4"),
}
BENCHMARK_BUCKET_WEIGHTS: dict[str, dict[str, Decimal]] = {
    "TREASURY_INDEX": {
        "1Y": Decimal("0.10"),
        "2Y": Decimal("0.15"),
        "3Y": Decimal("0.20"),
        "5Y": Decimal("0.25"),
        "7Y": Decimal("0.15"),
        "10Y": Decimal("0.10"),
        "20Y": Decimal("0.03"),
        "30Y": Decimal("0.02"),
    },
    "CDB_INDEX": {
        "1Y": Decimal("0.10"),
        "2Y": Decimal("0.20"),
        "3Y": Decimal("0.25"),
        "5Y": Decimal("0.25"),
        "7Y": Decimal("0.10"),
        "10Y": Decimal("0.10"),
    },
    "AAA_CREDIT_INDEX": {
        "1Y": Decimal("0.15"),
        "2Y": Decimal("0.25"),
        "3Y": Decimal("0.30"),
        "5Y": Decimal("0.20"),
        "7Y": Decimal("0.10"),
    },
}


def summarize_return_decomposition(
    rows: list[dict[str, Any]],
    *,
    period_start: date,
    period_end: date,
    treasury_curve_current: dict[str, Decimal] | None = None,
    treasury_curve_prior: dict[str, Decimal] | None = None,
    cdb_curve_current: dict[str, Decimal] | None = None,
    cdb_curve_prior: dict[str, Decimal] | None = None,
    aaa_credit_curve_current: dict[str, Decimal] | None = None,
    aaa_credit_curve_prior: dict[str, Decimal] | None = None,
    fx_rates_current: dict[str, Decimal] | None = None,
    fx_rates_prior: dict[str, Decimal] | None = None,
) -> dict[str, Any]:
    days = Decimal((period_end - period_start).days + 1)
    detail_rows = []
    carry_total = ZERO
    roll_down_total = ZERO
    rate_effect_total = ZERO
    spread_effect_total = ZERO
    convexity_effect_total = ZERO
    fx_effect_total = ZERO
    for row in rows:
        carry = safe_decimal(row.get("coupon_rate")) * safe_decimal(row.get("face_value")) * days / Decimal("365")
        curve_type = infer_curve_type(
            row.get("instrument_name"),
            row.get("bond_type"),
            row.get("asset_class_raw"),
        )
        current_curve = cdb_curve_current if curve_type == "cdb" else treasury_curve_current
        prior_curve = cdb_curve_prior if curve_type == "cdb" else treasury_curve_prior
        years_to_maturity = _to_years(row.get("years_to_maturity"))
        modified_duration = safe_decimal(row.get("modified_duration"))
        market_value = safe_decimal(row.get("market_value"))
        roll_down = _curve_roll_down(
            current_curve=current_curve,
            years_to_maturity=years_to_maturity,
            period_days=int(days),
            modified_duration=modified_duration,
            market_value=market_value,
        )
        rate_effect = _curve_rate_effect(
            current_curve=current_curve,
            prior_curve=prior_curve,
            years_to_maturity=years_to_maturity,
            modified_duration=modified_duration,
            market_value=market_value,
        )
        convexity_effect = _convexity_effect(
            row=row,
            current_curve=current_curve,
            prior_curve=prior_curve,
            market_value=market_value,
        )
        spread_effect = _spread_effect(
            row=row,
            treasury_curve_current=treasury_curve_current,
            treasury_curve_prior=treasury_curve_prior,
            aaa_credit_curve_current=aaa_credit_curve_current,
            aaa_credit_curve_prior=aaa_credit_curve_prior,
            years_to_maturity=years_to_maturity,
            modified_duration=modified_duration,
            market_value=market_value,
        )
        fx_effect = _fx_effect(
            row=row,
            fx_rates_current=fx_rates_current,
            fx_rates_prior=fx_rates_prior,
        )
        carry_total += carry
        roll_down_total += roll_down
        rate_effect_total += rate_effect
        spread_effect_total += spread_effect
        convexity_effect_total += convexity_effect
        fx_effect_total += fx_effect
        detail_rows.append(
            {
                **row,
                "carry": carry,
                "roll_down": roll_down,
                "rate_effect": rate_effect,
                "spread_effect": spread_effect,
                "convexity_effect": convexity_effect,
                "fx_effect": fx_effect,
                "total": carry + roll_down + rate_effect + spread_effect + convexity_effect + fx_effect,
            }
        )
    return {
        "carry_total": carry_total,
        "roll_down_total": roll_down_total,
        "rate_effect_total": rate_effect_total,
        "spread_effect_total": spread_effect_total,
        "convexity_effect_total": convexity_effect_total,
        "fx_effect_total": fx_effect_total,
        "total_market_value": _sum(rows, "market_value"),
        "bond_count": len(rows),
        "bond_details": detail_rows,
        "by_asset_class": _aggregate_return(detail_rows, "asset_class_std"),
        "by_accounting_class": _aggregate_return(detail_rows, "accounting_class"),
    }


def compute_benchmark_excess(
    rows: list[dict[str, Any]],
    *,
    period_start: date,
    period_end: date,
    benchmark_id: str,
    benchmark_curve_current: dict[str, Decimal] | None,
    benchmark_curve_prior: dict[str, Decimal] | None,
    treasury_curve_current: dict[str, Decimal] | None = None,
    treasury_curve_prior: dict[str, Decimal] | None = None,
    cdb_curve_current: dict[str, Decimal] | None = None,
    cdb_curve_prior: dict[str, Decimal] | None = None,
    aaa_credit_curve_current: dict[str, Decimal] | None = None,
    aaa_credit_curve_prior: dict[str, Decimal] | None = None,
) -> dict[str, Any]:
    risk = summarize_portfolio_risk(rows)
    total_market_value = safe_decimal(risk["total_market_value"])
    portfolio_duration = safe_decimal(risk["portfolio_modified_duration"])
    benchmark_duration = _benchmark_duration(benchmark_id)
    zero_result = {
        "portfolio_return": ZERO,
        "benchmark_return": ZERO,
        "excess_return": ZERO,
        "duration_effect": ZERO,
        "curve_effect": ZERO,
        "spread_effect": ZERO,
        "selection_effect": ZERO,
        "allocation_effect": ZERO,
        "explained_excess": ZERO,
        "recon_error": ZERO,
        "portfolio_duration": portfolio_duration,
        "benchmark_duration": ZERO,
        "duration_diff": portfolio_duration,
        "excess_sources": _excess_sources(
            duration_effect=ZERO,
            curve_effect=ZERO,
            spread_effect=ZERO,
            selection_effect=ZERO,
            allocation_effect=ZERO,
        ),
    }
    if (
        not rows
        or total_market_value == ZERO
        or not benchmark_curve_current
        or not benchmark_curve_prior
    ):
        return zero_result

    delta_by_bucket = _curve_delta_by_bucket(
        benchmark_curve_current=benchmark_curve_current,
        benchmark_curve_prior=benchmark_curve_prior,
    )
    portfolio_krd = _portfolio_krd_by_bucket(rows, total_market_value=total_market_value)
    benchmark_krd = _benchmark_krd_by_bucket(benchmark_id, benchmark_duration=benchmark_duration)
    all_buckets = sorted(set(delta_by_bucket) | set(portfolio_krd) | set(benchmark_krd))

    return_summary = summarize_return_decomposition(
        rows,
        period_start=period_start,
        period_end=period_end,
        treasury_curve_current=treasury_curve_current,
        treasury_curve_prior=treasury_curve_prior,
        cdb_curve_current=cdb_curve_current,
        cdb_curve_prior=cdb_curve_prior,
        aaa_credit_curve_current=aaa_credit_curve_current,
        aaa_credit_curve_prior=aaa_credit_curve_prior,
    )
    portfolio_return = _return_pct(
        total_effect=_summary_total_for_excess_return(return_summary),
        total_market_value=total_market_value,
    )
    benchmark_return = -sum(
        (benchmark_krd.get(bucket, ZERO) * delta_by_bucket.get(bucket, ZERO) for bucket in all_buckets),
        ZERO,
    )
    excess_return = (portfolio_return - benchmark_return) * Decimal("100")
    benchmark_delta = ZERO if benchmark_duration == ZERO else -(benchmark_return / benchmark_duration)
    duration_effect = -((portfolio_duration - benchmark_duration) * benchmark_delta * Decimal("100"))
    curve_effect = -sum(
        (
            (portfolio_krd.get(bucket, ZERO) - benchmark_krd.get(bucket, ZERO))
            * (delta_by_bucket.get(bucket, ZERO) - benchmark_delta)
            for bucket in all_buckets
        ),
        ZERO,
    ) * Decimal("100")
    credit_rows = [row for row in rows if str(row.get("asset_class_std")) == "credit"]
    spread_effect = _weighted_spread_change(
        credit_rows,
        aaa_credit_curve_current=aaa_credit_curve_current,
        aaa_credit_curve_prior=aaa_credit_curve_prior,
        treasury_curve_current=treasury_curve_current,
        treasury_curve_prior=treasury_curve_prior,
        total_market_value=total_market_value,
    ) * Decimal("100")
    allocation_effect = _compute_allocation_effect(
        rows,
        benchmark_id=benchmark_id,
        benchmark_return=benchmark_return,
        total_market_value=total_market_value,
        period_start=period_start,
        period_end=period_end,
        treasury_curve_current=treasury_curve_current,
        treasury_curve_prior=treasury_curve_prior,
        cdb_curve_current=cdb_curve_current,
        cdb_curve_prior=cdb_curve_prior,
        aaa_credit_curve_current=aaa_credit_curve_current,
        aaa_credit_curve_prior=aaa_credit_curve_prior,
    )
    selection_effect = excess_return - duration_effect - curve_effect - spread_effect - allocation_effect
    explained_excess = duration_effect + curve_effect + spread_effect + selection_effect + allocation_effect
    recon_error = excess_return - explained_excess
    return {
        "portfolio_return": portfolio_return,
        "benchmark_return": benchmark_return,
        "excess_return": excess_return,
        "duration_effect": duration_effect,
        "curve_effect": curve_effect,
        "spread_effect": spread_effect,
        "selection_effect": selection_effect,
        "allocation_effect": allocation_effect,
        "explained_excess": explained_excess,
        "recon_error": recon_error,
        "portfolio_duration": portfolio_duration,
        "benchmark_duration": benchmark_duration,
        "duration_diff": portfolio_duration - benchmark_duration,
        "excess_sources": _excess_sources(
            duration_effect=duration_effect,
            curve_effect=curve_effect,
            spread_effect=spread_effect,
            selection_effect=selection_effect,
            allocation_effect=allocation_effect,
        ),
    }


def summarize_portfolio_risk(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_market_value = _sum(rows, "market_value")
    return {
        "bond_count": len(rows),
        "total_market_value": total_market_value,
        "portfolio_duration": _weighted(rows, "macaulay_duration"),
        "portfolio_modified_duration": _weighted(rows, "modified_duration"),
        "portfolio_convexity": _weighted(rows, "convexity"),
        "portfolio_dv01": _sum(rows, "dv01"),
    }


def build_krd_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["tenor_bucket"])].append(row)
    return [
        {
            "tenor_bucket": tenor_bucket,
            "market_value": _sum(bucket_rows, "market_value"),
            "dv01": _sum(bucket_rows, "dv01"),
            "krd": _weighted(bucket_rows, "modified_duration"),
        }
        for tenor_bucket, bucket_rows in sorted(grouped.items())
    ]


def build_curve_scenarios(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_build_curve_scenario(rows, scenario) for scenario in STANDARD_SCENARIOS]


def build_asset_class_risk_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total_market_value = _sum(rows, "market_value")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["asset_class_std"])].append(row)
    return [
        {
            "asset_class": asset_class,
            "market_value": _sum(asset_rows, "market_value"),
            "duration": _weighted(asset_rows, "macaulay_duration"),
            "dv01": _sum(asset_rows, "dv01"),
            "weight": _ratio(_sum(asset_rows, "market_value"), total_market_value),
        }
        for asset_class, asset_rows in sorted(grouped.items())
    ]


def summarize_credit(
    rows: list[dict[str, Any]],
    *,
    total_rows: list[dict[str, Any]],
    aaa_credit_curve_current: dict[str, Decimal] | None = None,
    treasury_curve_current: dict[str, Decimal] | None = None,
) -> dict[str, Any]:
    total_market_value = _sum(total_rows, "market_value")
    credit_market_value = _sum(rows, "market_value")
    weighted_avg_spread = _weighted_average_spread(
        rows,
        aaa_credit_curve_current=aaa_credit_curve_current,
        treasury_curve_current=treasury_curve_current,
    )
    return {
        "total_market_value": total_market_value,
        "credit_bond_count": len(rows),
        "credit_market_value": credit_market_value,
        "credit_weight": _ratio(credit_market_value, total_market_value),
        "spread_dv01": _sum(rows, "spread_dv01"),
        "weighted_avg_spread_duration": _weighted(rows, "modified_duration"),
        "weighted_avg_spread": weighted_avg_spread,
        "oci_credit_exposure": _sum([row for row in rows if str(row["accounting_class"]) == "OCI"], "market_value"),
        "oci_spread_dv01": _sum([row for row in rows if str(row["accounting_class"]) == "OCI"], "spread_dv01"),
        "tpl_spread_dv01": _sum([row for row in rows if str(row["accounting_class"]) == "TPL"], "spread_dv01"),
    }


# Domestic main-grade ladder (strong → weak). Used for AA-and-below portfolio weight in credit-spread migration.
_RATING_LADDER_DOMESTIC: tuple[str, ...] = (
    "AAA",
    "AA+",
    "AA",
    "AA-",
    "A+",
    "A",
    "A-",
    "BBB+",
    "BBB",
    "BBB-",
    "BB+",
    "BB",
    "BB-",
    "B+",
    "B",
    "B-",
    "CCC",
    "CC",
    "C",
    "D",
)


def _domestic_rating_rank(raw: object) -> int | None:
    if raw is None:
        return None
    key = str(raw).strip().upper()
    if not key:
        return None
    try:
        return _RATING_LADDER_DOMESTIC.index(key)
    except ValueError:
        return None


def rating_aa_and_below_portfolio_weight(
    credit_rows: list[dict[str, Any]],
    *,
    total_portfolio_market_value: Decimal,
) -> Decimal:
    """Market-value weight of credit bonds rated **AA or weaker** vs **total portfolio** MV.

    Includes ``AA``, ``AA-``, ``A+``, …; excludes ``AAA`` and ``AA+``. Unrecognized ``rating``
    strings are omitted from the numerator (not treated as low-grade).
    """
    if total_portfolio_market_value == ZERO or not credit_rows:
        return ZERO
    threshold = _RATING_LADDER_DOMESTIC.index("AA")
    sub = ZERO
    for row in credit_rows:
        rank = _domestic_rating_rank(row.get("rating"))
        if rank is not None and rank >= threshold:
            sub += safe_decimal(row["market_value"])
    return _ratio(sub, total_portfolio_market_value)


def build_concentration(rows: list[dict[str, Any]], *, field_name: str, dimension: str) -> dict[str, Any] | None:
    total_market_value = _sum(rows, "market_value")
    if total_market_value == ZERO or not rows:
        return None
    grouped: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in rows:
        grouped[str(row.get(field_name) or "unknown")] += safe_decimal(row["market_value"])
    ranked = sorted(grouped.items(), key=lambda item: (-item[1], item[0]))
    return {
        "dimension": dimension,
        "hhi": sum((_ratio(value, total_market_value) ** 2 for _name, value in ranked), ZERO),
        "top5_concentration": sum((_ratio(value, total_market_value) for _name, value in ranked[:5]), ZERO),
        "top_items": [
            {
                "name": name,
                "weight": _ratio(value, total_market_value),
                "market_value": value,
            }
            for name, value in ranked[:5]
        ],
    }


def summarize_accounting_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_market_value = _sum(rows, "market_value")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["asset_class_raw"])].append(row)
    item_rows: list[dict[str, Any]] = []
    for asset_class_raw, asset_rows in sorted(grouped.items()):
        dominant = max(asset_rows, key=lambda row: safe_decimal(row["market_value"]))
        inferred = infer_accounting_class_from_rule_id(str(dominant.get("accounting_rule_id") or ""))
        mapped = str(dominant.get("accounting_class") or "other")
        market_value = _sum(asset_rows, "market_value")
        item_rows.append(
            {
                "asset_class_raw": asset_class_raw,
                "position_count": len(asset_rows),
                "market_value": market_value,
                "market_value_weight": _ratio(market_value, total_market_value),
                "infer_accounting_class": inferred["accounting_class"],
                "map_accounting_class": mapped,
                "infer_rule_id": inferred["rule_id"],
                "infer_match": inferred["rule_match"],
                "map_rule_id": str(dominant.get("accounting_rule_id") or ENGINE_RULE_VERSION),
                "map_match": None,
                "is_divergent": inferred["accounting_class"] != mapped,
                "is_map_unclassified": mapped == "other",
            }
        )
    divergent_rows = [row for row in item_rows if row["is_divergent"]]
    unclassified_rows = [row for row in item_rows if row["is_map_unclassified"]]
    return {
        "rows": item_rows,
        "total_positions": len(rows),
        "total_market_value": total_market_value,
        "distinct_asset_classes": len(item_rows),
        "divergent_asset_classes": len(divergent_rows),
        "divergent_position_count": sum((int(row["position_count"]) for row in divergent_rows), 0),
        "divergent_market_value": sum((safe_decimal(row["market_value"]) for row in divergent_rows), ZERO),
        "map_unclassified_asset_classes": len(unclassified_rows),
        "map_unclassified_position_count": sum((int(row["position_count"]) for row in unclassified_rows), 0),
        "map_unclassified_market_value": sum((safe_decimal(row["market_value"]) for row in unclassified_rows), ZERO),
    }


def infer_accounting_class_from_rule_id(rule_id: str) -> dict[str, str | None]:
    if rule_id.startswith("R00"):
        return {"accounting_class": "AC", "rule_id": rule_id or "R001", "rule_match": "accounting_rule_id:R00*"}
    if rule_id.startswith("R01"):
        return {"accounting_class": "OCI", "rule_id": rule_id or "R010", "rule_match": "accounting_rule_id:R01*"}
    if rule_id.startswith("R02"):
        return {"accounting_class": "TPL", "rule_id": rule_id or "R020", "rule_match": "accounting_rule_id:R02*"}
    return {"accounting_class": "other", "rule_id": rule_id or "R999", "rule_match": None}


def _aggregate_carry(rows: list[dict[str, Any]], field_name: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row[field_name])
        bucket = grouped.setdefault(key, {"key": key, "carry": ZERO, "market_value": ZERO, "bond_count": 0})
        bucket["carry"] += safe_decimal(row["carry"])
        bucket["market_value"] += safe_decimal(row["market_value"])
        bucket["bond_count"] += 1
    return list(grouped.values())


def _aggregate_return(rows: list[dict[str, Any]], field_name: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row[field_name])
        bucket = grouped.setdefault(
            key,
            {
                "key": key,
                "carry": ZERO,
                "roll_down": ZERO,
                "rate_effect": ZERO,
                "spread_effect": ZERO,
                "convexity_effect": ZERO,
                "fx_effect": ZERO,
                "market_value": ZERO,
                "bond_count": 0,
                "total": ZERO,
            },
        )
        bucket["carry"] += safe_decimal(row["carry"])
        bucket["roll_down"] += safe_decimal(row.get("roll_down"))
        bucket["rate_effect"] += safe_decimal(row.get("rate_effect"))
        bucket["spread_effect"] += safe_decimal(row.get("spread_effect"))
        bucket["convexity_effect"] += safe_decimal(row.get("convexity_effect"))
        bucket["fx_effect"] += safe_decimal(row.get("fx_effect"))
        bucket["market_value"] += safe_decimal(row["market_value"])
        bucket["bond_count"] += 1
        bucket["total"] += safe_decimal(row.get("total"))
    return list(grouped.values())


def _curve_roll_down(
    *,
    current_curve: dict[str, Decimal] | None,
    years_to_maturity: Decimal,
    period_days: int,
    modified_duration: Decimal,
    market_value: Decimal,
) -> Decimal:
    if not current_curve or years_to_maturity <= ZERO or modified_duration == ZERO or market_value == ZERO:
        return ZERO
    current_rate = _curve_rate(current_curve, years_to_maturity)
    rolled_years = max(float(years_to_maturity) - (period_days / 365), 0.0)
    rolled_rate = _curve_rate(current_curve, Decimal(str(rolled_years)))
    return ((current_rate - rolled_rate) / Decimal("100")) * modified_duration * market_value


def _curve_rate_effect(
    *,
    current_curve: dict[str, Decimal] | None,
    prior_curve: dict[str, Decimal] | None,
    years_to_maturity: Decimal,
    modified_duration: Decimal,
    market_value: Decimal,
) -> Decimal:
    if (
        not current_curve
        or not prior_curve
        or years_to_maturity <= ZERO
        or modified_duration == ZERO
        or market_value == ZERO
    ):
        return ZERO
    current_rate = _curve_rate(current_curve, years_to_maturity)
    prior_rate = _curve_rate(prior_curve, years_to_maturity)
    return -(((current_rate - prior_rate) / Decimal("100")) * modified_duration * market_value)


def _convexity_effect(
    *,
    row: dict[str, Any],
    current_curve: dict[str, Decimal] | None,
    prior_curve: dict[str, Decimal] | None,
    market_value: Decimal,
) -> Decimal:
    convexity_val = safe_decimal(row.get("convexity"))
    if not current_curve or not prior_curve or convexity_val == ZERO or market_value == ZERO:
        return ZERO
    tenor = str(row.get("tenor_bucket") or "")
    current_y = _interpolate_from_curve(current_curve, tenor)
    prior_y = _interpolate_from_curve(prior_curve, tenor)
    if current_y is None or prior_y is None:
        return ZERO
    delta_y = (current_y - prior_y) / Decimal("100")
    return Decimal("0.5") * convexity_val * delta_y * delta_y * market_value


def _interpolate_from_curve(curve: dict[str, Decimal], tenor_bucket: str) -> Decimal | None:
    """Return the tenor-bucket rate from a curve after filling standard buckets."""
    if not curve or not tenor_bucket:
        return None
    val = build_full_curve(curve).get(tenor_bucket)
    if val is None:
        return None
    return safe_decimal(val)


def _spread_effect(
    *,
    row: dict[str, Any],
    treasury_curve_current: dict[str, Decimal] | None,
    treasury_curve_prior: dict[str, Decimal] | None,
    aaa_credit_curve_current: dict[str, Decimal] | None,
    aaa_credit_curve_prior: dict[str, Decimal] | None,
    years_to_maturity: Decimal,
    modified_duration: Decimal,
    market_value: Decimal,
) -> Decimal:
    if str(row.get("asset_class_std")) != "credit":
        return ZERO
    if (
        not treasury_curve_current
        or not treasury_curve_prior
        or not aaa_credit_curve_current
        or not aaa_credit_curve_prior
        or years_to_maturity <= ZERO
        or modified_duration == ZERO
        or market_value == ZERO
    ):
        return ZERO
    current_spread = _curve_rate(aaa_credit_curve_current, years_to_maturity) - _curve_rate(
        treasury_curve_current, years_to_maturity
    )
    prior_spread = _curve_rate(aaa_credit_curve_prior, years_to_maturity) - _curve_rate(
        treasury_curve_prior, years_to_maturity
    )
    return -(((current_spread - prior_spread) / Decimal("100")) * modified_duration * market_value)


def _fx_effect(
    *,
    row: dict[str, Any],
    fx_rates_current: dict[str, Decimal] | None,
    fx_rates_prior: dict[str, Decimal] | None,
) -> Decimal:
    currency_code = str(row.get("currency_code") or "CNY").upper().strip()
    if currency_code in {"", "CNY", "CNX", "RMB"} or not fx_rates_current or not fx_rates_prior:
        return ZERO
    current_rate = safe_decimal(fx_rates_current.get(currency_code))
    prior_rate = safe_decimal(fx_rates_prior.get(currency_code))
    if current_rate == ZERO or prior_rate == ZERO:
        return ZERO
    market_value_native = safe_decimal(row.get("market_value_native"))
    if market_value_native == ZERO:
        return ZERO
    return market_value_native * (current_rate - prior_rate)


def _curve_rate(curve: dict[str, Decimal], years_to_maturity: Decimal) -> Decimal:
    points = build_curve_points(build_full_curve(curve))
    return interpolate_rate(points, float(years_to_maturity))


def _to_years(value: Any) -> Decimal:
    if value in (None, ""):
        return ZERO
    return safe_decimal(value)


def _weighted_average_spread(
    rows: list[dict[str, Any]],
    *,
    aaa_credit_curve_current: dict[str, Decimal] | None,
    treasury_curve_current: dict[str, Decimal] | None,
) -> Decimal:
    if not rows or not aaa_credit_curve_current or not treasury_curve_current:
        return ZERO
    total_market_value = _sum(rows, "market_value")
    if total_market_value == ZERO:
        return ZERO
    weighted_spread = ZERO
    for row in rows:
        years_to_maturity = _to_years(row.get("years_to_maturity"))
        market_value = safe_decimal(row.get("market_value"))
        if years_to_maturity <= ZERO or market_value == ZERO:
            continue
        spread = _curve_rate(aaa_credit_curve_current, years_to_maturity) - _curve_rate(
            treasury_curve_current, years_to_maturity
        )
        weighted_spread += spread * market_value
    return weighted_spread / total_market_value


def _weighted_spread_change(
    rows: list[dict[str, Any]],
    *,
    aaa_credit_curve_current: dict[str, Decimal] | None,
    aaa_credit_curve_prior: dict[str, Decimal] | None,
    treasury_curve_current: dict[str, Decimal] | None,
    treasury_curve_prior: dict[str, Decimal] | None,
    total_market_value: Decimal,
) -> Decimal:
    if not rows or total_market_value == ZERO:
        return ZERO
    total_spread_effect = ZERO
    for row in rows:
        market_value = safe_decimal(row.get("market_value"))
        total_spread_effect += _spread_effect(
            row=row,
            treasury_curve_current=treasury_curve_current,
            treasury_curve_prior=treasury_curve_prior,
            aaa_credit_curve_current=aaa_credit_curve_current,
            aaa_credit_curve_prior=aaa_credit_curve_prior,
            years_to_maturity=_to_years(row.get("years_to_maturity")),
            modified_duration=safe_decimal(row.get("modified_duration")),
            market_value=market_value,
        )
    return (total_spread_effect / total_market_value) * Decimal("100")


def _compute_allocation_effect(
    rows: list[dict[str, Any]],
    *,
    benchmark_id: str,
    benchmark_return: Decimal,
    total_market_value: Decimal,
    period_start: date,
    period_end: date,
    treasury_curve_current: dict[str, Decimal] | None = None,
    treasury_curve_prior: dict[str, Decimal] | None = None,
    cdb_curve_current: dict[str, Decimal] | None = None,
    cdb_curve_prior: dict[str, Decimal] | None = None,
    aaa_credit_curve_current: dict[str, Decimal] | None = None,
    aaa_credit_curve_prior: dict[str, Decimal] | None = None,
) -> Decimal:
    if not rows or total_market_value == ZERO:
        return ZERO
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped_rows[str(row.get("asset_class_std") or "other")].append(row)
    benchmark_weights = _benchmark_asset_class_weights(benchmark_id)
    allocation_effect = ZERO
    for asset_class in sorted(set(grouped_rows) | set(benchmark_weights)):
        sector_rows = grouped_rows.get(asset_class, [])
        sector_market_value = _sum(sector_rows, "market_value")
        portfolio_weight = ZERO if total_market_value == ZERO else sector_market_value / total_market_value
        benchmark_weight = benchmark_weights.get(asset_class, ZERO)
        if sector_market_value == ZERO and benchmark_weight == ZERO:
            continue
        sector_return = ZERO
        if sector_market_value != ZERO:
            sector_summary = summarize_return_decomposition(
                sector_rows,
                period_start=period_start,
                period_end=period_end,
                treasury_curve_current=treasury_curve_current,
                treasury_curve_prior=treasury_curve_prior,
                cdb_curve_current=cdb_curve_current,
                cdb_curve_prior=cdb_curve_prior,
                aaa_credit_curve_current=aaa_credit_curve_current,
                aaa_credit_curve_prior=aaa_credit_curve_prior,
            )
            sector_return = _allocation_sector_return(
                sector_summary=sector_summary,
                sector_market_value=sector_market_value,
            )
        allocation_effect += (portfolio_weight - benchmark_weight) * (sector_return - benchmark_return)
    return allocation_effect * Decimal("100")


def _summary_total_for_excess_return(summary: dict[str, Any]) -> Decimal:
    return (
        safe_decimal(summary.get("carry_total"))
        + safe_decimal(summary.get("roll_down_total"))
        + safe_decimal(summary.get("rate_effect_total"))
        + safe_decimal(summary.get("spread_effect_total"))
        + safe_decimal(summary.get("convexity_effect_total"))
        + safe_decimal(summary.get("fx_effect_total"))
    )


def _allocation_sector_return(*, sector_summary: dict[str, Any], sector_market_value: Decimal) -> Decimal:
    if sector_market_value == ZERO:
        return ZERO
    total_effect = (
        safe_decimal(sector_summary.get("carry_total"))
        + safe_decimal(sector_summary.get("roll_down_total"))
        + safe_decimal(sector_summary.get("rate_effect_total"))
        + safe_decimal(sector_summary.get("convexity_effect_total"))
    )
    return (total_effect / sector_market_value) * Decimal("100")


def _build_curve_scenario(rows: list[dict[str, Any]], scenario: dict[str, Any]) -> dict[str, Any]:
    pnl_economic = pnl_oci = pnl_tpl = rate_contribution = convexity_contribution = ZERO
    by_asset_class: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"pnl_economic": ZERO, "pnl_oci": ZERO, "pnl_tpl": ZERO})
    shocks = dict(scenario["shocks"])
    for row in rows:
        shock_bp = Decimal(str(shocks.get("all", shocks.get(str(row["tenor_bucket"]), 0))))
        if shock_bp == ZERO:
            continue
        market_value = safe_decimal(row["market_value"])
        modified = safe_decimal(row["modified_duration"])
        convexity = safe_decimal(row["convexity"])
        shock = shock_bp / Decimal("10000")
        linear = -(modified * shock * market_value)
        convex = Decimal("0.5") * convexity * (shock ** 2) * market_value
        pnl = linear + convex
        rate_contribution += linear
        convexity_contribution += convex
        pnl_economic += pnl
        asset_key = str(row["asset_class_std"])
        by_asset_class[asset_key]["pnl_economic"] += pnl
        if str(row["accounting_class"]) == "OCI":
            pnl_oci += pnl
            by_asset_class[asset_key]["pnl_oci"] += pnl
        if str(row["accounting_class"]) == "TPL":
            pnl_tpl += pnl
            by_asset_class[asset_key]["pnl_tpl"] += pnl
    return {
        "scenario_name": str(scenario["name"]),
        "scenario_description": str(scenario["description"]),
        "shocks": shocks,
        "pnl_economic": pnl_economic,
        "pnl_oci": pnl_oci,
        "pnl_tpl": pnl_tpl,
        "rate_contribution": rate_contribution,
        "convexity_contribution": convexity_contribution,
        "by_asset_class": by_asset_class,
    }


def _sum(rows: list[dict[str, Any]], field_name: str) -> Decimal:
    return sum((safe_decimal(row.get(field_name)) for row in rows), ZERO)


def _weighted(rows: list[dict[str, Any]], field_name: str, *, weight_field: str = "market_value") -> Decimal:
    numerator = sum((safe_decimal(row[field_name]) * safe_decimal(row[weight_field]) for row in rows), ZERO)
    denominator = _sum(rows, weight_field)
    return ZERO if denominator == ZERO else numerator / denominator


def weighted_average_by_market_value(rows: list[dict[str, Any]], field_name: str) -> Decimal:
    """MV-weighted average of ``field_name`` (missing values treated as 0)."""
    numerator = sum(
        (safe_decimal(row.get(field_name)) * safe_decimal(row.get("market_value")) for row in rows),
        ZERO,
    )
    denominator = _sum(rows, "market_value")
    return ZERO if denominator == ZERO else numerator / denominator


def _return_pct(*, total_effect: Decimal, total_market_value: Decimal) -> Decimal:
    if total_market_value == ZERO:
        return ZERO
    return (total_effect / total_market_value) * Decimal("100")


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    return ZERO if denominator == ZERO else numerator / denominator


def _benchmark_duration(benchmark_id: str) -> Decimal:
    return BENCHMARK_DURATION_ASSUMPTIONS.get(benchmark_id, Decimal("5"))


def _benchmark_asset_class_weights(benchmark_id: str) -> dict[str, Decimal]:
    if benchmark_id == "AAA_CREDIT_INDEX":
        return {"credit": Decimal("1"), "rate": ZERO}
    return {"rate": Decimal("1"), "credit": ZERO}


def _benchmark_krd_by_bucket(benchmark_id: str, *, benchmark_duration: Decimal) -> dict[str, Decimal]:
    weights = BENCHMARK_BUCKET_WEIGHTS.get(benchmark_id, BENCHMARK_BUCKET_WEIGHTS["CDB_INDEX"])
    return {
        bucket: benchmark_duration * weight
        for bucket, weight in weights.items()
    }


def _portfolio_krd_by_bucket(
    rows: list[dict[str, Any]],
    *,
    total_market_value: Decimal,
) -> dict[str, Decimal]:
    bucket_krd: dict[str, Decimal] = defaultdict(lambda: ZERO)
    if total_market_value == ZERO:
        return {}
    for row in rows:
        bucket = str(row.get("tenor_bucket") or "5Y")
        bucket_krd[bucket] += (
            safe_decimal(row.get("modified_duration"))
            * safe_decimal(row.get("market_value"))
            / total_market_value
        )
    return dict(bucket_krd)


def _curve_delta_by_bucket(
    *,
    benchmark_curve_current: dict[str, Decimal],
    benchmark_curve_prior: dict[str, Decimal],
) -> dict[str, Decimal]:
    current_curve = build_full_curve(benchmark_curve_current)
    prior_curve = build_full_curve(benchmark_curve_prior)
    return {
        bucket: safe_decimal(current_curve.get(bucket)) - safe_decimal(prior_curve.get(bucket))
        for bucket in sorted(set(current_curve) | set(prior_curve))
    }


def _excess_sources(
    *,
    duration_effect: Decimal,
    curve_effect: Decimal,
    spread_effect: Decimal,
    selection_effect: Decimal,
    allocation_effect: Decimal,
) -> list[dict[str, Any]]:
    return [
        {
            "source": "duration",
            "contribution": duration_effect,
            "description": "Duration mismatch against benchmark parallel shift.",
        },
        {
            "source": "curve",
            "contribution": curve_effect,
            "description": "Bucketed KRD mismatch against benchmark curve shape move.",
        },
        {
            "source": "spread",
            "contribution": spread_effect,
            "description": "Portfolio-weighted credit spread move using AAA credit versus treasury curves.",
        },
        {
            "source": "selection",
            "contribution": selection_effect,
            "description": "Residual selection effect after duration and curve attribution.",
        },
        {
            "source": "allocation",
            "contribution": allocation_effect,
            "description": "Asset-class allocation effect versus simplified benchmark sector weights.",
        },
    ]
