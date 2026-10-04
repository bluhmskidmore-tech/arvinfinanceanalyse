"""Bond refresh diagnostics and fail-fast storage access without live inputs."""

from contextlib import ExitStack, contextmanager
from datetime import date
from itertools import count
from queue import Queue
import subprocess
import sys
from threading import Thread
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import Mock

import duckdb
import pytest

from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from tests.helpers import load_module

REPORT_DATE = "2026-08-31"


@contextmanager
def _external_read_only_connection(duckdb_path):
    """Keep a separate process's shared file lock until the test releases it."""
    code = (
        "import sys, duckdb; "
        "conn = duckdb.connect(sys.argv[1], read_only=True); "
        "print('reader-ready', flush=True); "
        "sys.stdin.read(1); conn.close()"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(duckdb_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    readiness = Queue()
    Thread(target=lambda: readiness.put(process.stdout.readline()), daemon=True).start()
    try:
        assert readiness.get(timeout=15).strip() == "reader-ready"
        yield
    finally:
        try:
            process.communicate(input="x", timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)


@pytest.fixture
def bond_refresh(tmp_path, monkeypatch):
    load_module("backend.app.core_finance.module_registry", "backend/app/core_finance/module_registry.py")
    load_module("backend.app.tasks.formal_compute_runtime", "backend/app/tasks/formal_compute_runtime.py")
    task = load_module(
        "backend.app.tasks.bond_analytics_materialize", "backend/app/tasks/bond_analytics_materialize.py"
    )
    duckdb_path = tmp_path / "bond.duckdb"
    governance_path = tmp_path / "governance"
    with duckdb.connect(str(duckdb_path)) as conn:
        conn.execute("create table sentinel (value integer)")
        conn.execute("insert into sentinel values (7)")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
    monkeypatch.setattr(
        task, "get_settings", lambda: SimpleNamespace(duckdb_path=duckdb_path, governance_path=governance_path)
    )
    monkeypatch.setattr(task, "_invalidate_bond_analytics_worker_caches", Mock())
    monkeypatch.setattr(task, "_yield_curve_anchor_dates_for_materialization", lambda **_: (REPORT_DATE,))
    clock = count(0.0, 0.25)
    monkeypatch.setattr(task, "perf_counter", lambda: next(clock))
    snapshot_rows = [{"instrument_code": "BOND-TEST", "source_version": "sv_bond_test"}]
    analytics_rows = [{"instrument_code": "BOND-TEST"}]
    repo = SimpleNamespace(
        load_snapshot_rows=Mock(return_value=snapshot_rows),
        replace_bond_analytics_rows=Mock(),
        invalidate_report_date_facts=Mock(),
    )
    monkeypatch.setattr(task, "BondAnalyticsRepository", lambda _: repo)
    ensure = Mock()
    compute = Mock(return_value=analytics_rows)
    monkeypatch.setattr(task, "ensure_yield_curve_inputs_on_or_before", ensure)
    monkeypatch.setattr(task, "compute_bond_analytics_rows", compute)
    governance = GovernanceRepository(base_dir=governance_path, backend_mode="jsonl")

    def run(**kwargs):
        return task._materialize_bond_analytics_facts(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_path),
            run_id="bond-runtime-test",
            **kwargs,
        )

    return SimpleNamespace(
        task=task,
        run=run,
        duckdb_path=duckdb_path,
        governance_path=governance_path,
        repo=repo,
        ensure=ensure,
        compute=compute,
        snapshot_rows=snapshot_rows,
        analytics_rows=analytics_rows,
        records=lambda: governance.read_all(CACHE_BUILD_RUN_STREAM),
    )


def test_read_only_process_lock_fails_preflight_before_vendor_or_compute(bond_refresh):
    env = bond_refresh
    with _external_read_only_connection(env.duckdb_path):
        started = perf_counter()
        with pytest.raises(env.task.FormalComputeMaterializeFailure, match="duckdb_write_preflight_failed:"):
            env.run()
        assert perf_counter() - started < 5.0

    env.ensure.assert_not_called()
    env.repo.load_snapshot_rows.assert_not_called()
    env.compute.assert_not_called()
    env.repo.replace_bond_analytics_rows.assert_not_called()
    records = env.records()
    assert records[-1]["status"] == "failed"
    assert records[-1]["failure_category"] == "materialize_failure"
    assert [(row["phase"], row["phase_status"]) for row in records if "phase" in row] == [
        ("write_access", "running"),
        ("write_access", "failed"),
    ]


def test_success_closes_preflight_before_vendor_and_records_each_phase(bond_refresh):
    from backend.app.services import bond_analytics_service

    env = bond_refresh
    observed_inflight = []

    def verify_closed_probe(*args, **kwargs):
        # DuckDB rejects a read-only connection while the same process still
        # holds a read-write connection. This also checks no schema was added.
        with duckdb.connect(str(env.duckdb_path), read_only=True) as conn:
            assert conn.execute("show tables").fetchall() == [("sentinel",)]
            assert conn.execute("select * from sentinel").fetchall() == [(7,)]
        # Phase records are the latest rows while work is running. The same
        # guard used by refresh dispatch must still recognize this active run.
        before = env.records()
        inflight = bond_analytics_service._latest_inflight_refresh(
            SimpleNamespace(governance_path=env.governance_path), report_date=REPORT_DATE
        )
        assert inflight is not None
        assert inflight["run_id"] == "bond-runtime-test"
        assert inflight["status"] == inflight["phase_status"] == "running"
        assert not bond_analytics_service._is_stale_inflight_record(inflight)
        assert inflight["queued_at"] and inflight["started_at"] and inflight["lock"]
        assert env.records() == before
        observed_inflight.append(inflight)
        return env.analytics_rows

    env.ensure.side_effect = verify_closed_probe
    env.compute.side_effect = verify_closed_probe

    result = env.run()

    env.ensure.assert_called_once_with(
        anchor_dates=(REPORT_DATE,), duckdb_path=str(env.duckdb_path), vendor_timeout_seconds=180.0
    )
    env.compute.assert_called_once_with(env.snapshot_rows, date.fromisoformat(REPORT_DATE))
    env.repo.replace_bond_analytics_rows.assert_called_once_with(
        report_date=REPORT_DATE, rows=env.analytics_rows
    )
    records = env.records()
    phases = ("write_access", "curve_prepare", "source_read", "compute", "write")
    assert {row["run_id"] for row in records} == {result["run_id"]}
    assert records[-1]["status"] == result["status"] == "completed"
    assert "phase" not in records[-1]
    assert [(row["phase"], row["phase_status"]) for row in records if "phase" in row] == [
        (phase, status) for phase in phases for status in ("running", "completed")
    ]
    assert all(row["status"] == "running" for row in records if "phase" in row)
    assert [row["phase"] for row in observed_inflight] == ["curve_prepare", "compute"]
    assert len({row["started_at"] for row in observed_inflight}) == 1
    timings = {phase: 0.25 for phase in phases}
    assert result["phase_timings_seconds"] == timings
    assert result["payload"]["result"]["phase_timings_seconds"] == timings
    assert {
        row["phase"]: row["phase_elapsed_seconds"]
        for row in records
        if row.get("phase_status") == "completed"
    } == timings


def test_late_read_only_conflict_is_still_a_write_failure(bond_refresh):
    env = bond_refresh
    with ExitStack() as stack:
        def compute_then_lock(*_args):
            stack.enter_context(_external_read_only_connection(env.duckdb_path))
            return env.analytics_rows

        def write(**_kwargs):
            with duckdb.connect(str(env.duckdb_path), read_only=False):
                pass

        env.compute.side_effect = compute_then_lock
        env.repo.replace_bond_analytics_rows.side_effect = write
        with pytest.raises(env.task.FormalComputeMaterializeFailure) as caught:
            env.run()

    assert "duckdb_write_preflight_failed" not in str(caught.value)
    env.compute.assert_called_once()
    env.repo.replace_bond_analytics_rows.assert_called_once()
    records = env.records()
    assert records[-1]["status"] == "failed"
    failed_phases = [row for row in records if row.get("phase_status") == "failed"]
    assert len(failed_phases) == 1
    assert failed_phases[0]["phase"] == "write"
    assert failed_phases[0]["phase_elapsed_seconds"] == 0.25
    assert not any(row["status"] == "completed" for row in records)


@pytest.mark.parametrize("changed_version", [False, True])
def test_existing_curves_skip_vendor_but_still_validate_selected_versions(
    bond_refresh, monkeypatch, changed_version
):
    from backend.app.repositories.yield_curve_repo import YieldCurveRepository

    env = bond_refresh
    expected = [
        {
            "anchor_date": REPORT_DATE,
            "curve_type": curve_type,
            "snapshot_date": REPORT_DATE,
            "source_version": f"sv_{curve_type}",
            "vendor_name": "test_vendor",
            "vendor_version": "vv_test",
            "rule_version": "rv_test",
        }
        for curve_type in ("treasury", "cdb", "aaa_credit")
    ]
    selected = {
        (REPORT_DATE, item["curve_type"]): (
            {
                **item,
                "trade_date": REPORT_DATE,
                "curve": {tenor: "2.0" for tenor in ("6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y")},
            },
            None,
        )
        for item in expected
    }
    if changed_version:
        selected[(REPORT_DATE, "treasury")][0]["source_version"] = "sv_drifted"
    selector = Mock(return_value=selected)
    monkeypatch.setattr(YieldCurveRepository, "resolve_curve_snapshots_many", selector)

    if changed_version:
        with pytest.raises(ValueError, match="curve source_version changed"):
            env.run(use_existing_curves_only=True, expected_curve_snapshots=expected)
        env.compute.assert_not_called()
        env.repo.replace_bond_analytics_rows.assert_not_called()
        records = env.records()
        assert records[-1]["status"] == "failed"
        assert [row["phase"] for row in records if row.get("phase_status") == "failed"] == [
            "curve_validation"
        ]
    else:
        result = env.run(use_existing_curves_only=True, expected_curve_snapshots=expected)
        assert result["status"] == "completed"
        assert len(result["qualified_curve_dependencies"]) == 3
        assert "curve_validation" in result["phase_timings_seconds"]
        assert "curve_prepare" not in result["phase_timings_seconds"]
    selector.assert_called_once()
    env.ensure.assert_not_called()
