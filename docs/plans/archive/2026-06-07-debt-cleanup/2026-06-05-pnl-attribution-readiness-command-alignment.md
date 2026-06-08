# PnL Attribution Readiness Command Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align the PnL Attribution machine readiness report with the sign-off/audit packets by listing the readiness `-Run` closure command while keeping business-owner approval pending.

**Architecture:** Keep the change inside the page-readiness reporting path. Add a narrow required-command builder for run-supported pages, append the readiness `-Run` command only for `pnl-attribution`, and let the existing PowerShell renderer print the report unchanged.

**Tech Stack:** Python readiness report generator, pytest, PowerShell page-readiness wrapper, existing PnL Attribution governance tests.

---

## Non-Goals

- Do not mark `pnl-attribution` as formally approved.
- Do not change `approval_status=pending` / `candidate_or_pending`.
- Do not set `business_owner_approval_captured=true`.
- Do not set `formal_use_allowed=true` or `closure_approved=true`.
- Do not change database schema, auth, schedulers/cache, shared infra, or other page workflows.
- Do not promote PnL Attribution to formal PnL truth.
- Do not commit unless the user explicitly asks.

## Task 1: Lock the Missing Readiness Command With a Failing Test

**Files:**
- Modify: `tests/test_codex_page_readiness_gate.py`

**Step 1: Add the third required command assertion**

In `test_pnl_attribution_readiness_exposes_run_commands_without_formal_pnl_promotion`, add:

```python
    assert len(report["required_commands"]) == 3
    assert "codex-page-smoke.ps1 -PageSlug pnl-attribution" in report["required_commands"][0]
    assert "codex-verify-page.ps1 -PageSlug pnl-attribution -Run" in report["required_commands"][1]
    assert "codex-page-readiness.ps1 -PageSlug pnl-attribution -Run" in report["required_commands"][2]
```

Keep the existing approval and formal-use assertions intact.

**Step 2: Run the focused red test**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py::test_pnl_attribution_readiness_exposes_run_commands_without_formal_pnl_promotion -q
```

Expected before implementation: FAIL because `required_commands` currently has only two entries.

## Task 2: Add the Narrow Required-Command Builder

**Files:**
- Modify: `scripts/codex_page_readiness.py`

**Step 1: Add a small helper near the other page-specific command helpers**

Add:

```python
def _required_commands(page_slug: str) -> list[str]:
    if page_slug not in RUN_SUPPORTED_PAGE_SLUGS:
        return []

    commands = [
        f"powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug {page_slug}",
        f"powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug {page_slug} -Run",
    ]

    if page_slug == "pnl-attribution":
        commands.append(
            "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
            "-PageSlug pnl-attribution -Run"
        )

    return commands
```

**Step 2: Replace the inline `required_commands` expression**

Change:

```python
        "required_commands": [
            f"powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug {page_slug}",
            f"powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug {page_slug} -Run",
        ]
        if page_slug in RUN_SUPPORTED_PAGE_SLUGS
        else [],
```

to:

```python
        "required_commands": _required_commands(page_slug),
```

**Step 3: Run the focused green test**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py::test_pnl_attribution_readiness_exposes_run_commands_without_formal_pnl_promotion -q
```

Expected after implementation: PASS.

## Task 3: Verify the PowerShell Readiness Output Shows the Same Command

**Files:**
- Modify: `tests/test_codex_page_readiness_gate.py`

**Step 1: Extend the existing PowerShell output test**

In `test_pnl_attribution_page_readiness_powershell_surfaces_approval_blockers`, add:

```python
    assert (
        "powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 "
        "-PageSlug pnl-attribution -Run"
    ) in completed.stdout
```

This confirms `scripts/codex-page-readiness.ps1` prints the report command through the existing `Required closure commands` section.

**Step 2: Run the targeted PowerShell-backed tests**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py::test_pnl_attribution_page_readiness_powershell_surfaces_approval_blockers tests/test_codex_page_readiness_gate.py::test_pnl_attribution_page_readiness_powershell_can_require_captured_approval -q
```

Expected: PASS. The second test must still exit non-zero internally because captured approval is required but missing.

## Task 4: Run the PnL Governance Slice

**Files:**
- No edits expected unless a regression appears.

**Step 1: Run the full PnL governance slice**

Run:

```powershell
python -m pytest tests/test_codex_page_readiness_gate.py tests/test_pnl_attribution_business_owner_approval_status.py tests/test_pnl_attribution_signoff_packet.py tests/test_pnl_attribution_governance_record.py tests/test_golden_samples_capture_ready.py -q
```

Expected: all tests pass. The previous observed baseline was `68 passed`; if the new assertions are added, the pass count may remain 68 or increase only if new tests are added instead of extending existing tests.

**Step 2: Run scoped formatting/lint**

Run:

```powershell
python -m ruff check scripts/codex_page_readiness.py tests/test_codex_page_readiness_gate.py
```

Expected: `All checks passed!`

## Task 5: Reconfirm Strict Approval Gates Still Fail

**Files:**
- No edits.

**Step 1: Business-owner approval gate**

Run:

```powershell
python scripts/check_pnl_attribution_business_owner_approval.py --require-captured
```

Expected: exit code 1. Output must still show approval pending and blockers including `business_owner_approval`, `verification_commands_rerun`, and `candidate_boundary_acceptance`.

**Step 2: Page-readiness approval gate**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured
```

Expected: exit code 1. Output must still show approval capture is required but not complete.

## Completion Criteria

- `pnl-attribution` readiness report lists three required closure commands:
  - page smoke
  - page verify `-Run`
  - page readiness `-Run`
- PowerShell readiness output surfaces the same third command.
- Sign-off/audit packet wording remains candidate-only and pending approval.
- `formal_use_allowed=false`, `closure_approved=false`, and captured approval remains false.
- Strict approval gates still fail intentionally until a real business-owner signature is captured.
