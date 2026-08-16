from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module
from tests.test_qdb_gl_monthly_analysis_core import _write_month_pair

import pytest

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_qdb_gl,
]

QDB_GL_MONTHLY_ANALYSIS_READ_HEADERS = {"X-User-Id": "qdb-gl-read-user", "X-User-Role": "viewer"}

_QDB_GL_MONTHLY_ANALYSIS_READ_CASES: tuple[tuple[str, dict[str, str]], ...] = (
    ("/ui/qdb-gl-monthly-analysis/dates", {}),
    ("/ui/qdb-gl-monthly-analysis/workbook", {"report_month": "202602"}),
    ("/ui/qdb-gl-monthly-analysis/workbook/export", {"report_month": "202602"}),
    ("/ui/qdb-gl-monthly-analysis/refresh-status", {"run_id": "qdb-gl-run"}),
    ("/ui/qdb-gl-monthly-analysis/scenario", {"report_month": "202602", "scenario_name": "threshold-stress"}),
    ("/ui/qdb-gl-monthly-analysis/manual-adjustments", {"report_month": "202602"}),
    ("/ui/qdb-gl-monthly-analysis/manual-adjustments/export", {"report_month": "202602"}),
)

def _qdb_scope_repo(tmp_path, monkeypatch) -> UserScopeRepository:
    sqlite_path = tmp_path / "qdb-gl-monthly-analysis-auth-scope.db"
    dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", "")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    return UserScopeRepository(dsn)

def _grant_qdb_read(tmp_path, monkeypatch) -> None:
    _qdb_scope_repo(tmp_path, monkeypatch).grant_scope(
        user_id="*",
        role=None,
        resource="qdb_gl_monthly_analysis",
        action="read",
    )

def _grant_qdb_refresh(tmp_path, monkeypatch) -> None:
    _qdb_scope_repo(tmp_path, monkeypatch).grant_scope(
        user_id="*",
        role=None,
        resource="qdb_gl_monthly_analysis",
        action="refresh",
    )

def _grant_qdb_adjustment_write(tmp_path, monkeypatch):
    _qdb_scope_repo(tmp_path, monkeypatch).grant_scope(
        user_id="*",
        role=None,
        resource="qdb_gl_monthly_analysis.adjustment",
        action="write",
    )

