from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from backend.app.core_finance.rate_units import normalize_annual_rate_to_decimal

ZERO = Decimal("0")
ONE_BPS = Decimal("0.0001")
DAYS_IN_YEAR = Decimal("365")
TYWL_DEMAND_PRODUCTS = frozenset({"同业存放", "存放同业"})


@dataclass(slots=True, frozen=True)
class CashflowEvent:
    """Single projected cashflow event."""

    event_date: date
    event_type: str
    instrument_code: str
    instrument_name: str
    side: str
    amount: Decimal
    currency_code: str


@dataclass(slots=True, frozen=True)
class MonthlyBucket:
    """Monthly cashflow aggregation bucket."""

    year_month: str
    asset_inflow: Decimal
    liability_outflow: Decimal
    net_cashflow: Decimal
    cumulative_net: Decimal


@dataclass(slots=True, frozen=True)
class DurationGapResult:
    """Duration-gap analysis output."""

    report_date: date
    asset_weighted_duration: Decimal
    liability_weighted_duration: Decimal
    duration_gap: Decimal
    modified_duration_gap: Decimal
    total_asset_market_value: Decimal
    total_liability_value: Decimal
    equity_duration: Decimal
    rate_sensitivity_1bp: Decimal
    monthly_buckets: list[MonthlyBucket]
    reinvestment_risk_12m: Decimal
    warnings: list[str]


def project_bond_cashflows(
    bond_rows: list[dict[str, Any]],
    report_date: date,
    horizon_months: int = 24,
) -> list[CashflowEvent]:
    """
    Project bond coupon and principal cashflows within the horizon.
    """

    horizon_end = _add_months(report_date, horizon_months)
    events: list[CashflowEvent] = []
    for row in bond_rows:
        maturity_date = _coerce_date(_get_value(row, "maturity_date"))
        if maturity_date is None or maturity_date <= report_date:
            continue

        face_value = _coerce_decimal(_get_value(row, "face_value", "face_value_amount", "face_value_native"))
        coupon_rate = _coerce_rate_decimal(_get_value(row, "coupon_rate"))
        interest_mode = _get_text(row, "interest_mode")
        interval_months = _coupon_interval_months(interest_mode)

        if _is_bullet_repayment(interest_mode):
            if maturity_date <= horizon_end and face_value > ZERO and coupon_rate > ZERO:
                events.append(
                    CashflowEvent(
                        event_date=maturity_date,
                        event_type="coupon",
                        instrument_code=_get_text(row, "instrument_code"),
                        instrument_name=_get_text(row, "instrument_name"),
                        side="asset",
                        amount=_bullet_coupon_amount(face_value, coupon_rate, row, maturity_date),
                        currency_code=_get_text(row, "currency_code", default="CNY"),
                    )
                )
        else:
            for coupon_date in _coupon_dates_between(
                report_date=report_date,
                horizon_end=horizon_end,
                maturity_date=maturity_date,
                interval_months=interval_months,
            ):
                if face_value <= ZERO or coupon_rate <= ZERO:
                    continue
                events.append(
                    CashflowEvent(
                        event_date=coupon_date,
                        event_type="coupon",
                        instrument_code=_get_text(row, "instrument_code"),
                        instrument_name=_get_text(row, "instrument_name"),
                        side="asset",
                        amount=_coupon_amount(face_value, coupon_rate, interval_months),
                        currency_code=_get_text(row, "currency_code", default="CNY"),
                    )
                )

        if maturity_date <= horizon_end and face_value > ZERO:
            events.append(
                CashflowEvent(
                    event_date=maturity_date,
                    event_type="principal",
                    instrument_code=_get_text(row, "instrument_code"),
                    instrument_name=_get_text(row, "instrument_name"),
                    side="asset",
                    amount=face_value,
                    currency_code=_get_text(row, "currency_code", default="CNY"),
                )
            )

    return sorted(events, key=lambda event: (event.event_date, event.event_type, event.instrument_code))


def project_liability_cashflows(
    tyw_rows: list[dict[str, Any]],
    report_date: date,
    horizon_months: int = 24,
) -> list[CashflowEvent]:
    """
    Project liability maturity and funding-cost cashflows within the horizon.
    """

    horizon_end = _add_months(report_date, horizon_months)
    events: list[CashflowEvent] = []
    for row in tyw_rows:
        if not _is_liability_row(row):
            continue
        events.extend(_project_tyw_row_cashflows(row, report_date, horizon_end))
    return sorted(events, key=lambda event: (event.event_date, event.event_type, event.instrument_code))


