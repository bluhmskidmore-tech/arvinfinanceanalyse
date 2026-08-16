# Calculation P1 Owner Meeting Checklist

Source snapshot status: `source_snapshot_status=owner_decision_required`
Owner meeting material ready: `true`
Implementation ready: `false`
Execution anchor ready: `true`

This checklist prepares the owner/governance meeting for the `calculation-display-p1-decisions` blocker. It does not select a convention, approve a metric, or close any P1 row.

## Summary

- `decision_item_count=8`
- `pending_decision_count=8`
- `captured_decision_count=0`
- `incomplete_decision_count=8`
- `total_missing_capture_field_count=40`
- `meeting_missing_field_count=8`
- `meeting_record_complete=false`
- `execution_referenced_path_count=16`
- `missing_execution_referenced_path_count=0`
- `post_meeting_required_fields=selected_decision, owner_rationale, implementation_owner, verification_gate, status`
- `post_meeting_allowed_statuses=approved-for-implementation, deferred, rejected`

## Source Artifacts

- `calculation_owner_decision_matrix`: `docs/audits/2026-06-10-calculation-p1-owner-decision-matrix.md`
- `calculation_owner_decision_snapshot`: `docs/audits/2026-06-10-calculation-p1-owner-decision-snapshot.json`
- `calculation_owner_decision_packet`: `docs/audits/2026-06-10-calculation-p1-owner-decision-packet.md`
- `owner_decision_capture_template_zh`: `docs/audits/2026-06-10-owner-decision-capture-template.zh.md`

## Readiness Checks

- `decision_ids_match_expected=true`
- `all_rows_pending_owner_decision=true`
- `captured_decision_count_is_zero=true`
- `meeting_record_is_incomplete=true`
- `execution_anchor_ready=true`
- `captures_owner_decisions=false`
- `chooses_or_approves_conventions=false`
- `changes_implementation_code=false`

## Owner Questions

| P1 | Rank | Area | Owner question | Candidate decisions | Proposed review default for discussion | Missing capture fields | Owner decision gate |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| `P1-01` | 2 | Campisi coupon income | Define the stored and calculation unit for `coupon_rate`. | A: source values are decimals; B: source values are percentages and must be divided by 100; C: source must carry explicit unit metadata and fail if absent. | Prefer C, then normalize through one rate-unit helper. | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | `docs/calc_rules.md` unit rule; one implementation path; numeric golden test for decimal and percent-shaped inputs. |
| `P1-02` | 2 | Bond analytics rate unit | Define the authoritative unit for `ytm_value` and coupon rates before DV01/duration. | A: all source rates are decimals; B: all source rates are percentages; C: source supplies explicit unit metadata. | Prefer C; remove `abs>1 -> /100` heuristics from formal paths. | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | Data-catalog/source contract evidence; formal engine regression for sub-1% rates; no heuristic in formal path. |
| `P1-03` | 3 | Roll-down sign | Decide the business sign convention for curve roll-down. | A: `attribution_daily` convention, `-MD * (y_realized - y_prior) * MV`; B: current `pnl_bridge` convention; C: report both with explicit labels. | Prefer A unless owner explicitly wants the bridge convention. | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | `docs/calc_rules.md` section for roll-down sign; one shared helper or adapter; tests updated on the losing side. |
| `P1-04` | 4 | QDB position-vs-ledger reconciliation | Decide whether the current check is a control or only a diagnostic. | A: require independent position and ledger source anchors; B: keep current same-source comparison but label it non-control. | Prefer A for any governance/control claim. | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | Reconciliation evidence uses two independent sources, or UI/report explicitly marks the check as non-control. |
| `P1-05` | 2 | Period yield denominator | Define the denominator for quarterly/yearly yield. | A: period average scale; B: sum of month-end snapshots; C: weighted daily average when daily facts exist. | Prefer A/C; avoid summing snapshots as scale. | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | Rule written to `calc_rules.md`; numeric tests for monthly, quarterly, and yearly buckets. |
| `P1-06` | 3 | PnL bridge zero-actual residual | Decide how reconciliation quality behaves when `actual_pnl=0`. | A: nonzero explained/residual with zero actual is warning/undefined; B: force ratio to 0 and mark ok. | Prefer A, consistent with fail-loud controls. | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | Regression where `actual_pnl=0` and explained amount nonzero returns warning and visible diagnostics. |
| `P1-10` | 1 | Frontend formal aggregation | Decide where formal PnL/yield/ADB aggregations are computed. | A: backend DTO only; B: frontend may derive display aggregates; C: frontend derives only clearly non-formal UI helpers. | Prefer A for formal metrics and C for labeled non-formal helpers. | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | Backend DTO added or confirmed; frontend removes formal aggregation; adapter/component tests consume DTO values. |
| `P1-11` | 1 | Credit spread rating-tenor matrix | Decide owner of rating-tenor bucket aggregation. | A: backend provides governed matrix; B: frontend aggregates rows and owns bucket mapping. | Prefer A. | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | API contract for rating-tenor matrix; frontend renders provided matrix only; regression covers bucket boundaries. |

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
| `P1-10` | `Option A`: backend DTO only<br>`Option B`: frontend may derive display aggregates<br>`Option C`: frontend derives only clearly non-formal UI helpers | `Option <allowed letter> - <copied option description>` |
| `P1-11` | `Option A`: backend provides governed matrix<br>`Option B`: frontend aggregates rows and owns bucket mapping | `Option <allowed letter> - <copied option description>` |

