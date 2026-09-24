# 2026-07 Batch 3 Risk-Budget Robustness V2 Report

- status: research_only
- risk_budget_0p005: research_only
- risk_budget_0p010: rejected_too_concentrated
- reason: Data blockers remain and robustness is not stable across bootstrap, walk-forward return, and independent slices.

## Daily IID Bootstrap

{"date_count": 381, "iterations": 300, "mean_increment": 0.076779, "p10_increment": -0.27736, "p50_increment": 0.035785, "p90_increment": 0.491997, "status": "ready"}

## Month-Cluster Bootstrap

{"cluster_count": 21, "date_count": 381, "iterations": 300, "mean_increment": 0.094095, "p10_increment": -0.280009, "p50_increment": 0.063963, "p90_increment": 0.429461, "period": "month", "status": "ready"}

## Walk Forward

- status: ready
- split_date: 2025-07-14
- selected_risk_per_trade: 0.003

| metric | selected_risk | fixed_20d | delta |
|---|---:|---:|---:|
| cumulative_return | 0.178617 | 0.596813 | -0.418196 |
| max_drawdown | 0.026885 | 0.154705 | -0.127820 |
| daily_sharpe | 2.473964 | 1.690984 | 0.782980 |
| cagr | 0.114826 | 0.362812 | -0.247986 |
| calmar | 4.271006 | 2.345186 | NA |

## Underperforming Independent Slices

| slice_type | slice_value | row_count | fixed_20d_return | risk_0p005_return | increment | max_drawdown | sharpe |
|---|---|---:|---:|---:|---:|---:|---:|
| calendar_year | 2026 | 44 | 0.511324 | 0.186080 | -0.325244 | 0.020158 | 2.494928 |
| market_state | WARM | 291 | 0.356551 | 0.246724 | -0.109827 | 0.084404 | 1.747512 |
| volatility_regime | low_vol | 13 | 0.137966 | 0.023752 | -0.114214 | 0.012800 | 1.017559 |
| volatility_regime | mid_vol | 19 | 0.106590 | 0.018322 | -0.088268 | 0.039655 | 0.389073 |
| volatility_regime | high_vol | 12 | 0.267078 | 0.144725 | -0.122353 | 0.010669 | 2.294665 |

Specific concern required by review: 2026, WARM, and low/mid/high volatility slices must be treated as independent robustness checks; any negative row above blocks live promotion.
