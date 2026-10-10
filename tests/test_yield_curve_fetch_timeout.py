from __future__ import annotations

import importlib
import io
import json
import os
import runpy
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from time import perf_counter, sleep
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def fetch_module():
    return importlib.import_module("backend.app.tasks.yield_curve_fetch")


@pytest.fixture
def task_module():
    return importlib.import_module("backend.app.tasks.yield_curve_materialize")


def _snapshot_payload(*, curve_type="treasury", trade_date="2026-08-31"):
    return {
        "curve_type": curve_type,
        "trade_date": trade_date,
        "points": [{"tenor": "1Y", "rate_pct": "1.234567890123456789"}],
        "vendor_name": "test_vendor",
        "vendor_version": "vv_test",
        "source_version": "sv_test",
    }


def _fetch(fetch_module, **overrides):
    arguments = {
        "curve_type": "treasury",
        "anchor_date": "2026-08-31",
        "max_backtrack_days": 3,
        "timeout_seconds": 5.0,
    }
    return fetch_module.fetch_curve_snapshot_with_timeout(**{**arguments, **overrides})


def _mock_process_result(fetch_module, monkeypatch, payload, *, returncode=0, raw=False, missing=False):
    process = SimpleNamespace(returncode=returncode, stdin=None)

    def launch(command, **_kwargs):
        def communicate(**_arguments):
            if not missing:
                Path(command[-1]).write_text(payload if raw else json.dumps(payload), encoding="utf-8")
            return None, None

        process.communicate = Mock(side_effect=communicate)
        return process

    popen = Mock(side_effect=launch)
    monkeypatch.setattr(fetch_module.subprocess, "Popen", popen)
    return popen, process


def _mock_repository(task_module, monkeypatch):
    repository = SimpleNamespace(fetch_curve_snapshot=Mock(return_value=None), replace_curve_snapshots=Mock())
    monkeypatch.setattr(task_module, "YieldCurveRepository", lambda _path: repository)
    monkeypatch.setattr(task_module, "VendorAdapter", Mock(side_effect=AssertionError("parent vendor constructed")))
    monkeypatch.setattr(
        task_module, "_fetch_curve_snapshot_on_or_before", Mock(side_effect=AssertionError("unbounded inline fetch"))
    )
    return repository


def test_process_response_preserves_decimal_date_and_lineage(fetch_module, monkeypatch):
    payload = _snapshot_payload(trade_date="2026-08-28")
    popen, process = _mock_process_result(fetch_module, monkeypatch, payload)

    snapshot = _fetch(fetch_module)

    assert snapshot.points[0].rate_pct == Decimal("1.234567890123456789")
    assert snapshot.trade_date == "2026-08-28"
    assert (snapshot.vendor_name, snapshot.vendor_version, snapshot.source_version) == ("test_vendor", "vv_test", "sv_test")
    command = popen.call_args.args[0]
    arguments = popen.call_args.kwargs
    assert command[:4] == [sys.executable, "-m", "backend.app.tasks.yield_curve_fetch", "--result-path"]
    assert arguments["cwd"] == str(fetch_module._REPO_ROOT)
    assert arguments.get("shell", False) is False
    assert arguments["encoding"] == "utf-8"
    assert arguments["stdout"] == subprocess.DEVNULL
    assert arguments["stderr"] == subprocess.DEVNULL
    assert process.communicate.call_args.kwargs["timeout"] == 5.0
    assert json.loads(process.communicate.call_args.kwargs["input"]) == {
        "curve_type": "treasury", "anchor_date": "2026-08-31", "max_backtrack_days": 3
    }
    if os.name == "nt":
        assert arguments["creationflags"] & subprocess.CREATE_NO_WINDOW


@pytest.mark.parametrize(
    "change",
    [
        {"curve_type": "cdb"},
        {"trade_date": "2026-09-01"},
        {"trade_date": "2026-08-27"},
        {"trade_date": "invalid"},
        {"points": [{"tenor": "1Y", "rate_pct": "not-a-number"}]},
        {"points": "malformed"},
        {"vendor_version": ""},
        {"source_version": " "},
        {"vendor_name": ""},
    ],
)
def test_process_response_rejects_wrong_family_date_or_model(fetch_module, monkeypatch, change):
    payload = {**_snapshot_payload(), **change}
    _mock_process_result(fetch_module, monkeypatch, payload)
    with pytest.raises(fetch_module.CurveFetchProcessError):
        _fetch(fetch_module)


