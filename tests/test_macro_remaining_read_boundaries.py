from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import Barrier, Lock
from typing import Iterator

import duckdb
import pytest

from backend.app.repositories.cffex_member_rank_repo import table_stats
from backend.app.repositories.dual_frequency_equity_repo import (
    load_dual_frequency_equity_history,
)
from backend.app.repositories.duckdb_read_context import (
    DuckDBOnlineReadRequiredError,
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    active_read_scope,
    duckdb_read_scope,
)
from backend.app.services.macro_toolkit_read_service import (
    build_macro_toolkit_full_analysis_blocks,
)


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]

ROOT = Path(__file__).resolve().parents[1]


def _seed_repository_facts(
    path: Path,
    *,
    cffex_rows: int,
    index_close: float,
) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_cffex_member_rank_daily (
              trade_date varchar,
              contract varchar,
              source_vendor varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_cffex_member_rank_daily values (?, ?, ?)",
            [("2026-09-16", f"T{index}.CFE", "choice") for index in range(cffex_rows)],
        )
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              trade_date varchar,
              value_numeric double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('CA.CSI300', '2026-09-16', ?, 'sv-test', 'vv-test',
               'rv-test', 'ok', 'run-test')
            """,
            [index_close],
        )
    finally:
        conn.close()


def _read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _wait_for_event(path: Path, event: str, *, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if any(item.get("event") == event for item in _read_events(path)):
            return
        time.sleep(0.01)
    raise AssertionError(f"Timed out waiting for {event!r}: {_read_events(path)}")


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
guard.set_pytest_duckdb_guard_phase("macro-remaining-rw-holder")

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
from contextvars import ContextVar
from pathlib import Path
from threading import Barrier, Lock, get_ident

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
active_path = Path(sys.argv[2]).resolve()
snapshot_path = Path(sys.argv[3]).resolve()
result_path = Path(sys.argv[4]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.set_pytest_duckdb_guard_phase("macro-remaining-readers")

import socket

http_calls = []

def forbid_network(*args, **kwargs):
    http_calls.append([str(value) for value in args])
    raise AssertionError("Network access is forbidden in macro remaining readers")

socket.create_connection = forbid_network
import requests
requests.Session.request = forbid_network
import duckdb

actual_connect = duckdb.connect
opened_paths = []
opened_lock = Lock()

def observed_connect(*args, **kwargs):
    raw_path = args[0] if args else kwargs.get("database")
    with opened_lock:
        opened_paths.append(str(Path(os.fspath(raw_path)).resolve()))
    return actual_connect(*args, **kwargs)

duckdb.connect = observed_connect

from backend.app.repositories.cffex_member_rank_repo import table_stats
from backend.app.repositories.dual_frequency_equity_repo import (
    load_dual_frequency_equity_history,
)
from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection,
    current_duckdb_read_selection,
    duckdb_read_scope,
)
from backend.app.services.macro_toolkit_read_service import (
    build_macro_toolkit_full_analysis_blocks,
)

attempts_before = guard.get_pytest_duckdb_guard_attempts()
worker_marker = ContextVar("worker_marker", default="parent")
barrier = Barrier(3, timeout=5)
callback_records = []
records_lock = Lock()

def enter_callback(name, path, **details):
    worker_marker.set(name)
    barrier.wait()
    selection = current_duckdb_read_selection()
    with records_lock:
        callback_records.append(
            {
                "name": name,
                "marker": worker_marker.get(),
                "generation": None if selection is None else selection.generation,
                "thread_id": get_ident(),
                "path": str(Path(path).resolve()),
                **details,
            }
        )

def risk(path):
    enter_callback("risk", path)
    stats = table_stats(path)
    return {"name": "risk", "row_count": stats["row_count"]}

def capabilities(path, *, report_date, history_limit):
    enter_callback(
        "capabilities",
        path,
        report_date=str(report_date),
        history_limit=history_limit,
    )
    history = load_dual_frequency_equity_history(
        duckdb_path=path,
        lookback_rows=history_limit,
    )
    return [{"name": "capabilities", "close": history["rows"][0]["close"]}]

def strategies(path):
    enter_callback("strategies", path)
    stats = table_stats(path)
    return [{"name": "strategies", "row_count": stats["row_count"]}]

try:
    selection = DuckDBReadSelection(
        active_path=active_path,
        snapshot_path=snapshot_path,
        generation="generation-held",
    )
    with duckdb_read_scope(selection, required_online=True):
        result = build_macro_toolkit_full_analysis_blocks(
            active_path,
            "2026-09-16",
            history_limit=5,
            a_share_stampede_risk=risk,
            macro_capability_results=capabilities,
            equity_strategy_summaries=strategies,
        )
    attempts_after = guard.get_pytest_duckdb_guard_attempts()
    receipt_path = guard.finalize_pytest_duckdb_guard()
    result_path.write_text(
        json.dumps(
            {
                "result": result,
                "callback_records": callback_records,
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


def test_repository_readers_follow_current_immutable_selection(tmp_path: Path) -> None:
    active_path = tmp_path / "active.duckdb"
    snapshot_path = tmp_path / "snapshot.duckdb"
    _seed_repository_facts(active_path, cffex_rows=1, index_close=10.0)
    _seed_repository_facts(snapshot_path, cffex_rows=2, index_close=20.0)
    selection = DuckDBReadSelection(
        active_path=active_path,
        snapshot_path=snapshot_path,
        generation="generation-a",
    )

    with duckdb_read_scope(selection, required_online=True):
        cffex = table_stats(active_path)
        dual = load_dual_frequency_equity_history(
            duckdb_path=active_path,
            lookback_rows=5,
        )

    assert cffex["row_count"] == 2
    assert [row["close"] for row in dual["rows"]] == [20.0]


def test_full_analysis_workers_avoid_held_active_database(tmp_path: Path) -> None:
    active_path = tmp_path / "active.duckdb"
    snapshot_path = tmp_path / "snapshot.duckdb"
    result_path = tmp_path / "reader-result.json"
    _seed_repository_facts(active_path, cffex_rows=1, index_close=10.0)
    _seed_repository_facts(snapshot_path, cffex_rows=2, index_close=20.0)

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
    assert payload["result"] == [
        {"name": "risk", "row_count": 2},
        [{"name": "capabilities", "close": 20.0}],
        [{"name": "strategies", "row_count": 2}],
    ]
    records = {record["name"]: record for record in payload["callback_records"]}
    assert set(records) == {"risk", "capabilities", "strategies"}
    assert {record["marker"] for record in records.values()} == set(records)
    assert {record["generation"] for record in records.values()} == {"generation-held"}
    assert len({record["thread_id"] for record in records.values()}) == 3
    assert {record["path"] for record in records.values()} == {
        str(active_path.resolve())
    }
    assert records["capabilities"]["report_date"] == "2026-09-16"
    assert records["capabilities"]["history_limit"] == 5
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


def test_overlapping_full_analysis_requests_keep_distinct_selections(
    tmp_path: Path,
) -> None:
    active_path = tmp_path / "active.duckdb"
    snapshot_a = tmp_path / "snapshot-a.duckdb"
    snapshot_b = tmp_path / "snapshot-b.duckdb"
    _seed_repository_facts(active_path, cffex_rows=1, index_close=10.0)
    _seed_repository_facts(snapshot_a, cffex_rows=2, index_close=20.0)
    _seed_repository_facts(snapshot_b, cffex_rows=3, index_close=30.0)
    six_workers = Barrier(6, timeout=5)

    def run_request(selection: DuckDBReadSelection) -> tuple[object, ...]:
        with duckdb_read_scope(selection, required_online=True):

            def risk(path: str | Path) -> dict[str, object]:
                six_workers.wait()
                return {"value": table_stats(path)["row_count"]}

            def capabilities(
                path: str | Path,
                *,
                report_date: object,
                history_limit: int,
            ) -> list[dict[str, object]]:
                assert report_date == "2026-09-16"
                six_workers.wait()
                history = load_dual_frequency_equity_history(
                    duckdb_path=path,
                    lookback_rows=history_limit,
                )
                return [{"value": history["rows"][0]["close"]}]

            def strategies(path: str | Path) -> list[dict[str, object]]:
                six_workers.wait()
                return [{"value": table_stats(path)["row_count"]}]

            return build_macro_toolkit_full_analysis_blocks(
                active_path,
                "2026-09-16",
                history_limit=5,
                a_share_stampede_risk=risk,
                macro_capability_results=capabilities,
                equity_strategy_summaries=strategies,
            )

    selection_a = DuckDBReadSelection(active_path, snapshot_a, "generation-a")
    selection_b = DuckDBReadSelection(active_path, snapshot_b, "generation-b")
    with ThreadPoolExecutor(max_workers=2) as outer_executor:
        future_a = outer_executor.submit(run_request, selection_a)
        future_b = outer_executor.submit(run_request, selection_b)
        result_a = future_a.result(timeout=15)
        result_b = future_b.result(timeout=15)

    assert result_a == ({"value": 2}, [{"value": 20.0}], [{"value": 2}])
    assert result_b == ({"value": 3}, [{"value": 30.0}], [{"value": 3}])
    assert six_workers.n_waiting == 0


def test_required_selection_failures_happen_before_native_open_in_workers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_path = tmp_path / "active.duckdb"
    snapshot_path = tmp_path / "snapshot.duckdb"
    _seed_repository_facts(active_path, cffex_rows=1, index_close=10.0)
    _seed_repository_facts(snapshot_path, cffex_rows=2, index_close=20.0)
    selection = DuckDBReadSelection(active_path, snapshot_path, "generation-a")
    open_attempts: list[object] = []

    def forbid_open(*args: object, **kwargs: object) -> None:
        open_attempts.append((args, kwargs))
        raise AssertionError("selection failure must happen before native open")

    monkeypatch.setattr(duckdb, "connect", forbid_open)

    def run_workers() -> tuple[object, ...]:
        return build_macro_toolkit_full_analysis_blocks(
            active_path,
            "2026-09-16",
            history_limit=5,
            a_share_stampede_risk=table_stats,
            macro_capability_results=lambda path, **kwargs: [
                load_dual_frequency_equity_history(
                    duckdb_path=path,
                    lookback_rows=kwargs["history_limit"],
                )
            ],
            equity_strategy_summaries=lambda path: [table_stats(path)],
        )

    with duckdb_read_scope(None, required_online=True, active_path=active_path):
        with pytest.raises(DuckDBOnlineReadRequiredError):
            table_stats(active_path)
        with pytest.raises(DuckDBOnlineReadRequiredError):
            load_dual_frequency_equity_history(duckdb_path=active_path)
        with pytest.raises(DuckDBOnlineReadRequiredError):
            run_workers()

    snapshot_path.unlink()
    with duckdb_read_scope(selection, required_online=True):
        with pytest.raises(DuckDBReadSelectionError):
            table_stats(active_path)
        with pytest.raises(DuckDBReadSelectionError):
            load_dual_frequency_equity_history(duckdb_path=active_path)
        with pytest.raises(DuckDBReadSelectionError):
            run_workers()

    assert open_attempts == []


def test_active_read_scope_restores_outer_repository_selection(tmp_path: Path) -> None:
    active_path = tmp_path / "active.duckdb"
    snapshot_path = tmp_path / "snapshot.duckdb"
    _seed_repository_facts(active_path, cffex_rows=1, index_close=10.0)
    _seed_repository_facts(snapshot_path, cffex_rows=2, index_close=20.0)
    selection = DuckDBReadSelection(active_path, snapshot_path, "generation-a")

    assert table_stats(active_path)["row_count"] == 1
    assert (
        load_dual_frequency_equity_history(duckdb_path=active_path)["rows"][0]["close"]
        == 10.0
    )
    with duckdb_read_scope(selection, required_online=True):
        assert table_stats(active_path)["row_count"] == 2
        with active_read_scope():
            assert table_stats(active_path)["row_count"] == 1
            assert (
                load_dual_frequency_equity_history(duckdb_path=active_path)["rows"][0][
                    "close"
                ]
                == 10.0
            )
        assert table_stats(active_path)["row_count"] == 2
        assert (
            load_dual_frequency_equity_history(duckdb_path=active_path)["rows"][0][
                "close"
            ]
            == 20.0
        )


@pytest.mark.parametrize("reader_name", ["cffex", "dual"])
def test_repository_query_errors_close_actual_connections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reader_name: str,
) -> None:
    database = tmp_path / "snapshot.duckdb"
    _seed_repository_facts(database, cffex_rows=2, index_close=20.0)
    actual_connect = duckdb.connect
    closed: list[bool] = []

    class FailingConnection:
        def __init__(self) -> None:
            self.inner = actual_connect(str(database), read_only=True)
            self.execute_count = 0

        def execute(self, *args: object, **kwargs: object) -> object:
            self.execute_count += 1
            if self.execute_count > 1:
                raise duckdb.IOException("forced repository query failure")
            return self.inner.execute(*args, **kwargs)

        def close(self) -> None:
            self.inner.close()
            closed.append(True)

        def __getattr__(self, name: str) -> object:
            return getattr(self.inner, name)

    monkeypatch.setattr(
        duckdb,
        "connect",
        lambda *args, **kwargs: FailingConnection(),
    )

    if reader_name == "cffex":
        result = table_stats(database)
        assert result["status"] == "query_failed"
    else:
        result = load_dual_frequency_equity_history(duckdb_path=database)
        assert "index_history_query_failed" in result["warnings"]
    assert closed == [True]


def test_worker_exception_propagates_after_executor_and_barrier_cleanup() -> None:
    three_workers = Barrier(3, timeout=5)
    events: list[str] = []
    events_lock = Lock()
    marker: ContextVar[str] = ContextVar("exception_worker_marker", default="parent")

    def finish(name: str, *, fail: bool = False) -> object:
        marker.set(name)
        three_workers.wait()
        with events_lock:
            events.append(f"entered:{marker.get()}")
        if fail:
            raise RuntimeError("worker boom")
        with events_lock:
            events.append(f"finished:{marker.get()}")
        return name

    with pytest.raises(RuntimeError, match="worker boom"):
        build_macro_toolkit_full_analysis_blocks(
            "unused.duckdb",
            "2026-09-16",
            history_limit=5,
            a_share_stampede_risk=lambda path: finish("risk", fail=True),
            macro_capability_results=lambda path, **kwargs: [finish("capabilities")],
            equity_strategy_summaries=lambda path: [finish("strategies")],
        )

    assert three_workers.n_waiting == 0
    assert set(events) == {
        "entered:risk",
        "entered:capabilities",
        "entered:strategies",
        "finished:capabilities",
        "finished:strategies",
    }
