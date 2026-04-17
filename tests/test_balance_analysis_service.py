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
    assert "build_formal_result_envelope_from_lineage" in src
    assert "def _formal_result_meta" not in src
    assert "def _resolve_latest_balance_manifest_lineage" not in src
    assert "def _resolve_report_date_build_lineage" not in src
    assert "def _resolve_balance_cache_version" not in src


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


def test_balance_analysis_decision_items_envelope_reads_generated_rows_from_workbook_helper(
    monkeypatch,
):
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    monkeypatch.setattr(
        service_mod,
        "_build_balance_workbook_payload",
        lambda **_kwargs: (
            {
                "report_date": "2025-12-31",
                "position_scope": "all",
                "currency_basis": "CNY",
                "cards": [],
                "tables": [
                    {
                        "key": "decision_items",
                        "title": "Decision Items",
                        "section_kind": "decision_items",
                        "columns": [
                            {"key": "title", "label": "Title"},
                            {"key": "action_label", "label": "Action"},
                            {"key": "severity", "label": "Severity"},
                            {"key": "reason", "label": "Reason"},
                            {"key": "source_section", "label": "Source Section"},
                            {"key": "rule_id", "label": "Rule Id"},
                            {"key": "rule_version", "label": "Rule Version"},
                        ],
                        "rows": [
                            {
                                "title": "Tighten duration gap",
                                "action_label": "Review",
                                "severity": "high",
                                "reason": "Gap widened",
                                "source_section": "maturity_gap",
                                "rule_id": "bal_gap_rule",
                                "rule_version": "rv-test",
                            }
                        ],
                    }
                ],
            },
            {
                "cache_key": service_mod.CACHE_KEY,
                "cache_version": "cv_balance_analysis_test",
                "source_version": "sv_balance_analysis_test",
                "vendor_version": "vv_none",
                "rule_version": "rv_balance_analysis_test",
                "report_date": "2025-12-31",
            },
        ),
    )

    class FakeDecisionRepo:
        def __init__(self, governance_dir: str) -> None:
            self.governance_dir = governance_dir

        def list_latest_statuses(self, **_kwargs):
            return {}

    monkeypatch.setattr(service_mod, "BalanceAnalysisDecisionRepository", FakeDecisionRepo)

    payload = service_mod.balance_analysis_decision_items_envelope(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert payload["result_meta"]["result_kind"] == "balance-analysis.decision-items"
    assert payload["result"]["columns"] == [
        {"key": "title", "label": "Title"},
        {"key": "action_label", "label": "Action"},
        {"key": "severity", "label": "Severity"},
        {"key": "reason", "label": "Reason"},
        {"key": "source_section", "label": "Source Section"},
        {"key": "rule_id", "label": "Rule Id"},
        {"key": "rule_version", "label": "Rule Version"},
    ]
    assert payload["result"]["rows"] == [
        {
            "decision_key": "bal_gap_rule::maturity_gap::Tighten duration gap",
            "title": "Tighten duration gap",
            "action_label": "Review",
            "severity": "high",
            "reason": "Gap widened",
            "source_section": "maturity_gap",
            "rule_id": "bal_gap_rule",
            "rule_version": "rv-test",
            "latest_status": {
                "decision_key": "bal_gap_rule::maturity_gap::Tighten duration gap",
                "status": "pending",
                "updated_at": None,
                "updated_by": None,
                "comment": None,
            },
        }
    ]


def test_update_balance_analysis_decision_status_rejects_unknown_generated_decision_key(
    monkeypatch,
):
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    schema_mod = load_module(
        "backend.app.schemas.balance_analysis",
        "backend/app/schemas/balance_analysis.py",
    )

    monkeypatch.setattr(
        service_mod,
        "_build_balance_workbook_payload",
        lambda **_kwargs: (
            {
                "report_date": "2025-12-31",
                "position_scope": "all",
                "currency_basis": "CNY",
                "cards": [],
                "tables": [
                    {
                        "key": "decision_items",
                        "title": "Decision Items",
                        "section_kind": "decision_items",
                        "columns": [],
                        "rows": [
                            {
                                "title": "Tighten duration gap",
                                "action_label": "Review",
                                "severity": "high",
                                "reason": "Gap widened",
                                "source_section": "maturity_gap",
                                "rule_id": "bal_gap_rule",
                                "rule_version": "rv-test",
                            }
                        ],
                    }
                ],
            },
            None,
        ),
    )

    with pytest.raises(
        ValueError,
        match="Unknown balance-analysis decision_key for the requested report_date and filters\\.",
    ):
        service_mod.update_balance_analysis_decision_status(
            duckdb_path="ignored.duckdb",
            governance_dir="ignored-governance",
            update=schema_mod.BalanceAnalysisDecisionStatusUpdateRequest(
                report_date="2025-12-31",
                position_scope="all",
                currency_basis="CNY",
                decision_key="missing-rule::missing-section::missing-title",
                status="confirmed",
                comment=None,
            ),
            updated_by="balance-owner",
        )


def test_export_balance_analysis_workbook_xlsx_uses_workbook_envelope_result(
    monkeypatch,
):
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    workbook_payload = {
        "report_date": "2025-12-31",
        "position_scope": "all",
        "currency_basis": "CNY",
        "cards": [{"key": "net_position", "label": "Net", "value": "1"}],
        "tables": [],
        "operational_sections": [],
    }
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        service_mod,
        "balance_analysis_workbook_envelope",
        lambda **kwargs: calls.append(kwargs) or {"result": workbook_payload},
    )
    monkeypatch.setattr(
        service_mod,
        "_build_balance_analysis_workbook_xlsx_bytes",
        lambda payload: b"excel-bytes" if payload is workbook_payload else b"wrong-payload",
    )

    filename, content = service_mod.export_balance_analysis_workbook_xlsx(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert calls == [
        {
            "duckdb_path": "ignored.duckdb",
            "governance_dir": "ignored-governance",
            "report_date": "2025-12-31",
            "position_scope": "all",
            "currency_basis": "CNY",
        }
    ]
    assert filename == "资产负债分析_2025-12-31.xlsx"
    assert content == b"excel-bytes"


def test_export_balance_analysis_summary_csv_uses_summary_rows_and_lineage(
    monkeypatch,
):
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
            assert kwargs == {
                "report_date": "2025-12-31",
                "position_scope": "asset",
                "currency_basis": "CNY",
                "limit": None,
                "offset": 0,
            }
            return {
                "rows": [
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
                        "detail_row_count": 1,
                        "market_value_amount": "720.00000000",
                        "amortized_cost_amount": "648.00000000",
                        "accrued_interest_amount": "36.00000000",
                    }
                ]
            }

    monkeypatch.setattr(service_mod, "BalanceAnalysisRepository", FakeRepo)
    monkeypatch.setattr(
        service_mod,
        "resolve_completed_formal_build_lineage",
        lambda **kwargs: {
            "cache_key": kwargs["cache_key"],
            "cache_version": "cv_balance_analysis_test",
            "source_version": "sv_balance_analysis_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_balance_analysis_test",
            "report_date": kwargs["report_date"],
        },
    )

    filename, content = service_mod.export_balance_analysis_summary_csv(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="asset",
        currency_basis="CNY",
    )

    assert filename == "balance-analysis-summary-2025-12-31-asset-CNY.csv"
    assert "row_key,source_family,display_name,owner_name" in content
    assert "zqtz:240001.IB:组合A:CC100:CNY:asset:A:FVOCI" in content
    assert "sv_balance_analysis_test" in content
    assert "rv_balance_analysis_test" in content


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