def test_vendor_failure_is_structured_and_never_retried_inline(fetch_module, task_module, monkeypatch):
    failure = {"error": {"kind": "vendor_window_exhausted", "type": "RuntimeError", "message": "vendor unavailable"}}
    popen, _process = _mock_process_result(fetch_module, monkeypatch, failure, returncode=1)
    inline = Mock(side_effect=AssertionError("unbounded inline fallback"))
    monkeypatch.setattr(task_module, "_fetch_curve_snapshot_on_or_before", inline)

    with pytest.raises(RuntimeError, match="vendor unavailable"):
        _fetch(fetch_module)

    popen.assert_called_once()
    inline.assert_not_called()


def test_real_timeout_kills_and_reaps_child(fetch_module, monkeypatch):
    real_popen = subprocess.Popen
    children = []

    def track_process(command, **kwargs):
        if command[1:3] != ["-m", "backend.app.tasks.yield_curve_fetch"]:
            return real_popen(command, **kwargs)
        process = real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(fetch_module.subprocess, "Popen", track_process)
    started = perf_counter()

    with pytest.raises(fetch_module.CurveFetchTimeout, match="timed out"):
        _fetch(fetch_module, timeout_seconds=0.2)

    assert perf_counter() - started < 5.0
    assert len(children) == 1
    assert children[0].returncode is not None
    assert children[0].poll() is not None


