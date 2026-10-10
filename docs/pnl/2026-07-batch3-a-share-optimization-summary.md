# 2026-07 Batch 3 A-Share Optimization Summary

- status: blocked
- paper_trading: NO
- live_strategy_change: NO
- best_research_candidate: risk_budget_0.005
- best_conservative_candidate: risk_budget_0.003
- best_exit_overlay_lead: day5_underwater_exit

## Data Readiness

- trading_day_gate_fallback: 0.0
- calendar_gate_fallback: 0.342229
- liquidity_canonical_status: blocked
- adjustment_factor_status: blocked
- adjustment_factor_missing_ratio: 0.175922
- macro_status: blocked_until_macro_composite_history_exists
- position_history_status: blocked_until_position_history_expands
- canonical_dataset_status: schema_ready
- canonical_schema_status: schema_ready
- canonical_data_quality_status: data_quality_blocked
- canonical_promotion_status: promotion_blocked
- canonical_data_quality_flags: ['liquidity_unit_unverified', 'adjustment_factor_missing_gt_2pct', 'canonical_path_gate_exposure_null', 'canonical_trade_exit_price_adjusted_null']
- a_share_execution_constraint_status: research_only_incomplete

## Strategy Ranking

- risk_budget_0.003: research_only (conservative research candidate; blocked by data gates)
- risk_budget_0.005: research_only (balanced research candidate; blocked by data gates)
- risk_budget_0.0075: diagnostic_only (higher concentration risk)
- risk_budget_0.010: rejected_diagnostic_only (too concentrated and not allowed as candidate)
- fixed_20d: baseline (comparison baseline)

## Exact Blockers

- A-share execution constraints are research_only/incomplete: board lot, ST, limit-down delay, or capacity gates are not fully integrated
- adjustment factor missing ratio > 2%
- capacity estimate blocked until canonical RMB liquidity amount is verified
- liquidity canonical RMB amount is not verified

## Final recommendation:

- Live strategy change: NO
- Paper trading: NO
- Best research candidate: risk_budget_0.005
- Best conservative candidate: risk_budget_0.003
- Best exit overlay lead: day5_underwater_exit
- Hard blockers: A-share execution constraints are research_only/incomplete: board lot, ST, limit-down delay, or capacity gates are not fully integrated, adjustment factor missing ratio > 2%, capacity estimate blocked until canonical RMB liquidity amount is verified, liquidity canonical RMB amount is not verified
- Next action: Verify vendor RMB liquidity unit and backfill missing adjustment-factor dates before rerunning promotion tests.

No live candidate generation, live risk-exit trigger, confluence semantics, or live FORMULA_VERSION was changed.
