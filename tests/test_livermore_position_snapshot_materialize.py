from __future__ import annotations

import csv

import duckdb
import pytest
from backend.app.tasks import livermore_position_snapshot_materialize as materialize_module

from backend.app.repositories.duckdb_migrations import (
    apply_pending_migrations_on_connection,
)
from backend.app.tasks.livermore_position_snapshot_materialize import (
    _materialize_livermore_position_snapshot as materialize_livermore_position_snapshot,
)
from backend.app.services.market_data_livermore_service import livermore_data_version

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]



def test_livermore_data_version_changes_when_duckdb_file_changes(tmp_path):
    path = tmp_path / "snapshot.duckdb"
    path.write_bytes(b"v1")
    first = livermore_data_version(str(path))
    path.write_bytes(b"v2-expanded")
    second = livermore_data_version(str(path))
    assert first != second
    assert livermore_data_version(str(path)) == second


def test_apply_pending_migrations_creates_livermore_position_snapshot_v22(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        exists = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = 'main' and table_name = 'livermore_position_snapshot'
            limit 1
            """
        ).fetchone()
        assert exists is not None
        row = conn.execute(
            """
            select version, description
            from _schema_migrations
            where version = 22
            """
        ).fetchone()
        assert row is not None
        assert row[0] == 22
        assert "livermore" in row[1].lower()
    finally:
        conn.close()


def _write_position_csv(path, *, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "as_of_date",
        "stock_code",
        "stock_name",
        "entry_cost",
        "bars_since_entry",
        "entry_date",
        "position_quantity",
        "position_status",
        "source_system",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def test_materialize_livermore_position_snapshot_writes_filtered_rows(tmp_path) -> None:
    csv_path = tmp_path / "positions.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_position_csv(
        csv_path,
        rows=[
            {
                "as_of_date": "2026-04-29",
                "stock_code": "000001.SZ",
                "stock_name": "Alpha",
                "entry_cost": "10.5",
                "bars_since_entry": "6",
            },
            {
                "as_of_date": "2026-04-29",
                "stock_code": "000002.SZ",
                "stock_name": "Beta",
                "entry_cost": "8.2",
                "bars_since_entry": "3",
            },
            {
                "as_of_date": "2026-04-28",
                "stock_code": "000003.SZ",
                "stock_name": "Gamma",
                "entry_cost": "9.1",
                "bars_since_entry": "4",
            },
        ],
    )

    payload = materialize_livermore_position_snapshot(
        as_of_date="2026-04-29",
        csv_path=str(csv_path),
        duckdb_path=str(duckdb_path),
        run_id="livermore-test-run-001",
    )

    assert payload["status"] == "completed"
    assert payload["as_of_date"] == "2026-04-29"
    assert payload["row_count"] == 2
    assert payload["run_id"] == "livermore-test-run-001"
    assert str(payload["source_version"]).startswith("sv_livermore_position_")
    assert str(payload["vendor_version"]).startswith("vv_livermore_position_csv_")

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select as_of_date, stock_code, stock_name, entry_cost, bars_since_entry, run_id
            from livermore_position_snapshot
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("2026-04-29", "000001.SZ", "Alpha", 10.5, 6, "livermore-test-run-001"),
        ("2026-04-29", "000002.SZ", "Beta", 8.2, 3, "livermore-test-run-001"),
    ]


def test_materialize_livermore_position_snapshot_rolls_back_failed_insert(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "positions.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_position_csv(csv_path, rows=[{"as_of_date": "2026-04-29", "stock_code": "000001.SZ", "stock_name": "Old", "entry_cost": "10", "bars_since_entry": "2"}])
    materialize_livermore_position_snapshot(as_of_date="2026-04-29", csv_path=str(csv_path), duckdb_path=str(duckdb_path), run_id="old-run")
    _write_position_csv(csv_path, rows=[
        {"as_of_date": "2026-04-29", "stock_code": "000001.SZ", "stock_name": "New", "entry_cost": "11", "bars_since_entry": "3"},
        {"as_of_date": "2026-04-29", "stock_code": "000002.SZ", "stock_name": "Partial", "entry_cost": "12", "bars_since_entry": "4"},
    ])
    real_connect = materialize_module.duckdb.connect
    class FailingConnection:
        def __init__(self, conn): self._conn = conn
        def execute(self, *args, **kwargs): return self._conn.execute(*args, **kwargs)
        def executemany(self, *args, **kwargs): raise RuntimeError("injected executemany failure")
        def close(self): return self._conn.close()
    monkeypatch.setattr(materialize_module.duckdb, "connect", lambda *a, **k: FailingConnection(real_connect(*a, **k)))
    with pytest.raises(RuntimeError, match="injected executemany failure"):
        materialize_livermore_position_snapshot(as_of_date="2026-04-29", csv_path=str(csv_path), duckdb_path=str(duckdb_path), run_id="new-run")
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute("select stock_name, run_id from livermore_position_snapshot order by stock_code").fetchall()
    finally:
        conn.close()
    assert rows == [("Old", "old-run")]


def test_materialize_livermore_position_snapshot_actor_fn_propagates_run_id(tmp_path) -> None:
    csv_path = tmp_path / "positions.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_position_csv(csv_path, rows=[{"as_of_date": "2026-04-29", "stock_code": "000001.SZ", "stock_name": "Actor", "entry_cost": "10", "bars_since_entry": "2"}])
    payload = materialize_module.materialize_livermore_position_snapshot.fn(as_of_date="2026-04-29", csv_path=str(csv_path), duckdb_path=str(duckdb_path), run_id="actor-run")
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        db_run_id = conn.execute("select run_id from livermore_position_snapshot").fetchone()[0]
    finally:
        conn.close()
    assert payload["run_id"] == db_run_id == "actor-run"


def test_materialize_livermore_position_snapshot_is_idempotent_per_as_of_date(tmp_path) -> None:
    csv_path = tmp_path / "positions.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_position_csv(
        csv_path,
        rows=[
            {
                "as_of_date": "2026-04-29",
                "stock_code": "000001.SZ",
                "stock_name": "Alpha",
                "entry_cost": "10.5",
                "bars_since_entry": "6",
            }
        ],
    )

    materialize_livermore_position_snapshot(
        as_of_date="2026-04-29",
        csv_path=str(csv_path),
        duckdb_path=str(duckdb_path),
    )
    materialize_livermore_position_snapshot(
        as_of_date="2026-04-29",
        csv_path=str(csv_path),
        duckdb_path=str(duckdb_path),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row_count = conn.execute("select count(*) from livermore_position_snapshot").fetchone()[0]
    finally:
        conn.close()

    assert row_count == 1


def test_materialize_livermore_position_snapshot_records_stock_fact_lineage(tmp_path) -> None:
    csv_path = tmp_path / "positions.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_position_csv(
        csv_path,
        rows=[
            {
                "as_of_date": "2026-04-29",
                "stock_code": "000001.SZ",
                "stock_name": "Alpha",
                "entry_cost": "10.5",
                "bars_since_entry": "6",
                "entry_date": "2026-04-21",
                "position_quantity": "10000",
                "source_system": "livermore_manual_book",
            }
        ],
    )

    payload = materialize_livermore_position_snapshot(
        as_of_date="2026-04-29",
        csv_path=str(csv_path),
        duckdb_path=str(duckdb_path),
    )

    assert payload["fact_source"] == "livermore_position_snapshot"
    assert payload["source_systems"] == ["livermore_manual_book"]
    assert str(payload["source_file_hash"]).startswith("sha256:")

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select
              as_of_date, stock_code, stock_name, entry_cost, bars_since_entry,
              entry_date, position_quantity, position_status, source_system,
              source_file_hash, source_row_no
            from livermore_position_snapshot
            """
        ).fetchone()
    finally:
        conn.close()

    assert row[:9] == (
        "2026-04-29",
        "000001.SZ",
        "Alpha",
        10.5,
        6,
        "2026-04-21",
        10000.0,
        "ACTIVE",
        "livermore_manual_book",
    )
    assert str(row[9]).startswith("sha256:")
    assert row[10] == 2


