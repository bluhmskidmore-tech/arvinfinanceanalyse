# 2026-07 Batch 3 Gate Exposure Repair Report

- status: blocked
- target: fallback ratio < 10%, ideally 0; current data remains blocked.
- explanation: Calendar-day readiness includes every date in the execution window; trading-day ratios are measured on portfolio equity-curve dates.

## Calendar-Day Exposure Readiness

| date_count | persisted_rows | replayed_rows | fallback_rows | fallback_ratio | missing_dates_total |
|---:|---:|---:|---:|---:|---:|
| 637 | 0 | 113 | 524 | 0.822606 | 524 |

- source_counts: {'missing': 524, 'replayed': 113}
- missing_date_ranges: [{'start': '2024-09-25', 'end': '2025-12-29', 'days': 461}, {'start': '2026-01-01', 'end': '2026-01-04', 'days': 4}, {'start': '2026-01-10', 'end': '2026-01-11', 'days': 2}, {'start': '2026-01-17', 'end': '2026-01-18', 'days': 2}, {'start': '2026-01-24', 'end': '2026-01-25', 'days': 2}, {'start': '2026-01-31', 'end': '2026-02-01', 'days': 2}, {'start': '2026-02-07', 'end': '2026-02-08', 'days': 2}, {'start': '2026-02-14', 'end': '2026-02-23', 'days': 10}, {'start': '2026-02-28', 'end': '2026-03-01', 'days': 2}, {'start': '2026-03-07', 'end': '2026-03-08', 'days': 2}, {'start': '2026-03-14', 'end': '2026-03-15', 'days': 2}, {'start': '2026-03-21', 'end': '2026-03-22', 'days': 2}, {'start': '2026-03-28', 'end': '2026-03-29', 'days': 2}, {'start': '2026-04-04', 'end': '2026-04-06', 'days': 3}, {'start': '2026-04-11', 'end': '2026-04-12', 'days': 2}, {'start': '2026-04-18', 'end': '2026-04-19', 'days': 2}, {'start': '2026-04-25', 'end': '2026-04-26', 'days': 2}, {'start': '2026-05-01', 'end': '2026-05-05', 'days': 5}, {'start': '2026-05-09', 'end': '2026-05-10', 'days': 2}, {'start': '2026-05-16', 'end': '2026-05-17', 'days': 2}, {'start': '2026-05-23', 'end': '2026-05-24', 'days': 2}, {'start': '2026-05-30', 'end': '2026-05-31', 'days': 2}, {'start': '2026-06-06', 'end': '2026-06-07', 'days': 2}, {'start': '2026-06-13', 'end': '2026-06-14', 'days': 2}, {'start': '2026-06-19', 'end': '2026-06-21', 'days': 3}]

## Trading-Day Equity-Curve Coverage

| variant | status | equity_curve_days | per_date_actual_days | state_max_fallback_days | fallback_ratio |
|---|---|---:|---:|---:|---:|
| fixed_20d_equal | blocked | 382 | 86 | 296 | 0.774869 |
| risk_budget_rpt_0p005 | blocked | 382 | 86 | 296 | 0.774869 |
| risk_budget_rpt_0p01 | blocked | 382 | 86 | 296 | 0.774869 |

The calendar-day ratio answers data-pipeline coverage; the trading-day ratio answers how much of the simulated equity curve still used the max policy exposure fallback.
Synthetic exposure-matched baselines remain controls only and do not prove real gate coverage.
