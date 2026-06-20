# Cursor System Closure Wave 1 — Review Packet

**Date:** 2026-04-24  
**Execution:** Lead agent integrated six parallel Composer lanes (A–F) per `docs/prompts/cursor-parallel-system-closure-wave1.md`.  
**Note:** Initial integration skipped per-lane reviewer subagents; **§「Wave 1 follow-up — Spec + quality reviewers」** below records Composer subagent spec/code-quality passes for lanes B / D / E.

## Summary

- **Docs:** Added/expanded Wave 1 page contracts (`PAGE-BOND-001`, `PAGE-POS-001`, `PAGE-MKT-001`, tightened `PAGE-OPS-001`) and documentation-only bindings from routes/pages to metric/sample/test anchors in `metric_dictionary` / golden sample docs. No new golden JSON.
- **Frontend:** `/market-data` now surfaces `result_meta` (quality, vendor, fallback) on primary sections via new page-local components; `/operations-analysis` clarifies provenance (real vs preview vs static demos) and attaches `result_meta` text to live headline KPIs where applicable.
- **Constraints:** No schema/auth/queue changes, no new dependencies, `client.ts` not grown; debt audit passes.

## Child-agent lane summaries

| Lane | Role | Outcome |
|------|------|---------|
| **A** | Route vs `PAGE-*` gap audit (read-only) | Delivered live route inventory, existing contracts, missing contracts, priority-4 list, non-promotable placeholders/exclusions. **DONE** |
| **B** | `docs/page_contracts.md` | Wave 1 four routes documented; pytest docs **17 passed**. **DONE_WITH_CONCERNS:** pending items in §13.5 (ops) and §13.8 (market-data) for product alignment. |
| **C** | Metric dictionary + golden sample docs | Binding tables + gaps; golden capture-ready **2 passed** (minimal subset). **DONE** |
| **D** | Market data page closure | New `LiveResultMetaStrip`, `MacroLatestReadinessBanner`; tests **8/8**, debt **pass**. **DONE** |
| **E** | Operations analysis page closure | Provenance + `result_meta` on headlines; **9/9** tests, debt **pass**. **DONE_WITH_CONCERNS:** `Collapse` top margin removed (spacing slightly tighter); typography tradeoffs noted by implementer. |
| **F** | `client.ts` decomposition scout (read-only) | Top domain blocks, mock migration order, safest extraction, regression tests list. **DONE** |

## Changed files (git)

**Modified**

- `docs/page_contracts.md`
- `docs/metric_dictionary.md`
- `docs/golden_sample_catalog.md`
- `docs/golden_sample_plan.md`
- `frontend/src/features/market-data/pages/MarketDataPage.tsx`
- `frontend/src/features/market-data/components/NcdMatrix.tsx`
- `frontend/src/features/market-data/components/LinkageSpreadTenorTable.tsx`
- `frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx`
- `frontend/src/features/workbench/business-analysis/BusinessContributionTable.tsx`
- `frontend/src/test/MarketDataPage.test.tsx`
- `frontend/src/test/OperationsAnalysisPage.test.tsx`
- `frontend/src/test/OperationsAnalysisPage.governed.test.tsx`

**Untracked (new)**

- `docs/prompts/cursor-parallel-system-closure-wave1.md` (prompt artifact)
- `frontend/src/features/market-data/components/LiveResultMetaStrip.tsx`
- `frontend/src/features/market-data/components/MacroLatestReadinessBanner.tsx`

No overlapping writes between lanes; no manual conflict resolution required.

## Business root cause / category

Repeated closure work: **page contracts**, **metric/sample traceability**, and **visible governance metadata** (`result_meta`, mixed-source honesty) for high-traffic workbench pages without platform refactors.

## Validation commands and results (lead integration)

Repository root:

```powershell
python -m pytest tests/test_balance_analysis_docs_contract.py tests/test_backend_release_gate_docs.py tests/test_golden_samples_capture_ready.py::test_capture_ready_golden_sample_files_exist tests/test_golden_samples_capture_ready.py::test_capture_ready_golden_sample_metadata_is_in_expected_state -q
```

**Result:** `19 passed`

`frontend/`:

```powershell
npm run debt:audit
npm run test -- MarketDataPage
npm run test -- OperationsAnalysisPage
npm run typecheck
```

**Results:** Debt audit **passed** (no growth). MarketDataPage **8/8**. OperationsAnalysisPage **9/9** (including governed). **Typecheck:** `tsc --noEmit` **pass**.

Full `pytest tests/test_golden_samples_capture_ready.py` not run in integration pass; Agent C reported minimal subset green.

## Debt audit result

- `npm run debt:audit` **passed** (baseline: TSX style props 3281/3286, `client.ts` lines unchanged in intent — no growth).

## Unresolved ambiguities

- **Operations analysis:** Contract “must not answer” / first-screen scope vs current UI — flagged **pending-confirmation** in `page_contracts.md` (Agent B).
- **Market data:** Whether to split formal vs preview navigation — **pending** in contract; page remains **mixed-source** by design.
- **Liability analytics / parity matrix:** Agent A notes tension between `live` nav and `excluded`/503 narrative in `V2_V3_PARITY_MATRIX.md` — not resolved in this wave.
- **`GS-BOND-HEADLINE-A`:** Remains **blocked** per Agent C / plan.

