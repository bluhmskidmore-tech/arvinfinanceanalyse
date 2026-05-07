"""Contract tests for ADB (/api/analysis/adb*)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from tests.helpers import load_module
from tests.test_balance_analysis_api import _configure_and_materialize
from tests.test_balance_analysis_materialize_flow import _patch_skip_fx_refresh


BOND_ASSET_CLASS = "\u503a\u5238\u7c7b"
BOND_GOV = "\u56fd\u503a"
BOND_CORP = "\u4fe1\u7528\u503a\u5238-\u4f01\u4e1a"
# bond_type BOND_CORP is classified as 非金融企业债券 (zqtz_asset_bond_category)
BOND_CORP_ZQTZ_CATEGORY = "\u975e\u91d1\u878d\u4f01\u4e1a\u503a\u5238"
BOND_CERT = "\u51ed\u8bc1\u5f0f\u56fd\u503a"
# 凭证式国债在 ZQTZ 资产类目中的 row_label
BOND_CERT_ZQTZ_CATEGORY = (
    "\u56fd\u503a\uff08\u542b\u51ed\u8bc1\u5f0f\u56fd\u503a\uff09"
)
INTERBANK_PLACE = "\u540c\u4e1a\u5b58\u653e"
POSITION_ASSET = "\u8d44\u4ea7"
POSITION_LIABILITY = "\u8d1f\u503a"
INTEREST_FIXED = "\u56fa\u5b9a"
MONTH_LABEL_JAN = "2025\u5e741\u6708"
MONTH_LABEL_FEB = "2025\u5e742\u6708"


def test_assign_zqtz_bond_categories_reuses_duplicate_asset_classifications(monkeypatch) -> None:
    from backend.app.services import adb_analysis_service

    calls: list[dict[str, object]] = []

    def _fake_classifier(row: dict[str, object]) -> str:
        calls.append(row)
        return f"asset-category-{row.get('bond_type')}-{row.get('instrument_code')}"

    monkeypatch.setattr(adb_analysis_service, "classify_zqtz_asset_bond_label", _fake_classifier)

    rows = [
        {
            "report_date": "2026-01-01",
            "market_value": Decimal("100"),
            "yield_to_maturity": Decimal("2.1"),
            "coupon_rate": Decimal("2.0"),
            "interest_rate": 0.0,
            "asset_class": "asset",
            "bond_type": "gov",
            "sub_type": "",
            "business_type_primary": "primary-a",
            "business_type_final": "final-a",
            "instrument_code": "BOND-001",
            "instrument_name": "Bond 001",
            "currency_code": "CNY",
            "accounting_basis": "FVOCI",
            "is_issuance_like": False,
        },
        {
            "report_date": "2026-01-02",
            "market_value": Decimal("110"),
            "yield_to_maturity": Decimal("2.2"),
            "coupon_rate": Decimal("2.0"),
            "interest_rate": 0.0,
            "asset_class": "asset",
            "bond_type": "gov",
            "sub_type": "",
            "business_type_primary": "primary-a",
            "business_type_final": "final-a",
            "instrument_code": "BOND-001",
            "instrument_name": "Bond 001",
            "currency_code": "CNY",
            "accounting_basis": "FVOCI",
            "is_issuance_like": False,
        },
        {
            "report_date": "2026-01-03",
            "market_value": Decimal("120"),
            "yield_to_maturity": Decimal("2.3"),
            "coupon_rate": Decimal("2.0"),
            "interest_rate": 0.0,
            "asset_class": "asset",
            "bond_type": "gov",
            "sub_type": "",
            "business_type_primary": "primary-a",
            "business_type_final": "final-a",
            "instrument_code": "BOND-001",
            "instrument_name": "Bond 001",
            "currency_code": "CNY",
            "accounting_basis": "FVOCI",
            "is_issuance_like": False,
        },
        {
            "report_date": "2026-01-01",
            "market_value": Decimal("200"),
            "yield_to_maturity": Decimal("2.5"),
            "coupon_rate": Decimal("2.4"),
            "interest_rate": 0.0,
            "asset_class": "asset",
            "bond_type": "policy",
            "sub_type": "",
            "business_type_primary": "primary-b",
            "business_type_final": "final-b",
            "instrument_code": "BOND-002",
            "instrument_name": "Bond 002",
            "currency_code": "CNY",
            "accounting_basis": "FVOCI",
            "is_issuance_like": False,
        },
        {
            "report_date": "2026-01-01",
            "market_value": Decimal("300"),
            "yield_to_maturity": Decimal("2.8"),
            "coupon_rate": Decimal("2.7"),
            "interest_rate": 0.0,
            "asset_class": "asset",
            "bond_type": "liability-bond",
            "sub_type": "issued-sub-type",
            "business_type_primary": "",
            "business_type_final": "",
            "instrument_code": "ISS-001",
            "instrument_name": "Issued 001",
            "currency_code": "CNY",
            "accounting_basis": "FVOCI",
            "is_issuance_like": True,
        },
    ]

    result = adb_analysis_service._assign_zqtz_bond_categories(pd.DataFrame(rows))

    assert list(result["bond_category"]) == [
        "asset-category-gov-BOND-001",
        "asset-category-gov-BOND-001",
        "asset-category-gov-BOND-001",
        "asset-category-policy-BOND-002",
        "issued-sub-type",
    ]
    assert len(calls) == 2


def _ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    snapshot_mod = load_module(
        "backend.app.repositories.snapshot_repo",
        "backend/app/repositories/snapshot_repo.py",
    )
    snapshot_mod.ensure_snapshot_tables(conn)


def _insert_zqtz(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    instrument_code: str,
    bond_type: str,
    market_value: Decimal,
    is_issuance_like: bool,
    coupon_rate: Decimal = Decimal("0.03"),
    ytm_value: Decimal = Decimal("0.035"),
) -> None:
    conn.execute(
        """
        insert into zqtz_bond_daily_snapshot (
          report_date, instrument_code, instrument_name, portfolio_name, cost_center,
          account_category, asset_class, bond_type, issuer_name, industry_name, rating,
          currency_code, face_value_native, market_value_native, amortized_cost_native,
          accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
          overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
          ingest_batch_id, trace_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            report_date,
            instrument_code,
            instrument_code,
            "p1",
            "cc1",
            "持有至到期",
            BOND_ASSET_CLASS,
            bond_type,
            "issuer-x",
            "\u94f6\u884c",
            "AAA",
            "CNY",
            market_value,
            market_value,
            market_value,
            Decimal("0"),
            coupon_rate,
            ytm_value,
            "2030-01-01",
            None,
            0,
            is_issuance_like,
            INTEREST_FIXED,
            "sv-adb",
            "rv-adb",
            "ib-adb",
            "tr-adb",
        ],
    )


