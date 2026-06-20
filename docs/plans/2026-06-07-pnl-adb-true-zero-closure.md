# PnL ADB True Zero Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining PnL risk where a real ADB average balance of `0` is still treated as missing/unavailable downstream.

**Architecture:** Keep the previous ADB comparison null-preservation slice intact. This plan only changes PnL downstream semantics so `undefined` means missing ADB, while numeric `0` means ADB is present but cannot be used as a yield/FTP denominator. Do not change backend, ADB comparison client normalization, monthly ADB, accounting-basis ADB, or YTD source payload shape.

**Tech Stack:** React, TypeScript, Vitest, existing PnL page model/helpers.

---

## Business Rule

- `undefined`: no ADB data was resolved for the business type.
- `0`: ADB data was resolved and is a real zero balance.
- Positive number: ADB data was resolved and is usable as a denominator.

Implications:

- Missing count must count only `undefined`, not `0`.
- Displayed ADB balance must show `0.00` for true zero.
- Annualized yield and FTP calculations must remain unavailable for `0`, because division by zero is invalid.
- User-facing status should distinguish "missing ADB" from "ADB is zero denominator".

## Non-Goals

- Do not touch `frontend/src/api/liabilityAdbClient.ts` except if verification reveals a direct regression from this plan.
- Do not touch `frontend/src/api/contracts.ts` except if TypeScript requires an existing nullable type import cleanup.
- Do not alter monthly ADB, accounting-basis ADB, backend calculations, schema, auth, cache, queues, or global API client composition.
- Do not make zero denominator produce annualized yield or FTP yield.

## Task 1: Lock Resolver Semantics With RED Tests

**Files:**
- Modify: `frontend/src/features/pnl/zqtzAdbAvgRollup.test.ts`
- Modify later: `frontend/src/features/pnl/zqtzAdbAvgRollup.ts`

**Step 1: Write failing tests**

Add tests:

```ts
it("returns direct zero when the category explicitly has true zero ADB", () => {
  const map = new Map<string, number>([["zero-business", 0]]);
  expect(resolveAdbAvgYuan("zero-business", map)).toBe(0);
});

it("returns rolled-up zero when child categories explicitly resolve to zero", () => {
  const map = new Map<string, number>([
    ["信托计划", 0],
    ["证券业资管计划", 0],
  ]);
  expect(resolveAdbAvgYuan("非底层投资资产", map)).toBe(0);
});

it("keeps missing rollup undefined when neither parent nor children are present", () => {
  const map = new Map<string, number>();
  expect(resolveAdbAvgYuan("非底层投资资产", map)).toBeUndefined();
});
```

If the existing file's Chinese literals are encoded differently, use the exact literals already present in the test file for `信托计划`, `证券业资管计划`, and `非底层投资资产`.

**Step 2: Verify RED**

Run:

```bash
cd frontend
npm run test -- src/features/pnl/zqtzAdbAvgRollup.test.ts -t "zero"
```

Expected:

- direct zero currently fails because `resolveAdbAvgYuan` requires `direct > 0`.
- rolled-up zero currently fails because rollup returns `undefined` when sum is `0`.

## Task 2: Make Resolver Preserve Zero Without Treating Missing As Zero

**Files:**
- Modify: `frontend/src/features/pnl/zqtzAdbAvgRollup.ts`

**Step 1: Minimal implementation**

Change direct lookup from `get + > 0` to explicit key presence:

```ts
if (directMap.has(businessType)) {
  return directMap.get(businessType);
}
```

For rollup, track whether any child resolved:

```ts
let sum = 0;
let resolvedChildCount = 0;
for (const label of children) {
  const v = resolveAdbAvgYuanFromRollup(label, directMap, visiting);
  if (v !== undefined) {
    resolvedChildCount += 1;
    sum += v;
  }
}
return resolvedChildCount > 0 ? sum : undefined;
```

Do not change the function return type; `number | undefined` remains enough when `0` is allowed as a number.

**Step 2: Verify GREEN**

Run:

