"""Realtime market-gate label anchor (``livermore_gate_history``, slice 41).

Covers the G-1 governance remediation:

- migration creates the table (three-way schema registration);
- the write task persists the freshest gate evaluation only (idempotent
  delete+insert, ``source='realtime'``), with a post-write consistency
  self-check;
- previously persisted labels are never rewritten; a replay that no longer
  matches them is reported as drift (the label-drift detector) with a WARN —
  scanned over an independent latest-N observation window so a normal daily
  refresh (run window = newest date only) still checks historical anchors;
- historical / future / stale targets are skipped — the table never
  backfills the past and never anchors a not-yet-happened date;
- the read side (``load_gate_exposure_by_date``) prefers the persisted label
  (``source='persisted:livermore_gate_history'``) and keeps the replay
  fallback for dates without a row.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

import backend.app.tasks.livermore_gate_history_materialize as gate_history_task
from backend.app.core_finance.gate_exposure_series import load_gate_exposure_by_date
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.tasks.livermore_gate_history_materialize import (
    persist_livermore_gate_history_for_run,
)
from backend.app.tasks.livermore_gate_supplement import (
    materialize_livermore_gate_supplement_daily,
)

_T = date(2026, 6, 8)


def _seed_benchmark(conn: duckdb.DuckDBPyConnection, *, end: date, n_days: int = 65) -> None:
    """Rising CSI300 closes ending at ``end`` so both trend legs pass."""
    conn.execute(
        """
        create table if not exists fact_choice_macro_daily (
          series_id varchar,
          trade_date varchar,
          value_numeric double,
          quality_flag varchar
        )
        """
    )
    conn.executemany(
        "insert into fact_choice_macro_daily values ('CA.CSI300', ?, ?, 'ok')",
        [
            ((end - timedelta(days=n_days - 1 - offset)).isoformat(), 3000.0 + offset * 10.0)
            for offset in range(n_days)
        ],
    )


def _seed_supplement(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[str, float, bool | None]],
) -> None:
    conn.execute(
        """
        create table if not exists fact_livermore_gate_supplement_daily (
          trade_date varchar,
          breadth_5d double,
          limit_up_quality_ok boolean,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        "insert into fact_livermore_gate_supplement_daily values (?, ?, ?, 'sv', 'vv', 'rv', 'run')",
        rows,
    )


