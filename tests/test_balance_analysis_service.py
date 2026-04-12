from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from tests.helpers import load_module
from tests.test_balance_analysis_api import _configure_and_materialize


def test_balance_analysis_overview_service_rejects_invalid_filters(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    with pytest.raises(ValueError, match="position_scope"):
        service_mod.balance_analysis_overview_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date="2025-12-31",
            position_scope="wrong-scope",
            currency_basis="CNY",
        )

    with pytest.raises(ValueError, match="currency_basis"):
        service_mod.balance_analysis_overview_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date="2025-12-31",
            position_scope="all",
            currency_basis="USD",
        )

    with pytest.raises(ValueError, match="position_scope"):
        service_mod.balance_analysis_basis_breakdown_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date="2025-12-31",
            position_scope="wrong-scope",
            currency_basis="CNY",
        )


def test_balance_analysis_service_uses_shared_formal_result_runtime_helper():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "balance_analysis_service.py"
    src = path.read_text(encoding="utf-8")

    assert "backend.app.services.formal_result_runtime" in src
    assert "backend.app.governance.formal_compute_lineage" in src
    assert "def _formal_result_meta" not in src
    assert "def _resolve_latest_balance_manifest_lineage" not in src
    assert "def _resolve_report_date_build_lineage" not in src


def test_balance_analysis_dates_envelope_uses_shared_manifest_lineage_helper(monkeypatch):
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    class FakeRepo:
        def __init__(self, duckdb_path: str) -> None:
            self.duckdb_path = duckdb_path

        def list_report_dates(self):
            return ["2025-12-31"]

    calls: list[dict[str, str]] = []

    monkeypatch.setattr(service_mod, "BalanceAnalysisRepository", FakeRepo)
    monkeypatch.setattr(
        service_mod,
        "resolve_formal_manifest_lineage",
        lambda **kwargs: calls.append(kwargs) or {
            "cache_key": service_mod.CACHE_KEY,
            "cache_version": "cv_balance_analysis_test",
            "source_version": "sv_balance_analysis_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_balance_analysis_test",
        },
    )

    payload = service_mod.balance_analysis_dates_envelope(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
    )

    assert calls == [
        {
            "governance_dir": "ignored-governance",
            "cache_key": service_mod.CACHE_KEY,
        }
    ]
    assert payload["result_meta"]["cache_version"] == "cv_balance_analysis_test"
    assert payload["result_meta"]["source_version"] == "sv_balance_analysis_test"
    assert payload["result_meta"]["rule_version"] == "rv_balance_analysis_test"
    assert payload["result"]["report_dates"] == ["2025-12-31"]


