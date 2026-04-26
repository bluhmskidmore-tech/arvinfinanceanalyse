from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path
from decimal import Decimal

import duckdb
from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    SOURCE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheBuildRunRecord
from tests.helpers import ROOT, load_module


def test_fastapi_application_registers_pnl_routes():
    from backend.app.main import app

    paths = {route.path for route in app.routes}

    assert "/api/pnl/dates" in paths
    assert "/api/pnl/data" in paths
    assert "/api/pnl/bridge" in paths
    assert "/api/pnl/overview" in paths
    assert "/api/data/refresh_pnl" in paths
    assert "/api/data/import_status/pnl" in paths


def test_pnl_service_uses_shared_formal_lineage_and_result_meta_helpers():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "pnl_service.py"
    src = path.read_text(encoding="utf-8")

    assert "resolve_formal_manifest_lineage" in src
    assert "build_formal_result_envelope_from_lineage" in src
    assert "def _resolve_pnl_manifest_lineage" not in src


def test_pnl_service_keeps_intentional_local_cache_version_wrapper():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "pnl_service.py"
    src = path.read_text(encoding="utf-8")

    assert "def _build_pnl_formal_result_envelope_from_lineage" in src
    assert "use_lineage_cache_version=False" in src
    assert "default_cache_version=PNL_CACHE_VERSION" in src


def test_pnl_refresh_serializes_decimal_rows_before_queue_dispatch(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    source_service = load_module(
        "backend.app.services.pnl_source_service",
        "backend/app/services/pnl_source_service.py",
    )

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: source_service.PnlRefreshInput(
            report_date="2026-02-28",
            is_month_end=True,
            fi_rows=[
                {
                    "report_date": "2026-02-28",
                    "instrument_code": "240001.IB",
                    "portfolio_name": "FI Desk",
                    "cost_center": "CC100",
                    "invest_type_raw": "交易性金融资产",
                    "interest_income_514": Decimal("12.34"),
                    "fair_value_change_516": Decimal("-5.67"),
                    "capital_gain_517": Decimal("1.00"),
                    "manual_adjustment": Decimal("0"),
                    "currency_basis": "CNY",
                    "source_version": "sv_decimal",
                    "rule_version": "rv_decimal",
                    "ingest_batch_id": "ib_decimal",
                    "trace_id": "trace-decimal",
                }
            ],
            nonstd_rows_by_type={
                "516": [
                    {
                        "voucher_date": "2026-02-28",
                        "account_code": "51601010004",
                        "asset_code": "240001.IB",
                        "portfolio_name": "FI Desk",
                        "cost_center": "CC100",
                        "dc_flag": "credit",
                        "event_type": "mtm",
                        "raw_amount": Decimal("8.90"),
                        "source_file": "nonstd-516.xlsx",
                        "source_version": "sv_decimal_nonstd",
                        "rule_version": "rv_decimal",
                        "ingest_batch_id": "ib_decimal",
                        "trace_id": "trace-decimal-nonstd",
                    }
                ]
            },
        ),
    )
    dispatched: list[dict[str, object]] = []

    def fake_send(**kwargs):
        json.dumps(kwargs)
        dispatched.append(kwargs)

    monkeypatch.setattr(pnl_service.materialize_pnl_facts, "send", fake_send)

    payload = pnl_service.refresh_pnl(get_settings())

    assert payload["status"] == "queued"
    assert dispatched[0]["fi_rows"][0]["interest_income_514"] == "12.34"
    assert dispatched[0]["nonstd_rows_by_type"]["516"][0]["raw_amount"] == "8.90"
    get_settings.cache_clear()


def test_pnl_overview_service_consumes_pnl_vs_ledger_reconciliation_check():
    service_module = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    check = service_module._pnl_overview_reconciliation_check(
        {
            "interest_income_514": Decimal("10"),
            "fair_value_change_516": Decimal("-2"),
            "capital_gain_517": Decimal("3"),
            "manual_adjustment": Decimal("1"),
            "total_pnl": Decimal("12"),
        }
    )

    assert check == {
        "pnl_total": 12.0,
        "ledger_pnl_total": 12.0,
        "diff": 0.0,
        "breached": False,
    }


