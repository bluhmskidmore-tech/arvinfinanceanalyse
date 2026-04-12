from __future__ import annotations

from tests.helpers import load_module
from tests.test_qdb_gl_monthly_analysis_core import _write_month_pair


def test_service_discovers_available_report_months(tmp_path):
    module = load_module(
        "backend.app.services.qdb_gl_monthly_analysis_service",
        "backend/app/services/qdb_gl_monthly_analysis_service.py",
    )
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    envelope = module.qdb_gl_monthly_analysis_dates_envelope(source_dir=str(source_dir))

    assert envelope["result_meta"]["basis"] == "analytical"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result"]["report_months"] == ["202602"]


def test_service_blocks_generation_when_input_contract_validation_fails(tmp_path):
    module = load_module(
        "backend.app.services.qdb_gl_monthly_analysis_service",
        "backend/app/services/qdb_gl_monthly_analysis_service.py",
    )
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    source_dir.mkdir(parents=True)
    avg_path, _ledger_path = _write_month_pair(source_dir, "202602")
    avg_path.rename(source_dir / "日均错误202602.xlsx")

    try:
        module.qdb_gl_monthly_analysis_workbook_envelope(
            source_dir=str(source_dir),
            report_month="202602",
        )
    except ValueError as exc:
        assert "202602" in str(exc)
    else:
        raise AssertionError("Expected month-pair generation to fail when the canonical source file is missing.")


def test_service_supports_sync_refresh_and_status_flow(tmp_path):
    module = load_module(
        "backend.app.services.qdb_gl_monthly_analysis_service",
        "backend/app/services/qdb_gl_monthly_analysis_service.py",
    )
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    refresh_payload = module.refresh_qdb_gl_monthly_analysis(
        source_dir=str(source_dir),
        governance_dir=str(governance_dir),
        report_month="202602",
    )

    assert refresh_payload["status"] in {"queued", "completed"}
    assert refresh_payload["job_name"] == "qdb_gl_monthly_analysis"
    status_payload = module.qdb_gl_monthly_analysis_refresh_status(
        governance_dir=str(governance_dir),
        run_id=refresh_payload["run_id"],
    )
    assert status_payload["run_id"] == refresh_payload["run_id"]


def test_service_scenario_envelope_uses_analytical_basis_and_override_summary(tmp_path):
    module = load_module(
        "backend.app.services.qdb_gl_monthly_analysis_service",
        "backend/app/services/qdb_gl_monthly_analysis_service.py",
    )
    source_dir = tmp_path / "data_input" / "pnl_总账对账-日均"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    envelope = module.qdb_gl_monthly_analysis_scenario_envelope(
        source_dir=str(source_dir),
        report_month="202602",
        scenario_name="threshold-stress",
        threshold_overrides={
            "DEVIATION_WARN": 6,
            "DEVIATION_ALERT": 12,
        },
    )

    assert envelope["result_meta"]["basis"] == "analytical"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["result_kind"] == "qdb-gl-monthly-analysis.scenario"
    assert envelope["result"]["scenario_name"] == "threshold-stress"
    assert envelope["result"]["applied_overrides"] == {
        "DEVIATION_WARN": 6,
        "DEVIATION_ALERT": 12,
    }


