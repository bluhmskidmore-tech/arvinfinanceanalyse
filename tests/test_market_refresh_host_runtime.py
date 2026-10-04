from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]
ROOT = Path(__file__).resolve().parents[1]
HOST_SCRIPT = ROOT / "scripts/scheduling/run_daily_data_refresh_host.ps1"
COMMON_SCRIPT = ROOT / "scripts/scheduling/market_refresh_host_common.ps1"


@pytest.mark.skipif(os.name != "nt", reason="Windows API identity functions")
@pytest.mark.parametrize("redirect_variant,accepted", [
    ("current_backend", True),
    ("wrong_base_executable", False),
    ("different_arguments", False),
    ("missing_venv_parent", False),
    ("foreign_venv_parent", False),
])
def test_backend_venv_redirected_api_requires_exact_base_and_parent(
    tmp_path: Path, redirect_variant: str, accepted: bool,
) -> None:
    # The current Python 3.11 venv redirector rewrites only argv[0] to the
    # configured base interpreter. Exercise real classification with a fake
    # process snapshot, without calling termination or service launch helpers.
    venv = tmp_path / "backend" / ".venv"
    venv.mkdir(parents=True)
    base_directory = tmp_path.parent / (tmp_path.name + "-Python311")
    (venv / "pyvenv.cfg").write_text(f"home = {base_directory}\n", encoding="utf-8")
    root = str(tmp_path).replace("'", "''")
    base_python = str(base_directory / "python.exe").replace("'", "''")
    common = str(COMMON_SCRIPT).replace("'", "''")
    driver = tmp_path / "backend-api-classification.ps1"
    driver.write_text(
        "$ErrorActionPreference='Stop'\n"
        f"$repoRoot='{root}'\n"
        f". '{common}'\n"
        "$venvPython=Join-Path $repoRoot 'backend\\.venv\\Scripts\\python.exe'\n"
        f"$basePython='{base_python}'\n"
        "$argsText='-m uvicorn backend.app.main:app --host 127.0.0.1 --port 7888'\n"
        "$parent=[pscustomobject]@{Name='python.exe';ProcessId=39572;ParentProcessId=41392;CreationDate='2026-10-04T07:54:53.501564Z';ExecutablePath=$venvPython;CommandLine=$venvPython+' '+$argsText}\n"
        "$child=[pscustomobject]@{Name='python.exe';ProcessId=40772;ParentProcessId=39572;CreationDate='2026-10-04T07:54:53.548430Z';ExecutablePath=$basePython;CommandLine='\"'+$basePython+'\" '+$argsText}\n"
        f"$variant='{redirect_variant}'\n"
        "if($variant -eq 'wrong_base_executable'){$child.ExecutablePath=Join-Path $repoRoot 'foreign\\python.exe';$child.CommandLine='\"'+$child.ExecutablePath+'\" '+$argsText}\n"
        "if($variant -eq 'different_arguments'){$child.CommandLine+=' --reload'}\n"
        "if($variant -eq 'missing_venv_parent'){$child.ParentProcessId=99999}\n"
        "if($variant -eq 'foreign_venv_parent'){$parent.ExecutablePath=Join-Path $repoRoot 'foreign\\.venv\\Scripts\\python.exe';$parent.CommandLine=$parent.ExecutablePath+' '+$argsText}\n"
        "$byId=@{};$byId[39572]=$parent;$byId[40772]=$child\n"
        "$approved=Test-ApiListenerIdentity -Process $child -ProcessesById $byId\n"
        "Write-Output ([bool]$approved).ToString().ToLowerInvariant()\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(driver)],
        capture_output=True, text=True, timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == str(accepted).lower()


@pytest.mark.skipif(os.name != "nt", reason="Windows API identity functions")
@pytest.mark.parametrize("command_suffix,ignored", [
    ('frontend-run --node "C:\\Program Files\\nodejs\\node.exe"', True),
    ('frontend-runner --node "C:\\Program Files\\nodejs\\node.exe"', False),
    ('run --command-base64 e30=', False),
    ('unknown-controller', False),
    ('frontend-run --node node.exe backend.app.main:app --port 7888', False),
    ('run --command-base64 e30= F:\\MOSS-V3\\scripts\\dev_runtime_control.py frontend-run --node node.exe', False),
])
def test_no_listener_excludes_only_exact_frontend_controller(
    tmp_path, command_suffix, ignored
) -> None:
    # Reproduce the actual frontend controller family using its executable
    # identities. Only process/port snapshots are isolated; all classification
    # functions come from the real host AST, with no termination/launch calls.
    root = str(ROOT).replace("'", "''")
    command_suffix = command_suffix.replace("F:\\MOSS-V3", str(ROOT))
    host = str(COMMON_SCRIPT).replace("'", "''")
    driver = tmp_path / "frontend-controller-classification.ps1"
    driver.write_text(
        "$ErrorActionPreference='Stop'\n"
        f"$repoRoot='{root}'\n"
        f". '{host}'\n"
        "function Get-ApiPortListeners { return @() }\n"
        "function Get-ProcessSnapshot {\n"
        f"  $command='\"{root}\\scripts\\dev_runtime_control.py\" --repo-root \"{root}\" "
        + command_suffix.replace("'", "''") + "'\n"
        "  [pscustomobject]@{Name='python.exe';ProcessId=51864;ParentProcessId=30796;CreationDate='2026-09-30T06:00:00Z';ExecutablePath='C:\\Users\\synthetic-user\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\python.exe';CommandLine='C:\\Users\\synthetic-user\\AppData\\Local\\hermes\\hermes-agent\\venv\\Scripts\\python.exe '+$command}\n"
        "  [pscustomobject]@{Name='python.exe';ProcessId=48032;ParentProcessId=51864;CreationDate='2026-09-30T06:00:00Z';ExecutablePath='C:\\Users\\synthetic-user\\AppData\\Local\\Programs\\Python\\Python311\\python.exe';CommandLine='\"C:\\Users\\synthetic-user\\AppData\\Local\\Programs\\Python\\Python311\\python.exe\" '+$command}\n"
        "}\n"
        "$tree=Get-ApiProcessTree\n"
        "if(@($tree.Processes).Count -ne 0){throw 'Frontend was selected as API'}\n"
        "Write-Output 'No API family selected'\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(driver)],
        capture_output=True, text=True, timeout=20,
    )
    if ignored:
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "No API family selected" in completed.stdout
    else:
        assert completed.returncode != 0
        assert "unverifiable executable identity (51864,48032)" in completed.stderr


def _powershell_function_source(source: str, name: str, next_name: str) -> str:
    start_marker = f"function {name} {{"
    end_marker = f"function {next_name} {{"
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end].rstrip()


