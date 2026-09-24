# 2026-07 Batch 3 Underwater Exit Overlay Optimization Report

- status: blocked
- priority_research_leads: ['day5_underwater_exit', 'day3_underwater_reduce_half']
- live_strategy_changes: none
- reason: Underwater exit overlay promotion is skipped until data blockers clear; existing path-mode diagnostics remain research-only.

## Blockers

- liquidity canonical RMB amount is not verified
- adjustment factor missing ratio > 2%

## Frozen Prior Diagnostic Reference

| rule | source_report | status | promotion_evidence | reason |
|---|---|---|---|---|
| day5_underwater_exit | docs\pnl\2026-07-batch3-hold-progress-exit-path-mode-report.md | frozen_prior_research_lead | False | prior path-mode diagnostic lead; requires rerun after liquidity, adjustment, and A-share execution blockers clear |
| day3_underwater_reduce_half | docs\pnl\2026-07-batch3-hold-progress-exit-path-mode-report.md | frozen_prior_research_lead | False | prior path-mode diagnostic lead; requires rerun after liquidity, adjustment, and A-share execution blockers clear |

## Rule Effects

| rule | triggers | usable | missing_open | p5_improvement | p10_improvement | winner_damage | missed_rebound | risk003_ret_delta | risk005_ret_delta | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|

Missing next open is not replaced with future close; theoretical next-open exits are not guaranteed execution.
