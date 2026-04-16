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


def test_formal_balance_pipeline_fails_closed_when_ingest_batch_id_is_missing(monkeypatch):
    pipeline_mod = _load_pipeline_module()

    calls: list[str] = []

    def _fake_ingest(**_kwargs):
        calls.append("ingest")
        return {"status": "completed"}

    def _fake_snapshot(**_kwargs):
        calls.append("snapshot")
        raise AssertionError("snapshot should not run without ingest_batch_id")

    def _fake_balance(**_kwargs):
        calls.append("balance")
        raise AssertionError("balance should not run without ingest_batch_id")

    monkeypatch.setattr(pipeline_mod.ingest_demo_manifest, "fn", _fake_ingest)
    monkeypatch.setattr(pipeline_mod.materialize_standard_snapshots, "fn", _fake_snapshot)
    monkeypatch.setattr(pipeline_mod.materialize_balance_analysis_facts, "fn", _fake_balance)

    try:
        pipeline_mod.run_formal_balance_pipeline.fn(report_date="2025-12-31")
    except ValueError as exc:
        assert "ingest_batch_id" in str(exc)
    else:
        raise AssertionError("pipeline should fail closed when ingest_batch_id is missing")

    assert calls == ["ingest"]


def test_formal_balance_pipeline_does_not_materialize_from_stale_snapshots_when_ingest_batch_id_is_missing(
    tmp_path,
    monkeypatch,
):
    pipeline_mod = _load_pipeline_module()
    snapshot_mod = load_module(
        "backend.app.repositories.snapshot_repo",
        "backend/app/repositories/snapshot_repo.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        snapshot_mod.ensure_snapshot_tables(conn)
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, issuer_name, industry_name, rating,
              currency_code, face_value_native, market_value_native, amortized_cost_native,
              accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
              overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'stale-z', '债券A', '组合A', 'CC100',
              '可供出售债券', '债券类', '国债', '发行人A', '主权', 'AAA',
              'USD', 100, 100, 90, 5, 0.025, 0.03, '2027-12-31', null,
              0, false, '固定', 'sv-stale-z', 'rv-snap-1', 'ib-stale', 'trace-stale-z'
            )
            """
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, currency_code,
              principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'stale-t', '持有至到期同业存单', 'liability', '银行A',
              '负债账户', '一般', '股份制银行', 'USD',
              10, 2, 0.015, '2026-06-30',
              'sv-stale-t', 'rv-snap-1', 'ib-stale', 'trace-stale-t'
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid (
              trade_date, base_currency, quote_currency, mid_rate,
              source_name, is_business_day, is_carry_forward, source_version
            ) values (
              '2025-12-31', 'USD', 'CNY', 7.20, 'CFETS', true, false, 'sv-stale-fx'
            )
            """
        )
    finally:
        conn.close()

    def _fake_ingest(**_kwargs):
        return {"status": "completed"}

    monkeypatch.setattr(pipeline_mod.ingest_demo_manifest, "fn", _fake_ingest)

    try:
        pipeline_mod.run_formal_balance_pipeline.fn(
            report_date="2025-12-31",
            duckdb_path=str(duckdb_path),
            governance_dir=str(tmp_path / "governance"),
        )
    except ValueError as exc:
        assert "ingest_batch_id" in str(exc)
    else:
        raise AssertionError("pipeline should fail closed when ingest_batch_id is missing")

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        table_names = {
            row[0]
            for row in conn.execute(
                """
                select table_name
                from information_schema.tables
                where table_name in ('fact_formal_zqtz_balance_daily', 'fact_formal_tyw_balance_daily')
                """
            ).fetchall()
        }
        zqtz_count = conn.execute("select count(*) from fact_formal_zqtz_balance_daily").fetchone()[0]
        tyw_count = conn.execute("select count(*) from fact_formal_tyw_balance_daily").fetchone()[0]
    finally:
        conn.close()

    assert table_names == {"fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"}
    assert zqtz_count == 0
    assert tyw_count == 0


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
