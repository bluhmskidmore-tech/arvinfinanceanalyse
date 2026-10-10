from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pandas as pd
import pytest

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.tasks import choice_macro

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_data,
]

_REPORT_DATE = "2026-09-15"
_REPO_ROOT = Path(__file__).resolve().parents[1]


class _UnexpectedHttpRequest(BaseException):
    pass


class _UnexpectedDatabaseDestination(BaseException):
    pass


def _install_http_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[object, object]]:
    calls: list[tuple[object, object]] = []

    def forbid_http_request(_session, *args, **kwargs):
        method = kwargs.get("method", args[0] if args else None)
        url = kwargs.get("url", args[1] if len(args) > 1 else None)
        calls.append((method, url))
        raise _UnexpectedHttpRequest("HTTP is forbidden in this isolated writer test.")

    monkeypatch.setattr(choice_macro.requests.Session, "request", forbid_http_request)
    return calls


def _assert_http_sentinel_wired(calls: list[tuple[object, object]]) -> None:
    assert calls == []
    with pytest.raises(_UnexpectedHttpRequest):
        choice_macro.requests.Session().request(
            method="GET",
            url="https://guard-self-check.invalid/",
        )
    assert calls == [("GET", "https://guard-self-check.invalid/")]


def _assert_database_destination_sentinel_wired(
    *,
    attempts: list[Path],
    foreign_database: Path,
) -> None:
    assert attempts == []
    with pytest.raises(_UnexpectedDatabaseDestination):
        choice_macro.duckdb.connect(os.fspath(foreign_database))
    assert attempts == [foreign_database.resolve()]


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
    raise AssertionError(f"Timed out waiting for child event {name}: {_read_events(path)}")


