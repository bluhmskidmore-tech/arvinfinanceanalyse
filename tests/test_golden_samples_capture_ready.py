from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import ROOT, load_module

GOLDEN_ROOT = ROOT / "tests" / "golden_samples"


def _sample_file(sample_id: str, filename: str) -> Path:
    path = GOLDEN_ROOT / sample_id / filename
    if not path.exists():
        pytest.fail(f"Missing golden-sample file: {path}")
    return path


def _load_json(sample_id: str, filename: str) -> dict[str, Any]:
    return json.loads(_sample_file(sample_id, filename).read_text(encoding="utf-8"))


def _read_text(sample_id: str, filename: str) -> str:
    return _sample_file(sample_id, filename).read_text(encoding="utf-8")


def _extract(value: Any, path: tuple[Any, ...]) -> Any:
    current = value
    for segment in path:
        current = current[segment]
    return current


def _assert_paths_equal(
    actual: dict[str, Any],
    expected: dict[str, Any],
    paths: list[tuple[Any, ...]],
) -> None:
    for path in paths:
        assert _extract(actual, path) == _extract(expected, path), path


def _clear_runtime_modules() -> None:
    for name in [
        "backend.app.main",
        "backend.app.api",
        "backend.app.api.routes.balance_analysis",
        "backend.app.api.routes.executive",
        "backend.app.api.routes.pnl",
        "backend.app.api.routes.product_category_pnl",
        "backend.app.api.routes.risk_tensor",
        "backend.app.services.balance_analysis_service",
        "backend.app.services.pnl_service",
        "backend.app.services.pnl_bridge_service",
        "backend.app.services.product_category_pnl_service",
        "backend.app.services.risk_tensor_service",
        "backend.app.tasks.product_category_pnl",
    ]:
        sys.modules.pop(name, None)


def _setup_balance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module(
        "tests._golden_balance_api",
        "tests/test_balance_analysis_api.py",
    )
    module._configure_and_materialize(tmp_path, monkeypatch)


def _setup_pnl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module(
        "tests._golden_pnl_api",
        "tests/test_pnl_api_contract.py",
    )
    module._materialize_three_pnl_dates(tmp_path, monkeypatch)


def _setup_product_category(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module(
        "tests._golden_product_category_flow",
        "tests/test_product_category_pnl_flow.py",
    )
    data_root = tmp_path / "data_input"
    source_dir = data_root / "pnl_\u603b\u8d26\u5bf9\u8d26-\u65e5\u5747"
    source_dir.mkdir(parents=True)
    module._write_month_pair(source_dir, "202601", january=True)
    module._write_month_pair(source_dir, "202602", january=False)

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.product_category_pnl")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.product_category_pnl",
            "backend/app/tasks/product_category_pnl.py",
        )
    task_module.materialize_product_category_pnl.fn(
        duckdb_path=str(duckdb_path),
        source_dir=str(source_dir),
        governance_dir=str(governance_dir),
    )


def _setup_risk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module(
        "tests._golden_risk_service",
        "tests/test_risk_tensor_service.py",
    )
    module._configure_and_materialize_risk_tensor(tmp_path, monkeypatch)


def _setup_bridge_warn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module(
        "tests._golden_bridge_warn_api",
        "tests/test_pnl_api_contract.py",
    )
    governance_dir = module._materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    module._append_manifest_override(
        governance_dir,
        source_version="sv_bridge_balance",
        vendor_version="vv_bridge_balance",
        rule_version="rv_bridge_balance",
    )
    module._seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=True,
        include_unusable_zqtz_intermediate_prior=True,
    )


def _setup_risk_warn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module(
        "tests._golden_risk_warn_api",
        "tests/test_risk_tensor_api.py",
    )
    module._configure_and_materialize_degraded_snapshot(tmp_path, monkeypatch)


