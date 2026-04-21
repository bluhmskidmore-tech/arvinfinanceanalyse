from __future__ import annotations
import json
import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import duckdb

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheBuildRunRecord
from tests.helpers import load_module
from tests.test_balance_analysis_materialize_flow import (
    _patch_skip_fx_refresh,
    _seed_snapshot_and_fx_tables,
)


def _configure_and_materialize(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_snapshot_and_fx_tables(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.balance_analysis_materialize",
        "backend/app/tasks/balance_analysis_materialize.py",
    )
    _patch_skip_fx_refresh(task_mod, monkeypatch)
    task_mod.materialize_balance_analysis_facts.fn(
        report_date="2025-12-31",
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    return duckdb_path, governance_dir, task_mod


def _seed_balance_decision_scope(tmp_path, monkeypatch, *, user_id: str, role: str | None = None) -> None:
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()
    repo_mod = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo = repo_mod.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")
    repo.grant_scope(
        user_id=user_id,
        role=role,
        resource="balance_analysis.decision_status",
        action="write",
    )


def _seed_overview_lineage_fixture(duckdb_path, governance_dir) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, market_value_amount,
              amortized_cost_amount, accrued_interest_amount, is_issuance_like, source_version,
              rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-11-30",
                "240099.IB",
                "Portfolio X",
                "CC999",
                "A",
                "FVOCI",
                "asset",
                "CNY",
                "100.00000000",
                "95.00000000",
                "4.00000000",
                False,
                "sv-z-old",
                "rv_balance_analysis_formal_materialize_v1",
                "ib-old-z",
                "trace-old-z",
            ],
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily (
              report_date, position_id, product_type, position_side, counterparty_name,
              invest_type_std, accounting_basis, position_scope, currency_basis,
              principal_amount, accrued_interest_amount, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-11-30",
                "pos-old-1",
                "Interbank",
                "liability",
                "Bank X",
                "H",
                "AC",
                "liability",
                "CNY",
                "20.00000000",
                "1.00000000",
                "sv-t-old",
                "rv_balance_analysis_formal_materialize_v1",
                "ib-old-t",
                "trace-old-t",
            ],
        )
    finally:
        conn.close()

    governance = GovernanceRepository(base_dir=governance_dir)
    governance.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="run-old",
                job_name="balance_analysis_materialize",
                status="completed",
                cache_key="balance_analysis:materialize:formal",
                lock="lock:duckdb:formal:balance-analysis:materialize",
                source_version="sv-fx-old__sv-t-old__sv-z-old",
                vendor_version="vv_none",
                rule_version="rv-old-balance",
            ).model_dump(),
            "report_date": "2025-11-30",
        },
    )
    governance.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="run-new",
                job_name="balance_analysis_materialize",
                status="completed",
                cache_key="balance_analysis:materialize:formal",
                lock="lock:duckdb:formal:balance-analysis:materialize",
                source_version="sv-fx-new__sv-t-new__sv-z-new",
                vendor_version="vv_none",
                rule_version="rv-new-balance",
            ).model_dump(),
            "report_date": "2026-01-31",
        },
    )
    governance.append(
        CACHE_MANIFEST_STREAM,
        {
            "cache_key": "balance_analysis:materialize:formal",
            "source_version": "sv-fx-new__sv-t-new__sv-z-new",
            "vendor_version": "vv_none",
            "rule_version": "rv_balance_analysis_formal_materialize_v1",
        },
    )


def _seed_overview_orphan_lineage_fixture(duckdb_path, governance_dir) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, market_value_amount,
              amortized_cost_amount, accrued_interest_amount, is_issuance_like, source_version,
              rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-10-31",
                "240088.IB",
                "Portfolio Y",
                "CC888",
                "A",
                "FVOCI",
                "asset",
                "CNY",
                "88.00000000",
                "80.00000000",
                "3.00000000",
                False,
                "sv-z-orphan",
                "rv_balance_analysis_formal_materialize_v1",
                "ib-orphan-z",
                "trace-orphan-z",
            ],
        )
    finally:
        conn.close()

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_MANIFEST_STREAM,
        {
            "cache_key": "balance_analysis:materialize:formal",
            "source_version": "sv-fx-new__sv-t-new__sv-z-new",
            "vendor_version": "vv_none",
            "rule_version": "rv_balance_analysis_formal_materialize_v1",
        },
    )


