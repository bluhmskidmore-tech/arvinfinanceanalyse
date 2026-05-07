# Cursor Prompt - Balance Analysis P1 Formal Recompute Closure

You are working in `F:\MOSS-V3`.

Goal: close the next P1 item from `docs/plans/2026-04-24-frontend-formal-recompute-audit.md` for `PAGE-BALANCE-001` / balance analysis. The objective is not a redesign. The objective is to move risky frontend number parsing, unit conversion, and chart magnitude logic for formal balance-analysis metrics into a tested local page model/helper boundary, then wire the existing page/components to that boundary.

Current checkpoint before this task:

- `09f6677 Keep product-category PnL display inside governed page model`
- Prior baseline mentioned in the handoff: `4fef3cf Keep boundary governance aligned for fast feature rollout`

## Non-Negotiable Scope

Do not touch:

- backend code
- database schema
- auth / permissions
- queue / scheduler / cache
- global SDK wrappers
- app-wide state architecture
- unrelated frontend pages
- product-category PnL files

Do not stage unrelated dirty files. This repository has many pre-existing dirty files. Only stage files you intentionally changed for this balance-analysis slice.

Do not replace all frontend number formatting globally. Keep changes local to balance analysis unless a helper already exists and is clearly intended for this exact use.

Do not promote analytical, mock, or preview surfaces into formal truth. `AdbAnalyticalPreview` and advanced attribution remain supporting analytical surfaces.

## Read First

Read these before editing:

- `AGENTS.md`
- `docs/NEW_WINDOW_PROMPT_2026-04-24_BOUNDARY_GOVERNANCE_CONTINUE.md`
- `docs/plans/2026-04-24-frontend-formal-recompute-audit.md`
- `docs/page_contracts.md` section for `PAGE-BALANCE-001`
- `docs/golden_sample_catalog.md`
- `tests/golden_samples/GS-BAL-OVERVIEW-A/assertions.md`
- `tests/golden_samples/GS-BAL-WORKBOOK-A/assertions.md`
- `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- `frontend/src/features/balance-analysis/components/BalanceAnalysisCardsSection.tsx`
- `frontend/src/features/balance-analysis/components/BalanceAnalysisTableSection.tsx`
- `frontend/src/features/balance-analysis/hooks/useBalanceAnalysisData.ts`
- `frontend/src/test/BalanceAnalysisPage.test.tsx`

## Problem To Fix

The audit found these risky frontend formal recompute points:

- `BalanceAnalysisPage.tsx`
  - `parseWorkbookNumber`
  - `formatOverviewNumber`
  - `formatAmountToYiFromYuan`
  - `formatAmountToYiFromWan`
  - workbook chart width calculations around distribution, rating, and maturity gap panels
- `BalanceAnalysisCardsSection.tsx`
  - duplicate `formatOverviewNumber`
- `BalanceAnalysisTableSection.tsx`
  - duplicate `thousandsValueFormatter`

Main risk: invalid formal data can be silently coerced to `0`, especially for workbook chart widths. That makes malformed data visually look like legitimate zero. Unit conversions also live inside render components, which makes yuan / wan / yi behavior easy to drift.

## Suggested Parallel Subtasks For Cursor Subagents

Please spawn subagents for independent slices, then integrate yourself. Keep each subagent scoped.

### Agent A - Repo Mapping / Contract Evidence

Read-only.

Deliver:

- exact list of balance-analysis files/functions that parse or format numeric business values
- exact tests that already cover balance-analysis rendering
- the expected `GS-BAL-OVERVIEW-A` and `GS-BAL-WORKBOOK-A` behaviors relevant to null / invalid / zero / unit display
- any ambiguity where page contract and current UI behavior disagree

Do not edit files.

### Agent B - Page Model / Helper Tests

Owned write scope:

- `frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.ts`
- `frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.test.ts`

Implement the smallest local helper/model layer needed to lock current behavior without global refactor.

Minimum helpers to consider:

- display formatter for overview/formal numeric strings
- display formatter for workbook cell values
- yuan-to-yi display conversion
- wan-to-yi display conversion
- grid/thousands formatter core used by AG Grid wrappers
- chart magnitude parser that returns a typed result instead of collapsing invalid values to `0`
- chart width helper that distinguishes invalid/missing from true zero

Required test cases:

- `null`, `undefined`, and empty string display as dash
- valid `"0"` stays a legitimate zero, not missing
- invalid string remains visible as the original string for display
- invalid chart magnitude does not become a legitimate `0` bar
- comma-containing numeric strings format correctly
- yuan-to-yi and wan-to-yi conversions preserve current visible precision
- negative gap amounts preserve sign for text while chart width uses absolute magnitude

Do not edit page/component files in Agent B.

### Agent C - Page / Component Integration

Owned write scope:

- `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- `frontend/src/features/balance-analysis/components/BalanceAnalysisCardsSection.tsx`
- `frontend/src/features/balance-analysis/components/BalanceAnalysisTableSection.tsx`

