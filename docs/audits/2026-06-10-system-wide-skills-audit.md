# 2026-06-10 System-Wide Skills Audit

## Scope

This audit applies the installed financial, MOSS, security, code-review, and frontend audit skills to the current MOSS worktree. The focus is business metric correctness, page closure, traceability, write-path safety, and dependency/security posture.

Authoritative MOSS MCP tools (`moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, `moss-data-quality`) were not exposed as direct Codex App tools in this session, but the repository MCP registrations, stdio launchers, server handshakes, tool/resource lists, and read-only queue calls were verified locally. `gitnexus` was declared in local MCP config but was not exposed as a direct Codex App tool. This report uses local MCP stdio calls, code, tests, static guards, and generated audit scripts as evidence. It does not approve formal metrics, pages, or business-owner signoff.

Companion artifacts:
- `docs/audits/2026-06-10-system-audit-index.md` is the entry point for the 2026-06-10 audit artifact set.
- `docs/audits/2026-06-10-system-audit-executive-summary.zh.md` is the Chinese owner/management first-read summary.
- `docs/audits/2026-06-10-owner-review-brief.zh.md` is the Chinese business-owner meeting brief for decisions, page approval sequencing, and Ledger PnL direct-record handling.
- `docs/audits/2026-06-10-owner-decision-capture-template.zh.md` is the fill-in template for recording owner meeting outputs before they are copied into authoritative page templates, calc rules, or governance workflows.
- `docs/audits/2026-06-10-system-audit-manifest.json` is the machine-readable audit status manifest; it carries fail-closed flags, artifact paths, counts, open blockers, fresh verification, and verification evidence.
- `docs/audits/2026-06-10-system-audit-action-register.md` is the execution queue for open audit actions, owners, evidence, and verification gates.
- `docs/audits/2026-06-10-system-audit-completion-checklist.md` and `docs/audits/2026-06-10-system-audit-completion-snapshot.json` are the gate-by-gate completion proof requirements and machine-readable open-blocker state.
- `docs/audits/2026-06-10-owner-governance-follow-up-packet.json` is the owner/governance handoff packet for all 5 open blockers. It records owner type, required input artifacts, meeting/governance outputs, engineering-safe prework, external closure inputs, closure evidence after external input, verification commands, prohibited actions, and explicit non-approval boundaries.
- `docs/audits/2026-06-10-owner-governance-follow-up-brief.zh.md` is the Chinese owner/governance distribution brief derived from the packet; it is for routing the 5 open blockers, not for granting approval.
- `docs/audits/2026-06-10-calculation-logic-audit.md` records the read-only calculation/display-logic audit across formal finance modules and frontend display chains.
- `docs/audits/2026-06-10-calculation-p1-owner-decision-matrix.md` retains the original 2026-06-10 10-row state as historical baseline and exposes the current 8 unresolved owner-decision rows after P1-07 and P1-09 were owner-selected and implementation-verified closed; P1-08 remains verified closed.
- `docs/audits/2026-06-10-calculation-p1-owner-decision-snapshot.json` is the read-only machine check for that matrix, owner-decision capture template, and engineering prework map; the 2026-08-06 overlay reports 8 open rows, 8 pending template rows, and 0 captured decisions among the remaining rows.
- `docs/audits/2026-06-10-owner-approval-mcp-evidence-summary.md` records the seven pending owner-approval pages and local MCP evidence packets.
- `docs/audits/2026-06-10-owner-approval-fail-closed-snapshot.json` records the current machine-readable owner gate: 7 pending pages, 0 captured approvals, 0 closure-approved pages, 84 action items, strict gate rejected 7/7, and owner approval tests at 93 passed.
- `docs/audits/2026-06-10-direct-app-mcp-gitnexus-tool-surface-snapshot.json` records the direct Codex App MCP/GitNexus tool-surface gap: current tool discovery found 0 relevant direct MOSS/GitNexus tools even though local registration files declare the expected servers; focused MOSS keyword rechecks returned 0 tools, and the focused GitNexus keyword recheck returned only non-evidence Codex App management tools.
- `docs/audits/2026-06-10-direct-app-mcp-gitnexus-tool-surface-runbook.md` defines the fresh-session retry and direct App evidence collection procedure for MOSS MCP and GitNexus.
- `docs/audits/2026-06-10-ledger-pnl-direct-governance-record-snapshot.json` records the Ledger PnL direct-record gap: dry-run candidate ready for audit review, no written direct record found, and page readiness still fail-closed.
- `docs/audits/2026-06-10-ledger-pnl-direct-governance-record-runbook.md` defines the authorized closure procedure for writing or locating the Ledger PnL direct page/API record and rerunning downstream gates.
- `docs/audits/2026-06-10-local-secret-hygiene-snapshot.json` records the local secret hygiene boundary: secret names only, `config/.env` ignored/untracked checks, and a redacted scan plan.
- `docs/audits/2026-06-10-local-secret-hygiene-runbook.md` defines the environment-owner path for rotating, removing, or accepting local-only secret findings without exposing values.
- `docs/audits/business-display-coverage-report.json` maps browser-smoke business-route coverage.
- `docs/audits/2026-06-10-system-audit-pulse-snapshot.json` is the saved read-only pulse snapshot: `status=pass`, `completion_state=not_complete`, 5 open blockers, 0 route gaps, 0 business-contract-certified routes, and no approval/write/secret-clear/certification flags.
- `scripts/system_audit_pulse.py` is the quick read-only pulse for route-scope, business display coverage, completion snapshot, and last full readiness drift; it emits JSON by default and a human-readable watch board with `--format markdown`. It currently reports `status=pass`, `completion_state=not_complete`, and 5 open blockers, without granting any approval.
- `docs/audits/2026-06-10-real-backend-smoke-runbook.md` defines the exact live-backend browser-smoke command, exclusions, acceptance criteria, and result-capture fields.
- `docs/audits/2026-06-10-real-backend-smoke-result.md` records the accepted full real-backend browser-smoke result: 47 passed, with a same-session Bond Analysis focus flake reviewed by targeted and full reruns.
- `tests/test_system_audit_manifest_contract.py`, `tests/test_system_audit_completion_snapshot_verifier.py`, `tests/test_system_audit_pulse.py`, `tests/test_system_audit_monitoring_snapshot_verifier.py`, `scripts/verify_system_audit_completion_snapshot.py`, and `scripts/verify_system_audit_monitoring_snapshot.py` are the narrow audit-package consistency guards for artifact links, fail-closed flags, owner non-approval boundaries, direct App MCP/GitNexus gap boundaries, manifest count alignment, pulse drift detection, completion snapshot alignment, monitoring snapshot alignment, owner/governance follow-up packet and Chinese brief coverage, Ledger PnL write authorization boundaries, calculation P1 engineering-prework map coverage, and no-secret-value handling.

## Findings Closed

### P1: Commodity Futures Refresh Wrote in the Request Path

Root cause: the macro toolkit commodity futures refresh endpoint previously called the commodity ingest function from the API request flow, creating a high-risk DuckDB write boundary violation.

Closure:
- API route delegates to service orchestration.
- Non-dry-run refresh queues `run_commodity_daily_ingest_task`.
- The request returns `queued` with baseline health, and does not clear full-analysis cache or pretend the evidence has already reloaded.
- Frontend copy and tests now show `商品期货刷新已排队，等待后台任务完成`.

Evidence:
- `backend/app/services/macro_toolkit_service.py`
- `backend/app/tasks/commodity_daily_ingest.py`
- `backend/app/api/routes/macro_toolkit.py`
- `frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx`
- `tests/test_macro_toolkit_scripts.py`
- `frontend/src/test/MacroToolkitPage.test.tsx`

### P1: Frontend Dependency Advisory

Root cause: `react-router-dom@6.30.3` pulled a `react-router` version with a moderate open-redirect advisory.

Closure:
- Upgraded to `react-router-dom@6.30.4`.
- Installed runtime dependency tree confirms `react-router-dom@6.30.4`, `react-router@6.30.4`, and `@remix-run/router@1.23.3`.
- `npm audit --audit-level=moderate` returns zero vulnerabilities.

Evidence:
- `frontend/package.json`
- `frontend/package-lock.json`

### P2: Audit Script and Build Friction

Closures:
- `scripts/supply_chain_security_scan.py` now passes absolute output paths when an absolute report directory is supplied.
- `BondDashboardPage.tsx` no longer imports the unused `nativeToNumber`.
- `MacroToolkitPage.test.tsx` no longer spreads string refresh product rows.

### P2: Supply-Chain and Secret Scan Evidence

Root cause: dependency/security posture needs both package-audit evidence and external scanner evidence. The first local run used repository-level scanning over the full working directory and was overwhelmed by ignored local caches, generated builds, OMX research copies, and temporary worktrees before reaching the live source signal.

Closure:
- `npm audit --audit-level=moderate` from `frontend/` reports 0 vulnerabilities.
- `scripts/supply_chain_security_scan.py --dry-run` emits gitleaks and osv-scanner commands over `.gitleaks.toml`, `backend/uv.lock`, and `frontend/package-lock.json`.
- Installed portable local audit copies of `gitleaks 8.30.1` and `osv-scanner 2.3.8` under `.codex-tmp/security-tools/`.
- Expanded `.gitleaks.toml` only for already-ignored local/generated directories: `.codex-tmp/`, `.omx/`, `data/`, `dist/`, and `frontend/dist/`.
- Added a narrow Risk Tensor metric-key false-positive allowlist for governed metric identifiers (`regulatory_dv01`, `dominant_krd_bucket`) without excluding `frontend/src/`.
- Non-dry-run gitleaks now reports only two findings, both in ignored/untracked `config/.env`: `MOSS_TUSHARE_TOKEN` and `STITCH_API_KEY` names were detected with values redacted. No value was exposed in this report.
- `osv-scanner` ran against `backend/uv.lock` and `frontend/package-lock.json` and reported 0 vulnerability results.
- Existing tests verify scanner assets, narrow generated-artifact allowlists, dry-run plan shape, fail-clear behavior when binaries are missing, selected-tool command construction, CI wiring, and local secret env ignore rules.

Evidence:
- `.gitleaks.toml`
- `scripts/supply_chain_security_scan.py`
- `.github/workflows/ci.yml`
- `tests/test_supply_chain_security_scanning.py`
- `tests/test_secret_hygiene.py`

### P1: Frontend Accessibility and Smoke Gate Regressions

Root causes:
- Market Data used Ant Design Tabs for the macro depth strip; the generated overflow control sat inside `role="tablist"` and triggered a critical axe `aria-required-children` failure.
- The gate-H smoke helper waited on the first selector match even when a later candidate was visible, so hidden Cross Asset state panels could block a valid visible state cue.
- Bond Analysis exposed the real "打开动作归因" next-action button, but the smoke contract still needed a stable decision-action test id.
- Stock Analysis observation preview leaked English strategy labels (`Factor`, `Mean reversion`, `Pending`, `Paused`) into the mock browser smoke path.

Closure:
- Replaced the Market Data macro-depth Ant Tabs with a small route-owned semantic tablist and current-panel rendering.
- Made the smoke helper return the first visible candidate across all selector matches.
- Pointed Cross Asset state-cue verification at the visible first-screen trust panel.
- Added `bond-analysis-decision-next-action` to the real Bond Analysis action button.
- Localized the Stock Analysis observation preview labels and empty states to Chinese.

Evidence:
- `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`
- `frontend/src/features/market-data/pages/MarketDataPage.css`
- `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`
- `frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx`
- `frontend/src/features/stock-analysis/components/StockAnalysisObservationPreview.tsx`
- `frontend/src/test/StockAnalysisObservationPreview.test.tsx`

### P2: Browser Smoke Data-Source Contracts Were Mixed

Root cause: the browser smoke suite contained both mock-first visual/a11y checks and real-client route-mocked checks. Running the whole suite under `VITE_DATA_SOURCE=mock` made the monthly operating analysis audit smoke look broken because that test asserts the real client path. Running the whole suite under `VITE_DATA_SOURCE=real` then exercised routes that still require a live real backend target or mock-only page fixtures.

Closure:
- Added explicit data-source guards to the real-only monthly operating analysis audit smoke and the mock-only stock analysis preview smoke.
- Re-ran the full mock smoke suite as the stable first-screen/a11y gate.
- Re-ran monthly operating analysis audit separately under the real client with route-mocked API responses.
- Kept the real-backend all-suite run out of the closure claim until a live backend target and MCP authority evidence are available.

Evidence:
- `frontend/tests/playwright/monthly-operating-analysis-audit-smoke.spec.mjs`
- `frontend/tests/playwright/stock-analysis-mock-smoke.spec.mjs`
- `.codex-tmp/playwright-page-results/full-a11y-smoke-mock-20260610091019`
- `.codex-tmp/playwright-page-results/monthly-operating-real-smoke-after-contract-20260610091413`

### P1: Full Real-Backend Browser Smoke Gate

Root cause: the audit previously had full mock smoke and route-mocked real-client evidence, but did not yet have a full browser run against a live backend target and a real-mode frontend.

Closure:
- Verified backend health at `http://127.0.0.1:7888/health` and readiness at `http://127.0.0.1:7888/health/ready`; PostgreSQL, DuckDB read-only path, Redis, object store, and home snapshot prewarm reported ok.
- Verified the running frontend at `http://127.0.0.1:5888` served `import.meta.env.VITE_DATA_SOURCE: "real"` in both `src/api/clientContext.ts` and `src/router/routes.tsx`.
- Ran the full `frontend/tests/playwright/a11y-visual-smoke.spec.mjs` route suite against the existing real-mode frontend and live backend target.
- First full run produced `46 passed, 1 failed` on Bond Analysis control-context keyboard focus. A read-only focus probe showed the report-date selector was enabled and reachable on the first `Tab` after the skip-link main-content path; the targeted rerun passed `1 passed`.
- Accepted full rerun output `.codex-tmp/playwright-page-results/full-real-backend-smoke-20260610-135505` passed: `47 passed`.

Boundary:
- This closes only the full real-backend browser-smoke audit lane.
- It does not approve metrics, certify routes, capture owner approval, write governance records, resolve calculation/display P1 owner decisions, or replace direct Codex App MCP/GitNexus evidence.

Evidence:
- `docs/audits/2026-06-10-real-backend-smoke-result.md`
- `.codex-tmp/playwright-page-results/full-real-backend-smoke-20260610-135505`
- `.codex-tmp/playwright-page-results/bond-analysis-control-context-rerun-20260610-135351`
- `.codex-tmp/playwright-page-results/full-real-backend-smoke-20260610-132949`

### P2: Business Display Coverage Report Lagged Behind Browser Smoke Scope

Root cause: the business display coverage report still mapped only 9 high-risk routes, while the browser smoke/a11y scaffold had expanded to 26 first-screen business routes.

Closure:
- Expanded the static coverage map to all 26 browser-smoke business display routes.
- Kept the report boundary explicit: it maps existing evidence and smoke configuration only; it does not run browser smoke, prove business correctness, approve a metric/page, or capture business-owner approval.
- Preserved owner-approval boundaries separately from generic governance/boundary evidence so readiness cannot be promoted to page closure by naming alone.

Evidence:
- `scripts/business_display_coverage_report.py`
- `tests/test_business_display_coverage_report.py`
- `docs/audits/business-display-coverage-report.json`
- `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`

### P2: Route-Scope Certification Remains Fail-Closed

Root cause: page readiness static-pass status can be misread as business-contract certification unless route scope, owner approval, golden/manual review, and closure status are checked together.

Closure:
- Generated current all-page readiness and route-scope classification summaries.
- Confirmed 39 seeded page routes, 39 static-pass pages, 27 run-supported pages, and 0 blocked static gates.
- Confirmed 0 business-contract-certified routes; 23 routes remain evidence-pending, 6 are frontend-ready analytical/tooling surfaces, and 10 are frontend-only/home/summary surfaces.
- Confirmed 7 business-owner approval-pending pages with 84 total approval action items: product-category PnL, balance analysis, average balance, ledger PnL, PnL attribution, bond analysis, and stock analysis.

Evidence:
- `scripts/codex_page_readiness.py`
- `tests/test_codex_page_readiness_gate.py`
- `docs/audits/2026-06-10-system-wide-skills-audit.md`

### P2: MCP Governance Queue Contract Drift

Root cause: local `tests/test_project_mcp_servers.py` no longer matches the current page-governance seeded queue. The MCP payload now reports additional ready/manual-review pages and different record-gap groupings than the test's hard-coded expected lists.

Closure:
- Verified project MCP registration in `.codex/config.toml` and `.mcp.json` for `gitnexus`, `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `moss-data-quality`.
- Verified local stdio handshakes through `scripts/mcp/moss_mcp_launcher.py`: metric contracts exposes 3 tools and 6 resources; lineage evidence exposes 13 tools and 9 resources; data catalog exposes 5 tools and 3 resources; data quality exposes 3 tools and 3 resources.
- Called read-only local MCP tools for current audit summaries:
  - `moss-metric-contracts.get_page_evidence_readiness` across 39 seeded pages -> 5 formal-use-allowed pages, 34 candidate/gap pages, and 39 pages still requiring direct catalog/date review.
  - `moss-data-catalog.get_page_catalog_date_coverage` -> 35-page catalog/date scope, 29 configured pages, 6 deferred no-direct-table pages, 0 missing explicit configs.
  - `moss-data-catalog.get_page_catalog_date_lineage_review_queue` -> 35 pages, 29 review rows, 6 deferred rows, `closure_ready_count=0`, `queue_grants_closure=false`, 50 checked boundary work items, 0 scope violations.
  - `moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue` with `all_seeded_pages=true` -> 39 pages, 42 manual-review blockers, 6 present-evidence-needs-review items, `closure_ready_count=0`, `queue_grants_closure=false`, 107 checked boundary work items, 0 scope violations.
- Split the two current queue scopes explicitly: all-seeded governance evidence packet queue is 39 pages with 16 ready/manual-review pages and 23 record-gap pages; catalog/date-lineage assignment queue is 35 pages with 13 ready/manual-review pages and 22 record-gap pages.
- Updated catalog/date coverage expectations for the current 35-page assignment scope: 29 configured pages, 6 deferred pages, and 0 missing explicit configs.
- Kept `kpi-performance` as ready/manual-review in the deferred lane, not a create-direct-record item.
- Preserved all no-closure/no-write/no-execution/no-approval boundary assertions.

Evidence:
- `.codex/config.toml`
- `.mcp.json`
- `scripts/mcp/moss_mcp_launcher.py`
- `scripts/mcp/moss_project_mcp.py`
- `tests/test_project_mcp_servers.py`
- `docs/MCP_RUNBOOK.md`
- `docs/audits/2026-06-02-system-audit-first-pass.md`

### P2: Business-Owner Approval Gates Remain Fail-Closed

Root cause: several high-risk pages have technical evidence packets or field-complete governance records, but business-owner approval is still external and not captured in the repository templates.

Closure:
- Ran the existing approval checkers for product-category PnL, balance analysis, average balance, ledger PnL, PnL attribution, bond analysis, and stock analysis.
- Normal mode reports `approval_status=pending` and `business_owner_approval_captured=false` for all seven.
- Strict `--require-captured` mode fails for all seven, preserving the approval gate instead of promoting technical readiness to page closure.
- Product Category remains `closure_approved=false` even though its checker reports `formal_use_allowed=true`; the closure checklist and owner action items still block certification.
- Added page-specific local MCP/owner-review evidence summary for all seven pending pages in `docs/audits/2026-06-10-owner-approval-mcp-evidence-summary.md`.
- Added a fresh approval action matrix to the owner-review summary: all seven pages still miss owner name, owner role, approval decision, approval date, and owner signature; page-specific pending review items are now split by evidence/boundary type.
- Confirmed `scripts/codex-verify-page.ps1 -DryRun` expands page-specific backend, frontend, browser-smoke, typecheck, debt-audit, and build checks for all seven pending pages.
- Ran the seven-page browser a11y smoke slice in single-worker mode; all seven page routes rendered their ready selectors and had zero critical axe violations in that run.
- Ran the seven-page frontend page/model/component test slice; 20 test files and 517 tests passed.
- Ran the seven-page backend/API/service/governance test slice after the PnL Attribution empty-storage fix; 592 tests passed.
- Added a machine-readable fail-closed owner snapshot: 7 pending pages, 0 captured approvals, 0 closure-approved pages, 84 action items, strict `--require-captured` rejection for all seven pages, and owner approval status tests at 93 passed.

Evidence:
- `scripts/check_product_category_pnl_business_owner_approval.py`
- `scripts/check_balance_analysis_business_owner_approval.py`
- `scripts/check_average_balance_business_owner_approval.py`
- `scripts/check_ledger_pnl_business_owner_approval.py`
- `scripts/check_pnl_attribution_business_owner_approval.py`
- `scripts/check_bond_analysis_business_owner_approval.py`
- `scripts/check_stock_analysis_business_owner_approval.py`
- `docs/pnl/*business-owner-approval-template.md`
- `docs/audits/2026-06-10-owner-approval-mcp-evidence-summary.md`
- `docs/audits/2026-06-10-owner-approval-fail-closed-snapshot.json`
- `scripts/codex-verify-page.ps1`
- `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`

### P1: PnL Attribution Empty Storage Broke Fail-Soft API Contract

Root cause: `PnlRepository._list_report_dates()` opened DuckDB in read-only mode and converted a missing database file into `Formal pnl storage is unavailable.`, so PnL Attribution's empty-storage contract returned a server exception instead of a warning/empty envelope.

Closure:
- Added a narrow PnL Attribution workbench helper that treats a missing DuckDB file as an empty formal-date list only for Attribution empty-state envelopes.
- Preserved the existing fail-closed behavior for formal PnL APIs, non-missing DuckDB errors, and other PnL repository paths.
- Kept missing-table handling as an empty report-date list where the repository already supports it.
- Re-ran the PnL Attribution API contract and the broader seven-page backend slice.

Evidence:
- `backend/app/services/pnl_attribution_service.py`
- `tests/test_pnl_attribution_api_contract.py`

## Open Findings

### P1: Calculation and Display Logic Requires Business Rulings

The companion calculation/display-logic audit found no P0 issue. It originally recorded 11 P1 findings. P1-08 bond-dashboard null handling and false MoM was verified closed before owner review; P1-07 and P1-09 were later owner-selected, implemented, and verified closed, leaving 8 unresolved P1 findings as of the 2026-08-06 governance overlay. Several remaining items are not simple implementation bugs: the repository contains two contradictory implementations or sign/unit conventions, and both sides have tests that preserve their current behavior.

Primary open P1 groups:
- Backend unit/sign conflicts: Campisi coupon-income units, bond analytics rate-unit heuristic, PnL bridge roll-down sign, period yield denominator, PnL bridge residual quality flag, and macro-liquidity score polarity.
- Backend control weakness: QDB monthly analysis compares position-vs-ledger through same-source formulas, so the reconciliation diff can be permanently zero.
- Frontend metric hazards: balance movement share recomputation ahead of backend values, frontend formal PnL/yield/ADB aggregation, and credit-spread rating-tenor aggregation in the browser. The bond-dashboard null-to-zero and false-MoM hazard is closed by formatter/page regression evidence.

Required closure path:
1. Business owner decides the authoritative rule where two conventions conflict.
2. `docs/calc_rules.md` and metric/page contracts are updated first.
3. Implementation is normalized at the authoritative layer.
4. The tests that currently freeze the wrong side are updated with numeric regression evidence.

This is a fail-closed audit result: existing green tests prove current behavior is stable, not that every calculation convention is business-approved.

Owner review aid:
- `docs/audits/2026-06-10-calculation-p1-owner-decision-matrix.md` lists the 8 remaining P1 decisions, candidate conventions, proposed review defaults, impact if unresolved, and closure evidence; it separately records P1-07/P1-09 as owner-decision closed and P1-08 as verified closed.

## Verification Run

Frontend:
- `npm audit --audit-level=moderate` -> 0 vulnerabilities.
- `npm ls react-router-dom react-router @remix-run/router` -> `react-router-dom@6.30.4`, `react-router@6.30.4`, `@remix-run/router@1.23.3`.
- `npm run lint` -> passed.
- `npm run typecheck` -> passed.
- `npm run debt:audit` -> passed.
- `npm run build` -> passed.
- `npm run test -- src/test/StockAnalysisObservationPreview.test.tsx src/test/MarketDataPage.test.tsx src/test/BondDashboardPage.test.tsx src/test/StockAnalysisPage.test.tsx` -> 127 passed.
- `npm run test -- src/test/StockAnalysisObservationPreview.test.tsx src/test/MarketDataPage.test.tsx src/test/BondDashboardPage.test.tsx` -> 35 passed.
- Initial fresh `npm.cmd run test:a11y-smoke -- --workers=1` with `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1`, `VITE_DATA_SOURCE=mock`, and output under `.codex-tmp/playwright-page-results/full-a11y-smoke-20260610085604` -> 50 passed, 1 failed, 1 skipped; the failure was the real-client monthly operating analysis audit smoke asserting "formal API path" while the app was intentionally in mock/offline mode.
- Follow-up `npm.cmd run test:a11y-smoke -- tests/playwright/monthly-operating-analysis-audit-smoke.spec.mjs --workers=1` with `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1`, `VITE_DATA_SOURCE=real`, and output under `.codex-tmp/playwright-page-results/monthly-operating-real-smoke-20260610090106` -> 1 passed, confirming the monthly operating analysis audit page works under its intended real-client route-mocked contract.
- Exploratory full real-client `npm.cmd run test:a11y-smoke -- --workers=1` with output under `.codex-tmp/playwright-page-results/full-a11y-smoke-real-20260610090211` -> 46 passed, 5 failed, 1 skipped; failures were not used for closure because the run mixed live-real route assumptions with mock-only smoke and routes that still need a real backend target.
- After adding data-source guards, `npm.cmd run test:a11y-smoke -- --workers=1` with `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1`, `MOSS_PLAYWRIGHT_PORT=5924`, `VITE_DATA_SOURCE=mock`, and output under `.codex-tmp/playwright-page-results/full-a11y-smoke-mock-20260610091019` -> 50 passed, 2 skipped.
- After adding data-source guards, `npm.cmd run test:a11y-smoke -- tests/playwright/monthly-operating-analysis-audit-smoke.spec.mjs --workers=1` with `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1`, `MOSS_PLAYWRIGHT_PORT=5925`, `VITE_DATA_SOURCE=real`, and output under `.codex-tmp/playwright-page-results/monthly-operating-real-smoke-after-contract-20260610091413` -> 1 passed.
- Real backend preflight on 2026-06-10: `GET http://127.0.0.1:7888/health` -> HTTP 200; `GET http://127.0.0.1:7888/health/ready` -> `status=ok`; `GET http://127.0.0.1:5888/` -> HTTP 200; served frontend modules expose `VITE_DATA_SOURCE: "real"`.
- First full real-backend run `npm.cmd run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1` with `MOSS_PLAYWRIGHT_BASE_URL=http://127.0.0.1:5888` and output under `.codex-tmp/playwright-page-results/full-real-backend-smoke-20260610-132949` -> 46 passed, 1 failed on Bond Analysis report-date keyboard focus.
- Bond Analysis flake review: read-only focus probe showed the report-date selector enabled, focusable, and reached on the first `Tab` after skip-link main-content focus; targeted rerun with output under `.codex-tmp/playwright-page-results/bond-analysis-control-context-rerun-20260610-135351` -> 1 passed.
- Accepted full real-backend rerun `npm.cmd run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1` with `MOSS_PLAYWRIGHT_BASE_URL=http://127.0.0.1:5888` and output under `.codex-tmp/playwright-page-results/full-real-backend-smoke-20260610-135505` -> 47 passed.

Backend and audit guards:
- `python -m pytest tests/test_macro_toolkit_scripts.py -q` -> 83 passed.
- `python -m pytest tests/test_write_route_auth_contract.py -q` -> 46 passed.
- `python -m pytest tests/test_worker_bootstrap.py -q` -> 6 passed.
- `python -m pytest tests/test_supply_chain_security_scanning.py tests/test_secret_hygiene.py -q` -> 7 passed.
- `python scripts/supply_chain_security_scan.py --dry-run` -> emitted gitleaks/osv scan plan.
- Portable local scanner versions: `gitleaks 8.30.1`; `osv-scanner 2.3.8`, `osv-scalibr 0.4.5`.
- First non-dry-run `python scripts\supply_chain_security_scan.py --tool all --report-dir test_output\security-scans` -> exit 1 with 950 gitleaks findings, dominated by ignored local caches, generated builds, OMX research copies, temporary worktrees, and one tracked Risk Tensor metric-key false positive. OSV still produced an empty vulnerability report.
- After narrowing `.gitleaks.toml` for already-ignored generated/local directories and the governed Risk Tensor metric-key false positive, direct portable redacted gitleaks was refreshed at `2026-06-10T15:45:10+08:00` -> exit 1 because 2 findings remain, both in ignored/untracked `config/.env` (`MOSS_TUSHARE_TOKEN`, `STITCH_API_KEY`, values redacted; no value captured).
- `git check-ignore -v config/.env` -> ignored by `.gitignore`; `git ls-files -- config/.env` -> not tracked.
- Direct portable `osv-scanner` was refreshed at `2026-06-10T15:45:10+08:00` against `backend/uv.lock` and `frontend/package-lock.json` -> exit 0; parsed `osv-report.json` shows 0 results, 0 package findings, and 0 vulnerabilities.
- Latest local-secret non-closing retry at `2026-06-10T17:30:56+08:00` -> safe boundary checks still show `config/.env` exists, is ignored by `.gitignore:4`, has no tracked path, and is reported as ignored; redacted gitleaks still reports 2 local findings with values not read or captured; OSV could not refresh because proxy `127.0.0.1:9` refused the connection, so the previous successful OSV 0-vulnerability result remains the last successful OSV evidence.
- Latest local-secret boundary-only recheck at `2026-06-10T21:25:00+08:00` -> without reading values or replacing the last full redacted scan, `config/.env` still exists, is ignored by `.gitignore:4:config/.env`, has no tracked Git path, is reported as ignored, dry-run still includes `--redact`, and refresh tests passed.
- `python -m pytest tests/test_startup_auth_guardrails.py tests/test_auth_context.py -q` -> 16 passed.
- `python -m pytest tests/test_codex_page_readiness_gate.py tests/test_frontend_playwright_smoke_scaffold.py -q` -> 49 passed.
- `python scripts\codex_page_readiness.py --all` refreshed at `2026-06-10T19:08:54+08:00` -> 39 pages, 39 static-pass, 0 blocked, 27 run-supported, 7 business-owner approval pending, 84 approval action items, 0 `governance_record_validation` nulls, 0 `audit_review` nulls, 23 `missing_direct_records`, 16 `direct_records_ready_for_audit_review`, and 12 incomplete catalog/date evidence pages.
- `python scripts\codex_page_readiness.py --route-scope` -> 39 seeded routes, 36 visible navigation routes, 0 visible-unseeded routes, 0 business-contract-certified, 23 evidence-pending, 6 frontend-ready, 10 frontend-only.
- `python scripts\business_display_coverage_report.py` -> 26 tracked routes, 0 route gaps, 26 configured browser smoke/a11y routes.
- `python -m pytest tests/test_business_display_coverage_report.py tests/test_frontend_playwright_smoke_scaffold.py -q` -> 8 passed.
- `pytest tests/test_system_audit_manifest_contract.py tests/test_system_audit_completion_snapshot_verifier.py -q` -> 21 passed. This checks that the manifest references existing artifacts, stays fail-closed, matches coverage/fresh-verification counts, preserves owner-approval, direct App MCP/GitNexus gap, Ledger PnL direct-record, local secret hygiene, owner-review non-approval boundaries, completion snapshot alignment, owner/governance follow-up packet and Chinese brief coverage, calculation P1 engineering-prework map coverage, action-register routing, and keeps the real-backend smoke result non-certifying.
- Historical 2026-06-10 `python scripts\verify_system_audit_completion_snapshot.py` evidence passed with 5 open blockers and 5 completion gates. The 2026-08-06 P1 overlay updates the active calculation target to `calculation_prework_p1_count=8` while preserving `calculation_snapshot_status=owner_decision_required`.
- `pytest tests/test_system_audit_pulse.py -q` -> 7 passed. This checks that `scripts/system_audit_pulse.py` remains read-only, preserves non-approval flags, detects route-scope and business-display drift, formats the Markdown watch board, and does not run the slower all-page readiness scan unless explicitly requested.
- `python scripts\system_audit_pulse.py --generated-at 2026-06-10T19:45:00+08:00` -> `status=pass`, `completion_state=not_complete`, `open_blocker_count=5`, `route_count=39`, `business_contract_certified_count=0`, `tracked_route_count=26`, `route_gap_count=0`, completion snapshot status pass, and `drift_errors=[]`; `--format markdown` renders the same non-approval watch board for human review. This is monitoring evidence only, not completion evidence.
- `python scripts\system_audit_pulse.py --generated-at 2026-06-10T20:05:00+08:00 --output docs\audits\2026-06-10-system-audit-pulse-snapshot.json` -> saved a machine-readable pulse snapshot with 5 open blockers, read-only evidence scope, no drift errors, and the same non-approval boundary.
- `pytest tests/test_system_audit_monitoring_snapshot_verifier.py -q` -> 7 passed. This checks that the unified monitoring snapshot stays aligned with the manifest, pulse, completion snapshot, calculation decision snapshot, direct App MCP/GitNexus tool-surface snapshot, local secret hygiene snapshot, and Ledger PnL direct-governance snapshot without granting approval.
- `python scripts\verify_system_audit_monitoring_snapshot.py` -> pass with `open_blocker_count=5`, `completion_status=pass`, `pulse_status=pass`, `pulse_completion_state=not_complete`, and `errors=[]`.
- `tool_search query: moss metric contracts lineage evidence data catalog gitnexus MCP tools` plus `python scripts\refresh_direct_app_mcp_gitnexus_tool_surface_snapshot.py --generated-at 2026-06-10T21:25:00+08:00 --gitnexus-tool-names codex_app.handoff_thread codex_app.fork_thread codex_app.automation_update` -> 0 relevant direct MOSS/GitNexus tools found in the current Codex App tool surface at `2026-06-10T21:25:00+08:00`; focused MOSS keyword rechecks returned 0 tools, and the focused GitNexus keyword recheck returned only 3 Codex App thread/automation management tools with 0 relevant direct evidence tools, so the direct App MCP/GitNexus evidence gap remains open.
- `python scripts\refresh_ledger_pnl_direct_governance_record_snapshot.py`; direct `cache_manifest.jsonl` search; `python scripts\codex_page_readiness.py --page-slug ledger-pnl` refreshed at `2026-06-10T21:25:00+08:00` -> dry-run candidate has `validation_status=ready_for_audit_review`, `record_write_status=not_requested`, `existing_record_line=null`, no written direct record search matches, and page readiness remains `formal_use_allowed=false` / `closure_approved=false`.
- `python scripts\supply_chain_security_scan.py --dry-run`; `Test-Path config/.env`; `git check-ignore -v config/.env`; `git ls-files -- config/.env`; `git status --ignored --short -- config/.env`; safe parsing of `osv-report.json` and redacted `gitleaks-report.json` refreshed at `2026-06-10T15:45:10+08:00` -> gitleaks plan includes `--redact`; `config/.env` exists, is ignored by `.gitignore:4`, has no tracked path, and is reported as ignored; OSV has 0 vulnerabilities; gitleaks has 2 local findings with values not read or captured.
- Latest local-secret retry at `2026-06-10T17:30:56+08:00` -> redacted gitleaks still has 2 ignored/untracked `config/.env` findings; OSV retry failed because proxy `127.0.0.1:9` refused the connection; secret values were not read, logged, or captured.
- Latest local-secret boundary-only recheck at `2026-06-10T21:25:00+08:00` -> `Test-Path config\.env` true, `git check-ignore -v config/.env` matched `.gitignore:4:config/.env`, `git ls-files -- config/.env` returned no tracked path, `git status --ignored --short -- config/.env` returned `!! config/.env`, and `pytest tests/test_local_secret_hygiene_snapshot_refresh.py -q` passed; secret values were not read, logged, or captured.
- `python -m pytest tests/test_frontend_playwright_smoke_scaffold.py -q --basetemp=.codex-tmp\pytest-basetemp\frontend-playwright-smoke-scaffold-after-data-source-guards` -> 4 passed.
- `python -m pytest tests/test_codex_page_readiness_gate.py tests/test_business_display_coverage_report.py tests/test_frontend_playwright_smoke_scaffold.py tests/test_supply_chain_security_scanning.py tests/test_secret_hygiene.py -q` -> 60 passed.
- `python -m pytest tests/test_materialize_flow.py tests/test_product_category_pnl_flow.py tests/test_ledger_analytics_api.py tests/test_pnl_materialize_flow.py -q` -> 84 passed, 1 skipped.
- `python -m pytest tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_coverage_prioritizes_missing_seeded_page_configs tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_routes_closure_blockers tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_groups_record_remediation_work_items tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_builds_record_gap_execution_plan tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_groups_record_remediation_evidence_work_items tests/test_project_mcp_servers.py::test_data_catalog_page_catalog_date_lineage_review_queue_groups_record_remediation_by_lane -q --tb=short` -> 6 passed.
- `python -m pytest tests/test_project_mcp_servers.py -q` -> 199 passed.
- Local MCP stdio handshake against `metric-contracts`, `lineage-evidence`, `data-catalog`, and `data-quality` launch modes -> all returned `returncode=0`, expected server names, non-empty tools, and non-empty resources.
- Local MCP tool calls:
  - `get_page_evidence_readiness` for 39 page IDs -> page count 39; formal-use-allowed 5; candidate/gap 34; direct catalog/date review required 39.
  - `get_page_catalog_date_coverage` -> 35 pages; configured 29; deferred 6; missing explicit configs 0.
  - `get_page_catalog_date_lineage_review_queue` -> 35 pages; 29 review items; 6 deferred items; closure ready 0; queue grants closure false; queue boundary audit has 50 checked work items and 0 scope violations.
  - `get_page_governance_audit_evidence_packet_queue` with `all_seeded_pages=true` -> 39 pages; 42 manual-review blockers; 6 present-evidence-needs-review items; closure ready 0; queue grants closure false; queue boundary audit has 107 checked work items and 0 scope violations.
- Fresh full MCP contract suite rerun: `python -m pytest tests/test_project_mcp_servers.py -q` -> 199 passed in 338.00s.
- Local MCP page-specific packets for product-category PnL, balance analysis, average balance, ledger PnL, PnL attribution, bond analysis, and stock analysis -> 6 pages ready for audit review with direct records; ledger PnL remains blocked by direct page/API record fields; all 7 have `closure_approved=false`.
- Fresh Ledger PnL direct-record drill-down: `python scripts\refresh_ledger_pnl_direct_governance_record_snapshot.py` -> dry-run only, `existing_record_line=null`, `record_write_status=not_requested`, and `validation_status=ready_for_audit_review` for a field-complete `PAGE-LEDGER-PNL-001` candidate keyed by `ledger_pnl.summary:2026-05-31:ALL`; no `--write` command was run.
- Direct search of `data/governance/cache_manifest.jsonl` for `PAGE-LEDGER-PNL-001`, `/api/ledger-pnl/summary`, and `ledger_pnl.summary:2026-05-31:ALL` -> no matching written direct record found.
- `python scripts\codex_page_readiness.py --page-slug ledger-pnl` -> static-pass, `formal_use_allowed=false`, `business_owner_approval_captured=false`, `governance_record_validation=missing_direct_records`, `audit_review=blocked_by_record_gaps`, and required direct-record/page-review gaps preserved.
- `python -m pytest tests\test_project_mcp_servers.py::test_lineage_evidence_governance_record_blueprint_queue_covers_default_open_gaps tests\test_ledger_pnl_business_owner_approval_status.py -q --tb=short --basetemp=.codex-tmp\pytest-basetemp\ledger-pnl-direct-record-refresh` -> 13 passed.
- Approval checker normal mode for product-category PnL, balance analysis, average balance, ledger PnL, PnL attribution, bond analysis, and stock analysis -> all report pending approval with no captured owner approval.
- Approval checker strict `--require-captured` mode for the same seven pages -> all fail as expected while approval is pending.
- `python -m pytest tests/test_product_category_pnl_business_owner_approval_status.py tests/test_balance_analysis_business_owner_approval_status.py tests/test_average_balance_business_owner_approval_status.py tests/test_ledger_pnl_business_owner_approval_status.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_bond_analysis_business_owner_approval_status.py tests/test_stock_analysis_business_owner_approval_status.py -q` -> 93 passed.
- Historical calculation owner-decision snapshot at `2026-06-10T21:25:00+08:00` recorded 10 open rows (`P1-01`, `P1-02`, `P1-03`, `P1-04`, `P1-05`, `P1-06`, `P1-07`, `P1-09`, `P1-10`, `P1-11`) and kept `P1-08` verified closed. The current overlay refreshed at `2026-08-06T22:30:00+08:00` retains that baseline explicitly as historical and reports 8 unresolved rows (`P1-01` through `P1-06`, `P1-10`, `P1-11`); P1-07 and P1-09 are owner-selected and implementation-verified closed.
- P1-08 regression refresh at `2026-06-10T19:29:53+08:00`: `npm.cmd test -- src/features/bond-dashboard/utils/format.test.ts src/test/BondDashboardPage.test.tsx` -> 2 test files passed, 16 tests passed.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-verify-page.ps1 -PageSlug <each pending page> -DryRun` -> product-category-pnl, balance-analysis, average-balance, bond-analysis, ledger-pnl, stock-analysis, and pnl-attribution all expand page-specific MCP/backend/frontend/browser/global verification plans.
- `npm run test:a11y-smoke -- --grep '@(product-category-pnl|balance-analysis|average-balance|bond-analysis|ledger-pnl|stock-analysis|pnl-attribution)'` -> first parallel run produced 3 passed and 4 axe execution-context failures during page navigation; no critical axe violation payload was reported in those failures.
- `npm run test:a11y-smoke -- --grep '@(product-category-pnl|balance-analysis|average-balance|bond-analysis|ledger-pnl|stock-analysis|pnl-attribution)' --workers=1` with `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1`, `MOSS_PLAYWRIGHT_PORT=5920`, and output under `.codex-tmp/playwright-page-results/owner-pending-7-sequential-20260610072852` -> 7 passed with screenshots.
- `npm.cmd run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/ProductCategoryBranchSwitcher.test.tsx src/test/ProductCategoryAdjustmentAuditPage.test.tsx src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts src/test/BalanceAnalysisPage.test.tsx src/test/AverageBalancePage.test.tsx src/test/AverageBalanceView.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx src/test/BondAnalyticsViewContent.test.tsx src/test/BondAnalyticsView.test.tsx src/test/BondAnalyticsInstitutionalCockpit.test.tsx src/test/LedgerPnlPage.test.tsx src/test/LedgerPnlRoutesSmoke.test.tsx src/test/StockAnalysisPage.test.tsx src/test/StockAnalysisPageModel.test.ts src/test/StockDetailDrawer.test.tsx src/features/stock-analysis/lib/buildConsensusSummary.test.ts src/test/PnlAttributionPage.test.tsx src/features/pnl-attribution/adapters/pnlAttributionAdapter.test.ts src/features/pnl-attribution/components/PnlAttributionView.test.ts` -> 20 test files passed, 517 tests passed.
- `python -m pytest tests/test_pnl_attribution_api_contract.py tests/test_pnl_api_contract.py::test_pnl_dates_returns_503_when_storage_is_unavailable tests/test_pnl_api_contract.py::test_pnl_overview_returns_503_when_storage_is_unavailable tests/test_pnl_api_contract.py::test_pnl_dates_returns_503_when_required_tables_are_missing tests/test_pnl_api_contract.py::test_pnl_dates_accepts_single_available_fact_table tests/test_pnl_api_contract.py::test_pnl_finance_read_surfaces_return_503_when_storage_is_unavailable -q --basetemp=.codex-tmp\pytest-basetemp\pnl-attribution-and-storage-contract-after-scope-fix` -> 15 passed.
- `python -m pytest <seven-page backend/API/service/governance slice> -q --basetemp=.codex-tmp\pytest-basetemp\owner-pending-7-backend-final-after-packet` covering product-category PnL, balance analysis, average balance, bond analysis, ledger PnL, stock analysis, and PnL Attribution -> 592 passed in 669.70s.
- `git diff --check` -> no whitespace errors; line-ending warnings only.

Generated evidence:
- `docs/audits/business-display-coverage-report.json` reports 26 tracked business display routes, 0 route gaps, and 26 configured browser smoke/a11y routes. Its own `evidence_scope` states it maps evidence only and does not run smoke tests, prove business correctness, capture owner approval, or approve metrics/pages.
- `docs/audits/2026-06-10-system-audit-manifest.json` records fresh verification for page readiness, route scope, business display coverage, owner approval, Ledger PnL direct-record evidence, and calculation P1 owner-decision evidence; it also carries the accepted full real-backend browser-smoke evidence. The manifest explicitly keeps `approves_metrics=false`, `approves_pages=false`, `captures_business_owner_approval=false`, `writes_governance_records=false`, and `certifies_routes=false`.
- `docs/audits/2026-06-10-system-audit-completion-snapshot.json` records 5 open blockers, 5 completion gates, 0 completed blockers, 0 business-contract-certified routes, and non-approval flags for metrics, pages, governance records, local secret hygiene, and direct App MCP/GitNexus evidence.
- `docs/audits/2026-06-10-owner-governance-follow-up-packet.json` and `docs/audits/2026-06-10-owner-governance-follow-up-brief.zh.md` record owner/governance routing for all 5 open blockers. The packet now separates engineering-safe prework from external closure inputs and post-input closure evidence. It is explicitly non-approving, does not authorize Ledger PnL `--write`, does not request/capture secret values, and is checked by `scripts/verify_system_audit_completion_snapshot.py`.
- `docs/audits/2026-06-10-owner-approval-fail-closed-snapshot.json` records the seven-page owner gate as fail-closed, refreshed at `2026-06-10T19:26:44+08:00`: 7 pending, 0 captured, 0 closure-approved, 84 action items, strict approval capture rejected 7/7, and 93 owner approval status tests passed.
- `docs/audits/2026-06-10-system-audit-pulse-snapshot.json` records the latest saved read-only pulse: status pass, completion state not complete, 5 open blockers, 39 route-scope routes, 26 tracked business-display routes, 0 route gaps, completion snapshot pass, and `drift_errors=[]`; it explicitly does not approve metrics, pages, owner signoff, governance records, secret hygiene, direct App MCP/GitNexus evidence, or route certification.
- `docs/audits/2026-06-10-direct-app-mcp-gitnexus-tool-surface-snapshot.json` records the direct App MCP/GitNexus evidence gap as fail-closed: 0 relevant direct MOSS/GitNexus tools discovered in the current App surface, focused MOSS keyword rechecks returned 0 tools, the focused GitNexus keyword recheck returned only non-evidence Codex App management tools, local config declarations present, local stdio evidence marked fallback-only, and no approval/closure effect.
- `docs/audits/2026-06-10-ledger-pnl-direct-governance-record-snapshot.json` records the Ledger PnL direct-record gap as fail-closed and is refreshable by `python scripts\refresh_ledger_pnl_direct_governance_record_snapshot.py`, refreshed at `2026-06-10T21:25:00+08:00`: dry-run only, no written direct record match, static-pass readiness only, `formal_use_allowed=false`, and `closure_approved=false`.
- `docs/audits/2026-06-10-local-secret-hygiene-snapshot.json` records the local secret hygiene gap as fail-closed, last fully refreshed at `2026-06-10T15:45:10+08:00`: direct OSV 0 vulnerabilities, direct redacted gitleaks 2 local ignored/untracked findings, secret names only, values not captured, `config/.env` ignored and untracked, and clean-runner/owner action still required. It also records the `2026-06-10T17:30:56+08:00` non-closing retry and the `2026-06-10T21:25:00+08:00` boundary-only recheck; the latest recheck still shows `config/.env` exists, is ignored, and is untracked.

## Residual Risks

- MCP App-surface gap: direct Codex App tools for MOSS MCP and GitNexus were not exposed in this session. Fresh tool discovery at 2026-06-10T21:25:00+08:00 for `moss metric contracts lineage evidence data catalog gitnexus MCP tools` returned 0 relevant direct tools; focused MOSS keyword rechecks returned 0 tools, while the focused GitNexus keyword recheck returned only 3 Codex App thread/automation management tools and 0 relevant direct evidence tools. Local `.codex/config.toml` and `.mcp.json` declare the expected servers, and local MOSS MCP stdio launchers, tools/resources, read-only queue calls, and the full project MCP server contract suite pass. The remaining gap is client/session direct-tool exposure plus page-level manual review, not local MOSS MCP server registration.
- GitNexus impact evidence was declared in MCP config but not callable as a direct Codex App tool in this session.
- Local MOSS MCP evidence still does not approve metrics/pages, prove live page/API execution, write governance records, or capture business-owner approval.
- Calculation/display-logic owner routing has 8 unresolved P1 items. Several need business owner rulings before code changes because existing tests currently freeze contradictory conventions. P1-07 and P1-09 are owner-selected and implementation-verified closed; P1-08 bond-dashboard null handling remains closed by the targeted formatter/page test slice.
- Ledger PnL has a field-complete dry-run direct-record candidate for `PAGE-LEDGER-PNL-001` and `/api/ledger-pnl/summary`, but no matching written record exists in `data/governance/cache_manifest.jsonl`; the page must remain `formal_use_allowed=false` and `closure_approved=false` until an approved governance workflow writes or locates the direct record and downstream review gates pass.
- Route-scope certification remains deliberately fail-closed: current local evidence reports 0 business-contract-certified routes even though all 39 seeded pages static-pass.
- Business-owner approval remains pending for several high-risk routes by design; readiness tests preserve that status instead of promoting candidate pages as formally approved.
- Browser smoke is now split by data-source contract: full mock smoke passes as the stable first-screen/a11y gate, the monthly operating analysis audit real-client smoke passes separately, and the full real-backend smoke has an accepted 47-passed rerun recorded in `docs/audits/2026-06-10-real-backend-smoke-result.md`. This browser evidence still does not certify business contracts, approve metrics/pages, write governance records, or capture business-owner approval.
- Redacted gitleaks still exits non-zero in this local workspace because ignored/untracked `config/.env` contains two detected local credential findings. The latest scan retry at `2026-06-10T17:30:56+08:00` did not clear them, and OSV could not be refreshed because proxy `127.0.0.1:9` refused the connection. The latest boundary-only recheck at `2026-06-10T21:25:00+08:00` still shows the file exists, is ignored, and is untracked. The file is not tracked, values were not captured, and the values should be treated as sensitive local secrets and rotated/confirmed according to owner policy if exposure is suspected.
- CI/clean-runner evidence is still recommended because this workspace contains many ignored runtime artifacts that are outside the repository source boundary.
- Wide all-file tests are large and were run as targeted slices. The targeted slices cover the changed/high-risk surfaces, but not every test in the repository.
- The worktree contains many pre-existing unrelated edits. This report does not claim ownership or validation for every changed file outside the audited surfaces above.

## Next Audit Lanes

Use `docs/audits/2026-06-10-system-audit-action-register.md` as the current execution queue.

1. Use `docs/audits/2026-06-10-owner-governance-follow-up-packet.json` and `docs/audits/2026-06-10-owner-governance-follow-up-brief.zh.md` to route each of the 5 open blockers to its required owner/governance output before claiming closure.
2. Use `docs/audits/2026-06-10-direct-app-mcp-gitnexus-tool-surface-runbook.md` to retry direct App MCP/GitNexus discovery in a fresh session, then compare any direct App evidence against the local stdio evidence already recorded.
3. Attach page-specific local MCP evidence packets for the 7 business-owner-approval-pending pages, then repeat through direct Codex App MCP tools when a fresh session exposes them.
4. Route the 8 remaining calculation/display P1 items to business-owner rule decisions, then update `docs/calc_rules.md`, the authoritative implementation layer, and the tests that currently freeze the losing convention.
5. Use `docs/audits/2026-06-10-owner-review-brief.zh.md` for the owner meeting and record meeting outputs in `docs/audits/2026-06-10-owner-decision-capture-template.zh.md` before copying approved inputs into authoritative templates and rules.
6. Work through the fresh owner-approval action matrix: fill owner identity/decision/signature fields, complete the page-specific evidence reviews, and keep `ledger-pnl` last until the approved governance workflow writes or locates the direct page/API record and the follow-up governance validation passes.
7. Use `docs/audits/2026-06-10-ledger-pnl-direct-governance-record-runbook.md` for Ledger PnL only after governance-owner authorization; dry-run evidence remains non-certifying.
8. Use `docs/audits/2026-06-10-local-secret-hygiene-runbook.md` to rotate, remove, or owner-accept the local `config/.env` findings without copying values into the repo.
9. Re-run `pytest tests/test_system_audit_manifest_contract.py tests/test_system_audit_completion_snapshot_verifier.py tests/test_system_audit_pulse.py tests/test_system_audit_monitoring_snapshot_verifier.py -q`, `python scripts\verify_system_audit_completion_snapshot.py`, `python scripts\verify_system_audit_monitoring_snapshot.py`, and `python scripts\system_audit_pulse.py` after edits to the manifest, completion snapshot, monitoring snapshot, owner/governance follow-up packet or brief, coverage report, owner brief, capture template, action register, direct App MCP/GitNexus artifacts, Ledger PnL direct-record artifacts, local secret hygiene artifacts, route-scope, or business-display coverage.
10. Re-run the full browser smoke suite after future frontend route-scope or data-source changes; preserve `docs/audits/2026-06-10-real-backend-smoke-result.md` as the current accepted real-backend smoke evidence, not as owner approval or route certification.
11. Re-run gitleaks in a clean CI runner and resolve or owner-accept the local `config/.env` credential findings without committing secret values.
