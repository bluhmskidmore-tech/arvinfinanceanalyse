from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping

from backend.app.core_finance.bond_analytics.common import (
    build_curve_points,
    build_full_curve,
    estimate_duration,
    estimate_modified_duration,
    infer_curve_type,
    interpolate_rate,
)


ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(slots=True, frozen=True)
class PnlBridgeRow:
    report_date: date
    instrument_code: str
    portfolio_name: str
    cost_center: str
    accounting_basis: str
    beginning_dirty_mv: Decimal
    ending_dirty_mv: Decimal
    carry: Decimal
    roll_down: Decimal
    treasury_curve: Decimal
    credit_spread: Decimal
    fx_translation: Decimal
    realized_trading: Decimal
    unrealized_fv: Decimal
    manual_adjustment: Decimal
    explained_pnl: Decimal
    actual_pnl: Decimal
    residual: Decimal
    residual_ratio: Decimal
    quality_flag: str
    current_balance_found: bool
    prior_balance_found: bool
    balance_diagnostics: tuple[str, ...]


def build_pnl_bridge_rows(
    pnl_fi_rows: list[dict],
    balance_rows_current: list[dict],
    balance_rows_prior: list[dict],
    *,
    treasury_curve_current: dict[str, Decimal] | None = None,
    treasury_curve_prior: dict[str, Decimal] | None = None,
    cdb_curve_current: dict[str, Decimal] | None = None,
    cdb_curve_prior: dict[str, Decimal] | None = None,
) -> list[PnlBridgeRow]:
    current_exact, current_exact_without_basis, current_fallback = _index_balance_rows(balance_rows_current)
    prior_exact, prior_exact_without_basis, prior_fallback = _index_balance_rows(balance_rows_prior)

    rows: list[PnlBridgeRow] = []
    for raw_row in pnl_fi_rows:
        report_date = _coerce_date(raw_row["report_date"])
        instrument_code = str(raw_row.get("instrument_code") or "")
        portfolio_name = str(raw_row.get("portfolio_name") or "")
        cost_center = str(raw_row.get("cost_center") or "")
        currency_basis = str(raw_row.get("currency_basis") or "")

        current_balance = _resolve_balance_row(
            instrument_code=instrument_code,
            portfolio_name=portfolio_name,
            cost_center=cost_center,
            currency_basis=currency_basis,
            accounting_basis=str(raw_row.get("accounting_basis") or ""),
            exact=current_exact,
            exact_without_basis=current_exact_without_basis,
            fallback=current_fallback,
        )
        prior_balance = _resolve_balance_row(
            instrument_code=instrument_code,
            portfolio_name=portfolio_name,
            cost_center=cost_center,
            currency_basis=currency_basis,
            accounting_basis=str(raw_row.get("accounting_basis") or ""),
            exact=prior_exact,
            exact_without_basis=prior_exact_without_basis,
            fallback=prior_fallback,
        )

        curve_type = infer_curve_type(
            raw_row.get("instrument_name"),
            current_balance.get("bond_type") if current_balance else "",
            current_balance.get("asset_class") if current_balance else "",
            current_balance.get("instrument_name") if current_balance else "",
        )
        current_curve = cdb_curve_current if curve_type == "cdb" else treasury_curve_current
        prior_curve = cdb_curve_prior if curve_type == "cdb" else treasury_curve_prior

        carry = _coerce_decimal(raw_row.get("interest_income_514", ZERO))
        roll_down = _calculate_roll_down(
            report_date=report_date,
            current_balance=current_balance,
            prior_balance=prior_balance,
            curve=current_curve,
        )
        treasury_curve = _calculate_curve_shift(
            report_date=report_date,
            current_balance=current_balance,
            current_curve=current_curve,
            prior_curve=prior_curve,
        )
        credit_spread = ZERO
        fx_translation = ZERO
        realized_trading = _coerce_decimal(raw_row.get("capital_gain_517", ZERO))
        unrealized_fv = _coerce_decimal(raw_row.get("fair_value_change_516", ZERO))
        manual_adjustment = _coerce_decimal(raw_row.get("manual_adjustment", ZERO))
        explained_pnl = (
            carry
            + roll_down
            + treasury_curve
            + credit_spread
            + fx_translation
            + realized_trading
            + unrealized_fv
            + manual_adjustment
        )
        actual_pnl = _coerce_decimal(raw_row.get("total_pnl", ZERO))
        residual = actual_pnl - explained_pnl
        residual_ratio = ZERO if actual_pnl == ZERO else residual / actual_pnl

        rows.append(
            PnlBridgeRow(
                report_date=report_date,
                instrument_code=instrument_code,
                portfolio_name=portfolio_name,
                cost_center=cost_center,
                accounting_basis=str(raw_row.get("accounting_basis") or ""),
                beginning_dirty_mv=_dirty_market_value(prior_balance),
                ending_dirty_mv=_dirty_market_value(current_balance),
                carry=carry,
                roll_down=roll_down,
                treasury_curve=treasury_curve,
                credit_spread=credit_spread,
                fx_translation=fx_translation,
                realized_trading=realized_trading,
                unrealized_fv=unrealized_fv,
                manual_adjustment=manual_adjustment,
                explained_pnl=explained_pnl,
                actual_pnl=actual_pnl,
                residual=residual,
                residual_ratio=residual_ratio,
                quality_flag=_quality_flag(residual_ratio),
                current_balance_found=current_balance is not None,
                prior_balance_found=prior_balance is not None,
                balance_diagnostics=_build_balance_diagnostics(
                    current_balance=current_balance,
                    prior_balance=prior_balance,
                ),
            )
        )
    return rows


