# Portfolio Home Full-Closure Sign-Off Packet

Page ID: `PAGE-PORTFOLIO-HOME-001`
Page slug: `portfolio`
Primary API: `frontend aggregation: module-home/portfolio`
Approval status: `candidate_or_pending`
Formal use allowed: `formal_use_allowed=false`
Closure approved: `closure_approved=false`
Current closure score: `99.86 / 100`
Remaining full-score gap: `0.14`

## Decision Boundary

This packet is prepared for business-owner and risk-owner review only. It does not approve page closure, metric formal use, or portfolio decision-grade wording.

- Do not promote `/portfolio` to decision-grade page closure.
- Do not restate same-day risk-date closure as full risk-tensor closure.
- Do not turn `quality_flag=warning` into `quality_flag=ok` without rematerialized evidence.
- Do not use frontend fill, inferred maturity dates, or synthetic KRD buckets as approval evidence.

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_capture_ready_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## Evidence Anchors

- Audit packet: `docs/audits/2026-06-05-portfolio-readiness-gate-audit.md`
- Business-owner approval template: `docs/portfolio/portfolio-home-business-owner-approval-template.md`
- Risk warning consistency check: `scripts/portfolio_home_risk_warning_consistency.py`
- KRD remap review queue: `scripts/portfolio_home_krd_remap_review_queue.py`
- KRD contract decision export: `scripts/portfolio_home_krd_contract_decision_export.py`
- KRD contract decision owner summary: `docs/portfolio/krd-contract-decision/2026-05-31/owner_summary.md`
- Maturity remediation queue: `scripts/portfolio_home_maturity_remediation_queue.py`
- Maturity remediation export: `scripts/portfolio_home_maturity_remediation_export.py`
- Maturity remediation owner summary: `docs/portfolio/maturity-remediation/2026-05-31/owner_summary.md`
- Closure artifact presence check: `scripts/portfolio_home_closure_artifact_presence_check.py`
- Evidence packet guard: `scripts/portfolio_home_evidence_packet_guard.py`
- Evidence snapshot: `scripts/portfolio_home_evidence_snapshot.py`
- Owner action packet: `scripts/portfolio_home_owner_action_packet.py`
- Business owner approval packet: `scripts/portfolio_home_business_owner_approval_packet.py`
- Supporting portfolio sample: `GS-PORTFOLIO-HOME-A`
- Risk warning sample: `GS-RISK-WARN-B`
- Live fallback proof: headless Playwright check recorded in the audit packet
- Decision anchor date: `2026-05-31`
- Risk date evidence: `risk_closure_ready=true` for date-gate wording only
- Downstream risk tensor payload: `quality_flag=warning`

## Current Real-Data Evidence

The current DuckDB state was read in `read_only=True` mode. No database data was modified for this packet.

Risk tensor fact row for `2026-05-31`:

```text
quality_flag=warning
portfolio_dv01=105628442.39590558
krd_sum=105628442.39590558
source_version=sv_risk_tensor__sv_837e9f35fdda__sv_67bf20398f44
upstream_source_version=sv_837e9f35fdda
liability_source_version=sv_67bf20398f44
```

Risk tensor warnings:

```text
Non-standard tenor buckets remapped to nearest KRD bucket: 20Y, 2Y, 6M
120 rows carry market_value=38318400505.50000008 and are excluded from portfolio duration denominator: 114 without maturity_date; 6 with non-positive modified_duration.
Excluded 114 rows without maturity_date from liquidity gap calculation.
Excluded 1455 liability rows without maturity_date from liquidity gap calculation.
```

Risk warning consistency:

```text
Risk warning consistency: `warning_consistency_status=mismatch`
Risk warning decision status: `decision_status=blocked`
consistency_blockers=duration_exclusion_warning_mismatch
decision_blockers=risk_tensor_quality_warning, risk_tensor_warning_mismatch
duration_exclusion parsed row_count=120, market_value_sum=38318400505.50000008, missing_maturity_rows=114, nonpositive_duration_rows=6
duration_exclusion recomputed row_count=120, market_value_sum=39109594105.50000008, missing_maturity_rows=114, nonpositive_duration_rows=6
bond_liquidity_gap missing_maturity_rows=114
tyw_liability_liquidity_gap missing_maturity_rows=1455
krd_buckets=20Y, 2Y, 6M
```

