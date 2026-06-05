# Cursor Prompt - Cross-Asset Investment Research Feature Surfacing

You are working in `F:\MOSS-V3`.

Goal: turn the already-implemented backend/read-model capabilities into a visible, usable frontend feature: a cross-asset investment research workbench. This is feature implementation, not another governance/audit cleanup pass.

Current checkpoints:

- `09f6677 Keep product-category PnL display inside governed page model`
- `e4cd532 Keep balance analysis display parsing inside page model`

The user concern is that the backend has many implemented capabilities that are not visible or usable in the frontend. This task should make one coherent frontend business surface real.

## Product Slice

Deliver a usable `Cross-Asset Investment Research` workbench through:

- canonical route: `/cross-asset`
- compatibility route: `/cross-asset-drivers`
- existing workbench navigation entry for cross asset

The page should answer, above the fold:

1. What is the current cross-asset stance for duration / curve / credit / instrument?
2. Which transmission axes are ready vs pending signal?
3. What current market indicators, supply/auction events, and NCD/funding proxy signals support or weaken the stance?
4. What candidate actions and watch-list items should a PM look at next?

Do not build a marketing/landing page. Build the actual workbench surface as the first screen.

## Non-Negotiable Scope

Allowed frontend scope:

- `frontend/src/features/cross-asset/**`
- `frontend/src/features/market-data/components/NcdMatrix.tsx` only if needed for reusable NCD proxy display
- `frontend/src/api/client.ts`
- `frontend/src/api/contracts.ts`
- `frontend/src/router/routes.tsx`
- `frontend/src/mocks/navigation.ts`
- targeted tests under `frontend/src/test/*CrossAsset*`, `frontend/src/test/ApiClient.test.ts`, `frontend/src/test/navigation.test.ts`, `frontend/src/test/RouteRegistry.test.tsx`

Avoid backend edits unless the frontend contract is impossible to consume due to a clear backend/schema mismatch. If backend edits are necessary, stop and report the exact blocker first.

Do not touch:

- product-category PnL
- balance-analysis
- risk tensor / risk overview
- database schema
- auth / permissions
- scheduler / queue / cache
- global SDK wrappers
- app-wide state architecture
- unrelated frontend pages

Do not stage unrelated dirty files. This repo already has many dirty files. Stage only the feature files intentionally changed for this task.

## Read First

Read these before editing:

- `AGENTS.md`
- `docs/NEW_WINDOW_PROMPT_2026-04-24_BOUNDARY_GOVERNANCE_CONTINUE.md`
- `frontend/src/router/routes.tsx`
- `frontend/src/mocks/navigation.ts`
- `frontend/src/api/client.ts`
- `frontend/src/api/contracts.ts`
- `backend/app/api/routes/macro_bond_linkage.py`
- `backend/app/api/routes/research_calendar.py`
- `backend/app/api/routes/market_data_ncd_proxy.py`
- `backend/app/schemas/research_calendar.py`
- `backend/app/schemas/ncd_proxy.py`
- `frontend/src/features/cross-asset/pages/CrossAssetPage.tsx`
- `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`
- `frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts`
- `frontend/src/features/cross-asset/lib/crossAssetKpiModel.ts`
- `frontend/src/features/cross-asset/components/CrossAssetEventCalendar.tsx`
- `frontend/src/features/cross-asset/components/MarketCandidateActions.tsx`
- `frontend/src/features/cross-asset/components/WatchList.tsx`
- `frontend/src/test/CrossAssetPage.test.tsx`
- `frontend/src/test/CrossAssetDriversRoute.test.tsx`
- `frontend/src/test/crossAssetDriversPageModel.test.ts`
- `frontend/src/test/ApiClient.test.ts`

## Backend Capabilities To Surface

Use existing API client methods or add the smallest missing frontend client contract:

- `getMacroBondLinkageAnalysis({ reportDate })`
  - backend: `/api/macro-bond-linkage/analysis`
  - important fields: `environment_score`, `portfolio_impact`, `top_correlations`, `research_views`, `transmission_axes`, `warnings`, `computed_at`
