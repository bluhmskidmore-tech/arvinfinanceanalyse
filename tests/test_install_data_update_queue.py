from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "scheduling" / "install_data_update_queue.ps1"
LAUNCHER = ROOT / "scripts" / "scheduling" / "drain_data_updates.ps1"


def _powershell() -> str:
    executable = shutil.which("powershell.exe") or shutil.which("powershell")
    if executable is None:
        pytest.skip("Windows PowerShell is required for this scheduler test")
    return executable


def _stage_repo(
    tmp_path: Path, *, python_layout: str | None, include_launcher: bool = True
) -> tuple[Path, Path]:
    repo = tmp_path / "repo with spaces"
    scheduling = repo / "scripts" / "scheduling"
    scheduling.mkdir(parents=True)
    installer = scheduling / INSTALLER.name
    installer.write_bytes(INSTALLER.read_bytes())
    if include_launcher:
        (scheduling / LAUNCHER.name).write_bytes(LAUNCHER.read_bytes())
    if python_layout is not None:
        python_dir = repo / python_layout / "Scripts"
        python_dir.mkdir(parents=True)
        (python_dir / "python.exe").write_bytes(b"")
    return repo, installer


def _run_harness(
    tmp_path: Path,
    *,
    python_layout: str | None,
    unregister: bool = False,
    include_launcher: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    repo, installer = _stage_repo(
        tmp_path, python_layout=python_layout, include_launcher=include_launcher
    )
    action_path = tmp_path / "action.json"
    trigger_path = tmp_path / "trigger.json"
    unregister_path = tmp_path / "unregister.txt"
    harness = tmp_path / "scheduler-harness.ps1"
    harness.write_text(
        """
function New-ScheduledTaskAction {
  param($Execute, $Argument, $WorkingDirectory)
  $payload = @{ execute = $Execute; argument = $Argument; working_directory = $WorkingDirectory } | ConvertTo-Json -Compress
  [IO.File]::WriteAllText($env:TEST_ACTION_PATH, $payload, [Text.UTF8Encoding]::new($false))
  return [pscustomobject]@{}
}
function New-ScheduledTaskTrigger {
  param([switch]$Once, [datetime]$At, [timespan]$RepetitionInterval)
  $payload = @{ once = [bool]$Once; interval_minutes = $RepetitionInterval.TotalMinutes } | ConvertTo-Json -Compress
  [IO.File]::WriteAllText($env:TEST_TRIGGER_PATH, $payload, [Text.UTF8Encoding]::new($false))
  return [pscustomobject]@{}
}
function New-ScheduledTaskSettingsSet {
  param([switch]$StartWhenAvailable, [switch]$AllowStartIfOnBatteries,
    [switch]$DontStopIfGoingOnBatteries, $MultipleInstances, [timespan]$ExecutionTimeLimit)
  return [pscustomobject]@{}
}
function Register-ScheduledTask { throw "real task registration must not run" }
function Unregister-ScheduledTask {
  param($TaskName, [switch]$Confirm)
  [IO.File]::WriteAllText($env:TEST_UNREGISTER_PATH, $TaskName, [Text.UTF8Encoding]::new($false))
}
if ($env:TEST_UNREGISTER -eq "1") {
  & $env:TEST_INSTALLER -RepoRoot $env:TEST_REPO -Unregister
} else {
  & $env:TEST_INSTALLER -RepoRoot $env:TEST_REPO -WhatIf
}
if (-not $?) { exit 1 }
""".lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    env = {
        **os.environ,
        "TEST_REPO": str(repo),
        "TEST_INSTALLER": str(installer),
        "TEST_ACTION_PATH": str(action_path),
        "TEST_TRIGGER_PATH": str(trigger_path),
        "TEST_UNREGISTER_PATH": str(unregister_path),
        "TEST_UNREGISTER": "1" if unregister else "0",
    }
    completed = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )
    return completed, action_path, trigger_path


@pytest.mark.parametrize("python_layout", [".venv", "backend/.venv"])
def test_installer_dry_run_resolves_python_layout_and_preserves_task_contract(
    tmp_path: Path, python_layout: str
) -> None:
    completed, action_path, trigger_path = _run_harness(
        tmp_path, python_layout=python_layout
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    action = json.loads(action_path.read_text(encoding="utf-8"))
    trigger = json.loads(trigger_path.read_text(encoding="utf-8"))
    repo = tmp_path / "repo with spaces"
    assert action["working_directory"] == str(repo)
    launcher = repo / "scripts" / "scheduling" / "drain_data_updates.ps1"
    assert f'-File "{launcher}"' in action["argument"]
    assert "-WindowStyle Hidden" in action["argument"]
    assert trigger == {"once": True, "interval_minutes": 5}
    assert "MOSS-DataUpdateQueue" in completed.stdout
    assert not (tmp_path / "unregister.txt").exists()


def test_uninstall_does_not_require_python_environment(tmp_path: Path) -> None:
    completed, action_path, trigger_path = _run_harness(
        tmp_path, python_layout=None, unregister=True
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert (tmp_path / "unregister.txt").read_text(
        encoding="utf-8"
    ) == "MOSS-DataUpdateQueue"
    assert not action_path.exists()
    assert not trigger_path.exists()


def test_install_rejects_missing_python_before_creating_action(tmp_path: Path) -> None:
    completed, action_path, trigger_path = _run_harness(tmp_path, python_layout=None)

    assert completed.returncode != 0
    assert "Repository Python not found" in (completed.stderr or completed.stdout)
    assert not action_path.exists()
    assert not trigger_path.exists()


def test_install_rejects_missing_launcher_before_creating_action(
    tmp_path: Path,
) -> None:
    completed, action_path, trigger_path = _run_harness(
        tmp_path, python_layout=".venv", include_launcher=False
    )

    assert completed.returncode != 0
    assert "Data update queue launcher not found" in (
        completed.stderr or completed.stdout
    )
    assert not action_path.exists()
    assert not trigger_path.exists()
