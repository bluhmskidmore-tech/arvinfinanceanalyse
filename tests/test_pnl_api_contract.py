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


def _force_pnl_ytd_refresh_bundle_contract(monkeypatch) -> None:
    """契约测试用 FakeRefreshInput 时关闭 formal 优先，避免与已物化的 DuckDB 行混用。"""
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "false")
    get_settings.cache_clear()


def test_fastapi_application_registers_pnl_routes():
    from backend.app.main import app

    paths = {route.path for route in app.routes}

    assert "/api/pnl/dates" in paths
    assert "/api/pnl/data" in paths
    assert "/api/pnl/bridge" in paths
    assert "/api/pnl/overview" in paths
    assert "/api/pnl/v1-data" in paths
    assert "/api/pnl/by-business" in paths
    assert "/api/pnl/by-business-ytd" in paths
    assert "/api/pnl/by-business-monthly" in paths
    assert "/api/pnl/by-business-analysis" in paths
    assert "/api/pnl/by-business/manual-adjustments" in paths
    assert "/api/pnl/by-business/manual-adjustments/{adjustment_id}/edit" in paths
    assert "/api/pnl/by-business/manual-adjustments/{adjustment_id}/revoke" in paths
    assert "/api/pnl/by-business/manual-adjustments/{adjustment_id}/restore" in paths
    assert "/api/pnl/yearly-summary" in paths
    assert "/api/data/refresh_pnl" in paths
    assert "/api/data/import_status/pnl" in paths


def test_pnl_by_business_analysis_reuses_inputs_for_same_period(monkeypatch):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    class FakePnlRepository:
        pnl_fetch_count = 0
        balance_fetch_count = 0

        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2026
            assert as_of_cap in {None, "2026-04-30"}
            return "2026-04-30"

        def list_union_report_dates(self):
            return ["2026-01-31", "2026-04-30"]

        def fetch_by_business_analysis_pnl_rows(self, *, year, as_of_date):
            assert year == 2026
            assert as_of_date == "2026-04-30"
            type(self).pnl_fetch_count += 1
            return [
                {
                    "source_kind": "formal_fi",
                    "report_date": "2026-04-30",
                    "instrument_code": "P001",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "currency_basis": "CNY",
                    "invest_type_std": "政策性金融债",
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("100.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("100.00"),
                }
            ]

        def fetch_by_business_analysis_balance_rows(self, *, start_date, end_date):
            assert start_date == "2026-01-01"
            assert end_date == "2026-04-30"
            type(self).balance_fetch_count += 1
            return [
                {
                    "report_date": "2026-04-30",
                    "instrument_code": "P001",
                    "instrument_name": "policy bond",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "account_category": "asset",
                    "asset_class": "政策性金融债",
                    "bond_type": "政策性金融债",
                    "sub_type": "政策性金融债",
                    "business_type_primary": "政策性金融债",
                    "business_type_final": "政策性金融债",
                    "invest_type_std": "T",
                    "accounting_basis": "FVTPL",
                    "position_scope": "asset",
                    "currency_basis": "CNY",
                    "currency_code": "CNY",
                    "avg_amount": Decimal("1000.00"),
                    "current_amount": Decimal("1000.00"),
                }
            ]

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result": kwargs["result_payload"]},
    )

    first = pnl_service.pnl_by_business_analysis_envelope(
        duckdb_path="fake.duckdb",
        governance_dir="fake-governance",
        year=2026,
        as_of_date="2026-04-30",
        dimension="bond_bucket",
    )
    second = pnl_service.pnl_by_business_analysis_envelope(
        duckdb_path="fake.duckdb",
        governance_dir="fake-governance",
        year=2026,
        as_of_date="2026-04-30",
        dimension="bond_bucket_monthly",
    )

    assert first["result"]["rows"][0]["dimension_label"] == "利率债"
    assert second["result"]["dimension"] == "bond_bucket_monthly"
    assert FakePnlRepository.pnl_fetch_count == 1
    assert FakePnlRepository.balance_fetch_count == 1
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()


def test_pnl_by_business_monthly_prefers_precomputed_payload(monkeypatch):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    cached_payload = {
        "year": 2025,
        "as_of_date": "2025-12-31",
        "source_tables": ["fact_pnl_by_business_precompute"],
        "months": [],
    }

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-12-31"}
            return "2025-12-31"

        def fetch_pnl_by_business_precompute(self, *, year, as_of_date, result_kind, dimension, business_key):
            assert (year, as_of_date, result_kind, dimension, business_key) == (
                2025,
                "2025-12-31",
                "monthly",
                "",
                "",
            )
            return cached_payload

        def list_union_report_dates(self):  # pragma: no cover - proves cache avoids live build
            raise AssertionError("monthly endpoint should not rebuild when precompute exists")

        def fetch_by_business_analysis_pnl_rows(self, **_kwargs):  # pragma: no cover
            raise AssertionError("monthly endpoint should not fetch analysis rows when precompute exists")

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result_meta": {"result_kind": kwargs["result_kind"]}, "result": kwargs["result_payload"]},
    )

    payload = pnl_service.pnl_by_business_monthly_envelope(
        duckdb_path="fake.duckdb",
        governance_dir="fake-governance",
        year=2025,
        as_of_date="2025-12-31",
    )

    assert payload["result_meta"]["result_kind"] == "pnl.by_business_monthly"
    assert payload["result"] == cached_payload


def test_pnl_by_business_analysis_prefers_precomputed_payload(monkeypatch):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    cached_payload = {
        "year": 2025,
        "as_of_date": "2025-12-31",
        "business_key": "asset_zqtz_policy_financial_bond",
        "dimension": "instrument",
        "period_start_date": "2025-01-01",
        "period_end_date": "2025-12-31",
        "source_tables": ["fact_pnl_by_business_precompute"],
        "rows": [],
    }

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-12-31"}
            return "2025-12-31"

        def fetch_pnl_by_business_precompute(self, *, year, as_of_date, result_kind, dimension, business_key):
            assert (year, as_of_date, result_kind, dimension, business_key) == (
                2025,
                "2025-12-31",
                "analysis",
                "instrument",
                "asset_zqtz_policy_financial_bond",
            )
            return cached_payload

        def list_union_report_dates(self):  # pragma: no cover - proves cache avoids live build
            raise AssertionError("analysis endpoint should not rebuild when precompute exists")

        def fetch_by_business_analysis_pnl_rows(self, **_kwargs):  # pragma: no cover
            raise AssertionError("analysis endpoint should not fetch rows when precompute exists")

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result_meta": {"result_kind": kwargs["result_kind"]}, "result": kwargs["result_payload"]},
    )

    payload = pnl_service.pnl_by_business_analysis_envelope(
        duckdb_path="fake.duckdb",
        governance_dir="fake-governance",
        year=2025,
        as_of_date="2025-12-31",
        business_key="asset_zqtz_policy_financial_bond",
        dimension="instrument",
    )

    assert payload["result_meta"]["result_kind"] == "pnl.by_business_analysis"
    assert payload["result"] == cached_payload