- `getChoiceMacroLatest()`
  - backend: `/ui/macro/choice-series/latest`
  - use only as market indicator evidence, not as formal portfolio truth
- `getResearchCalendarEvents({ reportDate })`
  - backend: `/ui/calendar/supply-auctions`
  - use supply/auction events; map amount, term, issuer, status, and headline fields when present
- `getNcdFundingProxy()`
  - backend: `/ui/market-data/ncd-funding-proxy`
  - must explicitly show it is a proxy if `is_actual_ncd_matrix === false`; do not present it as actual NCD issuance matrix

## Suggested Parallel Subtasks For Cursor Subagents

Spawn subagents for independent work, then integrate yourself. Keep each subagent scoped.

### Agent A - Capability / Gap Mapper

Read-only.

Deliver:

- current backend endpoints and schemas relevant to this feature
- current frontend pages/components that already consume those endpoints
- missing gaps to make `/cross-asset` a usable first-screen feature
- existing dirty files that are relevant vs unrelated
- proposed exact changed file list

Do not edit files.

### Agent B - API Client / Contract Tightening

Owned write scope:

- `frontend/src/api/contracts.ts`
- `frontend/src/api/client.ts`
- `frontend/src/test/ApiClient.test.ts`

Tasks:

1. Ensure `ResearchCalendarResultPayload` matches backend schema, including:
   - `amount`
   - `amount_unit`
   - `currency`
   - `status`
   - `headline_text`
   - `headline_url`
   - `headline_published_at`
2. Ensure `mapResearchCalendarApiEvent` maps useful display fields:
   - stable `id`
   - `date`
   - `kind`
   - `severity`
   - human `amount_label`, for example `180 亿元` when amount/unit/currency exist
   - `note` with issuer / term / status / headline where useful
3. Ensure `getNcdFundingProxy()` exists in the `ApiClient` interface and real client, and mock mode returns a clearly marked proxy payload.
4. Add/update targeted `ApiClient.test.ts` coverage for real URL construction and mapping.

Rules:

- Do not change backend.
- Do not fabricate actual NCD matrix semantics.
- Preserve existing mock behavior unless it contradicts explicit proxy labeling.

### Agent C - Cross-Asset Page Model

Owned write scope:

- `frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts`
- `frontend/src/test/crossAssetDriversPageModel.test.ts`

Tasks:

1. Make the page model produce a stable view model for:
   - research view cards
   - transmission axes
   - candidate actions
   - watch list
   - event calendar rows
   - NCD/funding proxy evidence
   - status/provenance flags
2. Prefer backend `research_views` and `transmission_axes` when present.
3. When backend signals are missing, show `pending_signal` or explicit fallback source, not hidden static conclusions.
4. Include NCD proxy evidence in candidate actions or watch list only as proxy evidence, with warning text when `is_actual_ncd_matrix` is false.
5. Keep model logic testable and UI-free.

Required tests:

- backend research views win over fallback
- missing research view produces pending/fallback card
- backend transmission axis order is stable and missing axes remain visible as `pending_signal`
- research calendar events map into visible calendar rows
- NCD proxy warning is surfaced and not promoted to actual matrix
- stale/fallback meta creates visible status flags

### Agent D - Cross-Asset UI / Route Integration

Owned write scope:

- `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`
- `frontend/src/features/cross-asset/pages/CrossAssetPage.tsx`
- `frontend/src/features/cross-asset/components/*.tsx` as needed
- `frontend/src/router/routes.tsx`
- `frontend/src/mocks/navigation.ts`

Tasks:

1. Make `/cross-asset` render the real cross-asset drivers workbench.
2. Keep `/cross-asset-drivers` as a compatibility route to the same experience.
3. Ensure the first screen contains:
   - page header with report date / source status
   - duration / curve / credit / instrument research cards
   - transmission axes panel
   - candidate actions
   - event calendar
   - watch list
   - NCD/funding proxy evidence or warning if available
