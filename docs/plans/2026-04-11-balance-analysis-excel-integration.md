# Balance Analysis Excel Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate the missing analysis views, rules, and formulas from `资产负债分析_20260301_1.xlsx` into the governed `zqtz / tyw` balance-analysis flow.

**Architecture:** Extend the `zqtz_bond_daily_snapshot` and `tyw_interbank_daily_snapshot` ingestion path to preserve the raw fields required by the Excel workbook, materialize enriched governed formal balance facts in `backend/app/core_finance/`, then expose workbook-style read models through the existing balance-analysis API surface. Keep all financial derivation inside `backend/app/core_finance/` and let service/API layers only orchestrate read access to governed formal facts.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, DuckDB, pytest, React/TypeScript (existing first governed balance-analysis consumer only).

---

## Scope Extracted From `资产负债分析_20260301_1.xlsx`

Workbook sheets and implied system capabilities:

1. `1-总览`
   - Asset/liability overview
   - Issuance-excluded bond assets
   - Interbank asset / liability split
   - Net position
2. `2-债券业务种类`
   - Bond-type grouping
   - Floating gain/loss = fair value - amortized cost
3. `3-期限缺口分析`
   - Maturity bucket classification
   - Bucket gap and cumulative gap
   - Asset/liability weighted rates
   - Spread in bp
4. `A-发行类分析`
   - Issuance-only breakdown
   - Issuance maturity structure
   - Full-scope liabilities = interbank liabilities + issuance
5. `B-币种拆分分析`
   - Currency split
   - USD -> CNY conversion
   - USD detail list
   - FX sensitivity rule
6. `4-信用评级分析`
   - Rating grouping
7. `5-利率分布分析`
   - Rate bucket grouping across bonds / interbank assets / interbank liabilities
8. `6-行业分布`
   - Industry grouping
9. `7-对手方类型`
   - Counterparty-type grouping using TYW source fields
10. `8-Campisi归因分析`
   - Benchmark rate from policy-bank bonds
   - Coupon contribution
   - Spread contribution
   - Price return = fair value - amortized cost
11. `9-交叉分析`
   - Book-class x bond-type matrix
12. `10-计息方式`
   - Fixed / floating grouping
13. `11-明细规则说明`
   - Canonical rule source for buckets / formulas / group definitions
14. `C-每日批量分析方案`
   - Daily snapshot + delta / trend / alert follow-on design

## Current Codebase Gap Summary

Already present:

- `backend/app/tasks/balance_analysis_materialize.py` can materialize first-wave formal balance facts.
- `backend/app/api/routes/balance_analysis.py` exposes governed overview/detail endpoints.
- `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx` is the first governed consumer.

Still missing relative to workbook:

- Formal fact enrichment fields needed for workbook analyses:
  - `face_value`
  - `bond_type`
  - `industry_name`
  - `rating`
  - `coupon_rate`
  - `ytm_value`
  - `maturity_date`
  - `interest_mode`
  - `core_customer_type`
  - `funding_cost_rate`
  - `currency_code`
- Real-source classification rules:
  - `ZQTZ` asset classes include `应收投资款项` and `发行类债劵`
  - `TYW` product types are real interbank labels, not synthetic `持有至到期同业存单`
- Workbook-style read models and API contracts
- Existing page sections for the new workbook analyses

## Open Decision Requiring User Confirmation

The repo does not currently define the formal accounting mapping for:

- `ZQTZ.asset_class = 应收投资款项`
- `ZQTZ.asset_class = 发行类债劵`
- real `TYW.product_type` values such as `同业存放`, `拆放同业`, `卖出回购票据`

Recommended temporary balance-analysis assumption:

- Map `应收投资款项` to `H / AC`
- Map issuance-like `ZQTZ` rows to `H / AC` for balance-analysis fact persistence
- Map `TYW` formal balance rows to `H / AC`

Reason:

- The workbook uses these rows in balance analysis, but not in H/A/T drilldown
- This keeps the formal balance pipeline operable while preserving raw source labels for workbook read models
- The assumption is contained to the `zqtz / tyw` balance-analysis workstream and can later be replaced by governed mapping

## Task 1: Lock Real-Source Classification In Tests

**Files:**
- Modify: `tests/test_balance_analysis_core.py`
- Modify: `tests/test_balance_analysis_materialize_flow.py`
- Create: `tests/test_balance_analysis_workbook_contract.py`

**Step 1: Write the failing tests**

- Add real-source classification tests for:
  - `应收投资款项`
  - issuance-like `ZQTZ` rows
  - real `TYW.product_type` rows
- Add failing contract tests for workbook sections:
  - overview
  - bond-type summary
  - maturity-gap buckets
  - currency split
  - rating / industry / rate buckets
  - counterparty type
  - Campisi
  - cross analysis
  - interest mode

**Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_balance_analysis_core.py tests/test_balance_analysis_materialize_flow.py tests/test_balance_analysis_workbook_contract.py -q
```

Expected:

- failures showing missing real-source mapping / missing workbook contract

**Step 3: Commit**

Only after minimal green implementation for this task.

## Task 2: Enrich Snapshot And Formal Fact Contracts

**Files:**
- Modify: `backend/app/repositories/snapshot_row_parse.py`
- Modify: `backend/app/repositories/snapshot_repo.py`
- Modify: `backend/app/core_finance/balance_analysis.py`
- Modify: `backend/app/repositories/balance_analysis_repo.py`
- Modify: `docs/data_contracts.md`
- Modify: `docs/acceptance_tests.md`

**Step 1: Write the failing tests**

- Snapshot parsing should preserve the raw fields required by the workbook
- Formal fact rows should carry the fields needed by governed read models

**Step 2: Run tests to verify they fail**

Run the targeted balance-analysis tests.

**Step 3: Write minimal implementation**

- Add ZQTZ raw fields:
  - `face_value_native`
  - `bond_type`
  - `industry_name`
  - `rating`
  - `coupon_rate`
  - `ytm_value`
  - `maturity_date`
  - `interest_mode`
  - `currency_code`
- Add TYW raw fields:
  - `core_customer_type`
  - `funding_cost_rate`
  - `maturity_date`
  - `currency_code`
- Extend formal fact rows with the governed fields needed by workbook read models
- Keep formulas in `backend/app/core_finance/`

**Step 4: Run tests to verify they pass**

Run the targeted balance-analysis tests again.

**Step 5: Commit**

Use a Lore-format commit message describing the contract enrichment.

## Task 3: Implement Workbook Read Models In `core_finance`

**Files:**
- Modify: `backend/app/core_finance/balance_analysis.py`
- Create: `backend/app/core_finance/balance_analysis_workbook.py`
- Modify: `backend/app/core_finance/__init__.py`
- Modify: `tests/test_balance_analysis_workbook_contract.py`

**Step 1: Write the failing tests**

One minimal test per workbook behavior:

- maturity bucket classification
- rate bucket classification
- weighted rate calculation
- gap / cumulative gap
- bond-type floating gain/loss
- issuance-only summary
- full-scope liability summary
- currency split and USD sensitivity
- Campisi benchmark / spread / price return
- cross matrix
- interest-mode grouping

**Step 2: Run tests to verify they fail**

Run only the targeted tests added for workbook read models.

**Step 3: Write minimal implementation**

- Keep pure grouping / bucketing / formula logic in `core_finance`
- Use only governed formal fact rows as input
- Preserve raw display labels required by the workbook

**Step 4: Run tests to verify they pass**

Run the targeted workbook tests.

**Step 5: Commit**

Use a Lore-format commit message describing workbook derivation logic.

## Task 4: Expose Governed Workbook API Surface

**Files:**
- Modify: `backend/app/schemas/balance_analysis.py`
- Modify: `backend/app/repositories/balance_analysis_repo.py`
- Modify: `backend/app/services/balance_analysis_service.py`
- Modify: `backend/app/api/routes/balance_analysis.py`
- Modify: `tests/test_balance_analysis_api.py`

**Step 1: Write the failing tests**

- Add an endpoint contract for workbook analytics, likely:
  - `GET /ui/balance-analysis/workbook`
- Assert:
  - `basis=formal`
  - governed `result_meta`
  - workbook section payload shape
  - report-date-specific lineage

**Step 2: Run tests to verify they fail**

Run the API test file for the new endpoint.

**Step 3: Write minimal implementation**

- Repository reads only formal facts
- Service orchestrates payload assembly and `result_meta`
- API validates params and returns schema payload

**Step 4: Run tests to verify they pass**

Run the targeted API tests.

**Step 5: Commit**

Use a Lore-format commit message describing the governed workbook endpoint.

## Task 5: Extend The First Governed Consumer Only

**Files:**
- Modify: `frontend/src/api/contracts.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- Modify: `frontend/src/test/BalanceAnalysisPage.test.tsx`

**Step 1: Write the failing tests**

- Add one UI test per new section rendered on the existing page
- Keep scope to the existing `/balance-analysis` page only

**Step 2: Run tests to verify they fail**

Run:

```powershell
pnpm --dir F:\\MOSS-V3\\frontend test -- BalanceAnalysisPage
```

**Step 3: Write minimal implementation**

- Add workbook sections to the existing governed page
- Do not create a broad new dashboard rollout
- Keep the existing provenance panel visible

**Step 4: Run tests to verify they pass**

Run the targeted frontend tests.

**Step 5: Commit**

Use a Lore-format commit message describing the first governed consumer extension.

## Task 6: Full Verification

**Files:**
- No new files by default

**Step 1: Run backend balance-analysis tests**

```powershell
pytest tests/test_balance_analysis_core.py tests/test_balance_analysis_materialize_flow.py tests/test_balance_analysis_api.py tests/test_balance_analysis_service.py tests/test_balance_analysis_boundary_guards.py tests/test_balance_analysis_workbook_contract.py -q
```

**Step 2: Run broader backend regression**

```powershell
pytest tests -q
```

**Step 3: Run frontend checks**

```powershell
pnpm --dir F:\\MOSS-V3\\frontend test -- BalanceAnalysisPage ApiClient
pnpm --dir F:\\MOSS-V3\\frontend typecheck
```

**Step 4: Update docs if needed**

- `docs/data_contracts.md`
- `docs/acceptance_tests.md`
- optional handoff note if assumptions remain temporary

**Step 5: Commit**

Use a Lore-format closeout commit only after the verification suite is green.

## Suggested Execution Order

1. Confirm the temporary mapping assumption for `应收投资款项` / issuance-like `ZQTZ` / real `TYW` rows.
2. Finish Task 1 and Task 2 first.
3. Only then implement workbook read models and API.
4. Extend the existing page last.
