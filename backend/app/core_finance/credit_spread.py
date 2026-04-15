from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Mapping

from .attribution_core import get_tenor_bucket
from .bond_duration import estimate_duration, modified_duration_from_macaulay
from .krd import classify_asset_class, map_accounting_class
from .safe_decimal import safe_decimal

CURVE_TENOR_YEARS = {
    "1Y": 1.0,
    "2Y": 2.0,
    "3Y": 3.0,
    "5Y": 5.0,
    "7Y": 7.0,
    "10Y": 10.0,
    "15Y": 15.0,
    "20Y": 20.0,
    "30Y": 30.0,
}

RATING_MAPPING = {
    "AAA": {"score": 1, "spread_basis_bp": 30},
    "AA+": {"score": 2, "spread_basis_bp": 50},
    "AA": {"score": 3, "spread_basis_bp": 80},
    "AA-": {"score": 4, "spread_basis_bp": 120},
    "A+": {"score": 5, "spread_basis_bp": 180},
    "A": {"score": 6, "spread_basis_bp": 250},
}

DEFAULT_MIGRATION_SCENARIOS = (
    {"from": "AAA", "to": "AA+", "spread_change_bp": 15},
    {"from": "AA+", "to": "AA", "spread_change_bp": 25},
    {"from": "AA", "to": "AA-", "spread_change_bp": 40},
    {"from": "AA-", "to": "A+", "spread_change_bp": 80},
)


