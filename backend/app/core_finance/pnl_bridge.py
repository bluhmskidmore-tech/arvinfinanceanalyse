from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from backend.app.core_finance.accounting_basis_constants import ACCOUNTING_BASIS_FVTPL
from backend.app.core_finance.bond_analytics.common import (
    build_curve_points,
    build_full_curve,
    classify_asset_class,
    estimate_duration,
    estimate_modified_duration,
    infer_curve_type,
)
from backend.app.core_finance.curve_engine.curve_types import (
    CurvePoint,
    FittedCurve,
    InterpolationMethod,
)
from backend.app.core_finance.curve_engine.interpolation import (
    build_cubic_spline as _build_cubic_spline,
)
from backend.app.core_finance.curve_engine.interpolation import (
    interpolate as _interpolate_fitted_curve,
)

ZERO = Decimal("0")
HUNDRED = Decimal("100")
AMOUNT_SCALE = Decimal("0.00000001")


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
    residual_ratio: Decimal | None
    quality_flag: str
    current_balance_found: bool
    prior_balance_found: bool
    balance_diagnostics: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class _ResolvedBalanceRow:
    row: dict | None
    diagnostic: str | None = None
    match_level: str = "missing"


_CurveCacheKey = tuple[tuple[str, Decimal], ...]


class _CurveRateLookup:
    """Per-build cache of fitted curve interpolation inputs.

    Mirrors the ``_CurveRateLookup`` pattern in ``bond_analytics.read_models``: the
    ``build_full_curve`` + ``build_curve_points`` + spline-fit pipeline is executed once
    per distinct curve, then reused for every rate lookup within one bridge build.
    The fitted-curve construction is step-for-step identical to
    ``interpolate_rate(build_curve_points(build_full_curve(curve)), target_years)``.
    """

    def __init__(self) -> None:
        self._fitted_curve_cache: dict[_CurveCacheKey, FittedCurve] = {}
        self._curve_object_keys: dict[int, _CurveCacheKey] = {}

    def _key(self, curve: dict[str, Decimal]) -> _CurveCacheKey:
        object_id = id(curve)
        cached = self._curve_object_keys.get(object_id)
        if cached is None:
            cached = tuple(
                sorted((str(tenor), _coerce_decimal(rate)) for tenor, rate in curve.items())
            )
            self._curve_object_keys[object_id] = cached
        return cached

    def rate(self, curve: dict[str, Decimal], target_years: float) -> Decimal:
        key = self._key(curve)
        fitted = self._fitted_curve_cache.get(key)
        if fitted is None:
            points = tuple(
                CurvePoint(years=years, rate=rate)
                for years, rate in build_curve_points(build_full_curve(curve))
            )
            if len(points) >= 3:
                fitted = _build_cubic_spline(list(points))
            else:
                fitted = FittedCurve(method=InterpolationMethod.LINEAR, points=points)
            self._fitted_curve_cache[key] = fitted
        return _interpolate_fitted_curve(fitted, target_years)


