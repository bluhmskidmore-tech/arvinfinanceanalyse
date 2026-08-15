# Calculation P1 Post-Owner Execution Plan

Source snapshot status: `source_snapshot_status=owner_decision_required`
Global owner gate ready: `false`
Implementation ready: `false`
Source snapshot generated at: `2026-08-06T22:30:00+08:00`

This plan prepares deterministic execution routing after owner/governance input is captured. It does not select or approve any calculation convention.

## Summary

- `row_count=8`
- `captured_decision_count=0`
- `post_owner_required_fields=selected_decision, owner_rationale, implementation_owner, verification_gate, status`
- `ready_for_implementation_count=0`
- `deferred_count=0`
- `rejected_count=0`
- `non_implementation_decision_count=0`
- `incomplete_count=8`
- `post_owner_blocking_reasons=owner_decision_capture_incomplete`
- `meeting_record_complete=false`
- `missing_meeting_field_count=8`
- `invalid_status_count=0`
- `invalid_selected_decision_count=0`
- `global_owner_decision_gate_ready=false`
- `implementation_ready=false`

## Source Artifacts

- `calculation_owner_decision_snapshot`: `docs/audits/2026-06-10-calculation-p1-owner-decision-snapshot.json`
- `owner_decision_capture_template_zh`: `docs/audits/2026-06-10-owner-decision-capture-template.zh.md`
- `calculation_owner_decision_packet`: `docs/audits/2026-06-10-calculation-p1-owner-decision-packet.md`
- `calculation_owner_meeting_checklist`: `docs/audits/2026-06-10-calculation-p1-owner-meeting-checklist.md`

## Readiness Checks

- `decision_ids_match_expected=true`
- `all_execution_slice_paths_exist=true`
- `no_invalid_statuses=true`
- `no_invalid_selected_decisions=true`
- `source_snapshot_is_owner_decision_required=true`
- `live_template_matches_snapshot_missing_fields=true`
- `owner_decision_capture_complete=false`
- `non_implementation_decisions_present=false`
- `global_owner_decision_gate_ready=false`
- `implementation_ready=false`
- `captures_owner_decisions=false`
- `chooses_or_approves_conventions=false`
- `changes_implementation_code=false`

## Execution Queues

| Queue | Count | P1 IDs |
| --- | ---: | --- |
| `ready_for_implementation` | 0 | none |
| `deferred` | 0 | none |
| `rejected` | 0 | none |
| `incomplete` | 8 | `P1-01`, `P1-02`, `P1-03`, `P1-04`, `P1-05`, `P1-06`, `P1-10`, `P1-11` |

## Row Routing

| P1 | Status | Queue | Implementation owner | Verification gate | Invalid selected decision | Missing capture fields | Owner decision gate | Referenced path count | Missing referenced paths |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| `P1-01` | `pending` | `incomplete` | none | suggested: `docs/calc_rules.md` + numeric golden tests | none | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | `docs/calc_rules.md` unit rule; one implementation path; numeric golden test for decimal and percent-shaped inputs. | 4 | none |
| `P1-02` | `pending` | `incomplete` | none | suggested: source contract evidence + sub-1% regression | none | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | Data-catalog/source contract evidence; formal engine regression for sub-1% rates; no heuristic in formal path. | 1 | none |
| `P1-03` | `pending` | `incomplete` | none | suggested: shared rule/helper + losing-side tests updated | none | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | `docs/calc_rules.md` section for roll-down sign; one shared helper or adapter; tests updated on the losing side. | 2 | none |
| `P1-04` | `pending` | `incomplete` | none | suggested: independent source anchors or non-control label | none | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | Reconciliation evidence uses two independent sources, or UI/report explicitly marks the check as non-control. | 1 | none |
| `P1-05` | `pending` | `incomplete` | none | suggested: monthly/quarterly/yearly numeric tests | none | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | Rule written to `calc_rules.md`; numeric tests for monthly, quarterly, and yearly buckets. | 2 | none |
| `P1-06` | `pending` | `incomplete` | none | suggested: zero-actual nonzero-explained warning regression | none | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | Regression where `actual_pnl=0` and explained amount nonzero returns warning and visible diagnostics. | 3 | none |
| `P1-10` | `pending` | `incomplete` | none | suggested: backend DTO / frontend removal tests | none | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | Backend DTO added or confirmed; frontend removes formal aggregation; adapter/component tests consume DTO values. | 1 | none |
| `P1-11` | `pending` | `incomplete` | none | suggested: API contract + frontend renders provided matrix | none | `selected_decision`, `owner_rationale`, `implementation_owner`, `verification_gate`, `status` | API contract for rating-tenor matrix; frontend renders provided matrix only; regression covers bucket boundaries. | 2 | none |

## Prohibited Actions

- treat approved-for-implementation rows as metric approval
- execute a row before selected_decision, owner_rationale, implementation_owner, verification_gate, and status are captured
- execute implementation when the meeting record is incomplete
- choose a convention for any pending, deferred, rejected, or invalid row
- write governance records or authorize Ledger PnL --write from this plan

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

This plan is a read-only post-owner execution router. It only classifies captured rows into execution queues and lists existing engineering anchors; it does not choose or approve conventions, capture owner decisions, change code, write DuckDB or governance records, approve metrics/pages, authorize Ledger PnL --write, certify routes, or clear secrets.
