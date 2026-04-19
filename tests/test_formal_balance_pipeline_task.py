from __future__ import annotations

import json
import os
import sys

import duckdb

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

    calls: list[tuple[str, dict[str, object], str | None, str | None]] = []

    def _fake_ingest(**kwargs):
        calls.append(
            (
                "ingest",
                kwargs,
                os.environ.get("MOSS_DATA_INPUT_ROOT"),
                os.environ.get("MOSS_FX_OFFICIAL_SOURCE_PATH"),
            )
        )
        return {
            "status": "completed",
            "ingest_batch_id": "ib-current",
            "source_families": ["zqtz", "tyw"],
        }

    def _fake_snapshot(**kwargs):
        calls.append(
            (
                "snapshot",
                kwargs,
                os.environ.get("MOSS_DATA_INPUT_ROOT"),
                os.environ.get("MOSS_FX_OFFICIAL_SOURCE_PATH"),
            )
        )
        return {"status": "completed", "zqtz_rows": 1, "tyw_rows": 1}

    def _fake_balance(**kwargs):
        calls.append(
            (
                "balance",
                kwargs,
                os.environ.get("MOSS_DATA_INPUT_ROOT"),
                os.environ.get("MOSS_FX_OFFICIAL_SOURCE_PATH"),
            )
        )
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
        fx_source_path=str(tmp_path / "data_input" / "fx" / "fx_daily_mid.csv"),
    )

    assert [name for name, _kwargs, _data_root, _fx_path in calls] == ["ingest", "snapshot", "balance"]
    assert calls[0][1]["data_root"] == str(tmp_path / "data_input")
    assert calls[0][1]["governance_dir"] == str(tmp_path / "governance")
    assert calls[0][1]["archive_dir"] == str(tmp_path / "archive")
    assert calls[0][1]["source_family_allowlist"] == ["zqtz", "tyw"]
    assert calls[0][2] is None
    assert calls[0][3] is None
    assert calls[1][1]["report_date"] == "2025-12-31"
    assert calls[1][1]["source_families"] == ["zqtz", "tyw"]
    assert calls[1][1]["ingest_batch_id"] == "ib-current"
    assert calls[1][2] is None
    assert calls[1][3] is None
    assert calls[2][1]["report_date"] == "2025-12-31"
    assert calls[2][1]["data_root"] == str(tmp_path / "data_input")
    assert calls[2][1]["fx_source_path"] == str(tmp_path / "data_input" / "fx" / "fx_daily_mid.csv")
    assert calls[2][1]["ingest_batch_id"] == "ib-current"
    assert calls[2][2] is None
    assert calls[2][3] is None
    assert payload["status"] == "completed"
    assert payload["steps"]["ingest"]["status"] == "completed"
    assert payload["steps"]["snapshot"]["status"] == "completed"
    assert payload["steps"]["balance"]["status"] == "completed"
    assert payload["steps"]["balance_runtime"]["run"]["status"] == "completed"
    assert payload["steps"]["balance_runtime"]["result"] == {"zqtz_rows": 2, "tyw_rows": 2}


def test_formal_balance_pipeline_runs_when_incremental_ingest_has_no_batch_but_report_date_is_explicit(
    monkeypatch,
):
    """Empty incremental ingest is normal after a full archive; lineage falls back to manifest + DuckDB."""
    pipeline_mod = _load_pipeline_module()

    calls: list[str] = []

    def _fake_ingest(**_kwargs):
        calls.append("ingest")
        return {"status": "completed"}

    def _fake_snapshot(**kwargs):
        calls.append("snapshot")
        assert kwargs.get("ingest_batch_id") is None
        assert kwargs.get("report_date") == "2025-12-31"
        return {"status": "completed", "zqtz_rows": 0, "tyw_rows": 0}

    def _fake_balance(**kwargs):
        calls.append("balance")
        assert kwargs.get("ingest_batch_id") is None
        assert kwargs.get("report_date") == "2025-12-31"
        return {"status": "completed", "zqtz_rows": 0, "tyw_rows": 0}

    monkeypatch.setattr(pipeline_mod.ingest_demo_manifest, "fn", _fake_ingest)
    monkeypatch.setattr(pipeline_mod.materialize_standard_snapshots, "fn", _fake_snapshot)
    monkeypatch.setattr(pipeline_mod.materialize_balance_analysis_facts, "fn", _fake_balance)

    payload = pipeline_mod.run_formal_balance_pipeline.fn(report_date="2025-12-31")
    assert calls == ["ingest", "snapshot", "balance"]
    assert payload["status"] == "completed"


