"""实时建议仓位（position_size_hint）正式计算。

主参考口径为等权（``primary_basis`` 由 :class:`SizingPolicy` 单一来源声明）：

- equal_weight = 当日门控敞口 / 候选数，与回测引擎 `portfolio_backtest` 的
  equal_weight 变体同语义（target = equity × exposure / 槽位，敞口直接进入权重，
  无需再叠加 gate 截断）；门控敞口缺失时该字段为 None。

risk_budget 输出保留为实验参考（walk-forward 样本外验证不支持固定 rpt=0.5% 的
优势，见 docs/strategy-reports/walk-forward-first-run.md），与回测引擎的
risk_budget 变体保持同款公式：

- stop_distance_pct = (close - ema10) / close，非正或缺失时用政策 fallback；
- raw_weight = min(risk_per_trade / stop_distance_pct, single_name_cap)。

raw_weight 是"单票权重上限建议"：引擎语义中 risk_budget 与 gate 敞口为串联约束
（先算单票权重，再受当日 gate 敞口剩余预算截断），实时提示不做敞口截断计算，
串联语义以文案披露。历史评估见 docs/strategy-reports/risk-budget-promotion.md。
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from backend.app.core_finance.strategy_policy import POLICY, SizingPolicy

STOP_BASIS_EMA10 = "ema10_stop_ref"
STOP_BASIS_FALLBACK = "fallback"

#: ema10 stop_ref 缺失率超过该阈值时，hint 标注覆盖率降级（蓝本前置条件：覆盖率 >= 90%）。
STOP_REF_COVERAGE_DEGRADED_THRESHOLD = 0.10

GATE_EXPOSURE_NOTE = (
    "raw_weight 为单票权重上限建议；实盘按引擎串联口径，"
    "建仓金额仍受当日 gate 敞口剩余预算截断"
    "（target = min(raw_weight×权益, 敞口×权益−当日已买入)），本提示不做实时敞口截断。"
)

EQUAL_WEIGHT_SHADOW_NOTE = "等权 shadow 对照仍在回测输出（sizing=equal_weight 变体），用于 drift 监控。"

#: risk_budget 输出的披露语义降级为实验参考（walk-forward 样本外未支持）。
RISK_BUDGET_STATUS_EXPERIMENTAL_REFERENCE = "experimental_reference"

EQUAL_WEIGHT_NOTE = (
    "等权仓位为主参考口径：equal_weight = 当日门控敞口 / 候选数，"
    "与回测 equal_weight 变体同语义（敞口直接进入权重，无需再叠加 gate 截断）；"
    "门控敞口缺失时等权仓位不可计算，仅保留 risk_budget 实验参考。"
)

OOS_VALIDATION_NOTE = (
    "walk-forward 样本外验证显示逐窗最优 rpt 在 0.25%~1% 间漂移，"
    "固定 0.5% 的全窗口优势在样本外普遍缩水；"
    "本建议仅供参考，需结合等权 shadow 对照观察。"
)

OOS_VALIDATION_EVIDENCE_REF = "docs/strategy-reports/walk-forward-first-run.md"

COVERAGE_DEGRADED_WARNING = (
    "ema10 stop_ref 缺失率超过 10%，建议仓位提示已降级：缺失候选按 fallback 止损距离估算，仅供参考。"
)


def _as_finite_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _stop_distance_pct(
    *,
    close: float | None,
    ema10: float | None,
    fallback_stop_distance_pct: float,
) -> tuple[float, str]:
    """镜像 portfolio_backtest._risk_budget_stop_distance 的口径。"""
    if close is None or close <= 0 or ema10 is None:
        return fallback_stop_distance_pct, STOP_BASIS_FALLBACK
    stop_distance_pct = (close - ema10) / close
    if stop_distance_pct <= 0 or not math.isfinite(stop_distance_pct):
        return fallback_stop_distance_pct, STOP_BASIS_FALLBACK
    return stop_distance_pct, STOP_BASIS_EMA10


def compute_position_size_hint_item(
    *,
    stock_code: str,
    close: object,
    ema10: object,
    policy: SizingPolicy,
) -> dict[str, object]:
    stop_distance_pct, stop_basis = _stop_distance_pct(
        close=_as_finite_float(close),
        ema10=_as_finite_float(ema10),
        fallback_stop_distance_pct=policy.fallback_stop_distance_pct,
    )
    uncapped_weight = policy.risk_per_trade / stop_distance_pct
    raw_weight = min(uncapped_weight, policy.single_name_cap)
    return {
        "stock_code": stock_code,
        "raw_weight": round(raw_weight, 6),
        "stop_distance_pct": round(stop_distance_pct, 6),
        "stop_basis": stop_basis,
        "capped": uncapped_weight > policy.single_name_cap,
    }


def _equal_weight_gate_exposure(market_gate_exposure: object) -> float | None:
    """归一当日门控敞口：镜像 portfolio_backtest 的 [0, 1] 截取口径。"""
    exposure = _as_finite_float(market_gate_exposure)
    if exposure is None:
        return None
    return min(max(exposure, 0.0), 1.0)


def build_stock_candidate_position_size_hint(
    items: Sequence[Mapping[str, object]],
    *,
    policy: SizingPolicy | None = None,
    market_gate_exposure: object = None,
) -> dict[str, object]:
    """为 stock_candidate 候选构建 position_size_hint 块。

    主参考为等权（门控敞口/候选数）；risk_budget 的每票权重上限建议保留为
    实验参考（``risk_budget_status``）。``market_gate_exposure`` 为当日门控敞口
    （market_gate.exposure，含宏观 overlay），缺失时 equal_weight 为 None。
    """
    sizing = policy if policy is not None else POLICY.sizing
    gate_exposure = _equal_weight_gate_exposure(market_gate_exposure)
    candidate_count = len(items)
    equal_weight = (
        round(gate_exposure / candidate_count, 6)
        if gate_exposure is not None and candidate_count > 0
        else None
    )
    hint_items: list[dict[str, object]] = []
    for item in items:
        hint_item = compute_position_size_hint_item(
            stock_code=str(item.get("stock_code") or ""),
            close=item.get("close"),
            ema10=item.get("ema10"),
            policy=sizing,
        )
        hint_item["equal_weight"] = equal_weight
        hint_items.append(hint_item)
    fallback_count = sum(1 for hint in hint_items if hint["stop_basis"] == STOP_BASIS_FALLBACK)
    missing_ratio = fallback_count / len(hint_items) if hint_items else 0.0
    coverage_degraded = missing_ratio > STOP_REF_COVERAGE_DEGRADED_THRESHOLD
    return {
        "policy_version": sizing.policy_version,
        "sizing_mode": sizing.sizing_mode,
        "primary_basis": sizing.primary_basis,
        "risk_budget_status": RISK_BUDGET_STATUS_EXPERIMENTAL_REFERENCE,
        "signal_kind": "stock_candidate",
        "risk_per_trade": sizing.risk_per_trade,
        "single_name_cap": sizing.single_name_cap,
        "fallback_stop_distance_pct": sizing.fallback_stop_distance_pct,
        "stop_basis": sizing.stop_basis,
        "items": hint_items,
        "stop_ref_fallback_count": fallback_count,
        "stop_ref_missing_ratio": round(missing_ratio, 6),
        "coverage_degraded": coverage_degraded,
        "coverage_warning": COVERAGE_DEGRADED_WARNING if coverage_degraded else None,
        "equal_weight_gate_exposure": round(gate_exposure, 6) if gate_exposure is not None else None,
        "equal_weight_candidate_count": candidate_count,
        "equal_weight_note": EQUAL_WEIGHT_NOTE,
        "gate_exposure_note": GATE_EXPOSURE_NOTE,
        "equal_weight_shadow_note": EQUAL_WEIGHT_SHADOW_NOTE,
        "oos_validation": {
            "status": sizing.oos_validation_status,
            "note": OOS_VALIDATION_NOTE,
            "evidence_ref": OOS_VALIDATION_EVIDENCE_REF,
        },
    }
