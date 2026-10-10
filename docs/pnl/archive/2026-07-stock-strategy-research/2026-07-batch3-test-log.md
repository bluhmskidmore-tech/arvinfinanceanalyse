# 2026-07 Batch 3 Test Log

- run_date: 2026-07-05
- repo: F:/MOSS-V3
- scope: Batch 3 revised research/report-only package

## Report Generation

Command:

```text
python scripts/run_batch3_stock_strategy_research.py --db-path data/moss.duckdb --output-dir docs/pnl
```

Output:

```text
{"data_readiness": {"report_path": "docs\\pnl\\2026-07-batch3-data-readiness-report.md", "status": "blocked"}, "entry_premium": {"report_path": "docs\\pnl\\2026-07-batch3-entry-premium-interaction-report.md", "status": "research_only"}, "hold_progress_exit": {"report_path": "docs\\pnl\\2026-07-batch3-hold-progress-exit-simulation-report.md", "status": "research_only"}, "reports": {"report_path": null, "status": null}, "risk_budget": {"report_path": "docs\\pnl\\2026-07-batch3-risk-budget-robustness-report.md", "status": "research_only"}, "summary": {"report_path": "docs\\pnl\\2026-07-batch3-summary.md", "status": "research_only"}}
```

## Focused Batch 3 Tests

Command:

```text
python -m pytest tests/test_batch3_stock_strategy_research.py -q
```

Output:

```text
..............                                                           [100%]
14 passed in 0.28s
```

## Ruff

Command:

```text
python -m ruff check scripts/run_batch3_stock_strategy_research.py tests/test_batch3_stock_strategy_research.py
```

Output:

```text
All checks passed!
```

## Batch 2 / Portfolio Focused Regression

Command:

```text
python -m pytest tests/test_portfolio_backtest.py tests/test_portfolio_paths.py tests/test_gate_exposure_series.py tests/test_walk_forward_threshold_scan.py tests/test_matched_baseline.py tests/test_batch3_stock_strategy_research.py -q
```

Output:

```text
............................................................             [100%]
60 passed in 2.35s
```

## Strategy Policy Contract

Command:

```text
python -m pytest backend/tests/core_finance/test_strategy_policy.py -q
```

Output:

```text
....                                                                     [100%]
4 passed in 0.71s
```
