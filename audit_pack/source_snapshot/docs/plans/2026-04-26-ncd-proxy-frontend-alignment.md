# NCD Proxy Frontend Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align frontend NCD proxy wording, mock payloads, and tests with the landed warehouse Shibor envelope so the UI does not imply live supplier pulls or a real NCD issuance matrix.

**Architecture:** Keep the backend read path unchanged and treat `/ui/market-data/ncd-funding-proxy` as an analytical envelope whose `result` is a proxy payload. Update only the frontend surfaces that display or mock that payload, preserving existing cross-asset page localization/chart work already present in the worktree.

**Tech Stack:** React, TypeScript, Vitest, existing `frontend/src/api/client.ts` mock client, existing cross-asset page model helpers.

---

## Current Scope

Page/workflow: cross-asset NCD proxy evidence plus the shared market-data NCD proxy mock/test surface.

Inspect first:
- `frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts`
- `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`
- `frontend/src/test/crossAssetDriversPageModel.test.ts`
- `frontend/src/api/client.ts`
- `frontend/src/test/ApiClient.test.ts`
- `frontend/src/test/MarketDataPage.test.tsx`
- `frontend/src/test/CrossAssetPage.test.tsx`

Do not touch:
- backend supplier refresh paths
- database schema
- Choice/Tushare credentials or permissions
- global SDK wrappers
- unrelated backend changes currently present in the worktree
- existing cross-asset chart/layout edits except where a direct NCD semantic fix requires it

## Success Criteria

- Mock NCD payload mirrors the real landed envelope: one `Shibor fixing` row, no `Quote median` row, `is_actual_ncd_matrix: false`, and warning text that says landed warehouse Shibor is used while quote medians are unavailable.
- Cross-asset evidence and candidate actions keep treating NCD as proxy evidence, not a real issuance matrix.
- Empty/unavailable state remains explicit.
- Targeted frontend tests pass.
- `npm run debt:audit` passes after page/model/client edits.
- Commit uses the repository Lore commit protocol.

---

### Task 1: Confirm Working-Tree Boundaries

**Files:**
- Read: `frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts`
- Read: `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`
- Read: `frontend/src/features/cross-asset/lib/crossAssetTrendChart.ts`
- Read: `frontend/src/test/crossAssetDriversPageModel.test.ts`
- Read: `backend/app/core_finance/macro_bond_linkage.py`
- Read: `tests/test_macro_bond_linkage.py`

**Step 1: Check status**

Run:

```powershell
git status --short
```

Expected: cross-asset frontend files and unrelated backend/MCP files may already be modified. Treat them as pre-existing unless edited in this plan.

**Step 2: Read relevant diffs**

Run:

```powershell
git diff -- frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts
git diff -- frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx
git diff -- frontend/src/test/crossAssetDriversPageModel.test.ts
```

Expected: existing localization/chart changes remain intact.

### Task 2: Update Mock NCD Payload To Landed-Warehouse Semantics

**Files:**
- Modify: `frontend/src/api/client.ts`
- Test: `frontend/src/test/ApiClient.test.ts`
- Test: `frontend/src/test/MarketDataPage.test.tsx`

**Step 1: Update the mock payload**

In `buildMockNcdFundingProxyPayload`, keep only the Shibor fixing row:

```typescript
rows: [
  {
    row_key: "shibor_fixing",
    label: "Shibor fixing",
    "1M": 1.405,
    "3M": 1.4275,
    "6M": 1.4505,
    "9M": 1.464,
    "1Y": 1.478,
    quote_count: null,
  },
],
warnings: [
  "Using landed external warehouse Shibor; quote medians unavailable.",
  "Proxy only; not actual NCD issuance matrix.",
],
```

Also remove the `quote_median` row from the fixture so mock mode no longer implies unavailable quote medians are present.

**Step 2: Update API client assertions**

Find the NCD mock test in `frontend/src/test/ApiClient.test.ts`.

Assert:

```typescript
expect(envelope.result.is_actual_ncd_matrix).toBe(false);
expect(envelope.result.rows).toHaveLength(1);
expect(envelope.result.rows[0].label).toBe("Shibor fixing");
expect(envelope.result.rows.some((row) => row.row_key === "quote_median")).toBe(false);
expect(envelope.result.warnings.join(" ")).toMatch(/warehouse|landed|quote medians unavailable/i);
```

**Step 3: Update market-data page test**

In the existing NCD panel test in `frontend/src/test/MarketDataPage.test.tsx`, remove expectations that require `Quote median`.

Assert:

```typescript
expect(screen.getByText(/Shibor fixing/i)).toBeInTheDocument();
expect(screen.queryByText(/Quote median/i)).not.toBeInTheDocument();
expect(screen.getByTestId("market-data-ncd-proxy-warning")).toHaveTextContent(/quote medians unavailable|not actual NCD/i);
```

Run:

```powershell
cd frontend
npm test -- src/test/ApiClient.test.ts src/test/MarketDataPage.test.tsx
```