```bash
cd frontend
npm run test -- src/features/pnl/zqtzAdbAvgRollup.test.ts
```

Expected: all resolver tests pass.

## Task 3: Split Missing ADB From Zero Denominator In Page Model

**Files:**
- Modify: `frontend/src/features/pnl/pnlByBusinessPageModel.ts`
- Modify: `frontend/src/features/pnl/pnlByBusinessPageModel.test.ts`

**Step 1: Write failing model test**

Add a test near the existing `missingAdbCount` tests:

```ts
it("counts true-zero ADB as covered but zero-denominator limited", () => {
  const model = buildPnlByBusinessPageModel({
    viewMode: "ytd",
    selectedReportDate: "2026-04-30",
    selectedYear: 2026,
    selectedBusinessKey: null,
    adbAvgByBusinessType: new Map([
      ["债券投资", 100_000_000],
      ["信托计划", 0],
      ["证券业资管计划", 0],
    ]),
    datesState: { isLoading: false, isError: false },
    monthlyState: { isLoading: false, isError: false },
    ytdState: { isLoading: false, isError: false },
    formalState: { isLoading: false, isError: false },
    ytdResult: ytdPayload(),
    ytdMeta: meta({ quality_flag: "ok" }),
  });

  expect(model.insight.missingAdbCount).toBe(0);
  expect(model.insight.zeroAdbCount).toBe(1);
  expect(model.insight.ftpAvailable).toBe(false);
});
```

Use exact encoded labels from existing tests if needed.

**Step 2: Verify RED**

Run:

```bash
cd frontend
npm run test -- src/features/pnl/pnlByBusinessPageModel.test.ts -t "true-zero ADB"
```

Expected: fails because `zeroAdbCount` does not exist and/or zero still contributes to `missingAdbCount`.

**Step 3: Implement model fields**

In `PnlByBusinessInsightModel`, add:

```ts
zeroAdbCount: number;
```

In YTD model building:

```ts
const resolvedAdbValues = input.parentYtdRows
  .filter(hasYtdBusinessActivity)
  .map((row) =>
    input.adbAvgByBusinessType
      ? resolveAdbAvgYuan(row.business_type, input.adbAvgByBusinessType)
      : undefined,
  );
const missingAdbCount = resolvedAdbValues.filter((adb) => adb === undefined).length;
const zeroAdbCount = resolvedAdbValues.filter((adb) => adb === 0).length;
const ftpAvailable = missingAdbCount === 0 && zeroAdbCount === 0 && input.parentYtdRows.length > 0;
```

Return `zeroAdbCount` in `insight`.

For non-YTD branches, set `zeroAdbCount: 0`.

**Step 4: Update status copy logic**

In `buildPnlByBusinessRecommendedDrilldown`, choose priority in this order:

1. `missingAdbCount > 0`: current missing ADB copy.
2. `zeroAdbCount > 0`: new zero-denominator copy, for example:
   - `priorityLabel: "日均为0"`
   - `dimensionLabel: "日均分母"`
   - `actionLabel: "先确认 ADB 为真实零，再查看损益贡献；收益率/FTP 暂不计算"`
   - `evidenceLabel: "日均为0 N 项"`
3. current FTP-ready copy.

Keep annualized/FTP math guarded by `adb <= 0`.

**Step 5: Verify GREEN**

Run:

```bash
cd frontend
npm run test -- src/features/pnl/pnlByBusinessPageModel.test.ts
```

Expected: all page model tests pass.

## Task 4: Fix Page Display For True Zero

**Files:**
- Modify: `frontend/src/features/pnl/PnlByBusinessPage.tsx`
- Modify or add tests in: `frontend/src/test/PnlRoutesSmoke.test.tsx` only if page-level assertions are stable.

**Step 1: Update display-only conditions**

Change display checks from `adbAvg !== undefined && adbAvg > 0` to `adbAvg !== undefined` where the cell is only displaying the ADB balance:

```ts
const avgDisplay = adbAvg !== undefined ? formatAdbAvgYiCell(adbAvg) : "-";
```

