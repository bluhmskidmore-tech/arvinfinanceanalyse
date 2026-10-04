from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.duckdb_read_context import (
    DuckDBOnlineReadRequiredError,
    DuckDBReadSelection,
    duckdb_read_scope,
)
from scripts import run_livermore_daily_pretrade_refresh as driver

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _wait_for_event(path: Path, name: str, *, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if any(event.get("event") == name for event in _read_events(path)):
            return
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for child event {name}: {_read_events(path)}")


def _inspector_child_code() -> str:
    return r'''
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
database = Path(sys.argv[2]).resolve()
events_path = Path(sys.argv[3]).resolve()
result_path = Path(sys.argv[4]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.set_pytest_duckdb_guard_phase("pretrade-inspector-child")

def emit(name, **details):
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": name, **details}, sort_keys=True) + "\n")
        handle.flush()

try:
    import duckdb
    import requests

    http_calls = []
    foreign_database_attempts = []

    class UnexpectedHttpRequest(BaseException):
        pass

    class UnexpectedDatabaseDestination(BaseException):
        pass

    def forbid_http_request(_session, *args, **kwargs):
        method = kwargs.get("method", args[0] if args else None)
        url = kwargs.get("url", args[1] if len(args) > 1 else None)
        http_calls.append([method, url])
        raise UnexpectedHttpRequest("HTTP is forbidden in this inspector child.")

    requests.Session.request = forbid_http_request
    from backend.app.governance.locks import acquire_lock as actual_acquire
    import scripts.run_livermore_daily_pretrade_refresh as driver

    actual_connect = duckdb.connect

    @contextmanager
    def observed_acquire(definition, *args, **kwargs):
        emit("path-attempt", key=definition.key)
        try:
            with actual_acquire(definition, *args, **kwargs) as value:
                emit("path-entered", key=definition.key)
                yield value
        finally:
            emit("path-released", key=definition.key)

    class ObservedConnection:
        def __init__(self, connection):
            self._connection = connection

        def __getattr__(self, name):
            return getattr(self._connection, name)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.close()

        def close(self):
            result = self._connection.close()
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
        emit("native-opened", database=os.fspath(database))
        return ObservedConnection(connection)

    driver.acquire_lock = observed_acquire
    duckdb.connect = observed_connect
    result = driver.inspect_livermore_daily_refresh_state(
        duckdb_path=os.fspath(database),
        target_date="2026-09-15",
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
        json.dumps(
            {
                "result": result,
                "producer_http_call_count": producer_http_call_count,
                "producer_foreign_database_count": producer_foreign_database_count,
                "http_self_check_count": len(http_calls),
                "database_self_check_count": len(foreign_database_attempts),
            },
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
except BaseException as exc:
    emit("child-error", error_class=type(exc).__name__, error=str(exc))
    raise
finally:
    guard.finalize_pytest_duckdb_guard()
'''


def test_active_inspector_waits_at_path_admission_before_native_open(tmp_path: Path) -> None:
    database = tmp_path / "active" / "livermore.duckdb"
    database.parent.mkdir(parents=True)
    duckdb.connect(os.fspath(database)).close()
    events_path = tmp_path / "inspector-events.jsonl"
    result_path = tmp_path / "inspector-result.json"

    lock_context = None
    lock_entered = False
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
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _inspector_child_code(),
                os.fspath(tmp_path),
                os.fspath(database),
                os.fspath(events_path),
                os.fspath(result_path),
            ],
            cwd=_REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_event(events_path, "path-attempt")
        assert [str(event["event"]) for event in _read_events(events_path)] == ["path-attempt"]
        assert child.poll() is None
    finally:
        try:
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
    assert child.returncode == 0, f"stdout={stdout}\nstderr={stderr}\nevents={_read_events(events_path)}"
    assert [str(event["event"]) for event in _read_events(events_path)] == [
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
    ]
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["result"]["ready"] is False
    assert payload["producer_http_call_count"] == 0
    assert payload["producer_foreign_database_count"] == 0
    assert payload["http_self_check_count"] == 1
    assert payload["database_self_check_count"] == 1


def _create_factor_database(database: Path, *, row_count: int) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(os.fspath(database), read_only=False) as conn:
        conn.execute("create table choice_stock_factor_snapshot (as_of_date varchar)")
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?)",
            [("2026-09-15",)] * row_count,
        )