def _run_host_harness(
    tmp_path: Path,
    *,
    api_running: bool,
    child_exit: int = 0,
    ownership_failure: bool = False,
    stop_failure: bool = False,
    no_listener_wrapper: bool = False,
    identity_change: str = "",
    invalid_enter_output: bool = False,
    foreign_listener: bool = False,
    foreign_marker_reason: bool = False,
    keepalive_running: bool = True,
    api_script_name: str = "dev-api.ps1",
    termination_return_value: int = 0,
    enter_stderr_after_marker: bool = False,
    late_api_tree: bool = False,
    post_drain_failure: str = "",
    residual_wrapper_disappears: bool = False,
    external_api_wrapper: bool = False,
    preexisting_marker: bool = False,
    balance_only: bool = False,
) -> subprocess.CompletedProcess[str]:
    scripts = tmp_path / "scripts"
    scheduling = scripts / "scheduling"
    scheduling.mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/scheduling/run_daily_data_refresh_host.ps1", scheduling / "run_daily_data_refresh_host.ps1")
    shutil.copyfile(COMMON_SCRIPT, scheduling / COMMON_SCRIPT.name)
    event_log = tmp_path / "lifecycle.log"
    marker_path = tmp_path / "tmp-governance" / "runtime-clean" / "control" / "maintenance.json"
    marker_path.parent.mkdir(parents=True)
    if preexisting_marker:
        marker_path.write_text(
            json.dumps(
                {
                    "state": "launch_blocked",
                    "drained": False,
                    "reason": "older maintenance owner",
                    "owner_token": "stale-maintenance-owner",
                    "entered_at": 0,
                }
            ),
            encoding="utf-8",
        )
    fake_python = tmp_path / "python.cmd"
    fake_python.write_text(
        "@echo off\n"
        'if "%~2"=="--run-once" (\n'
        '  echo balance>>"%CHOICE_TEST_EVENT_LOG%"\n'
        f"  exit /b {child_exit}\n"
        ")\n"
        'if "%~2"=="enter" (\n'
        '  echo enter>>"%CHOICE_TEST_EVENT_LOG%"\n'
        '  if "%CHOICE_TEST_OWNERSHIP_FAILURE%"=="1" exit /b 9\n'
        '  if "%CHOICE_TEST_FOREIGN_MARKER_REASON%"=="1" (\n'
        '    >"%CHOICE_TEST_MARKER_PATH%" echo {"state":"launch_blocked","drained":false,"reason":"another maintenance owner","owner_token":"synthetic-maintenance-owner","entered_at":1}\n'
        '  ) else (\n'
        '    >"%CHOICE_TEST_MARKER_PATH%" echo {"state":"launch_blocked","drained":false,"reason":"%~4","owner_token":"synthetic-maintenance-owner","entered_at":1}\n'
        '  )\n'
        '  if "%CHOICE_TEST_ENTER_STDERR_AFTER_MARKER%"=="1" (>&2 echo synthetic enter failure & exit /b 9)\n'
        '  if "%CHOICE_TEST_INVALID_ENTER_OUTPUT%"=="1" (echo invalid & exit /b 0)\n'
        '  echo {"state":"launch_blocked","owner_token":"synthetic-maintenance-owner"}\n'
        ")\n"
        'if "%~2"=="leave" (echo leave>>"%CHOICE_TEST_EVENT_LOG%" & del /q "%CHOICE_TEST_MARKER_PATH%" >nul 2>nul)\n'
        "exit /b 0\n",
        encoding="utf-8",
    )
    (scripts / "dev-env.ps1").write_text(
        "$devEnvPython = Join-Path (Split-Path $PSScriptRoot -Parent) 'python.cmd'\n",
        encoding="utf-8",
    )
    (scripts / "dev-up.ps1").write_text(
        "Add-Content -LiteralPath $env:CHOICE_TEST_EVENT_LOG -Value 'restore'\nexit 0\n",
        encoding="utf-8",
    )
    (scripts / "dev-api.ps1").write_text("exit 0\n", encoding="utf-8")
    (scripts / "dev-agent-api.ps1").write_text("exit 0\n", encoding="utf-8")
    (scheduling / "daily_data_refresh.ps1").write_text(
        "Add-Content -LiteralPath $env:CHOICE_TEST_EVENT_LOG -Value 'refresh'\n"
        f"exit {child_exit}\n",
        encoding="utf-8",
    )
    driver = tmp_path / "driver.ps1"
    driver.write_text(
        "$global:ChoiceTestApiAlive = $env:CHOICE_TEST_API_RUNNING -eq '1'\n"
        "$global:ChoiceTestStoppedIds = @()\n"
        "$global:ChoiceTestProcessInspectionCount = 0\n"
        "$global:ChoiceTestPortInspectionCount = 0\n"
        "$global:ChoiceTestPostDrainFailureRaised = $false\n"
        "$global:ChoiceTestLateApiArrived = $false\n"
        "$global:ChoiceTestRecoveryHealthFailed = $false\n"
        "$global:ChoiceTestResidualWrapperDisappeared = $false\n"
        "Add-Type -TypeDefinition @'\n"
        "using System;\n"
        "using System.IO;\n"
        "using System.Text;\n"
        "public static class MossDailyRefreshNativeProcessV1 {\n"
        " public static int TerminateVerified(uint processId, long expectedCreationUtcTicks, string expectedExecutablePath) {\n"
        "  if (Environment.GetEnvironmentVariable(\"CHOICE_TEST_STOP_FAILURE\") == \"1\" && processId == 424241U) throw new InvalidOperationException(\"synthetic stop failure\");\n"
        "  File.AppendAllText(Environment.GetEnvironmentVariable(\"CHOICE_TEST_EVENT_LOG\"), \"stop:\" + processId + Environment.NewLine, new UTF8Encoding(false));\n"
        "  return Int32.Parse(Environment.GetEnvironmentVariable(\"CHOICE_TEST_TERMINATION_RETURN_VALUE\"));\n"
        " }\n"
        "}\n"
        "'@\n"
        "function Get-NetIPConfiguration { [pscustomobject]@{\n"
        " NetAdapter=[pscustomobject]@{HardwareInterface=$true;Status='Up'}\n"
        " IPv4DefaultGateway='192.0.2.1'; InterfaceIndex=3; InterfaceAlias='test'\n"
        " NetIPv4Interface=[pscustomobject]@{InterfaceMetric=1}\n"
        "} }\n"
        "function Get-NetIPAddress { [pscustomobject]@{\n"
        " AddressState='Preferred';SkipAsSource=$false;IPAddress='192.0.2.10'\n"
        "} }\n"
        "function Get-NetTCPConnection { param([string]$State,[int]$LocalPort,[string]$ErrorAction)\n"
        " Add-Content -LiteralPath $env:CHOICE_TEST_EVENT_LOG -Value 'inspect-port'\n"
        " Invoke-ChoiceTestStoppedState\n"
        " $global:ChoiceTestPortInspectionCount++\n"
        " if ($env:CHOICE_TEST_LATE_API_TREE -eq '1' -and -not $global:ChoiceTestLateApiArrived -and -not $global:ChoiceTestApiAlive -and $global:ChoiceTestProcessInspectionCount -ge 1) {\n"
        "   $global:ChoiceTestApiAlive = $true\n"
        "   $global:ChoiceTestLateApiArrived = $true\n"
        "   Add-Content -LiteralPath $env:CHOICE_TEST_EVENT_LOG -Value 'late-api-arrived'\n"
        " }\n"
        " if ($env:CHOICE_TEST_POST_DRAIN_FAILURE -eq 'scan_error' -and -not $global:ChoiceTestPostDrainFailureRaised -and ($global:ChoiceTestStoppedIds -contains 424245) -and $global:ChoiceTestPortInspectionCount -ge 3) {\n"
        "   $global:ChoiceTestPostDrainFailureRaised = $true\n"
        "   throw 'synthetic quiet port scan failure'\n"
        " }\n"
         " if ($global:ChoiceTestApiAlive -and $env:CHOICE_TEST_NO_LISTENER_WRAPPER -ne '1') {\n"
         "   $listenerPid = if ($env:CHOICE_TEST_FOREIGN_LISTENER -eq '1') { 454545 } else { 424245 }\n"
         "   [pscustomobject]@{State='Listen';LocalPort=7888;OwningProcess=$listenerPid}\n"
         " }\n"
        "}\n"
        "function Get-CimInstance { param([string]$ClassName,[string]$Filter,[string]$ErrorAction)\n"
        " Add-Content -LiteralPath $env:CHOICE_TEST_EVENT_LOG -Value 'inspect-process'\n"
        " Invoke-ChoiceTestStoppedState\n"
        " if ($env:CHOICE_TEST_RESIDUAL_WRAPPER_DISAPPEARS -eq '1' -and $global:ChoiceTestRecoveryHealthFailed -and -not $global:ChoiceTestResidualWrapperDisappeared) {\n"
        "   $global:ChoiceTestStoppedIds += 424241\n"
        "   $global:ChoiceTestResidualWrapperDisappeared = $true\n"
        "   Add-Content -LiteralPath $env:CHOICE_TEST_EVENT_LOG -Value 'residual-wrapper-disappeared'\n"
        " }\n"
        " $global:ChoiceTestProcessInspectionCount++\n"
        " $root = $PSScriptRoot\n"
        " $venvPython = Join-Path $root '.venv\\Scripts\\python.exe'\n"
        " $basePython = 'C:\\Users\\tester\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe'\n"
        " $outerApiScript = Join-Path $root ('scripts\\' + $env:CHOICE_TEST_API_SCRIPT_NAME)\n"
        " $outerApiCommand = 'powershell.exe -File \"' + $outerApiScript + '\"'\n"
        " $keepaliveScript = Join-Path $root 'scripts\\dev-keepalive.ps1'\n"
        " $keepaliveCommand = 'powershell.exe -File \"' + $keepaliveScript + '\"'\n"
        " $uvicornCommand = $venvPython + ' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 7888'\n"
        " $runtimeControlCommand = $venvPython + ' ' + (Join-Path $root 'scripts\\dev_runtime_control.py') + ' --repo-root ' + $root + ' run --command-base64 synthetic'\n"
        " $rows = @(\n"
        "  [pscustomobject]@{Name='python.exe';ProcessId=424245;ParentProcessId=424244;CreationDate='2026-09-23T22:00:00.4242450Z';ExecutablePath=$basePython;CommandLine=$uvicornCommand},\n"
        "  [pscustomobject]@{Name='python.exe';ProcessId=424244;ParentProcessId=424243;CreationDate='2026-09-23T22:00:00.4242440Z';ExecutablePath=$venvPython;CommandLine=$uvicornCommand},\n"
        "  [pscustomobject]@{Name='python.exe';ProcessId=424243;ParentProcessId=424242;CreationDate='2026-09-23T22:00:00.4242430Z';ExecutablePath=$basePython;CommandLine=$runtimeControlCommand},\n"
        "  [pscustomobject]@{Name='python.exe';ProcessId=424242;ParentProcessId=424241;CreationDate='2026-09-23T22:00:00.4242420Z';ExecutablePath=$venvPython;CommandLine=$runtimeControlCommand},\n"
        "  [pscustomobject]@{Name='powershell.exe';ProcessId=424241;ParentProcessId=424240;CreationDate='2026-09-23T22:00:00.4242410Z';ExecutablePath='C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe';CommandLine=$outerApiCommand},\n"
        "  [pscustomobject]@{Name='cmd.exe';ProcessId=424240;ParentProcessId=400000;CreationDate='2026-09-23T22:00:00.4242400Z';ExecutablePath='C:\\Windows\\System32\\cmd.exe';CommandLine=('cmd.exe /d /c ' + $outerApiCommand)},\n"
        "  [pscustomobject]@{Name='powershell.exe';ProcessId=424239;ParentProcessId=400001;CreationDate='2026-09-23T22:00:00.4242390Z';ExecutablePath='C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe';CommandLine=$keepaliveCommand},\n"
        "  [pscustomobject]@{Name='python.exe';ProcessId=464646;ParentProcessId=400002;CreationDate='2026-09-23T22:00:00.4646460Z';ExecutablePath=(Join-Path $root '.venv\\Scripts\\python.exe');CommandLine=(Join-Path $root '.venv\\Scripts\\python.exe') + ' -m backend.app.tasks.dev_worker_runner --threads 4'},\n"
        "  [pscustomobject]@{Name='python.exe';ProcessId=454545;ParentProcessId=400003;CreationDate='2026-09-23T22:00:00.4545450Z';ExecutablePath='C:\\unrelated\\.venv\\Scripts\\python.exe';CommandLine='C:\\unrelated\\.venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --app-dir ' + $root + ' --port 7888'}\n"
        " )\n"
        " if ($env:CHOICE_TEST_FOREIGN_LISTENER -ne '1') { $rows = @($rows | Where-Object { $_.ProcessId -ne 454545 }) }\n"
        " if ($env:CHOICE_TEST_KEEPALIVE_RUNNING -ne '1') { $rows = @($rows | Where-Object { $_.ProcessId -ne 424239 }) }\n"
        " if (-not $global:ChoiceTestApiAlive) {\n"
        "   if ($env:CHOICE_TEST_RESIDUAL_WRAPPER_DISAPPEARS -eq '1') {\n"
        "     $rows = @($rows | Where-Object { $_.ProcessId -eq 424241 -or $_.ProcessId -notin @(424240,424241,424242,424243,424244,424245) })\n"
        "   } else {\n"
        "     $rows = @($rows | Where-Object { $_.ProcessId -notin @(424240,424241,424242,424243,424244,424245) })\n"
        "   }\n"
        " }\n"
        " if ($env:CHOICE_TEST_EXTERNAL_API_WRAPPER -eq '1') {\n"
        "   $repoApiReference = Join-Path $root 'scripts\\dev-api.ps1'\n"
        "   $rows += [pscustomobject]@{Name='powershell.exe';ProcessId=484848;ParentProcessId=400005;CreationDate='2026-09-23T22:00:00.4848480Z';ExecutablePath='C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe';CommandLine='powershell.exe -File \"C:\\other\\scripts\\dev-api.ps1\" --repo-root \"' + $root + '\" --reference \"' + $repoApiReference + '\"'}\n"
        " }\n"
        " if ($global:ChoiceTestProcessInspectionCount -ge 2 -and $env:CHOICE_TEST_IDENTITY_CHANGE -and $global:ChoiceTestApiAlive) {\n"
        "   $changed = $rows | Where-Object { $_.ProcessId -eq 424240 } | Select-Object -First 1\n"
        "   if ($changed) {\n"
        "     if ($env:CHOICE_TEST_IDENTITY_CHANGE -eq 'creation') { $changed.CreationDate = '2026-09-23T22:00:00.9999990Z' }\n"
        "     if ($env:CHOICE_TEST_IDENTITY_CHANGE -eq 'command') { $changed.CommandLine = $changed.CommandLine + ' --replaced' }\n"
        "     if ($env:CHOICE_TEST_IDENTITY_CHANGE -eq 'pid') { $changed.ExecutablePath = 'C:\\foreign\\python.exe'; $changed.CommandLine = 'C:\\foreign\\python.exe -m unrelated' }\n"
        "   }\n"
        " }\n"
        " if ($env:CHOICE_TEST_POST_DRAIN_FAILURE -eq 'unverifiable' -and -not $global:ChoiceTestPostDrainFailureRaised -and ($global:ChoiceTestStoppedIds -contains 424245) -and $global:ChoiceTestPortInspectionCount -ge 3) {\n"
        "   $global:ChoiceTestPostDrainFailureRaised = $true\n"
        "   $rows += [pscustomobject]@{Name='python.exe';ProcessId=474747;ParentProcessId=400004;CreationDate='2026-09-23T22:00:00.4747470Z';ExecutablePath='C:\\unapproved\\python.exe';CommandLine='C:\\unapproved\\python.exe -m uvicorn backend.app.main:app --app-dir ' + $root + ' --port 7888'}\n"
        " }\n"
        " return @($rows | Where-Object { -not ($global:ChoiceTestStoppedIds -contains $_.ProcessId) })\n"
        "}\n"
        "function Invoke-ChoiceTestStoppedState {\n"
        " $newStops = @(Get-Content -LiteralPath $env:CHOICE_TEST_EVENT_LOG -ErrorAction SilentlyContinue | Where-Object { $_ -match '^stop:(\\d+)$' } | ForEach-Object { [int]($_ -replace '^stop:', '') })\n"
        " $global:ChoiceTestStoppedIds = $newStops\n"
        " if ($newStops -contains 424245) { $global:ChoiceTestApiAlive = $false }\n"
        "}\n"
        "function Start-Process { param([string]$FilePath,[object[]]$ArgumentList,[string]$WorkingDirectory,[string]$WindowStyle,[string]$RedirectStandardOutput,[string]$RedirectStandardError)\n"
        " $payload = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([string]$ArgumentList[-1]))\n"
        " Add-Content -LiteralPath $env:CHOICE_TEST_EVENT_LOG -Value ('recover-payload:' + $payload)\n"
        " [pscustomobject]@{Id=515151}\n"
        "}\n"
        "function Invoke-WebRequest { param([string]$Uri,[switch]$UseBasicParsing,[int]$TimeoutSec)\n"
        " Add-Content -LiteralPath $env:CHOICE_TEST_EVENT_LOG -Value ('probe:' + $Uri)\n"
        " if ($env:CHOICE_TEST_RESIDUAL_WRAPPER_DISAPPEARS -eq '1' -and ($global:ChoiceTestStoppedIds -contains 424245) -and -not $global:ChoiceTestResidualWrapperDisappeared) {\n"
        "   $global:ChoiceTestRecoveryHealthFailed = $true\n"
        "   Add-Content -LiteralPath $env:CHOICE_TEST_EVENT_LOG -Value 'recovery-health-failed'\n"
        "   throw 'synthetic stale wrapper health failure'\n"
        " }\n"
        " [pscustomobject]@{StatusCode=200;Content='{}'}\n"
        "}\n"
        "if ($env:CHOICE_TEST_BALANCE_ONLY -eq '1') {\n"
        " & (Join-Path $PSScriptRoot 'scripts\\scheduling\\run_daily_data_refresh_host.ps1') -BalanceMovementOnly\n"
        "} else {\n"
        " & (Join-Path $PSScriptRoot 'scripts\\scheduling\\run_daily_data_refresh_host.ps1')\n"
        "}\n"
        "exit $LASTEXITCODE\n",
        encoding="utf-8",
    )
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(driver)],
        cwd=tmp_path,
        env={
            **os.environ,
            "CHOICE_TEST_EVENT_LOG": str(event_log),
            "CHOICE_TEST_API_RUNNING": "1" if api_running else "0",
            "CHOICE_TEST_OWNERSHIP_FAILURE": "1" if ownership_failure else "0",
            "CHOICE_TEST_STOP_FAILURE": "1" if stop_failure else "0",
            "CHOICE_TEST_NO_LISTENER_WRAPPER": "1" if no_listener_wrapper else "0",
            "CHOICE_TEST_IDENTITY_CHANGE": identity_change,
            "CHOICE_TEST_MARKER_PATH": str(marker_path),
            "CHOICE_TEST_INVALID_ENTER_OUTPUT": "1" if invalid_enter_output else "0",
            "CHOICE_TEST_FOREIGN_LISTENER": "1" if foreign_listener else "0",
            "CHOICE_TEST_FOREIGN_MARKER_REASON": "1" if foreign_marker_reason else "0",
            "CHOICE_TEST_KEEPALIVE_RUNNING": "1" if keepalive_running else "0",
            "CHOICE_TEST_API_SCRIPT_NAME": api_script_name,
            "CHOICE_TEST_TERMINATION_RETURN_VALUE": str(termination_return_value),
            "CHOICE_TEST_ENTER_STDERR_AFTER_MARKER": "1" if enter_stderr_after_marker else "0",
            "CHOICE_TEST_LATE_API_TREE": "1" if late_api_tree else "0",
            "CHOICE_TEST_POST_DRAIN_FAILURE": post_drain_failure,
            "CHOICE_TEST_RESIDUAL_WRAPPER_DISAPPEARS": "1" if residual_wrapper_disappears else "0",
            "CHOICE_TEST_EXTERNAL_API_WRAPPER": "1" if external_api_wrapper else "0",
            "CHOICE_TEST_BALANCE_ONLY": "1" if balance_only else "0",
        },
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
@pytest.mark.parametrize("child_exit", [0, 7])
def test_balance_host_reuses_owned_drain_and_recovers_after_writer_failure(
    tmp_path: Path, child_exit: int
) -> None:
    completed = _run_host_harness(
        tmp_path, api_running=True, child_exit=child_exit, balance_only=True
    )
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]
    assert completed.returncode == child_exit, completed.stderr
    assert "balance" in events
    assert "refresh" not in events
    assert events.index("enter") < events.index("stop:424240") < events.index("balance")
    assert events.index("balance") < events.index("leave")
    assert events.index("leave") < events.index("probe:http://127.0.0.1:7888/health")
    assert not any(event.startswith("stop:464646") for event in events)


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_balance_host_refuses_foreign_listener_before_writing(tmp_path: Path) -> None:
    completed = _run_host_harness(
        tmp_path, api_running=True, foreign_listener=True, balance_only=True
    )
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]
    assert completed.returncode != 0
    assert "not the repository API" in completed.stderr
    assert "balance" not in events
    assert not any(event.startswith("stop:") for event in events)
    assert "leave" in events


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_balance_host_refuses_unowned_maintenance_before_writing(tmp_path: Path) -> None:
    completed = _run_host_harness(
        tmp_path, api_running=True, ownership_failure=True, balance_only=True
    )
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]
    assert completed.returncode != 0
    assert events == ["enter"]


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
@pytest.mark.parametrize("child_exit", [0, 7])
def test_market_host_drains_full_owned_tree_before_refresh_and_uses_keepalive(
    tmp_path: Path, child_exit: int
) -> None:
    completed = _run_host_harness(tmp_path, api_running=True, child_exit=child_exit)
    event_log = tmp_path / "lifecycle.log"
    events = [line.strip() for line in event_log.read_text(encoding="utf-8-sig").splitlines()]

    assert completed.returncode == child_exit, completed.stdout + completed.stderr
    assert events.index("enter") < events.index("inspect-port")
    assert (
        events.index("stop:424240")
        < events.index("stop:424241")
        < events.index("stop:424242")
        < events.index("stop:424243")
        < events.index("stop:424244")
        < events.index("stop:424245")
    )
    assert events.index("refresh") > events.index("stop:424245")
    assert events.index("leave") > events.index("refresh")
    assert events.index("probe:http://127.0.0.1:7888/health") > events.index("leave")
    assert "stop:464646" not in events
    assert "restore" not in events
    assert list((tmp_path / "data/logs").glob("market_daily_host_*.log"))


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_acquires_and_releases_maintenance_when_api_is_absent(tmp_path: Path) -> None:
    completed = _run_host_harness(tmp_path, api_running=False)
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert events.index("enter") < events.index("inspect-port")
    assert events.count("refresh") == 1
    assert events.count("leave") == 1
    assert not any(event.startswith("stop:") for event in events)
    assert "restore" not in events


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_drains_api_tree_that_arrives_during_quiet_window(tmp_path: Path) -> None:
    completed = _run_host_harness(tmp_path, api_running=False, late_api_tree=True)
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert events.index("inspect-process") < events.index("late-api-arrived")
    assert [event for event in events if event.startswith("stop:")] == [
        "stop:424240",
        "stop:424241",
        "stop:424242",
        "stop:424243",
        "stop:424244",
        "stop:424245",
    ]
    assert events.index("late-api-arrived") < events.index("stop:424240")
    assert events.index("stop:424245") < events.index("refresh")
    assert events.index("refresh") < events.index("leave")


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_drains_dev_api_wrappers_when_port_is_closed(tmp_path: Path) -> None:
    completed = _run_host_harness(tmp_path, api_running=True, no_listener_wrapper=True)
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "inspect-port" in events
    assert (
        events.index("stop:424240")
        < events.index("stop:424241")
        < events.index("stop:424242")
        < events.index("stop:424243")
        < events.index("stop:424244")
        < events.index("stop:424245")
    )
    assert events.index("refresh") > events.index("stop:424245")
    assert "stop:464646" not in events


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_never_stops_external_api_wrapper_that_only_mentions_repo_root(tmp_path: Path) -> None:
    completed = _run_host_harness(
        tmp_path,
        api_running=False,
        external_api_wrapper=True,
    )
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert not any(event.startswith("stop:") for event in events)
    assert "refresh" not in events
    assert events.count("leave") == 1
    assert "unverifiable executable identity (484848)" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
