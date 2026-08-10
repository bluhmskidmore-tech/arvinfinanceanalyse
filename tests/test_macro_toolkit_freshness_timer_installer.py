from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_macro_toolkit_freshness_timer.ps1"


def test_installer_writes_scheduled_receipt_flags() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert "--run-once" in text
    assert "--run-kind scheduled" in text
    assert "macro_toolkit_freshness_refresh_receipt.json" in text
    assert "06:30" in text
    assert "post-enable" in text
    assert "schtasks /Create" in text


def test_installer_can_persist_explicit_choice_source_ip() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert '[string]$ChoiceSourceIp = ""' in text
    assert "--choice-source-ip" in text
    assert "ChoiceSourceIp" in text
    assert "[System.Net.IPAddress]::Parse" in text
    assert "AddressFamily]::InterNetwork" in text


def test_installer_propagates_refresh_failure_exit_code() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert "setlocal EnableExtensions EnableDelayedExpansion" in text
    assert 'set "refreshExit=!ERRORLEVEL!"' in text
    assert 'if not "!refreshExit!"=="0" echo ALERT' in text
    assert "exit /b !refreshExit!" in text


def test_installer_allows_laptop_execution_and_catchup() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert "-AllowStartIfOnBatteries" in text
    assert "-DontStopIfGoingOnBatteries" in text
    assert "-StartWhenAvailable" in text


def test_installer_runs_wrapper_without_an_interactive_console() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert "New-ScheduledTaskAction" in text
    assert "WindowsPowerShell\\v1.0\\powershell.exe" in text
    assert "-NonInteractive -WindowStyle Hidden" in text
    assert "exit `$LASTEXITCODE" in text
    assert "-WorkingDirectory $RepoRoot" in text
    assert "-Action $taskAction -Settings $taskSettings" in text
