from __future__ import annotations

import json

import duckdb
import pytest

from backend.app.repositories.bond_analytics_repo import (
    FACT_TABLE,
    ensure_bond_analytics_tables,
)
from backend.app.tasks import bond_analytics_materialize as task_module

REPORT_DATE = "2026-03-31"


def test_bond_materialize_marks_failed_when_interrupted_after_committed_purge(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    run_id = "bond-purge-interruption"

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_bond_analytics_tables(conn)
        conn.execute(
            f"""
            insert into {FACT_TABLE} (
              report_date, instrument_code, portfolio_name, cost_center,
              accounting_class, maturity_date, source_version
            ) values (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                REPORT_DATE,
                "OLD-ROW",
                "旧组合",
                "CC-OLD",
                "AC",
                "2027-03-31",
                "sv_old",
            ],
        )
    finally:
        conn.close()

    # The materialize-flow tests reload these modules and actor registration
    # updates the shared actor's ``fn`` in place. Resolve the live bindings from
    # that function so the monkeypatch cannot target a stale repository module.
    materialize_fn = task_module.materialize_bond_analytics_facts.fn
    task_globals = materialize_fn.__globals__
    repository_class = task_globals["BondAnalyticsRepository"]
    repository_globals = repository_class.replace_bond_analytics_rows.__globals__
    materialize_failure = task_globals["FormalComputeMaterializeFailure"]
    original_purge = repository_globals["commit_report_date_purge"]
    purge_observed = False

    def purge_then_interrupt(conn, **kwargs):
        nonlocal purge_observed
        original_purge(conn, **kwargs)
        purge_observed = (
            conn.execute(
                f"select count(*) from {FACT_TABLE} where report_date = ?",
                [REPORT_DATE],
            ).fetchone()[0]
            == 0
        )
        raise RuntimeError("synthetic interruption after committed purge")

    monkeypatch.setitem(
        repository_globals,
        "commit_report_date_purge",
        purge_then_interrupt,
    )

    with pytest.raises(
        materialize_failure,
        match="synthetic interruption after committed purge",
    ):
        materialize_fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            run_id=run_id,
            use_existing_curves_only=True,
        )

    assert purge_observed is True
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        assert (
            conn.execute(
                f"select count(*) from {FACT_TABLE} where report_date = ?",
                [REPORT_DATE],
            ).fetchone()[0]
            == 0
        )
    finally:
        conn.close()

    run_records = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    statuses = [record["status"] for record in run_records]
    assert statuses[0] == "queued"
    assert statuses[1:-1], "the run must enter running before its terminal failure"
    assert all(status == "running" for status in statuses[1:-1])
    assert statuses[-1] == "failed"
    assert statuses.count("failed") == 1
    assert all(record["run_id"] == run_id for record in run_records)
    assert all(record["report_date"] == REPORT_DATE for record in run_records)
    assert run_records[-1]["failure_category"] == "materialize_failure"
    assert (
        "synthetic interruption after committed purge"
        in run_records[-1]["error_message"]
    )
