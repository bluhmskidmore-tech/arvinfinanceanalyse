# Balance Analysis Gap Closure Implementation Plan

> **Contract sync（2026-04-12+）：** **已支持 vs 显式未支持**的 governed workbook `section` keys 以 [`docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`](../BALANCE_ANALYSIS_SPEC_FOR_CODEX.md) **§13** 为唯一权威。本文档保留任务分解与**剩余**产品差距；Tranche A/B 中大量「新增 section」条目在仓库当前状态下 **已实现**——代理不得再将其当作未完成任务，除非另行打开新的 execution update / PRD。
>
> **`advanced_attribution_bundle`** 明确留在 governed workbook **已支持边界外**（见 spec §13 与 `2026-04-12-balance-analysis-advanced-attribution-boundary.md`）。

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the highest-value gaps between the governed `zqtz / tyw` balance-analysis implementation and the target workbook/report requirements without violating the repo's current architecture or execution boundary.

**Architecture:** Keep all formal derivation inside `backend/app/core_finance/`, materialize only through `backend/app/tasks/`, and expose read models only through the existing governed balance-analysis, risk-tensor, and bond-analytics service/API surfaces. Treat the 28-sheet workbook as a product requirement source, not as a license to create a parallel batch-only implementation.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, DuckDB, pytest, React, TypeScript, openpyxl.

---

## Boundary First

Historical plan note:

- This file is a dated planning artifact, not the current repo-level boundary source.
- Current repo-level state lookup now enters through `AGENTS.md` -> `docs/DOCUMENT_AUTHORITY.md` -> `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`.
- The boundary wording below should be read as historical planning context unless it matches the current authority chain.

This repo is not authorized for a repo-wide Phase 2 rollout.

Current directly executable lane:

- `zqtz / tyw` formal balance compute
- governed `balance-analysis` repository / service / API / first workbench consumer
- tests and docs for that same lane

Not directly executable in the current override unless separately authorized:

- broad frontend rollout beyond the first balance-analysis consumer
- unrelated formal-finance expansions
- full Phase 3 attribution semantics
- a parallel `alm-analysis/` batch tool outside the repo's governed stack

So this plan is split into:

1. **Tranche A: executable now**
2. **Tranche B: next authorized balance-analysis window**
3. **Tranche C: Phase 3+ advanced attribution**

## Requirement Translation

The workbook/DDD requirements map to repo-native surfaces as follows:

- `balance-analysis`
  - overview
  - workbook-style governed tables
  - decision / event / risk rails
- `risk-tensor`
  - DV01 / KRD / convexity / concentration / liquidity gap
- `bond-analytics`
  - return decomposition
  - credit spread migration
  - action attribution
  - benchmark excess

Any sheet that cannot be expressed via those three governed surfaces should be treated as a new governed read model, not as a standalone script feature.

## Gap Summary

**Baseline（与 spec §13 对齐，已实现）：**

- H/A/T -> AC / FVOCI / FVTPL mapping
- issuance exclusion for asset scope
- FX projection into formal balance facts
- governed workbook sections（keys 见 spec §13），包括但不限于：`bond_business_types`、`maturity_gap`、`issuance_business_types`、`cashflow_calendar`、`currency_split`、`rating_analysis`、`rate_distribution`、`industry_distribution`、`counterparty_types`、`campisi_breakdown`、`cross_analysis`、`interest_modes`、`issuer_concentration`、`liquidity_layers`、`regulatory_limits`、`overdue_credit_quality`（及 ratings子表）、`vintage_analysis`、`customer_attribute_analysis`、`portfolio_comparison`、`account_category_comparison`、`ifrs9_classification` / `ifrs9_position_scope` / `ifrs9_source_family`、`rule_reference`
- separate `risk-tensor` and `bond-analytics` APIs（**不**自动等价于 workbook 已支持 `advanced_attribution_bundle`）

**Remaining gaps / non-goals（示例，非穷举）：**

