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

It does not widen the launch boundary to excluded surfaces such as Agent MVP, broader `executive.*` expansion, preview/vendor/analytical-only surfaces, or later `Phase 3 / Phase 4` work.

For the current code state, excluded surfaces are expected to remain visibly excluded:

- excluded executive routes stay explicit `503`
- reserved `cube-query` public routes stay explicit `503`
- reserved liability-analytics compatibility public routes stay explicit `503`
- retained frontend entries for excluded surfaces may stay placeholder / compat instead of live

## Hard Gates

All of the following must be true before calling this scope launch-ready:

1. Backend regression is green:
   - `python scripts/backend_release_suite.py`
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
   - risk tensor

## Required Probe Set

The controlled-rollout preflight treats every probe below as required:

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

Any `blocked` or `skipped` result inside that set is a launch blocker.

## Preflight Command

Run:

```bash
python scripts/governed_phase2_preflight.py
```

Optional overrides:

```bash
python scripts/governed_phase2_preflight.py --api-base http://127.0.0.1:7888 --frontend-base http://127.0.0.1:5888
```

## Failure Interpretation

### `balance_dates` or `balance_overview` blocked

Interpretation:

- canonical balance-analysis lineage is missing or malformed
- balance-analysis materialization has not completed successfully for the target report date

Action:

- rerun `balance_analysis:materialize:formal`
- verify the resulting completed build run and manifest lineage

### `pnl_dates`, `pnl_overview`, or `pnl_bridge` blocked

Interpretation:

- canonical pnl lineage is missing or malformed
- PnL materialization has not completed successfully for the target report date

Action:

- rerun `pnl:phase2:materialize:formal`
- verify completed build-run and manifest lineage for the target report date

### `risk_tensor` blocked

Interpretation:

- risk tensor is stale against bond analytics and/or TYW liability lineage
- risk tensor materialization has not been refreshed after upstream changes

Action:

- rerun `risk_tensor:materialize:formal` after upstream bond analytics / liability lineage is current

### formal balance materialization fails on FX

Interpretation:

- formal FX prerequisites are not satisfied
- current environment may lack `Choice` entitlement or valid formal USD/CNY middle-rate inputs

Action:

- verify `Choice` entitlement for formal FX middle-rate access
- confirm the target report date has governed FX data
- do not override this with analytical fallbacks for formal launch

## Release Decision Rule

- `GO`:
  - all regression gates pass
  - preflight returns `pass`
  - no required governed route is `blocked` or `skipped`
- `NO-GO`:
  - any required governed route is `blocked`
  - any required governed route is `skipped`
  - required lineage / materialization prerequisites are unresolved

## Residual Risks

These do not block controlled rollout, but should stay visible:

- environment/vendor prerequisites can still fail closed even when code regressions are green
- rollout authority remains limited to governed `Phase 2`; excluded surfaces remain excluded
- excluded-surface behavior must stay explicit; placeholder routes or `503` reserved routes should not drift into accidental promotion
- frontend bundle size is still larger than ideal and should be optimized in a later slice

## Canonical Backend Gate

For the current governed `Phase 2` launch scope, the canonical backend cutoff gate is:

- `python scripts/backend_release_suite.py`

Interpretation:

- this command is the named bounded backend release suite for the current included scope
- `python -m pytest -q` may still be used as a broader diagnostic command
- broader diagnostic commands do not replace the canonical backend cutoff gate for this checklist