def _insert_tyw(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    position_id: str,
    product_type: str,
    position_side: str,
    principal: Decimal,
    rate: Decimal,
) -> None:
    conn.execute(
        """
        insert into tyw_interbank_daily_snapshot (
          report_date, position_id, product_type, position_side, counterparty_name,
          account_type, special_account_type, core_customer_type, currency_code,
          principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
          pledged_bond_code, source_version, rule_version, ingest_batch_id, trace_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            report_date,
            position_id,
            product_type,
            position_side,
            "cp",
            "acct",
            None,
            None,
            "CNY",
            principal,
            Decimal("0"),
            rate,
            "2030-01-01",
            None,
            "sv-adb",
            "rv-adb",
            "ib-adb",
            "tr-adb",
        ],
    )


def _materialize_balance_analysis(
    db_path: Path,
    governance_dir: Path,
    monkeypatch,
    *,
    report_dates: list[str],
) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    settings_mod = load_module("backend.app.governance.settings", "backend/app/governance/settings.py")
    settings_mod.get_settings.cache_clear()
    task_mod = load_module(
        "backend.app.tasks.balance_analysis_materialize",
        "backend/app/tasks/balance_analysis_materialize.py",
    )
    _patch_skip_fx_refresh(task_mod, monkeypatch)
    for report_date in report_dates:
        task_mod.materialize_balance_analysis_facts.fn(
            report_date=report_date,
            duckdb_path=str(db_path),
            governance_dir=str(governance_dir),
        )


def test_adb_endpoints_return_structure(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "adb.duckdb"
    governance_dir = tmp_path / "governance"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2025-06-02",
            instrument_code="B1",
            bond_type=BOND_GOV,
            market_value=Decimal("100000000"),
            is_issuance_like=False,
        )
        _insert_zqtz(
            conn,
            report_date="2025-06-03",
            instrument_code="B1",
            bond_type=BOND_GOV,
            market_value=Decimal("200000000"),
            is_issuance_like=False,
        )
        _insert_tyw(
            conn,
            report_date="2025-06-03",
            position_id="T1",
            product_type="\u62c6\u653e\u540c\u4e1a",
            position_side=POSITION_ASSET,
            principal=Decimal("50000000"),
            rate=Decimal("2.5"),
        )
    finally:
        conn.close()

    _materialize_balance_analysis(
        db_path,
        governance_dir,
        monkeypatch,
        report_dates=["2025-06-02", "2025-06-03"],
    )
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)

    response = client.get(
        "/api/analysis/adb",
        params={"start_date": "2025-06-02", "end_date": "2025-06-03"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result_meta"]["basis"] == "analytical"
    body = body["result"]
    assert "summary" in body and "trend" in body and "breakdown" in body
    assert body["summary"]["total_avg_assets"] > 0

    comparison = client.get(
        "/api/analysis/adb-comparison",
        params={"start_date": "2025-06-02", "end_date": "2025-06-03", "top_n": 5},
    )
    assert comparison.status_code == 200, comparison.text
    payload = comparison.json()
    assert payload["result_meta"]["basis"] == "analytical"
    payload = payload["result"]
    assert payload["num_days"] == 2
    assert payload["report_date"] == "2025-06-03"
    assert "assets_breakdown" in payload and isinstance(payload["assets_breakdown"], list)
    assert "liabilities_breakdown" in payload and isinstance(payload["liabilities_breakdown"], list)
    assert "assets" not in payload
    assert "liabilities" not in payload
    assert "deviation" not in payload["assets_breakdown"][0]
    assert "total_spot_assets" in payload
    assert "total_avg_assets" in payload
    assert payload["total_avg_interbank_assets"] == pytest.approx(25_000_000.0)
    assert payload["total_avg_interbank_liabilities"] == pytest.approx(0.0)
    assert "asset_yield" in payload
    assert "liability_cost" in payload
    assert "net_interest_margin" in payload
    assert payload["adb_denominator_basis"] == "formal_calendar"
    assert payload["coverage_days"] == 2
    assert payload["sample_filled"] is False
    assert payload["calendar_days_inclusive"] == 2

    alias = client.get(
        "/api/analysis/adb/comparison",
        params={"start_date": "2025-06-02", "end_date": "2025-06-03", "top_n": 5},
    )
    assert alias.status_code == 200, alias.text
    alias_payload = alias.json()["result"]
    assert alias_payload["report_date"] == payload["report_date"]
    assert alias_payload["total_spot_assets"] == payload["total_spot_assets"]
    assert alias_payload["total_avg_assets"] == payload["total_avg_assets"]

    monthly = client.get("/api/analysis/adb/monthly", params={"year": 2025})
    assert monthly.status_code == 200, monthly.text
    monthly_json = monthly.json()
    assert monthly_json["result_meta"]["basis"] == "analytical"
    assert monthly_json["result_meta"]["result_kind"] == "adb.monthly"
    assert "filters_applied" in monthly_json["result_meta"]
    assert monthly_json["result_meta"]["filters_applied"].get("year") == 2025
    assert "tables_used" in monthly_json["result_meta"] and set(monthly_json["result_meta"]["tables_used"]) == {
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    }
    monthly_payload = monthly_json["result"]
    assert len(monthly_payload["months"]) == 1
    assert monthly_payload["year"] == 2025
    assert "months" in monthly_payload and "ytd_avg_assets" in monthly_payload
    assert "ytd_nim" in monthly_payload
    assert "ytd_net_interest_margin" not in monthly_payload
    assert "mom_change_assets" in monthly_payload["months"][0]
    assert "mom_change_pct_assets" in monthly_payload["months"][0]
    assert "mom_change_liabilities" in monthly_payload["months"][0]
    assert "mom_change_pct_liabilities" in monthly_payload["months"][0]
    assert "assets_mom_change" not in monthly_payload["months"][0]
    assert "liabilities_mom_change" not in monthly_payload["months"][0]
    assert "accounting_basis_daily_avg_trend" not in monthly_payload


def test_adb_comparison_returns_500_on_service_error(monkeypatch) -> None:
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    route_mod = load_module("backend.app.api.routes.adb_analysis", "backend/app/api/routes/adb_analysis.py")
    client = TestClient(main_mod.app)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("adb comparison exploded")

    monkeypatch.setattr(route_mod.adb_analysis_service, "adb_comparison_envelope", _boom)

    response = client.get(
        "/api/analysis/adb/comparison",
        params={"start_date": "2025-06-02", "end_date": "2025-06-03", "top_n": 5},
    )

    assert response.status_code == 500, response.text
    assert response.json()["detail"] == "Failed to get adb comparison: adb comparison exploded"


def test_adb_comparison_normalizes_bond_rates_from_percent_inputs(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "adb-rates.duckdb"
    governance_dir = tmp_path / "governance"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2025-05-16",
            instrument_code="B-RATE-1",
            bond_type=BOND_CORP,
            market_value=Decimal("100000000"),
            is_issuance_like=False,
            coupon_rate=Decimal("2.50"),
            ytm_value=Decimal("2.40"),
        )
    finally:
        conn.close()

    _materialize_balance_analysis(
        db_path,
        governance_dir,
        monkeypatch,
        report_dates=["2025-05-16"],
    )
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)

    response = client.get(
        "/api/analysis/adb/comparison",
        params={"start_date": "2025-05-16", "end_date": "2025-05-16", "top_n": 5},
    )

    assert response.status_code == 200, response.text
    payload = response.json()["result"]
    assert payload["simulated"] is True
    assert payload["assets_breakdown"][0]["category"] == BOND_CORP_ZQTZ_CATEGORY
    assert payload["assets_breakdown"][0]["weighted_rate"] == 2.4
    assert payload["asset_yield"] == 2.4


def test_adb_monthly_normalizes_rates_and_exposes_new_contract_fields(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "adb-monthly-rates.duckdb"
    governance_dir = tmp_path / "governance"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2025-01-15",
            instrument_code="B-MONTH-1",
            bond_type=BOND_CORP,
            market_value=Decimal("100000000"),
            is_issuance_like=False,
            coupon_rate=Decimal("2.50"),
            ytm_value=Decimal("2.40"),
        )
        _insert_zqtz(
            conn,
            report_date="2025-01-15",
            instrument_code="B-MONTH-NULL",
            bond_type=BOND_CERT,
            market_value=Decimal("0"),
            is_issuance_like=False,
            coupon_rate=Decimal("0"),
            ytm_value=Decimal("0"),
        )
        _insert_tyw(
            conn,
            report_date="2025-01-15",
            position_id="TYW-LIAB-1",
            product_type=INTERBANK_PLACE,
            position_side=POSITION_LIABILITY,
            principal=Decimal("50000000"),
            rate=Decimal("1.50"),
        )
        _insert_zqtz(
            conn,
            report_date="2025-02-15",
            instrument_code="B-MONTH-2",
            bond_type=BOND_CORP,
            market_value=Decimal("120000000"),
            is_issuance_like=False,
            coupon_rate=Decimal("2.50"),
            ytm_value=Decimal("2.40"),
        )
        _insert_tyw(
            conn,
            report_date="2025-02-15",
            position_id="TYW-LIAB-2",
            product_type=INTERBANK_PLACE,
            position_side=POSITION_LIABILITY,
            principal=Decimal("60000000"),
            rate=Decimal("1.50"),
        )
    finally:
        conn.close()

    _materialize_balance_analysis(
        db_path,
        governance_dir,
        monkeypatch,
        report_dates=["2025-01-15", "2025-02-15"],
    )
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)

    response = client.get("/api/analysis/adb/monthly", params={"year": 2025})

    assert response.status_code == 200, response.text
    payload = response.json()["result"]
    first_month = payload["months"][0]
    second_month = payload["months"][1]

    assert first_month["asset_yield"] == 2.4
    assert first_month["liability_cost"] == 1.5
    assert first_month["net_interest_margin"] == 0.9
    assert first_month["month_label"] == MONTH_LABEL_JAN
    assert first_month["mom_change_assets"] is None
    assert first_month["mom_change_pct_assets"] is None
    assert first_month["mom_change_liabilities"] is None
    assert first_month["mom_change_pct_liabilities"] is None

    assert second_month["month_label"] == MONTH_LABEL_FEB
    assert second_month["mom_change_assets"] == 20000000.0
    assert second_month["mom_change_pct_assets"] == 20.0
    assert second_month["mom_change_liabilities"] == 10000000.0
    assert second_month["mom_change_pct_liabilities"] == 20.0

    assert payload["ytd_nim"] == 0.9
    assert "ytd_net_interest_margin" not in payload

    null_rate_item = next(
        item
        for item in first_month["breakdown_assets"]
        if item["category"] == BOND_CERT_ZQTZ_CATEGORY
    )
    assert null_rate_item["weighted_rate"] is None


def test_adb_comparison_returns_analytical_envelope(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "adb-envelope.duckdb"
    governance_dir = tmp_path / "governance"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2025-06-03",
            instrument_code="B-ENV-1",
            bond_type=BOND_GOV,
            market_value=Decimal("100000000"),
            is_issuance_like=False,
        )
    finally:
        conn.close()

    _materialize_balance_analysis(
        db_path,
        governance_dir,
        monkeypatch,
        report_dates=["2025-06-03"],
    )
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)

    response = client.get(
        "/api/analysis/adb/comparison",
        params={"start_date": "2025-06-03", "end_date": "2025-06-03", "top_n": 5},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["scenario_flag"] is False
    assert payload["result_meta"]["result_kind"] == "adb.comparison"
    assert payload["result"]["report_date"] == "2025-06-03"


def test_adb_comparison_reads_formal_facts_without_snapshot_tables(tmp_path: Path, monkeypatch) -> None:
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("drop table zqtz_bond_daily_snapshot")
        conn.execute("drop table tyw_interbank_daily_snapshot")
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    settings_mod = load_module("backend.app.governance.settings", "backend/app/governance/settings.py")
    settings_mod.get_settings.cache_clear()
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)

    response = client.get(
        "/api/analysis/adb/comparison",
        params={"start_date": "2025-12-31", "end_date": "2025-12-31", "top_n": 5},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result"]["report_date"] == "2025-12-31"
    assert payload["result"]["total_avg_assets"] > 0


def test_adb_comparison_ignores_snapshot_when_formal_tables_missing(tmp_path: Path, monkeypatch) -> None:
    """ADB 不读 snapshot：无 formal 表时仅有快照行也不会出数（须物化 formal）。"""
    db_path = tmp_path / "adb_snapshot_fallback.duckdb"
    governance_dir = tmp_path / "governance_snap"
    governance_dir.mkdir()
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        conn.execute("drop table if exists fact_formal_zqtz_balance_daily")
        conn.execute("drop table if exists fact_formal_tyw_balance_daily")
        _insert_zqtz(
            conn,
            report_date="2025-06-02",
            instrument_code="SB1",
            bond_type=BOND_GOV,
            market_value=Decimal("100000000"),
            is_issuance_like=False,
        )
        _insert_tyw(
            conn,
            report_date="2025-06-02",
            position_id="ST1",
            product_type=INTERBANK_PLACE,
            position_side=POSITION_ASSET,
            principal=Decimal("50000000"),
            rate=Decimal("2.5"),
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    settings_mod = load_module("backend.app.governance.settings", "backend/app/governance/settings.py")
    settings_mod.get_settings.cache_clear()

    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)
    response = client.get(
        "/api/analysis/adb/comparison",
        params={"start_date": "2025-06-02", "end_date": "2025-06-02", "top_n": 10},
    )
    assert response.status_code == 200, response.text
    payload = response.json()["result"]
    assert payload["adb_denominator_basis"] == "snapshot_calendar"
    assert payload["total_avg_assets"] == 0.0
    assert payload["total_avg_interbank_assets"] == 0.0
    assert payload["coverage_days"] == 0


def test_adb_comparison_denominator_uses_calendar_span(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """宽日历区间、仅部分日期有 formal 余额：分母为日历区间天数，样本补齐后日均与 formal CNY 一致。"""
    db_path = tmp_path / "adb_distinct_days.duckdb"
    governance_dir = tmp_path / "governance_adb_dd"
    report_dates = ["2025-01-01", "2025-01-03", "2025-01-05", "2025-01-07", "2025-01-09"]
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        for i, rd in enumerate(report_dates):
            _insert_zqtz(
                conn,
                report_date=rd,
                instrument_code=f"B-SP-{i}",
                bond_type=BOND_GOV,
                market_value=Decimal("100000000"),
                is_issuance_like=False,
            )
    finally:
        conn.close()

    _materialize_balance_analysis(db_path, governance_dir, monkeypatch, report_dates=report_dates)
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)

    response = client.get(
        "/api/analysis/adb-comparison",
        params={"start_date": "2025-01-01", "end_date": "2025-01-10", "top_n": 20},
    )
    assert response.status_code == 200, response.text
    payload = response.json()["result"]
    assert payload["calendar_days_inclusive"] == 10
    assert payload["num_days"] == 10
    assert payload["coverage_days"] == 5
    assert payload["adb_denominator_basis"] == "formal_calendar"
    assert payload["sample_filled"] is True
    assert payload["sample_fill_method"] == "observed_days_scaled_to_calendar"
    # 样本补齐：5 个观测日各 1 亿，扩展到 10 天窗口后日均仍保持 1 亿
    assert payload["total_avg_assets"] == pytest.approx(100_000_000.0)


def test_adb_comparison_liab_spot_locf_when_end_date_has_no_row(tmp_path: Path, monkeypatch) -> None:
    """区间末日无快照时，负债分类期末时点用最近观测日结转（LOCF），避免 spot=0 而日均>0 的伪偏离。"""
    db_path = tmp_path / "adb_locf_liab.duckdb"
    governance_dir = tmp_path / "gov_locf_liab"
    repo_product = "\u5356\u51fa\u56de\u8d2d\u8bc1\u5238"
    principal = Decimal("16866000000")
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_tyw(
            conn,
            report_date="2025-06-02",
            position_id="R-LOCF",
            product_type=repo_product,
            position_side=POSITION_LIABILITY,
            principal=principal,
            rate=Decimal("2.5"),
        )
    finally:
        conn.close()

    _materialize_balance_analysis(db_path, governance_dir, monkeypatch, report_dates=["2025-06-02"])
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    settings_mod = load_module("backend.app.governance.settings", "backend/app/governance/settings.py")
    settings_mod.get_settings.cache_clear()
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)

    response = client.get(
        "/api/analysis/adb/comparison",
        params={"start_date": "2025-06-02", "end_date": "2025-06-03", "top_n": 20},
    )
    assert response.status_code == 200, response.text
    rows = response.json()["result"]["liabilities_breakdown"]
    repo_row = next(r for r in rows if r["category"] == repo_product)
    assert repo_row["spot_balance"] == pytest.approx(float(principal))
    assert repo_row["avg_balance"] > 0


def test_adb_comparison_liability_falls_back_past_blank_sub_type(tmp_path: Path, monkeypatch) -> None:
    """发行类负债 sub_type 为空时，分类回退 bond_type，不整包挤进「其它」。"""
    db_path = tmp_path / "adb_liab_fallback.duckdb"
    governance_dir = tmp_path / "gov_liab_fb"
    conn = duckdb.connect(str(db_path))
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2025-07-15",
            instrument_code="ISS-FB-1",
            bond_type=BOND_GOV,
            market_value=Decimal("300000000"),
            is_issuance_like=True,
        )
    finally:
        conn.close()

    _materialize_balance_analysis(db_path, governance_dir, monkeypatch, report_dates=["2025-07-15"])
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    settings_mod = load_module("backend.app.governance.settings", "backend/app/governance/settings.py")
    settings_mod.get_settings.cache_clear()
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_mod.app)

    response = client.get(
        "/api/analysis/adb/comparison",
        params={"start_date": "2025-07-15", "end_date": "2025-07-15", "top_n": 20},
    )
    assert response.status_code == 200, response.text
    rows = response.json()["result"]["liabilities_breakdown"]
    assert any(r["category"] == BOND_GOV and r["avg_balance"] > 0 for r in rows)
