# PnL Attribution Governance Gate Stabilization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stabilize the `pnl-attribution` candidate governance gate so MCP evidence packet tests, readiness gates, approval checks, and sign-off documents agree while approval remains pending.

**Architecture:** Treat the expanded evidence-scope flags in `scripts/mcp/moss_project_mcp.py` as the stricter production contract. The next round should update stale test expectations and packet evidence only where they are out of sync with that contract, then verify that strict approval gates still fail until real business-owner approval is captured.

**Tech Stack:** Python pytest, Ruff, PowerShell readiness wrapper, project MCP server test harness, Markdown governance packets.

---

## Scope

Workflow being fixed:
- `pnl-attribution` candidate governance readiness and MCP evidence packet closure.

Files to inspect first:
- `tests/test_project_mcp_servers.py`
- `scripts/mcp/moss_project_mcp.py`
- `docs/pnl/pnl-attribution-sign-off-packet.md`
- `docs/pnl/pnl-attribution-governance-audit-packet.md`
- `scripts/check_pnl_attribution_business_owner_approval.py`
- `scripts/codex_page_readiness.py`
- `scripts/codex-page-readiness.ps1`

Do not touch:
- database schema
- auth or permission framework
- queue, scheduler, cache, or shared infrastructure
- global SDK wrappers
- unrelated frontend pages or backend services
- formal PnL truth surfaces such as `/api/pnl/overview` or `/ui/pnl/attribution`

Preserve these invariants:
- `approval_status=candidate_or_pending`
- `formal_use_allowed=false`
- `closure_approved=false`
- `business_owner_approval_captured=false`
- strict approval commands fail while approval is incomplete
- no code path implies page execution, UI/API smoke execution, governance writes, approval capture, or formal metric/page approval unless separately proven

No commits in this plan unless the user explicitly asks.

---

### Task 1: Reproduce the Current MCP Failure

**Files:**
- Read: `tests/test_project_mcp_servers.py`
- Read: `scripts/mcp/moss_project_mcp.py`

**Step 1: Run the focused failing pair**

Run:

```powershell
python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_direct_record_remediation_scope_audit_counts_next_steps tests/test_project_mcp_servers.py::test_lineage_evidence_governance_audit_evidence_packet_queue_collects_ready_pages_only -q
```

Expected:
- first test passes
- second test fails on stale expected `evidence_scope` dictionaries
- actual output includes explicit false flags such as `executes_tool_calls`, `runs_ui_or_api_smoke`, and `captures_business_owner_approval`

**Step 2: Confirm production scope contract**

Inspect only the relevant builders/audits in `scripts/mcp/moss_project_mcp.py`:
- direct record remediation work item creation
- direct record table anchor creation
- queue boundary audit / direct record remediation scope audit
- evidence packet queue summary assembly

Expected:
- production already emits the expanded false scope flags
- no production code should be loosened to satisfy stale tests

---

### Task 2: Sync the Stale Expected MCP Payloads

**Files:**
- Modify: `tests/test_project_mcp_servers.py`

**Step 1: Update the failing expected dictionary only**

In `test_lineage_evidence_governance_audit_evidence_packet_queue_collects_ready_pages_only`, update stale nested `evidence_scope` expectations under sections such as:
- `create_direct_record_table_anchor_work_items`
- `repair_direct_record_evidence_work_items`
- `direct_record_remediation_work_items`
- `blocked_by_record_gap_next_steps`
- `direct_record_remediation_scope_audit`
- `queue_boundary_audit`

Where the actual work item is direct-record remediation or direct-record table-anchor evidence, the expected scope must include:

```python
"executes_tool_calls": False,
"runs_ui_or_api_smoke": False,
"captures_business_owner_approval": False,
```

Where a scope is specifically a record-existence or table-sampling preflight, keep its existing specialized keys such as:

```python
"checks_record_existence": False,
"samples_duckdb_tables": False,
```

Do not add unrelated scope keys to payload types that do not emit them.

**Step 2: Keep assertions strict**

Do not normalize away extra keys and do not switch the large expected payload to broad subset matching. The test should continue to catch accidental evidence-scope drift.

---

### Task 3: Verify the MCP Suite

**Files:**
- Test: `tests/test_project_mcp_servers.py`
- Read: `scripts/mcp/moss_project_mcp.py`

**Step 1: Run the focused test**

Run:

```powershell
python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_governance_audit_evidence_packet_queue_collects_ready_pages_only -q
```