def _get_value(record: Any, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if isinstance(record, Mapping) and key in record:
            value = record[key]
        else:
            value = getattr(record, key, None)
        if value is not None:
            return value
    return default


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return None
    return None


def _get_market_value(position: Any) -> Decimal:
    return safe_decimal(
        _get_value(
            position,
            "market_value",
            "market_value_end",
            "market_value_start",
            default=Decimal("0"),
        )
    )


def interpolate_curve_rate(
    curve: Mapping[str, Any],
    tenor: str,
) -> Decimal:
    if not curve:
        return Decimal("0")
    if tenor in curve:
        return safe_decimal(curve[tenor])

    target_years = CURVE_TENOR_YEARS.get(tenor)
    if target_years is None:
        return Decimal("0")

    points: list[tuple[float, Decimal]] = []
    for label, rate in curve.items():
        years = CURVE_TENOR_YEARS.get(str(label))
        if years is not None:
            points.append((years, safe_decimal(rate)))
    points.sort(key=lambda item: item[0])

    if not points:
        return Decimal("0")
    if target_years <= points[0][0]:
        return points[0][1]
    if target_years >= points[-1][0]:
        return points[-1][1]

    for index in range(len(points) - 1):
        left_years, left_rate = points[index]
        right_years, right_rate = points[index + 1]
        if left_years <= target_years <= right_years:
            span = right_years - left_years
            if span <= 0:
                return left_rate
            weight = Decimal(str(target_years - left_years)) / Decimal(str(span))
            return left_rate + weight * (right_rate - left_rate)

    return Decimal("0")


def _get_tenor_bucket(position: Any, *, report_date: date | None = None) -> str:
    maturity_date = _coerce_date(_get_value(position, "maturity_date", "maturity_date_end"))
    effective_report_date = _coerce_date(
        _get_value(position, "report_date", "biz_date", "report_date_end", default=report_date)
    )
    if maturity_date is not None and effective_report_date is not None:
        years = max((maturity_date - effective_report_date).days / 365.0, 0.0)
        return get_tenor_bucket(years)
    return "3Y"


def get_credit_spread(
    position: Any,
    *,
    spread_curves: Mapping[str, Mapping[str, Any]] | None = None,
    report_date: date | None = None,
) -> Decimal:
    rating = str(_get_value(position, "agency_rating", default="AA") or "AA")
    tenor = _get_tenor_bucket(position, report_date=report_date)
    if spread_curves:
        curve = spread_curves.get(rating)
        if curve:
            if tenor in curve:
                return safe_decimal(curve[tenor])
            for fallback_tenor in ("3Y", "5Y", "1Y"):
                if fallback_tenor in curve:
                    return safe_decimal(curve[fallback_tenor])

    if rating in RATING_MAPPING:
        return Decimal(str(RATING_MAPPING[rating]["spread_basis_bp"])) / Decimal("10000")
    return Decimal("0.008")


def _build_credit_position_metrics(
    positions: Iterable[Any],
    *,
    report_date: date | None = None,
    spread_curves: Mapping[str, Mapping[str, Any]] | None = None,
    wind_metrics: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], Decimal, Decimal]:
    positions_list = list(positions)
    total_market_value = sum(
        (_get_market_value(position) for position in positions_list),
        Decimal("0"),
    )
    credit_positions = [
        position
        for position in positions_list
        if classify_asset_class(str(_get_value(position, "sub_type", "bond_type", default="")))
        == "credit"
    ]
    credit_market_value = sum(
        (_get_market_value(position) for position in credit_positions),
        Decimal("0"),
    )

    metrics: list[dict[str, Any]] = []
    for position in credit_positions:
        market_value = _get_market_value(position)
        if market_value <= Decimal("0"):
            continue

        bond_code = str(_get_value(position, "bond_code", default=""))
        coupon_rate = safe_decimal(_get_value(position, "coupon_rate"))
        ytm = safe_decimal(_get_value(position, "yield_to_maturity"))
        effective_report_date = _coerce_date(
            _get_value(position, "report_date", "biz_date", "report_date_end", default=report_date)
        )
        maturity_date = _coerce_date(_get_value(position, "maturity_date", "maturity_date_end"))
        # 超短融为年付息(1)，其余信用债默认半年付息(2)，与 return_decomposition.py:256 保持一致
        coupon_frequency = 1 if "超短融" in str(_get_value(position, "sub_type", default="")) else 2
        wind_bond = dict((wind_metrics or {}).get(bond_code, {}))
        duration = estimate_duration(
            maturity_date=maturity_date,
            report_date=effective_report_date or report_date or date.today(),
            coupon_rate=coupon_rate,
            bond_code=bond_code,
            ytm=ytm,
            wind_metrics={bond_code: wind_bond} if wind_bond else None,
            coupon_frequency=coupon_frequency,
        )
        spread_duration = modified_duration_from_macaulay(
            duration=duration,
            ytm=ytm,
            coupon_frequency=coupon_frequency,
            wind_mod_dur=safe_decimal(wind_bond.get("mod_duration")) if wind_bond else None,
        )
        metrics.append(
            {
                "bond_code": bond_code,
                "market_value": market_value,
                "duration": duration,
                "spread_duration": spread_duration,
                "spread": get_credit_spread(
                    position,
                    spread_curves=spread_curves,
                    report_date=report_date,
                ),
                "dv01": market_value * spread_duration / Decimal("10000"),
                "rating": str(_get_value(position, "agency_rating", default="AA") or "AA"),
                "issuer": str(
                    _get_value(position, "credit_name", "counterparty", "issuer_name", default="UNKNOWN")
                ),
                "industry": str(_get_value(position, "industry", default="UNKNOWN")),
                "accounting_class": map_accounting_class(
                    str(_get_value(position, "asset_class", default=""))
                ),
                "tenor_bucket": _get_tenor_bucket(position, report_date=report_date),
            }
        )

    return metrics, total_market_value, credit_market_value