@pytest.mark.parametrize("identity_change", ["creation", "command", "pid"])
def test_market_host_refuses_identity_change_or_pid_reuse(
    tmp_path: Path, identity_change: str
) -> None:
    completed = _run_host_harness(tmp_path, api_running=True, identity_change=identity_change)
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert not any(event.startswith("stop:") for event in events)
    assert "refresh" not in events
    assert "identity changed before stop" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_reports_stop_failure_and_does_not_start_writer(tmp_path: Path) -> None:
    completed = _run_host_harness(tmp_path, api_running=True, stop_failure=True)
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "refresh" not in events
    assert "leave" in events
    assert "Could not stop every repository API process" in completed.stderr
    assert "Market refresh primary failure" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_launches_owned_recovery_after_residual_wrapper_disappears(tmp_path: Path) -> None:
    completed = _run_host_harness(
        tmp_path,
        api_running=True,
        keepalive_running=False,
        stop_failure=True,
        residual_wrapper_disappears=True,
    )
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]
    recovery_index = next(index for index, event in enumerate(events) if event.startswith("recover-payload:"))

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "refresh" not in events
    assert "stop:424241" not in events
    assert (
        events.index("leave")
        < events.index("recovery-health-failed")
        < events.index("residual-wrapper-disappeared")
        < recovery_index
    )
    assert recovery_index < len(events) - 1
    assert events[recovery_index + 1 :] == [
        "probe:http://127.0.0.1:7888/health",
        "probe:http://127.0.0.1:7888/health/ready",
    ]
    assert "Market refresh primary failure: Could not stop every repository API process" in completed.stderr
    assert "Market refresh recovery failure(s)" not in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
