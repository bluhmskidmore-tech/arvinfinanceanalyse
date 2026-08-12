"""实时建议仓位（position_size_hint）正式计算。

与回测引擎 `portfolio_backtest` 的 risk_budget 变体保持同款公式：

- stop_distance_pct = (close - ema10) / close，非正或缺失时用政策 fallback；
- raw_weight = min(risk_per_trade / stop_distance_pct, single_name_cap)。

hint 是"单票权重上限建议"：引擎语义中 risk_budget 与 gate 敞口为串联约束
（先算单票权重，再受当日 gate 敞口剩余预算截断），实时提示不做敞口截断计算，
串联语义以文案披露。评估依据见 docs/strategy-reports/risk-budget-promotion.md。
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


def build_stock_candidate_position_size_hint(
    items: Sequence[Mapping[str, object]],
    *,
    policy: SizingPolicy | None = None,
) -> dict[str, object]:
    """为 stock_candidate 候选构建 position_size_hint 块（政策口径 + 每票权重上限建议）。"""
    sizing = policy if policy is not None else POLICY.sizing
    hint_items = [
        compute_position_size_hint_item(
            stock_code=str(item.get("stock_code") or ""),
            close=item.get("close"),
            ema10=item.get("ema10"),
            policy=sizing,
        )
        for item in items
    ]
    fallback_count = sum(1 for hint in hint_items if hint["stop_basis"] == STOP_BASIS_FALLBACK)
    missing_ratio = fallback_count / len(hint_items) if hint_items else 0.0
    coverage_degraded = missing_ratio > STOP_REF_COVERAGE_DEGRADED_THRESHOLD
    return {
        "policy_version": sizing.policy_version,
        "sizing_mode": sizing.sizing_mode,
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
        "gate_exposure_note": GATE_EXPOSURE_NOTE,
        "equal_weight_shadow_note": EQUAL_WEIGHT_SHADOW_NOTE,
        "oos_validation": {
            "status": sizing.oos_validation_status,
            "note": OOS_VALIDATION_NOTE,
            "evidence_ref": OOS_VALIDATION_EVIDENCE_REF,
        },
    }
