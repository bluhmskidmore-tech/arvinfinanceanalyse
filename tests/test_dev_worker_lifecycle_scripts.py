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


def test_dev_keepalive_skips_postgres_recovery_when_private_cluster_is_healthy(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = (
        r'''
$PostgresRecoveryMaxAttempts = 3
$PostgresProbeFailureThreshold = 3
$script:PostgresRecoveryFailureCount = 0
$script:PostgresRecoverySuppressionLogged = $false
$script:RecoveryAttempted = $false

function Get-DevPostgresProbe { return [pscustomobject]@{ State = "owned"; OwningProcess = 4242 } }
function Invoke-DevPostgresUp { $script:RecoveryAttempted = $true; throw "unexpected recovery" }
function Test-RestartCooldown { param([string]$Key) return $false }
function Set-RestartTimestamp { param([string]$Key) }
function Write-KeepaliveLog { param([string]$Message) }
'''
        + _extract_powershell_function(script, "Ensure-DevPostgresRunning")
        + r'''
$ready = Ensure-DevPostgresRunning
if (-not $ready) { throw "healthy private Postgres cluster was reported unavailable" }
if ($script:RecoveryAttempted) { throw "healthy private Postgres cluster triggered recovery" }
'''
    )
    _assert_harness_ok(_run_harness(tmp_path, "dev-keepalive-postgres-healthy", harness))


def test_dev_keepalive_recovers_private_postgres_when_listener_is_down(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = (
        r'''
$PostgresRecoveryMaxAttempts = 3
$PostgresProbeFailureThreshold = 3
$script:PostgresRecoveryFailureCount = 0
$script:PostgresRecoverySuppressionLogged = $false
$script:ProbeCalls = 0
$script:RecoveryCalls = 0

function Get-DevPostgresProbe {
  $script:ProbeCalls += 1
  $state = if ($script:ProbeCalls -ge 4) { "owned" } else { "missing" }
  return [pscustomobject]@{ State = $state; OwningProcess = $null }
}
function Invoke-DevPostgresUp {
  $script:RecoveryCalls += 1
  return [pscustomobject]@{ ExitCode = 0; Output = "started" }
}
function Test-RestartCooldown { param([string]$Key) return $false }
function Set-RestartTimestamp { param([string]$Key) }
function Write-KeepaliveLog { param([string]$Message) }
'''
        + _extract_powershell_function(script, "Ensure-DevPostgresRunning")
        + r'''
$first = Ensure-DevPostgresRunning
$second = Ensure-DevPostgresRunning
$ready = Ensure-DevPostgresRunning
if ($first -or $second) { throw "transient probe failures triggered recovery before threshold" }
if (-not $ready) { throw "private Postgres cluster was not reported recovered" }
if ($script:RecoveryCalls -ne 1) { throw "expected one recovery call, got $($script:RecoveryCalls)" }
if ($script:PostgresRecoveryFailureCount -ne 0) { throw "successful recovery did not reset the failure counter" }
'''
    )
    _assert_harness_ok(_run_harness(tmp_path, "dev-keepalive-postgres-recovers", harness))


def test_dev_keepalive_caps_failed_postgres_recovery_attempts(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = (
        r'''
$PostgresRecoveryMaxAttempts = 3
$PostgresProbeFailureThreshold = 1
$script:PostgresRecoveryFailureCount = 0
$script:PostgresRecoverySuppressionLogged = $false
$script:RecoveryCalls = 0
$script:Messages = @()

function Get-DevPostgresProbe { return [pscustomobject]@{ State = "missing"; OwningProcess = $null } }
function Invoke-DevPostgresUp {
  $script:RecoveryCalls += 1
  return [pscustomobject]@{ ExitCode = 1; Output = "failed" }
}
function Test-RestartCooldown { param([string]$Key) return $false }
function Set-RestartTimestamp { param([string]$Key) }
function Write-KeepaliveLog { param([string]$Message) $script:Messages += $Message }
'''
        + _extract_powershell_function(script, "Ensure-DevPostgresRunning")
        + r'''
1..4 | ForEach-Object { Ensure-DevPostgresRunning | Out-Null }
if ($script:RecoveryCalls -ne 3) { throw "expected recovery to stop after 3 attempts, got $($script:RecoveryCalls)" }
if ($script:PostgresRecoveryFailureCount -ne 3) { throw "expected 3 recorded failures" }
if (-not ($script:Messages -match "suppressed after 3 failed attempts")) {
  throw "missing bounded-recovery suppression log"
}
'''
    )
    _assert_harness_ok(_run_harness(tmp_path, "dev-keepalive-postgres-bounded", harness))


def test_dev_keepalive_fails_closed_for_foreign_postgres_listener(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = (
        r'''
$PostgresRecoveryMaxAttempts = 3
$PostgresProbeFailureThreshold = 3
$script:PostgresRecoveryFailureCount = 0
$script:PostgresRecoverySuppressionLogged = $false
$script:RecoveryAttempted = $false
$script:Messages = @()

function Get-DevPostgresProbe { return [pscustomobject]@{ State = "foreign"; OwningProcess = 9001 } }
function Invoke-DevPostgresUp { $script:RecoveryAttempted = $true; throw "unsafe recovery" }
function Test-RestartCooldown { param([string]$Key) return $false }
function Set-RestartTimestamp { param([string]$Key) }
function Write-KeepaliveLog { param([string]$Message) $script:Messages += $Message }
'''
        + _extract_powershell_function(script, "Ensure-DevPostgresRunning")
        + r'''
$ready = Ensure-DevPostgresRunning
if ($ready) { throw "foreign listener was reported as the private cluster" }
if ($script:RecoveryAttempted) { throw "foreign listener triggered dev-postgres-up.ps1" }
if (-not ($script:Messages -match "foreign listener")) { throw "missing fail-closed ownership diagnostic" }
'''
    )
    _assert_harness_ok(_run_harness(tmp_path, "dev-keepalive-postgres-foreign", harness))


def test_dev_keepalive_stops_api_and_worker_behind_foreign_postgres_gate(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = (
        r'''
$script:LastPostgresProbeState = "foreign"
$script:StoppedServices = @()

function Ensure-DevPostgresRunning { return $false }
function Stop-KnownServiceProcesses { param([string]$ServiceName) $script:StoppedServices += $ServiceName }
function Write-KeepaliveLog { param([string]$Message) }
function Test-HttpEndpoint { throw "API probe must not run behind ownership gate" }
function Restart-HttpService { throw "service restart must not run behind ownership gate" }
function Ensure-WorkerRunning { throw "worker restart must not run behind ownership gate" }
function Test-FrontendReady { throw "frontend recovery must not run behind ownership gate" }
'''
        + _extract_powershell_function(script, "Invoke-KeepaliveCycle")
        + r'''
Invoke-KeepaliveCycle
if ($script:StoppedServices -notcontains "api") { throw "foreign ownership gate did not stop API" }
if ($script:StoppedServices -notcontains "worker") { throw "foreign ownership gate did not stop worker" }
'''
    )
    _assert_harness_ok(_run_harness(tmp_path, "dev-keepalive-postgres-foreign-gate", harness))


def test_dev_keepalive_monitors_only_private_postgres_port_and_heartbeats_it() -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    probe = _extract_powershell_function(script, "Get-DevPostgresProbe")
    heartbeat = _extract_powershell_function(script, "Write-HeartbeatIfDue")

    assert "Get-DevListeningPortOwner -Port 55432" in probe
    assert "Get-DevListeningPortOwner -Port 5432" not in probe
    assert r"tmp-governance\pgdev\data" in probe
    assert '"foreign"' in probe
    assert "State = $state" in probe
    assert "Ensure-DevPostgresRunning" in _extract_powershell_function(script, "Invoke-KeepaliveCycle")
    assert "postgres=$postgresOk" in heartbeat
    assert "postgresRecoveryFailures=$script:PostgresRecoveryFailureCount" in heartbeat


def test_dev_down_waits_for_keepalive_before_stopping_private_postgres() -> None:
    script = (ROOT / "scripts" / "dev-down.ps1").read_text(encoding="utf-8")

    keepalive_wait = script.index('Wait-ProcessStopped -Description "keepalive"')
    postgres_down = script.index(r'& (Join-Path $root "scripts\dev-postgres-down.ps1")')

    assert keepalive_wait < postgres_down


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