def test_formal_balance_pipeline_passes_none_ingest_batch_through_snapshot_and_balance(
    tmp_path,
    monkeypatch,
):
    """With an explicit report_date, missing incremental batch id must not abort the orchestration."""
    pipeline_mod = _load_pipeline_module()

    duckdb_path = tmp_path / "moss.duckdb"
    calls: list[tuple[str, object]] = []

    def _fake_ingest(**_kwargs):
        return {"status": "completed"}

    def _fake_snapshot(**kwargs):
        calls.append(("snapshot", kwargs.get("ingest_batch_id")))
        return {"status": "completed", "zqtz_rows": 0, "tyw_rows": 0}

    def _fake_balance(**kwargs):
        calls.append(("balance", kwargs.get("ingest_batch_id")))
        return {"status": "completed", "zqtz_rows": 0, "tyw_rows": 0}

    monkeypatch.setattr(pipeline_mod.ingest_demo_manifest, "fn", _fake_ingest)
    monkeypatch.setattr(pipeline_mod.materialize_standard_snapshots, "fn", _fake_snapshot)
    monkeypatch.setattr(pipeline_mod.materialize_balance_analysis_facts, "fn", _fake_balance)

    payload = pipeline_mod.run_formal_balance_pipeline.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
    )
    assert payload["status"] == "completed"
    assert calls == [("snapshot", None), ("balance", None)]


