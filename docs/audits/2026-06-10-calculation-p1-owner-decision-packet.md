# Calculation P1 Owner Decision Packet

Decision status: `decision_status=owner_decision_required`
Owner decision ready: `false`
Implementation ready: `false`
Execution anchor ready: `true`
Source snapshot generated at: `2026-06-10T21:25:00+08:00`

This packet prepares the first open blocker for owner/governance intake. It does not approve a calculation convention, capture owner decisions, change implementation code, write governance records, approve pages, authorize Ledger PnL `--write`, or certify routes.

## Summary

- `decision_item_count=10`
- `pending_decision_count=10`
- `captured_decision_count=0`
- `post_owner_required_fields=selected_decision, owner_rationale, implementation_owner, verification_gate, status`
- `execution_referenced_path_count=24`
- `missing_execution_referenced_path_count=0`
- First priority group: `P1-09, P1-10, P1-11`

**2026-07-03 P1-07 overlay**: owner/chat decision selected Option B for macro liquidity score polarity and implementation is complete. Historical 2026-06-10 snapshot counters above are retained because generated JSON snapshots were not refreshed in this pass.

## Source Artifacts

- `calculation_logic_audit`: `docs/audits/2026-06-10-calculation-logic-audit.md`
- `calculation_owner_decision_matrix`: `docs/audits/2026-06-10-calculation-p1-owner-decision-matrix.md`
- `calculation_owner_decision_snapshot`: `docs/audits/2026-06-10-calculation-p1-owner-decision-snapshot.json`
- `owner_decision_capture_template`: `docs/audits/2026-06-10-owner-decision-capture-template.zh.md`
- `calc_rules`: `docs/calc_rules.md`

## Intake Checklist

- `source_matrix_exists=true`
- `source_snapshot_exists=true`
- `decision_ids_match_expected=true`
- `all_rows_pending_owner_decision=true`
- `captured_decision_count=0`
- `invalid_status_count=0`
- `invalid_selected_decision_count=0`
- `execution_slice_count=10`
- `execution_referenced_path_count=24`
- `all_execution_slices_present=true`
- `all_execution_slice_paths_exist=true`
- `missing_execution_referenced_path_count=0`
- `captures_owner_decisions=false`
- `chooses_or_approves_conventions=false`

## Priority Groups

| Rank | P1 IDs | Rationale |
| ---: | --- | --- |
| 1 | `P1-09`, `P1-10`, `P1-11` | fastest remaining frontend/user-facing risk reduction once owner accepts the boundary. |
| 2 | `P1-02`, `P1-01`, `P1-05` | highest numeric magnitude risk. |
| 3 | `P1-03`, `P1-06`, `P1-07` | narrative/sign quality risks that need explicit wording. |
| 4 | `P1-04` | governance/control classification decision before any control claim. |

## Decision Items

