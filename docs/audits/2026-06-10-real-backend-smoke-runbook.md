# 2026-06-10 Real Backend Smoke Runbook

## Purpose

This runbook defines the evidence needed to close the open full real-backend browser-smoke gate from the 2026-06-10 system audit. It does not approve metrics, pages, governance records, or business-owner signoff. It only describes how to run and record a browser smoke against a live backend and a real frontend data source.

## Preconditions

- A live backend/API target is available to the frontend.
- The frontend is started with `VITE_DATA_SOURCE=real`.
- Any backend environment needed by the real routes is configured outside this audit artifact.
- The run has an evidence owner and an output directory before it starts.
- No mock-only, route-mocked, or mixed-source smoke result is used as closure evidence for this gate.
- Owner approval and governance-record gates remain fail-closed even if this smoke passes.

## Primary Command

Use this path when Playwright should start the local Vite frontend itself.

```powershell
cd frontend
$env:MOSS_PLAYWRIGHT_USE_WEB_SERVER = "1"
$env:MOSS_PLAYWRIGHT_PORT = "<free-port>"
$env:VITE_DATA_SOURCE = "real"
$env:MOSS_PLAYWRIGHT_OUTPUT_DIR = "../.codex-tmp/playwright-page-results/full-real-backend-smoke-<timestamp>"
npm.cmd run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1
```

The audited route scope is the 26 business display routes configured in `frontend/tests/playwright/a11y-visual-smoke.spec.mjs` and mapped by `docs/audits/business-display-coverage-report.json`.

## Existing Frontend Target Variant

Use this path when a real-mode frontend is already running. The existing frontend must already have been started with `VITE_DATA_SOURCE=real`; setting the variable only for Playwright does not change an already-running Vite app.

```powershell
cd frontend
$env:MOSS_PLAYWRIGHT_BASE_URL = "http://127.0.0.1:<frontend-port>"
$env:MOSS_PLAYWRIGHT_OUTPUT_DIR = "../.codex-tmp/playwright-page-results/full-real-backend-smoke-<timestamp>"
npm.cmd run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1
```

## Supplemental Real-Route Checks

These can add confidence, but they do not replace the primary full-route smoke.

```powershell
cd frontend
$env:MOSS_PLAYWRIGHT_REAL_STOCK_SMOKE = "1"
npm.cmd run test:a11y-smoke -- tests/playwright/stock-analysis-real-smoke.spec.mjs --workers=1
```

The monthly operating analysis audit smoke uses real-client code with route-mocked API responses. It remains useful for its narrow contract, but it is not full real-backend closure evidence.

## Evidence That Does Not Close This Gate

- Full mock smoke, even when all routes pass.
- Route-mocked real-client smoke.
- Stock-analysis mock smoke.
- Dry-run page verifier output.
- Static page-readiness output.
- Local MCP queue evidence without a live browser/API run.

## Acceptance Criteria

- The primary command exits with code 0.
- Each route reaches its configured ready selector.
- The axe critical-violation assertion reports zero critical violations.
- The run is against a live backend target and real frontend data source.
- The output directory, timestamp, command, environment variables, and route scope are recorded.
- Any failure is triaged by route, backend/API dependency, data-source setup, and browser assertion.
- The final audit note states that this smoke does not grant owner approval, governance-record write approval, formal-use approval, or business-contract certification.

## Result Capture Template

```text
Run date:
Runner:
Backend/API target:
Frontend base URL:
Command:
Environment:
Output directory:
Result:
Failed routes, if any:
Backend/API failures, if any:
Screenshots/traces:
Conclusion:
Non-approval statement:
```
