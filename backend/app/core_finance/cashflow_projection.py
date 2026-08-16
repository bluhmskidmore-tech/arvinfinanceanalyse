from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

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
    """Duration-gap analysis output.

    Honest-caliber disclosure: weighted durations and the duration gap are built
    only from rows that carry a duration (the *duration-covered* balance). Balances
    that lack a duration are reported separately via ``*_excluded_balance`` /
    ``*_coverage_ratio`` and are never assigned the covered average duration. When
    the duration-covered asset balance is zero the duration-gap family
    (``asset_weighted_duration``, ``duration_gap``, ``modified_duration_gap``,
    ``equity_duration``, ``rate_sensitivity_1bp``) is ``None`` (unavailable) rather
    than a misleading value.
    """

    report_date: date
    asset_weighted_duration: Decimal | None
    liability_weighted_duration: Decimal
    duration_gap: Decimal | None
    modified_duration_gap: Decimal | None
    total_asset_market_value: Decimal
    total_liability_value: Decimal
    asset_duration_covered_balance: Decimal
    liability_duration_covered_balance: Decimal
    asset_excluded_balance: Decimal
    liability_excluded_balance: Decimal
    asset_duration_coverage_ratio: Decimal | None
    liability_duration_coverage_ratio: Decimal | None
    equity_duration: Decimal | None
    rate_sensitivity_1bp: Decimal | None
    monthly_buckets: list[MonthlyBucket]
    reinvestment_risk_12m: Decimal | None
    warnings: list[str]


