# 2026-07 Batch 3 Risk-Budget Robustness V2 Report

- status: research_only
- risk_budget_0p005: research_only
- risk_budget_0p010: rejected_too_concentrated
- reason: Data blockers remain and robustness is not stable across bootstrap, walk-forward return, and independent slices.

## Daily IID Bootstrap

{"date_count": 381, "iterations": 300, "mean_increment": 0.158004, "p10_increment": -0.145225, "p50_increment": 0.1199, "p90_increment": 0.507274, "status": "ready"}

## Month-Cluster Bootstrap

{"cluster_count": 21, "date_count": 381, "iterations": 300, "mean_increment": 0.190641, "p10_increment": -0.20375, "p50_increment": 0.181058, "p90_increment": 0.588927, "period": "month", "status": "ready"}

## Walk Forward

- status: ready
- split_date: 2025-07-14
- selected_risk_per_trade: 0.003

| metric | selected_risk | fixed_20d | delta |
|---|---:|---:|---:|
| cumulative_return | 0.157617 | 0.724106 | -0.566489 |
| max_drawdown | 0.025700 | 0.154705 | -0.129005 |
| daily_sharpe | 2.315979 | 1.916043 | 0.399936 |
| cagr | 0.101648 | 0.433730 | -0.332082 |
| calmar | 3.955175 | 2.803594 | 1.151581 |

## Underperforming Independent Slices

| slice_type | slice_value | row_count | fixed_20d_return | risk_0p005_return | increment | max_drawdown | sharpe |
|---|---|---:|---:|---:|---:|---:|---:|
| calendar_year | 2026 | 44 | 0.301043 | 0.085820 | -0.215223 | 0.018738 | 1.835687 |
| market_state | HOT | 342 | 0.269359 | 0.124633 | -0.144726 | 0.085464 | 1.014147 |
| volatility_regime | high_vol | 321 | 0.139638 | 0.055600 | -0.084038 | 0.077779 | 0.633802 |
| volatility_regime | low_vol | 267 | 0.353978 | 0.141906 | -0.212072 | 0.066481 | 1.146746 |

Specific concern required by review: 2026, WARM, and low/mid/high volatility slices must be treated as independent robustness checks; any negative row above blocks live promotion.