def _pid_is_running(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            assert kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            return exit_code.value == 259
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    status = Path(f"/proc/{pid}/stat")
    return not status.exists() or status.read_text().split(")", 1)[1].strip().split()[0] != "Z"


def test_real_timeout_terminates_launcher_and_sleeping_grandchild(fetch_module, monkeypatch, tmp_path):
    real_popen = subprocess.Popen
    marker = tmp_path / "grandchild.pid"
    sleeper = "import os,pathlib,time; pathlib.Path(" + repr(str(marker)) + ").write_text(str(os.getpid())); time.sleep(30)"
    launcher = "import subprocess,sys; child=subprocess.Popen([sys.executable,'-c'," + repr(sleeper) + "]); child.wait()"
    launchers = []

    def launch(command, **kwargs):
        if command[1:3] != ["-m", "backend.app.tasks.yield_curve_fetch"]:
            return real_popen(command, **kwargs)
        process = real_popen([sys.executable, "-c", launcher], **kwargs)
        launchers.append(process)
        return process

    monkeypatch.setattr(fetch_module.subprocess, "Popen", launch)
    started = perf_counter()
    with pytest.raises(fetch_module.CurveFetchTimeout):
        _fetch(fetch_module, timeout_seconds=1.0)

    assert perf_counter() - started < 12.0
    assert marker.is_file(), "The real grandchild must start before the timeout."
    grandchild_pid = int(marker.read_text())
    deadline = perf_counter() + 2.0
    while _pid_is_running(grandchild_pid) and perf_counter() < deadline:
        sleep(0.02)
    try:
        assert launchers[0].returncode is not None
        assert not _pid_is_running(grandchild_pid)
    finally:
        if _pid_is_running(grandchild_pid):
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(grandchild_pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW, check=False,
                )
            else:
                import signal

                os.kill(grandchild_pid, signal.SIGKILL)


def test_cleanup_waits_are_bounded_even_when_tree_termination_fails(fetch_module, monkeypatch):
    process = SimpleNamespace(pid=123, stdin=Mock(), kill=Mock(), wait=Mock(side_effect=subprocess.TimeoutExpired("wait", 5)))
    if os.name == "nt":
        terminate = Mock(side_effect=subprocess.TimeoutExpired("taskkill", 5))
        monkeypatch.setattr(fetch_module.subprocess, "run", terminate)
    else:
        terminate = Mock(side_effect=OSError("killpg unavailable"))
        monkeypatch.setattr(fetch_module.os, "killpg", terminate)

    fetch_module._terminate_process_tree(process)

    process.kill.assert_called_once()
    process.stdin.close.assert_called_once()
    assert process.wait.call_args.kwargs["timeout"] <= 5
    if os.name == "nt":
        assert terminate.call_args.kwargs["timeout"] <= 5


def test_real_native_stdout_noise_cannot_corrupt_result_file(fetch_module, monkeypatch):
    real_popen = subprocess.Popen
    payload = json.dumps(_snapshot_payload())
    script = (
        "import os,pathlib,sys; os.write(1,b'native vendor output\\n'); "
        "os.write(2,b'native vendor error stream\\n'); "
        "pathlib.Path(sys.argv[1]).write_text(" + repr(payload) + ", encoding='utf-8')"
    )

    def launch(command, **kwargs):
        return real_popen([sys.executable, "-c", script, command[-1]], **kwargs)

    monkeypatch.setattr(fetch_module.subprocess, "Popen", launch)
    assert _fetch(fetch_module).source_version == "sv_test"


@pytest.mark.parametrize("failure", ["startup", "missing", "bad_json", "crash", "process_error", "wrong_date"])
def test_process_and_protocol_failures_never_use_local_fallback(fetch_module, task_module, monkeypatch, failure):
    repository = _mock_repository(task_module, monkeypatch)
    monkeypatch.setattr(task_module, "fetch_curve_snapshot_with_timeout", fetch_module.fetch_curve_snapshot_with_timeout)
    fallback = Mock(return_value={"trade_date": "2026-08-30"})
    monkeypatch.setattr(task_module, "_existing_curve_snapshot_on_or_before", fallback)
    if failure == "startup":
        monkeypatch.setattr(fetch_module.subprocess, "Popen", Mock(side_effect=OSError("cannot start")))
    elif failure == "missing":
        _mock_process_result(fetch_module, monkeypatch, None, missing=True)
    elif failure == "bad_json":
        _mock_process_result(fetch_module, monkeypatch, "not json", raw=True)
    elif failure == "crash":
        _mock_process_result(fetch_module, monkeypatch, {}, returncode=17)
    elif failure == "process_error":
        _mock_process_result(fetch_module, monkeypatch, {"error": {"kind": "process_error", "message": "bootstrap failed"}}, returncode=1)
    else:
        _mock_process_result(fetch_module, monkeypatch, _snapshot_payload(trade_date="2026-09-01"))

    with pytest.raises(fetch_module.CurveFetchProcessError):
        task_module.ensure_yield_curve_inputs_on_or_before(
            anchor_dates=("2026-08-31",), duckdb_path="unused.duckdb", curve_types=("treasury",), vendor_timeout_seconds=180
        )

    fallback.assert_not_called()
    repository.replace_curve_snapshots.assert_not_called()


def test_child_uses_existing_backtrack_and_result_file(fetch_module, task_module, monkeypatch, tmp_path, capsys):
    adapter_module = importlib.import_module("backend.app.repositories.akshare_adapter")
    requested = []

    def vendor_fetch(_self, *, curve_type, trade_date):
        print("vendor startup diagnostic")
        requested.append((curve_type, trade_date))
        if trade_date != "2026-08-29":
            raise RuntimeError("market closed")
        return fetch_module._SNAPSHOT_ADAPTER.validate_python(_snapshot_payload(trade_date=trade_date))

    monkeypatch.setattr(adapter_module.VendorAdapter, "fetch_yield_curve", vendor_fetch)
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"curve_type": "treasury", "anchor_date": "2026-08-31", "max_backtrack_days": 3}))
    )
    result_path = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["yield_curve_fetch", "--result-path", str(result_path)])
    monkeypatch.setattr(task_module.YieldCurveRepository, "replace_curve_snapshots", Mock(side_effect=AssertionError("child writes")))

    assert fetch_module._main() == 0

    captured = capsys.readouterr()
    assert json.loads(result_path.read_text(encoding="utf-8"))["trade_date"] == "2026-08-29"
    assert "vendor startup diagnostic" in captured.out
    assert requested == [("treasury", "2026-08-31"), ("treasury", "2026-08-30"), ("treasury", "2026-08-29")]


