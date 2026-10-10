from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator

import duckdb
import pytest

import backend.app.core_finance.macro.toolkit.system_sources as system_sources
from backend.app.core_finance.macro import (
    equity_shadow_portfolio as shadow_portfolio_module,
)
from backend.app.core_finance.macro.equity_shadow_portfolio import (
    compute_equity_shadow_portfolio_report,
)
from backend.app.core_finance.macro.toolkit.system_sources import (
    clear_system_macro_source_cache,
    load_series_by_alias,
    load_system_macro_frame,
    resolve_system_duckdb_path,
)
from backend.app.repositories.duckdb_read_context import (
    DuckDBOnlineReadRequiredError,
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    active_read_scope,
    duckdb_read_scope,
)


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]

ROOT = Path(__file__).resolve().parents[1]


def _seed_macro_value(path: Path, value: float) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_status varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('TEST.IMMUTABLE', 'Immutable test series', '2026-09-16', ?,
               'daily', 'index', 'sv_test', 'vv_test', 'rv_test', 'ok', 'run-test')
            """,
            [value],
        )
    finally:
        conn.close()


def _seed_combined_reader_db(path: Path, value: float, *, month: str) -> None:
    from tests.test_macro_toolkit_shadow_portfolio_report import (  # noqa: PLC0415
        _seed_shadow_report_db,
    )

    _seed_shadow_report_db(path)
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            "update choice_stock_daily_observation "
            "set trade_date = replace(trade_date, '2026-05', ?)",
            [month],
        )
        conn.execute(
            "update choice_stock_factor_snapshot "
            "set as_of_date = replace(as_of_date, '2026-05', ?)",
            [month],
        )
        conn.execute(
            "update stock_adjustment_factor "
            "set trade_date = replace(trade_date, '2026-05', ?)",
            [month],
        )
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_status varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('TEST.IMMUTABLE', 'Immutable test series', '2026-09-16', ?,
               'daily', 'index', 'sv_test', 'vv_test', 'rv_test', 'ok', 'run-test')
            """,
            [value],
        )
    finally:
        conn.close()


def _wait_for_event(path: Path, event: str, *, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists():
            events = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if any(item.get("event") == event for item in events):
                return
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for {event!r} in {path}")


def _holder_child_code() -> str:
    return r"""
import json
import sys
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
database = Path(sys.argv[2]).resolve()
events_path = Path(sys.argv[3]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.set_pytest_duckdb_guard_phase("macro-active-rw-holder")

import socket

def forbid_network(*args, **kwargs):
    raise AssertionError("Network access is forbidden in the macro RW holder")

socket.create_connection = forbid_network
import requests
requests.Session.request = forbid_network
import duckdb

connection = None
try:
    connection = duckdb.connect(str(database), read_only=False)
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": "rw-opened"}) + "\n")
        handle.flush()
    sys.stdin.readline()
finally:
    if connection is not None:
        connection.close()
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": "rw-closed"}) + "\n")
        handle.flush()
    guard.finalize_pytest_duckdb_guard()
"""


@contextmanager
def _held_active_writer(active_path: Path, tmp_path: Path) -> Iterator[None]:
    events_path = tmp_path / "holder-events.jsonl"
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _holder_child_code(),
            os.fspath(tmp_path),
            os.fspath(active_path),
            os.fspath(events_path),
        ],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout = ""
    stderr = ""
    try:
        _wait_for_event(events_path, "rw-opened")
        assert child.poll() is None
        yield
    finally:
        if child.poll() is None and child.stdin is not None:
            child.stdin.write("stop\n")
            child.stdin.flush()
            child.stdin.close()
            child.stdin = None
        try:
            stdout, stderr = child.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            stdout, stderr = child.communicate(timeout=5)
        assert child.returncode == 0, stdout + stderr
        _wait_for_event(events_path, "rw-closed")