def _child_code() -> str:
    return r'''
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
database = Path(sys.argv[2]).resolve()
events_path = Path(sys.argv[3]).resolve()
result_path = Path(sys.argv[4]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.set_pytest_duckdb_guard_phase("macro-writer-child")

def emit(name, **details):
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": name, **details}, sort_keys=True) + "\n")
        handle.flush()

try:
    import pandas as pd
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
    import backend.app.tasks.choice_macro as task

    actual_acquire = task.acquire_lock
    actual_connect = task.duckdb.connect
    foreign_database_attempts = []

    class UnexpectedDatabaseDestination(BaseException):
        pass

    @contextmanager
    def observed_acquire(definition, *args, **kwargs):
        kind = "path" if definition.key.startswith("lock:duckdb:materialize:") else "macro"
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

    calls = []

    def index_daily(**kwargs):
        calls.append(["index_daily", kwargs])
        return pd.DataFrame([
            {
                "ts_code": "000300.SH",
                "trade_date": "20260915",
                "close": 4500.0,
                "pct_chg": -1.25,
            }
        ])

    def index_dailybasic(**kwargs):
        calls.append(["index_dailybasic", kwargs])
        emit("supplier-complete")
        return pd.DataFrame([
            {"ts_code": "000300.SH", "trade_date": "20260915", "pe": 14.5}
        ])

    pro = SimpleNamespace(index_daily=index_daily, index_dailybasic=index_dailybasic)
    task.acquire_lock = observed_acquire
    task.duckdb.connect = observed_connect
    task.resolve_tushare_token_with_settings_fallback = lambda _settings: "synthetic-token"
    task.import_tushare_pro = lambda: SimpleNamespace(pro_api=lambda _token: pro)
    task._load_public_cross_asset_history_rows = lambda **_kwargs: (_ for _ in ()).throw(
        AssertionError("broad source loader must not run in CSI300 scope")
    )

    result = task.refresh_public_cross_asset_headlines(
        duckdb_path=os.fspath(database),
        report_date="2026-09-15",
        csi300_only=True,
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
                "calls": calls,
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


def _install_admission_event_recorders(
    monkeypatch: pytest.MonkeyPatch,
    *,
    expected_database: Path,
) -> tuple[list[str], list[Path]]:
    events: list[str] = []
    foreign_database_attempts: list[Path] = []
    actual_acquire = choice_macro.acquire_lock
    actual_connect = choice_macro.duckdb.connect

    @contextmanager
    def observed_acquire(definition, *args, **kwargs):
        kind = (
            "path"
            if definition.key.startswith("lock:duckdb:materialize:")
            else "macro"
        )
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

    def observed_connect(*args, **kwargs):
        raw_database = args[0] if args else kwargs.get("database")
        requested_database = Path(os.fspath(raw_database)).resolve()
        if requested_database != expected_database.resolve():
            foreign_database_attempts.append(requested_database)
            raise _UnexpectedDatabaseDestination(
                f"Unexpected database destination: {requested_database}"
            )
        events.append("native-open-attempt")
        connection = actual_connect(*args, **kwargs)
        events.append("native-opened")
        return ObservedConnection(connection)

    monkeypatch.setattr(choice_macro, "acquire_lock", observed_acquire)
    monkeypatch.setattr(choice_macro.duckdb, "connect", observed_connect)
    return events, foreign_database_attempts


def _install_csi300_source(
    monkeypatch: pytest.MonkeyPatch,
    *,
    events: list[str] | None = None,
) -> None:
    daily = [{"ts_code": "000300.SH", "trade_date": "20260915", "close": 4500.0, "pct_chg": -1.25}]
    basic = [{"ts_code": "000300.SH", "trade_date": "20260915", "pe": 14.5}]

    def index_daily(**_kwargs):
        return pd.DataFrame(daily)

    def index_dailybasic(**_kwargs):
        if events is not None:
            events.append("supplier-complete")
        return pd.DataFrame(basic)

    pro = SimpleNamespace(
        index_daily=index_daily,
        index_dailybasic=index_dailybasic,
    )
    monkeypatch.setattr(
        choice_macro,
        "resolve_tushare_token_with_settings_fallback",
        lambda _settings: "synthetic-token",
    )
    monkeypatch.setattr(
        choice_macro,
        "import_tushare_pro",
        lambda: SimpleNamespace(pro_api=lambda _token: pro),
    )
    monkeypatch.setattr(
        choice_macro,
        "_load_public_cross_asset_history_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("broad source loader must not run in CSI300 scope")
        ),
    )


def _run_csi300_writer(database: Path) -> dict[str, object]:
    return choice_macro.refresh_public_cross_asset_headlines(
        duckdb_path=os.fspath(database),
        report_date=_REPORT_DATE,
        csi300_only=True,
    )


def _bootstrap_database(database: Path) -> None:
    with duckdb.connect(os.fspath(database), read_only=False) as conn:
        choice_macro._ensure_tables(conn)


def _snapshot_writer_tables(database: Path) -> dict[str, list[tuple[object, ...]]]:
    tables = (
        "fact_choice_macro_daily",
        "choice_market_snapshot",
        "phase1_macro_vendor_catalog",
        "market_data_series_category",
    )
    with duckdb.connect(os.fspath(database), read_only=True) as conn:
        return {
            table: conn.execute(f"select * from {table} order by all").fetchall()
            for table in tables
        }


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
guard.set_pytest_duckdb_guard_phase("macro-lock-probe-child")
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
        cwd=os.fspath(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, (
        f"stdout={completed.stdout}\nstderr={completed.stderr}"
    )
    payload = json.loads(marker.read_text(encoding="utf-8"))
    assert payload == {
        "acquired": True,
        "database_self_check_count": 1,
        "http_self_check_count": 1,
        "producer_database_call_count": 0,
        "producer_http_call_count": 0,
    }


def _install_choice_snapshot_source(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tmp_path: Path,
    events: list[str],
) -> None:
    series = choice_macro.ChoiceMacroSeriesConfig(
        series_id="SYNTHETIC.CHOICE",
        series_name="Synthetic Choice",
        vendor_series_code="SYNTHETIC001",
        frequency="daily",
        unit="index",
        theme="synthetic",
        is_core=False,
    )
    batch = choice_macro.ChoiceMacroBatchConfig(
        batch_id="synthetic_batch",
        request_options="IsLatest=0,StartDate=2026-09-15,EndDate=2026-09-15",
        series=[series],
        catalog_version="synthetic_v1",
    )
    snapshot = choice_macro.ChoiceMacroSnapshot.model_validate(
        {
            "vendor_name": "choice",
            "vendor_version": "synthetic-choice-vendor",
            "captured_at": datetime(2026, 9, 15, 8, 0, tzinfo=UTC),
            "series": [
                {
                    "series_id": series.series_id,
                    "series_name": series.series_name,
                    "vendor_series_code": series.vendor_series_code,
                    "vendor_name": "choice",
                    "trade_date": _REPORT_DATE,
                    "value_numeric": 42.0,
                    "frequency": series.frequency,
                    "unit": series.unit,
                    "vendor_version": "synthetic-choice-vendor",
                }
            ],
            "raw_payload": {"series": [series.series_id]},
        }
    )
    settings = SimpleNamespace(
        choice_timeout_seconds=5.0,
        minio_endpoint="",
        minio_access_key="",
        minio_secret_key="",
        minio_bucket="synthetic",
        object_store_mode="local",
        local_archive_path=tmp_path / "archive",
    )
    monkeypatch.setattr(choice_macro, "_init_runtime", lambda: None)
    monkeypatch.setattr(choice_macro, "get_settings", lambda: settings)
    monkeypatch.setattr(choice_macro, "load_choice_macro_batches", lambda _settings: [batch])

    def fetch_macro_snapshot(_self, series, **_kwargs):
        assert [item.series_id for item in series] == ["SYNTHETIC.CHOICE"]
        events.append("supplier-complete")
        return snapshot

    monkeypatch.setattr(
        choice_macro.VendorAdapter,
        "fetch_macro_snapshot",
        fetch_macro_snapshot,
    )


def _run_choice_snapshot_writer(database: Path, tmp_path: Path) -> dict[str, object]:
    return choice_macro._refresh_choice_macro_snapshot(
        duckdb_path=os.fspath(database),
        governance_dir=os.fspath(tmp_path / "governance"),
        batch_ids=["synthetic_batch"],
        run_id="synthetic-choice-writer",
    )


def _install_ncd_source(
    monkeypatch: pytest.MonkeyPatch,
    *,
    events: list[str],
) -> None:
    rows = [
        choice_macro._public_history_row(
            str(meta["series_id"]),
            _REPORT_DATE,
            float(index + 1),
            "synthetic-ncd-vendor",
            "synthetic-ncd-source",
        )
        for index, meta in enumerate(choice_macro.NCD_SHIBOR_TENORS.values())
    ]
    monkeypatch.setattr(choice_macro, "get_settings", lambda: SimpleNamespace())

    def fetch_history_rows(**_kwargs):
        events.append("supplier-complete")
        return rows

    monkeypatch.setattr(
        choice_macro,
        "_fetch_tushare_ncd_shibor_history_rows",
        fetch_history_rows,
    )


def _run_ncd_writer(database: Path) -> dict[str, object]:
    return choice_macro.refresh_tushare_ncd_shibor_proxy(
        duckdb_path=os.fspath(database),
        report_date=_REPORT_DATE,
    )


@pytest.mark.parametrize("writer", ("choice", "ncd"))
def test_other_macro_writers_hold_path_then_macro_through_native_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    writer: str,
) -> None:
    database = tmp_path / f"{writer}.duckdb"
    _bootstrap_database(database)
    events, foreign_database_attempts = _install_admission_event_recorders(
        monkeypatch,
        expected_database=database,
    )
    http_calls = _install_http_sentinel(monkeypatch)
    if writer == "choice":
        _install_choice_snapshot_source(
            monkeypatch,
            tmp_path=tmp_path,
            events=events,
        )
    else:
        _install_ncd_source(monkeypatch, events=events)

    result = (
        _run_choice_snapshot_writer(database, tmp_path)
        if writer == "choice"
        else _run_ncd_writer(database)
    )

    assert result["status"] == "completed"
    assert events[:10] == [
        "supplier-complete",
        "path-attempt",
        "path-entered",
        "macro-attempt",
        "macro-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "macro-released",
        "path-released",
    ]
    with duckdb.connect(os.fspath(database), read_only=True) as conn:
        if writer == "choice":
            rows = conn.execute(
                """
                select series_id, trade_date, value_numeric
                from fact_choice_macro_daily
                where series_id = 'SYNTHETIC.CHOICE'
                """
            ).fetchall()
            assert rows == [("SYNTHETIC.CHOICE", _REPORT_DATE, 42.0)]
        else:
            rows = conn.execute(
                """
                select series_id, trade_date, value_numeric
                from fact_choice_macro_daily
                order by series_id
                """
            ).fetchall()
            expected = sorted(
                (
                    str(meta["series_id"]),
                    _REPORT_DATE,
                    float(index + 1),
                )
                for index, meta in enumerate(choice_macro.NCD_SHIBOR_TENORS.values())
            )
            assert rows == expected

    _assert_http_sentinel_wired(http_calls)
    _assert_database_destination_sentinel_wired(
        attempts=foreign_database_attempts,
        foreign_database=tmp_path / "foreign.duckdb",
    )


def test_csi300_writer_waits_at_path_admission_before_native_open(
    tmp_path: Path,
) -> None:
    database = tmp_path / "macro.duckdb"
    events_path = tmp_path / "child-events.jsonl"
    result_path = tmp_path / "child-result.json"
    child_trace = tmp_path / "pytest-duckdb-guard-attempts.jsonl"
    with duckdb.connect(os.fspath(database), read_only=False) as conn:
        choice_macro._ensure_tables(conn)
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('CONTROL.UNRELATED', 'Control', '2026-09-14', 7.0, 'daily', 'index',
             'synthetic', 'control-source', 'control-vendor', 'control-rule', 'control-run')
            """
        )

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
                _child_code(),
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
        _wait_for_event(events_path, "supplier-complete")
        _wait_for_event(events_path, "path-attempt")
        held_events = [str(event["event"]) for event in _read_events(events_path)]
        assert held_events == ["supplier-complete", "path-attempt"]
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
    assert child.poll() is not None
    assert child.returncode == 0, f"stdout={stdout}\nstderr={stderr}\nevents={_read_events(events_path)}"
    assert [str(event["event"]) for event in _read_events(events_path)] == [
        "supplier-complete",
        "path-attempt",
        "path-entered",
        "macro-attempt",
        "macro-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "macro-released",
        "path-released",
    ]
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["result"]["status"] == "completed"
    assert payload["producer_http_call_count"] == 0
    assert payload["producer_foreign_database_count"] == 0
    assert payload["http_self_check_count"] == 1
    assert payload["database_self_check_count"] == 1
    assert [call[0] for call in payload["calls"]] == [
        "index_daily",
        "index_dailybasic",
    ]
    with duckdb.connect(os.fspath(database), read_only=True) as conn:
        rows = conn.execute(
            """
            select series_id, trade_date, value_numeric
            from fact_choice_macro_daily
            order by series_id
            """
        ).fetchall()
    assert rows == [
        ("CA.CSI300", _REPORT_DATE, 4500.0),
        ("CA.CSI300_PCT_CHG", _REPORT_DATE, -1.25),
        ("CA.CSI300_PE", _REPORT_DATE, 14.5),
        ("CONTROL.UNRELATED", "2026-09-14", 7.0),
    ]
    attempts = [
        json.loads(line)
        for line in child_trace.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    writer_attempts = [
        attempt
        for attempt in attempts
        if attempt["canonical_path"] == str(database.resolve())
    ]
    assert len(writer_attempts) == 1
    assert writer_attempts[0]["phase"] == "macro-writer-child"
    assert writer_attempts[0]["decision"] == "allow"
    assert writer_attempts[0]["access"] == "read_write_or_default"


def test_csi300_transaction_failure_rolls_back_and_releases_path_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "rollback.duckdb"
    _bootstrap_database(database)
    with duckdb.connect(os.fspath(database), read_only=False) as conn:
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('CONTROL.UNRELATED', 'Control', '2026-09-14', 7.0, 'daily', 'index',
             'control-vendor', 'control-version', 'control-source', 'control-run', current_timestamp)
            """
        )
    before = _snapshot_writer_tables(database)
    events, foreign_database_attempts = _install_admission_event_recorders(
        monkeypatch,
        expected_database=database,
    )
    http_calls = _install_http_sentinel(monkeypatch)
    _install_csi300_source(monkeypatch, events=events)

    def fail_after_transaction_writes(*_args, **_kwargs):
        raise RuntimeError("synthetic transaction failure")

    monkeypatch.setattr(
        choice_macro,
        "_insert_market_data_series_category",
        fail_after_transaction_writes,
    )

    with pytest.raises(RuntimeError, match="synthetic transaction failure"):
        _run_csi300_writer(database)

    assert events == [
        "supplier-complete",
        "path-attempt",
        "path-entered",
        "macro-attempt",
        "macro-entered",
        "native-open-attempt",
        "native-opened",
        "native-closed",
        "macro-released",
        "path-released",
    ]
    assert _snapshot_writer_tables(database) == before
    _assert_http_sentinel_wired(http_calls)
    _assert_database_destination_sentinel_wired(
        attempts=foreign_database_attempts,
        foreign_database=tmp_path / "rollback-foreign.duckdb",
    )
    _assert_another_process_can_acquire_path_lock(
        tmp_path=tmp_path,
        database=database,
        marker_name="rollback-path-lock-acquired.txt",
    )


def test_macro_lock_timeout_does_not_open_database_and_releases_path_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "macro-timeout.duckdb"
    _bootstrap_database(database)
    supplier_events: list[str] = []
    _install_csi300_source(monkeypatch, events=supplier_events)
    http_calls = _install_http_sentinel(monkeypatch)
    actual_acquire = choice_macro.acquire_lock
    native_open_attempts: list[str] = []
    path_events: list[str] = []

    @contextmanager
    def short_macro_timeout(definition, *args, **kwargs):
        if definition.key == choice_macro.CHOICE_MACRO_LOCK.key:
            with actual_acquire(
                definition,
                *args,
                **kwargs,
                timeout_seconds=0.1,
                poll_interval_seconds=0.01,
            ) as value:
                yield value
            return
        path_events.append("path-attempt")
        try:
            with actual_acquire(definition, *args, **kwargs) as value:
                path_events.append("path-entered")
                yield value
        finally:
            path_events.append("path-released")

    def forbidden_connect(*_args, **_kwargs):
        native_open_attempts.append("native-open-attempt")
        raise AssertionError("Database open occurred before the macro lock was acquired.")

    with acquire_lock(
        choice_macro.CHOICE_MACRO_LOCK,
        base_dir=database.parent,
        timeout_seconds=1,
    ):
        monkeypatch.setattr(choice_macro, "acquire_lock", short_macro_timeout)
        monkeypatch.setattr(choice_macro.duckdb, "connect", forbidden_connect)
        with pytest.raises(TimeoutError):
            _run_csi300_writer(database)

    assert native_open_attempts == []
    assert supplier_events == ["supplier-complete"]
    assert path_events == ["path-attempt", "path-entered", "path-released"]
    _assert_http_sentinel_wired(http_calls)
    _assert_another_process_can_acquire_path_lock(
        tmp_path=tmp_path,
        database=database,
        marker_name="timeout-path-lock-acquired.txt",
    )
