from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _extract_powershell_function(script: str, name: str) -> str:
    start = script.index(f"function {name} ")
    brace_start = script.index("{", start)
    depth = 0
    for index in range(brace_start, len(script)):
        char = script[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return script[start : index + 1]
    raise AssertionError(f"Could not extract PowerShell function {name}")


def _powershell_quote(value: Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_harness(tmp_path: Path, name: str, source: str) -> subprocess.CompletedProcess[str]:
    harness_path = tmp_path / f"{name}.ps1"
    harness_path.write_text(source, encoding="utf-8")
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness_path),
        ],
        cwd=ROOT,
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )


def _assert_harness_ok(completed: subprocess.CompletedProcess[str]) -> None:
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_native_worker_matchers_accept_default_and_cli_modes(tmp_path: Path) -> None:
    minimum_matcher_uses = {
        "dev-up.ps1": 2,
        "dev-down.ps1": 2,
        "dev-keepalive.ps1": 2,
    }
    for script_name, minimum_uses in minimum_matcher_uses.items():
        script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")
        matcher = _extract_powershell_function(script, "Test-NativeWorkerProcess")
        completed = _run_harness(
            tmp_path,
            f"{script_name}-worker-matcher",
            matcher
            + r'''
$defaultRunner = [pscustomobject]@{
  Name = "python.exe"
  CommandLine = "python -m backend.app.tasks.dev_worker_runner --threads 4"
}
$cliRunner = [pscustomobject]@{
  Name = "python.exe"
  CommandLine = "python -m dramatiq backend.app.tasks.worker_bootstrap"
}
$api = [pscustomobject]@{
  Name = "python.exe"
  CommandLine = "python -m uvicorn backend.app.main:app"
}
$wrapper = [pscustomobject]@{
  Name = "powershell.exe"
  CommandLine = "powershell -File scripts\dev-worker.ps1"
}

if (-not (Test-NativeWorkerProcess -Process $defaultRunner)) { throw "default runner was not recognized" }
if (-not (Test-NativeWorkerProcess -Process $cliRunner)) { throw "CLI runner was not recognized" }
if (Test-NativeWorkerProcess -Process $api) { throw "API was misclassified as a worker" }
if (Test-NativeWorkerProcess -Process $wrapper) { throw "PowerShell wrapper was misclassified as a native worker" }
''',
        )
        _assert_harness_ok(completed)
        assert script.count("Test-NativeWorkerProcess -Process $_") >= minimum_uses


