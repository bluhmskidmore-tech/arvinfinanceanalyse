from __future__ import annotations

import asyncio
import multiprocessing
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.duckdb_read_context import (
    DuckDBOnlineReadRequiredError,
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    active_read_scope,
    current_duckdb_read_selection,
    duckdb_read_scope,
)
from backend.app.repositories.duckdb_repo import (
    DuckDBRepository,
    read_only_connection,
    reset_catalog_presence_cache,
)


def _create_database(path: Path, sentinel: str, *, has_feature: bool = False) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute("CREATE TABLE sentinel(value VARCHAR)")
        conn.execute("INSERT INTO sentinel VALUES (?)", [sentinel])
        if has_feature:
            conn.execute("CREATE TABLE generation_feature(value INTEGER)")
    finally:
        conn.close()


def _write_active_in_process(
    database_path: str,
    lock_base_dir: str,
    next_value: str,
    started: multiprocessing.synchronize.Event,
    result: multiprocessing.connection.Connection,
) -> None:
    started.set()
    try:
        writer_lock = resolve_duckdb_writer_lock(database_path)
        with acquire_lock(writer_lock, base_dir=Path(lock_base_dir), timeout_seconds=3.0):
            conn = duckdb.connect(database_path)
            try:
                conn.execute("UPDATE sentinel SET value = ?", [next_value])
            finally:
                conn.close()
    except Exception as exc:  # pragma: no cover - assertion is in the parent process
        result.send((False, exc.__class__.__name__, str(exc)))
    else:
        result.send((True, "", ""))
    finally:
        result.close()


def _run_writer(
    database_path: Path,
    lock_base_dir: Path,
    next_value: str,
) -> tuple[multiprocessing.Process, multiprocessing.synchronize.Event, object]:
    context = multiprocessing.get_context("spawn")
    started = context.Event()
    parent_result, child_result = context.Pipe(duplex=False)
    process = context.Process(
        target=_write_active_in_process,
        args=(str(database_path), str(lock_base_dir), next_value, started, child_result),
    )
    process.start()
    child_result.close()
    return process, started, parent_result


def _finish_writer(process: multiprocessing.Process, result: object) -> tuple[bool, str, str]:
    try:
        assert result.poll(8.0), "writer process did not report a bounded result"
        outcome = result.recv()
        process.join(timeout=5.0)
        assert not process.is_alive(), "writer process did not exit after reporting"
        return outcome
    finally:
        result.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)


