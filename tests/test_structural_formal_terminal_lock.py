"""BD031: participating writers commit facts and terminal lineage in one lock.

Only temporary synthetic DuckDB/JSONL/SQLite storage is used. Thread events and
an actual zero-timeout file-lock probe force the old interleaving without a
sleep-based absence assertion. These tests do not imply cross-store atomicity
for unlocked readers or production publication acceptance.
"""
from __future__ import annotations

from contextlib import contextmanager
import importlib
import json
from pathlib import Path
from queue import Queue
from threading import Event, Thread, current_thread
from types import SimpleNamespace

import duckdb
import pytest
from sqlalchemy import event

from backend.app.core_finance.fixed_income_version_set import FIXED_INCOME_VERSION_SET
from backend.app.core_finance.module_registry import ensure_formal_module
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM, GovernanceRepository,
)
from backend.app.repositories.risk_tensor_repo import load_latest_bond_analytics_lineage
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure, FormalComputeMaterializeResult,
)
from backend.app.tasks import formal_compute_runtime as runtime

DAY = "2026-09-30"


@pytest.fixture(params=["jsonl", "sql-authority", "sql-shadow"])
def store(request, tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", request.param)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", f"sqlite:///{tmp_path / 'authority.sqlite'}")
    descriptor = ensure_formal_module(FIXED_INCOME_VERSION_SET.bond_analytics.descriptor)
    repo = GovernanceRepository(tmp_path / "governance")  # Initialize SQL before threads.
    db = tmp_path / "synthetic.duckdb"
    with duckdb.connect(str(db)) as conn:
        conn.execute("CREATE TABLE synthetic_fact(amount BIGINT, source_version VARCHAR, run_id VARCHAR)")
    return SimpleNamespace(repo=repo, db=db, descriptor=descriptor, mode=request.param)


def _run(store, name, callback, *, physical=True):
    return runtime.run_formal_materialize(
        descriptor=store.descriptor, job_name="bond_analytics_materialize",
        report_date=DAY, governance_dir=str(store.repo.base_dir),
        lock_base_dir=str(store.db.parent), duckdb_path=str(store.db) if physical else None,
        run_id=name, execute_materialization=callback,
    )


def _write(store, name):
    with duckdb.connect(str(store.db)) as conn:
        conn.execute("DELETE FROM synthetic_fact")
        conn.execute("INSERT INTO synthetic_fact VALUES (?, ?, ?)",
                     [101 if name == "A" else 202, f"sv_{name}", name])
    return FormalComputeMaterializeResult(source_version=f"sv_{name}", vendor_version=f"vv_{name}",
                                          payload={"synthetic_amount": 101 if name == "A" else 202})


def _fact(store):
    with duckdb.connect(str(store.db), read_only=True) as conn:
        return conn.execute("SELECT amount, source_version, run_id FROM synthetic_fact").fetchone()


def _probe(store):
    try:
        with acquire_lock(resolve_duckdb_writer_lock(store.db), base_dir=store.db.parent, timeout_seconds=0):
            return "available"
    except TimeoutError:
        return "held"


def _jsonl(store, stream):
    path = store.repo.base_dir / f"{stream}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def _terminal_rows(store):
    return [row for row in store.repo.read_all(CACHE_BUILD_RUN_STREAM)
            if row["status"] in {"completed", "failed"}]


