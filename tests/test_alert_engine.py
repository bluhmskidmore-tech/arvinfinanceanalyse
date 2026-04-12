from __future__ import annotations

from datetime import date
from decimal import Decimal

from tests.helpers import load_module


def _alert_engine():
    return load_module(
        "backend.app.core_finance.alert_engine",
        "backend/app/core_finance/alert_engine.py",
    )


def _risk_tensor():
    return load_module(
        "backend.app.core_finance.risk_tensor",
        "backend/app/core_finance/risk_tensor.py",
    )


def _tensor(**kwargs: object):
    rt = _risk_tensor()
    PortfolioRiskTensor = rt.PortfolioRiskTensor
    base: dict[str, object] = {
        "report_date": date(2026, 3, 31),
        "portfolio_dv01": Decimal("0"),
        "krd_1y": Decimal("0"),
        "krd_3y": Decimal("0"),
        "krd_5y": Decimal("0"),
        "krd_7y": Decimal("0"),
        "krd_10y": Decimal("0"),
        "krd_30y": Decimal("0"),
        "cs01": Decimal("0"),
        "portfolio_convexity": Decimal("0"),
        "portfolio_modified_duration": Decimal("0"),
        "issuer_concentration_hhi": Decimal("0"),
        "issuer_top5_weight": Decimal("0"),
        "liquidity_gap_30d": Decimal("0"),
        "liquidity_gap_90d": Decimal("0"),
        "liquidity_gap_30d_ratio": Decimal("0"),
        "total_market_value": Decimal("1"),
        "bond_count": 1,
        "quality_flag": "ok",
        "warnings": [],
    }
    base.update(kwargs)
    return PortfolioRiskTensor(**base)


def test_duration_high_triggers():
    mod = _alert_engine()
    t = _tensor(portfolio_modified_duration=Decimal("7.5"))
    rules = [mod.DEFAULT_RULES[0]]
    fired = mod.evaluate_alerts(t, rules=rules)
    assert len(fired) == 1
    assert fired[0]["rule_id"] == "R_DUR_HIGH"


def test_below_threshold_no_alert():
    mod = _alert_engine()
    t = _tensor(
        portfolio_modified_duration=Decimal("5"),
        issuer_top5_weight=Decimal("0.2"),
        liquidity_gap_30d_ratio=Decimal("0.05"),
    )
    assert mod.evaluate_alerts(t) == []


def test_multiple_rules_fire():
    mod = _alert_engine()
    t = _tensor(
        portfolio_modified_duration=Decimal("7.5"),
        issuer_top5_weight=Decimal("0.6"),
        liquidity_gap_30d_ratio=Decimal("0.15"),
    )
    fired = mod.evaluate_alerts(t)
    ids = {entry["rule_id"] for entry in fired}
    assert ids == {"R_DUR_HIGH", "R_DUR_WARN", "R_CREDIT_CONC", "R_LIQ_30D"}
