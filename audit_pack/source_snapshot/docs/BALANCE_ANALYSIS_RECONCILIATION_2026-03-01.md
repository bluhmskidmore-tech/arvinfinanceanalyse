# Balance Analysis Reconciliation (2026-03-01)

## Boundary note（与阶段授权对齐）

- 本文记录的是 **2026-03-01** 一次**对账切片**的结论，用于证明当时 governed workbook **已支持 section** 与参考表之间的数值一致性。
- **不等于**参考 Excel 全簿 1:1 完成，**也不等于**仓库整体进入 `Phase 2` 或正式金融全域交付。阶段边界应通过 `AGENTS.md` -> `docs/DOCUMENT_AUTHORITY.md` -> `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md` 查阅。
- 后续若仅存在局部 lane（如 `zqtz / tyw` formal-balance）的 dated execution update，其授权**只作用于被点名的工作流**，不得解释为 repo-wide Phase 2 cutover。

## Purpose

This document records the reconciliation status between:

- source input `C:/Users/arvin/Desktop/ZQTZSHOW-20260301.xls`
- source input `C:/Users/arvin/Desktop/TYWLSHOW-20260301.xls`
- reference workbook `C:/Users/arvin/Desktop/资产负债分析_20260301_1.xlsx`
- current governed `balance-analysis` implementation in this repo

The goal is not to restate the workbook. The goal is to show what has been proven to match, what was corrected during reconciliation, and what still has a measurable residual.

## Controlled Assumption

For this reconciliation run only, FX was injected using the workbook literal:

- `USD/CNY = 7.24`

This was used as a temporary compare harness input, not as a permanent formal-FX source change.

## Root Causes Identified And Resolved

1. Workbook general analysis pages use `native` balance amounts, not globally FX-converted `CNY` amounts.
2. Currency split is the exception and intentionally uses FX-converted `CNY`.
3. `发行类债券` must be classified from real `ZQTZSHOW` source fields, not only from `业务种类` text.
4. `同业存放` must be treated as liability-side in `TYWLSHOW`.
5. Business-type duration must ignore rows with missing maturity and rows already matured before report date.
6. Campisi benchmark must use `政策性金融债` only.

## Reconciled Results

### Summary Cards

These values are aligned with the workbook:

| Metric | System | Workbook | Delta |
| --- | ---: | ---: | ---: |
| 债券资产(剔除发行类) | 32877980.959254 | 32877980.959254 | 0 |
| 同业资产 | 2379161.576545 | 2379161.576545 | ~0 |
| 同业负债 | 6133682.553610 | 6133682.553610 | 0 |
| 发行类负债 | 12127674.825769 | 12127674.825769 | 0 |
| 净头寸 | 29123459.982189 | 29123459.982189 | ~0 |

### Bond Business Types

The following sample rows are aligned on amount:

| Bond Type | System | Workbook | Delta |
| --- | ---: | ---: | ---: |
| 政策性金融债 | 6482200 | 6482200 | 0 |
| 其他 | 5545276.520454 | 5545276.520454 | 0 |
| 固定计息规模 | 32874418.154254 | 32874418.154254 | 0 |

### Ratings

The following rating balances are aligned:

| Rating | System | Workbook | Delta |
| --- | ---: | ---: | ---: |
| AAA | 16960854.1122 | 16960854.1122 | 0 |
| 无评级(利率债等) | 13498333.886754 | 13498333.886754 | 0 |

### Industry Distribution

Industry distribution balances and counts are aligned for checked rows. During reconciliation, no material industry-balance mismatch remained after switching workbook general pages to `native` basis.

### Counterparty Types

Counterparty net-position direction and amounts are aligned for checked rows, including:

- `代客理财项目`
- `股份制银行`
- `国有银行`
- `城市商业银行`

### Campisi

Campisi spread outputs are aligned for checked rows:

| Metric | System | Workbook | Delta |
| --- | ---: | ---: | ---: |
| 政策性金融债 spread bp | 0 | 0 | 0 |
| 信用债券-企业 spread bp | 58.33151799876219 | 58.33151799876215 | negligible |
| 信用债券-企业 spread income | 28017.097665275315 | 28017.09766527529 | negligible |

