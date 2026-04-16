from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tests.helpers import load_module


def test_fx_mid_backfill_records_governance_on_success(tmp_path, monkeypatch):
    module = load_module(
        "backend.app.tasks.fx_mid_backfill",
        "backend/app/tasks/fx_mid_backfill.py",
    )

    def fake_materialize(*, report_date, duckdb_path, data_input_root, official_csv_path="", explicit_csv_path=""):
        return {
            "status": "completed",
            "report_date": report_date,
            "row_count": 5,
            "source_version": f"sv_{report_date}",
            "vendor_version": f"vv_{report_date}",
            "source_kind": "choice",
        }

    monkeypatch.setattr(
        module,
        "materialize_fx_mid_for_report_date",
        SimpleNamespace(fn=fake_materialize),
    )

    payload = module.backfill_fx_mid_history.fn(
        start_date="2026-02-27",
        end_date="2026-02-28",
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    assert payload["status"] == "completed"
    assert payload["row_count"] == 10

    build_runs = [
        json.loads(line)
        for line in (tmp_path / "governance" / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifests = [
        json.loads(line)
        for line in (tmp_path / "governance" / "cache_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert build_runs[0]["status"] == "running"
    assert build_runs[-1]["status"] == "completed"
    assert build_runs[-1]["cache_key"] == module.CACHE_KEY
    assert build_runs[-1]["report_dates"] == ["2026-02-27", "2026-02-28"]
    assert manifests[-1]["cache_key"] == module.CACHE_KEY
    assert manifests[-1]["row_count"] == 10


def test_fx_mid_backfill_records_failed_governance_when_range_is_partial(tmp_path, monkeypatch):
    module = load_module(
        "backend.app.tasks.fx_mid_backfill",
        "backend/app/tasks/fx_mid_backfill.py",
    )

    def fake_materialize(*, report_date, duckdb_path, data_input_root, official_csv_path="", explicit_csv_path=""):
        if report_date == "2026-02-28":
            raise RuntimeError("missing required formal middle-rates")
        return {
            "status": "completed",
            "report_date": report_date,
            "row_count": 5,
            "source_version": f"sv_{report_date}",
            "vendor_version": f"vv_{report_date}",
            "source_kind": "choice",
        }

    monkeypatch.setattr(
        module,
        "materialize_fx_mid_for_report_date",
        SimpleNamespace(fn=fake_materialize),
    )

    with pytest.raises(RuntimeError, match="missing required formal middle-rates"):
        module.backfill_fx_mid_history.fn(
            start_date="2026-02-27",
            end_date="2026-02-28",
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(tmp_path / "governance"),
        )

    build_runs = [
        json.loads(line)
        for line in (tmp_path / "governance" / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert build_runs[0]["status"] == "running"
    assert build_runs[-1]["status"] == "failed"
    assert build_runs[-1]["completed_dates"] == ["2026-02-27"]
    assert not (tmp_path / "governance" / "cache_manifest.jsonl").exists()