def test_service_workbook_envelope_applies_approved_analysis_adjustments(tmp_path):
    module = load_module(
        "backend.app.services.qdb_gl_monthly_analysis_service",
        "backend/app/services/qdb_gl_monthly_analysis_service.py",
    )
    source_dir = tmp_path / "data_input" / "pnl_鎬昏处瀵硅处-鏃ュ潎"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    module.create_qdb_gl_monthly_analysis_manual_adjustment(
        governance_dir=str(governance_dir),
        payload={
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

    envelope = module.qdb_gl_monthly_analysis_workbook_envelope(
        source_dir=str(source_dir),
        governance_dir=str(governance_dir),
        report_month="202602",
    )

    alerts_sheet = next(
        sheet for sheet in envelope["result"]["sheets"] if sheet["key"] == "alerts"
    )
    code_key = alerts_sheet["columns"][0]
    level_key = alerts_sheet["columns"][2]
    target_row = next(row for row in alerts_sheet["rows"] if str(row[code_key]) == "14001000001")

    assert target_row[level_key] == "manual_override"


def test_service_scenario_envelope_returns_rebuilt_workbook_payload_with_override_effects(tmp_path):
    module = load_module(
        "backend.app.services.qdb_gl_monthly_analysis_service",
        "backend/app/services/qdb_gl_monthly_analysis_service.py",
    )
    source_dir = tmp_path / "data_input" / "pnl_鎬昏处瀵硅处-鏃ュ潎"
    governance_dir = tmp_path / "governance"
    source_dir.mkdir(parents=True)
    _write_month_pair(source_dir, "202602")

    baseline = module.qdb_gl_monthly_analysis_workbook_envelope(
        source_dir=str(source_dir),
        governance_dir=str(governance_dir),
        report_month="202602",
    )
    scenario = module.qdb_gl_monthly_analysis_scenario_envelope(
        source_dir=str(source_dir),
        governance_dir=str(governance_dir),
        report_month="202602",
        scenario_name="threshold-stress",
        threshold_overrides={
            "DEVIATION_WARN": 80,
            "DEVIATION_ALERT": 90,
            "DEVIATION_CRITICAL": 100,
        },
    )

    baseline_alerts = next(
        sheet for sheet in baseline["result"]["sheets"] if sheet["key"] == "alerts"
    )["rows"]
    scenario_alerts = next(
        sheet for sheet in scenario["result"]["sheets"] if sheet["key"] == "alerts"
    )["rows"]

    assert scenario["result"]["scenario_name"] == "threshold-stress"
    assert scenario["result"]["report_month"] == "202602"
    assert [sheet["key"] for sheet in scenario["result"]["sheets"]] == [
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
    assert scenario["result"]["applied_overrides"] == {
        "DEVIATION_WARN": 80,
        "DEVIATION_ALERT": 90,
        "DEVIATION_CRITICAL": 100,
    }
    assert len(baseline_alerts) > len(scenario_alerts)


def test_service_supports_branch_specific_manual_adjustment_audit_flow(tmp_path):
    module = load_module(
        "backend.app.services.qdb_gl_monthly_analysis_service",
        "backend/app/services/qdb_gl_monthly_analysis_service.py",
    )
    governance_dir = tmp_path / "governance"

    created = module.create_qdb_gl_monthly_analysis_manual_adjustment(
        governance_dir=str(governance_dir),
        payload={
            "report_month": "202602",
            "adjustment_class": "mapping_adjustment",
            "target": {"account_code": "12301", "field": "industry_name"},
            "operator": "OVERRIDE",
            "value": "农业",
            "approval_status": "approved",
        },
    )

    assert created["stream"] == "monthly_operating_analysis_adjustments"
    assert created["adjustment_class"] == "mapping_adjustment"

    listed = module.list_qdb_gl_monthly_analysis_manual_adjustments(
        governance_dir=str(governance_dir),
        report_month="202602",
    )
    assert listed["adjustment_count"] == 1
    assert listed["adjustments"][0]["adjustment_id"] == created["adjustment_id"]

    edited = module.update_qdb_gl_monthly_analysis_manual_adjustment(
        governance_dir=str(governance_dir),
        adjustment_id=created["adjustment_id"],
        payload={
            "report_month": "202602",
            "adjustment_class": "analysis_adjustment",
            "target": {"section_key": "alerts", "row_key": "14001000001", "metric_key": "alert_level"},
            "operator": "OVERRIDE",
            "value": "中度",
            "approval_status": "approved",
        },
    )
    assert edited["adjustment_class"] == "analysis_adjustment"

    revoked = module.revoke_qdb_gl_monthly_analysis_manual_adjustment(
        governance_dir=str(governance_dir),
        adjustment_id=created["adjustment_id"],
    )
    assert revoked["approval_status"] == "rejected"

    restored = module.restore_qdb_gl_monthly_analysis_manual_adjustment(
        governance_dir=str(governance_dir),
        adjustment_id=created["adjustment_id"],
    )
    assert restored["approval_status"] == "approved"

    filename, content = module.export_qdb_gl_monthly_analysis_manual_adjustments_csv(
        governance_dir=str(governance_dir),
        report_month="202602",
    )
    assert filename == "monthly-operating-analysis-audit-202602.csv"
    assert "analysis_adjustment" in content
