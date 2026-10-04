from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
import requests

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.tasks import commodity_daily_ingest as task

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


class _UnexpectedHttpRequest(BaseException):
    pass


class _UnexpectedDatabaseDestination(BaseException):
    pass


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _commodity_row(product_code: str = "RB") -> dict[str, object]:
    return {
        "trade_date": "2026-09-15",
        "product_code": product_code,
        "contract_code": f"{product_code}0",
        "exchange": "SHF",
        "close_value": 3910.0,
        "source_version": "synthetic-source",
        "vendor_version": "synthetic-vendor",
        "rule_version": task.RULE_VERSION,
    }


def _configure_isolated_writer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        task,
        "resolve_tushare_token_with_settings_fallback",
        lambda _settings: None,
    )
    monkeypatch.setattr(
        task,
        "apply_pending_migrations_on_connection",
        task.ensure_commodity_futures_daily_schema,
    )


def _read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _wait_for_event(path: Path, name: str, *, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if any(event.get("event") == name for event in _read_events(path)):
            return
        time.sleep(0.01)
    raise AssertionError(
        f"Timed out waiting for child event {name}: {_read_events(path)}"
    )


def _strict_writer_child_code() -> str:
    return r"""
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
database = Path(sys.argv[2]).resolve()
events_path = Path(sys.argv[3]).resolve()
result_path = Path(sys.argv[4]).resolve()
mode = sys.argv[5] if len(sys.argv) > 5 else "single"
release_path = (
    None
    if len(sys.argv) <= 6 or sys.argv[6] == "-"
    else Path(sys.argv[6]).resolve()
)
guard.register_pytest_duckdb_temp_root(owned_root)
guard.set_pytest_duckdb_guard_phase("commodity-writer-child")

def emit(name, **details):
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": name, **details}, sort_keys=True) + "\n")
        handle.flush()

try:
    import requests

    http_calls = []

    class UnexpectedHttpRequest(BaseException):
        pass

    class UnexpectedDatabaseDestination(BaseException):
        pass

    def forbid_http_request(_session, *args, **kwargs):
        method = kwargs.get("method", args[0] if args else None)
        url = kwargs.get("url", args[1] if len(args) > 1 else None)
        http_calls.append([method, url])
        raise UnexpectedHttpRequest("HTTP is forbidden in this writer child.")

    requests.Session.request = forbid_http_request
    import backend.app.tasks.commodity_daily_ingest as task

    actual_acquire = task.acquire_lock
    actual_connect = task.duckdb.connect
    actual_resolve_writer_lock = task.resolve_duckdb_writer_lock
    foreign_database_attempts = []
    supplier_calls = []
    state = {"native_open": 0, "path_lock_depth": 0}

    @contextmanager
    def observed_acquire(definition, *args, **kwargs):
        kind = (
            "commodity"
            if definition.key == task.COMMODITY_DAILY_LOCK.key
            else "path"
        )
        emit(f"{kind}-attempt", key=definition.key)
        entered = False
        try:
            with actual_acquire(definition, *args, **kwargs) as value:
                entered = True
                emit(f"{kind}-entered", key=definition.key)
                if kind == "path":
                    state["path_lock_depth"] += 1
                try:
                    yield value
                finally:
                    if kind == "path":
                        state["path_lock_depth"] -= 1
        except BaseException:
            if not entered:
                emit(f"{kind}-failed", key=definition.key)
            raise
        finally:
            if entered:
                emit(f"{kind}-released", key=definition.key)

    class ObservedConnection:
        def __init__(self, connection):
            self._connection = connection
            self._closed = False

        def __getattr__(self, name):
            return getattr(self._connection, name)

        def close(self):
            if self._closed:
                return None
            result = self._connection.close()
            self._closed = True
            state["native_open"] -= 1
            emit("native-closed")
            return result

    def observed_connect(*args, **kwargs):
        raw_database = args[0] if args else kwargs.get("database")
        requested_database = Path(os.fspath(raw_database)).resolve()
        if requested_database != database:
            foreign_database_attempts.append(os.fspath(requested_database))
            raise UnexpectedDatabaseDestination(
                f"Unexpected database destination: {requested_database}"
            )
        emit("native-open-attempt", database=os.fspath(database))
        connection = actual_connect(*args, **kwargs)
        state["native_open"] += 1
        emit("native-opened", database=os.fspath(database))
        return ObservedConnection(connection)

    def fetch_rows(**kwargs):
        supplier_calls.append(kwargs["spec"].product_code)
        if state != {"native_open": 0, "path_lock_depth": 0}:
            raise AssertionError(f"supplier called inside database session: {state}")
        if mode == "path-timeout":
            raise AssertionError("supplier must not run after path-lock timeout")
        if release_path is not None:
            emit("supplier-started")
            deadline = time.monotonic() + 10
            while not release_path.exists():
                if state != {"native_open": 0, "path_lock_depth": 0}:
                    raise AssertionError(f"database session opened during supplier wait: {state}")
                if time.monotonic() >= deadline:
                    raise TimeoutError("parent did not release synthetic supplier")
                time.sleep(0.01)
        emit("supplier-complete")
        product_code = kwargs["spec"].product_code
        return [{
            "trade_date": "2026-09-16" if mode == "second" else "2026-09-15",
            "product_code": product_code,
            "contract_code": f"{product_code}0",
            "exchange": "SHF",
            "close_value": 3910.0,
            "source_version": "synthetic-source",
            "vendor_version": "synthetic-vendor",
            "rule_version": task.RULE_VERSION,
        }], "synthetic-vendor", [{
            "vendor": "synthetic-vendor",
            "status": "success",
            "row_count": 1,
        }]

    task.acquire_lock = observed_acquire
    task.duckdb.connect = observed_connect
    task.resolve_tushare_token_with_settings_fallback = lambda _settings: None
    task.apply_pending_migrations_on_connection = task.ensure_commodity_futures_daily_schema
    task._fetch_product_rows = fetch_rows
    if mode == "path-timeout":
        task.resolve_duckdb_writer_lock = lambda path: actual_resolve_writer_lock(
            path,
            ttl_seconds=0.1,
        )
        try:
            task.run_commodity_daily_ingest(
                start_date="2026-09-15",
                end_date="2026-09-15",
                duckdb_path=os.fspath(database),
                products=("RB",),
            )
        except TimeoutError as exc:
            result = {
                "status": "path_lock_timeout",
                "error_class": type(exc).__name__,
                "error": str(exc),
            }
        else:
            raise AssertionError("held path lock should time out")
    else:
        result = task.run_commodity_daily_ingest(
            start_date="2026-09-15",
            end_date="2026-09-16" if mode == "second" else "2026-09-15",
            duckdb_path=os.fspath(database),
            products=("RB",),
        )
    producer_http_call_count = len(http_calls)
    producer_foreign_database_count = len(foreign_database_attempts)
    try:
        requests.Session().request(method="GET", url="https://guard-self-check.invalid/")
    except UnexpectedHttpRequest:
        pass
    else:
        raise AssertionError("HTTP sentinel self-check did not block the request.")
    try:
        observed_connect(os.fspath(owned_root / "foreign.duckdb"))
    except UnexpectedDatabaseDestination:
        pass
    else:
        raise AssertionError("Database destination sentinel self-check did not block the open.")
    result_path.write_text(
        json.dumps({
            "result": result,
            "producer_http_call_count": producer_http_call_count,
            "producer_foreign_database_count": producer_foreign_database_count,
            "supplier_call_count": len(supplier_calls),
            "http_self_check_count": len(http_calls),
            "database_self_check_count": len(foreign_database_attempts),
        }, sort_keys=True, default=str),
        encoding="utf-8",
    )
except BaseException as exc:
    emit("child-error", error_class=type(exc).__name__, error=str(exc))
    raise
finally:
    guard.finalize_pytest_duckdb_guard()
"""


def _communicate_child_bounded(
    child: subprocess.Popen[str],
) -> tuple[str, str]:
    try:
        return child.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        child.terminate()
        try:
            return child.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            return child.communicate(timeout=5)


def _install_http_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[object, object]]:
    calls: list[tuple[object, object]] = []

    def forbid_http_request(_session, *args, **kwargs):
        method = kwargs.get("method", args[0] if args else None)
        url = kwargs.get("url", args[1] if len(args) > 1 else None)
        calls.append((method, url))
        raise _UnexpectedHttpRequest("HTTP is forbidden in this isolated writer test.")

    monkeypatch.setattr(requests.Session, "request", forbid_http_request)
    return calls


