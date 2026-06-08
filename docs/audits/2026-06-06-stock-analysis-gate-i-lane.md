# Stock Analysis Observational Gate I Lane

Date: 2026-06-06

Route: `/stock-analysis`

Page ID: `GAP-STOCK-ANALYSIS-PAGE`

Primary API: `/ui/market-data/livermore`

Status: `gate-i-gap`

Business-contract certified: `false`

Formal use allowed: `false`

## Purpose

This lane defines the direct review path for `/stock-analysis`. It keeps the page scoped as an observational analytics surface and prevents Livermore diagnostics, proxy backtests, or signal summaries from being treated as formal trading advice or certified business metrics.

## Direct Decision Surface

The first-screen review surface is driven by `GET /ui/market-data/livermore` through `marketDataClient`, `StockAnalysisPage`, and `stockAnalysisPageModel`.

Visible first-screen decision-support values include:

| Visible value | Current route source | Certification status |
| --- | --- | --- |
| Livermore candidate observations | `/ui/market-data/livermore` | not certified |
| signal confluence diagnostics | `/ui/market-data/livermore/signal-confluence` | observational only |
| strategy score and optimization diagnostics | `/ui/market-data/livermore/strategy-score` and `/strategy-optimization` | not certified |
| proxy backtest summaries | `/cycle-proxy-backtest` and `/candidate-history-portfolio-backtest` | reduced proxy evidence only |
| risk-exit readiness | backend-owned Livermore risk-exit logic | blocked until required inputs are ready |
| as-of date, stale, fallback, unsupported, and no-data states | Livermore envelopes and page model | must remain visible |

Supporting surfaces include stock detail, candidate history, sector rank series, signal confluence, strategy diagnostics, and proxy backtests.

## Observational Boundaries

Any future certification must separately review:

- PAGE-STOCK or approved route contract scope
- MTR-STOCK metric dictionary rows, if any are proposed
- unit, precision, null, stale, fallback, and date rules
- candidate ranking semantics
- signal confluence weighting and explainability
- proxy backtest sample maturity and limitations
- risk-exit input readiness, including holdings, entry cost, close history, and gate supplement evidence
- no-trading-instruction and no-execution-approval language
- lineage records, golden samples, manual audit review, and business-owner approval

Browser cleanliness does not certify those values.

## Forbidden Claims

- `/stock-analysis` is business-contract certified.
- Livermore observations are formal trading instructions.
- Strategy score, signal confluence, sector ranking, or proxy backtest output is execution approval.
- GAP-STOCK-ANALYSIS-PAGE has a standalone PAGE-STOCK contract.
- Any stock-analysis field is an approved `MTR-*` metric.
- Missing stock, candidate-history, sector, signal, risk-exit, or proxy-backtest rows can be backfilled with static demo values in real mode.

## Required Closure Work

Before `/stock-analysis` can be called business-contract certified, it needs:

1. A standalone route contract or explicitly approved observational-only certification scope.
2. Direct metric dictionary rows for any field proposed as certified.
3. A golden-sample boundary for the selected page/API payloads.
4. Catalog/date evidence for the configured Livermore and candidate-history tables.
5. Governance-record validation for the direct route/API surface.
6. Manual audit review of date, stale, fallback, unsupported, proxy-backtest, risk-exit, and no-data states.
7. Business-owner approval captured by a strict checker.

## Current Allowed Claim

`/stock-analysis` has a direct, machine-visible observational Gate I lane and a frontend-ready review surface. It is not business-contract certified and does not provide trading instructions.

## Current Forbidden Promotions

- Do not promote `GAP-STOCK-ANALYSIS-PAGE` to `PAGE-STOCK-*` without a route contract and owner approval.
- Do not create or imply `MTR-STOCK-*` approval from Livermore diagnostics.
- Do not treat proxy backtests as formal portfolio strategy validation.
- Do not turn read-only diagnostics into position-change commands, allocation advice, or execution approval.
