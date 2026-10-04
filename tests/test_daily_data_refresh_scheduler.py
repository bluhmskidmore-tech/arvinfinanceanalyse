from __future__ import annotations

import os
import shutil
import subprocess
import sys
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "scheduling" / "daily_data_refresh.ps1"
HOST_SCRIPT = ROOT / "scripts" / "scheduling" / "run_daily_data_refresh_host.ps1"

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]


def _write_fake_python(exe_path: Path) -> None:
    exe_path.write_text(
        "@echo off\n"
        "setlocal EnableExtensions EnableDelayedExpansion\n"
        f"set \"PYTHONPATH={ROOT};%PYTHONPATH%\"\n"
        "if \"%MOSS_SYSTEM_READ_PUBLICATION_ENABLED%\"==\"\" set \"MOSS_SYSTEM_READ_PUBLICATION_ENABLED=false\"\n"
        "if /I \"%~1\"==\"-m\" if /I \"%~2\"==\"backend.app.tasks.system_read_market_publication\" (\n"
        "  if not \"%DAILY_CHAIN_CONTROL_LOG%\"==\"\" echo %~3>>\"%DAILY_CHAIN_CONTROL_LOG%\"\n"
        f"  \"{sys.executable}\" %*\n"
        "  exit /b !errorlevel!\n"
        ")\n"
        "set \"CALL_LOG=%DAILY_CHAIN_CALL_LOG%\"\n"
        "set \"STEP_NAME=%~nx1\"\n"
        "if /I \"%~1\"==\"-m\" set \"STEP_NAME=%~2\"\n"
        "if not \"%CALL_LOG%\"==\"\" echo %STEP_NAME%>>\"%CALL_LOG%\"\n"
        "if /I \"%STEP_NAME%\"==\"%FAKE_FAIL_STEP%\" exit /b 7\n"
        "if /I \"%STEP_NAME%\"==\"choice_stock_daily_refresh.py\" if \"%FAKE_CHOICE_NON_TRADING%\"==\"1\" (\n"
        "  echo {\"status\":\"skipped_non_trading_day\",\"as_of_date\":\"%FAKE_REPORT_DATE%\",\"as_of_date_explicit\":false,\"no_write\":true,\"database_write_scope\":[],\"governance_write_scope\":[]}\n"
        "  exit /b 0\n"
        ")\n"
        "echo {\"status\":\"completed\"}\n"
        "exit /b 0\n",
        encoding="utf-8",
    )


def _prepare_script_copy(tmp_path: Path) -> Path:
    script_copy = tmp_path / "scripts" / "scheduling" / "daily_data_refresh.ps1"
    script_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SCRIPT, script_copy)
    return script_copy


def _run_powershell(
    script_path: Path,
    *args: str,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
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
        env=env,
        stdin=subprocess.DEVNULL,
    )


def test_daily_data_refresh_runs_factor_between_choice_and_pretrade(tmp_path: Path) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    call_log = tmp_path / "calls.log"
    _write_fake_python(fake_python)

    completed = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AsOfDate",
        "2026-08-11",
        "-IgnoreExistingTimers",
        env_overrides={"DAILY_CHAIN_CALL_LOG": str(call_log)},
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "choice_stock_daily_refresh.py",
        "stock_adjustment_factor_daily_refresh.py",
        "backend.app.tasks.stock_limit_price_daily_refresh",
        "macro_toolkit_freshness_refresh.py",
        "run_livermore_daily_pretrade_refresh.py",
        "refresh_tushare_news_backup.py",
        "macro_toolkit_daily_chain.py",
    ]
    assert "--db-path" not in completed.stdout
    assert "-m backend.app.tasks.stock_limit_price_daily_refresh" in completed.stdout
    assert "--duckdb-path" not in completed.stdout
    assert "--run-once" in completed.stdout
    assert "--as-of-date 2026-08-11" in completed.stdout
    assert "--run-kind scheduled" in completed.stdout
    assert "stock_adjustment_factor_daily_refresh_market-daily_2026-08-11_" in completed.stdout
    assert "--trade-date 2026-08-11" not in completed.stdout