@pytest.mark.parametrize("as_main", [False, True])
def test_child_failure_returns_error_and_nonzero(fetch_module, task_module, monkeypatch, tmp_path, as_main):
    adapter_module = importlib.import_module("backend.app.repositories.akshare_adapter")
    vendor = Mock(side_effect=RuntimeError("vendor failed"))
    monkeypatch.setattr(adapter_module.VendorAdapter, "fetch_yield_curve", vendor)
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"curve_type": "treasury", "anchor_date": "2026-08-31", "max_backtrack_days": 0}))
    )
    result_path = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["yield_curve_fetch", "--result-path", str(result_path)])

    if as_main:
        with pytest.raises(SystemExit) as exit_result:
            runpy.run_path(fetch_module.__file__, run_name="__main__")
        assert exit_result.value.code == 1
    else:
        assert fetch_module._main() == 1
    vendor.assert_called_once_with(curve_type="treasury", trade_date="2026-08-31")

    assert json.loads(result_path.read_text(encoding="utf-8")) == {
        "error": {"kind": "vendor_window_exhausted", "type": "RuntimeError", "message": "vendor failed"}
    }


def test_child_bootstrap_error_is_not_vendor_exhaustion(fetch_module, monkeypatch, tmp_path):
    result_path = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["yield_curve_fetch", "--result-path", str(result_path)])
    monkeypatch.setattr(sys, "stdin", io.StringIO("bad request"))

    assert fetch_module._main() == 1

    assert json.loads(result_path.read_text(encoding="utf-8"))["error"]["kind"] == "process_error"


def test_child_date_overflow_does_not_authorize_local_fallback(fetch_module, task_module, monkeypatch, tmp_path):
    adapter_module = importlib.import_module("backend.app.repositories.akshare_adapter")
    vendor = Mock(side_effect=RuntimeError("vendor unavailable"))
    monkeypatch.setattr(adapter_module.VendorAdapter, "fetch_yield_curve", vendor)
    request = {"curve_type": "treasury", "anchor_date": "0001-01-02", "max_backtrack_days": 2}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    result_path = tmp_path / "overflow.json"
    monkeypatch.setattr(sys, "argv", ["yield_curve_fetch", "--result-path", str(result_path)])

    assert fetch_module._main() == 1
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert vendor.call_count == 2
    assert payload["error"]["kind"] == "process_error"
    assert payload["error"]["type"] == "OverflowError"

    repository = _mock_repository(task_module, monkeypatch)
    fallback = Mock(return_value={"trade_date": "0001-01-01"})
    monkeypatch.setattr(task_module, "_existing_curve_snapshot_on_or_before", fallback)
    _mock_process_result(fetch_module, monkeypatch, payload, returncode=1)
    with pytest.raises(fetch_module.CurveFetchProcessError):
        task_module.ensure_yield_curve_inputs_on_or_before(
            anchor_dates=(request["anchor_date"],), duckdb_path="unused.duckdb",
            curve_types=("treasury",), max_backtrack_days=2, vendor_timeout_seconds=10,
        )
    fallback.assert_not_called()
    repository.replace_curve_snapshots.assert_not_called()


def test_inline_programming_error_does_not_authorize_local_fallback(task_module, monkeypatch):
    repository = SimpleNamespace(fetch_curve_snapshot=Mock(return_value=None), replace_curve_snapshots=Mock())
    monkeypatch.setattr(task_module, "YieldCurveRepository", lambda _path: repository)
    monkeypatch.setattr(task_module, "VendorAdapter", Mock())
    monkeypatch.setattr(task_module, "_fetch_curve_snapshot_on_or_before", Mock(side_effect=TypeError("broken loop")))
    fallback = Mock(return_value={"trade_date": "2026-08-30"})
    monkeypatch.setattr(task_module, "_existing_curve_snapshot_on_or_before", fallback)

    with pytest.raises(TypeError, match="broken loop"):
        task_module.ensure_yield_curve_inputs_on_or_before(
            anchor_dates=("2026-08-31",), duckdb_path="unused.duckdb", curve_types=("treasury",),
        )
    fallback.assert_not_called()
    repository.replace_curve_snapshots.assert_not_called()


