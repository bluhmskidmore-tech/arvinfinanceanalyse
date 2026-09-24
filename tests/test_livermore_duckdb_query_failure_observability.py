"""Observability: distinguish DuckDB query failure from genuine empty Livermore reads."""

from __future__ import annotations

from unittest.mock import MagicMock

import duckdb

from backend.app.repositories.livermore_market_read_repo import (
    open_livermore_read_connection,
)
from backend.app.services import market_data_livermore_service as livermore_service
from backend.app.services.livermore_candidate_history_service import (
    DUCKDB_QUERY_FAILED_PREFIX,
    livermore_candidate_history_envelope,
    livermore_candidate_history_envelope_or_none,
)
from backend.app.services.market_data_livermore_service import (
    DUCKDB_QUERY_FAILED_PREFIX as LIVERMORE_DUCKDB_QUERY_FAILED_PREFIX,
    _load_factor_screen_rows,
    _load_sector_rank_inputs,
)

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]



def test_factor_screen_query_failure_distinct_from_missing_rows(tmp_path, monkeypatch, caplog):
    duckdb_path = tmp_path / "factor_obs.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date date,
              stock_code varchar,
              stock_name varchar,
              pe_ttm double,
              pb double,
              ps_ttm double,
              market_cap double,
              one_month_return double,
              three_month_return double,
              twelve_month_return double,
              volatility double,
              dividend_yield double,
              industry varchar,
              sector_code varchar,
              sector_name varchar,
              avg_amount_20d double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
    finally:
        conn.close()

    empty_load = _load_factor_screen_rows(duckdb_path=str(duckdb_path), as_of_date="2026-05-08")
    assert empty_load.rows == []
    assert empty_load.unavailable_reason
    assert not empty_load.unavailable_reason.startswith(LIVERMORE_DUCKDB_QUERY_FAILED_PREFIX)
    assert "DuckDB query failed" not in empty_load.unavailable_reason

    broken = MagicMock()
    broken.execute.side_effect = duckdb.Error("catalog is corrupt: factor_screen probe")

    def _fake_open(_path: str):
        return broken

    monkeypatch.setattr(livermore_service, "open_livermore_read_connection", _fake_open)
    with caplog.at_level("WARNING"):
        failed_load = _load_factor_screen_rows(duckdb_path=str(duckdb_path), as_of_date="2026-05-08")

    assert failed_load.rows == []
    assert failed_load.unavailable_reason.startswith(LIVERMORE_DUCKDB_QUERY_FAILED_PREFIX)
    assert "choice_stock_factor_snapshot" in failed_load.unavailable_reason
    assert "2026-05-08" in failed_load.unavailable_reason
    assert "catalog is corrupt" in failed_load.unavailable_reason
    assert any("livermore_duckdb_query_failed" in record.message for record in caplog.records)
    assert failed_load.unavailable_reason != empty_load.unavailable_reason


def test_sector_rank_query_failure_records_diagnostic_sink(tmp_path, monkeypatch, caplog):
    duckdb_path = tmp_path / "sector_obs.duckdb"
    writer = duckdb.connect(str(duckdb_path))
    try:
        writer.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date date, stock_code varchar, sw2021code varchar, sw2021 varchar,
              source_version varchar, vendor_version varchar
            )
            """
        )
        writer.execute(
            """
            create table choice_stock_daily_observation (
              trade_date date, stock_code varchar, pctchange double, turn double, amplitude double,
              source_version varchar, vendor_version varchar
            )
            """
        )
    finally:
        writer.close()

    empty_rows, empty_tables, _, _ = _load_sector_rank_inputs(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-05-08",
    )
    assert empty_rows == []
    # Genuine missing snapshot date still reports required tables without query-failure sink.
    assert empty_tables  # membership/obs present but no rows on or before date

    broken = MagicMock()
    broken.execute.side_effect = duckdb.Error("IO Error: disk full while reading sector rank")

    def _fake_open(_path: str):
        return broken

    monkeypatch.setattr(livermore_service, "open_livermore_read_connection", _fake_open)
    failures: list[str] = []
    with caplog.at_level("WARNING"):
        failed_rows, failed_tables, _, _ = _load_sector_rank_inputs(
            duckdb_path=str(duckdb_path),
            as_of_date="2026-05-08",
            query_failures=failures,
        )

    assert failed_rows == []
    assert failed_tables
    assert failures
    assert failures[0].startswith(LIVERMORE_DUCKDB_QUERY_FAILED_PREFIX)
    assert "sector_rank_inputs" in failures[0]
    assert "disk full" in failures[0]
    assert any("livermore_duckdb_query_failed" in record.message for record in caplog.records)


def test_candidate_history_envelope_or_none_query_failure_vs_empty(tmp_path, monkeypatch, caplog):
    missing_path = tmp_path / "missing_candidate_history.duckdb"
    empty_envelope = livermore_candidate_history_envelope(
        duckdb_path=str(missing_path),
        stock_code=None,
        snapshot_from="2026-01-01",
        snapshot_to="2026-01-31",
        limit=10,
    )
    assert empty_envelope is not None
    assert empty_envelope["result"]["items"] == []

    def _boom(**_kwargs):
        raise duckdb.Error("Binder Error: table livermore_candidate_history is damaged")

    monkeypatch.setattr(
        "backend.app.services.livermore_candidate_history_service.livermore_candidate_history_envelope",
        _boom,
    )
    failures: list[str] = []
    with caplog.at_level("WARNING"):
        failed = livermore_candidate_history_envelope_or_none(
            duckdb_path=str(missing_path),
            stock_code=None,
            snapshot_from="2026-01-01",
            snapshot_to="2026-01-31",
            limit=10,
            query_failures=failures,
        )

    assert failed is None
    assert failures
    assert failures[0].startswith(DUCKDB_QUERY_FAILED_PREFIX)
    assert "candidate_history_envelope" in failures[0]
    assert "damaged" in failures[0]
    assert any("livermore_duckdb_query_failed" in record.message for record in caplog.records)


def test_open_livermore_read_connection_logs_failure(tmp_path, monkeypatch, caplog):
    path = tmp_path / "busy.duckdb"
    path.write_text("not-a-duckdb-file", encoding="utf-8")

    with caplog.at_level("WARNING"):
        conn = open_livermore_read_connection(str(path))

    assert conn is None
    assert any("livermore_duckdb_query_failed" in record.message for record in caplog.records)
    assert any("open_livermore_read_connection" in record.message for record in caplog.records)