@pytest.mark.parametrize(
    ("post_drain_failure", "expected_failure"),
    [
        (
            "scan_error",
            "Could not inspect TCP port 7888; API drain refused: synthetic quiet port scan failure",
        ),
        (
            "unverifiable",
            "Repository-like API processes have unverifiable executable identity (474747); writer was not started.",
        ),
    ],
)
def test_market_host_releases_and_recovers_after_post_drain_quiet_scan_failure(
    tmp_path: Path,
    post_drain_failure: str,
    expected_failure: str,
) -> None:
    completed = _run_host_harness(
        tmp_path,
        api_running=True,
        keepalive_running=False,
        post_drain_failure=post_drain_failure,
    )
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]
    recovery_index = next(index for index, event in enumerate(events) if event.startswith("recover-payload:"))

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert events.index("stop:424245") < events.index("leave") < recovery_index
    assert "refresh" not in events
    assert events.count("leave") == 1
    assert recovery_index < events.index("probe:http://127.0.0.1:7888/health")
    assert recovery_index < events.index("probe:http://127.0.0.1:7888/health/ready")
    assert f"Market refresh primary failure: {expected_failure}" in completed.stderr
    assert "Market refresh recovery failure(s)" not in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_refuses_nonzero_cim_termination_status(tmp_path: Path) -> None:
    completed = _run_host_harness(tmp_path, api_running=True, termination_return_value=5)
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "refresh" not in events
    assert "native termination returned 5" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_ownership_failure_happens_before_api_discovery(tmp_path: Path) -> None:
    completed = _run_host_harness(tmp_path, api_running=True, ownership_failure=True)
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert events == ["enter"]
    assert "valid durable claim" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_releases_claim_when_enter_output_is_invalid(tmp_path: Path) -> None:
    completed = _run_host_harness(tmp_path, api_running=True, invalid_enter_output=True)
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]
    marker_path = tmp_path / "tmp-governance" / "runtime-clean" / "control" / "maintenance.json"

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert events == ["enter", "leave"]
    assert not marker_path.exists()
    assert "claim adopted for cleanup" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_adopts_exact_reason_claim_after_preexisting_marker(tmp_path: Path) -> None:
    completed = _run_host_harness(
        tmp_path,
        api_running=True,
        invalid_enter_output=True,
        preexisting_marker=True,
    )
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]
    marker_path = tmp_path / "tmp-governance" / "runtime-clean" / "control" / "maintenance.json"

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert events == ["enter", "leave"]
    assert not marker_path.exists()
    assert "claim adopted for cleanup" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_releases_claim_when_enter_writes_stderr_and_fails(tmp_path: Path) -> None:
    completed = _run_host_harness(tmp_path, api_running=True, enter_stderr_after_marker=True)
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]
    marker_path = tmp_path / "tmp-governance" / "runtime-clean" / "control" / "maintenance.json"

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert events == ["enter", "leave"]
    assert not marker_path.exists()
    assert "claim adopted for cleanup" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_never_adopts_another_maintenance_owner(tmp_path: Path) -> None:
    completed = _run_host_harness(
        tmp_path,
        api_running=True,
        invalid_enter_output=True,
        foreign_marker_reason=True,
    )
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]
    marker_path = tmp_path / "tmp-governance" / "runtime-clean" / "control" / "maintenance.json"

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert events == ["enter"]
    assert marker_path.exists()
    assert "valid durable claim" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_market_host_refuses_foreign_listener_identity(tmp_path: Path) -> None:
    completed = _run_host_harness(tmp_path, api_running=True, foreign_listener=True)
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]

    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert events[:2] == ["enter", "inspect-port"]
    assert not any(event.startswith("stop:") for event in events)
    assert "not the repository API" in completed.stderr


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
@pytest.mark.parametrize("api_script_name", ["dev-api.ps1", "dev-agent-api.ps1"])
def test_market_host_owned_recovery_preserves_api_entrypoint(
    tmp_path: Path, api_script_name: str
) -> None:
    completed = _run_host_harness(
        tmp_path,
        api_running=True,
        keepalive_running=False,
        api_script_name=api_script_name,
    )
    events = [line.strip() for line in (tmp_path / "lifecycle.log").read_text(encoding="utf-8-sig").splitlines()]
    payload_line = next(event for event in events if event.startswith("recover-payload:"))
    payload = __import__("json").loads(payload_line.removeprefix("recover-payload:"))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert any(str(argument).endswith(api_script_name) for argument in payload["argv"])
    if api_script_name == "dev-api.ps1":
        assert "-SkipStartupStorageMigrations" in payload["argv"]
    else:
        assert "-SkipStartupStorageMigrations" not in payload["argv"]


