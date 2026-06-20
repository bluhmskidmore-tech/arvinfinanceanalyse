# Frontend Page Chain Audit

## Status

- date: 2026-04-24
- scope: read-only frontend boundary audit
- purpose: identify reusable good patterns and first page-closure candidates

## Existing Good Patterns

### Shared State Shell

- `frontend/src/components/DataSection.tsx`
- `frontend/src/components/DataSection.types.ts`
- `frontend/src/components/DataSection.test.tsx`

Use this for loading / error / empty / stale / fallback / ok state consistency.

### Executive Dashboard Chain

- `frontend/src/features/workbench/pages/DashboardPage.tsx`
- `frontend/src/features/executive-dashboard/adapters/executiveDashboardAdapter.ts`
- `frontend/src/features/executive-dashboard/adapters/executiveDashboardAdapter.test.ts`
- `frontend/src/features/executive-dashboard/selectors/executiveDashboardSelectors.ts`
- `frontend/src/features/executive-dashboard/selectors/executiveDashboardSelectors.test.ts`
- `frontend/src/features/executive-dashboard/components/OverviewSection.tsx`
- `frontend/src/features/executive-dashboard/components/OverviewSection.states.test.tsx`

This is the strongest current pattern:

```text
API hook -> adapter -> selector -> section component -> state tests
```

### Existing Adapter Families

- `frontend/src/features/cashflow-projection/adapters/cashflowProjectionAdapter.ts`
- `frontend/src/features/pnl/adapters/pnlBridgeAdapter.ts`
- `frontend/src/features/pnl-attribution/adapters/pnlAttributionAdapter.ts`
- `frontend/src/features/bond-analytics/adapters/bondAnalyticsAdapter.ts`
- `frontend/src/features/liability-analytics/adapters/liabilityAdapter.ts`

These are good Cursor targets because each already has or expects local adapter tests.

### Contract Test Base

- `frontend/src/test/contract/README.md`
- `frontend/src/test/contract/mock-contract.test.ts`
- `frontend/src/test/contract/assertAllNumerics.ts`

Use these to keep frontend mock envelopes aligned with contract expectations.

## Gaps

- Page-level contract tests are uneven across pages.
- Many `DataSection` usage sites do not yet have local `.states.test.tsx`.
- Selector layers are mature in executive-dashboard but not universal.
- "No frontend formal metric recomputation" is mostly documented, not strongly executable.
- Some components still contain direct `Number(...)` / `parseFloat(...)` display transformations; these need classification before changing, because some are harmless UI formatting while others may be business-risky.

## Risky Search Anchors

Use these to locate follow-up slices:

```powershell
rg -n "parseFloat|Number\\(|result_meta|fallback_mode|quality_flag|vendor_status|adapter|selector" frontend/src -g "*.ts" -g "*.tsx"
```

Classify findings as:

- adapter-owned view-model conversion
- local display formatting only
- risky formal metric derivation in component
- mock/demo/placeholder-only behavior

## Recommended Cursor Task Groups

### Group 1 - Page Contract Baseline

Goal:

- Add or tighten page-level contract tests for one page at a time.

Good first candidates:

- executive dashboard sections
- pnl bridge
- pnl attribution
- cashflow projection

### Group 2 - State Tests

Goal:

- Add `.states.test.tsx` around `DataSection` consumers for no_data / empty / error / stale / fallback / loading / ok.

Priority directories:

- `frontend/src/features/executive-dashboard/components`
- `frontend/src/features/pnl-attribution/components`
- `frontend/src/features/cashflow-projection`

### Group 3 - Formal Recompute Audit

Goal:

- Turn the "frontend must not compute formal finance metrics" rule into a small executable audit.

Start docs-only:

- list suspect component-level parsing sites
- separate display formatting from business derivation
- recommend one testable rule

### Group 4 - Selector Standardization

Goal:

- Move repeated derivation logic into selectors or adapter pure functions.

Priority:

- `pnl-attribution`
- `bond-analytics`

Do this only after a page has a contract/state test baseline.

## First Implementation Recommendation

Pick one page that already has:

- adapter test
- states test pattern nearby
- page contract or golden sample

Then close:

```text
page contract -> adapter/selector state mapping -> component states -> targeted tests
```

Do not start with an excluded surface.