| P1 | Rank | Area | Decision needed | Candidate decisions | Proposed review default | Current status | Missing capture fields | Owner decision gate |
| --- | ---: | --- | --- | --- | --- | --- | --- | --- |
| `P1-01` | 2 | Campisi coupon income | Define the stored and calculation unit for `coupon_rate`. | A: source values are decimals; B: source values are percentages and must be divided by 100; C: source must carry explicit unit metadata and fail if absent. | Prefer C, then normalize through one rate-unit helper. | `pending_owner_decision` | selected_decision, owner_rationale, implementation_owner, verification_gate, status | `docs/calc_rules.md` unit rule; one implementation path; numeric golden test for decimal and percent-shaped inputs. |
| `P1-02` | 2 | Bond analytics rate unit | Define the authoritative unit for `ytm_value` and coupon rates before DV01/duration. | A: all source rates are decimals; B: all source rates are percentages; C: source supplies explicit unit metadata. | Prefer C; remove `abs>1 -> /100` heuristics from formal paths. | `pending_owner_decision` | selected_decision, owner_rationale, implementation_owner, verification_gate, status | Data-catalog/source contract evidence; formal engine regression for sub-1% rates; no heuristic in formal path. |
| `P1-03` | 3 | Roll-down sign | Decide the business sign convention for curve roll-down. | A: `attribution_daily` convention, `-MD * (y_realized - y_prior) * MV`; B: current `pnl_bridge` convention; C: report both with explicit labels. | Prefer A unless owner explicitly wants the bridge convention. | `pending_owner_decision` | selected_decision, owner_rationale, implementation_owner, verification_gate, status | `docs/calc_rules.md` section for roll-down sign; one shared helper or adapter; tests updated on the losing side. |
| `P1-04` | 4 | QDB position-vs-ledger reconciliation | Decide whether the current check is a control or only a diagnostic. | A: require independent position and ledger source anchors; B: keep current same-source comparison but label it non-control. | Prefer A for any governance/control claim. | `pending_owner_decision` | selected_decision, owner_rationale, implementation_owner, verification_gate, status | Reconciliation evidence uses two independent sources, or UI/report explicitly marks the check as non-control. |
| `P1-05` | 2 | Period yield denominator | Define the denominator for quarterly/yearly yield. | A: period average scale; B: sum of month-end snapshots; C: weighted daily average when daily facts exist. | Prefer A/C; avoid summing snapshots as scale. | `pending_owner_decision` | selected_decision, owner_rationale, implementation_owner, verification_gate, status | Rule written to `calc_rules.md`; numeric tests for monthly, quarterly, and yearly buckets. |
| `P1-06` | 3 | PnL bridge zero-actual residual | Decide how reconciliation quality behaves when `actual_pnl=0`. | A: nonzero explained/residual with zero actual is warning/undefined; B: force ratio to 0 and mark ok. | Prefer A, consistent with fail-loud controls. | `pending_owner_decision` | selected_decision, owner_rationale, implementation_owner, verification_gate, status | Regression where `actual_pnl=0` and explained amount nonzero returns warning and visible diagnostics. |
| `P1-07` | 3 | Macro liquidity score polarity | Captured 2026-07-03: keep `liquidity_score` looseness-positive and invert it only inside the composite. | B: liquidity remains looseness-positive but enters composite with inverse sign. | Implemented as `0.4*rate - 0.3*liquidity + 0.2*growth + 0.1*inflation`; macro-context metadata exposes polarity/formula. | `approved-for-implementation; implemented` | none | Isolated liquidity regression; macro-context formula/polarity metadata assertions; frontend copy states polarity. |
| `P1-09` | 1 | Balance movement share source | Decide authoritative source for current-balance share. | A: backend `current_balance_pct` is authoritative; B: frontend recomputes from visible rows; C: backend provides both official and visible-row share. | Prefer A, with C only if users need visible-row share. | `pending_owner_decision` | selected_decision, owner_rationale, implementation_owner, verification_gate, status | Component/model tests prove backend value wins and missing share remains missing. |
| `P1-10` | 1 | Frontend formal aggregation | Decide where formal PnL/yield/ADB aggregations are computed. | A: backend DTO only; B: frontend may derive display aggregates; C: frontend derives only clearly non-formal UI helpers. | Prefer A for formal metrics and C for labeled non-formal helpers. | `pending_owner_decision` | selected_decision, owner_rationale, implementation_owner, verification_gate, status | Backend DTO added or confirmed; frontend removes formal aggregation; adapter/component tests consume DTO values. |
| `P1-11` | 1 | Credit spread rating-tenor matrix | Decide owner of rating-tenor bucket aggregation. | A: backend provides governed matrix; B: frontend aggregates rows and owns bucket mapping. | Prefer A. | `pending_owner_decision` | selected_decision, owner_rationale, implementation_owner, verification_gate, status | API contract for rating-tenor matrix; frontend renders provided matrix only; regression covers bucket boundaries. |

## Candidate Option Contract

selected_decision must reference an allowed option letter for that P1 and include substantive text matching the option description from the Decision Matrix Candidate Decisions column. The safest accepted shape is `Option <letter> - <copied option description>`. Bare Option A/B/C labels, undefined option letters, unrelated option text, and evidence-only text on approved-for-implementation rows remain invalid.

Allowed option letters are row-specific; some P1 rows only allow `Option A` and `Option B`. For `approved-for-implementation`, use the required capture format below rather than evidence-only wording. The format example is not a recommended option and does not approve any listed candidate.

