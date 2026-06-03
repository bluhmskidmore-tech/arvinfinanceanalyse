# PnL By Business Formal Untraced Detail Packet 2026-05-31

Status: owner triage packet. This is read-only reconciliation evidence for `/pnl-by-business`; it is not a metric contract, not a backend matching-rule change, and not an approval to relax the formal trace grain.

## Purpose

Turn the formal primary warning into an owner-review packet. The page already shows that 148 formal FI PnL rows are not traced to ZQTZ asset balance under the current strict join. This packet lists the highest-impact rows and the exact owner decisions needed before any code or backend matching rule changes.

This packet must stay separate from monthly/YTD business conclusions. It supports reconciliation closure only.

## Current Trace Grain

Formal FI PnL rows are traced to ZQTZ asset balance rows by:

- `report_date`
- `instrument_code`
- `portfolio_name`
- `cost_center`
- `currency_basis`
- `position_scope = 'asset'`

Rows below are untraced when the join does not return a non-blank ZQTZ `business_type_primary`.

## Executive Summary

| Check | Rows | Total PnL yuan | Absolute PnL yuan |
| --- | ---: | ---: | ---: |
| Untraced formal FI rows | 148 | 4,465,365.25 | 5,010,288.97 |
| `no_same_instrument_in_balance` | 123 | 4,064,966.86 | 4,609,890.48 |
| `cost_center_mismatch` | 25 | 400,398.39 | 400,398.49 |

The highest-impact issue is not a `BOND-` prefix mismatch. Most exposure comes from formal PnL rows with no same-instrument asset balance on 2026-05-31. A smaller set has same-instrument balance candidates, but strict `cost_center` matching blocks the trace.

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
| 14 | `A` | `cost_center_mismatch` | `250215` | `FIOA` | `50202001` | CNY | 70,737.95 | Can cost_center be normalized or relaxed for this trace grain? |
| 15 | `A` | `cost_center_mismatch` | `250215` | `FIOA` | `50104001` | CNY | 70,626.88 | Can cost_center be normalized or relaxed for this trace grain? |

## Cost-Center Candidate Matches

These rows have same-instrument balance candidates on the same report date, but current strict matching does not trace them because `cost_center` differs.

| Instrument | PnL cost center | Balance cost center candidates | Candidate balance rows | Total PnL yuan | Owner decision |
| --- | --- | --- | ---: | ---: | --- |
| `260303` | `50106001` | `501060` | 1 | 133,823.81 | Can cost_center be normalized or relaxed for this trace grain? |
| `250215` | `50202001` | `50102002`, `50104002`, `501060`, `50106001` | 4 | 70,737.95 | Can cost_center be normalized or relaxed for this trace grain? |
| `250215` | `50104001` | `50102002`, `50104002`, `501060`, `50106001` | 4 | 70,626.88 | Can cost_center be normalized or relaxed for this trace grain? |
| `260205` | `5010200201` | `5010200101`, `501060`, `50106001` | 3 | 60,564.86 | Can cost_center be normalized or relaxed for this trace grain? |
| `250220` | `5010200101` | `50104002`, `5020200101` | 2 | 36,803.36 | Can cost_center be normalized or relaxed for this trace grain? |

## Coverage

| Slice | Total PnL yuan | Absolute PnL yuan |
| --- | ---: | ---: |
| Top 5 absolute rows | 2,063,765.09 | 2,063,765.09 |
| Top 10 absolute rows | 2,980,521.50 | 2,980,521.50 |
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
- If yes, what is the approved normalization dictionary and effective date?
- If no, should these rows remain visible as strict-trace exceptions?

For `invest_type_std`:

- Confirm the owner-approved meanings of `A`, `T`, and `H`.
- Confirm whether any type should be excluded from formal FI-to-ZQTZ balance tracing.

## Required Closure Before Code Change

Do not change backend join logic until owners approve one of these outcomes:

- Keep strict trace grain and accept these rows as formal reconciliation exceptions.
- Add an approved cost-center normalization rule with tests and lineage evidence.
- Add an approved no-position classification rule with tests and lineage evidence.
- Fix missing balance ingestion upstream, then re-run the same read-only diagnostic.

Until then, `/pnl-by-business` should continue to show formal primary as reconciliation evidence only, separate from monthly/YTD business analysis.
