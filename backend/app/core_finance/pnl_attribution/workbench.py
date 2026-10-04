"""PnL attribution workbench — pure functions over in-memory fact rows (float payloads for API).

Formal calculations live here; services only read DuckDB (read-only) and pass rows in.
Reuses `read_models` aggregators where applicable (iron rule: no duplicate bucket/KRD math).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from math import isfinite
from typing import Any, Literal, cast

from backend.app.core_finance.bond_analytics.common import (
    build_curve_points,
    build_full_curve,
    get_tenor_bucket,
    interpolate_rate,
)
from backend.app.core_finance.bond_analytics.read_models import (
    build_krd_distribution,
    summarize_portfolio_risk,
)
from backend.app.core_finance.decimal_utils import to_decimal
from backend.app.core_finance.field_normalization import ACCOUNTING_BASIS_FVTPL

CompareType = Literal["mom", "yoy"]
PositionKey = tuple[str, str, str]
DATA_FALLBACK_MSG = "数据尚未物化，当前展示空白结构。"
ZERO = Decimal("0")
HUNDRED = Decimal("100")
TEN_THOUSAND = Decimal("10000")
TWELVE = Decimal("12")
FOUR_DP = Decimal("0.0001")


def _f(x: object | None, _field_hint: str = "") -> Decimal:
    return to_decimal(x)


def _out(value: Decimal, quantum: Decimal | None = None) -> float:
    if quantum is not None:
        value = value.quantize(quantum, rounding=ROUND_HALF_UP)
    return float(value)


def _pearson_r(xs: list[Decimal], ys: list[Decimal]) -> float | None:
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx = sum(xs, ZERO) / Decimal(n)
    my = sum(ys, ZERO) / Decimal(n)
    num = sum(((xs[i] - mx) * (ys[i] - my) for i in range(n)), ZERO)
    denx = sum(((xi - mx) ** 2 for xi in xs), ZERO)
    deny = sum(((yi - my) ** 2 for yi in ys), ZERO)
    if denx <= 0 or deny <= 0:
        return None
    return _out(num / (denx.sqrt() * deny.sqrt()))


def _period_label_cn(ym: str) -> str:
    y, m = ym.split("-", 1)
    return f"{y}年{int(m)}月"


def is_tpl_accounting(accounting_basis: str) -> bool:
    u = (accounting_basis or "").upper()
    raw = accounting_basis or ""
    return "TPL" in u or ACCOUNTING_BASIS_FVTPL in u or "交易性" in raw


def _category_type_for_invest(inv: str) -> str:
    if "负债" in inv:
        return "liability"
    return "asset"


def position_key(row: dict[str, Any]) -> PositionKey:
    return (
        str(row.get("instrument_code") or ""),
        str(row.get("portfolio_name") or ""),
        str(row.get("cost_center") or ""),
    )


def _mv_decimal_index(bond_rows: list[dict[str, Any]]) -> dict[PositionKey, Decimal]:
    out: dict[PositionKey, Decimal] = defaultdict(Decimal)
    for r in bond_rows:
        out[position_key(r)] += _f(r.get("market_value"))
    return dict(out)


def mv_index(bond_rows: list[dict[str, Any]]) -> dict[PositionKey, float]:
    """Compatibility boundary for service consumers; attribution uses Decimal internally."""
    return {key: _out(value) for key, value in _mv_decimal_index(bond_rows).items()}


def _aggregate_scale_pnl_by_group(
    pnl_rows: list[dict[str, Any]],
    mv_by_key: dict[PositionKey, Decimal],
    group_field: str = "invest_type_std",
) -> dict[str, dict[str, Decimal]]:
    agg: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"pnl": ZERO, "scale": ZERO})
    for r in pnl_rows:
        g = str(r.get(group_field) or "未分类")
        mv = mv_by_key.get(position_key(r), ZERO)
        agg[g]["pnl"] += _f(r.get("total_pnl"))
        agg[g]["scale"] += mv
    return dict(agg)


def _aggregate_pnl_scale_rows_by_group(
    rows: list[dict[str, Any]],
    *,
    group_field: str,
    pnl_field: str,
    scale_field: str,
    interest_field: str | None = None,
) -> dict[str, dict[str, Decimal | None]]:
    component_fields = ("fair_value_change_516", "capital_gain_517", "manual_adjustment")
    agg: dict[str, dict[str, Decimal | None]] = defaultdict(
        lambda: {"pnl": ZERO, "scale": ZERO, "interest": ZERO, **dict.fromkeys(component_fields, ZERO)}
    )
    for r in rows:
        g = str(r.get(group_field) or r.get("business_type") or r.get("invest_type_std") or "Unclassified")
        pnl = _finite_decimal(r.get(pnl_field))
        if pnl is None:
            raise ValueError(f"Volume/rate attribution requires finite {pnl_field} for {g}")
        # Unlike the optional components, these two totals are initialized to ZERO
        # and are only ever assigned Decimal sums inside this function.
        agg[g]["pnl"] = cast(Decimal, agg[g]["pnl"]) + pnl
        agg[g]["scale"] = cast(Decimal, agg[g]["scale"]) + _f(r.get(scale_field), scale_field)
        # An absent account component is unknown, not an observed zero. The
        # unexplained amount keeps any missing component or source tie-out gap.
        if interest_field is not None:
            for target, source in (("interest", interest_field), *((field, field) for field in component_fields)):
                value = _finite_decimal(r.get(source))
                accumulated = agg[g][target]
                agg[g][target] = accumulated + value if accumulated is not None and value is not None else None
        else:
            # interest_field is fixed for the entire call, so this branch never
            # encounters the unknown-component assignments from the other branch.
            agg[g]["interest"] = cast(Decimal, agg[g]["interest"]) + _f(r.get(pnl_field), pnl_field)
    return dict(agg)


def _build_volume_rate_from_group_aggregates(
    *,
    cur: dict[str, dict[str, Any]],
    prev: dict[str, dict[str, Any]],
    has_prior: bool,
    current_period: str,
    previous_period: str,
    compare_type: CompareType,
    separate_interest: bool = False,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    categories = sorted(set(cur) | set(prev))
    total_cur_pnl = sum((v["pnl"] for v in cur.values()), ZERO)
    total_prev_pnl = sum((v["pnl"] for v in prev.values()), ZERO) if has_prior else None
    total_pnl_change = (total_cur_pnl - total_prev_pnl) if has_prior and total_prev_pnl is not None else None

    total_vol = total_rate = total_ix = ZERO
    direct_fields = {
        "fair_value_effect": "fair_value_change_516",
        "capital_gain_effect": "capital_gain_517",
        "manual_adjustment_effect": "manual_adjustment",
    }
    total_direct = dict.fromkeys(direct_fields, ZERO)
    direct_inputs_complete = dict.fromkeys(direct_fields, True)
    interest_inputs_complete = True
    for cat in categories:
        c = cur.get(cat, {"pnl": ZERO, "scale": ZERO})
        p = prev.get(cat, {"pnl": ZERO, "scale": ZERO}) if has_prior else None
        Qc, Pc = c["scale"], c["pnl"]
        Qp = p["scale"] if p else None
        Pp = p["pnl"] if p else None
        Ic = c.get("interest", Pc)
        Ip = p.get("interest", Pp) if p else None
        interest_inputs_complete = interest_inputs_complete and Ic is not None and (not has_prior or Ip is not None)
        yc = (Ic / Qc) if Qc > 0 and Ic is not None else None
        yp = (Ip / Qp) if p and Qp is not None and Qp > 0 and Ip is not None else None
        pnl_change = (Pc - Pp) if p and Pp is not None else None
        pnl_change_pct = ((pnl_change / Pp) * HUNDRED) if p and Pp not in (None, ZERO) and pnl_change is not None else None
        vol_eff = rate_eff = ix_eff = None
        if p is not None and Qp is not None and yp is not None and yc is not None:
            vol_eff = (Qc - Qp) * yp
            rate_eff = Qp * (yc - yp)
            ix_eff = (Qc - Qp) * (yc - yp)
        attrib_sum = None
        if vol_eff is not None and rate_eff is not None and ix_eff is not None:
            attrib_sum = vol_eff + rate_eff + ix_eff
        direct_effects = {}
        known_direct_sum = ZERO
        for effect, source in direct_fields.items():
            c_component, p_component = c.get(source, ZERO), p.get(source, ZERO) if p else None
            direct = c_component - p_component if c_component is not None and p_component is not None else None
            direct_effects[effect] = _out(direct) if direct is not None else None
            direct_inputs_complete[effect] = direct_inputs_complete[effect] and c_component is not None and (not has_prior or p_component is not None)
            if direct is not None:
                total_direct[effect] += direct
                known_direct_sum += direct
        if separate_interest and has_prior:
            attrib_sum = sum((v for v in (vol_eff, rate_eff, ix_eff) if v is not None), ZERO)
            attrib_sum += known_direct_sum
        recon = (pnl_change - attrib_sum) if pnl_change is not None and attrib_sum is not None else None
        vol_pct = (
            (vol_eff / pnl_change * HUNDRED)
            if vol_eff is not None and pnl_change not in (None, ZERO)
            else None
        )
        rate_pct = (
            (rate_eff / pnl_change * HUNDRED)
            if rate_eff is not None and pnl_change not in (None, ZERO)
            else None
        )
        if vol_eff is not None:
            total_vol += vol_eff
        if rate_eff is not None:
            total_rate += rate_eff
        if ix_eff is not None:
            total_ix += ix_eff
        items.append(
            {
                "category": cat,
                "category_type": _category_type_for_invest(cat),
                "level": 0,
                "current_scale": _out(Qc),
                "current_pnl": _out(Pc),
                "current_yield_pct": _out(yc * HUNDRED) if yc is not None else None,
                "previous_scale": _out(Qp) if Qp is not None else None,
                "previous_pnl": _out(Pp) if Pp is not None else None,
                "previous_yield_pct": _out(yp * HUNDRED) if yp is not None else None,
                "pnl_change": _out(pnl_change) if pnl_change is not None else None,
                "pnl_change_pct": _out(pnl_change_pct) if pnl_change_pct is not None else None,
                "volume_effect": _out(vol_eff) if vol_eff is not None else None,
                "rate_effect": _out(rate_eff) if rate_eff is not None else None,
                "interaction_effect": _out(ix_eff) if ix_eff is not None else None,
                **direct_effects,
                "attrib_sum": _out(attrib_sum) if attrib_sum is not None else None,
                "recon_error": _out(recon) if recon is not None else None,
                "volume_contribution_pct": _out(vol_pct) if vol_pct is not None else None,
                "rate_contribution_pct": _out(rate_pct) if rate_pct is not None else None,
            }
        )

    total_attrib_sum = (total_vol + total_rate + total_ix + sum(total_direct.values(), ZERO)) if has_prior else None
    total_recon_error = (
        total_pnl_change - total_attrib_sum
        if total_pnl_change is not None and total_attrib_sum is not None
        else None
    )
    return {
        "current_period": current_period,
        "previous_period": previous_period,
        "compare_type": compare_type,
        "total_current_pnl": _out(total_cur_pnl),
        "total_previous_pnl": _out(total_prev_pnl) if total_prev_pnl is not None else None,
        "total_pnl_change": _out(total_pnl_change) if total_pnl_change is not None else None,
        "total_volume_effect": _out(total_vol) if has_prior and interest_inputs_complete else None,
        "total_rate_effect": _out(total_rate) if has_prior and interest_inputs_complete else None,
        "total_interaction_effect": _out(total_ix) if has_prior and interest_inputs_complete else None,
        **{f"total_{effect}": _out(value) if has_prior and direct_inputs_complete[effect] else None for effect, value in total_direct.items()},
        "has_complete_inputs": interest_inputs_complete and all(direct_inputs_complete.values()),
        "attribution_basis": "interest_income_and_direct_pnl" if separate_interest else "total_pnl_scale_proxy",
        "total_recon_error": _out(total_recon_error) if total_recon_error is not None else None,
        "items": items,
        "has_previous_data": has_prior,
    }


def _treasury_10y_pct(curve: dict[str, Decimal]) -> float | None:
    for key in ("10Y", "10y", "10"):
        if key in curve:
            return float(curve[key])
    return None


def _tenor_bucket_mid_years(tenor: str) -> float:
    t = (tenor or "").strip().upper().replace(" ", "")
    fixed = {"1Y": 1.0, "2Y": 2.0, "3Y": 3.0, "5Y": 5.0, "7Y": 7.0, "10Y": 10.0, "20Y": 20.0, "30Y": 30.0}
    if t in fixed:
        return fixed[t]
    if t.endswith("M"):
        try:
            months = float(t[:-1])
            if months > 0:
                return months / 12.0
        except ValueError:
            pass
    if "-" in t and t.endswith("Y"):
        body = t[:-1]
        parts = body.split("-")
        if len(parts) == 2:
            try:
                return (float(parts[0]) + float(parts[1])) / 2.0
            except ValueError:
                pass
    return 5.0


def _finite_float(value: object | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) else None


def _finite_decimal(value: object | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return None
    return parsed if parsed.is_finite() else None


def _weighted_ytm_decimal(rows: list[dict[str, Any]]) -> Decimal | None:
    """Market-value-weighted average YTM over rows with an explicit finite YTM."""
    num = ZERO
    den = ZERO
    for row in rows:
        ytm = _finite_decimal(row.get("ytm"))
        market_value = _finite_decimal(row.get("market_value"))
        if ytm is None or market_value is None:
            continue
        num += market_value * ytm
        den += market_value
    if den <= 0:
        return None
    return num / den


def _mv_weighted_field_decimal(rows: list[dict[str, Any]], field: str) -> Decimal | None:
    """Market-value-weighted average of ``field`` over rows with a finite value.

    Same missing-value contract as :func:`_weighted_ytm_decimal` and as the
    bond-analytics SQL layer: a row missing the field (or missing market value)
    leaves both numerator and denominator, so missing is never read as zero.
    """
    num = ZERO
    den = ZERO
    for row in rows:
        value = _finite_decimal(row.get(field))
        market_value = _finite_decimal(row.get("market_value"))
        if value is None or market_value is None:
            continue
        num += market_value * value
        den += market_value
    if den <= 0:
        return None
    return num / den


def _weighted_ytm_float(rows: list[dict[str, Any]]) -> float | None:
    """Compatibility boundary for callers that still consume float payloads."""
    value = _weighted_ytm_decimal(rows)
    return _out(value) if value is not None else None


def _curve_rate_pct(points: list[tuple[float, Decimal]], target_years: Decimal) -> Decimal:
    return _f(interpolate_rate(points, max(0.0, _out(target_years))))


def _roll_down_slope_bp(
    row: dict[str, Any],
    curve_points: list[tuple[float, Decimal]] | None,
) -> Decimal | None:
    if not curve_points:
        return None
    years = _f(row.get("years_to_maturity"))
    if years <= 0:
        return None
    rolled_years = max(ZERO, years - Decimal("1"))
    current_rate = _curve_rate_pct(curve_points, years)
    rolled_rate = _curve_rate_pct(curve_points, rolled_years)
    return (current_rate - rolled_rate) * HUNDRED


def _rows_for_bucket(all_rows: list[dict[str, Any]], tenor_bucket: str) -> list[dict[str, Any]]:
    return [r for r in all_rows if str(r.get("tenor_bucket") or "") == tenor_bucket]


def _rows_with_current_tenor_bucket(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply one current tenor policy to both comparison dates without mutating facts."""
    normalized: list[dict[str, Any]] = []
    for row in rows:
        years = _finite_float(row.get("years_to_maturity"))
        if years is None or years <= 0:
            normalized.append(row)
            continue
        tenor = get_tenor_bucket(years)
        if tenor == str(row.get("tenor_bucket") or ""):
            normalized.append(row)
            continue
        normalized_row = dict(row)
        normalized_row["tenor_bucket"] = tenor
        normalized.append(normalized_row)
    return normalized


