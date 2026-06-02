# V3 Feature Audit (Live Verification)

- Audit date: 2026-04-17
- Workspace: `F:\MOSS-V3`
- Scope: current V3 frontend, backend test surface, and lightweight HTTP smoke through `TestClient`

## Goal

Create a current-state audit for V3 similar in spirit to the V2 live audit, but grounded in what the V3 repo can actually prove today.

This audit is evidence-first:

- commands were run in the current workspace
- timeouts are reported as timeouts
- inconsistent route behavior is reported as a finding, not hidden

## Commands Run

### Frontend

- `npm run test`
- `npm run build`

### Backend

- `python -m pytest --collect-only -q`
- `python -m pytest -q`
- targeted smoke suite:
  `python -m pytest -q ..\tests\test_health_endpoints.py ..\tests\test_positions_api_contract.py ..\tests\test_pnl_api_contract.py ..\tests\test_risk_tensor_api.py ..\tests\test_balance_analysis_api.py ..\tests\test_executive_dashboard_endpoints.py ..\tests\test_bond_analytics_api.py`
- follow-up excluded-surface verification (same audit date, route-contract level):
  `python -m pytest -q ..\tests\test_cube_query_api.py ..\tests\test_liability_analytics_api.py ..\tests\test_liability_analytics_envelope_contract.py`

### Direct HTTP smoke

- repo-root `TestClient` smoke
- backend-dir `TestClient` smoke with `PYTHONPATH=F:\MOSS-V3`

## Results

### Frontend

- `npm run test`
  - result: `79` test files passed
  - result: `393` tests passed
- `npm run build`
  - result: passed

Non-blocking warnings observed:

- React Router future-flag warnings during tests
- ECharts width/height warning in one dashboard test context
- build chunk-size warnings for large vendor bundles

### Backend

- `python -m pytest --collect-only -q`
  - result: `1274 tests collected`
- `python -m pytest -q`
  - result: did not finish within `604s`
  - verdict: no full green backend proof in the current audit window
- `python scripts/backend_release_suite.py`
  - result: `135 passed in 103.08s`
- targeted smoke suite
  - result: `99 passed`
- follow-up excluded-surface verification
  - result: `38 passed`

## Direct HTTP Smoke

### Repo-root smoke

The following routes returned the listed status codes when the app was loaded from repo root:

| Route | Status |
| --- | --- |
| `/health` | `200` |
| `/ui/home/overview` | `200` |
| `/ui/home/summary` | `200` |
| `/ui/pnl/attribution` | `200` |
| `/ui/risk/overview` | `503` |
| `/ui/home/alerts` | `503` |
| `/ui/home/contribution` | `503` |
| `/api/pnl/dates` | `200` |
| `/api/risk/tensor/dates` | `200` |
| `/ui/balance-analysis/dates` | `200` |
| `/ui/pnl/product-category/dates` | `200` |
| `/api/bond-analytics/dates` | `200` |
| `/api/ledger-pnl/dates` | `200` |

Date-driven detail smoke also succeeded from repo root:

| Route | Report date | Status |
| --- | --- | --- |
| `/api/pnl/overview` | `2026-02-28` | `200` |
| `/api/risk/tensor` | `2026-02-28` | `200` |
| `/ui/balance-analysis/overview` | `2026-02-28` | `200` |
| `/ui/pnl/product-category` | `2026-02-28` | `200` |
| `/api/bond-analytics/portfolio-headlines` | `2026-02-28` | `200` |
| `/api/ledger-pnl/summary` | `2026-02-28` | `200` |

### Backend-dir smoke

When the app was loaded from `F:\MOSS-V3\backend` with `PYTHONPATH=F:\MOSS-V3`, the critical route statuses matched repo-root behavior:

| Route | Status |
| --- | --- |
| `/health` | `200` |
| `/api/pnl/dates` | `200` |
| `/api/risk/tensor/dates` | `200` |
| `/ui/balance-analysis/dates` | `200` |
| `/api/bond-analytics/dates` | `200` |
| `/api/ledger-pnl/dates` | `200` |
| `/ui/home/overview` | `200` |
| `/ui/home/summary` | `200` |
| `/ui/pnl/attribution` | `200` |
| `/ui/risk/overview` | `503` |
| `/ui/home/alerts` | `503` |
| `/ui/home/contribution` | `503` |

