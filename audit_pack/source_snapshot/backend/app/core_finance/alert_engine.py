"""Rule-based portfolio alerts from a computed risk tensor (threshold comparisons only)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.app.core_finance.risk_tensor import PortfolioRiskTensor


@dataclass(slots=True, frozen=True)
class AlertRule:
    rule_id: str
    metric_name: str
    threshold: Decimal
    comparison: str  # "gt" / "lt" / "gte" / "lte"
    severity: str  # "high" / "medium" / "low"
    title_template: str
    detail_template: str


DEFAULT_RULES: list[AlertRule] = [
    AlertRule(
        "R_DUR_HIGH",
        "portfolio_modified_duration",
        Decimal("7.0"),
        "gte",
        "high",
        "久期敞口接近上限",
        "组合修正久期 {value:.2f}，阈值 {threshold}",
    ),
    AlertRule(
        "R_DUR_WARN",
        "portfolio_modified_duration",
        Decimal("6.0"),
        "gte",
        "medium",
        "久期敞口偏高",
        "组合修正久期 {value:.2f}，关注阈值 {threshold}",
    ),
    AlertRule(
        "R_CREDIT_CONC",
        "issuer_top5_weight",
        Decimal("0.50"),
        "gte",
        "medium",
        "信用集中度预警",
        "前五大发行人市值占比 {value:.1%}，阈值 {threshold:.0%}",
    ),
    AlertRule(
        "R_LIQ_30D",
        "liquidity_gap_30d_ratio",
        Decimal("0.10"),
        "gte",
        "medium",
        "短期流动性缺口",
        "30 天内到期市值占比 {value:.1%}，阈值 {threshold:.0%}",
    ),
]


def _comparison_holds(value: Decimal, threshold: Decimal, op: str) -> bool:
    if op == "gt":
        return value > threshold
    if op == "lt":
        return value < threshold
    if op == "gte":
        return value >= threshold
    if op == "lte":
        return value <= threshold
    raise ValueError(f"Unsupported comparison: {op!r}")


def _metric_value(tensor: PortfolioRiskTensor, metric_name: str) -> Decimal:
    raw = getattr(tensor, metric_name, None)
    if raw is None:
        raise AttributeError(metric_name)
    if isinstance(raw, Decimal):
        return raw
    return Decimal(str(raw))


def evaluate_alerts(
    risk_tensor: PortfolioRiskTensor,
    rules: list[AlertRule] | None = None,
) -> list[dict[str, str]]:
    """对每条规则检查是否触发，返回触发的告警列表（元素含 rule_id / severity / title / detail）。"""
    active = rules if rules is not None else list(DEFAULT_RULES)
    fired: list[dict[str, str]] = []
    for rule in active:
        value = _metric_value(risk_tensor, rule.metric_name)
        if not _comparison_holds(value, rule.threshold, rule.comparison):
            continue
        detail = rule.detail_template.format(value=float(value), threshold=float(rule.threshold))
        fired.append(
            {
                "rule_id": rule.rule_id,
                "severity": rule.severity,
                "title": rule.title_template,
                "detail": detail,
            }
        )
    return fired