Bond maturity gap:

```text
fact_formal_bond_analytics_daily, report_date=2026-05-31
row_count=1710
missing_maturity_rows=114
missing_maturity_market_value=37622164239.83000008
```

TYW liability maturity gap, risk-tensor input scope:

```text
fact_formal_tyw_balance_daily, report_date=2026-05-31
position_scope=liability
currency_basis=CNY
row_count=3071
missing_maturity_rows=1455
missing_maturity_principal=43822652393.01000002
```

TYW full formal table profile:

```text
fact_formal_tyw_balance_daily, report_date=2026-05-31
row_count=6514
missing_maturity_rows=3106
missing_maturity_principal=95975460037.78000008
```

The full-table count is larger because the formal TYW table carries both `CNY` and `native` currency-basis rows. The risk tensor uses only `position_scope=liability` and `currency_basis=CNY`.

Maturity remediation export for data-owner review:

```text
manifest=docs/portfolio/maturity-remediation/2026-05-31/manifest.json
bond_csv=docs/portfolio/maturity-remediation/2026-05-31/bond_missing_maturity.csv
tyw_liability_csv=docs/portfolio/maturity-remediation/2026-05-31/tyw_liability_missing_maturity.csv
export_status=blocked
bond_missing_maturity_rows=114
tyw_liability_missing_maturity_rows=1455
proposed_maturity_date columns are intentionally blank for owner/source remediation.
```

Largest maturity-remediation queue rows sampled from the current real database:

```text
Bond missing maturity sample, order by market_value desc:
SA0106070101, market_value=2103574090.74000000, tenor_bucket=6M, trace_id=ffa8fb22-4d9a-4352-91fa-03eba25c98d5
SA0207360101, market_value=1555799222.10000000, tenor_bucket=6M, trace_id=c08602d6-94d4-4503-8f56-8b5cb39d8b4d
SA0212890101, market_value=1217040000.00000000, tenor_bucket=6M, trace_id=e02c9982-9e8f-49a3-8d9a-8b66927d737c

TYW liability missing maturity sample, order by principal_amount desc:
802010201929379, principal_amount=5936179478.40000000, counterparty=中信信托有限责任公司, trace_id=5201ad34-40fe-4656-8e52-f323176bc3af
802010201895068, principal_amount=2500000000.00000000, counterparty=兴业银行股份有限公司青岛分行, trace_id=3c207177-865e-43bb-b65d-e1deeded4c69
802010201960657, principal_amount=1455500000.00000000, counterparty=上银理财有限责任公司, trace_id=cb897a2b-57b1-4c9d-b76f-b7cd4851e104
```

KRD remap scope, non-zero DV01 rows:

```text
20Y: all_rows=39, nonzero_dv01_rows=39, all_market_value=22035562498.29000004, nonzero_dv01_market_value=22035562498.29000004, dv01_sum=23598290.06912522, mapped_to=krd_30y
2Y: all_rows=301, nonzero_dv01_rows=301, all_market_value=48919869887.65000000, nonzero_dv01_market_value=48919869887.65000000, dv01_sum=9037781.19296191, mapped_to=krd_3y
6M: all_rows=282, nonzero_dv01_rows=160, all_market_value=62550571662.68000010, nonzero_dv01_market_value=24232171157.18000002, dv01_sum=544906.37425771, mapped_to=krd_1y
```

KRD contract decision export for risk-owner review:

```text
manifest=docs/portfolio/krd-contract-decision/2026-05-31/manifest.json
summary_csv=docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_summary.csv
detail_csv=docs/portfolio/krd-contract-decision/2026-05-31/krd_remap_detail.csv
owner_summary=docs/portfolio/krd-contract-decision/2026-05-31/owner_summary.md
export_status=decision_required
remap_tenor_count=3
nonzero_dv01_rows=500
dv01_sum=33180977.63634484
risk_owner_decision columns are intentionally blank; this export does not approve nearest-bucket mapping.
```