def _calculate_roll_down(
    *,
    report_date: date,
    current_balance: Mapping[str, object] | None,
    prior_balance: Mapping[str, object] | None,
    curve: dict[str, Decimal] | None,
) -> Decimal:
    if current_balance is None or prior_balance is None or not curve:
        return ZERO
    years_to_maturity = _years_to_maturity(report_date=report_date, row=current_balance)
    if years_to_maturity <= 0:
        return ZERO
    current_curve_rate = _curve_rate(curve, years_to_maturity)
    period_days = _period_days(current_balance=current_balance, prior_balance=prior_balance)
    if period_days <= 0:
        return ZERO
    rolled_years = max(0.0, years_to_maturity - (period_days / 365))
    rolled_curve_rate = _curve_rate(curve, rolled_years)
    modified_duration = _modified_duration(report_date=report_date, row=current_balance)
    market_value = _curve_market_value(current_balance)
    if modified_duration == ZERO or market_value == ZERO:
        return ZERO
    rate_delta = (current_curve_rate - rolled_curve_rate) / HUNDRED
    return rate_delta * modified_duration * market_value


def _calculate_curve_shift(
    *,
    report_date: date,
    current_balance: Mapping[str, object] | None,
    current_curve: dict[str, Decimal] | None,
    prior_curve: dict[str, Decimal] | None,
) -> Decimal:
    if current_balance is None or not current_curve or not prior_curve:
        return ZERO
    years_to_maturity = _years_to_maturity(report_date=report_date, row=current_balance)
    if years_to_maturity <= 0:
        return ZERO
    current_curve_rate = _curve_rate(current_curve, years_to_maturity)
    prior_curve_rate = _curve_rate(prior_curve, years_to_maturity)
    modified_duration = _modified_duration(report_date=report_date, row=current_balance)
    market_value = _curve_market_value(current_balance)
    if modified_duration == ZERO or market_value == ZERO:
        return ZERO
    rate_delta = (current_curve_rate - prior_curve_rate) / HUNDRED
    return -(rate_delta * modified_duration * market_value)


def _curve_rate(curve: dict[str, Decimal], target_years: float) -> Decimal:
    if not curve:
        return ZERO
    points = build_curve_points(build_full_curve(curve))
    return interpolate_rate(points, target_years)


def _years_to_maturity(*, report_date: date, row: Mapping[str, object]) -> float:
    maturity_date = row.get("maturity_date")
    if maturity_date in (None, ""):
        return 0.0
    maturity = _coerce_date(maturity_date)
    remaining_days = (maturity - report_date).days
    if remaining_days <= 0:
        return 0.0
    return remaining_days / 365


def _period_days(
    *,
    current_balance: Mapping[str, object],
    prior_balance: Mapping[str, object],
) -> int:
    current_date = _coerce_date(current_balance.get("report_date"))
    prior_date = _coerce_date(prior_balance.get("report_date"))
    return max((current_date - prior_date).days, 0)