| P1 | Allowed candidate options | Required capture format, not a recommendation |
| --- | --- | --- |
| `P1-01` | `Option A`: source values are decimals<br>`Option B`: source values are percentages and must be divided by 100<br>`Option C`: source must carry explicit unit metadata and fail if absent | `Option <allowed letter> - <copied option description>` |
| `P1-02` | `Option A`: all source rates are decimals<br>`Option B`: all source rates are percentages<br>`Option C`: source supplies explicit unit metadata | `Option <allowed letter> - <copied option description>` |
| `P1-03` | `Option A`: `attribution_daily` convention, `-MD * (y_realized - y_prior) * MV`<br>`Option B`: current `pnl_bridge` convention<br>`Option C`: report both with explicit labels | `Option <allowed letter> - <copied option description>` |
| `P1-04` | `Option A`: require independent position and ledger source anchors<br>`Option B`: keep current same-source comparison but label it non-control | `Option <allowed letter> - <copied option description>` |
| `P1-05` | `Option A`: period average scale<br>`Option B`: sum of month-end snapshots<br>`Option C`: weighted daily average when daily facts exist | `Option <allowed letter> - <copied option description>` |
| `P1-06` | `Option A`: nonzero explained/residual with zero actual is warning/undefined<br>`Option B`: force ratio to 0 and mark ok | `Option <allowed letter> - <copied option description>` |
| `P1-07` | `Option A`: all components tightness-positive<br>`Option B`: liquidity remains looseness-positive but enters composite with inverse sign<br>`Option C`: separate liquidity narrative from composite | `Option <allowed letter> - <copied option description>` |
| `P1-09` | `Option A`: backend `current_balance_pct` is authoritative<br>`Option B`: frontend recomputes from visible rows<br>`Option C`: backend provides both official and visible-row share | `Option <allowed letter> - <copied option description>` |
| `P1-10` | `Option A`: backend DTO only<br>`Option B`: frontend may derive display aggregates<br>`Option C`: frontend derives only clearly non-formal UI helpers | `Option <allowed letter> - <copied option description>` |
| `P1-11` | `Option A`: backend provides governed matrix<br>`Option B`: frontend aggregates rows and owns bucket mapping | `Option <allowed letter> - <copied option description>` |

## Post-Decision Execution Slices