def test_dev_up_reuses_default_worker_when_wrapper_is_missing(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-up.ps1").read_text(encoding="utf-8")
    fake_root = tmp_path / "repo"
    (fake_root / "scripts").mkdir(parents=True)
    (fake_root / "scripts" / "dev-worker.ps1").write_text("# test worker\n", encoding="utf-8")
    fake_logs = fake_root / "logs"
    fake_logs.mkdir()

    harness = f'''
$root = {_powershell_quote(fake_root)}
$logRoot = {_powershell_quote(fake_logs)}
$powershellExe = "powershell.exe"
$script:ProcessInspectionAvailable = $true

function Get-NativeScriptProcess {{ param([string]$ScriptName) return $null }}
function Get-NativeWorkerProcess {{
  return [pscustomobject]@{{
    ProcessId = 4242
    Name = "python.exe"
    CommandLine = "python -m backend.app.tasks.dev_worker_runner --threads 4"
  }}
}}
function Quote-CmdArgument {{ param([string]$Value) return ('"' + $Value + '"') }}
function Get-RecentLogLines {{ param([string]$Path) return @() }}
function New-Object {{ param([string]$ComObject) throw "duplicate worker launch attempted" }}

{_extract_powershell_function(script, "Start-DevScriptDetached")}

$launch = Start-DevScriptDetached -ScriptName "dev-worker.ps1"
if ($launch.Started) {{ throw "existing default worker was reported as newly started" }}
if ($launch.ProcessId -ne 4242) {{ throw "existing default worker PID was not reused" }}
'''
    _assert_harness_ok(_run_harness(tmp_path, "dev-up-reuses-default-worker", harness))


def test_dev_up_refuses_worker_launch_when_process_inspection_is_unavailable(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-up.ps1").read_text(encoding="utf-8")
    fake_root = tmp_path / "repo"
    (fake_root / "scripts").mkdir(parents=True)
    (fake_root / "scripts" / "dev-worker.ps1").write_text("# test worker\n", encoding="utf-8")
    fake_logs = fake_root / "logs"
    fake_logs.mkdir()

    harness = f'''
$root = {_powershell_quote(fake_root)}
$logRoot = {_powershell_quote(fake_logs)}
$powershellExe = "powershell.exe"
$script:ProcessInspectionAvailable = $true
$script:LauncherCalled = $false

function Get-NativeScriptProcess {{
  param([string]$ScriptName)
  $script:ProcessInspectionAvailable = $false
  return $null
}}
function Get-NativeWorkerProcess {{ throw "native worker lookup should be skipped after inspection failure" }}
function Quote-CmdArgument {{ param([string]$Value) return ('"' + $Value + '"') }}
function Get-RecentLogLines {{ param([string]$Path) return @() }}
function New-Object {{
  param([string]$ComObject)
  $script:LauncherCalled = $true
  throw "worker launcher was called"
}}

{_extract_powershell_function(script, "Start-DevScriptDetached")}

try {{
  Start-DevScriptDetached -ScriptName "dev-worker.ps1" | Out-Null
  throw "expected worker launch to fail closed"
}} catch {{
  if ($script:LauncherCalled) {{ throw "worker launch was attempted without reliable process inspection" }}
  if ($_.Exception.Message -notlike "*process inspection unavailable*") {{
    throw "missing fail-closed diagnostic: $($_.Exception.Message)"
  }}
}}
'''
    _assert_harness_ok(_run_harness(tmp_path, "dev-up-worker-inspection-fail-closed", harness))


def test_dev_keepalive_does_not_restart_running_default_worker_without_wrapper(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = (
        r'''
$script:ProcessInspectionAvailable = $true
$script:RestartAttempted = $false

function Get-NativeScriptProcess { param([string]$ScriptName) return $null }
function Get-NativeWorkerProcess {
  return [pscustomobject]@{
    ProcessId = 4242
    Name = "python.exe"
    CommandLine = "python -m backend.app.tasks.dev_worker_runner --threads 4"
  }
}
function Write-KeepaliveLog { param([string]$Message) }
function Test-RestartCooldown { param([string]$Key) return $false }
function Set-RestartTimestamp { param([string]$Key) }
function Stop-KnownServiceProcesses { param([string]$ServiceName) $script:RestartAttempted = $true }
function Start-DevScriptDetached { param([string]$ScriptName) $script:RestartAttempted = $true }
'''
        + _extract_powershell_function(script, "Ensure-WorkerRunning")
        + r'''
Ensure-WorkerRunning
if ($script:RestartAttempted) { throw "keepalive attempted to restart a running default worker" }
'''
    )
    _assert_harness_ok(_run_harness(tmp_path, "dev-keepalive-reuses-default-worker", harness))


def test_dev_down_stops_default_worker_runner(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-down.ps1").read_text(encoding="utf-8")
    harness = (
        f'''
$root = {_powershell_quote(ROOT)}
$script:CimCall = 0
$script:StoppedProcessIds = @()

function Get-CimInstance {{
  $script:CimCall += 1
  if ($script:CimCall -eq 1) {{
    return [pscustomobject]@{{
      ProcessId = 4242
      ParentProcessId = 7
      Name = "python.exe"
      CommandLine = "python -m backend.app.tasks.dev_worker_runner --threads 4"
    }}
  }}
  return @()
}}
function Stop-Process {{
  param([int]$Id, [switch]$Force, [object]$ErrorAction)
  $script:StoppedProcessIds += $Id
}}
'''
        + _extract_powershell_function(script, "Test-NativeWorkerProcess")
        + _extract_powershell_function(script, "Stop-NativeProcesses")
        + r'''
$result = Stop-NativeProcesses
if ($result.TargetIds -notcontains 4242) { throw "default worker was not selected for shutdown" }
if ($script:StoppedProcessIds -notcontains 4242) { throw "default worker was not stopped" }
'''
    )
    _assert_harness_ok(_run_harness(tmp_path, "dev-down-stops-default-worker", harness))
