# PnL Attribution Evidence Packet Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Sync the `pnl-attribution` candidate sign-off and governance audit packets with the verification commands that were rerun, while preserving pending business-owner approval gates.

**Architecture:** Treat smoke, verify, and page-readiness `-Run` outputs as current evidence for reviewer confirmation only. Update packet prose and packet tests so generated/static packets say verification was rerun, but still require business-owner review/signature before approval capture, closure, formal use, or formal PnL truth promotion.

**Tech Stack:** Markdown governance packets, Python pytest, Ruff, PowerShell readiness wrappers.

---

## Scope

Workflow being fixed:
- `pnl-attribution` candidate governance/sign-off evidence packet wording after verification reruns.

Files to inspect first:
- `docs/pnl/pnl-attribution-sign-off-packet.md`
- `docs/pnl/pnl-attribution-governance-audit-packet.md`
- `tests/test_pnl_attribution_signoff_packet.py`
- `tests/test_pnl_attribution_governance_record.py`
- `scripts/emit_pnl_attribution_governance_record.py`

Do not touch:
- database schema
- auth or permission framework
- queue, scheduler, cache, or shared infrastructure
- unrelated backend services or frontend pages
- approval template values that would capture real approval
- formal PnL truth surfaces or production approval state

Preserve these invariants:
- `approval_status=pending` or `candidate_or_pending`
- `business_owner_approval_captured=false`
- `formal_use_allowed=false`
- `closure_approved=false`
- strict approval gates fail while approval is pending
- `verification_commands_rerun` remains an approval action item until the owner completes/signs the template
- no doc or output implies formal approval, formal PnL truth, governance writes, page execution proof beyond the commands actually run, or business-owner approval capture

No commits in this plan unless the user explicitly asks.

---

### Task 1: Update Sign-Off Packet Evidence Language

**Files:**
- Modify: `docs/pnl/pnl-attribution-sign-off-packet.md`
- Test: `tests/test_pnl_attribution_signoff_packet.py`

**Step 1: Move rerun commands into freshly verified evidence**

Under `Commands freshly verified for this candidate sign-off packet:`, ensure the block includes:

```text
scripts\codex-page-smoke.ps1 -PageSlug pnl-attribution
scripts\codex-verify-page.ps1 -PageSlug pnl-attribution -Run
scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution -Run
```

Expected:
- These commands are no longer described as unexecuted follow-up commands in the sign-off packet.

**Step 2: Ensure the old required-command section is absent**

Confirm this stale section is absent:

```markdown
Commands still required before business-owner approval can be captured:
```

Confirm the packet uses:

```markdown
Business-owner review still required before approval can be captured:
```

List only reviewer/business actions:

```text
Review current API payload and visible UI state.
Confirm live smoke/browser evidence.
Complete/sign docs\pnl\pnl-attribution-business-owner-approval-template.md.
```

Expected:
- The packet clearly separates machine verification already rerun from human approval still missing.

**Step 3: Update observed evidence lines**

Replace the stale observed evidence section with:

```markdown
- Current pnl-attribution governance chain: `71 passed`
- Current MCP evidence suite: `151 passed`
- Current pnl-attribution page verification: `94 backend passed; 27 frontend passed; 1 browser a11y smoke passed; typecheck passed; debt audit passed`
- Current pnl-attribution readiness run: `Page readiness gate passed`
- Strict approval gate: `expected failure while business_owner_approval_captured=false`
- Page closure command status: `verification rerun complete; business-owner review and signature still pending`
```

Expected:
- Evidence is concrete and current.
- The closure line cannot be mistaken for approval.

**Step 4: Update sign-off packet tests**

In `tests/test_pnl_attribution_signoff_packet.py`, update assertions so they require:
- `Business-owner review still required before approval can be captured:`
- all three rerun PowerShell commands in the freshly verified block
- `Current MCP evidence suite: `151 passed``
- the page verification summary
- the readiness pass line
- the new closure command status

Also keep assertions that stale counts/statuses do not appear:
- `134 passed`
- `136 passed`
- `60 passed`
- `61 passed`
- `62 passed`
- `63 passed`
- `65 passed`
- `137 passed`
- `138 passed`
- `139 passed`
- `140 passed`
- `listed for follow-up; not executed by this packet`
- `70 passed`
- `68 passed`
- `67 passed`
- `150 passed`
- `147 passed`
- `146 passed`

Expected:
- Tests prove the sign-off packet is synchronized and still pending-only.

---

### Task 2: Update Governance Audit Packet Follow-Up Language

