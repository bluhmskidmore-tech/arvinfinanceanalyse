# Executive Cutover Evaluation (2026-04-17)

## Goal

Evaluate whether `executive.*` should enter the next cutover.

## Verdict

`NO-GO` for a full `executive.*` cutover in one step.

`GO` for a **staged executive consumer cutover** with a narrower first scope.

## Why Full Executive Cutover Is Not Ready

### 1. Route semantics are still inconsistent

Current route behavior is split:

- always-envelope / non-hard-fail:
  - `/ui/home/overview`
  - `/ui/home/summary`
  - `/ui/pnl/attribution`
- hard-fail on missing governed backing:
  - `/ui/risk/overview`
  - `/ui/home/contribution`
  - `/ui/home/alerts`

This means `executive.*` is not yet one coherent consumer family. It is still a mix of:

- analytical fallback surfaces
- governed-when-present surfaces
- explicit fail-closed surfaces

### 2. Dependency maturity is uneven

Current dependency shape:

- `overview`
  - formal balance
  - formal PnL
  - liability analytics compat
  - bond analytics
  - KPI service
- `summary`
  - static analytical narrative
- `pnl-attribution`
  - product-category PnL repository
- `risk-overview`
  - bond analytics repository
- `contribution`
  - product-category PnL repository
- `alerts`
  - bond analytics rows
  - risk tensor
  - alert engine

This is not a single dependency profile. Some routes are close to governed formal consumers; others are still management-layer composites or fallbacks.

### 3. Frontend already models partial availability

`DashboardPage.tsx` currently treats:

- risk
- alerts
- contribution

as optional panels that may disappear when the backend returns `503`.

That is evidence that the UI contract still assumes executive partial availability, not a fully landed governed suite.

## Recommended Next Cutover Shape

Do **not** define the next cutover as:

- `executive.* all routes`

Instead define it as:

- `executive-consumer cutover v1`

with a staged scope.

## Recommended Staging

### Stage E1: Stable Executive Read Surfaces

Candidate inclusion:

- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/pnl/attribution`

Reason:

- These already behave like stable outward envelopes.
- They do not currently depend on route-level `503` gating to preserve correctness.

### Stage E2: Governed Risk/Alert Consumer Promotion

Candidate inclusion after additional hardening:

- `/ui/risk/overview`
- `/ui/home/alerts`

Preconditions:

- clear governed fallback policy
- stable `vendor_status` semantics
- explicit rule for when 200-with-warning is allowed vs 503 fail-closed

### Stage E3: Contribution Promotion

Candidate inclusion last:

- `/ui/home/contribution`

Reason:

- It is the clearest currently excluded route
- its contract still explicitly models “not backed by governed data yet”

## Cutover Criteria

`executive-consumer cutover v1` should not be declared until all in-scope routes satisfy:

1. one consistent outward contract
2. one explicit policy for missing governed inputs
3. one documented frontend behavior for degraded states
4. route-level tests that match the chosen policy

## Recommended Boundary Decision

For the next cutover:

- keep full `executive.*` excluded from the current active repo-wide `Phase 2`
- create a new staged consumer cutover rather than broadening the current formal-compute cutover in place

## Files Used

- `backend/app/api/routes/executive.py`
- `backend/app/services/executive_service.py`
- `frontend/src/features/workbench/pages/DashboardPage.tsx`
- `tests/test_executive_dashboard_endpoints.py`
- `tests/test_executive_service_contract.py`
