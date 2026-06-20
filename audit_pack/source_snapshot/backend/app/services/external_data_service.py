"""External-data catalog read surface for API (M1)."""

from __future__ import annotations

from backend.app.governance.settings import get_settings
from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.schemas.external_data import ExternalDataCatalogEntry


class ExternalDataService:
    """Thin wrapper over ``ExternalDataCatalogRepository``."""

    def __init__(self, catalog_repo: ExternalDataCatalogRepository) -> None:
        self._repo = catalog_repo

    def list_catalog(self) -> list[ExternalDataCatalogEntry]:
        return self._repo.list_all()

    def get_catalog_entry(self, series_id: str) -> ExternalDataCatalogEntry | None:
        return self._repo.get_by_series_id(series_id)

    def list_by_domain(self, domain: str) -> list[ExternalDataCatalogEntry]:
        return self._repo.list_by_domain(domain)


def default_service() -> ExternalDataService:
    settings = get_settings()
    repo = ExternalDataCatalogRepository(path=settings.duckdb_path)
    return ExternalDataService(repo)