Largest KRD remap review rows sampled from the current real database:

```text
200004, dv01=8246445.66600614, tenor_bucket=20Y, mapped_to=krd_30y, trace_id=3f678076-1d7c-49ec-847e-f280b25cef75
2005399, dv01=2009635.95767714, tenor_bucket=20Y, mapped_to=krd_30y, trace_id=06f6f3a3-d3c0-4c36-84bf-e2ac06a24fa9
2005298, dv01=1332277.08948445, tenor_bucket=20Y, mapped_to=krd_30y, trace_id=8fbdf8fd-8ebf-42ec-822e-65081c85e781
```

## Full-Score Closure Gates

Gate 1: KRD contract decision.

- Option A: approve the current minimal six-bucket KRD tensor and formally accept nearest-bucket mappings for `2Y`, `6M`, and `20Y`.
- Option B: reject nearest-bucket approval and expand schema/API/UI to carry exact tenor buckets before any full closure claim.
- Required evidence either way: row-level KRD review queue from `python scripts/portfolio_home_krd_remap_review_queue.py`, owner decision, updated metric contract, tests, and rerun risk tensor evidence.

Gate 2: maturity data remediation.

- Remediate missing `maturity_date` in upstream bond and TYW liability sources, then rematerialize formal bond analytics, balance facts, and risk tensor.
- If a business owner accepts a scoped exclusion instead, the exclusion must be explicit, signed, and shown as a warning or scope boundary. It must not be hidden behind `quality_flag=ok`.
- Required evidence: row-level remediation queue from `python scripts/portfolio_home_maturity_remediation_queue.py`, row-level remediation file or approved exclusion scope, before/after counts, rematerialization result, risk tensor warnings review.

Gate 3: capture-ready page governance.

- Convert the fallback live proof into capture-ready page evidence.
- Review `GS-PORTFOLIO-HOME-A`; keep it supporting-only unless it is replaced by a live capture-ready sample.
- Write or approve the primary `/portfolio` governance record only after evidence parity and owner review are complete.

Gate 4: business-owner approval.

- Complete and sign `docs/portfolio/portfolio-home-business-owner-approval-template.md`.
- Approval must explicitly decide KRD mapping, maturity remediation/exclusion, warning handling, and whether the page remains candidate-only.
- Until then, keep `formal_use_allowed=false` and `closure_approved=false`.

## Business Owner Approval Action Items

- Business owner name: `Business owner legal or operating name` (`missing`)
- Business owner role: `Business owner accountability role` (`missing`)
- Risk owner name: `Risk owner legal or operating name` (`missing`)
- Risk owner role: `Risk owner accountability role` (`missing`)
- Approval decision: `approve | reject | request_changes` (`missing`)
- Approval date: `YYYY-MM-DD` (`missing`)
- Business owner signature: `Business owner signature` (`missing`)
- Risk owner signature: `Risk owner signature` (`missing`)
- KRD contract decision: `approve_nearest_bucket | require_exact_bucket_schema | reject` (`missing`)
- Maturity data decision: `remediate_source | approve_scoped_exclusion | reject` (`missing`)
- Risk tensor warning decision: `keep_warning | approve_after_clean_rerun | request_changes` (`missing`)
- Governance record reviewed: `yes` (`pending`)
- Supporting sample `GS-PORTFOLIO-HOME-A` reviewed: `yes` (`pending`)
- Risk warning sample `GS-RISK-WARN-B` reviewed: `yes` (`pending`)
- Live proof reviewed: `yes` (`pending`)
- DuckDB maturity-gap evidence reviewed: `yes` (`pending`)
- KRD remap evidence reviewed: `yes` (`pending`)
- Verification commands rerun before approval: `yes` (`pending`)
- Candidate-only boundary accepted: `yes` (`pending`)

## Reviewer Handoff

Handoff status: `ready_for_risk_and_business_owner_review_pending_signature`
Approval action item count: `19`
Approval template to complete: `docs/portfolio/portfolio-home-business-owner-approval-template.md`

