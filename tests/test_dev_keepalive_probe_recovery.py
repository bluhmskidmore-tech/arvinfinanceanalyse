from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.governance_meta

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell")


def _require_powershell() -> str:
    if POWERSHELL is None:
        pytest.skip("Windows PowerShell is required for the keepalive harness")
    return POWERSHELL


def _extract_powershell_function(script: str, name: str) -> str:
    start = script.index(f"function {name} ")
    brace_start = script.index("{", start)
    depth = 0
    for index in range(brace_start, len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[start : index + 1]
    raise AssertionError(f"Could not extract PowerShell function {name}")


def _powershell_quote(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_harness(tmp_path: Path, source: str) -> subprocess.CompletedProcess[str]:
    harness = tmp_path / "keepalive-probe-harness.ps1"
    harness.write_text(source, encoding="utf-8")
    return subprocess.run(
        [
            _require_powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _fake_controller(root: Path, *, exit_code: int, stream: str | None) -> None:
    message = "probe stdout\\n" if stream == "stdout" else "probe stderr\\n"
    output = (
        "import sys\n"
        + (f"sys.{stream}.write({message!r})\n" if stream else "")
        + f"raise SystemExit({exit_code})\n"
    )
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "dev_runtime_control.py").write_text(output, encoding="utf-8")


def _probe_harness(script: str, fake_root: Path, expected: bool) -> str:
    ps_expected = "$true" if expected else "$false"
    return f'''
$ErrorActionPreference = "Stop"
$root = {_powershell_quote(fake_root)}
$expectedResult = {ps_expected}
function Get-DevRuntimePython {{ return {_powershell_quote(sys.executable)} }}
{_extract_powershell_function(script, "Test-FrontendReady")}
try {{
  $result = @(Test-FrontendReady)
  if ($result.Count -ne 1 -or $result[0] -isnot [bool] -or $result[0] -ne $expectedResult) {{
    throw "unexpected frontend readiness result: $result"
  }}
  "READY=$($result[0])"
}} catch {{
  Write-Error $_
  exit 91
}}
'''


@pytest.mark.parametrize(
    ("exit_code", "stream", "expected"),
    [
        (0, None, True),
        (73, "stdout", False),
        (73, "stderr", False),
    ],
    ids=["success", "nonzero-stdout", "nonzero-stderr"],
)
def test_frontend_probe_child_exit_and_stderr_are_fail_closed(
    tmp_path: Path,
    exit_code: int,
    stream: str | None,
    expected: bool,
) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    fake_root = tmp_path / "fake-root"
    _fake_controller(fake_root, exit_code=exit_code, stream=stream)

    completed = _run_harness(tmp_path, _probe_harness(script, fake_root, expected))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert f"READY={str(expected)}" in completed.stdout


def test_keepalive_recovers_frontend_after_probe_stderr_child_failure(
    tmp_path: Path,
) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    fake_root = tmp_path / "fake-root"
    _fake_controller(fake_root, exit_code=73, stream="stderr")
    harness = f'''
$ErrorActionPreference = "Stop"
$root = {_powershell_quote(fake_root)}
$script:FrontendRestartCalls = @()
function Get-DevRuntimePython {{ return {_powershell_quote(sys.executable)} }}
function Assert-DevRuntimeAllowed {{}}
function Ensure-DevPostgresRunning {{ return $true }}
function Test-HttpEndpoint {{ param([string]$Url) return $true }}
function Confirm-ServiceHealthy {{ param([string]$ServiceName) }}
function Update-ApiDependencyReadiness {{ param([bool]$Ready) }}
function Ensure-WorkerRunning {{}}
function Restart-HttpService {{
  param(
    [string]$ServiceName,
    [string]$ScriptName,
    [string]$Url,
    [int]$Port
  )
  $script:FrontendRestartCalls += $ServiceName
}}
{_extract_powershell_function(script, "Test-FrontendReady")}
{_extract_powershell_function(script, "Invoke-KeepaliveCycle")}
try {{
  Invoke-KeepaliveCycle
  if ($script:FrontendRestartCalls.Count -ne 1 -or $script:FrontendRestartCalls[0] -ne "frontend") {{
    throw "frontend recovery was not requested exactly once: $script:FrontendRestartCalls"
  }}
  "RESTARTED=$($script:FrontendRestartCalls[0])"
}} catch {{
  Write-Error $_
  exit 92
}}
'''

    completed = _run_harness(tmp_path, harness)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "RESTARTED=frontend" in completed.stdout


def test_api_dependency_degradation_is_recorded_without_restarting_live_api(
    tmp_path: Path,
) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = f'''
$ErrorActionPreference = "Stop"
$script:Messages = @()
$script:LastApiReadinessState = "unknown"
$lastHeartbeatAt = [datetime]::MinValue
$script:PostgresRecoveryFailureCount = 0
$script:ProcessInspectionAvailable = $true
function Assert-DevRuntimeAllowed {{}}
function Ensure-DevPostgresRunning {{ return $true }}
function Test-DevPostgresReady {{ return $true }}
function Test-HttpEndpoint {{
  param([string]$Url)
  return ($Url -eq "http://127.0.0.1:7888/health")
}}
function Confirm-ServiceHealthy {{ param([string]$ServiceName) }}
function Ensure-WorkerRunning {{}}
function Test-FrontendReady {{ return $true }}
function Restart-HttpService {{ throw "readiness degradation must not restart a live API" }}
function Write-KeepaliveLog {{ param([string]$Message) $script:Messages += $Message }}
{_extract_powershell_function(script, "Update-ApiDependencyReadiness")}
{_extract_powershell_function(script, "Invoke-KeepaliveCycle")}
{_extract_powershell_function(script, "Write-HeartbeatIfDue")}
Invoke-KeepaliveCycle
Write-HeartbeatIfDue
if (-not ($script:Messages -match "dependency readiness degraded")) {{
  throw "dependency degradation was not recorded"
}}
'''

    completed = _run_harness(tmp_path, harness)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_http_recovery_attempts_are_bounded_until_service_is_stably_healthy(
    tmp_path: Path,
) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = f'''
$ErrorActionPreference = "Stop"
$ServiceRecoveryMaxAttempts = 2
$RestartCooldownSeconds = 0
$serviceRecoveryAttempts = @{{}}
$serviceRecoverySuppressionLogged = @{{}}
$serviceHealthySince = @{{}}
$lastRestartAt = @{{}}
$script:StopCalls = 0
$script:Messages = @()
function Test-RestartCooldown {{ param([string]$Key) return $false }}
function Set-RestartTimestamp {{ param([string]$Key) $lastRestartAt[$Key] = Get-Date }}
function Write-KeepaliveLog {{ param([string]$Message) $script:Messages += $Message }}
function Stop-KnownServiceProcesses {{ param([string]$ServiceName) $script:StopCalls += 1 }}
function Start-DevScriptDetached {{ param([string]$ScriptName) }}
function Get-DevListeningPortOwner {{ param([int]$Port) return $null }}
function Wait-HttpEndpoint {{ param([string]$Url, [string]$Description) throw "still unavailable" }}
{_extract_powershell_function(script, "Get-ServiceRecoveryAttemptCount")}
{_extract_powershell_function(script, "Test-ServiceRecoverySuppressed")}
{_extract_powershell_function(script, "Register-ServiceRecoveryAttempt")}
{_extract_powershell_function(script, "Clear-ServiceHealthyObservation")}
{_extract_powershell_function(script, "Restart-HttpService")}
1..3 | ForEach-Object {{
  try {{
    Restart-HttpService -ServiceName "api" -ScriptName "dev-api.ps1" -Url "http://127.0.0.1:7888/health" -Port 7888
  }} catch {{}}
}}
if ($script:StopCalls -ne 2) {{ throw "expected exactly two bounded recoveries, got $($script:StopCalls)" }}
if ((Get-ServiceRecoveryAttemptCount -ServiceName "api") -ne 2) {{ throw "recovery attempt count drifted" }}
if (-not ($script:Messages -match "recovery suppressed after 2 attempts")) {{
  throw "missing bounded-recovery diagnostic"
}}
'''

    completed = _run_harness(tmp_path, harness)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_stable_health_clears_the_bounded_recovery_counter(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = f'''
$RestartCooldownSeconds = 15
$serviceRecoveryAttempts = @{{ api = 2 }}
$serviceRecoverySuppressionLogged = @{{ api = $true }}
$serviceHealthySince = @{{ api = (Get-Date).AddSeconds(-16) }}
$script:Messages = @()
function Write-KeepaliveLog {{ param([string]$Message) $script:Messages += $Message }}
{_extract_powershell_function(script, "Get-ServiceRecoveryAttemptCount")}
{_extract_powershell_function(script, "Confirm-ServiceHealthy")}
Confirm-ServiceHealthy -ServiceName "api"
if ((Get-ServiceRecoveryAttemptCount -ServiceName "api") -ne 0) {{ throw "stable health did not reset attempts" }}
if ($serviceRecoverySuppressionLogged["api"]) {{ throw "stable health did not clear suppression" }}
'''

    completed = _run_harness(tmp_path, harness)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_missing_worker_recovery_attempts_are_bounded(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = f'''
$ServiceRecoveryMaxAttempts = 2
$serviceRecoveryAttempts = @{{}}
$serviceRecoverySuppressionLogged = @{{}}
$serviceHealthySince = @{{}}
$script:ProcessInspectionAvailable = $true
$script:StartCalls = 0
$script:Messages = @()
function Get-NativeScriptProcess {{ param([string]$ScriptName) return $null }}
function Get-NativeWorkerProcess {{ return $null }}
function Test-RestartCooldown {{ param([string]$Key) return $false }}
function Set-RestartTimestamp {{ param([string]$Key) }}
function Stop-KnownServiceProcesses {{ param([string]$ServiceName) }}
function Start-DevScriptDetached {{ param([string]$ScriptName) $script:StartCalls += 1 }}
function Write-KeepaliveLog {{ param([string]$Message) $script:Messages += $Message }}
{_extract_powershell_function(script, "Get-ServiceRecoveryAttemptCount")}
{_extract_powershell_function(script, "Test-ServiceRecoverySuppressed")}
{_extract_powershell_function(script, "Register-ServiceRecoveryAttempt")}
{_extract_powershell_function(script, "Clear-ServiceHealthyObservation")}
{_extract_powershell_function(script, "Ensure-WorkerRunning")}
1..3 | ForEach-Object {{ Ensure-WorkerRunning }}
if ($script:StartCalls -ne 2) {{ throw "expected two bounded worker starts, got $($script:StartCalls)" }}
if (-not ($script:Messages -match "worker recovery suppressed after 2 attempts")) {{
  throw "missing bounded worker recovery diagnostic"
}}
'''

    completed = _run_harness(tmp_path, harness)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_flapping_health_does_not_clear_the_bounded_recovery_counter(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = f'''
$RestartCooldownSeconds = 15
$serviceRecoveryAttempts = @{{ api = 2 }}
$serviceRecoverySuppressionLogged = @{{ api = $false }}
$serviceHealthySince = @{{}}
function Write-KeepaliveLog {{ param([string]$Message) $script:Messages += $Message }}
{_extract_powershell_function(script, "Get-ServiceRecoveryAttemptCount")}
{_extract_powershell_function(script, "Clear-ServiceHealthyObservation")}
{_extract_powershell_function(script, "Confirm-ServiceHealthy")}
Confirm-ServiceHealthy -ServiceName "api"
Clear-ServiceHealthyObservation -ServiceName "api"
Confirm-ServiceHealthy -ServiceName "api"
Confirm-ServiceHealthy -ServiceName "api"
if ((Get-ServiceRecoveryAttemptCount -ServiceName "api") -ne 2) {{
  throw "flapping health incorrectly reset recovery attempts"
}}
'''

    completed = _run_harness(tmp_path, harness)

    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_postgres_gate_clears_all_service_health_observation_windows(tmp_path: Path) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    harness = f'''
$serviceHealthySince = @{{
  api = (Get-Date).AddMinutes(-1)
  worker = (Get-Date).AddMinutes(-1)
  frontend = (Get-Date).AddMinutes(-1)
}}
$script:LastPostgresProbeState = "missing"
function Assert-DevRuntimeAllowed {{}}
function Ensure-DevPostgresRunning {{ return $false }}
function Stop-KnownServiceProcesses {{ throw "missing Postgres must only gate this cycle" }}
function Write-KeepaliveLog {{ param([string]$Message) }}
{_extract_powershell_function(script, "Clear-ServiceHealthyObservation")}
{_extract_powershell_function(script, "Invoke-KeepaliveCycle")}
Invoke-KeepaliveCycle
foreach ($service in @("api", "worker", "frontend")) {{
  if ($serviceHealthySince.ContainsKey($service)) {{
    throw "Postgres gate retained $service continuous-health observation"
  }}
}}
'''

    completed = _run_harness(tmp_path, harness)

    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.parametrize("script_name", ["dev-api.ps1", "dev-worker.ps1"])
def test_detached_recovery_passes_current_environment_to_wmi(
    tmp_path: Path, script_name: str,
) -> None:
    script = (ROOT / "scripts" / "dev-keepalive.ps1").read_text(encoding="utf-8")
    fake_root = tmp_path / "fake-root"
    (fake_root / "scripts").mkdir(parents=True)
    (fake_root / "scripts" / script_name).write_text("", encoding="utf-8")
    harness = f'''
$ErrorActionPreference = "Stop"
$root = {_powershell_quote(fake_root)}
$logRoot = {_powershell_quote(tmp_path / "logs")}
$powershellExe = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
$script:ProcessInspectionAvailable = $true
$script:InspectionCalls = 0
$script:LaunchCalls = 0
$script:StartupProperties = $null
$env:MOSS_DUCKDB_PATH = "D:\\MOSS-data\\data\\moss.duckdb"
$env:MOSS_AGENT_DEV_SCOPE_BYPASS = "true"
$env:MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS = "1"
$env:MOSS_TEST_IN_MEMORY_SECRET = "fixture-only-sensitive-value"
function Get-NativeScriptProcess {{
  param([string]$ScriptName)
  $script:InspectionCalls += 1
  if ($script:InspectionCalls -gt 1) {{ return [pscustomobject]@{{ ProcessId = 424242 }} }}
  return $null
}}
function Get-NativeWorkerProcess {{ return $null }}
function Quote-CmdArgument {{ param([string]$Value) return ('"' + $Value + '"') }}
function Write-KeepaliveLog {{ param([string]$Message) }}
function New-CimInstance {{
  param([string]$ClassName,[switch]$ClientOnly,[hashtable]$Property)
  if ($ClassName -ne "Win32_ProcessStartup") {{ throw "unexpected CIM class" }}
  $script:StartupProperties = $Property
  return [pscustomobject]$Property
}}
function Invoke-CimMethod {{
  param([string]$ClassName,[string]$MethodName,[hashtable]$Arguments)
  $script:LaunchCalls += 1
  if ($ClassName -ne "Win32_Process" -or $MethodName -ne "Create") {{ throw "unexpected launch" }}
  if ($Arguments.ProcessStartupInformation.ShowWindow -ne 0) {{ throw "visible startup" }}
  return [pscustomobject]@{{ ReturnValue = 0; ProcessId = 424242 }}
}}
function Invoke-DevRuntimeAction {{ param([scriptblock]$Action) & $Action }}
{_extract_powershell_function(script, "Start-DevScriptDetached")}
Start-DevScriptDetached -ScriptName {_powershell_quote(script_name)}
if ($script:LaunchCalls -ne 1 -or $script:StartupProperties.ShowWindow -ne 0) {{
  throw "expected one hidden WMI launch"
}}
$inherited = @($script:StartupProperties.EnvironmentVariables)
foreach ($entry in @(
  "MOSS_DUCKDB_PATH=D:\\MOSS-data\\data\\moss.duckdb",
  "MOSS_AGENT_DEV_SCOPE_BYPASS=true",
  "MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS=1",
  "MOSS_TEST_IN_MEMORY_SECRET=fixture-only-sensitive-value"
)) {{
  if ($inherited -notcontains $entry) {{ throw "current environment was not supplied to WMI" }}
}}
"CURRENT_ENVIRONMENT_PASSED"
'''
    completed = _run_harness(tmp_path, harness)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "CURRENT_ENVIRONMENT_PASSED" in completed.stdout
    assert "fixture-only-sensitive-value" not in completed.stdout + completed.stderr