def test_pnl_by_business_precompute_writes_page_payloads(monkeypatch):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    row_defs = (
        {
            "row_key": "asset_zqtz_policy_financial_bond",
            "row_label": "Policy Financial Bond",
            "sort_order": 66,
            "source_note": "test",
        },
    )

    class FakePnlRepository:
        written_records: list[dict[str, object]] = []

        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-12-31"}
            return "2025-12-31"

        def list_union_report_dates(self):
            return ["2025-12-31"]

        def fetch_by_business_analysis_pnl_rows(self, *, year, as_of_date):
            assert year == 2025
            assert as_of_date == "2025-12-31"
            return [
                {
                    "source_kind": "formal_fi",
                    "report_date": "2025-12-31",
                    "instrument_code": "P001",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "currency_basis": "CNY",
                    "invest_type_std": "Policy Financial Bond",
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("100.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("100.00"),
                }
            ]

        def fetch_by_business_analysis_balance_rows(self, *, start_date, end_date):
            assert start_date == "2025-12-01"
            assert end_date == "2025-12-31"
            return [
                {
                    "report_date": "2025-12-31",
                    "instrument_code": "P001",
                    "instrument_name": "policy bond",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "account_category": "asset",
                    "asset_class": "Policy Financial Bond",
                    "bond_type": "Policy Financial Bond",
                    "sub_type": "Policy Financial Bond",
                    "business_type_primary": "Policy Financial Bond",
                    "business_type_final": "Policy Financial Bond",
                    "invest_type_std": "Policy Financial Bond",
                    "accounting_basis": "FVTPL",
                    "position_scope": "asset",
                    "currency_basis": "CNY",
                    "currency_code": "CNY",
                    "avg_amount": Decimal("10000.00"),
                    "current_amount": Decimal("11000.00"),
                }
            ]

        def replace_pnl_by_business_precompute(self, *, year, as_of_date, records):
            assert year == 2025
            assert as_of_date == "2025-12-31"
            type(self).written_records = records

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(pnl_service, "ZQTZ_ASSET_BOND_ROWS", row_defs)
    monkeypatch.setattr(pnl_service, "match_zqtz_asset_bond_rows", lambda _classification: row_defs)

    summary = pnl_service.precompute_pnl_by_business_payloads(
        duckdb_path="fake.duckdb",
        governance_dir="fake-governance",
        year=2025,
        as_of_date="2025-12-31",
    )

    record_keys = {
        (str(record["result_kind"]), str(record["dimension"]), str(record["business_key"]))
        for record in FakePnlRepository.written_records
    }
    assert ("monthly", "", "") in record_keys
    assert ("analysis", "bond_bucket", "") in record_keys
    assert ("analysis", "instrument", "asset_zqtz_policy_financial_bond") in record_keys
    assert summary["records"] == len(FakePnlRepository.written_records)

    monthly_record = next(record for record in FakePnlRepository.written_records if record["result_kind"] == "monthly")
    monthly_payload = json.loads(str(monthly_record["payload_json"]))
    assert monthly_payload["as_of_date"] == "2025-12-31"
    assert monthly_payload["months"][0]["month_key"] == "2025-12"


def test_pnl_by_business_precompute_invalidates_after_source_change(tmp_path, monkeypatch):
    task_module = load_module("backend.app.tasks.pnl_materialize", "backend/app/tasks/pnl_materialize.py")
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    task_module.materialize_pnl_facts.fn(
        report_date="2025-12-31",
        is_month_end=True,
        fi_rows=[
            {
                "report_date": "2025-12-31",
                "instrument_code": "P001",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "interest_income_514": "10.00",
                "fair_value_change_516": "0.00",
                "capital_gain_517": "0.00",
                "manual_adjustment": "0.00",
                "currency_basis": "CNY",
                "source_version": "src-v1",
                "rule_version": "rule-v1",
                "ingest_batch_id": "batch-fi",
                "trace_id": "trace-fi",
                "approval_status": "approved",
                "event_semantics": "realized_formal",
                "realized_flag": True,
            }
        ],
        nonstd_rows_by_type={},
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        formal_pnl_enabled=True,
        formal_pnl_scope_json='["*"]',
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi values (
              '2025-12-31', 'P002', 'FI Desk', 'CC100', 'T', 'FVTPL', 'CNY',
              5.00, 0.00, 0.00, 0.00, 5.00,
              'src-v2', 'rv_pnl_phase2_materialize_v1', 'batch-fi-2', 'trace-fi-2'
            )
            """
        )
    finally:
        conn.close()

    payload = pnl_service.pnl_by_business_analysis_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        year=2025,
        as_of_date="2025-12-31",
        dimension="bond_bucket",
    )

    total_pnl = sum(Decimal(str(row["total_pnl"])) for row in payload["result"]["rows"])
    assert total_pnl == Decimal("15.00")


def test_pnl_by_business_monthly_contract_returns_independent_month_buckets(monkeypatch):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    category_module = load_module(
        "backend.app.core_finance.zqtz_asset_bond_category",
        "backend/app/core_finance/zqtz_asset_bond_category.py",
    )
    row_defs = {str(row["row_key"]): row for row in category_module.ZQTZ_ASSET_BOND_ROWS}
    policy_type = str(row_defs["asset_zqtz_policy_financial_bond"]["match_keywords"][0])
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()

    class FakePnlRepository:
        def __init__(self, _path):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap):
            assert year == 2025
            assert as_of_cap in {None, "2025-02-28"}
            return "2025-02-28"

        def list_union_report_dates(self):
            return ["2025-01-31", "2025-02-28"]

        def fetch_by_business_analysis_pnl_rows(self, *, year, as_of_date):
            assert year == 2025
            assert as_of_date == "2025-02-28"
            return [
                {
                    "source_kind": "formal_fi",
                    "report_date": "2025-01-31",
                    "instrument_code": "P001",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "currency_basis": "CNY",
                    "invest_type_std": policy_type,
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("100.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("100.00"),
                },
                {
                    "source_kind": "formal_fi",
                    "report_date": "2025-02-28",
                    "instrument_code": "P001",
                    "portfolio_name": "Rate Desk",
                    "cost_center": "CC-RATE",
                    "currency_basis": "CNY",
                    "invest_type_std": policy_type,
                    "accounting_basis": "FVTPL",
                    "interest_income_514": Decimal("200.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "manual_adjustment": Decimal("0.00"),
                    "total_pnl": Decimal("200.00"),
                },
            ]

        def fetch_by_business_analysis_balance_rows(self, *, start_date, end_date):
            assert start_date == "2025-01-01"
            assert end_date == "2025-02-28"
            base = {
                "instrument_code": "P001",
                "instrument_name": "policy bond",
                "portfolio_name": "Rate Desk",
                "cost_center": "CC-RATE",
                "account_category": "asset",
                "asset_class": policy_type,
                "bond_type": policy_type,
                "sub_type": policy_type,
                "business_type_primary": policy_type,
                "business_type_final": policy_type,
                "invest_type_std": "T",
                "accounting_basis": "FVTPL",
                "position_scope": "asset",
                "currency_basis": "CNY",
                "currency_code": "CNY",
            }
            return [
                {
                    **base,
                    "report_date": "2025-01-31",
                    "avg_amount": Decimal("1000.00"),
                    "current_amount": Decimal("1100.00"),
                },
                {
                    **base,
                    "report_date": "2025-02-28",
                    "avg_amount": Decimal("2000.00"),
                    "current_amount": Decimal("2200.00"),
                },
            ]

    monkeypatch.setattr(pnl_service, "PnlRepository", FakePnlRepository)
    monkeypatch.setattr(
        pnl_service,
        "_build_pnl_formal_result_envelope_from_lineage",
        lambda **kwargs: {"result_meta": {"result_kind": kwargs["result_kind"]}, "result": kwargs["result_payload"]},
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/by-business-monthly", params={"year": 2025, "as_of_date": "2025-02-28"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business_monthly"
    result = payload["result"]
    assert result["year"] == 2025
    assert result["as_of_date"] == "2025-02-28"
    assert [month["month_key"] for month in result["months"]] == ["2025-01", "2025-02"]

    jan, feb = result["months"]
    assert jan["period_start_date"] == "2025-01-01"
    assert jan["period_end_date"] == "2025-01-31"
    assert jan["calendar_days"] == 31
    assert jan["summary"]["total_pnl"] == "100.00"
    assert jan["summary"]["avg_balance"] == "1000.00"
    assert jan["summary"]["current_balance"] == "1100.00"
    assert jan["summary"]["ftp_cost"] == "1.36"
    assert jan["summary"]["ftp_net_pnl"] == "98.64"
    jan_item = next(item for item in jan["items"] if item["row_key"] == "asset_zqtz_policy_financial_bond")
    assert set(jan_item) == {
        "row_key",
        "sort_order",
        "business_type",
        "interest_income",
        "fair_value_change",
        "capital_gain",
        "manual_adjustment",
        "total_pnl",
        "avg_balance",
        "current_balance",
        "annualized_yield_pct",
        "ftp_rate_pct",
        "ftp_cost",
        "ftp_net_pnl",
        "ftp_net_annualized_yield_pct",
        "proportion",
        "asset_count",
        "source_note",
    }
    assert jan_item["total_pnl"] == "100.00"
    assert jan_item["avg_balance"] == "1000.00"
    assert jan_item["current_balance"] == "1100.00"
    assert jan_item["annualized_yield_pct"] == "117.741935"
    assert jan_item["ftp_rate_pct"] == "1.600000"
    assert jan_item["ftp_cost"] == "1.36"
    assert jan_item["ftp_net_pnl"] == "98.64"
    assert jan_item["ftp_net_annualized_yield_pct"] == "116.141935"
    assert jan_item["proportion"] == "1.000000"
    assert jan_item["asset_count"] == 1
    assert feb["summary"]["total_pnl"] == "200.00"
    assert feb["summary"]["avg_balance"] == "2000.00"
    assert feb["items"][0]["total_pnl"] != "300.00"
    if hasattr(pnl_service, "_clear_pnl_by_business_analysis_cache"):
        pnl_service._clear_pnl_by_business_analysis_cache()


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


def test_pnl_by_business_ytd_runtime_cache_reuses_same_arguments(monkeypatch):
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    pnl_service.clear_pnl_by_business_ytd_cache()
    calls: list[dict[str, object]] = []

    def fake_uncached(**kwargs):
        calls.append(kwargs)
        return {"result": {"call_count": len(calls)}}

    monkeypatch.setattr(pnl_service, "_pnl_by_business_ytd_envelope_uncached", fake_uncached)

    first = pnl_service.pnl_by_business_ytd_envelope(
        duckdb_path="fake.duckdb",
        governance_dir="fake-governance",
        year=2025,
        as_of_date="2025-12-31",
    )
    second = pnl_service.pnl_by_business_ytd_envelope(
        duckdb_path="fake.duckdb",
        governance_dir="fake-governance",
        year=2025,
        as_of_date="2025-12-31",
    )

    assert first == second
    assert first["result"]["call_count"] == 1
    assert len(calls) == 1
    pnl_service.clear_pnl_by_business_ytd_cache()


def test_adb_comparison_runtime_cache_reuses_same_arguments(monkeypatch):
    adb_service = load_module("backend.app.services.adb_analysis_service", "backend/app/services/adb_analysis_service.py")
    adb_service.clear_adb_comparison_cache()
    calls: list[tuple[str, str, int]] = []

    def fake_uncached(start_date, end_date, top_n=20):
        calls.append((start_date, end_date, top_n))
        return {"result": {"call_count": len(calls)}}

    monkeypatch.setattr(adb_service, "_adb_comparison_envelope_uncached", fake_uncached)

    first = adb_service.adb_comparison_envelope("2025-01-01", "2025-12-31", top_n=200)
    second = adb_service.adb_comparison_envelope("2025-01-01", "2025-12-31", top_n=200)

    assert first == second
    assert first["result"]["call_count"] == 1
    assert calls == [("2025-01-01", "2025-12-31", 200)]
    adb_service.clear_adb_comparison_cache()


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


def test_pnl_by_business_traces_formal_fi_to_zqtz_business_type_primary(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/by-business", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business"
    result = payload["result"]
    assert result["report_date"] == "2025-12-31"
    assert result["source_tables"] == [
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "fact_formal_zqtz_balance_daily",
    ]
    by_business = {row["business_type_primary"]: row for row in result["rows"]}
    assert by_business["bond-trading"]["total_pnl"] == "111.50"
    assert by_business["bond-trading"]["capital_gain_517"] == "1.75"
    assert by_business["bond-trading"]["scale_amount"] == "1099.00"
    assert by_business["bond-trading"]["yield_pct"] == "10.145587"
    assert by_business["bond-trading"]["pnl_row_count"] == 2
    assert by_business["bond-allocation"]["total_pnl"] == "10.00"
    assert by_business["bond-allocation"]["scale_amount"] == "300.00"
    assert by_business["H"]["total_pnl"] == "4.00"
    assert by_business["H"]["scale_amount"] == "0.00"
    assert by_business["H"]["yield_pct"] is None
    assert result["summary"]["total_pnl"] == "125.50"
    assert result["summary"]["traced_pnl_row_count"] == 3
    assert result["summary"]["untraced_pnl_row_count"] == 1
    get_settings.cache_clear()


def test_pnl_by_business_ytd_total_matches_formal_fact_rollups(tmp_path, monkeypatch):
    """默认 formal 路径：YTD 总损益应等于 FI + nonstd 桥接在 as_of 前的累计（与物化口径一致）。"""
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business_ytd"
    result = payload["result"]
    repo_mod = load_module("backend.app.repositories.pnl_repo", "backend/app/repositories/pnl_repo.py")
    repo = repo_mod.PnlRepository(str(duckdb_path))
    expected = repo.sum_formal_total_pnl_through_report_date("2025-12-31") + repo.sum_nonstd_bridge_total_pnl_through_report_date(
        "2025-12-31"
    )
    assert Decimal(str(result["total_pnl"])) == expected.quantize(Decimal("0.01"))
    assert result["period_start_date"] == "2025-12-01"
    assert result["period_end_date"] == "2025-12-31"
    assert "fact_formal_pnl_fi" in result["source_tables"]
    get_settings.cache_clear()


def test_pnl_by_business_ytd_formal_path_classifies_nonstd_prefix_rows(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows = [
            ("SA001", "20.00", "0.00", "0.00", "20.00"),
            ("G0001", "7.00", "0.00", "0.00", "7.00"),
            ("J4001", "11.00", "0.00", "0.00", "11.00"),
            ("J1001", "14.00", "0.00", "0.00", "14.00"),
            ("J02205260102", "0.00", "9.00", "0.00", "9.00"),
            ("J09999990102", "0.00", "0.00", "4.00", "4.00"),
            ("JM001", "10.00", "0.00", "0.00", "10.00"),
        ]
        conn.executemany(
            """
            insert into fact_nonstd_pnl_bridge values (
              '2025-12-31', ?, 'NonStd Desk', 'CC-PREFIX',
              ?, ?, ?, 0.00, ?,
              'sv-nonstd-prefix', 'rv_pnl_phase2_materialize_v1', 'ib-nonstd-prefix', 'tr-nonstd-prefix'
            )
            """,
            rows,
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})

    assert response.status_code == 200
    by_key = {item["row_key"]: item for item in response.json()["result"]["items"]}
    assert by_key["asset_zqtz_public_fund"]["total_pnl"] == "20.00"
    assert by_key["asset_zqtz_non_bottom_investment"]["total_pnl"] == "45.00"
    assert by_key["asset_zqtz_detail_trust_plan"]["total_pnl"] == "7.00"
    assert by_key["asset_zqtz_detail_securities_asset_management_plan"]["total_pnl"] == "38.00"
    assert by_key["asset_zqtz_detail_structured_finance_broker"]["total_pnl"] == "11.00"
    assert by_key["asset_zqtz_detail_foreign_currency_delegated"]["total_pnl"] == "14.00"
    assert by_key["asset_zqtz_detail_local_currency_delegated_market_value"]["total_pnl"] == "9.00"
    assert by_key["asset_zqtz_detail_local_currency_special_account_cost"]["total_pnl"] == "4.00"
    assert by_key["asset_zqtz_other_debt_financing"]["total_pnl"] == "10.00"
    get_settings.cache_clear()


def test_pnl_by_business_manual_adjustment_audit_tracks_current_and_events(
    tmp_path,
    monkeypatch,
    seed_wildcard_scope,
):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    create_response = client.post(
        "/api/pnl/by-business/manual-adjustments",
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "政策性金融债",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "125.50",
            "reason": "补录估值调整",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    adjustment_id = created["adjustment_id"]
    assert created["event_type"] == "created"
    assert created["manual_adjustment"] == "125.50"
    assert created["stream"] == "pnl_by_business_adjustments"

    edit_response = client.post(
        f"/api/pnl/by-business/manual-adjustments/{adjustment_id}/edit",
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "政策性金融债",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "150.00",
            "reason": "复核后修正",
        },
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["event_type"] == "edited"

    list_response = client.get(
        "/api/pnl/by-business/manual-adjustments",
        params={"report_date": "2025-12-31"},
    )

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["report_date"] == "2025-12-31"
    assert payload["adjustment_count"] == 1
    assert payload["event_total"] == 2
    assert payload["adjustments"][0]["adjustment_id"] == adjustment_id
    assert payload["adjustments"][0]["event_type"] == "edited"
    assert payload["adjustments"][0]["manual_adjustment"] == "150.00"
    assert [event["event_type"] for event in payload["events"]] == ["edited", "created"]
    get_settings.cache_clear()


def test_pnl_by_business_manual_adjustment_feeds_ytd_monthly_and_analysis(
    tmp_path,
    monkeypatch,
    seed_wildcard_scope,
):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi values (
              '2025-12-31', 'P001', 'Rate Desk', 'CC-RATE', 'T', 'FVTPL', 'CNY',
              100.00, 0.00, 25.50, 0.00, 125.50,
              'fi-policy-adjust-base', 'rv_pnl_phase2_materialize_v1', 'ib-policy-adjust-base', 'trace-policy-adjust-base'
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-12-31', 'P001', 'policy financial bond', 'Rate Desk', 'CC-RATE',
              'asset', '政策性金融债', '政策性金融债', '政策性金融债', '政策性金融债',
              'T', 'FVTPL', 'asset', 'CNY', 'CNY',
              1000.00000000, 1000.00000000, 0.00000000, false,
              'sv-policy-adjust-balance', 'rv-policy-adjust-balance', 'ib-policy-adjust-balance', 'trace-policy-adjust-balance'
            )
            """
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    create_response = client.post(
        "/api/pnl/by-business/manual-adjustments",
        json={
            "report_date": "2025-12-31",
            "row_key": "asset_zqtz_policy_financial_bond",
            "business_type": "政策性金融债",
            "operator": "DELTA",
            "approval_status": "approved",
            "manual_adjustment": "25.00",
            "reason": "补录政策性金融债调整",
        },
    )
    assert create_response.status_code == 200

    ytd_response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})
    assert ytd_response.status_code == 200
    ytd_result = ytd_response.json()["result"]
    ytd_by_key = {item["row_key"]: item for item in ytd_result["items"]}
    adjusted_ytd = ytd_by_key["asset_zqtz_policy_financial_bond"]
    assert adjusted_ytd["manual_adjustment"] == "25.00"
    assert adjusted_ytd["total_pnl"] == "150.50"
    assert ytd_result["total_pnl"] == "262.00"
    assert "pnl_by_business_adjustments" in ytd_result["source_tables"]

    monthly_response = client.get(
        "/api/pnl/by-business-monthly",
        params={"year": 2025, "as_of_date": "2025-12-31"},
    )
    assert monthly_response.status_code == 200
    month = monthly_response.json()["result"]["months"][0]
    monthly_by_key = {item["row_key"]: item for item in month["items"]}
    assert monthly_by_key["asset_zqtz_policy_financial_bond"]["manual_adjustment"] == "25.00"
    assert monthly_by_key["asset_zqtz_policy_financial_bond"]["total_pnl"] == "150.50"
    assert month["summary"]["manual_adjustment"] == "25.00"

    analysis_response = client.get(
        "/api/pnl/by-business-analysis",
        params={
            "year": 2025,
            "as_of_date": "2025-12-31",
            "business_key": "asset_zqtz_policy_financial_bond",
            "dimension": "monthly",
        },
    )
    assert analysis_response.status_code == 200
    analysis_row = analysis_response.json()["result"]["rows"][0]
    assert analysis_row["manual_adjustment"] == "25.00"
    assert analysis_row["total_pnl"] == "150.50"
    get_settings.cache_clear()


