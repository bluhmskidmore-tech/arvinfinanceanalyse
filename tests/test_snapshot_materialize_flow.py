"""End-to-end: ingest + archive manifests, then materialize standardized snapshots from archives."""

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


def test_snapshot_tables_materialize_from_manifest_archives(tmp_path, monkeypatch):
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
    result = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert result["status"] == "completed"
    assert result["zqtz_rows"] > 0
    assert result["tyw_rows"] > 0

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        zcols = [r[1] for r in conn.execute("pragma table_info('zqtz_bond_daily_snapshot')").fetchall()]
        assert "source_version" in zcols
        assert "rule_version" in zcols
        assert "ingest_batch_id" in zcols
        assert "trace_id" in zcols

        tcols = [r[1] for r in conn.execute("pragma table_info('tyw_interbank_daily_snapshot')").fetchall()]
        assert "source_version" in tcols
        assert "rule_version" in tcols
        assert "ingest_batch_id" in tcols
        assert "trace_id" in tcols

        zrow = conn.execute(
            """
            select report_date, instrument_code, portfolio_name, cost_center, currency_code,
                   source_version, rule_version, ingest_batch_id, trace_id
            from zqtz_bond_daily_snapshot
            limit 1
            """
        ).fetchone()
        assert zrow is not None
        assert all(zrow)

        trow = conn.execute(
            """
            select report_date, position_id, source_version, rule_version, ingest_batch_id, trace_id
            from tyw_interbank_daily_snapshot
            limit 1
            """
        ).fetchone()
        assert trow is not None
        assert all(trow)
    finally:
        conn.close()

    get_settings.cache_clear()


def test_snapshot_materialize_respects_report_date_filter(tmp_path, monkeypatch):
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
    assert full["zqtz_rows"] > 0

    filtered = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
    )
    assert filtered["zqtz_rows"] == full["zqtz_rows"]

    empty_scope = snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2099-01-01",
    )
    assert empty_scope["zqtz_rows"] == 0
    assert empty_scope["tyw_rows"] == 0

    get_settings.cache_clear()


def test_snapshot_materialize_normalizes_currency_labels_to_iso_codes(tmp_path, monkeypatch):
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
    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        zqtz_codes = {
            row[0]
            for row in conn.execute("select distinct currency_code from zqtz_bond_daily_snapshot").fetchall()
        }
        tyw_codes = {
            row[0]
            for row in conn.execute("select distinct currency_code from tyw_interbank_daily_snapshot").fetchall()
        }
    finally:
        conn.close()

    assert "人民币" not in zqtz_codes
    assert "美元" not in zqtz_codes
    assert "人民币" not in tyw_codes
    assert "美元" not in tyw_codes

    get_settings.cache_clear()


def test_snapshot_materialize_keeps_prior_report_dates_within_same_ingest_batch(tmp_path, monkeypatch):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    data_root.mkdir()
    for file_name in (
        "ZQTZSHOW-20251231.xls",
        "TYWLSHOW-20251231.xls",
        "ZQTZSHOW-20260101.xls",
        "TYWLSHOW-20260101.xls",
    ):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    ingest_payload = ingest_mod.ingest_demo_manifest.fn()
    ingest_batch_id = ingest_payload["ingest_batch_id"]

    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=ingest_batch_id,
        source_families=["zqtz", "tyw"],
        report_date="2025-12-31",
    )
    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=ingest_batch_id,
        source_families=["zqtz", "tyw"],
        report_date="2026-01-01",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        zqtz_dates = [row[0].isoformat() for row in conn.execute(
            "select distinct report_date from zqtz_bond_daily_snapshot order by report_date"
        ).fetchall()]
        tyw_dates = [row[0].isoformat() for row in conn.execute(
            "select distinct report_date from tyw_interbank_daily_snapshot order by report_date"
        ).fetchall()]
    finally:
        conn.close()

    assert zqtz_dates == ["2025-12-31", "2026-01-01"]
    assert tyw_dates == ["2025-12-31", "2026-01-01"]

    get_settings.cache_clear()


def test_snapshot_materialize_explicit_ingest_batch_replaces_whole_report_date_slice(tmp_path, monkeypatch):
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

    first = ingest_mod.ingest_demo_manifest.fn()
    first_batch_id = first["ingest_batch_id"]
    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=first_batch_id,
        source_families=["zqtz", "tyw"],
        report_date="2025-12-31",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            "update zqtz_bond_daily_snapshot set ingest_batch_id = 'ib-old' where report_date = date '2025-12-31'"
        )
        conn.execute(
            "update tyw_interbank_daily_snapshot set ingest_batch_id = 'ib-old' where report_date = date '2025-12-31'"
        )
    finally:
        conn.close()

    snap_mod.materialize_standard_snapshots.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        ingest_batch_id=first_batch_id,
        source_families=["zqtz", "tyw"],
        report_date="2025-12-31",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        z_batches = {
            row[0]
            for row in conn.execute(
                "select distinct ingest_batch_id from zqtz_bond_daily_snapshot where report_date = date '2025-12-31'"
            ).fetchall()
        }
        t_batches = {
            row[0]
            for row in conn.execute(
                "select distinct ingest_batch_id from tyw_interbank_daily_snapshot where report_date = date '2025-12-31'"
            ).fetchall()
        }
    finally:
        conn.close()

    assert z_batches == {first_batch_id}
    assert t_batches == {first_batch_id}

    get_settings.cache_clear()
