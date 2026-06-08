# Home Startup AG Grid Guard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `npm run guard:home-startup` pass by keeping AG Grid theme aliases out of the eager global stylesheet while preserving AG Grid pages.

**Architecture:** Keep institutional shell tokens and non-grid shell styling in `frontend/src/styles/global.css`. Move only AG Grid-specific theme aliases into `frontend/src/styles/agGridInstitutional.css`, and import that deferred stylesheet only from pages/components that render AG Grid. Do not change homepage startup code, risk pages, backend code, or unrelated shell/theme work.

**Tech Stack:** React, Vite, Vitest, CSS, AG Grid, PowerShell on Windows.

---

## Scope

Fix only the homepage startup guard blocker:

- `frontend/src/styles/global.css` must not contain `ag-theme-alpine` or AG Grid runtime/theme selectors.
- `frontend/src/styles/agGridInstitutional.css` must contain the institutional AG Grid CSS variable bridge.
- AG Grid pages must import `agGridInstitutional.css` next to their existing AG Grid CSS imports.
- Theme tests must enforce the split.

Do not touch:

- `/risk-overview` or risk tensor behavior.
- Homepage first-screen code already committed in `5f2a41fd`.
- Ledger PnL explainability work in `ea5b0374`.
- Backend, auth, seed data, market/macro pages, or unrelated dirty files.
- Global formatting or cleanup outside the files below.

## Files

- Modify: `frontend/src/styles/global.css`
- Modify or keep: `frontend/src/styles/agGridInstitutional.css`
- Modify: `frontend/src/test/theme.test.ts`
- Verify imports in:
  - `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
  - `frontend/src/features/balance-analysis/components/BalanceContributionRow.tsx`
  - `frontend/src/features/pnl/FormalPnlV1Page.tsx`
  - `frontend/src/features/pnl/PnlBridgePage.tsx`

## Task 1: Lock The CSS Split With Tests

**Step 1: Inspect current assertions**

Open `frontend/src/test/theme.test.ts` and confirm it contains:

```ts
const AG_GRID_INSTITUTIONAL_CSS_PATH = resolve(
  process.cwd(),
  "src/styles/agGridInstitutional.css",
);
```

and assertions equivalent to:

```ts
expect(globalCss).not.toContain("ag-theme-alpine");
expect(agGridCss).toContain(
  ".workbench-shell-grid--institutional-console :where(.ag-theme-alpine, .ag-theme-quartz)",
);
expect(agGridCss).toContain("--ag-background-color");
```

**Step 2: Add or adjust only missing assertions**

If any assertion is missing, add it to the existing `globalCss design token bridge (:root)` tests. Keep existing institutional shell token assertions intact.

**Step 3: Run targeted test**

Run from `frontend/`:

```bash
npm run test -- src/test/theme.test.ts -t "AG Grid|render-critical|global stylesheet"
```

Expected: pass after the CSS split is correct. If it fails because `global.css` still contains `ag-theme-alpine`, continue to Task 2.

## Task 2: Move AG Grid Selectors Out Of Global CSS

**Step 1: Inspect AG Grid selectors**

Search only the frontend source:

```bash
rg "ag-theme-alpine|ag-theme-quartz|--ag-" frontend/src
```

Expected:

- `frontend/src/styles/global.css` should not contain these strings after the fix.
- `frontend/src/styles/agGridInstitutional.css` should contain the institutional AG Grid overrides.
- Existing AG Grid page files may still import `ag-grid-community/styles/ag-theme-alpine.css`.

**Step 2: Edit `global.css` minimally**

Remove only the AG Grid-specific selector block from `frontend/src/styles/global.css`, if present:

```css
.workbench-shell-grid--institutional-console :where(.ag-theme-alpine, .ag-theme-quartz) {
  --ag-background-color: var(--moss-institutional-surface-raised);
  --ag-header-background-color: var(--moss-institutional-surface-muted);
  --ag-odd-row-background-color: var(--moss-institutional-row-stripe);
  --ag-row-hover-color: var(--moss-institutional-row-hover);
  --ag-border-color: var(--moss-institutional-border);
  --ag-header-foreground-color: var(--moss-institutional-text-muted);
  --ag-foreground-color: var(--moss-institutional-text);
  --ag-font-family: var(--moss-font-sans);
  --ag-font-size: 12px;
}
```

Do not remove the broader `.workbench-shell-grid--institutional-console` shell styles unless they are AG Grid-specific.

**Step 3: Keep `agGridInstitutional.css` as the only AG Grid override home**

Ensure `frontend/src/styles/agGridInstitutional.css` contains:

```css
.workbench-shell-grid--institutional-console :where(.ag-theme-alpine, .ag-theme-quartz) {
  --ag-background-color: var(--moss-institutional-surface-raised);
  --ag-header-background-color: var(--moss-institutional-surface-muted);
  --ag-odd-row-background-color: var(--moss-institutional-row-stripe);
  --ag-row-hover-color: var(--moss-institutional-row-hover);
  --ag-border-color: var(--moss-institutional-border);
  --ag-header-foreground-color: var(--moss-institutional-text-muted);
  --ag-foreground-color: var(--moss-institutional-text);
  --ag-font-family: var(--moss-font-sans);
  --ag-font-size: 12px;
}
```

## Task 3: Ensure AG Grid Pages Import The Deferred Stylesheet

**Step 1: Inspect the four known AG Grid entry points**

Confirm imports are present next to the existing AG Grid CSS imports:

```ts
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import "../../../styles/agGridInstitutional.css";
```

Use `../../styles/agGridInstitutional.css` for files under `frontend/src/features/pnl/`.

**Step 2: Add only missing imports**

Known expected files:

- `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- `frontend/src/features/balance-analysis/components/BalanceContributionRow.tsx`
- `frontend/src/features/pnl/FormalPnlV1Page.tsx`
- `frontend/src/features/pnl/PnlBridgePage.tsx`