- 参考 Excel 全簿 **1:1 行级/公式级** 对齐（当前文档明确「不等于全簿对齐完成」）
- 产品类别 PnL 只读模型中「真·YTD 多月合并」等（见 `BALANCE_ANALYSIS_SPEC_FOR_CODEX.md` §4；与 balance-analysis workbook 不同面）
- **Phase 3 级** carry / roll-down / reinvestment / 交易粒度归因（属 `bond-analytics` 与边界文档，**不得**并入 governed workbook 已支持列表）
- `advanced_attribution_bundle` 作为 workbook section 的「完成态」交付（**未纳入** spec §13 已支持）
- 更完整的监管引擎、ECL、IFRS9 三阶段推断等（超出当前 governed读模型边界；Prompt 7「深化」为可选增量而非「未实现」）

## Tranche A: Executable Now

Objective:

- finish the governed `balance-analysis` lane using only the current `zqtz / tyw` formal-balance authorization
- avoid unrelated Phase 3 math

Target deliverables:

- workbook parity improvements for sheets already on the `balance-analysis` path
- stronger docs/tests for sheet coverage and known gaps
- no new unrelated read model families

### Task 1: Lock the sheet-coverage baseline in docs and tests

**Files:**
- Modify: `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`
- Modify: `docs/BALANCE_ANALYSIS_RECONCILIATION_2026-03-01.md`
- Modify: `tests/test_balance_analysis_workbook_contract.py`

**Step 1: Write the failing test**

Add a contract test that asserts the governed workbook currently exposes exactly the supported sections and does not silently imply unsupported ones.

```python
def test_governed_workbook_declares_supported_sections_only():
    payload = load_workbook_payload(...)
    keys = {table["key"] for table in payload["result"]["tables"]}
    assert "bond_business_types" in keys
    assert "maturity_gap" in keys
    assert "currency_split" in keys
    assert "cashflow_calendar" not in keys
```

**Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_balance_analysis_workbook_contract.py::test_governed_workbook_declares_supported_sections_only -q
```

Expected: FAIL because the assertion does not exist yet.

**Step 3: Write minimal implementation**

- Add the new test
- Update docs to explicitly separate:
  - supported workbook sections
  - unsupported workbook sections
  - related-but-separate capability in `risk-tensor` / `bond-analytics`

**Step 4: Run test to verify it passes**

Run the targeted test again.

**Step 5: Commit**

```bash
git add docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md docs/BALANCE_ANALYSIS_RECONCILIATION_2026-03-01.md tests/test_balance_analysis_workbook_contract.py
git commit -m "<Lore-format message>"
```

### Task 2: Add full-scope liability gap into the governed workbook

**Files:**
- Modify: `backend/app/core_finance/balance_analysis_workbook.py`
- Modify: `backend/app/schemas/balance_analysis.py`
- Modify: `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- Modify: `tests/test_balance_analysis_workbook_contract.py`
- Modify: `tests/test_balance_analysis_excel_export.py`

**Step 1: Write the failing test**

Add a workbook contract test for issuance-inclusive liability columns.

```python
def test_maturity_gap_includes_full_scope_liabilities():
    table = load_gap_table(...)
    first_row = table["rows"][0]
    assert "issuance_amount" in first_row
    assert "full_scope_liability_amount" in first_row
```

**Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_balance_analysis_workbook_contract.py::test_maturity_gap_includes_full_scope_liabilities -q
```

Expected: FAIL because those fields are missing.

**Step 3: Write minimal implementation**

- Extend `_build_maturity_gap_table` to calculate:
  - `issuance_amount`
  - `full_scope_liability_amount`
  - `full_scope_gap_amount`
- Keep formulas inside `core_finance`
- Expose the new columns through schema and UI table rendering

Representative implementation shape:

```python
issuance_bucket = [
    row for row in issuance_rows
    if _match_bucket(_remaining_years(report_date, row.maturity_date), lower, upper)
]
issuance_amount = _sum_decimal(issuance_bucket, lambda row: row.face_value_amount)
full_scope_liability_amount = interbank_liability_amount + issuance_amount
full_scope_gap_amount = asset_total - full_scope_liability_amount
```

**Step 4: Run tests to verify they pass**

Run:

```powershell
pytest tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_excel_export.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/core_finance/balance_analysis_workbook.py backend/app/schemas/balance_analysis.py frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_excel_export.py
git commit -m "<Lore-format message>"
```

### Task 3: Add a governed cashflow ladder section

**Files:**
- Modify: `backend/app/core_finance/balance_analysis_workbook.py`
- Modify: `backend/app/schemas/balance_analysis.py`
- Modify: `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- Modify: `tests/test_balance_analysis_workbook_contract.py`