def test_timeout_propagates_without_local_snapshot_fallback(fetch_module, task_module, monkeypatch):
    repository = _mock_repository(task_module, monkeypatch)
    timeout = fetch_module.CurveFetchTimeout("vendor timed out")
    monkeypatch.setattr(task_module, "fetch_curve_snapshot_with_timeout", Mock(side_effect=timeout))
    fallback = Mock(return_value={"trade_date": "2026-08-30"})
    monkeypatch.setattr(task_module, "_existing_curve_snapshot_on_or_before", fallback)

    with pytest.raises(fetch_module.CurveFetchTimeout, match="vendor timed out"):
        task_module.ensure_yield_curve_inputs_on_or_before(
            anchor_dates=("2026-08-31",), duckdb_path="unused.duckdb", curve_types=("treasury",), vendor_timeout_seconds=180
        )

    fallback.assert_not_called()
    repository.replace_curve_snapshots.assert_not_called()
    repository.fetch_curve_snapshot.assert_called_once_with("2026-08-31", "treasury")


def test_ordinary_vendor_error_still_uses_existing_local_fallback(task_module, monkeypatch):
    repository = _mock_repository(task_module, monkeypatch)
    monkeypatch.setattr(
        task_module, "fetch_curve_snapshot_with_timeout",
        Mock(side_effect=task_module.CurveVendorWindowExhausted("vendor down")),
    )
    fallback = Mock(return_value={"trade_date": "2026-08-30"})
    monkeypatch.setattr(task_module, "_existing_curve_snapshot_on_or_before", fallback)

    task_module.ensure_yield_curve_inputs_on_or_before(
        anchor_dates=("2026-08-31",), duckdb_path="unused.duckdb", curve_types=("treasury",), vendor_timeout_seconds=180
    )

    fallback.assert_called_once()
    repository.replace_curve_snapshots.assert_not_called()


def test_preparation_budget_is_shared_across_dates_and_curve_types(fetch_module, task_module, monkeypatch):
    repository = _mock_repository(task_module, monkeypatch)
    clock = iter([100, 101, 102, 103, 104, 105, 106, 108, 109])
    monkeypatch.setattr(task_module, "monotonic", lambda: next(clock))
    requests = []

    def fetch(**kwargs):
        requests.append(kwargs)
        return fetch_module._SNAPSHOT_ADAPTER.validate_python(
            _snapshot_payload(curve_type=kwargs["curve_type"], trade_date=kwargs["anchor_date"])
        )

    monkeypatch.setattr(task_module, "fetch_curve_snapshot_with_timeout", fetch)

    task_module.ensure_yield_curve_inputs_on_or_before(
        anchor_dates=("2026-08-31", "2026-08-30"), duckdb_path="unused.duckdb",
        curve_types=("treasury", "cdb"), vendor_timeout_seconds=10,
    )

    assert [request["timeout_seconds"] for request in requests] == [9, 7, 5, 2]
    assert [(request["anchor_date"], request["curve_type"]) for request in requests] == [
        ("2026-08-30", "treasury"), ("2026-08-30", "cdb"), ("2026-08-31", "treasury"), ("2026-08-31", "cdb"),
    ]
    assert repository.replace_curve_snapshots.call_count == 4


