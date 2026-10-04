from __future__ import annotations

from backend.app.core_finance.strategy_walk_forward_verdicts import (
    VERDICT_NOT_ASSESSABLE,
    VERDICT_SUPPORTED,
    VERDICT_WEAKENED,
    WALK_FORWARD_JUDGED_AT,
    WALK_FORWARD_REPORT,
    WALK_FORWARD_VERDICT_CONTRACT_VERSION,
    walk_forward_verdict,
)

ALL_SIGNAL_KINDS = (
    "stock_candidate",
    "theme_breakout",
    "mean_reversion",
    "uptrend_momentum",
    "fresh_trend_watchlist",
    "factor_screen",
    "hybrid_fusion",
)


def test_verdicts_match_walk_forward_report_primary_split() -> None:
    stock = walk_forward_verdict("stock_candidate")
    assert stock is not None
    assert stock["verdict"] == VERDICT_WEAKENED
    assert stock["oos_windows"] == 5
    assert stock["positive_excess_windows"] == 1
    assert stock["chained_excess_return"] == -0.5458

    theme = walk_forward_verdict("theme_breakout")
    assert theme is not None
    assert theme["verdict"] == VERDICT_SUPPORTED
    assert theme["positive_excess_windows"] == 5
    assert theme["chained_excess_return"] == 1.5378

    mean_reversion = walk_forward_verdict("mean_reversion")
    assert mean_reversion is not None
    assert mean_reversion["verdict"] == VERDICT_WEAKENED
    assert mean_reversion["chained_excess_return"] == -0.117

    for kind in ("uptrend_momentum", "fresh_trend_watchlist", "factor_screen", "hybrid_fusion"):
        verdict = walk_forward_verdict(kind)
        assert verdict is not None, kind
        assert verdict["verdict"] == VERDICT_NOT_ASSESSABLE, kind
        assert verdict["chained_excess_return"] is None, kind


def test_every_verdict_carries_report_anchor_and_contract() -> None:
    for kind in ALL_SIGNAL_KINDS:
        verdict = walk_forward_verdict(kind)
        assert verdict is not None, kind
        assert verdict["contract_version"] == WALK_FORWARD_VERDICT_CONTRACT_VERSION
        assert verdict["report"] == WALK_FORWARD_REPORT
        assert verdict["judged_at"] == WALK_FORWARD_JUDGED_AT
        assert verdict["signal_kind"] == kind
        assert verdict["verdict_label"]
        assert verdict["reason"]


def test_unknown_signal_kind_returns_none() -> None:
    assert walk_forward_verdict("sector_rank") is None
    assert walk_forward_verdict("") is None