@pytest.mark.parametrize("names", [("A", "B"), ("B", "A")])
def test_two_writers_preserve_fact_manifest_and_consuming_lineage_order(store, monkeypatch, names):
    first, second = names
    at_terminal, release_terminal, second_done = Event(), Event(), Event()
    probe_results, errors, entries, writes, outputs = Queue(), Queue(), [], [], {}
    real_append, real_acquire = GovernanceRepository.append_many_atomic, runtime.acquire_lock

    def delayed_terminal(repo, records):
        if records[0][1]["run_id"] == first:
            at_terminal.set()
            assert release_terminal.wait(15), "controller did not release terminal barrier"
        return real_append(repo, records)

    @contextmanager
    def probe_second(definition, **kwargs):
        if current_thread().name != "writer-second":
            with real_acquire(definition, **kwargs) as held:
                yield held
            return
        candidate = real_acquire(definition, **kwargs, timeout_seconds=0)
        try:
            held = candidate.__enter__()
        except TimeoutError:
            probe_results.put("blocked")
            with real_acquire(definition, **kwargs, timeout_seconds=10) as held:
                yield held
        else:
            probe_results.put("acquired")
            try:
                yield held
            finally:
                candidate.__exit__(None, None, None)

    def callback(name):
        if name == second:
            entries.append((_fact(store), store.repo.read_latest_manifest(store.descriptor.cache_key, report_date=DAY),
                            load_latest_bond_analytics_lineage(governance_dir=str(store.repo.base_dir), report_date=DAY)))
        result = _write(store, name)
        writes.append(name)
        return result

    def worker(name):
        try:
            outputs[name] = _run(store, name, lambda: callback(name))
        except BaseException as exc:
            errors.put(exc)
        finally:
            if name == second:
                second_done.set()

    monkeypatch.setattr(GovernanceRepository, "append_many_atomic", delayed_terminal)
    monkeypatch.setattr(runtime, "acquire_lock", probe_second)
    a, b = Thread(target=worker, args=(first,), name="writer-first"), Thread(target=worker, args=(second,), name="writer-second")
    try:
        a.start()
        assert at_terminal.wait(15)
        assert _fact(store)[1:] == (f"sv_{first}", first)
        b.start()
        probe = probe_results.get(timeout=15)
        if probe == "acquired":
            assert second_done.wait(15), "old-code branch must finish B before delayed A"
        release_terminal.set()
    finally:
        release_terminal.set()
        a.join(20)
        if b.ident is not None:
            b.join(20)
    assert not a.is_alive() and not b.is_alive()
    assert errors.empty(), list(errors.queue)
    assert _probe(store) == "available"
    fact = _fact(store)
    manifest = store.repo.read_latest_manifest(store.descriptor.cache_key, report_date=DAY)
    run = store.repo.read_latest_run(store.descriptor.cache_key, report_date=DAY)
    lineage = load_latest_bond_analytics_lineage(governance_dir=str(store.repo.base_dir), report_date=DAY)
    # Final physical readout is checked before the probe observation, so the red
    # result demonstrates wrong facts/lineage, not merely a different lock spy.
    assert fact[1] == manifest["source_version"] == run["source_version"] == lineage["source_version"] == f"sv_{second}"
    assert fact[0] == outputs[second]["synthetic_amount"]
    assert fact[2] == manifest["run_id"] == run["run_id"] == second
    assert [row["run_id"] for row in _terminal_rows(store)] == writes == [first, second]
    prior_fact, prior_manifest, prior_lineage = entries[0]
    assert prior_fact[1] == prior_manifest["source_version"] == prior_lineage["source_version"] == f"sv_{first}"
    assert probe == "blocked"
    assert all(output["payload"]["run"]["lock"] == store.descriptor.lock_key for output in outputs.values())


@pytest.mark.parametrize("failure", ["materialize", "system", "invalid_result", "terminal_jsonl"])
def test_failure_accounting_stays_under_writer_lock_without_duplicate_categories(store, monkeypatch, failure):
    observed = []
    original_append, original_file_append = GovernanceRepository.append, GovernanceRepository._append_unlocked

    def inspect_failure(repo, stream, row):
        if row.get("status") == "failed":
            observed.append(_probe(store))
        return original_append(repo, stream, row)

    def fail_completed(repo, stream, row):
        if failure == "terminal_jsonl" and row.get("status") == "completed":
            raise OSError("synthetic terminal JSONL failure after manifest")
        return original_file_append(repo, stream, row)

    def callback():
        _write(store, "A")
        if failure == "materialize":
            raise FormalComputeMaterializeFailure(source_version="sv_A", vendor_version="vv_A", message="synthetic materialize failure")
        if failure == "system":
            raise ValueError("synthetic callback failure")
        if failure == "invalid_result":
            return {"unexpected": True}
        return FormalComputeMaterializeResult(source_version="sv_A", vendor_version="vv_A")

    monkeypatch.setattr(GovernanceRepository, "append", inspect_failure)
    monkeypatch.setattr(GovernanceRepository, "_append_unlocked", fail_completed)
    with pytest.raises(Exception):
        _run(store, "A", callback)
    rows = _terminal_rows(store)
    assert len(rows) == 1 and rows[0]["status"] == "failed"
    expected = "materialize_failure" if failure == "materialize" else "governance_terminal_write_failure" if failure == "terminal_jsonl" else "system_exception"
    assert rows[0]["failure_category"] == expected
    assert rows[0]["source_version"] == ("sv_A" if failure in {"materialize", "terminal_jsonl"} else store.descriptor.running_source_version)
    assert rows[0]["vendor_version"] == ("vv_A" if failure in {"materialize", "terminal_jsonl"} else store.descriptor.vendor_version)
    assert not store.repo.read_all(CACHE_MANIFEST_STREAM)
    assert not _jsonl(store, CACHE_MANIFEST_STREAM)
    assert [row["status"] for row in _jsonl(store, CACHE_BUILD_RUN_STREAM)] == ["queued", "running", "failed"]
    assert _fact(store)[1] == "sv_A"  # Runtime never promised to roll back committed facts.
    assert _probe(store) == "available"
    monkeypatch.setattr(GovernanceRepository, "_append_unlocked", original_file_append)
    assert _run(store, "B", lambda: _write(store, "B"))["status"] == "completed"
    assert store.repo.read_latest_manifest(store.descriptor.cache_key)["source_version"] == _fact(store)[1] == "sv_B"
    assert observed == ["held"]


