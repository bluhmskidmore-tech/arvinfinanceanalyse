# P2 Roll-Down Time Anchor Owner Decision Request

Status: `approved_for_implementation`
Metric: `MTR-BRG-004`
Scope: roll-down time anchor after P1-03 sign alignment
Prepared at: `2026-07-03`

This document records the owner decisions captured on 2026-07-03 before P2
formula implementation.

## Background

P1-03 closed the sign convention: upward-sloping curves produce positive
roll-down. P2 is separate. It asks which dates and exposure fields anchor the
formal PnL Bridge roll-down calculation.

Current implementation evidence:

- `backend/app/core_finance/pnl_bridge.py` uses report-date remaining tenor,
  current curve, current-row duration, current-row market value, and
  `current_balance.report_date - prior_balance.report_date`.
- `backend/app/core_finance/bond_analytics/read_models.py` uses row-provided
  `years_to_maturity`, `modified_duration`, `market_value`, current curve, and
  `(period_end - period_start).days + 1`.
- `backend/app/core_finance/attribution_daily.py` uses period-end market curve,
  slides from `T(prev)` to `T(report)`, and uses start market value.

## Gate 1: Formal Bridge Anchor

Owner selected one option for `MTR-BRG-004` / `pnl_bridge`.

### Option A: Period-end/current-anchor

- curve date: period end / report date curve
- current tenor: maturity minus report date
- rolled tenor: current tenor minus elapsed period
- duration base: current/end duration
- market-value base: current/end market value
- period days: exclusive elapsed days unless owner specifies inclusive

Engineering note: this is closest to current `pnl_bridge`; it is only a
recommendation, not approval.

### Option B: Period-start exposure anchor

- curve date: period end / report date curve
- start tenor: maturity minus previous date
- end tenor: maturity minus report date
- duration base: start duration
- market-value base: start market value
- period days: `prev_date -> report_date`

Implementation blocker: before code changes, engineering must prove a reliable
start-duration source for `pnl_bridge`.

### Option C: Defer

Make no formula change. Keep P2 open until the formal bridge anchor is approved.

## Gate 1 Required Capture

| Field | Required value |
| --- | --- |
| selected_option | `A` |
| approving_owner_or_role | user-confirmed owner authority |
| owner_rationale | Formal PnL Bridge roll-down should use period-end/current exposure anchors; adjacent consumers should follow to avoid divergent roll-down semantics. |
| effective_date_or_version | `2026-07-03` |
| curve_date | period-end / report-date curve |
| tenor_pair | current/end remaining tenor and `current_remaining_tenor - elapsed_days / 365` |
| period_day_inclusivity | exclusive elapsed days: `period_end - period_start` |
| duration_base | current/end duration |
| market_value_base | current/end market value |
| missing_data_behavior | missing curve, maturity, duration, market value, or non-positive elapsed days returns zero roll-down |
| p1_03_sign_reaffirmed | `yes` |
| implementation_owner | Codex |
| verification_gate | targeted anchor tests, P1-03 sign tests, affected consumer suites, `tests -k "pnl_bridge"`, GitNexus detect-changes |
| status | `approved_for_implementation` |

## Gate 2: Adjacent Consumer Scope

Owner separately decided whether adjacent consumers conform to the formal bridge
anchor or remain intentionally distinct.

| Consumer | Decision | Rationale |
| --- | --- | --- |
| `bond_analytics/read_models` | `conform` | Keep read-model roll-down aligned with formal bridge sign and time-anchor semantics. |
| `attribution_daily` | `conform` | Keep daily attribution roll-down aligned with formal bridge sign and time-anchor semantics. |

Consumers marked `distinct` or `defer` must have no-change test evidence so a
P2 bridge implementation is not mistaken for repo-wide harmonization.

## Minimum Verification After Decision

- Run GitNexus impact before editing touched symbols.
- Add failing anchor-sensitive PnL Bridge tests before implementation.
- Keep P1-03 sign tests green.
- Do not change `_calculate_curve_shift` or `_calculate_credit_spread_shift`
  signs.
- Run targeted bridge tests and `python -m pytest tests -k "pnl_bridge" -q`.
- Run no-change or conformance tests for each Gate 2 consumer according to the
  owner decision.
- Run GitNexus detect-changes before final report.

## Boundary Statement

This decision approves implementation of the P2 roll-down time-anchor change
only. It does not approve unrelated metrics, write DuckDB facts, rerun
materialization, or authorize shared-helper refactoring.
