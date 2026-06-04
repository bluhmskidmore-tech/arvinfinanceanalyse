# PnL By Business Formal Untraced Detail Packet 2026-05-31

Status: owner triage packet. This is reconciliation evidence for `/pnl-by-business`; it is not a metric contract. Owner approval now allows a controlled `cost_center` relaxed fallback only after the strict trace grain misses.

## Purpose

Turn the formal primary warning into an owner-review packet. The page showed 148 formal FI PnL rows not traced to ZQTZ asset balance under the previous strict join. This packet lists the highest-impact rows and records the owner decision that `cost_center` may be relaxed as a fallback, while remaining no-same-instrument rows still need business review.

This packet must stay separate from monthly/YTD business conclusions. It supports reconciliation closure only.

## Current Trace Grain

Formal FI PnL rows are traced to ZQTZ asset balance rows by:

- `report_date`
- `instrument_code`
- `portfolio_name`
- `cost_center` first; if strict trace misses, `cost_center` may be relaxed by owner approval
- `currency_basis`
- `position_scope = 'asset'`

Rows below were untraced under the pre-approval strict join when the join did not return a non-blank ZQTZ `business_type_primary`.

## Executive Summary

| Check | Rows | Total PnL yuan | Absolute PnL yuan |
| --- | ---: | ---: | ---: |
| Untraced formal FI rows | 148 | 4,465,365.25 | 5,010,288.97 |
| `no_same_instrument_in_balance` | 123 | 4,064,966.86 | 4,609,890.48 |
| `cost_center_mismatch` | 25 | 400,398.39 | 400,398.49 |

The highest-impact issue is not a `BOND-` prefix mismatch. Most exposure comes from formal PnL rows with no same-instrument asset balance on 2026-05-31. A smaller set has same-instrument balance candidates where strict `cost_center` matching blocked the trace before owner approval.

## Priority Rows By Absolute PnL

| Rank | Invest type | Cause bucket | Instrument | Portfolio | Cost center | Currency | Total PnL yuan | Triage owner question |
| ---: | --- | --- | --- | --- | --- | --- | ---: | --- |
| 1 | `T` | `no_same_instrument_in_balance` | `2120046` | `FIOA` | `5010` | CNY | 603,782.19 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 2 | `A` | `no_same_instrument_in_balance` | `115364` | `FIOA` | `5010` | CNY | 519,780.82 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 3 | `A` | `no_same_instrument_in_balance` | `102381245` | `FIOA` | `5010` | CNY | 398,904.11 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 4 | `A` | `no_same_instrument_in_balance` | `250218` | `FIOA` | `5010` | CNY | 304,996.60 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 5 | `A` | `no_same_instrument_in_balance` | `032380473` | `FIOA` | `5010` | CNY | 236,301.37 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 6 | `A` | `no_same_instrument_in_balance` | `251117` | `FIOA` | `5010` | CNY | 214,619.18 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 7 | `A` | `no_same_instrument_in_balance` | `250218` | `FIOA` | `501060` | CNY | 198,465.99 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 8 | `A` | `no_same_instrument_in_balance` | `148288.SZ` | `FIOA` | `5010` | CNY | 189,287.67 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 9 | `A` | `no_same_instrument_in_balance` | `251037` | `FIOA` | `5010` | CNY | 158,356.17 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 10 | `A` | `no_same_instrument_in_balance` | `251060` | `FIOA` | `5010` | CNY | 156,027.40 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 11 | `A` | `no_same_instrument_in_balance` | `102681643` | `FIOA` | `5010` | CNY | 151,246.57 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 12 | `A` | `no_same_instrument_in_balance` | `250306` | `FIOA` | `501060` | CNY | 144,628.45 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 13 | `A` | `cost_center_mismatch` | `260303` | `FIOA` | `50106001` | CNY | 133,823.81 | Can cost_center be normalized or relaxed for this trace grain? |
| 14 | `A` | `no_same_instrument_in_balance` | `250211` | `FIOA` | `5010` | CNY | 116,374.43 | Does this PnL row represent matured, sold, or no-position accrual activity? |
| 15 | `A` | `no_same_instrument_in_balance` | `188155` | `FIOA` | `5020` | CNY | 96,869.29 | Does this PnL row represent matured, sold, or no-position accrual activity? |

## Cost-Center Candidate Matches

These rows have same-instrument balance candidates on the same report date. Owner approval allows these to use a controlled relaxed `cost_center` fallback after strict matching misses.

| Instrument | PnL cost center | Balance cost center candidates | Candidate balance rows | Total PnL yuan | Owner decision |
| --- | --- | --- | ---: | ---: | --- |
| `260303` | `50106001` | `501060` | 1 | 133,823.81 | Approved: controlled `cost_center` relaxed fallback |
| `250215` | `50202001` | `50102002`, `50104002`, `501060`, `50106001` | 4 | 70,737.95 | Approved: controlled `cost_center` relaxed fallback |
| `250215` | `50104001` | `50102002`, `50104002`, `501060`, `50106001` | 4 | 70,626.88 | Approved: controlled `cost_center` relaxed fallback |
| `260205` | `5010200201` | `5010200101`, `501060`, `50106001` | 3 | 60,564.86 | Approved: controlled `cost_center` relaxed fallback |
| `250220` | `5010200101` | `50104002`, `5020200101` | 2 | 36,803.36 | Approved: controlled `cost_center` relaxed fallback |

## Coverage

| Slice | Total PnL yuan | Absolute PnL yuan |
| --- | ---: | ---: |
| Top 5 absolute rows | 2,063,765.09 | 2,063,765.09 |
| Top 10 absolute rows | 2,980,521.50 | 2,980,521.50 |
| Top 15 absolute rows | 3,623,464.05 | 3,623,464.05 |
| Top 20 absolute rows | 3,889,222.65 | 4,040,140.27 |
| All untraced rows | 4,465,365.25 | 5,010,288.97 |

Reviewing the top 20 absolute rows covers most of the untraced amount. The remaining rows still need classification, but they are lower priority for first-pass governance closure.

## Owner Decision Questions

For `no_same_instrument_in_balance`:

- Does this PnL row represent matured, sold, or no-position accrual activity?
- If yes, should the page evidence classify it as an expected no-position reconciliation item?
- If no, is the ZQTZ balance ingestion missing a same-date asset row?

For `cost_center_mismatch`:

- Can cost_center be normalized or relaxed for this trace grain?
- Owner answer: yes, use controlled relaxed fallback only after strict trace misses.
- Keep report date, instrument code, portfolio, currency basis, and `position_scope = 'asset'` strict.

For `invest_type_std`:

- Confirm the owner-approved meanings of `A`, `T`, and `H`.
- Confirm whether any type should be excluded from formal FI-to-ZQTZ balance tracing.

## Required Closure After Rule Change

After the relaxed fallback is implemented, re-run the read path and confirm:

- `cost_center_mismatch` rows are no longer counted as formal untraced rows when same-date, same-instrument, same-portfolio, same-currency asset balance evidence exists.
- No-same-instrument rows remain visible as formal reconciliation follow-up.
- Monthly/YTD business conclusions remain separate from formal primary reconciliation.

Until then, `/pnl-by-business` should continue to show formal primary as reconciliation evidence only, separate from monthly/YTD business analysis.
