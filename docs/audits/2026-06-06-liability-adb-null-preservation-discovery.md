# Liability ADB Null Preservation Discovery

## Scope

Approved Ralph execution for Phase B of `.omx/plans/2026-06-06-wrapper-hardening-and-liability-adb-null-preservation-consensus.md`.

Goal: determine whether one missing-average-balance field family can be safely fixed in this slice without overlapping existing dirty hunks or triggering a broad shared ADB contract migration.

## MCP Evidence Status

Project-specific MCP tools requested by `AGENTS.md` were not exposed in this Codex App session:
- `moss-metric-contracts`
- `moss-lineage-evidence`
- `moss-data-catalog`
- `gitnexus`

Fallback evidence used:
- local contract types in `frontend/src/api/contracts.ts`
- local normalization code in `frontend/src/api/liabilityAdbClient.ts`
- local consumers and tests under `frontend/src/features/**` and `frontend/src/test/**`

Residual risk: field semantics still need governance/lineage confirmation before a shared nullable contract migration.

## Dirty Worktree Gate

Preflight commands were run:
- `git status --short`
- `git diff -- frontend/src/api/contracts.ts frontend/src/features/average-balance/components/AverageBalanceView.tsx frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx`
- `git diff --name-only`

Relevant dirty files:
- `frontend/src/api/contracts.ts`
- `frontend/src/features/average-balance/components/AverageBalanceView.tsx`
- `frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx`

Observed dirty hunk relevance:
- `frontend/src/api/contracts.ts` is dirty outside the ADB type block, but any nullable ADB migration still requires editing the same shared contract file.
- `frontend/src/features/average-balance/components/AverageBalanceView.tsx` is dirty in ADB `avg_balance`/YoY handling near the comparison-family consumer path.
- `frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx` is dirty in null-aware liability aggregation helpers.

Gate result: implementation is not allowed in this slice because the candidate fixes require shared ADB numeric nullability and consumer changes across dirty shared files.

## Field-Family Matrix

| Field family | Contract type | Normalization site | Consumers | Current missing-state behavior | True-zero behavior | Minimal closure path | Go/No-Go |
| --- | --- | --- | --- | --- | --- | --- | --- |
| comparison `avg_balance` | `AdbCategoryItem.avg_balance: number` at `frontend/src/api/contracts.ts` | `Number(row.avg_balance ?? 0)` at `frontend/src/api/liabilityAdbClient.ts` | `AverageBalanceView.tsx` direct table render/sort/chart math; `AdbAnalyticalPreview.tsx` deviation math; liability page maps values through `numericToYiNumeric(x.avg_balance ?? null)` after client coercion | Missing becomes `0`, then renders/sorts/calculates as real zero | Real `0` remains `0` | Change contract to nullable, update client, update average-balance and balance-analysis preview math/render tests | NO-GO: shared contract migration plus dirty consumer overlap |
| accounting-basis `daily_avg_balance` | `AdbAccountingBasisDailyAvgItem.daily_avg_balance: number` at `frontend/src/api/contracts.ts` | `Number(row.daily_avg_balance ?? 0)` at `frontend/src/api/liabilityAdbClient.ts` | `AdbAccountingBasisSection.tsx` divides by `YI`; `AdbAccountingBasisTrendChart.tsx` divides by `YI`; `AverageBalanceView.tsx` passes snapshot/trend through | Missing becomes `0` and chart/table treat it as zero balance | Real `0` remains `0` | Change item contract to nullable, update client, update section/chart null rendering and tests | NO-GO: shared contract migration and multiple consumer updates |
| monthly breakdown `avg_balance` | `AdbMonthlyBreakdownItem.avg_balance: number` at `frontend/src/api/contracts.ts` | `Number(breakdown.avg_balance ?? 0)` at `frontend/src/api/liabilityAdbClient.ts` | `AverageBalanceView.tsx` monthly totals, table rows, chart rows; `AdbMonthlyHorizontalChart.tsx` assumes numeric `avgYi`; `AdbMonthlyBreakdownTable.tsx` receives numeric rows | Missing becomes `0`, affects totals and chart/table display | Real `0` remains `0` | Change monthly breakdown contract to nullable and update aggregation/chart/table tests | NO-GO: broad monthly consumer changes |
| YTD / total average fields | `AdbComparisonResponse.total_avg_*: number`, `AdbMonthlyResponse.ytd_avg_*: number` at `frontend/src/api/contracts.ts` | `Number(raw.total_avg_* ?? 0)` and `Number(raw.ytd_avg_* ?? 0)` at `frontend/src/api/liabilityAdbClient.ts` | `AverageBalanceView.tsx` deviation cards and YTD stats; `AdbAnalyticalPreview.tsx` cards and preview rows | Missing becomes `0`, can become a headline metric | Real `0` remains `0` | Needs explicit backend contract decision: totals may be structural zero or missing aggregate | NO-GO: semantics ambiguous without MCP/governance confirmation |

## Decision

Phase B stops after discovery. No frontend implementation was performed.

Rationale:
- Every candidate family requires changing non-null shared ADB contract fields to nullable or adding equivalent nullable display handling downstream.
- The highest-priority family, comparison `avg_balance`, overlaps existing dirty ADB consumer work in `AverageBalanceView.tsx`.
- Accounting-basis `daily_avg_balance` is not isolated either; its chart and section consumers directly divide by the value.
- YTD/total fields may be structural aggregates, so changing them without metric-governance evidence risks reclassifying true zero/missing incorrectly.

## Follow-Up Plan

1. Use project MCP/governance tools when available to confirm null semantics for ADB category, accounting-basis, monthly, and YTD/total fields.
2. Create a dedicated shared-contract migration plan for `frontend/src/api/contracts.ts` ADB numeric fields.
3. Close one family per slice with TDD:
   - comparison `avg_balance` first, because it is the user-visible missing-average-balance defect and feeds both average-balance and balance-analysis preview.
   - accounting-basis `daily_avg_balance` second, because it needs chart/table null rendering.
   - monthly breakdown and YTD/total fields only after aggregate semantics are confirmed.
4. For each slice, write RED tests that assert missing stays unavailable/dash and true zero stays zero, then update client and consumers minimally.