def build_pnl_bridge_rows(
    pnl_fi_rows: list[dict],
    balance_rows_current: list[dict],
    balance_rows_prior: list[dict],
    *,
    treasury_curve_current: dict[str, Decimal] | None = None,
    treasury_curve_prior: dict[str, Decimal] | None = None,
    cdb_curve_current: dict[str, Decimal] | None = None,
    cdb_curve_prior: dict[str, Decimal] | None = None,
    aaa_credit_curve_current: dict[str, Decimal] | None = None,
    aaa_credit_curve_prior: dict[str, Decimal] | None = None,
    fx_rates_current: dict[str, Decimal] | None = None,
    fx_rates_prior: dict[str, Decimal] | None = None,
) -> list[PnlBridgeRow]:
    current_exact, current_exact_without_basis, current_fallback = _index_balance_rows(balance_rows_current)
    prior_exact, prior_exact_without_basis, prior_fallback = _index_balance_rows(balance_rows_prior)

    curve_lookup = _CurveRateLookup()
    rows: list[PnlBridgeRow] = []
    for raw_row in pnl_fi_rows:
        report_date = _coerce_date(raw_row["report_date"])
        instrument_code = str(raw_row.get("instrument_code") or "")
        portfolio_name = str(raw_row.get("portfolio_name") or "")
        cost_center = str(raw_row.get("cost_center") or "")
        currency_basis = str(raw_row.get("currency_basis") or "")

        current_resolution = _resolve_balance_row(
            instrument_code=instrument_code,
            portfolio_name=portfolio_name,
            cost_center=cost_center,
            currency_basis=currency_basis,
            accounting_basis=str(raw_row.get("accounting_basis") or ""),
            exact=current_exact,
            exact_without_basis=current_exact_without_basis,
            fallback=current_fallback,
        )
        current_balance = current_resolution.row
        prior_resolution = _resolve_balance_row(
            instrument_code=instrument_code,
            portfolio_name=portfolio_name,
            cost_center=cost_center,
            currency_basis=currency_basis,
            accounting_basis=str(raw_row.get("accounting_basis") or ""),
            exact=prior_exact,
            exact_without_basis=prior_exact_without_basis,
            fallback=prior_fallback,
        )
        prior_balance = prior_resolution.row

        carry = _coerce_decimal(raw_row.get("interest_income_514", ZERO))
        realized_trading = _coerce_decimal(raw_row.get("capital_gain_517", ZERO))
        unrealized_fv = _coerce_decimal(raw_row.get("fair_value_change_516", ZERO))
        manual_adjustment = _coerce_decimal(raw_row.get("manual_adjustment", ZERO))

        # 市场效应（骑乘/曲线/利差/汇兑）是对公允价值变动 516 的解释项，只对
        # FVTPL 行计算：非 FVTPL 行的 516 已在正式事实门控中剔除
        # （pnl._recognized_pnl_components），其会计损益中不存在这些效应可解释
        # 的部分。与 bond_four_effects 的 AC 归零、campisi_attribution_service
        # 的 FVTPL 门控保持同一口径（2026-08 审计 PNL-02）。
        include_market_effects = (
            str(raw_row.get("accounting_basis") or "") == ACCOUNTING_BASIS_FVTPL
        )
        if include_market_effects:
            curve_type = infer_curve_type(
                raw_row.get("instrument_name"),
                current_balance.get("bond_type") if current_balance else "",
                current_balance.get("asset_class") if current_balance else "",
                current_balance.get("instrument_name") if current_balance else "",
            )
            current_curve = cdb_curve_current if curve_type == "cdb" else treasury_curve_current
            prior_curve = cdb_curve_prior if curve_type == "cdb" else treasury_curve_prior

            # roll_down / curve_shift / credit_spread all key off the current balance row's
            # years-to-maturity and modified duration; compute them once per row instead of
            # once per effect (all three effects require a current benchmark curve).
            if current_balance is not None and current_curve:
                years_to_maturity = _years_to_maturity(report_date=report_date, row=current_balance)
                modified_duration = (
                    _modified_duration(report_date=report_date, row=current_balance)
                    if years_to_maturity > 0
                    else ZERO
                )
            else:
                years_to_maturity = 0.0
                modified_duration = ZERO

            roll_down = _calculate_roll_down(
                report_date=report_date,
                current_balance=current_balance,
                prior_balance=prior_balance,
                curve=current_curve,
                curve_lookup=curve_lookup,
                years_to_maturity=years_to_maturity,
                modified_duration=modified_duration,
            )
            treasury_curve = _calculate_curve_shift(
                report_date=report_date,
                current_balance=current_balance,
                current_curve=current_curve,
                prior_curve=prior_curve,
                curve_lookup=curve_lookup,
                years_to_maturity=years_to_maturity,
                modified_duration=modified_duration,
            )
            credit_spread = _calculate_credit_spread_shift(
                report_date=report_date,
                current_balance=current_balance,
                current_curve=current_curve,
                prior_curve=prior_curve,
                aaa_credit_curve_current=aaa_credit_curve_current,
                aaa_credit_curve_prior=aaa_credit_curve_prior,
                curve_lookup=curve_lookup,
                years_to_maturity=years_to_maturity,
                modified_duration=modified_duration,
            )
            fx_translation = _calculate_fx_translation(
                currency_basis=currency_basis,
                exposure_native=_fx_exposure_native(current_balance),
                fx_rate_current=fx_rates_current,
                fx_rate_prior=fx_rates_prior,
            )
            fx_rate_missing_diagnostic = _fx_rate_missing_diagnostic(
                currency_basis=currency_basis,
                fx_rate_current=fx_rates_current,
                fx_rate_prior=fx_rates_prior,
            )
        else:
            roll_down = ZERO
            treasury_curve = ZERO
            credit_spread = ZERO
            fx_translation = ZERO
            fx_rate_missing_diagnostic = None

        # 互斥分解：516 不计入 explained。市场效应本身就是对 516 的解释，二者
        # 同时相加会使 residual 在代数上恒等于市场效应之和的相反数，质量标记
        # 随之失真（2026-08 审计 PNL-01）。residual = 516 − 市场效应，即模型
        # 未能解释的公允价值变动；非 FVTPL 行两侧均为 0，残差自然闭合。
        explained_pnl = (
            carry
            + roll_down
            + treasury_curve
            + credit_spread
            + fx_translation
            + realized_trading
            + manual_adjustment
        )
        actual_raw = raw_row.get("total_pnl")
        actual_pnl_missing = actual_raw in (None, "")
        actual_pnl = ZERO if actual_pnl_missing else _coerce_decimal(actual_raw)
        residual = actual_pnl - explained_pnl
        residual_ratio = (
            None
            if actual_pnl_missing
            else _calculate_residual_ratio(
                actual_pnl=actual_pnl,
                explained_pnl=explained_pnl,
                residual=residual,
            )
        )

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
                quality_flag="warning" if actual_pnl_missing else _quality_flag(residual_ratio),
                current_balance_found=current_balance is not None,
                prior_balance_found=prior_balance is not None,
                balance_diagnostics=_build_balance_diagnostics(
                    current_balance=current_balance,
                    prior_balance=prior_balance,
                    current_resolution_diagnostic=current_resolution.diagnostic,
                    prior_resolution_diagnostic=prior_resolution.diagnostic,
                    actual_pnl_diagnostic=(
                        "actual_pnl missing; residual_ratio unavailable."
                        if actual_pnl_missing
                        else None
                    ),
                    fx_rate_missing_diagnostic=fx_rate_missing_diagnostic,
                ),
            )
        )
    return rows