def _seed_benchmark_into_migrated_db(db: Path, *, end: date, n_days: int = 65) -> None:
    """Apply the real migrations first, then land benchmark rows in the canonical shape."""
    conn = duckdb.connect(str(db), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        conn.executemany(
            """
            insert into fact_choice_macro_daily (
              series_id, series_name, trade_date, value_numeric, quality_flag
            ) values ('CA.CSI300', 'CSI300', ?, ?, 'ok')
            """,
            [
                ((end - timedelta(days=n_days - 1 - offset)).isoformat(), 3000.0 + offset * 10.0)
                for offset in range(n_days)
            ],
        )
    finally:
        conn.close()


def _gate_history_rows(conn: duckdb.DuckDBPyConnection) -> list[tuple]:
    return conn.execute(
        """
        select trade_date, state, exposure, passed_conditions, available_conditions,
               required_conditions, conditions_json, source, vendor_version, rule_version, run_id
        from livermore_gate_history order by trade_date
        """
    ).fetchall()


# ---------------------------------------------------------------------------
# schema migration
# ---------------------------------------------------------------------------


def test_migration_creates_gate_history_table_idempotently(tmp_path: Path) -> None:
    db = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        apply_pending_migrations_on_connection(conn)
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
        columns = {row[1] for row in conn.execute("pragma table_info('livermore_gate_history')").fetchall()}
    finally:
        conn.close()

    assert "livermore_gate_history" in tables
    assert {
        "trade_date",
        "state",
        "exposure",
        "passed_conditions",
        "available_conditions",
        "required_conditions",
        "conditions_json",
        "source",
        "source_version",
        "vendor_version",
        "rule_version",
        "run_id",
        "persisted_at",
    } <= columns


# ---------------------------------------------------------------------------
# write task: realtime persist + consistency self-check
# ---------------------------------------------------------------------------


def test_persist_writes_realtime_row_readable_as_persisted() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _seed_benchmark(conn, end=_T)
        _seed_supplement(conn, [(_T.isoformat(), 14.0, True)])

        result = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-gate-1",
            vendor_version_by_date={_T.isoformat(): "vv_breadth_x"},
            reference_date=_T,
        )

        rows = _gate_history_rows(conn)
        points = load_gate_exposure_by_date(conn, _T, _T)
    finally:
        conn.close()

    assert result["status"] == "written"
    assert result["target_trade_date"] == _T.isoformat()
    assert result["write_consistency"] == "healthy"
    assert result["drift_status"] == "clean"

    assert len(rows) == 1
    row = rows[0]
    # Rising closes + positive breadth + positive limit-up quality = 4/4.
    assert row[:6] == (_T.isoformat(), "OVERHEAT", 1.0, 4, 4, 4)
    conditions = json.loads(str(row[6]))
    assert [condition["key"] for condition in conditions] == [
        "csi300_close_gt_ma60",
        "csi300_ma20_gt_ma60",
        "breadth_5d_positive",
        "limit_up_quality_positive",
    ]
    assert all(condition["status"] == "pass" for condition in conditions)
    assert row[7] == "realtime"
    assert row[8] == "vv_breadth_x"
    assert row[9] == "rv_livermore_gate_history_v1"
    assert row[10] == "run-gate-1"

    point = points[_T.isoformat()]
    assert point.source == "persisted:livermore_gate_history"
    assert point.state == "OVERHEAT"
    assert point.exposure == pytest.approx(1.0)


def test_persist_is_idempotent() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _seed_benchmark(conn, end=_T)
        _seed_supplement(conn, [(_T.isoformat(), 14.0, True)])

        first = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-gate-1",
            reference_date=_T,
        )
        second = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-gate-2",
            reference_date=_T,
        )
        rows = _gate_history_rows(conn)
    finally:
        conn.close()

    assert first["status"] == second["status"] == "written"
    assert len(rows) == 1
    assert rows[0][:3] == (_T.isoformat(), "OVERHEAT", 1.0)
    # Same-day re-run refreshes the freshest date (mirrors the supplement
    # inputs' own latest-date rewrite policy).
    assert rows[0][10] == "run-gate-2"


# ---------------------------------------------------------------------------
# no historical backfill
# ---------------------------------------------------------------------------


def test_persist_skips_historical_target() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _seed_benchmark(conn, end=_T)
        _seed_supplement(conn, [(_T.isoformat(), 14.0, True)])

        result = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-backfill",
            reference_date=_T + timedelta(days=10),
        )
        count = conn.execute("select count(*) from livermore_gate_history").fetchone()[0]
    finally:
        conn.close()

    assert result["status"] == "skipped_historical_target"
    assert int(count) == 0


def test_persist_never_writes_older_than_newest_persisted_row() -> None:
    earlier = _T - timedelta(days=3)
    conn = duckdb.connect(":memory:")
    try:
        _seed_benchmark(conn, end=_T)
        _seed_supplement(
            conn,
            [(earlier.isoformat(), 10.0, True), (_T.isoformat(), 14.0, True)],
        )

        newest = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-newest",
            reference_date=_T,
        )
        stale = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[earlier.isoformat()],
            run_id="run-stale",
            reference_date=_T,
        )
        rows = _gate_history_rows(conn)
    finally:
        conn.close()

    assert newest["status"] == "written"
    assert stale["status"] == "skipped_stale_target"
    assert [row[0] for row in rows] == [_T.isoformat()]
    assert rows[0][10] == "run-newest"