Expected:
- PASS

**Step 2: Run the full MCP evidence suite**

Run:

```powershell
python -m pytest tests/test_project_mcp_servers.py -q
```

Expected:
- all tests pass
- record the final pass count for the sign-off packet if it changes from the current observed value

---

### Task 4: Revalidate the PnL Attribution Governance Chain

**Files:**
- Test: `tests/test_codex_page_readiness_gate.py`
- Test: `tests/test_pnl_attribution_business_owner_approval_status.py`
- Test: `tests/test_pnl_attribution_signoff_packet.py`
- Test: `tests/test_pnl_attribution_governance_record.py`
- Test: `tests/test_golden_samples_capture_ready.py`
- Check: `scripts/check_pnl_attribution_business_owner_approval.py`
- Check: `scripts/codex_page_readiness.py`
- Check: `scripts/codex-page-readiness.ps1`
- Check: `scripts/emit_pnl_attribution_governance_record.py`

**Step 1: Run the candidate governance chain**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py tests/test_golden_samples_capture_ready.py -q
```

Expected:
- all tests pass
- approval remains pending

**Step 2: Run scoped Ruff**

Run:

```powershell
python -m ruff check scripts/mcp/moss_project_mcp.py scripts/check_pnl_attribution_business_owner_approval.py scripts/codex_page_readiness.py scripts/emit_pnl_attribution_governance_record.py tests/test_project_mcp_servers.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py
```

Expected:
- `All checks passed!`

---

### Task 5: Reconfirm Strict Approval Gates

**Files:**
- Check: `scripts/check_pnl_attribution_business_owner_approval.py`
- Check: `scripts/codex-page-readiness.ps1`
- Read: `docs/pnl/pnl-attribution-business-owner-approval-template.md`

**Step 1: Run approval status without strict capture**

Run:

```powershell
python scripts\check_pnl_attribution_business_owner_approval.py
```

Expected:
- command reports pending approval state
- output includes the remaining blocker set
- no formal approval is implied

**Step 2: Run strict Python approval gate**

Run:

```powershell
python scripts\check_pnl_attribution_business_owner_approval.py --require-captured
```

Expected:
- non-zero exit
- output says approval capture is required but not complete
- blockers include `business_owner_approval`, `business_owner_signature`, and `candidate_boundary_acceptance`

**Step 3: Run strict single-page readiness gate**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured
```

Expected:
- non-zero exit
- output identifies `pnl-attribution` / `PAGE-PNL-ATTR-WB-001`
- output surfaces approval blockers

**Step 4: Run strict all-page readiness gate**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -All -RequireApprovalCaptured
```

Expected:
- non-zero exit
- output identifies `pnl-attribution` / `PAGE-PNL-ATTR-WB-001`
- output surfaces approval blockers

---

### Task 6: Sync Packet Evidence if Counts Changed

**Files:**
- Modify if needed: `docs/pnl/pnl-attribution-sign-off-packet.md`
- Modify if needed: `docs/pnl/pnl-attribution-governance-audit-packet.md`
- Test if docs change: `tests/test_pnl_attribution_signoff_packet.py`

**Step 1: Compare observed verification results to the packet**

If the full MCP suite pass count changed, update the sign-off packet line:

```text
Current MCP evidence suite: `<count> passed`
```

If the command list or approval gate wording changed, update the packet and test expectations together.

**Step 2: Keep the candidate boundary visible**

Confirm both packets still state:
- approval is pending
- business owner approval is not captured
- formal use is not allowed
- closure is not approved
- this does not replace `/api/pnl/overview`
- this does not merge with `/ui/pnl/attribution`

---

### Task 7: Final Verification and Report

**Files:**
- Review changed files only

**Step 1: Inspect the diff**

Run:

```powershell
git diff -- tests/test_project_mcp_servers.py docs/pnl/pnl-attribution-sign-off-packet.md docs/pnl/pnl-attribution-governance-audit-packet.md tests/test_pnl_attribution_signoff_packet.py
```

Expected:
- diff is limited to stale expected payload/doc evidence sync
- no production contract has been loosened
- candidate-only boundary remains intact

**Step 2: Final report**

Report:
- root cause: stale test expected payloads after stricter evidence-scope flags
- changed files
- validation commands and results
- expected strict-gate failures
- remaining risk: real business owner approval still not captured

Do not claim `pnl-attribution` is formally closed or approved.