RiskCoverageExclusionReason = Literal[
    "no_maturity",
    "missing_maturity",
    "matured_or_expired",
    "nonpositive_duration",
]


def _as_date(value: object | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _risk_exclusion_reason(
    row: dict[str, Any],
    *,
    report_date: str,
) -> RiskCoverageExclusionReason | None:
    """Return why a row cannot enter maturity-based duration attribution.

    An explicit blank bond-ledger maturity is the governed no-maturity signal,
    so it is never inferred from duration or a legacy tenor bucket. Rows from
    older in-memory callers that do not carry a maturity_date key remain
    compatible when they provide positive years to maturity and positive
    modified duration.
    """
    years = _finite_float(row.get("years_to_maturity"))
    has_maturity_field = "maturity_date" in row
    maturity_value = row.get("maturity_date")
    if has_maturity_field and (
        maturity_value is None or not str(maturity_value).strip()
    ):
        return "no_maturity"
    if has_maturity_field and _as_date(maturity_value) is None:
        return "missing_maturity"
    if not has_maturity_field and years is None:
        return "missing_maturity"

    market_value = _finite_float(row.get("market_value"))
    if market_value == 0:
        return None

    maturity = _as_date(maturity_value)
    as_of = _as_date(report_date)
    if maturity is not None and as_of is not None and maturity <= as_of:
        return "matured_or_expired"
    if years is None:
        return "nonpositive_duration"
    if years <= 0:
        return "matured_or_expired"

    duration = _finite_float(row.get("modified_duration"))
    if duration is None or duration <= 0:
        return "nonpositive_duration"
    return None


def _partition_maturity_risk_rows(
    rows: list[dict[str, Any]],
    *,
    report_date: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Split covered rows from rows that cannot support maturity risk math."""
    covered: list[dict[str, Any]] = []
    excluded: dict[RiskCoverageExclusionReason, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        reason = _risk_exclusion_reason(row, report_date=report_date)
        if reason is None:
            covered.append(row)
        else:
            excluded[reason].append(row)

    total_mv = sum((_f(row.get("market_value")) for row in rows), ZERO)
    covered_mv = sum((_f(row.get("market_value")) for row in covered), ZERO)
    excluded_mv = sum(
        (
            _f(row.get("market_value"))
            for reason_rows in excluded.values()
            for row in reason_rows
        ),
        ZERO,
    )
    coverage_pct = covered_mv / total_mv * HUNDRED if total_mv != 0 else ZERO
    excluded_pct = excluded_mv / total_mv * HUNDRED if total_mv != 0 else ZERO
    reason_order: tuple[RiskCoverageExclusionReason, ...] = (
        "no_maturity",
        "missing_maturity",
        "matured_or_expired",
        "nonpositive_duration",
    )
    exclusions = [
        {
            "reason": reason,
            "row_count": len(excluded[reason]),
            "market_value": sum((_f(row.get("market_value")) for row in excluded[reason]), ZERO),
        }
        for reason in reason_order
        if excluded[reason]
    ]
    return covered, {
        "total_row_count": len(rows),
        "covered_row_count": len(covered),
        "excluded_row_count": len(rows) - len(covered),
        "total_market_value": total_mv,
        "covered_market_value": covered_mv,
        "excluded_market_value": excluded_mv,
        "coverage_pct": coverage_pct,
        "excluded_pct": excluded_pct,
        "exclusions": exclusions,
    }


def _serialize_risk_coverage(coverage: dict[str, Any]) -> dict[str, Any]:
    return {
        **coverage,
        "total_market_value": _out(coverage["total_market_value"]),
        "covered_market_value": _out(coverage["covered_market_value"]),
        "excluded_market_value": _out(coverage["excluded_market_value"]),
        "coverage_pct": _out(coverage["coverage_pct"], FOUR_DP),
        "excluded_pct": _out(coverage["excluded_pct"], FOUR_DP),
        "exclusions": [
            {**item, "market_value": _out(item["market_value"])}
            for item in coverage["exclusions"]
        ],
    }


def build_volume_rate_attribution(
    *,
    current_pnl: list[dict[str, Any]],
    prior_pnl: list[dict[str, Any]] | None,
    current_bond: list[dict[str, Any]],
    prior_bond: list[dict[str, Any]] | None,
    current_period: str,
    previous_period: str,
    compare_type: CompareType,
) -> dict[str, Any]:
    """Two-period volume / rate / interaction on scale×yield proxy (PnL FI + bond MV)."""
    mv_c = _mv_decimal_index(current_bond)
    cur = _aggregate_scale_pnl_by_group(current_pnl, mv_c)
    has_prior = bool(prior_pnl and prior_bond)
    mv_p = _mv_decimal_index(prior_bond or []) if has_prior else {}
    prev = _aggregate_scale_pnl_by_group(prior_pnl or [], mv_p) if has_prior else {}

    return _build_volume_rate_from_group_aggregates(
        cur=cur,
        prev=prev,
        has_prior=has_prior,
        current_period=current_period,
        previous_period=previous_period,
        compare_type=compare_type,
    )


def build_volume_rate_attribution_from_grouped_rows(
    *,
    current_rows: list[dict[str, Any]],
    prior_rows: list[dict[str, Any]] | None,
    current_period: str,
    previous_period: str,
    compare_type: CompareType,
    group_field: str = "business_type_primary",
    pnl_field: str = "total_pnl",
    scale_field: str = "scale_amount",
    interest_field: str | None = None,
) -> dict[str, Any]:
    """Two-period attribution when PnL and scale are already aligned by business group."""
    cur = _aggregate_pnl_scale_rows_by_group(
        current_rows,
        group_field=group_field,
        pnl_field=pnl_field,
        scale_field=scale_field,
        interest_field=interest_field,
    )
    has_prior = bool(prior_rows)
    prev = (
        _aggregate_pnl_scale_rows_by_group(
            prior_rows or [],
            group_field=group_field,
            pnl_field=pnl_field,
            scale_field=scale_field,
            interest_field=interest_field,
        )
        if has_prior
        else {}
    )
    return _build_volume_rate_from_group_aggregates(
        cur=cur,
        prev=prev,
        has_prior=has_prior,
        current_period=current_period,
        previous_period=previous_period,
        compare_type=compare_type,
        separate_interest=interest_field is not None,
    )


def tpl_monthly_treasury_change_bp(current: object | None, previous: object | None) -> float | None:
    """One calendar month's yield change; input levels are percent points."""
    current_value = _finite_decimal(current)
    previous_value = _finite_decimal(previous)
    if current_value is None or previous_value is None:
        return None
    return _out((current_value - previous_value) * HUNDRED)


def _tpl_complete_month_window(
    monthly_points: list[dict[str, Any]], start_period: str, end_period: str
) -> bool:
    try:
        start = date.fromisoformat(f"{start_period}-01")
        end = date.fromisoformat(f"{end_period}-01")
        periods = [date.fromisoformat(f"{point.get('period')}-01") for point in monthly_points]
    except (TypeError, ValueError):
        return False
    start_month = start.year * 12 + start.month
    expected_months = end.year * 12 + end.month - start_month + 1
    return expected_months > 0 and len(periods) == expected_months and all(
        period.year * 12 + period.month == start_month + index
        for index, period in enumerate(periods)
    )


def build_tpl_market_correlation(
    *,
    monthly_points: list[dict[str, Any]],
    start_period: str,
    end_period: str,
) -> dict[str, Any]:
    """monthly_points: period (YYYY-MM), tpl_fair_value_change, tpl_total_pnl, tpl_scale, treasury_10y, treasury_10y_change, dr007."""
    xs: list[Decimal] = []
    ys: list[Decimal] = []
    for p in monthly_points:
        dty = _finite_decimal(p.get("treasury_10y_change"))
        dfv = _finite_decimal(p.get("tpl_fair_value_change"))
        if dty is None or dfv is None:
            continue
        xs.append(dty)
        ys.append(dfv)
    r = _pearson_r(xs, ys)
    interpretation = (
        "样本不足或缺曲线点位，无法估计相关系数。"
        if r is None
        else (
            "TPL 公允价值月度变动与 10Y 国债收益率变动呈负相关，方向与久期逻辑一致。"
            if r < -0.3
            else (
                "TPL 公允价值月度变动与 10Y 国债收益率变动呈正相关。"
                if r > 0.3
                else "TPL 与国债收益率变动的线性相关性较弱。"
            )
        )
    )
    complete_window = _tpl_complete_month_window(monthly_points, start_period, end_period)
    tpl_amounts = [_finite_decimal(p.get("tpl_fair_value_change")) for p in monthly_points]
    total_tpl = (
        None
        if not complete_window or any(value is None for value in tpl_amounts)
        else sum((value for value in tpl_amounts if value is not None), ZERO)
    )
    t_changes = [
        value
        for p in monthly_points
        if (value := _finite_decimal(p.get("treasury_10y_change"))) is not None
    ]
    avg_dt = sum(t_changes, ZERO) / Decimal(len(t_changes)) if t_changes else None
    ttot = (
        sum(t_changes, ZERO)
        if complete_window and len(t_changes) == len(monthly_points)
        else None
    )
    summary = (
        "样本期内数据不足，无法生成解读。"
        if not monthly_points
        else "样本期内利率与 TPL 估值变动的对照关系见相关系数与散点结构。"
    )
    if monthly_points and (total_tpl is None or ttot is None):
        summary += "观察窗口存在缺失或无效数据，相应累计值显示为空；相关系数仅使用有效的同月配对。"
    return {
        "start_period": start_period,
        "end_period": end_period,
        "num_periods": len(monthly_points),
        "correlation_coefficient": r,
        "correlation_interpretation": interpretation,
        "total_tpl_fv_change": _out(total_tpl) if total_tpl is not None else None,
        "avg_treasury_10y_change": _out(avg_dt) if avg_dt is not None else None,
        "treasury_10y_total_change_bp": _out(ttot) if ttot is not None else None,
        "data_points": monthly_points,
        "analysis_summary": summary,
    }


def build_pnl_composition(
    *,
    report_period: str,
    report_date: str,
    pnl_rows: list[dict[str, Any]],
    trend_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """trend_rows: list of {period, period_label, interest_income, fair_value_change, capital_gain, total_pnl}."""
    items: list[dict[str, Any]] = []
    by_cat: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {
            "interest": ZERO,
            "fv": ZERO,
            "cg": ZERO,
            "oth": ZERO,
            "total": ZERO,
        }
    )
    for r in pnl_rows:
        cat = str(r.get("invest_type_std") or "未分类")
        by_cat[cat]["interest"] += _f(r.get("interest_income_514"))
        by_cat[cat]["fv"] += _f(r.get("fair_value_change_516"))
        by_cat[cat]["cg"] += _f(r.get("capital_gain_517"))
        by_cat[cat]["oth"] += _f(r.get("manual_adjustment"))
        by_cat[cat]["total"] += _f(r.get("total_pnl"))

    tot_i = sum((v["interest"] for v in by_cat.values()), ZERO)
    tot_f = sum((v["fv"] for v in by_cat.values()), ZERO)
    tot_c = sum((v["cg"] for v in by_cat.values()), ZERO)
    tot_o = sum((v["oth"] for v in by_cat.values()), ZERO)
    tot_p = sum((v["total"] for v in by_cat.values()), ZERO)

    def _pct(part: Decimal, whole: Decimal) -> Decimal:
        return (part / whole * HUNDRED) if whole else ZERO

    for cat, v in sorted(by_cat.items()):
        t = v["total"]
        explained = v["interest"] + v["fv"] + v["cg"] + v["oth"]
        items.append(
            {
                "category": cat,
                "category_type": _category_type_for_invest(cat),
                "level": 0,
                "total_pnl": _out(t),
                "interest_income": _out(v["interest"]),
                "fair_value_change": _out(v["fv"]),
                "capital_gain": _out(v["cg"]),
                "other_income": _out(v["oth"]),
                "interest_pct": _out(_pct(v["interest"], t)),
                "fair_value_pct": _out(_pct(v["fv"], t)),
                "capital_gain_pct": _out(_pct(v["cg"], t)),
                "other_pct": _out(_pct(v["oth"], t)),
                "unexplained_residual": _out(t - explained),
            }
        )

    return {
        "report_period": report_period,
        "report_date": report_date,
        "total_pnl": _out(tot_p),
        "total_interest_income": _out(tot_i),
        "total_fair_value_change": _out(tot_f),
        "total_capital_gain": _out(tot_c),
        "total_other_income": _out(tot_o),
        "interest_pct": _out(_pct(tot_i, tot_p)),
        "fair_value_pct": _out(_pct(tot_f, tot_p)),
        "capital_gain_pct": _out(_pct(tot_c, tot_p)),
        "other_pct": _out(_pct(tot_o, tot_p)),
        "unexplained_residual": _out(tot_p - (tot_i + tot_f + tot_c + tot_o)),
        "items": items,
        "trend_data": trend_rows,
    }


def build_pnl_attribution_analysis_summary(
    *,
    report_date: str,
    volume_effect: float | None,
    rate_effect: float | None,
    correlation_tpl_treasury: float | None,
    interaction_effect: float | None = None,
    fair_value_effect: float | None = None,
    capital_gain_effect: float | None = None,
    manual_adjustment_effect: float | None = None,
    unexplained_effect: float | None = None,
    attribution_basis: str | None = None,
) -> dict[str, Any]:
    effects = {"volume": volume_effect, "rate": rate_effect}
    if attribution_basis == "interest_income_and_direct_pnl":
        effects.update(
            interaction=interaction_effect, fair_value=fair_value_effect,
            capital_gain=capital_gain_effect, manual_adjustment=manual_adjustment_effect,
            unexplained=unexplained_effect,
        )
    observed = {key: _finite_decimal(value) for key, value in effects.items()}
    primary, pct = "unknown", None
    if all(value is not None for value in observed.values()):
        magnitudes = {key: abs(value) for key, value in observed.items() if value is not None}
        denominator = sum(magnitudes.values(), ZERO)
        pct = ZERO
        if denominator > 0:
            primary = max(magnitudes, key=magnitudes.__getitem__)
            pct = magnitudes[primary] / denominator * HUNDRED

    aligned = correlation_tpl_treasury is not None and correlation_tpl_treasury < -0.4
    note = (
        "相关系数为负且绝对值较大时，TPL 与利率走势更一致。"
        if correlation_tpl_treasury is not None
        else "缺少 TPL–利率样本，暂不评价对齐程度。"
    )
    findings = [
        "本期损益变动按利息量价、非利息科目直接变动及未解释差额列示；主驱动占比以各项绝对值合计为分母。"
        if attribution_basis == "interest_income_and_direct_pnl"
        else "规模与利率效应的相对分解见规模/利率页签。",
    ]
    if primary != "unknown" and pct is not None:
        labels = {"volume": "规模效应", "rate": "利息收益率效应", "interaction": "交叉效应", "fair_value": "公允价值变动", "capital_gain": "投资收益变动", "manual_adjustment": "手工调整变动", "unexplained": "未解释差额"}
        findings.append(f"最大变动项为{labels[primary]}（约 {pct.quantize(Decimal('1'), rounding=ROUND_HALF_UP)}% 相对占比）。")
    elif pct is None:
        findings.append("归因分项缺失，暂不判断主驱动。")
    if correlation_tpl_treasury is not None:
        findings.append(f"TPL 与 10Y 国债月度变动的样本相关系数约为 {correlation_tpl_treasury:.2f}。")

    return {
        "report_date": report_date,
        "primary_driver": primary,
        "primary_driver_pct": _out(pct, Decimal("0.1")) if pct is not None else None,
        "key_findings": findings,
        "tpl_market_aligned": aligned,
        "tpl_market_note": note,
    }


def build_carry_roll_down(
    *,
    report_date: str,
    bond_rows: list[dict[str, Any]],
    ftp_rate_pct: float,
    curve_slope_bp: float | None,
    treasury_curve: dict[str, Decimal] | None = None,
) -> dict[str, Any]:
    """Grouped by asset_class_std; uses read-model-style weights from rows."""
    if not bond_rows:
        return {
            "report_date": report_date,
            "total_market_value": 0.0,
            "portfolio_carry": 0.0,
            "portfolio_rolldown": 0.0,
            "portfolio_static_return": 0.0,
            "total_carry_pnl": 0.0,
            "total_rolldown_pnl": 0.0,
            "total_static_pnl": 0.0,
            "ftp_rate": _out(_f(ftp_rate_pct)),
            "items": [],
        }

    by_ac: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in bond_rows:
        by_ac[str(r.get("asset_class_std") or "未分类")].append(r)

    total_mv = sum((_f(r.get("market_value")) for r in bond_rows), ZERO)
    items: list[dict[str, Any]] = []
    port_carry = port_roll = port_static = ZERO
    t_carry_pnl = t_roll_pnl = t_static_pnl = ZERO
    carry_complete = roll_portfolio_complete = static_complete = True
    # curve_slope_bp 按签名就是可选项（None = 无组合级斜率兜底，逐券用曲线点位），
    # 不走 _f：to_decimal 会把 None 记成一次“静默归零”告警，稀释真正的缺数信号。
    slope = _finite_decimal(curve_slope_bp)
    funding = _f(ftp_rate_pct)
    curve_points = (
        build_curve_points(build_full_curve(treasury_curve))
        if treasury_curve
        else None
    )

    for ac, rows in sorted(by_ac.items()):
        mv = sum((_f(r.get("market_value")) for r in rows), ZERO)
        w = (mv / total_mv * HUNDRED) if total_mv > 0 else ZERO
        # 组率用于全额市值折算，必须覆盖组内全部非零持仓；不能外推观测子集。
        coupon_dec = _mv_weighted_field_decimal(rows, "coupon_rate")
        if any(_f(r.get("market_value")) != ZERO and _finite_decimal(r.get("coupon_rate")) is None for r in rows):
            coupon_dec = None
        coupon_pct = coupon_dec * HUNDRED if coupon_dec is not None else None
        ytm_dec = _weighted_ytm_decimal(rows)
        ytm_pct = ytm_dec * HUNDRED if ytm_dec is not None else None
        dur = _mv_weighted_field_decimal(rows, "modified_duration")
        if any(_f(r.get("market_value")) != ZERO and _finite_decimal(r.get("modified_duration")) is None for r in rows):
            dur = None
        carry_pct = coupon_pct - funding if coupon_pct is not None else None
        carry_pnl = mv * (carry_pct / HUNDRED) / TWELVE if carry_pct is not None else None
        roll_num = ZERO
        roll_den = ZERO
        slope_num = ZERO
        slope_den = ZERO
        slope_complete = True
        roll_complete = dur is not None
        for r in rows:
            row_mv = _f(r.get("market_value"))
            if row_mv <= 0:
                continue
            row_slope = _roll_down_slope_bp(r, curve_points)
            if row_slope is None:
                row_slope = slope
            if row_slope is None:
                slope_complete = False
                roll_complete = False
                continue
            slope_num += row_slope * row_mv
            slope_den += row_mv
            # 斜率只依赖曲线，久期缺失只阻断骑乘及其依赖项。
            row_dur = _finite_decimal(r.get("modified_duration"))
            if row_dur is None:
                roll_complete = False
                continue
            row_rolldown_pct = (row_slope / HUNDRED) * row_dur
            roll_num += row_rolldown_pct * row_mv
            roll_den += row_mv
        rolldown_pct = (roll_num / roll_den) if roll_complete and roll_den > 0 else None
        display_slope = (slope_num / slope_den) if slope_complete and slope_den > 0 else None
        rolldown_pnl = mv * (rolldown_pct / HUNDRED) / TWELVE if rolldown_pct is not None else None
        static_pct = carry_pct + rolldown_pct if carry_pct is not None and rolldown_pct is not None else None
        static_pnl = carry_pnl + rolldown_pnl if carry_pnl is not None and rolldown_pnl is not None else None
        # 零敞口分类不阻断其他持仓；正负敞口抵消仍需完整输入。
        if any(_f(r.get("market_value")) != ZERO for r in rows):
            carry_complete = carry_complete and carry_pct is not None
            roll_portfolio_complete = roll_portfolio_complete and rolldown_pct is not None
            static_complete = static_complete and static_pct is not None
        weight_port = (mv / total_mv) if total_mv > 0 else ZERO
        if carry_pct is not None:
            port_carry += carry_pct * weight_port
        if carry_pnl is not None:
            t_carry_pnl += carry_pnl
        if rolldown_pct is not None:
            port_roll += rolldown_pct * weight_port
        if rolldown_pnl is not None:
            t_roll_pnl += rolldown_pnl
        if static_pct is not None:
            port_static += static_pct * weight_port
        if static_pnl is not None:
            t_static_pnl += static_pnl
        items.append(
            {
                "category": ac,
                "category_type": "asset",
                "market_value": _out(mv),
                "weight": _out(w, FOUR_DP),
                "coupon_rate": _out(coupon_pct, FOUR_DP) if coupon_pct is not None else None,
                "ytm": _out(ytm_pct, FOUR_DP) if ytm_pct is not None else None,
                "funding_cost": _out(funding),
                "carry": _out(carry_pct, FOUR_DP) if carry_pct is not None else None,
                "carry_pnl": _out(carry_pnl, FOUR_DP) if carry_pnl is not None else None,
                "duration": _out(dur, FOUR_DP) if dur is not None else None,
                "curve_slope": _out(display_slope, FOUR_DP) if display_slope is not None else None,
                "rolldown": _out(rolldown_pct, FOUR_DP) if rolldown_pct is not None else None,
                "rolldown_pnl": _out(rolldown_pnl, FOUR_DP) if rolldown_pnl is not None else None,
                "static_return": _out(static_pct, FOUR_DP) if static_pct is not None else None,
                "static_pnl": _out(static_pnl, FOUR_DP) if static_pnl is not None else None,
            }
        )

    return {
        "report_date": report_date,
        "total_market_value": _out(total_mv),
        "portfolio_carry": _out(port_carry, FOUR_DP) if carry_complete else None,
        "portfolio_rolldown": _out(port_roll, FOUR_DP) if roll_portfolio_complete else None,
        "portfolio_static_return": _out(port_static, FOUR_DP) if static_complete else None,
        "total_carry_pnl": _out(t_carry_pnl, FOUR_DP) if carry_complete else None,
        "total_rolldown_pnl": _out(t_roll_pnl, FOUR_DP) if roll_portfolio_complete else None,
        "total_static_pnl": _out(t_static_pnl, FOUR_DP) if static_complete else None,
        "ftp_rate": _out(funding),
        "items": items,
    }


def _spread_position_key(row: dict[str, Any]) -> tuple[str, ...] | None:
    key = tuple(str(row.get(field) or "").strip() for field in (
        "instrument_code", "portfolio_name", "cost_center", "accounting_class", "currency_code",
    ))
    if not key[0] or not key[3] or not key[4]:
        return None
    return (*key[:3], key[3].upper(), key[4].upper())


def _spread_curve_points(curve: dict[str, Decimal] | None) -> list[tuple[float, Decimal]]:
    # Do not synthesize a full curve or turn malformed rates into observed zeroes.
    finite_curve = {
        tenor: rate for tenor, value in (curve or {}).items()
        if (rate := _finite_decimal(value)) is not None
    }
    return build_curve_points(finite_curve)


def _spread_pair_inputs(
    start: dict[str, Any],
    end: dict[str, Any],
    *,
    start_date: str,
    end_date: str,
    curve_start: list[tuple[float, Decimal]],
    curve_end: list[tuple[float, Decimal]],
) -> tuple[str | None, dict[str, Decimal]]:
    if str(start.get("currency_code") or "").strip().upper() != "CNY":
        return "unsupported_currency", {}
    mv_start = _finite_decimal(start.get("market_value"))
    mv_end = _finite_decimal(end.get("market_value"))
    if mv_start is None or mv_end is None or mv_start <= 0 or mv_end <= 0:
        return "invalid_market_value", {}
    y_start = _finite_decimal(start.get("ytm"))
    y_end = _finite_decimal(end.get("ytm"))
    if y_start is None or start.get("ytm_input_status") not in (None, "observed"):
        return "missing_start_ytm", {}
    if y_end is None or end.get("ytm_input_status") not in (None, "observed"):
        return "missing_end_ytm", {}
    if _risk_exclusion_reason(start, report_date=start_date) is not None:
        return "invalid_start_risk", {}
    if start.get("duration_quality_flag") not in (None, "observed"):
        return "estimated_start_duration", {}
    term_start = _finite_decimal(start.get("years_to_maturity"))
    term_end = _finite_decimal(end.get("years_to_maturity"))
    end_maturity = _as_date(end.get("maturity_date"))
    if (term_end is None or term_end <= 0 or
            ("maturity_date" in end and (end_maturity is None or end_maturity <= date.fromisoformat(end_date)))):
        return "invalid_end_tenor", {}
    for side, points, term in (("start", curve_start, term_start), ("end", curve_end, term_end)):
        if not points:
            return f"missing_{side}_curve", {}
        if term is None or not Decimal(str(points[0][0])) <= term <= Decimal(str(points[-1][0])):
            return f"benchmark_{side}_tenor_uncovered", {}
    assert term_start is not None
    g_start = _curve_rate_pct(curve_start, term_start) / HUNDRED
    g_end = _curve_rate_pct(curve_end, term_end) / HUNDRED
    duration = _f(start["modified_duration"])
    exposure = mv_start * duration
    return None, {
        "market_value_start": mv_start,
        "market_value_end": mv_end,
        "exposure": exposure,
        "yield_change": y_end - y_start,
        "treasury_change": g_end - g_start,
        "spread_change": (y_end - g_end) - (y_start - g_start),
        "treasury_effect": -exposure * (g_end - g_start),
        "spread_effect": -exposure * ((y_end - g_end) - (y_start - g_start)),
    }


def build_spread_attribution(
    *,
    report_date: str,
    start_date: str,
    end_date: str,
    bond_rows_end: list[dict[str, Any]],
    bond_rows_start: list[dict[str, Any]],
    treasury_10y_start_pct: float | None,
    treasury_10y_end_pct: float | None,
    treasury_curve_start: dict[str, Decimal] | None = None,
    treasury_curve_end: dict[str, Decimal] | None = None,
) -> dict[str, Any]:
    covered_end, risk_coverage = _partition_maturity_risk_rows(
        bond_rows_end,
        report_date=report_date,
    )
    risk_end = summarize_portfolio_risk(covered_end)
    total_mv = _f(risk_coverage["total_market_value"])
    port_dur = _f(risk_end["portfolio_modified_duration"])
    ten_year_start = _finite_decimal(treasury_10y_start_pct)
    ten_year_end = _finite_decimal(treasury_10y_end_pct)
    dt_pct = ten_year_end - ten_year_start if ten_year_start is not None and ten_year_end is not None else None
    d_bp = (dt_pct * HUNDRED) if dt_pct is not None else None
    curve_start = _spread_curve_points(treasury_curve_start)
    curve_end = _spread_curve_points(treasury_curve_end)
    indexed: list[dict[tuple[str, ...], list[dict[str, Any]]]] = []
    exclusions: dict[str, dict[str, Any]] = {}

    def exclude(reason: str, starts: list[dict[str, Any]], ends: list[dict[str, Any]]) -> None:
        item = exclusions.setdefault(reason, {
            "reason": reason, "start_row_count": 0, "end_row_count": 0,
            "start_market_value": ZERO, "end_market_value": ZERO,
        })
        for side, rows in (("start", starts), ("end", ends)):
            item[f"{side}_row_count"] += len(rows)
            item[f"{side}_market_value"] += sum(
                (_finite_decimal(row.get("market_value")) or ZERO for row in rows), ZERO,
            )

    for side, rows in (("start", bond_rows_start), ("end", bond_rows_end)):
        index: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            key = _spread_position_key(row)
            if key is None:
                exclude("missing_position_key", [row] if side == "start" else [], [row] if side == "end" else [])
            else:
                index[key].append(row)
        indexed.append(index)

    valid_by_ac: dict[str, list[dict[str, Decimal]]] = defaultdict(list)
    valid_pairs: list[dict[str, Decimal]] = []
    matched_count = 0
    for key in sorted(indexed[0].keys() | indexed[1].keys()):
        starts, ends = indexed[0].get(key, []), indexed[1].get(key, [])
        if len(starts) > 1 or len(ends) > 1:
            exclude("duplicate_position_key", starts, ends)
            continue
        if not starts or not ends:
            exclude("added_position" if not starts else "exited_position", starts, ends)
            continue
        matched_count += 1
        reason, values = _spread_pair_inputs(
            starts[0], ends[0], start_date=start_date, end_date=end_date,
            curve_start=curve_start, curve_end=curve_end,
        )
        if reason is not None:
            exclude(reason, starts, ends)
            continue
        valid_pairs.append(values)
        valid_by_ac[str(ends[0].get("asset_class_std") or "未分类")].append(values)

    by_ac: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in covered_end:
        by_ac[str(r.get("asset_class_std") or "未分类")].append(r)
    items: list[dict[str, Any]] = []
    for ac in sorted(by_ac.keys() | valid_by_ac.keys()):
        rows_e = by_ac.get(ac, [])
        mv = sum((_f(r.get("market_value")) for r in rows_e), ZERO)
        w = (mv / total_mv * HUNDRED) if total_mv > 0 else ZERO
        num_d = sum(
            (
                _f(r.get("market_value")) * _f(r.get("modified_duration"))
                for r in rows_e
            ),
            ZERO,
        )
        dur = (num_d / mv) if mv > 0 else ZERO
        pairs = valid_by_ac.get(ac, [])
        matched_mv = sum((pair["market_value_start"] for pair in pairs), ZERO)
        exposure = sum((pair["exposure"] for pair in pairs), ZERO)
        changes = {
            field: (sum((pair["exposure"] * pair[field] for pair in pairs), ZERO) / exposure * TEN_THOUSAND)
            if exposure else None
            for field in ("yield_change", "treasury_change", "spread_change")
        }
        tre_eff = sum((pair["treasury_effect"] for pair in pairs), ZERO)
        spr_eff = sum((pair["spread_effect"] for pair in pairs), ZERO)
        price = tre_eff + spr_eff
        t_pct = (abs(tre_eff) / abs(price) * HUNDRED) if price else (ZERO if tre_eff == 0 else None)
        s_pct = (abs(spr_eff) / abs(price) * HUNDRED) if price else (ZERO if spr_eff == 0 else None)
        items.append(
            {
                "category": ac,
                "category_type": "asset",
                "market_value": _out(mv),
                "duration": _out(dur, FOUR_DP),
                "weight": _out(w, FOUR_DP),
                "matched_start_market_value": _out(matched_mv),
                "attribution_duration": _out(exposure / matched_mv, FOUR_DP) if matched_mv else None,
                "attributed_position_count": len(pairs),
                **{field: _out(value) if value is not None else None for field, value in changes.items()},
                "treasury_effect": _out(tre_eff, FOUR_DP) if pairs else None,
                "spread_effect": _out(spr_eff, FOUR_DP) if pairs else None,
                "total_price_effect": _out(price, FOUR_DP) if pairs else None,
                "treasury_contribution_pct": _out(t_pct, FOUR_DP) if pairs and t_pct is not None else None,
                "spread_contribution_pct": _out(s_pct, FOUR_DP) if pairs and s_pct is not None else None,
            }
        )

    t_eff_tot = sum((pair["treasury_effect"] for pair in valid_pairs), ZERO)
    s_eff_tot = sum((pair["spread_effect"] for pair in valid_pairs), ZERO)
    total_price = t_eff_tot + s_eff_tot
    status = "unavailable" if not valid_pairs else "partial" if exclusions else "complete"
    driver = "unavailable" if not valid_pairs else "unchanged" if t_eff_tot == s_eff_tot == 0 else (
        "treasury" if abs(t_eff_tot) >= abs(s_eff_tot) else "spread"
    )
    interp = {
        "unavailable": "缺少完整的同券两期报价、期初风险暴露或同币种期限基准，无法计算利差归因。",
        "unchanged": "可归因持仓的国债与利差估值效应均为零。",
        "treasury": "可归因持仓中国债基准变动（含期限滚动）主导估值效应。",
        "spread": "可归因持仓中利差变动对估值效应贡献更大。",
    }[driver]
    coverage: dict[str, Any] = {
        "start_row_count": len(bond_rows_start), "end_row_count": len(bond_rows_end),
        "matched_position_count": matched_count, "attributed_position_count": len(valid_pairs),
        "exclusions": [{
            **item, "start_market_value": _out(item["start_market_value"]),
            "end_market_value": _out(item["end_market_value"]),
        } for item in exclusions.values()],
    }
    for side, rows in (("start", bond_rows_start), ("end", bond_rows_end)):
        total = sum((_finite_decimal(row.get("market_value")) or ZERO for row in rows), ZERO)
        covered = sum((pair[f"market_value_{side}"] for pair in valid_pairs), ZERO)
        coverage.update({
            f"{side}_market_value": _out(total),
            f"covered_{side}_market_value": _out(covered),
            f"excluded_{side}_market_value": _out(total - covered),
            f"{side}_coverage_pct": _out(covered / total * HUNDRED, FOUR_DP) if total > 0 else 0.0,
        })
    warnings = []
    if exclusions:
        warnings.append("利差归因仅覆盖两期可匹配且定价资料完整的持仓；新增、退出及资料缺口见覆盖明细。")
    return {
        "report_date": report_date,
        "start_date": start_date,
        "end_date": end_date,
        "treasury_10y_start": _out(ten_year_start) if ten_year_start is not None else None,
        "treasury_10y_end": _out(ten_year_end) if ten_year_end is not None else None,
        "treasury_10y_change": _out(d_bp) if d_bp is not None else None,
        "total_market_value": _out(total_mv),
        "portfolio_duration": _out(port_dur, FOUR_DP),
        "total_treasury_effect": _out(t_eff_tot, FOUR_DP) if valid_pairs else None,
        "total_spread_effect": _out(s_eff_tot, FOUR_DP) if valid_pairs else None,
        "total_price_change": _out(total_price, FOUR_DP) if valid_pairs else None,
        "primary_driver": driver,
        "interpretation": interp,
        "risk_coverage": _serialize_risk_coverage(risk_coverage),
        "attribution_basis": "matched_positions_start_exposure",
        "method_note": (
            "按债券、组合、成本中心、会计分类及币种匹配，固定期初市值与修正久期，逐券计算两期收益率变化。"
            "人民币国债基准按各期剩余期限插值；国债效应包含期限滚动，不能与 Carry/骑乘结果直接相加。"
            "10 年国债仅作参考；贡献为一阶估值估算，不含交易、利息、凸性或汇率损益。"
        ),
        "calculation_status": status,
        "attribution_coverage": coverage,
        "warnings": warnings,
        "items": items,
    }


def build_krd_attribution(
    *,
    report_date: str,
    start_date: str,
    end_date: str,
    bond_rows_end: list[dict[str, Any]],
    bond_rows_start: list[dict[str, Any]],
    treasury_shift_bp: float | None,
) -> dict[str, Any]:
    normalized_end = _rows_with_current_tenor_bucket(bond_rows_end)
    normalized_start = _rows_with_current_tenor_bucket(bond_rows_start)
    covered_end, risk_coverage = _partition_maturity_risk_rows(
        normalized_end,
        report_date=report_date,
    )
    covered_start, _ = _partition_maturity_risk_rows(
        normalized_start,
        report_date=start_date,
    )
    risk = summarize_portfolio_risk(covered_end)
    total_mv = _f(risk_coverage["total_market_value"])
    port_dur = _f(risk["portfolio_modified_duration"])
    port_dv01 = _f(risk["portfolio_dv01"])
    dist_end = build_krd_distribution(covered_end)
    by_bucket_start: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in covered_start:
        by_bucket_start[str(r.get("tenor_bucket") or "")].append(r)

    buckets_out: list[dict[str, Any]] = []
    total_dur_eff = ZERO
    shift_bp = _finite_decimal(treasury_shift_bp)
    duration_available = shift_bp is not None and not (
        risk_coverage["excluded_row_count"] and not risk_coverage["covered_row_count"]
    )
    calculation_status = (
        "unavailable" if not duration_available else
        "partial" if risk_coverage["excluded_row_count"] else "complete"
    )
    for b in dist_end:
        tenor = str(b["tenor_bucket"])
        mv = _f(b["market_value"])
        w = (mv / total_mv * HUNDRED) if total_mv > 0 else ZERO
        # Bucket metric is avg modified duration (not true KRD contribution).
        avg_md = _f(b.get("avg_modified_duration", b["krd"]))
        rows_s = by_bucket_start.get(tenor, [])
        rows_e = _rows_for_bucket(covered_end, tenor)
        ye = _weighted_ytm_decimal(rows_e)
        ys = _weighted_ytm_decimal(rows_s)
        ychg = ((ye - ys) * TEN_THOUSAND) if ye is not None and ys is not None else None
        contrib = -mv * avg_md * (shift_bp / TEN_THOUSAND) if duration_available and shift_bp is not None else None
        if contrib is not None:
            total_dur_eff += contrib
        buckets_out.append(
            {
                "tenor": tenor,
                "tenor_years": _tenor_bucket_mid_years(tenor),
                "market_value": mv,
                "weight": w,
                "bond_count": len(rows_e),
                "bucket_duration": avg_md,
                "avg_modified_duration": avg_md,
                "krd": avg_md,  # deprecated alias of avg_modified_duration
                "yield_change": ychg,
                "duration_contribution": contrib,
                "contribution_pct": ZERO,
            }
        )
    for b in buckets_out:
        b["contribution_pct"] = None if not duration_available else (
            abs(b["duration_contribution"]) / abs(total_dur_eff) * HUNDRED
            if total_dur_eff
            else ZERO
        )
    max_tenor = ""
    max_val = ZERO
    for b in buckets_out:
        if b["duration_contribution"] is not None and abs(b["duration_contribution"]) > abs(max_val):
            max_val = b["duration_contribution"]
            max_tenor = str(b["tenor"])
    serialized_buckets = [
        {
            **bucket,
            "market_value": _out(bucket["market_value"]),
            "weight": _out(bucket["weight"], FOUR_DP),
            "bucket_duration": _out(bucket["bucket_duration"]),
            "avg_modified_duration": _out(bucket["avg_modified_duration"], FOUR_DP),
            "krd": _out(bucket["krd"], FOUR_DP),
            "yield_change": _out(bucket["yield_change"]) if bucket["yield_change"] is not None else None,
            "duration_contribution": _out(bucket["duration_contribution"], FOUR_DP) if bucket["duration_contribution"] is not None else None,
            "contribution_pct": _out(bucket["contribution_pct"], FOUR_DP) if bucket["contribution_pct"] is not None else None,
        }
        for bucket in buckets_out
    ]
    curve_type = "parallel"
    interp = (
        "期限桶久期效应按期末市值、桶内平均修正久期与同一 10Y 国债收益率平移估算；"
        "各桶 Δyield 仅作诊断展示，不参与贡献计算，非逐关键期限 KRD。"
    )
    if shift_bp is None:
        curve_type = "unavailable"
        interp = "缺少可比的期初或期末 10Y 国债收益率，久期效应不可用；持仓风险覆盖率不代表曲线输入完整。"
    elif not duration_available:
        interp = "没有具备有效期限和久期的持仓，久期效应不可用。"
    return {
        "report_date": report_date,
        "start_date": start_date,
        "end_date": end_date,
        "total_market_value": _out(total_mv),
        "portfolio_duration": _out(port_dur, FOUR_DP),
        "portfolio_dv01": _out(port_dv01, FOUR_DP),
        "total_duration_effect": _out(total_dur_eff, FOUR_DP) if duration_available else None,
        "calculation_status": calculation_status,
        "curve_shift_type": curve_type,
        "curve_interpretation": interp,
        "risk_coverage": _serialize_risk_coverage(risk_coverage),
        "buckets": serialized_buckets,
        "max_contribution_tenor": max_tenor,
        "max_contribution_value": _out(max_val, FOUR_DP) if duration_available else None,
    }


def build_advanced_attribution_summary(
    *,
    report_date: str,
    carry_payload: dict[str, Any],
    spread_payload: dict[str, Any],
    krd_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "report_date": report_date,
        "portfolio_carry": carry_payload.get("portfolio_carry"),
        "portfolio_rolldown": carry_payload.get("portfolio_rolldown"),
        "static_return_annualized": carry_payload.get("portfolio_static_return"),
        "treasury_effect_total": spread_payload.get("total_treasury_effect"),
        "spread_effect_total": spread_payload.get("total_spread_effect"),
        "spread_driver": str(spread_payload.get("primary_driver") or "unknown"),
        "max_krd_tenor": str(krd_payload.get("max_contribution_tenor") or ""),
        "curve_shape_change": str(krd_payload.get("curve_shift_type") or ""),
        "key_insights": [
            "Carry / 骑乘与利差分解见高级归因各子图。",
            f"利差主导项归类为 {spread_payload.get('primary_driver') or 'unknown'}。",
        ],
    }
