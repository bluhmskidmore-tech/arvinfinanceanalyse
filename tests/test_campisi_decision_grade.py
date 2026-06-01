from __future__ import annotations

from types import SimpleNamespace

import duckdb
import pytest

from backend.app.services import campisi_attribution_service as campisi_svc


def _create_decision_grade_tables(db_path) -> None:
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
                report_date date,
                instrument_code varchar,
                portfolio_name varchar,
                cost_center varchar,
                invest_type_std varchar,
                accounting_basis varchar,
                currency_basis varchar,
                interest_income_514 double,
                fair_value_change_516 double,
                capital_gain_517 double,
                manual_adjustment double,
                total_pnl double,
                source_version varchar,
                rule_version varchar,
                ingest_batch_id varchar,
                trace_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
                report_date date,
                instrument_code varchar,
                instrument_name varchar,
                portfolio_name varchar,
                cost_center varchar,
                account_category varchar,
                asset_class varchar,
                bond_type varchar,
                issuer_name varchar,
                industry_name varchar,
                rating varchar,
                invest_type_std varchar,
                accounting_basis varchar,
                position_scope varchar,
                currency_basis varchar,
                currency_code varchar,
                face_value_amount double,
                market_value_amount double,
                amortized_cost_amount double,
                accrued_interest_amount double,
                coupon_rate double,
                ytm_value double,
                maturity_date date,
                interest_mode varchar,
                is_issuance_like boolean,
                source_version varchar,
                rule_version varchar,
                ingest_batch_id varchar,
                trace_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
                report_date date,
                instrument_code varchar,
                instrument_name varchar,
                portfolio_name varchar,
                cost_center varchar,
                asset_class_raw varchar,
                asset_class_std varchar,
                bond_type varchar,
                issuer_name varchar,
                industry_name varchar,
                rating varchar,
                accounting_class varchar,
                currency_code varchar,
                face_value double,
                market_value double,
                amortized_cost double,
                accrued_interest double,
                coupon_rate double,
                ytm double,
                maturity_date date,
                years_to_maturity double,
                tenor_bucket varchar,
                macaulay_duration double,
                modified_duration double,
                convexity double,
                dv01 double,
                is_credit boolean,
                spread_dv01 double,
                source_version varchar,
                rule_version varchar,
                ingest_batch_id varchar,
                trace_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_yield_curve_daily (
                trade_date date,
                curve_type varchar,
                tenor varchar,
                rate_pct double,
                vendor_name varchar,
                vendor_version varchar,
                source_version varchar,
                rule_version varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_formal_risk_tensor_daily (
                report_date date,
                portfolio_name varchar,
                cost_center varchar,
                portfolio_dv01 double,
                krd_1y double,
                krd_3y double,
                krd_5y double,
                krd_7y double,
                krd_10y double,
                krd_30y double,
                cs01 double,
                portfolio_convexity double,
                portfolio_modified_duration double,
                total_market_value double,
                bond_count integer,
                quality_flag varchar,
                warnings_json varchar,
                source_version varchar,
                rule_version varchar
            )
            """
        )
    finally:
        conn.close()


def _seed_decision_grade_sample(db_path, *, with_curves: bool = True) -> None:
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.executemany(
            """
            insert into fact_formal_pnl_fi values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "2026-01-31",
                    "BOND_FVTPL",
                    "FIOA",
                    "5010",
                    "bond_investment",
                    "FVTPL",
                    "CNY",
                    10.0,
                    20.0,
                    5.0,
                    2.0,
                    100.0,
                    "sv_formal",
                    "rv_formal",
                    "batch1",
                    "trace1",
                ),
                (
                    "2026-01-31",
                    "BOND_FVOCI",
                    "FIOA",
                    "5010",
                    "bond_investment",
                    "FVOCI",
                    "CNY",
                    7.0,
                    50.0,
                    0.0,
                    0.0,
                    7.0,
                    "sv_formal",
                    "rv_formal",
                    "batch1",
                    "trace2",
                ),
            ],
        )
        analytics_rows = [
            (
                "2026-01-01",
                "BOND_FVTPL",
                "Bond FVTPL",
                "FIOA",
                "5010",
                "bond",
                "credit",
                "credit",
                "Issuer A",
                "FI",
                "AAA",
                "FVTPL",
                "CNY",
                1000.0,
                1000.0,
                1000.0,
                0.0,
                0.03,
                0.02,
                "2031-01-01",
                5.0,
                "5Y",
                2.0,
                2.0,
                100.0,
                2.0,
                True,
                0.0,
                "sv_bond",
                "rv_bond",
                "batch1",
                "tracea",
            ),
            (
                "2026-01-01",
                "BOND_FVOCI",
                "Bond FVOCI",
                "FIOA",
                "5010",
                "bond",
                "treasury",
                "treasury",
                "Issuer B",
                "Gov",
                "AAA",
                "FVOCI",
                "CNY",
                700.0,
                700.0,
                700.0,
                0.0,
                0.03,
                0.02,
                "2031-01-01",
                5.0,
                "5Y",
                3.0,
                3.0,
                80.0,
                0.0,
                False,
                0.0,
                "sv_bond",
                "rv_bond",
                "batch1",
                "traceb",
            ),
        ]
        conn.executemany(
            """
            insert into fact_formal_bond_analytics_daily values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            analytics_rows,
        )
        balance_rows = [
            (
                "2026-01-01",
                "BOND_FVTPL",
                "Bond FVTPL",
                "FIOA",
                "5010",
                "bond",
                "credit",
                "credit",
                "Issuer A",
                "FI",
                "AAA",
                "bond_investment",
                "FVTPL",
                "asset",
                "CNY",
                "CNY",
                1000.0,
                1000.0,
                1000.0,
                0.0,
                0.03,
                0.02,
                "2031-01-01",
                "fixed",
                False,
                "sv_bal",
                "rv_bal",
                "batch1",
                "tracebal1",
            ),
            (
                "2026-01-01",
                "BOND_FVOCI",
                "Bond FVOCI",
                "FIOA",
                "5010",
                "bond",
                "treasury",
                "treasury",
                "Issuer B",
                "Gov",
                "AAA",
                "bond_investment",
                "FVOCI",
                "asset",
                "CNY",
                "CNY",
                700.0,
                700.0,
                700.0,
                0.0,
                0.03,
                0.02,
                "2031-01-01",
                "fixed",
                False,
                "sv_bal",
                "rv_bal",
                "batch1",
                "tracebal2",
            ),
        ]
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily values
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            balance_rows,
        )
        conn.execute(
            """
            insert into fact_formal_risk_tensor_daily values
            ('2026-01-31', 'FIOA', '5010', 2.0, 0, 0, 2, 0, 0, 0, 0, 100, 2, 1700, 2, 'ok', '[]', 'sv_risk', 'rv_risk')
            """
        )
        if with_curves:
            curve_rows = []
            for trade_date, treasury_rate in (("2026-01-01", 2.0), ("2026-01-31", 3.0)):
                for tenor in ("1Y", "3Y", "5Y", "7Y", "10Y", "30Y"):
                    curve_rows.append((trade_date, "treasury", tenor, treasury_rate, "formal", "vv", "sv_curve", "rv_curve"))
                    curve_rows.append((trade_date, "aaa_credit", tenor, treasury_rate, "formal", "vv", "sv_curve", "rv_curve"))
            conn.executemany(
                """
                insert into fact_formal_yield_curve_daily values
                (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                curve_rows,
            )
    finally:
        conn.close()


def test_decision_grade_campisi_closes_formal_pnl_and_separates_valuation_view(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "decision_grade.duckdb"
    _create_decision_grade_tables(db_path)
    _seed_decision_grade_sample(db_path)
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    envelope = campisi_svc.campisi_decision_grade_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    result = envelope["result"]
    assert envelope["result_meta"]["result_kind"] == "campisi.decision_grade"
    assert result["summary"]["formal_actual_pnl"] == pytest.approx(107.0)
    assert result["summary"]["explained_pnl"] == pytest.approx(107.0)
    assert result["summary"]["residual_noise"] == pytest.approx(0.0)
    assert result["formal_pnl_view"]["components"]["carry"] == pytest.approx(17.0)
    assert result["formal_pnl_view"]["components"]["rate_level_effect"] == pytest.approx(-20.0)
    assert result["formal_pnl_view"]["components"]["curve_shape_effect"] == pytest.approx(0.0)
    assert result["formal_pnl_view"]["components"]["convexity_effect"] == pytest.approx(5.0)
    assert result["formal_pnl_view"]["components"]["realized_trading"] == pytest.approx(5.0)
    assert result["formal_pnl_view"]["components"]["manual_adjustment"] == pytest.approx(2.0)
    assert result["formal_pnl_view"]["components"]["selection_proxy"] == pytest.approx(98.0)
    assert result["valuation_oci_view"]["total_valuation_change_516"] == pytest.approx(70.0)
    assert result["valuation_oci_view"]["fvoci_valuation_change_516"] == pytest.approx(50.0)
    assert result["valuation_oci_view"]["fvtpl_valuation_change_516"] == pytest.approx(20.0)
    assert result["accounting_matrix"]["FVOCI"]["formal_pnl"] == pytest.approx(7.0)
    assert result["accounting_matrix"]["FVOCI"]["valuation_or_oci_516"] == pytest.approx(50.0)
    assert result["accounting_matrix"]["FVTPL"]["formal_pnl"] == pytest.approx(100.0)
    assert result["accounting_matrix"]["FVTPL"]["valuation_or_oci_516"] == pytest.approx(20.0)
    assert "fact_formal_pnl_fi" in envelope["result_meta"]["tables_used"]
    assert "fact_formal_yield_curve_daily" in envelope["result_meta"]["tables_used"]
    assert "fact_formal_risk_tensor_daily" in envelope["result_meta"]["tables_used"]


def test_decision_grade_missing_curve_goes_to_residual_noise_not_selection_proxy(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "decision_grade_missing_curve.duckdb"
    _create_decision_grade_tables(db_path)
    _seed_decision_grade_sample(db_path, with_curves=False)
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    result = campisi_svc.campisi_decision_grade_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]

    assert result["formal_pnl_view"]["components"]["selection_proxy"] == pytest.approx(0.0)
    assert result["formal_pnl_view"]["components"]["residual_noise"] == pytest.approx(83.0)
    assert result["summary"]["quality_flag"] == "warning"
    assert result["residual_diagnostics"]["missing_curve_count"] > 0
    assert any("曲线" in warning for warning in result["warnings"])