## Closure Evidence And Engineering Handoff

| P1 | Impact if unresolved | Closure evidence after owner input | Post-decision execution slice |
| --- | --- | --- | --- |
| `P1-01` | Coupon income can be off by 100x and both current implementations have tests preserving opposite behavior. | `docs/calc_rules.md` unit rule; one implementation path; numeric golden test for decimal and percent-shaped inputs. | after the owner selects the `coupon_rate` unit rule, update `docs/calc_rules.md` and normalize the affected Campisi workbook paths in `backend/app/core_finance/balance_analysis_workbook.py` and `backend/app/core_finance/balance_workbook/_analysis_tables.py`; regression should cover decimal-shaped and percent-shaped coupon inputs, including `tests/test_balance_workbook_campisi_rate.py` and Campisi golden samples. |
| `P1-02` | Low-rate inputs such as `0.85` can be read as 85%, corrupting duration, convexity, and DV01. | Data-catalog/source contract evidence; formal engine regression for sub-1% rates; no heuristic in formal path. | after source-unit evidence is captured for `ytm_value` and coupon rates, remove or quarantine the formal-path heuristic in `backend/app/core_finance/bond_analytics/engine.py`; regression should include sub-1% rate examples in the bond analytics engine/service tests and preserve explicit-unit handling. |
| `P1-03` | PnL bridge and daily attribution can tell opposite stories for the same curve movement. | `docs/calc_rules.md` section for roll-down sign; one shared helper or adapter; tests updated on the losing side. | after owner sign convention is selected, align `backend/app/core_finance/pnl_bridge.py` with the authoritative attribution convention or label both conventions explicitly; regression should update `tests/test_pnl_bridge_roll_down_sign.py` and any attribution comparison test that freezes the losing sign. |
| `P1-04` | Same-source formulas make diff permanently zero and create false assurance. | Reconciliation evidence uses two independent sources, or UI/report explicitly marks the check as non-control. | after governance classifies the check as a control or diagnostic, update `backend/app/core_finance/qdb_gl_monthly_analysis.py` so control claims require independent anchors, or label same-source checks as non-control; regression should use QDB GL core/API tests to prove the selected label and evidence path. |
| `P1-05` | Quarterly yield can be understated by roughly 3x and yearly view by roughly 12x. | Rule written to `calc_rules.md`; numeric tests for monthly, quarterly, and yearly buckets. | after the denominator rule is approved, normalize `backend/app/core_finance/yield_by_period.py`; the unrouted frontend YieldByPeriodPanel display surface was removed as dead code in commit 559de28d (2026-08-12), so a display contract re-enters scope only if a successor page is routed; regression should extend `tests/test_yield_by_period_core.py` across monthly, quarterly, and yearly buckets. |
| `P1-06` | Material residuals can be hidden behind `quality_flag=ok`. | Regression where `actual_pnl=0` and explained amount nonzero returns warning and visible diagnostics. | after reconciliation-quality behavior is selected, align `backend/app/core_finance/pnl_bridge.py` with `backend/app/core_finance/attribution_core.py` or document the explicit difference; regression should cover `actual_pnl=0` with nonzero explained/residual in `tests/test_pnl_bridge_core.py`. |
| `P1-10` | Decimal values are converted to floating point, category trees are duplicated, and frontend can diverge from governed rules. | Backend DTO added or confirmed; frontend removes formal aggregation; adapter/component tests consume DTO values. | after backend-vs-frontend aggregation ownership is approved, move or label formal aggregation currently in `frontend/src/features/pnl/zqtzAdbAvgRollup.ts`; the unrouted yieldAnalysisAggregates dead-code surface was removed in commit 559de28d (2026-08-12); regression should keep DTO consumption and non-formal helper boundaries explicit in the corresponding frontend tests. |
| `P1-11` | Frontend hard-coded buckets can drift from backend tenor/rating rules without detection. | API contract for rating-tenor matrix; frontend renders provided matrix only; regression covers bucket boundaries. | after matrix ownership is approved, render a governed backend matrix or explicitly document frontend ownership in `frontend/src/features/bond-analytics/components/CreditSpreadView.tsx`; regression should update `frontend/src/test/CreditSpreadView.test.tsx` for rating/tenor bucket boundaries and missing governed matrix behavior. |

## Post-Meeting Capture Rule

Every row must have `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, and a `status` of `approved-for-implementation`, `deferred`, or `rejected` before the strict owner-decision capture gate can pass. For `approved-for-implementation`, `selected_decision` must use a row-specific allowed option and substantive text matching the option description. A populated checklist is still not metric approval; approved rows must be copied into the authoritative rule or contract location and verified with targeted tests.

## Prohibited Actions

- treat this checklist as owner approval
- select proposed review defaults without business owner and metric governance input
- start implementation before the selected decision and owner rationale are captured
- count a pending row as a captured owner decision
- write governance records or authorize Ledger PnL --write from this checklist

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

This checklist is read-only owner-meeting preparation. It asks what must be decided, lists candidate options from the P1 matrix, and records missing capture fields; it does not choose or approve calculation conventions, capture owner decisions, change code, approve metrics or pages, write governance records, authorize Ledger PnL --write, certify routes, or clear secrets.