def _remove_completed_balance_analysis_build_runs(governance_dir: Path) -> None:
    path = governance_dir / "cache_build_run.jsonl"
    if not path.exists():
        return

    kept: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        if (
            str(payload.get("cache_key") or "").strip() == "balance_analysis:materialize:formal"
            and str(payload.get("job_name") or "").strip() == "balance_analysis_materialize"
            and str(payload.get("status") or "").strip() == "completed"
        ):
            continue
        kept.append(line)

    path.write_text(
        ("\n".join(kept) + "\n") if kept else "",
        encoding="utf-8",
    )


def test_balance_analysis_dates_and_detail_api_flow(tmp_path, monkeypatch):
    _duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    dates_response = client.get("/ui/balance-analysis/dates")
    assert dates_response.status_code == 200
    dates_payload = dates_response.json()
    assert dates_payload["result_meta"]["basis"] == "formal"
    assert dates_payload["result_meta"]["result_kind"] == "balance-analysis.dates"
    assert dates_payload["result"]["report_dates"] == ["2025-12-31"]

    detail_response = client.get(
        "/ui/balance-analysis",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["result_meta"]["basis"] == "formal"
    assert detail_payload["result_meta"]["formal_use_allowed"] is True
    assert detail_payload["result_meta"]["result_kind"] == "balance-analysis.detail"
    assert detail_payload["result_meta"]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"
    assert detail_payload["result_meta"]["cache_version"] == "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1"
    assert detail_payload["result"]["report_date"] == "2025-12-31"
    assert detail_payload["result"]["position_scope"] == "all"
    assert detail_payload["result"]["currency_basis"] == "CNY"
    assert {row["source_family"] for row in detail_payload["result"]["details"]} == {"zqtz", "tyw"}
    assert {row["source_family"] for row in detail_payload["result"]["summary"]} == {"zqtz", "tyw"}

    overview_response = client.get(
        "/ui/balance-analysis/overview",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )
    assert overview_response.status_code == 200
    overview_payload = overview_response.json()
    assert overview_payload["result_meta"]["basis"] == "formal"
    assert overview_payload["result_meta"]["formal_use_allowed"] is True
    assert overview_payload["result_meta"]["result_kind"] == "balance-analysis.overview"
    assert overview_payload["result_meta"]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"
    assert overview_payload["result_meta"]["rule_version"] == "rv_balance_analysis_formal_materialize_v1"
    assert overview_payload["result_meta"]["cache_version"] == (
        "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1"
    )
    assert overview_payload["result"] == {
        "report_date": "2025-12-31",
        "position_scope": "all",
        "currency_basis": "CNY",
        "detail_row_count": 2,
        "summary_row_count": 2,
        "total_market_value_amount": "792.00000000",
        "total_amortized_cost_amount": "720.00000000",
        "total_accrued_interest_amount": "50.40000000",
    }

    workbook_response = client.get(
        "/ui/balance-analysis/workbook",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )
    assert workbook_response.status_code == 200
    workbook_payload = workbook_response.json()
    table_map = {table["key"]: table for table in workbook_payload["result"]["tables"]}
    operational_map = {
        section["key"]: section for section in workbook_payload["result"]["operational_sections"]
    }
    assert operational_map["decision_items"]["section_kind"] == "decision_items"
    assert operational_map["event_calendar"]["section_kind"] == "event_calendar"
    assert operational_map["risk_alerts"]["section_kind"] == "risk_alerts"
    assert {
        "title",
        "action_label",
        "severity",
        "reason",
        "source_section",
        "rule_id",
        "rule_version",
    } <= set(operational_map["decision_items"]["rows"][0])
    assert {
        "event_date",
        "event_type",
        "title",
        "source",
        "impact_hint",
        "source_section",
    } <= set(operational_map["event_calendar"]["rows"][0])
    assert {
        "title",
        "severity",
        "reason",
        "source_section",
        "rule_id",
        "rule_version",
    } <= set(operational_map["risk_alerts"]["rows"][0])

    get_settings.cache_clear()


def test_balance_analysis_workbook_api_keeps_right_rail_sections_when_rows_are_empty(tmp_path, monkeypatch):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    workbook_mod = load_module(
        "backend.app.core_finance.balance_analysis_workbook",
        "backend/app/core_finance/balance_analysis_workbook.py",
    )
    original_builder = workbook_mod.build_balance_analysis_workbook_payload

    def build_empty_right_rail(**kwargs):
        payload = original_builder(**kwargs)
        for table in payload["tables"]:
            if table["section_kind"] in {"decision_items", "event_calendar", "risk_alerts"}:
                table["rows"] = []
        return payload

    monkeypatch.setattr(workbook_mod, "build_balance_analysis_workbook_payload", build_empty_right_rail)
    monkeypatch.setattr(service_mod.importlib, "reload", lambda module: module)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/balance-analysis/workbook",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    operational_map = {
        section["key"]: section for section in payload["result"]["operational_sections"]
    }
    assert operational_map["decision_items"]["section_kind"] == "decision_items"
    assert operational_map["decision_items"]["rows"] == []
    assert operational_map["event_calendar"]["section_kind"] == "event_calendar"
    assert operational_map["event_calendar"]["rows"] == []
    assert operational_map["risk_alerts"]["section_kind"] == "risk_alerts"
    assert operational_map["risk_alerts"]["rows"] == []

    get_settings.cache_clear()


