# 2026-07 Batch 3 Path Engine Tie-Out Report

- status: ready
- max_abs_cumulative_return_delta: 0.000000
- explanation: Report-layer path baseline now uses the same buy-before-path-sell ordering as run_portfolio_backtest(mode='path').

| variant | engine_return | report_return | return_delta | engine_maxDD | report_maxDD | maxDD_delta | engine_sharpe | report_sharpe | sharpe_delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_20d | -0.081789 | -0.081789 | 0.000000 | 0.457000 | 0.457000 | 0.000000 | -0.103494 | -0.103494 | 0.000000 |
| risk_0p005 | 0.106070 | 0.106070 | 0.000000 | 0.144072 | 0.144072 | 0.000000 | 0.843448 | 0.843448 | 0.000000 |
| risk_0p010 | 0.147513 | 0.147513 | 0.000000 | 0.267600 | 0.267600 | 0.000000 | 0.653023 | 0.653023 | 0.000000 |

## Blockers

- none
