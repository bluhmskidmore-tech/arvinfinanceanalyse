# 2026-07 Batch 3 Summary

- status: research_only
- risk_budget_0p005_go_no_go: no-go
- no_progress_exit_go_no_go: no-go
- calendar_gate_fallback_ratio: 0.342229
- trading_day_gate_fallback_ratio: 0.000000
- true_trading_day_missing_count: 0
- calendar_missing_classification: non_trading_dates_only
- legacy_calendar_fallback_exposure_ratio: 0.342229

## Go / No-Go

- risk_budget_0.005: no-go (research_only)
- risk_budget_0.010 too concentrated: True
- no-progress exit: no-go (research_only)

## Data Blockers

- Formal post-data-fix risk-budget study is blocked until gate, liquidity, and adjustment blockers are all resolved.
- Hold-progress retest is blocked until data gates pass; current path-mode result is a research lead only.
- Post-data-fix robustness cannot be run as a promotion study until gate, liquidity, and adjustment data blockers are resolved.
- adjustment factor gaps remain in price paths
- clean adjustment subset share is below 80%
- clean adjustment subset share is below 80%; promotion conclusions would be sample-biased
- daily_amount upstream unit remains unconfirmed
- daily_amount upstream unit remains unverified
- liquidity thresholds have no passing known rows
- liquidity thresholds have no passing known rows under raw unit
- macro composite history is missing or lacks required fields
- macro composite history remains missing
- raw liquidity thresholds still have zero passing rows

## Liquidity Counts

| threshold_rmb | pass_count | fail_count | missing_count |
|---:|---:|---:|---:|
| 20000000.000000 | 0 | 826 | 0 |
| 50000000.000000 | 0 | 826 | 0 |
| 100000000.000000 | 0 | 826 | 0 |
| 200000000.000000 | 0 | 826 | 0 |

## Explicit Reject / Defer

- current_probe_pyramid: defer/rework
- max_entry_premium_2_3pct_hard_cap: rejected
- simple_gate_downgrade_delay: rejected
- vol_target: control_only
- macro_multiplier: blocked_until_macro_composite_history_exists
- overheat_live_exit: blocked_until_position_history_is_much_richer

## Report Status

- data readiness: blocked
- risk-budget robustness: research_only
- hold-progress exit simulation: research_only
- entry-premium interaction: research_only

## Additional Batch 3 Blocker Reports

- gate_exposure_repair: blocked
- liquidity_unit_capacity: blocked
- adjustment_factor_gap: research_only
- hold_progress_exit_path_mode: research_only
- risk_budget_robustness_v2: research_only
- gate_exposure_repair_v2: blocked
- gate_exposure_repair_v3: ready
- liquidity_unit_capacity_v2: blocked
- adjustment_factor_gap_v2: blocked
- path_engine_tieout: ready
- risk_budget_003_005_post_data_fix: blocked
- data_blocker_resolution: blocked
- post_data_fix_risk_budget: blocked
- post_data_fix_hold_progress: blocked

## Tests

- Run `python -m pytest -q tests/test_batch3_stock_strategy_research.py ...` plus existing Batch 2 focused tests.
- Run `python -m ruff check` on changed Batch 3 files.

No Batch 3 result is wired into live strategy behavior.
