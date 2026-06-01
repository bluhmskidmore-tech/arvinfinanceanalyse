# V3 Cutoff Declaration Template

## Status

- declaration type: maintainer release statement
- scope: current governed `Phase 2` formal-compute release only

## Use

Fill this template only when the current release boundary is ready to be declared at cutoff.

This declaration is for:

- formal balance
- formal PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal read surfaces
- `executive-consumer cutover v1`

It is not a statement that the whole repo is live.

## Declaration

Release decision:

- `GO` or `NO-GO`

Decision date:

- `YYYY-MM-DD`

Decision owner:

- `<name>`

Candidate release scope:

- governed `Phase 2` formal-compute cutoff candidate
- plus `executive-consumer cutover v1`
- excluded surfaces remain excluded

## Required Evidence

Canonical backend gate:

- `python scripts/backend_release_suite.py`
- result: `<paste result>`

Frontend verification:

- `npm run test`
- `npm run build`
- `npm run lint`
- result: `<paste result>`

Preflight:

- `python scripts/governed_phase2_preflight.py`
- result: `<pass|blocked>`

Live audit reference:

- `docs/V3_FEATURE_AUDIT_LIVE_2026-04-17.md` or newer

Parity reference:

- `docs/V2_V3_PARITY_MATRIX.md`

Cutoff criteria reference:

- `docs/V3_CUTOFF_EXIT_CRITERIA.md`

## Included Surfaces Confirmed

- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/pnl/attribution`
- in-scope formal read surfaces behave as documented

## Excluded Surfaces Confirmed

These excluded surfaces remain excluded:

- `/ui/risk/overview`
- `/ui/home/alerts`
- `/ui/home/contribution`
- `/api/cube/query`
- `/api/cube/dimensions/*`
- `/api/risk/buckets`
- `/api/analysis/yield_metrics`
- `/api/analysis/liabilities/counterparty`
- `/api/liabilities/monthly`
- Agent MVP / real `/api/agent/query`
- preview/vendor/analytical-only expansion surfaces outside the current cutover

Current excluded-surface behavior is still explicit:

- excluded executive surfaces: `503 fail-closed`
- reserved query / compatibility routes: `503 reserved surface`
- retained workbench entries may remain placeholder / compat / hidden without being treated as live promotion

## Open Risks

- `<list remaining P1/P2 items>`

## Final Statement

Example `GO`:

`The current governed Phase 2 formal-compute release is accepted at cutoff for the included scope only. executive-consumer cutover v1 is included. excluded surfaces remain excluded.`

Example `NO-GO`:

`The current governed Phase 2 formal-compute release is not yet accepted at cutoff. The release remains a cutoff candidate only, pending resolution of the blockers listed above.`
