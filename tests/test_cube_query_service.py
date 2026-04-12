from __future__ import annotations

import duckdb
import pytest

from tests.helpers import load_module


def _seed_cube_tables(duckdb_path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date varchar,
              asset_class_std varchar,
              accounting_class varchar,
              tenor_bucket varchar,
              rating varchar,
              bond_type varchar,
              issuer_name varchar,
              industry_name varchar,
              portfolio_name varchar,
              cost_center varchar,
              market_value decimal(24, 8),
              modified_duration decimal(18, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_bond_analytics_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-03-31", "rate", "AC", "0-1Y", "AAA", "gov", "Issuer A", "Sovereign", "Portfolio A", "CC100", "100.00000000", "1.10000000", "sv_bond_1", "rv_bond_1"),
                ("2026-03-31", "credit", "FVOCI", "1-3Y", "AA", "corp", "Issuer B", "Banking", "Portfolio B", "CC200", "150.00000000", "2.30000000", "sv_bond_1", "rv_bond_1"),
                ("2026-03-31", "credit", "FVOCI", "3-5Y", "AAA", "corp", "Issuer C", "Utilities", "Portfolio B", "CC200", "200.00000000", "3.40000000", "sv_bond_2", "rv_bond_1"),
            ],
        )
        conn.execute(
            """
            create table fact_formal_pnl_fi (
              report_date varchar,
              portfolio_name varchar,
              cost_center varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              total_pnl decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_pnl_fi values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-03-31", "Portfolio A", "CC100", "T", "FVTPL", "10.00000000", "sv_pnl_1", "rv_pnl_1"),
                ("2026-03-31", "Portfolio B", "CC200", "A", "FVOCI", "20.00000000", "sv_pnl_1", "rv_pnl_1"),
            ],
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date varchar,
              asset_class varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              bond_type varchar,
              rating varchar,
              market_value_amount decimal(24, 8),
              amortized_cost_amount decimal(24, 8),
              accrued_interest_amount decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_formal_zqtz_balance_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-03-31", "bond", "H", "AC", "asset", "gov", "AAA", "300.00000000", "290.00000000", "5.00000000", "sv_bal_1", "rv_bal_1"),
                ("2026-03-31", "bond", "A", "FVOCI", "asset", "corp", "AA", "120.00000000", "110.00000000", "3.00000000", "sv_bal_1", "rv_bal_1"),
            ],
        )
        conn.execute(
            """
            create table product_category_pnl_formal_read_model (
              report_date varchar,
              category_id varchar,
              category_name varchar,
              side varchar,
              view varchar,
              business_net_income decimal(24, 8),
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into product_category_pnl_formal_read_model values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-03-31", "asset_total", "Asset Total", "asset", "monthly", "60.00000000", "sv_cat_1", "rv_cat_1"),
                ("2026-03-31", "liability_total", "Liability Total", "liability", "monthly", "-15.00000000", "sv_cat_1", "rv_cat_1"),
            ],
        )
    finally:
        conn.close()


def _build_service():
    module = load_module("backend.app.services.cube_query_service", "backend/app/services/cube_query_service.py")
    return module.CubeQueryService()


def _build_request(**overrides):
    schema_module = load_module("backend.app.schemas.cube_query", "backend/app/schemas/cube_query.py")
    payload = {
        "report_date": "2026-03-31",
        "fact_table": "bond_analytics",
        "measures": ["sum(market_value)"],
    }
    payload.update(overrides)
    return schema_module.CubeQueryRequest(**payload)


def test_simple_sum_query(tmp_path):
    duckdb_path = tmp_path / "cube.duckdb"
    _seed_cube_tables(duckdb_path)
    response = _build_service().execute(_build_request(), str(duckdb_path))
    assert response.fact_table == "bond_analytics"
    assert response.total_rows == 1
    assert float(response.rows[0]["market_value"]) == 450.0
    assert response.result_meta.basis == "formal"


def test_group_by_dimension(tmp_path):
    duckdb_path = tmp_path / "cube.duckdb"
    _seed_cube_tables(duckdb_path)
    response = _build_service().execute(
        _build_request(dimensions=["asset_class_std"], order_by=["-market_value"]),
        str(duckdb_path),
    )
    assert response.total_rows == 2
    assert response.rows[0]["asset_class_std"] == "credit"
    assert float(response.rows[0]["market_value"]) == 350.0
    assert response.rows[1]["asset_class_std"] == "rate"


def test_filter_narrows_results(tmp_path):
    duckdb_path = tmp_path / "cube.duckdb"
    _seed_cube_tables(duckdb_path)
    response = _build_service().execute(
        _build_request(filters={"asset_class_std": ["rate"]}),
        str(duckdb_path),
    )
    assert response.total_rows == 1
    assert float(response.rows[0]["market_value"]) == 100.0


def test_invalid_fact_table_rejected():
    with pytest.raises(ValueError, match="Unsupported fact_table"):
        _build_request(fact_table="drop_table")


def test_sql_injection_prevented(tmp_path):
    duckdb_path = tmp_path / "cube.duckdb"
    _seed_cube_tables(duckdb_path)
    response = _build_service().execute(
        _build_request(filters={"asset_class_std": ["credit' OR 1=1 --"]}),
        str(duckdb_path),
    )
    assert response.rows == []
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute("select count(*) from fact_formal_bond_analytics_daily").fetchone()
    finally:
        conn.close()
    assert row == (3,)


def test_drill_paths_populated(tmp_path):
    duckdb_path = tmp_path / "cube.duckdb"
    _seed_cube_tables(duckdb_path)
    response = _build_service().execute(
        _build_request(dimensions=["asset_class_std", "rating"], filters={"asset_class_std": ["credit"]}),
        str(duckdb_path),
    )
    paths = {path.dimension: path for path in response.drill_paths}
    assert set(paths) == {"asset_class_std", "rating"}
    assert paths["asset_class_std"].current_filter == ["credit"]
    assert set(paths["asset_class_std"].available_values) == {"credit", "rate"}
    assert set(paths["rating"].available_values) == {"AA", "AAA"}
