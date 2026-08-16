from __future__ import annotations

from collections.abc import Iterable, Mapping
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
    resolve_ytm_with_par_fallback,
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
from backend.app.core_finance.rate_units import normalize_percent_rate_to_decimal

ZERO = Decimal("0")
HUNDRED = Decimal("100")
AMOUNT_SCALE = Decimal("0.00000001")

# 曲线类效应"归零但不是观测值"的诊断前缀。行级 `balance_diagnostics` 是本模块
# 唯一能带出结构化信号的通道（`PnlBridgeRowSchema` 是 extra="forbid"），因此这些
# 前缀就是调用方与页面用来区分"真为零"和"没有曲线"的判据。
TREASURY_CURVE_UNAVAILABLE_PREFIX = "TREASURY_CURVE_UNAVAILABLE"
TREASURY_CURVE_SAME_SOURCE_PREFIX = "TREASURY_CURVE_SAME_SOURCE"
CREDIT_SPREAD_CURVE_UNAVAILABLE_PREFIX = "CREDIT_SPREAD_CURVE_UNAVAILABLE"
CREDIT_SPREAD_CURVE_SAME_SOURCE_PREFIX = "CREDIT_SPREAD_CURVE_SAME_SOURCE"
# 这两条不是曲线缺失，但同样把效应顶成 0：市值基数全 NULL（三项效应）和滚动窗口
# 缺失（仅 roll_down）。它们此前只有字符串，没有结构化通道。
MARKET_VALUE_BASE_MISSING_PREFIX = "MARKET_VALUE_BASE_MISSING"
ROLL_DOWN_WINDOW_MISSING_PREFIX = "ROLL_DOWN_WINDOW_MISSING"
ROLL_DOWN_TENOR_OUTSIDE_CURVE_PREFIX = "ROLL_DOWN_TENOR_OUTSIDE_CURVE"
CURVE_EFFECT_DEGRADED_PREFIXES = (
    TREASURY_CURVE_UNAVAILABLE_PREFIX,
    TREASURY_CURVE_SAME_SOURCE_PREFIX,
    CREDIT_SPREAD_CURVE_UNAVAILABLE_PREFIX,
    CREDIT_SPREAD_CURVE_SAME_SOURCE_PREFIX,
)

# 与上面的诊断前缀同源的结构化可用性取值。诊断字符串是给人读的一句话，可用性枚举
# 是给页面分支用的判据；两者由 `_curve_effect_availability` 从同一个诊断派生，所以
# 不可能出现"字符串说不可用、枚举说正常"的漂移。既有的文本匹配器不受影响：枚举是
# 并行新增的通道，不替换任何一条诊断。
CURVE_EFFECT_OK = "ok"
CURVE_EFFECT_UNAVAILABLE = "unavailable"
CURVE_EFFECT_NOT_APPLICABLE = "not_applicable"
# 汇总级独有：部分行不可用时，合计既不是干净的观测值也不是完全缺失。
CURVE_EFFECT_PARTIAL = "partial"

CURVE_EFFECT_REASON_CURVE_UNAVAILABLE = "curve_unavailable"
CURVE_EFFECT_REASON_SAME_SOURCE_CURVE = "same_source_curve"
CURVE_EFFECT_REASON_MARKET_VALUE_BASE_MISSING = "market_value_base_missing"
CURVE_EFFECT_REASON_ROLL_WINDOW_MISSING = "roll_window_missing"
CURVE_EFFECT_REASON_TENOR_OUTSIDE_CURVE = "tenor_outside_curve_support"
CURVE_EFFECT_REASON_NON_FVTPL_BASIS = "non_fvtpl_basis"
CURVE_EFFECT_REASON_NOT_CREDIT_BOOK = "not_credit_book"
CURVE_EFFECT_REASON_NO_CURVE_SENSITIVITY = "no_curve_sensitivity"
CURVE_EFFECT_REASON_BALANCE_ROW_MISSING = "balance_row_missing"

_CURVE_EFFECT_REASON_BY_PREFIX: tuple[tuple[str, str], ...] = (
    (TREASURY_CURVE_UNAVAILABLE_PREFIX, CURVE_EFFECT_REASON_CURVE_UNAVAILABLE),
    (TREASURY_CURVE_SAME_SOURCE_PREFIX, CURVE_EFFECT_REASON_SAME_SOURCE_CURVE),
    (CREDIT_SPREAD_CURVE_UNAVAILABLE_PREFIX, CURVE_EFFECT_REASON_CURVE_UNAVAILABLE),
    (CREDIT_SPREAD_CURVE_SAME_SOURCE_PREFIX, CURVE_EFFECT_REASON_SAME_SOURCE_CURVE),
    (MARKET_VALUE_BASE_MISSING_PREFIX, CURVE_EFFECT_REASON_MARKET_VALUE_BASE_MISSING),
    (ROLL_DOWN_WINDOW_MISSING_PREFIX, CURVE_EFFECT_REASON_ROLL_WINDOW_MISSING),
    (ROLL_DOWN_TENOR_OUTSIDE_CURVE_PREFIX, CURVE_EFFECT_REASON_TENOR_OUTSIDE_CURVE),
)


