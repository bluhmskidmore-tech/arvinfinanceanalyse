from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from tests.helpers import load_module


def _load_runner_module():
    return load_module(
        "backend.app.tasks.choice_stock_materialize_run",
        "backend/app/tasks/choice_stock_materialize_run.py",
    )


def test_choice_stock_materialize_run_main_forwards_args_and_emits_json(monkeypatch, capsys) -> None:
    module = _load_runner_module()
    calls: list[dict[str, object]] = []

    def fake_materialize_choice_stock_inputs(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "completed",
            "as_of_date": "2026-04-28",
            "row_count": 7,
        }

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fake_materialize_choice_stock_inputs)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--duckdb-path",
            "tmp/moss.duckdb",
            "--catalog-path",
            "tmp/choice_stock_catalog.json",
        ],
    )

    module.main()

    captured = capsys.readouterr()
    assert calls == [
        {
            "as_of_date": "2026-04-28",
            "duckdb_path": "tmp/moss.duckdb",
            "catalog_path": "tmp/choice_stock_catalog.json",
            "enable_tushare_concept_fallback": False,
        }
    ]
    assert json.loads(captured.out) == {
        "status": "completed",
        "as_of_date": "2026-04-28",
        "row_count": 7,
    }
    assert captured.err == ""


def test_choice_stock_materialize_run_main_forwards_none_for_omitted_paths(monkeypatch, capsys) -> None:
    module = _load_runner_module()
    calls: list[dict[str, object]] = []

    def fake_materialize_choice_stock_inputs(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {"status": "completed"}

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fake_materialize_choice_stock_inputs)
    monkeypatch.setattr(
        sys,
        "argv",
        ["choice_stock_materialize_run.py", "--as-of-date", "2026-04-28"],
    )

    module.main()

    captured = capsys.readouterr()
    assert calls == [
        {
            "as_of_date": "2026-04-28",
            "duckdb_path": None,
            "catalog_path": None,
            "enable_tushare_concept_fallback": False,
        }
    ]
    assert json.loads(captured.out) == {"status": "completed"}
    assert captured.err == ""


def test_choice_stock_materialize_run_main_can_emit_post_run_coverage(monkeypatch, capsys) -> None:
    module = _load_runner_module()
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_materialize_choice_stock_inputs(**kwargs: object) -> dict[str, object]:
        calls.append(("materialize", dict(kwargs)))
        return {
            "status": "completed",
            "as_of_date": "2026-04-28",
            "row_count": 42,
        }

    def fake_load_choice_stock_materialization_coverage(**kwargs: object) -> object:
        calls.append(("coverage", dict(kwargs)))
        return SimpleNamespace(
            as_of_date="2026-04-28",
            full_coverage=True,
            status="ready",
            completed_request_items=["stock_universe:a_share_universe_sector_001004"],
            missing_request_items=[],
            message="Choice stock inputs are materialized for 2026-04-28.",
        )

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fake_materialize_choice_stock_inputs)
    monkeypatch.setattr(
        module,
        "load_choice_stock_materialization_coverage",
        fake_load_choice_stock_materialization_coverage,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--duckdb-path",
            "tmp/moss.duckdb",
            "--catalog-path",
            "tmp/choice_stock_catalog.json",
            "--verify-coverage",
        ],
    )

    module.main()

    captured = capsys.readouterr()
    assert calls == [
        (
            "materialize",
            {
                "as_of_date": "2026-04-28",
                "duckdb_path": "tmp/moss.duckdb",
                "catalog_path": "tmp/choice_stock_catalog.json",
                "enable_tushare_concept_fallback": False,
            },
        ),
        (
            "coverage",
            {
                "duckdb_path": "tmp/moss.duckdb",
                "as_of_date": "2026-04-28",
            },
        ),
    ]
    assert json.loads(captured.out) == {
        "status": "completed",
        "as_of_date": "2026-04-28",
        "row_count": 42,
        "coverage": {
            "as_of_date": "2026-04-28",
            "full_coverage": True,
            "status": "ready",
            "completed_request_items": ["stock_universe:a_share_universe_sector_001004"],
            "missing_request_items": [],
            "message": "Choice stock inputs are materialized for 2026-04-28.",
        },
    }
    assert captured.err == ""


def test_choice_stock_materialize_run_main_can_run_factor_snapshot(monkeypatch, capsys) -> None:
    module = _load_runner_module()
    calls: list[dict[str, object]] = []

    def fake_materialize_choice_stock_factor_snapshot(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "completed",
            "as_of_date": "2026-04-28",
            "table": "choice_stock_factor_snapshot",
            "row_count": 123,
        }

    monkeypatch.setattr(
        module,
        "materialize_choice_stock_factor_snapshot",
        fake_materialize_choice_stock_factor_snapshot,
        raising=False,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "choice_stock_materialize_run.py",
            "--as-of-date",
            "2026-04-28",
            "--duckdb-path",
            "tmp/moss.duckdb",
            "--factor-snapshot",
            "--factor-max-stock-count",
            "750",
        ],
    )

    module.main()

    captured = capsys.readouterr()
    assert calls == [
        {
            "as_of_date": "2026-04-28",
            "duckdb_path": "tmp/moss.duckdb",
            "max_stock_count": 750,
        }
    ]
    assert json.loads(captured.out) == {
        "status": "completed",
        "as_of_date": "2026-04-28",
        "table": "choice_stock_factor_snapshot",
        "row_count": 123,
    }
    assert captured.err == ""


def test_choice_stock_materialize_run_main_propagates_failures_without_json(monkeypatch, capsys) -> None:
    module = _load_runner_module()

    def fake_materialize_choice_stock_inputs(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("choice materialization failed")

    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fake_materialize_choice_stock_inputs)
    monkeypatch.setattr(
        sys,
        "argv",
        ["choice_stock_materialize_run.py", "--as-of-date", "2026-04-28"],
    )

    with pytest.raises(RuntimeError, match="choice materialization failed"):
        module.main()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