def test_persist_skips_when_gate_not_replayable() -> None:
    conn = duckdb.connect(":memory:")
    try:
        # No benchmark table at all: the gate cannot be evaluated for the date.
        _seed_supplement(conn, [(_T.isoformat(), 14.0, True)])

        result = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-no-benchmark",
            reference_date=_T,
        )
        count = conn.execute("select count(*) from livermore_gate_history").fetchone()[0]
        points = load_gate_exposure_by_date(conn, _T, _T)
    finally:
        conn.close()

    assert result["status"] == "skipped_not_replayable"
    assert int(count) == 0
    # An existing-but-empty anchor table must not disturb the read fallback.
    assert points[_T.isoformat()].source == "missing"


def test_empty_gate_history_table_keeps_replay_fallback() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _seed_benchmark(conn, end=_T)
        _seed_supplement(conn, [(_T.isoformat(), 14.0, True)])
        conn.execute(
            "create table livermore_gate_history (trade_date varchar, state varchar, exposure double)"
        )

        points = load_gate_exposure_by_date(conn, _T, _T)
    finally:
        conn.close()

    assert points[_T.isoformat()].source == "replayed"
    assert points[_T.isoformat()].state == "OVERHEAT"


# ---------------------------------------------------------------------------
# drift detector: persisted labels are the anchor, replays only compare
# ---------------------------------------------------------------------------


def test_drift_detection_warns_and_preserves_persisted_label(
    caplog: pytest.LogCaptureFixture,
) -> None:
    next_day = _T + timedelta(days=1)
    conn = duckdb.connect(":memory:")
    try:
        _seed_benchmark(conn, end=next_day, n_days=66)
        _seed_supplement(conn, [(_T.isoformat(), 14.0, True)])

        first = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-day-1",
            reference_date=_T,
        )
        assert first["status"] == "written"

        # Vendor restates the breadth input for _T after the realtime label
        # was anchored: the replay flips OVERHEAT (4/4) -> HOT (3/4).
        conn.execute(
            "update fact_livermore_gate_supplement_daily set breadth_5d = -5.0 where trade_date = ?",
            [_T.isoformat()],
        )
        _seed_supplement(conn, [(next_day.isoformat(), 14.0, True)])

        with caplog.at_level("WARNING", logger="backend.app.tasks.livermore_gate_history_materialize"):
            second = persist_livermore_gate_history_for_run(
                conn,
                supplement_dates=[_T.isoformat(), next_day.isoformat()],
                run_id="run-day-2",
                reference_date=next_day,
            )
        rows = _gate_history_rows(conn)
        points = load_gate_exposure_by_date(conn, _T, next_day)
    finally:
        conn.close()

    assert second["status"] == "written"
    assert second["target_trade_date"] == next_day.isoformat()
    assert second["drift_status"] == "detected"
    assert second["drift_count"] == 1
    drift_entry = second["drift_dates"][0]
    assert drift_entry["trade_date"] == _T.isoformat()
    assert drift_entry["persisted_state"] == "OVERHEAT"
    assert drift_entry["persisted_exposure"] == pytest.approx(1.0)
    assert drift_entry["replayed_state"] == "HOT"
    assert drift_entry["replayed_exposure"] == pytest.approx(0.75)
    assert any("drift" in record.message for record in caplog.records)

    # The anchored realtime label survives untouched and stays authoritative
    # on the read side; only the new day was written.
    assert [row[0] for row in rows] == [_T.isoformat(), next_day.isoformat()]
    assert rows[0][1:3] == ("OVERHEAT", 1.0)
    assert rows[0][10] == "run-day-1"
    assert points[_T.isoformat()].source == "persisted:livermore_gate_history"
    assert points[_T.isoformat()].state == "OVERHEAT"
    assert points[_T.isoformat()].exposure == pytest.approx(1.0)
    assert points[next_day.isoformat()].source == "persisted:livermore_gate_history"