def compute_spread_scenarios(
    metrics: Iterable[Mapping[str, Any]],
    shocks_bp: Iterable[int | Decimal],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    metrics_list = list(metrics)
    for raw_shock in shocks_bp:
        shock = int(safe_decimal(raw_shock))
        for direction in (1, -1):
            actual_shock = shock * direction
            pnl_impact = Decimal("0")
            oci_impact = Decimal("0")
            tpl_impact = Decimal("0")

            for metric in metrics_list:
                delta = (
                    -safe_decimal(metric["spread_duration"])
                    * safe_decimal(metric["market_value"])
                    * Decimal(actual_shock)
                    / Decimal("10000")
                )
                pnl_impact += delta
                accounting_class = str(metric["accounting_class"])
                if accounting_class == "OCI":
                    oci_impact += delta
                elif accounting_class == "TPL":
                    tpl_impact += delta

            results.append(
                {
                    "scenario_name": f"spread_{'up' if direction > 0 else 'down'}_{shock}bp",
                    "spread_change_bp": actual_shock,
                    "pnl_impact": pnl_impact,
                    "oci_impact": oci_impact,
                    "tpl_impact": tpl_impact,
                }
            )
    return results


def compute_migration_scenarios(
    metrics: Iterable[Mapping[str, Any]],
    scenarios: Iterable[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    metrics_list = list(metrics)
    scenario_list = list(scenarios) if scenarios is not None else list(DEFAULT_MIGRATION_SCENARIOS)
    results: list[dict[str, Any]] = []

    for scenario in scenario_list:
        from_rating = str(scenario.get("from") or "")
        to_rating = str(scenario.get("to") or "")
        spread_change_bp = safe_decimal(scenario.get("spread_change_bp"))
        affected = [metric for metric in metrics_list if str(metric["rating"]) == from_rating]
        if not affected:
            continue

        affected_market_value = sum(
            (safe_decimal(metric["market_value"]) for metric in affected),
            Decimal("0"),
        )
        pnl_impact = Decimal("0")
        oci_impact = Decimal("0")
        for metric in affected:
            delta = (
                -safe_decimal(metric["spread_duration"])
                * safe_decimal(metric["market_value"])
                * spread_change_bp
                / Decimal("10000")
            )
            pnl_impact += delta
            if str(metric["accounting_class"]) == "OCI":
                oci_impact += delta

        results.append(
            {
                "scenario_name": f"{from_rating}_to_{to_rating}",
                "from_rating": from_rating,
                "to_rating": to_rating,
                "affected_bonds": len(affected),
                "affected_market_value": affected_market_value,
                "pnl_impact": pnl_impact,
                "oci_impact": oci_impact,
            }
        )
    return results


def _issuer_metrics_all_positions(positions: Iterable[Any]) -> list[dict[str, Any]]:
    """全量债券持仓按发行人汇总市值（与信用利差子集无关），用于组合层 CRn / 阶梯图。"""
    metrics: list[dict[str, Any]] = []
    for position in positions:
        market_value = _get_market_value(position)
        if market_value <= Decimal("0"):
            continue
        raw = _get_value(position, "credit_name", "counterparty", "issuer_name", default="")
        name = str(raw).strip() if raw else ""
        if not name:
            name = "其他"
        metrics.append({"issuer": name, "market_value": market_value})
    return metrics


def compute_concentration(
    metrics: Iterable[Mapping[str, Any]],
    *,
    dimension: str,
    total_market_value: Decimal,
    top_n: int = 5,
) -> dict[str, Any]:
    buckets: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for metric in metrics:
        key = str(metric.get(dimension) or "UNKNOWN")
        buckets[key] += safe_decimal(metric["market_value"])

    hhi = Decimal("0")
    for market_value in buckets.values():
        weight = market_value / total_market_value if total_market_value > 0 else Decimal("0")
        hhi += weight * weight

    sorted_items = sorted(buckets.items(), key=lambda item: item[1], reverse=True)
    top_slice = sorted_items[: max(1, top_n)]
    top5_slice = sorted_items[:5]
    top10_slice = sorted_items[:10]

    def _sum_mv(items: list[tuple[str, Decimal]]) -> Decimal:
        return sum((mv for _, mv in items), Decimal("0"))

    top5_mv = _sum_mv(top5_slice)
    top10_mv = _sum_mv(top10_slice)
    return {
        "dimension": dimension,
        "hhi": hhi,
        "top5_concentration": (
            top5_mv / total_market_value if total_market_value > 0 else Decimal("0")
        ),
        "top10_concentration": (
            top10_mv / total_market_value if total_market_value > 0 else Decimal("0")
        ),
        "top_items": [
            {
                "name": name,
                "weight": (
                    market_value / total_market_value if total_market_value > 0 else Decimal("0")
                ),
                "market_value": market_value,
            }
            for name, market_value in top_slice
        ],
    }


def compute_oci_sensitivity(metrics: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    exposure = Decimal("0")
    dv01 = Decimal("0")
    for metric in metrics:
        if str(metric["accounting_class"]) != "OCI":
            continue
        exposure += safe_decimal(metric["market_value"])
        dv01 += safe_decimal(metric["dv01"])
    return {
        "exposure": exposure,
        "dv01": dv01,
        "sensitivity_25bp": -dv01 * Decimal("25"),
    }


def compute_credit_spread_profile(
    positions: Iterable[Any],
    *,
    report_date: date | None = None,
    spread_curves: Mapping[str, Mapping[str, Any]] | None = None,
    spread_scenarios: Iterable[int | Decimal] | None = None,
    migration_scenarios: Iterable[Mapping[str, Any]] | None = None,
    wind_metrics: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    positions_list = list(positions)
    metrics, total_market_value, credit_market_value = _build_credit_position_metrics(
        positions_list,
        report_date=report_date,
        spread_curves=spread_curves,
        wind_metrics=wind_metrics,
    )
    warnings: list[str] = []
    if total_market_value <= Decimal("0"):
        warnings.append("NO_POSITIONS_FOUND")
    if credit_market_value <= Decimal("0"):
        warnings.append("NO_CREDIT_BONDS_FOUND")

    spread_dv01 = sum(
        (safe_decimal(metric["dv01"]) for metric in metrics),
        Decimal("0"),
    )
    weighted_spread_sum = sum(
        (
            safe_decimal(metric["market_value"]) * safe_decimal(metric["spread"])
            for metric in metrics
        ),
        Decimal("0"),
    )
    weighted_spread_duration_sum = sum(
        (
            safe_decimal(metric["market_value"]) * safe_decimal(metric["spread_duration"])
            for metric in metrics
        ),
        Decimal("0"),
    )
    weighted_avg_spread = (
        weighted_spread_sum / credit_market_value if credit_market_value > 0 else Decimal("0")
    )
    weighted_avg_spread_duration = (
        weighted_spread_duration_sum / credit_market_value
        if credit_market_value > 0
        else Decimal("0")
    )
    scenario_shocks = list(spread_scenarios) if spread_scenarios is not None else [10, 25, 50]
    oci_metrics = compute_oci_sensitivity(metrics)

    return {
        "warnings": warnings,
        "credit_bond_count": len(metrics),
        "total_market_value": total_market_value,
        "credit_market_value": credit_market_value,
        "credit_weight": (
            credit_market_value / total_market_value if total_market_value > 0 else Decimal("0")
        ),
        "spread_dv01": spread_dv01,
        "weighted_avg_spread": weighted_avg_spread,
        "weighted_avg_spread_bp": weighted_avg_spread * Decimal("10000"),
        "weighted_avg_spread_duration": weighted_avg_spread_duration,
        "spread_scenarios": compute_spread_scenarios(metrics, scenario_shocks),
        "migration_scenarios": compute_migration_scenarios(
            metrics,
            scenarios=migration_scenarios,
        ),
        "concentration_by_issuer": compute_concentration(
            _issuer_metrics_all_positions(positions_list),
            dimension="issuer",
            total_market_value=total_market_value,
            top_n=10,
        ),
        "concentration_by_industry": compute_concentration(
            metrics,
            dimension="industry",
            total_market_value=credit_market_value,
            top_n=5,
        ),
        "concentration_by_rating": compute_concentration(
            metrics,
            dimension="rating",
            total_market_value=credit_market_value,
            top_n=5,
        ),
        "concentration_by_tenor": compute_concentration(
            metrics,
            dimension="tenor_bucket",
            total_market_value=credit_market_value,
            top_n=5,
        ),
        "oci_credit_exposure": oci_metrics["exposure"],
        "oci_spread_dv01": oci_metrics["dv01"],
        "oci_sensitivity_25bp": oci_metrics["sensitivity_25bp"],
        "position_metrics": metrics,
    }