4. Keep the page utilitarian and information-dense. No landing hero, no decorative rewrite.
5. Use existing `SectionCard`, `AsyncSection`, `StatusPill`, `KpiCard`, `CalendarList`, and existing cross-asset components where possible.
6. Show loading, error, empty, stale, fallback, and proxy states explicitly.
7. Do not change route names outside this feature.

Rules:

- Do not add dependencies.
- Do not create a separate new navigation group.
- Do not hide backend warnings.
- Do not present analytical/fallback data as formal truth.

### Agent E - Feature Acceptance Tests

Owned write scope:

- `frontend/src/test/CrossAssetPage.test.tsx`
- `frontend/src/test/CrossAssetDriversRoute.test.tsx`
- `frontend/src/test/navigation.test.ts`
- `frontend/src/test/RouteRegistry.test.tsx` only if route registry assertions need updates

Add/adjust the smallest tests that prove the feature is actually surfaced:

- `/cross-asset` renders the real workbench, not a placeholder
- `/cross-asset-drivers` compatibility route renders the same workbench
- backend `research_views` and `transmission_axes` are visible in cards/panels
- research calendar supply/auction events are visible
- NCD proxy warning is visible and not mislabeled as actual matrix
- navigation exposes the cross-asset entry as live
- fallback/pending states remain visible when backend research fields are absent

Prefer role/text/testid assertions over fragile style snapshots.

## Integration Requirements

After subagents return:

1. Review their patches before accepting.
2. Integrate into one minimal feature diff.
3. Remove dead imports/helpers created during integration.
4. Keep every changed line tied to this feature surfacing task.
5. Do not repair unrelated mojibake/text unless the changed line is part of this feature.
6. If existing dirty files overlap, preserve unrelated local edits and report that the file was pre-dirty.

## Required Verification

Run:

```powershell
cd F:\MOSS-V3\frontend
npx vitest run src/test/CrossAssetPage.test.tsx src/test/CrossAssetDriversRoute.test.tsx src/test/crossAssetDriversPageModel.test.ts src/test/ApiClient.test.ts src/test/navigation.test.ts
npx eslint src/features/cross-asset/pages/CrossAssetDriversPage.tsx src/features/cross-asset/pages/CrossAssetPage.tsx src/features/cross-asset/lib/crossAssetDriversPageModel.ts src/api/client.ts src/api/contracts.ts src/router/routes.tsx src/mocks/navigation.ts
npx tsc --noEmit
```

Then run backend/API contract checks relevant to surfaced endpoints:

```powershell
cd F:\MOSS-V3
python -m pytest -q tests/test_macro_bond_linkage.py tests/test_market_data_ncd_proxy_api.py tests/test_research_calendar_ingest_service.py tests/test_supply_auction_calendar_api.py
git diff --check -- frontend/src/features/cross-asset frontend/src/api/client.ts frontend/src/api/contracts.ts frontend/src/router/routes.tsx frontend/src/mocks/navigation.ts frontend/src/test/CrossAssetPage.test.tsx frontend/src/test/CrossAssetDriversRoute.test.tsx frontend/src/test/crossAssetDriversPageModel.test.ts frontend/src/test/ApiClient.test.ts frontend/src/test/navigation.test.ts
```

If a listed Python test is not present in this checkout, report the missing path and run the closest matching `rg "ncd|research_calendar|supply_auction|macro_bond_linkage" tests -g "*.py"` results instead.

## Delivery Contract Back To Codex

When done, report:

- root cause / product gap addressed
- feature behavior delivered
- files changed
- exact subagent results
- exact verification commands and pass/fail output
- known remaining backend capabilities still not surfaced
- whether anything was staged or committed

Do not ask Codex to approve midstream unless blocked by a destructive action or a scope decision that would change this feature slice.

Codex will do final review, fix integration issues if needed, and perform final acceptance after Cursor finishes.