def test_drift_detected_on_normal_next_day_refresh_with_single_date_window(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Acceptance repro: a mature daily refresh only carries the newest date.

    The drift scan must still check the historical anchors (independent
    latest-N observation window), so revising yesterday's breadth after its
    realtime label was anchored produces a drift WARN on the very next normal
    daily call — not ``checked_persisted_dates=0``.
    """
    next_day = _T + timedelta(days=1)
    conn = duckdb.connect(":memory:")
    try:
        _seed_benchmark(conn, end=next_day, n_days=66)
        _seed_supplement(conn, [(_T.isoformat(), 14.0, True)])

        first = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-day-1",
            reference_date=_T,
        )
        assert first["status"] == "written"

        # Data revision after anchoring: replay at _T flips OVERHEAT -> HOT.
        conn.execute(
            "update fact_livermore_gate_supplement_daily set breadth_5d = -5.0 where trade_date = ?",
            [_T.isoformat()],
        )
        _seed_supplement(conn, [(next_day.isoformat(), 14.0, True)])

        with caplog.at_level("WARNING", logger="backend.app.tasks.livermore_gate_history_materialize"):
            second = persist_livermore_gate_history_for_run(
                conn,
                # Normal next-day call: the run window is only the newest date.
                supplement_dates=[next_day.isoformat()],
                run_id="run-day-2",
                reference_date=next_day,
            )
        rows = _gate_history_rows(conn)
    finally:
        conn.close()

    assert second["status"] == "written"
    assert second["checked_persisted_dates"] >= 1
    assert second["drift_status"] == "detected"
    assert second["drift_count"] == 1
    drift_entry = second["drift_dates"][0]
    assert drift_entry["trade_date"] == _T.isoformat()
    assert drift_entry["persisted_state"] == "OVERHEAT"
    assert drift_entry["replayed_state"] == "HOT"
    assert any("drift" in record.message for record in caplog.records)

    # The anchored label itself is never rewritten by the drift scan.
    assert [row[0] for row in rows] == [_T.isoformat(), next_day.isoformat()]
    assert rows[0][1:3] == ("OVERHEAT", 1.0)
    assert rows[0][10] == "run-day-1"


# ---------------------------------------------------------------------------
# write-eligibility boundaries: age window and future targets
# ---------------------------------------------------------------------------


def test_persist_age_boundary_exactly_three_days_allowed() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _seed_benchmark(conn, end=_T)
        _seed_supplement(conn, [(_T.isoformat(), 14.0, True)])
        result = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-age-3",
            reference_date=_T + timedelta(days=3),
        )
        count = conn.execute("select count(*) from livermore_gate_history").fetchone()[0]
    finally:
        conn.close()

    assert result["status"] == "written"
    assert int(count) == 1


def test_persist_age_boundary_four_days_skipped() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _seed_benchmark(conn, end=_T)
        _seed_supplement(conn, [(_T.isoformat(), 14.0, True)])
        result = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-age-4",
            reference_date=_T + timedelta(days=4),
        )
        count = conn.execute("select count(*) from livermore_gate_history").fetchone()[0]
    finally:
        conn.close()

    assert result["status"] == "skipped_historical_target"
    assert int(count) == 0


def test_persist_rejects_future_target() -> None:
    conn = duckdb.connect(":memory:")
    try:
        _seed_benchmark(conn, end=_T)
        _seed_supplement(conn, [(_T.isoformat(), 14.0, True)])
        result = persist_livermore_gate_history_for_run(
            conn,
            supplement_dates=[_T.isoformat()],
            run_id="run-future",
            # The run's reference date lies before the target: a negative age
            # must never be treated as a realtime label.
            reference_date=_T - timedelta(days=1),
        )
        count = conn.execute("select count(*) from livermore_gate_history").fetchone()[0]
    finally:
        conn.close()

    assert result["status"] == "skipped_future_target"
    assert int(count) == 0


# ---------------------------------------------------------------------------
# full write chain: supplement materialize persists the anchor
# ---------------------------------------------------------------------------


def test_supplement_materialize_chain_persists_gate_history(tmp_path: Path) -> None:
    today = date.today()
    db = tmp_path / "moss.duckdb"
    _seed_benchmark_into_migrated_db(db, end=today)

    supplement_rows = [
        {
            "trade_date": today,
            "breadth_5d": 14.0,
            "limit_up_quality_ok": True,
            "source_version": "sv_chain",
            "vendor_version": "vv_chain",
        }
    ]
    first = materialize_livermore_gate_supplement_daily(
        duckdb_path=str(db),
        rows=supplement_rows,
        run_id="run-chain-1",
    )
    second = materialize_livermore_gate_supplement_daily(
        duckdb_path=str(db),
        rows=supplement_rows,
        run_id="run-chain-2",
    )

    assert first["status"] == second["status"] == "completed"
    assert first["gate_history"]["status"] == "written"
    assert first["gate_history"]["write_consistency"] == "healthy"
    assert second["gate_history"]["status"] == "written"

    conn = duckdb.connect(str(db), read_only=True)
    try:
        rows = _gate_history_rows(conn)
        points = load_gate_exposure_by_date(conn, today, today)
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0][:3] == (today.isoformat(), "OVERHEAT", 1.0)
    assert rows[0][7] == "realtime"
    assert rows[0][8] == "vv_chain"
    assert rows[0][10] == "run-chain-2"
    assert points[today.isoformat()].source == "persisted:livermore_gate_history"


def test_supplement_materialize_chain_skips_historical_backfill(tmp_path: Path) -> None:
    """A historical supplement backfill must never fabricate past gate labels."""
    db = tmp_path / "moss.duckdb"
    _seed_benchmark_into_migrated_db(db, end=_T)

    result = materialize_livermore_gate_supplement_daily(
        duckdb_path=str(db),
        rows=[
            {
                "trade_date": _T,
                "breadth_5d": 14.0,
                "limit_up_quality_ok": True,
                "source_version": "sv_backfill",
                "vendor_version": "vv_backfill",
            }
        ],
        run_id="run-backfill",
    )

    assert result["status"] == "completed"
    assert result["gate_history"]["status"] == "skipped_historical_target"

    conn = duckdb.connect(str(db), read_only=True)
    try:
        supplement_count = conn.execute(
            "select count(*) from fact_livermore_gate_supplement_daily"
        ).fetchone()[0]
        gate_count = conn.execute("select count(*) from livermore_gate_history").fetchone()[0]
    finally:
        conn.close()

    # The supplement write itself is unaffected; only the label anchor skips.
    assert int(supplement_count) == 1
    assert int(gate_count) == 0


def test_supplement_materialize_chain_degrades_on_gate_history_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fault injection: an anchor write failure must never sink the supplement."""
    today = date.today()
    db = tmp_path / "moss.duckdb"
    _seed_benchmark_into_migrated_db(db, end=today)

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected gate-history write failure")

    monkeypatch.setattr(gate_history_task, "_replace_gate_row", _boom)

    result = materialize_livermore_gate_supplement_daily(
        duckdb_path=str(db),
        rows=[
            {
                "trade_date": today,
                "breadth_5d": 14.0,
                "limit_up_quality_ok": True,
                "source_version": "sv_fault",
                "vendor_version": "vv_fault",
            }
        ],
        run_id="run-fault",
    )

    assert result["status"] == "completed"
    assert result["gate_history"]["status"] == "failed"
    assert "injected gate-history write failure" in str(result["gate_history"]["error"])

    conn = duckdb.connect(str(db), read_only=True)
    try:
        supplement_count = conn.execute(
            "select count(*) from fact_livermore_gate_supplement_daily"
        ).fetchone()[0]
        gate_count = conn.execute("select count(*) from livermore_gate_history").fetchone()[0]
    finally:
        conn.close()

    assert int(supplement_count) == 1
    assert int(gate_count) == 0