def _setup_exec_overview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )

    monkeypatch.setattr(
        service_mod,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "duckdb_path": str(tmp_path / "exec-overview.duckdb"),
                "governance_path": tmp_path / "governance",
                "governance_sql_dsn": "",
                "postgres_dsn": "",
            },
        )(),
    )

    class BalanceRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2026-02-28", "2026-02-27"]

        def fetch_formal_overview(self, **kwargs):
            values = {
                "2026-02-28": 3572.76e8,
                "2026-02-27": 3712.29e8,
            }
            return {
                "report_date": kwargs["report_date"],
                "position_scope": kwargs["position_scope"],
                "currency_basis": kwargs["currency_basis"],
                "detail_row_count": 10,
                "summary_row_count": 10,
                "total_market_value_amount": values[kwargs["report_date"]],
                "total_amortized_cost_amount": values[kwargs["report_date"]],
                "total_accrued_interest_amount": 0.0,
                "source_version": "sv_balance_union",
                "rule_version": "rv_balance_union",
            }

    class PnlRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_formal_fi_report_dates(self):
            return ["2026-02-28", "2026-02-27"]

        def sum_formal_total_pnl_through_report_date(self, report_date: str):
            return 4.69e8 if report_date == "2026-02-28" else 4.60e8

    class LiabilityRepo:
        def __init__(self, *_a, **_k):
            pass

        def resolve_latest_report_date(self):
            return "2026-02-28"

        def list_report_dates(self):
            return ["2026-02-28", "2026-02-27"]

        def fetch_zqtz_rows(self, report_date: str):
            return []

        def fetch_tyw_rows(self, report_date: str):
            return []

    class BondRepo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2026-02-28", "2026-02-27"]

        def fetch_risk_overview_snapshot(self, *, report_date: str):
            return {
                "report_date": report_date,
                "portfolio_dv01": 13826218.0 if report_date == "2026-02-28" else 13855000.0,
            }

    monkeypatch.setattr(service_mod, "FormalZqtzBalanceMetricsRepository", BalanceRepo)
    monkeypatch.setattr(service_mod, "PnlRepository", PnlRepo)
    monkeypatch.setattr(service_mod, "LiabilityAnalyticsRepository", LiabilityRepo)
    monkeypatch.setattr(service_mod, "BondAnalyticsRepository", BondRepo)
    monkeypatch.setattr(
        service_mod,
        "compute_liability_yield_metrics",
        lambda report_date, zqtz_rows, tyw_rows: {
            "report_date": report_date,
            "kpi": {"nim": 0.01},
        },
    )
    monkeypatch.setattr(service_mod, "resolve_executive_kpi_metrics", lambda **_kwargs: [])


def _setup_exec_pnl_attr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )

    monkeypatch.setattr(
        service_mod,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "duckdb_path": str(tmp_path / "exec-pnl-attribution.duckdb"),
                "governance_path": tmp_path / "governance",
                "governance_sql_dsn": "",
                "postgres_dsn": "",
            },
        )(),
    )

    class Repo:
        def __init__(self, *_a, **_k):
            pass

        def list_report_dates(self):
            return ["2026-02-28"]

        def fetch_rows(self, rd, grain):
            assert rd == "2026-02-28"
            assert grain == "monthly"
            return [
                {
                    "level": 1,
                    "is_total": False,
                    "category_id": "bond_tpl",
                    "business_net_income": 1e8,
                    "source_version": "sv_pc_a",
                    "rule_version": "rv_pc_a",
                },
                {
                    "level": 1,
                    "is_total": False,
                    "category_id": "bond_ac",
                    "business_net_income": 2e8,
                    "source_version": "sv_pc_a",
                    "rule_version": "rv_pc_a",
                },
                {
                    "level": 1,
                    "is_total": False,
                    "category_id": "bond_fvoci",
                    "business_net_income": 1e8,
                    "source_version": "sv_pc_b",
                    "rule_version": "rv_pc_b",
                },
                {
                    "level": 1,
                    "is_total": False,
                    "category_id": "bond_ac_other",
                    "business_net_income": 0.5e8,
                    "source_version": "sv_pc_b",
                    "rule_version": "rv_pc_b",
                },
                {
                    "level": 1,
                    "is_total": False,
                    "category_id": "bond_valuation_spread",
                    "business_net_income": -3e8,
                    "source_version": "sv_pc_c",
                    "rule_version": "rv_pc_c",
                },
                {
                    "level": 1,
                    "is_total": False,
                    "category_id": "unknown_bucket",
                    "business_net_income": 0.25e8,
                    "source_version": "sv_pc_c",
                    "rule_version": "rv_pc_c",
                },
            ]

    monkeypatch.setattr(service_mod, "ProductCategoryPnlRepository", Repo)


