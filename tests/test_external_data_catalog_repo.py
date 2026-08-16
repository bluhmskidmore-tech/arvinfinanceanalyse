from __future__ import annotations

from pathlib import Path
from typing import Literal

import duckdb
import pytest

from backend.app.repositories import external_data_catalog_repo as catalog_repo_module
from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.schemas.external_data import ExternalDataCatalogEntry

DomainLit = Literal["macro", "news", "yield_curve", "fx", "other"]


def _sample_entry(*, series_id: str = "s1", domain: DomainLit = "macro") -> ExternalDataCatalogEntry:
    return ExternalDataCatalogEntry(
        series_id=series_id,
        series_name="Name",
        vendor_name="choice",
        source_family="edb",
        domain=domain,
        frequency="daily",
        unit="pct",
        refresh_tier="daily",
        fetch_mode="batch",
        raw_zone_path="data/raw/choice/{ingest_batch_id}/x.json",
        standardized_table="std_external_macro_daily",
        view_name="vw_external_macro_daily",
        access_path="select 1",
        catalog_version="v1",
        created_at="2026-04-21T12:00:00+00:00",
    )


def test_register_upserts_by_series_id() -> None:
    conn = duckdb.connect(":memory:")
    try:
        ensure_external_data_catalog_schema(conn)
        repo = ExternalDataCatalogRepository(conn=conn)
        e1 = _sample_entry(series_id="macro.a")
        e2 = e1.model_copy(update={"series_name": "Updated"})
        with repository_task_write_scope("backend.app.tasks.external_data_catalog_seed_test"):
            repo.register(e1)
            repo.register(e2)
        got = repo.get_by_series_id("macro.a")
        assert got is not None
        assert got.series_name == "Updated"
    finally:
        conn.close()


def test_list_all_and_get_and_by_domain() -> None:
    conn = duckdb.connect(":memory:")
    try:
        ensure_external_data_catalog_schema(conn)
        repo = ExternalDataCatalogRepository(conn=conn)
        with repository_task_write_scope("backend.app.tasks.external_data_catalog_seed_test"):
            repo.register(_sample_entry(series_id="m1", domain="macro"))
            repo.register(_sample_entry(series_id="n1", domain="news"))
        all_rows = repo.list_all()
        assert {r.series_id for r in all_rows} == {"m1", "n1"}
        assert repo.get_by_series_id("missing") is None
        macro_only = repo.list_by_domain("macro")
        assert [r.series_id for r in macro_only] == ["m1"]
    finally:
        conn.close()


def _seed_path_catalog(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        ensure_external_data_catalog_schema(conn)
        with repository_task_write_scope("backend.app.tasks.external_data_catalog_seed_test"):
            ExternalDataCatalogRepository(conn=conn).register(_sample_entry(series_id="path.series"))
    finally:
        conn.close()


def test_path_reads_open_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "catalog.duckdb"
    _seed_path_catalog(db_path)
    original_connect = duckdb.connect
    read_only_modes: list[bool] = []

    def _recording_connect(path: str, *, read_only: bool = False):
        read_only_modes.append(read_only)
        return original_connect(path, read_only=read_only)

    monkeypatch.setattr(catalog_repo_module.duckdb, "connect", _recording_connect)
    repo = ExternalDataCatalogRepository(path=str(db_path))

    assert [entry.series_id for entry in repo.list_all()] == ["path.series"]
    assert repo.get_by_series_id("path.series") is not None
    assert [entry.series_id for entry in repo.list_by_domain("macro")] == ["path.series"]
    assert read_only_modes == [True, True, True]


def test_absent_path_read_does_not_create_database(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.duckdb"
    repo = ExternalDataCatalogRepository(path=str(db_path))

    with pytest.raises(duckdb.Error):
        repo.list_all()

    assert not db_path.exists()


@pytest.mark.parametrize("path", ["", ":memory:"])
def test_memory_path_read_preserves_missing_table_behavior(path: str) -> None:
    repo = ExternalDataCatalogRepository(path=path)

    with pytest.raises(duckdb.CatalogException, match="external_data_catalog does not exist"):
        repo.list_all()


def test_path_registration_remains_writable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "catalog.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        ensure_external_data_catalog_schema(conn)
    finally:
        conn.close()

    original_connect = duckdb.connect
    read_only_modes: list[bool] = []

    def _recording_connect(path: str, *, read_only: bool = False):
        read_only_modes.append(read_only)
        return original_connect(path, read_only=read_only)

    monkeypatch.setattr(catalog_repo_module.duckdb, "connect", _recording_connect)
    repo = ExternalDataCatalogRepository(path=str(db_path))

    with repository_task_write_scope("backend.app.tasks.external_data_catalog_seed_test"):
        repo.register(_sample_entry(series_id="written.series"))
    persisted = repo.get_by_series_id("written.series")

    assert persisted is not None
    assert persisted.series_id == "written.series"
    assert read_only_modes == [False, True]
