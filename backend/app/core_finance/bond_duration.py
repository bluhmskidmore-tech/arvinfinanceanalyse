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
) -> Decimal:
    """Macaulay 久期（年）。委托 ``bond_analytics.common`` 的逐期贴现实现。

    W-fi-2026-08：本函数原先自带一套**整期**闭合公式，按
    ``to_integral_value()``（ROUND_HALF_EVEN）四舍五入取期数。而生产入口
    ``estimate_duration`` 的剩余年限恒为 ``剩余天数/365``，几乎从不是整数，于是
    1.4986 年的债被按 1 年期定价（1.0000 vs 正确 1.4695，差 −32%）；向上取整时
    又撞上 ``mac > years`` 护栏退回剩余年限。逐日扫描年付券：82% 的剩余天数下
    误差 > 0.05 年、36.5% > 0.25 年。后果是 engine 路径与 Campisi 归因路径对同
    一批持仓给出不同久期（组合加权修正久期差 −9%）。

    共享实现按 ROUND_CEILING 取期数、首期按残期定位、逐期贴现，并把 ≤0.01 期的
    尾数残差并入上一期避免多算一期；已用独立教科书参考实现（浮点直算 / 高精度
    Decimal 直算 / 几何级数闭合式 / dP·dy⁻¹ 数值导数四路交叉）验证全样本一致。

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
        coupon_rate, ytm if ytm is not None else Decimal("0")
    )
    if coupon_rate > Decimal("0") and effective_ytm > Decimal("0"):
        return compute_macaulay_duration(
            years_to_maturity, coupon_rate, effective_ytm, frequency=coupon_frequency
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
    """Macaulay → 修正久期；与旧 common.estimate_modified_duration(duration, ytm, ...) 一致。"""
    if wind_mod_dur is not None and wind_mod_dur > Decimal("0"):
        return wind_mod_dur

    if ytm <= Decimal("-0.99"):
        return duration
    if ytm <= 0:
        return duration
    if coupon_frequency <= 0:
        return duration
    divisor = Decimal("1") + ytm / Decimal(str(coupon_frequency))
    if divisor <= 0:
        return duration
    return duration / divisor


def estimate_convexity_bond(
    duration: Decimal,
    ytm: Decimal,
    wind_convexity: Decimal | None = None,
    coupon_frequency: int = 2,
) -> Decimal:
    """基于 Macaulay 久期 ``D`` 的凸性近似（非现金流二阶导凸性）。

    W-fi-2026-08 P3：本函数原有独立实现 ``[D² + D(1 + 1/f)] / (1 + y/f)²``
    （``y<=0`` 时另乘 ``1.1``）已删除，改为委托
    ``bond_analytics.common.estimate_convexity``，仓库内只保留一套久期型凸性口径。
    删除依据：以标准现金流凸性恒等式
    ``C_std = (D² + D/f + M²) / (1 + y/f)²``（``M²`` 为现值加权付息时点方差，单位年²）
    为参照，原式等价于强行假设 ``M² = D``——没有任何近似族这么取，实测 0.25Y 高估
    80%（``f=2`` 时最高 133%）、30Y 低估 17%，只在 7~12Y 段巧合接近；``y<=0`` 分支的
    ``1.1`` 系数同样无出处。委托口径是零息近似族（单笔现金流时精确），其对付息债的
    系统性低估量 ``M²/(1+y/f)²`` 由 ``common.estimate_convexity`` 统一承担。

    Wind 覆盖分支保留：外部观测凸性优先于估计值，与 ``estimate_duration`` /
    ``modified_duration_from_macaulay`` 的 Wind 优先约定一致。
    """
    if wind_convexity is not None and wind_convexity > Decimal("0"):
        return wind_convexity

    frequency = coupon_frequency if coupon_frequency and coupon_frequency > 0 else 1
    return _shared_estimate_convexity(duration, ytm, coupon_frequency=frequency)
