"""Shared utilities for bond analytics calculations."""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from backend.app.core_finance.cashflow_projection import _add_months, _coupon_dates_between
from backend.app.core_finance.config.classification_rules import infer_invest_type
from backend.app.core_finance.field_normalization import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    ACCOUNTING_BASIS_FVTPL,
    derive_accounting_basis_value,
)
from backend.app.core_finance.safe_decimal import safe_decimal as _core_safe_decimal
from backend.app.core_finance.zqtz_asset_bond_category import ZQTZ_ASSET_BOND_ROWS

logger = logging.getLogger(__name__)

# --- Decimal helpers ---

# 身份哨兵：共享实现在任何回退分支都原样返回 ``default`` 对象，据此区分
# "转换失败回退 0" 与 "输入本就是 0"。取值仍为 Decimal("0")，即使将来共享实现
# 不再返回同一对象，也只会漏掉日志而不会改变返回值。
_CONVERSION_FALLBACK = Decimal("0")


def safe_decimal(value) -> Decimal:
    """Bond-analytics 侧入口，委托 ``core_finance.safe_decimal`` 取值。

    共享实现已覆盖 None / NaN / Infinity / numpy 标量 / 空串等全部缺省语义；
    本包历史上按 ERROR 级披露转换失败（共享实现按 warning 级），保留该级别。
    None 属于常规缺失输入，与历史行为一致地静默归 0。
    """
    if value is None:
        return Decimal("0")
    result = _core_safe_decimal(value, default=_CONVERSION_FALLBACK)
    if result is _CONVERSION_FALLBACK:
        logger.error("safe_decimal: failed to convert %r", type(value).__name__)
        return Decimal("0")
    return result


def decimal_to_str(value: Decimal) -> str:
    return (
        str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        if isinstance(value, Decimal)
        else str(value)
    )


# --- Asset classification ---

RATE_KEYWORDS = ("国债", "国开", "政金", "政策性", "地方政府", "央票", "treasury", "government", "policy")
CREDIT_KEYWORDS = (
    "企业债",
    "公司债",
    "信用债",
    "商业银行债",
    "次级债",
    "资产支持证券",
    "中票",
    "短融",
    "超短融",
    "ppn",
    "abs",
    "corporate",
    "credit",
) + tuple(
    keyword.lower()
    for definition in ZQTZ_ASSET_BOND_ROWS
    if definition["row_key"] in {
        "asset_zqtz_commercial_financial_bond",
        "asset_zqtz_interbank_cd",
        "asset_zqtz_nonfinancial_enterprise_bond",
        "asset_zqtz_abs",
    }
    for keyword in definition["match_keywords"]
)
CDB_KEYWORDS = ("国开", "政策性", "政金", "cdb", "policy bank")


def classify_asset_class(sub_type: str) -> str:
    lower = (sub_type or "").lower()
    for kw in RATE_KEYWORDS:
        if kw in lower:
            return "rate"
    for kw in CREDIT_KEYWORDS:
        if kw in lower:
            return "credit"
    return "other"


def infer_curve_type(*surfaces: object) -> str:
    combined = " ".join(str(surface or "").lower() for surface in surfaces)
    if any(keyword in combined for keyword in CDB_KEYWORDS):
        return "cdb"
    return "treasury"


# --- Accounting classification ---

# Fallback patterns when ``infer_invest_type`` returns None (e.g. bare ``AC`` token).
# W-bond-2026-04-21: H/A/T labels delegate to canonical ``hat_mapping`` via
# ``infer_invest_type``; rows for 持有至到期 / 可供出售 were removed as redundant.
ACCOUNTING_RULES = [
    {"rule_id": "R002", "pattern": "摊余成本", "result": "AC"},
    {"rule_id": "R003", "pattern": "HTM", "result": "AC"},
    {"rule_id": "R004", "pattern": "AC", "result": "AC"},
    {"rule_id": "R011", "pattern": "其他债权", "result": "OCI"},
    {"rule_id": "R012", "pattern": "FVOCI", "result": "OCI"},
    {"rule_id": "R013", "pattern": "OCI", "result": "OCI"},
    {"rule_id": "R020", "pattern": "交易性", "result": "TPL"},
    {"rule_id": "R021", "pattern": "FVTPL", "result": "TPL"},
    {"rule_id": "R022", "pattern": "TPL", "result": "TPL"},
]

