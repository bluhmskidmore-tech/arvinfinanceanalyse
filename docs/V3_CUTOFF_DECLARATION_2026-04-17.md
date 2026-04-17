# V3 Cutoff Declaration (2026-04-17)

## Status

- declaration type: maintainer release statement
- release decision: `GO`
- decision date: `2026-04-17`
- decision owner: `current workspace maintainer delegate (Codex, per in-thread instruction)`
- scope: current governed `Phase 2` formal-compute release only

## Candidate Release Scope

This declaration applies only to the currently included release surface:

- formal balance
- formal PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal read surfaces
- `executive-consumer cutover v1`
  - `/ui/home/overview`
  - `/ui/home/summary`
  - `/ui/pnl/attribution`

It is not a statement that the whole repo is live.

## Required Evidence

Canonical backend gate:

- `python scripts/backend_release_suite.py`
- result: `141 passed in 228.49s (0:03:48)`

Frontend verification:

- `cd frontend && npm run lint`
  - result: passed with `0 errors, 5 warnings`
- `cd frontend && npm run test`
  - result: `79` test files passed; `393` tests passed
- `cd frontend && npm run build`
  - result: passed; vendor chunk-size warnings remain non-blocking

Code-level excluded/reserved route verification:

- `python -m pytest -q tests/test_executive_dashboard_endpoints.py tests/test_cube_query_api.py tests/test_liability_analytics_api.py tests/test_liability_analytics_envelope_contract.py`
- result: `13 passed`

Live preflight:

- `python scripts/governed_phase2_preflight.py`
- result: `pass`
- summary: `24 pass`, `0 blocked`, `0 skipped`

Cutoff criteria reference:

- `docs/V3_CUTOFF_EXIT_CRITERIA.md`

Live audit reference:

- `docs/V3_FEATURE_AUDIT_LIVE_2026-04-17.md`

Parity reference:

- `docs/V2_V3_PARITY_MATRIX.md`

## Included Surfaces Confirmed

The current listener at `http://127.0.0.1:7888` returned `200` for these included routes on `2026-04-17`:

- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/pnl/attribution`
- `/ui/pnl/product-category/dates`
- `/ui/pnl/product-category?report_date=2026-02-28&view=monthly`
- governed formal read probes covered by `python scripts/governed_phase2_preflight.py`

## Runtime Reconciliation

During this cutoff pass, the first live preflight detected stale runtime drift on the port `7888` listener: excluded/reserved routes were serving `200` despite checked-in fail-closed route code and green route-level tests.

That listener was then restarted against the current workspace code, after which:

- `/ui/risk/overview` returned `503`
- `/ui/home/alerts` returned `503`
- `/ui/home/contribution` returned `503`
- `/api/cube/dimensions/bond_analytics` returned `503`
- `/api/risk/buckets?report_date=2026-02-28` returned `503`
- `/api/analysis/yield_metrics?report_date=2026-02-28` returned `503`
- `/api/analysis/liabilities/counterparty?report_date=2026-02-28&top_n=10` returned `503`
- `/api/liabilities/monthly?year=2026` returned `503`

The current declaration is therefore based on the reconciled live listener, not the stale pre-restart process.

## Final Statement

`The current governed Phase 2 formal-compute release is accepted at cutoff for the included scope only. executive-consumer cutover v1 is included. excluded surfaces remain excluded and are currently fail-closed or reserved as documented.`
