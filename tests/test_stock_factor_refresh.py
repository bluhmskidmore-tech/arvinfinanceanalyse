from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import duckdb

from backend.app.tasks.stock_factor_refresh import (
    FACTOR_FIELDS,
    SOURCE_VERSION,
    refresh_stock_factors,
)


def _seed_universe(duckdb_path: Path, *, as_of_date: str = "2026-05-20") -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists choice_stock_universe (
              as_of_date varchar,
              stock_code varchar,
              stock_name varchar,
              field_key varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute("delete from choice_stock_universe")
        conn.executemany(
            "insert into choice_stock_universe values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (as_of_date, "000001.SZ", "Ping An", "a_share_universe_sector_001004", "sv", "vv", "rv", "run"),
                (as_of_date, "600000.SH", "SPDB", "a_share_universe_sector_001004", "sv", "vv", "rv", "run"),
            ],
        )
    finally:
        conn.close()


class FakeChoiceFactorClient:
    def css(self, codes: object, indicators: object, *, options: str = "") -> object:
        requested = [code for code in str(codes).split(",") if code]
        return SimpleNamespace(
            ErrorCode=0,
            Indicators=["PETTM", "PBMRT", "PSTTM", "ROEWA", "GPMARGIN", "DIVYIELD"],
            Data={code: [10.0 + index, 1.0 + index, 2.0 + index, 15.0, 40.0, 3.5] for index, code in enumerate(requested)},
        )


def test_refresh_stock_factors_dry_run_reports_universe_and_fields(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_universe(duckdb_path)

    payload = refresh_stock_factors(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-20",
        dry_run=True,
    )

    assert payload["status"] == "dry_run"
    assert payload["stock_code_count"] == 2
    assert payload["fields"] == list(FACTOR_FIELDS)
    assert payload["source_version"] == SOURCE_VERSION


def test_refresh_stock_factors_writes_choice_rows(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_universe(duckdb_path)

    payload = refresh_stock_factors(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-20",
        choice_client=FakeChoiceFactorClient(),
    )

    assert payload["status"] == "completed"
    assert payload["row_count"] == 2
    assert payload["source_version"] == SOURCE_VERSION

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, pe, pb, ps, roe, gross_margin, dividend_yield, source_version
            from choice_stock_factor_snapshot
            where as_of_date = '2026-05-20'
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows[0][0] == "000001.SZ"
    assert rows[0][1] == 10.0
    assert rows[0][2] == 1.0
    assert rows[0][3] == 2.0
    assert rows[0][4] == 0.15
    assert rows[0][5] == 0.4
    assert rows[0][6] == 0.035
    assert rows[0][7] == SOURCE_VERSION