Do not add the import to homepage, route registry, app root, or `global.css`.

## Task 4: Verify Startup Guard And Build

Run from `frontend/`:

```bash
npm run test -- src/test/theme.test.ts src/test/StartupPerformanceGuards.test.ts
npm run build
npm run guard:home-startup
npm run lint
npm run typecheck
npm run debt:audit
```

Expected:

- Theme and startup guard tests pass.
- Build passes.
- `guard:home-startup` no longer reports `ag-theme-alpine` in eager CSS.
- Lint, typecheck, and debt audit pass or report only pre-existing unrelated failures with evidence.

If `guard:home-startup` still fails, inspect the generated asset named in the guard output and trace which import pulled AG Grid into the eager path. Fix only that import path.

## Task 5: Browser Verification

Use the in-app browser or Playwright/browser tool.

Open:

- `http://localhost:5888/`
- `http://localhost:5888/dashboard`
- One AG Grid page, preferably `http://localhost:5888/balance-analysis`

Expected:

- Home and dashboard render normally.
- AG Grid page still shows table styling.
- No visible full-page error.
- No obvious shell/header overlap caused by the CSS split.

If the dev server is not running, start the existing frontend dev workflow without changing ports unless the port is occupied.

## Task 6: Commit Only The Guard Fix

**Step 1: Review dirty work**

Run:

```bash
git status --short
git diff -- frontend/src/styles/global.css frontend/src/styles/agGridInstitutional.css frontend/src/test/theme.test.ts frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx frontend/src/features/balance-analysis/components/BalanceContributionRow.tsx frontend/src/features/pnl/FormalPnlV1Page.tsx frontend/src/features/pnl/PnlBridgePage.tsx
```

**Step 2: Stage only relevant hunks**

Stage only:

- AG Grid selector removal from `global.css`.
- `agGridInstitutional.css`.
- AG Grid page imports, if they are part of this fix.
- Theme test assertions that enforce the split.

Do not stage unrelated institutional shell restyling, Ledger PnL, risk, backend, docs, or market/macro changes.

**Step 3: Commit if cleanly separable**

Use a focused message:

```bash
git commit -m "Keep AG Grid styles out of home startup path"
```

Include trailers in the body:

```text
Constraint: Keep eager global CSS free of AG Grid theme aliases.
Scope-risk: Low; AG Grid overrides move to page-imported stylesheet only.
Tested: npm run test -- src/test/theme.test.ts src/test/StartupPerformanceGuards.test.ts
Tested: npm run build
Tested: npm run guard:home-startup
Tested: npm run lint
Tested: npm run typecheck
Tested: npm run debt:audit
```

If the AG Grid fix cannot be cleanly separated from existing shell/theme dirty work, do not commit. Report: `与既有 shell/theme 改动耦合，未提交`.

## Final Report

Report in Chinese:

- Root cause: `global.css` eagerly carried AG Grid theme alias text, so the homepage startup guard flagged the first-screen CSS bundle.
- Changed files.
- Verification results.
- Whether a commit was created.
- Remaining risk: any unrelated dirty files or unavailable browser/server checks.
