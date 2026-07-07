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
                '{"stale": true}', 'sv-anything', 'rv_pnl_by_business_precompute_v1',
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
    assert pnl_repo_module.PNL_BY_BUSINESS_PRECOMPUTE_RULE_VERSION != "rv_pnl_by_business_precompute_v1"