@pytest.mark.parametrize(
    "sample_report_date",
    ["2024-01-01", "2025-11-20", "2026-02-28"],
)
def test_balance_analysis_overview_envelope_resolves_lineage_per_historical_report_date(
    monkeypatch,
    sample_report_date: str,
):
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )

    class FakeRepo:
        def __init__(self, duckdb_path: str) -> None:
            self.duckdb_path = duckdb_path

        def list_report_dates(self):
            return ["2026-03-31", sample_report_date, "2025-12-31"]

        def fetch_formal_overview(self, **kwargs):
            assert kwargs["report_date"] == sample_report_date
            return {
                "report_date": sample_report_date,
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "detail_row_count": 1,
                "summary_row_count": 1,
                "total_market_value_amount": "10.00000000",
                "total_amortized_cost_amount": "9.00000000",
                "total_accrued_interest_amount": "0.10000000",
                "rule_version": "rv_repo_fallback",
            }

    calls: list[dict[str, str]] = []

    monkeypatch.setattr(service_mod, "BalanceAnalysisRepository", FakeRepo)
    monkeypatch.setattr(
        service_mod,
        "resolve_completed_formal_build_lineage",
        lambda **kwargs: calls.append(kwargs)
        or {
            "cache_key": service_mod.CACHE_KEY,
            "cache_version": "cv_test",
            "source_version": "sv_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_test",
            "report_date": sample_report_date,
        },
    )

    service_mod.balance_analysis_overview_envelope(
        duckdb_path="ignored.duckdb",
        governance_dir="ignored-governance",
        report_date=sample_report_date,
        position_scope="all",
        currency_basis="CNY",
    )

    assert calls == [
        {
            "governance_dir": "ignored-governance",
            "cache_key": service_mod.CACHE_KEY,
            "job_name": service_mod.BALANCE_ANALYSIS_JOB_NAME,
            "report_date": sample_report_date,
        }
    ]