def test_formal_balance_pipeline_backfills_manifest_report_date_range_in_order(tmp_path, monkeypatch):
    pipeline_mod = _load_pipeline_module()

    ingest_batch_id = "ib-backfill"
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = governance_dir / "source_manifest.jsonl"
    manifest_rows = [
        {
            "source_name": "ZQTZSHOW",
            "source_family": "zqtz",
            "source_file": "ZQTZSHOW-20251230.xls",
            "file_name": "ZQTZSHOW-20251230.xls",
            "file_path": str(tmp_path / "data_input" / "ZQTZSHOW-20251230.xls"),
            "file_size": 1,
            "report_date": "2025-12-30",
            "report_start_date": "2025-12-30",
            "report_end_date": "2025-12-30",
            "report_granularity": "day",
            "source_version": "sv-z-20251230",
            "ingest_batch_id": ingest_batch_id,
            "archive_mode": "local",
            "archived_path": str(tmp_path / "archive" / "ZQTZSHOW-20251230.xls"),
            "schema_version": "phase1.manifest.v1",
            "created_at": "2026-04-12T00:00:00+00:00",
            "status": "completed",
        },
        {
            "source_name": "TYWLSHOW",
            "source_family": "tyw",
            "source_file": "TYWLSHOW-20251230.xls",
            "file_name": "TYWLSHOW-20251230.xls",
            "file_path": str(tmp_path / "data_input" / "TYWLSHOW-20251230.xls"),
            "file_size": 1,
            "report_date": "2025-12-30",
            "report_start_date": "2025-12-30",
            "report_end_date": "2025-12-30",
            "report_granularity": "day",
            "source_version": "sv-t-20251230",
            "ingest_batch_id": ingest_batch_id,
            "archive_mode": "local",
            "archived_path": str(tmp_path / "archive" / "TYWLSHOW-20251230.xls"),
            "schema_version": "phase1.manifest.v1",
            "created_at": "2026-04-12T00:00:00+00:00",
            "status": "completed",
        },
        {
            "source_name": "ZQTZSHOW",
            "source_family": "zqtz",
            "source_file": "ZQTZSHOW-20251231.xls",
            "file_name": "ZQTZSHOW-20251231.xls",
            "file_path": str(tmp_path / "data_input" / "ZQTZSHOW-20251231.xls"),
            "file_size": 1,
            "report_date": "2025-12-31",
            "report_start_date": "2025-12-31",
            "report_end_date": "2025-12-31",
            "report_granularity": "day",
            "source_version": "sv-z-20251231",
            "ingest_batch_id": ingest_batch_id,
            "archive_mode": "local",
            "archived_path": str(tmp_path / "archive" / "ZQTZSHOW-20251231.xls"),
            "schema_version": "phase1.manifest.v1",
            "created_at": "2026-04-12T00:00:00+00:00",
            "status": "completed",
        },
        {
            "source_name": "TYWLSHOW",
            "source_family": "tyw",
            "source_file": "TYWLSHOW-20251231.xls",
            "file_name": "TYWLSHOW-20251231.xls",
            "file_path": str(tmp_path / "data_input" / "TYWLSHOW-20251231.xls"),
            "file_size": 1,
            "report_date": "2025-12-31",
            "report_start_date": "2025-12-31",
            "report_end_date": "2025-12-31",
            "report_granularity": "day",
            "source_version": "sv-t-20251231",
            "ingest_batch_id": ingest_batch_id,
            "archive_mode": "local",
            "archived_path": str(tmp_path / "archive" / "TYWLSHOW-20251231.xls"),
            "schema_version": "phase1.manifest.v1",
            "created_at": "2026-04-12T00:00:00+00:00",
            "status": "completed",
        },
        {
            "source_name": "ZQTZSHOW",
            "source_family": "zqtz",
            "source_file": "ZQTZSHOW-20260101.xls",
            "file_name": "ZQTZSHOW-20260101.xls",
            "file_path": str(tmp_path / "data_input" / "ZQTZSHOW-20260101.xls"),
            "file_size": 1,
            "report_date": "2026-01-01",
            "report_start_date": "2026-01-01",
            "report_end_date": "2026-01-01",
            "report_granularity": "day",
            "source_version": "sv-z-20260101",
            "ingest_batch_id": ingest_batch_id,
            "archive_mode": "local",
            "archived_path": str(tmp_path / "archive" / "ZQTZSHOW-20260101.xls"),
            "schema_version": "phase1.manifest.v1",
            "created_at": "2026-04-12T00:00:00+00:00",
            "status": "completed",
        },
        {
            "source_name": "TYWLSHOW",
            "source_family": "tyw",
            "source_file": "TYWLSHOW-20260101.xls",
            "file_name": "TYWLSHOW-20260101.xls",
            "file_path": str(tmp_path / "data_input" / "TYWLSHOW-20260101.xls"),
            "file_size": 1,
            "report_date": "2026-01-01",
            "report_start_date": "2026-01-01",
            "report_end_date": "2026-01-01",
            "report_granularity": "day",
            "source_version": "sv-t-20260101",
            "ingest_batch_id": ingest_batch_id,
            "archive_mode": "local",
            "archived_path": str(tmp_path / "archive" / "TYWLSHOW-20260101.xls"),
            "schema_version": "phase1.manifest.v1",
            "created_at": "2026-04-12T00:00:00+00:00",
            "status": "completed",
        },
        {
            "source_name": "PNL",
            "source_family": "pnl",
            "source_file": "FI-20251231.xlsx",
            "file_name": "FI-20251231.xlsx",
            "file_path": str(tmp_path / "data_input" / "FI-20251231.xlsx"),
            "file_size": 1,
            "report_date": "2025-12-31",
            "report_start_date": "2025-12-31",
            "report_end_date": "2025-12-31",
            "report_granularity": "day",
            "source_version": "sv-pnl-20251231",
            "ingest_batch_id": ingest_batch_id,
            "archive_mode": "local",
            "archived_path": str(tmp_path / "archive" / "FI-20251231.xlsx"),
            "schema_version": "phase1.manifest.v1",
            "created_at": "2026-04-12T00:00:00+00:00",
            "status": "completed",
        },
    ]
    manifest_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in manifest_rows) + "\n",
        encoding="utf-8",
    )

    calls: list[tuple[str, dict[str, object]]] = []

    def _fake_ingest(**kwargs):
        calls.append(("ingest", kwargs))
        return {
            "status": "completed",
            "ingest_batch_id": ingest_batch_id,
        }

    def _fake_snapshot(**kwargs):
        calls.append(("snapshot", kwargs))
        return {"status": "completed", "report_date": kwargs["report_date"]}

    def _fake_balance(**kwargs):
        calls.append(("balance", kwargs))
        return {"status": "completed", "report_date": kwargs["report_date"]}

    monkeypatch.setattr(pipeline_mod.ingest_demo_manifest, "fn", _fake_ingest)
    monkeypatch.setattr(pipeline_mod.materialize_standard_snapshots, "fn", _fake_snapshot)
    monkeypatch.setattr(pipeline_mod.materialize_balance_analysis_facts, "fn", _fake_balance)

    payload = pipeline_mod.run_formal_balance_pipeline.fn(
        start_date="2025-12-31",
        end_date="2026-01-01",
        governance_dir=str(governance_dir),
    )

    assert [name for name, _kwargs in calls] == [
        "ingest",
        "snapshot",
        "balance",
        "snapshot",
        "balance",
    ]
    assert [kwargs["report_date"] for name, kwargs in calls if name in {"snapshot", "balance"}] == [
        "2025-12-31",
        "2025-12-31",
        "2026-01-01",
        "2026-01-01",
    ]
    assert all(
        kwargs.get("ingest_batch_id") == ingest_batch_id
        for name, kwargs in calls
        if name in {"snapshot", "balance"}
    )
    assert payload["status"] == "completed"
    assert payload["report_dates"] == ["2025-12-31", "2026-01-01"]
    assert all(
        "balance_runtime" in item and isinstance(item["balance_runtime"], dict)
        for item in payload["steps"]["per_report_date"]
    )


