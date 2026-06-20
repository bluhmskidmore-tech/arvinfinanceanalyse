# PnL By Business Formal Untraced Diagnostic 2026-05-31

Status: read-only diagnostic. This note supports `/pnl-by-business` reconciliation evidence; it is not a metric contract and not a formal promotion. A later owner decision allows controlled `cost_center` relaxed fallback after strict matching misses.

## Purpose

Record why the formal primary tab shows an untraced warning on 2026-05-31, using only existing local DuckDB facts and the current API join grain.

The finding is a data-quality and reconciliation follow-up. It should not mix formal primary into monthly/YTD conclusions, and it should not replace the page contract `PAGE-PNL-BY-BUSINESS-001`.

## Grain

Formal FI PnL rows are traced to ZQTZ asset balance rows by:

- `report_date`
- `instrument_code`
- `portfolio_name`
- `cost_center`
- `currency_basis`
- `position_scope = 'asset'`

The current API counts a formal FI PnL row as untraced when this join does not return a non-blank ZQTZ `business_type_primary`.

## Source Counts

For `report_date = 2026-05-31`:

| Source | Filter | Rows |
| --- | --- | ---: |
| `fact_formal_pnl_fi` | `report_date = 2026-05-31` | 1684 |
| `fact_nonstd_pnl_bridge` | `report_date = 2026-05-31` | 145 |
| `fact_formal_zqtz_balance_daily` | `report_date = 2026-05-31 and position_scope = 'asset'` | 3420 |

## Result

| Check | Untraced rows | Total PnL yuan |
| --- | ---: | ---: |
| Strict API-compatible join | 148 | 4,465,365.25 |
| Loose `BOND-` prefix compatibility join | 148 | 4,465,365.25 |

The loose prefix check did not reduce the warning, so this is not explained by a `BOND-` instrument-code prefix mismatch.

## Invest-Type Split

| `invest_type_std` | Rows | Total PnL yuan |
| --- | ---: | ---: |
| `T` | 94 | 338,198.87 |
| `A` | 40 | 3,911,770.06 |
| `H` | 14 | 215,396.32 |

## Cause Buckets

| `invest_type_std` | Cause bucket | Rows | Total PnL yuan |
| --- | --- | ---: | ---: |
| `A` | `no_same_instrument_in_balance` | 31 | 3,511,371.77 |
| `A` | `cost_center_mismatch` | 9 | 400,398.29 |
| `H` | `no_same_instrument_in_balance` | 14 | 215,396.32 |
| `T` | `no_same_instrument_in_balance` | 78 | 338,198.77 |
| `T` | `cost_center_mismatch` | 16 | 0.10 |

Most rows have no same-instrument asset balance row on the same report date. A smaller subset has same instrument/portfolio/currency evidence, but the current strict key does not match because `cost_center` differs.

## Post-Relaxed Residual Split

After owner-approved `cost_center` relaxed fallback, the remaining `123` rows are still reconciliation follow-up. A read-only rerun against `data/moss.duckdb` splits them by balance evidence:

| Residual evidence bucket | Invest type | Rows | Total PnL yuan | Absolute PnL yuan |
| --- | --- | ---: | ---: | ---: |
| `position_absent_before_maturity` | `A` | 21 | 2,916,063.75 | 2,916,063.75 |
| `position_absent_before_maturity` | `T` | 14 | 603,782.26 | 603,782.52 |
| `matured_before_or_on_report_date` | `A` | 7 | 583,565.28 | 583,565.28 |
| `matured_before_or_on_report_date` | `T` | 10 | -265,583.51 | 279,339.65 |
| `matured_before_or_on_report_date` | `H` | 11 | 182,436.76 | 182,436.76 |
| `position_absent_before_maturity` | `H` | 3 | 32,959.56 | 32,959.56 |
| `never_seen_in_zqtz_asset_balance` | `A` | 3 | 11,742.74 | 11,742.74 |
| `never_seen_in_zqtz_asset_balance` | `T` | 54 | 0.02 | 0.22 |

This split is evidence only. `position_absent_before_maturity` means the same instrument existed in historical ZQTZ asset balance but not on `2026-05-31`, so it still needs owner confirmation as sold/no-position accrual versus missing same-date balance. `matured_before_or_on_report_date` is the strongest candidate for expected no-position reconciliation. `never_seen_in_zqtz_asset_balance` is mostly immaterial T-class rounding/tail rows, except one A-class row requiring source review.

## Interpretation

- The page warning is real reconciliation evidence, not a front-end display bug.
- The formal primary tab should remain reconciliation-only: do not mix formal primary into monthly/YTD conclusions.
- Owner approval now allows relaxing `cost_center` only as a fallback after strict matching misses; report date, instrument, portfolio, currency, and asset scope remain strict.
- The zero-balance `A/T/H` and residual evidence distributions shown by the page are useful triage evidence, but they are not new business metrics.

## Next Governance Actions

- Validate the business dictionary for `invest_type_std` codes `A`, `T`, and `H`.
- Investigate `position_absent_before_maturity` rows first as sold/no-position accruals versus missing same-date ZQTZ balance ingestion.
- Review the one material `never_seen_in_zqtz_asset_balance` A-class row (`09260202`, 11,742.74 yuan); T-class never-seen rows are immaterial tail rows in the current evidence.
- Use `docs/pnl/pnl-by-business-formal-untraced-detail-packet-2026-05-31.md` as the owner triage packet for priority row review.
- Keep `/pnl-by-business` as a temporary-exception route until formal untraced evidence is closed or explicitly accepted by governance.
