from __future__ import annotations

import json
import sys

import pytest

from tests.helpers import load_module


def _load_runner_module():
    return load_module(
        "backend.app.tasks.livermore_position_snapshot_run",
        "backend/app/tasks/livermore_position_snapshot_run.py",
    )


def test_livermore_position_snapshot_run_main_forwards_args_and_emits_json(monkeypatch, capsys) -> None:
    module = _load_runner_module()
    calls: list[dict[str, object]] = []

    def fake_materialize_livermore_position_snapshot(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "completed",
            "as_of_date": "2026-04-29",
            "row_count": 2,
        }

    monkeypatch.setattr(
        module,
        "materialize_livermore_position_snapshot",
        fake_materialize_livermore_position_snapshot,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "livermore_position_snapshot_run.py",
            "--as-of-date",
            "2026-04-29",
            "--csv-path",
            "tmp/positions.csv",
            "--duckdb-path",
            "tmp/moss.duckdb",
        ],
    )

    module.main()

    captured = capsys.readouterr()
    assert calls == [
        {
            "as_of_date": "2026-04-29",
            "csv_path": "tmp/positions.csv",
            "duckdb_path": "tmp/moss.duckdb",
        }
    ]
    assert json.loads(captured.out) == {
        "status": "completed",
        "as_of_date": "2026-04-29",
        "row_count": 2,
    }
    assert captured.err == ""


def test_livermore_position_snapshot_run_main_can_check_existing_risk_inputs(
    monkeypatch,
    capsys,
) -> None:
    module = _load_runner_module()
    materialize_calls: list[dict[str, object]] = []
    check_calls: list[dict[str, object]] = []

    def fake_materialize_livermore_position_snapshot(**kwargs: object) -> dict[str, object]:
        materialize_calls.append(dict(kwargs))
        raise AssertionError("check-only mode should not materialize positions")

    def fake_risk_exit_input_block_reason(**kwargs: object) -> str:
        check_calls.append(dict(kwargs))
        return "livermore_position_snapshot table is not materialized for Livermore A-share holdings."

    monkeypatch.setattr(
        module,
        "materialize_livermore_position_snapshot",
        fake_materialize_livermore_position_snapshot,
    )
    monkeypatch.setattr(
        module,
        "_risk_exit_input_block_reason",
        fake_risk_exit_input_block_reason,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "livermore_position_snapshot_run.py",
            "--as-of-date",
            "2026-04-29",
            "--duckdb-path",
            "tmp/moss.duckdb",
            "--check-risk-inputs",
        ],
    )

    module.main()

    captured = capsys.readouterr()
    assert materialize_calls == []
    assert check_calls == [{"duckdb_path": "tmp/moss.duckdb", "as_of_date": "2026-04-29"}]
    assert json.loads(captured.out) == {
        "status": "blocked",
        "fact_source": "livermore_position_snapshot",
        "as_of_date": "2026-04-29",
        "risk_exit_input_status": "blocked",
        "risk_exit_input_block_reason": (
            "livermore_position_snapshot table is not materialized for Livermore A-share holdings."
        ),
    }
    assert captured.err == ""


def test_livermore_position_snapshot_run_main_can_verify_risk_inputs_after_materialize(
    monkeypatch,
    capsys,
) -> None:
    module = _load_runner_module()
    check_calls: list[dict[str, object]] = []

    def fake_materialize_livermore_position_snapshot(**_kwargs: object) -> dict[str, object]:
        return {
            "status": "completed",
            "fact_source": "livermore_position_snapshot",
            "as_of_date": "2026-04-29",
            "row_count": 2,
        }

    def fake_risk_exit_input_block_reason(**kwargs: object) -> str:
        check_calls.append(dict(kwargs))
        return ""

    monkeypatch.setattr(
        module,
        "materialize_livermore_position_snapshot",
        fake_materialize_livermore_position_snapshot,
    )
    monkeypatch.setattr(
        module,
        "_risk_exit_input_block_reason",
        fake_risk_exit_input_block_reason,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "livermore_position_snapshot_run.py",
            "--as-of-date",
            "2026-04-29",
            "--csv-path",
            "tmp/positions.csv",
            "--duckdb-path",
            "tmp/moss.duckdb",
            "--check-risk-inputs",
        ],
    )

    module.main()

    captured = capsys.readouterr()
    assert check_calls == [{"duckdb_path": "tmp/moss.duckdb", "as_of_date": "2026-04-29"}]
    assert json.loads(captured.out) == {
        "status": "completed",
        "fact_source": "livermore_position_snapshot",
        "as_of_date": "2026-04-29",
        "row_count": 2,
        "risk_exit_input_status": "ready",
        "risk_exit_input_block_reason": "",
    }
    assert captured.err == ""


def test_livermore_position_snapshot_run_main_propagates_failures_without_json(monkeypatch, capsys) -> None:
    module = _load_runner_module()

    def fake_materialize_livermore_position_snapshot(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("position snapshot materialization failed")

    monkeypatch.setattr(
        module,
        "materialize_livermore_position_snapshot",
        fake_materialize_livermore_position_snapshot,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "livermore_position_snapshot_run.py",
            "--as-of-date",
            "2026-04-29",
            "--csv-path",
            "tmp/positions.csv",
        ],
    )

    with pytest.raises(RuntimeError, match="position snapshot materialization failed"):
        module.main()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
