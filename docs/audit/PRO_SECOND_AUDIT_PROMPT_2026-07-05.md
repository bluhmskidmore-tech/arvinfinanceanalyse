# Prompt For Pro Second Architecture Audit

You are auditing the current MOSS-V3 repository state.

Repository root: `F:\MOSS-V3`
Current date: 2026-07-05
Original audit baseline: `moss_v3_audit_pack.zip`, snapshot date 2026-05-07

Important: do not assume issues from the 2026-05-07 snapshot still exist. Audit the current repository state and use `MOSS_V3_SECOND_AUDIT_EVIDENCE_2026-07-05.md` as the primary evidence file.

## Context

A 13-prompt architecture remediation pack was generated from the 2026-05-07 audit. Each prompt had a Preflight rule: verify the issue still exists before editing; if the current issue no longer exists or the precondition is false, stop and report only.

Codex implemented and verified the currently applicable remediation scope for:

1. Prompt 03A: promoted `/ui/home/snapshot` from reserved/promised to landed and added backend endpoint coverage.
2. Prompt 06: added `response_model` only to three endpoints whose real TestClient responses passed round-trip validation, without changing payloads to fit schemas.
3. Prompt 12: fixed the bond analytics Numeric / warning-code / frontend parsing chain while preserving governed Numeric JSON and existing business formulas.

After the first evidence pass, `npm run build` exposed an unrelated stock-analysis / Livermore `return_10d` horizon contract drift. That blocker has now been fixed and reverified.

## Current Verification Snapshot

- `python -m pytest --collect-only -q`: 5555 tests collected.
- `python -m pytest tests/test_home_snapshot_endpoint.py tests/test_executive_dashboard_endpoints.py -q`: 32 passed.
- `python -m pytest tests/test_envelope_contract.py -q`: 12 passed.
- `python -m pytest tests/test_pnl_attribution_api_contract.py tests/test_executive_dashboard_endpoints.py -q`: 20 passed.
- Prompt 12 backend checks pass for Numeric / warning-code / real-data coverage.
- `npm ci --legacy-peer-deps`: passed; plain `npm ci` still fails on React peer conflict.
- `npm run build`: passed after the `return_10d` contract alignment.
- `npm run typecheck`: passed.
- `npm run test -- HomeStartupClient`, `BondAnalyticsClient`, `bondAnalyticsModuleReadiness`: passed.
- `npm run test -- StockAnalysisBacktestModel`, `StockAnalysisPageModel`, `StockAnalysisPriorityModel`, `src/test/StockAnalysisPage.test.tsx`: passed.
- `npm run debt:audit`: passed.
- `npm run test -- StockAnalysisPage`: still fails only because the broad filter includes the pre-existing `StockAnalysisPageSizeGuard.test.ts` line-count guard.
- `git diff --check`: passed with only line-ending normalization warnings.

## Your Task

Please audit the current repository state and answer:

1. Did Prompt 03A, Prompt 06, and Prompt 12 actually close the original architecture risks?
2. For each unexecuted prompt, should it be closed as obsolete, kept open, or rewritten against the current code?
3. Are there any current P0/P1 architecture risks that remain after these changes?
4. Does the stock-analysis `return_10d` build-unblock remain narrow and safe?
5. If more remediation is needed, generate new single-PR prompts based on the current code, not the old 2026-05-07 snapshot.

## Required Output

1. Executive summary
2. Closure decision for 03A / 06 / 12
3. Closure or rewrite decision for each unexecuted prompt
4. Current P0/P1 findings, if any
5. New remediation prompts only where needed

For each new remediation prompt, include:

- Preflight
- Read first
- Write scope
- Do not touch
- Required checks
- Output back