## Remaining risks

- **UX:** Slightly reduced vertical gap after removing `Collapse` margin on operations page (Agent E).
- **Coverage:** Golden-sample full suite not executed in lead integration; expand if release gate requires it.
- **Copy density:** More `result_meta` text on KPIs may need product copy pass for brevity.

## Recommended Wave 2 tasks

- Extract small pure-mock blocks from `frontend/src/api/client.ts` per Agent F (ledger PnL mocks, Campisi structures, then macro `MOCK_*` blocks).
- Docs-contract tests: live routes → `PAGE-*` completeness; `PAGE-*` → metric dictionary references.
- Promote `GS-BOND-HEADLINE-A` only after bond dashboard contract, metric/GAP closure, an on-disk `tests/golden_samples/GS-BOND-HEADLINE-A/` package, and capture-ready gate registration are review-ready.
- One-page closure continuation: `/ledger-pnl`, `/average-balance`, `/liability-analytics`, `/cashflow-projection`, `/concentration-monitor` (per prompt §6).

## Files intentionally not touched

- Database, auth, queue/scheduler/cache layers, backend calculation logic, shared API client architecture.
- `frontend/src/api/client.ts` (no extraction in this wave).
- New golden sample JSON files.
- `TenorConcentrationPanel` and other out-of-scope workbench sections (only called out in copy on operations page).

---

## Wave 1 follow-up — Spec + quality reviewers (lanes B / D / E)

**When:** Same calendar day, after parallel implementers. **Model:** Composer (`composer-2-fast`). **Mode:** read-only review subagents.

### Lane B — `docs/page_contracts.md`

| Gate | Verdict | Summary |
|------|---------|---------|
| **Spec compliance** | **SPEC GAPS** | §13.7 missing `generated_at` in time semantics; §13.8 status section thin vs §13.5; §13.6 optional sections unclear; §13.8 missing explicit forbidden block; §13.5 `MTR-BAL-001`–`103` range notation imprecise vs dictionary. **(Remediated 2026-04-24):** `metric_dictionary` §12.5 / `golden_sample_catalog` §5.2 / `golden_sample_plan` §7.4 now align `PAGE-BOND/POS/MKT-001` with explicit metric/sample GAPs; `page_contracts` §13.6 H no longer implies `GS-BOND-HEADLINE-A` on-disk. |
| **Doc quality** | **QUALITY ISSUES** | **P0:** fix metric_dictionary ↔ page_contracts cross-authority in same PR or immediate follow-up. **P1:** add §13.7 `generated_at`; replace imprecise MTR-BAL range with explicit list or scoped wording. **P2:** template symmetry (optional/forbidden), §13 markdown heading levels (13 vs 13.5), §2 “9 pages” mental model note. |

### Lane D — `/market-data` frontend

| Gate | Verdict | Summary |
|------|---------|---------|
| **Spec compliance** | **SPEC GAPS** | **P1:** curve tab (`latestQuery`) no `isError` branch — failure can look like empty data; Banner does not cover that path. **P2:** linkage tab weaker `LiveResultMetaStrip` vs spreads; some primary tables lack meta strip; tests missing Banner edge cases and curve error. |
| **Code quality** | **QUALITY ISSUES** | **P0:** same curve error/empty conflation. **P1:** `MarketDataPage.tsx` size/complexity; duplicated `formatCorrelation` (`LinkageSpreadTenorTable` vs page — `"—"` vs `"不可用"`). **P2:** tests need error/vendor_stale/fallback branches; EN/ZH copy mix (`Retry` in `NcdMatrix`); Tab `forceRender` cost (**P3**). |

### Lane E — `/operations-analysis` frontend

| Gate | Verdict | Summary |
|------|---------|---------|
| **Spec compliance** | **SPEC COMPLIANT** | **P2 only:** unreachable assertions after early `return` in `OperationsAnalysisPage.test.tsx` (~605–618); `style=` baseline needs diff check; optional extra `result_meta` in balance formal `AsyncSection`. |
| **Code quality** | **QUALITY ISSUES** | Dead test block (**605–618**); repeated provenance ternary pattern (helper candidate); `formatResultMetaProvenance` / optional chaining edge cases (~1345); large commented block (~1055–1096); table/page inline style debt; duplicated test harness between `.test` and `.governed.test`. |

### Suggested fix order (for implementer, not done in review pass)

1. **Docs P0:** Align `metric_dictionary.md` §12.5 / Wave 1 table rows with existing `PAGE-*` in `page_contracts.md`.
2. **D P0:** Curve tab explicit error UI + narrow test (failed `getChoiceMacroLatest`).
3. **B P1/P2:** Contract template gaps (`generated_at`, status symmetry, forbidden/optional, MTR list).
4. **E P2:** Remove or fix dead test code; optionally dedupe `formatCorrelation` / provenance helper.

---

**Packet path:** `docs/plans/2026-04-24-cursor-system-closure-wave1-review-packet.md`
