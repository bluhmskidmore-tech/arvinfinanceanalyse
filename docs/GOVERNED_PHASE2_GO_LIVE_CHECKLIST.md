# Governed Phase 2 Go-Live Checklist

## Scope

This checklist applies only to the currently authorized governed `Phase 2` launch scope:

- formal balance
- formal PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal read surfaces

It does **not** widen the launch boundary to excluded surfaces such as:

- Agent MVP / real `/api/agent/query`
- broad `executive.*` expansion outside `executive-consumer cutover v1`
- preview / vendor / analytical-only expansion surfaces
- other `Phase 3 / Phase 4` style rollout items

## Hard Gates

All of the following must be true before calling this scope launch-ready:

1. Backend regression is green:
   - `python -m pytest tests -q`
2. Frontend regression is green:
   - `npm test`
   - `npm run typecheck`
   - `npm run build`
3. Environment-level preflight is green:
   - `python scripts/governed_phase2_preflight.py`
4. Required formal lineage exists for the candidate report date(s):
   - balance-analysis lineage
   - pnl lineage
   - bond analytics lineage
5. Formal FX prerequisites are satisfied:
   - production `Choice` entitlement is available, or
   - the environment already contains valid formal FX middle-rate facts for the target report date(s)
6. Formal materialization has completed for the target report date(s):
   - balance analysis
   - bond analytics
   - pnl

## Release Preconditions

These are not optional:

- Production or pre-production vendor credentials are present and valid.
- The target report date has complete governed source inputs.
- The materialize/build pipeline has run to completion for the target report date.
- `result_meta` / lineage fields are available on all in-scope outward reads.
- Any `503` on an in-scope governed route is treated as a launch blocker until explained and cleared.

## Preflight Command

Run:

```bash
python scripts/governed_phase2_preflight.py
```

Optional overrides:

```bash
python scripts/governed_phase2_preflight.py --api-base http://127.0.0.1:7888 --frontend-base http://127.0.0.1:5888
```

## What Preflight Checks

The preflight probes these surfaces:

- `/health`
- frontend root `/`
- `/api/bond-analytics/dates`
- `/api/bond-analytics/return-decomposition`
- `/api/risk/tensor/dates`
- `/api/risk/tensor`
- `/ui/balance-analysis/dates`
- `/ui/balance-analysis/overview`
- `/api/pnl/dates`
- `/api/pnl/overview`
- `/api/pnl/bridge`

The script reports:

- `pass`
- `blocked`
- `skipped`

## How To Interpret Failures

### `balance_dates` or `pnl_dates` returns `503`

Interpretation:

- formal lineage is missing
- materialization likely has not completed for the target report date

Action:

- run the formal materialization pipeline for the target report date
- verify the corresponding governance/cache lineage exists

### `risk_tensor` returns `503`

Interpretation:

- bond analytics lineage is missing, or freshness gating failed

Action:

- materialize bond analytics for the target report date
- verify governed lineage is readable before retrying

### formal balance materialization fails on FX

Interpretation:

- formal FX prerequisites are not satisfied
- the current environment may lack `Choice` entitlement or valid formal USD/CNY middle-rate inputs

Action:

- verify `Choice` entitlement for formal FX middle-rate access
- confirm the target report date has governed FX data
- do not override this with analytical fallbacks for formal launch

## Current Known Local-Dev Findings (2026-04-17)

Observed on the local native dev stack:

- `/health`: pass
- frontend root: pass
- bond analytics dates: pass
- bond analytics return decomposition: pass
- risk tensor dates: pass
- risk tensor: blocked when bond analytics lineage is missing
- balance-analysis dates: blocked when canonical formal lineage is missing
- pnl dates: blocked when canonical formal lineage is missing
- local formal balance sync can also be blocked by:
  - missing `Choice` API entitlement
  - missing formal USD/CNY middle-rate from fallback vendors

These findings support a `GO for controlled rollout` only when materialization and vendor prerequisites are satisfied in the target environment.

## Release Decision Rule

Use this rule:

- `GO`:
  - all tests/build gates pass
  - preflight passes
  - no blocked in-scope governed route remains
- `NO-GO`:
  - any in-scope governed route is blocked
  - any required lineage is missing
  - any required formal FX/vendor prerequisite is unresolved

## Files Used

- `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md`
- `docs/EXECUTIVE_CUTOVER_EVALUATION_2026-04-17.md`
- `scripts/governed_phase2_preflight.py`
- `scripts/dev-smoke.ps1`