ACCOUNTING_BASIS_RISK_CLASS_RULE_IDS = {
    "AC": "R001",
    "OCI": "R010",
    "TPL": "R020",
}


def map_accounting_basis_to_risk_class(accounting_basis: str | None) -> str | None:
    normalized = str(accounting_basis or "").strip().upper()
    if normalized == ACCOUNTING_BASIS_AC:
        return "AC"
    if normalized in {ACCOUNTING_BASIS_FVOCI, "OCI"}:
        return "OCI"
    if normalized in {ACCOUNTING_BASIS_FVTPL, "TPL"}:
        return "TPL"
    return None


def map_accounting_class(asset_class: str) -> str:
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
    upper = asset_class.upper()
    for rule in ACCOUNTING_RULES:
        if rule["pattern"].upper() in upper:
            return rule["result"]
    return "other"


def infer_accounting_class(asset_class: str) -> str:
    return map_accounting_class(asset_class)


def get_accounting_rule_trace(asset_class: str) -> tuple[str, str | None]:
    """Return (rule_id, representative_pattern) for the asset_class match.

    The Chinese-label *return values* below are output-side trace literals
    that name the matched canonical bucket; they are NOT input-side
    classifiers (those live in ``classification_rules.infer_invest_type``).
    Audit ``hat_mapping/accounting_class_substring`` flags them as a regex
    false positive — see W-final-2026-04-21 docstring on
    ``calibers.rules.hat_mapping``.
    Human: caliber-hat_mapping-justified (output trace literals, not filters).
    """
    if not asset_class:
        return "R999", None
    invest = infer_invest_type(None, None, asset_class)
    if invest == "H":
        return "R001", "持有至到期"
    if invest == "A":
        return "R010", "可供出售"
    if invest == "T":
        return "R020", "交易性"
    upper = asset_class.upper()
    for rule in ACCOUNTING_RULES:
        if rule["pattern"].upper() in upper:
            return rule["rule_id"], rule["pattern"]
    return "R999", None


# --- Duration estimation ---

YTM_PAR_FALLBACK_RULE_ID = "ytm_par_fallback_duration_v1"
MISSING_MATURITY_RULE_ID = "duration_maturity_unavailable_v1"

# 剩余期限输入的可得性分级。三条久期路径（bond_duration.estimate_duration /
# bond_analytics.common.estimate_duration / bond_analytics.engine）共用这一套字面量，
# 消费方只需认一套词表。
#
# observed             —— 到期日与报告日均可得，久期由剩余期限算出。
# no_remaining_term    —— 到期日可得且 <= 报告日：已到期，久期真的是 0。
# maturity_unavailable —— 到期日（或报告日）缺失：久期**不适用**，不是 0。
DURATION_TERM_OBSERVED = "observed"
DURATION_TERM_NO_REMAINING_TERM = "no_remaining_term"
DURATION_TERM_MATURITY_UNAVAILABLE = "maturity_unavailable"

# 缺到期日时久期不可得。历史调用方（krd / credit_spread / pnl_bridge /
# bond_four_effects / cashflow_projection）都直接对返回值做 Decimal 算术，返回
# None 会让它们全部 TypeError，因此数值契约仍是 Decimal；但取值必须是 0，不是
# 任何正的占位常数：
#
#   0    → 不生成久期敞口，也不生成 DV01/凸性敞口，聚合层可按披露口径整行剔除；
#   3.0  → 凭空给非债券编 3 年久期（2026-07-31 实测抬高组合加权久期 0.3804 年）；
#   0.25 → 凭空给非债券编 3 个月久期（同日实测凭空造出 106.47 万/bp 的 DV01）。
#
# 想区分「久期确实是 0（已到期）」与「久期不适用（缺到期日）」的调用方，请改用
# ``estimate_duration_with_status``：它在不可得时返回 ``(None, maturity_unavailable)``。
# 正面样板见 ``core_finance/risk_tensor.py``：缺到期日的行整行移出久期分母，
# 另由 ``missing_maturity_count`` / ``missing_maturity_market_value`` 单独披露。
DURATION_UNAVAILABLE = Decimal("0")