def test_selected_snapshot_and_explicit_snapshot_skip_active_path_lock(tmp_path: Path) -> None:
    active = tmp_path / "active" / "livermore.duckdb"
    snapshot = tmp_path / "sealed" / "generation-1.duckdb"
    _create_factor_database(active, row_count=1)
    _create_factor_database(snapshot, row_count=2)
    selection = DuckDBReadSelection(
        active_path=active,
        snapshot_path=snapshot,
        generation="generation-1",
    )
    active.unlink()

    with duckdb_read_scope(selection):
        selected = driver.inspect_livermore_daily_refresh_state(
            duckdb_path=active,
            target_date="2026-09-15",
        )
        explicit_snapshot = driver.inspect_livermore_daily_refresh_state(
            duckdb_path=snapshot,
            target_date="2026-09-15",
        )

    assert selected["checks"]["factor_snapshot"]["row_count"] == 2
    assert explicit_snapshot["checks"]["factor_snapshot"]["row_count"] == 2
    assert not (active.parent / ".locks").exists()
    assert not (snapshot.parent / ".locks").exists()


def test_required_online_without_selection_fails_closed_before_lock_or_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "active" / "livermore.duckdb"
    _create_factor_database(active, row_count=1)
    open_attempts: list[tuple[object, dict[str, object]]] = []

    @contextmanager
    def forbid_read(*args, **kwargs):
        open_attempts.append((args, kwargs))
        raise AssertionError("required-online failure must happen before native open")
        yield  # pragma: no cover

    monkeypatch.setattr(driver, "read_only_connection", forbid_read)
    with duckdb_read_scope(None, required_online=True, active_path=active):
        with pytest.raises(DuckDBOnlineReadRequiredError):
            driver.inspect_livermore_daily_refresh_state(
                duckdb_path=active,
                target_date="2026-09-15",
            )

    assert open_attempts == []
    assert not (active.parent / ".locks").exists()


def test_native_open_failure_is_attempted_once_and_releases_path_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "active" / "livermore.duckdb"
    _create_factor_database(active, row_count=1)
    attempts: list[tuple[Path, int | None]] = []

    @contextmanager
    def failing_read(path: str, *, retries: int = 3, **_kwargs):
        attempts.append((Path(path).resolve(), retries))
        raise duckdb.IOException("synthetic native open failure")
        yield  # pragma: no cover

    monkeypatch.setattr(driver, "read_only_connection", failing_read)
    with pytest.raises(duckdb.IOException, match="synthetic native open failure"):
        driver.inspect_livermore_daily_refresh_state(
            duckdb_path=active,
            target_date="2026-09-15",
        )

    assert attempts == [(active.resolve(), 1)]
    with acquire_lock(
        resolve_duckdb_writer_lock(active),
        base_dir=active.parent,
        timeout_seconds=0.2,
    ):
        pass


def test_query_failure_closes_connection_before_releasing_path_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "active" / "livermore.duckdb"
    _create_factor_database(active, row_count=1)
    events: list[str] = []
    actual_acquire = driver.acquire_lock

    @contextmanager
    def observed_acquire(definition, *args, **kwargs):
        events.append("path-attempt")
        try:
            with actual_acquire(definition, *args, **kwargs) as value:
                events.append("path-entered")
                yield value
        finally:
            events.append("path-released")

    class FailingConnection:
        def execute(self, _query, *_args, **_kwargs):
            events.append("query-failed")
            raise RuntimeError("synthetic query failure")

    @contextmanager
    def observed_read(path: str, *, retries: int = 3, **_kwargs):
        assert Path(path).resolve() == active.resolve()
        assert retries == 1
        events.append("native-opened")
        try:
            yield FailingConnection()
        finally:
            events.append("native-closed")

    monkeypatch.setattr(driver, "acquire_lock", observed_acquire)
    monkeypatch.setattr(driver, "read_only_connection", observed_read)
    with pytest.raises(RuntimeError, match="synthetic query failure"):
        driver.inspect_livermore_daily_refresh_state(
            duckdb_path=active,
            target_date="2026-09-15",
        )

    assert events == [
        "path-attempt",
        "path-entered",
        "native-opened",
        "query-failed",
        "native-closed",
        "path-released",
    ]


