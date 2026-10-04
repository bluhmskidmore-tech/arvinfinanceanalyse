from __future__ import annotations

import json
import ctypes
import os
import runpy
import shutil
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "data_update_" + "a" * 32
pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_market_data]


def run_host(
    tmp_path: Path,
    monkeypatch,
    *,
    execute=True,
    preflight_ready=True,
    child_exit=0,
    foreign_listener=False,
    ownership_failure=False,
    recovery_failure=False,
    lose_owner=False,
    keepalive=False,
    completed_request=False,
    running_request=False,
    existing_receipt=False,
    receipt_hardlink=False,
    hanging_worker=False,
    swap_receipt=False,
    invocation_exception=False,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    # Reuse the established isolated Windows process/port fixture. It creates
    # only synthetic process identities; native termination logs fake IDs.
    existing = runpy.run_path(str(ROOT / "tests/test_market_refresh_host_runtime.py"))
    with monkeypatch.context() as patch:
        patch.setattr(
            subprocess,
            "run",
            lambda *a, **k: subprocess.CompletedProcess([], 0, "", ""),
        )
        existing["_run_host_harness"](
            tmp_path, api_running=True, keepalive_running=keepalive
        )
    scheduling = tmp_path / "scripts/scheduling"
    shutil.copyfile(
        ROOT / "scripts/scheduling/run_choice_stock_pit_request_host.ps1",
        scheduling / "run_choice_stock_pit_request_host.ps1",
    )
    if invocation_exception:
        host_copy = scheduling / "run_choice_stock_pit_request_host.ps1"
        host_copy.write_text(
            host_copy.read_text(encoding="utf-8").replace(
                "param([string[]]$Arguments, [int]$TimeoutSeconds = 180)",
                "param([string[]]$Arguments, [int]$TimeoutSeconds = 180)\n"
                "    if ($Arguments[0] -eq '-m') { throw 'synthetic missing terminal code' }",
            ),
            encoding="utf-8",
        )
    fake = tmp_path / "python.cmd"
    original = (
        fake.read_text(encoding="utf-8").replace("%~4", "%~6").replace("%~2", "%~4")
    )
    extra = (
        'if "%~2"=="--timeout-seconds" (\n shift\n shift\n shift\n shift\n)\n'
        'if "%~1"=="-c" (\n'
        ' echo preflight:%~4>>"%CHOICE_TEST_EVENT_LOG%"\n'
        ' if "%CHOICE_PIT_PREFLIGHT_READY%"=="0" exit /b 2\n'
        ' if "%~4"=="after" (\n'
        f'  echo {{"run_id":"{RUN_ID}","workflow":"choice_stock_pit_history","report_date":"2026-05-28","status":"%CHOICE_PIT_FINAL_STATUS%"}}\n'
        " ) else (\n"
        f'  echo {{"run_id":"{RUN_ID}","workflow":"choice_stock_pit_history","report_date":"2026-05-28","status":"{"completed" if completed_request else "running" if running_request else "queued"}","requested_by":"synthetic-local-operator","read_only_ready":true}}\n'
        " )\n exit /b 0\n)\n"
        'if "%~1"=="-m" (\n'
        ' if "%~2" NEQ "backend.app.tasks.data_update_center" exit /b 8\n'
        ' if "%~3" NEQ "--run-id" exit /b 8\n'
        ' if "%MOSS_DATA_UPDATE_PIT_MAINTENANCE_OWNER_TOKEN%"=="" exit /b 8\n'
        ' echo worker:%~4>>"%CHOICE_TEST_EVENT_LOG%"\n'
        ' echo reader:%MOSS_SYSTEM_READ_PUBLICATION_ENABLED%>>"%CHOICE_TEST_EVENT_LOG%"\n'
        + (' del /f /q "%CHOICE_PIT_RECEIPT%" 2>nul\n' if swap_receipt else "")
        + (
            f' "{ROOT / ".venv/Scripts/python.exe"}" "{ROOT / "scripts/scheduling/pit_request_process.py"}" --timeout-seconds 5 -- "{tmp_path / "hung.py"}"\n'
            if hanging_worker
            else ""
        )
        + ' if "%CHOICE_PIT_LOSE_OWNER%"=="1" >"%CHOICE_TEST_MARKER_PATH%" echo {"state":"launch_blocked","reason":"foreign replaced owner","owner_token":"foreign-owner"}\n'
        f" exit /b {child_exit}\n)\n"
    )
    fake.write_text(
        original.replace("@echo off\n", "@echo off\n" + extra), encoding="utf-8"
    )
    receipt_path = tmp_path / "data/logs/pit-host.json"
    if existing_receipt or receipt_hardlink:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        protected = tmp_path / "protected-source.json"
        protected.write_bytes(b"original-protected-bytes")
        if receipt_hardlink:
            os.link(protected, receipt_path)
        else:
            receipt_path.write_bytes(b"original-protected-bytes")
    if hanging_worker:
        (tmp_path / "hung.py").write_text(
            "import os,subprocess,sys,time\n"
            "from pathlib import Path\n"
            "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'])\n"
            f"Path({str(tmp_path / 'owned-pids.json')!r}).write_text(str(os.getpid())+','+str(child.pid))\n"
            "time.sleep(120)\n",
            encoding="utf-8",
        )
    driver = tmp_path / "driver.ps1"
    source = driver.read_text(encoding="utf-8")
    source = source[: source.index("if ($env:CHOICE_TEST_BALANCE_ONLY")]
    if recovery_failure:
        source = source.replace(
            "[pscustomobject]@{StatusCode=200;Content='{}'}",
            "throw 'synthetic API recovery failure'",
        )
        # Fail immediately rather than consuming the production 45-second wait.
        source += "function Start-Sleep { param([int]$Milliseconds) }\n"
        source = source.replace(
            "function Invoke-WebRequest {", "function Invoke-WebRequest {"
        )
        # Reused wait code uses wall-clock deadlines. The short mock timeout is
        # installed in the shared helper by rewriting only the fixture copy.
        host_copy = scheduling / "market_refresh_host_common.ps1"
        host_copy.write_text(
            host_copy.read_text(encoding="utf-8").replace(
                "[int]$TimeoutSeconds = 45", "[int]$TimeoutSeconds = 1"
            ),
            encoding="utf-8",
        )
    source += (
        f"& (Join-Path $PSScriptRoot 'scripts\\scheduling\\run_choice_stock_pit_request_host.ps1') -RunId '{RUN_ID}' "
        + ("-Execute " if execute else "")
        + "-ReceiptPath (Join-Path $PSScriptRoot 'data\\logs\\pit-host.json')\nexit $LASTEXITCODE\n"
    )
    driver.write_text(source, encoding="utf-8")
    env = {
        **os.environ,
        "CHOICE_TEST_EVENT_LOG": str(tmp_path / "lifecycle.log"),
        "CHOICE_TEST_MARKER_PATH": str(
            tmp_path / "tmp-governance/runtime-clean/control/maintenance.json"
        ),
        "CHOICE_TEST_API_RUNNING": "1",
        "CHOICE_TEST_KEEPALIVE_RUNNING": "1" if keepalive else "0",
        "CHOICE_TEST_API_SCRIPT_NAME": "dev-api.ps1",
        "CHOICE_TEST_TERMINATION_RETURN_VALUE": "0",
        "CHOICE_TEST_FOREIGN_LISTENER": "1" if foreign_listener else "0",
        "CHOICE_TEST_OWNERSHIP_FAILURE": "1" if ownership_failure else "0",
        "CHOICE_PIT_PREFLIGHT_READY": "1" if preflight_ready else "0",
        "CHOICE_PIT_FINAL_STATUS": "completed" if child_exit == 0 else "failed",
        "CHOICE_PIT_LOSE_OWNER": "1" if lose_owner else "0",
        "MOSS_SYSTEM_READ_PUBLICATION_ENABLED": "true",
        "CHOICE_PIT_RECEIPT": str(receipt_path),
    }
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(driver),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    log = tmp_path / "lifecycle.log"
    return completed, [
        line.strip() for line in log.read_text(encoding="utf-8").splitlines()
    ] if log.exists() else []


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
def test_prepare_is_read_only_and_does_not_drain(tmp_path, monkeypatch) -> None:
    result, events = run_host(tmp_path, monkeypatch, execute=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"status":  "prepared_only"' in result.stdout
    assert events == ["preflight:before"]


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
def test_invalid_preflight_blocks_before_lease_and_drain(tmp_path, monkeypatch) -> None:
    result, events = run_host(tmp_path, monkeypatch, preflight_ready=False)
    assert result.returncode == 1
    assert events == ["preflight:before"]


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
@pytest.mark.parametrize("child_exit", [0, 7])
def test_exact_worker_runs_after_owned_drain_and_api_is_recovered(
    tmp_path, monkeypatch, child_exit
) -> None:
    result, events = run_host(tmp_path, monkeypatch, child_exit=child_exit)
    assert result.returncode == (0 if child_exit == 0 else 1), (
        result.stdout + result.stderr
    )
    assert (
        events.index("enter")
        < events.index("stop:424245")
        < events.index(f"worker:{RUN_ID}")
        < events.index("leave")
    )
    assert sum(x.startswith("worker:") for x in events) == 1
    assert "refresh" not in events and "balance" not in events
    assert "reader:true" in events
    assert "probe:http://127.0.0.1:7888/health" in events
    assert "probe:http://127.0.0.1:7888/health/ready" in events
    receipt = json.loads(
        (tmp_path / "data/logs/pit-host.json").read_text(encoding="utf-8")
    )
    assert receipt["api_restored"] is True and receipt["lease_released"] is True
    assert "owner_token" not in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
@pytest.mark.parametrize("failure", ["foreign_listener", "ownership_failure"])
def test_foreign_process_or_lease_cannot_start_writer(
    tmp_path, monkeypatch, failure
) -> None:
    result, events = run_host(tmp_path, monkeypatch, **{failure: True})
    assert result.returncode == 1
    assert not any(x.startswith("stop:") or x.startswith("worker:") for x in events)


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
def test_lost_owner_never_releases_foreign_marker_or_recovers(
    tmp_path, monkeypatch
) -> None:
    result, events = run_host(tmp_path, monkeypatch, lose_owner=True)
    assert result.returncode == 1
    assert "leave" not in events
    assert not any(x.startswith("recover-payload:") for x in events)
    assert "foreign-owner" not in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
def test_api_recovery_failure_does_not_fake_completed_runtime(
    tmp_path, monkeypatch
) -> None:
    result, events = run_host(tmp_path, monkeypatch, recovery_failure=True)
    assert result.returncode == 1
    assert f"worker:{RUN_ID}" in events
    receipt = json.loads(
        (tmp_path / "data/logs/pit-host.json").read_text(encoding="utf-8")
    )
    assert receipt["request_status"] == "completed"
    assert receipt["status"] == "failed" and receipt["api_restored"] is False


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
@pytest.mark.parametrize("receipt_hardlink", [False, True])
def test_existing_receipt_or_protected_alias_blocks_before_maintenance(
    tmp_path, monkeypatch, receipt_hardlink
) -> None:
    result, events = run_host(
        tmp_path,
        monkeypatch,
        existing_receipt=not receipt_hardlink,
        receipt_hardlink=receipt_hardlink,
    )
    assert result.returncode == 1
    assert events == ["preflight:before"]
    assert (
        tmp_path / "data/logs/pit-host.json"
    ).read_bytes() == b"original-protected-bytes"
    assert (
        tmp_path / "protected-source.json"
    ).read_bytes() == b"original-protected-bytes"


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
def test_reserved_receipt_cannot_be_replaced_while_worker_runs(
    tmp_path, monkeypatch
) -> None:
    result, events = run_host(tmp_path, monkeypatch, swap_receipt=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "leave" in events
    assert (
        json.loads((tmp_path / "data/logs/pit-host.json").read_text())["status"]
        == "completed"
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
def test_completed_request_never_enters_maintenance_or_worker(
    tmp_path, monkeypatch
) -> None:
    result, events = run_host(tmp_path, monkeypatch, completed_request=True)
    assert result.returncode == 0
    assert '"status":  "already_completed"' in result.stdout
    assert events == ["preflight:before"]
    assert not (tmp_path / "data/logs/pit-host.json").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
def test_real_owned_worker_family_timeout_restores_api(tmp_path, monkeypatch) -> None:
    result, events = run_host(
        tmp_path, monkeypatch, child_exit=124, hanging_worker=True
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "leave" in events
    assert "probe:http://127.0.0.1:7888/health/ready" in events
    pids = [
        int(value) for value in (tmp_path / "owned-pids.json").read_text().split(",")
    ]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    for pid in pids:
        handle = kernel.OpenProcess(0x100000, False, pid)
        if handle:
            try:
                assert kernel.WaitForSingleObject(handle, 0) == 0
            finally:
                kernel.CloseHandle(handle)
    receipt = json.loads((tmp_path / "data/logs/pit-host.json").read_text())
    assert receipt["worker_exit_code"] == 124 and receipt["api_restored"] is True


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
def test_unverified_owned_termination_retains_maintenance(
    tmp_path, monkeypatch
) -> None:
    result, events = run_host(tmp_path, monkeypatch, child_exit=126)
    assert result.returncode == 1
    assert "leave" not in events
    assert not any(value.startswith("recover-payload:") for value in events)
    receipt = json.loads((tmp_path / "data/logs/pit-host.json").read_text())
    assert receipt["recovery_blocked"] == "owned_worker_termination_unverified"
    assert receipt["lease_released"] is False and receipt["api_restored"] is False


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
def test_missing_worker_terminal_code_retains_maintenance(
    tmp_path, monkeypatch
) -> None:
    result, events = run_host(tmp_path, monkeypatch, invocation_exception=True)
    assert result.returncode == 1
    assert "leave" not in events
    assert not any(value.startswith("recover-payload:") for value in events)
    receipt = json.loads((tmp_path / "data/logs/pit-host.json").read_text())
    assert receipt["recovery_blocked"] == "owned_worker_termination_unverified"
    assert receipt["lease_released"] is False


def test_process_cleanup_failure_has_distinct_exit_code(monkeypatch) -> None:
    from scripts.scheduling import pit_request_process

    def cleanup_failed(*arguments):
        raise pit_request_process.ContainmentUnverified("synthetic cleanup failure")

    monkeypatch.setattr(pit_request_process, "run_bounded", cleanup_failed)
    monkeypatch.setattr(
        "sys.argv",
        ["pit_request_process.py", "--timeout-seconds", "1", "--", "-c", "pass"],
    )
    assert pit_request_process.main() == 126


@pytest.mark.parametrize("valid_receipt", [False, True])
def test_running_preflight_requires_exact_receipt_without_replanning(
    monkeypatch, capsys, valid_receipt
) -> None:
    source = (
        ROOT / "scripts/scheduling/run_choice_stock_pit_request_host.ps1"
    ).read_text(encoding="utf-8")
    code = source.split("$code = @'\n", 1)[1].split("\n'@", 1)[0]
    run = {
        "run_id": RUN_ID,
        "workflow": "choice_stock_pit_history",
        "report_date": "2026-05-28",
        "status": "running",
        "target_duckdb_path": str(ROOT / "data/moss.duckdb"),
    }
    calls = []

    def recover(settings, actual_run):
        assert actual_run is run
        calls.append("recover_exact_receipt")
        if not valid_receipt:
            raise ValueError("Missing or mismatched committed receipt")
        return {"status": "completed"}

    def replan(*arguments, **keywords):
        pytest.fail("Running recovery must not recompute the pre-import plan")

    replacements = {
        "backend.app.governance.settings": SimpleNamespace(
            get_settings=lambda: SimpleNamespace(
                governance_path=ROOT, duckdb_path=run["target_duckdb_path"]
            )
        ),
        "backend.app.repositories.data_update_repo": SimpleNamespace(
            latest_runs=lambda path: [run]
        ),
        "backend.app.services.data_update_service": SimpleNamespace(
            choice_stock_pit_preflight=replan
        ),
        "backend.app.tasks.data_update_choice_stock_pit": SimpleNamespace(
            recover_choice_stock_pit_result=recover
        ),
    }
    for module, value in replacements.items():
        monkeypatch.setitem(sys.modules, module, value)
    monkeypatch.setattr(sys, "argv", ["preflight", RUN_ID, "before"])
    if valid_receipt:
        exec(code, {})
        assert json.loads(capsys.readouterr().out)["status"] == "running"
    else:
        with pytest.raises(ValueError, match="Missing or mismatched"):
            exec(code, {})
    assert calls == ["recover_exact_receipt"]


@pytest.mark.skipif(os.name != "nt", reason="Windows maintenance host")
def test_verified_running_receipt_uses_owned_scoped_worker(
    tmp_path, monkeypatch
) -> None:
    result, events = run_host(tmp_path, monkeypatch, running_request=True)
    assert result.returncode == 0
    assert (
        events.index("stop:424245")
        < events.index(f"worker:{RUN_ID}")
        < events.index("leave")
    )