def required_curve_types_for_pnl_bridge(
    pnl_fi_rows: list[dict],
    balance_rows_current: list[dict],
    balance_rows_prior: list[dict],
) -> set[str]:
    current_exact, current_exact_without_basis, current_fallback = _index_balance_rows(balance_rows_current)
    prior_exact, prior_exact_without_basis, prior_fallback = _index_balance_rows(balance_rows_prior)
    required: set[str] = set()
    for raw_row in pnl_fi_rows:
        currency_basis = str(raw_row.get("currency_basis") or "")
        accounting_basis = str(raw_row.get("accounting_basis") or "")
        instrument_code = str(raw_row.get("instrument_code") or "")
        portfolio_name = str(raw_row.get("portfolio_name") or "")
        cost_center = str(raw_row.get("cost_center") or "")
        current_balance = _resolve_balance_row(
            instrument_code=instrument_code,
            portfolio_name=portfolio_name,
            cost_center=cost_center,
            currency_basis=currency_basis,
            accounting_basis=accounting_basis,
            exact=current_exact,
            exact_without_basis=current_exact_without_basis,
            fallback=current_fallback,
        ).row
        prior_balance = _resolve_balance_row(
            instrument_code=instrument_code,
            portfolio_name=portfolio_name,
            cost_center=cost_center,
            currency_basis=currency_basis,
            accounting_basis=accounting_basis,
            exact=prior_exact,
            exact_without_basis=prior_exact_without_basis,
            fallback=prior_fallback,
        ).row
        representative = current_balance or prior_balance
        if representative is None:
            continue
        if _is_credit_row(representative):
            required.update({"treasury", "aaa_credit"})
            continue
        curve_type = infer_curve_type(
            representative.get("instrument_name"),
            representative.get("bond_type"),
            representative.get("asset_class"),
        )
        required.add("cdb" if curve_type == "cdb" else "treasury")
    return required


