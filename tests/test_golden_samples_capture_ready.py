from __future__ import annotations

from datetime import date
import json
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import ROOT, load_module

GOLDEN_ROOT = ROOT / "tests" / "golden_samples"
EXECUTIVE_SAMPLE_PATHS = {"/ui/home/overview", "/ui/home/summary", "/ui/pnl/attribution"}
EXECUTIVE_READ_HEADERS = {"X-User-Id": "executive-read-user", "X-User-Role": "viewer"}
BOND_DASHBOARD_SAMPLE_PATHS = {"/api/bond-dashboard/headline-kpis"}
BOND_DASHBOARD_READ_HEADERS = {"X-User-Id": "bond-dashboard-read-user", "X-User-Role": "viewer"}
BOND_ANALYSIS_SAMPLE_PATHS = {"/api/bond-analytics/action-attribution"}
BOND_ANALYSIS_READ_HEADERS = {"X-User-Id": "bond-analysis-read-user", "X-User-Role": "viewer"}
CONCENTRATION_MONITOR_SAMPLE_PATHS = {"/api/bond-analytics/credit-spread-migration"}
CONCENTRATION_MONITOR_READ_HEADERS = {"X-User-Id": "concentration-monitor-read-user", "X-User-Role": "viewer"}
STOCK_ANALYSIS_SAMPLE_PATHS = {"/ui/market-data/livermore"}
STOCK_ANALYSIS_READ_HEADERS = {"X-User-Id": "stock-analysis-read-user", "X-User-Role": "viewer"}
PNL_ATTRIBUTION_SAMPLE_PATHS = {"/api/pnl-attribution/volume-rate"}
PNL_ATTRIBUTION_READ_HEADERS = {"X-User-Id": "pnl-attribution-read-user", "X-User-Role": "viewer"}
LEDGER_PNL_SAMPLE_PATHS = {"/api/ledger-pnl/summary"}
LEDGER_PNL_READ_HEADERS = {"X-User-Id": "ledger-pnl-read-user", "X-User-Role": "viewer"}
CASHFLOW_PROJECTION_SAMPLE_PATHS = {"/api/cashflow-projection"}
CASHFLOW_PROJECTION_READ_HEADERS = {"X-User-Id": "cashflow-projection-read-user", "X-User-Role": "viewer"}
PNL_SAMPLE_PATHS = {"/api/pnl/bridge", "/api/pnl/data", "/api/pnl/overview"}
PNL_READ_HEADERS = {"X-User-Id": "pnl-read-user", "X-User-Role": "viewer"}
PNL_BUSINESS_INSIGHTS_SAMPLE_PATHS = {
    "/api/pnl/by-business-candidate-insights",
    "/api/pnl/by-business-insights",
}
PNL_BUSINESS_INSIGHTS_READ_HEADERS = {"X-User-Id": "pnl-business-insights-read-user", "X-User-Role": "viewer"}
PRODUCT_CATEGORY_PNL_SAMPLE_PATHS = {"/ui/pnl/product-category"}
PRODUCT_CATEGORY_PNL_READ_HEADERS = {
    "X-User-Id": "product-category-pnl-read-user",
    "X-User-Role": "viewer",
}
RISK_TENSOR_SAMPLE_PATHS = {"/api/risk/tensor"}
RISK_TENSOR_READ_HEADERS = {"X-User-Id": "risk-tensor-read-user", "X-User-Role": "viewer"}
AVERAGE_BALANCE_SAMPLE_PATHS = {"/api/analysis/adb"}
AVERAGE_BALANCE_READ_HEADERS = {"X-User-Id": "average-balance-read-user", "X-User-Role": "viewer"}
MARKET_DATA_RATES_SAMPLE_PATHS = {"/ui/market-data/rates"}
MARKET_DATA_RATES_READ_HEADERS = {"X-User-Id": "macro-vendor-read-user", "X-User-Role": "viewer"}


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


def _row_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["category_id"]) for row in rows]


def _rows_by_category(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["category_id"]): row for row in rows}