def test_exhausted_budget_does_not_launch_another_fetch(fetch_module, task_module, monkeypatch):
    repository = _mock_repository(task_module, monkeypatch)
    clock = iter([100, 101, 102, 111])
    monkeypatch.setattr(task_module, "monotonic", lambda: next(clock))
    fetch = Mock(return_value=fetch_module._SNAPSHOT_ADAPTER.validate_python(_snapshot_payload()))
    monkeypatch.setattr(task_module, "fetch_curve_snapshot_with_timeout", fetch)
    fallback = Mock(side_effect=AssertionError("timeout uses local fallback"))
    monkeypatch.setattr(task_module, "_existing_curve_snapshot_on_or_before", fallback)

    with pytest.raises(fetch_module.CurveFetchTimeout, match="budget has expired"):
        task_module.ensure_yield_curve_inputs_on_or_before(
            anchor_dates=("2026-08-31",), duckdb_path="unused.duckdb",
            curve_types=("treasury", "cdb"), vendor_timeout_seconds=10,
        )

    fetch.assert_called_once()
    assert repository.replace_curve_snapshots.call_count == 1
    fallback.assert_not_called()


def test_late_response_does_not_write_after_budget_expired(fetch_module, task_module, monkeypatch):
    repository = _mock_repository(task_module, monkeypatch)
    clock = iter([100, 101, 111])
    monkeypatch.setattr(task_module, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        task_module, "fetch_curve_snapshot_with_timeout",
        Mock(return_value=fetch_module._SNAPSHOT_ADAPTER.validate_python(_snapshot_payload())),
    )
    with pytest.raises(fetch_module.CurveFetchTimeout):
        task_module.ensure_yield_curve_inputs_on_or_before(
            anchor_dates=("2026-08-31",), duckdb_path="unused.duckdb", curve_types=("treasury",), vendor_timeout_seconds=10
        )
    repository.replace_curve_snapshots.assert_not_called()


def test_exact_existing_curves_do_not_launch_vendor_process(task_module, monkeypatch):
    repository = _mock_repository(task_module, monkeypatch)
    repository.fetch_curve_snapshot.return_value = {"trade_date": "2026-08-31"}
    fetch = Mock(side_effect=AssertionError("unnecessary vendor process"))
    monkeypatch.setattr(task_module, "fetch_curve_snapshot_with_timeout", fetch)

    task_module.ensure_yield_curve_inputs_on_or_before(
        anchor_dates=("2026-08-31",), duckdb_path="unused.duckdb", vendor_timeout_seconds=180,
    )

    fetch.assert_not_called()
    repository.replace_curve_snapshots.assert_not_called()


@pytest.mark.parametrize("budget", [-1, 0, float("inf"), float("nan")])
def test_preparation_rejects_invalid_budgets(task_module, monkeypatch, budget):
    _mock_repository(task_module, monkeypatch)
    with pytest.raises(ValueError, match="finite and positive"):
        task_module.ensure_yield_curve_inputs_on_or_before(
            anchor_dates=("2026-08-31",), duckdb_path="unused.duckdb", vendor_timeout_seconds=budget,
        )


def test_private_bootstrap_error_is_not_forwarded_or_fallback(fetch_module, task_module, monkeypatch, tmp_path):
    adapter_module = importlib.import_module("backend.app.repositories.akshare_adapter")
    marker = "synthetic-child-bootstrap-private-token"
    monkeypatch.setattr(adapter_module, "VendorAdapter", Mock(side_effect=TypeError(marker)))
    request = {"curve_type": "treasury", "anchor_date": "2026-08-31", "max_backtrack_days": 2}
    result_path = tmp_path / "private-result.json"
    monkeypatch.setattr(sys, "argv", ["yield_curve_fetch", "--result-path", str(result_path)])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(request)))
    assert fetch_module._main() == 1
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["error"]["kind"] == "process_error"
    assert payload["error"]["type"] == "TypeError"
    repository = _mock_repository(task_module, monkeypatch)
    fallback = Mock()
    monkeypatch.setattr(task_module, "_existing_curve_snapshot_on_or_before", fallback)
    _mock_process_result(fetch_module, monkeypatch, payload, returncode=1)
    with pytest.raises(fetch_module.CurveFetchProcessError) as caught:
        task_module.ensure_yield_curve_inputs_on_or_before(anchor_dates=("2026-08-31",), duckdb_path="unused.duckdb", curve_types=("treasury",), vendor_timeout_seconds=10)
    assert marker not in str(caught.value)
    fallback.assert_not_called()
    repository.replace_curve_snapshots.assert_not_called()