def project_zqtz_cashflows(
    zqtz_rows: list[dict[str, Any]],
    report_date: date,
    horizon_months: int = 24,
) -> list[CashflowEvent]:
    """Project bond-like asset and issuance-liability cashflows within the horizon."""

    horizon_end = _add_months(report_date, horizon_months)
    events: list[CashflowEvent] = []
    for row in zqtz_rows:
        maturity_date = _coerce_date(_get_value(row, "maturity_date"))
        if maturity_date is None or maturity_date <= report_date:
            continue

        side = _row_scope(row)
        if side not in {"asset", "liability"}:
            continue
        sign = Decimal("1") if side == "asset" else Decimal("-1")

        principal = _coerce_decimal(_get_value(row, "face_value", "face_value_amount", "face_value_native"))
        coupon_rate = _coerce_rate_decimal(_get_value(row, "coupon_rate"))
        interest_mode = _get_text(row, "interest_mode")
        interval_months = _coupon_interval_months(interest_mode)

        if _is_bullet_repayment(interest_mode):
            if maturity_date <= horizon_end and principal > ZERO and coupon_rate > ZERO:
                events.append(
                    CashflowEvent(
                        event_date=maturity_date,
                        event_type="coupon",
                        instrument_code=_get_text(row, "instrument_code"),
                        instrument_name=_get_text(row, "instrument_name"),
                        side=side,
                        amount=sign * _bullet_coupon_amount(principal, coupon_rate, row, maturity_date),
                        currency_code=_get_text(row, "currency_code", default="CNY"),
                    )
                )
        else:
            for coupon_date in _coupon_dates_between(
                report_date=report_date,
                horizon_end=horizon_end,
                maturity_date=maturity_date,
                interval_months=interval_months,
            ):
                if principal <= ZERO or coupon_rate <= ZERO:
                    continue
                events.append(
                    CashflowEvent(
                        event_date=coupon_date,
                        event_type="coupon",
                        instrument_code=_get_text(row, "instrument_code"),
                        instrument_name=_get_text(row, "instrument_name"),
                        side=side,
                        amount=sign * _coupon_amount(principal, coupon_rate, interval_months),
                        currency_code=_get_text(row, "currency_code", default="CNY"),
                    )
                )

        if maturity_date <= horizon_end and principal > ZERO:
            events.append(
                CashflowEvent(
                    event_date=maturity_date,
                    event_type="principal",
                    instrument_code=_get_text(row, "instrument_code"),
                    instrument_name=_get_text(row, "instrument_name"),
                    side=side,
                    amount=sign * principal,
                    currency_code=_get_text(row, "currency_code", default="CNY"),
                )
            )

    return sorted(events, key=lambda event: (event.event_date, event.event_type, event.instrument_code))


def project_tyw_cashflows(
    tyw_rows: list[dict[str, Any]],
    report_date: date,
    horizon_months: int = 24,
) -> list[CashflowEvent]:
    """Project interbank asset/liability cashflows within the horizon."""

    horizon_end = _add_months(report_date, horizon_months)
    events: list[CashflowEvent] = []
    for row in tyw_rows:
        events.extend(_project_tyw_row_cashflows(row, report_date, horizon_end))
    return sorted(events, key=lambda event: (event.event_date, event.event_type, event.instrument_code))


