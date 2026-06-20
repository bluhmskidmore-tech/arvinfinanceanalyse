# PnL Attribution Verification Rerun Approval Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make "verification commands rerun before approval" a checker-enforced business-owner approval item across the `pnl-attribution` readiness gate, approval packet, audit packet, and tests.

**Architecture:** Keep `pnl-attribution` as a candidate/pending workflow and extend only the existing approval-action-item contract. The checker already emits the new `verification_commands_rerun` blocker; the next round syncs stale readiness expectations and packet evidence, then proves strict approval gates still fail until real business-owner approval is captured.

**Tech Stack:** Python pytest, Ruff, PowerShell readiness wrapper, Markdown governance packets.

---

## Scope

Workflow being fixed:
- `pnl-attribution` business-owner approval readiness, specifically the approval item that verification commands must be rerun before approval.

Files to inspect first:
- `scripts/check_pnl_attribution_business_owner_approval.py`
- `scripts/codex_page_readiness.py`
- `scripts/codex-page-readiness.ps1`
- `docs/pnl/pnl-attribution-business-owner-approval-template.md`
- `docs/pnl/pnl-attribution-sign-off-packet.md`
- `docs/pnl/pnl-attribution-governance-audit-packet.md`
- `tests/test_pnl_attribution_business_owner_approval_status.py`
- `tests/test_codex_page_readiness_gate.py`
- `tests/test_pnl_attribution_signoff_packet.py`
- `tests/test_pnl_attribution_governance_record.py`

Do not touch:
- database schema
- auth or permission framework
- queue, scheduler, cache, or shared infrastructure
- unrelated backend services or frontend pages
- formal PnL truth surfaces or production approval state

Preserve these invariants:
- `approval_status=pending` or `candidate_or_pending`
- `business_owner_approval_captured=false`
- `formal_use_allowed=false`
- `closure_approved=false`
- strict approval gates fail while approval is pending
- no doc or output implies formal approval, formal PnL truth, governance writes, page execution proof, or business-owner approval capture

No commits in this plan unless the user explicitly asks.

---

### Task 1: Confirm the New Approval Item Contract

**Files:**
- Read: `scripts/check_pnl_attribution_business_owner_approval.py`
- Read: `docs/pnl/pnl-attribution-business-owner-approval-template.md`
- Test: `tests/test_pnl_attribution_business_owner_approval_status.py`

**Step 1: Inspect the checker contract**

Confirm that `verification_commands_rerun` exists in:
- approval action item definitions
- evidence review field parsing
- `approval_field_status`
- pending approval blockers/action items

Expected:
- the checker treats `- Verification commands rerun before approval: <yes | no>` as required
- the required value is `yes`
- incomplete approval reports this as pending

**Step 2: Run focused checker tests**

Run:

```powershell
python -m pytest tests/test_pnl_attribution_business_owner_approval_status.py::test_pnl_attribution_business_owner_approval_checker_reports_pending_template tests/test_pnl_attribution_business_owner_approval_status.py::test_pnl_attribution_business_owner_approval_checker_captures_complete_approval -q
```

Expected:
- PASS
- pending template reports the new blocker
- filled template treats `verification_commands_rerun` as valid

---

### Task 2: Sync Page Readiness Expectations

**Files:**
- Modify: `tests/test_codex_page_readiness_gate.py`

**Step 1: Update stale action item counts**

Change stale expectations from `10` to `11` wherever they refer to `business_owner_approval_action_item_count`, PowerShell output, or all-page readiness rows.

Expected:
- pending approval count is consistently `11`

**Step 2: Add the new blocker to expected lists**

Add `verification_commands_rerun` to pending blocker expectations after `live_smoke_evidence_review` and before `candidate_boundary_acceptance`.

Expected blocker ordering:

```python
"live_smoke_evidence_review",
"verification_commands_rerun",
"candidate_boundary_acceptance",
```

**Step 3: Add expected field status and action item**

Add:

```python
"verification_commands_rerun": "pending",
```

Add the expected action item:

```python
{
    "blocker": "verification_commands_rerun",
    "template_field": "- Verification commands rerun before approval",
    "required_value": "yes",
    "current_status": "pending",
}
```

**Step 4: Add PowerShell output assertions**

Assert output includes:

```text
- verification_commands_rerun
Verification commands rerun before approval: yes (pending)
```

Expected:
- page readiness tests now describe the same approval contract as the checker

---

### Task 3: Sync Sign-Off and Audit Packets

**Files:**
- Modify: `docs/pnl/pnl-attribution-sign-off-packet.md`
- Modify: `docs/pnl/pnl-attribution-governance-audit-packet.md`
- Modify: `tests/test_pnl_attribution_signoff_packet.py`
- Modify: `tests/test_pnl_attribution_governance_record.py`

