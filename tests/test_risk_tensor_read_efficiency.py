from __future__ import annotations

import json

import duckdb
import pytest

from tests.helpers import load_module


@pytest.fixture
def risk_repo_module():
    return load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )


def _bond_run(module, run_id, report_date, status="completed", **overrides):
    return {
        "run_id": run_id,
        "cache_key": module.BOND_ANALYTICS_CACHE_KEY,
        "job_name": "bond_analytics_materialize",
        "report_date": report_date,
        "status": status,
        "source_version": " sv_current ",
        "rule_version": " rv_current ",
        "cache_version": " cv_current ",
        "vendor_version": " ",
        **overrides,
    }


@pytest.mark.parametrize("backend", ["jsonl", "sql-authority", "frozen"])
@pytest.mark.parametrize("latest_status", ["completed", "failed", "running", "queued"])
def test_bond_lineage_keeps_latest_attempt_order_and_date_isolation(
    tmp_path, monkeypatch, risk_repo_module, backend, latest_status
):
    module = risk_repo_module
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    rows = [
        _bond_run(module, "z-earlier", "2026-08-31", source_version="sv_old"),
        _bond_run(module, "history", "2026-07-31"),
        _bond_run(module, "a-latest", "2026-08-31", latest_status),
        _bond_run(module, "wrong-key", "2026-08-31", cache_key="unrelated"),
        _bond_run(module, "padded-key", "2026-08-31", cache_key=f" {module.BOND_ANALYTICS_CACHE_KEY} "),
        _bond_run(module, "wrong-job", "2026-08-31", job_name="other_materialize"),
        _bond_run(module, "empty-date", ""),
    ]
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    repo = governance_module.GovernanceRepository(
        base_dir=governance_dir,
        backend_mode="jsonl" if backend == "frozen" else backend,
        sql_dsn=f"sqlite:///{(tmp_path / 'governance.db').as_posix()}" if backend == "sql-authority" else "",
    )
    if backend == "frozen":
        monkeypatch.setattr(
            governance_module,
            "frozen_system_governance_rows",
            lambda _base_dir, _stream: rows,
        )
    else:
        for row in rows:
            repo.append(governance_module.CACHE_BUILD_RUN_STREAM, row)
    monkeypatch.setattr(module, "GovernanceRepository", lambda **_kwargs: repo)

    current = module.load_latest_bond_analytics_lineage(
        governance_dir=str(governance_dir), report_date="2026-08-31"
    )
    history = module.load_latest_bond_analytics_lineage_by_report_date(
        governance_dir=str(governance_dir)
    )
    expected = {
        "source_version": "sv_current",
        "rule_version": "rv_current",
        "cache_version": "cv_current",
        "vendor_version": "vv_none",
    }
    assert current == (expected if latest_status == "completed" else None)
    assert history == {
        "2026-07-31": expected,
        **({"2026-08-31": expected} if latest_status == "completed" else {}),
    }


@pytest.mark.parametrize("reader", ["single", "all_dates"])
def test_bond_lineage_copies_only_its_cache_key_rows(
    tmp_path, monkeypatch, risk_repo_module, reader
):
    module = risk_repo_module
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )
    relevant = [
        _bond_run(module, "old", "2026-08-31", source_version="sv_old"),
        _bond_run(module, "current", "2026-08-31"),
        _bond_run(module, "history", "2026-07-31"),
    ]
    rows = relevant + [
        {"cache_key": f"unrelated:{index}", "nested": {"values": list(range(20))}}
        for index in range(1000)
    ]
    stream_path = tmp_path / f"{governance_module.CACHE_BUILD_RUN_STREAM}.jsonl"
    stream_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    repo = governance_module.GovernanceRepository(base_dir=tmp_path, backend_mode="jsonl")
    monkeypatch.setattr(module, "GovernanceRepository", lambda **_kwargs: repo)
    copied_rows = []
    original_deepcopy = governance_module.deepcopy

    def record_copy(row):
        copied_rows.append(row)
        return original_deepcopy(row)

    monkeypatch.setattr(governance_module, "deepcopy", record_copy)
    # Exercise both a freshly parsed stream and the cached, indexed stream.
    for _ in range(2):
        copied_rows.clear()
        if reader == "single":
            result = module.load_latest_bond_analytics_lineage(
                governance_dir=str(tmp_path), report_date="2026-08-31"
            )
            assert result["source_version"] == "sv_current"
        else:
            result = module.load_latest_bond_analytics_lineage_by_report_date(
                governance_dir=str(tmp_path)
            )
            assert set(result) == {"2026-07-31", "2026-08-31"}
        assert len(copied_rows) == len(relevant)


