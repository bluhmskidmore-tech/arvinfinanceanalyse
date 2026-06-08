# Hermes Five Agent Team Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reliable local launcher that opens five Hermes agents for MOSS work: Leader, Product Manager, Developer, Code Reviewer, and QA.

**Architecture:** `scripts/start-hermes-agent-team.ps1` prepares a team workspace under `.omx/hermes-teams/<team-id>/`, writes role prompts as files, and opens Windows Terminal panes or windows. A shared generated runner, `launch/run-role.ps1`, owns Hermes runtime behavior so role launchers stay tiny wrappers. WSL Hermes is the primary backend because local evidence shows it can call the model, while Windows Hermes currently fails authentication.

**Tech Stack:** PowerShell, Windows Terminal, WSL distro `HermesUbuntu`, Hermes CLI, Python `pytest`.

---

## Current Evidence

- Windows Hermes model calls are not usable yet: `hermes chat -q ... -Q --max-turns 1` fails with `401 Missing Authentication header`.
- WSL Hermes works in `HermesUbuntu`: `hermes chat -q 'Smoke test only. Reply exactly: HERMES_OK' -Q --max-turns 1` has returned `HERMES_OK`.
- Hermes CLI supports `hermes chat -q`, `hermes chat --resume <session_id>`, and `hermes chat --continue [session_name]`.
- `hermes chat -z` is invalid; one-shot mode is global `hermes -z`.
- Passing long multiline role prompts through PowerShell to WSL to Bash to Hermes is fragile. The stable path is: write prompt files, then pass Hermes a short seed prompt that tells it which file to read.
- Current local scope is the Hermes team launcher workflow only. Do not touch MOSS business code, frontend pages, backend routes, database schema, auth, schedulers, or shared infrastructure.
- Do not commit unless the user explicitly asks.

## Success Criteria

1. `-PrepareOnly` creates a complete team workspace:
   - `TEAM_BOARD.md`
   - `manifest.json`
   - `prompts/*.md`
   - `inbox/*.md`
   - `outbox/*.md`
   - `sessions/*.txt` only after seeding
   - `launch/run-role.ps1`
   - `launch/<role>.ps1`
2. All generated PowerShell files parse successfully.
3. WSL backend prompt paths use `/mnt/<drive>/...`.
4. `-SeedSessions -Roles lead` initializes one role and writes `sessions/lead.txt`.
5. `-SeedSessions` initializes all five roles and writes five session id files.
6. `-Launch -Layout Panes` opens a Windows Terminal tab with five panes.
7. `-Launch -Layout Windows` opens five separate Windows Terminal tabs or windows.
8. Existing Windows backend generation remains possible with `-Backend Windows`, but it is not the default success path until Windows Hermes auth is fixed.

## Non-Goals

- Do not build a web UI dashboard for agent coordination in this pass.
- Do not replace Hermes with Codex native subagents.
- Do not repair Windows Hermes authentication as part of this launcher. Record it as a separate environment issue.
- Do not start five live model sessions during unit tests.
- Do not add dependencies.

---

### Task 1: Add No-Model Regression Tests For The Launcher Contract

**Files:**
- Modify: `tests/test_hermes_agent_team_launcher.py`

**Step 1: Add tests for WSL backend artifacts**

Extend the existing prepare-only test so it verifies:

```python
assert (team_dir / "manifest.json").exists()
assert (team_dir / "launch" / "run-role.ps1").exists()
assert "/mnt/" in (team_dir / "prompts" / "lead.md").read_text(encoding="utf-8")
assert "Read and follow the Hermes role prompt at" in (
    team_dir / "launch" / "run-role.ps1"
).read_text(encoding="utf-8")
```

**Step 2: Add tests for resume semantics**

Add a test that reads the generated runner and verifies that session ids are resumed by id:

```python
def test_generated_runner_resumes_session_id(tmp_path):
    output_root = tmp_path / "hermes-teams"
    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "resume-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    runner_text = (output_root / "resume-team" / "launch" / "run-role.ps1").read_text(
        encoding="utf-8"
    )
    assert "hermes chat --resume $sessionId" in runner_text
    assert "hermes chat --continue" not in runner_text
```

**Step 3: Add tests for one-role smoke selection**

Add the test first, before implementation:

```python
def test_roles_argument_limits_seed_and_launch_targets(tmp_path):
    output_root = tmp_path / "hermes-teams"
    completed = run_launcher(
        "-PrepareOnly",
        "-TeamId",
        "lead-only-team",
        "-Task",
        "Build the MOSS agent system",
        "-OutputRoot",
        str(output_root),
        "-Backend",
        "Wsl",
        "-Roles",
        "lead",
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    manifest = (output_root / "lead-only-team" / "manifest.json").read_text(
        encoding="utf-8"
    )
    assert '"selected_roles":' in manifest
    assert '"lead"' in manifest
```