def _calculate_roll_down(
    *,
    report_date: date,
    current_balance: Mapping[str, object] | None,
    prior_balance: Mapping[str, object] | None,
    curve: dict[str, Decimal] | None,
    curve_lookup: _CurveRateLookup | None = None,
    years_to_maturity: float | None = None,
    modified_duration: Decimal | None = None,
) -> Decimal:
    if current_balance is None or prior_balance is None or not curve:
        return ZERO
    if years_to_maturity is None:
        years_to_maturity = _years_to_maturity(report_date=report_date, row=current_balance)
    if years_to_maturity <= 0:
        return ZERO
    lookup = curve_lookup or _CurveRateLookup()
    current_curve_rate = _curve_rate(curve, years_to_maturity, curve_lookup=lookup)
    period_days = _period_days(current_balance=current_balance, prior_balance=prior_balance)
    if period_days <= 0:
        return ZERO
    rolled_years = max(0.0, years_to_maturity - (period_days / 365))
    rolled_curve_rate = _curve_rate(curve, rolled_years, curve_lookup=lookup)
    if modified_duration is None:
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
    curve_lookup: _CurveRateLookup | None = None,
    years_to_maturity: float | None = None,
    modified_duration: Decimal | None = None,
) -> Decimal:
    if current_balance is None or not current_curve or not prior_curve:
        return ZERO
    if years_to_maturity is None:
        years_to_maturity = _years_to_maturity(report_date=report_date, row=current_balance)
    if years_to_maturity <= 0:
        return ZERO
    lookup = curve_lookup or _CurveRateLookup()
    current_curve_rate = _curve_rate(current_curve, years_to_maturity, curve_lookup=lookup)
    prior_curve_rate = _curve_rate(prior_curve, years_to_maturity, curve_lookup=lookup)
    if modified_duration is None:
        modified_duration = _modified_duration(report_date=report_date, row=current_balance)
    market_value = _curve_market_value(current_balance)
    if modified_duration == ZERO or market_value == ZERO:
        return ZERO
    rate_delta = (current_curve_rate - prior_curve_rate) / HUNDRED
    return -(rate_delta * modified_duration * market_value)