def _assert_http_sentinel_wired(calls: list[tuple[object, object]]) -> None:
    assert calls == []
    with pytest.raises(_UnexpectedHttpRequest):
        requests.Session().request(
            method="GET",
            url="https://guard-self-check.invalid/",
        )
    assert calls == [("GET", "https://guard-self-check.invalid/")]


def _install_admission_observers(
    monkeypatch: pytest.MonkeyPatch,
    *,
    database: Path,
) -> tuple[list[str], dict[str, int], list[Path], object]:
    events: list[str] = []
    state = {"native_open": 0, "path_lock_depth": 0}
    foreign_database_attempts: list[Path] = []
    actual_acquire = task.acquire_lock
    actual_connect = task.duckdb.connect

    @contextmanager
    def observed_acquire(definition, *args, **kwargs):
        if definition.key == task.COMMODITY_DAILY_LOCK.key:
            kind = "commodity"
        elif definition.key.startswith("lock:duckdb:materialize:"):
            kind = "path"
        else:
            raise AssertionError(f"unexpected lock: {definition.key}")
        events.append(f"{kind}-attempt")
        try:
            with actual_acquire(definition, *args, **kwargs) as value:
                events.append(f"{kind}-entered")
                if kind == "path":
                    state["path_lock_depth"] += 1
                try:
                    yield value
                finally:
                    if kind == "path":
                        state["path_lock_depth"] -= 1
        finally:
            events.append(f"{kind}-released")

    class ObservedConnection:
        def __init__(self, connection):
            self._connection = connection
            self._closed = False

        def __getattr__(self, name):
            return getattr(self._connection, name)

        def close(self):
            if self._closed:
                return None
            result = self._connection.close()
            self._closed = True
            state["native_open"] -= 1
            events.append("native-closed")
            return result

    def observed_connect(*args, **kwargs):
        raw_database = args[0] if args else kwargs.get("database")
        requested_database = Path(os.fspath(raw_database)).resolve()
        if requested_database != database.resolve():
            foreign_database_attempts.append(requested_database)
            raise _UnexpectedDatabaseDestination(
                f"Unexpected database destination: {requested_database}"
            )
        events.append("native-open-attempt")
        connection = actual_connect(*args, **kwargs)
        state["native_open"] += 1
        events.append("native-opened")
        return ObservedConnection(connection)

    monkeypatch.setattr(task, "acquire_lock", observed_acquire)
    monkeypatch.setattr(task.duckdb, "connect", observed_connect)
    return events, state, foreign_database_attempts, actual_connect


