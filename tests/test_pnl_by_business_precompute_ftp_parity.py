from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.config.product_category_mapping import (
    resolve_product_category_ftp_rate_pct,
)
from backend.app.core_finance.pnl import compute_pnl_by_business_yield_and_ftp
from tests.helpers import load_module

precompute_module = load_module(
    "backend.app.tasks.pnl_by_business_precompute",
    "backend/app/tasks/pnl_by_business_precompute.py",
)
pnl_repo_module = load_module(
    "backend.app.repositories.pnl_repo",
    "backend/app/repositories/pnl_repo.py",
)
pnl_service_module = load_module(
    "backend.app.services.pnl_service",
    "backend/app/services/pnl_service.py",
)


def test_precompute_rule_version_tracks_current_analysis_contract() -> None:
    assert pnl_repo_module.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION == (
        "rv_pnl_by_business_precompute_v4"
    )


def test_precompute_classification_matches_live_when_only_formal_metadata_is_available() -> None:
    pnl_row = {
        "source_kind": "formal_fi",
        "report_date": "2026-06-30",
        "instrument_code": "P001",
        "instrument_name": "政策性金融债测试券",
        "portfolio_name": "FI Desk",
        "cost_center": "CC-POLICY",
        "currency_basis": "CNY",
        "invest_type_std": "T",
        "accounting_basis": "FVTPL",
        "asset_class": "政策性金融债",
    }
    kwargs = {
        "pnl_row": pnl_row,
        "balance_lookup": {},
        "historical_balance_lookup": {},
        "sub_type_by_date_code": {},
        "fallback_date": "2026-06-30",
    }

    live = pnl_service_module._analysis_classification_for_pnl_row(**kwargs)
    precomputed = precompute_module._analysis_classification_for_pnl_row(**kwargs)

    assert precomputed == live
    assert precomputed["asset_class"] == "政策性金融债"
    assert precomputed["instrument_name"] == "政策性金融债测试券"


@pytest.mark.parametrize(
    ("report_year", "expected_rate_pct"),
    [
        (2025, Decimal("1.75")),
        (2026, Decimal("1.60")),
    ],
)
def test_precompute_ftp_values_match_core_finance_function(report_year, expected_rate_pct):
    total_pnl = Decimal("130000")
    avg_balance = Decimal("100000000")
    calendar_days = 31

    ftp_rate_pct = resolve_product_category_ftp_rate_pct(
        date(report_year, 12, 31), Decimal("9.99")
    )
    assert ftp_rate_pct == expected_rate_pct

    annualized_yield_pct = precompute_module._analysis_annualized_yield_pct(
        total_pnl,
        avg_balance,
        calendar_days,
        ftp_rate_pct,
    )
    ftp_values = precompute_module._analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )

    expected = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )

    assert annualized_yield_pct == expected.annualized_yield_pct
    assert ftp_values["ftp_rate_pct"] == expected.ftp_rate_pct
    assert ftp_values["ftp_cost"] == expected.ftp_cost
    assert ftp_values["ftp_net_pnl"] == expected.ftp_net_pnl
    assert ftp_values["ftp_net_annualized_yield_pct"] == expected.ftp_net_annualized_yield_pct


def test_precompute_ftp_values_match_core_finance_function_without_denominator():
    total_pnl = Decimal("130000")
    avg_balance = Decimal("0")
    calendar_days = 31
    ftp_rate_pct = Decimal("1.75")

    annualized_yield_pct = precompute_module._analysis_annualized_yield_pct(
        total_pnl,
        avg_balance,
        calendar_days,
        ftp_rate_pct,
    )
    ftp_values = precompute_module._analysis_ftp_values(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        annualized_yield_pct=annualized_yield_pct,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )

    expected = compute_pnl_by_business_yield_and_ftp(
        total_pnl=total_pnl,
        avg_balance=avg_balance,
        calendar_days=calendar_days,
        ftp_rate_pct=ftp_rate_pct,
    )

    assert annualized_yield_pct is None
    assert ftp_values["ftp_cost"] is None
    assert ftp_values["ftp_net_pnl"] is None
    assert ftp_values["ftp_net_annualized_yield_pct"] is None
    assert expected.annualized_yield_pct is None


def test_fetch_precompute_returns_none_when_rule_version_mismatches(tmp_path):
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_pnl_by_business_precompute (
                year integer, as_of_date varchar, result_kind varchar,
                dimension varchar, business_key varchar,
                payload_json varchar, source_version varchar, rule_version varchar,
                generated_at timestamp
            )
            """
        )
        conn.execute(
            """
            insert into fact_pnl_by_business_precompute values (
                2025, '2025-12-31', 'monthly', '', '',
                '{"stale": true}', 'sv-anything', 'rv_pnl_by_business_precompute_v3',
                current_timestamp
            )
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    result = repo.fetch_pnl_by_business_precompute(
        year=2025,
        as_of_date="2025-12-31",
        result_kind="monthly",
        dimension="",
        business_key="",
        expected_rule_version=pnl_repo_module.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION,
    )

    assert result is None
    assert pnl_repo_module.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION != "rv_pnl_by_business_precompute_v3"


def test_formal_fact_rule_gate_rejects_stale_2026_h1_rows(tmp_path) -> None:
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
                report_date varchar,
                interest_income_514 decimal(24, 8),
                fair_value_change_516 decimal(24, 8),
                capital_gain_517 decimal(24, 8),
                manual_adjustment decimal(24, 8),
                total_pnl decimal(24, 8),
                rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values (
                '2026-04-30', 106, 0, 0, 0, 106, 'rv_pnl_phase2_materialize_v1'
            )
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    assert hasattr(repo, "require_formal_pnl_rule_version")
    with pytest.raises(RuntimeError, match="rv_pnl_phase2_materialize_v1"):
        repo.require_formal_pnl_rule_version(
            start_date="2026-01-01",
            end_date="2026-06-30",
            expected_rule_version="rv_pnl_phase2_materialize_v3",
        )


def test_precompute_source_fingerprint_includes_fact_rule_version(tmp_path) -> None:
    import duckdb

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_pnl_fi (
                report_date varchar,
                interest_income_514 decimal(24, 8),
                fair_value_change_516 decimal(24, 8),
                capital_gain_517 decimal(24, 8),
                manual_adjustment decimal(24, 8),
                total_pnl decimal(24, 8),
                rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_pnl_fi values (
                '2026-04-30', 100, 0, 0, 0, 100, 'rv_pnl_phase2_materialize_v1'
            )
            """
        )
    finally:
        conn.close()

    repo = pnl_repo_module.PnlRepository(str(duckdb_path))
    stale_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            "update fact_formal_pnl_fi set rule_version = 'rv_pnl_phase2_materialize_v3'"
        )
    finally:
        conn.close()

    current_source_version = repo.pnl_by_business_precompute_source_version(
        year=2026,
        as_of_date="2026-06-30",
    )

    assert stale_source_version.startswith("sv_pnl_by_business_precompute_v2:")
    assert current_source_version.startswith("sv_pnl_by_business_precompute_v2:")
    assert stale_source_version != current_source_version
    assert "rv_pnl_phase2_materialize_v1" in stale_source_version
    assert "rv_pnl_phase2_materialize_v3" in current_source_version