def build_monthly_buckets(
    cashflows: list[CashflowEvent],
    report_date: date,
    horizon_months: int = 24,
) -> list[MonthlyBucket]:
    """
    Aggregate cashflows by month and compute cumulative net cashflow.
    """

    month_start = date(report_date.year, report_date.month, 1)
    horizon_end = _add_months(report_date, horizon_months)
    aggregates: dict[str, dict[str, Decimal]] = {}
    ordered_months: list[str] = []
    for offset in range(horizon_months):
        bucket_date = _add_months(month_start, offset)
        year_month = bucket_date.strftime("%Y-%m")
        ordered_months.append(year_month)
        aggregates[year_month] = {
            "asset_inflow": ZERO,
            "liability_outflow": ZERO,
        }

    for event in cashflows:
        if event.event_date <= report_date or event.event_date > horizon_end:
            continue
        year_month = event.event_date.strftime("%Y-%m")
        if year_month not in aggregates:
            continue
        if event.side == "asset" and event.amount > ZERO:
            aggregates[year_month]["asset_inflow"] += event.amount
        if event.side == "liability" and event.amount < ZERO:
            aggregates[year_month]["liability_outflow"] += abs(event.amount)

    buckets: list[MonthlyBucket] = []
    cumulative_net = ZERO
    for year_month in ordered_months:
        asset_inflow = aggregates[year_month]["asset_inflow"]
        liability_outflow = aggregates[year_month]["liability_outflow"]
        net_cashflow = asset_inflow - liability_outflow
        cumulative_net += net_cashflow
        buckets.append(
            MonthlyBucket(
                year_month=year_month,
                asset_inflow=asset_inflow,
                liability_outflow=liability_outflow,
                net_cashflow=net_cashflow,
                cumulative_net=cumulative_net,
            )
        )
    return buckets


def compute_duration_gap(
    zqtz_rows: list[dict[str, Any]],
    tyw_rows: list[dict[str, Any]],
    report_date: date,
    horizon_months: int = 24,
) -> DurationGapResult:
    """
    Compute full-scope term-proxy duration gap, projected monthly cashflows,
    and 12-month reinvestment risk from formal balance facts.
    """

    warnings: list[str] = []

    total_asset_market_value = ZERO
    total_liability_value = ZERO
    asset_duration_numerator = ZERO
    liability_duration_numerator = ZERO
    asset_duration_weight = ZERO
    liability_duration_weight = ZERO

    for row in zqtz_rows:
        scope = _row_scope(row)
        market_value = _coerce_decimal(_get_value(row, "market_value", "market_value_amount", "market_value_native"))
        if market_value <= ZERO:
            continue
        if scope == "asset":
            total_asset_market_value += market_value
        elif scope == "liability":
            total_liability_value += market_value
        else:
            continue
        duration = _coerce_asset_duration(row, report_date) if scope == "asset" else _coerce_years_to_maturity(row, report_date)
        if duration is None:
            _append_warning(
                warnings,
                f"{scope.title()} {(_get_text(row, 'instrument_code') or 'unknown')} missing duration information and was excluded from weighted duration.",
            )
            continue
        if scope == "asset":
            asset_duration_numerator += duration * market_value
            asset_duration_weight += market_value
        else:
            liability_duration_numerator += duration * market_value
            liability_duration_weight += market_value

    for row in tyw_rows:
        scope = _row_scope(row)
        principal = _coerce_decimal(_get_value(row, "principal_amount", "principal_native"))
        if principal <= ZERO:
            continue
        if scope == "asset":
            total_asset_market_value += principal
        elif scope == "liability":
            total_liability_value += principal
        else:
            continue
        duration = _coerce_tyw_years_to_maturity(row, report_date)
        if duration is None:
            _append_warning(
                warnings,
                f"{scope.title()} {(_get_text(row, 'position_id') or 'unknown')} missing maturity information and was excluded from weighted duration.",
            )
            continue
        if scope == "asset":
            asset_duration_numerator += duration * principal
            asset_duration_weight += principal
        else:
            liability_duration_numerator += duration * principal
            liability_duration_weight += principal

    asset_weighted_duration = asset_duration_numerator / asset_duration_weight if asset_duration_weight > ZERO else ZERO
    liability_weighted_duration = (
        liability_duration_numerator / liability_duration_weight if liability_duration_weight > ZERO else ZERO
    )
    duration_gap = asset_weighted_duration - liability_weighted_duration
    modified_duration_gap = duration_gap

    if total_asset_market_value <= ZERO:
        _append_warning(warnings, "Total asset market value is zero; duration gap metrics were computed as zero.")
    if total_liability_value <= ZERO:
        _append_warning(warnings, "No liability rows were available; liability duration defaults to zero.")

    equity = total_asset_market_value - total_liability_value
    if equity == ZERO:
        _append_warning(warnings, "Equity is zero; equity duration and 1bp sensitivity were set to zero.")
        equity_duration = ZERO
        rate_sensitivity_1bp = ZERO
    else:
        equity_duration = duration_gap * (total_asset_market_value / equity)
        rate_sensitivity_1bp = equity_duration * equity * ONE_BPS
        if equity < ZERO:
            _append_warning(warnings, "Equity is negative; equity duration should be interpreted with caution.")

    projected_cashflows = [
        *project_zqtz_cashflows(zqtz_rows, report_date, horizon_months=horizon_months),
        *project_tyw_cashflows(tyw_rows, report_date, horizon_months=horizon_months),
    ]
    monthly_buckets = build_monthly_buckets(projected_cashflows, report_date, horizon_months=horizon_months)

    reinvestment_horizon_end = _add_months(report_date, 12)
    maturing_asset_face_value_12m = ZERO
    for row in zqtz_rows:
        if _row_scope(row) != "asset":
            continue
        maturity_date = _coerce_date(_get_value(row, "maturity_date"))
        if maturity_date is None or maturity_date <= report_date or maturity_date > reinvestment_horizon_end:
            continue
        maturing_asset_face_value_12m += _coerce_decimal(
            _get_value(row, "face_value", "face_value_amount", "face_value_native")
        )
    for row in tyw_rows:
        if _row_scope(row) != "asset":
            continue
        maturity_date = _effective_tyw_maturity_date(row, report_date)
        if maturity_date is None or maturity_date <= report_date or maturity_date > reinvestment_horizon_end:
            continue
        maturing_asset_face_value_12m += _coerce_decimal(_get_value(row, "principal_amount", "principal_native"))

    reinvestment_risk_12m = maturing_asset_face_value_12m / total_asset_market_value if total_asset_market_value > ZERO else ZERO

    return DurationGapResult(
        report_date=report_date,
        asset_weighted_duration=asset_weighted_duration,
        liability_weighted_duration=liability_weighted_duration,
        duration_gap=duration_gap,
        modified_duration_gap=modified_duration_gap,
        total_asset_market_value=total_asset_market_value,
        total_liability_value=total_liability_value,
        equity_duration=equity_duration,
        rate_sensitivity_1bp=rate_sensitivity_1bp,
        monthly_buckets=monthly_buckets,
        reinvestment_risk_12m=reinvestment_risk_12m,
        warnings=warnings,
    )


