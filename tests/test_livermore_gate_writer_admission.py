"""Regression proof for the existing gate writer's database admission."""

from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest
import requests

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.tasks import livermore_gate_supplement as task

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_livermore]


class ForbiddenIO(BaseException):
    pass


def _rows(conn):
    return conn.execute(
        "select cast(trade_date as varchar), breadth_5d, limit_up_quality_ok, "
        "source_version, vendor_version, rule_version, run_id "
        "from fact_livermore_gate_supplement_daily order by trade_date"
    ).fetchall()


def _seed(path):
    with duckdb.connect(str(path)) as conn:
        apply_pending_migrations_on_connection(conn)
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily "
            "(trade_date, breadth_5d, limit_up_quality_ok, source_version, "
            "vendor_version, rule_version, run_id) values "
            "('2026-06-01', .25, false, 'old', 'old', 'old', 'old'), "
            "('2026-05-29', .5, true, 'control', 'control', 'control', 'control')"
        )
        return _rows(conn)


def _observe(monkeypatch, path):
    events = []
    held = set()
    forbidden = {"http": 0, "destination": 0}
    native = duckdb.connect
    path_key = resolve_duckdb_writer_lock(path).key

    @contextmanager
    def observed_lock(definition, **kwargs):
        kind = "path" if definition.key == path_key else "gate"
        assert definition.key in {path_key, task.LIVERMORE_GATE_SUPPLEMENT_LOCK.key}
        events.append(f"{kind}:attempt")
        entered = False
        try:
            with acquire_lock(definition, **{**kwargs, "timeout_seconds": .05}):
                entered = True
                held.add(kind)
                events.append(f"{kind}:entered")
                try:
                    yield
                finally:
                    held.remove(kind)
        finally:
            if entered:
                events.append(f"{kind}:released")

    class ObservedConnection:
        def __init__(self, conn):
            self.conn = conn

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def close(self):
            assert held == {"path", "gate"}
            self.conn.close()
            events.append("close")

    def connect(database=":memory:", *args, **kwargs):
        if Path(database).resolve() != path.resolve():
            forbidden["destination"] += 1
            raise ForbiddenIO("unexpected database destination")
        events.append("open:attempt")
        assert held == {"path", "gate"}, "native open precedes canonical admission"
        assert kwargs.get("read_only") is False
        conn = native(database, *args, **kwargs)
        events.append("open")
        return ObservedConnection(conn)

    def no_http(self, method, url, *args, **kwargs):
        forbidden["http"] += 1
        raise ForbiddenIO("real HTTP is forbidden")

    monkeypatch.setattr(task, "acquire_lock", observed_lock)
    monkeypatch.setattr(task.duckdb, "connect", connect)
    monkeypatch.setattr(requests.sessions.Session, "request", no_http)
    return events, forbidden, native


def _assert_containment(path, forbidden):
    assert forbidden == {"http": 0, "destination": 0}
    with pytest.raises(ForbiddenIO):
        requests.Session().request(method="GET", url="https://guard-self-check.invalid")
    with pytest.raises(ForbiddenIO):
        duckdb.connect(str(path.parent / "unexpected.duckdb"), read_only=False)
    assert forbidden == {"http": 1, "destination": 1}


def _reacquire_in_child(path, tmp_path):
    code = """
import json, sys
from pathlib import Path
from _pytest_duckdb_guard import install_pytest_duckdb_guard, register_pytest_duckdb_temp_root
install_pytest_duckdb_guard(repo_root=Path.cwd())
register_pytest_duckdb_temp_root(Path(sys.argv[2]))
import duckdb, requests
counts = {'http': 0, 'database': 0}
class ForbiddenIO(BaseException): pass
def no_database(*a, **kw):
    counts['database'] += 1
    raise ForbiddenIO()
def no_http(self, method, url, *a, **kw):
    counts['http'] += 1
    raise ForbiddenIO()
duckdb.connect = no_database
requests.sessions.Session.request = no_http
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
path = Path(sys.argv[1])
with acquire_lock(resolve_duckdb_writer_lock(path), base_dir=path.parent, timeout_seconds=.5):
    acquired = True
assert counts == {'http': 0, 'database': 0}
print(json.dumps({'acquired': acquired, 'business_calls': counts}))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(path), str(tmp_path)],
        capture_output=True, text=True, timeout=10, check=True,
    )
    receipt = json.loads(result.stdout.strip().splitlines()[-1])
    assert receipt == {"acquired": True, "business_calls": {"http": 0, "database": 0}}


@pytest.mark.parametrize("fail_write", [False, True])
def test_gate_writer_closes_before_release_and_preserves_rows(tmp_path, monkeypatch, fail_write):
    path = tmp_path / "gate.duckdb"
    before = _seed(path)
    events, forbidden, native = _observe(monkeypatch, path)
    rows = [{
        "trade_date": "2026-06-01", "breadth_5d": .75, "limit_up_quality_ok": True,
        "source_version": "new-source", "vendor_version": "new-vendor",
    }]
    if fail_write:
        rows.append({"trade_date": "2026-06-02", "breadth_5d": "invalid"})
        with pytest.raises(ValueError):
            task.materialize_livermore_gate_supplement_daily(
                duckdb_path=str(path), rows=rows, run_id="gate-test",
            )
    else:
        result = task.materialize_livermore_gate_supplement_daily(
            duckdb_path=str(path), rows=rows, run_id="gate-test",
        )
        assert result["status"] == "completed" and result["row_count"] == 1
        assert result["run_id"] == "gate-test"
        assert result["gate_history"]["status"] == "skipped_not_replayable"
    assert events == [
        "path:attempt", "path:entered", "gate:attempt", "gate:entered",
        "open:attempt", "open", "close", "gate:released", "path:released",
    ]
    with native(str(path), read_only=True) as conn:
        after = _rows(conn)
    if fail_write:
        assert after == before
    else:
        assert after == [before[0], (
            "2026-06-01", .75, True, "new-source", "new-vendor", task.RULE_VERSION, "gate-test",
        )]
    _reacquire_in_child(path, tmp_path)
    _assert_containment(path, forbidden)


@pytest.mark.parametrize("block_path", [True, False])
def test_gate_admission_failure_does_not_open_database(tmp_path, monkeypatch, block_path):
    path = tmp_path / "gate.duckdb"
    _seed(path)
    definition = resolve_duckdb_writer_lock(path) if block_path else task.LIVERMORE_GATE_SUPPLEMENT_LOCK
    with acquire_lock(definition, base_dir=path.parent):
        events, forbidden, _ = _observe(monkeypatch, path)
        with pytest.raises(TimeoutError):
            task.materialize_livermore_gate_supplement_daily(duckdb_path=str(path), rows=[])
    assert not any(event.startswith("open") for event in events)
    if block_path:
        assert events == ["path:attempt"]
    else:
        assert events == ["path:attempt", "path:entered", "gate:attempt", "path:released"]
    _reacquire_in_child(path, tmp_path)
    _assert_containment(path, forbidden)
