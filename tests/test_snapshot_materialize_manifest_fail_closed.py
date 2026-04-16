"""Fail-closed: manifest-selected archives must produce non-zero standardized snapshot rows."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from tests.helpers import load_module


def test_snapshot_materialize_fails_closed_when_zqtz_manifest_yields_zero_rows(tmp_path, monkeypatch):
    snap_mod = load_module(
        "backend.app.tasks.snapshot_materialize",
        "backend/app/tasks/snapshot_materialize.py",
    )
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir(parents=True, exist_ok=True)
    dummy_archive = tmp_path / "archive" / "ZQTZSHOW-20251231.xls"
    dummy_archive.parent.mkdir(parents=True, exist_ok=True)
    dummy_archive.write_bytes(b"dummy")

    def fake_select(self, **kwargs):
        return [
            {
                "source_family": "zqtz",
                "ingest_batch_id": "ib-zero",
                "report_date": "2025-12-31",
                "archived_path": str(dummy_archive),
                "source_version": "sv-zero",
                "source_file": "ZQTZSHOW-20251231.xls",
            }
        ]

    monkeypatch.setattr(
        snap_mod.SourceManifestRepository,
        "select_for_snapshot_materialization",
        fake_select,
    )
    monkeypatch.setattr(
        snap_mod,
        "parse_zqtz_snapshot_rows_from_bytes",
        lambda **kwargs: [],
    )

    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))

    from backend.app.governance.settings import get_settings

    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Fail closed: zqtz manifest"):
        snap_mod.materialize_standard_snapshots.fn(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            source_families=["zqtz"],
            report_date="2025-12-31",
            ingest_batch_id="ib-zero",
        )

    get_settings.cache_clear()


def test_formal_zqtz_balance_metrics_repo_queries_formal_fact_only():
    repo_mod = load_module(
        "backend.app.repositories.formal_zqtz_balance_metrics_repo",
        "backend/app/repositories/formal_zqtz_balance_metrics_repo.py",
    )
    src = inspect.getsource(repo_mod.FormalZqtzBalanceMetricsRepository)
    assert "fact_formal_zqtz_balance_daily" in src
    assert "zqtz_bond_daily_snapshot" not in src