def test_sql_commit_failure_rolls_back_authority_and_shadow_before_failure_record(store, monkeypatch):
    if store.mode == "jsonl":
        # Exercise the same terminal transaction-failure contract without SQL.
        def fail_terminal(_records):
            raise OSError("synthetic terminal commit failure")
        monkeypatch.setattr(store.repo, "append_many_atomic", fail_terminal)
    else:
        def fail_commit(connection):
            # Only the terminal transaction contains the manifest insert.
            if connection.exec_driver_sql("SELECT COUNT(*) FROM cache_manifest").scalar():
                raise OSError("synthetic terminal commit failure")
        event.listen(store.repo._sql_engine, "commit", fail_commit)
    monkeypatch.setattr(runtime, "GovernanceRepository", lambda **_kwargs: store.repo)
    held = []
    append = store.repo.append

    def inspect(stream, row):
        if row.get("status") == "failed":
            held.append(_probe(store))
        return append(stream, row)
    monkeypatch.setattr(store.repo, "append", inspect)
    with pytest.raises(OSError, match="synthetic terminal commit failure"):
        _run(store, "A", lambda: _write(store, "A"))
    assert not store.repo.read_all(CACHE_MANIFEST_STREAM)
    assert not _jsonl(store, CACHE_MANIFEST_STREAM)
    assert [row["status"] for row in store.repo.read_all(CACHE_BUILD_RUN_STREAM)] == ["queued", "running", "failed"]
    assert [row["status"] for row in _jsonl(store, CACHE_BUILD_RUN_STREAM)] == ["queued", "running", "failed"]
    assert _terminal_rows(store)[0]["failure_category"] == "governance_terminal_write_failure"
    assert _terminal_rows(store)[0]["source_version"] == "sv_A"
    assert held == ["held"]
    assert _probe(store) == "available"


@pytest.mark.parametrize("phase", ["callback", "terminal"])
def test_interrupt_propagates_and_releases_lock_without_false_completion(store, monkeypatch, phase):
    def interrupted():
        _write(store, "A")
        raise KeyboardInterrupt("synthetic interrupt")
    if phase == "terminal":
        def terminal_interrupt(_repo, _records):
            raise KeyboardInterrupt("synthetic interrupt")
        monkeypatch.setattr(GovernanceRepository, "append_many_atomic", terminal_interrupt)
    with pytest.raises(KeyboardInterrupt, match="synthetic interrupt"):
        _run(store, "A", interrupted if phase == "callback" else lambda: _write(store, "A"))
    assert _terminal_rows(store) == []
    assert not store.repo.read_all(CACHE_MANIFEST_STREAM)
    assert _probe(store) == "available"


@pytest.mark.parametrize("phase", ["callback", "terminal"])
def test_secondary_failure_record_error_propagates_and_never_completes(store, monkeypatch, phase):
    held = []
    original = GovernanceRepository.append

    def secondary(repo, stream, row):
        if row.get("status") == "failed":
            held.append(_probe(store))
            raise OSError("synthetic failure record unavailable")
        return original(repo, stream, row)

    def initial():
        raise ValueError("synthetic initial failure")

    if phase == "terminal":
        monkeypatch.setattr(GovernanceRepository, "append_many_atomic", lambda *_args: initial())
    monkeypatch.setattr(GovernanceRepository, "append", secondary)
    with pytest.raises(OSError, match="failure record unavailable") as error:
        _run(store, "A", initial if phase == "callback" else lambda: _write(store, "A"))
    assert isinstance(error.value.__context__, ValueError)
    assert _terminal_rows(store) == []
    assert not store.repo.read_all(CACHE_MANIFEST_STREAM)
    assert _probe(store) == "available"
    assert held == ["held"]


