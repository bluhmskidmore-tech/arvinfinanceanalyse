# 2026-07 Batch 3 A-Share Trading Constraint Report

- status: blocked
- live_strategy_changes: none
- execution_constraint_status: research_only_incomplete
- capacity_status: blocked
- incomplete_reasons: ["100-share board-lot sizing is not modeled", "capacity estimate is blocked until canonical RMB liquidity amount is verified", "limit-down exit delay is not integrated into underwater overlay retests", "ST/special treatment constraints are not integrated"]

## Diagnostics

- t_plus_one_assessment: Day 3/5/8 exits happen after entry date, so T+1 does not block these overlays in the current path logic.
- entry_halted_count: 0
- entry_missing_open_count: 0
- path_halted_count: 0
- path_limit_down_count: 469
- missing_open_path_rows: 0
- st_or_special_treatment_trade_rows: 21
- board_lot_rule: 100-share lot sizing not modeled in current research engine; sizing remains notional-level diagnostic.
- cost_model: `{"buy_cost_rate": 0.0008, "sell_cost_rate": 0.0013, "slippage_rate": 0.001}`
- capacity_note: Capacity estimate requires daily_amount_rmb_canonical; theoretical next-open exits are not guaranteed executions.

## Blockers

- A-share execution constraints are research_only/incomplete: board lot, ST, limit-down delay, or capacity gates are not fully integrated
- capacity estimate blocked until canonical RMB liquidity amount is verified

Theoretical next-open exits are not treated as guaranteed execution.