def test_balance_analysis_overview_envelope_uses_shared_completed_build_lineage_helper(monkeypatch):
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    class FakeRepo:
        def __init__(self, duckdb_path: str) -> None:
            self.duckdb_path = duckdb_path

        def list_report_dates(self):
            return ["2025-12-31"]

        def fetch_formal_overview(self, **kwargs):
            return {
                "report_date": "2025-12-31",
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "detail_row_count": 2,
                "summary_row_count": 2,
                "total_market_value_amount": "100.00000000",
                "total_amortized_cost_amount": "90.00000000",
                "total_accrued_interest_amount": "5.00000000",
                "rule_version": "rv_repo_fallback",
            }

    calls: list[dict[str, str]] = []

    monkeypatch.setattr(service_mod, "BalanceAnalysisRepository", FakeRepo)
    monkeypatch.setattr(
        service_mod,
        "resolve_completed_formal_build_lineage",
        lambda **kwargs: calls.append(kwargs) or {
            "cache_key": service_mod.CACHE_KEY,
            "cache_version": "cv_balance_analysis_test",
            "source_version": "sv_balance_analysis_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_balance_analysis_test",
            "report_date": "2025-12-31",
        },
    )

    payload = service_mod.balance_analysis_overview_envelope(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert calls == [
        {
            "governance_dir": "ignored-governance",
            "cache_key": service_mod.CACHE_KEY,
            "job_name": service_mod.BALANCE_ANALYSIS_JOB_NAME,
            "report_date": "2025-12-31",
        }
    ]
    assert payload["result_meta"]["cache_version"] == "cv_balance_analysis_test"
    assert payload["result_meta"]["source_version"] == "sv_balance_analysis_test"
    assert payload["result_meta"]["rule_version"] == "rv_balance_analysis_test"
    assert payload["result"]["detail_row_count"] == 2


def test_balance_analysis_summary_envelope_uses_shared_completed_build_lineage_helper(monkeypatch):
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    class FakeRepo:
        def __init__(self, duckdb_path: str) -> None:
            self.duckdb_path = duckdb_path

        def list_report_dates(self):
            return ["2025-12-31"]

        def fetch_formal_summary_table(self, **kwargs):
            return {
                "total_rows": 1,
                "rows": [
                    {
                        "row_key": "zqtz:test",
                        "source_family": "zqtz",
                        "display_name": "240001.IB",
                        "owner_name": "组合A",
                        "category_name": "CC100",
                        "position_scope": kwargs["position_scope"],
                        "currency_basis": kwargs["currency_basis"],
                        "invest_type_std": "A",
                        "accounting_basis": "FVOCI",
                        "detail_row_count": 1,
                        "market_value_amount": "100.00000000",
                        "amortized_cost_amount": "90.00000000",
                        "accrued_interest_amount": "5.00000000",
                    }
                ],
            }

    calls: list[dict[str, str]] = []

    monkeypatch.setattr(service_mod, "BalanceAnalysisRepository", FakeRepo)
    monkeypatch.setattr(
        service_mod,
        "resolve_completed_formal_build_lineage",
        lambda **kwargs: calls.append(kwargs) or {
            "cache_key": service_mod.CACHE_KEY,
            "cache_version": "cv_balance_analysis_test",
            "source_version": "sv_balance_analysis_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_balance_analysis_test",
            "report_date": "2025-12-31",
        },
    )

    payload = service_mod.balance_analysis_summary_envelope(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
        limit=10,
        offset=0,
    )

    assert calls == [
        {
            "governance_dir": "ignored-governance",
            "cache_key": service_mod.CACHE_KEY,
            "job_name": service_mod.BALANCE_ANALYSIS_JOB_NAME,
            "report_date": "2025-12-31",
        }
    ]
    assert payload["result_meta"]["cache_version"] == "cv_balance_analysis_test"
    assert payload["result_meta"]["source_version"] == "sv_balance_analysis_test"
    assert payload["result_meta"]["rule_version"] == "rv_balance_analysis_test"
    assert payload["result"]["total_rows"] == 1


def test_balance_analysis_basis_breakdown_envelope_uses_shared_completed_build_lineage_helper(monkeypatch):
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    class FakeRepo:
        def __init__(self, duckdb_path: str) -> None:
            self.duckdb_path = duckdb_path

        def list_report_dates(self):
            return ["2025-12-31"]

        def fetch_formal_basis_breakdown(self, **kwargs):
            return [
                {
                    "source_family": "zqtz",
                    "invest_type_std": "A",
                    "accounting_basis": "FVOCI",
                    "position_scope": kwargs["position_scope"],
                    "currency_basis": kwargs["currency_basis"],
                    "detail_row_count": 1,
                    "market_value_amount": "100.00000000",
                    "amortized_cost_amount": "90.00000000",
                    "accrued_interest_amount": "5.00000000",
                }
            ]

    calls: list[dict[str, str]] = []

    monkeypatch.setattr(service_mod, "BalanceAnalysisRepository", FakeRepo)
    monkeypatch.setattr(
        service_mod,
        "resolve_completed_formal_build_lineage",
        lambda **kwargs: calls.append(kwargs) or {
            "cache_key": service_mod.CACHE_KEY,
            "cache_version": "cv_balance_analysis_test",
            "source_version": "sv_balance_analysis_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_balance_analysis_test",
            "report_date": "2025-12-31",
        },
    )

    payload = service_mod.balance_analysis_basis_breakdown_envelope(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert calls == [
        {
            "governance_dir": "ignored-governance",
            "cache_key": service_mod.CACHE_KEY,
            "job_name": service_mod.BALANCE_ANALYSIS_JOB_NAME,
            "report_date": "2025-12-31",
        }
    ]
    assert payload["result_meta"]["cache_version"] == "cv_balance_analysis_test"
    assert payload["result_meta"]["source_version"] == "sv_balance_analysis_test"
    assert payload["result_meta"]["rule_version"] == "rv_balance_analysis_test"
    assert payload["result"]["rows"][0]["source_family"] == "zqtz"


def test_build_balance_workbook_payload_uses_shared_completed_build_lineage_helper(monkeypatch):
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    class FakeRepo:
        def __init__(self, duckdb_path: str) -> None:
            self.duckdb_path = duckdb_path

        def list_report_dates(self):
            return ["2025-12-31"]

        def fetch_formal_zqtz_rows(self, **kwargs):
            if kwargs["currency_basis"] == "native":
                return [
                    {
                        "report_date": "2025-12-31",
                        "instrument_code": "240001.IB",
                        "instrument_name": "测试债券",
                        "portfolio_name": "组合A",
                        "cost_center": "CC100",
                        "account_category": "可供出售类资产",
                        "asset_class": "信用债",
                        "bond_type": "企业债",
                        "issuer_name": "发行人A",
                        "industry_name": "工业",
                        "rating": "AAA",
                        "invest_type_std": "A",
                        "accounting_basis": "FVOCI",
                        "position_scope": kwargs["position_scope"],
                        "currency_basis": kwargs["currency_basis"],
                        "currency_code": "CNY",
                        "face_value_amount": "100.00000000",
                        "market_value_amount": "100.00000000",
                        "amortized_cost_amount": "90.00000000",
                        "accrued_interest_amount": "5.00000000",
                        "coupon_rate": "0.03000000",
                        "ytm_value": "0.03100000",
                        "maturity_date": "2026-12-31",
                        "interest_mode": "固定",
                        "is_issuance_like": False,
                        "overdue_principal_days": 0,
                        "overdue_interest_days": 0,
                        "value_date": "2025-12-31",
                        "customer_attribute": "internal",
                        "source_version": "sv_balance_analysis_test",
                        "rule_version": "rv_balance_analysis_test",
                        "ingest_batch_id": "ib-test",
                        "trace_id": "trace-test",
                    }
                ]
            return []

        def fetch_formal_tyw_rows(self, **kwargs):
            return []

    class FakeWorkbookModule:
        @staticmethod
        def build_balance_analysis_workbook_payload(**kwargs):
            return {
                "report_date": str(kwargs["report_date"]),
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "cards": [],
                "tables": [],
            }

    calls: list[dict[str, str]] = []

    monkeypatch.setattr(service_mod, "BalanceAnalysisRepository", FakeRepo)
    monkeypatch.setattr(
        service_mod.importlib,
        "import_module",
        lambda _name: FakeWorkbookModule,
    )
    monkeypatch.setattr(service_mod.importlib, "reload", lambda module: module)
    monkeypatch.setattr(
        service_mod,
        "resolve_completed_formal_build_lineage",
        lambda **kwargs: calls.append(kwargs) or {
            "cache_key": service_mod.CACHE_KEY,
            "cache_version": "cv_balance_analysis_test",
            "source_version": "sv_balance_analysis_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_balance_analysis_test",
            "report_date": "2025-12-31",
        },
    )

    workbook, build_lineage = service_mod._build_balance_workbook_payload(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert calls == [
        {
            "governance_dir": "ignored-governance",
            "cache_key": service_mod.CACHE_KEY,
            "job_name": service_mod.BALANCE_ANALYSIS_JOB_NAME,
            "report_date": "2025-12-31",
        }
    ]
    assert workbook["report_date"] == "2025-12-31"
    assert build_lineage is not None
    assert build_lineage["source_version"] == "sv_balance_analysis_test"


def test_balance_analysis_service_uses_persisted_cache_version_from_governance(
    tmp_path,
    monkeypatch,
):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    monkeypatch.setattr(
        service_mod,
        "CACHE_VERSION",
        "cv_balance_analysis_formal__rv_future_bump",
    )

    payload = service_mod.balance_analysis_overview_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert (
        payload["result_meta"]["cache_version"]
        == "cv_balance_analysis_formal__rv_balance_analysis_formal_materialize_v1"
    )
