from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "scheduling" / "register_scheduled_tasks.ps1"

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]


def _prepare_script_copy(tmp_path: Path) -> Path:
    script_copy = tmp_path / "scripts" / "scheduling" / "register_scheduled_tasks.ps1"
    script_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SCRIPT, script_copy)
    for name in ("run_daily_data_refresh_host.ps1", "market_refresh_host_common.ps1"):
        shutil.copyfile(SCRIPT.parent / name, script_copy.parent / name)
    shutil.copyfile(
        ROOT / "scripts" / "scheduling" / "daily_data_refresh.ps1",
        script_copy.parent / "daily_data_refresh.ps1",
    )
    shutil.copyfile(
        ROOT / "scripts" / "scheduling" / "monthly_walk_forward.ps1",
        script_copy.parent / "monthly_walk_forward.ps1",
    )
    return script_copy


def _run_powershell(script_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            *args,
        ],
        cwd=script_path.parents[2],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        stdin=subprocess.DEVNULL,
    )


def test_register_script_can_forward_vendor_source_ip_into_daily_chain() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert '[string]$VendorSourceIp = ""' in text
    assert '[string]$DailyTime = "18:45"' in text
    assert "function ConvertTo-CommandLineString" in text
    assert "$dailyScriptArgs = @()" in text
    assert "Resolve-ValidatedVendorSourceIp" in text
    assert "VendorSourceIp must be a plain IPv4 literal" in text
    assert "-ScriptArgs $dailyScriptArgs" in text
    assert '$dailyScript = Join-Path $PSScriptRoot "run_daily_data_refresh_host.ps1"' in text
    assert '"market_refresh_host_common.ps1"' in text
    assert '"-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`"$scriptArgString"' in text


