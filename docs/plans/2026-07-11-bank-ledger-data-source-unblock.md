# Bank Ledger Data Source Unblock Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Make `/bank-ledger-dashboard` consume imported `position_snapshot` only, return currency-separated totals, never fall forward in time, and remove the placeholder alert claim.

**Architecture:** Keep the existing read-only repository/service/route chain and DuckDB schema. Replace the dashboard scalar DTO with a clean `currency_breakdown` list, normalize blank currencies into an independent `UNKNOWN` bucket, and synchronize the selected currency across KPI cards, positions, URL state, and export parameters. Do not read or materialize `position_snapshot_agg`.

**Tech Stack:** FastAPI, Pydantic, DuckDB, React, TypeScript, React Query, Vitest, pytest.

---

### Task 1: Freeze backend source, currency, and date behavior with RED tests

**Files:**
- Modify: `tests/test_ledger_analytics_api.py`

**Steps:**
1. Change the imported-snapshot integration test so ZQTZ and imported data coexist; expect dates/dashboard/positions/export to use only the imported batch.
2. Replace the ZQTZ-success test with ZQTZ-only no-data assertions.
3. Add a mixed CNY/USD batch and expect:
   `data={as_of_date,currency_breakdown:[{currency,asset_face_amount,liability_face_amount,net_face_exposure}]}`.
4. Assert the payload contains no top-level amount scalars and no `alert_count`.
5. Add dates before and after a requested date; expect fallback only to the latest snapshot `<= requested_as_of_date`.
6. Add a request earlier than the first imported snapshot; expect no-data and no future fallback.
7. Add `currency=USD` positions/export assertions, including trace and export metadata.
8. Run the targeted tests and confirm they fail for the expected old source/DTO/fallback behavior.

### Task 2: Implement the minimal backend GREEN path

**Files:**
- Modify: `backend/app/repositories/ledger_analytics_repo.py`
- Modify: `backend/app/services/ledger_analytics_service.py`
- Modify: `backend/app/schemas/ledger.py`
- Modify: `backend/app/api/routes/ledger.py`

**Steps:**
1. Remove ZQTZ branches and helpers from dates/dashboard/positions.
2. Query only the latest imported `position_snapshot` batch for the resolved date.
3. Change fallback SQL to `as_of_date <= requested_as_of_date`, choosing the latest date and latest batch.
4. Group dashboard values by canonical currency: `upper(trim(currency))`, blank -> `UNKNOWN`; return stable currency order.
5. Replace `LedgerDashboardData` scalars and `alert_count` with `currency_breakdown`.
6. Add normalized currency filtering to positions and export routes, trace filters, and repository predicates.
7. Run backend RED tests and the complete Ledger analytics/import suites until green.

### Task 3: Freeze frontend currency selection with RED tests

**Files:**
- Modify: `frontend/src/test/LedgerDashboardPageModel.test.ts`
- Modify: `frontend/src/test/LedgerDashboardPage.test.tsx`
- Modify: `frontend/src/test/LedgerImportClient.test.ts`
- Modify: `frontend/src/test/RouteRegistry.test.tsx`

**Steps:**
1. Update fixtures to return CNY/USD `currency_breakdown`.
2. Expect exactly three KPI cards for the selected currency and no alert card.
3. Expect default CNY when present, otherwise the first stable currency.
4. Switch to USD and assert KPI values, positions request, URL query, and drill direction retain `currency=USD`.
5. Assert real positions/export URLs include currency.
6. Assert a successful import invalidates dates/dashboard/positions and makes the imported batch visible.
7. Run the targeted tests and confirm they fail for the missing frontend behavior.

### Task 4: Implement the minimal frontend GREEN path

**Files:**
- Modify: `frontend/src/api/ledgerClient.ts`
- Modify: `frontend/src/features/ledger-dashboard/pages/LedgerDashboardPage.tsx`
- Modify: `frontend/src/features/ledger-dashboard/pages/ledgerDashboardPageModel.ts`
- Modify: `frontend/src/features/ledger-dashboard/pages/LedgerDashboardPage.css`

**Steps:**
1. Update TypeScript DTOs and mock/real clients to the clean breakdown contract.
2. Add selected-currency URL state and a compact selector.
3. Build three cards from the selected bucket using `<CURRENCY>/1亿`; never aggregate buckets.
4. Add currency to positions query keys, requests, drill state, and export options.
5. Replace the old source-blocked copy with candidate imported-snapshot wording while keeping classification/default-asset caveats visible.
6. Run frontend tests, typecheck, ESLint, debt audit, and production build.

### Task 5: Synchronize governance evidence and verify

**Files:**
- Modify: `docs/page_contracts.md`
- Modify: `docs/live_route_maturity.md`
- Modify: `scripts/mcp/moss_project_mcp.py`
- Modify: `tests/test_governance_doc_contract.py`
- Modify: `tests/test_project_mcp_servers.py`

**Steps:**
1. Update PAGE truth from ZQTZ/source-blocked scalars to imported, currency-separated candidate evidence.
2. Keep `temporary-exception`, `formal_use_allowed=false`, no MTR, no golden, and pending owner approval.
3. Preserve the default-to-asset classification risk and `UNKNOWN` currency boundary.
4. Update MCP truth chain and tests; retain the old GAP alias.
5. Run governance/MCP tests and browser verification.
6. Dispatch spec review, fix all findings, then dispatch code-quality review and fix all findings.
7. Do not commit this new round unless the user explicitly requests it.

**Out of scope:** database schema changes, auth, queue/scheduler, shared infrastructure, formal metric promotion, FX conversion, or inventing alert rules.