def test_formal_balance_pipeline_prefers_new_runtime_payload_shape(tmp_path, monkeypatch):
    pipeline_mod = _load_pipeline_module()

    def _fake_ingest(**_kwargs):
        return {"status": "completed", "ingest_batch_id": "ib-new-shape"}

    def _fake_snapshot(**_kwargs):
        return {"status": "completed"}

    def _fake_balance(**_kwargs):
        return {
            "status": "completed",
            "run_id": "legacy-run-id",
            "payload": {
                "run": {
                    "run_id": "new-run-id",
                    "job_name": "balance_analysis_materialize",
                    "report_date": "2025-12-31",
                    "status": "completed",
                    "lock": "lock:duckdb:formal:balance-analysis:materialize",
                    "queued_at": "2026-01-01T00:00:00+00:00",
                    "started_at": "2026-01-01T00:00:01+00:00",
                    "finished_at": "2026-01-01T00:00:02+00:00",
                },
                "lineage": {
                    "cache_key": "formal:balance_analysis:materialize",
                    "cache_version": "cv_formal_balance_analysis__rv_balance_analysis_formal_materialize_v1",
                    "source_version": "sv-balance-new",
                    "vendor_version": "vv_none",
                    "rule_version": "rv_balance_analysis_formal_materialize_v1",
                    "basis": "formal",
                    "module_name": "balance_analysis",
                    "result_kind_family": "balance-analysis",
                    "run_id": "new-run-id",
                    "report_date": "2025-12-31",
                    "input_sources": ["zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot", "fx_daily_mid"],
                    "fact_tables": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
                },
                "result": {
                    "zqtz_rows": 9,
                    "tyw_rows": 3,
                },
            },
        }

    monkeypatch.setattr(pipeline_mod.ingest_demo_manifest, "fn", _fake_ingest)
    monkeypatch.setattr(pipeline_mod.materialize_standard_snapshots, "fn", _fake_snapshot)
    monkeypatch.setattr(pipeline_mod.materialize_balance_analysis_facts, "fn", _fake_balance)

    payload = pipeline_mod.run_formal_balance_pipeline.fn(report_date="2025-12-31")
    balance_runtime = payload["steps"]["balance_runtime"]
    assert balance_runtime["run"]["run_id"] == "new-run-id"
    assert balance_runtime["lineage"]["source_version"] == "sv-balance-new"
    assert balance_runtime["result"] == {"zqtz_rows": 9, "tyw_rows": 3}


def test_formal_balance_pipeline_main_emits_single_json_to_stdout(monkeypatch, capsys):
    pipeline_mod = _load_pipeline_module()

    monkeypatch.setattr(
        pipeline_mod.run_formal_balance_pipeline,
        "fn",
        lambda **_kwargs: {"status": "completed", "report_date": "2025-12-31"},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["formal_balance_pipeline.py", "--report-date", "2025-12-31"],
    )

    pipeline_mod.main()

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "status": "completed",
        "report_date": "2025-12-31",
    }
    assert captured.err == ""