def test_fetch_runs_between_short_path_locked_database_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "commodity.duckdb"
    http_calls = _install_http_sentinel(monkeypatch)
    events, state, foreign_attempts, _actual_connect = _install_admission_observers(
        monkeypatch,
        database=database,
    )
    _configure_isolated_writer(monkeypatch)

    def fetch_rows(**_kwargs):
        assert state == {"native_open": 0, "path_lock_depth": 0}
        events.append("supplier-complete")
        return (
            [_commodity_row()],
            "synthetic-vendor",
            [{"vendor": "synthetic-vendor", "status": "success", "row_count": 1}],
        )

    monkeypatch.setattr(task, "_fetch_product_rows", fetch_rows)

    result = task.run_commodity_daily_ingest(
        start_date="2026-09-15",
        end_date="2026-09-15",
        duckdb_path=os.fspath(database),
        products=("RB",),
    )

    assert result["status"] == "completed"
    assert result["row_count"] == 1
    assert events == [
        "commodity-attempt",
        "commodity-entered",
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
        "supplier-complete",
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
        "commodity-released",
    ]
    assert state == {"native_open": 0, "path_lock_depth": 0}
    assert foreign_attempts == []
    _assert_http_sentinel_wired(http_calls)


def test_writer_waits_at_path_admission_before_native_open_or_fetch(
    tmp_path: Path,
) -> None:
    database = tmp_path / "commodity-blocked.duckdb"
    events_path = tmp_path / "child-events.jsonl"
    result_path = tmp_path / "child-result.json"
    bootstrap_connection = task.duckdb.connect(os.fspath(database), read_only=False)
    bootstrap_connection.close()

    lock_context = None
    lock_entered = False
    reader = None
    child: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    try:
        lock_context = acquire_lock(
            resolve_duckdb_writer_lock(database),
            base_dir=database.parent,
        )
        lock_context.__enter__()
        lock_entered = True
        reader = task.duckdb.connect(os.fspath(database), read_only=True)
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _strict_writer_child_code(),
                os.fspath(tmp_path),
                os.fspath(database),
                os.fspath(events_path),
                os.fspath(result_path),
            ],
            cwd=os.fspath(_REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_event(events_path, "path-attempt")
        assert [str(event["event"]) for event in _read_events(events_path)] == [
            "commodity-attempt",
            "commodity-entered",
            "path-attempt",
        ]
        assert child.poll() is None
    finally:
        try:
            try:
                if reader is not None:
                    reader.close()
            finally:
                if lock_entered and lock_context is not None:
                    lock_context.__exit__(None, None, None)
        finally:
            if child is not None:
                try:
                    stdout, stderr = child.communicate(timeout=20)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    try:
                        stdout, stderr = child.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        stdout, stderr = child.communicate(timeout=5)

    assert child is not None
    assert child.returncode == 0, (
        f"stdout={stdout}\nstderr={stderr}\nevents={_read_events(events_path)}"
    )
    assert [str(event["event"]) for event in _read_events(events_path)] == [
        "commodity-attempt",
        "commodity-entered",
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
        "supplier-complete",
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
        "commodity-released",
    ]
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["result"]["status"] == "completed"
    assert payload["result"]["row_count"] == 1
    assert payload["producer_http_call_count"] == 0
    assert payload["producer_foreign_database_count"] == 0
    assert payload["http_self_check_count"] == 1
    assert payload["database_self_check_count"] == 1


def test_two_competing_calls_remain_serial_for_the_whole_run(
    tmp_path: Path,
) -> None:
    database = tmp_path / "commodity-serial.duckdb"
    first_events_path = tmp_path / "first-events.jsonl"
    first_result_path = tmp_path / "first-result.json"
    second_events_path = tmp_path / "second-events.jsonl"
    second_result_path = tmp_path / "second-result.json"
    release_path = tmp_path / "release-first-fetch"
    bootstrap_connection = task.duckdb.connect(os.fspath(database), read_only=False)
    bootstrap_connection.close()

    first_child: subprocess.Popen[str] | None = None
    second_child: subprocess.Popen[str] | None = None
    first_stdout = first_stderr = ""
    second_stdout = second_stderr = ""
    try:
        first_child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _strict_writer_child_code(),
                os.fspath(tmp_path),
                os.fspath(database),
                os.fspath(first_events_path),
                os.fspath(first_result_path),
                "first",
                os.fspath(release_path),
            ],
            cwd=os.fspath(_REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_event(first_events_path, "supplier-started")
        first_events = [
            str(event["event"]) for event in _read_events(first_events_path)
        ]
        assert first_events == [
            "commodity-attempt",
            "commodity-entered",
            "path-attempt",
            "path-entered",
            "native-open-attempt",
            "native-opened",
            "native-closed",
            "path-released",
            "supplier-started",
        ]
        assert first_child.poll() is None

        second_child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _strict_writer_child_code(),
                os.fspath(tmp_path),
                os.fspath(database),
                os.fspath(second_events_path),
                os.fspath(second_result_path),
                "second",
                "-",
            ],
            cwd=os.fspath(_REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_event(second_events_path, "commodity-attempt")
        assert [str(event["event"]) for event in _read_events(second_events_path)] == [
            "commodity-attempt"
        ]
        assert second_child.poll() is None
        release_path.write_text("release", encoding="utf-8")
    finally:
        if not release_path.exists():
            release_path.write_text("release", encoding="utf-8")
        if first_child is not None:
            first_stdout, first_stderr = _communicate_child_bounded(first_child)
        if second_child is not None:
            second_stdout, second_stderr = _communicate_child_bounded(second_child)

    assert first_child is not None
    assert second_child is not None
    assert first_child.returncode == 0, (
        f"stdout={first_stdout}\nstderr={first_stderr}\nevents={_read_events(first_events_path)}"
    )
    assert second_child.returncode == 0, (
        f"stdout={second_stdout}\nstderr={second_stderr}\nevents={_read_events(second_events_path)}"
    )
    assert [str(event["event"]) for event in _read_events(first_events_path)][-3:] == [
        "native-closed",
        "path-released",
        "commodity-released",
    ]
    assert [str(event["event"]) for event in _read_events(second_events_path)] == [
        "commodity-attempt",
        "commodity-entered",
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
        "supplier-complete",
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
        "commodity-released",
    ]
    for result_path in (first_result_path, second_result_path):
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        assert payload["result"]["status"] == "completed"
        assert payload["producer_http_call_count"] == 0
        assert payload["producer_foreign_database_count"] == 0
        assert payload["supplier_call_count"] == 1
        assert payload["http_self_check_count"] == 1
        assert payload["database_self_check_count"] == 1


@pytest.mark.parametrize("failure_phase", ["fetch", "insert"])
def test_later_product_failure_preserves_the_first_product_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_phase: str,
) -> None:
    database = tmp_path / f"commodity-{failure_phase}-failure.duckdb"
    _configure_isolated_writer(monkeypatch)
    actual_connect = task.duckdb.connect
    fetched_products: list[str] = []

    def fetch_rows(**kwargs):
        product_code = kwargs["spec"].product_code
        fetched_products.append(product_code)
        if product_code == "CU" and failure_phase == "fetch":
            raise RuntimeError("synthetic later fetch failure")
        return (
            [_commodity_row(product_code)],
            "synthetic-vendor",
            [{"vendor": "synthetic-vendor", "status": "success", "row_count": 1}],
        )

    class FailingInsertConnection:
        def __init__(self, connection):
            self._connection = connection
            self._write_product: str | None = None

        def __getattr__(self, name):
            return getattr(self._connection, name)

        def execute(self, query, parameters=None):
            if "delete from fact_commodity_futures_daily" in str(query).lower():
                self._write_product = str(parameters[0])
            if parameters is None:
                return self._connection.execute(query)
            return self._connection.execute(query, parameters)

        def executemany(self, query, parameters):
            if failure_phase == "insert" and self._write_product == "CU":
                raise RuntimeError("synthetic later insert failure")
            return self._connection.executemany(query, parameters)

    def observed_connect(*args, **kwargs):
        return FailingInsertConnection(actual_connect(*args, **kwargs))

    monkeypatch.setattr(task, "_fetch_product_rows", fetch_rows)
    monkeypatch.setattr(task.duckdb, "connect", observed_connect)

    with pytest.raises(RuntimeError, match=f"synthetic later {failure_phase} failure"):
        task.run_commodity_daily_ingest(
            start_date="2026-09-15",
            end_date="2026-09-15",
            duckdb_path=os.fspath(database),
            products=("RB", "CU"),
        )

    conn = actual_connect(os.fspath(database), read_only=True)
    try:
        assert conn.execute(
            "select product_code, trade_date from fact_commodity_futures_daily order by product_code"
        ).fetchall() == [("RB", "2026-09-15")]
    finally:
        conn.close()
    assert fetched_products == ["RB", "CU"]


