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
import requests

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.tasks import stock_limit_price_ingest as task

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_market_data,
]

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TRADE_DATE = "2026-09-15"


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


def _bootstrap_database(database: Path) -> None:
    with duckdb.connect(os.fspath(database), read_only=False) as conn:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date date not null,
              stock_code varchar not null
            )
            """
        )
        task.ensure_stock_limit_price_daily_schema(conn)
        conn.execute(
            """
            insert into stock_limit_price_daily values
              ('2026-09-14', '000001.SZ', 10.5, 8.5, 9.5,
               'control-source', 'vv_tushare_stk_limit_20260914_aaaaaaaaaaaa',
               'control-rule', 'control-run')
            """
        )
        conn.execute(
            """
            insert into choice_stock_daily_observation values
              ('2026-09-15', '000001.SZ'),
              ('2026-09-15', '600000.SH'),
              ('2026-09-14', 'CONTROL.SH')
            """
        )


def _strict_writer_child_code() -> str:
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
guard.set_pytest_duckdb_guard_phase("stock-limit-writer-child")

def emit(name, **details):
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": name, **details}, sort_keys=True) + "\n")
        handle.flush()

try:
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
        raise UnexpectedHttpRequest("HTTP is forbidden in this writer child.")

    requests.Session.request = forbid_http_request
    import backend.app.tasks.stock_limit_price_ingest as task

    actual_acquire = task.acquire_lock
    actual_connect = task.duckdb.connect

    @contextmanager
    def observed_acquire(definition, *args, **kwargs):
        kind = "path" if definition.key.startswith("lock:duckdb:materialize:") else "limit"
        emit(f"{kind}-attempt", key=definition.key)
        try:
            with actual_acquire(definition, *args, **kwargs) as value:
                emit(f"{kind}-entered", key=definition.key)
                yield value
        finally:
            emit(f"{kind}-released", key=definition.key)

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
                },
                {
                    "trade_date": "20260915",
                    "ts_code": "600000.SH",
                    "pre_close": 8.0,
                    "up_limit": 8.8,
                    "down_limit": 7.2,
                },
            ]

    task.acquire_lock = observed_acquire
    task.duckdb.connect = observed_connect
    result = task.ingest_stock_limit_prices(
        duckdb_path=os.fspath(database),
        start_date="2026-09-15",
        client=FakeVendor(),
        retry_sleep_seconds=0.0,
        require_observation_coverage=True,
        run_id="writer-admission-test",
    )
    producer_http_call_count = len(http_calls)
    producer_foreign_database_count = len(foreign_database_attempts)
    try:
        requests.Session().request(
            method="GET",
            url="https://guard-self-check.invalid/",
        )
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


def test_strict_writer_waits_at_path_admission_before_native_open(tmp_path: Path) -> None:
    database = tmp_path / "stock-limit.duckdb"
    events_path = tmp_path / "child-events.jsonl"
    result_path = tmp_path / "child-result.json"
    _bootstrap_database(database)

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
        reader = duckdb.connect(os.fspath(database), read_only=True)
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
    assert child.returncode == 0, f"stdout={stdout}\nstderr={stderr}\nevents={_read_events(events_path)}"
    assert [str(event["event"]) for event in _read_events(events_path)] == [
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
        "supplier-complete",
        "path-attempt",
        "path-entered",
        "limit-attempt",
        "limit-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "limit-released",
        "path-released",
    ]
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["result"]["status"] == "completed"
    assert payload["result"]["inserted_row_count"] == 2
    assert payload["producer_http_call_count"] == 0
    assert payload["producer_foreign_database_count"] == 0
    assert payload["http_self_check_count"] == 1
    assert payload["database_self_check_count"] == 1
    with duckdb.connect(os.fspath(database), read_only=True) as conn:
        assert conn.execute(
            """
            select stock_code, up_limit, down_limit, typeof(up_limit), typeof(down_limit)
            from stock_limit_price_daily
            where trade_date = '2026-09-15'
            order by stock_code
            """
        ).fetchall() == [
            ("000001.SZ", 11.0, 9.0, "DOUBLE", "DOUBLE"),
            ("600000.SH", 8.8, 7.2, "DOUBLE", "DOUBLE"),
        ]
        assert conn.execute(
            """
            select trade_date, stock_code, up_limit, down_limit, run_id
            from stock_limit_price_daily
            where trade_date = '2026-09-14'
            """
        ).fetchall() == [("2026-09-14", "000001.SZ", 10.5, 8.5, "control-run")]
        assert conn.execute(
            """
            select stock_code from choice_stock_daily_observation
            where trade_date = '2026-09-14'
            """
        ).fetchall() == [("CONTROL.SH",)]


class _UnexpectedHttpRequest(BaseException):
    pass


class _UnexpectedDatabaseDestination(BaseException):
    pass


def _install_http_sentinel(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, object]]:
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
    fail_target_insert: bool = False,
) -> tuple[list[str], list[Path], object]:
    events: list[str] = []
    foreign_database_attempts: list[Path] = []
    actual_acquire = task.acquire_lock
    actual_connect = task.duckdb.connect

    @contextmanager
    def observed_acquire(definition, *args, **kwargs):
        kind = "path" if definition.key.startswith("lock:duckdb:materialize:") else "limit"
        events.append(f"{kind}-attempt")
        try:
            with actual_acquire(definition, *args, **kwargs) as value:
                events.append(f"{kind}-entered")
                yield value
        finally:
            events.append(f"{kind}-released")

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
            events.append("native-closed")
            return result

        def executemany(self, query, parameters):
            if fail_target_insert and "insert into stock_limit_price_daily" in str(query).lower():
                events.append("transaction-failed")
                raise RuntimeError("synthetic transaction failure")
            return self._connection.executemany(query, parameters)

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
        events.append("native-opened")
        return ObservedConnection(connection)

    monkeypatch.setattr(task, "acquire_lock", observed_acquire)
    monkeypatch.setattr(task.duckdb, "connect", observed_connect)
    return events, foreign_database_attempts, actual_connect


class _FakeVendor:
    def __init__(
        self,
        rows: list[dict[str, object]],
        *,
        events: list[str] | None = None,
    ) -> None:
        self._rows = rows
        self._events = events
        self.calls = 0

    def stk_limit(self, *, trade_date: str, fields: str) -> list[dict[str, object]]:
        assert trade_date == "20260915"
        assert fields == task.TUSHARE_STK_LIMIT_FIELDS
        self.calls += 1
        if self._events is not None:
            self._events.append("supplier-complete")
        return list(self._rows)


def _valid_vendor_rows() -> list[dict[str, object]]:
    return [
        {
            "trade_date": "20260915",
            "ts_code": "000001.SZ",
            "pre_close": 10.0,
            "up_limit": 11.0,
            "down_limit": 9.0,
        },
        {
            "trade_date": "20260915",
            "ts_code": "600000.SH",
            "pre_close": 8.0,
            "up_limit": 8.8,
            "down_limit": 7.2,
        },
    ]


def _assert_another_process_can_acquire_path_lock(
    *,
    tmp_path: Path,
    database: Path,
    marker_name: str,
) -> None:
    marker = tmp_path / marker_name
    code = r'''
import json
import os
import sys
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
database = Path(sys.argv[2]).resolve()
marker = Path(sys.argv[3]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.set_pytest_duckdb_guard_phase("stock-limit-lock-probe-child")
try:
    import duckdb
    import requests

    http_calls = []
    database_calls = []

    class UnexpectedHttpRequest(BaseException):
        pass

    class UnexpectedDatabaseOpen(BaseException):
        pass

    def forbid_http_request(_session, *args, **kwargs):
        method = kwargs.get("method", args[0] if args else None)
        url = kwargs.get("url", args[1] if len(args) > 1 else None)
        http_calls.append([method, url])
        raise UnexpectedHttpRequest("HTTP is forbidden in the lock probe child.")

    def forbid_database_open(*args, **kwargs):
        raw_database = args[0] if args else kwargs.get("database")
        database_calls.append(os.fspath(raw_database))
        raise UnexpectedDatabaseOpen("Database opens are forbidden in the lock probe child.")

    requests.Session.request = forbid_http_request
    duckdb.connect = forbid_database_open
    from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock

    with acquire_lock(
        resolve_duckdb_writer_lock(database),
        base_dir=database.parent,
        timeout_seconds=2,
    ):
        producer_http_call_count = len(http_calls)
        producer_database_call_count = len(database_calls)
    try:
        requests.Session().request(method="GET", url="https://guard-self-check.invalid/")
    except UnexpectedHttpRequest:
        pass
    else:
        raise AssertionError("HTTP sentinel self-check did not block the request.")
    try:
        duckdb.connect(os.fspath(owned_root / "foreign.duckdb"))
    except UnexpectedDatabaseOpen:
        pass
    else:
        raise AssertionError("Database sentinel self-check did not block the open.")
    marker.write_text(
        json.dumps(
            {
                "acquired": True,
                "producer_http_call_count": producer_http_call_count,
                "producer_database_call_count": producer_database_call_count,
                "http_self_check_count": len(http_calls),
                "database_self_check_count": len(database_calls),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
finally:
    guard.finalize_pytest_duckdb_guard()
'''
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            os.fspath(tmp_path),
            os.fspath(database),
            os.fspath(marker),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, f"stdout={completed.stdout}\nstderr={completed.stderr}"
    assert json.loads(marker.read_text(encoding="utf-8")) == {
        "acquired": True,
        "database_self_check_count": 1,
        "http_self_check_count": 1,
        "producer_database_call_count": 0,
        "producer_http_call_count": 0,
    }


def test_transaction_failure_rolls_back_closes_and_releases_path_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "stock-limit-rollback.duckdb"
    _bootstrap_database(database)
    with duckdb.connect(os.fspath(database), read_only=False) as conn:
        conn.execute(
            """
            insert into stock_limit_price_daily values
              ('2026-09-15', '000001.SZ', 12.1, 9.9, 11.0,
               'old-target-source', 'vv_tushare_stk_limit_20260915_aaaaaaaaaaaa',
               'old-target-rule', 'old-target-run')
            """
        )
        before_rows = conn.execute("select * from stock_limit_price_daily order by all").fetchall()
    http_calls = _install_http_sentinel(monkeypatch)
    events, foreign_attempts, actual_connect = _install_admission_observers(
        monkeypatch,
        database=database,
        fail_target_insert=True,
    )
    vendor = _FakeVendor(_valid_vendor_rows(), events=events)

    with pytest.raises(RuntimeError, match="synthetic transaction failure"):
        task.ingest_stock_limit_prices(
            duckdb_path=database,
            start_date=_TRADE_DATE,
            client=vendor,
            retry_sleep_seconds=0.0,
            require_observation_coverage=True,
            run_id="transaction-failure-test",
        )

    assert events == [
        "path-attempt",
        "path-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "path-released",
        "supplier-complete",
        "path-attempt",
        "path-entered",
        "limit-attempt",
        "limit-entered",
        "native-open-attempt",
        "native-opened",
        "transaction-failed",
        "native-closed",
        "limit-released",
        "path-released",
    ]
    assert foreign_attempts == []
    assert vendor.calls == 1
    with actual_connect(os.fspath(database), read_only=True) as conn:
        assert conn.execute("select * from stock_limit_price_daily order by all").fetchall() == before_rows
    _assert_another_process_can_acquire_path_lock(
        tmp_path=tmp_path,
        database=database,
        marker_name="rollback-lock-probe.json",
    )
    _assert_http_sentinel_wired(http_calls)


@pytest.mark.parametrize("failed_lock", ["path", "limit"])
def test_lock_failure_does_not_open_database_or_leak_path_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_lock: str,
) -> None:
    database = tmp_path / f"stock-limit-{failed_lock}-failure.duckdb"
    _bootstrap_database(database)
    http_calls = _install_http_sentinel(monkeypatch)
    actual_acquire = task.acquire_lock
    connect_attempts: list[tuple[object, dict[str, object]]] = []
    events: list[str] = []

    @contextmanager
    def failing_acquire(definition, *args, **kwargs):
        kind = "path" if definition.key.startswith("lock:duckdb:materialize:") else "limit"
        events.append(f"{kind}-attempt")
        entered = False
        try:
            with actual_acquire(definition, *args, **{**kwargs, "timeout_seconds": .05}) as value:
                entered = True
                events.append(f"{kind}-entered")
                yield value
        finally:
            if entered:
                events.append(f"{kind}-released")

    def forbid_database_open(*args, **kwargs):
        connect_attempts.append((args[0] if args else kwargs.get("database"), kwargs))
        raise _UnexpectedDatabaseDestination("database must not open after admission failure")

    monkeypatch.setattr(task, "acquire_lock", failing_acquire)
    monkeypatch.setattr(task.duckdb, "connect", forbid_database_open)
    vendor = _FakeVendor(_valid_vendor_rows(), events=events)
    blocked_definition = (
        resolve_duckdb_writer_lock(database) if failed_lock == "path" else task.STOCK_LIMIT_PRICE_LOCK
    )
    with actual_acquire(blocked_definition, base_dir=database.parent):
        with pytest.raises(TimeoutError, match="Timed out acquiring lock"):
            task.ingest_stock_limit_prices(
                duckdb_path=database,
                start_date=_TRADE_DATE,
                client=vendor,
                retry_sleep_seconds=0.0,
                run_id=f"{failed_lock}-failure-test",
            )

    expected_events = ["supplier-complete", "path-attempt"]
    if failed_lock == "limit":
        expected_events.extend(["path-entered", "limit-attempt", "path-released"])
    assert events == expected_events
    assert connect_attempts == []
    assert vendor.calls == 1
    _assert_another_process_can_acquire_path_lock(
        tmp_path=tmp_path,
        database=database,
        marker_name=f"{failed_lock}-failure-lock-probe.json",
    )
    _assert_http_sentinel_wired(http_calls)


@pytest.mark.parametrize("mode", ["dry_run", "empty"])
def test_read_only_phases_close_before_releasing_path_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    database = tmp_path / f"stock-limit-{mode}.duckdb"
    _bootstrap_database(database)
    http_calls = _install_http_sentinel(monkeypatch)
    events, foreign_attempts, _actual_connect = _install_admission_observers(
        monkeypatch,
        database=database,
    )
    vendor = _FakeVendor([], events=events)

    if mode == "dry_run":
        result = task.ingest_stock_limit_prices(
            duckdb_path=database,
            start_date=_TRADE_DATE,
            client=vendor,
            dry_run=True,
            require_observation_coverage=True,
        )
        assert result["status"] == "dry_run"
        assert vendor.calls == 0
        expected_events = [
            "path-attempt",
            "path-entered",
            "native-open-attempt",
            "native-opened",
            "native-closed",
            "path-released",
            "path-attempt",
            "path-entered",
            "native-open-attempt",
            "native-opened",
            "native-closed",
            "path-released",
        ]
    else:
        result = task.ingest_stock_limit_prices(
            duckdb_path=database,
            start_date=_TRADE_DATE,
            client=vendor,
            retry_sleep_seconds=0.0,
        )
        assert result["status"] == "completed_with_warnings"
        assert result["empty_trade_date_count"] == 1
        assert vendor.calls == 1
        expected_events = [
            "supplier-complete",
            "path-attempt",
            "path-entered",
            "native-open-attempt",
            "native-opened",
            "native-closed",
            "path-released",
        ]

    assert events == expected_events
    assert foreign_attempts == []
    _assert_http_sentinel_wired(http_calls)
