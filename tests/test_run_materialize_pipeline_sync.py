from __future__ import annotations

import sys

import pytest
from types import SimpleNamespace

import scripts.run_materialize_pipeline_sync as pipeline


def test_pipeline_runs_balance_movement_after_product_category(monkeypatch):
    calls: list[tuple[str, str | None]] = []
    settings = SimpleNamespace()

    monkeypatch.setattr(pipeline, "get_settings", lambda: settings)
    monkeypatch.setattr(pipeline, "_source_preview", lambda _: calls.append(("source", None)))
    monkeypatch.setattr(
        pipeline,
        "_balance",
        lambda _, report_date: calls.append(("balance", report_date)),
    )
    monkeypatch.setattr(
        pipeline,
        "_bond",
        lambda _, report_date: calls.append(("bond", report_date)),
    )
    monkeypatch.setattr(pipeline, "_pnl", lambda _, report_date: calls.append(("pnl", report_date)))
    monkeypatch.setattr(pipeline, "_product_category", lambda _: calls.append(("product_category", None)))
    monkeypatch.setattr(
        pipeline,
        "_balance_movement",
        lambda _, report_date: calls.append(("balance_movement", report_date)),
        raising=False,
    )
    monkeypatch.setattr(sys, "argv", ["run_materialize_pipeline_sync.py", "--report-date", "2026-06-30"])

    pipeline.main()

    assert calls[-2:] == [("product_category", None), ("balance_movement", "2026-06-30")]


def test_balance_movement_step_materializes_requested_report_date(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    def fake_refresh(**kwargs):
        captured.update(kwargs)
        return {
            "status": "completed",
            "payloads_by_date": {"2026-06-30": {"row_count": 3}},
        }

    monkeypatch.setattr(
        pipeline,
        "refresh_accounting_asset_movement_window_sync",
        fake_refresh,
        raising=False,
    )
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "governance",
    )

    pipeline._balance_movement(settings, "2026-06-30")

    assert captured == {
        "report_dates": ["2026-06-30"],
        "anchor_report_date": "2026-06-30",
        "duckdb_path": str(settings.duckdb_path),
        "governance_dir": str(settings.governance_path),
        "currency_basis": "CNX",
    }


def test_balance_movement_step_rejects_empty_materialization(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pipeline,
        "refresh_accounting_asset_movement_window_sync",
        lambda **_kwargs: {
            "status": "completed",
            "payloads_by_date": {"2026-06-30": {"row_count": 0}},
        },
    )
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "governance",
    )

    with pytest.raises(
        RuntimeError,
        match="balance movement materialization did not produce usable rows",
    ):
        pipeline._balance_movement(settings, "2026-06-30")
