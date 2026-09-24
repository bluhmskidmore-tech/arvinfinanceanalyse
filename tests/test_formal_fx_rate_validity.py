from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.pnl_repo import PnlRepository


def _seed_formal_fx_row(
    duckdb_path: Path,
    *,
    mid_rate: str,
    trade_date: str = "2026-02-27",
    is_business_day: bool = True,
    is_carry_forward: bool = False,
    observed_trade_date: str = "2026-02-27",
) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date varchar,
              base_currency varchar,
              quote_currency varchar,
              mid_rate varchar,
              source_version varchar,
              is_business_day boolean,
              is_carry_forward boolean,
              observed_trade_date varchar
            )
            """
        )
        conn.execute(
            """
            insert into fx_daily_mid values
            (?, 'USD', 'CNY', ?, 'sv_fx_invalid', ?, ?, ?)
            """,
            [trade_date, mid_rate, is_business_day, is_carry_forward, observed_trade_date],
        )
    finally:
        conn.close()


@pytest.mark.parametrize(
    "invalid_rate",
    ["0", "-7.2", "NaN", "Infinity", "-Infinity", "not-a-number"],
)
def test_balance_formal_fx_lookup_rejects_invalid_rate(tmp_path, invalid_rate) -> None:
    duckdb_path = tmp_path / "balance.duckdb"
    _seed_formal_fx_row(duckdb_path, mid_rate=invalid_rate)

    with pytest.raises(ValueError, match="finite and greater than zero"):
        BalanceAnalysisRepository(str(duckdb_path)).lookup_formal_fx_rate(
            report_date="2026-02-27",
            base_currency="USD",
        )


@pytest.mark.parametrize(
    "invalid_rate",
    ["0", "-7.2", "NaN", "Infinity", "-Infinity", "not-a-number"],
)
def test_pnl_formal_fx_lookup_rejects_invalid_rate(tmp_path, invalid_rate) -> None:
    duckdb_path = tmp_path / "pnl.duckdb"
    _seed_formal_fx_row(duckdb_path, mid_rate=invalid_rate)

    with pytest.raises(ValueError, match="finite and greater than zero"):
        PnlRepository(str(duckdb_path)).fetch_formal_fx_rates(
            "2026-02-27",
            {"USD"},
        )


def test_formal_fx_consumers_reject_carry_forward_on_business_day(tmp_path) -> None:
    duckdb_path = tmp_path / "business-day-carry.duckdb"
    _seed_formal_fx_row(
        duckdb_path,
        mid_rate="7.2",
        trade_date="2026-03-02",
        is_business_day=False,
        is_carry_forward=True,
        observed_trade_date="2026-02-27",
    )

    with pytest.raises(ValueError, match="confirmed non-business-day"):
        BalanceAnalysisRepository(str(duckdb_path)).lookup_formal_fx_rate(
            report_date="2026-03-02",
            base_currency="USD",
        )

    with pytest.raises(ValueError, match="confirmed non-business-day"):
        PnlRepository(str(duckdb_path)).fetch_formal_fx_rates(
            "2026-03-02",
            {"USD"},
        )
