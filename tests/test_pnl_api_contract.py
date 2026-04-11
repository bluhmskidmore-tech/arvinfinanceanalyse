from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path
from decimal import Decimal

from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.schemas.materialize import CacheBuildRunRecord
from tests.helpers import ROOT, load_module


def test_fastapi_application_registers_pnl_routes():
    from backend.app.main import app

    paths = {route.path for route in app.routes}

    assert "/api/pnl/dates" in paths
    assert "/api/pnl/data" in paths
    assert "/api/pnl/overview" in paths
    assert "/api/data/refresh_pnl" in paths
    assert "/api/data/import_status/pnl" in paths


def test_pnl_dates_returns_union_and_constituent_lists(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/dates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["result_kind"] == "pnl.dates"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v1"
    assert payload["result"] == {
        "report_dates": ["2026-02-28", "2026-01-31", "2025-12-31"],
        "formal_fi_report_dates": ["2026-01-31", "2025-12-31"],
        "nonstd_bridge_report_dates": ["2026-02-28", "2025-12-31"],
    }
    get_settings.cache_clear()


def test_pnl_data_returns_shared_date_with_two_explicit_lists_and_manifest_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(governance_dir, source_version="sv_override", vendor_version="vv_override", rule_version="rv_override")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/data", params={"date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["result_kind"] == "pnl.data"
    assert payload["result_meta"]["source_version"] == "sv_override"
    assert payload["result_meta"]["vendor_version"] == "vv_override"
    assert payload["result_meta"]["rule_version"] == "rv_override"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v1"
    assert payload["result"]["report_date"] == "2025-12-31"
    assert len(payload["result"]["formal_fi_rows"]) == 1
    assert len(payload["result"]["nonstd_bridge_rows"]) == 1
    assert payload["result"]["formal_fi_rows"][0]["instrument_code"] == "240001.IB"
    assert payload["result"]["nonstd_bridge_rows"][0]["bond_code"] == "BOND-001"
    get_settings.cache_clear()


def test_pnl_data_returns_one_sided_dates_with_empty_other_list(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    fi_only = client.get("/api/pnl/data", params={"date": "2026-01-31"})
    assert fi_only.status_code == 200
    fi_payload = fi_only.json()["result"]
    assert len(fi_payload["formal_fi_rows"]) == 1
    assert fi_payload["nonstd_bridge_rows"] == []

    nonstd_only = client.get("/api/pnl/data", params={"date": "2026-02-28"})
    assert nonstd_only.status_code == 200
    nonstd_payload = nonstd_only.json()["result"]
    assert nonstd_payload["formal_fi_rows"] == []
    assert len(nonstd_payload["nonstd_bridge_rows"]) == 1
    get_settings.cache_clear()


def test_pnl_data_returns_404_for_absent_union_date(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/data", params={"date": "2027-01-31"})

    assert response.status_code == 404
    assert response.json()["detail"] == "No pnl data found for report_date=2027-01-31 in fact_formal_pnl_fi or fact_nonstd_pnl_bridge."
    get_settings.cache_clear()


def test_pnl_overview_returns_backend_owned_aggregation_and_manifest_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(governance_dir, source_version="sv_overview", vendor_version="vv_overview", rule_version="rv_overview")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["result_kind"] == "pnl.overview"
    assert payload["result_meta"]["source_version"] == "sv_overview"
    assert payload["result_meta"]["vendor_version"] == "vv_overview"
    assert payload["result_meta"]["rule_version"] == "rv_overview"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v1"
    assert payload["result"] == {
        "report_date": "2025-12-31",
        "formal_fi_row_count": 1,
        "nonstd_bridge_row_count": 1,
        "interest_income_514": "12.50",
        "fair_value_change_516": "96.75",
        "capital_gain_517": "1.75",
        "manual_adjustment": "0.50",
        "total_pnl": "111.50",
    }
    get_settings.cache_clear()


def test_pnl_overview_returns_404_for_absent_union_date(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/overview", params={"report_date": "2027-01-31"})

    assert response.status_code == 404
    assert response.json()["detail"] == "No pnl data found for report_date=2027-01-31 in fact_formal_pnl_fi or fact_nonstd_pnl_bridge."
    get_settings.cache_clear()


def test_pnl_refresh_queue_and_latest_import_status_flow(tmp_path, monkeypatch):
    duckdb_path, governance_dir = _configure_refresh_sources(tmp_path, monkeypatch)
    queued_messages: list[dict[str, object]] = []
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    def fake_send(**kwargs):
        queued_messages.append(kwargs)
        return None

    monkeypatch.setattr(pnl_service.materialize_pnl_facts, "send", fake_send)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post("/api/data/refresh_pnl")

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["status"] == "queued"
    assert refresh_payload["job_name"] == "pnl_materialize"
    assert refresh_payload["trigger_mode"] == "async"
    assert refresh_payload["cache_key"] == "pnl:phase2:materialize:formal"
    assert refresh_payload["report_date"] == "2026-02-28"
    assert queued_messages[0]["run_id"] == refresh_payload["run_id"]
    assert queued_messages[0]["report_date"] == "2026-02-28"
    assert queued_messages[0]["is_month_end"] is True
    assert len(queued_messages[0]["fi_rows"]) > 0
    assert len(queued_messages[0]["nonstd_rows_by_type"]["516"]) == 2

    queued_status = client.get("/api/data/import_status/pnl")
    assert queued_status.status_code == 200
    assert queued_status.json()["status"] == "queued"
    assert queued_status.json()["run_id"] == refresh_payload["run_id"]

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        CacheBuildRunRecord(
            run_id=refresh_payload["run_id"],
            job_name="pnl_materialize",
            status="completed",
            cache_key="pnl:phase2:materialize:formal",
            lock="lock:duckdb:formal:pnl:phase2:materialize",
            source_version="sv_pnl_test",
            vendor_version="vv_none",
        ).model_dump(),
    )

    completed_status = client.get("/api/data/import_status/pnl")
    assert completed_status.status_code == 200
    completed_payload = completed_status.json()
    assert completed_payload["status"] == "completed"
    assert completed_payload["run_id"] == refresh_payload["run_id"]
    assert completed_payload["trigger_mode"] == "terminal"
    assert completed_payload["cache_key"] == "pnl:phase2:materialize:formal"
    assert completed_payload["source_version"] == "sv_pnl_test"
    assert duckdb_path.exists() is False
    get_settings.cache_clear()


def test_pnl_refresh_sync_fallback_materializes_latest_sources(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("queue disabled")),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post("/api/data/refresh_pnl")

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["status"] == "completed"
    assert refresh_payload["job_name"] == "pnl_materialize"
    assert refresh_payload["trigger_mode"] == "sync-fallback"
    assert refresh_payload["cache_key"] == "pnl:phase2:materialize:formal"
    assert refresh_payload["report_date"] == "2026-02-28"
    assert refresh_payload["formal_fi_rows"] > 0
    assert refresh_payload["nonstd_bridge_rows"] == 1

    status_response = client.get("/api/data/import_status/pnl")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["run_id"] == refresh_payload["run_id"]
    assert status_payload["report_date"] == "2026-02-28"
    assert status_payload["cache_key"] == "pnl:phase2:materialize:formal"
    assert status_payload["job_name"] == "pnl_materialize"

    dates_response = client.get("/api/pnl/dates")
    assert dates_response.status_code == 200
    assert dates_response.json()["result"]["report_dates"] == ["2026-02-28"]

    data_response = client.get("/api/pnl/data", params={"date": "2026-02-28"})
    assert data_response.status_code == 200
    assert len(data_response.json()["result"]["formal_fi_rows"]) > 0
    assert len(data_response.json()["result"]["nonstd_bridge_rows"]) == 1
    get_settings.cache_clear()


def test_pnl_refresh_returns_503_when_send_error_is_not_safe_for_sync_fallback(
    tmp_path,
    monkeypatch,
):
    _, governance_dir = _configure_refresh_sources(tmp_path, monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    fallback_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("unexpected broker failure")),
    )
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "fn",
        lambda **kwargs: fallback_calls.append(kwargs),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post("/api/data/refresh_pnl")

    assert response.status_code == 503
    assert response.json()["detail"] == "Pnl refresh queue dispatch failed."
    assert fallback_calls == []

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    latest = [record for record in records if record.get("job_name") == "pnl_materialize"][-1]
    assert latest["status"] == "failed"
    assert latest["error_message"] == "Pnl refresh queue dispatch failed."
    get_settings.cache_clear()


def test_pnl_refresh_returns_409_when_same_report_date_is_already_in_progress(
    tmp_path,
    monkeypatch,
):
    _configure_refresh_sources(tmp_path, monkeypatch)
    governance_dir = tmp_path / "governance"
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="run-inflight",
                job_name="pnl_materialize",
                status="running",
                cache_key="pnl:phase2:materialize:formal",
                lock="lock:duckdb:formal:pnl:phase2:materialize",
                source_version="sv_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": "2026-02-28",
            "queued_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    send_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: send_calls.append(kwargs),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post("/api/data/refresh_pnl")

    assert response.status_code == 409
    assert response.json()["detail"] == "Pnl refresh already in progress for report_date=2026-02-28."
    assert send_calls == []
    get_settings.cache_clear()


def test_pnl_refresh_returns_409_when_legacy_inflight_has_no_timestamps(
    tmp_path,
    monkeypatch,
):
    _configure_refresh_sources(tmp_path, monkeypatch)
    governance_dir = tmp_path / "governance"
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="run-legacy-inflight",
                job_name="pnl_materialize",
                status="running",
                cache_key="pnl:phase2:materialize:formal",
                lock="lock:duckdb:formal:pnl:phase2:materialize",
                source_version="sv_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": "2026-02-28",
        },
    )

    send_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: send_calls.append(kwargs),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post("/api/data/refresh_pnl")

    assert response.status_code == 409
    assert response.json()["detail"] == "Pnl refresh already in progress for report_date=2026-02-28."
    assert send_calls == []

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    legacy = [record for record in records if record.get("run_id") == "run-legacy-inflight"]
    assert len(legacy) == 1
    assert legacy[0]["status"] == "running"
    get_settings.cache_clear()