def _reader_child_code() -> str:
    return r"""
import json
import os
import sys
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
active_path = Path(sys.argv[2]).resolve()
snapshot_path = Path(sys.argv[3]).resolve()
result_path = Path(sys.argv[4]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.set_pytest_duckdb_guard_phase("macro-immutable-readers")

import socket

http_calls = []

def forbid_network(*args, **kwargs):
    http_calls.append([str(value) for value in args])
    raise AssertionError("Network access is forbidden in macro immutable readers")

socket.create_connection = forbid_network
import requests
requests.Session.request = forbid_network
import duckdb

actual_connect = duckdb.connect
opened_paths = []

def observed_connect(*args, **kwargs):
    raw_path = args[0] if args else kwargs.get("database")
    opened_paths.append(str(Path(os.fspath(raw_path)).resolve()))
    return actual_connect(*args, **kwargs)

duckdb.connect = observed_connect

from backend.app.core_finance.macro.equity_shadow_portfolio import (
    compute_equity_shadow_portfolio_report,
)
from backend.app.core_finance.macro.toolkit.system_sources import (
    clear_system_macro_source_cache,
    load_series_by_alias,
    load_system_macro_frame,
    resolve_system_duckdb_path,
)
from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection,
    duckdb_read_scope,
)

attempts_before = guard.get_pytest_duckdb_guard_attempts()
try:
    selection = DuckDBReadSelection(
        active_path=active_path,
        snapshot_path=snapshot_path,
        generation="generation-held",
    )
    clear_system_macro_source_cache()
    with duckdb_read_scope(selection, required_online=True):
        resolved = resolve_system_duckdb_path(active_path)
        frame = load_system_macro_frame(
            active_path,
            series_ids=("TEST.IMMUTABLE",),
        )
        alias = load_series_by_alias("TEST.IMMUTABLE", duckdb_path=active_path)
        shadow = compute_equity_shadow_portfolio_report(active_path)
    attempts_after = guard.get_pytest_duckdb_guard_attempts()
    receipt_path = guard.finalize_pytest_duckdb_guard()
    result_path.write_text(
        json.dumps(
            {
                "resolved": str(resolved),
                "frame_values": frame["value_numeric"].tolist(),
                "alias_values": alias["value"].tolist(),
                "shadow_status": shadow["status"],
                "shadow_as_of_date": shadow["as_of_date"],
                "opened_paths": opened_paths,
                "attempts_before": attempts_before,
                "attempts_after": attempts_after,
                "http_calls": http_calls,
                "receipt_path": str(receipt_path),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
except BaseException:
    guard.finalize_pytest_duckdb_guard()
    raise
"""


def test_macro_system_readers_follow_immutable_selection(tmp_path: Path) -> None:
    active_path = tmp_path / "active.duckdb"
    snapshot_path = tmp_path / "snapshot.duckdb"
    _seed_macro_value(active_path, 10.0)
    _seed_macro_value(snapshot_path, 20.0)
    selection = DuckDBReadSelection(
        active_path=active_path,
        snapshot_path=snapshot_path,
        generation="generation-a",
    )
    clear_system_macro_source_cache()

    try:
        with duckdb_read_scope(selection, required_online=True):
            assert resolve_system_duckdb_path(active_path) == snapshot_path
            frame = load_system_macro_frame(
                active_path,
                series_ids=("TEST.IMMUTABLE",),
            )
            alias = load_series_by_alias(
                "TEST.IMMUTABLE",
                duckdb_path=active_path,
            )

        assert frame["value_numeric"].tolist() == [20.0]
        assert alias["value"].tolist() == [20.0]
    finally:
        clear_system_macro_source_cache()


