from __future__ import annotations

import json
from pathlib import Path

import duckdb

import scripts.run_fable_extension_study as study_module
from scripts.run_fable_extension_study import run_extension_study_from_duckdb


def _write_contract(path: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / (
        "docs/stock_analysis_fable_extension_study_contract.json"
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["inference"]["bootstrap_iterations"] = 100
    payload["inference"]["bootstrap_seed"] = 17
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _seed_db(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date date,
              stock_code varchar,
              stock_name varchar,
              signal_kind varchar,
              candidate_rank integer,
              market_state varchar,
              signal_close double,
              entry_date date,
              entry_executable boolean,
              entry_block_reason varchar,
              return_5d_net double,
              return_5d_net_adj double,
              return_10d_net double,
              return_10d_net_adj double,
              return_20d_net double,
              return_20d_net_adj double,
              data_status varchar,
              formula_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history values
              (date '2026-06-01', '000001.SZ', 'A', 'stock_candidate', 1, 'WARM',
               108.0, date '2026-06-02', true, null, 0.01, 0.01, 0.02, 0.02,
               0.03, 0.03, 'complete', 'fv_test', 'run-1')
            """
        )
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date date,
              stock_code varchar,
              signal_kind varchar,
              ma20 double
            )
            """
        )
        conn.execute(
            "insert into livermore_candidate_history values (date '2026-06-01', '000001.SZ', 'stock_candidate', 100.0)"
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date date,
              stock_code varchar,
              close_value double,
              tradestatus varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', 10.0, 'Trading')",
            [(f"2026-06-{day:02d}",) for day in range(2, 22)],
        )
    finally:
        conn.close()


def test_duckdb_runner_reads_source_without_mutating_it(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "study.duckdb"
    _seed_db(db_path)
    contract_path = _write_contract(tmp_path / "contract.json")
    monkeypatch.setattr(
        study_module,
        "load_gate_exposure_by_date",
        lambda conn, start, end: {"2026-06-01": {"state": "HOT", "source": "replayed"}},
    )

    result = run_extension_study_from_duckdb(
        db_path=db_path,
        contract_path=contract_path,
        output_root=tmp_path / "runs",
        run_id="db-fixture-001",
    )

    assert result["summary"]["source_metadata"]["raw_execution_row_count"] == 1
    assert result["summary"]["state_lineage"]["conflict_count"] == 1
    read_only = duckdb.connect(str(db_path), read_only=True)
    try:
        assert (
            read_only.execute(
                "select count(*) from livermore_candidate_execution_history"
            ).fetchone()[0]
            == 1
        )
    finally:
        read_only.close()
