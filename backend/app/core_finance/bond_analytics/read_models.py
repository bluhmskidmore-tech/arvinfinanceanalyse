"""Pure read-model calculations over materialized bond analytics fact rows."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.bond_analytics.common import STANDARD_SCENARIOS
from backend.app.core_finance.bond_analytics.engine import ENGINE_RULE_VERSION
from backend.app.core_finance.bond_analytics.common import safe_decimal

ZERO = Decimal("0")


def summarize_return_decomposition(
    rows: list[dict[str, Any]],
    *,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    days = Decimal((period_end - period_start).days + 1)
    detail_rows = []
    carry_total = ZERO
    for row in rows:
        carry = safe_decimal(row.get("coupon_rate")) * safe_decimal(row.get("face_value")) * days / Decimal("365")
        carry_total += carry
        detail_rows.append({**row, "carry": carry})
    return {
        "carry_total": carry_total,
        "total_market_value": _sum(rows, "market_value"),
        "bond_count": len(rows),
        "bond_details": detail_rows,
        "by_asset_class": _aggregate_carry(detail_rows, "asset_class_std"),
        "by_accounting_class": _aggregate_carry(detail_rows, "accounting_class"),
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


def summarize_credit(rows: list[dict[str, Any]], *, total_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_market_value = _sum(total_rows, "market_value")
    credit_market_value = _sum(rows, "market_value")
    return {
        "total_market_value": total_market_value,
        "credit_bond_count": len(rows),
        "credit_market_value": credit_market_value,
        "credit_weight": _ratio(credit_market_value, total_market_value),
        "spread_dv01": _sum(rows, "spread_dv01"),
        "weighted_avg_spread_duration": _weighted(rows, "modified_duration"),
        "weighted_avg_spread": ZERO,
        "oci_credit_exposure": _sum([row for row in rows if str(row["accounting_class"]) == "OCI"], "market_value"),
        "oci_spread_dv01": _sum([row for row in rows if str(row["accounting_class"]) == "OCI"], "spread_dv01"),
        "tpl_spread_dv01": _sum([row for row in rows if str(row["accounting_class"]) == "TPL"], "spread_dv01"),
    }


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


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    return ZERO if denominator == ZERO else numerator / denominator
