from __future__ import annotations

import sys

from tests.helpers import load_module


def _load_pipeline_module():
    module = sys.modules.get("backend.app.tasks.formal_balance_pipeline")
    if module is None:
        module = load_module(
            "backend.app.tasks.formal_balance_pipeline",
            "backend/app/tasks/formal_balance_pipeline.py",
        )
    return module


def test_formal_balance_pipeline_runs_ingest_snapshot_and_balance_in_order(tmp_path, monkeypatch):
    pipeline_mod = _load_pipeline_module()

    calls: list[tuple[str, dict[str, object]]] = []

    def _fake_ingest(**kwargs):
        calls.append(("ingest", kwargs))
        return {"status": "completed", "source_families": ["zqtz", "tyw"]}

    def _fake_snapshot(**kwargs):
        calls.append(("snapshot", kwargs))
        return {"status": "completed", "zqtz_rows": 1, "tyw_rows": 1}

    def _fake_balance(**kwargs):
        calls.append(("balance", kwargs))
        return {"status": "completed", "zqtz_rows": 2, "tyw_rows": 2}

    monkeypatch.setattr(pipeline_mod.ingest_demo_manifest, "fn", _fake_ingest)
    monkeypatch.setattr(pipeline_mod.materialize_standard_snapshots, "fn", _fake_snapshot)
    monkeypatch.setattr(pipeline_mod.materialize_balance_analysis_facts, "fn", _fake_balance)

    payload = pipeline_mod.run_formal_balance_pipeline.fn(
        report_date="2025-12-31",
        data_root=str(tmp_path / "data_input"),
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
        archive_dir=str(tmp_path / "archive"),
    )

    assert [name for name, _kwargs in calls] == ["ingest", "snapshot", "balance"]
    assert calls[0][1]["data_root"] == str(tmp_path / "data_input")
    assert calls[0][1]["governance_dir"] == str(tmp_path / "governance")
    assert calls[0][1]["archive_dir"] == str(tmp_path / "archive")
    assert calls[1][1]["report_date"] == "2025-12-31"
    assert calls[1][1]["source_families"] == ["zqtz", "tyw"]
    assert calls[2][1]["report_date"] == "2025-12-31"
    assert payload["status"] == "completed"
    assert payload["steps"]["ingest"]["status"] == "completed"
    assert payload["steps"]["snapshot"]["status"] == "completed"
    assert payload["steps"]["balance"]["status"] == "completed"