def _modified_duration(*, report_date: date, row: Mapping[str, object]) -> Decimal:
    maturity_date_value = row.get("maturity_date")
    if maturity_date_value in (None, ""):
        return ZERO
    maturity_date = _coerce_date(maturity_date_value)
    coupon_rate = _coerce_decimal(row.get("coupon_rate", ZERO))
    ytm_value = _coerce_decimal(row.get("ytm_value", ZERO))
    macaulay_duration = estimate_duration(
        maturity_date=maturity_date,
        report_date=report_date,
        coupon_rate=coupon_rate,
        ytm=ytm_value,
        bond_code=str(row.get("instrument_code") or ""),
    )
    return estimate_modified_duration(macaulay_duration, ytm_value)


def _curve_market_value(row: Mapping[str, object]) -> Decimal:
    return _coerce_decimal(
        row.get("market_value_amount", row.get("market_value", row.get("market_value_native", ZERO)))
    )


def _build_balance_diagnostics(
    *,
    current_balance: Mapping[str, object] | None,
    prior_balance: Mapping[str, object] | None,
) -> tuple[str, ...]:
    diagnostics: list[str] = []
    if current_balance is None:
        diagnostics.append("Missing current balance row; ending_dirty_mv defaults to 0.")
    if prior_balance is None:
        diagnostics.append("Missing prior balance row; beginning_dirty_mv defaults to 0.")
    return tuple(diagnostics)


def _index_balance_rows(
    rows: list[dict],
) -> tuple[
    dict[tuple[str, str, str, str, str], dict],
    dict[tuple[str, str, str, str], dict],
    dict[tuple[str, str, str, str], dict],
]:
    exact: dict[tuple[str, str, str, str, str], dict] = {}
    exact_without_basis: dict[tuple[str, str, str, str], dict] = {}
    fallback: dict[tuple[str, str, str, str], dict] = {}
    for row in rows:
        instrument_code = str(row.get("instrument_code") or "")
        portfolio_name = str(row.get("portfolio_name") or "")
        cost_center = str(row.get("cost_center") or "")
        currency_basis = str(row.get("currency_basis") or "")
        accounting_basis = str(row.get("accounting_basis") or "")
        exact.setdefault(
            (instrument_code, portfolio_name, cost_center, currency_basis, accounting_basis),
            row,
        )
        if not accounting_basis:
            exact_without_basis.setdefault(
                (instrument_code, portfolio_name, cost_center, currency_basis),
                row,
            )
        fallback.setdefault((instrument_code, portfolio_name, cost_center, accounting_basis), row)
    return exact, exact_without_basis, fallback


def _resolve_balance_row(
    *,
    instrument_code: str,
    portfolio_name: str,
    cost_center: str,
    currency_basis: str,
    accounting_basis: str,
    exact: dict[tuple[str, str, str, str, str], dict],
    exact_without_basis: dict[tuple[str, str, str, str], dict],
    fallback: dict[tuple[str, str, str, str], dict],
) -> dict | None:
    if currency_basis:
        exact_match = exact.get(
            (instrument_code, portfolio_name, cost_center, currency_basis, accounting_basis)
        )
        if exact_match is not None:
            return exact_match
        exact_match_without_basis = exact_without_basis.get(
            (instrument_code, portfolio_name, cost_center, currency_basis)
        )
        if exact_match_without_basis is not None:
            return exact_match_without_basis
    return fallback.get((instrument_code, portfolio_name, cost_center, accounting_basis))


def _dirty_market_value(row: Mapping[str, object] | None) -> Decimal:
    if row is None:
        return ZERO
    market_value = _coerce_decimal(
        row.get("market_value_amount", row.get("market_value", row.get("market_value_native", ZERO)))
    )
    accrued_interest = _coerce_decimal(
        row.get(
            "accrued_interest_amount",
            row.get("accrued_interest", row.get("accrued_interest_native", ZERO)),
        )
    )
    return market_value + accrued_interest


def _quality_flag(residual_ratio: Decimal) -> str:
    abs_ratio = abs(residual_ratio)
    if abs_ratio < Decimal("0.05"):
        return "ok"
    if abs_ratio < Decimal("0.10"):
        return "warning"
    return "error"


def _coerce_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _coerce_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return ZERO
    return Decimal(str(value))


__all__ = ["PnlBridgeRow", "build_pnl_bridge_rows"]
