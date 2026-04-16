from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_bond_analytics_curve_effects import _seed_curve_rows
from tests.test_bond_analytics_materialize_flow import REPORT_DATE
from tests.test_bond_analytics_service import _configure_and_materialize


@pytest.fixture
def service_mod(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    module = load_module(
        f"tests._bond_contract.bond_analytics_service_{uuid.uuid4().hex}",
        "backend/app/services/bond_analytics_service.py",
    )
    try:
        yield module
    finally:
        get_settings.cache_clear()


def _seed_fx_rows(duckdb_path: str) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(18, 8),
              source_version varchar,
              vendor_name varchar,
              vendor_version varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fx_daily_mid (trade_date, base_currency, quote_currency, mid_rate, source_version, vendor_name, vendor_version)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2026-03-31", "USD", "CNY", Decimal("7.08270000"), "sv_fx_current", "cfets", "vv_fx_current"),
                ("2026-03-01", "USD", "CNY", Decimal("7.04135000"), "sv_fx_prior", "cfets", "vv_fx_prior"),
            ],
        )
    finally:
        conn.close()


def test_bond_analytics_return_decomposition_with_real_facts_uses_filtered_fact_rows(service_mod):
    payload = service_mod.get_return_decomposition(
        date.fromisoformat(REPORT_DATE),
        "MoM",
        "credit",
        "all",
    )
    result = payload["result"]

    assert payload["result_meta"]["source_version"] == "sv_bond_snap_1"
    assert result["bond_count"] == 2
    assert result["total_market_value"] == "330.00000000"
    assert result["carry"] == "1.01917808"
    assert result["actual_pnl"] == "1.01917808"
    assert service_mod.RETURN_TRADING_GAP_WARNING in result["warnings"]
    assert result["by_asset_class"] == [
        {
            "asset_class": "credit",
            "carry": "1.01917808",
            "roll_down": "0.00000000",
            "rate_effect": "0.00000000",
            "spread_effect": "0.00000000",
            "convexity_effect": "0.00000000",
            "trading": "0.00000000",
            "total": "1.01917808",
            "bond_count": 2,
            "market_value": "330.00000000",
        }
    ]
    assert result["by_accounting_class"] == [
        {
            "asset_class": "OCI",
            "carry": "0.50958904",
            "roll_down": "0.00000000",
            "rate_effect": "0.00000000",
            "spread_effect": "0.00000000",
            "convexity_effect": "0.00000000",
            "trading": "0.00000000",
            "total": "0.50958904",
            "bond_count": 1,
            "market_value": "190.00000000",
        },
        {
            "asset_class": "TPL",
            "carry": "0.50958904",
            "roll_down": "0.00000000",
            "rate_effect": "0.00000000",
            "spread_effect": "0.00000000",
            "convexity_effect": "0.00000000",
            "trading": "0.00000000",
            "total": "0.50958904",
            "bond_count": 1,
            "market_value": "140.00000000",
        },
    ]
    assert [row["bond_code"] for row in result["bond_details"]] == ["CB-001", "CB-002"]