def project_bond_cashflows(
    bond_rows: list[dict[str, Any]],
    report_date: date,
    horizon_months: int = 24,
    *,
    coupon_rate_unit: str = "percent",
) -> list[CashflowEvent]:
    """
    Project bond coupon and principal cashflows within the horizon.

    ``coupon_rate_unit`` 声明输入行 ``coupon_rate`` 的单位：
    - ``"percent"``（默认）：来自 `fact_formal_zqtz_balance_daily` 的百分数口径
      （1.82 = 1.82%），显式 ÷100。
    - ``"decimal"``：来自 `fact_formal_bond_analytics_daily` 的小数口径
      （engine 归一后 0.0182 = 1.82%，如 risk_tensor 流动性缺口路径）。
    """

    if coupon_rate_unit == "percent":
        coerce_rate = _coerce_rate_decimal
    elif coupon_rate_unit == "decimal":
        coerce_rate = _coerce_decimal_caliber_rate
    else:
        raise ValueError(f"Unsupported coupon_rate_unit={coupon_rate_unit!r}")

    horizon_end = _add_months(report_date, horizon_months)
    events: list[CashflowEvent] = []
    for row in bond_rows:
        maturity_date = _coerce_date(_get_value(row, "maturity_date"))
        if maturity_date is None or maturity_date <= report_date:
            continue

        face_value = _coerce_decimal(_get_value(row, "face_value", "face_value_amount", "face_value_native"))
        coupon_rate = coerce_rate(_get_value(row, "coupon_rate"))
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

    Buckets run from the report month through the month containing
    ``horizon_end`` (= report_date + horizon_months). Events are admitted up to
    ``horizon_end`` inclusive, so the bucket range must cover that final —
    possibly partial — calendar month; building exactly ``horizon_months``
    buckets used to drop events between the last built month-end and
    ``horizon_end`` silently.
    """

    month_start = date(report_date.year, report_date.month, 1)
    horizon_end = _add_months(report_date, horizon_months)
    month_count = (
        (horizon_end.year * 12 + horizon_end.month)
        - (month_start.year * 12 + month_start.month)
        + 1
    )
    aggregates: dict[str, dict[str, Decimal]] = {}
    ordered_months: list[str] = []
    for offset in range(month_count):
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

    Honest caliber (no implicit extrapolation):
    - Dollar-duration numerators are the direct sums over duration-covered rows,
      ``DD_A = Σ(D_i * balance_i)`` and ``DD_L = Σ(D_j * balance_j)``.
    - ``A_cov`` / ``L_cov`` are the duration-covered balances (denominators for the
      headline weighted durations). Balances lacking duration are excluded and
      disclosed via ``asset_excluded_balance`` / ``liability_excluded_balance`` and
      ``*_coverage_ratio``; they are never assigned the covered average duration.
    - ``duration_gap = D_A - (L_cov / A_cov) * D_L`` (leverage on the covered base,
      so ``duration_gap * A_cov == DD_A - DD_L``).
    - ``equity_duration = (DD_A - DD_L) / E`` with ``E = A_total - L_total``.
    - ``modified_duration_gap`` mirrors ``duration_gap`` (term-proxy / Macaulay
      basis, not divided by (1 + y)); treat it as a proxy pending confirmation of
      the modified-duration convention.

    Sign convention for ``rate_sensitivity_1bp``: projected change in equity value
    for a +1bp parallel rate move, ``-(DD_A - DD_L) * 0.0001``. With a positive
    equity dollar duration a rate rise produces a negative sensitivity.

    Availability: when the duration-covered asset balance is zero (no assets, or no
    asset carries duration) the duration-gap family is returned as ``None`` with a
    warning instead of a misleading ``-D_L`` value. ``reinvestment_risk_12m`` is
    ``None`` when total asset market value is zero.
    """

    warnings: list[str] = []

    total_asset_market_value = ZERO
    total_liability_value = ZERO
    asset_duration_numerator = ZERO
    liability_duration_numerator = ZERO
    asset_duration_covered_balance = ZERO
    liability_duration_covered_balance = ZERO

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
            asset_duration_covered_balance += market_value
        else:
            liability_duration_numerator += duration * market_value
            liability_duration_covered_balance += market_value

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
            asset_duration_covered_balance += principal
        else:
            liability_duration_numerator += duration * principal
            liability_duration_covered_balance += principal

    asset_excluded_balance = total_asset_market_value - asset_duration_covered_balance
    liability_excluded_balance = total_liability_value - liability_duration_covered_balance
    asset_duration_coverage_ratio: Decimal | None = (
        asset_duration_covered_balance / total_asset_market_value if total_asset_market_value > ZERO else None
    )
    liability_duration_coverage_ratio: Decimal | None = (
        liability_duration_covered_balance / total_liability_value if total_liability_value > ZERO else None
    )

    # Headline weighted durations divide the direct Σ(duration × balance) numerator
    # by the duration-covered balance only; excluded balances never inherit the
    # covered average duration.
    liability_weighted_duration = (
        liability_duration_numerator / liability_duration_covered_balance
        if liability_duration_covered_balance > ZERO
        else ZERO
    )

    if liability_duration_covered_balance > ZERO:
        _append_warning(
            warnings,
            "Liability duration uses a remaining-term proxy (years to maturity), not a cashflow-weighted duration.",
        )
    if asset_excluded_balance > ZERO:
        _append_warning(
            warnings,
            f"{asset_excluded_balance} of {total_asset_market_value} asset market value lacks duration "
            "information; the duration gap uses only the duration-covered balance and does not extrapolate "
            "the covered average duration onto the excluded balance.",
        )
    if liability_excluded_balance > ZERO:
        _append_warning(
            warnings,
            f"{liability_excluded_balance} of {total_liability_value} liability value lacks duration "
            "information; the duration gap uses only the duration-covered balance and does not extrapolate "
            "the covered average duration onto the excluded balance.",
        )
    if total_liability_value <= ZERO:
        _append_warning(warnings, "No liability rows were available; liability duration defaults to zero.")

    equity = total_asset_market_value - total_liability_value
    if asset_duration_covered_balance > ZERO:
        asset_weighted_duration: Decimal | None = asset_duration_numerator / asset_duration_covered_balance
        duration_gap: Decimal | None = asset_weighted_duration - (
            liability_duration_covered_balance / asset_duration_covered_balance
        ) * liability_weighted_duration
        modified_duration_gap: Decimal | None = duration_gap
        # Equity dollar-duration is the measured DD_A - DD_L (covered rows only), so
        # missing-duration balances are not extrapolated into the 1bp sensitivity.
        equity_dollar_duration = asset_duration_numerator - liability_duration_numerator
        if equity == ZERO:
            _append_warning(warnings, "Equity is zero; equity duration and 1bp sensitivity were set to zero.")
            equity_duration: Decimal | None = ZERO
            rate_sensitivity_1bp: Decimal | None = ZERO
        else:
            equity_duration = equity_dollar_duration / equity
            rate_sensitivity_1bp = -(equity_dollar_duration * ONE_BPS)
            if equity < ZERO:
                _append_warning(warnings, "Equity is negative; equity duration should be interpreted with caution.")
    else:
        # Asset denominator is zero (no assets, or no asset carries duration): the
        # duration-gap family is undefined. Return explicit unavailability instead of
        # a misleading -liability_duration value.
        asset_weighted_duration = None
        duration_gap = None
        modified_duration_gap = None
        equity_duration = None
        rate_sensitivity_1bp = None
        if total_asset_market_value <= ZERO:
            _append_warning(
                warnings,
                "Total asset market value is zero; duration gap, equity duration and 1bp sensitivity are unavailable.",
            )
        else:
            _append_warning(
                warnings,
                "No asset positions carry duration information; duration gap, equity duration and 1bp "
                "sensitivity are unavailable.",
            )

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

    reinvestment_risk_12m: Decimal | None = (
        maturing_asset_face_value_12m / total_asset_market_value if total_asset_market_value > ZERO else None
    )

    return DurationGapResult(
        report_date=report_date,
        asset_weighted_duration=asset_weighted_duration,
        liability_weighted_duration=liability_weighted_duration,
        duration_gap=duration_gap,
        modified_duration_gap=modified_duration_gap,
        total_asset_market_value=total_asset_market_value,
        total_liability_value=total_liability_value,
        asset_duration_covered_balance=asset_duration_covered_balance,
        liability_duration_covered_balance=liability_duration_covered_balance,
        asset_excluded_balance=asset_excluded_balance,
        liability_excluded_balance=liability_excluded_balance,
        asset_duration_coverage_ratio=asset_duration_coverage_ratio,
        liability_duration_coverage_ratio=liability_duration_coverage_ratio,
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
    funding_rate = _coerce_tyw_rate_decimal(_get_value(row, "funding_cost_rate"))
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
    if any(token in normalized for token in ("asset", "璧勪骇", "璧勴骇", "璧勘骇", "璧勷骇", "\u8d44\u4ea7", "\u8cc7\u7522")):
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
    # fact_formal_zqtz_balance_daily.coupon_rate 为百分数口径（1.82 = 1.82%），
    # 必须显式除以 100；>2 启发式会把 [0.2, 2) 灰区低票息当作小数 182% 计息。
    # 取证：docs/audits/2026-07-19-system-calculation-audit.md 取证 1。
    from backend.app.core_finance.rate_units import normalize_percent_rate_to_decimal

    normalized = normalize_percent_rate_to_decimal(value)
    if normalized is None:
        return ZERO
    return Decimal(str(normalized))


def _coerce_decimal_caliber_rate(value: Any) -> Decimal:
    # 小数口径来源（fact_formal_bond_analytics_daily，engine 已归一），
    # 仅做防御性处理。
    from backend.app.core_finance.rate_units import normalize_annual_rate_to_decimal

    normalized = normalize_annual_rate_to_decimal(value)
    if normalized is None:
        return ZERO
    return Decimal(str(normalized))


def _coerce_tyw_rate_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return ZERO
    from backend.app.core_finance.rate_units import pct_to_decimal

    return pct_to_decimal(value)


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
