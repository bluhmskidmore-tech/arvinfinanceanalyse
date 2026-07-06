from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
from datetime import date, timedelta

import pytest
from backend.app.core_finance.livermore_strategy import (
    BroadIndexObservation,
    MarketGateSupplement,
    evaluate_market_gate,
)


def _history(*, closes: list[float]) -> list[BroadIndexObservation]:
    start = date(2026, 1, 1)
    return [
        BroadIndexObservation(
            trade_date=start + timedelta(days=offset),
            close=close,
            source_series_id="CA.CSI300",
        )
        for offset, close in enumerate(closes)
    ]


def test_strategy_policy_snapshot_values_are_centralized() -> None:
    from backend.app.core_finance.strategy_policy import POLICY, POLICY_VERSION

    assert POLICY_VERSION == "sp_v1"
    assert is_dataclass(POLICY)
    assert POLICY.__dataclass_params__.frozen is True
    with pytest.raises(FrozenInstanceError):
        POLICY.buy_cost_rate = 0.0  # type: ignore[misc]

    assert POLICY.entry_observation_states == frozenset({"WARM", "HOT"})
    assert POLICY.mean_reversion_active_states == frozenset({"WARM"})
    assert POLICY.hybrid_fusion_active_states == frozenset({"WARM", "HOT"})
    assert POLICY.factor_screen_active_states == frozenset({"OFF", "WARM", "HOT", "OVERHEAT"})
    assert dict(POLICY.exposure_by_market_state) == {
        "NO_DATA": (0.0,),
        "STALE": (0.0,),
        "PENDING_DATA": (0.0,),
        "OFF": (0.0, 0.25),
        "WARM": (0.25, 0.5, 0.75),
        "HOT": (0.75,),
        "OVERHEAT": (1.0,),
    }
    assert dict(POLICY.macro_multipliers) == {
        "supportive": 1.0,
        "neutral": 0.5,
        "restrictive": 0.0,
        "unknown": 0.0,
    }
    assert POLICY.buy_cost_rate == 0.0008
    assert POLICY.sell_cost_rate == 0.0013
    assert POLICY.slippage_rate == 0.0010

    assert POLICY.risk_exit.ema_window == 10
    assert POLICY.risk_exit.volume_ma_window == 20
    assert POLICY.risk_exit.volume_confirmation_ratio == 1.3
    assert POLICY.risk_exit.min_history == 21

    filters = POLICY.entry_filters
    assert filters.min_history == 120
    assert filters.ema_window == 10
    assert filters.max_ranked == 6
    assert filters.close_strength_min == 0.95
    assert filters.abnormal_turnover_range == (1.2, 2.0)
    assert filters.gap_norm_min == 0.0
    assert filters.max_breakout_extension_norm == 0.35
    assert filters.crowded_leader_turnover_block == 2.0
    assert filters.default_fundamental_top_fraction == 0.5
    assert filters.warm_fundamental_top_fraction == 1 / 3

    policies = {policy.name: policy for policy in filters.stock_candidate_policies}
    assert policies["default"].active_market_states == frozenset({"WARM", "HOT", "OVERHEAT"})
    assert policies["default"].close_strength_min == 0.95
    assert policies["default"].gap_norm_max == 0.45
    assert policies["default"].abnormal_turnover_min == 1.2
    assert policies["default"].abnormal_turnover_max == 2.0
    assert policies["default"].close_strength_first is False
    assert policies["exp3b"].active_market_states == frozenset({"WARM", "HOT"})
    assert policies["exp3b"].close_strength_min == 0.99
    assert policies["exp3b"].gap_norm_max == 0.35
    assert policies["exp3b"].abnormal_turnover_min == 1.2
    assert policies["exp3b"].abnormal_turnover_max == 2.4
    assert policies["exp3b"].close_strength_first is True
    assert policies["exp3c_shadow"].abnormal_turnover_min == 1.0
    assert policies["exp3c_shadow"].abnormal_turnover_max == 2.4
    assert policies["v6_compat"].active_market_states == frozenset({"WARM", "HOT", "OVERHEAT"})
    assert policies["v6_compat"].abnormal_turnover_min == 1.0
    assert policies["v6_compat"].abnormal_turnover_max == 3.5

    assert POLICY.monitoring_thresholds.factor_screen_primary_coverage_threshold == 0.8
    assert POLICY.monitoring_thresholds.factor_screen_partial_coverage_threshold == 0.5
    assert POLICY.monitoring_thresholds.factor_screen_freshness_threshold_days == 3

    assert POLICY.backtest_variants.risk_budget_risk_per_trade_grid == (0.005, 0.010)
    assert POLICY.backtest_variants.risk_budget_single_name_cap == 0.25
    assert POLICY.backtest_variants.risk_budget_fallback_stop_distance_pct == 0.08
    assert POLICY.backtest_variants.probe_fraction == 0.5
    assert POLICY.backtest_variants.probe_confirm_days_grid == (3, 5)
    assert POLICY.backtest_variants.max_entry_premium_grid == (0.02, 0.03, None)
    assert POLICY.backtest_variants.vol_target_grid == (0.15, 0.20)
    assert POLICY.backtest_variants.vol_target_window == 20