def _create_liability_table(conn):
    conn.execute(
        "create table fact_formal_tyw_balance_daily ("
        "report_date varchar, position_scope varchar, currency_basis varchar, "
        "source_version varchar, rule_version varchar)"
    )


def test_liability_lineage_fetches_one_summary_without_changing_values(
    tmp_path, monkeypatch, risk_repo_module
):
    module = risk_repo_module
    path = tmp_path / "risk-lineage.duckdb"
    versions = [
        ("sv_b", "rv_2"),
        (" sv_a ", " rv_1 "),
        ("\tsv_b\n", "\nrv_2\t"),
        (None, None),
        ("", " "),
        ("\u3000sv_a\u3000", "\u00a0rv_1\u00a0"),
    ]
    with duckdb.connect(str(path)) as conn:
        _create_liability_table(conn)
        conn.executemany(
            "insert into fact_formal_tyw_balance_daily values (?, ?, ?, ?, ?)",
            [("2026-08-31", "liability", "CNY", source, rule) for source, rule in versions],
        )
        conn.execute(
            "insert into fact_formal_tyw_balance_daily "
            "select report_date, position_scope, currency_basis, source_version, rule_version "
            "from fact_formal_tyw_balance_daily cross join range(999)"
        )
        conn.executemany(
            "insert into fact_formal_tyw_balance_daily values (?, ?, ?, ?, ?)",
            [
                ("2026-07-31", "liability", "CNY", "sv_ignore", "rv_ignore"),
                ("2026-08-31", "asset", "CNY", "sv_ignore", "rv_ignore"),
                ("2026-08-31", "liability", "USD", "sv_ignore", "rv_ignore"),
            ],
        )
    fetched_fact_rows = []
    original_connect = module._connect_read_only

    class TrackingConnection:
        def __init__(self, connection):
            self.connection = connection
            self.fact_query = False

        def execute(self, query, *args):
            self.fact_query = "from fact_formal_tyw_balance_daily" in query.lower()
            self.connection.execute(query, *args)
            return self

        def fetchall(self):
            rows = self.connection.fetchall()
            if self.fact_query:
                fetched_fact_rows.extend(rows)
            return rows

        def fetchone(self):
            row = self.connection.fetchone()
            if self.fact_query and row is not None:
                fetched_fact_rows.append(row)
            return row

        def close(self):
            self.connection.close()

    monkeypatch.setattr(module, "_connect_read_only", lambda path: TrackingConnection(original_connect(path)))
    state = module.load_current_tyw_liability_lineage_state(
        duckdb_path=str(path), report_date="2026-08-31"
    )
    assert state == module.TywLiabilityLineageState(
        availability="available", row_count=6000,
        source_version="sv_a__sv_b", rule_version="rv_1__rv_2",
    )
    assert len(fetched_fact_rows) == 1


@pytest.mark.parametrize(
    ("layout", "availability"),
    [("no_file", "unavailable"), ("missing_table", "missing_table"),
     ("malformed_table", "unavailable"), ("empty", "available")],
)
def test_liability_lineage_preserves_empty_and_unavailable_states(
    tmp_path, risk_repo_module, layout, availability
):
    module = risk_repo_module
    path = tmp_path / "risk-lineage.duckdb"
    if layout != "no_file":
        with duckdb.connect(str(path)) as conn:
            if layout == "empty":
                _create_liability_table(conn)
            elif layout == "malformed_table":
                conn.execute("create table fact_formal_tyw_balance_daily (report_date varchar)")
    assert module.load_current_tyw_liability_lineage_state(
        duckdb_path=str(path), report_date="2026-08-31"
    ) == module.TywLiabilityLineageState(availability=availability, row_count=0)