### Maturity Gap

The maturity-gap table was verified after reconciliation and bucket-level deltas were reduced to rounding noise for:

- bucket amounts
- gap amounts
- weighted asset/liability rates

## Weighted Term Convention (Resolved)

Previously a tiny residual appeared on `其他` 加权期限(年):

| Metric | System (before fix) | Workbook | Delta |
| --- | ---: | ---: | ---: |
| `其他` weighted term (业务种类页) | 4.497542197779638 | 4.497201648705183 | 0.000340549074455 |

**Evidence (not hand-waving):** A full parse of `C:/Users/arvin/Desktop/ZQTZSHOW-20260301.xls` was used to rebuild the157-row `其他` asset cohort (same issuance / maturity filters as production). Weighted averages were recomputed under several day-count hypotheses:

- `sum(face * (days-1) / 365) / sum(face)` reproduces the **old** system value exactly (delta ~ 0 vs old code).
- `sum(face * days / 365.25) / sum(face)` reproduces the **workbook** literal **to machine precision** (delta ~ `1e-15`, i.e. double noise only).

So the workbook column is **elapsed calendar days divided by 365.25**, not `(days-1)/365`. The implementation in `balance_analysis_workbook._optional_remaining_years` was updated accordingly. **Maturity-gap buckets** still use `_remaining_years` (`days/365`) and were intentionally left unchanged.

## What Was Verified

Commands run during this reconciliation slice:

```powershell
pytest tests/test_balance_analysis_contracts.py tests/test_balance_analysis_core.py tests/test_balance_analysis_materialize_flow.py tests/test_balance_analysis_api.py tests/test_balance_analysis_service.py tests/test_balance_analysis_boundary_guards.py tests/test_balance_analysis_workbook_contract.py -q
pnpm --dir F:\MOSS-V3\frontend test -- BalanceAnalysisPage ApiClient
pnpm --dir F:\MOSS-V3\frontend typecheck
pytest tests -q
```

Observed results:

- balance-analysis backend tests: pass
- affected frontend tests: pass
- frontend typecheck: pass
- full `pytest tests -q`: pass

Fresh full-suite evidence:

```text
314 passed in 165.20s (0:02:45)
```

## Current Status

当前对账结论仅覆盖当前 governed workbook 已支持的 section，
不等于 `资产负债分析_20260301_4.xlsx` 全量 1:1 对齐完成。

Current balance-analysis reconciliation status for `2026-03-01`:

- workbook summary: aligned
- business-type balances: aligned
- business-type **加权期限** (365.25-day basis): aligned with workbook after `_optional_remaining_years` fix
- ratings: aligned
- industry balances: aligned
- counterparty net positions: aligned
- Campisi spread metrics: aligned

## Next Step

Closeout: re-run the verification block in this doc after any future workbook-side formula change; if a new residual appears, isolate with the same cohort-level day-count sweep before touching amounts or scope filters.
> 2026-04-17 status update:
> This reconciliation note remains valid as a historical compare slice, but its old boundary wording is superseded.
> The active repository interpretation is now `repo-wide Phase 2 (通用正式计算)` for the governed formal-compute mainline, with explicit exclusions for `executive.*`, Agent, and preview/vendor/analytical-only surfaces.
> Use `AGENTS.md`, `docs/DOCUMENT_AUTHORITY.md`, and `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md` as the current navigation path for boundary interpretation; use `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md` as the cutover-definition reference.
> 2026-04-17 status update:
> This reconciliation note remains valid as a historical compare slice, but its old boundary wording is superseded.
> The active repository interpretation is now `repo-wide Phase 2 (通用正式计算)` for the governed formal-compute mainline, with explicit exclusions for `executive.*`, Agent, and preview/vendor/analytical-only surfaces.
> Use `AGENTS.md`, `docs/DOCUMENT_AUTHORITY.md`, and `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md` as the current navigation path for boundary interpretation; use `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md` as the cutover-definition reference.
