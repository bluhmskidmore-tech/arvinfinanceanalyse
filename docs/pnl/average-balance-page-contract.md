# Average Balance Candidate Page Contract

## Purpose

This document defines the current review contract for `/average-balance` as a candidate analytical ADB page. It is not a formal page approval, not a replacement for `PAGE-BALANCE-001`, and not an owner approval.

## Page Identity

- Page ID: `PAGE-ADB-001`
- Contract binding: `PAGE-ADB-001`
- Page slug: `average-balance`
- Frontend route: `/average-balance`
- Primary API: `GET /api/analysis/adb`
- Supporting APIs:
  - `GET /api/analysis/adb/comparison`
  - `GET /api/analysis/adb/monthly`
  - `GET /api/analysis/adb/coverage`
  - `GET /ui/balance-analysis/dates`
- Current status: `candidate_or_pending`
- Formal use allowed: `formal_use_allowed=false`

## Primary Business Question

The page answers: for a selected date range, how do daily average asset and liability balances compare with ending spot balances, and what candidate explanatory categories drive the difference?

The page must show the ADB analytical boundary clearly and must not imply that interval ADB values are the formal balance truth.

## Metric Boundary

Daily sample-bound candidate metrics:

- `MTR-ADB-001`: interval daily average total assets, from `GET /api/analysis/adb` summary.
- `MTR-ADB-002`: interval daily average total liabilities, from `GET /api/analysis/adb` summary.

Monthly sample-bound candidate metric:

- `MTR-ADB-003`: YTD spread / monthly ADB-NIM view, from `GET /api/analysis/adb/monthly`; this metric has candidate sample coverage through `GS-AVERAGE-BALANCE-MONTHLY-A`.

`GS-AVERAGE-BALANCE-A` freezes only the daily ADB candidate DTO for `MTR-ADB-001` and `MTR-ADB-002`. `GS-AVERAGE-BALANCE-MONTHLY-A` freezes selected monthly ADB/NIM candidate DTO fields for `MTR-ADB-003`. Neither sample approves formal balance truth, manual audit closure, page closure, or business-owner approval.

## Denominator Semantics

The page must keep denominator semantics visible when they are present in result metadata or coverage output:

- `observed`: average over dates with observed source rows.
- `LOCF`: last-observation-carried-forward analytical fill, when explicitly provided by backend evidence.
- `calendar-zero`: calendar-day denominator where missing dates contribute zero, only when explicitly stated by backend evidence.

Frontend code must not infer, swap, or silently relabel these denominator modes. Missing or unavailable denominator metadata must be surfaced as pending or no-data evidence, not filled with demo values.

## Formal Truth Boundary

- Formal balance truth remains `PAGE-BALANCE-001` and `/balance-analysis`.
- `/average-balance` may use formal balance daily tables as source anchors, but that does not make the ADB interval result a formal balance value.
- Do not replace `/balance-analysis` totals, report-date controls, or closure evidence with `/average-balance` ADB output.
- Do not promote `MTR-ADB-001` through `MTR-ADB-003` to formal use until page contract approval, golden approval, direct lineage/governance records, live UI/API evidence, manual audit review, and business-owner approval are complete.

## Required Evidence Before Closure

- Direct page/API governance record for `PAGE-ADB-001` and `/api/analysis/adb`.
- Catalog/date evidence for:
  - `fact_formal_zqtz_balance_daily`
  - `fact_formal_tyw_balance_daily`
  - `zqtz_bond_daily_snapshot`
  - `tyw_interbank_daily_snapshot`
- Golden sample review for `GS-AVERAGE-BALANCE-A`, limited to the daily candidate DTO.
- Golden sample review for `GS-AVERAGE-BALANCE-MONTHLY-A`, limited to selected monthly ADB/NIM candidate DTO fields.
- Live smoke evidence for visible candidate, stale, fallback, no-data, denominator, date-range, and `result_meta` states.
- Completed owner evidence packet and signed business-owner approval template.

## Prohibitions

- Do not set `formal_use_allowed=true` for `/average-balance`.
- Do not use `GS-AVERAGE-BALANCE-A` or `GS-AVERAGE-BALANCE-MONTHLY-A` as metric approval, page approval, or business-owner approval.
- Do not hide candidate-only, stale, fallback, denominator, or no-data states.
- Do not backfill missing ADB, monthly, comparison, or coverage rows with static demo values.
- Do not treat written governance evidence as owner approval or live page execution proof.