def _project_tyw_row_cashflows(row: dict[str, Any], report_date: date, horizon_end: date) -> list[CashflowEvent]:
    scope = _row_scope(row)
    if scope not in {"asset", "liability"}:
        return []

    maturity_date = _effective_tyw_maturity_date(row, report_date)
    if maturity_date is None or maturity_date <= report_date or maturity_date > horizon_end:
        return []

    principal = _coerce_decimal(_get_value(row, "principal_amount", "principal_native"))
    if principal <= ZERO:
        return []

    code = _get_text(row, "position_id", default=_get_text(row, "instrument_code"))
    name = _get_text(row, "counterparty_name", default=_get_text(row, "instrument_name"))
    sign = Decimal("1") if scope == "asset" else Decimal("-1")
    funding_rate = _coerce_rate_decimal(_get_value(row, "funding_cost_rate"))
    days = max(0, (maturity_date - report_date).days)

    events: list[CashflowEvent] = []
    if funding_rate > ZERO and days > 0:
        events.append(
            CashflowEvent(
                event_date=maturity_date,
                event_type="funding_income" if scope == "asset" else "funding_cost",
                instrument_code=code,
                instrument_name=name,
                side=scope,
                amount=sign * principal * funding_rate * Decimal(days) / DAYS_IN_YEAR,
                currency_code=_get_text(row, "currency_code", default="CNY"),
            )
        )

    events.append(
        CashflowEvent(
            event_date=maturity_date,
            event_type="maturity",
            instrument_code=code,
            instrument_name=name,
            side=scope,
            amount=sign * principal,
            currency_code=_get_text(row, "currency_code", default="CNY"),
        )
    )
    return events


def _append_warning(warnings: list[str], message: str) -> None:
    if message and message not in warnings:
        warnings.append(message)


def _coupon_interval_months(interest_mode: str) -> int:
    from backend.app.core_finance.interest_mode import coupon_interval_months

    return coupon_interval_months(interest_mode)


