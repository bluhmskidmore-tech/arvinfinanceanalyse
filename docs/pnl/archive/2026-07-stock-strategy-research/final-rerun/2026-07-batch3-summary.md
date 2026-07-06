# 2026-07 Batch 3 Summary

- status: research_only
- risk_budget_0p005_go_no_go: no-go
- no_progress_exit_go_no_go: no-go
- fallback_exposure_ratio: 0.822606

## Go / No-Go

- risk_budget_0.005: no-go (research_only)
- risk_budget_0.010 too concentrated: True
- no-progress exit: no-go (research_only)

## Data Blockers

- calendar-day gate exposure fallback ratio 0.822606 remains above 10%
- daily_amount upstream unit remains unverified
- gate exposure fallback ratio 82.26% is above 10%
- liquidity thresholds have no passing known rows
- macro composite history is missing or lacks required fields
- macro composite history remains missing
- trading-day gate exposure fallback ratio 0.774869 remains above 10%

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

## Tests

- Run `python -m pytest -q tests/test_batch3_stock_strategy_research.py ...` plus existing Batch 2 focused tests.
- Run `python -m ruff check` on changed Batch 3 files.

No Batch 3 result is wired into live strategy behavior.
