# Executive Consumer Cutover V1

## Status

Active boundary overlay.

## Purpose

Promote a narrow, stable subset of executive-facing read surfaces into the active governed consumer boundary without promoting the entire `executive.*` family.

## In Scope

- `/ui/home/overview`
- `/ui/home/summary`
- `/ui/pnl/attribution`

These routes are now treated as active executive consumer surfaces layered on top of the current formal-compute mainline.

## Out Of Scope

- `/ui/risk/overview`
- `/ui/home/alerts`
- `/ui/home/contribution`
- executive-wide management rollout
- broader dashboard redesign

## Contract

For in-scope routes:

- must return `{ result_meta, result }`
- `result_meta.basis == "analytical"`
- `formal_use_allowed == false`
- `scenario_flag == false`
- they are allowed to assemble from governed read models and analytical management-layer composition without being treated as formal source-of-truth results

## Remaining Promotion Path

### Stage E2 candidates

- `/ui/risk/overview`
- `/ui/home/alerts`

### Stage E3 candidate

- `/ui/home/contribution`

Those routes remain excluded until a later explicit boundary update.
