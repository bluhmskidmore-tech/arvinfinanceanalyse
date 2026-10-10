"""
债券久期 / 会计推断（自 MOSS-SYSTEM-V1 bond_analytics/common.py 迁入，无 SQLAlchemy / Wind）。

与 attribution_core.estimate_modified_duration(maturity, report, coupon, ytm) 不同：
本模块提供 Macaulay 久期估计 + Macaulay→修正久期转换（modified_duration_from_macaulay）。

久期本身不在此处实现：``compute_macaulay_duration`` 委托
``bond_analytics.common``，本模块只保留业务外壳（Wind 覆盖、缺到期日的不可用信号）。

W-fi-2026-08 P2：原有的 ``SA``/``SCP`` 前缀短路（直接 ``return Decimal("0.25")``）
已删除，缺到期日的取值也已收敛到 ``common.resolve_missing_maturity_duration``。删除依据：

* ``SCP`` 前缀在本套账里 **0 行匹配**（fact / snapshot / balance 三张表全为 0），
  是纯死代码。
* ``SA`` 前缀被当成「短融/超短融」处理，但实测 57,115 行 ``SA`` 记录里
  **到期日 0 行有值、票息 0 行非零、应计利息 0 行非零、券名 57,115/57,115 全是纯 6
  位数字**——它们是公募基金与 ETF（``010607`` 新沃安鑫 87 个月定开、``006925``
  永赢中债 1-3 政策金融债 等），``bond_type='其他'``、``asset_class='交易性资产'``。
  前缀含义与注释里的「短融」假设完全无关，0.25 年是给非债券编的债券久期。
* 短路位置在 Wind 覆盖与到期日判断**之前**，因此即便某只 ``SA`` 券将来补上了真实
  到期日或 Wind 久期，也仍会被 0.25 覆盖掉。
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.core_finance.bond_analytics.common import (
    DURATION_TERM_MATURITY_UNAVAILABLE,
    DURATION_TERM_NO_REMAINING_TERM,
    DURATION_TERM_OBSERVED,
    resolve_missing_maturity_duration,
    resolve_ytm_with_par_fallback,
)
from backend.app.core_finance.bond_analytics.common import (
    compute_macaulay_duration as _shared_compute_macaulay_duration,
)
from backend.app.core_finance.bond_analytics.common import (
    estimate_convexity as _shared_estimate_convexity,
)
from backend.app.core_finance.config.classification_rules import infer_invest_type
from backend.app.core_finance.field_normalization import (
    ACCOUNTING_BASIS_AC,
    ACCOUNTING_BASIS_FVOCI,
    derive_accounting_basis_value,
)

logger = logging.getLogger(__name__)


def _coerce_date_like(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime().date()
        except (ValueError, TypeError, AttributeError):
            logger.exception("_coerce_date_like: to_pydatetime() failed for %r", type(value).__name__)
            return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except (ValueError, TypeError, AttributeError):
            logger.exception("_coerce_date_like: .date() failed for %r", type(value).__name__)
            return None
    return None


def compute_macaulay_duration(
    years_to_maturity: Decimal,
    coupon_rate: Decimal,
    ytm: Decimal,
    frequency: int = 1,
    *,
    report_date: date | None = None,
    maturity_date: date | None = None,
) -> Decimal:
    """Macaulay 久期（年）。委托 ``bond_analytics.common`` 的逐期贴现实现。

    W-fi-2026-08：本函数原先自带一套**整期**闭合公式，按
    ``to_integral_value()``（ROUND_HALF_EVEN）四舍五入取期数。而生产入口
    ``estimate_duration`` 的剩余年限恒为 ``剩余天数/365``，几乎从不是整数，于是
    1.4986 年的债被按 1 年期定价（1.0000 vs 正确 1.4695，差 −32%）；向上取整时
    又撞上 ``mac > years`` 护栏退回剩余年限。逐日扫描年付券：82% 的剩余天数下
    误差 > 0.05 年、36.5% > 0.25 年。后果是 engine 路径与 Campisi 归因路径对同
    一批持仓给出不同久期（组合加权修正久期差 −9%）。

    日期齐全时共享实现按到期日锚定的日历确定票息笔数；只有报告日严格落在票息网格才
    用 k/f 年保留整期结果，其余日期采用票息日的 ACT/365 时点。无日期调用保留历史
    0.01 期小碎期归并，不再用随期限增长的闰日预算推断票息日期。

    边界口径统一到共享实现，仅保留一处本地归一化：``frequency <= 0 → 1``。共享
    实现对 ``freq <= 0`` 直接返回剩余年限，而本函数的既有契约是退化为年付。
    """
    if frequency <= 0:
        frequency = 1

    try:
        # 两个函数的位置参数顺序相反（本函数 years 在前，共享实现 coupon 在前）。
        # 必须按关键字传参：位置传参不会报错，只会静默算出另一种错误结果。
        return _shared_compute_macaulay_duration(
            coupon_rate=coupon_rate,
            ytm=ytm,
            years_to_maturity=years_to_maturity,
            coupon_frequency=frequency,
            report_date=report_date,
            maturity_date=maturity_date,
        )
    except (OverflowError, ZeroDivisionError, ValueError, InvalidOperation):
        # 保留既有 fail-closed 契约（本函数从不向 Campisi 归因链抛异常），但改为
        # 记录堆栈，避免脏数据引发的静默回退再次伪装成正常结果。
        logger.exception(
            "compute_macaulay_duration failed (years=%s coupon=%s ytm=%s freq=%s); "
            "falling back to remaining years",
            years_to_maturity,
            coupon_rate,
            ytm,
            frequency,
        )
        return years_to_maturity if years_to_maturity > Decimal("0") else Decimal("0")


def _estimate_macaulay_duration_years(
    maturity_date: date,
    report_date: date,
    coupon_rate: Decimal,
    ytm: Decimal | None = None,
    coupon_frequency: int = 1,
) -> Decimal:
    remaining_days = (maturity_date - report_date).days
    if remaining_days <= 0:
        return Decimal("0")
    years_to_maturity = Decimal(str(remaining_days)) / Decimal("365")

    # 有票息缺 ytm 时按 par 假设（ytm=coupon）；与 common.estimate_duration 同源，
    # 避免两条路径各自维护一份 par 回退逻辑。
    effective_ytm, _par_fallback_used = resolve_ytm_with_par_fallback(
        coupon_rate, ytm
    )
    # 本路径唯一的本地归一化（见 compute_macaulay_duration 文档）：frequency <= 0 → 年付。
    frequency = coupon_frequency if coupon_frequency > 0 else 1
    if coupon_rate > Decimal("0") and Decimal("1") + effective_ytm / Decimal(str(frequency)) > 0:
        return compute_macaulay_duration(
            years_to_maturity, coupon_rate, effective_ytm, frequency=frequency,
            report_date=report_date, maturity_date=maturity_date,
        )

    return years_to_maturity


def infer_accounting_class(asset_class: str | None) -> str:
    """Map accounting label to AC / OCI / TPL (legacy bond_duration buckets).

    W-bond-2026-04-21: delegates H/A/T to ``classification_rules.infer_invest_type``
    (caliber ``hat_mapping``), then ``derive_accounting_basis_value``. Preserves
    fallbacks for substrings not fully covered by the canonical matcher (e.g.
    ``摊余`` without ``摊余成本``, bare ``AC`` token).
    """
    if not asset_class:
        return "TPL"
    invest = infer_invest_type(None, None, str(asset_class))
    if invest is not None:
        basis = derive_accounting_basis_value(invest)  # type: ignore[arg-type]
        if basis == ACCOUNTING_BASIS_AC:
            return "AC"
        if basis == ACCOUNTING_BASIS_FVOCI:
            return "OCI"
        return "TPL"
    s = str(asset_class)
    if "债权投资" in s or "摊余" in s or ACCOUNTING_BASIS_AC in s:
        return "AC"
    if "出售" in s or "OCI" in s or "可供" in s:
        return "OCI"
    return "TPL"


def estimate_duration_with_status(
    maturity_date: date | None,
    report_date: date,
    coupon_rate: Decimal,
    bond_code: str = "",
    ytm: Decimal | None = None,
    wind_metrics: dict[str, Any] | None = None,
    coupon_frequency: int = 1,
) -> tuple[Decimal | None, str]:
    """久期 + 剩余期限输入状态；缺到期日时返回 ``(None, maturity_unavailable)``。

    状态字面量与 ``bond_analytics.common`` 同源（同一组常量），三条路径共用一套词表。
    """
    if wind_metrics and bond_code in wind_metrics:
        wind_dur = wind_metrics[bond_code].get("duration")
        if wind_dur is not None and wind_dur > Decimal("0"):
            return wind_dur, DURATION_TERM_OBSERVED

    mat = _coerce_date_like(maturity_date)
    report = _coerce_date_like(report_date)
    if mat is None or report is None:
        return None, DURATION_TERM_MATURITY_UNAVAILABLE

    if (mat - report).days <= 0:
        return Decimal("0"), DURATION_TERM_NO_REMAINING_TERM

    return (
        _estimate_macaulay_duration_years(mat, report, coupon_rate, ytm, coupon_frequency),
        DURATION_TERM_OBSERVED,
    )


def estimate_duration(
    maturity_date: date | None,
    report_date: date,
    coupon_rate: Decimal,
    bond_code: str = "",
    ytm: Decimal | None = None,
    wind_metrics: dict[str, Any] | None = None,
    coupon_frequency: int = 1,
) -> Decimal:
    """Macaulay 久期（年）。缺到期日时返回 ``DURATION_UNAVAILABLE``（0）+ 告警。

    返回值仍是 ``Decimal``，供既有调用方（krd / credit_spread / pnl_bridge /
    bond_four_effects / cashflow_projection）直接参与算术；需要区分「久期为 0」与
    「久期不适用」的调用方请改用 ``estimate_duration_with_status``。
    """
    duration, status = estimate_duration_with_status(
        maturity_date,
        report_date,
        coupon_rate,
        bond_code=bond_code,
        ytm=ytm,
        wind_metrics=wind_metrics,
        coupon_frequency=coupon_frequency,
    )
    if duration is None or status == DURATION_TERM_MATURITY_UNAVAILABLE:
        return resolve_missing_maturity_duration(
            bond_code=bond_code,
            maturity_date_missing=_coerce_date_like(maturity_date) is None,
            report_date_missing=_coerce_date_like(report_date) is None,
        )
    return duration


def modified_duration_from_macaulay(
    duration: Decimal,
    ytm: Decimal,
    coupon_frequency: int = 1,
    wind_mod_dur: Decimal | None = None,
) -> Decimal:
    """Macaulay → 修正久期；``ytm`` 应传久期估计实际使用的生效 ytm。

    本路径的本地归一化与 Macaulay / 凸性一致：``coupon_frequency <= 0 → 年付``，
    这样三项指标在无效频率下仍共用同一套 ``(1 + y/f)``，而不是修正久期单独退回
    未折算的 Macaulay。折现基数非正时保守返回 Macaulay。
    """
    if wind_mod_dur is not None and wind_mod_dur > Decimal("0"):
        return wind_mod_dur

    frequency = coupon_frequency if coupon_frequency > 0 else 1
    divisor = Decimal("1") + ytm / Decimal(str(frequency))
    if divisor <= 0:
        return duration
    return duration / divisor


def estimate_convexity_bond(
    duration: Decimal,
    ytm: Decimal,
    wind_convexity: Decimal | None = None,
    coupon_frequency: int = 2,
    *,
    coupon_rate: Decimal | None = None,
    years_to_maturity: Decimal | None = None,
    report_date: date | None = None,
    maturity_date: date | None = None,
) -> Decimal:
    """凸性；委托 ``bond_analytics.common.estimate_convexity`` 的薄封装。

    W-fi-2026-08 P3：本函数原有独立实现 ``[D² + D(1 + 1/f)] / (1 + y/f)²``
    （``y<=0`` 时另乘 ``1.1``）已删除，仓库内只保留一套凸性口径。删除依据：以标准
    现金流凸性恒等式 ``C_std = (D² + D/f + M²) / (1 + y/f)²``（``M²`` 为现值加权付息
    时点方差，单位年²）为参照，原式等价于强行假设 ``M² = D``——没有任何近似族这么
    取；``y<=0`` 分支的 ``1.1`` 系数同样无出处。

    W-fi-2026-08 P4：共享实现已由久期型近似升级为**标准现金流凸性**。传入
    ``coupon_rate`` / ``years_to_maturity`` 即走标准路径（Campisi 与 KRD 调用方均已
    传入）；两者缺一时退化为单笔现金流闭式解，仍是零息近似。

    Wind 覆盖分支保留：外部观测凸性优先于估计值，与 ``estimate_duration`` /
    ``modified_duration_from_macaulay`` 的 Wind 优先约定一致。
    """
    if wind_convexity is not None and wind_convexity > Decimal("0"):
        return wind_convexity

    frequency = coupon_frequency if coupon_frequency and coupon_frequency > 0 else 1
    return _shared_estimate_convexity(
        duration,
        ytm,
        coupon_frequency=frequency,
        coupon_rate=coupon_rate,
        years_to_maturity=years_to_maturity,
        report_date=report_date,
        maturity_date=maturity_date,
    )
