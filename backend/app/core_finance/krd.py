from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping

from backend.app.core_finance.config.classification_rules import infer_invest_type
from backend.app.core_finance.field_normalization import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    derive_accounting_basis_value,
)

from .attribution_core import get_tenor_bucket
from .bond_duration import (
    estimate_convexity_bond,
    estimate_duration,
    modified_duration_from_macaulay,
)
from .safe_decimal import safe_decimal

KRD_TENORS = ("1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "15Y", "20Y", "30Y")

STANDARD_KRD_SCENARIOS = (
    {
        "name": "parallel_up_25bp",
        "description": "Parallel +25bp",
        "shocks": {tenor: 25 for tenor in KRD_TENORS},
    },
    {
        "name": "parallel_up_50bp",
        "description": "Parallel +50bp",
        "shocks": {tenor: 50 for tenor in KRD_TENORS},
    },
    {
        "name": "parallel_up_100bp",
        "description": "Parallel +100bp",
        "shocks": {tenor: 100 for tenor in KRD_TENORS},
    },
    {
        "name": "parallel_down_25bp",
        "description": "Parallel -25bp",
        "shocks": {tenor: -25 for tenor in KRD_TENORS},
    },
    {
        "name": "steepening_50bp",
        "description": "Curve steepening",
        "shocks": {
            "1Y": -25,
            "2Y": -15,
            "3Y": -5,
            "5Y": 5,
            "7Y": 15,
            "10Y": 25,
            "15Y": 20,
            "20Y": 23,
            "30Y": 25,
        },
    },
    {
        "name": "flattening_50bp",
        "description": "Curve flattening",
        "shocks": {
            "1Y": 25,
            "2Y": 15,
            "3Y": 5,
            "5Y": -5,
            "7Y": -15,
            "10Y": -25,
            "15Y": -20,
            "20Y": -23,
            "30Y": -25,
        },
    },
)

RATE_BOND_TYPES = {
    "国债",
    "国开债",
    "政金债",
    "地方债",
    "央票",
    "政府债",
    "政策性金融债",
    "地方政府债券",
    "地方政府债",
    "国家开发银行",
    "进出口银行",
    "农业发展银行",
}

CREDIT_BOND_TYPES = {
    "企业债",
    "公司债",
    "中票",
    "短融",
    "PPN",
    "ABS",
    "金融债",
    "同业存单",
    "NCD",
    "超短融",
    "短期融资券",
    "中期票据",
    "私募债",
    "定向工具",
}


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
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime().date()
        except Exception:
            return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return None
    return None


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    converted = safe_decimal(value)
    return converted if converted != Decimal("0") else None


def classify_asset_class(bond_type: str | None) -> str:
    if not bond_type:
        return "other"
    for rate_type in RATE_BOND_TYPES:
        if rate_type in bond_type:
            return "rate"
    for credit_type in CREDIT_BOND_TYPES:
        if credit_type in bond_type:
            return "credit"
    return "other"


def map_accounting_class(asset_class: str | None) -> str:
    """Map raw accounting label to KRD bucket (TPL / OCI / AC / other).

    W-krd-2026-04-21: H/A/T classification delegates to canonical
    ``classification_rules.infer_invest_type`` (caliber ``hat_mapping``),
    then maps ``derive_accounting_basis_value`` outputs to legacy KRD
    strings (``OCI`` for FVOCI, ``TPL`` for FVTPL).

    When the canonical matcher returns ``None``, the historical fallbacks
    for ``债权投资``, substring ``摊余``, and exact ``AC`` remain — these
    are not expressible solely via ``_match_invest_type_by_substring``.
    """
    if not asset_class:
        return "other"
    invest = infer_invest_type(None, None, asset_class)
    if invest is not None:
        basis = derive_accounting_basis_value(invest)  # type: ignore[arg-type]
        if basis == ACCOUNTING_BASIS_AC:
            return "AC"
        if basis == ACCOUNTING_BASIS_FVOCI:
            return "OCI"
        return "TPL"
    if (
        "债权投资" in asset_class
        or "摊余" in asset_class
        or str(asset_class).strip() == ACCOUNTING_BASIS_AC
    ):
        return "AC"
    return "other"


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


def _get_coupon_frequency(position: Any) -> int:
    explicit = _get_value(position, "coupon_frequency")
    if explicit is not None:
        try:
            return max(int(explicit), 1)
        except (TypeError, ValueError):
            pass

    bond_code = str(_get_value(position, "bond_code", default="")).upper()
    asset_hint = " ".join(
        str(_get_value(position, key, default=""))
        for key in ("asset_class", "sub_type", "bond_type")
    )
    if "超短融" in asset_hint or bond_code.startswith("SCP") or bond_code.startswith("SA"):
        return 1
    return 2


def _get_tenor_from_position(
    position: Any,
    *,
    report_date: date | None = None,
    duration: Decimal | None = None,
) -> str:
    maturity_date = _coerce_date(_get_value(position, "maturity_date", "maturity_date_end"))
    effective_report_date = _coerce_date(
        _get_value(position, "report_date", "biz_date", "report_date_end", default=report_date)
    )
    if maturity_date is not None and effective_report_date is not None:
        years = max((maturity_date - effective_report_date).days / 365.0, 0.0)
        return get_tenor_bucket(years)
    return get_tenor_bucket(float(duration or Decimal("5")))


def build_krd_position_metrics(
    positions: Iterable[Any],
    *,
    report_date: date | None = None,
    wind_metrics: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    position_list = list(positions)
    total_market_value = sum(
        (_get_market_value(position) for position in position_list),
        Decimal("0"),
    )
    metrics: list[dict[str, Any]] = []

    for position in position_list:
        market_value = _get_market_value(position)
        if market_value <= Decimal("0"):
            continue

        bond_code = str(_get_value(position, "bond_code", default=""))
        coupon_rate = safe_decimal(_get_value(position, "coupon_rate"))
        ytm = safe_decimal(_get_value(position, "yield_to_maturity"))
        coupon_frequency = _get_coupon_frequency(position)
        report_for_position = _coerce_date(
            _get_value(position, "report_date", "biz_date", "report_date_end", default=report_date)
        )
        maturity_date = _coerce_date(_get_value(position, "maturity_date", "maturity_date_end"))
        wind_bond = dict((wind_metrics or {}).get(bond_code, {}))
        duration = estimate_duration(
            maturity_date=maturity_date,
            report_date=report_for_position or report_date or date.today(),
            coupon_rate=coupon_rate,
            bond_code=bond_code,
            ytm=ytm,
            wind_metrics={bond_code: wind_bond} if wind_bond else None,
            coupon_frequency=coupon_frequency,
        )
        modified_duration = modified_duration_from_macaulay(
            duration=duration,
            ytm=ytm,
            coupon_frequency=max(coupon_frequency, 1),
            wind_mod_dur=_optional_decimal(wind_bond.get("mod_duration")),
        )
        convexity = estimate_convexity_bond(
            duration=duration,
            ytm=ytm,
            wind_convexity=_optional_decimal(wind_bond.get("convexity")),
            coupon_frequency=max(coupon_frequency, 1),
        )
        weight = market_value / total_market_value if total_market_value > 0 else Decimal("0")
        metrics.append(
            {
                "bond_code": bond_code,
                "market_value": market_value,
                "duration": duration,
                "modified_duration": modified_duration,
                "convexity": convexity,
                "dv01": market_value * modified_duration / Decimal("10000"),
                "weight": weight,
                "tenor_bucket": _get_tenor_from_position(
                    position,
                    report_date=report_date,
                    duration=duration,
                ),
                "asset_class": classify_asset_class(
                    str(_get_value(position, "sub_type", "bond_type", default=""))
                ),
                "accounting_class": map_accounting_class(
                    str(_get_value(position, "asset_class", default=""))
                ),
            }
        )
    return metrics


def compute_krd_by_tenor(
    positions: Iterable[Any],
    *,
    report_date: date | None = None,
    wind_metrics: Mapping[str, Mapping[str, Any]] | None = None,
    tenors: Iterable[str] = KRD_TENORS,
) -> list[dict[str, Any]]:
    metrics = build_krd_position_metrics(
        positions,
        report_date=report_date,
        wind_metrics=wind_metrics,
    )
    tenor_map = {
        tenor: {
            "tenor": tenor,
            "krd": Decimal("0"),
            "dv01": Decimal("0"),
            "market_value_weight": Decimal("0"),
        }
        for tenor in tenors
    }
    total_market_value = sum(
        (metric["market_value"] for metric in metrics),
        Decimal("0"),
    )

    for metric in metrics:
        tenor_bucket = metric["tenor_bucket"]
        if tenor_bucket not in tenor_map:
            continue
        tenor_map[tenor_bucket]["krd"] += metric["weight"] * safe_decimal(metric["duration"])
        tenor_map[tenor_bucket]["dv01"] += safe_decimal(metric["dv01"])
        tenor_map[tenor_bucket]["market_value_weight"] += (
            safe_decimal(metric["market_value"]) / total_market_value
            if total_market_value > 0
            else Decimal("0")
        )

    return list(tenor_map.values())


def compute_curve_scenario(
    position_metrics: Iterable[Mapping[str, Any]],
    scenario: Mapping[str, Any],
) -> dict[str, Any]:
    shocks = dict(scenario.get("shocks") or {})
    pnl_economic = Decimal("0")
    pnl_oci = Decimal("0")
    pnl_tpl = Decimal("0")
    rate_contribution = Decimal("0")
    convexity_contribution = Decimal("0")
    by_asset_class = {"rate": Decimal("0"), "credit": Decimal("0"), "other": Decimal("0")}

    for metric in position_metrics:
        shock_bp = safe_decimal(shocks.get(str(metric["tenor_bucket"]), 0))
        shock_decimal = shock_bp / Decimal("10000")
        market_value = safe_decimal(metric["market_value"])
        modified_duration = safe_decimal(metric["modified_duration"])
        convexity = safe_decimal(metric["convexity"])
        rate_effect = -modified_duration * market_value * shock_decimal
        convexity_effect = (
            Decimal("0.5") * convexity * market_value * shock_decimal * shock_decimal
        )
        delta_pnl = rate_effect + convexity_effect

        pnl_economic += delta_pnl
        rate_contribution += rate_effect
        convexity_contribution += convexity_effect

        accounting_class = str(metric["accounting_class"])
        if accounting_class == "OCI":
            pnl_oci += delta_pnl
        elif accounting_class == "TPL":
            pnl_tpl += delta_pnl

        asset_class = str(metric["asset_class"])
        by_asset_class[asset_class if asset_class in by_asset_class else "other"] += delta_pnl

    return {
        "scenario_name": str(scenario.get("name") or "custom"),
        "scenario_description": str(scenario.get("description") or ""),
        "shocks": {key: int(safe_decimal(value)) for key, value in shocks.items()},
        "pnl_economic": pnl_economic,
        "pnl_oci": pnl_oci,
        "pnl_tpl": pnl_tpl,
        "rate_contribution": rate_contribution,
        "convexity_contribution": convexity_contribution,
        "by_asset_class": by_asset_class,
    }


def aggregate_krd_by_asset_class(
    position_metrics: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    metrics = list(position_metrics)
    total_market_value = sum(
        (safe_decimal(metric["market_value"]) for metric in metrics),
        Decimal("0"),
    )
    groups: dict[str, dict[str, Any]] = {}

    for metric in metrics:
        asset_class = str(metric["asset_class"])
        group = groups.setdefault(
            asset_class,
            {
                "asset_class": asset_class,
                "market_value": Decimal("0"),
                "weighted_duration": Decimal("0"),
                "dv01": Decimal("0"),
            },
        )
        market_value = safe_decimal(metric["market_value"])
        group["market_value"] += market_value
        group["weighted_duration"] += market_value * safe_decimal(metric["duration"])
        group["dv01"] += safe_decimal(metric["dv01"])

    results: list[dict[str, Any]] = []
    for asset_class, payload in groups.items():
        market_value = payload["market_value"]
        results.append(
            {
                "asset_class": asset_class,
                "market_value": market_value,
                "duration": (
                    payload["weighted_duration"] / market_value
                    if market_value > 0
                    else Decimal("0")
                ),
                "dv01": payload["dv01"],
                "weight": (
                    market_value / total_market_value if total_market_value > 0 else Decimal("0")
                ),
            }
        )
    return results


def compute_krd_curve_risk(
    positions: Iterable[Any],
    *,
    report_date: date | None = None,
    scenarios: Iterable[Mapping[str, Any]] | None = None,
    wind_metrics: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    metrics = build_krd_position_metrics(
        positions,
        report_date=report_date,
        wind_metrics=wind_metrics,
    )
    total_market_value = sum(
        (metric["market_value"] for metric in metrics),
        Decimal("0"),
    )

    portfolio_duration = Decimal("0")
    portfolio_modified_duration = Decimal("0")
    portfolio_dv01 = Decimal("0")
    portfolio_convexity = Decimal("0")

    for metric in metrics:
        weight = safe_decimal(metric["weight"])
        portfolio_duration += weight * safe_decimal(metric["duration"])
        portfolio_modified_duration += weight * safe_decimal(metric["modified_duration"])
        portfolio_dv01 += safe_decimal(metric["dv01"])
        portfolio_convexity += weight * safe_decimal(metric["convexity"])

    scenario_inputs = list(scenarios) if scenarios is not None else list(STANDARD_KRD_SCENARIOS)
    return {
        "position_metrics": metrics,
        "total_market_value": total_market_value,
        "portfolio_duration": portfolio_duration,
        "portfolio_modified_duration": portfolio_modified_duration,
        "portfolio_dv01": portfolio_dv01,
        "portfolio_convexity": portfolio_convexity,
        "krd_buckets": compute_krd_by_tenor(
            positions,
            report_date=report_date,
            wind_metrics=wind_metrics,
        ),
        "scenarios": [compute_curve_scenario(metrics, scenario) for scenario in scenario_inputs],
        "by_asset_class": aggregate_krd_by_asset_class(metrics),
    }
