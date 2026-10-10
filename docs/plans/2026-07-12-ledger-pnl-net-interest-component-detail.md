# Ledger PnL Net-Interest Component Detail Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Let users open any available net-interest bridge component and reconcile its movement to exact 11-digit main-ledger accounts and workbook evidence without depending on the microloan sheet or recomputing finance amounts in the browser.

**Architecture:** Keep the existing period-comparison v2 response unchanged. Add one lazy, read-only candidate component-detail endpoint bound to `report_month`, one of the fixed four component metric IDs, and the visible parent idempotency key. The backend reuses the governed three-month main-ledger parser, expands the frozen rule terms to deduplicated 11-digit CNX rows, computes all Decimal values and foot checks, and fails closed when period account sets drift. The frontend adds a local drawer/query/model under the existing period-comparison component and only validates/format returned strings.

**Tech Stack:** FastAPI, Pydantic v2, Python `Decimal`, existing finance-metric XLSX parser, React, TanStack Query, TypeScript, Vitest, Testing Library.

---

## Contract invariants

- Fixed component IDs and bridge weights remain:
  - `income.interest.loan.total` (`+1`)
  - `expense.interest.deposit.total` (`-1`)
  - `income.interest.investment` (`+1`)
  - `income.interest.interbank_net` (`+1`)
- Account evidence comes only from the three exact `总账对账YYYYMM.xlsx` files, sheet `综本`, currency `CNX`, consumed field `期末余额`.
- Rule expansion comes from `qdb-finance-2026-v1.0.1`; it is not duplicated as a new frontend or narrative rule.
- `50206` remains assigned to the loan component. In the interbank component it matches both `502(-1)` and `50206(+1)`, has effective component weight `0`, and is returned as an excluded offset row rather than counted twice.
- The three periods must have identical matched 11-digit account sets. Any added, removed, duplicated, or missing account makes the detail `not_evaluable`; no missing row is converted to zero.
- Available detail requires exact unrounded Decimal tie-outs for current month, previous month, component delta, and contribution to the parent component values. A non-zero foot is not a valid explanation.
- Raw source amounts serialize as yuan Decimal strings; calculated values serialize as 亿元 Decimal strings. The frontend does not subtract, multiply, sum, rank, or recalculate a foot.
- `formal_use_allowed=false`, `certification_effect=none`, and `driver_status=unclear` remain invariant. This is accounting contribution evidence, not rate/volume/causal attribution.
- The detail calculation and its availability/foot never consume the daily or microloan workbook and never fall back to another month. Parent-idempotency validation may reuse the existing outer period-comparison full-scope probe; a daily/microloan gap may remain visible in the parent evidence but must not make an otherwise valid main-ledger component detail unavailable.

## Task 1: Backend component-detail contract and calculation

**Files:**

- Create: `backend/app/core_finance/finance_metric_component_detail.py`
- Create: `backend/app/schemas/candidate_financial_indicator_component_detail.py`
- Modify: `backend/app/services/candidate_financial_indicator_period_comparison_service.py`
- Modify: `backend/app/api/routes/ledger_pnl.py`
- Create: `tests/test_finance_metric_component_detail.py`
- Create: `tests/test_candidate_financial_indicator_component_detail_schema.py`
- Create: `tests/test_candidate_financial_indicator_component_detail_service.py`
- Modify: `tests/test_candidate_financial_indicator_period_comparison_route.py`

### Step 1: Write failing core tests

Cover:

- all four real 202604/202605/202606 component totals and row counts `21/14/18/19` effective rows;
- investment top account `51402010003` contribution `-1.3160266974` 亿元;
- source evidence includes file hash, `综本`, changing row number, account-code cell, and ending-balance cell;
- `50206000001` has effective weight zero in interbank, is marked excluded, and does not enter the foot;
- mismatched three-period account sets return `not_evaluable` without synthetic zeros;
- exact Decimal foot and deterministic absolute-contribution ordering.

Run:

```powershell
python -m pytest tests/test_finance_metric_component_detail.py -q
```

Expected: RED because the core module and builder do not exist.

### Step 2: Implement the minimal pure core builder

The builder accepts the selected fixed component definition, its governed direct rule, the three parsed `FinanceMetricLedgerOnlySourceData` objects, and the parent component summary. It must:

- derive term matches by rule `level/code/weight`;
- deduplicate by `account_code + CNX` within each period;
- sum overlapping term weights for the effective component weight;
- require stable account identity sets across all three periods;
- apply the existing January/February/natural-month rules;
- return full source locators and backend-computed account contribution rows;
- compare account totals to the exact parent component strings.

### Step 3: Write failing schema/service/route tests

Cover strict extra-field rejection, fixed metric IDs, source-period ordering, parent idempotency binding, available/not-evaluable/stale-parent state invariants, row/source evidence consistency, exact foot, unlocked-source degradation, locked mismatch rejection, invalid inputs, and route response model.

Run:

```powershell
python -m pytest tests/test_candidate_financial_indicator_component_detail_schema.py tests/test_candidate_financial_indicator_component_detail_service.py tests/test_candidate_financial_indicator_period_comparison_route.py -q
```

Expected: RED because the DTO, service function, and route do not exist.

### Step 4: Implement schema, service, and route

Add:

```text
GET /api/ledger-pnl/candidate-financial-indicators/period-comparison/component-detail
  ?report_month=YYYYMM
  &metric_id=<fixed component id>
  &parent_idempotency_key=<64 hex>
```

The service must first rebuild/validate the visible parent comparison, then load the three source snapshots used for detail and require their hashes to match the parent source evidence. Parent mismatch returns the explicit stale-parent state with no account explanation. Build a detail idempotency key from the parent key, rule/hash, source hashes, rule terms, source locators, account values, ordering, and foot.

