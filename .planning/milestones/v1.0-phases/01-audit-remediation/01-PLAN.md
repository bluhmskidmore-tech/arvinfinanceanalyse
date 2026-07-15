---
phase: "01-audit-remediation"
plan: "01"
status: complete
requirements:
  - REQ-AUDIT-001
  - REQ-AUDIT-002
  - REQ-AUDIT-003
  - REQ-AUDIT-004
  - REQ-AUDIT-005
  - REQ-AUDIT-006
---

# Phase 01 Plan: Audit Remediation

## Objective

Close the current milestone audit blockers with minimal, reviewable changes and restore an auditable release evidence chain.

## Tasks

1. Restore release gate behavior.
   - Make `get_auth_context()` trust `X-User-Id` and `X-User-Role` only when `MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST=1`.
   - Enable that switch inside the backend release suite environment.
   - Verify Balance Analysis current-user and write-status role behavior through release tests.

2. Add live page contracts.
   - Add formal `PAGE-*` contracts for `/agent`, `/balance-movement-analysis`, and `/liability-analytics`.
   - Include business question, route, primary API, data chain, unit/date rules, empty/failure/stale states, and tests.

3. Seal frontend finance-boundary intent.
   - Confirm dashboard cockpit DV01 usage is display-only text.
   - Add a narrow, file-scoped guard exception for that display-only label only.

4. Fix Dashboard first-screen delta semantics.
   - Treat blank, dash, `N/A`, and unavailable labels as missing.
   - Fall back to the governed read-chain delta label.
   - Add model tests for placeholder values.

5. Harden development security boundaries.
   - Add explicit authorization for macro choice-series refresh.
   - Require auth on agent run lookup and reject run-owner mismatch.
   - Restrict GitNexus repo paths and force the project launcher for MCP commands.
   - Add focused tests for each boundary.

6. Restore release evidence.
   - Add frontend production build to CI.
   - Include page-contract, finance-boundary, and MCP self-checks in the backend release suite.
   - Create minimal GSD ROADMAP, REQUIREMENTS, phase SUMMARY, VERIFICATION, and VALIDATION artifacts.

## Verification

Run the ordered plan test suite from the remediation request:

- `python -m pytest -q tests/test_live_route_page_contract_completeness.py`
- `python -m pytest -q tests/test_no_finance_logic_in_frontend.py`
- `python -m pytest -q tests/test_auth_context.py tests/test_write_route_auth_contract.py tests/test_agent_runs_api.py tests/test_agent_intent_routing.py`
- `python scripts/backend_release_suite.py`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run test`
- `cd frontend && npm run lint`
- `cd frontend && npm run debt:audit`
- `cd frontend && npm run build`
- Rerun milestone audit.