@contextmanager
def _function_reader(path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    with read_only_connection(str(path)) as conn:
        yield conn


@contextmanager
def _repository_reader(path: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    repository = DuckDBRepository(str(path))
    conn = repository._connect_read_only()
    assert conn is not None
    try:
        yield conn
    finally:
        conn.close()


@pytest.mark.parametrize("reader", [_function_reader, _repository_reader])
def test_selected_snapshot_reader_does_not_block_governed_active_writer(
    tmp_path: Path,
    reader: Callable[[Path], object],
) -> None:
    active = tmp_path / "active.duckdb"
    snapshot = tmp_path / "generation-r0.duckdb"
    _create_database(active, "A0")
    _create_database(snapshot, "R0")
    selection = DuckDBReadSelection(active, snapshot, "r0")

    with duckdb_read_scope(selection, required_online=True):
        with reader(active) as conn:
            assert conn.execute("SELECT value FROM sentinel").fetchone() == ("R0",)
            process, started, result = _run_writer(active, tmp_path / "locks", "A1")
            try:
                assert started.wait(timeout=5.0)
                assert _finish_writer(process, result) == (True, "", "")
            finally:
                result.close()
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5.0)
            assert conn.execute("SELECT value FROM sentinel").fetchone() == ("R0",)

        with active_read_scope():
            assert current_duckdb_read_selection() is None
            with read_only_connection(str(active)) as active_conn:
                assert active_conn.execute("SELECT value FROM sentinel").fetchone() == ("A1",)
        assert current_duckdb_read_selection() == selection
        with read_only_connection(str(active)) as restored_conn:
            assert restored_conn.execute("SELECT value FROM sentinel").fetchone() == ("R0",)

    with read_only_connection(str(active)) as conn:
        assert conn.execute("SELECT value FROM sentinel").fetchone() == ("A1",)


def test_unselected_active_reader_is_the_locking_control_group(tmp_path: Path) -> None:
    active = tmp_path / "active.duckdb"
    _create_database(active, "A0")

    with read_only_connection(str(active)) as conn:
        assert conn.execute("SELECT value FROM sentinel").fetchone() == ("A0",)
        process, started, result = _run_writer(active, tmp_path / "locks", "A1")
        try:
            assert started.wait(timeout=5.0)
            ok, error_type, _ = _finish_writer(process, result)
        finally:
            result.close()
            if process.is_alive():
                process.terminate()
                process.join(timeout=5.0)
        assert ok is False
        assert error_type in {"IOException", "IOExceptionError"}

    with read_only_connection(str(active)) as conn:
        assert conn.execute("SELECT value FROM sentinel").fetchone() == ("A0",)


def test_scopes_are_task_local_and_restore_outer_selection(tmp_path: Path) -> None:
    active = tmp_path / "active.duckdb"
    snapshot_r0 = tmp_path / "generation-r0.duckdb"
    snapshot_r1 = tmp_path / "generation-r1.duckdb"
    _create_database(active, "A")
    _create_database(snapshot_r0, "R0")
    _create_database(snapshot_r1, "R1")
    selection_r0 = DuckDBReadSelection(active, snapshot_r0, "r0")
    selection_r1 = DuckDBReadSelection(active, snapshot_r1, "r1")

    async def read_in_task(selection: DuckDBReadSelection, ready: asyncio.Event) -> tuple[str, str]:
        with duckdb_read_scope(selection):
            with read_only_connection(str(active)) as conn:
                first = conn.execute("SELECT value FROM sentinel").fetchone()[0]
                ready.set()
                await asyncio.sleep(0)
                second = conn.execute("SELECT value FROM sentinel").fetchone()[0]
                return first, second

    async def run_concurrently() -> list[tuple[str, str]]:
        ready_r0 = asyncio.Event()
        ready_r1 = asyncio.Event()
        task_r0 = asyncio.create_task(read_in_task(selection_r0, ready_r0))
        task_r1 = asyncio.create_task(read_in_task(selection_r1, ready_r1))
        await asyncio.wait_for(asyncio.gather(ready_r0.wait(), ready_r1.wait()), timeout=5.0)
        return list(await asyncio.gather(task_r0, task_r1))

    with duckdb_read_scope(selection_r0):
        assert current_duckdb_read_selection() == selection_r0
        with duckdb_read_scope(selection_r1):
            assert current_duckdb_read_selection() == selection_r1
        assert current_duckdb_read_selection() == selection_r0
        with duckdb_read_scope(None):
            assert current_duckdb_read_selection() is None
            with read_only_connection(str(active)) as conn:
                assert conn.execute("SELECT value FROM sentinel").fetchone() == ("A",)
        assert current_duckdb_read_selection() == selection_r0

    assert current_duckdb_read_selection() is None
    assert asyncio.run(run_concurrently()) == [("R0", "R0"), ("R1", "R1")]


def test_required_online_scope_fails_closed_and_other_paths_are_untouched(tmp_path: Path) -> None:
    active = tmp_path / "active.duckdb"
    snapshot = tmp_path / "generation-r0.duckdb"
    other = tmp_path / "other.duckdb"
    _create_database(active, "A")
    _create_database(snapshot, "R0")
    _create_database(other, "OTHER")
    selection = DuckDBReadSelection(active, snapshot, "r0")

    with duckdb_read_scope(None, required_online=True, active_path=active):
        with pytest.raises(DuckDBOnlineReadRequiredError):
            with read_only_connection(str(active)):
                pass
        with read_only_connection(str(other)) as conn:
            assert conn.execute("SELECT value FROM sentinel").fetchone() == ("OTHER",)

    snapshot.unlink()
    with duckdb_read_scope(selection):
        with pytest.raises(DuckDBReadSelectionError):
            with read_only_connection(str(active)):
                pass
        with read_only_connection(str(other)) as conn:
            assert conn.execute("SELECT value FROM sentinel").fetchone() == ("OTHER",)

    with pytest.raises(DuckDBReadSelectionError):
        DuckDBReadSelection(active, tmp_path / "missing.duckdb", "missing")


def test_repository_rejects_context_change_while_scoped_connection_is_active(
    tmp_path: Path,
) -> None:
    active = tmp_path / "active.duckdb"
    snapshot = tmp_path / "generation-r0.duckdb"
    _create_database(active, "A")
    _create_database(snapshot, "R0")
    selection = DuckDBReadSelection(active, snapshot, "r0")
    repository = DuckDBRepository(str(active))

    with repository.scoped_connection() as conn:
        assert conn is not None
        assert repository._fetch_rows("SELECT value FROM sentinel") == [("A",)]
        with duckdb_read_scope(selection):
            with pytest.raises(RuntimeError, match="read context changed"):
                repository._fetch_rows("SELECT value FROM sentinel")
            with pytest.raises(RuntimeError, match="read context changed"):
                with repository.scoped_connection():
                    pass

    with duckdb_read_scope(selection):
        assert repository._fetch_rows("SELECT value FROM sentinel") == [("R0",)]


def test_catalog_presence_cache_isolated_by_effective_generation(tmp_path: Path) -> None:
    reset_catalog_presence_cache()
    active = tmp_path / "active.duckdb"
    snapshot_r0 = tmp_path / "generation-r0.duckdb"
    snapshot_r1 = tmp_path / "generation-r1.duckdb"
    _create_database(active, "A", has_feature=True)
    _create_database(snapshot_r0, "R0", has_feature=True)
    _create_database(snapshot_r1, "R1", has_feature=False)
    selection_r0 = DuckDBReadSelection(active, snapshot_r0, "r0")
    selection_r1 = DuckDBReadSelection(active, snapshot_r1, "r1")
    repository = DuckDBRepository(str(active))

    with duckdb_read_scope(selection_r0):
        assert repository._table_exists("generation_feature") is True
    with duckdb_read_scope(selection_r1):
        assert repository._table_exists("generation_feature") is False
    assert repository._table_exists("generation_feature") is True