This handoff does not capture approval, write governance records, prove capture-ready page parity, or grant closure. Keep `formal_use_allowed=false` and `closure_approved=false` until business-owner approval and rematerialized evidence are explicitly captured.

## Verification Evidence

Fresh verification performed for this packet:

```text
DuckDB read-only evidence query for bond maturity gap, TYW liability maturity gap, KRD remap scope, and risk tensor warning boundary
python scripts/portfolio_home_full_closure_evidence.py
python scripts/portfolio_home_full_closure_evidence.py --require-clean
python scripts/portfolio_home_risk_warning_consistency.py --require-consistent
python scripts/portfolio_home_risk_warning_consistency.py --require-clean
python scripts/portfolio_home_krd_remap_review_queue.py
python scripts/portfolio_home_krd_remap_review_queue.py --require-clean
python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision
python scripts/portfolio_home_krd_contract_decision_export.py --output-dir docs/portfolio/krd-contract-decision --require-clean
python scripts/portfolio_home_maturity_remediation_queue.py
python scripts/portfolio_home_maturity_remediation_queue.py --require-empty
python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation
python scripts/portfolio_home_maturity_remediation_export.py --output-dir docs/portfolio/maturity-remediation --require-clean
python scripts/portfolio_home_closure_artifact_presence_check.py --limit 3 --require-current
python scripts/portfolio_home_evidence_packet_guard.py --require-clean
python scripts/portfolio_home_closure_scorecard.py --limit 3
python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score
python scripts/portfolio_home_evidence_snapshot.py --scorecard-limit 1 --verifier-limit 1 --require-verifier-matched
python scripts/portfolio_home_owner_action_packet.py --limit 3
python scripts/portfolio_home_owner_action_packet.py --limit 3 --require-clean
python scripts/portfolio_home_business_owner_approval_packet.py --limit 3
python scripts/portfolio_home_business_owner_approval_packet.py --limit 3 --require-ready
python scripts/portfolio_home_dependency_consistency_check.py --limit 3
python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent
python scripts/portfolio_home_owner_decision_intake_check.py --limit 3
python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready
Headless Playwright fallback proof recorded in docs/audits/2026-06-05-portfolio-readiness-gate-audit.md
python scripts/check_portfolio_home_business_owner_approval.py
python scripts/check_portfolio_home_business_owner_approval.py --require-captured
python -m pytest tests/test_golden_samples_capture_ready.py::test_supporting_only_golden_sample_files_exist_without_capture_ready_claim -q
python scripts/verify_portfolio_home_scorecard_commands.py --require-matched
```

Observed status:

