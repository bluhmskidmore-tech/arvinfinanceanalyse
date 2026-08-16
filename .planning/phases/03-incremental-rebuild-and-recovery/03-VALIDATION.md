---
phase: 03
slug: incremental-rebuild-and-recovery
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-17
---

# Phase 03 Validation Strategy

## Test Infrastructure

| Property | Value |
|---|---|
| Framework | pytest; Vitest only if frontend files change |
| Config | `pytest.ini`; `frontend/vite.config.ts` |
| Quick run | `pytest tests/test_pnl_api_contract.py -q -k "precompute or incremental or recovery or coalesce"` |
| Full page run | `pytest tests/test_pnl_api_contract.py -q` |
| Adjacent parity run | `pytest tests/test_pnl_by_business_precompute_ftp_parity.py -q` |
| Expected feedback | quick under 90 seconds; page contract under 5 minutes |

## Sampling Rate

- After each backend behavior task: run the quick targeted selection.
- After each plan wave: run the complete page contract.
- Before phase verification: run the page contract plus adjacent parity test.
- If frontend changes: run its targeted test, scoped lint/typecheck, and `npm run debt:audit` from `frontend/`.

## Per-Requirement Verification Map

| Requirement | Threat Ref | Secure behavior | Test type | Automated command | Status |
|---|---|---|---|---|---|
| INC-01 | T-03-01, T-03-03 | only frozen same-year available cutoffs at/after the changed cutoff are targeted | unit/orchestration | `pytest tests/test_pnl_api_contract.py -q -k "incremental or cutoff"` | pending |
| INC-02 | T-03-02, T-03-03 | overlaps widen one durable successor without duplicate dispatch | orchestration | `pytest tests/test_pnl_api_contract.py -q -k "coalesce or successor or duplicate"` | pending |
| REC-01 | T-03-02, T-03-04, T-03-05 | exact-cutoff failure remains visible/recoverable while current peers remain available | worker/contract | `pytest tests/test_pnl_api_contract.py -q -k "recovery or retry or failure or status"` | pending |

## Wave 0 Requirements

Existing test infrastructure covers all phase requirements. New cases belong in `tests/test_pnl_api_contract.py`; no framework or shared fixture installation is required.

## Manual-Only Verification

No business rule is manual-only. If the status panel changes, perform a browser check of one failed selected cutoff and one unaffected current cutoff after automated contract tests pass.

## Validation Sign-Off

- [x] Every requirement has an automated test lane.
- [x] No watch-mode command is used.
- [x] Wave 0 needs no new infrastructure.
- [x] Threat-model behaviors map to tests.
- [ ] Implementation tests are green.
- [ ] Final page-level verification is complete.

Approval: pending implementation