@pytest.mark.skipif(os.name != "nt", reason="Windows scheduler entry point")
def test_repository_command_rejects_similarly_prefixed_repo_copy(tmp_path: Path) -> None:
    powershell = shutil.which("powershell.exe")
    assert powershell is not None
    host_source = COMMON_SCRIPT.read_text(encoding="utf-8")
    repository_command_function = _powershell_function_source(
        host_source,
        "Test-RepositoryCommand",
        "Convert-ProcessIdentityValue",
    )
    driver = tmp_path / "repository-command-boundary.ps1"
    driver.write_text(
        "param([string]$RootPath)\n"
        "$ErrorActionPreference = 'Stop'\n"
        "$repoRoot = $RootPath\n"
        + repository_command_function
        + "\n"
        "$approvedPowerShell = Join-Path $env:SystemRoot 'System32\\WindowsPowerShell\\v1.0\\powershell.exe'\n"
        "$candidate = [pscustomobject]@{\n"
        "  Name = 'powershell.exe'\n"
        "  ExecutablePath = $approvedPowerShell\n"
        "  CommandLine = '& \"' + $approvedPowerShell + '\" -File \"' + $RootPath + '-copy\\scripts\\dev-api.ps1\"'\n"
        "}\n"
        "[pscustomobject]@{is_repository = [bool](Test-RepositoryCommand -Process $candidate)} | ConvertTo-Json -Compress\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(driver),
            "-RootPath",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(completed.stdout) == {"is_repository": False}


@pytest.mark.skipif(os.name != "nt", reason="Windows native process termination")
def test_terminate_verified_process_uses_native_handle_to_stop_real_process(tmp_path: Path) -> None:
    powershell = shutil.which("powershell.exe")
    assert powershell is not None
    host_source = COMMON_SCRIPT.read_text(encoding="utf-8")
    native_functions = "\n\n".join(
        [
            _powershell_function_source(
                host_source,
                "Convert-ProcessIdentityValue",
                "Get-ProcessIdentity",
            ),
            _powershell_function_source(
                host_source,
                "Initialize-NativeProcessApi",
                "Terminate-VerifiedProcess",
            ),
            _powershell_function_source(
                host_source,
                "Terminate-VerifiedProcess",
                "Stop-ApiProcessTree",
            ),
        ]
    )
    driver = tmp_path / "terminate-verified-process.ps1"
    driver.write_text(
        "param([int]$TargetProcessId)\n"
        "$ErrorActionPreference = 'Stop'\n"
        + native_functions
        + "\n"
        "$target = Get-CimInstance -ClassName Win32_Process -Filter (\"ProcessId = {0}\" -f $TargetProcessId) -ErrorAction Stop\n"
        "if ($null -eq $target) { throw \"Target process $TargetProcessId was not found.\" }\n"
        "Terminate-VerifiedProcess -Process $target\n",
        encoding="utf-8",
    )
    sleeper = subprocess.Popen(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", "Start-Sleep -Seconds 120"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        completed = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(driver),
                "-TargetProcessId",
                str(sleeper.pid),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert sleeper.wait(timeout=10) is not None
    finally:
        if sleeper.poll() is None:
            sleeper.terminate()
            sleeper.wait(timeout=10)
