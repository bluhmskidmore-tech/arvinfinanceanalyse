from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_qdb_gl_monthly_analysis_core import _write_month_pair


def test_api_exposes_dates_and_workbook_payload(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

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
    assert workbook_payload["result"]["report_month"] == "202602"
    assert [sheet["title"] for sheet in workbook_payload["result"]["sheets"]] == [
        "经营概览",
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
    ]

    get_settings.cache_clear()


def test_api_returns_404_for_missing_report_month(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

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

    status_response = client.get(
        "/ui/qdb-gl-monthly-analysis/refresh-status",
        params={"run_id": refresh_payload["run_id"]},
    )
    assert status_response.status_code == 200
    assert status_response.json()["run_id"] == refresh_payload["run_id"]

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


def test_api_exposes_branch_specific_manual_adjustment_endpoints(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
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


def test_api_scenario_returns_rebuilt_workbook_payload(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_鎬昏处瀵硅处-鏃ュ潎"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

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
    ]
    alerts_sheet = next(
        sheet for sheet in scenario_payload["result"]["sheets"] if sheet["key"] == "alerts"
    )
    assert len(alerts_sheet["rows"]) == 1

    get_settings.cache_clear()


def test_api_workbook_rebuild_applies_approved_monthly_analysis_adjustments(tmp_path, monkeypatch):
    source_dir = tmp_path / "data_input" / "pnl_鎬昏处瀵硅处-鏃ュ潎"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

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