def resolve_missing_maturity_duration(
    *,
    bond_code: str = "",
    maturity_date_missing: bool,
    report_date_missing: bool,
) -> Decimal:
    """缺到期日时久期的**唯一**取值定义（W-fi-2026-08 P2）。

    此前同一批持仓在三条路径上拿到三个答案：事实表物化 0、
    ``bond_duration.estimate_duration`` 0.25（``SA``/``SCP`` 前缀短路）、
    ``bond_analytics.common.estimate_duration`` 3.0（硬编码占位）。三个数散落三处，
    折合 2026-07-31 组合加权久期差 0.3487 年（= (3.0 − 0.25) × 12.68% 缺失市值占比），
    比同期修掉的整期截断 bug（0.0249 年）大一个数量级。

    现在三条路径都必须经过本函数，常数只此一处。
    """
    missing = [
        name
        for name, flag in (("maturity_date", maturity_date_missing), ("report_date", report_date_missing))
        if flag
    ]
    logger.warning(
        "duration unavailable for instrument %s: missing %s (rule_id=%s); "
        "returning %s as an UNAVAILABLE marker, not an observed zero-duration position — "
        "aggregations must exclude this row from the duration denominator and disclose it "
        "separately (see risk_tensor.missing_maturity_count)",
        bond_code or "<unknown>",
        ",".join(missing) or "<unknown>",
        MISSING_MATURITY_RULE_ID,
        DURATION_UNAVAILABLE,
    )
    return DURATION_UNAVAILABLE


def resolve_ytm_with_par_fallback(
    coupon_rate: Decimal,
    ytm: Decimal | None,
) -> tuple[Decimal, bool]:
    """解析久期/修正久期/凸性生效 YTM；缺失时才用 par 假设。

    W-fi-2026-08 P1：有票息但 ytm 缺失的债此前落入零息回退
    （Macaulay=剩余年限），10Y/3% 票息券回退值 10 年 vs par 口径 ≈8.79 年，
    久期与 DV01 被系统性高估。与 bond_duration._estimate_macaulay_duration_years
    的既有口径对齐：按 ytm=coupon_rate（par 假设）走 Macaulay。

    返回 ``(生效 ytm, 是否使用 par 回退)``。所有有限观测值（包括 0 与合法
    负收益率）保留原值；调用方必须以 ``None`` 表示缺失/脏值，不得先折成 0。
    """
    if ytm is not None and ytm.is_finite():
        return ytm, False
    if coupon_rate > 0:
        return coupon_rate, True
    return Decimal("0"), False


# 收益率复利惯例：源字段「到期收益率」是**名义年利率、按付息频率复利**
# （``docs/calc_rules.md`` 的 ``yield_compounding=nominal_annual_with_coupon_frequency``）。
# 该声明已由 ``.tmp-agent/ytm-compounding-empirical.md``（2026-08-13）用真实账本实证：
# 在 63 只由应收/应付利息独立反推为半年付的券上，按 f 复利折现复现摊余成本
# RMSE 0.0100 元/百元、63/63 全胜，年复利 RMSE 0.2621；年复利口径的隐含收益率
# 偏移 +2.77bp 恰等于口径错配的理论值 ``(1+y/2)²−1−y ≈ y²/4`` = +2.96bp。
# 因此 ``f`` **同时**决定现金流时点与折现除数 ``(1 + ytm/f)``，这是正确行为，
# 不得拆成两个参数。
YIELD_COMPOUNDING_CONVENTION = "nominal_annual_with_coupon_frequency"


def _single_cashflow_convexity(
    time_years: Decimal,
    ytm: Decimal,
    coupon_frequency: int,
) -> Decimal:
    """单笔现金流在按 f 复利下的标准凸性：``t(t + 1/f) / (1 + y/f)²``。

    这是标准现金流凸性 ``C = Σ[CF_k·k(k+1)/(1+y/f)^(k+2)]/(P·f²)``（``k`` 为期数）
    在只有一笔现金流时的闭式解，不是近似：现值加权付息时点方差 ``M² = 0``，
    恒等式 ``C = (D² + D/f + M²)/(1+y/f)²`` 退化为 ``t(t + 1/f)/(1+y/f)²``。

    注意分子是 ``t(t + 1/f)`` 而非旧实现的 ``t(t + 1)``——旧式分子与 ``f`` 无关，
    在 ``f = 2`` 下相对零息恒等式对短端系统性高估 ``D/2``。
    ``y = 0`` 处连续（给 ``t(t + 1/f)``），无需 ``D²`` 特判。
    """
    frequency = Decimal(str(coupon_frequency)) if coupon_frequency > 0 else Decimal("1")
    numerator = time_years * (time_years + Decimal("1") / frequency)
    base = Decimal("1") + ytm / frequency
    if base <= 0:
        # ytm <= -f×100%：折现基数非正，``base ** -2`` 无定义。退回未折现的时点项，
        # 保证返回值仍非负且有限；这是护栏，不是口径。
        return numerator
    return numerator / (base**2)