**Step 4: Run tests and verify the new role-selection test fails**

Run:

```powershell
pytest tests/test_hermes_agent_team_launcher.py
```

Expected:

- Existing tests still pass if run alone.
- New `-Roles` test fails because the script does not yet support the parameter.

---

### Task 2: Make Runtime Commands Injectable For Safe Tests

**Files:**
- Modify: `scripts/start-hermes-agent-team.ps1`
- Modify: `tests/test_hermes_agent_team_launcher.py`

**Step 1: Add script parameters**

Add these parameters to the main `param(...)` block:

```powershell
[string]$HermesCommand = "hermes",
[string]$WslCommand = "wsl.exe",
[string[]]$Roles = @("all")
```

**Step 2: Replace direct command literals**

Replace direct calls:

```powershell
& "wsl.exe" ...
& "hermes" ...
```

with:

```powershell
& $WslCommand ...
& $HermesCommand ...
```

In generated `run-role.ps1`, add matching parameters:

```powershell
[string]$HermesCommand = "hermes",
[string]$WslCommand = "wsl.exe",
```

and use them in the runner.

**Step 3: Pass command paths from wrappers to runner**

When generating each `launch/<role>.ps1`, include:

```powershell
-HermesCommand '<value>' `
-WslCommand '<value>' `
```

Use `Quote-PowerShellLiteral` for both values.

**Step 4: Add parser verification**

Run:

```powershell
$tokens=$null; $errs=$null
$null=[System.Management.Automation.Language.Parser]::ParseFile('scripts/start-hermes-agent-team.ps1',[ref]$tokens,[ref]$errs)
if($errs.Count){ $errs | ForEach-Object { $_.Message }; exit 1 }
```

Expected: no parser errors.

**Step 5: Run tests**

Run:

```powershell
pytest tests/test_hermes_agent_team_launcher.py
```

Expected: tests still fail only for behavior not implemented yet, not parser/runtime command wiring.

---

### Task 3: Fix WSL Seed Session Handling

**Files:**
- Modify: `scripts/start-hermes-agent-team.ps1`
- Modify: `tests/test_hermes_agent_team_launcher.py`

**Root Cause:** In the non-interactive `Invoke-RoleSeed` path, WSL seeding can call WSL Hermes for the model request but then use Windows Hermes for `sessions rename`. That reintroduces the Windows authentication problem and can fail even when WSL Hermes is healthy.

**Step 1: Update WSL rename path**

In `Invoke-RoleSeed`, keep the WSL branch entirely inside WSL:

```powershell
if ($Backend -eq "Wsl") {
  & $WslCommand "-d" $WslDistro "-e" "bash" "-lc" "hermes sessions rename $sessionId $(Quote-BashLiteral $SessionTitle)" | Out-Null
} else {
  & $HermesCommand @("sessions", "rename", $sessionId, $SessionTitle) | Out-Null
}
```

**Step 2: Keep session id files as the source of truth**

After successful seed, write:

```powershell
Write-Utf8File -Path (Join-Path $sessionDir "$($role.Slug).txt") -Value $sessionId
```

Do not rely on session title lookup for runtime resume.

**Step 3: Add a no-model static regression**

Add a test that checks the main script contains a WSL rename branch:

```python
def test_wsl_seed_rename_stays_inside_wsl():
    script = (ROOT / "scripts" / "start-hermes-agent-team.ps1").read_text(
        encoding="utf-8"
    )
    assert "hermes sessions rename $sessionId" in script
    assert "$WslCommand" in script
    assert "$HermesCommand" in script
```

**Step 4: Run targeted tests**

Run:

```powershell
pytest tests/test_hermes_agent_team_launcher.py
```

Expected: tests pass after the implementation.

---

### Task 4: Add Role Selection For Cheap Smoke Tests

**Files:**
- Modify: `scripts/start-hermes-agent-team.ps1`
- Modify: `tests/test_hermes_agent_team_launcher.py`

**Step 1: Normalize selected roles**

Add a helper after `$roles` is built:

```powershell
function Select-Roles {
  param(
    [object[]]$AllRoles,
    [string[]]$RequestedRoles
  )

  if (-not $RequestedRoles -or $RequestedRoles.Count -eq 0 -or $RequestedRoles -contains "all") {
    return $AllRoles
  }

  $requested = @{}
  foreach ($item in $RequestedRoles) {
    foreach ($part in ($item -split ",")) {
      $slug = $part.Trim()
      if (-not [string]::IsNullOrWhiteSpace($slug)) {
        $requested[$slug] = $true
      }
    }
  }

  $selected = $AllRoles | Where-Object { $requested.ContainsKey($_.Slug) }
  if (-not $selected -or $selected.Count -eq 0) {
    throw "No known Hermes roles selected. Valid roles: all, lead, product-manager, developer, code-reviewer, qa"
  }
  return @($selected)
}
```

**Step 2: Use selected roles only for seeding and launch**

Keep generating all prompts and inbox/outbox files. Use selected roles for:

- `-SeedSessions`
- `-Launch`
- `manifest.selected_roles`

This preserves a complete team workspace while allowing cheap one-role checks.

**Step 3: Update launch layout behavior**

When `-Layout Panes` is used with one selected role, open only that role in one tab.

When `-Layout Panes` is used with multiple selected roles:

- first selected role starts the tab
- remaining selected roles use `split-pane`

**Step 4: Run tests**

Run:

```powershell
pytest tests/test_hermes_agent_team_launcher.py
```

Expected: all launcher tests pass.

---

### Task 5: Verify Generated Artifacts Without Model Calls

**Files:**
- No code edits expected.

**Step 1: Parse the main script**

Run:

```powershell
$tokens=$null; $errs=$null
$null=[System.Management.Automation.Language.Parser]::ParseFile('scripts/start-hermes-agent-team.ps1',[ref]$tokens,[ref]$errs)
if($errs.Count){ $errs | ForEach-Object { $_.Message }; exit 1 }
```

Expected: no output and exit code 0.

**Step 2: Generate a dry-run workspace**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -PrepareOnly `
  -TeamId moss-wsl-smoke `
  -Task "Build the MOSS five-agent Hermes team launcher" `
  -Backend Wsl `
  -WslDistro HermesUbuntu
```

Expected:

- `.omx/hermes-teams/moss-wsl-smoke/TEAM_BOARD.md` exists.
- `.omx/hermes-teams/moss-wsl-smoke/manifest.json` exists.
- `.omx/hermes-teams/moss-wsl-smoke/launch/run-role.ps1` exists.

**Step 3: Parse generated scripts**

Run:

```powershell
$files = Get-ChildItem .omx\hermes-teams\moss-wsl-smoke\launch\*.ps1
foreach($file in $files){
  $tokens=$null; $errs=$null
  $null=[System.Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errs)
  if($errs.Count){ throw "$($file.FullName): $($errs[0].Message)" }
}
```

Expected: no parser errors.

---

### Task 6: Verify WSL Hermes Health With One Cheap Model Call

**Files:**
- No code edits expected.

**Step 1: Confirm WSL Hermes is available**

Run:

```powershell
wsl.exe -d HermesUbuntu -e sh -lc "command -v hermes && hermes status | head -80"
```

Expected:

- `hermes` path is printed.
- status output does not report missing installation.

**Step 2: Run the known smoke query**

Run:

```powershell
wsl.exe -d HermesUbuntu -e sh -lc "cd /mnt/f/MOSS-V3 && hermes chat -q 'Smoke test only. Reply exactly: HERMES_OK' -Q --max-turns 1"
```

Expected:

- Output contains `HERMES_OK`.
- Output includes a `session_id`.

If this fails, stop launcher execution and diagnose WSL Hermes credentials/config. Do not switch back to Windows Hermes as a workaround unless Windows auth is repaired first.

---

### Task 7: Seed One Role End-To-End

**Files:**
- Runtime artifacts only under `.omx/hermes-teams/<team-id>/`.

**Step 1: Seed only Leader**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -PrepareOnly `
  -SeedSessions `
  -Roles lead `
  -TeamId moss-lead-seed `
  -Task "Build the MOSS five-agent Hermes team launcher" `
  -Backend Wsl `
  -WslDistro HermesUbuntu
```

Expected:

- Output contains `Hermes agent team prepared`.
- `.omx/hermes-teams/moss-lead-seed/sessions/lead.txt` exists.
- The file contains a non-empty Hermes session id.

**Step 2: Inspect generated Leader prompt**

Run:

```powershell
Get-Content .omx\hermes-teams\moss-lead-seed\prompts\lead.md -TotalCount 80
```

Expected:

- It names the Leader role.
- It points to `TEAM_BOARD.md`.
- It includes WSL-readable backend paths.

---

### Task 8: Seed All Five Roles

**Files:**
- Runtime artifacts only under `.omx/hermes-teams/<team-id>/`.

