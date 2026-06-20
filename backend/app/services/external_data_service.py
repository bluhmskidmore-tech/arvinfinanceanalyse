"""External-data catalog read surface for API (M1)."""

from __future__ import annotations

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.services.external_data_query_service import (
    SeriesDataPage,
    fetch_series_data_page,
    fetch_series_data_recent,
)


class ExternalDataService:
    """Thin wrapper over ``ExternalDataCatalogRepository``."""

    def __init__(
        self,
        catalog_repo: ExternalDataCatalogRepository,
        *,
        duckdb_path: str | None = None,
    ) -> None:
        self._repo = catalog_repo
        self._duckdb_path = duckdb_path

    def list_catalog(self) -> list[ExternalDataCatalogEntry]:
        return self._repo.list_all()

    def get_catalog_entry(self, series_id: str) -> ExternalDataCatalogEntry | None:
        return self._repo.get_by_series_id(series_id)

    def list_by_domain(self, domain: str) -> list[ExternalDataCatalogEntry]:
        return self._repo.list_by_domain(domain)

    def get_series_data_page(
        self,
        series_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> SeriesDataPage | None:
        return self._fetch_series_page(series_id, recent_days=None, limit=limit, offset=offset)

    def get_series_data_recent(
        self,
        series_id: str,
        *,
        days: int = 30,
        limit: int = 10_000,
    ) -> SeriesDataPage | None:
        return self._fetch_series_page(series_id, recent_days=days, limit=limit, offset=0)

    def _fetch_series_page(
        self,
        series_id: str,
        *,
        recent_days: int | None,
        limit: int,
        offset: int,
    ) -> SeriesDataPage | None:
        entry = self.get_catalog_entry(series_id.strip())
        if entry is None:
            return None
        if self._duckdb_path is None:
            msg = "duckdb_path is required for external data series reads"
            raise RuntimeError(msg)

        conn = duckdb.connect(self._duckdb_path, read_only=True)
        try:
            if recent_days is None:
                return fetch_series_data_page(conn, entry, limit=limit, offset=offset)
            return fetch_series_data_recent(conn, entry, days=recent_days, limit=limit)
        finally:
            conn.close()


def default_service() -> ExternalDataService:
    settings = get_settings()
    repo = ExternalDataCatalogRepository(path=settings.duckdb_path)
    return ExternalDataService(repo, duckdb_path=str(settings.duckdb_path))