_DAYS_PER_YEAR = Decimal("365")


def whole_period_calendar_merge_tolerance_days(
    nearest_whole_years: Decimal,
    coupon_frequency: int,
) -> Decimal:
    """无日期调用的历史 0.01 期兼容阈值；不能据此推断真实付息日。

    阈值不随期限增长。已知日期的正式路径必须用票息日历，不能用闰日预算吞掉未来票息。
    ``nearest_whole_years`` 保留供既有调用方使用，已不影响阈值。
    """
    frequency = Decimal(str(coupon_frequency)) if coupon_frequency > 0 else Decimal("1")
    return Decimal("0.01") * _DAYS_PER_YEAR / frequency


def whole_period_calendar_merge_applies(
    years_to_maturity: Decimal,
    nearest_periods: int,
    coupon_frequency: int,
) -> bool:
    """仅无日期调用使用的历史小碎期归并；真实日期路径不使用该猜测窗口。"""
    frequency = Decimal(str(coupon_frequency)) if coupon_frequency > 0 else Decimal("1")
    # 直接以期数判定，保持历史精确边界；量化成微天会误判月付的 0.01 期端点。
    fractional_period = years_to_maturity * frequency - Decimal(nearest_periods)
    return Decimal("0") <= fractional_period <= Decimal("0.01")