**Step 1: Write the failing test**

```python
def test_workbook_exposes_cashflow_calendar_section():
    payload = load_workbook_payload(...)
    keys = {table["key"] for table in payload["result"]["tables"]}
    assert "cashflow_calendar" in keys
```

**Step 2: Run test to verify it fails**

Run the single new test and confirm failure.

**Step 3: Write minimal implementation**

- Add `_build_cashflow_calendar_table`
- Bucket maturities by calendar month
- Compute:
  - bond maturities
  - interbank asset maturities
  - interbank liability maturities
  - issuance maturities
  - net cashflow
  - cumulative net cashflow
- Limit first implementation to 12 forward months

Representative row shape:

```python
{
    "month": "2026-03",
    "bond_maturity_amount": ...,
    "interbank_asset_maturity_amount": ...,
    "interbank_liability_maturity_amount": ...,
    "issuance_maturity_amount": ...,
    "net_cashflow_amount": ...,
    "cumulative_net_cashflow_amount": ...,
}
```

**Step 4: Run tests to verify they pass**

Run the workbook contract tests.

**Step 5: Commit**

```bash
git add backend/app/core_finance/balance_analysis_workbook.py backend/app/schemas/balance_analysis.py frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx tests/test_balance_analysis_workbook_contract.py
git commit -m "<Lore-format message>"
```

### Task 4: Add a governed concentration section to `balance-analysis`

**Files:**
- Modify: `backend/app/core_finance/balance_analysis_workbook.py`
- Modify: `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- Modify: `tests/test_balance_analysis_workbook_contract.py`

**Step 1: Write the failing test**

```python
def test_workbook_exposes_issuer_concentration_top_rows():
    table = load_table("issuer_concentration", ...)
    assert table["rows"]
    assert "issuer_name" in table["rows"][0]
    assert "balance_amount" in table["rows"][0]
```

**Step 2: Run test to verify it fails**

Run the new targeted test.

**Step 3: Write minimal implementation**

- Add issuer concentration Top-N from `FormalZqtzBalanceFactRow`
- Use `issuer_name`
- Compute:
  - count
  - balance
  - share_of_bond_assets
  - share_of_total_assets
- Keep first wave to issuer only; group concentration can wait for a richer governed field

**Step 4: Run tests to verify they pass**

Run workbook contract tests.

**Step 5: Commit**

```bash
git add backend/app/core_finance/balance_analysis_workbook.py frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx tests/test_balance_analysis_workbook_contract.py
git commit -m "<Lore-format message>"
```

### Task 5: Add a rule-reference section instead of freehand Excel formulas

**Files:**
- Modify: `backend/app/core_finance/balance_analysis_workbook.py`
- Modify: `docs/calc_rules.md`
- Modify: `docs/data_contracts.md`
- Modify: `tests/test_balance_analysis_docs_contract.py`

**Step 1: Write the failing test**

Add a docs contract test asserting the workbook rule section points to repo-native rule ids / docs rather than becoming a second source of truth.

```python
def test_balance_rule_sheet_references_repo_native_rule_sources():
    section = load_rule_reference_section(...)
    assert any(row["rule_id"] == "bal_scope_issuance_exclusion" for row in section["rows"])