def test_path_lock_timeout_does_not_attempt_native_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = tmp_path / "active" / "livermore.duckdb"
    _create_factor_database(active, row_count=1)
    ready = tmp_path / "holder-ready"
    release = tmp_path / "holder-release"
    holder_code = r'''
import sys
import time
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
database = Path(sys.argv[2]).resolve()
ready = Path(sys.argv[3]).resolve()
release = Path(sys.argv[4]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.set_pytest_duckdb_guard_phase("pretrade-inspector-lock-holder")
try:
    from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock

    with acquire_lock(
        resolve_duckdb_writer_lock(database),
        base_dir=database.parent,
        timeout_seconds=2,
    ):
        ready.write_text("ready", encoding="utf-8")
        deadline = time.monotonic() + 10
        while not release.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("parent did not release lock holder")
            time.sleep(0.01)
finally:
    guard.finalize_pytest_duckdb_guard()
'''
    holder: subprocess.Popen[str] | None = None
    stdout = ""
    stderr = ""
    actual_acquire = driver.acquire_lock
    open_attempts: list[tuple[object, dict[str, object]]] = []

    @contextmanager
    def short_acquire(definition, *args, **kwargs):
        kwargs["timeout_seconds"] = 0.1
        with actual_acquire(definition, *args, **kwargs) as value:
            yield value

    @contextmanager
    def forbid_read(*args, **kwargs):
        open_attempts.append((args, kwargs))
        raise AssertionError("native open must not run after path admission timeout")
        yield  # pragma: no cover

    monkeypatch.setattr(driver, "acquire_lock", short_acquire)
    monkeypatch.setattr(driver, "read_only_connection", forbid_read)
    try:
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                holder_code,
                os.fspath(tmp_path),
                os.fspath(active),
                os.fspath(ready),
                os.fspath(release),
            ],
            cwd=_REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 5
        while not ready.exists():
            if holder.poll() is not None:
                stdout, stderr = holder.communicate(timeout=1)
                raise AssertionError(f"lock holder exited early: stdout={stdout}\nstderr={stderr}")
            if time.monotonic() >= deadline:
                raise AssertionError("timed out waiting for lock holder")
            time.sleep(0.01)
        with pytest.raises(TimeoutError, match="Timed out acquiring lock"):
            driver.inspect_livermore_daily_refresh_state(
                duckdb_path=active,
                target_date="2026-09-15",
            )
    finally:
        release.write_text("release", encoding="utf-8")
        if holder is not None:
            try:
                stdout, stderr = holder.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                holder.terminate()
                try:
                    stdout, stderr = holder.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    holder.kill()
                    stdout, stderr = holder.communicate(timeout=5)

    assert holder is not None
    assert holder.returncode == 0, f"stdout={stdout}\nstderr={stderr}"
    assert open_attempts == []


def _stock_limit_writer_child_code() -> str:
    return r'''
import json
import os
import sys
import time
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
database = Path(sys.argv[2]).resolve()
events_path = Path(sys.argv[3]).resolve()
release_path = Path(sys.argv[4]).resolve()
result_path = Path(sys.argv[5]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.set_pytest_duckdb_guard_phase("pretrade-stock-limit-writer-child")

def emit(name, **details):
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": name, **details}, sort_keys=True) + "\n")
        handle.flush()

try:
    import requests

    http_calls = []

    class UnexpectedHttpRequest(BaseException):
        pass

    def forbid_http_request(_session, *args, **kwargs):
        method = kwargs.get("method", args[0] if args else None)
        url = kwargs.get("url", args[1] if len(args) > 1 else None)
        http_calls.append([method, url])
        raise UnexpectedHttpRequest("HTTP is forbidden in this writer child.")

    requests.Session.request = forbid_http_request
    import backend.app.tasks.stock_limit_price_ingest as task

    actual_connect = task.duckdb.connect
    actual_replace = task._replace_rows_by_date
    foreign_database_attempts = []

    class UnexpectedDatabaseDestination(BaseException):
        pass

    def observed_connect(*args, **kwargs):
        raw_database = args[0] if args else kwargs.get("database")
        requested_database = Path(os.fspath(raw_database)).resolve()
        if requested_database != database:
            foreign_database_attempts.append(os.fspath(requested_database))
            raise UnexpectedDatabaseDestination(
                f"Unexpected database destination: {requested_database}"
            )
        return actual_connect(*args, **kwargs)

    def paused_replace(conn, rows_by_date, *, run_id):
        emit("writer-holding")
        deadline = time.monotonic() + 15
        while not release_path.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("parent did not release stock-limit writer")
            time.sleep(0.01)
        return actual_replace(conn, rows_by_date, run_id=run_id)

    class FakeVendor:
        def stk_limit(self, *, trade_date, fields):
            assert trade_date == "20260915"
            assert fields == task.TUSHARE_STK_LIMIT_FIELDS
            emit("supplier-complete")
            return [
                {
                    "trade_date": "20260915",
                    "ts_code": "000001.SZ",
                    "pre_close": 10.0,
                    "up_limit": 11.0,
                    "down_limit": 9.0,
                }
            ]

    task.duckdb.connect = observed_connect
    task._replace_rows_by_date = paused_replace
    result = task.ingest_stock_limit_prices(
        duckdb_path=os.fspath(database),
        start_date="2026-09-15",
        client=FakeVendor(),
        retry_sleep_seconds=0.0,
        require_observation_coverage=True,
        run_id="pretrade-writer-concurrency",
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
        json.dumps(
            {
                "result": result,
                "producer_http_call_count": producer_http_call_count,
                "producer_foreign_database_count": producer_foreign_database_count,
                "http_self_check_count": len(http_calls),
                "database_self_check_count": len(foreign_database_attempts),
            },
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
except BaseException as exc:
    emit("writer-error", error_class=type(exc).__name__, error=str(exc))
    raise
finally:
    guard.finalize_pytest_duckdb_guard()
'''