def _clear_runtime_modules() -> None:
    for name in [
        "backend.app.main",
        "backend.app.api",
        "backend.app.api.routes.bond_dashboard",
        "backend.app.api.routes.balance_analysis",
        "backend.app.api.routes.executive",
        "backend.app.api.routes.pnl",
        "backend.app.api.routes.product_category_pnl",
        "backend.app.api.routes.risk_tensor",
        "backend.app.services.balance_analysis_service",
        "backend.app.services.bond_dashboard_service",
        "backend.app.services.pnl_service",
        "backend.app.services.pnl_bridge_service",
        "backend.app.services.pnl_by_business_candidate_insights",
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


def _pnl_business_insights_fi_row(
    *,
    report_date: str,
    instrument_code: str,
    interest_income: str,
) -> dict[str, object]:
    return {
        "report_date": report_date,
        "instrument_code": instrument_code,
        "portfolio_name": "Insights Desk",
        "cost_center": "CC-INS",
        "invest_type_raw": "持有至到期",
        "interest_income_514": interest_income,
        "fair_value_change_516": "0.00",
        "capital_gain_517": "0.00",
        "manual_adjustment": "0.00",
        "currency_basis": "CNY",
        "source_version": f"sv_pnl_business_insights_{instrument_code}_{report_date}",
        "rule_version": "rv_pnl_business_insights_gs_a",
        "ingest_batch_id": f"batch-pnl-business-insights-{report_date}",
        "trace_id": f"trace-pnl-business-insights-{instrument_code}-{report_date}",
        "approval_status": "approved",
        "event_semantics": "realized_formal",
        "realized_flag": True,
    }


def _pnl_business_insights_balance_row(
    *,
    report_date: str,
    instrument_code: str,
    bond_type: str,
    market_value_amount: str,
) -> tuple:
    return (
        report_date,
        instrument_code,
        f"{bond_type} {instrument_code}",
        "Insights Desk",
        "CC-INS",
        "asset",
        bond_type,
        bond_type,
        bond_type,
        bond_type,
        "H",
        "AC",
        "asset",
        "CNY",
        "CNY",
        market_value_amount,
        market_value_amount,
        "0.00000000",
        False,
        f"sv_pnl_business_insights_balance_{instrument_code}_{report_date}",
        "rv_pnl_business_insights_gs_a",
        f"ib-pnl-business-insights-{report_date}",
        f"trace-pnl-business-insights-balance-{instrument_code}-{report_date}",
    )


def _setup_pnl_business_insights(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two ZQTZ business types across the exact baseline/monthly/current cutoffs.

    2025-02-28 is the prior-year same-period baseline, 2025-12-31 closes the prior-year
    monthly component, and 2026-01/02 supply the current YTD/monthly window.
    """
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

    fi_rows_by_date = {
        "2025-02-28": [
            _pnl_business_insights_fi_row(report_date="2025-02-28", instrument_code="TB001", interest_income="5.00"),
            _pnl_business_insights_fi_row(report_date="2025-02-28", instrument_code="PF001", interest_income="2.00"),
        ],
        "2025-12-31": [
            _pnl_business_insights_fi_row(report_date="2025-12-31", instrument_code="TB001", interest_income="5.00"),
            _pnl_business_insights_fi_row(report_date="2025-12-31", instrument_code="PF001", interest_income="2.00"),
        ],
        "2026-01-31": [
            _pnl_business_insights_fi_row(report_date="2026-01-31", instrument_code="TB001", interest_income="4.00"),
            _pnl_business_insights_fi_row(report_date="2026-01-31", instrument_code="PF001", interest_income="3.00"),
        ],
        "2026-02-28": [
            _pnl_business_insights_fi_row(report_date="2026-02-28", instrument_code="TB001", interest_income="3.50"),
            _pnl_business_insights_fi_row(report_date="2026-02-28", instrument_code="PF001", interest_income="3.00"),
        ],
    }
    for report_date, fi_rows in fi_rows_by_date.items():
        task_module.materialize_pnl_facts.fn(
            fi_rows=fi_rows,
            nonstd_rows_by_type={},
            report_date=report_date,
            is_month_end=True,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    balance_module = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    balances = {
        "2025-02-28": {"TB001": "700.00000000", "PF001": "300.00000000"},
        "2025-12-31": {"TB001": "680.00000000", "PF001": "320.00000000"},
        "2026-01-31": {"TB001": "650.00000000", "PF001": "350.00000000"},
        "2026-02-28": {"TB001": "600.00000000", "PF001": "400.00000000"},
    }
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        balance_module.ensure_balance_analysis_tables(conn)
        rows = [
            _pnl_business_insights_balance_row(
                report_date=report_date,
                instrument_code="TB001",
                bond_type="国债",
                market_value_amount=amounts["TB001"],
            )
            for report_date, amounts in balances.items()
        ] + [
            _pnl_business_insights_balance_row(
                report_date=report_date,
                instrument_code="PF001",
                bond_type="政策性金融债",
                market_value_amount=amounts["PF001"],
            )
            for report_date, amounts in balances.items()
        ]
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
            rows,
        )
    finally:
        conn.close()


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
    module._configure_and_materialize_clean_risk_tensor(tmp_path, monkeypatch)


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


def _setup_average_balance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import duckdb

    module = load_module(
        "backend.app.repositories.balance_analysis_repo",
        "backend/app/repositories/balance_analysis_repo.py",
    )
    duckdb_path = tmp_path / "average-balance.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        module.ensure_balance_analysis_tables(conn)
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, account_category,
              asset_class, bond_type, invest_type_std, accounting_basis, position_scope,
              currency_basis, currency_code, market_value_amount, amortized_cost_amount,
              accrued_interest_amount, coupon_rate, ytm_value, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values
              (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),
              (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "GS-ADB-BOND-A",
                "Average Balance Desk",
                "ADB",
                "Hold to maturity",
                "\u503a\u5238\u7c7b",
                "\u56fd\u503a",
                "H",
                "AC",
                "asset",
                "CNY",
                "CNY",
                Decimal("120000000.00000000"),
                Decimal("119000000.00000000"),
                Decimal("1000000.00000000"),
                Decimal("2.00000000"),
                Decimal("2.50000000"),
                False,
                "sv_adb_gs_a_zqtz",
                "rv_adb_gs_a",
                "ib_adb_gs_a",
                "tr_adb_gs_a_z1",
                "2025-12-31",
                "GS-ADB-BOND-L",
                "Average Balance Desk",
                "ADB",
                "Issued bond",
                "\u503a\u5238\u7c7b",
                "\u56fd\u503a",
                "H",
                "AC",
                "liability",
                "CNY",
                "CNY",
                Decimal("30000000.00000000"),
                Decimal("30000000.00000000"),
                Decimal("0.00000000"),
                Decimal("1.80000000"),
                Decimal("1.80000000"),
                True,
                "sv_adb_gs_a_zqtz",
                "rv_adb_gs_a",
                "ib_adb_gs_a",
                "tr_adb_gs_a_z2",
            ],
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily (
              report_date, position_id, product_type, position_side, counterparty_name,
              invest_type_std, accounting_basis, position_scope, currency_basis,
              currency_code, principal_amount, accrued_interest_amount, funding_cost_rate,
              source_version, rule_version, ingest_batch_id, trace_id
            ) values
              (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?),
              (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "2025-12-31",
                "GS-ADB-TYW-A",
                "\u62c6\u653e\u540c\u4e1a",
                "asset",
                "Bank A",
                "H",
                "AC",
                "asset",
                "CNY",
                "CNY",
                Decimal("50000000.00000000"),
                Decimal("0.00000000"),
                Decimal("2.20000000"),
                "sv_adb_gs_a_tyw",
                "rv_adb_gs_a",
                "ib_adb_gs_a",
                "tr_adb_gs_a_t1",
                "2025-12-31",
                "GS-ADB-TYW-L",
                "\u540c\u4e1a\u5b58\u653e",
                "liability",
                "Bank B",
                "H",
                "AC",
                "liability",
                "CNY",
                "CNY",
                Decimal("20000000.00000000"),
                Decimal("0.00000000"),
                Decimal("1.60000000"),
                "sv_adb_gs_a_tyw",
                "rv_adb_gs_a",
                "ib_adb_gs_a",
                "tr_adb_gs_a_t2",
            ],
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "average-balance-governance"))
    get_settings.cache_clear()


def _append_bond_analytics_completed_build(
    *,
    governance_path: Path,
    report_date: str,
    source_version: str,
    run_id: str,
) -> None:
    from backend.app.tasks.bond_analytics_materialize import CACHE_KEY, CACHE_VERSION, RULE_VERSION

    governance_path.mkdir(parents=True, exist_ok=True)
    record = {
        "run_id": run_id,
        "job_name": "bond_analytics_materialize",
        "status": "completed",
        "cache_key": CACHE_KEY,
        "cache_version": CACHE_VERSION,
        "source_version": source_version,
        "vendor_version": "vv_none",
        "rule_version": RULE_VERSION,
        "report_date": report_date,
    }
    with (governance_path / "cache_build_run.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _setup_bond_headline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    module = load_module(
        "tests._golden_bond_dashboard_api",
        "tests/test_bond_dashboard_api_contract.py",
    )

    duckdb_path = tmp_path / "bond-headline.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    repo = BondAnalyticsRepository(str(duckdb_path))
    with repository_task_write_scope("backend.app.tasks.golden_samples_capture_ready_test"):
        repo.replace_bond_analytics_rows(
            report_date="2026-03-30",
            rows=[
                module._make_bond_analytics_row(
                    report_date="2026-03-30",
                    instrument_code="RATE_PREV",
                    portfolio_name="P1",
                    asset_class_std="rate",
                    market_value=Decimal("120"),
                    ytm=Decimal("0.025"),
                    modified_duration=Decimal("3"),
                    bond_type_label="Gov",
                ),
                module._make_bond_analytics_row(
                    report_date="2026-03-30",
                    instrument_code="CREDIT_PREV",
                    portfolio_name="P2",
                    asset_class_std="credit",
                    market_value=Decimal("180"),
                    ytm=Decimal("0.035"),
                    modified_duration=Decimal("5"),
                    bond_type_label="Credit",
                ),
            ],
        )
        repo.replace_bond_analytics_rows(
            report_date="2026-03-31",
            rows=[
                module._make_bond_analytics_row(
                    report_date="2026-03-31",
                    instrument_code="RATE_CUR",
                    portfolio_name="P1",
                    asset_class_std="rate",
                    market_value=Decimal("100"),
                    ytm=Decimal("0.02"),
                    modified_duration=Decimal("2"),
                    bond_type_label="Gov",
                ),
                module._make_bond_analytics_row(
                    report_date="2026-03-31",
                    instrument_code="CREDIT_CUR",
                    portfolio_name="P2",
                    asset_class_std="credit",
                    market_value=Decimal("300"),
                    ytm=Decimal("0.04"),
                    modified_duration=Decimal("6"),
                    bond_type_label="Credit",
                ),
                module._make_bond_analytics_row(
                    report_date="2026-03-31",
                    instrument_code="OTHER_CUR",
                    portfolio_name="P3",
                    asset_class_std="other",
                    market_value=Decimal("600"),
                    ytm=Decimal("0"),
                    modified_duration=Decimal("0"),
                    bond_type_label="Other",
                ),
            ],
        )
    _append_bond_analytics_completed_build(
        governance_path=tmp_path / "gov",
        report_date="2026-03-31",
        source_version="sv",
        run_id="golden-sample:bond-headline:2026-03-31",
    )


def _setup_bond_analysis_action_attribution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    service_mod._action_attribution_cache.clear()

    monkeypatch.setattr(
        service_mod,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "duckdb_path": str(tmp_path / "bond-analysis-action-attribution.duckdb"),
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
            return ["2026-03-31", "2026-02-28"]

        def fetch_bond_analytics_rows(self, *, report_date, **_kwargs):
            common = {
                "instrument_code": "BOND-A",
                "portfolio_name": "FI Desk",
                "cost_center": "Desk 1",
                "asset_class_std": "rate",
                "accounting_class": "OCI",
                "source_version": "sv_bond_analysis_action_attr_gs_a",
            }
            if str(report_date) == "2026-02-28":
                return [
                    {
                        **common,
                        "market_value": Decimal("100000000"),
                        "modified_duration": Decimal("3.00"),
                    }
                ]
            return [
                {
                    **common,
                    "market_value": Decimal("120000000"),
                    "modified_duration": Decimal("3.20"),
                }
            ]

    class PnlRepo:
        def __init__(self, *_a, **_k):
            pass

        def merged_capital_gain_517_by_position_for_dates(self, dates):
            assert dates == ["2026-03-31"]
            return {"BOND-A::FI Desk::Desk 1": Decimal("1250000")}

    monkeypatch.setattr(service_mod, "BondAnalyticsRepository", Repo)
    monkeypatch.setattr(service_mod, "PnlRepository", PnlRepo)
    _append_bond_analytics_completed_build(
        governance_path=tmp_path / "governance",
        report_date="2026-03-31",
        source_version="sv_bond_analysis_action_attr_gs_a",
        run_id="golden-sample:bond-analysis-action-attribution:2026-03-31",
    )


def _setup_concentration_monitor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    monkeypatch.setattr(
        service_mod,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "duckdb_path": str(tmp_path / "concentration-monitor.duckdb"),
                "governance_path": tmp_path / "governance",
                "governance_sql_dsn": "",
                "postgres_dsn": "",
            },
        )(),
    )

    rows = [
        {
            "instrument_code": "CON-CREDIT-AAA",
            "issuer_name": "Issuer A",
            "industry_name": "Industry 1",
            "rating": "AAA",
            "tenor_bucket": "3Y",
            "asset_class_std": "credit",
            "accounting_class": "OCI",
            "market_value": Decimal("100"),
            "modified_duration": Decimal("4.00"),
            "years_to_maturity": Decimal("3"),
            "spread_dv01": Decimal("4"),
            "source_version": "sv_concentration_monitor_gs_a",
            "rule_version": "rv_concentration_monitor_gs_a",
        },
        {
            "instrument_code": "CON-CREDIT-AA",
            "issuer_name": "Issuer B",
            "industry_name": "Industry 1",
            "rating": "AA",
            "tenor_bucket": "5Y",
            "asset_class_std": "credit",
            "accounting_class": "TPL",
            "market_value": Decimal("60"),
            "modified_duration": Decimal("5.00"),
            "years_to_maturity": Decimal("5"),
            "spread_dv01": Decimal("3"),
            "source_version": "sv_concentration_monitor_gs_a",
            "rule_version": "rv_concentration_monitor_gs_a",
        },
        {
            "instrument_code": "CON-RATE-001",
            "issuer_name": "Treasury",
            "industry_name": "Rates",
            "rating": "AAA",
            "tenor_bucket": "1Y",
            "asset_class_std": "rate",
            "accounting_class": "AC",
            "market_value": Decimal("40"),
            "modified_duration": Decimal("1.00"),
            "years_to_maturity": Decimal("1"),
            "spread_dv01": Decimal("0"),
            "source_version": "sv_concentration_monitor_gs_a",
            "rule_version": "rv_concentration_monitor_gs_a",
        },
    ]

    class Repo:
        def __init__(self, *_a, **_k):
            pass

        def fetch_bond_analytics_rows(self, *, report_date, asset_class="all", **_kwargs):
            assert report_date == "2026-03-31"
            if asset_class == "credit":
                return [row for row in rows if row["asset_class_std"] == "credit"]
            return rows

    monkeypatch.setattr(service_mod, "_repo", lambda: Repo())
    monkeypatch.setattr(
        service_mod,
        "_fetch_credit_curves",
        lambda *, curve_repo, trade_date: {
            "treasury_current": None,
            "treasury_warning": "No treasury curve available for 2026-03-31.",
            "aaa_current": None,
            "aaa_warning": "No aaa_credit curve available for 2026-03-31.",
            "curve_snapshots": [],
            "curve_latest_fallback": False,
            "curve_unavailable": True,
        },
    )
    _append_bond_analytics_completed_build(
        governance_path=tmp_path / "governance",
        report_date="2026-03-31",
        source_version="sv_concentration_monitor_gs_a",
        run_id="golden-sample:concentration-monitor:2026-03-31",
    )


def _setup_market_data_rates_fragment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import duckdb

    duckdb_path = tmp_path / "market-data-rates-fragment.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              vendor_name varchar,
              vendor_version varchar,
              frequency varchar,
              unit varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "EMM00166466",
                    "中债国债到期收益率:10年",
                    "2026-04-10",
                    1.71,
                    "daily",
                    "%",
                    "sv_market_data_rates_gs_a",
                    "vv_choice_macro_gs_a",
                    "rv_choice_macro_public_history_v1",
                    "ok",
                    "gs-mkt-rates-a-1",
                ),
                (
                    "EMM00166466",
                    "中债国债到期收益率:10年",
                    "2026-04-09",
                    1.72,
                    "daily",
                    "%",
                    "sv_market_data_rates_gs_a",
                    "vv_choice_macro_gs_a",
                    "rv_choice_macro_public_history_v1",
                    "ok",
                    "gs-mkt-rates-a-2",
                ),
                (
                    "EMM00166462",
                    "中债国债到期收益率:5年",
                    "2026-04-10",
                    1.58,
                    "daily",
                    "%",
                    "sv_market_data_rates_gs_a",
                    "vv_choice_macro_gs_a",
                    "rv_choice_macro_public_history_v1",
                    "ok",
                    "gs-mkt-rates-a-3",
                ),
                (
                    "EMM00166498",
                    "中债国开债到期收益率:5年",
                    "2026-04-10",
                    2.05,
                    "daily",
                    "%",
                    "sv_market_data_rates_gs_a",
                    "vv_choice_macro_gs_a",
                    "rv_choice_macro_public_history_v1",
                    "ok",
                    "gs-mkt-rates-a-4",
                ),
                (
                    "EMM00166502",
                    "中债国开债到期收益率:10年",
                    "2026-04-10",
                    2.18,
                    "daily",
                    "%",
                    "sv_market_data_rates_gs_a",
                    "vv_choice_macro_gs_a",
                    "rv_choice_macro_public_history_v1",
                    "ok",
                    "gs-mkt-rates-a-5",
                ),
                (
                    "M001",
                    "公开市场7天逆回购利率",
                    "2026-04-10",
                    1.75,
                    "daily",
                    "%",
                    "sv_market_data_rates_gs_a",
                    "vv_choice_macro_gs_a",
                    "rv_choice_macro_public_history_v1",
                    "ok",
                    "gs-mkt-rates-a-6",
                ),
                (
                    "M002",
                    "DR007",
                    "2026-04-10",
                    1.83,
                    "daily",
                    "%",
                    "sv_public_funding",
                    "vv_public_repo",
                    "rv_choice_macro_public_history_v1",
                    "ok",
                    "gs-mkt-rates-a-7",
                ),
            ],
        )
        conn.executemany(
            """
            insert into phase1_macro_vendor_catalog values (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "EMM00166466",
                    "中债国债到期收益率:10年",
                    "choice",
                    "vv_choice_macro_gs_a",
                    "daily",
                    "%",
                ),
                (
                    "EMM00166462",
                    "中债国债到期收益率:5年",
                    "choice",
                    "vv_choice_macro_gs_a",
                    "daily",
                    "%",
                ),
                (
                    "EMM00166498",
                    "中债国开债到期收益率:5年",
                    "choice",
                    "vv_choice_macro_gs_a",
                    "daily",
                    "%",
                ),
                (
                    "EMM00166502",
                    "中债国开债到期收益率:10年",
                    "choice",
                    "vv_choice_macro_gs_a",
                    "daily",
                    "%",
                ),
                (
                    "M001",
                    "公开市场7天逆回购利率",
                    "choice",
                    "vv_choice_macro_gs_a",
                    "daily",
                    "%",
                ),
                (
                    "M002",
                    "DR007",
                    "choice",
                    "vv_public_repo",
                    "daily",
                    "%",
                ),
            ],
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    _grant_sample_read_scope(
        tmp_path,
        monkeypatch,
        db_name="market-data-rates-read-scope.db",
        resource="macro_vendor",
    )
    get_settings.cache_clear()


def _setup_stock_analysis_observation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import duckdb

    duckdb_path = tmp_path / "stock-analysis-observation.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('CA.CSI300', 'CSI 300 close', '2026-04-01', 3200.0, 'daily', 'index',
             'sv_stock_analysis_obs_gs_a', 'vv_choice_stock_obs_gs_a',
             'rv_choice_macro_public_history_v1', 'ok', 'stock-analysis-gs-a-1'),
            ('CA.CSI300', 'CSI 300 close', '2026-04-02', 3235.0, 'daily', 'index',
             'sv_stock_analysis_obs_gs_a', 'vv_choice_stock_obs_gs_a',
             'rv_choice_macro_public_history_v1', 'ok', 'stock-analysis-gs-a-2'),
            ('CA.CSI300', 'CSI 300 close', '2026-04-03', 3270.0, 'daily', 'index',
             'sv_stock_analysis_obs_gs_a', 'vv_choice_stock_obs_gs_a',
             'rv_choice_macro_public_history_v1', 'ok', 'stock-analysis-gs-a-3')
            """
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_CHOICE_STOCK_CATALOG_FILE", str(tmp_path / "missing-choice-stock-catalog.json"))
    get_settings.cache_clear()


def _setup_exec_overview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    governance_path = tmp_path / "governance"
    governance_path.mkdir(parents=True, exist_ok=True)
    cache_build_run_rows = []
    for report_date in ("2026-02-27", "2026-02-28"):
        cache_build_run_rows.extend(
            [
                {
                    "cache_key": service_mod.PNL_CACHE_KEY,
                    "job_name": service_mod.PNL_JOB_NAME,
                    "status": "completed",
                    "report_date": report_date,
                    "source_version": service_mod._DEFAULT_SOURCE,
                    "rule_version": service_mod._DEFAULT_RULE,
                    "cache_version": service_mod._CACHE_VERSION,
                    "vendor_version": "vv_none",
                },
                {
                    "cache_key": service_mod.BOND_ANALYTICS_CACHE_KEY,
                    "job_name": "bond_analytics_materialize",
                    "status": "completed",
                    "report_date": report_date,
                    "source_version": service_mod._DEFAULT_SOURCE,
                    "rule_version": service_mod._DEFAULT_RULE,
                    "cache_version": service_mod._CACHE_VERSION,
                    "vendor_version": "vv_none",
                },
            ]
        )
    (governance_path / f"{service_mod.CACHE_BUILD_RUN_STREAM}.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in cache_build_run_rows),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        service_mod,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "duckdb_path": str(tmp_path / "exec-overview.duckdb"),
                "governance_path": governance_path,
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


def _setup_pnl_attr_workbench(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service_mod = load_module(
        "backend.app.services.pnl_attribution_service",
        "backend/app/services/pnl_attribution_service.py",
    )

    monkeypatch.setattr(
        service_mod,
        "get_settings",
        lambda: type(
            "SettingsStub",
            (),
            {
                "duckdb_path": str(tmp_path / "pnl-attr-workbench.duckdb"),
                "governance_path": tmp_path / "governance",
                "governance_sql_dsn": "",
                "postgres_dsn": "",
            },
        )(),
    )

    class Repo:
        rows_by_date = {
            "2026-04-30": [
                {
                    "report_date": "2026-04-30",
                    "business_type_primary": "business_cd",
                    "business_type": "business_cd",
                    "currency_basis": "CNY",
                    "interest_income_514": 100.0,
                    "fair_value_change_516": 17.0,
                    "capital_gain_517": 3.0,
                    "manual_adjustment": 0.0,
                    "total_pnl": 120.0,
                    "scale_amount": 1_000.0,
                    "yield_pct": 12.0,
                    "pnl_row_count": 2,
                    "balance_row_count": 2,
                }
            ],
            "2026-03-31": [
                {
                    "report_date": "2026-03-31",
                    "business_type_primary": "business_cd",
                    "business_type": "business_cd",
                    "currency_basis": "CNY",
                    "interest_income_514": 70.0,
                    "fair_value_change_516": 10.0,
                    "capital_gain_517": 0.0,
                    "manual_adjustment": 0.0,
                    "total_pnl": 80.0,
                    "scale_amount": 800.0,
                    "yield_pct": 10.0,
                    "pnl_row_count": 1,
                    "balance_row_count": 1,
                }
            ],
        }

        def list_formal_fi_report_dates(self) -> list[str]:
            return ["2026-04-30", "2026-03-31"]

    def by_business_envelope(*, duckdb_path: str, governance_dir: str, report_date: str) -> dict[str, Any]:
        rows = list(Repo.rows_by_date.get(report_date, []))
        return {
            "result_meta": {
                "trace_id": f"tr_pnl_by_business_{report_date}",
                "basis": "formal",
                "result_kind": "pnl.by_business",
                "formal_use_allowed": True,
                "source_version": "sv_pnl_by_business_gs_attr_wb",
                "vendor_version": "vv_none",
                "rule_version": "rv_pnl_attr_wb_golden_v1",
                "cache_version": "cv_pnl_attr_wb_golden_v1",
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "scenario_flag": False,
                "as_of_date": report_date,
                "generated_at": "2026-04-30T00:00:00Z",
                "tables_used": [],
                "filters_applied": {},
                "evidence_rows": sum(
                    int(row.get("pnl_row_count") or 0) + int(row.get("balance_row_count") or 0)
                    for row in rows
                ),
                "next_drill": [],
            },
            "result": {
                "report_date": report_date,
                "source_tables": [
                    "fact_formal_pnl_fi",
                    "fact_nonstd_pnl_bridge",
                    "fact_formal_zqtz_balance_daily",
                ],
                "summary": {
                    "business_count": len(rows),
                    "total_pnl": str(sum(float(row.get("total_pnl") or 0) for row in rows)),
                    "total_scale_amount": str(sum(float(row.get("scale_amount") or 0) for row in rows)),
                    "traced_pnl_row_count": sum(int(row.get("pnl_row_count") or 0) for row in rows),
                    "untraced_pnl_row_count": 0,
                },
                "rows": rows,
            },
        }

    monkeypatch.setattr(service_mod, "_pnl_repo", lambda: Repo())
    monkeypatch.setattr(service_mod.pnl_service, "pnl_by_business_envelope", by_business_envelope)


def _ledger_fact(
    account_code: str,
    currency: str,
    *,
    ending_balance: str = "0",
    monthly_pnl: str = "0",
) -> Any:
    from backend.app.core_finance.product_category_pnl import CanonicalFactRow

    return CanonicalFactRow(
        report_date=date(2026, 4, 30),
        account_code=account_code,
        currency=currency,
        account_name=account_code,
        beginning_balance=Decimal("0"),
        ending_balance=Decimal(ending_balance),
        monthly_pnl=Decimal(monthly_pnl),
        daily_avg_balance=Decimal("0"),
        annual_avg_balance=Decimal("0"),
        days_in_period=30,
    )


def _setup_ledger_pnl_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service_mod = load_module(
        "backend.app.services.ledger_pnl_service",
        "backend/app/services/ledger_pnl_service.py",
    )

    facts = [
        _ledger_fact("10101000001", "CNX", ending_balance="100"),
        _ledger_fact("12301000001", "CNX", ending_balance="40"),
        _ledger_fact("14201000001", "CNX", ending_balance="10"),
        _ledger_fact("20101000001", "CNX", ending_balance="-50"),
        _ledger_fact("23401000001", "CNX", ending_balance="-30"),
        _ledger_fact("51401000001", "CNY", monthly_pnl="7"),
        _ledger_fact("51601000001", "CNX", monthly_pnl="3"),
    ]

    monkeypatch.setattr(
        service_mod,
        "_load_facts_for_date",
        lambda _source_dir, _report_date: (facts, "sv_ledger_pnl_summary_gs_a"),
    )


def _setup_bank_ledger_classification(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.test_ledger_import_flow import (
        _configure_ledger_import_env,
        _ledger_csv_bytes,
        _ledger_row_values,
        _scoped_import,
    )

    duckdb_path = _configure_ledger_import_env(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.ledger_import_service",
        "backend/app/services/ledger_import_service.py",
    )
    asset_pairs = (
        ("\u4ea4\u6613\u8d26\u6237", "\u4ea4\u6613\u6027\u8d44\u4ea7"),
        ("\u94f6\u884c\u8d26\u6237", "\u4ea4\u6613\u6027\u8d44\u4ea7"),
        ("\u94f6\u884c\u8d26\u6237", "\u53ef\u4f9b\u51fa\u552e\u7c7b\u8d44\u4ea7"),
        ("\u94f6\u884c\u8d26\u6237", "\u5e94\u6536\u6295\u8d44\u6b3e\u9879"),
        ("\u94f6\u884c\u8d26\u6237", "\u6301\u6709\u81f3\u5230\u671f\u7c7b\u8d44\u4ea7"),
    )
    rows = [
        _ledger_row_values(
            service_mod,
            bond_code=f"ASSET-{index}",
            account_category=account_category,
            asset_class=asset_class,
            face_amount="100000000",
            as_of_date="2026-03-17",
        )
        for index, (account_category, asset_class) in enumerate(asset_pairs, start=1)
    ]
    rows.extend(
        [
            _ledger_row_values(
                service_mod,
                bond_code="LIABILITY-1",
                account_category="\u53d1\u884c\u7c7b\u503a\u5238",
                asset_class="\u53d1\u884c\u7c7b\u503a\u5238",
                face_amount="200000000",
                as_of_date="2026-03-17",
            ),
            _ledger_row_values(
                service_mod,
                bond_code="UNCLASSIFIED-MISSING",
                account_category="",
                asset_class="",
                face_amount="300000000",
                as_of_date="2026-03-17",
            ),
            _ledger_row_values(
                service_mod,
                bond_code="UNCLASSIFIED-UNKNOWN",
                account_category="\u672a\u77e5\u8d26\u6237",
                asset_class="\u672a\u77e5\u8d44\u4ea7",
                face_amount="300000000",
                as_of_date="2026-03-17",
            ),
            _ledger_row_values(
                service_mod,
                bond_code="UNCLASSIFIED-CONFLICT",
                account_category="\u53d1\u884c\u7c7b\u503a\u5238",
                asset_class="\u6301\u6709\u81f3\u5230\u671f\u7c7b\u8d44\u4ea7",
                face_amount="300000000",
                as_of_date="2026-03-17",
            ),
        ]
    )
    _scoped_import(
        service_mod,
        duckdb_path,
        file_name="GS-BANK-LEDGER-CLASSIFICATION-A.csv",
        content=_ledger_csv_bytes(service_mod, rows),
    )


def _setup_cashflow_projection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )

    def fake_fetch_zqtz_rows(self, *, report_date, position_scope="all", currency_basis="CNY"):
        assert report_date == "2026-04-30"
        assert position_scope == "all"
        assert currency_basis == "CNY"
        return [
            {
                "instrument_code": "CF-BOND-001",
                "instrument_name": "Cashflow Bond A",
                "portfolio_name": "Liquidity Desk",
                "cost_center": "CF",
                "position_scope": "asset",
                "maturity_date": date(2026, 10, 30),
                "face_value_amount": Decimal("1000"),
                "market_value_amount": Decimal("1000"),
                "coupon_rate": Decimal("0"),
                "interest_mode": "bullet",
                "currency_code": "CNY",
                "source_version": "sv_cashflow_projection_gs_a_asset",
                "rule_version": "rv_cashflow_projection_gs_a",
            }
        ]

    def fake_fetch_tyw_rows(self, *, report_date, currency_basis="CNY"):
        assert report_date == "2026-04-30"
        assert currency_basis == "CNY"
        return [
            {
                "position_id": "CF-LIAB-001",
                "counterparty_name": "Funding Bank A",
                "product_type": "Term Funding",
                "position_scope": "liability",
                "position_side": "liability",
                "maturity_date": date(2026, 7, 30),
                "principal_amount": Decimal("800"),
                "funding_cost_rate": Decimal("0"),
                "currency_code": "CNY",
                "source_version": "sv_cashflow_projection_gs_a_liability",
                "rule_version": "rv_cashflow_projection_gs_a",
            }
        ]

    def fake_fetch_bond_analytics_rows(self, *, report_date, asset_class="all", accounting_class="all"):
        assert report_date == "2026-04-30"
        return [
            {
                "report_date": date(2026, 4, 30),
                "instrument_code": "CF-BOND-001",
                "portfolio_name": "Liquidity Desk",
                "cost_center": "CF",
                "currency_code": "CNY",
                "maturity_date": date(2026, 10, 30),
                "coupon_rate": Decimal("0"),
                "ytm": Decimal("0"),
                "macaulay_duration": Decimal("0.50"),
            }
        ]

    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_zqtz_rows",
        fake_fetch_zqtz_rows,
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
        fake_fetch_tyw_rows,
    )
    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        fake_fetch_bond_analytics_rows,
    )


def _run_sample_request(sample_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    request = _load_json(sample_id, "request.json")
    if sample_id == "GS-BOND-ANALYSIS-ACTION-ATTR-A":
        return _run_bond_analysis_action_attribution_payload(request)
    if sample_id == "GS-CONCENTRATION-MONITOR-A":
        return _run_concentration_monitor_payload(request)
    if sample_id == "GS-STOCK-ANALYSIS-OBS-A":
        return _run_stock_analysis_observation_payload(request, tmp_path)
    if sample_id == "GS-CASHFLOW-PROJECTION-A":
        return _run_cashflow_projection_payload(request)
    if sample_id == "GS-AVERAGE-BALANCE-A":
        return _run_average_balance_payload(request)
    if sample_id == "GS-AVERAGE-BALANCE-MONTHLY-A":
        return _run_average_balance_monthly_payload(request)
    return _run_request_payload(request, tmp_path, monkeypatch)


def _run_bond_analysis_action_attribution_payload(request: dict[str, Any]) -> dict[str, Any]:
    service_mod = sys.modules.get("backend.app.services.bond_analytics_service")
    if service_mod is None:
        pytest.fail("Bond-analysis golden-sample service fixture was not initialized.")
    params = dict(request.get("params") or {})
    return service_mod.get_action_attribution(
        date.fromisoformat(str(params["report_date"])),
        str(params.get("period_type") or "MoM"),
    )


def _run_concentration_monitor_payload(request: dict[str, Any]) -> dict[str, Any]:
    service_mod = sys.modules.get("backend.app.services.bond_analytics_service")
    if service_mod is None:
        pytest.fail("Concentration-monitor golden-sample service fixture was not initialized.")
    params = dict(request.get("params") or {})
    payload = service_mod.get_credit_spread_migration(
        date.fromisoformat(str(params["report_date"])),
        str(params.get("spread_scenarios") or "10,25,50"),
    )
    payload["result_meta"]["trace_id"] = "tr_concentration_monitor_gs_a"
    payload["result_meta"]["generated_at"] = "2026-06-09T00:00:00Z"
    payload["result"]["computed_at"] = "2026-06-09T00:00:00Z"
    return payload


def _run_stock_analysis_observation_payload(request: dict[str, Any], tmp_path: Path) -> dict[str, Any]:
    from backend.app.repositories.choice_stock_adapter import choice_stock_readiness_missing
    from backend.app.services.market_data_livermore_service import livermore_strategy_envelope

    params = dict(request.get("params") or {})
    payload = livermore_strategy_envelope(
        duckdb_path=str(tmp_path / "stock-analysis-observation.duckdb"),
        as_of_date=str(params["as_of_date"]),
        stock_readiness=choice_stock_readiness_missing(""),
    )
    payload["result_meta"]["trace_id"] = "tr_stock_analysis_obs_gs_a"
    payload["result_meta"]["generated_at"] = "2026-06-06T00:00:00Z"
    return payload


def _run_cashflow_projection_payload(request: dict[str, Any]) -> dict[str, Any]:
    service_mod = sys.modules.get("backend.app.services.cashflow_projection_service")
    if service_mod is None:
        pytest.fail("Cashflow golden-sample service fixture was not initialized.")
    params = dict(request.get("params") or {})
    payload = service_mod.get_cashflow_projection(date.fromisoformat(str(params["report_date"])))
    payload["result_meta"]["trace_id"] = "tr_cashflow_projection_gs_a"
    payload["result_meta"]["generated_at"] = "2026-06-09T00:00:00Z"
    payload["result"]["computed_at"] = "2026-06-09T00:00:00Z"
    return payload


def _run_average_balance_payload(request: dict[str, Any]) -> dict[str, Any]:
    service_mod = sys.modules.get("backend.app.services.adb_analysis_service")
    if service_mod is None:
        service_mod = load_module(
            "backend.app.services.adb_analysis_service",
            "backend/app/services/adb_analysis_service.py",
        )
    params = dict(request.get("params") or {})
    return service_mod.adb_envelope_for_dates(
        str(params["start_date"]),
        str(params["end_date"]),
    )


def _run_average_balance_monthly_payload(request: dict[str, Any]) -> dict[str, Any]:
    service_mod = sys.modules.get("backend.app.services.adb_analysis_service")
    if service_mod is None:
        service_mod = load_module(
            "backend.app.services.adb_analysis_service",
            "backend/app/services/adb_analysis_service.py",
        )
    params = dict(request.get("params") or {})
    return service_mod.adb_monthly_envelope(int(params["year"]))


def _run_request_payload(
    request: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    _clear_runtime_modules()
    headers: dict[str, str] | None = None
    if request["path"] in EXECUTIVE_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="executive-read-scope.db",
            resource="executive",
        )
        headers = EXECUTIVE_READ_HEADERS
    elif request["path"] in BOND_DASHBOARD_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="bond-dashboard-read-scope.db",
            resource="bond_dashboard",
        )
        headers = BOND_DASHBOARD_READ_HEADERS
    elif request["path"] in BOND_ANALYSIS_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="bond-analysis-read-scope.db",
            resource="bond_analytics",
        )
        headers = BOND_ANALYSIS_READ_HEADERS
    elif request["path"] in CONCENTRATION_MONITOR_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="concentration-monitor-read-scope.db",
            resource="bond_analytics",
        )
        headers = CONCENTRATION_MONITOR_READ_HEADERS
    elif request["path"] in STOCK_ANALYSIS_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="stock-analysis-read-scope.db",
            resource="market_data.livermore",
        )
        headers = STOCK_ANALYSIS_READ_HEADERS
    elif request["path"] in PNL_ATTRIBUTION_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="pnl-attribution-read-scope.db",
            resource="pnl_attribution",
        )
        headers = PNL_ATTRIBUTION_READ_HEADERS
    elif request["path"] in LEDGER_PNL_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="ledger-pnl-read-scope.db",
            resource="ledger_pnl",
        )
        headers = LEDGER_PNL_READ_HEADERS
    elif request["path"] in CASHFLOW_PROJECTION_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="cashflow-projection-read-scope.db",
            resource="cashflow_projection",
        )
        headers = CASHFLOW_PROJECTION_READ_HEADERS
    elif request["path"] in PNL_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="pnl-read-scope.db",
            resource="pnl",
        )
        headers = PNL_READ_HEADERS
    elif request["path"] in PNL_BUSINESS_INSIGHTS_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="pnl-business-insights-read-scope.db",
            resource="pnl",
        )
        headers = PNL_BUSINESS_INSIGHTS_READ_HEADERS
    elif request["path"] in PRODUCT_CATEGORY_PNL_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="product-category-pnl-read-scope.db",
            resource="product_category_pnl",
        )
        headers = PRODUCT_CATEGORY_PNL_READ_HEADERS
    elif request["path"] in RISK_TENSOR_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="risk-tensor-read-scope.db",
            resource="risk_tensor",
        )
        headers = RISK_TENSOR_READ_HEADERS
    elif request["path"] in AVERAGE_BALANCE_SAMPLE_PATHS:
        _grant_sample_read_scope(
            tmp_path,
            monkeypatch,
            db_name="average-balance-read-scope.db",
            resource="adb_analysis",
        )
        headers = AVERAGE_BALANCE_READ_HEADERS
    elif request["path"] in MARKET_DATA_RATES_SAMPLE_PATHS:
        headers = MARKET_DATA_RATES_READ_HEADERS
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.request(
        request["method"],
        request["path"],
        params=request.get("params"),
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _grant_sample_read_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    db_name: str,
    resource: str,
) -> None:
    sqlite_path = tmp_path / db_name
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource=resource,
        action="read",
    )


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


def _validate_product_category_scenario(
    actual: dict[str, Any],
    baseline_expected: dict[str, Any],
) -> None:
    assert actual["result_meta"]["basis"] == "scenario"
    assert actual["result_meta"]["result_kind"] == "product_category_pnl.detail"
    assert actual["result_meta"]["formal_use_allowed"] is False
    assert actual["result_meta"]["vendor_version"] == "vv_none"
    assert actual["result_meta"]["rule_version"] == "rv_product_category_pnl_v1"
    assert actual["result_meta"]["cache_version"] == "cv_product_category_pnl_v1"
    assert actual["result_meta"]["quality_flag"] == "ok"
    assert actual["result_meta"]["vendor_status"] == "ok"
    assert actual["result_meta"]["fallback_mode"] == "none"
    assert actual["result_meta"]["scenario_flag"] is True
    assert actual["result"]["report_date"] == "2026-02-28"
    assert actual["result"]["view"] == "monthly"
    assert actual["result"]["available_views"] == baseline_expected["result"]["available_views"]
    assert actual["result"]["scenario_rate_pct"] == 2.5
    actual_rows = actual["result"]["rows"]
    baseline_rows = baseline_expected["result"]["rows"]
    assert len(actual_rows) == len(baseline_rows)
    assert _row_ids(actual_rows) == _row_ids(baseline_rows)

    scenario_row_map = _rows_by_category(actual_rows)
    baseline_row_map = _rows_by_category(baseline_rows)
    scenario_only_fields = {
        "cny_ftp",
        "foreign_ftp",
        "cny_net",
        "foreign_net",
        "business_net_income",
        "scenario_rate_pct",
    }

    for actual_row, baseline_row in zip(actual_rows, baseline_rows, strict=True):
        assert actual_row["children"] == baseline_row["children"], actual_row["category_id"]
        for field, value in baseline_row.items():
            if field not in scenario_only_fields:
                assert actual_row[field] == value, (actual_row["category_id"], field)
        assert Decimal(str(actual_row["scenario_rate_pct"])) == Decimal("2.5"), actual_row["category_id"]

    for total_key in ("asset_total", "liability_total", "grand_total"):
        assert actual["result"][total_key] == scenario_row_map[total_key]

    assert scenario_row_map["bond_investment"]["children"] == baseline_row_map["bond_investment"]["children"]
    assert Decimal(str(scenario_row_map["bond_tpl"]["cny_ftp"])) != Decimal(str(baseline_row_map["bond_tpl"]["cny_ftp"]))
    assert Decimal(str(scenario_row_map["bond_ac"]["cny_ftp"])) != Decimal(str(baseline_row_map["bond_ac"]["cny_ftp"]))
    assert Decimal(str(scenario_row_map["bond_valuation_spread"]["cny_ftp"])) == Decimal(
        str(baseline_row_map["bond_valuation_spread"]["cny_ftp"])
    )
    assert scenario_row_map["bond_valuation_spread"]["weighted_yield"] is None
    assert Decimal(str(scenario_row_map["asset_total"]["cny_ftp"])) != Decimal(str(baseline_row_map["asset_total"]["cny_ftp"]))
    assert Decimal(str(actual["result"]["liability_total"]["cny_ftp"])) != Decimal(
        str(baseline_expected["result"]["liability_total"]["cny_ftp"])
    )
    assert Decimal(str(actual["result"]["grand_total"]["cny_ftp"])) != Decimal(
        str(baseline_expected["result"]["grand_total"]["cny_ftp"])
    )


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


def _validate_bond_headline(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    _assert_paths_equal(
        actual,
        expected,
        [
            ("data_source",),
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
            ("result_meta", "filters_applied"),
            ("result_meta", "tables_used"),
            ("result_meta", "evidence_rows"),
            ("result_meta", "next_drill"),
            ("result_meta", "source_surface"),
            ("result",),
        ],
    )


def _validate_bond_analysis_action_attribution(actual: dict[str, Any], expected: dict[str, Any]) -> None:
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
            ("result_meta", "source_surface"),
            ("result", "report_date"),
            ("result", "period_type"),
            ("result", "period_start"),
            ("result", "period_end"),
            ("result", "total_actions"),
            ("result", "total_pnl_from_actions"),
            ("result", "period_start_duration"),
            ("result", "period_end_duration"),
            ("result", "duration_change_from_actions"),
            ("result", "period_start_dv01"),
            ("result", "period_end_dv01"),
            ("result", "status"),
            ("result", "available_components"),
            ("result", "missing_inputs"),
            ("result", "blocked_components"),
            ("result", "warnings"),
        ],
    )


def _validate_concentration_monitor(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    actual["result_meta"]["trace_id"] = expected["result_meta"]["trace_id"]
    actual["result_meta"]["generated_at"] = expected["result_meta"]["generated_at"]
    actual["result"]["computed_at"] = expected["result"]["computed_at"]
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
            ("result_meta", "requested_report_date"),
            ("result_meta", "resolved_report_date"),
            ("result_meta", "as_of_date"),
            ("result_meta", "date_basis"),
            ("result_meta", "filters_applied"),
            ("result_meta", "tables_used"),
            ("result_meta", "evidence_rows"),
            ("result_meta", "source_surface"),
            ("result", "report_date"),
            ("result", "credit_bond_count"),
            ("result", "credit_market_value"),
            ("result", "credit_weight"),
            ("result", "rating_aa_and_below_weight"),
            ("result", "spread_dv01"),
            ("result", "weighted_avg_spread"),
            ("result", "weighted_avg_spread_duration"),
            ("result", "spread_scenarios"),
            ("result", "migration_scenarios"),
            ("result", "concentration_by_issuer"),
            ("result", "concentration_by_industry"),
            ("result", "concentration_by_rating"),
            ("result", "concentration_by_tenor"),
            ("result", "oci_credit_exposure"),
            ("result", "oci_spread_dv01"),
            ("result", "oci_sensitivity_25bp"),
            ("result", "warnings"),
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


def _validate_pnl_attr_workbench(actual: dict[str, Any], expected: dict[str, Any]) -> None:
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
            ("result_meta", "filters_applied"),
            ("result_meta", "tables_used"),
            ("result_meta", "evidence_rows"),
            ("result_meta", "as_of_date"),
            ("result_meta", "source_surface"),
            ("result", "current_period"),
            ("result", "previous_period"),
            ("result", "compare_type"),
            ("result", "total_current_pnl"),
            ("result", "total_previous_pnl"),
            ("result", "total_volume_effect"),
            ("result", "total_rate_effect"),
            ("result", "total_interaction_effect"),
            ("result", "total_recon_error"),
            ("result", "items"),
            ("result", "has_previous_data"),
        ],
    )


def _validate_ledger_pnl_summary(actual: dict[str, Any], expected: dict[str, Any]) -> None:
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
            ("result_meta", "requested_report_date"),
            ("result_meta", "resolved_report_date"),
            ("result_meta", "as_of_date"),
            ("result_meta", "date_basis"),
            ("result_meta", "filters_applied"),
            ("result_meta", "tables_used"),
            ("result_meta", "evidence_rows"),
            ("result", "report_date"),
            ("result", "source_version"),
            ("result", "ledger_total_assets"),
            ("result", "ledger_total_liabilities"),
            ("result", "ledger_net_assets"),
            ("result", "ledger_monthly_pnl_core"),
            ("result", "ledger_monthly_pnl_all"),
            ("result", "by_currency"),
            ("result", "by_account"),
        ],
    )


def _validate_bank_ledger_classification(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    actual["trace"]["request_id"] = expected["trace"]["request_id"]
    _assert_paths_equal(
        actual,
        expected,
        [
            ("data", "as_of_date"),
            ("data", "classification_status"),
            ("data", "classification_rule_version"),
            ("data", "currency_breakdown"),
            ("metadata", "source_version"),
            ("metadata", "rule_version"),
            ("metadata", "fallback"),
            ("metadata", "stale"),
            ("metadata", "no_data"),
            ("metadata", "batch_id"),
            ("trace", "requested_as_of_date"),
            ("trace", "resolved_as_of_date"),
            ("trace", "batch_id"),
        ],
    )


def _validate_cashflow_projection(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    actual["result_meta"]["trace_id"] = expected["result_meta"]["trace_id"]
    actual["result_meta"]["generated_at"] = expected["result_meta"]["generated_at"]
    actual["result"]["computed_at"] = expected["result"]["computed_at"]
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
            ("result_meta", "requested_report_date"),
            ("result_meta", "resolved_report_date"),
            ("result_meta", "as_of_date"),
            ("result_meta", "date_basis"),
            ("result_meta", "filters_applied"),
            ("result_meta", "tables_used"),
            ("result_meta", "evidence_rows"),
            ("result_meta", "source_surface"),
            ("result", "report_date"),
            ("result", "duration_gap"),
            ("result", "asset_duration"),
            ("result", "liability_duration"),
            ("result", "equity_duration"),
            ("result", "rate_sensitivity_1bp"),
            ("result", "reinvestment_risk_12m"),
            ("result", "monthly_buckets"),
            ("result", "top_maturing_assets_12m"),
            ("result", "warnings"),
        ],
    )


def _validate_market_data_rates_fragment(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    actual["result_meta"]["generated_at"] = expected["result_meta"]["generated_at"]
    actual["result_meta"]["trace_id"] = expected["result_meta"]["trace_id"]
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
            ("result_meta", "source_surface"),
            ("result", "read_target"),
        ],
    )
    actual_by_id = {str(item["series_id"]): item for item in actual["result"]["series"]}
    expected_by_id = {str(item["series_id"]): item for item in expected["result"]["series"]}
    assert set(actual_by_id) == set(expected_by_id)
    for series_id, expected_item in expected_by_id.items():
        actual_item = actual_by_id[series_id]
        assert actual_item["trade_date"] == expected_item["trade_date"]
        assert actual_item["value_numeric"] == expected_item["value_numeric"]
        assert actual_item["unit"] == expected_item["unit"]
        if "latest_change" in expected_item:
            assert actual_item.get("latest_change") == expected_item["latest_change"]


def _validate_stock_analysis_observation(actual: dict[str, Any], expected: dict[str, Any]) -> None:
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
            ("result_meta", "filters_applied"),
            ("result_meta", "tables_used"),
            ("result_meta", "evidence_rows"),
            ("result", "as_of_date"),
            ("result", "requested_as_of_date"),
            ("result", "strategy_name"),
            ("result", "basis"),
            ("result", "market_gate", "state"),
            ("result", "supported_outputs"),
            ("result", "unsupported_outputs"),
            ("result", "data_gaps"),
            ("result", "rule_readiness"),
        ],
    )


def _validate_average_balance(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    actual["result_meta"]["generated_at"] = expected["result_meta"]["generated_at"]
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
            ("result_meta", "filters_applied"),
            ("result_meta", "tables_used"),
            ("result_meta", "evidence_rows"),
            ("result", "summary"),
            ("result", "trend"),
            ("result", "breakdown"),
        ],
    )


def _validate_average_balance_monthly(actual: dict[str, Any], expected: dict[str, Any]) -> None:
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
            ("result_meta", "filters_applied"),
            ("result_meta", "tables_used"),
            ("result", "year"),
            ("result", "months", 0, "month"),
            ("result", "months", 0, "num_days"),
            ("result", "months", 0, "avg_assets"),
            ("result", "months", 0, "avg_liabilities"),
            ("result", "months", 0, "end_spot_assets"),
            ("result", "months", 0, "end_spot_liabilities"),
            ("result", "months", 0, "mom_change_assets"),
            ("result", "months", 0, "mom_change_pct_assets"),
            ("result", "months", 0, "mom_change_liabilities"),
            ("result", "months", 0, "mom_change_pct_liabilities"),
            ("result", "months", 0, "asset_yield"),
            ("result", "months", 0, "liability_cost"),
            ("result", "months", 0, "net_interest_margin"),
            ("result", "ytd_avg_assets"),
            ("result", "ytd_avg_liabilities"),
            ("result", "ytd_asset_yield"),
            ("result", "ytd_liability_cost"),
            ("result", "ytd_nim"),
            ("result", "unit"),
        ],
    )


def _validate_pnl_business_insights(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    actual["result_meta"]["trace_id"] = expected["result_meta"]["trace_id"]
    actual["result_meta"]["generated_at"] = expected["result_meta"]["generated_at"]
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
            ("result_meta", "requested_report_date"),
            ("result_meta", "resolved_report_date"),
            ("result_meta", "as_of_date"),
            ("result_meta", "filters_applied"),
            ("result_meta", "tables_used"),
            ("result", "result_version"),
            ("result", "year"),
            ("result", "as_of_date"),
            ("result", "baseline_requested_report_date"),
            ("result", "baseline_resolved_report_date"),
            ("result", "baseline_fallback_mode"),
            ("result", "component_evidence"),
            ("result", "concentration"),
            ("result", "negative_ftp_persistence"),
            ("result", "share_drift"),
            ("result", "scale_yield_quadrant"),
            ("result", "reconciliation_diagnostics"),
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
    "GS-BOND-HEADLINE-A": CaptureReadyCase(setup=_setup_bond_headline, validator=_validate_bond_headline),
    "GS-BOND-ANALYSIS-ACTION-ATTR-A": CaptureReadyCase(
        setup=_setup_bond_analysis_action_attribution,
        validator=_validate_bond_analysis_action_attribution,
    ),
    "GS-CONCENTRATION-MONITOR-A": CaptureReadyCase(
        setup=_setup_concentration_monitor,
        validator=_validate_concentration_monitor,
    ),
    "GS-STOCK-ANALYSIS-OBS-A": CaptureReadyCase(
        setup=_setup_stock_analysis_observation,
        validator=_validate_stock_analysis_observation,
    ),
    "GS-MKT-RATES-FRAGMENT-A": CaptureReadyCase(
        setup=_setup_market_data_rates_fragment,
        validator=_validate_market_data_rates_fragment,
    ),
    "GS-EXEC-OVERVIEW-A": CaptureReadyCase(setup=_setup_exec_overview, validator=_validate_exec_overview),
    "GS-EXEC-PNL-ATTR-A": CaptureReadyCase(setup=_setup_exec_pnl_attr, validator=_validate_exec_pnl_attr),
    "GS-EXEC-SUMMARY-A": CaptureReadyCase(setup=_setup_exec_summary, validator=_validate_exec_summary),
    "GS-PNL-ATTR-WB-A": CaptureReadyCase(setup=_setup_pnl_attr_workbench, validator=_validate_pnl_attr_workbench),
    "GS-LEDGER-PNL-SUMMARY-A": CaptureReadyCase(
        setup=_setup_ledger_pnl_summary,
        validator=_validate_ledger_pnl_summary,
    ),
    "GS-BANK-LEDGER-CLASSIFICATION-A": CaptureReadyCase(
        setup=_setup_bank_ledger_classification,
        validator=_validate_bank_ledger_classification,
    ),
    "GS-CASHFLOW-PROJECTION-A": CaptureReadyCase(
        setup=_setup_cashflow_projection,
        validator=_validate_cashflow_projection,
    ),
    "GS-AVERAGE-BALANCE-A": CaptureReadyCase(
        setup=_setup_average_balance,
        validator=_validate_average_balance,
    ),
    "GS-AVERAGE-BALANCE-MONTHLY-A": CaptureReadyCase(
        setup=_setup_average_balance,
        validator=_validate_average_balance_monthly,
    ),
    "GS-PNL-BUSINESS-INSIGHTS-A": CaptureReadyCase(
        setup=_setup_pnl_business_insights,
        validator=_validate_pnl_business_insights,
    ),
}

SPECIALIZED_CAPTURE_READY_CASE_TESTS: dict[str, tuple[str, str]] = {
    "GS-LEDGER-PNL-NET-INTEREST-202606-A": (
        "tests/test_ledger_pnl_net_interest_golden_sample.py",
        "test_committed_synthetic_fixture_executes_the_production_calculation_chain",
    ),
}
CAPTURE_READY_SAMPLE_IDS = frozenset(CAPTURE_READY_CASES) | frozenset(
    SPECIALIZED_CAPTURE_READY_CASE_TESTS
)

SUPPORTING_ONLY_SAMPLE_IDS = {"GS-PORTFOLIO-HOME-A"}


def test_capture_ready_golden_sample_files_exist() -> None:
    for sample_id in CAPTURE_READY_CASES:
        for filename in ("request.json", "response.json", "assertions.md", "approval.md"):
            assert _sample_file(sample_id, filename).exists()


def test_specialized_capture_ready_cases_have_dedicated_gate_and_files() -> None:
    from scripts.backend_release_suite import RELEASE_SUITE_TESTS

    for sample_id, (test_path, test_name) in SPECIALIZED_CAPTURE_READY_CASE_TESTS.items():
        assert sample_id not in CAPTURE_READY_CASES
        assert (ROOT / test_path).exists()
        assert test_path in RELEASE_SUITE_TESTS
        module = load_module(
            f"tests._specialized_capture_ready_{sample_id.lower().replace('-', '_')}",
            test_path,
        )
        test_callable = getattr(module, test_name)
        assert callable(test_callable)
        module_marks = getattr(module, "pytestmark", ())
        if not isinstance(module_marks, (list, tuple)):
            module_marks = (module_marks,)
        all_marks = (*module_marks, *getattr(test_callable, "pytestmark", ()))
        assert not {mark.name for mark in all_marks} & {"skip", "skipif", "xfail"}
        for filename in ("request.json", "response.json", "assertions.md", "approval.md"):
            assert _sample_file(sample_id, filename).exists()


def test_supporting_only_golden_sample_files_exist_without_capture_ready_claim() -> None:
    for sample_id in SUPPORTING_ONLY_SAMPLE_IDS:
        assert sample_id not in CAPTURE_READY_CASES
        for filename in ("request.json", "response.json", "assertions.md", "approval.md"):
            assert _sample_file(sample_id, filename).exists()

        approval = _read_text(sample_id, "approval.md")
        assertions = _read_text(sample_id, "assertions.md")
        response = _load_json(sample_id, "response.json")

        assert "supporting-only" in approval
        assert "captured-awaiting-approval" not in approval
        assert "formal_use_allowed=false" in assertions
        assert response["governance_status"]["formal_use_allowed"] is False
        assert response["frontend_gate_observation"]["proves_page_execution"] is False
        assert response["risk_evidence"]["risk_closure_ready"] is True
        assert response["risk_evidence"]["risk_report_date"] == response["decision_anchor_date"]
        assert response["risk_evidence"]["risk_result_meta_date"] == response["decision_anchor_date"]


def test_capture_ready_golden_sample_metadata_is_in_expected_state() -> None:
    for sample_id in CAPTURE_READY_CASES:
        approval = _read_text(sample_id, "approval.md")
        if sample_id == "GS-PNL-BUSINESS-INSIGHTS-A":
            assert "- Status: `approved`" in approval
        else:
            assert "captured-awaiting-approval" in approval


def test_product_category_capture_ready_companion_scenario_files_exist() -> None:
    for filename in ("scenario.request.json",):
        assert _sample_file("GS-PROD-CAT-PNL-A", filename).exists()


def test_bank_ledger_classification_sample_freezes_allowlist_and_fail_closed_pairs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_bank_ledger_classification(tmp_path, monkeypatch)
    conn = duckdb.connect(str(tmp_path / "moss.duckdb"), read_only=True)
    try:
        directions = dict(
            conn.execute(
                "select bond_code, direction from position_snapshot order by row_no"
            ).fetchall()
        )
    finally:
        conn.close()

    assert directions == {
        "ASSET-1": "ASSET",
        "ASSET-2": "ASSET",
        "ASSET-3": "ASSET",
        "ASSET-4": "ASSET",
        "ASSET-5": "ASSET",
        "LIABILITY-1": "LIABILITY",
        "UNCLASSIFIED-MISSING": "UNCLASSIFIED",
        "UNCLASSIFIED-UNKNOWN": "UNCLASSIFIED",
        "UNCLASSIFIED-CONFLICT": "UNCLASSIFIED",
    }


def test_product_category_sample_documents_approved_metric_boundary() -> None:
    assertions = _read_text("GS-PROD-CAT-PNL-A", "assertions.md")
    sample_doc = (ROOT / "docs" / "pnl" / "product-category-golden-sample-a.md").read_text(encoding="utf-8")
    combined = "\n".join((assertions, sample_doc))

    for metric_id in tuple(f"MTR-PCP-{index:03d}" for index in range(1, 13)):
        assert metric_id in combined

    for required in (
        "The approved sample-to-metric bindings include the three headline totals:",
        "Decision 3C activates these row-level detail metric bindings for `result.rows[]`",
        "This sample is now bound to the three headline `metric_id` values and the decision 3C row-level detail metric set.",
        "Scenario outputs remain analytical scenario payloads unless a future decision explicitly promotes them.",
    ):
        assert required in combined

    assert "not yet at approved `metric_id` level" not in combined


def test_product_category_companion_scenario_documents_promotion_gate() -> None:
    assertions = _read_text("GS-PROD-CAT-PNL-A", "assertions.md")
    sample_doc = (ROOT / "docs" / "pnl" / "product-category-golden-sample-a.md").read_text(encoding="utf-8")
    combined = "\n".join((assertions, sample_doc))

    for required in (
        "Scenario promotion gate",
        "A separate scenario `request.json` and `response.json` pair captured from the governed endpoint.",
        "Scenario-specific assertions that freeze row identity, category tree, scenario-owned FTP deltas, and unchanged non-scenario fields.",
        "No new scenario `metric_id` binding without an approved metric matrix and metric dictionary rows.",
        "Business-owner or delegated approval recorded in a non-placeholder scenario approval artifact.",
    ):
        assert required in combined


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


def test_product_category_capture_ready_companion_scenario_matches_selected_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = CAPTURE_READY_CASES["GS-PROD-CAT-PNL-A"]
    try:
        case.setup(tmp_path, monkeypatch)
        baseline_expected = _load_json("GS-PROD-CAT-PNL-A", "response.json")
        scenario_request = _load_json("GS-PROD-CAT-PNL-A", "scenario.request.json")
        actual = _run_request_payload(scenario_request, tmp_path, monkeypatch)
        _validate_product_category_scenario(actual, baseline_expected)
    finally:
        get_settings.cache_clear()
