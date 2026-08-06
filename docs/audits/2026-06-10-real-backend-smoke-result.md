# 2026-06-10 Real Backend Smoke Result

## Result Capture

Run date: 2026-06-10

Runner: Codex audit pass

Backend/API target: `http://127.0.0.1:7888`

Backend readiness evidence:
- `GET /health` returned HTTP 200.
- `GET /health/ready` returned `status=ok`.
- Ready checks reported PostgreSQL, DuckDB read-only path, Redis, object store, and home snapshot prewarm as ok.

Frontend base URL: `http://127.0.0.1:5888`

Frontend data-source evidence:
- Served `src/api/clientContext.ts` includes `import.meta.env.VITE_DATA_SOURCE: "real"`.
- Served `src/router/routes.tsx` includes `import.meta.env.VITE_DATA_SOURCE: "real"`.

Primary command:

```powershell
cd frontend
$env:MOSS_PLAYWRIGHT_BASE_URL = "http://127.0.0.1:5888"
$env:MOSS_PLAYWRIGHT_OUTPUT_DIR = "../.codex-tmp/playwright-page-results/full-real-backend-smoke-20260610-135505"
npm.cmd run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1
```

Result: `47 passed`.

Route scope: the 26 business display routes configured in `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`, plus the Gate-H keyboard and control-context checks in that same suite.

Output directory: `.codex-tmp/playwright-page-results/full-real-backend-smoke-20260610-135505`

Failed routes: none in the accepted run.

Backend/API failures: none reported by the accepted run.

Screenshots/traces: Playwright output directory above.

## Flake Review

An earlier same-session run against the same frontend/backend targets produced `46 passed, 1 failed` at `.codex-tmp/playwright-page-results/full-real-backend-smoke-20260610-132949`.

Failure: `bond-analysis exposes named controls, visible focus, and non-color state cues @gate-h-control-context`; the route rendered and the report-date selector existed, but the keyboard focus helper did not reach the selector in that run.

Follow-up evidence:
- A read-only browser focus probe confirmed the Bond Analysis report-date selector was enabled, had `tabIndex=0`, exposed an `aria-label` for the report-date control, and was reached on the first `Tab` after the skip-link main-content focus path.
- Targeted rerun command with output `.codex-tmp/playwright-page-results/bond-analysis-control-context-rerun-20260610-135351` passed: `1 passed`.
- Full rerun with output `.codex-tmp/playwright-page-results/full-real-backend-smoke-20260610-135505` passed: `47 passed`.

Interpretation: the accepted closure evidence is the full `47 passed` rerun. The earlier Bond Analysis failure is retained as flake-review evidence, not as an unresolved route failure.

## Non-Approval Statement

This smoke result closes only the full real-backend browser-smoke audit lane. It does not grant business-owner approval, does not write or approve governance records, does not approve metrics, does not certify routes, does not resolve calculation/display P1 owner decisions, and does not replace direct Codex App MCP/GitNexus evidence. At the 2026-06-10 run date that separate lane had 10 open rows; the current 2026-08-06 governance overlay has 8 remaining after P1-07 and P1-09 closed.