def _setup_exec_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )

    monkeypatch.setattr(
        service_mod,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "duckdb_path": str(tmp_path / "exec-summary.duckdb"),
                "governance_path": tmp_path / "governance",
                "governance_sql_dsn": "",
                "postgres_dsn": "",
            },
        )(),
    )

    monkeypatch.setattr(
        service_mod,
        "executive_overview",
        lambda report_date=None: {
            "result_meta": {
                "source_version": "sv_summary_requested",
                "rule_version": "rv_summary_requested",
                "vendor_status": "ok",
            },
            "result": {"metrics": [], "report_date": report_date},
        },
    )


def _run_sample_request(sample_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    request = _load_json(sample_id, "request.json")
    _clear_runtime_modules()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.request(
        request["method"],
        request["path"],
        params=request.get("params"),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _validate_balance_overview(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result", "report_date"),
            ("result", "position_scope"),
            ("result", "currency_basis"),
            ("result", "detail_row_count"),
            ("result", "summary_row_count"),
            ("result", "total_market_value_amount"),
            ("result", "total_amortized_cost_amount"),
            ("result", "total_accrued_interest_amount"),
        ],
    )


def _table_keys(payload: dict[str, Any]) -> list[str]:
    return [str(item["key"]) for item in payload["result"]["tables"]]


def _validate_balance_workbook(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result", "report_date"),
            ("result", "position_scope"),
            ("result", "currency_basis"),
            ("result", "cards"),
            ("result", "operational_sections"),
        ],
    )
    assert _table_keys(actual) == _table_keys(expected)


def _validate_pnl_overview(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result", "report_date"),
            ("result", "formal_fi_row_count"),
            ("result", "nonstd_bridge_row_count"),
            ("result", "interest_income_514"),
            ("result", "fair_value_change_516"),
            ("result", "capital_gain_517"),
            ("result", "manual_adjustment"),
            ("result", "total_pnl"),
        ],
    )


def _validate_pnl_data(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result", "report_date"),
            ("result", "formal_fi_rows"),
            ("result", "nonstd_bridge_rows"),
        ],
    )


def _validate_product_category(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result", "report_date"),
            ("result", "view"),
            ("result", "available_views"),
            ("result", "scenario_rate_pct"),
            ("result", "rows"),
            ("result", "asset_total"),
            ("result", "liability_total"),
            ("result", "grand_total"),
        ],
    )
    assert str(actual["result_meta"]["source_version"]).startswith("sv_product_category_")


def _validate_bridge(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result", "report_date"),
            ("result", "rows"),
            ("result", "summary"),
            ("result", "warnings"),
        ],
    )


def _validate_risk(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result",),
        ],
    )


def _validate_bridge_warn(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result", "report_date"),
            ("result", "rows"),
            ("result", "summary"),
            ("result", "warnings"),
        ],
    )


def _validate_risk_warn(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result",),
        ],
    )


