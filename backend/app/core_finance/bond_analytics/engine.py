"""Pure bond-analytics calculations from snapshot rows."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.core_finance.bond_analytics.common import (
    ACCOUNTING_BASIS_RISK_CLASS_RULE_IDS,
    DURATION_TERM_MATURITY_UNAVAILABLE,
    DURATION_TERM_NO_REMAINING_TERM,
    DURATION_UNAVAILABLE,
    MISSING_MATURITY_RULE_ID,
    YTM_PAR_FALLBACK_RULE_ID,
    classify_asset_class,
    compute_macaulay_duration_and_convexity,
    estimate_modified_duration,
    get_accounting_rule_trace,
    get_tenor_bucket,
    map_accounting_basis_to_risk_class,
    map_accounting_class,
    resolve_ytm_with_par_fallback,
    safe_decimal,
)
from backend.app.core_finance.interest_mode import (
    classify_interest_rate_style,
    coupon_frequency_per_year,
    resolve_interest_payment_frequency,
)

logger = logging.getLogger(__name__)

MISSING_SOURCE_VERSION = "sv_bond_analytics_snapshot_missing"
ENGINE_RULE_VERSION = "rv_bond_analytics_engine_v1"
MISSING_INGEST_BATCH_ID = "ib_bond_analytics_missing"
_FORMAL_CNY_AMOUNT_FIELDS = (
    "face_value_cny",
    "market_value_cny",
    "amortized_cost_cny",
    "accrued_interest_cny",
)
# 假设口径聚合告警中最多列出的债券代码数，超出以“…共 N 只”收尾（防日志爆炸）。
_DISCLOSURE_LOG_CODE_LIMIT = 20

# 利率输入可得性分级：把「真实 0」「缺失」「脏值」三类彻底分开。
# 归一后为 0 的零息券是合法观测值（observed），与 None 不同；
# ``normalize_percent_rate_to_decimal`` 对 >20%、负数、非数值返回 None，
# 这类脏值同样不是观测值，只是与「字段为空」的成因不同。
RATE_INPUT_STATUS_OBSERVED = "observed"
RATE_INPUT_STATUS_MISSING = "missing"
RATE_INPUT_STATUS_DIRTY = "dirty"

# 行级久期/DV01/凸性输入质量标记：消费方据此判断该行三项指标是否有观测支撑。
# observed             —— 票息与 ytm 均为观测值（含真实零息 coupon=0），常规计算。
# ytm_par_fallback     —— 有票息、ytm 缺失/脏值/非正，按 par 假设（ytm=coupon）计算。
# ytm_unavailable      —— 零息券缺 ytm：Macaulay=剩余年限本就正确，但修正久期未折现、
#                         凸性退化为 D²，属近似值。
# coupon_unavailable   —— 票息缺失/脏值：久期退化为「剩余年限」这一零息代理，
#                         该行久期/DV01/凸性不可当作正式风险指标使用。
# no_remaining_term    —— 到期日可得且 <= 报告日：已到期，久期真的是 0。
# maturity_unavailable —— 到期日缺失：久期**不适用**（该行多半根本不是债券），
#                         三项指标按 DURATION_UNAVAILABLE(0) 记，但那是「不可用」标记
#                         而非观测到的零久期。聚合层必须整行移出久期分母并单独披露。
#
# W-fi-2026-08 P2：后两者此前共用 no_remaining_term 一个标记，把「已到期的债」和
# 「根本没有到期日的基金」混在一起，消费方无从区分。字面量与
# ``bond_analytics.common`` 的 DURATION_TERM_* 同源，三条路径共用一套词表。
DURATION_QUALITY_OBSERVED = "observed"
DURATION_QUALITY_YTM_PAR_FALLBACK = "ytm_par_fallback"
DURATION_QUALITY_YTM_UNAVAILABLE = "ytm_unavailable"
DURATION_QUALITY_COUPON_UNAVAILABLE = "coupon_unavailable"
DURATION_QUALITY_NO_REMAINING_TERM = DURATION_TERM_NO_REMAINING_TERM
DURATION_QUALITY_MATURITY_UNAVAILABLE = DURATION_TERM_MATURITY_UNAVAILABLE

COUPON_UNAVAILABLE_RULE_ID = "duration_coupon_unavailable_proxy_v1"


class FormalCNYClosureError(ValueError):
    """Raised when a foreign-currency row lacks a complete CNY closure."""

    def __init__(
        self,
        *,
        report_date: date,
        instrument_code: str,
        currency_code: str,
        missing_fields: tuple[str, ...] = (),
        invalid_fields: tuple[str, ...] = (),
    ) -> None:
        self.report_date = report_date
        self.instrument_code = instrument_code
        self.currency_code = currency_code
        self.missing_fields = tuple(missing_fields)
        self.invalid_fields = tuple(invalid_fields)

        details: list[str] = []
        if self.missing_fields:
            details.append(f"missing fields={','.join(self.missing_fields)}")
        if self.invalid_fields:
            details.append(f"invalid fields={','.join(self.invalid_fields)}")
        if not details:
            details.append("missing/invalid fields=unknown")
        super().__init__(
            "formal CNY closure unavailable: "
            f"report_date={report_date.isoformat()}, "
            f"instrument_code={instrument_code or '<unknown>'}, "
            f"currency={currency_code or '<unknown>'}; "
            + "; ".join(details)
        )


@dataclass(slots=True)
class _AssumptionDisclosure:
    """按假设口径（而非观测值）计算的行的聚合披露累加器：行数 / 市值 / 债券代码。"""

    row_count: int = 0
    market_value: Decimal = Decimal("0")
    instrument_codes: list[str] = field(default_factory=list)

    def record(self, *, instrument_code: str, market_value: Decimal) -> None:
        self.row_count += 1
        self.market_value += market_value
        self.instrument_codes.append(instrument_code or "<unknown>")


@dataclass(slots=True, frozen=True)
class BondAnalyticsRow:
    """Per-bond analytics row derived from a standardized zqtz snapshot row."""

    report_date: date
    instrument_code: str
    instrument_name: str
    portfolio_name: str
    cost_center: str
    asset_class_raw: str
    asset_class_std: str
    bond_type: str
    issuer_name: str
    industry_name: str
    rating: str
    accounting_class: str
    accounting_rule_id: str
    currency_code: str
    face_value: Decimal
    market_value_native: Decimal
    market_value: Decimal
    amortized_cost: Decimal
    accrued_interest: Decimal
    coupon_rate: Decimal | None
    interest_mode: str
    interest_payment_frequency: str
    interest_rate_style: str
    ytm: Decimal | None
    maturity_date: date | None
    next_call_date: date | None
    years_to_maturity: Decimal
    tenor_bucket: str
    macaulay_duration: Decimal
    modified_duration: Decimal
    convexity: Decimal
    dv01: Decimal
    is_credit: bool
    spread_dv01: Decimal
    source_version: str
    rule_version: str
    ingest_batch_id: str
    trace_id: str
    value_date: date | None = None
    interest_payment_frequency_fallback_used: bool | None = None
    # 诚实性披露（W-fi-2026-08 P1 后续）：区分票息/ytm 的「真实 0」「缺失」「脏值」，
    # 并声明该行久期/DV01/凸性是观测值支撑还是假设值支撑。默认值只服务于
    # 直接构造 BondAnalyticsRow 的测试/夹具，引擎始终显式赋值。
    coupon_rate_input_status: str = RATE_INPUT_STATUS_OBSERVED
    ytm_input_status: str = RATE_INPUT_STATUS_OBSERVED
    duration_quality_flag: str = DURATION_QUALITY_OBSERVED


def compute_bond_analytics_rows(
    snapshot_rows: list[dict[str, Any]],
    report_date: date,
) -> list[BondAnalyticsRow]:
    """Project canonical snapshot rows into pure-compute bond analytics rows."""

    analytics_rows: list[BondAnalyticsRow] = []
    ytm_par_fallback = _AssumptionDisclosure()
    coupon_unavailable = _AssumptionDisclosure()
    maturity_unavailable = _AssumptionDisclosure()
    for index, snapshot_row in enumerate(snapshot_rows):
        if _coerce_bool(snapshot_row.get("is_issuance_like")):
            continue

        row_report_date = _resolve_report_date(
            expected_report_date=report_date,
            value=snapshot_row.get("report_date"),
        )
        instrument_code = _as_text(snapshot_row.get("instrument_code"))
        instrument_name = _as_text(snapshot_row.get("instrument_name"))
        asset_class_raw = _as_text(snapshot_row.get("asset_class"))
        bond_type = _as_text(snapshot_row.get("bond_type"))
        accounting_source = _first_non_blank(
            snapshot_row.get("account_category"),
            asset_class_raw,
        )
        asset_class_surface = " ".join(
            part
            for part in (asset_class_raw, bond_type, instrument_name)
            if part
        )
        asset_class_std = classify_asset_class(asset_class_surface)
        accounting_class_from_basis = map_accounting_basis_to_risk_class(
            _as_text(snapshot_row.get("accounting_basis"))
        )
        if accounting_class_from_basis is not None:
            accounting_class = accounting_class_from_basis
            accounting_rule_id = ACCOUNTING_BASIS_RISK_CLASS_RULE_IDS[accounting_class]
        else:
            accounting_class = map_accounting_class(accounting_source)
            accounting_rule_id, _ = get_accounting_rule_trace(accounting_source)

        coupon_rate, coupon_rate_input_status = _classify_rate_input(
            snapshot_row.get("coupon_rate")
        )
        interest_mode = _as_text(snapshot_row.get("interest_mode"))
        interest_payment_frequency, interest_payment_frequency_fallback_used = resolve_interest_payment_frequency(interest_mode)
        coupon_frequency = coupon_frequency_per_year(interest_mode)
        interest_rate_style = classify_interest_rate_style(interest_mode)
        ytm, ytm_input_status = _classify_rate_input(snapshot_row.get("ytm_value"))
        maturity_date = _coerce_date(snapshot_row.get("maturity_date"))
        years_to_maturity = _compute_years_to_maturity(
            report_date=report_date,
            maturity_date=maturity_date,
        )
        currency_code = _as_text(snapshot_row.get("currency_code"))
        formal_cny_amounts = (
            _validate_formal_cny_closure(
                snapshot_row=snapshot_row,
                report_date=report_date,
                instrument_code=instrument_code,
                currency_code=currency_code,
            )
            if not _is_cny_currency(currency_code)
            else {}
        )
        face_value_native = safe_decimal(snapshot_row.get("face_value_native"))
        face_value = formal_cny_amounts.get("face_value_cny", face_value_native)
        market_value_native = safe_decimal(snapshot_row.get("market_value_native"))
        market_value = formal_cny_amounts.get("market_value_cny", market_value_native)
        amortized_cost_native = safe_decimal(snapshot_row.get("amortized_cost_native"))
        amortized_cost = _select_cny_amount(
            currency_code=currency_code,
            cny_value=formal_cny_amounts.get("amortized_cost_cny"),
            native_value=amortized_cost_native,
        )
        accrued_interest_native = safe_decimal(snapshot_row.get("accrued_interest_native"))
        accrued_interest = _select_cny_amount(
            currency_code=currency_code,
            cny_value=formal_cny_amounts.get("accrued_interest_cny"),
            native_value=accrued_interest_native,
        )
        if years_to_maturity == Decimal("0"):
            # 缺到期日与已到期都没有可用的剩余期限，数值同为 DURATION_UNAVAILABLE(0)，
            # 但成因完全不同，必须分开标记：已到期的债久期真的是 0；缺到期日的行
            # 久期不适用，0 只是「不可用」标记。取值定义见
            # ``common.resolve_missing_maturity_duration``（三条路径唯一常数出处）。
            macaulay_duration = DURATION_UNAVAILABLE
            modified_duration = DURATION_UNAVAILABLE
            convexity = DURATION_UNAVAILABLE
            dv01 = DURATION_UNAVAILABLE
            if maturity_date is None:
                duration_quality_flag = DURATION_QUALITY_MATURITY_UNAVAILABLE
                maturity_unavailable.record(
                    instrument_code=instrument_code,
                    market_value=market_value,
                )
            else:
                duration_quality_flag = DURATION_QUALITY_NO_REMAINING_TERM
        else:
            # 缺失/脏值的票息与 ytm 在算式入口仍按 0 代入（保持既有数值行为），
            # 但不再静默：duration_quality_flag 逐行声明该行三项指标究竟由观测值
            # 还是假设值支撑，缺失与脏值再由 *_input_status 进一步区分。
            coupon_rate_for_math = coupon_rate if coupon_rate is not None else Decimal("0")
            ytm_for_math = ytm if ytm is not None else Decimal("0")
            # W-fi-2026-08 P1：有票息缺 ytm 的行按 par 假设（ytm=coupon）计算
            # 久期/修正久期/凸性，三项指标共用同一生效 ytm 口径；
            # ytm>0 正常路径 effective_ytm == ytm，行为不变。
            effective_ytm, ytm_par_fallback_used = resolve_ytm_with_par_fallback(
                coupon_rate_for_math,
                ytm_for_math,
            )
            duration_quality_flag = _resolve_duration_quality_flag(
                coupon_rate_input_status=coupon_rate_input_status,
                ytm_input_status=ytm_input_status,
                ytm_par_fallback_used=ytm_par_fallback_used,
            )
            if ytm_par_fallback_used:
                ytm_par_fallback.record(
                    instrument_code=instrument_code,
                    market_value=market_value,
                )
            if duration_quality_flag == DURATION_QUALITY_COUPON_UNAVAILABLE:
                coupon_unavailable.record(
                    instrument_code=instrument_code,
                    market_value=market_value,
                )
            # W-fi-2026-08 P4：久期与标准现金流凸性由同一次现金流遍历产出，
            # 保证两者恒基于同一组 (时点, 金额)。此处不再走 estimate_duration
            # 外壳：缺到期日/已到期已由上面的 years_to_maturity == 0 分支处理，
            # 且 years_to_maturity 与该外壳内部的 (到期日-报告日)/365 同式同值。
            # bullet（到期一次还本付息）唯一现金流落在到期日：不得按年付虚构
            # 中途票息现金流（那会把 Macaulay 拉向票息时点、低估久期），
            # 与 cashflow_projection 的 bullet 单笔建模同口径。
            macaulay_duration, convexity = compute_macaulay_duration_and_convexity(
                coupon_rate=coupon_rate_for_math,
                ytm=effective_ytm,
                years_to_maturity=years_to_maturity,
                coupon_frequency=coupon_frequency,
                single_cashflow_at_maturity=interest_payment_frequency == "bullet",
            )
            modified_duration = estimate_modified_duration(
                macaulay_duration,
                effective_ytm,
                coupon_frequency=coupon_frequency,
            )
            dv01 = face_value * modified_duration / Decimal("10000")
        is_credit = asset_class_std == "credit"

        analytics_rows.append(
            BondAnalyticsRow(
                report_date=row_report_date,
                instrument_code=instrument_code,
                instrument_name=instrument_name,
                portfolio_name=_as_text(snapshot_row.get("portfolio_name")),
                cost_center=_as_text(snapshot_row.get("cost_center")),
                asset_class_raw=asset_class_raw,
                asset_class_std=asset_class_std,
                bond_type=bond_type,
                issuer_name=_as_text(snapshot_row.get("issuer_name")),
                industry_name=_as_text(snapshot_row.get("industry_name")),
                rating=_as_text(snapshot_row.get("rating")),
                accounting_class=accounting_class,
                accounting_rule_id=accounting_rule_id,
                currency_code=currency_code,
                face_value=face_value,
                market_value_native=market_value_native,
                market_value=market_value,
                amortized_cost=amortized_cost,
                accrued_interest=accrued_interest,
                coupon_rate=coupon_rate,
                interest_mode=interest_mode,
                interest_payment_frequency=interest_payment_frequency,
                interest_payment_frequency_fallback_used=interest_payment_frequency_fallback_used,
                interest_rate_style=interest_rate_style,
                ytm=ytm,
                maturity_date=maturity_date,
                next_call_date=_coerce_date(snapshot_row.get("next_call_date")),
                years_to_maturity=years_to_maturity,
                tenor_bucket=get_tenor_bucket(float(years_to_maturity)),
                macaulay_duration=macaulay_duration,
                modified_duration=modified_duration,
                convexity=convexity,
                dv01=dv01,
                is_credit=is_credit,
                spread_dv01=dv01 if is_credit else Decimal("0"),
                source_version=_first_non_blank(
                    snapshot_row.get("source_version"),
                    MISSING_SOURCE_VERSION,
                ),
                rule_version=_first_non_blank(
                    snapshot_row.get("rule_version"),
                    ENGINE_RULE_VERSION,
                ),
                ingest_batch_id=_first_non_blank(
                    snapshot_row.get("ingest_batch_id"),
                    MISSING_INGEST_BATCH_ID,
                ),
                trace_id=_first_non_blank(
                    snapshot_row.get("trace_id"),
                    f"trace_bond_analytics_{instrument_code or 'row'}_{index}",
                ),
                value_date=_coerce_date(snapshot_row.get("value_date")),
                coupon_rate_input_status=coupon_rate_input_status,
                ytm_input_status=ytm_input_status,
                duration_quality_flag=duration_quality_flag,
            )
        )

    if ytm_par_fallback.row_count:
        # 聚合级披露（行级标记见 duration_quality_flag，尚未落库）：本批有票息但 ytm
        # 缺失/非正的行按 par 假设计算久期/DV01；附回退债券代码清单便于排查。
        logger.warning(
            "compute_bond_analytics_rows: %d coupon-bond rows with missing/non-positive ytm "
            "used par-assumption duration (rule_id=%s, ytm=coupon_rate); "
            "market_value_cny=%s report_date=%s instrument_codes=%s",
            ytm_par_fallback.row_count,
            YTM_PAR_FALLBACK_RULE_ID,
            ytm_par_fallback.market_value,
            report_date.isoformat(),
            _format_disclosure_instrument_codes(ytm_par_fallback.instrument_codes),
        )

    if maturity_unavailable.row_count:
        # 缺到期日：久期/修正久期/凸性/DV01 全部不可得，按 DURATION_UNAVAILABLE 记 0。
        # 这不是「久期为 0 的债」，多半根本不是债券（2026-07-31 实测 127 笔 / 434.00 亿
        # 全是公募基金与 ETF）。消费方必须整行移出久期分母并单独披露 —— 正面样板见
        # ``risk_tensor.missing_maturity_count`` / ``missing_maturity_market_value``。
        logger.warning(
            "compute_bond_analytics_rows: %d rows without maturity_date have NO available "
            "duration (rule_id=%s, duration_quality_flag=%s); duration/modified_duration/"
            "convexity/dv01 are recorded as %s = UNAVAILABLE marker, not an observed zero — "
            "exclude them from the duration denominator and disclose separately; "
            "market_value_cny=%s report_date=%s instrument_codes=%s",
            maturity_unavailable.row_count,
            MISSING_MATURITY_RULE_ID,
            DURATION_QUALITY_MATURITY_UNAVAILABLE,
            DURATION_UNAVAILABLE,
            maturity_unavailable.market_value,
            report_date.isoformat(),
            _format_disclosure_instrument_codes(maturity_unavailable.instrument_codes),
        )

    if coupon_unavailable.row_count:
        # 票息缺失/脏值：这些行的久期只是「剩余年限」零息代理，DV01/凸性同源，
        # 不得当作观测支撑的正式风险指标；行级标记为 coupon_unavailable。
        logger.warning(
            "compute_bond_analytics_rows: %d rows with missing/dirty coupon_rate produced "
            "remaining-term duration proxy (rule_id=%s, duration_quality_flag=%s); "
            "their duration/DV01/convexity are assumption-based, not observation-backed; "
            "market_value_cny=%s report_date=%s instrument_codes=%s",
            coupon_unavailable.row_count,
            COUPON_UNAVAILABLE_RULE_ID,
            DURATION_QUALITY_COUPON_UNAVAILABLE,
            coupon_unavailable.market_value,
            report_date.isoformat(),
            _format_disclosure_instrument_codes(coupon_unavailable.instrument_codes),
        )

    return analytics_rows


def _resolve_duration_quality_flag(
    *,
    coupon_rate_input_status: str,
    ytm_input_status: str,
    ytm_par_fallback_used: bool,
) -> str:
    """按输入可得性给该行久期/DV01/凸性定级（取最严重的一项）。

    票息未知最严重：``estimate_duration`` 在 ``coupon_rate<=0`` 时直接返回剩余
    年限（零息假设），对真正的付息债会系统性高估久期与 DV01，且无法由 ytm 补救。
    """
    if coupon_rate_input_status != RATE_INPUT_STATUS_OBSERVED:
        return DURATION_QUALITY_COUPON_UNAVAILABLE
    if ytm_par_fallback_used:
        return DURATION_QUALITY_YTM_PAR_FALLBACK
    if ytm_input_status != RATE_INPUT_STATUS_OBSERVED:
        return DURATION_QUALITY_YTM_UNAVAILABLE
    return DURATION_QUALITY_OBSERVED


def _format_disclosure_instrument_codes(codes: list[str]) -> str:
    """去重保序后最多列 20 个披露债券代码，超出以“…共 N 只”收尾（N 为去重后总只数）。"""
    unique_codes = list(dict.fromkeys(codes))
    shown = ",".join(unique_codes[:_DISCLOSURE_LOG_CODE_LIMIT])
    if len(unique_codes) > _DISCLOSURE_LOG_CODE_LIMIT:
        return f"{shown}…共 {len(unique_codes)} 只"
    return shown


def _compute_years_to_maturity(*, report_date: date, maturity_date: date | None) -> Decimal:
    if maturity_date is None:
        return Decimal("0")
    remaining_days = (maturity_date - report_date).days
    if remaining_days <= 0:
        return Decimal("0")
    return Decimal(str(remaining_days)) / Decimal("365")


def _resolve_report_date(*, expected_report_date: date, value: Any) -> date:
    row_report_date = _coerce_date(value)
    if row_report_date is None:
        return expected_report_date
    if row_report_date != expected_report_date:
        raise ValueError(
            f"snapshot row report_date {row_report_date.isoformat()} does not match "
            f"requested report_date {expected_report_date.isoformat()}"
        )
    return row_report_date


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_non_blank(*values: Any) -> str:
    for value in values:
        text = _as_text(value)
        if text:
            return text
    return ""


def _is_cny_currency(value: str) -> bool:
    return value.upper() in {"CNY", "RMB", "CNH"}


def _validate_formal_cny_closure(
    *,
    snapshot_row: dict[str, Any],
    report_date: date,
    instrument_code: str,
    currency_code: str,
) -> dict[str, Decimal]:
    parsed: dict[str, Decimal] = {}
    missing_fields: list[str] = []
    invalid_fields: list[str] = []

    for field_name in _FORMAL_CNY_AMOUNT_FIELDS:
        raw_value = snapshot_row.get(field_name)
        if raw_value is None or not str(raw_value).strip():
            missing_fields.append(field_name)
            continue
        try:
            value = raw_value if isinstance(raw_value, Decimal) else Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError):
            invalid_fields.append(field_name)
            continue
        if not value.is_finite():
            invalid_fields.append(field_name)
            continue
        parsed[field_name] = value

    if missing_fields or invalid_fields:
        raise FormalCNYClosureError(
            report_date=report_date,
            instrument_code=instrument_code,
            currency_code=currency_code,
            missing_fields=tuple(missing_fields),
            invalid_fields=tuple(invalid_fields),
        )
    return parsed


def _select_cny_amount(*, currency_code: str, cny_value: Any, native_value: Decimal) -> Decimal:
    if _is_cny_currency(currency_code):
        return native_value
    if cny_value is None or str(cny_value).strip() == "":
        raise ValueError("formal CNY closure unavailable: non-CNY amount is missing")
    return safe_decimal(cny_value)


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return safe_decimal(value)


def _normalize_rate_decimal(value: Any) -> Decimal | None:
    """Normalize a snapshot annual rate (percent caliber) to decimal form.

    ``zqtz_bond_daily_snapshot.coupon_rate`` / ``ytm_value`` are stored as
    percent values (1.82 = 1.82%; evidenced in
    docs/audits/2026-07-19-system-calculation-audit.md, 取证 1), so the value is
    unconditionally divided by 100 via
    ``rate_units.normalize_percent_rate_to_decimal`` (> 20, i.e. rates above
    20%, rejected as dirty data). The previous > 2 heuristic silently treated
    the [0.2, 2) low-coupon gray zone (~550 bonds per day) as decimal-form
    rates, corrupting duration/DV01 on re-materialization.
    """
    from backend.app.core_finance.rate_units import normalize_percent_rate_to_decimal

    normalized = normalize_percent_rate_to_decimal(value)
    if normalized is None:
        return None
    return Decimal(str(normalized))


def _classify_rate_input(value: Any) -> tuple[Decimal | None, str]:
    """归一利率并区分「真实 0」「缺失」「脏值」三类输入。

    - 归一成功（含零息券的真实 0）→ ``(值, observed)``；
    - 字段为 ``None`` / 空串 → ``(None, missing)``；
    - 有值但被 ``normalize_percent_rate_to_decimal`` 拒绝（>20%、负数、非数值）
      → ``(None, dirty)``。

    缺失与脏值的归一结果同为 ``None``，数值路径一致，但成因不同：缺失指向上游
    补数，脏值指向源数据清洗，必须分别可见。
    """
    normalized = _normalize_rate_decimal(value)
    if normalized is not None:
        return normalized, RATE_INPUT_STATUS_OBSERVED
    if value is None or not str(value).strip():
        return None, RATE_INPUT_STATUS_MISSING
    return None, RATE_INPUT_STATUS_DIRTY


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text)


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y"}
    return bool(value)


__all__ = [
    "COUPON_UNAVAILABLE_RULE_ID",
    "DURATION_QUALITY_COUPON_UNAVAILABLE",
    "DURATION_QUALITY_NO_REMAINING_TERM",
    "DURATION_QUALITY_OBSERVED",
    "DURATION_QUALITY_YTM_PAR_FALLBACK",
    "DURATION_QUALITY_YTM_UNAVAILABLE",
    "RATE_INPUT_STATUS_DIRTY",
    "RATE_INPUT_STATUS_MISSING",
    "RATE_INPUT_STATUS_OBSERVED",
    "BondAnalyticsRow",
    "ENGINE_RULE_VERSION",
    "FormalCNYClosureError",
    "MISSING_INGEST_BATCH_ID",
    "MISSING_SOURCE_VERSION",
    "compute_bond_analytics_rows",
]