def test_strategy_policy_mirrors_market_gate_exposures() -> None:
    from backend.app.core_finance.strategy_policy import POLICY

    possible_exposures = {state: set(values) for state, values in POLICY.exposure_by_market_state.items()}

    assert evaluate_market_gate([])["exposure"] in possible_exposures["NO_DATA"]
    stale_history = _history(closes=[3000.0 + day for day in range(65)])
    stale_history[-1] = BroadIndexObservation(
        trade_date=stale_history[-1].trade_date,
        close=stale_history[-1].close,
        quality_flag="stale",
    )
    assert evaluate_market_gate(stale_history)["exposure"] in possible_exposures["STALE"]
    assert evaluate_market_gate(_history(closes=[3000.0 + day for day in range(59)]))["exposure"] in possible_exposures[
        "PENDING_DATA"
    ]

    warm_gate = evaluate_market_gate(_history(closes=[3000.0 + day * 10 for day in range(65)]))
    assert warm_gate["state"] == "WARM"
    assert warm_gate["exposure"] in possible_exposures["WARM"]

    overheat_history = _history(closes=[3000.0 + day * 10 for day in range(65)])
    overheat_gate = evaluate_market_gate(
        overheat_history,
        supplement=MarketGateSupplement(
            trade_date=overheat_history[-1].trade_date,
            breadth_5d=12.3,
            limit_up_quality_ok=True,
        ),
    )
    assert overheat_gate["state"] == "OVERHEAT"
    assert overheat_gate["exposure"] in possible_exposures["OVERHEAT"]


def test_strategy_formula_versions_match_current_contracts() -> None:
    from backend.app.core_finance import (
        factor_screen_candidates,
        hybrid_fusion_candidates,
        livermore_risk_exit,
        livermore_stock_candidates,
        mean_reversion_candidates,
    )
    from backend.app.tasks import livermore_candidate_history_materialize

    assert mean_reversion_candidates.FORMULA_VERSION == "rv_mean_reversion_candidates_v2"
    assert factor_screen_candidates.FORMULA_VERSION == "rv_factor_screen_candidates_v2"
    assert hybrid_fusion_candidates.FORMULA_VERSION == "rv_hybrid_fusion_candidates_v3"
    assert livermore_stock_candidates.FORMULA_VERSION == "rv_livermore_stock_candidates_bundle_v7"
    assert livermore_risk_exit.FORMULA_VERSION == "rv_livermore_risk_exit_ema10_volume_obsfallback_v3"
    assert (
        livermore_candidate_history_materialize.FORMULA_VERSION
        == "fv_livermore_candidate_forward_close_dual_adjust_v2"
    )
    assert (
        livermore_candidate_history_materialize.EXECUTION_FORMULA_VERSION
        == "fv_livermore_candidate_execution_dual_adjust_v2"
    )


def test_existing_modules_alias_policy_values() -> None:
    from backend.app.core_finance import (
        factor_screen_candidates,
        hybrid_fusion_candidates,
        livermore_risk_exit,
        livermore_stock_candidates,
        mean_reversion_candidates,
    )
    from backend.app.core_finance.strategy_policy import POLICY
    from backend.app.services import livermore_signal_confluence_service
    from backend.app.tasks import livermore_candidate_history_materialize

    assert mean_reversion_candidates.ACTIVE_MARKET_STATES is POLICY.mean_reversion_active_states
    assert hybrid_fusion_candidates.ACTIVE_MARKET_STATES is POLICY.hybrid_fusion_active_states
    assert factor_screen_candidates.ACTIVE_MARKET_STATES is POLICY.factor_screen_active_states
    assert livermore_signal_confluence_service.ENTRY_OBSERVATION_STATES is POLICY.entry_observation_states
    assert livermore_signal_confluence_service.MACRO_MULTIPLIERS is POLICY.macro_multipliers
    assert livermore_risk_exit.MIN_HISTORY == POLICY.risk_exit.min_history
    assert livermore_risk_exit.EMA_WINDOW == POLICY.risk_exit.ema_window
    assert livermore_risk_exit.VOLUME_MA_WINDOW == POLICY.risk_exit.volume_ma_window
    assert livermore_risk_exit.VOLUME_CONFIRMATION_RATIO == POLICY.risk_exit.volume_confirmation_ratio
    assert livermore_stock_candidates.GAP_NORM_MIN == POLICY.entry_filters.gap_norm_min
    assert livermore_stock_candidates.ABNORMAL_TURNOVER_MIN_V7 == POLICY.entry_filters.abnormal_turnover_range[0]
    assert livermore_stock_candidates.ABNORMAL_TURNOVER_MAX_V7 == POLICY.entry_filters.abnormal_turnover_range[1]
    assert livermore_stock_candidates.CROWDED_LEADER_TURNOVER_BLOCK == POLICY.entry_filters.crowded_leader_turnover_block
    assert livermore_candidate_history_materialize.BUY_COST_RATE == POLICY.buy_cost_rate
    assert livermore_candidate_history_materialize.SELL_COST_RATE == POLICY.sell_cost_rate
    assert livermore_candidate_history_materialize.SLIPPAGE_RATE == POLICY.slippage_rate
