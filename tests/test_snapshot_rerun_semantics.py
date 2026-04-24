"""Rerun replaces rows for the same ingest_batch_id scope without duplicate grains."""

from __future__ import annotations

import sys

import duckdb

from backend.app.governance.settings import get_settings
from tests.helpers import ROOT, load_module


def _load_tasks():
    ingest_mod = sys.modules.get("backend.app.tasks.ingest")
    if ingest_mod is None:
        ingest_mod = load_module("backend.app.tasks.ingest", "backend/app/tasks/ingest.py")
    snap_mod = sys.modules.get("backend.app.tasks.snapshot_materialize")
    if snap_mod is None:
        snap_mod = load_module(
            "backend.app.tasks.snapshot_materialize",
            "backend/app/tasks/snapshot_materialize.py",
        )
    return ingest_mod, snap_mod


def test_zqtz_rerun_same_batch_no_duplicate_grains(tmp_path, monkeypatch):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    data_root.mkdir()
    for file_name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_mod.ingest_demo_manifest.fn()
    first = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    batch_id = first["ingest_batch_ids"][0]

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        n1 = conn.execute(
            """
            select count(*) from (
              select report_date, instrument_code, portfolio_name, cost_center, currency_code, count(*) c
              from zqtz_bond_daily_snapshot
              where ingest_batch_id = ?
              group by 1,2,3,4,5
              having c > 1
            )
            """,
            [batch_id],
        ).fetchone()[0]
        assert n1 == 0
        total1 = conn.execute(
            "select count(*) from zqtz_bond_daily_snapshot where ingest_batch_id = ?",
            [batch_id],
        ).fetchone()[0]
    finally:
        conn.close()

    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=batch_id,
        source_families=["zqtz"],
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        n2 = conn.execute(
            """
            select count(*) from (
              select report_date, instrument_code, portfolio_name, cost_center, currency_code, count(*) c
              from zqtz_bond_daily_snapshot
              where ingest_batch_id = ?
              group by 1,2,3,4,5
              having c > 1
            )
            """,
            [batch_id],
        ).fetchone()[0]
        assert n2 == 0
        total2 = conn.execute(
            "select count(*) from zqtz_bond_daily_snapshot where ingest_batch_id = ?",
            [batch_id],
        ).fetchone()[0]
        assert total2 == total1
    finally:
        conn.close()

    get_settings.cache_clear()


def test_mixed_family_scope_zqtz_rerun_leaves_tyw_intact(tmp_path, monkeypatch):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    data_root.mkdir()
    for file_name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_mod.ingest_demo_manifest.fn()
    full = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    batch_id = full["ingest_batch_ids"][0]

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        tyw_before = conn.execute(
            "select count(*) from tyw_interbank_daily_snapshot where ingest_batch_id = ?",
            [batch_id],
        ).fetchone()[0]
    finally:
        conn.close()
    assert tyw_before > 0

    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=batch_id,
        source_families=["zqtz"],
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        tyw_after = conn.execute(
            "select count(*) from tyw_interbank_daily_snapshot where ingest_batch_id = ?",
            [batch_id],
        ).fetchone()[0]
    finally:
        conn.close()

    assert tyw_after == tyw_before
    get_settings.cache_clear()
