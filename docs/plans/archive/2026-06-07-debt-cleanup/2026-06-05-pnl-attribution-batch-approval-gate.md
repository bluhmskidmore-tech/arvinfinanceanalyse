# PnL Attribution Batch Approval Gate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the all-page readiness loophole where `-All -RequireApprovalCaptured` can pass even when `pnl-attribution` still lacks captured business owner approval.

**Architecture:** Keep the existing candidate boundary intact. The Python readiness report already carries `business_owner_approval_status`; the PowerShell all-page wrapper should enforce that field only when `-RequireApprovalCaptured` is explicitly passed. Default all-page readiness must remain a dry static-readiness report and must not treat pending approval as a static blocker.

**Tech Stack:** Python pytest, PowerShell readiness wrapper, existing MOSS readiness report JSON.

---

## Scope

Page/workflow: `pnl-attribution` readiness approval capture, specifically batch all-page readiness enforcement.

First files to inspect:
- `tests/test_codex_page_readiness_gate.py`
- `scripts/codex-page-readiness.ps1`
- `scripts/codex_page_readiness.py`

Do not touch:
- database schema
- auth or permission framework
- queue, scheduler, cache, or shared infrastructure
- unrelated backend or frontend pages
- metric definitions or formal PnL truth promotion

Preserve these invariants:
- `approval_status=candidate_or_pending`
- `formal_use_allowed=false`
- `closure_approved=false`
- `business_owner_approval_captured=false`
- default `-All` remains allowed while approval is pending
- strict `-All -RequireApprovalCaptured` fails while approval is pending

---

### Task 1: Add the Failing Batch Strict Approval Test

**Files:**
- Modify: `tests/test_codex_page_readiness_gate.py`

**Step 1: Add the regression test**

Add this test near the existing PowerShell readiness tests:

```python
def test_all_page_readiness_powershell_can_require_captured_approval() -> None:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "codex-page-readiness.ps1"),
            "-All",
            "-RequireApprovalCaptured",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    combined_output = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert "Approval capture is required but not complete." in combined_output
    assert "pnl-attribution" in combined_output
    assert "PAGE-PNL-ATTR-WB-001" in combined_output
    assert "- business_owner_approval" in combined_output
    assert "- candidate_boundary_acceptance" in combined_output
```

**Step 2: Run it and verify RED**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py::test_all_page_readiness_powershell_can_require_captured_approval -q
```

Expected:
- FAIL
- Failure reason shows return code is currently `0`, or the strict approval message is missing.

---

### Task 2: Enforce Strict Approval in Batch Mode

**Files:**
- Modify: `scripts/codex-page-readiness.ps1`

**Step 1: Add a batch helper**

Add a helper after `Assert-ApprovalCaptured`:

```powershell
function Assert-AllApprovalCaptured {
  param(
    [object]$Report
  )

  if (-not $RequireApprovalCaptured) {
    return
  }

  $pendingPages = @()
  foreach ($page in $Report.pages) {
    if (
      $null -ne $page.business_owner_approval_status -and
      -not $page.business_owner_approval_status.business_owner_approval_captured
    ) {
      $pendingPages += $page
    }
  }

  if ($pendingPages.Count -eq 0) {
    return
  }

  Write-Output "Approval capture is required but not complete."
  foreach ($page in $pendingPages) {
    Write-Output "- $($page.page_slug) ($($page.page_id))"
    if ($null -ne $page.business_owner_approval_status.remaining_blockers) {
      foreach ($blocker in $page.business_owner_approval_status.remaining_blockers) {
        Write-Output "  - $blocker"
      }
    }
  }

  throw "Business-owner approval capture is required."
}
```

**Step 2: Call it in the all-page path**

In the `if ($All)` branch, after `$report = $json | ConvertFrom-Json` and before any early dry-run `exit 0`, call:

```powershell
Assert-AllApprovalCaptured -Report $report
```

This keeps default `-All` unchanged and only tightens the explicit strict mode.

---

### Task 3: Verify GREEN for the New Behavior

**Files:**
- Test: `tests/test_codex_page_readiness_gate.py`
- Script: `scripts/codex-page-readiness.ps1`

**Step 1: Run the new test**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py::test_all_page_readiness_powershell_can_require_captured_approval -q
```

Expected:
- PASS

**Step 2: Confirm default batch mode still passes**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -All
```

Expected:
- exit code `0`
- output includes `Batch dry run complete. Pass -Run to execute page checks for supported pages.`

**Step 3: Confirm strict batch mode fails for the right reason**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -All -RequireApprovalCaptured
```

Expected:
- non-zero exit
- output includes `Approval capture is required but not complete.`
- output includes `pnl-attribution`
- output includes `PAGE-PNL-ATTR-WB-001`
- output includes `business_owner_approval`
- output includes `candidate_boundary_acceptance`

---

### Task 4: Run the Existing Governance Verification Set

**Files:**
- Test: `tests/test_codex_page_readiness_gate.py`
- Test: `tests/test_pnl_attribution_business_owner_approval_status.py`
- Test: `tests/test_pnl_attribution_signoff_packet.py`
- Test: `tests/test_pnl_attribution_governance_record.py`
- Test: `tests/test_golden_samples_capture_ready.py`
- Test: `tests/test_project_mcp_servers.py`
- Check: `scripts/codex-page-readiness.ps1`
- Check: `scripts/check_pnl_attribution_business_owner_approval.py`
- Check: `scripts/codex_page_readiness.py`
- Check: `scripts/emit_pnl_attribution_governance_record.py`
- Check: `scripts/mcp/moss_project_mcp.py`

**Step 1: Run the PnL attribution governance chain**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py tests/test_golden_samples_capture_ready.py -q
```

Expected:
- all tests pass

**Step 2: Run the MCP evidence suite**

Run:

```powershell
python -m pytest tests/test_project_mcp_servers.py -q
```

Expected:
- all tests pass

**Step 3: Run scoped lint**

Run:

```powershell
python -m ruff check scripts/mcp/moss_project_mcp.py scripts/check_pnl_attribution_business_owner_approval.py scripts/codex_page_readiness.py scripts/emit_pnl_attribution_governance_record.py tests/test_project_mcp_servers.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py
```

Expected:
- exit code `0`

**Step 4: Reconfirm single-page readiness semantics**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution
```

Expected:
- exit code `0`
- output surfaces approval blockers

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured
```

Expected:
- non-zero exit
- failure is caused by pending business owner approval capture

---

### Task 5: Update Docs Only If Output Contract Changes

**Files:**
- Maybe modify: `docs/pnl/pnl-attribution-sign-off-packet.md`
- Maybe modify: `docs/pnl/pnl-attribution-governance-audit-packet.md`

**Step 1: Compare output wording**

If the strict batch command introduces materially new wording that belongs in the sign-off or audit packet, update only the affected command/evidence section.

**Step 2: Keep candidate language**

Any doc update must continue to say:
- business owner approval is pending
- strict approval gate failure is expected while pending
- the page is a candidate workbench, not formal PnL truth

**Step 3: Re-run affected doc tests**

Run:

```powershell
python -m pytest tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py -q
```

Expected:
- all tests pass

---

## Completion Checklist

- New regression test failed before the implementation change.
- New regression test passes after the implementation change.
- Default `-All` remains non-strict and passes.
- Strict `-All -RequireApprovalCaptured` fails while approval remains pending.
- Single-page default and strict readiness behavior is unchanged.
- PnL attribution remains `candidate_or_pending`.
- No formal-use promotion is introduced.
- No unrelated files are changed.
- No commit is made unless the user explicitly asks for one.
