"""Unit tests for DuckDBRepository scoped connection reuse.

Covers the read-path performance mechanism that collapses "one connection per
query" into "one connection per scope":

- reuse: many queries inside a scope share a single ``duckdb.connect`` call;
- freshness: a new scope always reflects data written after the previous scope
  closed (no stale cross-scope caching);
- concurrency: threads each get an isolated connection and correct results;
- backward compatibility: non-scoped calls still open/close per query;
- guarded/missing path: a scope yields ``None`` and queries return empty.
"""

from __future__ import annotations

import threading

import duckdb as real_duckdb
import pytest

from tests.helpers import load_module

DUCK_MODULE_PATH = "backend/app/repositories/duckdb_repo.py"


def _load_duck(name: str):
    return load_module(f"backend.app.repositories.{name}", DUCK_MODULE_PATH)


def _seed(db_path, rows: list[tuple[str, int]]) -> None:
    conn = real_duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("create table if not exists t (k varchar, v integer)")
        conn.executemany("insert into t values (?, ?)", rows)
    finally:
        conn.close()


def _install_connect_counter(monkeypatch, duck_module) -> dict[str, int]:
    real_connect = real_duckdb.connect
    counter = {"opens": 0}

    def counting_connect(*args, **kwargs):
        counter["opens"] += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(duck_module.duckdb, "connect", counting_connect)
    return counter


def test_scoped_connection_reuses_single_open(monkeypatch, tmp_path):
    duck_module = _load_duck("duck_scoped_reuse")
    db_path = tmp_path / "moss.duckdb"
    _seed(db_path, [("a", 1), ("b", 2)])

    counter = _install_connect_counter(monkeypatch, duck_module)
    repo = duck_module.DuckDBRepository(str(db_path))

    with repo.scoped_connection():
        assert repo._table_exists("t") is True
        assert repo._fetch_rows("select count(*) from t")[0][0] == 2
        assert repo._fetch_rows("select v from t where k = ?", ["b"])[0][0] == 2

    # One open for the whole scope, despite three queries.
    assert counter["opens"] == 1


def test_unscoped_calls_open_per_query(monkeypatch, tmp_path):
    duck_module = _load_duck("duck_unscoped")
    db_path = tmp_path / "moss.duckdb"
    _seed(db_path, [("a", 1)])

    counter = _install_connect_counter(monkeypatch, duck_module)
    repo = duck_module.DuckDBRepository(str(db_path))

    repo._table_exists("t")
    repo._fetch_rows("select count(*) from t")

    # Backward compatible: each call opens (and closes) its own connection.
    assert counter["opens"] == 2


def test_new_scope_sees_data_written_after_previous_scope(tmp_path):
    duck_module = _load_duck("duck_freshness")
    db_path = tmp_path / "moss.duckdb"
    _seed(db_path, [("a", 1)])
    repo = duck_module.DuckDBRepository(str(db_path))

    with repo.scoped_connection():
        assert repo._fetch_rows("select count(*) from t")[0][0] == 1

    # A separate writer updates the file after the scope closed.
    _seed(db_path, [("b", 2), ("c", 3)])

    with repo.scoped_connection():
        assert repo._fetch_rows("select count(*) from t")[0][0] == 3


def test_nested_scope_reuses_outer_connection(monkeypatch, tmp_path):
    duck_module = _load_duck("duck_nested")
    db_path = tmp_path / "moss.duckdb"
    _seed(db_path, [("a", 1)])

    counter = _install_connect_counter(monkeypatch, duck_module)
    repo = duck_module.DuckDBRepository(str(db_path))

    with repo.scoped_connection():
        with repo.scoped_connection():
            repo._fetch_rows("select 1")
        repo._fetch_rows("select 1")

    assert counter["opens"] == 1


def test_concurrent_scopes_are_isolated_and_correct(tmp_path):
    duck_module = _load_duck("duck_concurrency")
    db_path = tmp_path / "moss.duckdb"
    _seed(db_path, [("a", 10), ("b", 20), ("c", 30)])
    repo = duck_module.DuckDBRepository(str(db_path))

    errors: list[BaseException] = []
    results: list[int] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        try:
            barrier.wait(timeout=5)
            for _ in range(15):
                with repo.scoped_connection():
                    assert repo._table_exists("t") is True
                    total = repo._fetch_rows("select sum(v) from t")[0][0]
                    results.append(int(total))
        except BaseException as exc:  # noqa: BLE001 - surface any thread failure
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors, f"thread failures: {errors!r}"
    assert results, "expected results from worker threads"
    assert set(results) == {60}


def test_guarded_missing_path_scope_yields_none_and_empty(tmp_path):
    duck_module = _load_duck("duck_guarded_missing")
    missing = tmp_path / "not-created-yet.duckdb"
    repo = duck_module.DuckDBRepository(str(missing), guard_path_exists=True)

    with repo.scoped_connection() as conn:
        assert conn is None
        assert repo._fetch_rows("select 1") == []
        assert repo._table_exists("t") is False


def test_read_only_connection_helper_opens_and_closes(tmp_path):
    duck_module = _load_duck("duck_helper")
    db_path = tmp_path / "moss.duckdb"
    _seed(db_path, [("a", 1)])

    with duck_module.read_only_connection(str(db_path)) as conn:
        assert conn.execute("select count(*) from t").fetchone()[0] == 1

    # Read-only helper must not permit writes.
    with pytest.raises(real_duckdb.Error):
        with duck_module.read_only_connection(str(db_path)) as conn:
            conn.execute("insert into t values ('x', 9)")