**Step 1: Update blocker summaries in packets**

In both packet docs, add `verification_commands_rerun` to the business-owner approval blocker list.

Expected:
- packet blocker summaries match checker output
- packet still says approval is pending/candidate, not approved

**Step 2: Add the approval action item to packets**

Add:

```markdown
- Verification commands rerun before approval: `yes` (`pending`)
```

Expected:
- sign-off and audit packets make rerunning verification a required pre-approval action, not just a note

**Step 3: Update packet tests**

Update direct expected blocker strings in:
- `tests/test_pnl_attribution_signoff_packet.py`
- `tests/test_pnl_attribution_governance_record.py`

Expected:
- generated packet tests match the new required action item

---

### Task 4: Run Focused Governance Verification

**Files:**
- Test: `tests/test_codex_page_readiness_gate.py`
- Test: `tests/test_pnl_attribution_business_owner_approval_status.py`
- Test: `tests/test_pnl_attribution_signoff_packet.py`
- Test: `tests/test_pnl_attribution_governance_record.py`
- Test: `tests/test_golden_samples_capture_ready.py`

**Step 1: Run focused changed tests**

Run:

```powershell
python -m pytest tests/test_pnl_attribution_business_owner_approval_status.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py::test_pnl_attribution_governance_record_can_write_audit_packet tests/test_codex_page_readiness_gate.py::test_pnl_attribution_readiness_exposes_run_commands_without_formal_pnl_promotion tests/test_codex_page_readiness_gate.py::test_all_page_readiness_covers_every_unique_seeded_trace_bundle tests/test_codex_page_readiness_gate.py::test_page_readiness_cli_all_mode_emits_batch_report tests/test_codex_page_readiness_gate.py::test_pnl_attribution_page_readiness_powershell_surfaces_approval_blockers tests/test_codex_page_readiness_gate.py::test_all_page_readiness_powershell_surfaces_pending_approval_summary -q
```

Expected:
- PASS

**Step 2: Run the full PnL governance slice**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py tests/test_golden_samples_capture_ready.py -q
```

Expected:
- PASS
- approval remains pending

---

### Task 5: Run Lint and MCP Regression Checks

**Files:**
- Check: `scripts/mcp/moss_project_mcp.py`
- Check: `scripts/check_pnl_attribution_business_owner_approval.py`
- Check: `scripts/codex_page_readiness.py`
- Check: `scripts/emit_pnl_attribution_governance_record.py`
- Test: `tests/test_project_mcp_servers.py`

**Step 1: Run scoped Ruff**

Run:

```powershell
python -m ruff check scripts/mcp/moss_project_mcp.py scripts/check_pnl_attribution_business_owner_approval.py scripts/codex_page_readiness.py scripts/emit_pnl_attribution_governance_record.py tests/test_project_mcp_servers.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py
```

Expected:
- `All checks passed!`

**Step 2: Run MCP evidence tests**

Run:

```powershell
python -m pytest tests/test_project_mcp_servers.py -q
```

Expected:
- PASS
- no recurrence of the transient MCP indentation failure

---

### Task 6: Prove Strict Approval Gates Still Block

**Files:**
- Check: `scripts/check_pnl_attribution_business_owner_approval.py`
- Check: `scripts/codex-page-readiness.ps1`

**Step 1: Run strict Python approval gate**

Run:

```powershell
python scripts\check_pnl_attribution_business_owner_approval.py --require-captured
```

Expected:
- exits non-zero
- reports approval capture is required but incomplete
- includes `verification_commands_rerun`
- reports `approval_action_item_count=11`

**Step 2: Run strict all-page readiness gate**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -All -RequireApprovalCaptured
```

Expected:
- exits non-zero
- reports `pnl-attribution`
- includes `verification_commands_rerun`
- does not imply approval capture

**Step 3: Run strict single-page readiness gate**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured
```

Expected:
- exits non-zero
- reports approval pending/candidate
- includes the new action item

---

### Task 7: Final Report

**Files:**
- Report only; do not commit unless asked.

**Step 1: Summarize root cause**

Expected wording:
- the checker contract gained an eleventh approval item, but readiness tests and governance packet expectations still reflected the old ten-item contract

**Step 2: List changed files**

Include only files actually changed in the execution round.

**Step 3: Report verification evidence**

Include:
- focused pytest result
- full PnL governance slice result
- Ruff result
- MCP suite result
- strict approval commands intentionally failing with pending approval

**Step 4: State remaining risk**

Required:
- real business-owner approval is still external and not captured
- `pnl-attribution` remains candidate/pending
- no formal PnL truth promotion was performed