def test_soft_deadline_keeps_receipt_and_does_not_fetch_following_product(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "commodity-deadline.duckdb"
    _configure_isolated_writer(monkeypatch)
    monkeypatch.setattr(task, "COMMODITY_PRODUCT_SOFT_DEADLINE_SECONDS", -1.0)
    fetched_products: list[str] = []

    def fetch_rows(**kwargs):
        product_code = kwargs["spec"].product_code
        fetched_products.append(product_code)
        return (
            [_commodity_row(product_code)],
            "synthetic-vendor",
            [{"vendor": "synthetic-vendor", "status": "success", "row_count": 1}],
        )

    monkeypatch.setattr(task, "_fetch_product_rows", fetch_rows)
    result = task.run_commodity_daily_ingest(
        start_date="2026-09-15",
        end_date="2026-09-15",
        duckdb_path=os.fspath(database),
        products=("RB", "CU"),
    )

    assert fetched_products == ["RB"]
    assert result["status"] == "partial"
    assert result["successful_products"] == ["RB"]
    assert result["missing_required_products"] == ["CU"]
    assert result["products"][0]["deadline_exceeded"] is True
    assert result["products"][1]["status"] == "not_attempted"


def test_path_lock_failure_does_not_open_database(
    tmp_path: Path,
) -> None:
    database = tmp_path / "commodity-lock-failure.duckdb"
    events_path = tmp_path / "timeout-events.jsonl"
    result_path = tmp_path / "timeout-result.json"
    bootstrap_connection = task.duckdb.connect(os.fspath(database), read_only=False)
    bootstrap_connection.close()
    path_lock_context = acquire_lock(
        resolve_duckdb_writer_lock(database),
        base_dir=database.parent,
    )
    path_lock_context.__enter__()
    path_lock_entered = True
    child: subprocess.Popen[str] | None = None
    stdout = stderr = ""
    try:
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _strict_writer_child_code(),
                os.fspath(tmp_path),
                os.fspath(database),
                os.fspath(events_path),
                os.fspath(result_path),
                "path-timeout",
                "-",
            ],
            cwd=os.fspath(_REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = _communicate_child_bounded(child)
        assert child.returncode == 0, (
            f"stdout={stdout}\nstderr={stderr}\nevents={_read_events(events_path)}"
        )
        with acquire_lock(
            task.COMMODITY_DAILY_LOCK,
            base_dir=database.parent,
            timeout_seconds=1,
        ):
            pass
    finally:
        if child is not None and child.poll() is None:
            stdout, stderr = _communicate_child_bounded(child)
        if path_lock_entered:
            path_lock_context.__exit__(None, None, None)

    assert child is not None
    assert [str(event["event"]) for event in _read_events(events_path)] == [
        "commodity-attempt",
        "commodity-entered",
        "path-attempt",
        "path-failed",
        "commodity-released",
    ]
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["result"]["status"] == "path_lock_timeout"
    assert payload["result"]["error_class"] == "TimeoutError"
    assert payload["producer_http_call_count"] == 0
    assert payload["producer_foreign_database_count"] == 0
    assert payload["supplier_call_count"] == 0
    assert payload["http_self_check_count"] == 1
    assert payload["database_self_check_count"] == 1


def test_schema_failure_closes_database_and_does_not_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "commodity-schema-failure.duckdb"
    http_calls = _install_http_sentinel(monkeypatch)
    events, state, foreign_attempts, _actual_connect = _install_admission_observers(
        monkeypatch,
        database=database,
    )
    monkeypatch.setattr(
        task, "resolve_tushare_token_with_settings_fallback", lambda _settings: None
    )

    def fail_schema(_conn) -> None:
        raise RuntimeError("synthetic schema failure")

    def forbid_fetch(**_kwargs):
        raise AssertionError("supplier must not run after schema failure")

    monkeypatch.setattr(task, "apply_pending_migrations_on_connection", fail_schema)
    monkeypatch.setattr(task, "_fetch_product_rows", forbid_fetch)

    with pytest.raises(RuntimeError, match="synthetic schema failure"):
        task.run_commodity_daily_ingest(
            start_date="2026-09-15",
            end_date="2026-09-15",
            duckdb_path=os.fspath(database),
            products=("RB",),
        )

    assert events == [
        "commodity-attempt",
        "commodity-entered",
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
        "commodity-released",
    ]
    assert state == {"native_open": 0, "path_lock_depth": 0}
    assert foreign_attempts == []
    _assert_http_sentinel_wired(http_calls)