Expected: both files pass.

### Task 3: Lock Cross-Asset Evidence Semantics

**Files:**
- Modify: `frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts`
- Modify: `frontend/src/test/crossAssetDriversPageModel.test.ts`

**Step 1: Keep unavailable state explicit**

Confirm `buildCrossAssetNcdProxyEvidence` returns:

```typescript
sourceMeta: "unavailable"
proxyWarning: "NCD 资金代理数据不可用（请求失败或空载荷）。"
rowCaptions: []
```

No code change is needed if this already holds.

**Step 2: Prefer landed-warning wording when present**

Ensure the evidence warning uses the first backend warning unchanged when the payload is available:

```typescript
proxyWarning: (payload.warnings[0] ?? defaultProxyWarn).trim()
```

No code change is needed if this already holds.

**Step 3: Update the focused test fixture**

In `frontend/src/test/crossAssetDriversPageModel.test.ts`, update the NCD evidence test fixture to mirror landed warehouse payload:

```typescript
rows: [
  {
    row_key: "shibor_fixing",
    label: "Shibor fixing",
    "1M": 1.405,
    "3M": 1.4275,
    "6M": 1.4505,
    "9M": 1.464,
    "1Y": 1.478,
    quote_count: null,
  },
],
warnings: ["Using landed external warehouse Shibor; quote medians unavailable."],
```

Assert:

```typescript
expect(evidence.proxyWarning).toMatch(/warehouse|landed|quote medians unavailable/i);
expect(evidence.rowCaptions[0]).toContain("Shibor fixing");
expect(evidence.rowCaptions.some((line) => /Quote median/i.test(line))).toBe(false);
```

Run:

```powershell
cd frontend
npm test -- src/test/crossAssetDriversPageModel.test.ts
```

Expected: file passes.

### Task 4: Check Cross-Asset Page Rendering Contract

**Files:**
- Modify only if needed: `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`
- Test: `frontend/src/test/CrossAssetPage.test.tsx`

**Step 1: Verify no page logic change is required**

The page should continue reading:

```typescript
ncdFundingProxyQuery.data?.result
```

because the API client returns an envelope. If the query and evidence builder already use `result`, leave the page unchanged.

**Step 2: Add a narrow render assertion only if existing tests do not cover the new warning**

Acceptable assertion:

```typescript
expect(screen.getByTestId("cross-asset-ncd-proxy-warning")).toHaveTextContent(/quote medians unavailable|not actual NCD/i);
```

Run:

```powershell
cd frontend
npm test -- src/test/CrossAssetPage.test.tsx
```

Expected: file passes.

### Task 5: Final Verification

**Files:**
- Read: all touched files

**Step 1: Run targeted frontend tests**

Run:

```powershell
cd frontend
npm test -- src/test/ApiClient.test.ts src/test/MarketDataPage.test.tsx src/test/CrossAssetPage.test.tsx src/test/crossAssetDriversPageModel.test.ts
```

Expected: all targeted tests pass.

**Step 2: Run typecheck**

Run:

```powershell
cd frontend
npm run typecheck
```

Expected: typecheck passes.

**Step 3: Run debt audit**

Run:

```powershell
cd frontend
npm run debt:audit
```

Expected: no-growth debt audit passes.

**Step 4: Review diff**

Run:

```powershell
git diff -- frontend/src/api/client.ts frontend/src/test/ApiClient.test.ts frontend/src/test/MarketDataPage.test.tsx frontend/src/test/CrossAssetPage.test.tsx frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts frontend/src/test/crossAssetDriversPageModel.test.ts
```

Expected: diff only changes NCD proxy semantics and minimal tests, while preserving pre-existing cross-asset localization/chart changes.

### Task 6: Commit

**Files:**
- Stage only files changed for this task and the plan document.

**Step 1: Stage deliberately**

Run:

```powershell
git add docs/plans/2026-04-26-ncd-proxy-frontend-alignment.md frontend/src/api/client.ts frontend/src/test/ApiClient.test.ts frontend/src/test/MarketDataPage.test.tsx frontend/src/test/CrossAssetPage.test.tsx frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts frontend/src/test/crossAssetDriversPageModel.test.ts
```

If a listed file was not changed by this task, omit it.

**Step 2: Commit with Lore protocol**

Use a commit message like:

```text
Align NCD proxy UI with landed warehouse authority

The backend now serves NCD funding proxy data from the landed warehouse
Shibor rows, so frontend mock data and page assertions should no longer
imply quote medians or a live supplier-backed NCD matrix are present.

Constraint: Backend read path is warehouse-only for this surface.
Rejected: Keep quote_median in mock payload | it contradicts the landed warehouse envelope and hides the unavailable median gap.
Confidence: high
Scope-risk: narrow
Directive: Do not reintroduce quote median display unless the warehouse refresh lands actual quote median rows with lineage.
Tested: frontend targeted NCD/cross-asset tests; npm run typecheck; npm run debt:audit
Not-tested: Browser visual pass
```

