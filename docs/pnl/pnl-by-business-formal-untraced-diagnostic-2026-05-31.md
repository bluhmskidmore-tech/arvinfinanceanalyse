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

## Interpretation

- The page warning is real reconciliation evidence, not a front-end display bug.
- The formal primary tab should remain reconciliation-only: do not mix formal primary into monthly/YTD conclusions.
- Owner approval now allows relaxing `cost_center` only as a fallback after strict matching misses; report date, instrument, portfolio, currency, and asset scope remain strict.
- The zero-balance `A/T/H` distribution shown by the page is useful triage evidence, but it is not a new business metric.

## Next Governance Actions

- Validate the business dictionary for `invest_type_std` codes `A`, `T`, and `H`.
- Investigate `no_same_instrument_in_balance` rows as matured/sold/no-position accruals versus missing ZQTZ balance ingestion.
- Re-run the formal read path after controlled `cost_center` fallback and confirm remaining untraced rows are no-same-instrument/no-balance cases.
- Use `docs/pnl/pnl-by-business-formal-untraced-detail-packet-2026-05-31.md` as the owner triage packet for priority row review.
- Keep `/pnl-by-business` as a temporary-exception route until formal untraced evidence is closed or explicitly accepted by governance.
