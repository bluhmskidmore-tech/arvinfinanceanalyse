from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

from backend.app.repositories.home_macro_release_context_repo import (
    HomeMacroReleaseContextRepository,
)


def _create_std_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table std_external_macro_daily (
          series_id varchar not null,
          vendor_name varchar not null,
          domain varchar not null,
          trade_date varchar not null,
          value_numeric double,
          frequency varchar,
          unit varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          ingest_batch_id varchar not null,
          raw_zone_path varchar,
          created_at timestamp not null
        )
        """
    )


def _insert_std(
    conn: duckdb.DuckDBPyConnection,
    *,
    trade_date: str,
    value: float | None,
    batch: str,
    created_at: datetime,
) -> None:
    conn.execute(
        """
        insert into std_external_macro_daily values (
          'tushare.macro.cn_cpi.monthly', 'tushare', 'macro', ?, ?,
          'monthly', 'pct', ?, ?, 'm2b.external_std_macro_etl.v1', ?, null, ?
        )
        """,
        [
            trade_date,
            value,
            f"raw@{batch}",
            f"tushare|{batch}",
            batch,
            created_at,
        ],
    )


def _create_choice_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table fact_choice_macro_daily (
          series_id varchar,
          series_name varchar,
          trade_date varchar,
          value_numeric double,
          frequency varchar,
          unit varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          quality_flag varchar,
          run_id varchar
        )
        """
    )


def test_std_reader_canonicalizes_batch_before_latest_previous_selection(tmp_path: Path) -> None:
    db = tmp_path / "macro.duckdb"
    conn = duckdb.connect(str(db))
    try:
        _create_std_table(conn)
        _insert_std(
            conn,
            trade_date="2026-05-01",
            value=1.2,
            batch="batch-old",
            created_at=datetime(2026, 6, 1, 9, 0),
        )
        _insert_std(
            conn,
            trade_date="2026-05-01",
            value=None,
            batch="batch-new",
            created_at=datetime(2026, 6, 2, 9, 0),
        )
        _insert_std(
            conn,
            trade_date="2026-04-01",
            value=0.0,
            batch="batch-apr",
            created_at=datetime(2026, 5, 2, 9, 0),
        )
        _insert_std(
            conn,
            trade_date="2026-07-01",
            value=9.9,
            batch="look-ahead",
            created_at=datetime(2026, 7, 2, 9, 0),
        )
    finally:
        conn.close()

    result = HomeMacroReleaseContextRepository(db).read_recent_observations(
        table="std_external_macro_daily",
        series_id="tushare.macro.cn_cpi.monthly",
        cutoff_date=date(2026, 6, 30),
        limit=2,
    )

    assert result.error is None
    assert [row.observation_date for row in result.observations] == [
        date(2026, 5, 1),
        date(2026, 4, 1),
    ]
    assert result.observations[0].value is None
    assert result.observations[0].ingest_batch_id == "batch-new"
    assert result.observations[1].value == 0.0


def test_choice_reader_deduplicates_by_latest_run_and_preserves_lineage(tmp_path: Path) -> None:
    db = tmp_path / "choice.duckdb"
    conn = duckdb.connect(str(db))
    try:
        _create_choice_table(conn)
        rows = [
            (
                "M0017126",
                "制造业PMI",
                "2026-06-01",
                49.9,
                "monthly",
                "index",
                "sv-old",
                "vv-old",
                "rv-old",
                "warning",
                "backfill_macro_v1:20260712T010101Z",
            ),
            (
                "M0017126",
                "制造业PMI",
                "2026-06-01",
                50.3,
                "monthly",
                "index",
                "sv-new",
                "vv-backfill_macro_tushare_macro-new",
                "rv-new",
                "ok",
                "backfill_macro_v1:20260713T010101Z",
            ),
            (
                "M0017126",
                "制造业PMI",
                "2026-05-01",
                0.0,
                "monthly",
                "index",
                "sv-prev",
                "vv-prev",
                "rv-prev",
                "ok",
                "backfill_macro_v1:20260613T010101Z",
            ),
            (
                "M0017126",
                "制造业PMI",
                "2026-08-01",
                88.8,
                "monthly",
                "index",
                "sv-lookahead",
                "vv-lookahead",
                "rv-lookahead",
                "ok",
                "backfill_macro_v1:20260813T010101Z",
            ),
        ]
        conn.executemany("insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    finally:
        conn.close()

    result = HomeMacroReleaseContextRepository(db).read_recent_observations(
        table="fact_choice_macro_daily",
        series_id="M0017126",
        cutoff_date=date(2026, 7, 16),
        limit=2,
    )

    assert result.error is None
    assert [row.value for row in result.observations] == [50.3, 0.0]
    latest = result.observations[0]
    assert latest.source_version == "sv-new"
    assert latest.vendor_version == "vv-backfill_macro_tushare_macro-new"
    assert latest.rule_version == "rv-new"
    assert latest.quality_flag == "ok"
    assert latest.run_id == "backfill_macro_v1:20260713T010101Z"


def test_missing_relation_returns_structured_error(tmp_path: Path) -> None:
    db = tmp_path / "empty.duckdb"
    conn = duckdb.connect(str(db))
    conn.close()

    result = HomeMacroReleaseContextRepository(db).read_recent_observations(
        table="std_external_macro_daily",
        series_id="tushare.macro.cn_cpi.monthly",
        cutoff_date=date(2026, 7, 16),
        limit=2,
    )

    assert result.error == "relation_missing"
    assert result.observations == []


def test_reader_rejects_unknown_table_and_invalid_limit(tmp_path: Path) -> None:
    repo = HomeMacroReleaseContextRepository(tmp_path / "empty.duckdb")

    with pytest.raises(ValueError, match="Unsupported home macro table"):
        repo.read_recent_observations(
            table="std_external_macro_daily; drop table x",
            series_id="x",
            cutoff_date=date(2026, 7, 16),
            limit=2,
        )

    with pytest.raises(ValueError, match="limit"):
        repo.read_recent_observations(
            table="std_external_macro_daily",
            series_id="x",
            cutoff_date=date(2026, 7, 16),
            limit=0,
        )
