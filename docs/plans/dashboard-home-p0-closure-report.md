# Dashboard Home P0 Closure Report

Date: 2026-05-23

## Scope

This closure only covers the workbench dashboard homepage first-screen P0 visual pass.

Touched scope:
- `frontend/src/features/workbench/pages/DashboardPage.tsx`
- `frontend/src/features/workbench/dashboard/DashboardCockpitPage.css`
- `frontend/src/test/DashboardPage.test.tsx`
- final evidence under `docs/plans/artifacts/dashboard-home-final-*`

Explicitly not touched:
- API clients, backend, data contracts, mock metric definitions
- balance analysis and liability analytics dirty work
- root `artifacts/`, `.tmp_old_block.txt`, historical target/before screenshots

## Root Cause

The homepage first screen still had too many equal-weight visual roles: grouped KPI cards, long depth tables, secondary drilldown links, and repeated decision/detail panels competed with the main daily judgment. On 768px width the cockpit shell also kept a multi-column shell layout, which compressed the page into a narrow column.

## Changes

- Promoted the judgment hero visually so the daily conclusion is readable before scanning the rest of the page.
- Flattened the KPI area into one compact 6-item operating band instead of two card groups.
- Deferred the depth zone and action queue until the depth drawer is opened.
- Kept the first-screen decision rail visible; the deeper decision queue panel remains behind the depth drawer as secondary supporting detail.
- Added responsive shell constraints for homepage cockpit widths at and below 1023px.
- Updated homepage tests to assert the closed-by-default depth drawer and deterministic drawer-open behavior.

## Evidence

Final retained artifacts:
- `docs/plans/artifacts/dashboard-home-final-1440.png`
- `docs/plans/artifacts/dashboard-home-final-768.png`
- `docs/plans/artifacts/dashboard-home-final-meta.json`

Browser checks in `dashboard-home-final-meta.json` cover:
- 1440 and 768 final screenshots
- 767, 1023, and 1279 width probes
- no horizontal overflow
- visible judgment conclusion
- 6 KPI cards
- depth zone and action queue not initially rendered
- first-screen decision rail still rendered

## Validation

Passed:
- `npm run test -- src/test/DashboardPage.test.tsx src/features/workbench/pages/useDashboardResearchCalendarQuery.test.tsx src/features/workbench/pages/useDashboardSnapshotBoundary.test.tsx src/features/workbench/pages/dashboardPageHelpers.test.ts src/features/workbench/dashboard/dashboardHomeModel.test.ts src/features/workbench/dashboard/dashboardCockpitModel.test.ts src/features/workbench/dashboard/dashboardCockpitHomeModel.test.ts`
- `npm run typecheck`
- `npm run debt:audit`
- `npx eslint src/features/workbench/pages/DashboardPage.tsx src/test/DashboardPage.test.tsx`
- Playwright browser probe against `http://127.0.0.1:5888/`

Not tested:
- MCP metric evidence servers were unavailable, so this pass did not change or re-validate metric definitions, units, report-date semantics, source lineage, or governed samples.
- Full app regression was not run because this closure is scoped to the homepage first screen.

## Residual Risk

The homepage visual closure is verified at the requested screenshot widths and nearby breakpoint probes. Remaining risk is limited to untested browser/device combinations outside those widths and any future business metric contract changes, which were intentionally out of scope for this pass.
