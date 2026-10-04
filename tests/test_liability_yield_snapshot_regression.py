"""Snapshot yield fallback must retain the calculation's maturity boundary."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.liability_analytics_compat import compute_liability_yield_metrics
from backend.app.repositories.liability_analytics_repo import LiabilityAnalyticsRepository

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_liability_analytics]


@pytest.fixture()
def snapshot_repo(tmp_path: Path) -> LiabilityAnalyticsRepository:
    path = tmp_path / "synthetic-yield.duckdb"
    with duckdb.connect(str(path)) as conn:
        conn.execute(
            """
            create table zqtz_bond_daily_snapshot (
                report_date date, instrument_code varchar, instrument_name varchar,
                asset_class varchar, bond_type varchar, is_issuance_like boolean,
                face_value_native decimal(18, 4), market_value_native decimal(18, 4),
                amortized_cost_native decimal(18, 4), coupon_rate decimal(10, 4),
                ytm_value decimal(10, 4), maturity_date date,
                source_version varchar, rule_version varchar
            )
            """
        )
        conn.executemany(
            "insert into zqtz_bond_daily_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("2026-08-31", "SYN-A", "Synthetic A", "持有至到期类资产", "gov", False,
                 120, 120, 100, 2, 2, "2027-08-31", "synthetic-s1", "synthetic-r1"),
                ("2026-08-31", "SYN-B", "Synthetic B", "可供出售类资产", "gov", False,
                 350, 300, 250, 4, 4, "2027-08-31", "synthetic-s1", "synthetic-r1"),
                # A genuinely undated asset stays excluded despite its positive weight/rate.
                ("2026-08-31", "SYN-UNDATED", "Synthetic undated", "持有至到期类资产", "gov", False,
                 900, 900, 900, 9, 9, None, "synthetic-s1", "synthetic-r1"),
                # Explicit zero amortized cost must not fall back to the positive market value.
                ("2026-08-31", "SYN-ZERO", "Synthetic zero", "持有至到期类资产", "gov", False,
                 900, 900, 0, 9, 9, "2027-08-31", "synthetic-s1", "synthetic-r1"),
                ("2026-07-31", "SYN-JUL", "Synthetic July", "可供出售类资产", "gov", False,
                 100, 100, 100, 8, 8, "2027-07-31", "synthetic-s0", "synthetic-r0"),
            ],
        )
        conn.execute(
            """
            create table tyw_interbank_daily_snapshot (
                report_date date, position_side varchar, principal_native decimal(18, 4),
                funding_cost_rate decimal(10, 4), source_version varchar, rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot values
                ('2026-08-31', 'liability', 400, 1.5, 'synthetic-s1', 'synthetic-r1')
            """
        )
    return LiabilityAnalyticsRepository(str(path))


@pytest.mark.parametrize("combined_read", [False, True], ids=["bond-batch", "combined-batch"])
def test_snapshot_yield_batch_keeps_dated_assets_and_independent_weighted_result(
    snapshot_repo: LiabilityAnalyticsRepository, combined_read: bool
) -> None:
    report_date = "2026-08-31"
    if combined_read:
        bonds, interbank = snapshot_repo.fetch_yield_rows_for_dates([report_date])
    else:
        bonds = snapshot_repo.fetch_zqtz_yield_rows_for_dates([report_date])
        interbank = snapshot_repo.fetch_tyw_yield_rows_for_dates([report_date])

    result = compute_liability_yield_metrics(report_date, bonds[report_date], interbank[report_date])

    # Independent expectation: (100 * 2% + 300 * 4%) / 400 = 3.5%; 3.5% - 1.5% = 2%.
    assert result["kpi"]["asset_yield"] == pytest.approx(0.035)
    assert result["kpi"]["liability_cost"] == pytest.approx(0.015)
    assert result["kpi"]["market_liability_cost"] == pytest.approx(0.015)
    assert result["kpi"]["nim"] == pytest.approx(0.02)
    assert set(bonds) == {report_date}
    assert sum(row["maturity_date"] == date(2027, 8, 31) for row in bonds[report_date]) == 3
    assert sum(row["maturity_date"] is None for row in bonds[report_date]) == 1
    assert {row["source_version"] for row in bonds[report_date]} == {"synthetic-s1"}


@pytest.mark.parametrize("combined_read", [False, True], ids=["bond-batch", "combined-batch"])
def test_snapshot_yield_batch_does_not_manufacture_yield_when_all_assets_are_undated(
    snapshot_repo: LiabilityAnalyticsRepository, combined_read: bool
) -> None:
    with duckdb.connect(snapshot_repo.path) as conn:
        conn.execute("update zqtz_bond_daily_snapshot set maturity_date = null")

    report_date = "2026-08-31"
    if combined_read:
        bonds, interbank = snapshot_repo.fetch_yield_rows_for_dates([report_date])
    else:
        bonds = snapshot_repo.fetch_zqtz_yield_rows_for_dates([report_date])
        interbank = snapshot_repo.fetch_tyw_yield_rows_for_dates([report_date])

    result = compute_liability_yield_metrics(report_date, bonds[report_date], interbank[report_date])
    assert result["kpi"]["asset_yield"] is None
    assert result["kpi"]["nim"] is None
    assert result["kpi"]["liability_cost"] == pytest.approx(0.015)