def test_pnl_by_business_analysis_contract_reconciles_selected_business(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    classification = _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    other_type = classification["other_type"]
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows = [
            ("SA001", "20.00", "0.00", "0.00", "20.00"),
            ("G0001", "7.00", "0.00", "0.00", "7.00"),
            ("J4001", "11.00", "0.00", "0.00", "11.00"),
            ("J1001", "14.00", "0.00", "0.00", "14.00"),
            ("J02205260102", "0.00", "9.00", "0.00", "9.00"),
            ("J09999990102", "0.00", "0.00", "4.00", "4.00"),
            ("JM001", "10.00", "0.00", "0.00", "10.00"),
        ]
        conn.executemany(
            """
            insert into fact_nonstd_pnl_bridge values (
              '2025-12-31', ?, 'NonStd Desk', 'CC-PREFIX',
              ?, ?, ?, 0.00, ?,
              'sv-nonstd-analysis', 'rv_pnl_phase2_materialize_v1', 'ib-nonstd-analysis', 'tr-nonstd-analysis'
            )
            """,
            rows,
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-01",
                    "J4001",
                    "J4 structured",
                    "NonStd Desk",
                    "CC-J4",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "500.00000000",
                    "500.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j4-prior",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j4-prior",
                ),
                (
                    "2025-12-01",
                    "J1001",
                    "J1 delegated",
                    "NonStd Desk",
                    "CC-J1",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "USD",
                    "1000.00000000",
                    "1000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j1-prior",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j1-prior",
                ),
                (
                    "2025-12-01",
                    "J02205260102",
                    "J0 market",
                    "NonStd Desk",
                    "CC-J0-M",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "H",
                    "AC",
                    "asset",
                    "CNY",
                    "CNY",
                    "1500.00000000",
                    "1500.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j0-market-prior",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j0-market-prior",
                ),
                (
                    "2025-12-01",
                    "J09999990102",
                    "J0 cost",
                    "NonStd Desk",
                    "CC-J0-C",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "H",
                    "AC",
                    "asset",
                    "CNY",
                    "CNY",
                    "2000.00000000",
                    "2000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j0-cost-prior",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j0-cost-prior",
                ),
            ],
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    ytd_response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})
    assert ytd_response.status_code == 200
    ytd_by_key = {item["row_key"]: item for item in ytd_response.json()["result"]["items"]}

    response = client.get(
        "/api/pnl/by-business-analysis",
        params={
            "year": 2025,
            "as_of_date": "2025-12-31",
            "business_key": "asset_zqtz_detail_securities_asset_management_plan",
            "dimension": "portfolio",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business_analysis"
    result = payload["result"]
    assert result["dimension"] == "portfolio"
    assert result["business_key"] == "asset_zqtz_detail_securities_asset_management_plan"
    assert result["period_start_date"] == "2025-12-01"
    assert result["period_end_date"] == "2025-12-31"
    assert "ZQTZ_ASSET_BOND_ROWS" in result["source_tables"]
    assert set(result["rows"][0]) == {
        "dimension_key",
        "dimension_label",
        "interest_income",
        "fair_value_change",
        "capital_gain",
        "manual_adjustment",
        "total_pnl",
        "avg_balance",
        "current_balance",
        "annualized_yield_pct",
        "ftp_rate_pct",
        "ftp_cost",
        "ftp_net_pnl",
        "ftp_net_annualized_yield_pct",
        "asset_count",
    }
    row = result["rows"][0]
    assert row["dimension_key"] == "NonStd Desk"
    assert row["total_pnl"] == ytd_by_key["asset_zqtz_detail_securities_asset_management_plan"]["total_pnl"]
    assert row["total_pnl"] == "38.00"
    assert row["avg_balance"] == "7500.00"
    assert row["current_balance"] == "10012.00"
    assert row["avg_balance"] != row["current_balance"]
    assert row["annualized_yield_pct"] == "5.965591"
    assert row["ftp_rate_pct"] == "1.600000"
    assert row["ftp_cost"] == "10.19"
    assert row["ftp_net_pnl"] == "27.81"
    assert row["ftp_net_annualized_yield_pct"] == "4.365591"
    assert row["asset_count"] == 4

    empty_response = client.get(
        "/api/pnl/by-business-analysis",
        params={
            "year": 2025,
            "as_of_date": "2025-12-31",
            "business_key": "missing-business-key",
            "dimension": "portfolio",
        },
    )
    assert empty_response.status_code == 200
    assert empty_response.json()["result"]["rows"] == []

    invalid_response = client.get(
        "/api/pnl/by-business-analysis",
        params={"year": 2025, "as_of_date": "2025-12-31", "dimension": "bad"},
    )
    assert invalid_response.status_code == 422
    get_settings.cache_clear()


def test_pnl_by_business_analysis_bond_bucket_and_ftp_contract(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    classification = _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    other_type = classification["other_type"]
    monkeypatch.setenv("MOSS_PNL_BY_BUSINESS_YTD_PREFER_FORMAL_FACTS", "true")
    get_settings.cache_clear()

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("delete from fact_formal_pnl_fi where substr(cast(report_date as varchar), 1, 4) = '2025'")
        conn.execute("delete from fact_nonstd_pnl_bridge where substr(cast(report_date as varchar), 1, 4) = '2025'")
        conn.execute(
            "delete from fact_formal_zqtz_balance_daily where substr(cast(report_date as varchar), 1, 4) = '2025'"
        )
        conn.executemany(
            """
            insert into fact_formal_pnl_fi values (
              '2025-12-31', ?, ?, ?, 'T', 'FVTPL', 'CNY',
              ?, 0.00, 0.00, 0.00, ?,
              'fi-bucket-v1', 'rv_pnl_phase2_materialize_v1', 'ib-bucket', 'trace-fi-bucket'
            )
            """,
            [
                ("P001", "Rate Desk", "CC-RATE", "100.00", "100.00"),
                ("E001", "Credit Desk", "CC-ENT", "30.00", "30.00"),
                ("ABS001", "Credit Desk", "CC-ABS", "50.00", "50.00"),
                ("C001", "Financial Desk", "CC-COM", "40.00", "40.00"),
                ("NCD001", "Financial Desk", "CC-NCD", "60.00", "60.00"),
                ("J0001", "Other Desk", "CC-J", "70.00", "70.00"),
                ("U001", "No Balance", "CC-U", "10.00", "10.00"),
            ],
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-12-31', ?, ?, ?, ?, 'asset', ?, ?, ?, ?,
              'T', 'FVTPL', 'asset', 'CNY', 'CNY',
              ?, ?, 0.00000000, false,
              'sv-z-bucket', 'rv-z-bucket', 'ib-z-bucket', 'trace-z-bucket'
            )
            """,
            [
                ("P001", "policy financial bond", "Rate Desk", "CC-RATE", "政策性金融债", "政策性金融债", "政策性金融债", "政策性金融债", "1000.00000000", "1000.00000000"),
                ("E001", "enterprise bond", "Credit Desk", "CC-ENT", "企业债", "企业债", "企业债", "企业债", "2000.00000000", "2000.00000000"),
                ("ABS001", "asset backed security", "Credit Desk", "CC-ABS", "资产支持证券", "资产支持证券", "资产支持证券", "资产支持证券", "3000.00000000", "3000.00000000"),
                ("C001", "commercial financial bond", "Financial Desk", "CC-COM", "商业性金融债", "商业性金融债", "商业性金融债", "商业性金融债", "4000.00000000", "4000.00000000"),
                ("NCD001", "interbank cd", "Financial Desk", "CC-NCD", "同业存单", "同业存单", "同业存单", "同业存单", "5000.00000000", "5000.00000000"),
                ("J0001", "non bottom asset", "Other Desk", "CC-J", other_type, other_type, other_type, other_type, "6000.00000000", "6000.00000000"),
            ],
        )
    finally:
        conn.close()

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    ytd_response = client.get("/api/pnl/by-business-ytd", params={"year": 2025, "as_of_date": "2025-12-31"})
    assert ytd_response.status_code == 200
    assert ytd_response.json()["result"]["total_pnl"] == "360.00"

    response = client.get(
        "/api/pnl/by-business-analysis",
        params={"year": 2025, "as_of_date": "2025-12-31", "dimension": "bond_bucket"},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["dimension"] == "bond_bucket"
    by_label = {row["dimension_label"]: row for row in result["rows"]}
    assert list(by_label) == ["利率债", "信用债", "金融债", "其它债券"]
    assert by_label["利率债"]["total_pnl"] == "100.00"
    assert by_label["信用债"]["total_pnl"] == "80.00"
    assert by_label["金融债"]["total_pnl"] == "100.00"
    assert by_label["其它债券"]["total_pnl"] == "80.00"
    assert sum(Decimal(row["total_pnl"]) for row in result["rows"]) == Decimal("360.00")
    assert by_label["利率债"]["avg_balance"] == "1000.00"
    assert by_label["利率债"]["current_balance"] == "1000.00"
    assert by_label["利率债"]["annualized_yield_pct"] == "117.741935"
    assert by_label["利率债"]["ftp_rate_pct"] == "1.600000"
    assert by_label["利率债"]["ftp_cost"] == "1.36"
    assert by_label["利率债"]["ftp_net_pnl"] == "98.64"
    assert by_label["利率债"]["ftp_net_annualized_yield_pct"] == "116.141935"

    trend_response = client.get(
        "/api/pnl/by-business-analysis",
        params={"year": 2025, "as_of_date": "2025-12-31", "dimension": "bond_bucket_monthly"},
    )
    assert trend_response.status_code == 200
    trend_result = trend_response.json()["result"]
    assert trend_result["dimension"] == "bond_bucket_monthly"
    trend_by_key = {row["dimension_key"]: row for row in trend_result["rows"]}
    assert list(trend_by_key) == [
        "2025-12-31::rate_bond",
        "2025-12-31::credit_bond",
        "2025-12-31::financial_bond",
        "2025-12-31::other_bond",
    ]
    assert trend_by_key["2025-12-31::rate_bond"]["dimension_label"] == "2025-12-31 利率债"
    assert trend_by_key["2025-12-31::rate_bond"]["total_pnl"] == "100.00"
    assert trend_by_key["2025-12-31::rate_bond"]["avg_balance"] == "1000.00"
    assert trend_by_key["2025-12-31::rate_bond"]["ftp_net_pnl"] == "98.64"

    no_avg_response = client.get(
        "/api/pnl/by-business-analysis",
        params={"year": 2025, "as_of_date": "2025-12-31", "dimension": "portfolio"},
    )
    assert no_avg_response.status_code == 200
    by_portfolio = {row["dimension_label"]: row for row in no_avg_response.json()["result"]["rows"]}
    assert by_portfolio["No Balance"]["avg_balance"] == "0.00"
    assert by_portfolio["No Balance"]["current_balance"] == "0.00"
    assert by_portfolio["No Balance"]["annualized_yield_pct"] is None
    assert by_portfolio["No Balance"]["ftp_cost"] is None
    assert by_portfolio["No Balance"]["ftp_net_pnl"] is None
    assert by_portfolio["No Balance"]["ftp_net_annualized_yield_pct"] is None
    get_settings.cache_clear()


def test_pnl_by_business_keeps_same_instrument_positions_separate(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi values (
              '2025-12-31', '240001.IB', 'Other Desk', 'CC300', 'T', 'FVTPL', 'CNY',
              20.00, 0.00, 0.00, 0.00, 20.00,
              'fi-same-instrument-v1', 'rv_pnl_phase2_materialize_v1', 'ib-same-instrument', 'trace-fi-same-instrument'
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-12-31', '240001.IB', 'Other Desk', 'CC300', 'bond-hedging',
              'T', 'FVTPL', 'asset', 'CNY', 'CNY', 200.00, 200.00, 0.00, false,
              'sv-z-hedge', 'rv-z-biz', 'ib-z-hedge', 'trace-z-hedge'
            )
            """
        )
    finally:
        conn.close()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/by-business", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    result = response.json()["result"]
    by_business = {row["business_type_primary"]: row for row in result["rows"]}
    assert by_business["bond-trading"]["total_pnl"] == "111.50"
    assert by_business["bond-trading"]["scale_amount"] == "1099.00"
    assert by_business["bond-hedging"]["total_pnl"] == "20.00"
    assert by_business["bond-hedging"]["scale_amount"] == "200.00"
    assert by_business["bond-hedging"]["pnl_row_count"] == 1
    get_settings.cache_clear()


def test_pnl_by_business_daily_uses_formal_facts_not_refresh_source_override(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    pnl_repo_module = load_module("backend.app.repositories.pnl_repo", "backend/app/repositories/pnl_repo.py")
    source_service = load_module(
        "backend.app.services.pnl_source_service",
        "backend/app/services/pnl_source_service.py",
    )

    class AlwaysDefaultPath:
        def __init__(self, *_args):
            pass

        def resolve(self):
            return "data/moss.duckdb"

    class FakeRefreshInput:
        fi_rows = [
            {
                "instrument_code": "250002.IB",
                "currency_basis": "CNY",
                "invest_type_raw": "source-only",
                "interest_income_514": Decimal("999.00"),
                "fair_value_change_516": Decimal("0.00"),
                "capital_gain_517": Decimal("0.00"),
                "manual_adjustment": Decimal("0.00"),
            }
        ]

    monkeypatch.setattr(pnl_repo_module, "Path", AlwaysDefaultPath, raising=False)
    monkeypatch.setattr(
        source_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: FakeRefreshInput(),
    )

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    rows = repo.fetch_by_business_rows("2025-12-31")
    total = sum((Decimal(str(row["total_pnl"])) for row in rows), Decimal("0"))
    by_business = {str(row["business_type_primary"]): row for row in rows}

    assert total == Decimal("125.50000000")
    assert Decimal(str(by_business["bond-trading"]["scale_amount"])) == Decimal("1099.00000000")
    assert "source-only" not in by_business


def test_pnl_by_business_ytd_uses_v1_formula_and_balance_movement_rows(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    classification = _seed_pnl_by_business_ytd_balance_rows(duckdb_path)
    _force_pnl_ytd_refresh_bundle_contract(monkeypatch)

    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")
    enterprise_type = classification["enterprise_type"]
    commercial_type = classification["commercial_type"]

    class FakeRefreshInput:
        report_date = "2025-12-31"
        is_month_end = True

        def __init__(self):
            self.fi_rows = [
                {
                    "instrument_code": "E001",
                    "asset_class": enterprise_type,
                    "interest_income_514": Decimal("106.00"),
                    "fair_value_change_516": Decimal("3.00"),
                    "capital_gain_517": Decimal("10.00"),
                    "source_version": "sv-fi-enterprise",
                },
                {
                    "instrument_code": "C001",
                    "asset_class": commercial_type,
                    "interest_income_514": Decimal("40.00"),
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "source_version": "sv-fi-commercial",
                },
            ]
            self.nonstd_rows_by_type = {
                "514": [
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "J4001",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("11.00"),
                        "source_version": "sv-nonstd-j4",
                    },
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "J1001",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("2.00"),
                        "source_version": "sv-nonstd-j1",
                    },
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "JM001",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("10.60"),
                        "source_version": "sv-nonstd-jm",
                    },
                ],
                "516": [
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "J02205260102",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("9.00"),
                        "source_version": "sv-nonstd-j0-market",
                    }
                ],
                "517": [
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "J09999990102",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("4.00"),
                        "source_version": "sv-nonstd-j0-cost",
                    },
                    {
                        "voucher_date": "2025-12-31",
                        "asset_code": "SA001",
                        "dc_flag": "credit",
                        "raw_amount": Decimal("20.00"),
                        "source_version": "sv-nonstd-sa",
                    },
                ],
            }

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: FakeRefreshInput(),
    )
    monkeypatch.setattr(
        pnl_service,
        "list_pnl_refresh_report_dates",
        lambda **_kwargs: ["2025-12-31"],
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/by-business-ytd", params={"year": 2025})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business_ytd"
    result = payload["result"]
    assert result["year"] == 2025
    assert result["period_label"].startswith("2025")
    assert "fact_formal_zqtz_balance_daily" in result["source_tables"]
    assert "ZQTZ_ASSET_BOND_ROWS" in result["source_tables"]
    assert [item["sort_order"] for item in result["items"]] == sorted(item["sort_order"] for item in result["items"])

    by_key = {item["row_key"]: item for item in result["items"]}
    assert by_key["asset_zqtz_nonfinancial_enterprise_bond"]["interest_income"] == "100.00"
    assert by_key["asset_zqtz_nonfinancial_enterprise_bond"]["fair_value_change"] == "3.00"
    assert by_key["asset_zqtz_nonfinancial_enterprise_bond"]["capital_gain"] == "-9.43"
    assert by_key["asset_zqtz_nonfinancial_enterprise_bond"]["total_pnl"] == "93.57"
    assert by_key["asset_zqtz_commercial_financial_bond"]["total_pnl"] == "40.00"
    assert by_key["asset_zqtz_public_fund"]["total_pnl"] == "20.00"
    assert by_key["asset_zqtz_other_debt_financing"]["total_pnl"] == "10.00"

    assert by_key["asset_zqtz_non_bottom_investment"]["total_pnl"] == "38.00"
    assert by_key["asset_zqtz_detail_securities_asset_management_plan"]["total_pnl"] == "38.00"
    assert by_key["asset_zqtz_detail_structured_finance_broker"]["total_pnl"] == "11.00"
    assert by_key["asset_zqtz_detail_foreign_currency_delegated"]["total_pnl"] == "14.00"
    assert by_key["asset_zqtz_detail_local_currency_delegated_market_value"]["total_pnl"] == "9.00"
    assert by_key["asset_zqtz_detail_local_currency_special_account_cost"]["total_pnl"] == "4.00"

    assert by_key["asset_zqtz_non_bottom_investment"]["current_balance"] == "10012.00"
    assert by_key["asset_zqtz_detail_securities_asset_management_plan"]["current_balance"] == "10012.00"
    assert by_key["asset_zqtz_detail_structured_finance_broker"]["current_balance"] == "1005.00"
    assert by_key["asset_zqtz_detail_foreign_currency_delegated"]["current_balance"] == "2000.00"
    assert by_key["asset_zqtz_detail_local_currency_delegated_market_value"]["current_balance"] == "3007.00"
    assert by_key["asset_zqtz_detail_local_currency_special_account_cost"]["current_balance"] == "4000.00"
    assert by_key["asset_zqtz_detail_structured_finance_broker"]["balance_yield_pct"] == "1.094527"
    assert by_key["asset_zqtz_central_bank_bill"]["balance_yield_pct"] is None
    assert result["total_pnl"] == "201.57"

    # 不变量：payload.total_pnl = 各条 V1 记录 total_pnl 之和（每条资产/凭证一条）；因 ZQTZ 多行命中，
    # items 各行 total_pnl 之和可大于该值（父级+其中重复分摊）。
    repo_mod = load_module("backend.app.repositories.pnl_repo", "backend/app/repositories/pnl_repo.py")
    repo = repo_mod.PnlRepository(str(duckdb_path))
    sub_map = repo.fetch_zqtz_sub_type_map(["2025-12-31"])
    fx_rates = repo.fetch_latest_fx_rates("2025-12-31", {"USD"})
    fake_in = FakeRefreshInput()
    v1_record_total = sum(
        Decimal(str(record["total_pnl"]))
        for record in pnl_service._iter_v1_compatible_pnl_records(
            report_date="2025-12-31",
            refresh_input=fake_in,
            sub_type_map=sub_map,
            fx_rates=fx_rates,
        )
    )
    assert v1_record_total.quantize(Decimal("0.01")) == Decimal(result["total_pnl"])
    items_total = sum(Decimal(item["total_pnl"]) for item in result["items"])
    assert items_total > v1_record_total.quantize(Decimal("0.01"))

    get_settings.cache_clear()


def legacy_pnl_by_business_ytd_uses_v1_import_formula_and_sub_type_mapping(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _force_pnl_ytd_refresh_bundle_contract(monkeypatch)
    _seed_pnl_by_business_rows(duckdb_path)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set sub_type = business_type_primary
            where report_date = '2025-12-31'
            """
        )
    finally:
        conn.close()

    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    class FakeRefreshInput:
        fi_rows = [
            {
                "instrument_code": "240001.IB",
                "asset_class": "企业债",
                "interest_income_514": Decimal("106.00"),
                "fair_value_change_516": Decimal("3.00"),
                "capital_gain_517": Decimal("10.00"),
                "source_version": "sv-fi",
            },
            {
                "instrument_code": "NO-ZQTZ.IB",
                "asset_class": "大额存单",
                "interest_income_514": Decimal("106.00"),
                "fair_value_change_516": Decimal("0.00"),
                "capital_gain_517": Decimal("0.00"),
                "source_version": "sv-fi",
            },
        ]
        nonstd_rows_by_type = {
            "514": [
                {
                    "voucher_date": "2025-12-15",
                    "asset_code": "JM001",
                    "dc_flag": "贷",
                    "raw_amount": Decimal("106.00"),
                    "source_version": "sv-nonstd-514",
                },
                {
                    "voucher_date": "2025-12-15",
                    "asset_code": "G0001",
                    "dc_flag": "贷",
                    "raw_amount": Decimal("7.00"),
                    "source_version": "sv-nonstd-514",
                },
            ],
            "517": [
                {
                    "voucher_date": "2025-12-16",
                    "asset_code": "SA001",
                    "dc_flag": "贷",
                    "raw_amount": Decimal("20.00"),
                    "source_version": "sv-nonstd-517",
                }
            ],
        }

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: FakeRefreshInput(),
    )
    monkeypatch.setattr(
        pnl_service,
        "list_pnl_refresh_report_dates",
        lambda **_kwargs: ["2025-12-31"],
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/by-business-ytd", params={"year": 2025})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.by_business_ytd"
    result = payload["result"]
    assert result["year"] == 2025
    assert result["period_label"] == "2025年12月累计"
    by_business = {item["business_type"]: item for item in result["items"]}
    assert by_business["bond-trading"]["interest_income"] == "100.00"
    assert by_business["bond-trading"]["fair_value_change"] == "3.00"
    assert by_business["bond-trading"]["capital_gain"] == "-9.43"
    assert by_business["bond-trading"]["total_pnl"] == "93.57"
    assert by_business["同业存单"]["total_pnl"] == "100.00"
    assert by_business["债权投资"]["total_pnl"] == "100.00"
    assert by_business["信托结构化产品"]["total_pnl"] == "7.00"
    assert by_business["公募基金"]["total_pnl"] == "20.00"
    assert result["total_pnl"] == "320.57"
    get_settings.cache_clear()


def test_pnl_by_business_ytd_respects_as_of_date_cutoff(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    _force_pnl_ytd_refresh_bundle_contract(monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    class FakeRefreshInput:
        nonstd_rows_by_type: dict[str, list[dict[str, object]]] = {}

        def __init__(self, report_date: str):
            amount = Decimal("10.00") if report_date == "2026-01-31" else Decimal("20.00")
            self.report_date = report_date
            self.is_month_end = True
            self.fi_rows = [
                {
                    "instrument_code": "250001.IB",
                    "asset_class": "政策性金融债",
                    "interest_income_514": amount,
                    "fair_value_change_516": Decimal("0.00"),
                    "capital_gain_517": Decimal("0.00"),
                    "source_version": f"sv-{report_date}",
                }
            ]

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **kwargs: FakeRefreshInput(str(kwargs["report_date"])),
    )
    monkeypatch.setattr(
        pnl_service,
        "list_pnl_refresh_report_dates",
        lambda **_kwargs: ["2026-02-28", "2026-01-31"],
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    cutoff_response = client.get(
        "/api/pnl/by-business-ytd",
        params={"year": 2026, "as_of_date": "2026-01-31"},
    )
    full_response = client.get("/api/pnl/by-business-ytd", params={"year": 2026})

    assert cutoff_response.status_code == 200
    assert full_response.status_code == 200
    cutoff_result = cutoff_response.json()["result"]
    full_result = full_response.json()["result"]
    assert cutoff_result["period_label"] == "2026年01月累计"
    assert cutoff_result["period_start_date"] == "2026-01-01"
    assert cutoff_result["period_end_date"] == "2026-01-31"
    assert cutoff_result["total_pnl"] == "10.00"
    assert full_result["period_label"] == "2026年01-02月累计"
    assert full_result["period_start_date"] == "2026-01-01"
    assert full_result["period_end_date"] == "2026-02-28"
    assert full_result["total_pnl"] == "30.00"
    get_settings.cache_clear()


def test_pnl_v1_data_returns_v1_detail_formula_rows(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    pnl_service = load_module("backend.app.services.pnl_service", "backend/app/services/pnl_service.py")

    class FakeRefreshInput:
        report_date = "2025-12-31"
        is_month_end = True
        fi_rows = [
            {
                "instrument_code": "240001.IB",
                "instrument_name": "Test FI",
                "portfolio_name": "FI Desk",
                "asset_class": "企业债",
                "interest_income_514": Decimal("106.00"),
                "fair_value_change_516": Decimal("3.00"),
                "capital_gain_517": Decimal("10.00"),
                "source_version": "sv-fi",
                "trace_id": "tr-fi",
            }
        ]
        nonstd_rows_by_type = {
            "514": [
                {
                    "voucher_date": "2025-12-15",
                    "asset_code": "JM001",
                    "portfolio_name": "NonStd Desk",
                    "dc_flag": "贷",
                    "raw_amount": Decimal("106.00"),
                    "source_version": "sv-nonstd-514",
                    "trace_id": "tr-nonstd-514",
                }
            ],
            "517": [
                {
                    "voucher_date": "2025-12-16",
                    "asset_code": "JM001",
                    "portfolio_name": "NonStd Desk",
                    "dc_flag": "贷",
                    "raw_amount": Decimal("20.00"),
                    "source_version": "sv-nonstd-517",
                    "trace_id": "tr-nonstd-517",
                }
            ],
        }

    monkeypatch.setattr(
        pnl_service,
        "load_latest_pnl_refresh_input",
        lambda **_kwargs: FakeRefreshInput(),
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/v1-data", params={"date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.v1_data"
    rows = payload["result"]["rows"]
    by_code = {row["asset_code"]: row for row in rows}
    assert Decimal(by_code["240001.IB"]["interest_income"]).quantize(Decimal("0.01")) == Decimal("100.00")
    assert Decimal(by_code["240001.IB"]["fair_value_change"]).quantize(Decimal("0.01")) == Decimal("3.00")
    assert Decimal(by_code["240001.IB"]["capital_gain"]).quantize(Decimal("0.01")) == Decimal("-9.43")
    assert Decimal(by_code["240001.IB"]["total_pnl"]).quantize(Decimal("0.01")) == Decimal("93.57")
    assert Decimal(by_code["JM001"]["interest_income"]).quantize(Decimal("0.01")) == Decimal("100.00")
    assert Decimal(by_code["JM001"]["capital_gain"]).quantize(Decimal("0.01")) == Decimal("20.00")
    assert Decimal(by_code["JM001"]["total_pnl"]).quantize(Decimal("0.01")) == Decimal("120.00")
    get_settings.cache_clear()


def test_pnl_yearly_summary_groups_months_by_zqtz_business_type_primary(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    _seed_pnl_by_business_month(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get("/api/pnl/yearly-summary", params={"year": 2025})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "pnl.yearly_summary"
    rows = payload["result"]["rows"]
    assert [row["report_month"] for row in rows] == ["2025-11", "2025-12", "2025-12", "2025-12"]
    by_key = {(row["report_month"], row["business_type_primary"]): row for row in rows}
    assert by_key[("2025-11", "bond-trading")]["total_pnl"] == "6.00"
    assert by_key[("2025-12", "bond-trading")]["total_pnl"] == "111.50"
    assert by_key[("2025-12", "bond-allocation")]["total_pnl"] == "10.00"
    assert by_key[("2025-12", "H")]["total_pnl"] == "4.00"
    get_settings.cache_clear()


def test_yield_by_period_monthly_and_quarterly_rollups_from_formal_pnl(tmp_path, monkeypatch):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_pnl_by_business_rows(duckdb_path)
    _seed_pnl_by_business_month(duckdb_path)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    monthly = client.get("/api/analysis/yield-by-period", params={"year": 2025, "period_type": "monthly"})
    assert monthly.status_code == 200
    mbody = monthly.json()
    assert mbody["result_meta"]["result_kind"] == "liability_analytics.yield_by_period"
    mperiods = {p["period"]: p for p in mbody["result"]["periods"]}
    assert mperiods["2025-11"]["num_days"] == 30
    assert abs(float(mperiods["2025-11"]["total_pnl"]) - 6.0) < 1e-6
    assert mperiods["2025-12"]["num_days"] == 31
    assert abs(float(mperiods["2025-12"]["total_pnl"]) - 125.5) < 1e-6

    quarterly = client.get("/api/analysis/yield-by-period", params={"year": 2025, "period_type": "quarterly"})
    assert quarterly.status_code == 200
    qperiods = {p["period"]: p for p in quarterly.json()["result"]["periods"]}
    q4 = qperiods["2025-Q4"]
    assert q4["start_date"] == "2025-10-01"
    assert abs(float(q4["total_pnl"]) - 131.5) < 1e-6

    yearly = client.get("/api/analysis/yield-by-period", params={"year": 2025, "period_type": "yearly"})
    assert yearly.status_code == 200
    yrows = yearly.json()["result"]["periods"]
    assert len(yrows) == 1
    assert yrows[0]["period"] == "2025"
    assert abs(float(yrows[0]["total_pnl"]) - 131.5) < 1e-6
    get_settings.cache_clear()


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


def test_pnl_refresh_report_date_uses_covering_nonstd_range_when_exact_month_end_missing(
    tmp_path,
    monkeypatch,
):
    _configure_refresh_sources(tmp_path, monkeypatch)
    _copy_fi_refresh_source(tmp_path, month_key="202601")
    _write_nonstd_refresh_workbook(
        tmp_path / "data_input" / "pnl_516" / "非标516-20260101-0228.xlsx",
        row_dates=("2026-01-30", "2026-02-28"),
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
    nonstd_rows = queued_messages[0]["nonstd_rows_by_type"]["516"]
    assert [row["voucher_date"] for row in nonstd_rows] == ["2026-01-30"]
    assert nonstd_rows[0]["source_file"] == "非标516-20260101-0228.xlsx"
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


def _seed_pnl_by_business_rows(duckdb_path: Path) -> None:
    repo_module = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        repo_module.ensure_balance_analysis_tables(conn)
        conn.execute("delete from fact_formal_zqtz_balance_daily where report_date = '2025-12-31'")
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-31",
                    "001",
                    "FI Desk",
                    "CC100",
                    "bond-trading",
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "100.00000000",
                    "99.00000000",
                    "2.00000000",
                    False,
                    "sv-z-biz",
                    "rv-z-biz",
                    "ib-z-biz",
                    "trace-z-biz-1",
                ),
                (
                    "2025-12-31",
                    "240001.IB",
                    "FI Desk",
                    "CC100",
                    "bond-trading",
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "999.00000000",
                    "998.00000000",
                    "9.00000000",
                    False,
                    "sv-z-biz-dup",
                    "rv-z-biz",
                    "ib-z-biz-dup",
                    "trace-z-biz-dup",
                ),
                (
                    "2025-12-31",
                    "250002.IB",
                    "FI Desk",
                    "CC200",
                    "bond-allocation",
                    "H",
                    "AC",
                    "asset",
                    "CNY",
                    "CNY",
                    "300.00000000",
                    "300.00000000",
                    "3.00000000",
                    False,
                    "sv-z-biz",
                    "rv-z-biz",
                    "ib-z-biz",
                    "trace-z-biz-2",
                ),
            ],
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values (
              '2025-12-31', '250002.IB', 'FI Desk', 'CC200', 'H', 'AC', 'CNY',
              8.00, 0.00, 2.00, 0.00, 10.00,
              'fi-extra-v1', 'rv_pnl_phase2_materialize_v1', 'ib-extra', 'trace-fi-extra'
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values (
              '2025-12-31', 'NO-ZQTZ.IB', 'FI Desk', 'CC999', 'H', 'AC', 'CNY',
              4.00, 0.00, 0.00, 0.00, 4.00,
              'fi-unmatched-v1', 'rv_pnl_phase2_materialize_v1', 'ib-unmatched', 'trace-fi-unmatched'
            )
            """
        )
    finally:
        conn.close()


def _seed_pnl_by_business_ytd_balance_rows(duckdb_path: Path) -> dict[str, str]:
    repo_module = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    category_module = load_module(
        "backend.app.core_finance.zqtz_asset_bond_category",
        "backend/app/core_finance/zqtz_asset_bond_category.py",
    )
    row_defs = {str(row["row_key"]): row for row in category_module.ZQTZ_ASSET_BOND_ROWS}
    other_type = str(row_defs["asset_zqtz_non_bottom_investment"]["bond_types"][0])
    enterprise_type = str(row_defs["asset_zqtz_nonfinancial_enterprise_bond"]["match_keywords"][1])
    commercial_type = str(row_defs["asset_zqtz_commercial_financial_bond"]["match_keywords"][2])
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        repo_module.ensure_balance_analysis_tables(conn)
        conn.execute("delete from fact_formal_zqtz_balance_daily where report_date = '2025-12-31'")
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
        conn.execute("delete from fx_daily_mid where trade_date = '2025-12-31'")
        conn.execute(
            """
            insert into fx_daily_mid (trade_date, base_currency, quote_currency, mid_rate, source_version)
            values ('2025-12-31', 'USD', 'CNY', 7.00000000, 'sv_fx_ytd_balance')
            """
        )
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, sub_type, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2025-12-31",
                    "J4001",
                    "J4 structured",
                    "NonStd Desk",
                    "CC-J4",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "1000.00000000",
                    "1000.00000000",
                    "5.00000000",
                    False,
                    "sv-z-j4",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j4",
                ),
                (
                    "2025-12-31",
                    "J1001",
                    "J1 delegated",
                    "NonStd Desk",
                    "CC-J1",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "USD",
                    "2000.00000000",
                    "2000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j1",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j1",
                ),
                (
                    "2025-12-31",
                    "J02205260102",
                    "J0 market",
                    "NonStd Desk",
                    "CC-J0-M",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "H",
                    "AC",
                    "asset",
                    "CNY",
                    "CNY",
                    "3000.00000000",
                    "3000.00000000",
                    "7.00000000",
                    False,
                    "sv-z-j0-market",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j0-market",
                ),
                (
                    "2025-12-31",
                    "J09999990102",
                    "J0 cost",
                    "NonStd Desk",
                    "CC-J0-C",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "H",
                    "AC",
                    "asset",
                    "CNY",
                    "CNY",
                    "4000.00000000",
                    "4000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-j0-cost",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-j0-cost",
                ),
                (
                    "2025-12-31",
                    "JM001",
                    "JM debt",
                    "NonStd Desk",
                    "CC-JM",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "5000.00000000",
                    "5000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-jm",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-jm",
                ),
                (
                    "2025-12-31",
                    "SA001",
                    "SA fund",
                    "NonStd Desk",
                    "CC-SA",
                    "asset",
                    other_type,
                    other_type,
                    other_type,
                    other_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "6000.00000000",
                    "6000.00000000",
                    "0.00000000",
                    False,
                    "sv-z-sa",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-sa",
                ),
                (
                    "2025-12-31",
                    "E001",
                    "enterprise bond",
                    "FI Desk",
                    "CC-E",
                    "asset",
                    enterprise_type,
                    enterprise_type,
                    enterprise_type,
                    enterprise_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "7000.00000000",
                    "7000.00000000",
                    "70.00000000",
                    False,
                    "sv-z-enterprise",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-enterprise",
                ),
                (
                    "2025-12-31",
                    "C001",
                    "commercial bank bond",
                    "FI Desk",
                    "CC-C",
                    "asset",
                    commercial_type,
                    commercial_type,
                    commercial_type,
                    commercial_type,
                    "T",
                    "FVTPL",
                    "asset",
                    "CNY",
                    "CNY",
                    "8000.00000000",
                    "8000.00000000",
                    "80.00000000",
                    False,
                    "sv-z-commercial",
                    "rv-z-ytd",
                    "ib-z-ytd",
                    "trace-z-commercial",
                ),
            ],
        )
    finally:
        conn.close()
    return {
        "enterprise_type": enterprise_type,
        "commercial_type": commercial_type,
        "other_type": other_type,
    }


def _seed_pnl_by_business_month(duckdb_path: Path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi values (
              '2025-11-30', '240001.IB', 'FI Desk', 'CC100', 'T', 'FVTPL', 'CNY',
              5.00, 1.00, 0.00, 0.00, 6.00,
              'fi-nov-v1', 'rv_pnl_phase2_materialize_v1', 'ib-nov', 'trace-fi-nov'
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, business_type_primary,
              invest_type_std, accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values (
              '2025-11-30', '240001.IB', 'FI Desk', 'CC100', 'bond-trading',
              'T', 'FVTPL', 'asset', 'CNY', 'CNY', 80.00, 80.00, 1.00, false,
              'sv-z-nov', 'rv-z-nov', 'ib-z-nov', 'trace-z-nov'
            )
            """
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
