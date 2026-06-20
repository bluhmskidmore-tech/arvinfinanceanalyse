# Bond Analysis Direct Gate I Lane

Date: 2026-06-06

Route: `/bond-analysis`

Page ID: `PAGE-BOND-ANALYSIS-001`

Primary API: `/api/bond-analytics/action-attribution`

Status: `evidence-pending`

Business-contract certified: `false`

Formal use allowed: `false`

## Purpose

This lane defines the direct certification path for `/bond-analysis`. It prevents a clean browser surface or `/bond-dashboard` evidence from being treated as fixed-income business-contract certification.

## Direct Decision Surface

The first-screen decision cockpit is driven by `GET /api/bond-analytics/action-attribution` through `getBondAnalyticsActionAttribution` and `BondAnalyticsViewContent`.

Visible first-screen decision values include:

| Visible value | Current route source | Certification status |
| --- | --- | --- |
| action-attribution PnL | `/api/bond-analytics/action-attribution` | not certified |
| duration action/change | `/api/bond-analytics/action-attribution` and KRD/duration modules | not certified |
| period start/end DV01 | `/api/bond-analytics/action-attribution` and DV01 modules | not certified |
| warning count and warning detail | action-attribution payload plus module warnings | not certified |
| report date and period type | `/api/bond-analytics/dates` and page filters | not certified |
| result_meta basis / formal-use state | action-attribution envelope | not certified |

Supporting module surfaces include DV01 risk, DV01 reconciliation, KRD curve risk, return decomposition, benchmark excess, credit-spread migration, portfolio headlines, top holdings, position changes, accounting-class audit, yield-curve term structure, and credit-spread detail.

## Fixed-Income Boundaries

Any future certification must separately review:

- DV01 scale and sign convention
- duration in years
- KRD/duration curve-risk units
- yield or YTM percent display
- bp movement for curve or spread changes
- action-attribution PnL unit and sign
- market value amount scale
- holdings grain and top-holdings selection
- accounting class filter semantics
- report date, period type, fallback, stale, no-data, warning, vendor status, and `formal_use_allowed`

Browser cleanliness does not certify any of those values.

## Non-Reusable Evidence

Do not use these artifacts to certify `/bond-analysis`:

| Artifact | Why it is non-reusable |
| --- | --- |
| `PAGE-BOND-001` | It names route `/bond-dashboard`, not `/bond-analysis`. |
| `GS-BOND-HEADLINE-A` | It captures `GET /api/bond-dashboard/headline-kpis`, not `/api/bond-analytics/*`. |
| `MTR-BOND-001` through `MTR-BOND-004` | They are candidate headline metrics bound to `/bond-dashboard` and `GS-BOND-HEADLINE-A`. |
| `/bond-dashboard` browser evidence | It proves a different route surface. |

## Required Closure Work

Before `/bond-analysis` can be called top investment-bank-grade at the business-contract level, it needs:

1. A direct `/bond-analysis` page contract or an explicitly approved alias decision.
2. Direct metric dictionary rows for the fixed-income decision values that are meant to be certified.
3. Golden-sample boundary for `/api/bond-analytics/*` payloads used by the page.
4. Catalog/date evidence for the configured bond-analytics tables.
5. Governance-record validation for the direct route/API surface.
6. Manual audit review of fixed-income units, signs, grains, stale/fallback/no-data states, and source lineage.
7. Business-owner approval captured by a strict checker.

## Current Allowed Claim

`/bond-analysis` has a direct, machine-visible Gate I lane and a frontend-ready surface. It is not business-contract certified.

## Current Forbidden Claims

- `/bond-analysis` is business-contract certified.
- `PAGE-BOND-001` is an alias for `/bond-analysis`.
- `GS-BOND-HEADLINE-A` certifies `/bond-analysis`.
- Browser evidence proves DV01, duration, yield, KRD, credit-spread, holdings, or action-attribution metric correctness.
- Bond dashboard candidate metrics approve BondAnalyticsView values.
