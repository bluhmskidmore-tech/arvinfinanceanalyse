from __future__ import annotations

import duckdb
import pytest

from backend.app.tasks.concept_membership_intervalize import (
    INTERVAL_TABLE,
    MembershipSnapshotRow,
    build_membership_intervals,
    ensure_concept_membership_interval_schema,
    intervalize_concept_membership,
)

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]

_SNAPSHOT_DDL = """
create table choice_stock_concept_membership (
  as_of_date varchar,
  stock_code varchar,
  concept_code varchar,
  concept_name varchar,
  concept_source varchar,
  field_key varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar
)
"""


def _snapshot(
    as_of_date: str,
    stock_code: str,
    concept_code: str,
    concept_name: str = "",
    concept_source: str = "tushare_ths_current",
) -> MembershipSnapshotRow:
    return MembershipSnapshotRow(
        as_of_date=as_of_date,
        stock_code=stock_code,
        concept_code=concept_code,
        concept_name=concept_name or f"Concept {concept_code}",
        concept_source=concept_source,
        field_key="tushare_ths_concept_membership",
        source_version=f"sv_{as_of_date}",
        vendor_version=f"vv_{as_of_date}",
    )


def _insert_snapshots(conn: duckdb.DuckDBPyConnection, rows: list[MembershipSnapshotRow]) -> None:
    conn.executemany(
        "insert into choice_stock_concept_membership values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row.as_of_date,
                row.stock_code,
                row.concept_code,
                row.concept_name,
                row.concept_source,
                row.field_key,
                row.source_version,
                row.vendor_version,
                "rv_src",
                "run_src",
            )
            for row in rows
        ],
    )


def _interval_rows(conn: duckdb.DuckDBPyConnection) -> list[tuple]:
    return conn.execute(
        f"""
        select stock_code, concept_code, concept_name, concept_source,
               valid_from, valid_to, last_observed_date
        from {INTERVAL_TABLE}
        order by stock_code, concept_source, concept_code, valid_from
        """
    ).fetchall()


# ---- pure fold ---------------------------------------------------------


def test_single_snapshot_opens_intervals_without_history_backfill() -> None:
    intervals = build_membership_intervals(
        [
            _snapshot("2026-05-13", "S1", "C1"),
            _snapshot("2026-05-13", "S1", "C2"),
        ]
    )

    assert [(row.concept_code, row.valid_from, row.valid_to) for row in intervals] == [
        ("C1", "2026-05-13", None),
        ("C2", "2026-05-13", None),
    ]
    assert all(row.last_observed_date == "2026-05-13" for row in intervals)


def test_empty_snapshot_set_yields_no_intervals() -> None:
    assert build_membership_intervals([]) == []


def test_diff_closes_exits_extends_stays_and_opens_entries() -> None:
    intervals = build_membership_intervals(
        [
            _snapshot("2026-05-13", "S1", "C_exit"),
            _snapshot("2026-05-13", "S1", "C_stay"),
            _snapshot("2026-07-08", "S1", "C_stay"),
            _snapshot("2026-07-08", "S1", "C_enter"),
        ]
    )

    by_code = {row.concept_code: row for row in intervals}
    assert len(intervals) == 3
    # exit event: closed half-open at the snapshot that discovered the exit
    assert (by_code["C_exit"].valid_from, by_code["C_exit"].valid_to) == ("2026-05-13", "2026-07-08")
    # stay: single interval extended, still open
    assert (by_code["C_stay"].valid_from, by_code["C_stay"].valid_to) == ("2026-05-13", None)
    assert by_code["C_stay"].last_observed_date == "2026-07-08"
    # entry event: opened at the discovering snapshot
    assert (by_code["C_enter"].valid_from, by_code["C_enter"].valid_to) == ("2026-07-08", None)


def test_unobserved_stock_day_does_not_close_intervals() -> None:
    """Probe-based snapshots: a stock absent from a snapshot was not observed."""
    intervals = build_membership_intervals(
        [
            _snapshot("2026-05-13", "S1", "C1"),
            # S1 is absent on 2026-07-08 (only S2 was probed) -> no exit for S1.
            _snapshot("2026-07-08", "S2", "C1"),
        ]
    )

    by_stock = {row.stock_code: row for row in intervals}
    assert by_stock["S1"].valid_to is None
    assert by_stock["S1"].last_observed_date == "2026-05-13"
    assert by_stock["S2"].valid_from == "2026-07-08"