def test_materialize_livermore_position_snapshot_derives_bars_since_entry_from_entry_date(
    tmp_path,
) -> None:
    csv_path = tmp_path / "positions.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_position_csv(
        csv_path,
        rows=[
            {
                "as_of_date": "2026-04-29",
                "stock_code": "000001.SZ",
                "stock_name": "Alpha",
                "entry_cost": "10.5",
                "entry_date": "2026-04-27",
            }
        ],
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              stock_code varchar,
              trade_date varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?)",
            [
                ("000001.SZ", "2026-04-27"),
                ("000001.SZ", "2026-04-28"),
                ("000001.SZ", "2026-04-29"),
            ],
        )
    finally:
        conn.close()

    materialize_livermore_position_snapshot(
        as_of_date="2026-04-29",
        csv_path=str(csv_path),
        duckdb_path=str(duckdb_path),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        bars_since_entry = conn.execute(
            "select bars_since_entry from livermore_position_snapshot"
        ).fetchone()[0]
    finally:
        conn.close()

    assert bars_since_entry == 3


def test_materialize_livermore_position_snapshot_rejects_non_a_share_stock_code(tmp_path) -> None:
    csv_path = tmp_path / "positions.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_position_csv(
        csv_path,
        rows=[
            {
                "as_of_date": "2026-04-29",
                "stock_code": "240001.IB",
                "stock_name": "BondLike",
                "entry_cost": "10.5",
                "bars_since_entry": "6",
            }
        ],
    )

    with pytest.raises(ValueError, match="A-share stock_code"):
        materialize_livermore_position_snapshot(
            as_of_date="2026-04-29",
            csv_path=str(csv_path),
            duckdb_path=str(duckdb_path),
        )


