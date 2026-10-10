from __future__ import annotations

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
                "asset_total_market_value_amount": "60.00000000",
                "liability_total_market_value_amount": "40.00000000",
                "asset_total_amortized_cost_amount": "55.00000000",
                "liability_total_amortized_cost_amount": "35.00000000",
                "asset_total_accrued_interest_amount": "3.00000000",
                "liability_total_accrued_interest_amount": "2.00000000",
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
    assert payload["result_meta"]["requested_report_date"] == "2025-12-31"
    assert payload["result_meta"]["resolved_report_date"] == "2025-12-31"
    assert payload["result_meta"]["as_of_date"] == "2025-12-31"
    assert payload["result_meta"]["date_basis"] == "balance_analysis_report_date"
    assert payload["result_meta"]["filters_applied"] == {
        "report_date": "2025-12-31",
        "position_scope": "all",
        "currency_basis": "CNY",
    }
    assert payload["result_meta"]["tables_used"] == [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    ]
    assert payload["result_meta"]["evidence_rows"] == 2
    assert payload["result"]["detail_row_count"] == 2
    definitions = {item["key"]: item for item in payload["result"]["metric_definitions"]}
    assert definitions["asset_total_market_value_amount"] == {
        "key": "asset_total_market_value_amount",
        "label": "资产市值合计",
        "source_field": "market_value_amount",
        "raw_unit": "yuan",
        "display_unit": "yi_yuan",
        "basis": "formal",
        "source_surface": "formal_balance",
        "applies_to": ["overview", "summary", "detail"],
        "description": "正式资产头寸市值金额合计；后端返回元，页面按亿元展示。",
    }
    assert definitions["liability_total_accrued_interest_amount"]["label"] == "负债应计利息合计"
    assert definitions["liability_total_accrued_interest_amount"]["source_field"] == "accrued_interest_amount"
    assert isinstance(payload["calibration"], dict)
    assert payload["data_source"] == "balance_analysis_facts"
    assert payload["calibration"]["data_basis"] == "formal_facts"
    assert "zqtz" in payload["calibration"]["source_families"]


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

        def fetch_formal_overview(self, **_kwargs):
            return {"detail_row_count": 3}

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
    assert payload["result_meta"]["filters_applied"] == {
        "report_date": "2025-12-31",
        "position_scope": "all",
        "currency_basis": "CNY",
        "limit": 10,
        "offset": 0,
    }
    assert payload["result_meta"]["evidence_rows"] == 3
    assert payload["result"]["total_rows"] == 1
    assert isinstance(payload["calibration"], dict)
    assert payload["data_source"] == "balance_analysis_facts"
    assert payload["calibration"]["currency_basis"] == "CNY"


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
    assert payload["result_meta"]["evidence_rows"] == 1
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
            # Honor requested currency_basis (workbook H-2); fixture amounts are CNY-like.
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