def test_return_decomposition_fx_effect_nonzero_for_usd_bonds(tmp_path, monkeypatch):
    duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    _seed_fx_rows(str(duckdb_path))
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set currency_code = 'USD',
                face_value_native = ?,
                market_value_native = ?
            where report_date = ? and instrument_code = ?
            """,
            [Decimal("1000.00000000"), Decimal("1000.00000000"), REPORT_DATE, "CB-001"],
        )
    finally:
        conn.close()
    _task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(_governance_dir),
    )
    service_mod = load_module(
        f"tests._bond_contract.bond_analytics_service_{uuid.uuid4().hex}",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date.fromisoformat(REPORT_DATE), "MoM", "credit", "all")
    result = payload["result"]

    assert result["fx_effect"] == "41.35000000"
    assert Decimal(result["explained_pnl"]) == Decimal(result["carry"]) + Decimal(result["fx_effect"])
    get_settings.cache_clear()


def test_benchmark_excess_spread_effect_nonzero_with_curves(tmp_path, monkeypatch):
    duckdb_path, _governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    _seed_curve_rows(str(duckdb_path))
    service_mod = load_module(
        f"tests._bond_contract.bond_analytics_service_{uuid.uuid4().hex}",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_benchmark_excess(date.fromisoformat(REPORT_DATE), "MoM", "TREASURY_INDEX")

    assert Decimal(payload["result"]["spread_effect"]) != Decimal("0")
    get_settings.cache_clear()


def test_return_decomposition_warns_when_fx_uses_latest_available_snapshot(tmp_path, monkeypatch):
    duckdb_path, governance_dir, task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(18, 8),
              source_version varchar,
              vendor_name varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid (trade_date, base_currency, quote_currency, mid_rate, source_version, vendor_name, vendor_version)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            ["2026-02-28", "USD", "CNY", Decimal("7.08270000"), "sv_fx_latest", "cfets", "vv_fx_latest"],
        )
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set currency_code = 'USD',
                face_value_native = ?,
                market_value_native = ?
            where report_date = ? and instrument_code = ?
            """,
            [Decimal("1000.00000000"), Decimal("1000.00000000"), REPORT_DATE, "CB-001"],
        )
    finally:
        conn.close()
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        f"tests._bond_contract.bond_analytics_service_{uuid.uuid4().hex}",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date.fromisoformat(REPORT_DATE), "MoM", "credit", "all")

    assert any("latest available FX rates" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


def test_return_decomposition_marks_result_meta_stale_when_fx_uses_latest_available_snapshot(tmp_path, monkeypatch):
    duckdb_path, governance_dir, task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    _seed_curve_rows(str(duckdb_path))
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate decimal(18, 8),
              source_version varchar,
              vendor_name varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid (trade_date, base_currency, quote_currency, mid_rate, source_version, vendor_name, vendor_version)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            ["2026-02-28", "USD", "CNY", Decimal("7.08270000"), "sv_fx_latest", "cfets", "vv_fx_latest"],
        )
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set currency_code = 'USD',
                face_value_native = ?,
                market_value_native = ?,
                maturity_date = ?,
                ytm_value = ?
            where report_date = ? and instrument_code = ?
            """,
            [Decimal("1000.00000000"), Decimal("1000.00000000"), "2028-03-30", Decimal("0"), REPORT_DATE, "TB-001"],
        )
    finally:
        conn.close()
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        f"tests._bond_contract.bond_analytics_service_{uuid.uuid4().hex}",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date.fromisoformat(REPORT_DATE), "MoM", "rate", "all")

    assert payload["result_meta"]["fallback_mode"] == "latest_snapshot"
    assert payload["result_meta"]["vendor_status"] == "vendor_stale"
    get_settings.cache_clear()


def test_return_decomposition_marks_result_meta_unavailable_when_required_fx_missing(tmp_path, monkeypatch):
    duckdb_path, governance_dir, task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    _seed_curve_rows(str(duckdb_path))
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set currency_code = 'USD',
                face_value_native = ?,
                market_value_native = ?,
                maturity_date = ?,
                ytm_value = ?
            where report_date = ? and instrument_code = ?
            """,
            [Decimal("1000.00000000"), Decimal("1000.00000000"), "2028-03-30", Decimal("0"), REPORT_DATE, "TB-001"],
        )
    finally:
        conn.close()
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    service_mod = load_module(
        f"tests._bond_contract.bond_analytics_service_{uuid.uuid4().hex}",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date.fromisoformat(REPORT_DATE), "MoM", "rate", "all")

    assert payload["result_meta"]["fallback_mode"] == "none"
    assert payload["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert any("No FX rates available" in warning or "Missing FX rates" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


def test_bond_analytics_krd_curve_risk_with_real_facts_formats_exact_risk_outputs(service_mod):
    payload = service_mod.get_krd_curve_risk(date.fromisoformat(REPORT_DATE), "standard")
    result = payload["result"]

    assert payload["result_meta"]["rule_version"] == "rv_bond_analytics_formal_materialize_v1"
    assert result["portfolio_duration"] == "5.05978431"
    assert result["portfolio_modified_duration"] == "4.87293147"
    assert result["portfolio_dv01"] == "0.20904876"
    assert result["portfolio_convexity"] == "36.65108294"
    assert result["krd_buckets"] == [
        {
            "tenor": "10Y",
            "krd": "8.03613072",
            "dv01": "0.11250583",
            "market_value_weight": "0.32634033",
        },
        {
            "tenor": "1Y",
            "krd": "0.98231827",
            "dv01": "0.00972495",
            "market_value_weight": "0.23076923",
        },
        {
            "tenor": "5Y",
            "krd": "4.56936732",
            "dv01": "0.08681798",
            "market_value_weight": "0.44289044",
        },
    ]
    assert result["scenarios"][0]["scenario_name"] == "parallel_up_25bp"
    assert result["scenarios"][0]["pnl_economic"] == "-5.17708364"
    assert result["by_asset_class"] == [
        {
            "asset_class": "credit",
            "market_value": "330.00000000",
            "duration": "6.27771960",
            "dv01": "0.19932381",
            "weight": "0.76923077",
        },
        {
            "asset_class": "rate",
            "market_value": "99.00000000",
            "duration": "1.00000000",
            "dv01": "0.00972495",
            "weight": "0.23076923",
        },
    ]


def test_bond_analytics_credit_spread_with_real_facts_returns_expected_scenario_and_concentration(service_mod):
    payload = service_mod.get_credit_spread_migration(date.fromisoformat(REPORT_DATE), "10,25")
    result = payload["result"]

    assert result["credit_bond_count"] == 2
    assert result["credit_market_value"] == "330.00000000"
    assert result["credit_weight"] == "0.76923077"
    assert result["rating_aa_and_below_weight"] == "0.00000000"
    assert result["spread_dv01"] == "0.19932381"
    assert result["weighted_avg_spread_duration"] == "6.04011543"
    assert result["spread_scenarios"] == [
        {
            "scenario_name": "利差走阔 10bp",
            "spread_change_bp": 10.0,
            "pnl_impact": "-1.99323810",
            "oci_impact": "-0.86817980",
            "tpl_impact": "-1.12505830",
        },
        {
            "scenario_name": "利差收窄 10bp",
            "spread_change_bp": -10.0,
            "pnl_impact": "1.99323810",
            "oci_impact": "0.86817980",
            "tpl_impact": "1.12505830",
        },
        {
            "scenario_name": "利差走阔 25bp",
            "spread_change_bp": 25.0,
            "pnl_impact": "-4.98309525",
            "oci_impact": "-2.17044950",
            "tpl_impact": "-2.81264575",
        },
        {
            "scenario_name": "利差收窄 25bp",
            "spread_change_bp": -25.0,
            "pnl_impact": "4.98309525",
            "oci_impact": "2.17044950",
            "tpl_impact": "2.81264575",
        },
    ]
    assert result["concentration_by_issuer"] == {
        "dimension": "issuer",
        "hhi": "0.51147842",
        "top5_concentration": "1.00000000",
        "top_items": [
            {
                "name": "发行人甲",
                "weight": "0.57575758",
                "market_value": "190.00000000",
            },
            {
                "name": "发行人乙",
                "weight": "0.42424242",
                "market_value": "140.00000000",
            },
        ],
    }
    assert any(
        "No aaa_credit curve available" in warning or "No treasury curve available" in warning
        for warning in result["warnings"]
    )


def test_bond_analytics_accounting_audit_with_real_facts_returns_rule_trace_rows(service_mod):
    payload = service_mod.get_accounting_class_audit(date.fromisoformat(REPORT_DATE))
    result = payload["result"]

    assert result["total_positions"] == 3
    assert result["total_market_value"] == "429.00000000"
    assert result["distinct_asset_classes"] == 2
    assert result["divergent_asset_classes"] == 0
    assert result["rows"] == [
        {
            "asset_class": "信用债",
            "position_count": 2,
            "market_value": "330.00000000",
            "market_value_weight": "0.76923077",
            "infer_accounting_class": "OCI",
            "map_accounting_class": "OCI",
            "infer_rule_id": "R010",
            "infer_match": "accounting_rule_id:R01*",
            "map_rule_id": "R010",
            "map_match": None,
            "is_divergent": False,
            "is_map_unclassified": False,
        },
        {
            "asset_class": "利率债",
            "position_count": 1,
            "market_value": "99.00000000",
            "market_value_weight": "0.23076923",
            "infer_accounting_class": "AC",
            "map_accounting_class": "AC",
            "infer_rule_id": "R001",
            "infer_match": "accounting_rule_id:R00*",
            "map_rule_id": "R001",
            "map_match": None,
            "is_divergent": False,
            "is_map_unclassified": False,
        },
    ]
    assert result["warnings"] == []