**Files:**
- Modify: `docs/pnl/pnl-attribution-governance-audit-packet.md`
- Modify: `scripts/emit_pnl_attribution_governance_record.py`
- Test: `tests/test_pnl_attribution_signoff_packet.py`
- Test: `tests/test_pnl_attribution_governance_record.py`

**Step 1: Update static audit packet follow-up**

In `docs/pnl/pnl-attribution-governance-audit-packet.md`, change `## Required Follow-up` to:

```markdown
- Review current API payload and visible UI state.
- Confirm live smoke/browser evidence before signing.
- Page smoke rerun: `scripts\codex-page-smoke.ps1 -PageSlug pnl-attribution` (`passed`)
- Page verification rerun: `scripts\codex-verify-page.ps1 -PageSlug pnl-attribution -Run` (`passed`)
- Page readiness rerun: `scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution -Run` (`passed`)
- Page closure command status: `verification rerun complete; business-owner review and signature still pending`
- Collect business-owner approval before any closure claim.
```

Expected:
- The audit packet reflects current verification evidence without claiming owner approval.

**Step 2: Update generated audit packet renderer**

In `scripts/emit_pnl_attribution_governance_record.py`, update `render_audit_packet_markdown()` so generated packets use the same `## Required Follow-up` wording as the static audit packet.

Expected:
- Static packet and generated packet tests cannot drift.

**Step 3: Update audit packet tests**

In `tests/test_pnl_attribution_signoff_packet.py`, add or update audit packet assertions for:
- `Confirm live smoke/browser evidence before signing.`
- `Page smoke rerun: ... (`passed`)`
- `Page verification rerun: ... (`passed`)`
- `Page readiness rerun: ... (`passed`)`
- new closure command status

In `tests/test_pnl_attribution_governance_record.py`, update generated packet assertions to match those same lines.

Expected:
- Both static and generated audit packets describe rerun evidence consistently.

---

### Task 3: Run Focused Packet Tests

**Files:**
- Test: `tests/test_pnl_attribution_signoff_packet.py`
- Test: `tests/test_pnl_attribution_governance_record.py`

**Step 1: Run packet-focused tests**

Run:

```powershell
python -m pytest tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py::test_pnl_attribution_governance_record_can_write_audit_packet -q
```

Expected:
- PASS
- packet docs and generated packet renderer agree

**Step 2: If tests fail, fix only packet wording or exact expected strings**

Expected:
- No unrelated logic changes.

---

### Task 4: Run Governance Regression Slice

**Files:**
- Test: `tests/test_codex_page_readiness_gate.py`
- Test: `tests/test_pnl_attribution_business_owner_approval_status.py`
- Test: `tests/test_pnl_attribution_signoff_packet.py`
- Test: `tests/test_pnl_attribution_governance_record.py`
- Test: `tests/test_golden_samples_capture_ready.py`

**Step 1: Run full PnL governance slice**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py tests/test_golden_samples_capture_ready.py -q
```

Expected:
- `71 passed`
- approval remains pending

---

### Task 5: Run Lint and MCP Regression Checks

**Files:**
- Check: `scripts/mcp/moss_project_mcp.py`
- Check: `scripts/check_pnl_attribution_business_owner_approval.py`
- Check: `scripts/codex_page_readiness.py`
- Check: `scripts/emit_pnl_attribution_governance_record.py`
- Check: `tests/test_project_mcp_servers.py`
- Check: packet tests touched above

**Step 1: Run scoped Ruff**

Run:

```powershell
python -m ruff check scripts/mcp/moss_project_mcp.py scripts/check_pnl_attribution_business_owner_approval.py scripts/codex_page_readiness.py scripts/emit_pnl_attribution_governance_record.py tests/test_project_mcp_servers.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py
```

Expected:
- `All checks passed!`

**Step 2: Run MCP evidence suite**

Run:

```powershell
python -m pytest tests/test_project_mcp_servers.py -q
```

Expected:
- `151 passed`

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
- Exit code `1`
- Output includes `approval_status=pending`
- Output includes `business_owner_approval_captured=false`
- Output includes `verification_commands_rerun`
- Output includes `approval_action_item_count=11`

**Step 2: Run strict page readiness approval gate**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured
```

Expected:
- Exit code `1`
- Output includes pending approval blockers
- Output includes `verification_commands_rerun`
- No output claims approval captured

---

## Final Report Requirements

Report:
- Root cause: evidence packets still described already-rerun page commands as future follow-up.
- Changed files.
- Validation commands and results.
- Remaining risk: external business-owner review/signature is still missing, so approval and formal use must remain blocked.

Do not report:
- page closure approved
- formal use allowed
- formal PnL truth promoted
- business-owner approval captured