def compute_macaulay_duration_and_convexity(
    coupon_rate: Decimal,
    ytm: Decimal,
    years_to_maturity: Decimal,
    coupon_frequency: int = 1,
    *,
    single_cashflow_at_maturity: bool = False,
    report_date: date | None = None,
    maturity_date: date | None = None,
) -> tuple[Decimal, Decimal]:
    """一次遍历现金流，同时产出 Macaulay 久期（年）与标准现金流凸性（年²）。

    定义（按付息频率复利，见 ``YIELD_COMPOUNDING_CONVENTION``；``k = t·f`` 为期数）：

        P = Σ CF_k / (1+y/f)^k
        D = Σ t_k · CF_k / (1+y/f)^k / P                      （年）
        C = Σ k(k+1) · CF_k / (1+y/f)^(k+2) / (P · f²)        （年²）

    ``C`` 就是 ``(1/P)·d²P/dy²``（``y`` 为名义年利率），与教科书定义一致；等价恒等式
    ``C = (D² + D/f + M²)/(1+y/f)²``（``M²`` = 现值加权付息时点方差，年²）可用于交叉
    验证。实现里按年单位写作 ``C = Σ t_k(t_k + 1/f)·PV_k / P / (1+y/f)²``，与上式等价
    （``k(k+1)/f² = t_k(t_k + 1/f)``）。

    日期齐全且频率能整除 12 时，复用到期日锚定的票息日历，报告日当天已付票息不再计入。
    保留既有混合时间口径：报告日严格落在票息网格时用 k/f 年；其余日期用实际票息日距
    报告日的 ACT/365 年数。所有分支仍按 (1+y/f)^(t*f) 折现。无日期或不能按月建模的
    频率保留历史等间隔碎期口径，不用随期限增长的容差猜测真实票息日期。

    ``single_cashflow_at_maturity=True`` 声明该券的全部现金流（本金+利息）一次性落在
    到期日（bullet / 到期一次还本付息）：即使票息为正也不得虚构中途付息现金流，
    Macaulay 恒等于剩余年限，凸性取同一时点的单笔闭式解。这与
    ``cashflow_projection`` 的 bullet 建模（单笔 ``_bullet_coupon_amount`` 落在
    到期日）保持同一口径。
    """
    if years_to_maturity <= 0:
        return Decimal("0"), Decimal("0")
    # 零息/无票息：唯一现金流落在到期日，D 恒等于剩余年限，C 有闭式解。
    # bullet（到期一次还本付息）与零息同构：唯一现金流在到期日。
    if single_cashflow_at_maturity or coupon_rate <= 0:
        return years_to_maturity, _single_cashflow_convexity(
            years_to_maturity, ytm, coupon_frequency
        )

    if coupon_frequency <= 0:
        return years_to_maturity, _single_cashflow_convexity(
            years_to_maturity, ytm, coupon_frequency
        )

    frequency = Decimal(str(coupon_frequency))
    one_plus_y = Decimal("1") + ytm / frequency
    if one_plus_y <= 0:
        return years_to_maturity, _single_cashflow_convexity(
            years_to_maturity, ytm, coupon_frequency
        )

    if report_date is not None and maturity_date is not None and 12 % coupon_frequency == 0:
        interval_months = 12 // coupon_frequency
        payment_dates = _coupon_dates_between(
            report_date=report_date,
            horizon_end=maturity_date,
            maturity_date=maturity_date,
            interval_months=interval_months,
        )
        n_periods = len(payment_dates)
        on_coupon_grid = _add_months(maturity_date, -n_periods * interval_months) == report_date
        payment_times = [
            Decimal(index + 1) / frequency
            if on_coupon_grid
            else Decimal((payment_date - report_date).days) / _DAYS_PER_YEAR
            for index, payment_date in enumerate(payment_dates)
        ]
    else:
        raw_periods = years_to_maturity * frequency
        nearest_periods = int(raw_periods.to_integral_value(rounding=ROUND_HALF_UP))
        if nearest_periods > 0 and whole_period_calendar_merge_applies(
            years_to_maturity, nearest_periods, coupon_frequency
        ):
            n_periods = nearest_periods
            cashflow_years = Decimal(nearest_periods) / frequency
        else:
            n_periods = int(raw_periods.to_integral_value(rounding=ROUND_CEILING))
            cashflow_years = years_to_maturity
        first_period_years = cashflow_years - Decimal(n_periods - 1) / frequency
        payment_times = [first_period_years + Decimal(index) / frequency for index in range(n_periods)]
    if n_periods <= 0:
        # coupon_frequency <= 0 也落在这里（raw_periods <= 0）。
        return years_to_maturity, _single_cashflow_convexity(
            years_to_maturity, ytm, coupon_frequency
        )

    c = coupon_rate / coupon_frequency if coupon_frequency > 0 else coupon_rate

    pv_sum = Decimal("0")
    convexity_sum = Decimal("0")
    price = Decimal("0")

    for t, payment_time_years in enumerate(payment_times, start=1):
        period_number = payment_time_years * frequency
        discount = one_plus_y**period_number
        cf = c if t < n_periods else c + Decimal("1")
        pv = cf / discount
        pv_sum += payment_time_years * pv
        convexity_sum += (
            payment_time_years * (payment_time_years + Decimal("1") / frequency) * pv
        )
        price += pv

    if price <= 0:
        return years_to_maturity, _single_cashflow_convexity(
            years_to_maturity, ytm, coupon_frequency
        )

    return pv_sum / price, convexity_sum / price / (one_plus_y**2)


def compute_macaulay_duration(
    coupon_rate: Decimal,
    ytm: Decimal,
    years_to_maturity: Decimal,
    coupon_frequency: int = 1,
    *,
    report_date: date | None = None,
    maturity_date: date | None = None,
) -> Decimal:
    """Macaulay 久期（年）。与凸性共用同一次现金流遍历，见上。

    W-fi-2026-08 P4：久期本身**未改动**（折现仍为 ``(1 + ytm/f)^(t·f)``），只是把
    原本重复构造现金流的凸性并入同一次遍历。逐位回归见
    ``tests/test_convexity_caliber_baseline.py``。
    """
    return compute_macaulay_duration_and_convexity(
        coupon_rate=coupon_rate,
        ytm=ytm,
        years_to_maturity=years_to_maturity,
        coupon_frequency=coupon_frequency,
        report_date=report_date,
        maturity_date=maturity_date,
    )[0]


