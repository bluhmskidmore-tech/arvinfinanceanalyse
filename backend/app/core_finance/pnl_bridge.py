from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Mapping


ZERO = Decimal("0")


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

        carry = _coerce_decimal(raw_row.get("interest_income_514", ZERO))
        roll_down = ZERO
        treasury_curve = ZERO
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