def test_inspector_waits_while_stock_limit_writer_holds_native_connection(tmp_path: Path) -> None:
    database = tmp_path / "active" / "livermore.duckdb"
    _create_factor_database(database, row_count=1)
    with duckdb.connect(os.fspath(database), read_only=False) as conn:
        conn.execute(
            "create table choice_stock_daily_observation (trade_date date, stock_code varchar)"
        )
        conn.execute(
            "insert into choice_stock_daily_observation values ('2026-09-15', '000001.SZ')"
        )
    writer_events = tmp_path / "writer-events.jsonl"
    writer_release = tmp_path / "writer-release"
    writer_result = tmp_path / "writer-result.json"
    inspector_events = tmp_path / "inspector-events.jsonl"
    inspector_result = tmp_path / "inspector-result.json"
    writer: subprocess.Popen[str] | None = None
    inspector: subprocess.Popen[str] | None = None
    writer_stdout = ""
    writer_stderr = ""
    inspector_stdout = ""
    inspector_stderr = ""
    try:
        writer = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _stock_limit_writer_child_code(),
                os.fspath(tmp_path),
                os.fspath(database),
                os.fspath(writer_events),
                os.fspath(writer_release),
                os.fspath(writer_result),
            ],
            cwd=_REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_event(writer_events, "writer-holding")
        inspector = subprocess.Popen(
            [
                sys.executable,
                "-c",
                _inspector_child_code(),
                os.fspath(tmp_path),
                os.fspath(database),
                os.fspath(inspector_events),
                os.fspath(inspector_result),
            ],
            cwd=_REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_event(inspector_events, "path-attempt")
        assert [str(event["event"]) for event in _read_events(inspector_events)] == [
            "path-attempt"
        ]
        assert writer.poll() is None
        assert inspector.poll() is None
    finally:
        writer_release.write_text("release", encoding="utf-8")
        if writer is not None:
            try:
                writer_stdout, writer_stderr = writer.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                writer.terminate()
                try:
                    writer_stdout, writer_stderr = writer.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    writer.kill()
                    writer_stdout, writer_stderr = writer.communicate(timeout=5)
        if inspector is not None:
            try:
                inspector_stdout, inspector_stderr = inspector.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                inspector.terminate()
                try:
                    inspector_stdout, inspector_stderr = inspector.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    inspector.kill()
                    inspector_stdout, inspector_stderr = inspector.communicate(timeout=5)

    assert writer is not None
    assert inspector is not None
    assert writer.returncode == 0, (
        f"stdout={writer_stdout}\nstderr={writer_stderr}\nevents={_read_events(writer_events)}"
    )
    assert inspector.returncode == 0, (
        f"stdout={inspector_stdout}\nstderr={inspector_stderr}"
        f"\nevents={_read_events(inspector_events)}"
    )
    assert [str(event["event"]) for event in _read_events(inspector_events)] == [
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
    ]
    writer_payload = json.loads(writer_result.read_text(encoding="utf-8"))
    assert writer_payload["result"]["status"] == "completed"
    assert writer_payload["producer_http_call_count"] == 0
    assert writer_payload["producer_foreign_database_count"] == 0
    assert writer_payload["http_self_check_count"] == 1
    assert writer_payload["database_self_check_count"] == 1
