# 2026-07 Batch 3 Adjustment Factor Gap V2 Report

- status: blocked
- missing_adjustment_factor_rows: 3564
- missing_adjustment_factor_ratio: 0.175922
- clean_path_count: 84
- clean_execution_row_count: 93
- clean_subset_share: 0.112591
- sample_selection_warning: clean subset may be biased because only paths with complete adjustment factors remain

## Adjustment Factor Table Diagnostics

- table_status: ready
- row_count: 589256
- date_count: 350
- stock_code_count: 1689
- first_date: 2024-08-30
- last_date: 2026-06-22
- missing_path_date_count: 61
- missing_path_dates_present_in_adj_table: 0
- missing_path_dates_absent_from_adj_table: 61
- diagnosis: Path-level gaps are concentrated on dates absent from the local adj_factor table; do not forward-fill factors without vendor-backed lineage.

### Top Missing Path Dates

| trade_date | missing_rows |
|---|---:|
| 2025-01-02 | 112 |
| 2025-03-21 | 109 |
| 2025-01-03 | 106 |
| 2025-01-06 | 100 |
| 2025-04-01 | 91 |
| 2025-01-08 | 90 |
| 2025-04-02 | 85 |
| 2025-10-28 | 82 |
| 2025-04-03 | 81 |
| 2025-04-07 | 80 |
| 2025-11-04 | 79 |
| 2025-01-10 | 78 |
| 2025-06-11 | 78 |
| 2025-11-11 | 78 |
| 2025-11-14 | 78 |
| 2025-08-12 | 76 |
| 2025-06-13 | 75 |
| 2025-06-18 | 75 |
| 2025-09-03 | 75 |
| 2025-08-13 | 74 |

## Missing By Month

| month | missing_rows |
|---|---:|
| 2025-01 | 823 |
| 2025-04 | 668 |
| 2025-11 | 438 |
| 2025-06 | 360 |
| 2025-08 | 224 |
| 2025-09 | 217 |
| 2025-07 | 155 |
| 2025-10 | 153 |
| 2025-05 | 128 |
| 2024-10 | 121 |
| 2025-03 | 109 |
| 2024-11 | 71 |
| 2025-12 | 52 |
| 2026-06 | 34 |
| 2024-09 | 6 |
| 2026-03 | 5 |

## Missing By Board

| board | missing_rows |
|---|---:|
| Shanghai_main | 1426 |
| Shenzhen_main | 1259 |
| ChiNext | 561 |
| STAR | 318 |

## Clean-Subset Sensitivity

- status: ready
- risk_0p005_return_delta: -0.274087
- risk_0p005_mdd_delta: 0.009928
- risk_0p005_still_beats_fixed_20d: False

## Blockers

- adjustment factor gaps remain in price paths
- clean adjustment subset share is below 80%; promotion conclusions would be sample-biased

Stop condition: this remains no-go until missing adjustment factor paths are filled or excluded with explicit sample-bias disclosure.