def _calculate_credit_spread_shift(
    *,
    report_date: date,
    current_balance: Mapping[str, object] | None,
    current_curve: dict[str, Decimal] | None,
    prior_curve: dict[str, Decimal] | None,
    aaa_credit_curve_current: dict[str, Decimal] | None,
    aaa_credit_curve_prior: dict[str, Decimal] | None,
    curve_lookup: _CurveRateLookup | None = None,
    years_to_maturity: float | None = None,
    modified_duration: Decimal | None = None,
) -> Decimal:
    """
    Credit PnL from change in (AAA enterprise curve − benchmark treasury/CDB curve) spread,
    for credit book rows, when governed curves exist for both dates.
    """
    if current_balance is None or not _is_credit_row(current_balance):
        return ZERO
    if (
        not current_curve
        or not prior_curve
        or not aaa_credit_curve_current
        or not aaa_credit_curve_prior
    ):
        return ZERO
    if years_to_maturity is None:
        years_to_maturity = _years_to_maturity(report_date=report_date, row=current_balance)
    if years_to_maturity <= 0:
        return ZERO
    lookup = curve_lookup or _CurveRateLookup()
    current_spread = (
        _curve_rate(aaa_credit_curve_current, years_to_maturity, curve_lookup=lookup)
        - _curve_rate(current_curve, years_to_maturity, curve_lookup=lookup)
    )
    prior_spread = (
        _curve_rate(aaa_credit_curve_prior, years_to_maturity, curve_lookup=lookup)
        - _curve_rate(prior_curve, years_to_maturity, curve_lookup=lookup)
    )
    if modified_duration is None:
        modified_duration = _modified_duration(report_date=report_date, row=current_balance)
    market_value = _curve_market_value(current_balance)
    if modified_duration == ZERO or market_value == ZERO:
        return ZERO
    spread_delta = (current_spread - prior_spread) / HUNDRED
    return -(spread_delta * modified_duration * market_value)


def _fx_exposure_native(row: Mapping[str, object] | None) -> Decimal:
    """Native FX base for bridge translation.

    Prefer dirty market value (aligned with beginning/ending dirty MV framing and with
    ``read_models._fx_effect``'s market-value base). Fall back to face only when no
    market-value fields are present so legacy fixtures still exercise the FX path.
    """
    if row is None:
        return ZERO
    dirty = _dirty_market_value(row)
    if dirty != ZERO:
        return dirty
    return _coerce_decimal(row.get("face_value_native", ZERO))


def _calculate_fx_translation(
    *,
    currency_basis: str,
    exposure_native: Decimal,
    fx_rate_current: dict[str, Decimal] | None,
    fx_rate_prior: dict[str, Decimal] | None,
) -> Decimal:
    """
    FX translation = exposure_native * (current_rate - prior_rate).

    ``exposure_native`` is dirty / market value in native currency (not face), matching
    the dirty-MV bridge framing and return-decomposition ``fx_effect``.

    - CNY/CNX/RMB rows have no FX translation.
    - Missing FX dictionaries or missing base-currency rates default to 0 so the bridge
      still closes; the missing-input condition is separately surfaced as a diagnostic via
      ``_fx_rate_missing_diagnostic`` rather than being silently treated as "no FX effect".
    """
    if not fx_rate_current or not fx_rate_prior:
        return ZERO
    base = currency_basis.upper().strip()
    if base in ("", "CNY", "CNX", "RMB"):
        return ZERO
    current_rate = fx_rate_current.get(base)
    prior_rate = fx_rate_prior.get(base)
    if current_rate is None or prior_rate is None:
        return ZERO
    return (exposure_native * (current_rate - prior_rate)).quantize(
        AMOUNT_SCALE, rounding=ROUND_HALF_UP
    )


def _fx_rate_missing_diagnostic(
    *,
    currency_basis: str,
    fx_rate_current: dict[str, Decimal] | None,
    fx_rate_prior: dict[str, Decimal] | None,
) -> str | None:
    """Distinguish "no FX exposure" (domestic row) from "missing FX input" (foreign row).

    Returns a diagnostic string (including the currency) when a foreign-currency row cannot
    be translated because the FX dictionary or the row's rate is missing. Domestic rows
    (empty/CNY/CNX/RMB) have no FX exposure and never produce a diagnostic.
    """
    base = currency_basis.upper().strip()
    if base in ("", "CNY", "CNX", "RMB"):
        return None
    if not fx_rate_current or not fx_rate_prior:
        return (
            f"FX_RATE_MISSING: currency={base}; FX rate dictionary missing; "
            "fx_translation defaulted to 0."
        )
    if fx_rate_current.get(base) is None or fx_rate_prior.get(base) is None:
        return (
            f"FX_RATE_MISSING: currency={base}; {base} rate missing for the period; "
            "fx_translation defaulted to 0."
        )
    return None