def test_qdb_gl_monthly_analysis_read_surfaces_require_explicit_read_scope(tmp_path, monkeypatch):
    route_module = load_module(
        "backend.app.api.routes.qdb_gl_monthly_analysis",
        "backend/app/api/routes/qdb_gl_monthly_analysis.py",
    )
    monkeypatch.setattr(
        route_module,
        "qdb_gl_monthly_analysis_dates_envelope",
        lambda **_kwargs: {"result_meta": {"result_kind": "qdb-gl-monthly-analysis.dates"}, "result": {}},
    )
    monkeypatch.setattr(
        route_module,
        "qdb_gl_monthly_analysis_workbook_envelope",
        lambda **_kwargs: {"result_meta": {"result_kind": "qdb-gl-monthly-analysis.workbook"}, "result": {}},
    )
    monkeypatch.setattr(route_module, "export_qdb_gl_monthly_analysis_workbook_xlsx", lambda **_kwargs: ("qdb.xlsx", b"x"))
    monkeypatch.setattr(route_module, "qdb_gl_monthly_analysis_refresh_status", lambda **_kwargs: {"run_id": "qdb-gl-run"})
    monkeypatch.setattr(
        route_module,
        "qdb_gl_monthly_analysis_scenario_envelope",
        lambda **_kwargs: {"result_meta": {"result_kind": "qdb-gl-monthly-analysis.scenario"}, "result": {}},
    )
    monkeypatch.setattr(
        route_module,
        "list_qdb_gl_monthly_analysis_manual_adjustments",
        lambda **_kwargs: {"adjustment_count": 0, "adjustments": []},
    )
    monkeypatch.setattr(
        route_module,
        "export_qdb_gl_monthly_analysis_manual_adjustments_csv",
        lambda **_kwargs: ("qdb-adjustments.csv", b""),
    )
    _qdb_scope_repo(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    for path, params in _QDB_GL_MONTHLY_ANALYSIS_READ_CASES:
        response = client.get(path, params=params or None, headers=QDB_GL_MONTHLY_ANALYSIS_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"

def test_qdb_gl_monthly_analysis_refresh_requires_explicit_refresh_scope(tmp_path, monkeypatch):
    route_module = load_module(
        "backend.app.api.routes.qdb_gl_monthly_analysis",
        "backend/app/api/routes/qdb_gl_monthly_analysis.py",
    )
    monkeypatch.setattr(
        route_module,
        "refresh_qdb_gl_monthly_analysis",
        lambda **_kwargs: {"status": "queued", "run_id": "qdb-gl-run"},
    )
    _qdb_scope_repo(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.post(
        "/ui/qdb-gl-monthly-analysis/refresh",
        params={"report_month": "202602"},
        headers=QDB_GL_MONTHLY_ANALYSIS_READ_HEADERS,
    )

    assert response.status_code == 403

def test_api_exposes_dates_and_workbook_payload(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    _grant_qdb_read(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    dates_response = client.get("/ui/qdb-gl-monthly-analysis/dates")
    assert dates_response.status_code == 200
    dates_payload = dates_response.json()
    assert dates_payload["result_meta"]["basis"] == "analytical"
    assert dates_payload["result"]["report_months"] == ["202602"]

    workbook_response = client.get(
        "/ui/qdb-gl-monthly-analysis/workbook",
        params={"report_month": "202602"},
    )
    assert workbook_response.status_code == 200
    workbook_payload = workbook_response.json()
    assert workbook_payload["result_meta"]["basis"] == "analytical"
    assert workbook_payload["result_meta"]["result_kind"] == "qdb-gl-monthly-analysis.workbook"
    assert workbook_payload["result_meta"]["tables_used"] == [
        "qdb_gl_average_balance_workbook",
        "qdb_gl_ledger_reconciliation_workbook",
    ]
    assert workbook_payload["result_meta"]["evidence_rows"] == 2
    assert workbook_payload["result_meta"]["requested_report_date"] == "202602"
    assert workbook_payload["result_meta"]["resolved_report_date"] == "202602"
    assert workbook_payload["result_meta"]["filters_applied"]["comparison_months"]["prior_month"] == {
        "report_month": "202601",
        "status": "missing",
    }
    assert workbook_payload["result"]["report_month"] == "202602"
    assert [sheet["title"] for sheet in workbook_payload["result"]["sheets"]] == [
        "经营概览",
        "财务指标落地状态",
        "3位科目总览",
        "资产结构",
        "负债结构",
        "贷款行业",
        "存款行业_活期",
        "存款行业_定期",
        "行业存贷差",
        "11位偏离TOP",
        "异动预警",
        "外币分析",
        "分部基础规模",
        "公司规模",
        "零售规模",
        "金融市场规模",
        "收益率分析（总账可复算）",
        "存款利息拆分",
        "母公司营收分项",
    ]

    get_settings.cache_clear()

def test_api_workbook_payload_includes_segment_scale_compare_when_history_exists(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202601")
    _write_month_pair(source_dir, "202602")

    _grant_qdb_read(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/ui/qdb-gl-monthly-analysis/workbook",
        params={"report_month": "202602"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "prior_month:202601" in payload["result_meta"]["source_version"]
    assert payload["result_meta"]["evidence_rows"] == 4
    assert payload["result_meta"]["tables_used"] == [
        "qdb_gl_average_balance_workbook",
        "qdb_gl_ledger_reconciliation_workbook",
    ]
    assert payload["result_meta"]["filters_applied"]["comparison_months"]["prior_month"] == {
        "report_month": "202601",
        "status": "loaded",
    }
    assert "segment_scale_compare" in [sheet["key"] for sheet in payload["result"]["sheets"]]
    segment_sheet = next(
        sheet for sheet in payload["result"]["sheets"] if sheet["key"] == "segment_scale_compare"
    )
    assert segment_sheet["title"] == "分部规模同比环比"
    assert any(row["口径"] == "时点环比" for row in segment_sheet["rows"])
    assert "financial_market_scale_compare" in [sheet["key"] for sheet in payload["result"]["sheets"]]
    market_sheet = next(
        sheet for sheet in payload["result"]["sheets"] if sheet["key"] == "financial_market_scale_compare"
    )
    assert market_sheet["title"] == "金融市场规模同比环比"
    assert any(row["指标"] == "同业负债" and row["口径"] == "月日均环比" for row in market_sheet["rows"])
    assert "company_scale_compare" in [sheet["key"] for sheet in payload["result"]["sheets"]]
    company_sheet = next(
        sheet for sheet in payload["result"]["sheets"] if sheet["key"] == "company_scale_compare"
    )
    assert company_sheet["title"] == "公司规模同比环比"
    assert any(row["指标"] == "公司贷款合计" and row["口径"] == "时点环比" for row in company_sheet["rows"])
    assert "retail_scale_compare" in [sheet["key"] for sheet in payload["result"]["sheets"]]
    retail_sheet = next(
        sheet for sheet in payload["result"]["sheets"] if sheet["key"] == "retail_scale_compare"
    )
    assert retail_sheet["title"] == "零售规模同比环比"
    assert any(row["指标"] == "零售存款合计" and row["口径"] == "时点环比" for row in retail_sheet["rows"])
    assert "income_rate_analysis" in [sheet["key"] for sheet in payload["result"]["sheets"]]
    income_sheet = next(
        sheet for sheet in payload["result"]["sheets"] if sheet["key"] == "income_rate_analysis"
    )
    assert income_sheet["title"] == "收益率分析（总账可复算）"
    assert any(row["指标"] == "公司贷款利息收入" for row in income_sheet["rows"])

    get_settings.cache_clear()

def test_api_returns_404_for_missing_report_month(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    _grant_qdb_read(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    get_settings.cache_clear()

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get(
        "/ui/qdb-gl-monthly-analysis/workbook",
        params={"report_month": "202603"},
    )

    assert response.status_code == 404
    assert "202603" in response.json()["detail"]
    get_settings.cache_clear()

def test_api_exposes_refresh_and_scenario_for_monthly_analysis(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    _grant_qdb_read(tmp_path, monkeypatch)
    _grant_qdb_refresh(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post(
        "/ui/qdb-gl-monthly-analysis/refresh",
        params={"report_month": "202602"},
    )
    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["job_name"] == "qdb_gl_monthly_analysis"
    assert refresh_payload["source_version"].startswith("sv_qdb_gl_")
    assert refresh_payload["source_version"] != "202602"
    assert refresh_payload["report_date"] == "202602"
    assert refresh_payload["sheet_count"] > 0
    assert refresh_payload["tables_used"] == [
        "qdb_gl_average_balance_workbook",
        "qdb_gl_ledger_reconciliation_workbook",
    ]
    assert refresh_payload["evidence_rows"] == 2
    assert refresh_payload["comparison_months"]["prior_month"] == {
        "report_month": "202601",
        "status": "missing",
    }

    status_response = client.get(
        "/ui/qdb-gl-monthly-analysis/refresh-status",
        params={"run_id": refresh_payload["run_id"]},
    )
    assert status_response.status_code == 200
    assert status_response.json()["run_id"] == refresh_payload["run_id"]
    assert status_response.json()["source_version"] == refresh_payload["source_version"]
    assert status_response.json()["report_date"] == "202602"

    scenario_response = client.get(
        "/ui/qdb-gl-monthly-analysis/scenario",
        params={
            "report_month": "202602",
            "scenario_name": "threshold-stress",
            "deviation_warn": "6",
            "deviation_alert": "12",
        },
    )
    assert scenario_response.status_code == 200
    scenario_payload = scenario_response.json()
    assert scenario_payload["result_meta"]["basis"] == "analytical"
    assert scenario_payload["result"]["scenario_name"] == "threshold-stress"
    assert scenario_payload["result"]["applied_overrides"] == {
        "DEVIATION_WARN": 6,
        "DEVIATION_ALERT": 12,
    }
    get_settings.cache_clear()

def test_api_refresh_reuses_run_for_same_idempotency_key(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_鎬昏处瀵硅处-鏃ュ潎"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    _grant_qdb_refresh(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    headers = {"Idempotency-Key": "qdb-gl-refresh-202602"}

    first_response = client.post(
        "/ui/qdb-gl-monthly-analysis/refresh",
        params={"report_month": "202602"},
        headers=headers,
    )
    second_response = client.post(
        "/ui/qdb-gl-monthly-analysis/refresh",
        params={"report_month": "202602"},
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_payload = first_response.json()
    second_payload = second_response.json()
    assert second_payload["run_id"] == first_payload["run_id"]
    assert second_payload["idempotency_key"] == "qdb-gl-refresh-202602"
    assert second_payload["idempotency_replay"] is True

    records = [
        record
        for record in GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
        if record.get("job_name") == "qdb_gl_monthly_analysis"
        and record.get("run_id") == first_payload["run_id"]
    ]
    assert len(records) == 1
    get_settings.cache_clear()

def test_api_refresh_returns_failed_payload_when_requested_month_rebuild_fails(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_鎬昏处瀵硅处-鏃ゅ潎"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _avg_path, ledger_path = _write_month_pair(source_dir, "202602")
    workbook = load_workbook(ledger_path)
    try:
        workbook.active["A6"] = "invalid-header"
        workbook.save(ledger_path)
    finally:
        workbook.close()

    _grant_qdb_read(tmp_path, monkeypatch)
    _grant_qdb_refresh(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    refresh_response = client.post(
        "/ui/qdb-gl-monthly-analysis/refresh",
        params={"report_month": "202602"},
    )

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload["status"] == "failed"
    assert refresh_payload["failure_category"] == "qdb_gl_monthly_analysis_build"
    assert "202602" in refresh_payload["error_message"]

    status_response = client.get(
        "/ui/qdb-gl-monthly-analysis/refresh-status",
        params={"run_id": refresh_payload["run_id"]},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "failed"
    assert status_response.json()["error_message"] == refresh_payload["error_message"]

    get_settings.cache_clear()

def test_api_refresh_returns_404_when_requested_month_is_missing(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_鎬昏处瀵硅处-鏃ゅ潎"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    _grant_qdb_refresh(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    refresh_response = client.post(
        "/ui/qdb-gl-monthly-analysis/refresh",
        params={"report_month": "202601"},
    )

    assert refresh_response.status_code == 404
    assert "202601" in refresh_response.text
    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    assert [
        record
        for record in records
        if record.get("job_name") == "qdb_gl_monthly_analysis"
        and record.get("report_date") == "202601"
    ] == []
    get_settings.cache_clear()

def test_api_exposes_branch_specific_manual_adjustment_endpoints(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    _grant_qdb_read(tmp_path, monkeypatch)
    _grant_qdb_adjustment_write(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    created = client.post(
        "/ui/qdb-gl-monthly-analysis/manual-adjustments",
        json={
            "report_month": "202602",
            "adjustment_class": "mapping_adjustment",
            "target": {"account_code": "12301", "field": "industry_name"},
            "operator": "OVERRIDE",
            "value": "农业",
            "approval_status": "approved",
        },
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["stream"] == "monthly_operating_analysis_adjustments"

    listed = client.get(
        "/ui/qdb-gl-monthly-analysis/manual-adjustments",
        params={"report_month": "202602"},
    )
    assert listed.status_code == 200
    assert listed.json()["adjustment_count"] == 1

    exported = client.get(
        "/ui/qdb-gl-monthly-analysis/manual-adjustments/export",
        params={"report_month": "202602"},
    )
    assert exported.status_code == 200
    assert exported.headers["content-disposition"] == (
        'attachment; filename="monthly-operating-analysis-audit-202602.csv"'
    )
    get_settings.cache_clear()

def test_api_rejects_invalid_manual_adjustment_payload(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    _grant_qdb_read(tmp_path, monkeypatch)
    _grant_qdb_adjustment_write(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.post(
        "/ui/qdb-gl-monthly-analysis/manual-adjustments",
        json={
            "report_month": "2026-02",
            "adjustment_class": "mapping_adjustment",
            "target": {},
            "operator": "PATCH",
            "value": "",
            "approval_status": "approved",
            "unexpected": "field",
        },
    )

    assert response.status_code == 422

    listed = client.get(
        "/ui/qdb-gl-monthly-analysis/manual-adjustments",
        params={"report_month": "202602"},
    )
    assert listed.status_code == 200
    assert listed.json()["adjustment_count"] == 0
    get_settings.cache_clear()

def test_api_scenario_returns_rebuilt_workbook_payload(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    _grant_qdb_read(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    scenario_response = client.get(
        "/ui/qdb-gl-monthly-analysis/scenario",
        params={
            "report_month": "202602",
            "scenario_name": "threshold-stress",
            "deviation_warn": "80",
            "deviation_alert": "90",
            "deviation_critical": "100",
        },
    )

    assert scenario_response.status_code == 200
    scenario_payload = scenario_response.json()
    assert scenario_payload["result"]["scenario_name"] == "threshold-stress"
    assert [sheet["key"] for sheet in scenario_payload["result"]["sheets"]] == [
        "overview",
        "financial_indicator_status",
        "summary_3d",
        "asset_structure",
        "liability_structure",
        "loan_industry",
        "deposit_demand_industry",
        "deposit_term_industry",
        "industry_gap",
        "top_11d",
        "alerts",
        "foreign_currency",
        "segment_base_scale",
        "company_scale",
        "retail_scale",
        "financial_market_scale",
        "income_rate_analysis",
        "deposit_interest_split",
        "parent_company_revenue_components",
    ]
    alerts_sheet = next(
        sheet for sheet in scenario_payload["result"]["sheets"] if sheet["key"] == "alerts"
    )
    assert len(alerts_sheet["rows"]) == 1

    get_settings.cache_clear()

def test_api_workbook_rebuild_applies_approved_monthly_analysis_adjustments(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    _grant_qdb_read(tmp_path, monkeypatch)
    _grant_qdb_adjustment_write(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    created = client.post(
        "/ui/qdb-gl-monthly-analysis/manual-adjustments",
        json={
            "report_month": "202602",
            "adjustment_class": "analysis_adjustment",
            "target": {
                "section_key": "alerts",
                "row_key": "14001000001",
                "metric_key": "alert_level",
            },
            "operator": "OVERRIDE",
            "value": "manual_override",
            "approval_status": "approved",
        },
    )
    assert created.status_code == 200

    workbook = client.get(
        "/ui/qdb-gl-monthly-analysis/workbook",
        params={"report_month": "202602"},
    )
    assert workbook.status_code == 200
    alerts_sheet = next(
        sheet for sheet in workbook.json()["result"]["sheets"] if sheet["key"] == "alerts"
    )
    code_key = alerts_sheet["columns"][0]
    level_key = alerts_sheet["columns"][2]
    target_row = next(row for row in alerts_sheet["rows"] if str(row[code_key]) == "14001000001")
    assert target_row[level_key] == "manual_override"

    get_settings.cache_clear()

def test_api_workbook_rebuild_applies_approved_mapping_adjustments(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    _grant_qdb_read(tmp_path, monkeypatch)
    _grant_qdb_adjustment_write(tmp_path, monkeypatch)
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    created = client.post(
        "/ui/qdb-gl-monthly-analysis/manual-adjustments",
        json={
            "report_month": "202602",
            "adjustment_class": "mapping_adjustment",
            "target": {
                "account_code": "14001000001",
                "field": "account_name",
            },
            "operator": "OVERRIDE",
            "value": "买入返售-人工修正",
            "approval_status": "approved",
        },
    )
    assert created.status_code == 200

    workbook = client.get(
        "/ui/qdb-gl-monthly-analysis/workbook",
        params={"report_month": "202602"},
    )
    assert workbook.status_code == 200
    alerts_sheet = next(
        sheet for sheet in workbook.json()["result"]["sheets"] if sheet["key"] == "alerts"
    )
    code_key = alerts_sheet["columns"][0]
    name_key = alerts_sheet["columns"][1]
    target_row = next(row for row in alerts_sheet["rows"] if str(row[code_key]) == "14001000001")
    assert target_row[name_key] == "买入返售-人工修正"

    get_settings.cache_clear()