```

**Step 2: Run test to verify it fails**

Run the new targeted docs contract test.

**Step 3: Write minimal implementation**

- Add a `rule_reference` workbook section
- Each row should contain:
  - `rule_id`
  - `rule_name`
  - `summary`
  - `source_doc`
  - `source_section`
- Do not copy full formulas out of docs into UI text

**Step 4: Run tests to verify they pass**

Run docs contract tests and workbook tests.

**Step 5: Commit**

```bash
git add backend/app/core_finance/balance_analysis_workbook.py docs/calc_rules.md docs/data_contracts.md tests/test_balance_analysis_docs_contract.py
git commit -m "<Lore-format message>"
```

## Tranche B: Next Authorized Balance-Analysis Window

Objective:

- extend governed read models that are still balance-analysis scoped but not clearly allowed in the current narrow override

**Contract sync note:** 下列多数 deliverable 的 **MVP / 第一版** 已在 spec §13 标为已支持。本 Tranche 在「下一授权窗口」语境下主要指：**深化**（额外维度、监管完备性、与 Excel 更细对齐），而非「从零新增 listed section」。

Target deliverables（历史列表 —请用 spec §13 核对落地状态）：

- `IFRS9` 相关 section（`ifrs9_*`）— **基底已落地**；ECL 等仍属边界外
- account-category comparison — **已落地**
- customer-attribute analysis — **已落地**
- vintage analysis — **已落地**
- overdue / credit quality view — **已落地**
- portfolio comparison — **已落地**
- liquidity-layer / HQLA view — **已落地**
- regulatory-limit view — **已落地**

### Task 6: Add IFRS9 and account-category governed read models

**Files:**
- Modify: `backend/app/core_finance/balance_analysis_workbook.py`
- Modify: `backend/app/schemas/balance_analysis.py`
- Modify: `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- Modify: `tests/test_balance_analysis_workbook_contract.py`

**Step 1: Write the failing test**

Add tests for:

- `ifrs9_classification`
- `account_category_comparison`

**Step 2: Run tests to verify they fail**

Run the targeted workbook contract tests.

**Step 3: Write minimal implementation**

- Group ZQTZ rows by:
  - `invest_type_std`
  - `accounting_basis`
  - `asset_class`
- Group again by:
  - `account_category`
  - `portfolio_name`

**Step 4: Run tests to verify they pass**

Run workbook contract tests.

**Step 5: Commit**

```bash
git add backend/app/core_finance/balance_analysis_workbook.py backend/app/schemas/balance_analysis.py frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx tests/test_balance_analysis_workbook_contract.py
git commit -m "<Lore-format message>"
```

### Task 7: Add overdue / credit-quality, customer-attribute, and vintage views

**Files:**
- Modify: `backend/app/core_finance/balance_analysis_workbook.py`
- Modify: `backend/app/repositories/balance_analysis_repo.py`
- Modify: `tests/test_balance_analysis_workbook_contract.py`

**Step 1: Write the failing test**

Add tests for:

- overdue rows by `overdue_days`
- customer-attribute aggregation
- start-year / vintage grouping

**Step 2: Run tests to verify they fail**

Run the targeted workbook contract tests.

**Step 3: Write minimal implementation**

- Use already-preserved fields where available:
  - `rating`
  - `customer_type`
  - `maturity_date`
  - `start_date` or upstream equivalent once formally preserved
- If upstream formal facts do not yet retain the needed field, extend contract first and document it

**Step 4: Run tests to verify they pass**

Run workbook contract tests and repository tests.

**Step 5: Commit**

```bash
git add backend/app/core_finance/balance_analysis_workbook.py backend/app/repositories/balance_analysis_repo.py tests/test_balance_analysis_workbook_contract.py
git commit -m "<Lore-format message>"
```

### Task 8: Add liquidity-layer and regulatory-limit governed views