def test_build_balance_workbook_payload_runtime_cache_reuses_matching_build_and_isolates_fingerprint(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_bytes(b"v1")
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    cache = getattr(service_mod, "_BALANCE_WORKBOOK_PAYLOAD_CACHE", None)
    if cache is not None:
        cache.clear()
    build_calls: list[dict[str, object]] = []

    def build_workbook_payload(**kwargs):
        build_calls.append(kwargs)
        return (
            {
                "report_date": kwargs["report_date"],
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "cards": [],
                "tables": [],
            },
            {
                "cache_key": service_mod.CACHE_KEY,
                "cache_version": "cv_balance_analysis_test",
                "source_version": "sv_balance_analysis_test",
                "vendor_version": "vv_none",
                "rule_version": "rv_balance_analysis_test",
                "report_date": kwargs["report_date"],
            },
        )

    monkeypatch.setattr(
        service_mod.balance_analysis_workbook_service,
        "_build_balance_workbook_payload",
        build_workbook_payload,
    )

    first = service_mod._build_balance_workbook_payload(
        duckdb_path=str(duckdb_path),
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )
    second = service_mod._build_balance_workbook_payload(
        duckdb_path=str(duckdb_path),
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )
    scope_variant = service_mod._build_balance_workbook_payload(
        duckdb_path=str(duckdb_path),
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="asset",
        currency_basis="CNY",
    )
    duckdb_path.write_bytes(b"v2-storage-fingerprint")
    fingerprint_variant = service_mod._build_balance_workbook_payload(
        duckdb_path=str(duckdb_path),
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert first == second
    assert scope_variant[0]["position_scope"] == "asset"
    assert fingerprint_variant[0]["position_scope"] == "all"
    assert len(build_calls) == 3


def test_build_balance_workbook_payload_runtime_cache_isolates_manifest_fingerprint(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_bytes(b"v1")
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    cache = getattr(service_mod, "_BALANCE_WORKBOOK_PAYLOAD_CACHE", None)
    if cache is not None:
        cache.clear()
    build_calls = 0

    def build_workbook_payload(**kwargs):
        nonlocal build_calls
        build_calls += 1
        return (
            {
                "report_date": kwargs["report_date"],
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "cards": [],
                "tables": [],
                "build_calls": build_calls,
            },
            {
                "cache_key": service_mod.CACHE_KEY,
                "cache_version": f"cv_balance_analysis_test_{build_calls}",
                "source_version": f"sv_balance_analysis_test_{build_calls}",
                "vendor_version": "vv_none",
                "rule_version": "rv_balance_analysis_test",
                "report_date": kwargs["report_date"],
            },
        )

    monkeypatch.setattr(
        service_mod.balance_analysis_workbook_service,
        "_build_balance_workbook_payload",
        build_workbook_payload,
    )

    first = service_mod._build_balance_workbook_payload(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )
    second = service_mod._build_balance_workbook_payload(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )
    (governance_dir / f"{service_mod.CACHE_MANIFEST_STREAM}.jsonl").write_text(
        '{"cache_key":"balance_analysis","source_version":"sv_manifest_new"}\n',
        encoding="utf-8",
    )
    manifest_variant = service_mod._build_balance_workbook_payload(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert first == second
    assert manifest_variant[0]["build_calls"] == 2
    assert build_calls == 2


def test_balance_workbook_quality_flag_warns_when_maturity_is_missing():
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    workbook = {
        "tables": [
            {
                "key": "risk_alerts",
                "section_kind": "risk_alerts",
                "rows": [
                    {"rule_id": "bal_wb_risk_maturity_missing_001"},
                ],
            },
        ],
    }

    assert service_mod._balance_workbook_quality_flag(workbook) == "warning"
    assert service_mod._balance_workbook_quality_flag({"tables": []}) is None


@pytest.fixture
def balance_workbook_refresh_harness(tmp_path, monkeypatch):
    from backend.app.services.runtime_cache import InMemoryTTLCache

    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    duckdb_path = tmp_path / "refresh.duckdb"
    duckdb_path.write_bytes(b"v1")
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    clock = [0.0]
    cache = InMemoryTTLCache(ttl_seconds=900, clock=lambda: clock[0])
    state = {"builds": 0, "on_build": None}
    args = {
        "duckdb_path": str(duckdb_path),
        "governance_dir": str(governance_dir),
        "report_date": "2025-12-31",
        "position_scope": "all",
        "currency_basis": "CNY",
    }

    def build_workbook(**kwargs):
        state["builds"] += 1
        callback = state["on_build"]
        if callback is not None:
            callback()
        return (
            {
                "report_date": kwargs["report_date"],
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "builds": state["builds"],
                "cards": [],
                "tables": [
                    {
                        "key": "decision_items",
                        "title": "Decision Items",
                        "section_kind": "decision_items",
                        "columns": [],
                        "rows": [
                            {
                                "title": "Review balance gap",
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
                "report_date": kwargs["report_date"],
            },
        )

    monkeypatch.setattr(service_mod, "_BALANCE_WORKBOOK_PAYLOAD_CACHE", cache)
    monkeypatch.setattr(service_mod, "_resolve_governance_backend_mode", lambda _mode: "jsonl")
    monkeypatch.setattr(
        service_mod.balance_analysis_workbook_service,
        "_build_balance_workbook_payload",
        build_workbook,
    )
    return service_mod, args, cache, clock, state


def test_balance_workbook_force_refresh_renews_ttl_before_original_expiry(
    balance_workbook_refresh_harness,
):
    service_mod, args, _cache, clock, state = balance_workbook_refresh_harness
    service_mod._build_balance_workbook_payload(**args)
    clock[0] = 800.0
    renewed = service_mod._build_balance_workbook_payload(**args, force_refresh=True)
    clock[0] = 901.0
    after_original_expiry = service_mod._build_balance_workbook_payload(**args)

    assert state["builds"] == 2
    assert after_original_expiry == renewed
    clock[0] = 1701.0
    service_mod._build_balance_workbook_payload(**args)
    assert state["builds"] == 3


def test_balance_workbook_force_refresh_keeps_valid_entry_available_during_build(
    balance_workbook_refresh_harness,
):
    service_mod, args, _cache, _clock, state = balance_workbook_refresh_harness
    first = service_mod._build_balance_workbook_payload(**args)
    reads_during_refresh = []
    state["on_build"] = lambda: reads_during_refresh.append(
        service_mod._build_balance_workbook_payload(**args)
    )

    renewed = service_mod._build_balance_workbook_payload(**args, force_refresh=True)

    assert reads_during_refresh == [first]
    assert state["builds"] == 2
    assert service_mod._build_balance_workbook_payload(**args) == renewed


def test_balance_workbook_force_refresh_failure_preserves_old_entry_and_expiry(
    balance_workbook_refresh_harness,
):
    service_mod, args, _cache, clock, state = balance_workbook_refresh_harness
    first = service_mod._build_balance_workbook_payload(**args)

    def fail_build():
        raise RuntimeError("refresh failed")

    state["on_build"] = fail_build
    clock[0] = 800.0
    with pytest.raises(RuntimeError, match="refresh failed"):
        service_mod._build_balance_workbook_payload(**args, force_refresh=True)
    assert service_mod._build_balance_workbook_payload(**args) == first
    state["on_build"] = None
    clock[0] = 901.0
    assert service_mod._build_balance_workbook_payload(**args)[0]["builds"] == 3


def test_balance_workbook_force_refresh_does_not_refill_after_generation_clear(
    balance_workbook_refresh_harness,
):
    service_mod, args, cache, _clock, state = balance_workbook_refresh_harness
    service_mod._build_balance_workbook_payload(**args)
    state["on_build"] = cache.clear

    service_mod._build_balance_workbook_payload(**args, force_refresh=True)

    key = service_mod._balance_workbook_payload_cache_key(**args)
    assert cache.get(key) == (False, None)
    state["on_build"] = None
    service_mod._build_balance_workbook_payload(**args)
    assert state["builds"] == 3


@pytest.mark.parametrize("changed_input", ["storage", "governance", "effective_path"])
def test_balance_workbook_force_refresh_does_not_refill_after_input_change(
    balance_workbook_refresh_harness,
    tmp_path,
    monkeypatch,
    changed_input,
):
    service_mod, args, cache, _clock, state = balance_workbook_refresh_harness
    first = service_mod._build_balance_workbook_payload(**args)
    original_key = service_mod._balance_workbook_payload_cache_key(**args)
    if changed_input == "storage":
        state["on_build"] = lambda: Path(args["duckdb_path"]).write_bytes(b"new-input")
    elif changed_input == "governance":
        stream_path = Path(args["governance_dir"]) / f"{service_mod.CACHE_MANIFEST_STREAM}.jsonl"
        state["on_build"] = lambda: stream_path.write_bytes(b'{"source_version":"sv_new"}\n')
    else:
        new_path = tmp_path / "selected-generation.duckdb"
        new_path.write_bytes(b"new-input")
        state["on_build"] = lambda: monkeypatch.setattr(
            service_mod, "resolve_effective_read_path", lambda _path: new_path
        )

    service_mod._build_balance_workbook_payload(**args, force_refresh=True)

    changed_key = service_mod._balance_workbook_payload_cache_key(**args)
    assert original_key != changed_key
    assert cache.get(original_key) == (True, first)
    assert cache.get(changed_key) == (False, None)
    state["on_build"] = None
    service_mod._build_balance_workbook_payload(**args)
    assert state["builds"] == 3


def test_balance_workbook_force_refresh_does_not_publish_under_changed_system_identity(
    balance_workbook_refresh_harness,
    monkeypatch,
):
    from backend.app.services import runtime_cache

    service_mod, args, cache, _clock, state = balance_workbook_refresh_harness
    identity = ["generation_before"]

    def system_identity(key):
        return identity[0], key

    monkeypatch.setattr(service_mod, "system_read_cache_identity", system_identity, raising=False)
    monkeypatch.setattr(runtime_cache, "system_read_cache_identity", system_identity)
    service_mod._build_balance_workbook_payload(**args)
    state["on_build"] = lambda: identity.__setitem__(0, "generation_after")

    service_mod._build_balance_workbook_payload(**args, force_refresh=True)

    key = service_mod._balance_workbook_payload_cache_key(**args)
    assert cache.get(key) == (False, None)
    state["on_build"] = None
    service_mod._build_balance_workbook_payload(**args)
    assert state["builds"] == 3


def test_balance_workbook_force_refresh_keeps_sql_authority_uncached(
    balance_workbook_refresh_harness,
    monkeypatch,
):
    service_mod, args, cache, _clock, state = balance_workbook_refresh_harness
    monkeypatch.setattr(service_mod, "_resolve_governance_backend_mode", lambda _mode: "sql-authority")
    service_mod._build_balance_workbook_payload(**args, force_refresh=True)
    service_mod._build_balance_workbook_payload(**args, force_refresh=True)
    service_mod._build_balance_workbook_payload(**args)

    assert state["builds"] == 3
    assert service_mod._balance_workbook_payload_cache_key(**args) is None
    assert not cache._store


def test_balance_decision_items_force_refresh_rebuilds_workbook_and_reads_statuses_fresh(
    balance_workbook_refresh_harness,
    monkeypatch,
):
    service_mod, args, _cache, _clock, state = balance_workbook_refresh_harness
    statuses = [{}, {"bal_gap_rule": {"decision_key": "bal_gap_rule", "status": "confirmed"}}, {}]
    status_reads = []

    class FakeDecisionRepo:
        def __init__(self, _governance_dir):
            pass

        def list_latest_statuses(self, **kwargs):
            status_reads.append(kwargs)
            return statuses.pop(0)

    monkeypatch.setattr(service_mod, "BalanceAnalysisDecisionRepository", FakeDecisionRepo)
    first = service_mod.balance_analysis_decision_items_envelope(**args)
    refreshed = service_mod.balance_analysis_decision_items_envelope(**args, force_refresh=True)
    cached = service_mod.balance_analysis_decision_items_envelope(**args)

    assert state["builds"] == 2
    assert len(status_reads) == 3
    assert first["result"]["rows"][0]["latest_status"]["status"] == "pending"
    assert refreshed["result"]["rows"][0]["latest_status"]["status"] == "confirmed"
    assert cached["result"]["rows"][0]["latest_status"]["status"] == "pending"


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
                        "key": "ifrs9_source_family",
                        "title": "IFRS9 Source Family",
                        "section_kind": "table",
                        "columns": [],
                        "rows": [
                            {"source_family": "zqtz", "row_count": 1},
                            {"source_family": "tyw", "row_count": 1},
                        ],
                    },
                    {
                        "key": "decision_items",
                        "title": "Decision Items",
                        "section_kind": "decision_items",
                        "columns": [
                            {"key": "title", "label": "标题"},
                            {"key": "action_label", "label": "动作"},
                            {"key": "severity", "label": "等级"},
                            {"key": "reason", "label": "原因"},
                            {"key": "source_section", "label": "来源区块"},
                            {"key": "rule_id", "label": "规则编号"},
                            {"key": "rule_version", "label": "规则版本"},
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
                    },
                    {
                        "key": "risk_alerts",
                        "title": "风险预警",
                        "section_kind": "risk_alerts",
                        "columns": [],
                        "rows": [
                            {
                                "rule_id": "bal_wb_risk_maturity_missing_001",
                            }
                        ],
                    },
                ],
            },
            {
                "cache_key": service_mod.CACHE_KEY,
                "cache_version": "cv_balance_analysis_test",
                "source_version": "sv_balance_analysis_test",
                "vendor_version": "vv_none",
                "rule_version": "rv_balance_analysis_test",
                "report_date": "2025-12-31",
                "quality_flag": "ok",
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
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["evidence_rows"] == 2
    assert payload["result"]["columns"] == [
        {"key": "title", "label": "标题"},
        {"key": "action_label", "label": "动作"},
        {"key": "severity", "label": "等级"},
        {"key": "reason", "label": "原因"},
        {"key": "source_section", "label": "来源区块"},
        {"key": "rule_id", "label": "规则编号"},
        {"key": "rule_version", "label": "规则版本"},
    ]
    assert payload["result"]["rows"] == [
        {
            "decision_key": "bal_gap_rule",
            "title": "Tighten duration gap",
            "action_label": "Review",
            "severity": "high",
            "reason": "Gap widened",
            "source_section": "maturity_gap",
            "rule_id": "bal_gap_rule",
            "rule_version": "rv-test",
            "latest_status": {
                "decision_key": "bal_gap_rule",
                "status": "pending",
                "updated_at": None,
                "updated_by": None,
                "comment": None,
            },
        }
    ]


def test_balance_analysis_decision_items_reuses_workbook_but_reads_statuses_fresh(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_bytes(b"v1")
    service_mod = load_module(
        "backend.app.services.balance_analysis_service",
        "backend/app/services/balance_analysis_service.py",
    )
    cache = getattr(service_mod, "_BALANCE_WORKBOOK_PAYLOAD_CACHE", None)
    if cache is not None:
        cache.clear()
    build_calls = 0

    def build_workbook_payload(**kwargs):
        nonlocal build_calls
        build_calls += 1
        return (
            {
                "report_date": kwargs["report_date"],
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "cards": [],
                "tables": [
                    {
                        "key": "ifrs9_source_family",
                        "title": "IFRS9 Source Family",
                        "section_kind": "table",
                        "columns": [],
                        "rows": [{"source_family": "zqtz", "row_count": 1}],
                    },
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
                    },
                ],
            },
            {
                "cache_key": service_mod.CACHE_KEY,
                "cache_version": "cv_balance_analysis_test",
                "source_version": "sv_balance_analysis_test",
                "vendor_version": "vv_none",
                "rule_version": "rv_balance_analysis_test",
                "report_date": kwargs["report_date"],
            },
        )

    statuses = [
        {},
        {
            "bal_gap_rule": {
                "decision_key": "bal_gap_rule",
                "status": "confirmed",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "updated_by": "balance-owner",
                "comment": "done",
            }
        },
    ]

    class FakeDecisionRepo:
        def __init__(self, governance_dir: str) -> None:
            self.governance_dir = governance_dir

        def list_latest_statuses(self, **_kwargs):
            return statuses.pop(0)

    monkeypatch.setattr(
        service_mod.balance_analysis_workbook_service,
        "_build_balance_workbook_payload",
        build_workbook_payload,
    )
    monkeypatch.setattr(service_mod, "BalanceAnalysisDecisionRepository", FakeDecisionRepo)

    first = service_mod.balance_analysis_decision_items_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )
    second = service_mod.balance_analysis_decision_items_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir="ignored-governance",
        report_date="2025-12-31",
        position_scope="all",
        currency_basis="CNY",
    )

    assert build_calls == 1
    assert first["result"]["rows"][0]["latest_status"]["status"] == "pending"
    assert second["result"]["rows"][0]["latest_status"]["status"] == "confirmed"
    assert second["result"]["rows"][0]["latest_status"]["updated_by"] == "balance-owner"


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
                "asset_total_market_value_amount": "6.00000000",
                "liability_total_market_value_amount": "4.00000000",
                "asset_total_amortized_cost_amount": "5.40000000",
                "liability_total_amortized_cost_amount": "3.60000000",
                "asset_total_accrued_interest_amount": "0.06000000",
                "liability_total_accrued_interest_amount": "0.04000000",
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