def _curve_rate(
    curve: dict[str, Decimal],
    target_years: float,
    *,
    curve_lookup: _CurveRateLookup | None = None,
) -> Decimal:
    if not curve:
        return ZERO
    lookup = curve_lookup or _CurveRateLookup()
    return lookup.rate(curve, target_years)


def _years_to_maturity(*, report_date: date, row: Mapping[str, object]) -> float:
    # Prefer the bond-analytics materialized value when the balance row carries it;
    # recompute from maturity_date only as fallback.
    materialized = row.get("years_to_maturity")
    if materialized not in (None, ""):
        return float(_coerce_decimal(materialized))
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
    # Prefer the bond-analytics materialized value when the balance row carries it;
    # recompute via estimate_duration only as fallback.
    materialized = row.get("modified_duration")
    if materialized not in (None, ""):
        return _coerce_decimal(materialized)
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


def _is_credit_row(row: Mapping[str, object]) -> bool:
    surface = " ".join(
        str(value or "")
        for value in (
            row.get("asset_class"),
            row.get("bond_type"),
            row.get("instrument_name"),
        )
    )
    return classify_asset_class(surface) == "credit"


def _build_balance_diagnostics(
    *,
    current_balance: Mapping[str, object] | None,
    prior_balance: Mapping[str, object] | None,
    current_resolution_diagnostic: str | None = None,
    prior_resolution_diagnostic: str | None = None,
    actual_pnl_diagnostic: str | None = None,
    fx_rate_missing_diagnostic: str | None = None,
) -> tuple[str, ...]:
    diagnostics: list[str] = []
    if current_resolution_diagnostic:
        diagnostics.append(current_resolution_diagnostic)
    if prior_resolution_diagnostic:
        diagnostics.append(prior_resolution_diagnostic)
    if actual_pnl_diagnostic:
        diagnostics.append(actual_pnl_diagnostic)
    if fx_rate_missing_diagnostic:
        diagnostics.append(fx_rate_missing_diagnostic)
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
) -> _ResolvedBalanceRow:
    if currency_basis:
        exact_match = exact.get(
            (instrument_code, portfolio_name, cost_center, currency_basis, accounting_basis)
        )
        if exact_match is not None:
            return _ResolvedBalanceRow(exact_match, match_level="exact")
        exact_match_without_basis = exact_without_basis.get(
            (instrument_code, portfolio_name, cost_center, currency_basis)
        )
        if exact_match_without_basis is not None:
            return _ResolvedBalanceRow(exact_match_without_basis, match_level="exact_without_basis")
    fallback_match = fallback.get((instrument_code, portfolio_name, cost_center, accounting_basis))
    if fallback_match is not None and currency_basis:
        fallback_currency = str(fallback_match.get("currency_basis") or "")
        if fallback_currency and fallback_currency != currency_basis:
            return _ResolvedBalanceRow(
                fallback_match,
                "Balance row currency_basis mismatch; "
                f"expected {currency_basis}, found {fallback_currency}; fallback balance row used.",
                match_level="fallback",
            )
    return _ResolvedBalanceRow(
        fallback_match,
        match_level="fallback" if fallback_match is not None else "missing",
    )


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


def _quality_flag(residual_ratio: Decimal | None) -> str:
    if residual_ratio is None:
        return "warning"
    abs_ratio = abs(residual_ratio)
    if abs_ratio < Decimal("0.05"):
        return "ok"
    if abs_ratio < Decimal("0.10"):
        return "warning"
    return "error"


def _calculate_residual_ratio(
    *,
    actual_pnl: Decimal,
    explained_pnl: Decimal,
    residual: Decimal,
) -> Decimal | None:
    if actual_pnl == ZERO:
        return ZERO if explained_pnl == ZERO else None
    return residual / actual_pnl


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


__all__ = ["PnlBridgeRow", "build_pnl_bridge_rows", "required_curve_types_for_pnl_bridge"]
