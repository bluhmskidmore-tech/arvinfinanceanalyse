# Institutional Frontend Scorecard

**Date:** 2026-06-05

> Historical snapshot. For current `/product-category-pnl` approval and owner-review counts, defer to `docs/audits/2026-06-06-top-investment-bank-certification-board.md` and the generated PnL packets. Current machine truth is `approval_action_item_count=15`, `closure_blocker_triage.blocker_count=15`, and `next_review_queue_item_count=4`; older 13/14 action-item counts below are retained as 2026-06-05 evidence only.

**Scope:** `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, `/bond-analysis`.

**Standard:** `docs/frontend-institutional-standard.md`.

## Verdict

The audited flagship scope is page-surface ready and continues to move toward the stricter top investment-bank certification bar.

This verdict is frontend-surface scoped. It does not retire governance markers, change metric definitions, certify unaudited routes, or complete MCP-backed business-contract certification.

Gate I business-contract work has started for `/ledger-pnl`. Local MCP stdio calls collected metric-contract, lineage, catalog/date, direct-record blocker-routing, and preflight-candidate evidence. The candidate record is now field-complete with `cache_key=ledger_pnl.summary:2026-05-31:ALL` and preflights as `ready_for_audit_review`; the sign-off packet, governance audit packet, owner evidence packet, business-owner approval template, and strict readiness checker are wired. The checker now validates the reviewed packet paths and the existence of those artifacts before any captured approval can pass. `/ledger-pnl` remains `evidence-pending` rather than `business-contract-certified` because validation still finds no written direct page/API governance record, no expanded anchor records, no manual audit review closure, no dedicated summary golden sample, and no captured business-owner approval.

Gate I evidence has also been collected for `/pnl-attribution`. Its current readiness is stronger than `not-started`: catalog/date evidence samples all five configured tables, direct governance-record validation is ready for audit review with one direct record and twenty expanded anchor records, and the business-owner approval lane is machine-checkable. `/pnl-attribution` still remains `evidence-pending` because manual audit checks, candidate-boundary acceptance, and captured business-owner approval are not complete.

Gate I boundary review has now identified `/bond-analysis` as a route-specific gap rather than a generic `not-started` item. The browser surface remains `frontend-ready`, and `python scripts/codex_page_readiness.py --page-slug bond-analysis` now exposes a direct route-specific readiness lane: `page_id=GAP-BOND-ANALYSIS-PAGE`, `overall_status=static-pass`, `approval_status=gap_or_observational`, `formal_use_allowed=false`, and `golden_samples=[]`. This is gap evidence only. `PAGE-BOND-001` and `GS-BOND-HEADLINE-A` belong to `/bond-dashboard` and must not be borrowed to certify BondAnalyticsView.

Gate J route-scope classification is now machine-checkable through `python scripts/codex_page_readiness.py --route-scope` and documented in `docs/audits/2026-06-06-route-scope-classification.md`. The current scope classifies 39 routes: `business-contract-certified=0`, `evidence-pending=12`, `gate-i-gap=2`, `frontend-ready=5`, `frontend-only=10`, `not-started=10`, `out-of-scope=0`, and `unclassified=0`. This explicitly prevents the seven-route frontend score from expanding into a whole-system or business-certification claim.

## Scorecard

| Route | Business trust | First-screen closure | Visual hierarchy | Responsive resilience | Accessibility/keyboard | Token alignment | Runtime cleanliness | Total | Level |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `/cross-asset` | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 28/28 | Flagship-ready |
| `/ledger-pnl` | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 28/28 | Flagship-ready |
| `/macro-toolkit` | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 28/28 | Flagship-ready |
| `/stock-analysis` | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 28/28 | Flagship-ready |
| `/product-category-pnl` | 4 | 3 | 4 | 4 | 4 | 4 | 4 | 27/28 | Flagship-ready |
| `/pnl-attribution` | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 28/28 | Flagship-ready |
| `/bond-analysis` | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 28/28 | Flagship-ready |

## Gate J Route Scope

Source of truth: `docs/audits/2026-06-06-route-scope-classification.md`.

| Classification | Count | Routes |
| --- | ---: | --- |
| `business-contract-certified` | 0 | none |
| `evidence-pending` | 12 | `product-category-pnl`, `balance-analysis`, `balance-movement-analysis`, `pnl`, `ledger-pnl`, `pnl-by-business`, `pnl-attribution`, `pnl-bridge`, `risk-tensor`, `bond-dashboard`, `positions`, `cube-query` |
| `gate-i-gap` | 2 | `bond-analysis`, `stock-analysis` |
| `frontend-ready` | 5 | `dashboard-home`, `operations-analysis`, `liability-analytics`, `market-data`, `macro-toolkit` |
| `frontend-only` | 10 | `executive-overview`, `executive-summary`, `executive-pnl-attribution`, `macro-observation`, `agent`, `portfolio-home`, `market-home`, `risk-home`, `performance-home`, `reports-home` |
| `not-started` | 10 | `cross-asset`, `team-performance`, `decision-items`, `platform-config`, `average-balance`, `bank-ledger-dashboard`, `concentration-monitor`, `cashflow-projection`, `kpi-performance`, `news-events` |
| `out-of-scope` | 0 | none |

## Business-Contract Status

| Route | Frontend surface | Gate I business-contract status | Evidence |
| --- | --- | --- | --- |
| `/ledger-pnl` | `frontend-ready` | `evidence-pending` | MCP trace, lineage, and catalog/date evidence captured in `docs/audits/2026-06-05-ledger-pnl-gate-i-mcp-evidence.json`; direct-record blocker routed in `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-blocker.json`; preflight candidate captured in `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json`; source/golden boundary captured in `docs/audits/2026-06-05-ledger-pnl-source-anchor-golden-boundary.json`; latest closure status captured in `docs/audits/2026-06-05-ledger-pnl-governance-closure-status.json`. The candidate now includes `cache_key=ledger_pnl.summary:2026-05-31:ALL` and preflights as `ready_for_audit_review`; `docs/pnl/ledger-pnl-sign-off-packet.md`, `docs/pnl/ledger-pnl-governance-audit-packet.md`, `docs/pnl/ledger-pnl-owner-evidence-packet.md`, `docs/pnl/ledger-pnl-business-owner-approval-template.md`, and `scripts/check_ledger_pnl_business_owner_approval.py` expose the pending approval lane through readiness. The checker validates reviewed packet paths and artifact existence, then still reports `approval_status=pending`, `business_owner_approval_captured=false`, and 11 action items. Latest dry-run still reports `record_write_status=not_requested` and `existing_record_line=null`. Not certified because direct record validation still reports missing written direct records/expanded lineage, no dedicated summary golden sample, and no written record/manual review/captured business-owner approval. |
| `/cross-asset` | `frontend-ready` | `not-started` | Gate J now classifies this visible navigation route as `not-started` because it has no seeded trace bundle in the current readiness ledger. Browser evidence may support frontend readiness, but it does not create page contract, metric dictionary, golden sample, governance, or approval evidence. |
| `/macro-toolkit` | `frontend-ready` | `frontend-ready` | Gate J classifies this as an analytical/tooling surface with run-supported frontend readiness. It is not formal business truth and remains outside business-contract certification until a direct certification lane exists. |
| `/stock-analysis` | `frontend-ready` | `gate-i-gap` | Gate J classifies this as `gate-i-gap`: it has a route-specific gap lane and must not turn observations into trading-instruction or formal metric claims without a standalone page contract, metric dictionary rows, governance evidence, golden samples, and owner approval. |
| `/product-category-pnl` | `frontend-ready` | `evidence-pending` | Gate I boundary captured in `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json`. Readiness reports `overall_status=static-pass`, `approval_status=formal_or_governed`, `formal_use_allowed=true`, catalog/date samples `2/2` configured tables, governance validation reports `direct_records_ready_for_audit_review`, `direct_record_count=1`, and `expanded_anchor_record_count=20`. `docs/pnl/product-category-pnl-first-certification-packet.md` now packages the `MTR-PCP-001` through `MTR-PCP-012` source-to-screen trace for owner review. The business-owner approval lane is machine-checkable through `docs/pnl/product-category-pnl-business-owner-approval-template.md` and `scripts/check_product_category_pnl_business_owner_approval.py`; the historical 2026-06-05 output reported `approval_status=pending`, `business_owner_approval_captured=false`, and 14 owner-action items, while the current board reports 15 action items and remains the active source of truth. The checker directly reads `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` and `docs/pnl/product-category-closure-checklist.md`: it requires `Status: approved` plus non-placeholder owner, approver, and approval date, and a closure checklist with no `PARTIAL` or `NOT_TRUSTED` units before `--require-captured` can pass. Template-only reconciliation cannot capture approval. Not certified because `closure_approved=false`, audit review still requires page contract, catalog/date, lineage freshness, UI/API payload, live-smoke, and business-owner approval checks; `python scripts/codex_page_readiness.py --page-slug product-category-pnl` exposes `golden_sample_approval_artifact_mismatch=true` because `GS-PROD-CAT-PNL-A/approval.md` says `captured-awaiting-approval` with owner/approver/approved_at as `TBD` while readiness shows the golden boundary as approved; the closure checklist still has ten `PARTIAL` units; and the liability fallback branch now requires model-boundary review rather than synthetic browser proof. |
| `/pnl-attribution` | `frontend-ready` | `evidence-pending` | Gate I boundary captured in `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json`. Readiness reports `overall_status=static-pass`, catalog/date samples `5/5` configured tables, governance validation reports `direct_records_ready_for_audit_review`, `direct_record_count=1`, and `expanded_anchor_record_count=20`. Dry-run governance generation locates existing record line `5403` for `cache_key=pnl-attribution:volume-rate:2026-04-30:mom` and keeps `record_write_status=not_requested`. `docs/pnl/pnl-attribution-owner-evidence-packet.md` now packages the owner-facing candidate boundary, dry-run governance status, catalog/date tables, DTO-only golden-sample boundary, and 11 approval action items; the approval template validates this packet path before captured approval. Not certified because `GS-PNL-ATTR-WB-A` is primary workbench DTO evidence only, advanced/Campisi/full-page surfaces remain out of scope, `formal_use_allowed=false`, `closure_approved=false`, manual audit checks remain required, and business-owner approval is pending with 11 action items. |
| `/bond-analysis` | `frontend-ready` | `gate-i-gap` | Boundary gap captured in `docs/audits/2026-06-05-bond-analysis-gate-i-boundary-gap.json`. Browser evidence remains clean at desktop `1440px`, tablet `768px`, and mobile `390px`. `python scripts/codex_page_readiness.py --page-slug bond-analysis` now returns `overall_status=static-pass`, `page_id=GAP-BOND-ANALYSIS-PAGE`, `approval_status=gap_or_observational`, `formal_use_allowed=false`, and no golden samples. The smoke and verification wrappers are wired for this route, but no direct catalog/date evidence, governance-record validation, audit review, golden-sample approval, or business-owner approval exists yet. `PAGE-BOND-001`, `GS-BOND-HEADLINE-A`, and `MTR-BOND-001` through `MTR-BOND-004` are `/bond-dashboard` evidence, not `/bond-analysis` certification. Not certified because direct `/bond-analysis` page contract closure, golden-sample boundary, governance validation, manual audit review, and business-owner approval are missing. |

## Certification Ledger

Allowed claim: the seven-route frontend surface is flagship-ready; business-contract certification and wider route scope remain open.

Forbidden claim: MOSS, or any individual route below, has reached full top investment-bank business certification unless the `Final claim status` column says `certified`.

| Route | Frontend surface | Gate I evidence | Golden-sample scope | Governance record | Manual audit review | Business-owner approval | Final claim status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/cross-asset` | `frontend-ready` | `not-started`; visible navigation route has no seeded trace bundle in Gate J | `not-collected` | `not-collected` | `not-started` | `not-started` | `not-started` |
| `/ledger-pnl` | `frontend-ready` | `evidence-pending`; MCP trace, dry-run preflight, sign-off packet, audit packet, and owner evidence packet captured | `missing`; no dedicated ledger summary sample for `MTR-LPN-001..003` | `missing-written-direct-record`; dry-run only | `open`; direct/expanded lineage and payload review pending | `pending`; checker validates packet artifacts and reports captured=false with 11 action items | `evidence-pending` |
| `/macro-toolkit` | `frontend-ready` | `frontend-ready`; analytical/tooling surface, not formal business truth | `not-collected` | `not-collected` | `not-started` | `not-started` | `frontend-ready` |
| `/stock-analysis` | `frontend-ready` | `gate-i-gap`; route-specific observational lane, no PAGE-STOCK certification closure | `missing` | `missing` | `not-started` | `not-started` | `gate-i-gap` |
| `/product-category-pnl` | `frontend-ready` | `evidence-pending`; readiness reports formal/governed evidence and direct-record readiness; first-certification packet covers 12 trace rows | `mismatch-open`; readiness now exposes `golden_sample_approval_artifact_mismatch=true` for `GS-PROD-CAT-PNL-A` | `ready-for-audit-review`; direct=1 and expanded=20 in readiness evidence | `open`; closure checklist and fallback branch proof remain | `pending`; historical checker output reported captured=false with 14 owner-action items, while the current board reports 15 action items and validates the first-certification packet path | `evidence-pending` |
| `/pnl-attribution` | `frontend-ready` | `evidence-pending`; catalog/date 5/5, direct-record readiness, and owner evidence packet captured | `limited`; `GS-PNL-ATTR-WB-A` covers primary workbench DTO only | `ready-for-audit-review`; existing record line 5403 located in dry-run | `open`; advanced/Campisi/full-page boundary and live-smoke review pending | `pending`; checker reports captured=false with 11 action items and validates the owner evidence packet path | `evidence-pending` |
| `/bond-analysis` | `frontend-ready` | `gate-i-gap`; route-specific readiness lane now exposes `GAP-BOND-ANALYSIS-PAGE`, `gap_or_observational`, `formal_use_allowed=false`, and no golden samples | `missing`; `/bond-dashboard` sample is non-reusable | `missing`; readiness lane has no direct governance-record validation evidence | `not-started`; direct route contract closure and fixed-income metric review missing | `not-started`; no direct approval lane | `gate-i-gap` |