def test_reentry_after_exit_creates_a_second_scd_row() -> None:
    intervals = build_membership_intervals(
        [
            _snapshot("2026-05-13", "S1", "C1"),
            _snapshot("2026-07-08", "S1", "C_other"),
            _snapshot("2026-07-10", "S1", "C1"),
        ]
    )

    c1_rows = [row for row in intervals if row.concept_code == "C1"]
    assert [(row.valid_from, row.valid_to) for row in c1_rows] == [
        ("2026-05-13", "2026-07-08"),
        ("2026-07-10", None),
    ]


def test_concept_sources_are_intervalized_independently() -> None:
    intervals = build_membership_intervals(
        [
            _snapshot("2026-05-13", "S1", "C1", concept_source="tushare_ths_current"),
            _snapshot("2026-07-08", "S1", "C2", concept_source="choice"),
        ]
    )

    by_source = {row.concept_source: row for row in intervals}
    # the choice observation on 07-08 says nothing about the tushare track
    assert by_source["tushare_ths_current"].valid_to is None
    assert by_source["choice"].valid_from == "2026-07-08"


# ---- task write path ---------------------------------------------------


def test_intervalize_rerun_on_same_snapshot_set_is_idempotent(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(_SNAPSHOT_DDL)
        _insert_snapshots(
            conn,
            [
                _snapshot("2026-05-13", "S1", "C1"),
                _snapshot("2026-07-08", "S1", "C2"),
            ],
        )
    finally:
        conn.close()

    first = intervalize_concept_membership(duckdb_path=str(duckdb_path), run_id="run_a")
    assert first["status"] == "completed"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows_first = _interval_rows(conn)
    finally:
        conn.close()

    second = intervalize_concept_membership(duckdb_path=str(duckdb_path), run_id="run_b")
    assert second["status"] == "completed"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows_second = _interval_rows(conn)
    finally:
        conn.close()

    assert rows_first == rows_second
    assert first["interval_row_count"] == second["interval_row_count"] == 2


def test_intervalize_appended_snapshot_closes_and_opens_incrementally(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(_SNAPSHOT_DDL)
        _insert_snapshots(
            conn,
            [
                _snapshot("2026-05-13", "S1", "C_exit"),
                _snapshot("2026-05-13", "S1", "C_stay"),
            ],
        )
    finally:
        conn.close()

    first = intervalize_concept_membership(duckdb_path=str(duckdb_path), run_id="run_a")
    assert first["interval_row_count"] == 2
    assert first["open_interval_count"] == 2

    conn = duckdb.connect(str(duckdb_path))
    try:
        _insert_snapshots(
            conn,
            [
                _snapshot("2026-07-08", "S1", "C_stay"),
                _snapshot("2026-07-08", "S1", "C_enter"),
            ],
        )
    finally:
        conn.close()

    second = intervalize_concept_membership(duckdb_path=str(duckdb_path), run_id="run_b")
    assert second["status"] == "completed"
    assert second["snapshot_dates"] == ["2026-05-13", "2026-07-08"]
    assert second["interval_row_count"] == 3
    assert second["open_interval_count"] == 2
    assert second["closed_interval_count"] == 1

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = _interval_rows(conn)
    finally:
        conn.close()
    by_code = {row[1]: row for row in rows}
    assert (by_code["C_exit"][4], by_code["C_exit"][5]) == ("2026-05-13", "2026-07-08")
    assert (by_code["C_stay"][4], by_code["C_stay"][5]) == ("2026-05-13", None)
    assert (by_code["C_enter"][4], by_code["C_enter"][5]) == ("2026-07-08", None)


def test_intervalize_empty_snapshot_table_reports_no_snapshots_and_preserves_intervals(
    tmp_path,
) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(_SNAPSHOT_DDL)
        ensure_concept_membership_interval_schema(conn)
        conn.execute(
            f"""
            insert into {INTERVAL_TABLE} values
            ('S1', 'C1', 'Concept C1', 'tushare_ths_current',
             '2026-05-13', null, '2026-05-13', 'fk', 'sv', 'vv', 'rv', 'run')
            """
        )
    finally:
        conn.close()

    result = intervalize_concept_membership(duckdb_path=str(duckdb_path), run_id="run_a")

    assert result["status"] == "no_snapshots"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        assert conn.execute(f"select count(*) from {INTERVAL_TABLE}").fetchone()[0] == 1
    finally:
        conn.close()


def test_intervalize_missing_snapshot_table_reports_no_snapshots(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(duckdb_path)).close()

    result = intervalize_concept_membership(duckdb_path=str(duckdb_path))

    assert result["status"] == "no_snapshots"


def test_ensure_interval_schema_is_idempotent(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        ensure_concept_membership_interval_schema(conn)
        ensure_concept_membership_interval_schema(conn)
        tables = {
            row[0]
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert INTERVAL_TABLE in tables