def estimate_duration_with_status(
    maturity_date: date | None,
    report_date: date | None,
    coupon_rate: Decimal = Decimal("0"),
    ytm: Decimal | None = None,
    bond_code: str = "",
    coupon_frequency: int = 1,
) -> tuple[Decimal | None, str]:
    """久期 + 剩余期限输入状态。缺到期日时返回 ``(None, maturity_unavailable)``。

    这是诚实版入口：``None`` 表示久期**不适用**（该行多半根本不是债券），调用方
    应把它移出久期分母并单独披露，而不是当成一只久期为 0 的债。
    ``estimate_duration`` 是它的兼容外壳，把 ``None`` 折成
    ``DURATION_UNAVAILABLE``（0）以维持既有 Decimal 契约。
    """
    if not maturity_date or not report_date:
        return None, DURATION_TERM_MATURITY_UNAVAILABLE

    remaining_days = (maturity_date - report_date).days
    if remaining_days <= 0:
        return Decimal("0"), DURATION_TERM_NO_REMAINING_TERM

    years = Decimal(str(remaining_days)) / Decimal("365")

    effective_ytm, _par_fallback_used = resolve_ytm_with_par_fallback(coupon_rate, ytm)
    frequency = Decimal(str(coupon_frequency)) if coupon_frequency > 0 else Decimal("1")
    if coupon_rate > 0 and coupon_frequency > 0 and Decimal("1") + effective_ytm / frequency > 0:
        return (
            compute_macaulay_duration(
                coupon_rate,
                effective_ytm,
                years,
                coupon_frequency=coupon_frequency,
                report_date=report_date,
                maturity_date=maturity_date,
            ),
            DURATION_TERM_OBSERVED,
        )

    return years, DURATION_TERM_OBSERVED


def estimate_duration(
    maturity_date: date | None,
    report_date: date | None,
    coupon_rate: Decimal = Decimal("0"),
    ytm: Decimal | None = None,
    bond_code: str = "",
    coupon_frequency: int = 1,
) -> Decimal:
    """Macaulay 久期（年）。缺到期日时返回 ``DURATION_UNAVAILABLE``（0）+ 告警。

    W-fi-2026-08 P2：此前缺到期日时 ``return Decimal("3")``——给一批**根本不是债券**
    的持仓（2026-07-31 实测 127 笔 / 434.00 亿，全是公募基金与 ETF）凭空编了 3 年
    久期。占位常数现已收敛到 ``resolve_missing_maturity_duration`` 一处。
    """
    duration, status = estimate_duration_with_status(
        maturity_date,
        report_date,
        coupon_rate=coupon_rate,
        ytm=ytm,
        bond_code=bond_code,
        coupon_frequency=coupon_frequency,
    )
    if duration is None or status == DURATION_TERM_MATURITY_UNAVAILABLE:
        return resolve_missing_maturity_duration(
            bond_code=bond_code,
            maturity_date_missing=not maturity_date,
            report_date_missing=not report_date,
        )
    return duration


def estimate_modified_duration(
    macaulay_duration: Decimal,
    ytm: Decimal,
    coupon_frequency: int = 1,
) -> Decimal:
    """Macaulay → 修正久期；``ytm`` 应传久期估计实际使用的生效 ytm。

    par 假设路径（estimate_duration 对有票息缺 ytm 的债按 ytm=coupon 计算）
    的调用方需传入该生效 ytm（见 ``resolve_ytm_with_par_fallback``），否则
    除数 ``1 + ytm/f`` 与源 ytm 的按付息频率复利报价惯例一致
    （见 ``YIELD_COMPOUNDING_CONVENTION``）。合法负收益率同样按标准公式折算；
    仅当频率无效或折现基数非正时保守返回 Macaulay。
    """
    if coupon_frequency <= 0:
        return macaulay_duration
    divisor = Decimal("1") + ytm / Decimal(str(coupon_frequency))
    if divisor <= 0:
        return macaulay_duration
    return macaulay_duration / divisor