## Evidence

### Gate H Accessibility

- Shared shell skip path: `Skip to main content` now appears before shell navigation and moves focus to `#workbench-main-content`.
- Main landmark evidence: shell main content has `aria-label="Main content"` and `tabIndex="-1"` so keyboard users can bypass repeated chrome.
- Browser keyboard smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-keyboard'`: 7 passed across `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, `/stock-analysis`, `/product-category-pnl`, `/pnl-attribution`, and `/bond-analysis`.
- Route-owned business-control smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-route-focus'`: 7 passed across the same flagship routes. The test starts from the skip link, focuses `#workbench-main-content`, then Tabs into each route's own decision/control surface such as selectors, tabs, refresh/drill buttons, or disclosure summaries.
- Control context smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-control-context'`: 7 passed. This checks human-readable control names, visible focus presentation after keyboard navigation, and non-color state text across the audited routes.
- Full a11y smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1`: 39 passed, including route axe coverage, shared keyboard entry, route-owned focus traversal, and control-level context evidence.
- Residual scope note: this closes the automated Gate H browser evidence for the seven audited routes. Manual assistive-technology walkthrough remains useful before external release, but it is no longer the blocker for the frontend-surface score.

### `/cross-asset`

- Screenshots: `frontend/.codex-tmp/cross-asset-gate1-desktop-cascade-fixed.png`, `frontend/.codex-tmp/cross-asset-gate1-tablet-cascade-fixed.png`, `frontend/.codex-tmp/cross-asset-gate1-mobile-cascade-fixed.png`.
- Evidence note: prior Gate 1 browser pass recorded no document-level horizontal overflow and no route fallback in the latest verified pass.

### `/ledger-pnl`

- Screenshots: `frontend/.codex-tmp/ledger-pnl-gate2-desktop-final3.png`, `frontend/.codex-tmp/ledger-pnl-gate2-tablet-final3.png`, `frontend/.codex-tmp/ledger-pnl-gate2-mobile-final3.png`.
- Measurements: desktop audit strip about `377px`, tablet audit strip about `516px`, mobile audit strip about `505px`.
- Evidence note: targeted page tests, shell tests, live-route tests, lint, typecheck, debt audit, and build passed in Gate A.
- Gate I MCP trace: `moss-metric-contracts.get_page_trace_bundle` resolved `PAGE-LEDGER-PNL-001`, route `/ledger-pnl`, primary API `/api/ledger-pnl/summary`, and supporting APIs `/api/ledger-pnl/dates`, `/api/ledger-pnl/data`, and `/api/ledger-pnl/formal-financial-indicators`.
- Gate I metric boundary: MCP guardrails keep `MTR-LPN-001` through `MTR-LPN-003` as candidate display metrics with `pending_confirmation=true`; the page must not use ledger summary cards to replace formal PnL, product-category PnL, PnL bridge, or formal financial-indicator truth.
- Gate I source-contract boundary: `GS-LEDGER-PNL-FIN-IND-202603-B` is a formal financial indicator source-contract fixture only; it freezes source status and Excel sample values but does not approve system values for formal use.
- Gate I lineage status: `moss-lineage-evidence.get_page_governance_audit_evidence_packet` returned `manual_review_blocker_count=1`, blocker `direct_page_api_record_fields`, and `closure_approved=false`.
- Gate I direct-record blocker routing: `moss-lineage-evidence.validate_page_governance_records` and `get_page_governance_record_blueprint_queue` now classify `/ledger-pnl` as `missing_direct_records`, with `direct_record_count=0`, `expanded_anchor_record_count=0`, P1 gap `missing_direct_and_expanded_records`, remediation lane `create_direct_record_and_supporting_lineage`, missing required fields `report_date`, `basis`, `source_surface`, `source_version`, `rule_version`, `created_at`, and failed required field group `execution_identifier` (`cache_key` or `run_id`). Evidence artifact: `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-blocker.json`.
- Gate I preflight candidate: local `ledger_pnl_summary_envelope` result_meta for report date `2026-05-31` supplies `basis=ledger`, `source_version=sv_product_category_3353b116b9a6`, `rule_version=rv_ledger_pnl_v1`, `created_at=2026-06-05T12:01:14.993184Z`, `cache_key=ledger_pnl.summary:2026-05-31:ALL`, `tables_used=["qdb_general_ledger_workbook"]`, and `formal_use_allowed=false`; `moss-lineage-evidence.preflight_page_governance_record` reports `validation_status=ready_for_audit_review`, `missing_required_fields=[]`, and `failed_required_field_groups=[]`. This is candidate field completeness only; no governance record was written and no certification or formal-use approval is granted. Evidence artifact: `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-preflight-candidate.json`.
- Gate I governance-record command path: `python scripts/emit_ledger_pnl_governance_record.py` now dry-runs the field-complete candidate without writing records; `python scripts/emit_ledger_pnl_governance_record.py --write` is the explicit append/locate command for an approved governance workflow. The command path is exposed through page readiness, but it does not by itself approve closure or formal use.
- Latest dry-run check: `python scripts/emit_ledger_pnl_governance_record.py` returned `mode=dry-run`, `record_write_status=not_requested`, `existing_record_line=null`, `preflight.validation.validation_status=ready_for_audit_review`, `missing_required_fields=[]`, `failed_required_field_groups=[]`, and `evidence_scope.writes_governance_records=false` with `created_at=2026-06-05T13:47:58.221725Z`. This refreshes candidate preflight evidence only; the real governance stream still has no written direct record from this command. Evidence artifact: `docs/audits/2026-06-05-ledger-pnl-governance-closure-status.json`.
- Gate I business-owner approval gate: `docs/pnl/ledger-pnl-sign-off-packet.md`, `docs/pnl/ledger-pnl-governance-audit-packet.md`, `docs/pnl/ledger-pnl-owner-evidence-packet.md`, and `docs/pnl/ledger-pnl-business-owner-approval-template.md` are present. `scripts/check_ledger_pnl_business_owner_approval.py` validates the expected packet paths and artifact existence, then reports `approval_status=pending`, `business_owner_approval_captured=false`, `formal_use_allowed=false`, `closure_approved=false`, and 11 action items including governance-record review, no dedicated ledger summary golden-sample review, UI/API payload review, live-smoke evidence review, verification rerun, and candidate-boundary acceptance. `scripts/codex_page_readiness.py` exposes both default and strict ledger approval commands, but this only surfaces blockers; it does not approve the page or metrics.
- Gate I source/golden boundary: `docs/audits/2026-06-05-ledger-pnl-source-anchor-golden-boundary.json` records the ledger summary grain (`report_date` plus `currency_or_ALL`), execution identifier (`cache_key`), configured source anchors, current catalog findings (`qdb_general_ledger_workbook=unknown_table`, `ledger_import_batch=present`, `ledger_raw_row=present_no_date_column`), and the missing dedicated summary golden sample for `MTR-LPN-001` through `MTR-LPN-003`.
- Gate I catalog/date status: `moss-data-catalog.get_page_catalog_date_evidence` found `ledger_import_batch` present with sampled `as_of_date` values including `2026-03-31`; `ledger_raw_row` is present without a date column; `qdb_general_ledger_workbook` is currently reported as `unknown_table`.
- Gate I readiness refresh: `python scripts/codex_page_readiness.py --page-slug ledger-pnl` returns `overall_status=static-pass`, `approval_status=candidate_or_pending`, `formal_use_allowed=false`, `golden_sample_boundary=missing`, `business_owner_approval_status=pending; captured=false`, `catalog_date_evidence=null`, `governance_record_validation=null`, and `audit_review=null`. This confirms routing and blockers, not closure.
- Gate I trace table:

| Displayed surface | Metric/status | API response | Client/model path | Component/table path | Unit/date/null/fallback status | Gate I status |
| --- | --- | --- | --- | --- | --- | --- |
| Summary card `ledger_monthly_pnl_core` | `MTR-LPN-001`, candidate | `LedgerPnlSummaryPayload.ledger_monthly_pnl_core` from `GET /api/ledger-pnl/summary` | `frontend/src/api/pnlCoreClient.ts` -> `getLedgerPnlSummary` -> React Query `summaryQuery` -> `summaryCards` | `LedgerSummaryCard` in `LedgerPnlPage.tsx` | Display unit `亿元`, precision 2, signed amount, `report_date`/`as_of_date` from `result_meta`, null renders `--`; stale/fallback must stay visible through result meta. | `evidence-pending`; candidate, no dedicated golden sample. |
| Summary card `ledger_monthly_pnl_all` | `MTR-LPN-002`, candidate | `LedgerPnlSummaryPayload.ledger_monthly_pnl_all` from `GET /api/ledger-pnl/summary` | Same summary chain | Same summary card chain | Same unit/date/null semantics; no frontend formal promotion. | `evidence-pending`; candidate, no dedicated golden sample. |
| Summary card `ledger_net_assets` | `MTR-LPN-003`, candidate | `LedgerPnlSummaryPayload.ledger_net_assets` from `GET /api/ledger-pnl/summary` | Same summary chain | Same summary card chain | Same unit/date/null semantics; not an approved formal net-assets metric. | `evidence-pending`; candidate, no dedicated golden sample. |
| Currency/account/detail tables | Ledger read-chain evidence | `LedgerPnlSummaryPayload.by_currency`, `by_account`; `LedgerPnlDataPayload.items` | `getLedgerPnlSummary`, `getLedgerPnlData`, local sort/filter display helpers | `ledger-pnl-currency-summary-table`, account summary table, detail table, residual diagnostics | Backend read chain owns totals; frontend sorting/truncation/display only; date/currency comparability guarded by `result_meta`. | `trace-collected`; not a separate formal metric certification. |
| Formal financial indicator source contract | Source status, not approved formal value | `LedgerPnlFormalFinancialIndicatorContractPayload` from `GET /api/ledger-pnl/formal-financial-indicators` | `getLedgerPnlFormalFinancialIndicators` -> `formalIndicatorSourceContractQuery` | formal indicator source-contract panel and release gate | `formal_use_allowed=false` keeps values pending; `value=null` must not render as zero; report month maps to month-end `as_of_date`. | `evidence-pending`; fixture only until governed source and manual review close. |

### `/macro-toolkit`

- Screenshots: `frontend/.codex-tmp/macro-toolkit-gateB-desktop-final2.png`, `frontend/.codex-tmp/macro-toolkit-gateB-tablet-final2.png`, `frontend/.codex-tmp/macro-toolkit-gateB-mobile-final2.png`.
- Measurements: desktop governance/action console about `1325px`; tablet governance about `3067px`, action console about `3375px`; mobile brief about `437px`, governance about `1554px`, action console about `1907px`.
- Evidence note: mobile first screen now preserves readiness, blocker, next action, and data-health signoff before deeper operations.

### `/stock-analysis`

- Screenshots: `frontend/.codex-tmp/stock-analysis-gateC-desktop-final.png`, `frontend/.codex-tmp/stock-analysis-gateC-tablet-final.png`, `frontend/.codex-tmp/stock-analysis-gateC-mobile-final.png`.
- Measurements: `frontend/.codex-tmp/stock-analysis-gateC-final-measurements.json`.
- Final measured closure:
  - desktop: cockpit `105px`, review queue `405px`, closed-loop trust evidence `132px`, sector chart `525px`
  - tablet: review queue `557px`, consensus `645px`, closed-loop trust evidence `742px`, sector chart `1035px`
  - mobile: review queue `353px`, consensus `441px`, closed-loop trust evidence `538px`, sector chart `831px`
- Runtime: status `200`, no fallback route, no permanent busy state, no blocking console errors, and no document-level horizontal overflow across desktop/tablet/mobile.

### `/product-category-pnl`

- Screenshots: `frontend/.codex-tmp/product-category-pnl-gateD-desktop-final3.png`, `frontend/.codex-tmp/product-category-pnl-gateD-tablet-final3.png`, `frontend/.codex-tmp/product-category-pnl-gateD-mobile-final3.png`.
- Measurements: `frontend/.codex-tmp/product-category-pnl-gateD-final3-measurements.json`.
- Final measured closure:
  - desktop: hero `344px`, status strip `565px`, formal readiness band `997px`, first-screen category row preview `1242px`
  - tablet: hero `499px`, status strip `938px`, formal readiness band `1370px`, first-screen category row preview `1709px`
  - mobile: hero `398px`, status strip `781px`, formal readiness band `1358px`, first-screen category row preview `1752px`
- Runtime: status `200`, no fallback route, no permanent busy state, no document-level horizontal overflow, and only dev-server/React informational console messages in the local Vite check.
- Evidence note: the full formal table remains in the later formal-readout section; Gate D adds a first-screen formal-chain summary with report date, view, basis, quality, vendor, fallback, generated-at, `MTR-PCP-001` through `MTR-PCP-003`, and a governed category-row preview.
- Gate G mobile table screenshots: `frontend/.codex-tmp/product-category-pnl-gate-g/desktop-1440.png`, `frontend/.codex-tmp/product-category-pnl-gate-g/tablet-768.png`, `frontend/.codex-tmp/product-category-pnl-gate-g/mobile-390.png`, `frontend/.codex-tmp/product-category-pnl-gate-g/mobile-formal-table-readout.png`.
- Gate G mobile table measurements: `frontend/.codex-tmp/product-category-pnl-gate-g/layout-verification.json`.
- Gate G evidence note: the formal table now has `product-category-formal-table-mobile-readout` before `product-category-formal-table-raw-grid`; desktop/tablet keep the mobile readout hidden while mobile `390px` shows the compact formal table readout before the raw grid.
- Gate G attribution screenshots: `frontend/.codex-tmp/product-category-pnl-gate-g-attribution/desktop-1440.png`, `frontend/.codex-tmp/product-category-pnl-gate-g-attribution/tablet-768.png`, `frontend/.codex-tmp/product-category-pnl-gate-g-attribution/mobile-390.png`, `frontend/.codex-tmp/product-category-pnl-gate-g-attribution/mobile-attribution-comparison-readout.png`, `frontend/.codex-tmp/product-category-pnl-gate-g-attribution/mobile-attribution-detail-readout.png`.
- Gate G attribution measurements: `frontend/.codex-tmp/product-category-pnl-gate-g-attribution/layout-verification.json`.
- Gate G attribution evidence note: the attribution comparison/detail tables now have `product-category-attribution-comparison-mobile-readout` and `product-category-attribution-detail-mobile-readout` before their raw tables; desktop/tablet keep the mobile readouts hidden while mobile `390px` shows both compact readouts before raw grid exploration.
- Gate G liability screenshots: `frontend/.codex-tmp/product-category-pnl-gate-g-liability/desktop-1440.png`, `frontend/.codex-tmp/product-category-pnl-gate-g-liability/tablet-768.png`, `frontend/.codex-tmp/product-category-pnl-gate-g-liability/mobile-390.png`.
- Gate G liability measurements: `frontend/.codex-tmp/product-category-pnl-gate-g-liability/browser-verification.json`.
- Gate G liability evidence note: the liability detail matrix now has `product-category-liability-side-detail-matrix-mobile-readout` before `product-category-liability-side-detail-matrix`; the RMB and foreign-currency matrices now have `product-category-liability-side-currency-matrix-*-mobile-readout` before their raw matrices. Desktop/tablet keep these readouts hidden while mobile `390px` shows them before raw matrix exploration. The fallback table readout exists as a defensive branch, but current model-derived liability detail rows also produce detail-matrix rows; `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts` now captures that boundary instead of treating synthetic fallback payloads as production browser proof.
- Gate I boundary artifact: `docs/audits/2026-06-05-product-category-pnl-gate-i-boundary-status.json`.
- Gate I readiness: `python scripts/codex_page_readiness.py --page-slug product-category-pnl` reports `overall_status=static-pass`, `approval_status=formal_or_governed`, `formal_use_allowed=true`, `catalog_date_evidence_sampled=2/2`, `direct_governance_record_ready`, `golden_sample_boundary=approved`, `golden_sample_approval_artifact_status=captured-awaiting-approval`, `golden_sample_approval_artifact_mismatch=true`, and no blocking static gates.
- Gate I governance validation: readiness reports `direct_records_ready_for_audit_review`, `ready_record_count=1`, `direct_record_count=1`, and `expanded_anchor_record_count=20`, but audit review remains `ready_for_audit_review` with `closure_approved=false`.
- Gate I business-owner approval gate: `docs/pnl/product-category-pnl-business-owner-approval-template.md` is present and `scripts/check_product_category_pnl_business_owner_approval.py` historically reported `approval_status=pending`, `business_owner_approval_captured=false`, `formal_use_allowed=true`, `closure_approved=false`, and 14 owner-action items; the current board reports 15 action items as the active machine truth. The action items include owner identity, approval decision/date/signature, governance review, owner-decision packet review, `GS-PROD-CAT-PNL-A` approval-artifact reconciliation, closure-checklist review, liability fallback model-boundary evidence review, UI/API payload review, live-smoke review, verification rerun, and evidence-pending boundary acceptance. The checker now also surfaces `golden_sample_approval_artifact.approved=false` from `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` and `closure_checklist_artifact.ready_for_owner_approval=false` / `partial_count=10` from `docs/pnl/product-category-closure-checklist.md`; `--require-captured` cannot pass from a completed template alone.
- Gate I first-certification owner packet: `docs/pnl/product-category-pnl-first-certification-packet.md` packages the source-to-screen trace for `MTR-PCP-001` through `MTR-PCP-012`, the machine-visible golden approval mismatch, and the 13 business-owner action items. The packet explicitly keeps `approves_metric_or_page=false`, `writes_governance_records=false`, `proves_page_execution=false`, and `captures_business_owner_approval=false`.
- Gate I golden-sample boundary: `GS-PROD-CAT-PNL-A` covers `GET /ui/pnl/product-category` for `2026-02-28`, `view=monthly`, plus a companion scenario probe. It binds `MTR-PCP-001` through `MTR-PCP-012`; additional fields need a new matrix, dictionary row, sample assertion, and test bundle.
- Gate I approval artifact mismatch: readiness now reports `golden_sample_approval_artifact_mismatch=true`: the golden sample boundary is `approved`, but `tests/golden_samples/GS-PROD-CAT-PNL-A/approval.md` still says `captured-awaiting-approval` with owner, approver, and approval date as `TBD`. The approval checker treats this as `approved=false`; this must be manually reviewed and signed before final certification wording.
- Gate I closure checklist: `docs/pnl/product-category-closure-checklist.md` still classifies all ten closure units as `PARTIAL`; the approval checker treats this as `ready_for_owner_approval=false`. Remaining blockers are mostly product/API/evidence decisions, not missing raw page implementation.

### `/pnl-attribution`

- Screenshots: `frontend/.codex-tmp/pnl-attribution-gate-e/desktop-1440.png`, `frontend/.codex-tmp/pnl-attribution-gate-e/tablet-768.png`, `frontend/.codex-tmp/pnl-attribution-gate-e/mobile-390.png`.
- Measurements: `frontend/.codex-tmp/pnl-attribution-gate-e/layout-verification.json`.
- Final measured closure after the mobile decision-strip compression:
  - desktop: title `199px`, decision strip `317px-523px`, product-category lens `543px`, no document-level horizontal overflow
  - tablet: title `298px`, decision strip `479px-684px`, product-category lens `704px`, no document-level horizontal overflow
  - mobile: title `269px`, decision strip `469px-786px`, product-category lens starts at `806px`, compact two-column evidence rows, no document-level horizontal overflow
- Runtime: status `200`, no fallback route, no permanent busy state, no blocking console errors, and no page errors across desktop/tablet/mobile production-preview checks.
- Gate G mobile table screenshots: `frontend/.codex-tmp/pnl-attribution-gate-g/desktop-1440.png`, `frontend/.codex-tmp/pnl-attribution-gate-g/tablet-768.png`, `frontend/.codex-tmp/pnl-attribution-gate-g/mobile-390.png`, `frontend/.codex-tmp/pnl-attribution-gate-g/mobile-attribution-readout.png`, `frontend/.codex-tmp/pnl-attribution-gate-g/mobile-ytd-readout.png`.
- Gate G mobile table measurements: `frontend/.codex-tmp/pnl-attribution-gate-g/layout-verification.json`.
- Evidence note: Gate E adds an attribution decision strip before lens cards. It surfaces active lens, report-date resolution, source path, view period, quality, fallback, comparison mode, and next action while preserving the explicit product-category operating lens, formal FI lens, TPL hybrid exception, and Campisi decision-grade boundary. Gate G adds mobile-first readouts before the product-category attribution and YTD raw grids; the raw grids remain available for audit and reconciliation.
- Gate I boundary artifact: `docs/audits/2026-06-05-pnl-attribution-gate-i-certification-boundary.json`.
- Gate I readiness: `python scripts/codex_page_readiness.py --page-slug pnl-attribution` reports `overall_status=static-pass`, `approval_status=candidate_or_pending`, no blocking static gates, `catalog_date_evidence_sampled=5/5`, `direct_governance_record_ready`, and `business_owner_approval_status=pending; captured=false`.
- Gate I governance-record dry-run: `python scripts/emit_pnl_attribution_governance_record.py` returns `mode=dry-run`, `record_write_status=not_requested`, `existing_record_line=5403`, `preflight.validation.validation_status=ready_for_audit_review`, `record_key.cache_key=pnl-attribution:volume-rate:2026-04-30:mom`, and `evidence_scope.writes_governance_records=false`.
- Gate I validation status: readiness reports `direct_records_ready_for_audit_review`, `ready_record_count=1`, `direct_record_count=1`, and `expanded_anchor_record_count=20`, but audit review still requires page contract review, catalog/date review, lineage freshness review, UI/API payload review, live-smoke evidence review, and business-owner approval.
- Gate I golden-sample boundary: `GS-PNL-ATTR-WB-A` is `captured-awaiting-approval` and freezes the primary `GET /api/pnl-attribution/volume-rate` workbench DTO only. It does not approve advanced attribution, Campisi, full-page closure, `/api/pnl/overview`, or the executive analytical overlay `/ui/pnl/attribution`.
- Gate I owner evidence packet: `docs/pnl/pnl-attribution-owner-evidence-packet.md` records `business_contract_status=evidence-pending`, `business_contract_certified=false`, `formal_use_allowed=false`, `closure_approved=false`, `governance_record_write_status=not_requested`, `governance_validation_status=ready_for_audit_review`, and the 11 business-owner action items. The packet explicitly keeps `approves_metric_or_page=false`, `writes_governance_records=false`, `proves_page_execution=false`, and `captures_business_owner_approval=false`.
- Gate I approval gate: `python scripts/check_pnl_attribution_business_owner_approval.py` reports `business_owner_approval_captured=false`, `formal_use_allowed=false`, `closure_approved=false`, and 11 action items covering owner identity, approval decision/date/signature, governance-record review, golden-sample review, UI/API payload review, live-smoke review, verification rerun, and candidate-boundary acceptance.

### `/bond-analysis`

- Screenshots: `frontend/.codex-tmp/bond-analysis-gate-f/final-stable4-desktop-1440.png`, `frontend/.codex-tmp/bond-analysis-gate-f/final-stable4-tablet-768.png`, `frontend/.codex-tmp/bond-analysis-gate-f/final-stable4-mobile-390.png`.
- Measurements: `frontend/.codex-tmp/bond-analysis-gate-f/final-stable4-measurements.json`.
- Gate G mobile table screenshots: `frontend/.codex-tmp/bond-analysis-gate-g/desktop-1440.png`, `frontend/.codex-tmp/bond-analysis-gate-g/tablet-768.png`, `frontend/.codex-tmp/bond-analysis-gate-g/mobile-390.png`, `frontend/.codex-tmp/bond-analysis-gate-g/mobile-accounting-dv01-section.png`, `frontend/.codex-tmp/bond-analysis-gate-g/mobile-holdings-section.png`.
- Gate G mobile table measurements: `frontend/.codex-tmp/bond-analysis-gate-g/layout-verification.json`.
- Final measured closure:
  - desktop: decision cockpit top about `207px`, height about `185px`, no document-level horizontal overflow
  - tablet: decision cockpit top about `227px`, height about `260px`, no document-level horizontal overflow
  - mobile: decision cockpit top about `349px`, height about `367px`, no document-level horizontal overflow, title and overview labels remain horizontal
- Runtime: status `200`, no fallback route, no permanent loading, no blocking console errors, and no page errors across desktop/tablet/mobile production-preview checks.
- Evidence note: Gate F adds a fixed-income risk decision cockpit before module detail. It surfaces report date, period, client mode, action-attribution conclusion, warning count, DV01/duration/PnL availability, fallback/no-data language, and a next-action drill path while preserving the temporary-exception and data-quality markers. Gate G adds mobile-first readouts before the lower accounting-DV01 and top-holdings raw grids; the raw grids remain available for audit and reconciliation.
- Gate I boundary gap artifact: `docs/audits/2026-06-05-bond-analysis-gate-i-boundary-gap.json`.
- Gate I readiness gap: `python scripts/codex_page_readiness.py --page-slug bond-analysis` now returns `overall_status=static-pass`, `page_id=GAP-BOND-ANALYSIS-PAGE`, `approval_status=gap_or_observational`, `formal_use_allowed=false`, `golden_samples=[]`, and `run_supported=true`. This wires a direct gap lane for `/bond-analysis`; it does not certify the page.
- Gate I non-reuse boundary: `PAGE-BOND-001` in `docs/page_contracts.md` names route `/bond-dashboard` and `GET /api/bond-dashboard/*`; `GS-BOND-HEADLINE-A` is a `captured-awaiting-approval` sample for `GET /api/bond-dashboard/headline-kpis?report_date=2026-03-31`; neither artifact certifies `/bond-analysis`.
- Gate I fixed-income convention risk: any future certification must preserve direct `/bond-analysis` evidence for DV01, duration, yield/YTM percent, bp movement, market value scale, accounting class, report date, and stale/fallback/result_meta state. Browser cleanliness alone does not prove fixed-income metric correctness.

## Verification

Run from `frontend/`:

- `npm run test -- src/test/PnlAttributionPage.test.tsx src/test/WorkbenchShell.test.tsx`: 45 passed
- `npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx`: 81 passed
- `npm run test -- src/test/StockAnalysisPage.test.tsx`: 91 passed
- `npm run test -- src/test/BondAnalyticsViewContent.test.tsx src/test/BondAnalyticsView.test.tsx src/test/WorkbenchShell.test.tsx`: 84 passed
- Gate G `/bond-analysis`: `npm run test -- src/test/BondAnalyticsView.test.tsx`: 15 passed after RED confirmed the missing mobile readout anchor.
- Gate G `/bond-analysis`: `npm run test -- src/test/BondAnalyticsViewContent.test.tsx src/test/BondAnalyticsView.test.tsx src/test/WorkbenchShell.test.tsx`: 64 passed
- Gate G `/pnl-attribution`: `npm run test -- src/test/PnlAttributionPage.test.tsx` failed in RED only because `pnl-attribution-product-category-attribution-mobile-readout` was missing, then passed with 6 tests.
- Gate G `/pnl-attribution`: `npm run test -- src/test/PnlAttributionPage.test.tsx src/test/WorkbenchShell.test.tsx`: 45 passed.
- Gate G `/product-category-pnl`: RED `npm run test -- src/test/ProductCategoryPnlPage.test.tsx` failed only because `product-category-formal-table-mobile-readout` was missing.
- Gate G `/product-category-pnl`: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx`: 84 passed.
- Gate G `/product-category-pnl` browser measurement at desktop `1440px`, tablet `768px`, and mobile `390px`: status `200`, formal table readout and raw-grid anchors present, readout before raw grid/table, mobile readout visible at `390px`, desktop/tablet hidden, no document-level horizontal overflow, no console warnings/errors, and no page errors.
- Gate G `/product-category-pnl` attribution RED `npm run test -- src/test/ProductCategoryPnlPage.test.tsx`: 2 failed only because `product-category-attribution-comparison-mobile-readout` and `product-category-attribution-detail-mobile-readout` were missing.
- Gate G `/product-category-pnl` attribution page test: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx`: 47 passed.
- Gate G `/product-category-pnl` attribution shell slice: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx`: 86 passed.
- Gate G `/product-category-pnl` attribution browser measurement at desktop `1440px`, tablet `768px`, and mobile `390px`: status `200`, comparison/detail readout anchors present before raw tables, mobile readouts visible at `390px`, desktop/tablet hidden, no document-level horizontal overflow, no console warnings/errors, and no page errors. Production build also passed; browser evidence used local mock-mode dev server because production preview correctly defaulted to real API and the local backend was not running.
- Gate G `/product-category-pnl` liability RED `npm run test -- src/test/ProductCategoryPnlPage.test.tsx`: 2 failed only because `product-category-liability-side-detail-matrix-mobile-readout` and `product-category-liability-side-currency-matrix-cny-mobile-readout` were missing.
- Gate G `/product-category-pnl` liability page test: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx`: 49 passed.
- Gate G `/product-category-pnl` liability shell slice: `npm run test -- src/test/ProductCategoryPnlPage.test.tsx src/test/WorkbenchShell.test.tsx`: 88 passed.
- Gate G `/product-category-pnl` liability live-route slice: `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed.
- Gate G `/product-category-pnl` liability browser measurement at desktop `1440px`, tablet `768px`, and mobile `390px`: status `200`, liability detail/currency readout anchors present before raw matrices, mobile readouts visible at `390px`, desktop/tablet hidden, no document-level horizontal overflow, no console warnings/errors, and no page errors.
- `npm run test -- src/test/LiveRouteReadiness.test.tsx src/test/LiveRouteRealPageSmoke.test.tsx`: 44 passed
- `npm run lint`: passed
- `npm run typecheck`: passed
- `npm run debt:audit`: passed, no growth over baseline
- `npm run build`: passed
- Browser anchor smoke across `/cross-asset`, `/ledger-pnl`, `/macro-toolkit`, and `/stock-analysis` at desktop `1440px`, tablet `768px`, and mobile `390px`: all returned status `200`, required anchors present, no document-level horizontal overflow, no blocking console errors, and no permanent busy state.
- Browser measurement for `/product-category-pnl` at desktop `1440px`, tablet `768px`, and mobile `390px`: status `200`, required anchors present, formal readiness anchors present, no document-level horizontal overflow, no fallback route, and no permanent busy state.
- Browser measurement for `/pnl-attribution` at desktop `1440px`, tablet `768px`, and mobile `390px`: status `200`, required anchors present, attribution decision strip present before lens cards, no document-level horizontal overflow, no fallback route, no permanent busy state, no blocking console errors, and no page errors.
- Gate G browser measurement for `/pnl-attribution` at desktop `1440px`, tablet `768px`, and mobile `390px`: status `200`, product-category attribution and YTD readout anchors present before raw grids, mobile readouts visible at `390px`, desktop/tablet readouts hidden, no document-level horizontal overflow, no console warnings/errors, and no page errors.
- Browser measurement for `/bond-analysis` at desktop `1440px`, tablet `768px`, and mobile `390px`: status `200`, required cockpit present, no document-level horizontal overflow, no fallback route, no permanent loading, no blocking console errors, and no page errors.
- Gate G browser measurement for `/bond-analysis` at desktop `1440px`, tablet `768px`, and mobile `390px`: status `200`, accounting-DV01 and holdings readout anchors present before raw grids, mobile readouts visible at `390px`, no document-level horizontal overflow, no console warnings/errors, and no page errors.
- Gate H shell test: `npm run test -- src/test/WorkbenchShell.test.tsx`: 40 passed after RED confirmed the missing skip link and unnamed main landmark.
- Gate H browser keyboard smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-keyboard'`: 7 passed.
- Gate H route-owned focus smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-route-focus'`: 7 passed.
- Gate H control context smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-control-context'`: 7 passed.
- Gate H combined keyboard/control smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- --grep '@gate-h-(keyboard|route-focus|control-context)'`: 21 passed.
- Gate H full a11y smoke: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs --workers=1`: 39 passed.
- Gate H standard checks: `npm run typecheck`, `npm run lint`, `npm run debt:audit`, and `npm run build`: passed.
- Anchor smoke evidence: `frontend/.codex-tmp/institutional-flagship-routes-anchor-smoke.json`.
- Gate I `/ledger-pnl` governance-record generator: `python -m pytest tests/test_ledger_pnl_governance_record.py`: 3 passed. This covers dry-run no-write preflight, explicit temporary write validation through MCP, and idempotent record-key behavior.
- Gate I readiness command surfacing: `python -m pytest tests/test_codex_page_readiness_gate.py::test_ledger_pnl_readiness_exposes_run_commands_without_direct_record_promotion -q`: 1 passed.
- Gate I `/ledger-pnl` closure refresh: `python scripts/emit_ledger_pnl_governance_record.py`, `python scripts/check_ledger_pnl_business_owner_approval.py`, and `python scripts/codex_page_readiness.py --page-slug ledger-pnl` returned the dry-run and approval evidence summarized above without writing governance records or capturing approval.
- Gate I `/pnl-attribution` evidence collection: `python scripts/codex_page_readiness.py --page-slug pnl-attribution`, `python scripts/emit_pnl_attribution_governance_record.py`, and `python scripts/check_pnl_attribution_business_owner_approval.py` returned the evidence summarized above without writing governance records or capturing approval.
- Gate I `/product-category-pnl` evidence collection: `python scripts/codex_page_readiness.py --page-slug product-category-pnl` and `python scripts/check_product_category_pnl_business_owner_approval.py` returned the evidence summarized above, including the machine-visible `golden_sample_approval_artifact_mismatch=true`; no certification promotion was made because closure approval, manual review, golden-approval artifact reconciliation, fallback branch proof review, and business-owner approval remain open.

Previously recorded Gate A/B verification:

- `/ledger-pnl`: page tests, shell tests, live-route tests, lint, typecheck, debt audit, and build passed.
- `/macro-toolkit`: page tests, live-route tests, lint, typecheck, debt audit, and build passed.

## MCP Status

The project MCP evidence servers were not exposed as direct Codex App tools in this session:

- `moss-metric-contracts`
- `moss-lineage-evidence`
- `moss-data-catalog`
- `gitnexus`

However, the configured local MCP servers were callable through their read-only stdio launchers for the `/ledger-pnl` Gate I slice:

- `moss-metric-contracts.get_page_trace_bundle`: available; evidence saved in `docs/audits/2026-06-05-ledger-pnl-gate-i-mcp-evidence.json`.
- `moss-lineage-evidence.get_page_governance_audit_evidence_packet`: available; returned `manual_review_blocker_count=1`, blocker `direct_page_api_record_fields`, and `closure_approved=false`.
- `moss-lineage-evidence.get_page_governance_record_requirements`, `validate_page_governance_records`, `get_page_governance_record_blueprint`, `get_page_governance_gap_queue`, and `get_page_governance_record_blueprint_queue`: available for `/ledger-pnl`; routed the blocker to P1 direct-record creation plus supporting lineage, with missing fields and failed required field group saved in `docs/audits/2026-06-05-ledger-pnl-gate-i-direct-record-blocker.json`.
- `moss-lineage-evidence.preflight_page_governance_record`: available for a `/ledger-pnl` candidate direct record populated from current summary `result_meta`; the candidate now includes `cache_key=ledger_pnl.summary:2026-05-31:ALL` and preflights as `ready_for_audit_review`. The same candidate is repeatable through `scripts/emit_ledger_pnl_governance_record.py`, but this still does not prove page/API execution completeness, capture approval, or certify the page.
- `moss-data-catalog.get_page_catalog_date_evidence`: available; returned catalog/date evidence for three ledger table anchors.
- `/pnl-attribution` Gate I readiness used the local readiness, governance-record, approval-checker, owner evidence packet, sign-off, and audit-packet scripts already wired in this repo. The resulting boundary artifacts record direct-record readiness, catalog/date sampling, golden-sample scope, and approval blockers, but they do not certify page closure or formal use.
- `gitnexus`: configured in `.mcp.json` and `.codex/config.toml`, but not directly exposed as an App tool and not used in this Gate I slice.

Local source, component tests, route contracts, browser measurements, approval-template checks, and MCP stdio evidence were used for `/ledger-pnl` trace collection only. They do not grant business closure, formal-use approval, or golden-sample approval.

## Retained Boundaries

- No metric definitions were changed.
- No formal-use semantics were changed.
- No governance, stale, fallback, no-data, or temporary-exception markers were retired.
- No backend, database, auth, scheduler, queue, cache, or global SDK layer was changed for this scorecard.

## Remaining Risks

- Accessibility is now `4/4` for the seven audited flagship routes under the automated frontend-surface gate: shared skip path, route-owned focus traversal, human-readable control names, visible focus, and non-color state cues are browser-tested. Manual assistive-technology walkthrough is still recommended before external release.
- The verdict applies to the seven audited flagship routes only. Other MOSS routes need independent scorecards before being called flagship-ready.
- Some lower-page mobile tables outside the completed `/bond-analysis`, `/pnl-attribution`, and `/product-category-pnl` formal/comparison/detail/liability Gate G slices remain controlled horizontal-scroll data grids. The `/product-category-pnl` fallback liability detail branch is now treated as model-boundary review evidence rather than a production browser-proof blocker.
- Business lineage and metric-contract certification remains pending for the whole seven-route scope. `/ledger-pnl` now has MCP-backed trace evidence, exact direct-record blocker routing, a field-complete preflight candidate with an evidence-backed `cache_key`, and a strict pending business-owner approval checker, but it remains `evidence-pending` until a direct page/API governance record plus supporting lineage are created or located, validation confirms the written record, manual review completes, business-owner approval is captured, and `closure_approved=true` is supported by evidence. `/pnl-attribution` now has a Gate I boundary package, direct-record readiness, and catalog/date sampling, but it remains `evidence-pending` until manual audit checks, golden-sample boundary review, UI/API/live-smoke review, verification rerun, candidate-boundary acceptance, and business-owner approval close. `/product-category-pnl` has the strongest formal/governed readiness so far and now has a strict pending business-owner approval checker, but still remains `evidence-pending` until the golden approval artifact mismatch, manual audit checks, business-owner approval, closure checklist residuals, and liability fallback model-boundary review are closed. `/bond-analysis` remains `gate-i-gap` until it has direct route contract/readiness/golden/governance evidence rather than borrowed `/bond-dashboard` evidence.