@dataclass(slots=True, frozen=True)
class CurveEffectAvailabilitySummary:
    """汇总级可用性：合计里的 0 和行级的 0 一样需要能被判读。"""

    status: str
    unavailable_rows: int
    applicable_rows: int
    reasons: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class _TreasuryCurveDiagnostic:
    """基准曲线诊断：给人读的一句话，加上它对每个效应各自意味着什么。

    ``treasury_curve`` 要把两端曲线相减，``roll_down`` 只沿当期曲线滚动，所以同一个
    曲线状态对两者的后果并不相同（缺上期曲线只打掉前者，两端同源只打掉前者）。把
    两个结论和字符串放在同一个分支里产出，是为了让它们不可能各说各话——如果各自
    再判一次门控，总有一天会出现"字符串说不可用、枚举说正常"。
    """

    message: str | None = None
    curve_shift_reason: str | None = None
    roll_down_reason: str | None = None


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
    # 这六个字段回答"上面那三个 0 是观测值还是缺失值"，不参与任何金额计算。
    # roll_down 与另外两项的门控并不相同：它只用当期曲线沿自身斜率滚动，却额外
    # 需要一个有效的滚动窗口（上期余额行 + 正的天数），所以必须单独报，不能借用
    # treasury_curve 的结论。
    roll_down_availability: str
    roll_down_availability_reason: str | None
    treasury_curve_availability: str
    treasury_curve_availability_reason: str | None
    credit_spread_availability: str
    credit_spread_availability_reason: str | None


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

    def _fitted(self, curve: dict[str, Decimal]) -> FittedCurve:
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
        return fitted

    def rate(self, curve: dict[str, Decimal], target_years: float) -> Decimal:
        return _interpolate_fitted_curve(self._fitted(curve), target_years)

    def support(self, curve: dict[str, Decimal]) -> tuple[float, float] | None:
        """拟合曲线真正覆盖的期限区间 ``[最短, 最长]``（年）。

        取自实际拟合出来的节点而不是写死的期限表：``build_full_curve`` 目前把任何
        原始曲线归一到 3M–30Y 网格，但这一点属于它的实现，不该在这里再抄一遍——
        它哪天补上 1M 节点，这里就应该自动跟着放宽，而不是继续误报。
        """
        points = self._fitted(curve).points
        if not points:
            return None
        return points[0].years, points[-1].years


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
            # Computed whenever a current balance row exists — including when the curve is
            # missing — because the curve-unavailable diagnostics need to know whether the
            # row was otherwise eligible for a non-zero effect. Numerically inert: every
            # effect returns 0 early when the curve is falsy.
            if current_balance is not None:
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
            fx_currency_code = _fx_currency_code(current_balance, fallback=currency_basis)
            fx_translation = _calculate_fx_translation(
                currency_code=fx_currency_code,
                exposure_native=_fx_exposure_native(current_balance),
                fx_rate_current=fx_rates_current,
                fx_rate_prior=fx_rates_prior,
            )
            fx_rate_missing_diagnostic = _fx_rate_missing_diagnostic(
                currency_code=fx_currency_code,
                fx_rate_current=fx_rates_current,
                fx_rate_prior=fx_rates_prior,
            )
            market_value_base_missing_diagnostic = _market_value_base_missing_diagnostic(
                current_balance=current_balance,
                current_curve=current_curve,
                years_to_maturity=years_to_maturity,
                modified_duration=modified_duration,
            )
            roll_down_window_missing_diagnostic = _roll_down_window_missing_diagnostic(
                current_balance=current_balance,
                prior_balance=prior_balance,
                current_curve=current_curve,
                years_to_maturity=years_to_maturity,
                modified_duration=modified_duration,
            )
            roll_down_flat_extrapolation_diagnostic = _roll_down_flat_extrapolation_diagnostic(
                current_balance=current_balance,
                prior_balance=prior_balance,
                current_curve=current_curve,
                curve_lookup=curve_lookup,
                years_to_maturity=years_to_maturity,
                modified_duration=modified_duration,
            )
            structural_exemption = _structural_exemption_reason(
                current_balance=current_balance,
                years_to_maturity=years_to_maturity,
                modified_duration=modified_duration,
            )
            curve_effect_eligible = structural_exemption is None
            treasury_curve_diagnostic = _treasury_curve_diagnostic(
                curve_type=curve_type,
                current_curve=current_curve,
                prior_curve=prior_curve,
                eligible=curve_effect_eligible,
            )
            credit_spread_curve_diagnostic = _credit_spread_curve_diagnostic(
                current_balance=current_balance,
                current_curve=current_curve,
                prior_curve=prior_curve,
                aaa_credit_curve_current=aaa_credit_curve_current,
                aaa_credit_curve_prior=aaa_credit_curve_prior,
                eligible=curve_effect_eligible,
            )
            # 市值基数全 NULL 会把三项效应一起顶成 0，而它既不是曲线问题也不是
            # 结构性豁免（_structural_exemption_reason 明确不豁免这种行），此前
            # 只有诊断字符串、没有结构化通道，枚举因此错报为 ok。
            market_value_base_reason = _reason_from_diagnostic(
                market_value_base_missing_diagnostic
            )
            (
                roll_down_availability,
                roll_down_availability_reason,
            ) = _curve_effect_availability(
                not_applicable_reason=structural_exemption,
                unavailable_reasons=(
                    treasury_curve_diagnostic.roll_down_reason,
                    market_value_base_reason,
                    _reason_from_diagnostic(roll_down_window_missing_diagnostic),
                    _reason_from_diagnostic(roll_down_flat_extrapolation_diagnostic),
                ),
            )
            (
                treasury_curve_availability,
                treasury_curve_availability_reason,
            ) = _curve_effect_availability(
                not_applicable_reason=structural_exemption,
                unavailable_reasons=(
                    treasury_curve_diagnostic.curve_shift_reason,
                    market_value_base_reason,
                ),
            )
            (
                credit_spread_availability,
                credit_spread_availability_reason,
            ) = _curve_effect_availability(
                # 口径豁免优先于敏感度豁免：对利率簿行说"没有信用利差可动"比说
                # "这行不随曲线动"更贴近它为什么是 0。
                not_applicable_reason=(
                    CURVE_EFFECT_REASON_NOT_CREDIT_BOOK
                    if current_balance is not None and not _is_credit_row(current_balance)
                    else structural_exemption
                ),
                unavailable_reasons=(
                    _reason_from_diagnostic(credit_spread_curve_diagnostic),
                    market_value_base_reason,
                ),
            )
        else:
            roll_down = ZERO
            treasury_curve = ZERO
            credit_spread = ZERO
            fx_translation = ZERO
            fx_rate_missing_diagnostic = None
            market_value_base_missing_diagnostic = None
            roll_down_window_missing_diagnostic = None
            roll_down_flat_extrapolation_diagnostic = None
            # 非 FVTPL 行的市场效应按口径整体不适用，其 0 是结构性的，
            # 与"缺曲线"无关，因此不产生曲线诊断（与 FX 诊断同一门控）。
            treasury_curve_diagnostic = _TreasuryCurveDiagnostic()
            credit_spread_curve_diagnostic = None
            roll_down_availability = CURVE_EFFECT_NOT_APPLICABLE
            roll_down_availability_reason = CURVE_EFFECT_REASON_NON_FVTPL_BASIS
            treasury_curve_availability = CURVE_EFFECT_NOT_APPLICABLE
            treasury_curve_availability_reason = CURVE_EFFECT_REASON_NON_FVTPL_BASIS
            credit_spread_availability = CURVE_EFFECT_NOT_APPLICABLE
            credit_spread_availability_reason = CURVE_EFFECT_REASON_NON_FVTPL_BASIS

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

        curve_effect_degraded = bool(
            treasury_curve_diagnostic.message or credit_spread_curve_diagnostic
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
                quality_flag=_escalate_quality_flag(
                    "warning" if actual_pnl_missing else _quality_flag(residual_ratio),
                    degraded=curve_effect_degraded,
                ),
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
                    market_value_base_missing_diagnostic=(
                        market_value_base_missing_diagnostic
                    ),
                    roll_down_window_missing_diagnostic=roll_down_window_missing_diagnostic,
                    roll_down_flat_extrapolation_diagnostic=(
                        roll_down_flat_extrapolation_diagnostic
                    ),
                    treasury_curve_diagnostic=treasury_curve_diagnostic.message,
                    credit_spread_curve_diagnostic=credit_spread_curve_diagnostic,
                ),
                roll_down_availability=roll_down_availability,
                roll_down_availability_reason=roll_down_availability_reason,
                treasury_curve_availability=treasury_curve_availability,
                treasury_curve_availability_reason=treasury_curve_availability_reason,
                credit_spread_availability=credit_spread_availability,
                credit_spread_availability_reason=credit_spread_availability_reason,
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

    Bridge balance rows come from the CNY-basis projection
    (``fetch_pnl_bridge_zqtz_balance_rows``), so their ``market_value_amount`` /
    ``accrued_interest_amount`` are already FX-converted and must not be multiplied by
    the rate delta again (that would scale fx_translation by the FX rate). Use the
    service-enriched native dirty market value (``market_value_native`` +
    ``accrued_interest_native``, aligned with ``read_models._fx_effect``'s
    market-value base); fall back to ``face_value_native`` only when the native
    market-value fields are absent, else 0.
    """
    if row is None:
        return ZERO
    market_value_native = row.get("market_value_native")
    accrued_interest_native = row.get("accrued_interest_native")
    if market_value_native not in (None, "") or accrued_interest_native not in (None, ""):
        return _coerce_decimal(market_value_native) + _coerce_decimal(accrued_interest_native)
    return _coerce_decimal(row.get("face_value_native", ZERO))


def _fx_currency_code(row: Mapping[str, object] | None, *, fallback: str) -> str:
    """Resolve the traded currency of a bridge row.

    The PnL fact's ``currency_basis`` is only the CNY/CNX reporting caliber
    (``pnl.CurrencyBasis``), so it can never identify a foreign currency; the balance
    row's ``currency_code`` column carries the real one. Resolution order mirrors
    ``pnl_bridge_service._bridge_fx_base_currencies`` so the currency looked up here is
    always a key of the FX dictionaries that service loaded.
    """
    if row is not None:
        code = str(row.get("currency_code") or row.get("currency_basis") or "")
        if code:
            return code
    return fallback


def _calculate_fx_translation(
    *,
    currency_code: str,
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
    base = currency_code.upper().strip()
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
    currency_code: str,
    fx_rate_current: dict[str, Decimal] | None,
    fx_rate_prior: dict[str, Decimal] | None,
) -> str | None:
    """Distinguish "no FX exposure" (domestic row) from "missing FX input" (foreign row).

    Returns a diagnostic string (including the currency) when a foreign-currency row cannot
    be translated because the FX dictionary or the row's rate is missing. Domestic rows
    (empty/CNY/CNX/RMB) have no FX exposure and never produce a diagnostic.
    """
    base = currency_code.upper().strip()
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
    coupon_rate = _percent_rate_to_decimal(row.get("coupon_rate"))
    ytm_value = _percent_rate_to_decimal(row.get("ytm_value"))
    macaulay_duration = estimate_duration(
        maturity_date=maturity_date,
        report_date=report_date,
        coupon_rate=coupon_rate,
        ytm=ytm_value,
        bond_code=str(row.get("instrument_code") or ""),
    )
    # W-fi-2026-08 P1 残余：ytm 缺失/非正时 estimate_duration 已按 par 假设
    # （ytm=coupon）计算 Macaulay，修正久期折算必须使用同一生效 ytm，否则
    # 有票息缺 ytm 行返回未折算的 Macaulay（约 +3% 高估）。
    effective_ytm, _ytm_par_fallback_used = resolve_ytm_with_par_fallback(coupon_rate, ytm_value)
    return estimate_modified_duration(macaulay_duration, effective_ytm)


def _percent_rate_to_decimal(value: object) -> Decimal:
    """Normalize a ``fact_formal_zqtz_balance_daily`` annual rate to decimal form.

    ``coupon_rate`` / ``ytm_value`` are stored in percent caliber (2.38 = 2.38%; see
    docs/audits/2026-07-19-system-calculation-audit.md 取证 1) while
    ``estimate_duration`` / ``estimate_modified_duration`` expect decimal form, so the
    raw value collapses duration systematically. Dirty inputs (missing, negative,
    > 20%) normalize to ``0``; ``estimate_duration`` / ``estimate_modified_duration``
    then apply the par-assumption fallback (ytm=coupon) for coupon-bearing rows and
    years-to-maturity only for zero-coupon rows.
    """
    normalized = normalize_percent_rate_to_decimal(value)
    if normalized is None:
        return ZERO
    return Decimal(str(normalized))


_MARKET_VALUE_KEYS = ("market_value_amount", "market_value", "market_value_native")
_ACCRUED_INTEREST_KEYS = (
    "accrued_interest_amount",
    "accrued_interest",
    "accrued_interest_native",
)


def _first_available_value(row: Mapping[str, object], keys: tuple[str, ...]) -> object | None:
    """First value among ``keys`` that is neither absent nor NULL-like.

    ``row.get(a, row.get(b, default))`` only falls back when ``a`` is *absent*; a nullable
    column materialized as ``None`` (``fact_formal_zqtz_balance_daily.market_value_amount``)
    short-circuits the chain and collapses to 0 without ever reaching ``b``. NULL-like is
    ``None`` / ``""``, matching ``_coerce_decimal`` and ``_fx_exposure_native``.
    """
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _curve_market_value(row: Mapping[str, object]) -> Decimal:
    return _coerce_decimal(_first_available_value(row, _MARKET_VALUE_KEYS))


def _market_value_base_missing_diagnostic(
    *,
    current_balance: Mapping[str, object] | None,
    current_curve: dict[str, Decimal] | None,
    years_to_maturity: float,
    modified_duration: Decimal,
) -> str | None:
    """Distinguish "flat position" from "missing market-value base" on curve effects.

    ``_curve_market_value`` returns 0 both for a genuinely flat position and for a balance
    row whose market-value columns are all NULL. Only the latter zeroes roll_down /
    treasury_curve / credit_spread against the operator's expectation, with the gap
    silently absorbed by the residual, so the diagnostic fires only when the row is
    otherwise eligible for a non-zero curve effect (current balance row, benchmark curve,
    positive remaining tenor, non-zero modified duration).
    """
    if current_balance is None or not current_curve:
        return None
    if years_to_maturity <= 0 or modified_duration == ZERO:
        return None
    if _first_available_value(current_balance, _MARKET_VALUE_KEYS) is not None:
        return None
    return (
        f"{MARKET_VALUE_BASE_MISSING_PREFIX}: current balance row has no usable market value "
        f"({'/'.join(_MARKET_VALUE_KEYS)} all missing or NULL); "
        "roll_down / treasury_curve / credit_spread defaulted to 0."
    )


def _roll_down_window_missing_diagnostic(
    *,
    current_balance: Mapping[str, object] | None,
    prior_balance: Mapping[str, object] | None,
    current_curve: dict[str, Decimal] | None,
    years_to_maturity: float,
    modified_duration: Decimal,
) -> str | None:
    """Flag roll_down zeroed by the rolling window while curve effects still compute.

    ``_calculate_roll_down`` additionally requires a prior balance row and a positive day
    count, while ``_calculate_curve_shift`` / ``_calculate_credit_spread_shift`` key off the
    current row only. A missing or same-day prior row therefore yields a half decomposition
    (curve effect without roll effect) that the generic "Missing prior balance row"
    diagnostic does not attribute to roll_down. Fires only when roll_down would otherwise
    have been non-zero, so a flat or base-less position is not double-reported.
    """
    if current_balance is None or not current_curve:
        return None
    if years_to_maturity <= 0 or modified_duration == ZERO:
        return None
    if _curve_market_value(current_balance) == ZERO:
        return None
    if prior_balance is not None and (
        _period_days(current_balance=current_balance, prior_balance=prior_balance) > 0
    ):
        return None
    reason = (
        "prior balance row unavailable"
        if prior_balance is None
        else "prior balance row shares the current report_date (period_days=0)"
    )
    return (
        f"{ROLL_DOWN_WINDOW_MISSING_PREFIX}: {reason}; roll_down defaulted to 0 while "
        "treasury_curve / credit_spread still computed from the current balance row."
    )


def _roll_down_flat_extrapolation_diagnostic(
    *,
    current_balance: Mapping[str, object] | None,
    prior_balance: Mapping[str, object] | None,
    current_curve: dict[str, Decimal] | None,
    curve_lookup: _CurveRateLookup,
    years_to_maturity: float,
    modified_duration: Decimal,
) -> str | None:
    """Flag roll_down that is 0 because the position sits outside the curve's tenor span.

    ``roll_down`` is the only market effect that reads *two tenors off one curve*, so it
    is the only one that dies when the position's remaining tenor falls outside the
    curve's support: the interpolator clamps to the nearest node, both reads return the
    same rate, and the effect is 0 by construction. On 2026-07-31 every governed curve
    starts at 3M while sub-3M money-market paper (SCP / NCD) is a real part of the book,
    so those rows publish a structural 0 that looks exactly like "this bond earned no
    roll". ``treasury_curve`` / ``credit_spread`` are unaffected: they compare the *same*
    tenor across two dates, so clamping still yields a genuine rate change.

    Fires only when roll_down would otherwise have been computable, so a row already
    reported as curve-less, base-less or window-less is not double-reported.
    """
    if current_balance is None or prior_balance is None or not current_curve:
        return None
    if years_to_maturity <= 0 or modified_duration == ZERO:
        return None
    if _curve_market_value(current_balance) == ZERO:
        return None
    period_days = _period_days(current_balance=current_balance, prior_balance=prior_balance)
    if period_days <= 0:
        return None
    support = curve_lookup.support(current_curve)
    if support is None:
        return None
    shortest, longest = support
    rolled_years = max(0.0, years_to_maturity - (period_days / 365))
    below = years_to_maturity < shortest and rolled_years < shortest
    above = years_to_maturity > longest and rolled_years > longest
    if not (below or above):
        return None
    edge = "shorter than" if below else "longer than"
    bound = shortest if below else longest
    return (
        f"{ROLL_DOWN_TENOR_OUTSIDE_CURVE_PREFIX}: remaining tenor "
        f"{years_to_maturity:.4f}y is {edge} the benchmark curve's {bound:.4f}y "
        "boundary, so both roll points clamp to the same node and roll_down is 0 by "
        "construction; this is missing curve coverage, not an observed absence of roll."
    )


def _structural_exemption_reason(
    *,
    current_balance: Mapping[str, object] | None,
    years_to_maturity: float,
    modified_duration: Decimal,
) -> str | None:
    """Why this row would show 0 even with a perfect curve — ``None`` if it would move.

    Only a row that would move can turn a missing curve into a misleading zero. A
    matured or zero-duration row, or a genuinely flat position (market-value column
    present and equal to 0), yields 0 whatever the curve says, so reporting "curve
    unavailable" there would be a false alarm — and counting it as an *observed* zero
    would be just as wrong, because nothing about the curve was measured. Both the
    diagnostic gate and the structured availability field key off this one answer.

    A row whose market-value columns are all NULL is *not* exempt: we cannot claim it
    is flat, and ``_market_value_base_missing_diagnostic`` only fires when a curve
    exists, so the curve gap would otherwise go unreported.
    """
    if current_balance is None:
        return CURVE_EFFECT_REASON_BALANCE_ROW_MISSING
    if years_to_maturity <= 0 or modified_duration == ZERO:
        return CURVE_EFFECT_REASON_NO_CURVE_SENSITIVITY
    market_value_present = _first_available_value(current_balance, _MARKET_VALUE_KEYS) is not None
    if market_value_present and _curve_market_value(current_balance) == ZERO:
        return CURVE_EFFECT_REASON_NO_CURVE_SENSITIVITY
    return None


def _treasury_curve_diagnostic(
    *,
    curve_type: str,
    current_curve: dict[str, Decimal] | None,
    prior_curve: dict[str, Decimal] | None,
    eligible: bool,
) -> _TreasuryCurveDiagnostic:
    """Separate "the benchmark did not move" from "there is no benchmark to compare".

    ``_calculate_curve_shift`` returns 0 both when the period's rates were genuinely
    flat and when a curve is missing or both period ends resolved to the *same*
    snapshot (the 2026-07-31 reality: every date falls back to the 2026-06-30 curve, so
    ``rate_delta`` is 0 by construction). Published as a bare 0 the two are
    indistinguishable, and the page reads the second as the first.

    The message is unchanged; what is new is that the same branch also states what the
    condition means for each effect, so the structured fields never have to re-decide
    (or re-parse) it.
    """
    if not eligible:
        return _TreasuryCurveDiagnostic()
    if not current_curve or not prior_curve:
        missing = ", ".join(
            side
            for side, curve in (("current", current_curve), ("prior", prior_curve))
            if not curve
        )
        return _TreasuryCurveDiagnostic(
            message=(
                f"{TREASURY_CURVE_UNAVAILABLE_PREFIX}: curve_type={curve_type}; no benchmark curve "
                f"for the {missing} period end; roll_down / treasury_curve defaulted to 0. "
                "This is a missing input, not an observed zero rate move."
            ),
            curve_shift_reason=CURVE_EFFECT_REASON_CURVE_UNAVAILABLE,
            # roll_down 只沿当期曲线滚动，缺上期曲线不影响它；只有当期缺失才归零。
            roll_down_reason=(
                CURVE_EFFECT_REASON_CURVE_UNAVAILABLE if not current_curve else None
            ),
        )
    if current_curve == prior_curve:
        return _TreasuryCurveDiagnostic(
            message=(
                f"{TREASURY_CURVE_SAME_SOURCE_PREFIX}: curve_type={curve_type}; both period ends "
                "resolved to an identical benchmark curve, so the curve shift is 0 by construction; "
                "treasury_curve carries no information about the period."
            ),
            curve_shift_reason=CURVE_EFFECT_REASON_SAME_SOURCE_CURVE,
            # 两端同源只让"两端相减"恒为 0；roll_down 仍是从一条真实（尽管陈旧）
            # 曲线上读出来的观测值，标成不可用是假警报。曲线的陈旧性由
            # YIELD_CURVE_LATEST_FALLBACK 与 result_meta 的 stale 标记负责披露。
            roll_down_reason=None,
        )
    return _TreasuryCurveDiagnostic()


def _credit_spread_curve_diagnostic(
    *,
    current_balance: Mapping[str, object] | None,
    current_curve: dict[str, Decimal] | None,
    prior_curve: dict[str, Decimal] | None,
    aaa_credit_curve_current: dict[str, Decimal] | None,
    aaa_credit_curve_prior: dict[str, Decimal] | None,
    eligible: bool,
) -> str | None:
    """Same separation for ``credit_spread``, restricted to credit-book rows.

    A rate-book row has no credit spread to move, so its 0 is structurally correct and
    must not be flagged — mirroring how ``_fx_rate_missing_diagnostic`` stays silent on
    domestic rows.
    """
    if not eligible or current_balance is None or not _is_credit_row(current_balance):
        return None
    legs = (
        ("benchmark current", current_curve),
        ("benchmark prior", prior_curve),
        ("AAA current", aaa_credit_curve_current),
        ("AAA prior", aaa_credit_curve_prior),
    )
    missing = [name for name, curve in legs if not curve]
    if missing:
        return (
            f"{CREDIT_SPREAD_CURVE_UNAVAILABLE_PREFIX}: missing {', '.join(missing)} curve; "
            "credit_spread defaulted to 0. This is a missing input, not an observed zero "
            "spread move."
        )
    same_source = [
        name
        for name, is_same in (
            ("benchmark", current_curve == prior_curve),
            ("AAA", aaa_credit_curve_current == aaa_credit_curve_prior),
        )
        if is_same
    ]
    if same_source:
        return (
            f"{CREDIT_SPREAD_CURVE_SAME_SOURCE_PREFIX}: the {', '.join(same_source)} curve is "
            "identical on both period ends, so that leg of the spread change is 0 by "
            "construction; credit_spread understates the period."
        )
    return None


def _reason_from_diagnostic(diagnostic: str | None) -> str | None:
    """把一条诊断映射回它的成因码；无诊断或前缀不认识时返回 ``None``。

    只有"触发条件与该效应归零条件完全重合"的诊断才配进这张表——
    ``MARKET_VALUE_BASE_MISSING`` 与 ``ROLL_DOWN_WINDOW_MISSING`` 都是如此，所以
    从字符串反查成因与重新判门控等价，且只有一处判定。基准曲线诊断不在此列：
    同一条字符串对 roll_down 与 treasury_curve 的后果不同，由
    ``_TreasuryCurveDiagnostic`` 分别给出。
    """
    if diagnostic is None:
        return None
    for prefix, reason in _CURVE_EFFECT_REASON_BY_PREFIX:
        if diagnostic.startswith(prefix):
            return reason
    return None


def _curve_effect_availability(
    *,
    not_applicable_reason: str | None,
    unavailable_reasons: tuple[str | None, ...],
) -> tuple[str, str | None]:
    """把行级归零成因翻成 (状态, 成因) 二元组。

    成因由产生诊断的那一处直接给出，而不是在这里重新判一遍门控条件：一旦两处各判
    一次，就会有一天诊断说"缺曲线"而枚举说"正常"，而使用者只会看到其中一个。

    ``not_applicable`` 留给"这一行本来就不会有这个效应"的事实（非 FVTPL 行、利率簿
    的信用利差、到期/零久期/空仓行、缺当期余额行），它与 ``unavailable`` 的处置完全
    不同：前者不需要补数据，后者需要。这类行也不能报 ``ok``——它们的 0 与曲线无关，
    算进"有多少行观测到了曲线"会把缺曲线的占比稀释掉。

    ``unavailable_reasons`` 按根因优先排列，取第一个非空。实际上这些成因互斥
    （缺曲线时市值/窗口诊断根本不触发），排序只是把话说明白。

    既不属于豁免、也没有任何归零成因的行返回 ``ok``：它的 0 是拿真曲线算出来的。
    """
    if not_applicable_reason is not None:
        return CURVE_EFFECT_NOT_APPLICABLE, not_applicable_reason
    for reason in unavailable_reasons:
        if reason is not None:
            return CURVE_EFFECT_UNAVAILABLE, reason
    return CURVE_EFFECT_OK, None


def summarize_curve_effect_availability(
    entries: Iterable[tuple[str, str | None]],
) -> CurveEffectAvailabilitySummary:
    """把行级可用性折叠成汇总级判据。

    ``not_applicable`` 行不进分母：非 FVTPL 行本来就不参与市场效应，把它们算进
    "多少行不可用"会把占比稀释到看不出问题。反过来，当所有行都 ``not_applicable``
    时汇总也是 ``not_applicable``——这一天根本没有可比的曲线效应，合计 0 不是
    "曲线没动"。只要还有一行可用，合计就仍是一个（可能被低估的）观测量，因此报
    ``partial`` 而不是 ``unavailable``。
    """
    applicable = 0
    unavailable = 0
    unavailable_reasons: list[str] = []
    exempt_reasons: list[str] = []
    total = 0
    for status, reason in entries:
        total += 1
        if status == CURVE_EFFECT_NOT_APPLICABLE:
            if reason is not None and reason not in exempt_reasons:
                exempt_reasons.append(reason)
            continue
        applicable += 1
        if status == CURVE_EFFECT_UNAVAILABLE:
            unavailable += 1
            if reason is not None and reason not in unavailable_reasons:
                unavailable_reasons.append(reason)
    if total == 0:
        return CurveEffectAvailabilitySummary(CURVE_EFFECT_OK, 0, 0, ())
    if applicable == 0:
        return CurveEffectAvailabilitySummary(
            CURVE_EFFECT_NOT_APPLICABLE, 0, 0, tuple(exempt_reasons)
        )
    if unavailable == 0:
        return CurveEffectAvailabilitySummary(CURVE_EFFECT_OK, 0, applicable, ())
    status = CURVE_EFFECT_UNAVAILABLE if unavailable == applicable else CURVE_EFFECT_PARTIAL
    return CurveEffectAvailabilitySummary(
        status, unavailable, applicable, tuple(unavailable_reasons)
    )


def _escalate_quality_flag(flag: str, *, degraded: bool) -> str:
    """A row whose curve effects are unavailable can never be ``ok``.

    ``_quality_flag`` only measures residual closure, and a structurally zeroed effect
    closes the bridge just as well as a correct one — that is precisely how the missing
    curve stayed invisible. Escalation is one-way: an existing ``error`` is never
    softened.
    """
    if degraded and flag == "ok":
        return "warning"
    return flag


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
    market_value_base_missing_diagnostic: str | None = None,
    roll_down_window_missing_diagnostic: str | None = None,
    roll_down_flat_extrapolation_diagnostic: str | None = None,
    treasury_curve_diagnostic: str | None = None,
    credit_spread_curve_diagnostic: str | None = None,
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
    if market_value_base_missing_diagnostic:
        diagnostics.append(market_value_base_missing_diagnostic)
    if roll_down_window_missing_diagnostic:
        diagnostics.append(roll_down_window_missing_diagnostic)
    if roll_down_flat_extrapolation_diagnostic:
        diagnostics.append(roll_down_flat_extrapolation_diagnostic)
    if treasury_curve_diagnostic:
        diagnostics.append(treasury_curve_diagnostic)
    if credit_spread_curve_diagnostic:
        diagnostics.append(credit_spread_curve_diagnostic)
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
    market_value = _coerce_decimal(_first_available_value(row, _MARKET_VALUE_KEYS))
    accrued_interest = _coerce_decimal(_first_available_value(row, _ACCRUED_INTEREST_KEYS))
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


__all__ = [
    "CREDIT_SPREAD_CURVE_SAME_SOURCE_PREFIX",
    "CREDIT_SPREAD_CURVE_UNAVAILABLE_PREFIX",
    "CURVE_EFFECT_DEGRADED_PREFIXES",
    "CURVE_EFFECT_NOT_APPLICABLE",
    "CURVE_EFFECT_OK",
    "CURVE_EFFECT_PARTIAL",
    "CURVE_EFFECT_REASON_BALANCE_ROW_MISSING",
    "CURVE_EFFECT_REASON_CURVE_UNAVAILABLE",
    "CURVE_EFFECT_REASON_MARKET_VALUE_BASE_MISSING",
    "CURVE_EFFECT_REASON_NO_CURVE_SENSITIVITY",
    "CURVE_EFFECT_REASON_NON_FVTPL_BASIS",
    "CURVE_EFFECT_REASON_NOT_CREDIT_BOOK",
    "CURVE_EFFECT_REASON_ROLL_WINDOW_MISSING",
    "CURVE_EFFECT_REASON_SAME_SOURCE_CURVE",
    "CURVE_EFFECT_REASON_TENOR_OUTSIDE_CURVE",
    "CURVE_EFFECT_UNAVAILABLE",
    "CurveEffectAvailabilitySummary",
    "MARKET_VALUE_BASE_MISSING_PREFIX",
    "PnlBridgeRow",
    "ROLL_DOWN_TENOR_OUTSIDE_CURVE_PREFIX",
    "ROLL_DOWN_WINDOW_MISSING_PREFIX",
    "TREASURY_CURVE_SAME_SOURCE_PREFIX",
    "TREASURY_CURVE_UNAVAILABLE_PREFIX",
    "build_pnl_bridge_rows",
    "required_curve_types_for_pnl_bridge",
    "summarize_curve_effect_availability",
]
