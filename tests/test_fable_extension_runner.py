from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import duckdb
import pytest

from scripts.run_fable_extension_study import (
    load_extension_study_rows,
    load_study_contract,
    load_trading_calendar,
    run_extension_study_from_inputs,
)


def _contract_payload() -> dict[str, Any]:
    source = Path(__file__).resolve().parents[1] / (
        "docs/stock_analysis_fable_extension_study_contract.json"
    )
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["inference"]["bootstrap_iterations"] = 100
    payload["inference"]["bootstrap_seed"] = 17
    return payload


def _write_contract(path: Path, payload: dict[str, Any] | None = None) -> Path:
    path.write_text(
        json.dumps(payload or _contract_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _study_row(
    stock_code: str, *, extension: float, adjusted: float | None
) -> dict[str, object]:
    return {
        "signal_date": "2026-06-01",
        "entry_date": "2026-06-02",
        "stock_code": stock_code,
        "candidate_rank": 1,
        "entry_executable": True,
        "signal_close_value": 100.0 * (1.0 + extension),
        "signal_sma20_value": 100.0,
        "signal_feature_status": "ready",
        "return_5d_net_adj": 0.01,
        "return_5d_net": 0.009,
        "return_10d_net_adj": 0.02,
        "return_10d_net": 0.019,
        "return_20d_net_adj": adjusted,
        "return_20d_net": 0.03,
    }


def test_contract_locks_research_boundary_and_causal_timing(tmp_path: Path) -> None:
    contract = load_study_contract(_write_contract(tmp_path / "contract.json"))

    assert contract["study_version"] == "rv_fable_extension_study_v1"
    assert contract["primary_endpoint"]["field"] == "return_20d_net_adj"
    assert contract["gate_state"]["as_of"] == "signal_date_close"

    invalid = _contract_payload()
    invalid["actionable"] = True
    with pytest.raises(ValueError, match="actionable must remain false"):
        load_study_contract(_write_contract(tmp_path / "invalid.json", invalid))


def test_execution_loader_collapses_exact_duplicates_and_preserves_raw_sensitivity() -> (
    None
):
    conn = duckdb.connect()
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date date,
              stock_code varchar,
              stock_name varchar,
              signal_kind varchar,
              candidate_rank integer,
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
              (date '2026-06-01', '000001.SZ', 'A', 'stock_candidate', 1, 108.0,
               date '2026-06-02', true, null, 0.01, 0.009, 0.02, 0.019,
               0.03, null, 'complete', 'fv_test', 'run-1'),
              (date '2026-06-01', '000001.SZ', 'A', 'stock_candidate', 1, 108.0,
               date '2026-06-02', true, null, 0.01, 0.009, 0.02, 0.019,
               0.03, null, 'complete', 'fv_test', 'run-1')
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

        rows, metadata = load_extension_study_rows(conn, signal_kind="stock_candidate")
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0]["return_20d_net"] == 0.03
    assert rows[0]["return_20d_net_adj"] is None
    assert rows[0]["signal_sma20_value"] == 100.0
    assert metadata["raw_execution_row_count"] == 2
    assert metadata["exact_duplicate_row_count"] == 1


def test_trading_calendar_excludes_null_status_and_invalid_close() -> None:
    conn = duckdb.connect()
    try:
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
        conn.execute(
            """
            insert into choice_stock_daily_observation values
              (date '2026-06-02', '000001.SZ', 10.0, 'Trading'),
              (date '2026-06-03', '000001.SZ', 0.0, 'Trading'),
              (date '2026-06-04', '000001.SZ', 11.0, null),
              (date '2026-06-05', '000001.SZ', 12.0, 'Trading')
            """
        )

        dates = load_trading_calendar(conn)
    finally:
        conn.close()

    assert dates == ["2026-06-02", "2026-06-05"]


def test_runner_writes_append_only_reproducible_research_artifacts(
    tmp_path: Path,
) -> None:
    contract = load_study_contract(_write_contract(tmp_path / "contract.json"))
    rows = [
        _study_row("000001.SZ", extension=0.04, adjusted=0.02),
        _study_row("000002.SZ", extension=0.08, adjusted=None),
    ]
    trading_dates = [f"2026-06-{day:02d}" for day in range(2, 22)]
    macro_points = {"2026-06-01": {"state": "HOT", "source": "replayed"}}
    output_root = tmp_path / "runs"

    first = run_extension_study_from_inputs(
        rows=rows,
        trading_dates=trading_dates,
        macro_points=macro_points,
        contract=contract,
        source_metadata={"fixture": True},
        output_root=output_root,
        run_id="fixture-001",
    )
    run_dir = output_root / "fixture-001"

    assert {path.name for path in run_dir.iterdir()} == {
        "README.md",
        "candidate_panel.csv",
        "extension_bins.csv",
        "gate_state_extension_cells.csv",
        "run_manifest.json",
        "sample_accountability.csv",
        "study_summary.json",
    }
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["research_only"] is True
    assert manifest["formal_use_allowed"] is False
    assert manifest["result_sha256"] == first["result_sha256"]
    assert manifest["script_path"] == "scripts/run_fable_extension_study.py"
    assert len(manifest["script_sha256"]) == 64
    with (run_dir / "extension_bins.csv").open(encoding="utf-8", newline="") as handle:
        extension_fields = csv.DictReader(handle).fieldnames or []
    assert "candidate_distinct_date_count" in extension_fields
    assert "adjusted_outcome_coverage" in extension_fields
    with (run_dir / "gate_state_extension_cells.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        state_fields = csv.DictReader(handle).fieldnames or []
    assert "candidate_distinct_date_count" in state_fields
    assert "adjusted_outcome_coverage" in state_fields

    with pytest.raises(FileExistsError):
        run_extension_study_from_inputs(
            rows=rows,
            trading_dates=trading_dates,
            macro_points=macro_points,
            contract=contract,
            source_metadata={"fixture": True},
            output_root=output_root,
            run_id="fixture-001",
        )

    second = run_extension_study_from_inputs(
        rows=rows,
        trading_dates=trading_dates,
        macro_points=macro_points,
        contract=contract,
        source_metadata={"fixture": True},
        output_root=output_root,
        run_id="fixture-002",
    )
    assert second["result_sha256"] == first["result_sha256"]


def test_result_fingerprint_ignores_machine_local_source_paths(tmp_path: Path) -> None:
    contract = load_study_contract(_write_contract(tmp_path / "contract.json"))
    rows = [_study_row("000001.SZ", extension=0.04, adjusted=0.02)]
    trading_dates = [f"2026-06-{day:02d}" for day in range(2, 22)]
    macro_points = {"2026-06-01": {"state": "HOT", "source": "replayed"}}

    first = run_extension_study_from_inputs(
        rows=rows,
        trading_dates=trading_dates,
        macro_points=macro_points,
        contract=contract,
        source_metadata={
            "db_path": "C:/machine-a/moss.duckdb",
            "contract_path": "C:/machine-a/contract.json",
            "db_sha256": "same-content",
        },
        output_root=tmp_path / "runs",
        run_id="path-a",
    )
    second = run_extension_study_from_inputs(
        rows=rows,
        trading_dates=trading_dates,
        macro_points=macro_points,
        contract=contract,
        source_metadata={
            "db_path": "/machine-b/moss.duckdb",
            "contract_path": "/machine-b/contract.json",
            "db_sha256": "same-content",
        },
        output_root=tmp_path / "runs",
        run_id="path-b",
    )

    assert first["result_sha256"] == second["result_sha256"]


@pytest.mark.parametrize(
    "run_id",
    [
        "../escape",
        "..\\escape",
        "C:/escape",
        "has space",
        "NUL",
        "trailing.",
        "trim-me ",
    ],
)
def test_runner_rejects_non_portable_or_escaping_run_ids(
    tmp_path: Path,
    run_id: str,
) -> None:
    contract = load_study_contract(_write_contract(tmp_path / "contract.json"))

    with pytest.raises(ValueError, match="run_id"):
        run_extension_study_from_inputs(
            rows=[_study_row("000001.SZ", extension=0.04, adjusted=0.02)],
            trading_dates=[f"2026-06-{day:02d}" for day in range(2, 22)],
            macro_points={"2026-06-01": {"state": "HOT", "source": "replayed"}},
            contract=contract,
            source_metadata={"fixture": True},
            output_root=tmp_path / "runs",
            run_id=run_id,
        )
