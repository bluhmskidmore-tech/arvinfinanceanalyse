from __future__ import annotations

from pathlib import Path
from decimal import Decimal
import importlib

import duckdb
import pytest

from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.adb_analysis_repo import AdbAnalysisRepository
from backend.app.repositories.pnl_repo import PnlRepository


def _read_formal_fx(consumer, duckdb_path, report_date, monkeypatch):
    if consumer == "balance":
        return BalanceAnalysisRepository(str(duckdb_path)).lookup_formal_fx_rate(
            report_date=report_date, base_currency="USD"
        ).rate
    if consumer == "adb":
        return AdbAnalysisRepository(str(duckdb_path)).lookup_formal_fx_rate(
            report_date=report_date, base_currency="USD"
        )
    if consumer == "pnl":
        return PnlRepository(str(duckdb_path)).fetch_formal_fx_rates(report_date, {"USD"})["USD"]
    module = importlib.import_module("backend.app.tasks.pnl_materialize")
    # The fixture owns just fx_daily_mid; migrations are unrelated to FX admission.
    monkeypatch.setattr(module, "_ensure_tables", lambda _conn: None)
    return module._load_pnl_fx_rates(
        duckdb_path=duckdb_path,
        report_date=report_date,
        fi_rows=[{"fx_base_currency": "USD"}],
        nonstd_rows_by_type={},
    )["USD"][0]


@pytest.mark.parametrize("consumer", ["balance", "adb", "pnl", "pnl_materialize"])
@pytest.mark.parametrize(
    "report_date,observed_date,business_day,carry_forward",
    [
        ("2026-03-08", "2026-03-02", False, True),
        ("2026-01-19", "2026-01-16", False, True),
        ("2026-03-08", "2026-03-07", False, True),
        ("2026-02-18", "2026-02-16", False, True),
        ("2026-03-08", "2026-03-08", True, False),
        ("2026-03-06", "2026-03-05", True, False),
        ("2026-03-06", None, True, False),
    ],
)
def test_formal_fx_consumers_reject_invalid_publication_dates(
    tmp_path, monkeypatch, consumer, report_date, observed_date, business_day, carry_forward
) -> None:
    duckdb_path = tmp_path / "invalid-publication.duckdb"
    _seed_formal_fx_row(
        duckdb_path, mid_rate="7.2", trade_date=report_date,
        is_business_day=business_day, is_carry_forward=carry_forward,
        observed_trade_date=observed_date,
    )
    with pytest.raises(ValueError):
        _read_formal_fx(consumer, duckdb_path, report_date, monkeypatch)


@pytest.mark.parametrize("consumer", ["balance", "adb", "pnl", "pnl_materialize"])
@pytest.mark.parametrize(
    "report_date,observed_date,business_day,carry_forward",
    [
        ("2026-03-08", "2026-03-06", False, True),
        ("2026-02-22", "2026-02-13", False, True),
        ("2026-01-19", "2026-01-19", True, False),
    ],
)
def test_formal_fx_consumers_accept_exact_or_previous_publication(
    tmp_path, monkeypatch, consumer, report_date, observed_date, business_day, carry_forward
) -> None:
    duckdb_path = tmp_path / "valid-publication.duckdb"
    _seed_formal_fx_row(
        duckdb_path, mid_rate="7.0051", trade_date=report_date,
        is_business_day=business_day, is_carry_forward=carry_forward,
        observed_trade_date=observed_date,
    )
    assert _read_formal_fx(consumer, duckdb_path, report_date, monkeypatch) == Decimal("7.0051")


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
