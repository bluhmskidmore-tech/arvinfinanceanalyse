from __future__ import annotations

from dataclasses import fields, replace

import duckdb
import pytest

from backend.app.repositories.cffex_member_rank_repo import TABLE_NAME, CffexMemberRankRow
from backend.app.tasks import cffex_member_rank as task

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]


def _row(member_name: str = "Member A", **changes: object) -> CffexMemberRankRow:
    row = CffexMemberRankRow(
        trade_date="2026-09-04",
        contract="TS.CFE",
        product_code="TS",
        exchange="CFFEX",
        member_name=member_name,
        source_vendor="tushare",
        source_row_no=1,
        volume=100.0,
        volume_change=-10.0,
        long_holding=200.0,
        long_change=20.0,
        short_holding=300.0,
        short_change=-30.0,
        source_version="source-v1",
        vendor_version="vendor-v1",
        ingest_batch_id="batch-v1",
        raw_payload_json='{"revision": 1}',
    )
    return replace(row, **changes)


def _snapshot(db):
    with duckdb.connect(str(db), read_only=True) as conn:
        return conn.execute(
            f"select * from {TABLE_NAME} order by trade_date, contract, source_vendor, member_name"
        ).fetchall()


def test_persist_repeats_same_keys_after_closing_disk_connection(tmp_path):
    db = tmp_path / "cffex.duckdb"
    row = _row()
    assert task.persist_cffex_member_rank_rows(duckdb_path=db, rows=[row]) == 1
    before = _snapshot(db)

    # Each persist call creates and closes its own connection. An in-memory,
    # same-connection test does not reproduce the DuckDB delete/reinsert failure.
    assert task.persist_cffex_member_rank_rows(duckdb_path=db, rows=[row]) == 1
    after = _snapshot(db)
    assert len(after) == 1
    assert after[0][:-1] == before[0][:-1]
    assert after[0][-1] >= before[0][-1]


def test_persist_replaces_all_metrics_and_lineage_adds_and_removes_members(tmp_path):
    db = tmp_path / "cffex.duckdb"
    unrelated = [
        _row("Other date", trade_date="2026-09-03"),
        _row("Other contract", contract="TF.CFE", product_code="TF"),
        _row("Other source", source_vendor="choice"),
    ]
    task.persist_cffex_member_rank_rows(
        duckdb_path=db, rows=[_row(), _row("Departed member"), *unrelated]
    )
    before = _snapshot(db)
    revised = _row(
        source_row_no=9,
        volume=101.0,
        volume_change=None,
        long_holding=202.0,
        long_change=-22.0,
        short_holding=303.0,
        short_change=0.0,
        source_version="source-v2",
        vendor_version="vendor-v2",
        rule_version="rule-v2",
        ingest_batch_id="batch-v2",
        raw_payload_json='{"revision": 2}',
    )
    added = _row("New member", source_row_no=10)
    assert task.persist_cffex_member_rank_rows(duckdb_path=db, rows=[revised, added]) == 2

    after = _snapshot(db)
    expected = [tuple(getattr(row, field.name) for field in fields(row)) for row in [revised, added]]
    affected = [row for row in after if row[0] == "2026-09-04" and row[1] == "TS.CFE" and row[5] == "tushare"]
    assert [row[:-1] for row in affected] == expected
    assert [row for row in after if row[4].startswith("Other")] == [
        row for row in before if row[4].startswith("Other")
    ]


def test_empty_input_preserves_all_partitions_and_does_not_create_database(tmp_path):
    missing = tmp_path / "missing.duckdb"
    assert task.persist_cffex_member_rank_rows(duckdb_path=missing, rows=[]) == 0
    assert not missing.exists()
    db = tmp_path / "cffex.duckdb"
    task.persist_cffex_member_rank_rows(duckdb_path=db, rows=[_row(), _row(contract="T.CFE")])
    before = _snapshot(db)
    assert task.persist_cffex_member_rank_rows(duckdb_path=db, rows=[]) == 0
    assert _snapshot(db) == before


@pytest.mark.parametrize("conflicting", [False, True])
def test_duplicate_input_fails_closed_without_changing_any_partition(tmp_path, conflicting):
    db = tmp_path / "cffex.duckdb"
    task.persist_cffex_member_rank_rows(duckdb_path=db, rows=[_row(), _row("Old member")])
    before = _snapshot(db)
    revised = _row(volume=999.0)
    duplicate = replace(revised, short_holding=444.0) if conflicting else revised
    with pytest.raises(duckdb.ConstraintException, match="Duplicate CFFEX member-rank input key"):
        task.persist_cffex_member_rank_rows(
            duckdb_path=db, rows=[revised, _row("Other partition", contract="TF.CFE"), duplicate]
        )
    assert _snapshot(db) == before


@pytest.mark.parametrize("fail_after", ["upsert", "delete"])
def test_database_failure_after_mutation_rolls_back_entire_snapshot(tmp_path, monkeypatch, fail_after):
    db = tmp_path / "cffex.duckdb"
    task.persist_cffex_member_rank_rows(
        duckdb_path=db, rows=[_row(), _row("Departed member"), _row("Other partition", contract="TF.CFE")]
    )
    before = _snapshot(db)
    real_connect = duckdb.connect
    mutations_seen = []

    class FailingConnection:
        def __init__(self, conn):
            self.conn = conn

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def execute(self, sql, *args):
            result = self.conn.execute(sql, *args)
            is_upsert = "on conflict" in sql.lower()
            is_delete = f"delete from {TABLE_NAME}" in sql.lower()
            if (fail_after == "upsert" and is_upsert) or (fail_after == "delete" and is_delete):
                # Verify real writes occurred, then provoke an actual database
                # constraint failure before commit, rather than mocking a raise.
                mutations_seen.append(self.conn.execute(
                    f"select member_name, volume from {TABLE_NAME} where contract = 'TS.CFE' order by member_name"
                ).fetchall())
                self.conn.execute(f"insert into {TABLE_NAME} (trade_date) values ('2026-09-04')")
            return result

    with monkeypatch.context() as patch:
        patch.setattr(task.duckdb, "connect", lambda *args, **kwargs: FailingConnection(real_connect(*args, **kwargs)))
        with pytest.raises(duckdb.ConstraintException):
            task.persist_cffex_member_rank_rows(
                duckdb_path=db, rows=[_row(volume=999.0), _row("New member")]
            )

    expected = [("Member A", 999.0), ("New member", 100.0)]
    if fail_after == "upsert":
        expected.insert(0, ("Departed member", 100.0))
    assert mutations_seen == [expected]
    assert _snapshot(db) == before
