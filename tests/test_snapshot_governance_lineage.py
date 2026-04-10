"""snapshot_build_run and snapshot_manifest streams carry authoritative linkage tuples."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    SNAPSHOT_BUILD_RUN_STREAM,
    SNAPSHOT_MANIFEST_STREAM,
)
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


def test_snapshot_governance_records_include_linkage_tuple(tmp_path, monkeypatch):
    ingest_mod, snap_mod = _load_tasks()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    data_root.mkdir()
    for file_name in ("ZQTZSHOW-20251231.xls",):
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
        source_families=["zqtz"],
    )

    build_path = Path(governance_dir) / f"{SNAPSHOT_BUILD_RUN_STREAM}.jsonl"
    manifest_path = Path(governance_dir) / f"{SNAPSHOT_MANIFEST_STREAM}.jsonl"
    assert build_path.exists()
    assert manifest_path.exists()

    build_lines = [json.loads(line) for line in build_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(line.get("status") == "completed" for line in build_lines)

    manifest_lines = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert manifest_lines
    for line in manifest_lines:
        link = line.get("source_linkage") or {}
        for key in ("ingest_batch_id", "source_family", "source_file", "source_version", "archived_path"):
            assert key in link, f"missing {key} in {line}"
        assert set(link.keys()) == {
            "ingest_batch_id",
            "source_family",
            "source_file",
            "source_version",
            "archived_path",
        }
        assert "snapshot_run_id" in line
        assert line.get("target_table") == "zqtz_bond_daily_snapshot"
        assert line.get("schema_version")
        assert line.get("canonical_grain_version")
        assert line.get("produced_row_count", 0) >= 0

    get_settings.cache_clear()