def estimate_convexity(
    duration: Decimal,
    ytm: Decimal,
    coupon_frequency: int = 2,
    *,
    coupon_rate: Decimal | None = None,
    years_to_maturity: Decimal | None = None,
    report_date: date | None = None,
    maturity_date: date | None = None,
) -> Decimal:
    """标准现金流凸性（年²）。

    W-fi-2026-08 P4：由久期型近似 ``D(D+1)/(1+y/f)²``（``y<=0`` 时特判 ``D²``）
    改为按现金流对收益率求二阶导的标准定义
    ``C = Σ[CF_k·k(k+1)/(1+y/f)^(k+2)]/(P·f²)``。旧式是零息近似族：
    单笔现金流且 ``f=1`` 时精确，付息债系统性低估 ``M²/(1+y/f)²``
    （``M²`` = 现值加权付息时点方差），组合层实测低估 9.24%、逐券 −26.1%~+33.2%；
    且分子 ``D(D+1)`` 与 ``f`` 无关，而零息恒等式要求 ``D² + D/f``，
    因此 ``f=2`` 时对短端又系统性高估 ``D/2``。

    传入 ``coupon_rate`` 与 ``years_to_maturity`` 时走标准现金流路径；两者缺一时
    退化为「一笔现金流落在 ``t = duration``」的闭式解 ``D(D + 1/f)/(1+y/f)²``——
    该式对零息券精确，对付息债仍低估 ``M²/(1+y/f)²``。正式物化链路
    （``bond_analytics.engine`` / ``bond_four_effects`` / ``krd``）一律传现金流入参。

    ``ytm <= 0`` 不再特判：标准式在 ``y = 0`` 处连续（旧实现在 ``y=0`` 有 ``D``
    大小的跳变——live 库 1,829 个合并持仓里 155 个、期初市值 529.1 亿落在该分支）。
    """
    # 只有「有票息 + 折现基数为正」才真的有多笔现金流可遍历；其余情形唯一现金流落在
    # 调用方给定的 ``duration`` 上，闭式解与遍历同值，且能沿用
    # 调用方对久期的口径选择（例如 KRD 的 par 回退久期），不会 D / C 各用一套时点。
    if (
        coupon_rate is not None
        and years_to_maturity is not None
        and coupon_rate > 0
        and coupon_frequency > 0
        and Decimal("1") + ytm / Decimal(str(coupon_frequency)) > 0
    ):
        return compute_macaulay_duration_and_convexity(
            coupon_rate=coupon_rate,
            ytm=ytm,
            years_to_maturity=years_to_maturity,
            coupon_frequency=coupon_frequency,
            report_date=report_date,
            maturity_date=maturity_date,
        )[1]
    return _single_cashflow_convexity(duration, ytm, coupon_frequency)


# --- Curve utilities ---

TENOR_YEARS: dict[str, float] = {
    "1M": 1 / 12, "3M": 0.25, "6M": 0.5, "9M": 0.75,
    "1Y": 1.0, "2Y": 2.0, "3Y": 3.0, "4Y": 4.0, "5Y": 5.0, "6Y": 6.0,
    "7Y": 7.0, "10Y": 10.0, "15Y": 15.0, "20Y": 20.0, "30Y": 30.0,
}


def tenor_to_years_or_none(tenor: str) -> float | None:
    """已知期限词表精确查询；未知标签返回 ``None`` 由调用方决定跳过或报错。"""
    return TENOR_YEARS.get(tenor)


def tenor_to_years(tenor: str) -> float:
    years = TENOR_YEARS.get(tenor)
    if years is None:
        # 未知标签绝不静默映射为 5.0 年：假 5Y 节点会与真实 5Y 重复（三次样条
        # h=0 除零）并污染全部插值结果（2026-08 审计 FI-05）。
        raise ValueError(f"Unknown curve tenor label: {tenor!r}")
    return years


def get_tenor_bucket(years_to_maturity: float) -> str:
    if years_to_maturity <= 0.5:
        return "6M"
    if years_to_maturity <= 1.5:
        return "1Y"
    if years_to_maturity <= 2.5:
        return "2Y"
    if years_to_maturity <= 4.0:
        return "3Y"
    if years_to_maturity <= 6.0:
        return "5Y"
    if years_to_maturity <= 8.5:
        return "7Y"
    if years_to_maturity <= 12.5:
        return "10Y"
    if years_to_maturity <= 25.0:
        return "20Y"
    return "30Y"


def build_curve_points(curve: dict[str, Decimal]) -> list[tuple[float, Decimal]]:
    # 未知期限标签跳过并告警（不发明节点）；按 years 去重以保证 x 严格递增，
    # 防止三次样条 h=0 除零（2026-08 审计 FI-05）。
    points: dict[float, Decimal] = {}
    skipped: list[str] = []
    for tenor, rate in curve.items():
        years = tenor_to_years_or_none(tenor)
        if years is None:
            skipped.append(str(tenor))
            continue
        points[years] = safe_decimal(rate)
    if skipped:
        logger.warning(
            "build_curve_points skipped unknown tenor labels %s (kept %d of %d nodes)",
            sorted(skipped),
            len(points),
            len(curve),
        )
    return sorted(points.items(), key=lambda x: x[0])


