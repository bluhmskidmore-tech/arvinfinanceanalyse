from __future__ import annotations

from typing import Literal

import duckdb

from backend.app.repositories.external_data_catalog_repo import (
    ExternalDataCatalogRepository,
    ensure_external_data_catalog_schema,
)
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
        repo.register(e1)
        e2 = e1.model_copy(update={"series_name": "Updated"})
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
        repo.register(_sample_entry(series_id="m1", domain="macro"))
        repo.register(_sample_entry(series_id="n1", domain="news"))
        all_rows = repo.list_all()
        assert {r.series_id for r in all_rows} == {"m1", "n1"}
        assert repo.get_by_series_id("missing") is None
        macro_only = repo.list_by_domain("macro")
        assert [r.series_id for r in macro_only] == ["m1"]
    finally:
        conn.close()