Keep calculation helpers unchanged where they correctly reject `avgBalance <= 0`.

Specific spots to inspect:

- `frontend/src/features/pnl/PnlByBusinessPage.tsx` parent row display around `resolveAdbAvgYuan`.
- Selected business cards that currently show "缺日均" when `avgBalance <= 0`.
- Footer ADB display: use a separate `hasAnyAdb` flag so all-zero covered rows display `0.00`, while all-missing rows display `-`.

**Step 2: Add page-level test only if stable**

If `PnlRoutesSmoke.test.tsx` can cheaply inject an ADB comparison payload with `avg_balance: 0`, add:

```ts
expect(screen.getByTestId("pnl-by-business-ytd-table")).toHaveTextContent("0.00");
expect(screen.getByTestId("pnl-by-business-insight")).toHaveTextContent("日均为0");
expect(screen.getByTestId("pnl-by-business-insight")).not.toHaveTextContent("缺日均 1 项");
```

If the route smoke setup is too broad or flaky, skip this page-level assertion and rely on model/helper tests plus typecheck.

**Step 3: Verify**

Run:

```bash
cd frontend
npm run test -- PnlRoutesSmoke.test.tsx -t "true zero"
```

If no page-level test was added, run the full route smoke instead:

```bash
cd frontend
npm run test -- PnlRoutesSmoke.test.tsx
```

## Task 5: Fix Export Display For True Zero

**Files:**
- Modify: `frontend/src/features/pnl/pnlByBusinessExport.ts`
- Modify: `frontend/src/features/pnl/pnlByBusinessExport.test.ts`

**Step 1: Write failing export test**

Add a test that builds a YTD sheet with an ADB map containing a direct `0` for a row and asserts:

- the ADB cell is `0`, not `null`.
- annualized yield cell is `null`.
- FTP yield cell is `null`.

**Step 2: Verify RED**

Run:

```bash
cd frontend
npm run test -- src/features/pnl/pnlByBusinessExport.test.ts -t "true zero"
```

Expected: ADB cell currently becomes `null` because export checks `adb > 0`.

**Step 3: Implement export fix**

Change display-only export cells from:

```ts
adb !== undefined && adb > 0 ? adb / YUAN_PER_YI : null
```

to:

```ts
adb !== undefined ? adb / YUAN_PER_YI : null
```

For parent footer, track `hasAnyAdb` separately from `adbSum > 0`.

Keep annualized and FTP calculations unchanged so zero denominator still returns `null`.

**Step 4: Verify GREEN**

Run:

```bash
cd frontend
npm run test -- src/features/pnl/pnlByBusinessExport.test.ts
```

Expected: all export tests pass.

## Task 6: Full Verification

Run from `frontend/`:

```bash
npm run test -- src/features/pnl/zqtzAdbAvgRollup.test.ts
npm run test -- src/features/pnl/pnlByBusinessPageModel.test.ts
npm run test -- src/features/pnl/PnlByBusinessPage.test.ts
npm run test -- src/features/pnl/pnlByBusinessExport.test.ts
npm run test -- src/features/pnl/pnlByBusinessAdbMap.test.ts
npm run test -- PnlRoutesSmoke.test.tsx
npm run debt:audit
npm run lint
npm run typecheck
npm run build
```

Expected:

- All targeted tests pass.
- `debt:audit` reports no growth over baseline.
- lint has 0 errors.
- typecheck exits 0.
- build exits 0.

## Task 7: Review And Report

Before final report:

- Confirm no backend/schema/monthly/accounting ADB files changed.
- Confirm all `avgBalance <= 0` guards remain only on denominator calculations, not on presence/display checks.
- Confirm `missingAdbCount` counts only `undefined`.
- Confirm `zeroAdbCount` is visible in tests and user-facing status copy.

Report:

- Root cause: downstream used `> 0` as both presence check and denominator-validity check.
- Fix: split presence from denominator validity.
- Remaining risk: business owner may decide `0` should still block a specific analytical recommendation, but it must no longer be labeled as missing ADB.