| P1 | Execution slice after owner input | Referenced paths |
| --- | --- | --- |
| `P1-01` | after the owner selects the `coupon_rate` unit rule, update `docs/calc_rules.md` and normalize the affected Campisi workbook paths in `backend/app/core_finance/balance_analysis_workbook.py` and `backend/app/core_finance/balance_workbook/_analysis_tables.py`; regression should cover decimal-shaped and percent-shaped coupon inputs, including `tests/test_balance_workbook_campisi_rate.py` and Campisi golden samples. | `docs/calc_rules.md`, `backend/app/core_finance/balance_analysis_workbook.py`, `backend/app/core_finance/balance_workbook/_analysis_tables.py`, `tests/test_balance_workbook_campisi_rate.py` |
| `P1-02` | after source-unit evidence is captured for `ytm_value` and coupon rates, remove or quarantine the formal-path heuristic in `backend/app/core_finance/bond_analytics/engine.py`; regression should include sub-1% rate examples in the bond analytics engine/service tests and preserve explicit-unit handling. | `backend/app/core_finance/bond_analytics/engine.py` |
| `P1-03` | after owner sign convention is selected, align `backend/app/core_finance/pnl_bridge.py` with the authoritative attribution convention or label both conventions explicitly; regression should update `tests/test_pnl_bridge_roll_down_sign.py` and any attribution comparison test that freezes the losing sign. | `backend/app/core_finance/pnl_bridge.py`, `tests/test_pnl_bridge_roll_down_sign.py` |
| `P1-04` | after governance classifies the check as a control or diagnostic, update `backend/app/core_finance/qdb_gl_monthly_analysis.py` so control claims require independent anchors, or label same-source checks as non-control; regression should use QDB GL core/API tests to prove the selected label and evidence path. | `backend/app/core_finance/qdb_gl_monthly_analysis.py` |
| `P1-05` | after the denominator rule is approved, normalize `backend/app/core_finance/yield_by_period.py` and the `frontend/src/features/pnl/yieldAnalysis/YieldByPeriodPanel.tsx` display contract; regression should extend `tests/test_yield_by_period_core.py` across monthly, quarterly, and yearly buckets. | `backend/app/core_finance/yield_by_period.py`, `frontend/src/features/pnl/yieldAnalysis/YieldByPeriodPanel.tsx`, `tests/test_yield_by_period_core.py` |
| `P1-06` | after reconciliation-quality behavior is selected, align `backend/app/core_finance/pnl_bridge.py` with `backend/app/core_finance/attribution_core.py` or document the explicit difference; regression should cover `actual_pnl=0` with nonzero explained/residual in `tests/test_pnl_bridge_core.py`. | `backend/app/core_finance/pnl_bridge.py`, `backend/app/core_finance/attribution_core.py`, `tests/test_pnl_bridge_core.py` |
| `P1-07` | completed 2026-07-03 under Option B; future derived narratives must keep `liquidity_score` looseness-positive and `composite_score` bond-unfavorable/tightness-positive. | `backend/app/core_finance/macro_bond_linkage.py`, `backend/app/services/macro_bond_linkage_service.py`, `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`, `frontend/src/features/market-data/`, `tests/test_macro_bond_linkage.py` |
| `P1-09` | after the authoritative share source is selected, update `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx` to prefer the governed backend value or clearly label visible-row share; regression should extend `frontend/src/test/BalanceMovementAnalysisPage.test.tsx` for backend value precedence and missing-share display. | `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx`, `frontend/src/test/BalanceMovementAnalysisPage.test.tsx` |
| `P1-10` | after backend-vs-frontend aggregation ownership is approved, move or label formal aggregation currently in `frontend/src/features/pnl/yieldAnalysis/yieldAnalysisAggregates.ts` and `frontend/src/features/pnl/zqtzAdbAvgRollup.ts`; regression should keep DTO consumption and non-formal helper boundaries explicit in the corresponding frontend tests. | `frontend/src/features/pnl/yieldAnalysis/yieldAnalysisAggregates.ts`, `frontend/src/features/pnl/zqtzAdbAvgRollup.ts` |
| `P1-11` | after matrix ownership is approved, render a governed backend matrix or explicitly document frontend ownership in `frontend/src/features/bond-analytics/components/CreditSpreadView.tsx`; regression should update `frontend/src/test/CreditSpreadView.test.tsx` for rating/tenor bucket boundaries and missing governed matrix behavior. | `frontend/src/features/bond-analytics/components/CreditSpreadView.tsx`, `frontend/src/test/CreditSpreadView.test.tsx` |

## Execution Anchor Checks

Every referenced execution path below is an engineering handoff anchor only. Existing paths do not approve the corresponding owner decision.

| P1 | Referenced path count | All referenced paths exist | Missing referenced paths |
| --- | ---: | --- | --- |
| `P1-01` | 4 | `true` | none |
| `P1-02` | 1 | `true` | none |
| `P1-03` | 2 | `true` | none |
| `P1-04` | 1 | `true` | none |
| `P1-05` | 3 | `true` | none |
| `P1-06` | 3 | `true` | none |
| `P1-07` | 4 | `true` | none |
| `P1-09` | 2 | `true` | none |
| `P1-10` | 2 | `true` | none |
| `P1-11` | 2 | `true` | none |

## Next Engineering Action After Owner Input

For each captured owner convention, update docs/calc_rules.md or the applicable contract, normalize the authoritative implementation path, update tests that froze the losing convention, then rerun the P1 snapshot strict capture gate and the system audit completion verifier.

## Prohibited Actions

- choose an authoritative calculation convention without business-owner input
- treat proposed review defaults as approved rules
- change formal implementation before the selected rule is captured
- count pending capture-template rows as owner decisions
- reopen P1-08 without new contradictory evidence

## Evidence Scope

- `read_only=true`
- `chooses_or_approves_conventions=false`
- `changes_code=false`
- `writes_duckdb=false`
- `writes_governance_records=false`
- `approves_metrics=false`
- `approves_pages=false`
- `captures_business_owner_approval=false`
- `captures_owner_decisions=false`
- `certifies_routes=false`
- `authorizes_ledger_pnl_governance_write=false`

## Boundary

This packet is a read-only execution-preparation artifact. It does not choose or approve conventions, capture owner decisions, change code, write DuckDB or governance records, approve metrics/pages, authorize Ledger PnL --write, or certify routes.