def test_balance_analysis_decision_items_api_returns_generated_items_with_pending_status(
    tmp_path,
    monkeypatch,
):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(
        "/ui/balance-analysis/decision-items",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "balance-analysis.decision-items"
    assert payload["result_meta"]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"
    assert payload["result"]["report_date"] == "2025-12-31"
    assert payload["result"]["position_scope"] == "all"
    assert payload["result"]["currency_basis"] == "CNY"
    assert payload["result"]["columns"] == [
        {"key": "title", "label": "Title"},
        {"key": "action_label", "label": "Action"},
        {"key": "severity", "label": "Severity"},
        {"key": "reason", "label": "Reason"},
        {"key": "source_section", "label": "Source Section"},
        {"key": "rule_id", "label": "Rule Id"},
        {"key": "rule_version", "label": "Rule Version"},
    ]
    assert payload["result"]["rows"][0]["decision_key"]
    assert payload["result"]["rows"][0]["latest_status"] == {
        "decision_key": payload["result"]["rows"][0]["decision_key"],
        "status": "pending",
        "updated_at": None,
        "updated_by": None,
        "comment": None,
    }

    get_settings.cache_clear()


def test_balance_analysis_current_user_api_uses_same_auth_context_as_status_write(tmp_path, monkeypatch):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/balance-analysis/current-user",
        headers={
            "X-User-Id": "decision-owner",
            "X-User-Role": "reviewer",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "decision-owner",
        "role": "reviewer",
        "identity_source": "header",
    }

    get_settings.cache_clear()


def test_balance_analysis_decision_status_update_overlays_latest_state(tmp_path, monkeypatch):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    _seed_balance_decision_scope(tmp_path, monkeypatch, user_id="balance-owner")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    list_response = client.get(
        "/ui/balance-analysis/decision-items",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )
    decision_key = list_response.json()["result"]["rows"][0]["decision_key"]

    update_response = client.post(
        "/ui/balance-analysis/decision-items/status",
        headers={"X-User-Id": "balance-owner"},
        json={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
            "decision_key": decision_key,
            "status": "confirmed",
            "comment": "Reviewed and accepted.",
        },
    )

    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["decision_key"] == decision_key
    assert update_payload["status"] == "confirmed"
    assert update_payload["updated_by"] == "balance-owner"
    assert update_payload["comment"] == "Reviewed and accepted."
    assert update_payload["updated_at"]

    refreshed_response = client.get(
        "/ui/balance-analysis/decision-items",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )

    assert refreshed_response.status_code == 200
    refreshed_rows = refreshed_response.json()["result"]["rows"]
    refreshed_row = next(row for row in refreshed_rows if row["decision_key"] == decision_key)
    assert refreshed_row["latest_status"] == {
        "decision_key": decision_key,
        "status": "confirmed",
        "updated_at": update_payload["updated_at"],
        "updated_by": "balance-owner",
        "comment": "Reviewed and accepted.",
    }

    get_settings.cache_clear()


def test_balance_analysis_decision_status_update_returns_404_for_unknown_decision_key(
    tmp_path,
    monkeypatch,
):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    _seed_balance_decision_scope(tmp_path, monkeypatch, user_id="balance-owner")

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post(
        "/ui/balance-analysis/decision-items/status",
        headers={"X-User-Id": "balance-owner"},
        json={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
            "decision_key": "missing-rule::missing-section::missing-title",
            "status": "confirmed",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Unknown balance-analysis decision_key for the requested report_date and filters."
    )

    get_settings.cache_clear()


def test_balance_analysis_decision_status_update_returns_403_without_scope(tmp_path, monkeypatch):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    list_response = client.get(
        "/ui/balance-analysis/decision-items",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )
    decision_key = list_response.json()["result"]["rows"][0]["decision_key"]

    response = client.post(
        "/ui/balance-analysis/decision-items/status",
        headers={"X-User-Id": "unauthorized-user", "X-User-Role": "viewer"},
        json={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
            "decision_key": decision_key,
            "status": "confirmed",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User is not allowed to update balance-analysis decision status."

    get_settings.cache_clear()


def test_balance_analysis_decision_status_update_returns_503_when_scope_store_is_unavailable(
    tmp_path,
    monkeypatch,
):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_POSTGRES_DSN", "postgresql://invalid:invalid@127.0.0.1:1/moss")
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", "")
    get_settings.cache_clear()

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    list_response = client.get(
        "/ui/balance-analysis/decision-items",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )
    decision_key = list_response.json()["result"]["rows"][0]["decision_key"]

    response = client.post(
        "/ui/balance-analysis/decision-items/status",
        headers={"X-User-Id": "unlucky-user", "X-User-Role": "viewer"},
        json={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
            "decision_key": decision_key,
            "status": "confirmed",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "User scope store is unavailable."

    get_settings.cache_clear()


def test_balance_analysis_current_user_api_falls_back_to_env_identity(tmp_path, monkeypatch):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_USER_ID", "env-balance-user")
    monkeypatch.setenv("MOSS_USER_ROLE", "ops")
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/ui/balance-analysis/current-user")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "env-balance-user",
        "role": "ops",
        "identity_source": "env",
    }

    get_settings.cache_clear()


def test_balance_analysis_detail_and_overview_use_report_date_specific_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    conn = __import__("duckdb").connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, market_value_amount,
              amortized_cost_amount, accrued_interest_amount, is_issuance_like, source_version,
              rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-11-30",
                "old-zqtz",
                "组合旧",
                "CC-old",
                "H",
                "AC",
                "asset",
                "CNY",
                "11.00000000",
                "10.00000000",
                "1.00000000",
                False,
                "sv-old-z",
                "rv-old-balance",
                "ib-old-z",
                "trace-old-z",
            ],
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily (
              report_date, position_id, product_type, position_side, counterparty_name,
              invest_type_std, accounting_basis, position_scope, currency_basis,
              principal_amount, accrued_interest_amount, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-11-30",
                "old-tyw",
                "老同业",
                "liability",
                "银行旧",
                "H",
                "AC",
                "liability",
                "CNY",
                "5.00000000",
                "0.50000000",
                "sv-old-t",
                "rv-old-balance",
                "ib-old-t",
                "trace-old-t",
            ],
        )
    finally:
        conn.close()

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="run-old-inline",
                job_name="balance_analysis_materialize",
                status="completed",
                cache_key="balance_analysis:materialize:formal",
                lock="lock:duckdb:formal:balance-analysis:materialize",
                source_version="sv-old-t__sv-old-z",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": "2025-11-30",
        },
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    detail_response = client.get(
        "/ui/balance-analysis",
        params={"report_date": "2025-11-30", "position_scope": "all", "currency_basis": "CNY"},
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["result_meta"]["source_version"] == "sv-old-t__sv-old-z"
    assert detail_payload["result_meta"]["rule_version"] == "rv-old-balance"

    overview_response = client.get(
        "/ui/balance-analysis/overview",
        params={"report_date": "2025-11-30", "position_scope": "all", "currency_basis": "CNY"},
    )
    assert overview_response.status_code == 200
    overview_payload = overview_response.json()
    assert overview_payload["result_meta"]["source_version"] == "sv-old-t__sv-old-z"
    assert overview_payload["result_meta"]["rule_version"] == "rv-old-balance"

    get_settings.cache_clear()


def test_balance_analysis_overview_api_returns_404_for_absent_report_date(tmp_path, monkeypatch):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(
        "/ui/balance-analysis/overview",
        params={
            "report_date": "2026-01-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "No balance-analysis data found for report_date=2026-01-31."

    get_settings.cache_clear()


def test_balance_analysis_overview_rejects_invalid_filter_values(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(
        "/ui/balance-analysis/overview",
        params={
            "report_date": "2025-12-31",
            "position_scope": "weird-scope",
            "currency_basis": "USD",
        },
    )

    assert response.status_code == 422
    get_settings.cache_clear()


def test_balance_analysis_overview_uses_report_date_specific_lineage_even_when_newer_manifest_exists(
    tmp_path,
    monkeypatch,
):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    _seed_overview_lineage_fixture(duckdb_path, governance_dir)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(
        "/ui/balance-analysis/overview",
        params={
            "report_date": "2025-11-30",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "balance-analysis.overview"
    assert payload["result_meta"]["source_version"] == "sv-fx-old__sv-t-old__sv-z-old"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["rule_version"] == "rv-old-balance"
    assert payload["result"]["report_date"] == "2025-11-30"

    get_settings.cache_clear()


def test_balance_analysis_overview_returns_503_when_report_date_lineage_is_missing(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    _seed_overview_orphan_lineage_fixture(duckdb_path, governance_dir)

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )

    response = client.get(
        "/ui/balance-analysis/overview",
        params={
            "report_date": "2025-10-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Canonical balance-analysis source_version unavailable for report_date=2025-10-31."
    )

    get_settings.cache_clear()


def test_balance_analysis_surfaces_fall_back_to_report_date_manifest_when_completed_run_is_missing(
    tmp_path,
    monkeypatch,
):
    _duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    _remove_completed_balance_analysis_build_runs(governance_dir)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    overview_response = client.get(
        "/ui/balance-analysis/overview",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )
    assert overview_response.status_code == 200
    overview_payload = overview_response.json()
    assert overview_payload["result_meta"]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"

    summary_response = client.get(
        "/ui/balance-analysis/summary",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
            "limit": 1,
            "offset": 0,
        },
    )
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["result_meta"]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"

    workbook_response = client.get(
        "/ui/balance-analysis/workbook",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )
    assert workbook_response.status_code == 200
    workbook_payload = workbook_response.json()
    assert workbook_payload["result_meta"]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"

    decision_response = client.get(
        "/ui/balance-analysis/decision-items",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )
    assert decision_response.status_code == 200
    decision_payload = decision_response.json()
    assert decision_payload["result_meta"]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"

    get_settings.cache_clear()


def test_balance_analysis_overview_returns_422_for_invalid_filters(tmp_path, monkeypatch):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    invalid_scope = client.get(
        "/ui/balance-analysis/overview",
        params={
            "report_date": "2025-12-31",
            "position_scope": "wrong-scope",
            "currency_basis": "CNY",
        },
    )
    assert invalid_scope.status_code == 422

    invalid_currency = client.get(
        "/ui/balance-analysis/overview",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "USD",
        },
    )
    assert invalid_currency.status_code == 422

    get_settings.cache_clear()


def test_balance_analysis_summary_api_returns_paginated_rows(tmp_path, monkeypatch):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(
        "/ui/balance-analysis/summary",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
            "limit": 1,
            "offset": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "balance-analysis.summary"
    assert payload["result_meta"]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"
    assert payload["result_meta"]["rule_version"] == "rv_balance_analysis_formal_materialize_v1"
    assert payload["result"] == {
        "report_date": "2025-12-31",
        "position_scope": "all",
        "currency_basis": "CNY",
        "limit": 1,
        "offset": 1,
        "total_rows": 2,
        "rows": [
            {
                "row_key": "tyw:pos-1:CNY:liability:H:AC",
                "source_family": "tyw",
                "display_name": "pos-1",
                "owner_name": "银行A",
                "category_name": "持有至到期同业存单",
                "position_scope": "liability",
                "currency_basis": "CNY",
                "invest_type_std": "H",
                "accounting_basis": "AC",
                "detail_row_count": 1,
                "market_value_amount": "72.00000000",
                "amortized_cost_amount": "72.00000000",
                "accrued_interest_amount": "14.40000000",
            }
        ],
    }

    get_settings.cache_clear()


def test_balance_analysis_summary_by_basis_api_aggregates_zqtz_and_tyw(tmp_path, monkeypatch):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(
        "/ui/balance-analysis/summary-by-basis",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "balance-analysis.basis-breakdown"
    assert payload["result_meta"]["source_version"] == "sv-fx-1__sv-t-1__sv-z-1"
    assert payload["result_meta"]["rule_version"] == "rv_balance_analysis_formal_materialize_v1"
    assert payload["result"] == {
        "report_date": "2025-12-31",
        "position_scope": "all",
        "currency_basis": "CNY",
        "rows": [
            {
                "source_family": "tyw",
                "invest_type_std": "H",
                "accounting_basis": "AC",
                "position_scope": "liability",
                "currency_basis": "CNY",
                "detail_row_count": 1,
                "market_value_amount": "72.00000000",
                "amortized_cost_amount": "72.00000000",
                "accrued_interest_amount": "14.40000000",
            },
            {
                "source_family": "zqtz",
                "invest_type_std": "A",
                "accounting_basis": "FVOCI",
                "position_scope": "asset",
                "currency_basis": "CNY",
                "detail_row_count": 1,
                "market_value_amount": "720.00000000",
                "amortized_cost_amount": "648.00000000",
                "accrued_interest_amount": "36.00000000",
            },
        ],
    }

    asset_only = client.get(
        "/ui/balance-analysis/summary-by-basis",
        params={
            "report_date": "2025-12-31",
            "position_scope": "asset",
            "currency_basis": "CNY",
        },
    )
    assert asset_only.status_code == 200
    assert asset_only.json()["result"]["rows"] == [
        {
            "source_family": "zqtz",
            "invest_type_std": "A",
            "accounting_basis": "FVOCI",
            "position_scope": "asset",
            "currency_basis": "CNY",
            "detail_row_count": 1,
            "market_value_amount": "720.00000000",
            "amortized_cost_amount": "648.00000000",
            "accrued_interest_amount": "36.00000000",
        },
    ]

    get_settings.cache_clear()


def test_balance_analysis_summary_export_csv_uses_filtered_rows_and_provenance(tmp_path, monkeypatch):
    _duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(
        "/ui/balance-analysis/summary/export",
        params={
            "report_date": "2025-12-31",
            "position_scope": "asset",
            "currency_basis": "CNY",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="balance-analysis-summary-2025-12-31-asset-CNY.csv"'
    )

    rows = list(csv.DictReader(StringIO(response.text)))
    assert rows == [
        {
                "row_key": "zqtz:240001.IB:组合A:CC100:CNY:asset:A:FVOCI",
                "source_family": "zqtz",
                "display_name": "240001.IB",
            "owner_name": "组合A",
            "category_name": "CC100",
            "position_scope": "asset",
            "currency_basis": "CNY",
            "invest_type_std": "A",
            "accounting_basis": "FVOCI",
            "detail_row_count": "1",
            "market_value_amount": "720.00000000",
            "amortized_cost_amount": "648.00000000",
            "accrued_interest_amount": "36.00000000",
            "report_date": "2025-12-31",
            "source_version": "sv-fx-1__sv-t-1__sv-z-1",
            "rule_version": "rv_balance_analysis_formal_materialize_v1",
        }
    ]

    get_settings.cache_clear()


def test_balance_analysis_summary_and_overview_count_real_group_rows(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, market_value_amount,
              amortized_cost_amount, accrued_interest_amount, is_issuance_like, source_version,
              rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                "2025-12-31",
                "240001.IB",
                "组合A",
                "CC100",
                "H",
                "AC",
                "asset",
                "CNY",
                "20.00000000",
                "19.00000000",
                "1.50000000",
                False,
                "sv-z-2",
                "rv_balance_analysis_formal_materialize_v1",
                "ib-z-2",
                "trace-z-2",
            ],
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    overview_response = client.get(
        "/ui/balance-analysis/overview",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        },
    )
    assert overview_response.status_code == 200
    overview_payload = overview_response.json()
    assert overview_payload["result"]["detail_row_count"] == 3
    assert overview_payload["result"]["summary_row_count"] == 3

    summary_response = client.get(
        "/ui/balance-analysis/summary",
        params={
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
            "limit": 10,
            "offset": 0,
        },
    )
    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["result"]["total_rows"] == 3
    row_keys = [row["row_key"] for row in summary_payload["result"]["rows"]]
    assert len(row_keys) == len(set(row_keys))

    get_settings.cache_clear()


def test_balance_analysis_refresh_queue_and_status_flow(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    queued_messages: list[dict[str, object]] = []

    monkeypatch.setattr(
        service_mod.materialize_balance_analysis_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post(
        "/ui/balance-analysis/refresh",
        params={"report_date": "2025-12-31"},
    )
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["status"] == "queued"
    assert refresh_payload["job_name"] == "balance_analysis_materialize"
    assert refresh_payload["trigger_mode"] == "async"
    assert refresh_payload["cache_key"] == "balance_analysis:materialize:formal"
    assert queued_messages[0]["run_id"] == refresh_payload["run_id"]
    assert queued_messages[0]["report_date"] == "2025-12-31"

    queued_status = client.get(
        "/ui/balance-analysis/refresh-status",
        params={"run_id": refresh_payload["run_id"]},
    )
    assert queued_status.status_code == 200
    assert queued_status.json()["status"] == "queued"

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=refresh_payload["run_id"],
                job_name="balance_analysis_materialize",
                status="completed",
                cache_key="balance_analysis:materialize:formal",
                lock="lock:duckdb:formal:balance-analysis:materialize",
                source_version="sv_balance_analysis_test",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": "2025-12-31",
            "queued_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    completed_status = client.get(
        "/ui/balance-analysis/refresh-status",
        params={"run_id": refresh_payload["run_id"]},
    )
    assert completed_status.status_code == 200
    assert completed_status.json()["status"] == "completed"
    assert completed_status.json()["trigger_mode"] == "terminal"

    get_settings.cache_clear()


def test_balance_analysis_refresh_returns_409_when_same_report_date_is_already_in_progress(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="balance-analysis-inflight",
                job_name="balance_analysis_materialize",
                status="queued",
                cache_key="balance_analysis:materialize:formal",
                lock="lock:duckdb:formal:balance-analysis:materialize",
                source_version="sv_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": "2025-12-31",
            "queued_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    send_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        service_mod.materialize_balance_analysis_facts,
        "send",
        lambda **kwargs: send_calls.append(kwargs),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post(
        "/ui/balance-analysis/refresh",
        params={"report_date": "2025-12-31"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Balance-analysis refresh already in progress for report_date=2025-12-31."
    assert send_calls == []
    get_settings.cache_clear()


def test_balance_analysis_refresh_returns_503_when_queue_dispatch_fails_without_sync_fallback(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    fallback_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        service_mod.materialize_balance_analysis_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("unexpected broker failure")),
    )
    monkeypatch.setattr(
        service_mod.materialize_balance_analysis_facts,
        "fn",
        lambda **kwargs: fallback_calls.append(kwargs),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post(
        "/ui/balance-analysis/refresh",
        params={"report_date": "2025-12-31"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Balance-analysis refresh queue dispatch failed."
    assert fallback_calls == []

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    latest = [record for record in records if record.get("job_name") == "balance_analysis_materialize"][-1]
    assert latest["status"] == "failed"
    assert latest["error_message"] == "Balance-analysis refresh queue dispatch failed."
    assert latest["report_date"] == "2025-12-31"
    get_settings.cache_clear()


def test_balance_analysis_refresh_reconciles_stale_inflight_run_and_requeues(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_snapshot_and_fx_tables(str(duckdb_path))

    stale_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="balance-analysis-stale",
                job_name="balance_analysis_materialize",
                status="queued",
                cache_key="balance_analysis:materialize:formal",
                lock="lock:duckdb:formal:balance-analysis:materialize",
                source_version="sv_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": "2025-12-31",
            "queued_at": stale_time,
        },
    )

    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    queued_messages: list[dict[str, object]] = []
    monkeypatch.setattr(
        service_mod.materialize_balance_analysis_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.post(
        "/ui/balance-analysis/refresh",
        params={"report_date": "2025-12-31"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert queued_messages[0]["report_date"] == "2025-12-31"

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    stale_records = [record for record in records if record.get("run_id") == "balance-analysis-stale"]
    assert stale_records[-1]["status"] == "failed"
    assert stale_records[-1]["error_message"] == "Marked stale balance-analysis refresh run as failed."
    get_settings.cache_clear()


def test_balance_analysis_refresh_status_returns_503_when_status_backend_fails(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    monkeypatch.setattr(
        service_mod.GovernanceRepository,
        "read_all",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("status backend unavailable")),
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get(
        "/ui/balance-analysis/refresh-status",
        params={"run_id": "run-any"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "status backend unavailable"
    get_settings.cache_clear()