def test_pnl_refresh_reconciles_stale_inflight_run_and_requeues_requested_month(
    tmp_path,
    monkeypatch,
):
    _configure_refresh_sources(tmp_path, monkeypatch)
    governance_dir = tmp_path / "governance"
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="run-stale",
                job_name="pnl_materialize",
                status="running",
                cache_key="pnl:phase2:materialize:formal",
                lock="lock:duckdb:formal:pnl:phase2:materialize",
                source_version="sv_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": "2026-02-28",
            "queued_at": stale_time,
        },
    )

    queued_messages: list[dict[str, object]] = []
    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post("/api/data/refresh_pnl")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert queued_messages[0]["report_date"] == "2026-02-28"

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    stale_records = [record for record in records if record.get("run_id") == "run-stale"]
    assert stale_records[-1]["status"] == "failed"
    assert stale_records[-1]["error_message"] == "Marked stale pnl refresh run as failed."
    get_settings.cache_clear()


def test_pnl_refresh_report_date_queues_exact_requested_month(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    _copy_fi_refresh_source(tmp_path, month_key="202601")
    queued_messages: list[dict[str, object]] = []
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post("/api/data/refresh_pnl", params={"report_date": "2026-01-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["report_date"] == "2026-01-31"
    assert queued_messages[0]["report_date"] == "2026-01-31"
    assert queued_messages[0]["nonstd_rows_by_type"] == {}
    get_settings.cache_clear()


def test_pnl_refresh_report_date_sync_fallback_materializes_requested_month(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    _copy_fi_refresh_source(tmp_path, month_key="202601")
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("queue disabled")),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post("/api/data/refresh_pnl", params={"report_date": "2026-01-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["report_date"] == "2026-01-31"
    assert payload["nonstd_bridge_rows"] == 0

    dates_response = client.get("/api/pnl/dates")
    assert dates_response.status_code == 200
    assert dates_response.json()["result"]["report_dates"] == ["2026-01-31"]
    get_settings.cache_clear()


def test_pnl_refresh_report_date_returns_404_when_requested_month_is_missing(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post("/api/data/refresh_pnl", params={"report_date": "2024-12-31"})

    assert response.status_code == 404
    assert "2024-12-31" in response.json()["detail"]
    get_settings.cache_clear()


def test_pnl_refresh_ignores_nonstd_rows_outside_target_report_month(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    nonstd_path = next((tmp_path / "data_input" / "pnl_516").glob("*.xlsx"))
    _write_nonstd_refresh_workbook(
        nonstd_path,
        include_prior_month_row=True,
    )
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("queue disabled")),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post("/api/data/refresh_pnl")

    assert refresh_response.status_code == 200
    assert refresh_response.json()["status"] == "completed"

    data_response = client.get("/api/pnl/data", params={"date": "2026-02-28"})

    assert data_response.status_code == 200
    bridge_row = data_response.json()["result"]["nonstd_bridge_rows"][0]
    assert Decimal(bridge_row["fair_value_change_516"]) == Decimal("100.00")
    assert Decimal(bridge_row["total_pnl"]) == Decimal("100.00")
    get_settings.cache_clear()


def test_pnl_import_status_run_id_returns_exact_queued_record(tmp_path, monkeypatch):
    governance_dir = _configure_import_status_env(tmp_path, monkeypatch)
    _append_pnl_build_run(governance_dir, run_id="run-queued", status="queued", source_version="sv_queued")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/data/import_status/pnl", params={"run_id": "run-queued"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-queued"
    assert payload["status"] == "queued"
    assert payload["source_version"] == "sv_queued"
    assert payload["trigger_mode"] == "async"
    get_settings.cache_clear()


def test_pnl_import_status_run_id_returns_latest_matching_completed_record_without_unrelated_fallback(tmp_path, monkeypatch):
    governance_dir = _configure_import_status_env(tmp_path, monkeypatch)
    _append_pnl_build_run(governance_dir, run_id="run-target", status="queued", source_version="sv_q")
    _append_pnl_build_run(governance_dir, run_id="run-target", status="running", source_version="sv_r")
    _append_pnl_build_run(governance_dir, run_id="run-target", status="completed", source_version="sv_done")
    _append_pnl_build_run(governance_dir, run_id="run-newer", status="queued", source_version="sv_other")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/data/import_status/pnl", params={"run_id": "run-target"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-target"
    assert payload["status"] == "completed"
    assert payload["source_version"] == "sv_done"
    assert payload["trigger_mode"] == "terminal"
    get_settings.cache_clear()


def test_pnl_import_status_run_id_returns_failed_terminal_record(tmp_path, monkeypatch):
    governance_dir = _configure_import_status_env(tmp_path, monkeypatch)
    _append_pnl_build_run(governance_dir, run_id="run-failed", status="queued", source_version="sv_q")
    _append_pnl_build_run(
        governance_dir,
        run_id="run-failed",
        status="failed",
        source_version="sv_failed",
        error_message="duckdb transaction rolled back",
        report_date="2026-01-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/data/import_status/pnl", params={"run_id": "run-failed"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-failed"
    assert payload["status"] == "failed"
    assert payload["source_version"] == "sv_failed"
    assert payload["trigger_mode"] == "terminal"
    assert payload["error_message"] == "duckdb transaction rolled back"
    assert payload["report_date"] == "2026-01-31"
    assert payload["cache_key"] == "pnl:phase2:materialize:formal"
    assert payload["job_name"] == "pnl_materialize"
    get_settings.cache_clear()


def test_pnl_import_status_run_id_returns_404_for_unknown_run_id(tmp_path, monkeypatch):
    _configure_import_status_env(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/data/import_status/pnl", params={"run_id": "run-missing"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown pnl refresh run_id=run-missing"
    get_settings.cache_clear()


def test_pnl_import_status_returns_503_when_status_backend_fails(tmp_path, monkeypatch):
    _configure_import_status_env(tmp_path, monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    monkeypatch.setattr(
        pnl_service.GovernanceRepository,
        "read_all",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("status backend unavailable")),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get("/api/data/import_status/pnl", params={"run_id": "run-any"})

    assert response.status_code == 503
    assert response.json()["detail"] == "status backend unavailable"
    get_settings.cache_clear()


def test_pnl_dates_returns_503_when_storage_is_unavailable_even_if_manifest_exists(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    _append_manifest_override(governance_dir, source_version="sv_manifest", vendor_version="vv_manifest", rule_version="rv_manifest")

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "missing.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/dates")

    assert response.status_code == 503
    assert response.json()["detail"] == "Formal pnl storage is unavailable."
    get_settings.cache_clear()


def test_pnl_overview_returns_503_when_storage_is_unavailable_even_if_manifest_exists(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    _append_manifest_override(governance_dir, source_version="sv_manifest", vendor_version="vv_manifest", rule_version="rv_manifest")

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "missing.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Formal pnl storage is unavailable."
    get_settings.cache_clear()


def _materialize_three_pnl_dates(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.pnl_materialize")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.pnl_materialize",
            "backend/app/tasks/pnl_materialize.py",
        )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    shared = {
        "report_date": "2025-12-31",
        "is_month_end": True,
        "duckdb_path": str(duckdb_path),
        "governance_dir": str(governance_dir),
    }
    task_module.materialize_pnl_facts.fn(
        fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "12.50",
                "fair_value_change_516": "-3.25",
                "capital_gain_517": "1.75",
                "manual_adjustment": "0.50",
                "currency_basis": "CNY",
                "source_version": "fi-shared-v1",
                "rule_version": "src-rule-fi-shared",
                "ingest_batch_id": "batch-fi-shared",
                "trace_id": "trace-fi-shared",
            }
        ],
        nonstd_rows_by_type={
            "516": [
                {
                    "voucher_date": "2025-12-30",
                    "account_code": "51601010004",
                    "asset_code": "BOND-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "credit",
                    "event_type": "mtm",
                    "raw_amount": "40.00",
                    "source_file": "nonstd-516.xlsx",
                    "source_version": "nonstd-shared-v1",
                    "rule_version": "src-rule-nonstd-shared",
                    "ingest_batch_id": "batch-bridge-shared",
                    "trace_id": "trace-001",
                },
                {
                    "voucher_date": "2025-12-31",
                    "account_code": "51601010004",
                    "asset_code": "BOND-001",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "dc_flag": "credit",
                    "event_type": "mtm",
                    "raw_amount": "60.00",
                    "source_file": "nonstd-516.xlsx",
                    "source_version": "nonstd-shared-v1",
                    "rule_version": "src-rule-nonstd-shared",
                    "ingest_batch_id": "batch-bridge-shared",
                    "trace_id": "trace-002",
                },
            ]
        },
        **shared,
    )

    task_module.materialize_pnl_facts.fn(
        fi_rows=[
            {
                "report_date": "2026-01-31",
                "instrument_code": "250001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC200",
                "invest_type_raw": "持有至到期",
                "interest_income_514": "20.00",
                "fair_value_change_516": "0.00",
                "capital_gain_517": "1.00",
                "manual_adjustment": "0.00",
                "currency_basis": "CNY",
                "source_version": "fi-only-v1",
                "rule_version": "src-rule-fi-only",
                "ingest_batch_id": "batch-fi-only",
                "trace_id": "trace-fi-only",
            }
        ],
        nonstd_rows_by_type={},
        report_date="2026-01-31",
        is_month_end=True,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    task_module.materialize_pnl_facts.fn(
        fi_rows=[],
        nonstd_rows_by_type={
            "514": [
                {
                    "voucher_date": "2026-02-28",
                    "account_code": "51401000004",
                    "asset_code": None,
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC300",
                    "dc_flag": "贷",
                    "event_type": "interest",
                    "raw_amount": "15.00",
                    "source_file": "nonstd-514.xlsx",
                    "source_version": "nonstd-only-v1",
                    "rule_version": "src-rule-nonstd-only",
                    "ingest_batch_id": "batch-bridge-only",
                    "trace_id": "trace-514",
                }
            ]
        },
        report_date="2026-02-28",
        is_month_end=True,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    return governance_dir


def _append_manifest_override(governance_dir, *, source_version: str, vendor_version: str, rule_version: str):
    manifest_path = governance_dir / "cache_manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "cache_key": "pnl:phase2:materialize:formal",
                    "source_version": source_version,
                    "vendor_version": vendor_version,
                    "rule_version": rule_version,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


def _configure_refresh_sources(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    data_root = tmp_path / "data_input"
    (data_root / "pnl").mkdir(parents=True)
    (data_root / "pnl_516").mkdir(parents=True)

    source_fi = ROOT / "data_input" / "pnl" / "FI损益202602.xls"
    target_fi = data_root / "pnl" / source_fi.name
    target_fi.write_bytes(source_fi.read_bytes())
    _write_nonstd_refresh_workbook(data_root / "pnl_516" / "非标516-20260101-0228.xlsx")

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    get_settings.cache_clear()
    return duckdb_path, governance_dir


def _copy_fi_refresh_source(tmp_path, *, month_key: str):
    source_fi = ROOT / "data_input" / "pnl" / f"FI损益{month_key}.xls"
    target_fi = tmp_path / "data_input" / "pnl" / source_fi.name
    target_fi.write_bytes(source_fi.read_bytes())


def _configure_import_status_env(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    return governance_dir


def _append_pnl_build_run(
    governance_dir,
    *,
    run_id: str,
    status: str,
    source_version: str,
    **extra: object,
):
    record = CacheBuildRunRecord(
        run_id=run_id,
        job_name="pnl_materialize",
        status=status,
        cache_key="pnl:phase2:materialize:formal",
        lock="lock:duckdb:formal:pnl:phase2:materialize",
        source_version=source_version,
        vendor_version="vv_none",
    ).model_dump()
    for key, value in extra.items():
        if value is not None:
            record[key] = value
    GovernanceRepository(base_dir=governance_dir).append(CACHE_BUILD_RUN_STREAM, record)


def _write_nonstd_refresh_workbook(path: Path, *, include_prior_month_row: bool = False) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append(["会计分录详情表"])
    worksheet.append(
        [
            "账务流水号",
            "序号",
            "所属账套",
            "账务日期",
            "交易流水号",
            "内部账户号",
            "产品类型",
            "客户名称",
            "会计分类",
            "成本中心",
            "投资组合",
            "资产代码",
            "交易机构",
            "会计事件",
            "币种",
            "借贷标识",
            "科目号",
            "科目名称",
            "金额",
            "备注",
        ]
    )
    if include_prior_month_row:
        worksheet.append(
            [
                "1411967",
                "0",
                "默认账套",
                "2026-01-31",
                "TRD000",
                "",
                "证券投资基金",
                "测试产品Z",
                "FVTPL",
                "5010",
                "FIOA",
                "BOND-001",
                "80002",
                "月初遗留估值",
                "人民币",
                "贷",
                "51601010004",
                "公允价值变动损益",
                "30.00",
                "carryover_val|",
            ]
        )
    worksheet.append(
        [
            "1411968",
            "1",
            "默认账套",
            "2026-02-27",
            "TRD001",
            "",
            "证券投资基金",
            "测试产品A",
            "FVTPL",
            "5010",
            "FIOA",
            "BOND-001",
            "80002",
            "冲销前一日估值",
            "人民币",
            "贷",
            "51601010004",
            "公允价值变动损益",
            "40.00",
            "revmtm_val|",
        ]
    )
    worksheet.append(
        [
            "1411969",
            "2",
            "默认账套",
            "2026-02-28",
            "TRD002",
            "",
            "证券投资基金",
            "测试产品B",
            "FVTPL",
            "5010",
            "FIOA",
            "BOND-001",
            "80002",
            "估值入账",
            "人民币",
            "贷",
            "51601010004",
            "公允价值变动损益",
            "60.00",
            "mtm_val|",
        ]
    )
    workbook.save(path)