def test_real_readers_avoid_active_native_open_while_independent_writer_holds_it(
    tmp_path: Path,
) -> None:
    active_path = tmp_path / "active.duckdb"
    snapshot_path = tmp_path / "snapshot.duckdb"
    result_path = tmp_path / "reader-result.json"
    _seed_combined_reader_db(active_path, 10.0, month="2026-05")
    _seed_combined_reader_db(snapshot_path, 20.0, month="2026-06")

    with _held_active_writer(active_path, tmp_path):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                _reader_child_code(),
                os.fspath(tmp_path),
                os.fspath(active_path),
                os.fspath(snapshot_path),
                os.fspath(result_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["resolved"] == str(snapshot_path.resolve())
    assert payload["frame_values"] == [20.0]
    assert payload["alias_values"] == [20.0]
    assert payload["shadow_status"] == "complete"
    assert payload["shadow_as_of_date"] == "2026-06-03"
    assert payload["attempts_before"] == []
    assert payload["http_calls"] == []
    assert payload["opened_paths"]
    assert set(payload["opened_paths"]) == {str(snapshot_path.resolve())}
    assert all(
        Path(attempt["canonical_path"]).resolve() != active_path.resolve()
        for attempt in payload["attempts_after"]
    )
    assert all(attempt["decision"] == "allow" for attempt in payload["attempts_after"])
    assert Path(payload["receipt_path"]).parent == tmp_path


def test_cache_key_follows_effective_snapshot_without_active_stat_change(
    tmp_path: Path,
) -> None:
    active_path = tmp_path / "active.duckdb"
    snapshot_a = tmp_path / "snapshot-a.duckdb"
    snapshot_b = tmp_path / "snapshot-b.duckdb"
    _seed_macro_value(active_path, 10.0)
    _seed_macro_value(snapshot_a, 20.0)
    _seed_macro_value(snapshot_b, 30.0)
    active_stat = active_path.stat()
    selection_a = DuckDBReadSelection(active_path, snapshot_a, "generation-a")
    selection_b = DuckDBReadSelection(active_path, snapshot_b, "generation-b")
    clear_system_macro_source_cache()

    try:
        with duckdb_read_scope(selection_a, required_online=True):
            first = load_series_by_alias("TEST.IMMUTABLE", duckdb_path=active_path)
        with duckdb_read_scope(selection_b, required_online=True):
            second = load_series_by_alias("TEST.IMMUTABLE", duckdb_path=active_path)

        assert first["value"].tolist() == [20.0]
        assert second["value"].tolist() == [30.0]
        after_stat = active_path.stat()
        assert (after_stat.st_mtime_ns, after_stat.st_size) == (
            active_stat.st_mtime_ns,
            active_stat.st_size,
        )
        cache_info = system_sources._load_series_subset_frame_cache.cache_info()
        assert cache_info.misses == 2
    finally:
        clear_system_macro_source_cache()


def test_required_selection_failures_do_not_return_warm_cache_or_open_active(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_path = tmp_path / "active.duckdb"
    snapshot_path = tmp_path / "snapshot.duckdb"
    _seed_macro_value(active_path, 10.0)
    _seed_macro_value(snapshot_path, 20.0)
    selection = DuckDBReadSelection(active_path, snapshot_path, "generation-a")
    clear_system_macro_source_cache()

    try:
        with active_read_scope():
            active = load_series_by_alias("TEST.IMMUTABLE", duckdb_path=active_path)
        with duckdb_read_scope(selection, required_online=True):
            snapshot = load_series_by_alias("TEST.IMMUTABLE", duckdb_path=active_path)
        assert active["value"].tolist() == [10.0]
        assert snapshot["value"].tolist() == [20.0]

        open_attempts: list[object] = []

        def forbid_open(*args: object, **kwargs: object) -> None:
            open_attempts.append((args, kwargs))
            raise AssertionError("selection failure must happen before DuckDB open")

        monkeypatch.setattr(system_sources.duckdb, "connect", forbid_open)
        with duckdb_read_scope(None, required_online=True, active_path=active_path):
            for reader in (
                lambda: load_series_by_alias(
                    "TEST.IMMUTABLE",
                    duckdb_path=active_path,
                ),
                lambda: load_system_macro_frame(active_path),
                lambda: compute_equity_shadow_portfolio_report(active_path),
            ):
                with pytest.raises(DuckDBOnlineReadRequiredError):
                    reader()

        snapshot_path.unlink()
        with duckdb_read_scope(selection, required_online=True):
            for reader in (
                lambda: load_series_by_alias(
                    "TEST.IMMUTABLE",
                    duckdb_path=active_path,
                ),
                lambda: load_system_macro_frame(active_path),
                lambda: compute_equity_shadow_portfolio_report(active_path),
            ):
                with pytest.raises(DuckDBReadSelectionError):
                    reader()
        assert open_attempts == []
    finally:
        clear_system_macro_source_cache()


def test_active_read_scope_temporarily_restores_legacy_active_selection(
    tmp_path: Path,
) -> None:
    active_path = tmp_path / "active.duckdb"
    snapshot_path = tmp_path / "snapshot.duckdb"
    _seed_macro_value(active_path, 10.0)
    _seed_macro_value(snapshot_path, 20.0)
    selection = DuckDBReadSelection(active_path, snapshot_path, "generation-a")
    clear_system_macro_source_cache()

    try:
        without_selection = load_series_by_alias(
            "TEST.IMMUTABLE",
            duckdb_path=active_path,
        )
        with duckdb_read_scope(selection, required_online=True):
            before = load_series_by_alias("TEST.IMMUTABLE", duckdb_path=active_path)
            with active_read_scope():
                active = load_series_by_alias(
                    "TEST.IMMUTABLE",
                    duckdb_path=active_path,
                )
            after = load_series_by_alias("TEST.IMMUTABLE", duckdb_path=active_path)

        assert without_selection["value"].tolist() == [10.0]
        assert before["value"].tolist() == [20.0]
        assert active["value"].tolist() == [10.0]
        assert after["value"].tolist() == [20.0]
    finally:
        clear_system_macro_source_cache()


def test_default_settings_path_uses_current_immutable_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.governance import settings as settings_module

    active_path = tmp_path / "active.duckdb"
    snapshot_path = tmp_path / "snapshot.duckdb"
    _seed_macro_value(active_path, 10.0)
    _seed_macro_value(snapshot_path, 20.0)
    selection = DuckDBReadSelection(active_path, snapshot_path, "generation-a")
    monkeypatch.setattr(
        settings_module,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(active_path)),
    )

    with duckdb_read_scope(selection, required_online=True):
        assert resolve_system_duckdb_path() == snapshot_path


def test_system_frame_closes_actual_connection_after_query_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "snapshot.duckdb"
    _seed_macro_value(database, 20.0)
    actual_connect = duckdb.connect
    closed: list[bool] = []

    class FailingConnection:
        def __init__(self) -> None:
            self.inner = actual_connect(str(database), read_only=True)

        def execute(self, *args: object, **kwargs: object) -> object:
            raise duckdb.IOException("forced query failure")

        def close(self) -> None:
            self.inner.close()
            closed.append(True)

    monkeypatch.setattr(
        system_sources.duckdb,
        "connect",
        lambda *args, **kwargs: FailingConnection(),
    )

    frame = load_system_macro_frame(database)

    assert frame.empty
    assert closed == [True]


def test_shadow_report_closes_actual_connection_after_query_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "snapshot.duckdb"
    _seed_combined_reader_db(database, 20.0, month="2026-06")
    actual_connect = duckdb.connect
    closed: list[bool] = []

    class FailingConnection:
        def __init__(self) -> None:
            self.inner = actual_connect(str(database), read_only=True)
            self.execute_count = 0

        def execute(self, *args: object, **kwargs: object) -> object:
            self.execute_count += 1
            if self.execute_count > 1:
                raise duckdb.IOException("forced shadow query failure")
            return self.inner.execute(*args, **kwargs)

        def close(self) -> None:
            self.inner.close()
            closed.append(True)

        def __getattr__(self, name: str) -> object:
            return getattr(self.inner, name)

    monkeypatch.setattr(
        shadow_portfolio_module.duckdb,
        "connect",
        lambda *args, **kwargs: FailingConnection(),
    )

    report = compute_equity_shadow_portfolio_report(database)

    assert report["status"] == "unavailable"
    assert report["warnings"][-1] == "DUCKDB_QUERY_FAILED: IOException"
    assert closed == [True]