def _is_bullet_repayment(interest_mode: str) -> bool:
    from backend.app.core_finance.interest_mode import is_bullet_repayment

    return is_bullet_repayment(interest_mode)


def _coupon_amount(face_value: Decimal, coupon_rate: Decimal, interval_months: int) -> Decimal:
    if interval_months <= 0:
        return ZERO
    periods_per_year = Decimal(12 // interval_months)
    return face_value * coupon_rate / periods_per_year


def _bullet_coupon_amount(
    face_value: Decimal,
    coupon_rate: Decimal,
    row: dict[str, Any],
    maturity_date: date,
) -> Decimal:
    value_date = _coerce_date(_get_value(row, "value_date", "interest_start_date", "start_date"))
    if value_date is None or value_date >= maturity_date:
        return face_value * coupon_rate
    years = Decimal((maturity_date - value_date).days) / DAYS_IN_YEAR
    return face_value * coupon_rate * years


def _coupon_dates_between(
    *,
    report_date: date,
    horizon_end: date,
    maturity_date: date,
    interval_months: int,
) -> list[date]:
    dates: list[date] = []
    current = maturity_date
    while current > horizon_end:
        current = _add_months(current, -interval_months)
    while current > report_date:
        dates.append(current)
        current = _add_months(current, -interval_months)
    return sorted(dates)


def _coerce_years_to_maturity(row: dict[str, Any], report_date: date) -> Decimal | None:
    explicit_value = _coerce_optional_decimal(_get_value(row, "years_to_maturity"))
    if explicit_value is not None and explicit_value >= ZERO:
        return explicit_value
    maturity_date = _coerce_date(_get_value(row, "maturity_date"))
    if maturity_date is None or maturity_date <= report_date:
        return None
    return Decimal((maturity_date - report_date).days) / DAYS_IN_YEAR


def _coerce_tyw_years_to_maturity(row: dict[str, Any], report_date: date) -> Decimal | None:
    explicit_value = _coerce_optional_decimal(_get_value(row, "years_to_maturity"))
    if explicit_value is not None and explicit_value >= ZERO:
        return explicit_value
    maturity_date = _effective_tyw_maturity_date(row, report_date)
    if maturity_date is None or maturity_date <= report_date:
        return None
    return Decimal((maturity_date - report_date).days) / DAYS_IN_YEAR


def _coerce_asset_duration(row: dict[str, Any], report_date: date) -> Decimal | None:
    macaulay_duration = _coerce_optional_decimal(_get_value(row, "macaulay_duration"))
    if macaulay_duration is not None and macaulay_duration >= ZERO:
        return macaulay_duration
    return _coerce_years_to_maturity(row, report_date)


def _effective_tyw_maturity_date(row: dict[str, Any], report_date: date) -> date | None:
    maturity_date = _coerce_date(_get_value(row, "maturity_date"))
    if maturity_date is not None:
        return maturity_date
    product_type = _get_text(row, "product_type").strip()
    if product_type in TYWL_DEMAND_PRODUCTS:
        return _add_months(report_date, 1)
    return None


def _row_scope(row: dict[str, Any]) -> str:
    position_scope = _get_text(row, "position_scope", "position_side")
    if not position_scope:
        return "asset"
    normalized = position_scope.lower()
    if any(token in normalized for token in ("asset", "璧勴骇", "璧勘骇", "璧勷骇", "\u8d44\u4ea7", "\u8cc7\u7522")):
        return "asset"
    if any(token in normalized for token in ("liab", "liability", "璐熷€?", "\u8d1f\u503a", "\u8ca0\u50b5")):
        return "liability"
    return normalized


def _is_liability_row(row: dict[str, Any]) -> bool:
    return _row_scope(row) == "liability"


def _add_months(value: date, months: int) -> date:
    month_index = (value.year * 12 + (value.month - 1)) + months
    year = month_index // 12
    month = (month_index % 12) + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _coerce_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _coerce_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _coerce_rate_decimal(value: Any) -> Decimal:
    normalized = normalize_annual_rate_to_decimal(value)
    if normalized is None:
        return ZERO
    return Decimal(str(normalized))


def _coerce_optional_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return _coerce_decimal(value)


def _get_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _get_text(row: dict[str, Any], *keys: str, default: str = "") -> str:
    value = _get_value(row, *keys)
    if value in (None, ""):
        return default
    return str(value)
