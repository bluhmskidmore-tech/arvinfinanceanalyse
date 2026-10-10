# Bank Ledger Classification Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace Bank Ledger's default-to-ASSET import rule with an explicit, fail-closed classification contract, expose per-currency classification quality without contaminating financial amounts, and block legacy-rule batches from presenting ungoverned KPI claims.

**Architecture:** A small governance module owns the versioned direction allowlist and is reused by import and analytics. New imports materialize `ASSET`, `LIABILITY`, or `UNCLASSIFIED` in `position_snapshot`; analytics aggregate only materialized directions from the resolved batch. Batches written under an older rule are marked `legacy_unassessed` and their asset/liability/net KPI values and coverage evidence fail closed instead of being recomputed at read time.

**Tech Stack:** Python 3.14, FastAPI, Pydantic, DuckDB, React, TypeScript, TanStack Query, Vitest, pytest.

---

## Contract fixed by this plan

- `LIABILITY`: only `(发行类债券, 发行类债券)` after existing alias normalization.
- `ASSET`: only the five combinations covered by existing local H/A/T evidence:
  - `(银行账户, 持有至到期类资产)`
  - `(银行账户, 可供出售类资产)`
  - `(银行账户, 交易性资产)`
  - `(交易账户, 交易性资产)`
  - `(银行账户, 应收投资款项)`; `docs/acceptance_tests.md` requires this class to map to H / AC.
- `UNCLASSIFIED`: missing/sentinel values, unknown values, one-sided issuance, conflicts, and any other unapproved combination.
- Current rule version: `rv_ledger_classification_v2`.
- No database schema change and no historical data mutation.
- No read-time reclassification of legacy rows. Legacy batches are `legacy_unassessed`, with financial KPI and classification-quality values set to null.
- For current-rule batches, each currency bucket exposes total row count, unclassified row count, unclassified native face amount `/1亿`, and row classification coverage percent. Unclassified amounts never enter asset, liability, or net.
- `UNKNOWN` currency and `UNCLASSIFIED` direction remain independent dimensions.
- The page keeps exactly three financial KPI cards and adds a separate classification-quality panel.

## Evidence and known boundary

- Read-only `data/moss.duckdb` contains 14,731 rows across six category pairs. All six are covered by the explicit five-asset/one-liability contract; no current live row changes direction under v2, while future unknown combinations fail closed.
- GitNexus and project metric/lineage/data-catalog MCP servers were unavailable in this session. Local code, tests, PAGE/MCP seed, source samples, and read-only DuckDB queries are the fallback evidence.
- `ledger_import_batch.file_hash` is uniquely indexed. The same historical file cannot be replayed under v2 without a separately authorized schema/data-remediation design.

### Task 1: Materialized fail-closed import classification

**Files:**
- Create: `backend/app/governance/ledger_classification.py`
- Modify: `backend/app/services/ledger_import_service.py`
- Test: `tests/test_ledger_import_flow.py`

1. Add failing parameterized tests for the five approved asset pairs, the approved liability pair, and missing/unknown/unapproved/conflicting pairs.
2. Run the focused tests and confirm failures are caused by the current default-to-ASSET behavior and old rule version.
3. Add the minimal shared versioned classifier and replace `_direction`/`RULE_VERSION` use in the import service.
4. Add a failing import-level trace test, then prove an unclassified row persists `direction`, `batch_id`, `row_no`, `position_key`, category fields, `raw_json`, source version, and v2 rule version.
5. Run the focused import tests green. Do not repurpose `error_count`; unclassified is quality evidence, not an import error.

### Task 2: Analytics DTO, aggregation, filter, and export

**Files:**
- Modify: `backend/app/repositories/ledger_analytics_repo.py`
- Modify: `backend/app/services/ledger_analytics_service.py`
- Modify: `backend/app/schemas/ledger.py`
- Test: `tests/test_ledger_analytics_api.py`

1. Add failing API tests for a current-rule batch containing asset, liability, and unclassified rows in one currency.
2. Assert asset/liability/net exclude unclassified amounts; coverage is classified rows / total rows; no exceptions yields zero amount and 100%; all-null exception faces yield null; unclassified-only yields null financial KPIs and zero coverage.
3. Add a failing legacy-rule test requiring `classification_status=legacy_unassessed`, expected v2 rule version, total rows retained, and KPI/coverage/exception amounts withheld as null.
4. Implement the minimal resolved-batch aggregation. Use stored/materialized direction only; do not recompute categories in the read query.
5. Add failing positions/export tests for normalized `direction=UNCLASSIFIED`, row trace, category evidence, and Excel filter metadata; extend validation and make them pass.
6. Re-run the focused analytics tests green and retain existing past-only date/currency behavior.

### Task 3: Frontend classification-quality surface

**Files:**
- Modify: `frontend/src/api/ledgerClient.ts`
- Modify: `frontend/src/features/ledger-dashboard/pages/ledgerDashboardPageModel.ts`
- Modify: `frontend/src/features/ledger-dashboard/pages/LedgerDashboardPage.tsx`
- Modify: `frontend/src/test/LedgerDashboardPageModel.test.ts`
- Modify: `frontend/src/test/LedgerDashboardPage.test.tsx`
- Modify: `frontend/src/test/LedgerImportClient.test.ts`

1. Add failing model tests for the extended DTO, percentage/count/amount formatting, null legacy state, and unchanged three-card financial model.
2. Add failing page tests for a separate first-screen classification panel, explicit legacy warning, excluded-unclassified net copy, and an unclassified drill action.
3. Extend `LedgerDirection`/URL parsing/segmented controls to include `UNCLASSIFIED`; prove back/forward and query cache keys retain it.
4. Show category columns alongside existing batch/row/position trace in the exception table. Do not add a new financial KPI card or an unrelated export UI.
5. Run focused frontend tests green.

### Task 4: Governance and trace contract

**Files:**
- Modify: `docs/page_contracts.md` (Bank Ledger section only)
- Modify: `docs/live_route_maturity.md` (Bank Ledger row only)
- Modify: `frontend/src/mocks/navigation.ts` (Bank Ledger copy only)
- Modify: `scripts/mcp/moss_project_mcp.py` (Bank Ledger trace bundle only)
- Modify: `tests/test_governance_doc_contract.py`
- Modify: `tests/test_project_mcp_servers.py`
- Modify: `frontend/src/test/RouteRegistry.test.tsx`
- Modify: `frontend/src/test/navigation.test.ts`

1. Add failing contract tests requiring v2 materialization, `UNCLASSIFIED`, legacy fail-closed behavior, per-currency coverage, row trace, and `formal_use_allowed=false`.
2. Update only the Bank Ledger governance text and trace seed.
3. Keep maturity `temporary-exception`; owner approval, dedicated golden evidence, and historical remediation remain open.
4. Run focused governance/MCP/navigation tests green.

### Task 5: Verification and review

1. Run the Bank Ledger backend import/analytics suites.
2. Run the exact Bank Ledger frontend test files; do not use a broad `Ledger` selector that includes unrelated dirty Ledger PnL work.
3. Run targeted Ruff/ESLint, frontend typecheck, `npm run debt:audit`, and build.
4. Run `git diff --check` and inspect every changed hunk against this plan.
5. Complete spec compliance review first, fix/re-review until clean, then code-quality review and final main-agent verification.
6. Do not commit this classification round unless the user explicitly asks after review.