def test_register_script_rejects_malicious_vendor_source_ip_before_scheduler_calls(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    sentinel = tmp_path / "schtasks-called.txt"
    harness = tmp_path / "harness.ps1"
    harness.write_text(
        f"""
function schtasks {{
    Add-Content -Path "{sentinel}" -Value "called"
    throw "schtasks should not be called"
}}
function Set-ScheduledTask {{
    throw "Set-ScheduledTask should not be called"
}}
& "{script_path}" -RepoRoot "{ROOT}" -DailyTime "18:45" -VendorSourceIp "10.0.0.9;Remove-Item C:\\\\oops"
exit $LASTEXITCODE
""".strip(),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        stdin=subprocess.DEVNULL,
    )

    assert completed.returncode != 0
    assert "plain IPv4 literal" in (completed.stderr or completed.stdout)
    assert not sentinel.exists()


@pytest.mark.parametrize("script_name", ["install_data_update_queue.ps1", "register_scheduled_tasks.ps1"])
def test_registrars_accept_backend_only_python_and_preserve_task_actions(tmp_path: Path, script_name: str) -> None:
    scripts = tmp_path / "scripts"
    scheduling = scripts / "scheduling"
    scheduling.mkdir(parents=True)
    registrar = scheduling / script_name
    shutil.copyfile(ROOT / "scripts/scheduling" / script_name, registrar)
    for name in ("run_daily_data_refresh_host.ps1", "market_refresh_host_common.ps1", "monthly_walk_forward.ps1", "drain_data_updates.ps1"):
        (scheduling / name).write_text("# synthetic path; never executed\n", encoding="utf-8")
    selected = tmp_path / "backend/.venv/Scripts/python.exe"
    selected.parent.mkdir(parents=True)
    selected.write_bytes(b"synthetic Python; never executed")
    resolver_marker = tmp_path / "resolver.txt"
    (scripts / "dev-python.ps1").write_text(
        "function Resolve-DevPython { param([string[]]$RequiredModules)\n"
        "  [IO.File]::WriteAllText($env:MOSS_TEST_RESOLVER_MARKER, ($RequiredModules -join ','))\n"
        "  return $env:MOSS_TEST_SELECTED_PYTHON\n}\n",
        encoding="utf-8",
    )
    calls = tmp_path / "registration-calls.json"
    harness = tmp_path / "registrar-harness.ps1"
    harness.write_text(
        """
$global:RecordedCalls = @()
function schtasks {
  $global:RecordedCalls += @{ kind = 'schtasks'; arguments = @($args) }
  $global:LASTEXITCODE = 0
}
function New-ScheduledTaskAction {
  param($Execute, $Argument, $WorkingDirectory)
  return @{ execute = $Execute; arguments = $Argument; directory = $WorkingDirectory }
}
function New-ScheduledTaskTrigger {
  param([switch]$Once, $At, $RepetitionInterval)
  return @{ once = [bool]$Once; at = $At; repeat_minutes = $RepetitionInterval.TotalMinutes }
}
function New-ScheduledTaskSettingsSet {
  param([switch]$StartWhenAvailable, [switch]$AllowStartIfOnBatteries,
        [switch]$DontStopIfGoingOnBatteries, $MultipleInstances, $ExecutionTimeLimit)
  return @{ start_available = [bool]$StartWhenAvailable; allow_battery = [bool]$AllowStartIfOnBatteries;
            stay_on_battery = [bool]$DontStopIfGoingOnBatteries; multiple = $MultipleInstances;
            limit_hours = $ExecutionTimeLimit.TotalHours }
}
function Register-ScheduledTask {
  param($TaskName, $Action, $Trigger, $Settings, $Description, [switch]$Force)
  $global:RecordedCalls += @{ kind = 'register'; name = $TaskName; action = $Action;
                             trigger = $Trigger; settings = $Settings; force = [bool]$Force }
}
function Set-ScheduledTask {
  param($TaskName, $Action, $Settings)
  $global:RecordedCalls += @{ kind = 'set'; name = $TaskName; action = $Action; settings = $Settings }
}
function Get-ScheduledTask { param($TaskName) return @{ State = 'Disabled' } }
$parameters = @{ RepoRoot = $env:MOSS_TEST_REPO_ROOT }
if ($env:MOSS_TEST_REGISTRAR_NAME -eq 'register_scheduled_tasks.ps1') {
  $parameters.DailyTime = '19:35'
  $parameters.MonthlyTime = '08:10'
  $parameters.VendorSourceIp = '10.0.0.9'
}
& $env:MOSS_TEST_REGISTRAR @parameters
[IO.File]::WriteAllText($env:MOSS_TEST_REGISTRATION_CALLS, (ConvertTo-Json -InputObject @($global:RecordedCalls) -Depth 8))
""".lstrip(),
        encoding="utf-8",
    )
    environment = {key: value for key, value in os.environ.items() if key not in {"MOSS_PYTHON", "VIRTUAL_ENV"}}
    environment.update(
        MOSS_TEST_REGISTRAR=str(registrar), MOSS_TEST_REGISTRAR_NAME=script_name,
        MOSS_TEST_REPO_ROOT=str(tmp_path), MOSS_TEST_SELECTED_PYTHON=str(selected),
        MOSS_TEST_RESOLVER_MARKER=str(resolver_marker), MOSS_TEST_REGISTRATION_CALLS=str(calls),
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(harness)], env=environment,
        capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert resolver_marker.read_text(encoding="utf-8") == "duckdb"
    observed = json.loads(calls.read_text(encoding="utf-8"))
    executable = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
    prefix = '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File '
    if script_name == "install_data_update_queue.ps1":
        assert len(observed) == 1
        registration = observed[0]
        assert registration["kind"] == "register"
        assert registration["name"] == "MOSS-DataUpdateQueue"
        assert registration["action"] == {
            "execute": executable, "arguments": prefix + f'"{scheduling / "drain_data_updates.ps1"}"', "directory": str(tmp_path),
        }
        assert registration["trigger"]["once"] is True
        assert registration["trigger"]["repeat_minutes"] == 5
        assert registration["settings"]["multiple"] == "IgnoreNew"
        assert registration["settings"]["limit_hours"] == 6
        assert registration["force"] is True
    else:
        create = [call for call in observed if call["kind"] == "schtasks"]
        assert len(create) == 2
        assert create[0]["arguments"][5:] == ["/SC", "DAILY", "/ST", "19:35", "/F", "/RL", "LIMITED"]
        assert create[1]["arguments"][5:] == ["/SC", "MONTHLY", "/MO", "FIRST", "/D", "SAT", "/ST", "08:10", "/F", "/RL", "LIMITED"]
        settings = [call for call in observed if call["kind"] == "set"]
        assert [call["name"] for call in settings] == ["MOSS-DailyDataRefresh", "MOSS-MonthlyWalkForward"]
        for call, entry, suffix in zip(settings, ["run_daily_data_refresh_host.ps1", "monthly_walk_forward.ps1"], [" -VendorSourceIp 10.0.0.9", ""], strict=True):
            assert call["action"] == {
                "execute": executable, "arguments": prefix + f'"{scheduling / entry}"' + suffix, "directory": str(tmp_path),
            }
            assert call["settings"]["limit_hours"] == 6
    for call in observed:
        if "settings" in call:
            assert call["settings"]["start_available"] is True
            assert call["settings"]["allow_battery"] is True
            assert call["settings"]["stay_on_battery"] is True
    assert not (tmp_path / ".venv").exists()


@pytest.mark.parametrize("script_name", ["install_data_update_queue.ps1", "register_scheduled_tasks.ps1"])
@pytest.mark.parametrize("mode", ["WhatIf", "Unregister"])
def test_registrar_preview_and_unregister_do_not_resolve_runtime(tmp_path: Path, script_name: str, mode: str) -> None:
    scripts = tmp_path / "scripts"
    scheduling = scripts / "scheduling"
    scheduling.mkdir(parents=True)
    registrar = scheduling / script_name
    shutil.copyfile(ROOT / "scripts/scheduling" / script_name, registrar)
    for name in ("run_daily_data_refresh_host.ps1", "market_refresh_host_common.ps1", "monthly_walk_forward.ps1"):
        (scheduling / name).write_text("# synthetic path; never executed\n", encoding="utf-8")
    marker = tmp_path / "resolver-called.txt"
    (scripts / "dev-python.ps1").write_text(
        "function Resolve-DevPython {\n"
        "  [IO.File]::WriteAllText($env:MOSS_TEST_RESOLVER_MARKER, 'called')\n"
        "  throw 'Runtime must not be required for preview or unregister'\n}\n",
        encoding="utf-8",
    )
    calls = tmp_path / "mutation-calls.txt"
    calls.write_text("", encoding="ascii")
    harness = tmp_path / "preview-unregister-harness.ps1"
    harness.write_text(
        """
function schtasks {
  [IO.File]::AppendAllText($env:MOSS_TEST_MUTATION_CALLS, (($args -join '|') + [Environment]::NewLine))
  $global:LASTEXITCODE = 0
}
function Unregister-ScheduledTask {
  param($TaskName, $Confirm)
  [IO.File]::AppendAllText($env:MOSS_TEST_MUTATION_CALLS, ('unregister|' + $TaskName + [Environment]::NewLine))
}
function Register-ScheduledTask { throw 'Unexpected registration API call' }
function Set-ScheduledTask { throw 'Unexpected registration API call' }
function New-ScheduledTaskAction { return @{ synthetic = $true } }
function New-ScheduledTaskTrigger { return @{ synthetic = $true } }
function New-ScheduledTaskSettingsSet { return @{ synthetic = $true } }
function Get-ScheduledTask { return @{ State = 'Disabled' } }
$parameters = @{ RepoRoot = $env:MOSS_TEST_REPO_ROOT }
$parameters[$env:MOSS_TEST_MODE] = $true
& $env:MOSS_TEST_REGISTRAR @parameters
""".lstrip(),
        encoding="utf-8",
    )
    environment = dict(
        os.environ, MOSS_TEST_REGISTRAR=str(registrar), MOSS_TEST_REPO_ROOT=str(tmp_path),
        MOSS_TEST_MODE=mode, MOSS_TEST_RESOLVER_MARKER=str(marker), MOSS_TEST_MUTATION_CALLS=str(calls),
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-File", str(harness)], env=environment,
        capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert not marker.exists()
    observed = calls.read_text(encoding="ascii").splitlines()
    if mode == "WhatIf":
        assert not observed
    elif script_name == "install_data_update_queue.ps1":
        assert observed == ["unregister|MOSS-DataUpdateQueue"]
    else:
        assert observed == [
            "/Query|/TN|MOSS-DailyDataRefresh", "/Delete|/TN|MOSS-DailyDataRefresh|/F",
            "/Query|/TN|MOSS-MonthlyWalkForward", "/Delete|/TN|MOSS-MonthlyWalkForward|/F",
        ]