def interpolate_rate(points: list[tuple[float, Decimal]], target_years: float) -> Decimal:
    """Interpolate a rate from sorted (years, rate) points.

    Delegates to ``curve_engine`` cubic spline when ≥ 3 points are available;
    falls back to piecewise linear otherwise.  Signature unchanged.
    """
    from backend.app.core_finance.curve_engine.curve_types import (
        CurvePoint,
        FittedCurve,
        InterpolationMethod,
    )
    from backend.app.core_finance.curve_engine.interpolation import (
        build_cubic_spline as _build_spline,
    )
    from backend.app.core_finance.curve_engine.interpolation import (
        interpolate as _engine_interpolate,
    )

    if not points:
        return Decimal("0")

    curve_points = tuple(CurvePoint(years=y, rate=r) for y, r in sorted(points, key=lambda p: p[0]))
    if len(curve_points) >= 3:
        fitted = _build_spline(list(curve_points))
    else:
        fitted = FittedCurve(method=InterpolationMethod.LINEAR, points=curve_points)
    return _engine_interpolate(fitted, target_years)


def build_full_curve(raw_curve: dict[str, Decimal]) -> dict[str, Decimal]:
    if not raw_curve:
        return {}
    points = build_curve_points(raw_curve)
    if not points:
        return {}
    all_tenors = ["3M", "6M", "9M", "1Y", "2Y", "3Y", "4Y", "5Y", "6Y", "7Y", "10Y", "20Y", "30Y"]
    all_tenors.extend(tenor for tenor in raw_curve if tenor not in all_tenors and tenor_to_years_or_none(tenor) is not None)
    full: dict[str, Decimal] = {}
    for tenor in all_tenors:
        if tenor in raw_curve:
            full[tenor] = raw_curve[tenor]
        else:
            full[tenor] = interpolate_rate(points, tenor_to_years(tenor))
    return full


# --- Period resolution ---

def resolve_period(report_date: date, period_type: str) -> tuple[date, date]:
    if period_type == "YTD":
        return date(report_date.year, 1, 1), report_date
    if period_type == "TTM":
        # 闰日报告日（2/29）在上一年不存在，直接 date(year-1, 2, 29) 会抛
        # ValueError 并让当天全部 TTM 视图 500；回退到目标月最后一天（2/28）。
        start_day = min(report_date.day, monthrange(report_date.year - 1, report_date.month)[1])
        start = date(report_date.year - 1, report_date.month, start_day)
        return start, report_date
    # MoM default
    first_of_month = report_date.replace(day=1)
    return first_of_month, report_date


# --- Standard scenarios ---

STANDARD_SCENARIOS: list[dict] = [
    {"name": "parallel_up_25bp", "description": "平行上移 25bp", "shocks": {"all": 25}},
    {"name": "parallel_up_50bp", "description": "平行上移 50bp", "shocks": {"all": 50}},
    {"name": "parallel_up_100bp", "description": "平行上移 100bp", "shocks": {"all": 100}},
    {"name": "parallel_down_25bp", "description": "平行下移 25bp", "shocks": {"all": -25}},
    {"name": "parallel_down_50bp", "description": "平行下移 50bp", "shocks": {"all": -50}},
    # 陡峭化/平坦化需覆盖 get_tenor_bucket 的全部桶，否则中间期限桶冲击为 0、
    # 情景损益被低估。非锚点桶按 1Y/10Y/30Y 锚点线性插值（取整 bp），
    # 端点外（6M）沿用最近锚点（1Y）值。
    # 口径说明（2026-07 经确认并存，勿擅自统一）：krd.py 的 STANDARD_KRD_SCENARIOS
    # 同名情景为 1Y∓25bp / 30Y±25bp 驼峰形，与此处 30Y±50bp 线性版本是两套已知口径。
    {
        "name": "steepening_50bp",
        "description": "陡峭化 50bp",
        "shocks": {
            "6M": -25, "1Y": -25, "2Y": -19, "3Y": -14, "5Y": -3,
            "7Y": 8, "10Y": 25, "20Y": 38, "30Y": 50,
        },
    },
    {
        "name": "flattening_50bp",
        "description": "平坦化 50bp",
        "shocks": {
            "6M": 25, "1Y": 25, "2Y": 19, "3Y": 14, "5Y": 3,
            "7Y": -8, "10Y": -25, "20Y": -38, "30Y": -50,
        },
    },
]