@pytest.mark.parametrize("script_name", ["daily_data_refresh.ps1", "monthly_walk_forward.ps1"])
def test_scheduled_entry_defers_database_selection_to_configured_cli(tmp_path: Path, script_name: str) -> None:
    script_path = tmp_path / "scripts" / "scheduling" / script_name
    script_path.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts" / "scheduling" / script_name, script_path)
    fake_python = tmp_path / "fake-python.cmd"
    _write_fake_python(fake_python)

    completed = _run_powershell(
        script_path, "-RepoRoot", str(tmp_path), "-PythonExe", str(fake_python), "-DryRun",
        env_overrides={"MOSS_DUCKDB_PATH": str(tmp_path / "external storage" / "moss.duckdb")},
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "--db-path" not in completed.stdout
    assert "--duckdb-path" not in completed.stdout
    assert not (tmp_path / "data" / "moss.duckdb").exists()


@pytest.mark.parametrize("script_name", ["daily_data_refresh.ps1", "monthly_walk_forward.ps1"])
def test_scheduled_entry_uses_shared_project_python_default(tmp_path: Path, script_name: str) -> None:
    script_path = tmp_path / "scripts" / "scheduling" / script_name
    script_path.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts" / "scheduling" / script_name, script_path)
    selected = tmp_path / "backend" / ".venv" / "Scripts" / "python.exe"
    legacy = tmp_path / ".venv" / "Scripts" / "python.exe"
    for candidate in (selected, legacy):
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(b"dry-run sentinel, never execute")
    (tmp_path / "scripts" / "dev-python.ps1").write_text(
        "function Resolve-DevPython { param([object]$RequiredModules) return $env:TEST_DEFAULT_SCHEDULER_PYTHON }\n",
        encoding="utf-8",
    )

    completed = _run_powershell(
        script_path, "-RepoRoot", str(tmp_path), "-DryRun",
        env_overrides={"TEST_DEFAULT_SCHEDULER_PYTHON": str(selected)},
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert str(selected) in completed.stdout
    assert str(legacy) not in completed.stdout


def test_daily_data_refresh_does_not_bypass_factor_when_choice_timer_exists(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    _write_fake_python(fake_python)
    harness_path = tmp_path / "harness.ps1"
    harness_path.write_text(
        f"""
function Get-ScheduledTask {{
    param([string]$TaskName)
    if ($TaskName -eq "MOSS-ChoiceStockDailyRefresh") {{
        return [pscustomobject]@{{ State = "Ready" }}
    }}
    throw "task not found"
}}
& "{script_path}" -RepoRoot "{tmp_path}" -PythonExe "{fake_python}" -AsOfDate "2026-08-11" -DryRun
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
            str(harness_path),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "choice_stock_daily_refresh" in completed.stdout
    assert "stock_adjustment_factor_daily_refresh.py" in completed.stdout
    assert "backend.app.tasks.stock_limit_price_daily_refresh" in completed.stdout
    assert "run_livermore_daily_pretrade_refresh.py" in completed.stdout
    assert "--run-once" in completed.stdout
    assert "--as-of-date 2026-08-11" in completed.stdout
    assert "--run-kind scheduled" in completed.stdout
    assert "stock_adjustment_factor_daily_refresh_market-daily_2026-08-11_" in completed.stdout
    assert "--trade-date 2026-08-11" not in completed.stdout
    assert "covered by enabled scheduled task 'MOSS-ChoiceStockDailyRefresh'" in completed.stdout


def test_daily_data_refresh_fails_closed_when_choice_is_owned_by_legacy_timer(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    call_log = tmp_path / "calls.log"
    aggregate_path = tmp_path / "aggregate-critical.json"
    _write_fake_python(fake_python)
    harness_path = tmp_path / "harness.ps1"
    harness_path.write_text(
        f"""
function Get-ScheduledTask {{
    param([string]$TaskName)
    if ($TaskName -eq "MOSS-ChoiceStockDailyRefresh") {{
        return [pscustomobject]@{{ State = "Ready" }}
    }}
    throw "task not found"
}}
& "{script_path}" -RepoRoot "{tmp_path}" -PythonExe "{fake_python}" -AsOfDate "2026-08-11" -AggregateRunId "market-daily:2026-08-11:critical" -AggregateReceiptPath "{aggregate_path}"
exit $LASTEXITCODE
""".strip(),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["DAILY_CHAIN_CALL_LOG"] = str(call_log)

    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness_path),
        ],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
    )

    assert completed.returncode == 2, completed.stderr or completed.stdout
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "macro_toolkit_freshness_refresh.py",
        "refresh_tushare_news_backup.py",
        "macro_toolkit_daily_chain.py",
    ]
    assert "cannot verify completion of legacy timer" in completed.stdout
    assert "skipped_upstream_unverified" in completed.stdout
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    assert aggregate["status"] == "business_failed"
    assert len(aggregate["children"]) == 7


def test_daily_data_refresh_factor_failure_blocks_pretrade_and_returns_nonzero(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    call_log = tmp_path / "calls.log"
    aggregate_path = tmp_path / "aggregate-partial.json"
    _write_fake_python(fake_python)

    completed = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AsOfDate",
        "2026-08-11",
        "-IgnoreExistingTimers",
        "-AggregateRunId",
        "market-daily:2026-08-11:partial",
        "-AggregateReceiptPath",
        str(aggregate_path),
        env_overrides={
            "DAILY_CHAIN_CALL_LOG": str(call_log),
            "FAKE_FAIL_STEP": "stock_adjustment_factor_daily_refresh.py",
        },
    )

    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert completed.returncode == 1, completed.stderr or completed.stdout
    assert calls == [
        "choice_stock_daily_refresh.py",
        "stock_adjustment_factor_daily_refresh.py",
        "macro_toolkit_freshness_refresh.py",
        "refresh_tushare_news_backup.py",
        "macro_toolkit_daily_chain.py",
    ]
    assert "SKIP: upstream step 'stock_adjustment_factor_daily_refresh' failed" in completed.stdout
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    assert aggregate["status"] == "business_failed"
    assert len(aggregate["children"]) == 7


def test_daily_data_refresh_limit_price_failure_blocks_pretrade_and_returns_nonzero(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    call_log = tmp_path / "calls.log"
    _write_fake_python(fake_python)

    completed = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AsOfDate",
        "2026-08-11",
        "-IgnoreExistingTimers",
        env_overrides={
            "DAILY_CHAIN_CALL_LOG": str(call_log),
            "FAKE_FAIL_STEP": "backend.app.tasks.stock_limit_price_daily_refresh",
        },
    )

    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert completed.returncode == 1, completed.stderr or completed.stdout
    assert calls == [
        "choice_stock_daily_refresh.py",
        "stock_adjustment_factor_daily_refresh.py",
        "backend.app.tasks.stock_limit_price_daily_refresh",
        "macro_toolkit_freshness_refresh.py",
        "refresh_tushare_news_backup.py",
        "macro_toolkit_daily_chain.py",
    ]
    assert "SKIP: upstream step 'stock_limit_price_daily_refresh' failed" in completed.stdout


def test_macro_freshness_failure_blocks_pretrade_but_not_independent_writers(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    call_log = tmp_path / "calls.log"
    aggregate_path = tmp_path / "aggregate-freshness-failed.json"
    _write_fake_python(fake_python)

    completed = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AsOfDate",
        "2026-08-11",
        "-IgnoreExistingTimers",
        "-AggregateRunId",
        "market-daily:2026-08-11:freshness-failed",
        "-AggregateReceiptPath",
        str(aggregate_path),
        env_overrides={
            "DAILY_CHAIN_CALL_LOG": str(call_log),
            "FAKE_FAIL_STEP": "macro_toolkit_freshness_refresh.py",
        },
    )

    calls = call_log.read_text(encoding="utf-8").splitlines()
    assert completed.returncode == 1, completed.stderr or completed.stdout
    assert calls == [
        "choice_stock_daily_refresh.py",
        "stock_adjustment_factor_daily_refresh.py",
        "backend.app.tasks.stock_limit_price_daily_refresh",
        "macro_toolkit_freshness_refresh.py",
        "refresh_tushare_news_backup.py",
        "macro_toolkit_daily_chain.py",
    ]
    assert "SKIP: upstream step 'macro_toolkit_freshness' failed" in completed.stdout
    assert json.loads(aggregate_path.read_text(encoding="utf-8"))["status"] == "business_failed"


def test_active_publication_rejects_historical_date_before_any_child_runs(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    call_log = tmp_path / "calls.log"
    _write_fake_python(fake_python)

    completed = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AsOfDate",
        "2026-08-11",
        "-IgnoreExistingTimers",
        env_overrides={
            "DAILY_CHAIN_CALL_LOG": str(call_log),
            "MOSS_SYSTEM_READ_PUBLICATION_ENABLED": "true",
        },
    )

    assert completed.returncode != 0
    assert "Historical AsOfDate cannot run the undated macro freshness writer" in (
        completed.stderr + completed.stdout
    )
    assert not call_log.exists()


def test_daily_data_refresh_passes_vendor_source_ip_to_tushare_and_other_vendor_steps(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    call_log = tmp_path / "calls.log"
    _write_fake_python(fake_python)

    completed = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AsOfDate",
        "2026-08-11",
        "-VendorSourceIp",
        "10.0.0.9",
        "-IgnoreExistingTimers",
        env_overrides={"DAILY_CHAIN_CALL_LOG": str(call_log)},
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert call_log.read_text(encoding="utf-8").splitlines()[:3] == [
        "choice_stock_daily_refresh.py",
        "stock_adjustment_factor_daily_refresh.py",
        "backend.app.tasks.stock_limit_price_daily_refresh",
    ]
    assert completed.stdout.count("--vendor-source-ip 10.0.0.9") == 5
    assert completed.stdout.count("--source-ip 10.0.0.9") == 1


def test_daily_data_refresh_can_enable_single_day_tushare_stock_gap_repair(tmp_path: Path) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    _write_fake_python(fake_python)

    completed = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AsOfDate",
        "2026-09-04",
        "-TushareStockGapRepair",
        "-IgnoreExistingTimers",
        "-DryRun",
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    choice_line = next(
        line
        for line in completed.stdout.splitlines()
        if "choice_stock_daily_refresh.py" in line and "command:" in line
    )
    assert "--tushare-gap-repair" in choice_line
    assert "--history-start-date" not in choice_line


def test_publication_only_recovery_uses_exact_run_without_business_children(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    call_log = tmp_path / "calls.log"
    control_log = tmp_path / "control.log"
    receipt_path = tmp_path / "aggregate.json"
    run_id = "market-daily:2026-09-15:recovery"
    _write_fake_python(fake_python)
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": "market-daily-aggregate/v1",
                "run_id": run_id,
                "workflow": "market_daily",
                "report_date": "2026-09-15",
                "status": "business_completed",
                "children": [],
            }
        ),
        encoding="utf-8",
    )

    completed = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AsOfDate",
        "2026-09-15",
        "-PublicationOnly",
        "-AggregateRunId",
        run_id,
        "-AggregateReceiptPath",
        str(receipt_path),
        env_overrides={
            "DAILY_CHAIN_CALL_LOG": str(call_log),
            "DAILY_CHAIN_CONTROL_LOG": str(control_log),
            "MOSS_SYSTEM_READ_PUBLICATION_ENABLED": "false",
        },
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert not call_log.exists()
    assert control_log.read_text(encoding="utf-8").splitlines() == ["recover"]
    assert "business children were not run" in completed.stdout


def test_late_choice_warning_blocks_publication_at_actual_scheduler_boundary(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    control_log = tmp_path / "control.log"
    call_log = tmp_path / "calls.log"
    aggregate_path = tmp_path / "aggregate.json"
    report_date = datetime.now().date().isoformat()
    run_id = f"market-daily:{report_date}:late"
    _write_fake_python(fake_python)
    receipt_dir = tmp_path / "data" / "logs"
    receipt_dir.mkdir(parents=True)
    choice_receipt = receipt_dir / f"choice_stock_daily_refresh_market-daily_{report_date}_late.json"
    choice_result = {
        "status": "success",
        "as_of_date": report_date,
        "history_start_date": report_date,
        "refresh": {
            "status": "completed",
            "report_date": report_date,
            "run_id": "choice-child",
            "cache_key": "choice-stock:daily",
            "theme_overlay_mode": "archive",
            "theme_overlay_status": "completed",
        },
        "gate_supplement": {"status": "completed"},
        "position_snapshot_rollforward": {"status": "failed"},
    }
    choice_receipt.write_text(
        json.dumps(
                {
                    "status": "success",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "result": choice_result,
                "warnings": ["position snapshot roll-forward failed"],
            }
        ),
        encoding="utf-8",
    )

    completed = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AsOfDate",
        report_date,
        "-AggregateRunId",
        run_id,
        "-AggregateReceiptPath",
        str(aggregate_path),
        "-IgnoreExistingTimers",
        env_overrides={
            "DAILY_CHAIN_CALL_LOG": str(call_log),
            "DAILY_CHAIN_CONTROL_LOG": str(control_log),
            "MOSS_SYSTEM_READ_PUBLICATION_ENABLED": "true",
            "MOSS_FINANCIAL_PUBLICATION_ROOT": str(tmp_path / "publications"),
            "MOSS_DUCKDB_PATH": str(tmp_path / "data" / "moss.duckdb"),
        },
    )

    assert completed.returncode == 1, completed.stderr or completed.stdout
    controls = control_log.read_text(encoding="utf-8").splitlines()
    assert controls[-2:] == ["complete-business", "fail-aggregate"]
    assert "publish" not in controls
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    assert aggregate["status"] == "qualification_failed"
    assert len(aggregate["children"]) == 7
    choice_child = next(
        child
        for child in aggregate["children"]
        if child["name"] == "choice_stock_daily_refresh"
    )
    assert choice_child["external_receipt"]["warnings"] == [
        "position snapshot roll-forward failed"
    ]
    assert choice_child["result"]["position_snapshot_rollforward"]["status"] == "failed"

    recovery = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AsOfDate",
        report_date,
        "-PublicationOnly",
        "-AggregateRunId",
        run_id,
        "-AggregateReceiptPath",
        str(aggregate_path),
        env_overrides={
            "DAILY_CHAIN_CALL_LOG": str(call_log),
            "DAILY_CHAIN_CONTROL_LOG": str(control_log),
            "MOSS_SYSTEM_READ_PUBLICATION_ENABLED": "false",
        },
    )

    assert recovery.returncode == 1
    assert json.loads(aggregate_path.read_text(encoding="utf-8"))["status"] == "qualification_failed"
    assert control_log.read_text(encoding="utf-8").splitlines()[-1] == "recover"


def test_default_date_choice_no_write_records_causal_skips_and_runs_independent_steps(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    fake_python = tmp_path / "fake-python.cmd"
    call_log = tmp_path / "calls.log"
    aggregate_path = tmp_path / "aggregate-weekend.json"
    _write_fake_python(fake_python)
    report_date = datetime.now().date().isoformat()
    run_id = f"market-daily:{report_date}:weekend-shape"

    completed = _run_powershell(
        script_path,
        "-RepoRoot",
        str(tmp_path),
        "-PythonExe",
        str(fake_python),
        "-AggregateRunId",
        run_id,
        "-AggregateReceiptPath",
        str(aggregate_path),
        "-IgnoreExistingTimers",
        env_overrides={
            "DAILY_CHAIN_CALL_LOG": str(call_log),
            "FAKE_CHOICE_NON_TRADING": "1",
            "FAKE_REPORT_DATE": report_date,
            "MOSS_SYSTEM_READ_PUBLICATION_ENABLED": "false",
        },
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "--as-of-date" not in completed.stdout
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "choice_stock_daily_refresh.py",
        "macro_toolkit_freshness_refresh.py",
        "refresh_tushare_news_backup.py",
        "macro_toolkit_daily_chain.py",
    ]
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    children = {item["name"]: item for item in aggregate["children"]}
    assert children["choice_stock_daily_refresh"]["result"]["no_write"] is True
    for child_name, upstream_name in {
        "stock_adjustment_factor_daily_refresh": "choice_stock_daily_refresh",
        "stock_limit_price_daily_refresh": "stock_adjustment_factor_daily_refresh",
        "livermore_pretrade_candidates": "stock_limit_price_daily_refresh",
    }.items():
        child = children[child_name]
        upstream = children[upstream_name]
        assert child["status"] == "not_executed"
        assert child["result"]["aggregate_run_id"] == run_id
        assert child["result"]["upstream_child_run_id"] == upstream["run_id"]
        assert child["result"]["no_write"] is True


def test_host_wrapper_routes_publication_only_before_network_discovery() -> None:
    script = HOST_SCRIPT.read_text(encoding="utf-8")

    assert script.index("if ($PublicationOnly)") < script.index('market_refresh_host_common.ps1')
    assert "AggregateRunId = $AggregateRunId" in script
    assert "AggregateReceiptPath = $AggregateReceiptPath" in script


def test_host_wrapper_publication_only_recovery_never_discovers_network(
    tmp_path: Path,
) -> None:
    script_path = _prepare_script_copy(tmp_path)
    host_copy = script_path.parent / "run_daily_data_refresh_host.ps1"
    shutil.copyfile(HOST_SCRIPT, host_copy)
    fake_python = tmp_path / "fake-python.cmd"
    _write_fake_python(fake_python)
    receipt_path = tmp_path / "aggregate.json"
    run_id = "market-daily:2026-09-15:host-recovery"
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": "market-daily-aggregate/v1",
                "run_id": run_id,
                "workflow": "market_daily",
                "report_date": "2026-09-15",
                "status": "business_completed",
                "children": [],
            }
        ),
        encoding="utf-8",
    )
    harness = tmp_path / "host-recovery-harness.ps1"
    harness.write_text(
        f"""
function Get-NetIPConfiguration {{ throw "network discovery must not run" }}
function Get-NetIPAddress {{ throw "network address lookup must not run" }}
& "{host_copy}" -PublicationOnly -AsOfDate "2026-09-15" -AggregateRunId "{run_id}" -AggregateReceiptPath "{receipt_path}" -PythonExe "{fake_python}"
exit $LASTEXITCODE
""".strip(),
        encoding="utf-8",
    )

    completed = _run_powershell(
        harness,
        env_overrides={"MOSS_SYSTEM_READ_PUBLICATION_ENABLED": "false"},
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "business children were not run" in completed.stdout
    assert "network discovery must not run" not in completed.stdout