**Step 1: Seed the full team**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -PrepareOnly `
  -SeedSessions `
  -TeamId moss-five-seed `
  -Task "Build the MOSS five-agent Hermes team launcher" `
  -Backend Wsl `
  -WslDistro HermesUbuntu
```

Expected:

- These files exist and contain non-empty session ids:
  - `.omx/hermes-teams/moss-five-seed/sessions/lead.txt`
  - `.omx/hermes-teams/moss-five-seed/sessions/product-manager.txt`
  - `.omx/hermes-teams/moss-five-seed/sessions/developer.txt`
  - `.omx/hermes-teams/moss-five-seed/sessions/code-reviewer.txt`
  - `.omx/hermes-teams/moss-five-seed/sessions/qa.txt`

**Step 2: Check session count**

Run:

```powershell
Get-ChildItem .omx\hermes-teams\moss-five-seed\sessions\*.txt | Measure-Object
```

Expected: count is `5`.

---

### Task 9: Launch The Screenshot-Style Five-Agent Team

**Files:**
- Runtime artifacts only under `.omx/hermes-teams/<team-id>/`.

**Step 1: Launch in one Windows Terminal tab with five panes**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -Launch `
  -Layout Panes `
  -TeamId moss-five-live `
  -Task "Build the MOSS five-agent Hermes team launcher" `
  -Backend Wsl `
  -WslDistro HermesUbuntu
```

Expected:

- Windows Terminal opens.
- The roles are visible as separate panes:
  - Hermes Leader
  - Hermes Product Manager
  - Hermes Developer
  - Hermes Code Reviewer
  - Hermes QA
- First launch initializes missing sessions, then resumes by session id.

**Step 2: Alternative layout**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -Launch `
  -Layout Windows `
  -TeamId moss-five-live-windows `
  -Task "Build the MOSS five-agent Hermes team launcher" `
  -Backend Wsl `
  -WslDistro HermesUbuntu
```

Expected:

- Five separate Windows Terminal tabs/windows open.
- Each role has its own Hermes session.

---

### Task 10: Operator Runbook

**Files:**
- Create or update only if desired after implementation: `docs/handoff/2026-06-07-hermes-five-agent-team-runbook.md`

**Recommended commands for daily use:**

Prepare without model calls:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -PrepareOnly `
  -TeamId moss-team `
  -Task "Close the selected MOSS workflow with evidence" `
  -Backend Wsl
```

Seed one role:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -PrepareOnly `
  -SeedSessions `
  -Roles lead `
  -TeamId moss-team `
  -Task "Close the selected MOSS workflow with evidence" `
  -Backend Wsl
```

Launch all five agents:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -Launch `
  -Layout Panes `
  -TeamId moss-team `
  -Task "Close the selected MOSS workflow with evidence" `
  -Backend Wsl
```

Launch only QA and reviewer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -Launch `
  -Roles code-reviewer,qa `
  -TeamId moss-review `
  -Task "Review and verify the selected MOSS workflow" `
  -Backend Wsl
```

---

## Final Verification Checklist

Run in this order:

```powershell
pytest tests/test_hermes_agent_team_launcher.py
```

```powershell
$tokens=$null; $errs=$null
$null=[System.Management.Automation.Language.Parser]::ParseFile('scripts/start-hermes-agent-team.ps1',[ref]$tokens,[ref]$errs)
if($errs.Count){ $errs | ForEach-Object { $_.Message }; exit 1 }
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -PrepareOnly `
  -TeamId moss-final-dry-run `
  -Task "Build the MOSS five-agent Hermes team launcher" `
  -Backend Wsl
```

```powershell
wsl.exe -d HermesUbuntu -e sh -lc "cd /mnt/f/MOSS-V3 && hermes chat -q 'Smoke test only. Reply exactly: HERMES_OK' -Q --max-turns 1"
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-hermes-agent-team.ps1 `
  -PrepareOnly `
  -SeedSessions `
  -Roles lead `
  -TeamId moss-final-lead-seed `
  -Task "Build the MOSS five-agent Hermes team launcher" `
  -Backend Wsl
```

Only after these pass, run the five-pane launch command.

## Residual Risks

- Five live agents consume five Hermes model sessions during initialization.
- Windows Terminal `wt.exe` must be installed for `-Launch`.
- Windows Hermes remains a separate auth problem until `hermes status`, `hermes login`, or provider config is repaired on Windows.
- The launcher coordinates agents by files. It does not enforce locks, so role prompts must continue to tell agents not to overwrite each other's files.
- If Hermes CLI changes its session output format, session id extraction may need a parser update.