def _validate_exec_overview(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result", "title"),
        ],
    )
    actual_metrics = actual["result"]["metrics"]
    expected_metrics = expected["result"]["metrics"]
    assert len(actual_metrics) == len(expected_metrics) == 4

    actual_by_id = {str(metric["id"]): metric for metric in actual_metrics}
    expected_by_id = {str(metric["id"]): metric for metric in expected_metrics}
    assert list(actual_by_id) == list(expected_by_id)

    for metric_id, expected_metric in expected_by_id.items():
        actual_metric = actual_by_id[metric_id]
        assert "history" in actual_metric
        _assert_paths_equal(
            actual_metric,
            expected_metric,
            [
                ("id",),
                ("label",),
                ("caliber_label",),
                ("value", "display"),
                ("delta", "display"),
                ("tone",),
                ("detail",),
            ],
        )


def _validate_exec_pnl_attr(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result",),
        ],
    )


def _validate_exec_summary(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("result_meta", "basis"),
            ("result_meta", "result_kind"),
            ("result_meta", "formal_use_allowed"),
            ("result_meta", "source_version"),
            ("result_meta", "vendor_version"),
            ("result_meta", "rule_version"),
            ("result_meta", "cache_version"),
            ("result_meta", "quality_flag"),
            ("result_meta", "vendor_status"),
            ("result_meta", "fallback_mode"),
            ("result_meta", "scenario_flag"),
            ("result",),
        ],
    )


@dataclass(frozen=True)
class CaptureReadyCase:
    setup: Any
    validator: Any


CAPTURE_READY_CASES: dict[str, CaptureReadyCase] = {
    "GS-BAL-OVERVIEW-A": CaptureReadyCase(setup=_setup_balance, validator=_validate_balance_overview),
    "GS-BAL-WORKBOOK-A": CaptureReadyCase(setup=_setup_balance, validator=_validate_balance_workbook),
    "GS-PNL-OVERVIEW-A": CaptureReadyCase(setup=_setup_pnl, validator=_validate_pnl_overview),
    "GS-PNL-DATA-A": CaptureReadyCase(setup=_setup_pnl, validator=_validate_pnl_data),
    "GS-PROD-CAT-PNL-A": CaptureReadyCase(setup=_setup_product_category, validator=_validate_product_category),
    "GS-BRIDGE-A": CaptureReadyCase(setup=_setup_pnl, validator=_validate_bridge),
    "GS-RISK-A": CaptureReadyCase(setup=_setup_risk, validator=_validate_risk),
    "GS-BRIDGE-WARN-B": CaptureReadyCase(setup=_setup_bridge_warn, validator=_validate_bridge_warn),
    "GS-RISK-WARN-B": CaptureReadyCase(setup=_setup_risk_warn, validator=_validate_risk_warn),
    "GS-EXEC-OVERVIEW-A": CaptureReadyCase(setup=_setup_exec_overview, validator=_validate_exec_overview),
    "GS-EXEC-PNL-ATTR-A": CaptureReadyCase(setup=_setup_exec_pnl_attr, validator=_validate_exec_pnl_attr),
    "GS-EXEC-SUMMARY-A": CaptureReadyCase(setup=_setup_exec_summary, validator=_validate_exec_summary),
}


def test_capture_ready_golden_sample_files_exist() -> None:
    for sample_id in CAPTURE_READY_CASES:
        for filename in ("request.json", "response.json", "assertions.md", "approval.md"):
            assert _sample_file(sample_id, filename).exists()


def test_capture_ready_golden_sample_metadata_is_in_expected_state() -> None:
    for sample_id in CAPTURE_READY_CASES:
        approval = _read_text(sample_id, "approval.md")
        assert "captured-awaiting-approval" in approval


@pytest.mark.parametrize("sample_id", sorted(CAPTURE_READY_CASES))
def test_capture_ready_golden_sample_matches_selected_fields(
    sample_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = CAPTURE_READY_CASES[sample_id]
    try:
        case.setup(tmp_path, monkeypatch)
        actual = _run_sample_request(sample_id, tmp_path, monkeypatch)
        expected = _load_json(sample_id, "response.json")
        case.validator(actual, expected)
    finally:
        get_settings.cache_clear()