### Step 5: Verify backend GREEN

Run all four focused backend files plus the existing period-comparison core/schema/service/route tests. Run scoped Ruff on changed Python files.

## Task 2: Frontend contract, client, and strict model

**Files:**

- Modify: `frontend/src/api/contracts.ts`
- Modify: `frontend/src/api/pnlCoreClient.ts`
- Modify: `frontend/src/mocks/ledgerPnlMocks.ts`
- Create: `frontend/src/features/ledger-pnl/models/candidateNetInterestComponentDetailModel.ts`
- Create: `frontend/src/test/LedgerPnlCandidateNetInterestComponentDetailModel.test.ts`
- Create: `frontend/src/test/PnlCoreClientComponentDetail.test.ts`

### Step 1: Write failing client/model tests

Cover exact query parameters and `AbortSignal`, strict contract/version/month/metric/parent-key validation, fixed rule terms and source periods, available/stale/not-evaluable states, Decimal lexical validation, source-locator preservation, and formatting without arithmetic recomputation.

Run:

```powershell
npm test -- --run src/test/LedgerPnlCandidateNetInterestComponentDetailModel.test.ts src/test/PnlCoreClientComponentDetail.test.ts
```

Expected: RED because the client method and model do not exist.

### Step 2: Implement minimal types/client/model/mock

- Keep `frontend/src/api/client.ts` unchanged.
- Add the method only to `pnlCoreClient.ts` and its composed interface.
- Query key inputs remain report month, client mode, parent idempotency key, and component metric ID.
- Model validation may compare exact backend strings for identity but must not sum or calculate amounts.

### Step 3: Verify frontend model/client GREEN

Run the two focused tests and TypeScript typecheck.

## Task 3: Accessible component-detail drawer and bridge interaction

**Files:**

- Create: `frontend/src/features/ledger-pnl/components/LedgerPnlNetInterestComponentDetailDrawer.tsx`
- Create: `frontend/src/features/ledger-pnl/components/LedgerPnlNetInterestComponentDetailDrawer.css`
- Modify: `frontend/src/features/ledger-pnl/components/LedgerPnlCandidatePeriodComparison.tsx`
- Modify: `frontend/src/features/ledger-pnl/components/LedgerPnlCandidatePeriodComparison.css`
- Create: `frontend/src/test/LedgerPnlNetInterestComponentDetailDrawer.test.tsx`
- Modify: `frontend/src/test/LedgerPnlCandidatePeriodComparison.test.tsx`

### Step 1: Write failing interaction tests

Cover:

- only `available + foot passed` rows expose real buttons;
- button accessible name, dialog semantics, Escape close, and trigger-focus restoration;
- opening binds report month, metric ID, parent key, and cancels stale requests;
- switching components never flashes the prior component;
- loading, error/retry, stale-parent, not-evaluable, unlocked/degraded, and failed-detail-foot states;
- available drawer shows backend summary, governed rule terms, source-backed account rows, evidence locators, and non-causal disclaimer;
- no frontend arithmetic helper or computed totals.

Run the two focused component tests and confirm RED.

### Step 2: Implement the drawer and bridge button

- Reuse the existing Ant Design controlled drawer behavior and page-local visual language; do not nest the existing exact-account drawer.
- Keep the component name button inside the existing row header; do not make `<tr>` clickable or add a new table column.
- Use `min(720px, 100vw)` and local horizontal scrolling for evidence tables.
- Preserve the existing first-screen section ordering.

### Step 3: Verify frontend GREEN

Run all Ledger PnL period-comparison/detail model/client/component tests, scoped ESLint, typecheck, `npm run debt:audit`, and production build.

## Task 4: Contract documentation, independent review, and browser verification

**Files:**

- Modify only the PAGE-LEDGER-PNL F.2 section in `docs/page_contracts.md`.

### Step 1: Update the page contract

Document endpoint identity, fixed component/account expansion, three-period stable-set fail-close rule, 50206 allocation, units, source locators, parent/detail idempotency, no fallback, and non-causal/formal boundaries.

### Step 2: Independent reviews

- Spec review: compare implementation line-by-line to this plan.
- Code-quality review: check finance math, Pydantic invariants, response size, React query isolation, accessibility, CSS specificity, and test quality.
- Fix every Critical/Important issue and re-review.

### Step 3: End-to-end verification

At `http://localhost:5888/ledger-pnl?report_date=2026-06-30` verify:

- all four buttons open the correct real API detail;
- investment detail leads with `51402010003` and `-1.3160266974` 亿元;
- source locator is visible and 50206 exclusion is explicit in interbank;
- unlocked historical source is visible;
- outer/detail foots pass;
- no console warnings/errors;
- 1440x900 and 390x844 have no page-level horizontal overflow;
- keyboard open/Escape close/focus return work.

### Step 4: Pre-commit gates

- Run `git diff --check` on target files.
- Run `npx gitnexus detect-changes --scope staged --repo F:\MOSS-V3` after exact staging.
- Commit only target hunks; preserve unrelated dirty worktree changes.

## Definition of done

- A user can move from the net-interest bridge to exact 11-digit source-backed accounts and workbook cells.
- Every displayed official amount is backend-produced and exactly tied to the visible parent component.
- Missing/drifted source facts fail closed and never become zero.
- 50206 is neither duplicated nor silently hidden.
- Microloan remains deferred and does not block the main-ledger detail.
- Focused tests, typecheck/lint/debt/build, GitNexus staged impact, and browser checks pass.