def test_materialize_livermore_position_snapshot_rejects_non_positive_entry_cost(
    tmp_path,
) -> None:
    csv_path = tmp_path / "positions.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_position_csv(
        csv_path,
        rows=[
            {
                "as_of_date": "2026-04-29",
                "stock_code": "000001.SZ",
                "stock_name": "Alpha",
                "entry_cost": "0",
                "bars_since_entry": "6",
            }
        ],
    )

    with pytest.raises(ValueError, match="entry_cost must be positive"):
        materialize_livermore_position_snapshot(
            as_of_date="2026-04-29",
            csv_path=str(csv_path),
            duckdb_path=str(duckdb_path),
        )


def test_materialize_livermore_position_snapshot_rejects_non_positive_bars_since_entry(
    tmp_path,
) -> None:
    csv_path = tmp_path / "positions.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_position_csv(
        csv_path,
        rows=[
            {
                "as_of_date": "2026-04-29",
                "stock_code": "000001.SZ",
                "stock_name": "Alpha",
                "entry_cost": "10.5",
                "bars_since_entry": "0",
            }
        ],
    )

    with pytest.raises(ValueError, match="bars_since_entry must be positive"):
        materialize_livermore_position_snapshot(
            as_of_date="2026-04-29",
            csv_path=str(csv_path),
            duckdb_path=str(duckdb_path),
        )


def test_materialize_livermore_position_snapshot_rejects_unknown_position_status(
    tmp_path,
) -> None:
    csv_path = tmp_path / "positions.csv"
    duckdb_path = tmp_path / "moss.duckdb"
    _write_position_csv(
        csv_path,
        rows=[
            {
                "as_of_date": "2026-04-29",
                "stock_code": "000001.SZ",
                "stock_name": "Alpha",
                "entry_cost": "10.5",
                "bars_since_entry": "6",
                "position_status": "ACTVE",
            }
        ],
    )

    with pytest.raises(ValueError, match="position_status must be one of"):
        materialize_livermore_position_snapshot(
            as_of_date="2026-04-29",
            csv_path=str(csv_path),
            duckdb_path=str(duckdb_path),
        )


def test_write_livermore_position_rows_holds_writer_lock_across_connect_and_close(
    tmp_path, monkeypatch
) -> None:
    """写连接 open→close 全程必须持有 resolve_duckdb_writer_lock（B5 审计修复）。"""
    from contextlib import contextmanager

    from backend.app.governance.locks import resolve_duckdb_writer_lock

    duckdb_path = tmp_path / "moss.duckdb"
    events: list[str] = []
    real_acquire_lock = materialize_module.acquire_lock
    real_connect = duckdb.connect

    @contextmanager
    def recording_acquire_lock(definition, *args, **kwargs):
        events.append(f"lock_enter:{definition.key}")
        with real_acquire_lock(definition, *args, **kwargs) as handle:
            try:
                yield handle
            finally:
                events.append(f"lock_exit:{definition.key}")

    class _RecordingConn:
        def __init__(self, inner) -> None:
            self._inner = inner

        def close(self) -> None:
            events.append("connection_closed")
            self._inner.close()

        def __getattr__(self, name: str):
            return getattr(self._inner, name)

    def recording_connect(*args, **kwargs):
        events.append("connection_opened")
        return _RecordingConn(real_connect(*args, **kwargs))

    monkeypatch.setattr(materialize_module, "acquire_lock", recording_acquire_lock)
    monkeypatch.setattr(materialize_module.duckdb, "connect", recording_connect)

    payload = materialize_module._materialize_livermore_position_snapshot_rows(
        as_of_date="2026-04-29",
        rows=[
            {
                "stock_code": "600000.SH",
                "stock_name": "Alpha",
                "entry_cost": "10.5",
                "bars_since_entry": "3",
            }
        ],
        duckdb_path=str(duckdb_path),
    )

    assert payload["status"] == "completed"
    writer_lock_key = resolve_duckdb_writer_lock(duckdb_path).key
    assert events == [
        f"lock_enter:{writer_lock_key}",
        "connection_opened",
        "connection_closed",
        f"lock_exit:{writer_lock_key}",
    ]

    conn = real_connect(str(duckdb_path), read_only=True)
    try:
        row_count = conn.execute("select count(*) from livermore_position_snapshot").fetchone()[0]
    finally:
        conn.close()
    assert int(row_count) == 1
