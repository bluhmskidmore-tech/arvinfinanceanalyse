from __future__ import annotations

import json
import sys
from dataclasses import dataclass

import pytest

from tests.helpers import load_module


@dataclass(frozen=True)
class _Coverage:
    full_coverage: bool


def test_select_replay_input_backfill_dates_prioritizes_non_proxy_rows() -> None:
    module = load_module(
        "scripts.backfill_choice_stock_replay_inputs",
        "scripts/backfill_choice_stock_replay_inputs.py",
    )
    summary = {
        "date_reasons": [
            {"trade_date": "2026-01-02", "status": "unsupported", "reason_code": "missing_required_source_table"},
            {"trade_date": "2026-01-03", "status": "proxy_only", "reason_code": "proxy_theme_only"},
            {"trade_date": "2026-01-04", "status": "unsupported", "reason_code": "missing_daily_limit_flags"},
            {"trade_date": "2026-01-05", "status": "unsupported", "reason_code": "missing_required_source_table"},
        ],
    }
    row_stats = {
        "2026-01-02": {"row_count": 10, "proxy_theme_rows": 8, "non_proxy_rows": 2},
        "2026-01-05": {"row_count": 8, "proxy_theme_rows": 0, "non_proxy_rows": 8},
    }

    dates = module.select_replay_input_backfill_dates(
        summary=summary,
        row_stats=row_stats,
        max_dates=2,
    )

    assert dates == ["2026-01-05", "2026-01-02"]


def test_backfill_replay_inputs_skips_ready_dates_and_records_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    module = load_module(
        "scripts.backfill_choice_stock_replay_inputs",
        "scripts/backfill_choice_stock_replay_inputs.py",
    )
    monkeypatch.setattr(
        module,
        "livermore_candidate_history_backtest_window_summary",
        lambda **_kwargs: {
            "date_reasons": [
                {"trade_date": "2026-01-02", "status": "unsupported", "reason_code": "missing_required_source_table"},
                {"trade_date": "2026-01-05", "status": "unsupported", "reason_code": "missing_required_source_table"},
                {"trade_date": "2026-01-06", "status": "unsupported", "reason_code": "missing_required_source_table"},
            ]
        },
    )
    monkeypatch.setattr(
        module,
        "load_replay_row_stats",
        lambda **_kwargs: {
            "2026-01-02": {"row_count": 1, "proxy_theme_rows": 0, "non_proxy_rows": 1},
            "2026-01-05": {"row_count": 8, "proxy_theme_rows": 0, "non_proxy_rows": 8},
            "2026-01-06": {"row_count": 5, "proxy_theme_rows": 0, "non_proxy_rows": 5},
        },
    )

    coverage_calls: list[str] = []

    def fake_coverage(*, duckdb_path: str, as_of_date: str) -> _Coverage:
        del duckdb_path
        coverage_calls.append(as_of_date)
        return _Coverage(full_coverage=as_of_date == "2026-01-05")

    materialized: list[str] = []

    def fake_materialize(*, as_of_date: str, duckdb_path: str) -> dict[str, object]:
        del duckdb_path
        materialized.append(as_of_date)
        if as_of_date == "2026-01-06":
            raise RuntimeError("vendor timeout")
        return {"status": "completed", "as_of_date": as_of_date, "row_count": 123}

    monkeypatch.setattr(module, "load_choice_stock_materialization_coverage", fake_coverage)
    monkeypatch.setattr(module, "materialize_choice_stock_inputs", fake_materialize)

    duckdb_path = tmp_path / "fixture.duckdb"
    duckdb_path.write_bytes(b"placeholder")

    result = module.backfill_choice_stock_replay_inputs(
        duckdb_path=duckdb_path,
        max_dates=3,
    )

    assert result["status"] == "partial"
    assert result["selected_dates"] == ["2026-01-05", "2026-01-06", "2026-01-02"]
    assert coverage_calls == ["2026-01-05", "2026-01-06", "2026-01-02"]
    assert materialized == ["2026-01-06", "2026-01-02"]
    assert [item["as_of_date"] for item in result["completed"]] == ["2026-01-02"]
    assert [item["as_of_date"] for item in result["skipped"]] == ["2026-01-05"]
    assert result["failed"] == [{"as_of_date": "2026-01-06", "error": "vendor timeout"}]


def test_backfill_replay_inputs_dry_run_only_reports_selected_dates(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    module = load_module(
        "scripts.backfill_choice_stock_replay_inputs",
        "scripts/backfill_choice_stock_replay_inputs.py",
    )
    duckdb_path = tmp_path / "fixture.duckdb"
    duckdb_path.write_bytes(b"placeholder")
    monkeypatch.setattr(
        module,
        "livermore_candidate_history_backtest_window_summary",
        lambda **_kwargs: {
            "date_reasons": [
                {"trade_date": "2026-01-02", "status": "unsupported", "reason_code": "missing_required_source_table"},
            ]
        },
    )
    monkeypatch.setattr(
        module,
        "load_replay_row_stats",
        lambda **_kwargs: {"2026-01-02": {"row_count": 1, "proxy_theme_rows": 0, "non_proxy_rows": 1}},
    )
    monkeypatch.setattr(
        module,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: pytest.fail("dry run must not materialize"),
    )

    result = module.backfill_choice_stock_replay_inputs(
        duckdb_path=duckdb_path,
        max_dates=1,
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["selected_dates"] == ["2026-01-02"]
    assert result["completed"] == []
    assert result["skipped"] == []
    assert result["failed"] == []


def test_choice_stock_replay_input_backfill_main_emits_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = load_module(
        "scripts.backfill_choice_stock_replay_inputs",
        "scripts/backfill_choice_stock_replay_inputs.py",
    )
    monkeypatch.setattr(
        module,
        "backfill_choice_stock_replay_inputs",
        lambda **_kwargs: {"status": "completed", "completed": []},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "backfill_choice_stock_replay_inputs.py",
            "--duckdb-path",
            "fixture.duckdb",
            "--max-dates",
            "2",
        ],
    )

    assert module.main() == 0
    assert json.loads(capsys.readouterr().out) == {"status": "completed", "completed": []}