Use Agent B's helper/model exports to remove duplicated local parsing/formatting from render components.

Rules:

- Do not change page layout.
- Do not rename public test ids.
- Do not change query keys or API calls.
- Do not change formal/analytical surface boundaries.
- Do not add new dependencies.
- Preserve current visible behavior except for the intentional fix: invalid workbook chart magnitudes must not be represented as legitimate zero bars.

### Agent D - Test Coverage / Acceptance

Owned write scope:

- Prefer `frontend/src/test/BalanceAnalysisPage.test.tsx`
- Only add a new test file if the existing page test is too broad or awkward.

Add the smallest integration test needed to prove the page/component actually uses the helper behavior. Good candidates:

- overview card shows invalid value text instead of silently zeroing it
- workbook chart row with invalid magnitude shows the raw value and does not render a regular zero-width/zero-like bar
- maturity gap negative amount keeps negative text while bar sizing remains based on absolute magnitude

Do not rely on fragile CSS snapshots. Prefer visible text and stable test ids.

## Integration Requirements

After subagents return:

1. Review their patches before accepting.
2. Integrate into one minimal diff.
3. Remove any unused local helper functions/imports created by the migration.
4. Ensure every changed line traces to this task.
5. Do not sweep unrelated mojibake/text issues unless the changed line requires it.

## Required Verification

Run these commands:

```powershell
cd F:\MOSS-V3\frontend
npx vitest run src/features/balance-analysis/pages/balanceAnalysisPageModel.test.ts src/test/BalanceAnalysisPage.test.tsx
npx eslint src/features/balance-analysis/pages/BalanceAnalysisPage.tsx src/features/balance-analysis/pages/balanceAnalysisPageModel.ts src/features/balance-analysis/pages/balanceAnalysisPageModel.test.ts src/features/balance-analysis/components/BalanceAnalysisCardsSection.tsx src/features/balance-analysis/components/BalanceAnalysisTableSection.tsx
npx tsc --noEmit
```

```powershell
cd F:\MOSS-V3
python -m pytest -q tests/test_golden_samples_capture_ready.py tests/test_balance_analysis_api.py tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_docs_contract.py
git diff --check -- frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.ts frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.test.ts frontend/src/features/balance-analysis/components/BalanceAnalysisCardsSection.tsx frontend/src/features/balance-analysis/components/BalanceAnalysisTableSection.tsx
```

If one of these commands cannot run, report why and include the exact error.

## Delivery Contract Back To Codex

When done, report:

- root cause fixed
- files changed
- exact subagent task results
- exact verification commands and pass/fail output
- any behavior intentionally changed
- remaining risks
- whether anything was staged or committed

Do not ask Codex to approve midstream unless blocked by ambiguity that would change scope or by a destructive action.

Codex will do final review and acceptance after Cursor finishes.