## Findings

### F1. Backend full-suite verification is not currently green

Evidence:

- `1274` backend tests were collected successfully.
- full `python -m pytest -q` did not complete within `604s`.
- the named bounded backend gate succeeded:
  - `python scripts/backend_release_suite.py`
  - `135 passed in 103.08s`

Impact:

- V3 now has a bounded backend release gate.
- V3 still does not have a full-suite green proof in the same audit window.

### F2. Core storage-path resolution is now consistent across execution contexts

Evidence:

- repo-root and backend-dir `TestClient` smoke now agree on:
  - formal date routes
  - executive E1 `200` routes
  - excluded executive `503` routes
- settings-path contract tests pass.

Impact:

- The app no longer depends on current working directory for the audited storage-backed routes in this pass.

### F3. Executive contract tests now align with the current cutover reality

Evidence:

- targeted smoke suite ended with:
  - `99 passed`
- `tests/test_executive_dashboard_endpoints.py` now passes.
- excluded executive surfaces return stable `503`:
  - `/ui/risk/overview`
  - `/ui/home/alerts`
  - `/ui/home/contribution`

Impact:

- Route behavior, tests, and cutover documents are aligned for the current executive boundary.

### F4. Product-category PnL formal read surface is now runnable in the current workspace

Evidence:

- `/ui/pnl/product-category/dates` returned `200`
- the route now exposes governed report dates through `2026-02-28`
- `/ui/pnl/product-category?report_date=2026-02-28&view=monthly` returned `200`

Impact:

- The consumer route is implemented and currently backed by materialized formal read-model data.

### F5. Core formal read surfaces are runnable from the current workspace

Evidence:

- repo-root `TestClient` smoke returned `200` for:
  - `/api/pnl/overview`
  - `/api/risk/tensor`
  - `/ui/balance-analysis/overview`
  - `/ui/pnl/product-category`
  - `/api/bond-analytics/portfolio-headlines`
  - `/api/ledger-pnl/summary`

Impact:

- V3 already has a usable governed read-path baseline across formal PnL, formal balance, risk tensor, bond analytics, and ledger PnL.

### F6. Frontend quality gate is materially stronger than the backend full-suite gate right now

Evidence:

- frontend test suite passed
- frontend production build passed
- backend full suite did not complete inside the audit timeout

Impact:

- Current delivery risk is concentrated more on backend runtime/test readiness than on frontend buildability.

### F7. Reserved non-cutover query / compatibility routes now fail closed instead of looking accidentally promoted

Evidence:

- route-level verification for excluded surfaces succeeded:
  - `38 passed`
- `cube-query` public HTTP surface now returns reserved `503`
- liability-analytics compatibility public HTTP surface now returns reserved `503`
- frontend workbench no longer presents `/risk-overview`、`/liability-analytics`、`/cube-query` as live primary-navigation pages

Impact:

- current release docs, runtime behavior, and route-level tests are now more tightly aligned for excluded surfaces
- these capabilities still exist as retained code assets, but are no longer presented as current governed rollout surfaces

## Audit Verdict

### Confirmed green

- frontend tests
- frontend production build
- backend collection health
- named bounded backend release suite:
  - `python scripts/backend_release_suite.py`
  - `135 passed`
- repo-root smoke for core governed read surfaces:
  - formal PnL
  - risk tensor
  - balance analysis
  - bond analytics
  - ledger PnL
- executive consumer overlay basics:
  - overview
  - summary
  - pnl-attribution
- targeted backend smoke across health, positions, pnl, risk tensor, balance analysis, executive, and bond analytics

### Confirmed yellow

- vendor-size chunk warnings remain on the frontend build
- full backend suite still lacks a full-window green result in this audit window

### Confirmed red

- no red finding is currently open inside the bounded backend release gate

## Recommended Next Actions

1. Keep `python scripts/backend_release_suite.py` aligned across authority docs, CI, acceptance, and live audit outputs as the canonical backend cutoff gate.
2. Keep product-category PnL materialization healthy in the current workspace so the formal read-model dates do not regress back to empty.
3. Keep executive E1 / excluded-route status under route-level tests so future cutover changes are explicit rather than accidental.