- Current portfolio closure score remains `99.86 / 100`.
- Remaining gap remains `0.14`.
- Score methodology is `discrete_full_closure_gate`; the `0.14` gap is not allocated across blockers as linear weights.
- Closure scorecard reports `score_status=blocked` and `full_score_ready=false`.
- Closure scorecard strict full-score gate exits non-zero while score blockers remain.
- Closure scorecard blockers: `risk_tensor_quality_warning`, `krd_contract_decision_required`, `bond_maturity_date_remediation_required`, `tyw_liability_maturity_date_remediation_required`, `duration_exclusion_warning_mismatch`, `risk_tensor_warning_mismatch`, `business_owner_approval`, `owner_decision_intake_blocked`.
- Closure scorecard action map records `owner`, `next_action`, `evidence_command`, and `exit_criteria` for every score blocker.
- Closure scorecard gates carry `score_blocker_action_coverage.status=clean`; unknown or unassigned score blockers prevent strict activation.
- Closure scorecard emits `verification_commands` with evidence, strict-gate, and regression commands plus expected blocked-state exits.
- Scorecard command verifier supports both `--expected-state blocked` and `--expected-state full_score`; current evidence should match only the blocked-state strict-gate expectations.
- Closure scorecard gates carry KRD `decision_options`/`review_actions` and maturity `remediation_scope`/`remediation_actions`.
- Closure scorecard gates carry risk tensor quality/source summary, KRD remap scale, and maturity missing-row amount summaries.
- Closure scorecard gates now carry `owner_decision_intake` with intake status, owner statuses, decision alignment, decision gaps, note/comment gaps, and nearest-bucket approval or exact-bucket schema evidence.
- Closure scorecard owner-decision intake gate now exposes `owner_input_boundary`, and `owner_decision_intake_alignment.compared_fields` includes it to prevent generated-owner boundaries drifting from direct intake evidence.
- Closure scorecard gates carry `approval_dependency_consistency`; stale or mismatched KRD/maturity manifests add `approval_dependency_consistency_blocked` and prevent `full_score_ready=true`.
- Closure scorecard `approval_dependency_consistency` gate also exposes `generated_owner_fields_boundaries` so missing manifest acceptance criteria is visible without opening manifest details.
- Closure scorecard treats owner-decision intake as the final full-score guard: if all upstream gates are clean but intake is not ready, `owner_decision_intake_blocked` prevents `full_score_ready=true`.
- Closure scorecard has a positive full-score regression path, but the current real template keeps full-closure scope disabled.
- Evidence snapshot reports `snapshot_kind=portfolio_home_closure_evidence`, `score_status=blocked`, `full_score_ready=false`, and an embedded verifier status of `matched_expected_blocked_state`.
- Evidence snapshot summarizes the current gate statuses without changing the score: full closure blocked, risk warning decision blocked, KRD contract decision required, maturity remediation blocked, and business-owner approval pending.
- Evidence snapshot gate summary now exposes `owner_decision_intake_status=pending`, `owner_decision_intake_ready=false`, and the current owner-decision blockers.
- Evidence snapshot gate summary now exposes `approval_dependency_consistency_status=consistent`, dependency blockers, and `generated_owner_fields_boundaries` from the scorecard gate.
- Evidence snapshot now embeds `business_owner_approval_packet_summary` with `packet_status=pending`, `activation_ready=false`, `approval_action_item_count=19`, and `dependency_consistency_status=consistent`.
- Evidence snapshot also exposes `csv_check_summary` with KRD summary/detail row counts, maturity queue row counts, and blank owner/proposed-field status.
- Evidence snapshot now exposes `owner_decision_intake_summary` with `intake_status=pending_owner_decisions`, three pending owner statuses, and the current owner-decision blockers.
- Evidence snapshot owner-decision intake summary also exposes `csv_check_summary` and `generated_owner_fields_boundaries`, so intake reviewers see queue row counts and generated-owner boundaries without opening the dependency check.
- Evidence snapshot owner-decision intake summary also exposes `owner_input_boundary`, so filled owner CSV fields are visible as owner input rather than generated approval evidence.
- Evidence snapshot now exposes `scorecard_owner_decision_intake_gate_summary` and `owner_decision_intake_alignment` so direct intake evidence is checked against the full-score gate view.
- Evidence snapshot scorecard owner-decision gate summary now carries `owner_input_boundary`, and the alignment comparison includes it.
- Evidence snapshot now exposes `score_blocker_action_coverage` in the gate summary and business-owner approval summary.
- Evidence snapshot now exposes `owner_summary_paths` with the KRD contract decision owner summary and maturity remediation owner summary.
- Evidence snapshot now exposes `generated_owner_fields_boundaries` so reviewers can see both KRD and maturity export manifests require `generated_owner_fields_must_be_blank=true`.
- Evidence snapshot now exposes `decision_gap_counts` with KRD owner decision gaps of 503 rows (summary 3, detail 500) and maturity owner decision gaps of 1569 rows (bond 114, TYW liability 1455).
- Evidence snapshot now exposes `note_gap_counts`; current real CSVs have blank owner decisions, so note/comment gaps are empty until a decision is filled without rationale.
- Evidence snapshot now exposes `exact_bucket_schema_evidence` so reviewers can see whether the exact-bucket schema path has metric-contract, API-schema, rematerialization, and verifier evidence.
- Owner action packet reports `handoff_status=owner_actions_required` and groups the current blockers into `risk_owner`, `data_owner`, and `business_owner` packets.
- Owner action packet reports `assignment_coverage.status=clean`; `unassigned_blockers`, `duplicate_assigned_blockers`, and `unexpected_assigned_blockers` are empty.
- Owner action packet strict clean gate also requires `score_blocker_action_coverage.status=clean`.
- Owner action packet carries `dependency_consistency_status=consistent` and the same `csv_check_summary` into risk-owner, data-owner, and business-owner packets.
- Owner handoff Markdown summary surfaces the same CSV row counts, blank owner-field status, generated-owner manifest boundaries, and export-current system-field gate before the checklist.
- Owner handoff Markdown summary states export-current system fields prove package freshness only; they do not approve KRD decisions, maturity remediation, signed exclusions, or business-owner closure.
- Owner action packet carries KRD `note_gap_counts`, maturity `comment_gap_counts`, and `exact_bucket_schema_evidence` into the owner packets without changing approval status.
- Owner action packet carries `owner_decision_intake_alignment.status=consistent` into the owner packets so owners can see activation evidence alignment before signing.
- Owner action packet assigns `risk_tensor_warning_mismatch` to the risk-owner packet, `duration_exclusion_warning_mismatch` to the data-owner packet, and `owner_decision_intake_blocked` to the business-owner packet so no score blocker is left unowned.
- Owner action packet strict clean gate exits non-zero while any owner packet remains blocked.
- Business owner approval packet reports `packet_status=pending`, `activation_ready=false`, and `approval_action_item_count=19`.
- Business owner approval packet lists sign-off, audit, evidence snapshot, owner action, KRD decision export, maturity remediation export, scorecard strict gate, and approval strict gate dependencies.
- Business owner approval packet lists the KRD and maturity owner summaries as evidence dependencies, but does not treat them as approvals.
- Business owner approval packet activation guard also requires dependency consistency and owner decision intake strict gates before full activation.
- Business owner approval packet reports `dependency_consistency_status=consistent` only when the KRD and maturity manifests match the current scorecard report date, blocked status, row counts, and amount totals.
- Business owner approval packet also checks the exported CSV row counts and keeps KRD `risk_owner_decision`/`decision_notes` plus maturity `proposed_maturity_date`/`owner_decision`/`owner_comment` fields blank.
- Business owner approval packet also carries `note_gap_counts` and `exact_bucket_schema_evidence` into the approval review payload without treating them as approvals.
- Business owner approval packet also exposes the scorecard `gates.owner_decision_intake` summary, so approval review can compare direct intake evidence with the full-score gate view.
- Business owner approval packet scorecard gate summary also carries `owner_input_boundary`, and activation alignment compares it before approval.
- Business owner approval packet also enforces `owner_decision_intake_alignment.status=consistent` before activation.
- Business owner approval packet also enforces `score_blocker_action_coverage.status=clean` before activation.
- Business owner approval packet also exposes `generated_owner_fields_boundaries`, so the approval entry point itself shows that KRD and maturity exports must keep generated owner fields blank.
- Dependency consistency check strict gate exits 0 only when the KRD and maturity manifests plus CSV queues match the current scorecard evidence.
- Dependency consistency check also exposes `generated_owner_fields_boundaries` directly, matching the scorecard and business-owner approval packet boundary summary.
- CSV summary currently reports `krd_summary_row_count=3`, `krd_detail_row_count=500`, `bond_missing_maturity_row_count=114`, `tyw_liability_missing_maturity_row_count=1455`, and blank owner/proposed fields.
- Owner decision intake check reports `intake_status=pending_owner_decisions` and `intake_ready=false` until risk-owner CSV decisions, conditional KRD evidence, data-owner CSV decisions, scoped-exclusion evidence, and business-owner approval are all filled.
- Owner decision intake check also exposes `csv_check_summary` and `generated_owner_fields_boundaries` at the top level before owner decisions are accepted.
- Owner decision intake check also exposes `owner_input_boundary` so allowed pre-intake owner-field blockers are separated from active dependency blockers.
- Owner decision intake strict ready gate exits non-zero in the current real-data state.
- KRD manifest consistency checks `remap_tenor_count=3`, `nonzero_dv01_rows=500`, and `dv01_sum=33180977.63634484`.
- Maturity manifest consistency checks `bond_missing_maturity_rows=114`, `tyw_liability_missing_maturity_rows=1455`, `bond_missing_maturity_market_value=37622164239.83000008`, and `tyw_liability_missing_maturity_principal=43822652393.01000002`.
- Business owner approval packet strict ready gate exits non-zero while the template is pending or any full-score blocker remains.
- Full-closure evidence script reports `data_quality_status=blocked`.
- Full-closure evidence strict clean gate exits non-zero while risk tensor and maturity blockers remain.
- Risk warning consistency strict gate exits non-zero while parsed and recomputed duration-exclusion evidence remains mismatched.
- Risk tensor rematerialization preview is read-only: it would clear `duration_exclusion_warning_mismatch`, but `preview_decision_status=blocked` remains because `preview_quality_flag=warning`.
- Risk warning clean gate exits non-zero while `quality_flag=warning` remains.
- KRD remap review queue reports `review_status=decision_required`.
- KRD remap review queue exposes `decision_options=approve_nearest_bucket|require_exact_bucket_schema|reject` and `review_actions` for risk-owner decision.
- KRD remap review queue strict clean gate exits non-zero while nearest-bucket approval is pending.
- KRD contract decision export writes full risk-owner CSV queues plus a manifest under `docs/portfolio/krd-contract-decision/2026-05-31/`.
- KRD contract decision export also writes the risk-owner summary `docs/portfolio/krd-contract-decision/2026-05-31/owner_summary.md`.
- KRD contract decision owner summary shows `generated_owner_fields_must_be_blank=true` so generated CSV fields cannot be mistaken for captured owner decisions.
- KRD contract decision export reports `export_status=decision_required`, `remap_tenor_count=3`, `nonzero_dv01_rows=500`, and `dv01_sum=33180977.63634484`.
- KRD contract decision export strict clean gate exits non-zero until the risk-owner decision is captured in the metric contract or exact-bucket schema is implemented.
- Maturity remediation queue reports `remediation_status=blocked`.
- Maturity remediation queue exposes `remediation_scope` and `remediation_actions` for data-owner remediation or signed exclusion.
- Maturity remediation queue strict empty gate exits non-zero while missing maturity rows remain.
- Maturity remediation export writes full data-owner CSV queues plus a manifest under `docs/portfolio/maturity-remediation/2026-05-31/`.
- Maturity remediation export also writes the data-owner summary `docs/portfolio/maturity-remediation/2026-05-31/owner_summary.md`.
- Maturity remediation owner summary shows `generated_owner_fields_must_be_blank=true` so generated proposed dates or owner decisions cannot be mistaken for remediation evidence.
- Maturity remediation export reports `export_status=blocked`, `bond_missing_maturity_rows=114`, `tyw_liability_missing_maturity_rows=1455`, and blank `proposed_maturity_date` fields.
- Maturity remediation export strict clean gate exits non-zero until the source remediation queue is empty or a signed scoped exclusion is captured.
- Closure artifact presence check reports `status=current`, `current=true`, and no blockers.
- Evidence packet guard requires the evidence snapshot, owner handoff packet, and this sign-off packet to carry the closure artifact presence command and currentness summary.
- `GS-PORTFOLIO-HOME-A` remains supporting-only.
- Approval checker default status reports `business_owner_approval_captured=false`.
- Approval checker supports explicit full-page approval only when `formal_use_allowed=true`, `closure_approved=true`, `approves_metric_or_page=true`, `writes_governance_records=true`, and `proves_capture_ready_page_execution=true` are all captured together.
- Approval checker strict captured gate exits non-zero while the template is pending.
- Scorecard verification command runner reports `verification_status=matched_expected_blocked_state`.
- The page may show same-day risk-date closure, but must not claim full risk-tensor decision closure.
- Full closure still requires KRD contract decision, maturity remediation or signed exclusion scope, capture-ready page evidence, business-owner approval, and owner-decision intake reconciliation.