def test_physical_acquisition_failure_never_executes_callback(store, monkeypatch):
    real = runtime.acquire_lock

    def immediate(definition, **kwargs):
        return real(definition, **kwargs, timeout_seconds=0)
    monkeypatch.setattr(runtime, "acquire_lock", immediate)
    with acquire_lock(resolve_duckdb_writer_lock(store.db), base_dir=store.db.parent):
        with pytest.raises(TimeoutError):
            _run(store, "A", lambda: pytest.fail("callback must not run without lock"))
    assert _terminal_rows(store)[0]["failure_category"] == "system_exception"
    assert not store.repo.read_all(CACHE_MANIFEST_STREAM)
    assert _fact(store) is None
    assert _probe(store) == "available"


def test_release_error_propagates_after_terminal_commit_without_second_failure(store, monkeypatch):
    real = runtime.acquire_lock

    @contextmanager
    def bad_release(definition, **kwargs):
        with real(definition, **kwargs) as held:
            yield held
        raise OSError("synthetic lock release failure")
    monkeypatch.setattr(runtime, "acquire_lock", bad_release)
    with pytest.raises(OSError, match="synthetic lock release failure"):
        _run(store, "A", lambda: _write(store, "A"))
    assert [row["status"] for row in _terminal_rows(store)] == ["completed"]
    assert store.repo.read_latest_manifest(store.descriptor.cache_key)["source_version"] == _fact(store)[1] == "sv_A"
    assert _probe(store) == "available"


def test_legacy_descriptor_lock_and_queued_running_order_are_preserved(store, monkeypatch):
    real, calls = runtime.acquire_lock, []

    @contextmanager
    def capture(definition, **kwargs):
        calls.append(definition.key)
        assert [row["status"] for row in store.repo.read_all(CACHE_BUILD_RUN_STREAM)] == ["queued", "running"]
        with real(definition, **kwargs) as held:
            yield held
    monkeypatch.setattr(runtime, "acquire_lock", capture)
    output = _run(store, "A", lambda: _write(store, "A"), physical=False)
    assert calls == [store.descriptor.lock_key]
    assert output["status"] == "completed"
    assert output["lock"] == store.descriptor.lock_key


def test_other_database_lock_does_not_block_this_physical_writer(store):
    other = store.db.with_name("other.duckdb")
    with acquire_lock(resolve_duckdb_writer_lock(other), base_dir=other.parent):
        assert _run(store, "A", lambda: _write(store, "A"))["status"] == "completed"
    assert _probe(store) == "available"


@pytest.mark.parametrize("module,entry,kwargs", [
    ("balance_analysis_materialize", "_materialize_balance_analysis_facts", {"report_date": DAY}),
    ("bond_analytics_materialize", "_materialize_bond_analytics_facts", {"report_date": DAY}),
    ("yield_curve_materialize", "_materialize_yield_curve_month_end_backfill", {"start_date": "2026-09-01", "end_date": DAY}),
    ("yield_curve_materialize", "_materialize_yield_curve", {"trade_date": DAY}),
    ("risk_tensor_materialize", "_materialize_risk_tensor_facts", {"report_date": DAY}),
])
def test_all_five_entrypoints_supply_same_physical_lock_identity(tmp_path, monkeypatch, module, entry, kwargs):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    task = importlib.import_module(f"backend.app.tasks.{module}")
    db, governance, seen = tmp_path / "synthetic.duckdb", tmp_path / "governance", []
    monkeypatch.setattr(task, "get_settings", lambda: SimpleNamespace())
    if module == "balance_analysis_materialize":
        monkeypatch.setattr(task, "_materialize_run_identity", lambda **_kwargs: {})
    if module == "bond_analytics_materialize":
        monkeypatch.setattr(task, "_invalidate_bond_analytics_worker_caches", lambda _day: None)

    class StopBeforeExpensiveCallback(Exception):
        pass

    def capture(**arguments):
        seen.append(arguments)
        raise StopBeforeExpensiveCallback
    monkeypatch.setattr(task, "run_formal_materialize", capture)
    with pytest.raises(StopBeforeExpensiveCallback):
        getattr(task, entry)(**kwargs, duckdb_path=str(db), governance_dir=str(governance))
    assert len(seen) == 1
    assert seen[0]["duckdb_path"] == str(db)
    assert seen[0]["lock_base_dir"] == str(db.parent)
    assert seen[0]["governance_dir"] == str(governance)