**Files:**
- Modify: `backend/app/core_finance/balance_analysis_workbook.py`
- Modify: `backend/app/core_finance/alert_engine.py`
- Modify: `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- Modify: `tests/test_balance_analysis_workbook_contract.py`

**Step 1: Write the failing test**

Add tests for:

- `liquidity_layers`
- `regulatory_limits`

**Step 2: Run tests to verify they fail**

Run the targeted workbook contract tests.

**Step 3: Write minimal implementation**

- Introduce governed liquidity-layer classification in `core_finance`
- Compute HQLA-style amount with explicit haircut assumptions
- Introduce a limit table that shows:
  - metric
  - current value
  - threshold
  - breach status
- Reuse `alert_engine` threshold semantics where possible

**Step 4: Run tests to verify they pass**

Run workbook tests plus alert-engine tests.

**Step 5: Commit**

```bash
git add backend/app/core_finance/balance_analysis_workbook.py backend/app/core_finance/alert_engine.py frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx tests/test_balance_analysis_workbook_contract.py
git commit -m "<Lore-format message>"
```

## Tranche C: Phase 3+ Advanced Attribution

Objective:

- finish the sheets that require richer market/curve/trade semantics and should not be faked early

Target deliverables:

- configuration vs selection attribution
- real carry / roll-down
- reinvestment analysis
- richer bond-analytics integration

### Task 9: Replace placeholder attribution semantics in `bond-analytics`

**Files:**
- Modify: `backend/app/services/bond_analytics_service.py`
- Modify: `backend/app/core_finance/bond_analytics/read_models.py`
- Modify: `tests/test_bond_analytics_service.py`
- Modify: `tests/test_bond_analytics_core.py`

**Step 1: Write the failing test**

Add tests asserting non-zero `roll_down` / `rate_effect` / `spread_effect` when the required fixture data is present.

**Step 2: Run tests to verify they fail**

Run:

```powershell
pytest tests/test_bond_analytics_service.py tests/test_bond_analytics_core.py -q
```

Expected: FAIL because current implementation zeros those fields.

**Step 3: Write minimal implementation**

- Remove placeholder-only zero filling once upstream facts support it
- Keep service thin; derive math in `core_finance`

**Step 4: Run tests to verify they pass**

Run the targeted bond-analytics tests.

**Step 5: Commit**

```bash
git add backend/app/services/bond_analytics_service.py backend/app/core_finance/bond_analytics/read_models.py tests/test_bond_analytics_service.py tests/test_bond_analytics_core.py
git commit -m "<Lore-format message>"
```

### Task 10: Add carry / roll-down / reinvestment workbook consumers

**Files:**
- Modify: `backend/app/core_finance/balance_analysis_workbook.py`
- Modify: `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- Modify: `tests/test_balance_analysis_workbook_contract.py`

**Step 1: Write the failing test**

Add tests for:

- `carry_roll_down`
- `reinvestment_analysis`

**Step 2: Run tests to verify they fail**

Run workbook contract tests.

**Step 3: Write minimal implementation**

- Consume already-governed bond-analytics outputs rather than recomputing in UI
- If a balance-analysis workbook row depends on bond-analytics semantics, reference the governed service result, not raw snapshot rows

**Step 4: Run tests to verify they pass**

Run workbook tests and any integration tests that touch the handoff.

**Step 5: Commit**

```bash
git add backend/app/core_finance/balance_analysis_workbook.py frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx tests/test_balance_analysis_workbook_contract.py
git commit -m "<Lore-format message>"
```

## Verification Checklist

For every task:

1. Run the targeted failing test first
2. Implement the smallest possible change
3. Re-run the targeted test
4. Re-run the relevant lane regression set
5. Re-read the output before claiming success

Recommended lane-level verification commands:

```powershell
pytest tests/test_balance_analysis_core.py tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_service.py tests/test_balance_analysis_api.py -q
pytest tests/test_balance_analysis_excel_export.py -q
pytest tests/test_risk_tensor_core.py tests/test_risk_tensor_service.py -q
pytest tests/test_bond_analytics_core.py tests/test_bond_analytics_service.py -q
pnpm --dir F:\MOSS-V3\frontend test -- BalanceAnalysisPage
pnpm --dir F:\MOSS-V3\frontend typecheck
```

## Acceptance Criteria

Tranche A is complete when:

- the governed workbook explicitly declares what it supports（**以 spec §13 +契约为准；上述 Task 1–5 多数已满足**）
- full-scope liability gap is present
- cashflow ladder is present
- issuer concentration is present
- rule-reference section is present
- tests and docs reflect the true implemented boundary

Tranche B is complete when:

- the missing balance-analysis read models exist without breaking the governed formal path（**contract sync：listed section 基底多已存在；本 Tranche 验收转向「深化与全簿差距」**）
- no UI layer computes formal finance logic

Tranche C is complete when:

- attribution sheets no longer rely on placeholder zero semantics
- carry / roll-down / reinvestment consumers read governed analytics outputs

## Non-Goals

- creating a parallel `alm-analysis/` codebase inside this repo
- pushing finance math into frontend code
- using preview tables as outward formal results
- pretending Phase 3 attribution is finished when service warnings still say otherwise