def test_pnl_overview_reconciliation_check_flags_inconsistent_total():
    service_module = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    check = service_module._pnl_overview_reconciliation_check(
        {
            "interest_income_514": Decimal("10"),
            "fair_value_change_516": Decimal("-2"),
            "capital_gain_517": Decimal("3"),
            "manual_adjustment": Decimal("1"),
            "total_pnl": Decimal("11"),
        }
    )

    assert check["breached"] is True
    assert check["diff"] == -1.0


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


def test_pnl_data_returns_shared_date_with_two_explicit_lists_and_report_date_build_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(governance_dir, source_version="sv_override", vendor_version="vv_override", rule_version="rv_override")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/data", params={"date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["result_kind"] == "pnl.data"
    assert payload["result_meta"]["source_version"] == "fi-shared-v1__nonstd-shared-v1"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_phase2_materialize_v1"
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


def test_pnl_overview_returns_backend_owned_aggregation_and_report_date_build_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(governance_dir, source_version="sv_overview", vendor_version="vv_overview", rule_version="rv_overview")

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["result_kind"] == "pnl.overview"
    assert payload["result_meta"]["source_version"] == "fi-shared-v1__nonstd-shared-v1"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_phase2_materialize_v1"
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


def test_pnl_overview_keeps_fixed_cache_version_even_if_manifest_contains_cache_version(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_overview_cache",
        vendor_version="vv_overview_cache",
        rule_version="rv_overview_cache",
        cache_version="cv_manifest_override_should_not_apply",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "fi-shared-v1__nonstd-shared-v1"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_phase2_materialize_v1"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v1"
    get_settings.cache_clear()


def test_pnl_data_prefers_report_date_specific_build_lineage_over_latest_manifest(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_manifest_latest",
        vendor_version="vv_manifest_latest",
        rule_version="rv_manifest_latest",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="run-2025-12",
        status="completed",
        source_version="sv_build_2025_12",
        vendor_version="vv_build_2025_12",
        rule_version="rv_build_2025_12",
        report_date="2025-12-31",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="run-2026-01",
        status="completed",
        source_version="sv_build_2026_01",
        vendor_version="vv_build_2026_01",
        rule_version="rv_build_2026_01",
        report_date="2026-01-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/data", params={"date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_build_2025_12"
    assert payload["result_meta"]["vendor_version"] == "vv_build_2025_12"
    assert payload["result_meta"]["rule_version"] == "rv_build_2025_12"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v1"
    get_settings.cache_clear()


def test_pnl_data_uses_report_date_specific_build_lineage_without_manifest(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_pnl_build_run(
        governance_dir,
        run_id="run-2025-12",
        status="completed",
        source_version="sv_build_2025_12",
        vendor_version="vv_build_2025_12",
        rule_version="rv_build_2025_12",
        report_date="2025-12-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/data", params={"date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_build_2025_12"
    assert payload["result_meta"]["vendor_version"] == "vv_build_2025_12"
    assert payload["result_meta"]["rule_version"] == "rv_build_2025_12"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v1"
    get_settings.cache_clear()


def test_pnl_overview_prefers_report_date_specific_build_lineage_over_latest_manifest(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_manifest_latest",
        vendor_version="vv_manifest_latest",
        rule_version="rv_manifest_latest",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="run-2025-12",
        status="completed",
        source_version="sv_build_2025_12",
        vendor_version="vv_build_2025_12",
        rule_version="rv_build_2025_12",
        report_date="2025-12-31",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="run-2026-01",
        status="completed",
        source_version="sv_build_2026_01",
        vendor_version="vv_build_2026_01",
        rule_version="rv_build_2026_01",
        report_date="2026-01-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_build_2025_12"
    assert payload["result_meta"]["vendor_version"] == "vv_build_2025_12"
    assert payload["result_meta"]["rule_version"] == "rv_build_2025_12"
    assert payload["result_meta"]["cache_version"] == "cv_pnl_formal__rv_pnl_phase2_materialize_v1"
    get_settings.cache_clear()


def test_pnl_bridge_returns_rows_and_phase3_warning_when_balance_rows_are_unavailable(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge",
        vendor_version="vv_bridge",
        rule_version="rv_bridge",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["result_kind"] == "pnl.bridge"
    assert payload["result_meta"]["source_version"] == "fi-shared-v1__nonstd-shared-v1"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_phase2_materialize_v1"
    assert "start_pack" not in payload["result_meta"]["cache_version"]
    assert payload["result_meta"]["cache_version"] == (
        "cv_pnl_bridge_formal_v1__cv_pnl_formal__rv_pnl_phase2_materialize_v1__"
        "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1__"
        "cv_yield_curve_formal__rv_yield_curve_formal_materialize_v1"
    )
    assert payload["result"]["report_date"] == "2025-12-31"
    assert len(payload["result"]["rows"]) == 1
    assert payload["result"]["rows"][0]["instrument_code"] == "240001.IB"
    assert payload["result"]["rows"][0]["carry"]["raw"] == 12.5
    assert payload["result"]["rows"][0]["carry"]["unit"] == "yuan"
    assert payload["result"]["rows"][0]["beginning_dirty_mv"]["raw"] == 0.0
    assert payload["result"]["rows"][0]["beginning_dirty_mv"]["sign_aware"] is False
    assert payload["result"]["rows"][0]["ending_dirty_mv"]["raw"] == 0.0
    assert payload["result"]["rows"][0]["ending_dirty_mv"]["sign_aware"] is False
    assert payload["result"]["rows"][0]["current_balance_found"] is False
    assert payload["result"]["rows"][0]["prior_balance_found"] is False
    assert payload["result"]["rows"][0]["balance_diagnostics"] == [
        "Missing current balance row; ending_dirty_mv defaults to 0.",
        "Missing prior balance row; beginning_dirty_mv defaults to 0.",
    ]
    assert payload["result"]["warnings"][0] == (
        "Phase 3 partial delivery: roll_down / treasury_curve / credit_spread use governed curves when available."
    )
    assert "Current balance rows unavailable" in payload["result"]["warnings"][1]
    assert "No prior balance report date found" in payload["result"]["warnings"][2]
    summary = payload["result"]["summary"]
    assert summary["row_count"] == 1
    assert summary["total_carry"]["raw"] == 12.5
    assert summary["total_roll_down"]["raw"] == 0.0
    assert summary["total_treasury_curve"]["raw"] == 0.0
    assert summary["total_credit_spread"]["raw"] == 0.0
    assert summary["total_fx_translation"]["raw"] == 0.0
    assert summary["total_realized_trading"]["raw"] == 1.75
    assert summary["total_unrealized_fv"]["raw"] == -3.25
    assert summary["total_manual_adjustment"]["raw"] == 0.5
    assert summary["total_explained_pnl"]["raw"] == 11.5
    assert summary["total_actual_pnl"]["raw"] == 11.5
    assert summary["total_residual"]["raw"] == 0.0
    get_settings.cache_clear()


def test_pnl_bridge_prefers_report_date_specific_pnl_build_lineage_over_latest_manifest(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_manifest_latest",
        vendor_version="vv_pnl_manifest_latest",
        rule_version="rv_pnl_manifest_latest",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="pnl-build-2025-12",
        status="completed",
        source_version="sv_pnl_build_2025_12",
        vendor_version="vv_pnl_build_2025_12",
        rule_version="rv_pnl_build_2025_12",
        report_date="2025-12-31",
    )
    _append_pnl_build_run(
        governance_dir,
        run_id="pnl-build-2026-01",
        status="completed",
        source_version="sv_pnl_build_2026_01",
        vendor_version="vv_pnl_build_2026_01",
        rule_version="rv_pnl_build_2026_01",
        report_date="2026-01-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_pnl_build_2025_12"
    assert payload["result_meta"]["vendor_version"] == "vv_pnl_build_2025_12"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_build_2025_12"
    get_settings.cache_clear()


def test_pnl_bridge_uses_report_date_specific_pnl_build_lineage_without_manifest(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_pnl_build_run(
        governance_dir,
        run_id="pnl-build-2025-12",
        status="completed",
        source_version="sv_pnl_build_2025_12",
        vendor_version="vv_pnl_build_2025_12",
        rule_version="rv_pnl_build_2025_12",
        report_date="2025-12-31",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "sv_pnl_build_2025_12"
    assert payload["result_meta"]["vendor_version"] == "vv_pnl_build_2025_12"
    assert payload["result_meta"]["rule_version"] == "rv_pnl_build_2025_12"
    get_settings.cache_clear()


def test_pnl_bridge_uses_current_and_latest_available_bond_prior_balance_rows(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge_balance",
        vendor_version="vv_bridge_balance",
        rule_version="rv_bridge_balance",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=True,
        include_unusable_zqtz_intermediate_prior=True,
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == "fi-shared-v1__nonstd-shared-v1__sv-z-current__sv-z-prior"
    assert payload["result_meta"]["rule_version"] == "rv-z-current__rv-z-prior__rv_pnl_phase2_materialize_v1"
    assert payload["result_meta"]["vendor_version"] == "vv_none"
    assert payload["result_meta"]["cache_version"] == (
        "cv_pnl_bridge_formal_v1__cv_pnl_formal__rv_pnl_phase2_materialize_v1__"
        "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1__"
        "cv_yield_curve_formal__rv_yield_curve_formal_materialize_v1"
    )
    row = payload["result"]["rows"][0]
    assert row["instrument_code"] == "240001.IB"
    assert row["beginning_dirty_mv"]["raw"] == 91.0
    assert row["ending_dirty_mv"]["raw"] == 102.0
    assert row["current_balance_found"] is True
    assert row["prior_balance_found"] is True
    assert row["balance_diagnostics"] == []
    summary = payload["result"]["summary"]
    assert summary["total_beginning_dirty_mv"]["raw"] == 91.0
    assert summary["total_ending_dirty_mv"]["raw"] == 102.0
    assert summary["total_carry"]["raw"] == 12.5
    assert summary["total_roll_down"]["raw"] == 0.0
    assert summary["total_treasury_curve"]["raw"] == 0.0
    assert summary["total_credit_spread"]["raw"] == 0.0
    assert summary["total_fx_translation"]["raw"] == 0.0
    assert summary["total_realized_trading"]["raw"] == 1.75
    assert summary["total_unrealized_fv"]["raw"] == -3.25
    assert summary["total_manual_adjustment"]["raw"] == 0.5
    assert summary["total_explained_pnl"]["raw"] == 11.5
    assert summary["total_actual_pnl"]["raw"] == 11.5
    assert summary["total_residual"]["raw"] == 0.0
    assert payload["result"]["warnings"][0] == (
        "Phase 3 partial delivery: roll_down / treasury_curve / credit_spread use governed curves when available."
    )
    assert any(
        "Balance lineage fallback used for report_date=2025-12-31" in warning
        for warning in payload["result"]["warnings"]
    )
    assert any(
        "Balance lineage fallback used for prior_report_date=2025-10-31" in warning
        for warning in payload["result"]["warnings"]
    )
    assert any("No treasury curve available" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


def test_pnl_bridge_returns_503_when_balance_query_fails(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge",
        vendor_version="vv_bridge",
        rule_version="rv_bridge",
    )
    bridge_service = load_module(
        "backend.app.services.pnl_bridge_service",
        "backend/app/services/pnl_bridge_service.py",
    )

    def fail_balance_read(*_args, **_kwargs):
        raise RuntimeError("Formal balance query failed for pnl.bridge.")

    monkeypatch.setattr(
        bridge_service.BalanceAnalysisRepository,
        "fetch_pnl_bridge_zqtz_balance_rows",
        fail_balance_read,
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Formal balance query failed for pnl.bridge."
    get_settings.cache_clear()


def test_pnl_bridge_result_meta_merges_report_date_specific_balance_build_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_bridge_meta",
        vendor_version="vv_pnl_bridge_meta",
        rule_version="rv_pnl_bridge_meta",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-current",
        report_date="2025-12-31",
        source_version="sv_balance_current",
        vendor_version="vv_balance",
        rule_version="rv_balance_current",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-prior",
        report_date="2025-10-31",
        source_version="sv_balance_prior",
        vendor_version="vv_balance",
        rule_version="rv_balance_prior",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-newer-unrelated",
        report_date="2026-01-31",
        source_version="sv_balance_newer",
        vendor_version="vv_balance",
        rule_version="rv_balance_newer",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == (
        "fi-shared-v1__nonstd-shared-v1__sv_balance_current__sv_balance_prior"
    )
    assert payload["result_meta"]["rule_version"] == (
        "rv_balance_current__rv_balance_prior__rv_pnl_phase2_materialize_v1"
    )
    assert payload["result_meta"]["vendor_version"] == "vv_balance__vv_none"
    assert payload["result"]["warnings"][0] == (
        "Phase 3 partial delivery: roll_down / treasury_curve / credit_spread use governed curves when available."
    )
    assert any("No treasury curve available" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


def test_pnl_bridge_prefers_latest_valid_balance_build_when_newer_completed_row_has_blank_source_version(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_bridge_meta",
        vendor_version="vv_pnl_bridge_meta",
        rule_version="rv_pnl_bridge_meta",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-current-valid",
        report_date="2025-12-31",
        source_version="sv_balance_current_valid",
        vendor_version="vv_balance",
        rule_version="rv_balance_current_valid",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-current-invalid-newer",
        report_date="2025-12-31",
        source_version="",
        vendor_version="vv_balance",
        rule_version="rv_balance_current_invalid",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-prior",
        report_date="2025-10-31",
        source_version="sv_balance_prior",
        vendor_version="vv_balance",
        rule_version="rv_balance_prior",
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["source_version"] == (
        "fi-shared-v1__nonstd-shared-v1__sv_balance_current_valid__sv_balance_prior"
    )
    assert payload["result_meta"]["rule_version"] == (
        "rv_balance_current_valid__rv_balance_prior__rv_pnl_phase2_materialize_v1"
    )
    assert not any(
        "Balance lineage fallback used for report_date=2025-12-31" in warning
        for warning in payload["result"]["warnings"]
    )
    get_settings.cache_clear()


def test_pnl_bridge_reads_fx_rates_from_duckdb_and_populates_fx_translation(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_bridge_fx",
        vendor_version="vv_bridge_fx",
        rule_version="rv_bridge_fx",
    )
    _seed_usd_pnl_bridge_balance_rows(duckdb_path)
    _seed_pnl_bridge_snapshot_face_values(duckdb_path)
    _seed_pnl_bridge_fx_rates(duckdb_path)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    row = payload["result"]["rows"][0]
    assert row["fx_translation"]["raw"] == 41.35
    assert payload["result"]["summary"]["total_fx_translation"]["raw"] == 41.35
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


def test_pnl_refresh_sync_fallback_uses_direct_sync_helper(tmp_path, monkeypatch):
    _configure_refresh_sources(tmp_path, monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    sync_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        pnl_service.materialize_pnl_facts,
        "send",
        lambda **_: (_ for _ in ()).throw(RuntimeError("queue disabled")),
    )
    monkeypatch.setattr(
        pnl_service,
        "run_pnl_materialize_sync",
        lambda **kwargs: sync_calls.append(kwargs) or {
            "status": "completed",
            "cache_key": "pnl:phase2:materialize:formal",
            "run_id": kwargs["run_id"],
            "report_date": kwargs["report_date"],
            "formal_fi_rows": 1,
            "nonstd_bridge_rows": 1,
            "source_version": "sv_test",
            "rule_version": "rv_test",
            "vendor_version": "vv_none",
            "lock": "lock:duckdb:formal:pnl:phase2:materialize",
        },
    )

    payload = pnl_service.refresh_pnl(get_settings())

    assert payload["status"] == "completed"
    assert payload["trigger_mode"] == "sync-fallback"
    assert sync_calls
    assert sync_calls[0]["report_date"] == "2026-02-28"


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
    assert response.json()["detail"] == (
        "Pnl refresh queue dispatch failed: RuntimeError: unexpected broker failure"
    )
    assert fallback_calls == []

    records = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
    latest = [record for record in records if record.get("job_name") == "pnl_materialize"][-1]
    assert latest["status"] == "failed"
    assert latest["error_message"] == (
        "Pnl refresh queue dispatch failed: RuntimeError: unexpected broker failure"
    )
    assert latest["failure_category"] == "RuntimeError"
    assert latest["failure_reason"] == "unexpected broker failure"
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


def test_pnl_refresh_report_date_prefers_manifest_source_over_direct_source_for_same_family(
    tmp_path,
    monkeypatch,
):
    _, governance_dir = _configure_refresh_sources(tmp_path, monkeypatch)
    _copy_fi_refresh_source(tmp_path, month_key="202601")
    manifest_fi = _create_archived_copy(
        tmp_path,
        source_file=ROOT / "data_input" / "pnl" / "FI损益202601.xls",
        archive_name="manifest-fi-202601.xls",
    )
    _append_source_manifest_row(
        governance_dir,
        source_family="pnl",
        report_date="2026-01-31",
        source_file="FI损益202601.xls",
        archived_path=manifest_fi,
        source_version="sv_manifest_fi_202601",
        ingest_batch_id="ib_manifest_fi_202601",
    )

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
    assert response.json()["report_date"] == "2026-01-31"
    assert queued_messages
    assert queued_messages[0]["fi_rows"]
    assert {
        row["source_version"] for row in queued_messages[0]["fi_rows"]
    } == {"sv_manifest_fi_202601"}
    get_settings.cache_clear()


def test_pnl_refresh_report_date_mixes_manifest_and_direct_sources_by_family(
    tmp_path,
    monkeypatch,
):
    _, governance_dir = _configure_refresh_sources(tmp_path, monkeypatch)
    _copy_fi_refresh_source(tmp_path, month_key="202601")
    _write_nonstd_refresh_workbook(
        tmp_path / "data_input" / "pnl_516" / "非标516-20260101-0131.xlsx",
        row_dates=("2026-01-30", "2026-01-31"),
    )
    manifest_fi = _create_archived_copy(
        tmp_path,
        source_file=ROOT / "data_input" / "pnl" / "FI损益202601.xls",
        archive_name="manifest-fi-202601.xls",
    )
    _append_source_manifest_row(
        governance_dir,
        source_family="pnl",
        report_date="2026-01-31",
        source_file="FI损益202601.xls",
        archived_path=manifest_fi,
        source_version="sv_manifest_fi_202601",
        ingest_batch_id="ib_manifest_fi_202601",
    )

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
    assert queued_messages
    fi_rows = queued_messages[0]["fi_rows"]
    nonstd_rows = queued_messages[0]["nonstd_rows_by_type"]["516"]
    assert {row["source_version"] for row in fi_rows} == {"sv_manifest_fi_202601"}
    assert all(row["source_version"] != "sv_manifest_fi_202601" for row in nonstd_rows)
    assert all(str(row["source_version"]).startswith("sv_pnl_") for row in nonstd_rows)
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


def test_pnl_dates_returns_empty_when_storage_is_unavailable(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    _append_manifest_override(governance_dir, source_version="sv_manifest", vendor_version="vv_manifest", rule_version="rv_manifest")

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "missing.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/dates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["report_dates"] == []
    get_settings.cache_clear()


def test_pnl_overview_returns_404_when_storage_is_unavailable(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    _append_manifest_override(governance_dir, source_version="sv_manifest", vendor_version="vv_manifest", rule_version="rv_manifest")

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "missing.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/overview", params={"report_date": "2025-12-31"})

    assert response.status_code == 404
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
    monkeypatch.setenv("MOSS_FORMAL_PNL_ENABLED", "true")
    monkeypatch.setenv("MOSS_FORMAL_PNL_SCOPE_JSON", '["*"]')
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
                "approval_status": "approved",
                "event_semantics": "realized_formal",
                "realized_flag": True,
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
                "approval_status": "approved",
                "event_semantics": "realized_formal",
                "realized_flag": True,
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


def _append_manifest_override(
    governance_dir,
    *,
    source_version: str,
    vendor_version: str,
    rule_version: str,
    cache_version: str | None = None,
):
    manifest_path = governance_dir / "cache_manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "cache_key": "pnl:phase2:materialize:formal",
                    "cache_version": cache_version,
                    "source_version": source_version,
                    "vendor_version": vendor_version,
                    "rule_version": rule_version,
                },
                ensure_ascii=False,
        )
            + "\n"
        )


def _seed_pnl_bridge_balance_rows(
    duckdb_path: Path,
    *,
    include_tyw_only_intermediate_prior: bool,
    include_unusable_zqtz_intermediate_prior: bool = False,
) -> None:
    repo_module = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        repo_module.ensure_balance_analysis_tables(conn)
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "240001.IB",
                "FI Desk",
                "CC100",
                "T",
                "FVTPL",
                "asset",
                "CNY",
                "CNY",
                "100.00000000",
                "99.00000000",
                "2.00000000",
                False,
                "sv-z-current",
                "rv-z-current",
                "ib-z-current",
                "trace-z-current",
            ],
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-10-31",
                "240001.IB",
                "FI Desk",
                "CC100",
                "T",
                "FVTPL",
                "asset",
                "CNY",
                "CNY",
                "90.00000000",
                "89.00000000",
                "1.00000000",
                False,
                "sv-z-prior",
                "rv-z-prior",
                "ib-z-prior",
                "trace-z-prior",
            ],
        )
        if include_tyw_only_intermediate_prior:
            conn.execute(
                """
                insert into fact_formal_tyw_balance_daily (
                  report_date, position_id, product_type, position_side, counterparty_name,
                  invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
                  principal_amount, accrued_interest_amount, source_version, rule_version,
                  ingest_batch_id, trace_id
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "2025-11-30",
                    "tyw-only-prior",
                    "Interbank",
                    "liability",
                    "Bank A",
                    "H",
                    "AC",
                    "liability",
                    "CNY",
                    "CNY",
                    "50.00000000",
                    "5.00000000",
                    "sv-tyw-prior",
                    "rv-tyw-prior",
                    "ib-tyw-prior",
                    "trace-tyw-prior",
                ],
            )
        if include_unusable_zqtz_intermediate_prior:
            conn.execute(
                """
                insert into fact_formal_zqtz_balance_daily (
                  report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
                  accounting_basis, position_scope, currency_basis, currency_code,
                  market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
                  source_version, rule_version, ingest_batch_id, trace_id
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "2025-11-30",
                    "240001.IB",
                    "FI Desk",
                    "CC100",
                    "T",
                    "FVTPL",
                    "liability",
                    "native",
                    "CNY",
                    "999.00000000",
                    "999.00000000",
                    "9.00000000",
                    True,
                    "sv-z-unusable",
                    "rv-z-unusable",
                    "ib-z-unusable",
                    "trace-z-unusable",
                ],
            )
    finally:
        conn.close()


def _seed_usd_pnl_bridge_balance_rows(duckdb_path: Path) -> None:
    repo_module = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        repo_module.ensure_balance_analysis_tables(conn)
        conn.execute(
            "update fact_formal_pnl_fi set currency_basis = 'USD' where report_date = '2025-12-31' and instrument_code = '240001.IB'"
        )
        conn.execute("delete from fact_formal_zqtz_balance_daily")
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-31",
                    "240001.IB",
                    "FI Desk",
                    "CC100",
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "USD",
                    "100.00000000",
                    "99.00000000",
                    "2.00000000",
                    False,
                    "sv-z-current-usd",
                    "rv-z-current-usd",
                    "ib-z-current-usd",
                    "trace-z-current-usd",
                ),
                (
                    "2025-10-31",
                    "240001.IB",
                    "FI Desk",
                    "CC100",
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "USD",
                    "90.00000000",
                    "89.00000000",
                    "1.00000000",
                    False,
                    "sv-z-prior-usd",
                    "rv-z-prior-usd",
                    "ib-z-prior-usd",
                    "trace-z-prior-usd",
                ),
            ],
        )
    finally:
        conn.close()


def _seed_pnl_bridge_snapshot_face_values(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists zqtz_bond_daily_snapshot (
              report_date varchar,
              instrument_code varchar,
              portfolio_name varchar,
              cost_center varchar,
              currency_code varchar,
              face_value_native decimal(24, 8)
            )
            """
        )
        conn.execute("delete from zqtz_bond_daily_snapshot")
        conn.executemany(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, portfolio_name, cost_center, currency_code, face_value_native
            ) values (?, ?, ?, ?, ?, ?)
            """,
            [
                ("2025-12-31", "240001.IB", "FI Desk", "CC100", "USD", "1000.00000000"),
                ("2025-10-31", "240001.IB", "FI Desk", "CC100", "USD", "1000.00000000"),
            ],
        )
    finally:
        conn.close()


def _seed_pnl_bridge_fx_rates(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(18, 8),
              source_version varchar
            )
            """
        )
        conn.execute("delete from fx_daily_mid")
        conn.executemany(
            """
            insert into fx_daily_mid (trade_date, base_currency, quote_currency, mid_rate, source_version)
            values (?, ?, ?, ?, ?)
            """,
            [
                ("2025-12-31", "USD", "CNY", "7.08270000", "sv_fx_daily_mid_test"),
                ("2025-10-31", "USD", "CNY", "7.04135000", "sv_fx_daily_mid_test"),
            ],
        )
    finally:
        conn.close()


def _configure_refresh_sources(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    data_root = tmp_path / "data_input"
    (data_root / "pnl").mkdir(parents=True)
    (data_root / "pnl_516").mkdir(parents=True)

    _write_fi_refresh_marker(data_root, month_key="202602")
    _write_nonstd_refresh_workbook(data_root / "pnl_516" / "非标516-20260101-0228.xlsx")
    source_service = load_module(
        "backend.app.services.pnl_source_service",
        "backend/app/services/pnl_source_service.py",
    )
    monkeypatch.setattr(source_service, "_parse_fi_rows", _fake_parse_fi_refresh_rows)

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_FORMAL_PNL_ENABLED", "true")
    monkeypatch.setenv("MOSS_FORMAL_PNL_SCOPE_JSON", '["*"]')
    get_settings.cache_clear()
    return duckdb_path, governance_dir


def _copy_fi_refresh_source(tmp_path, *, month_key: str):
    _write_fi_refresh_marker(tmp_path / "data_input", month_key=month_key)


def _write_fi_refresh_marker(data_root: Path, *, month_key: str) -> Path:
    path = data_root / "pnl" / f"FI损益{month_key}.xls"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("test-only FI refresh marker; parser is monkeypatched\n", encoding="utf-8")
    return path


def _fake_parse_fi_refresh_rows(snapshot) -> list[dict[str, object]]:
    return [
        {
            "report_date": snapshot.report_date,
            "instrument_code": "240001.IB",
            "portfolio_name": "FI Desk",
            "cost_center": "CC100",
            "invest_type_raw": "交易性金融资产",
            "interest_income_514": Decimal("12.50"),
            "fair_value_change_516": Decimal("-3.25"),
            "capital_gain_517": Decimal("1.75"),
            "manual_adjustment": Decimal("0"),
            "currency_basis": "CNY",
            "source_version": snapshot.source_version,
            "rule_version": "rv_test_fi_refresh_parser",
            "ingest_batch_id": snapshot.ingest_batch_id,
            "trace_id": f"{snapshot.path.name}:fi:1",
            "approval_status": "approved",
            "event_semantics": "realized_formal",
            "realized_flag": True,
        }
    ]


def _configure_import_status_env(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()
    return governance_dir


def _append_source_manifest_row(
    governance_dir,
    *,
    source_family: str,
    report_date: str,
    source_file: str,
    archived_path: Path,
    source_version: str,
    ingest_batch_id: str,
):
    GovernanceRepository(base_dir=governance_dir).append(
        SOURCE_MANIFEST_STREAM,
        {
            "source_family": source_family,
            "report_date": report_date,
            "source_file": source_file,
            "archived_path": str(archived_path),
            "source_version": source_version,
            "ingest_batch_id": ingest_batch_id,
            "status": "completed",
            "created_at": "2026-04-11T00:00:00+00:00",
        },
    )


def _create_archived_copy(tmp_path, *, source_file: Path, archive_name: str) -> Path:
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / archive_name
    target.write_text(
        f"test-only archived marker for {source_file.name}\n",
        encoding="utf-8",
    )
    return target


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


def _append_balance_build_run(
    governance_dir,
    *,
    run_id: str,
    report_date: str,
    source_version: str,
    vendor_version: str,
    rule_version: str,
):
    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=run_id,
                job_name="balance_analysis_materialize",
                status="completed",
                cache_key="balance_analysis:materialize:formal",
                cache_version="cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1",
                lock="lock:duckdb:formal:balance-analysis:materialize",
                source_version=source_version,
                vendor_version=vendor_version,
                rule_version=rule_version,
            ).model_dump(),
            "report_date": report_date,
        },
    )


def _write_nonstd_refresh_workbook(
    path: Path,
    *,
    include_prior_month_row: bool = False,
    row_dates: tuple[str, str] = ("2026-02-27", "2026-02-28"),
) -> None:
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
            row_dates[0],
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
            row_dates[1],
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
