from __future__ import annotations

from unittest.mock import MagicMock

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.services.external_data_service import ExternalDataService


def _entry(sid: str) -> ExternalDataCatalogEntry:
    return ExternalDataCatalogEntry(
        series_id=sid,
        series_name="n",
        vendor_name="v",
        source_family="sf",
        domain="macro",
        catalog_version="cv",
        created_at="2026-04-21T00:00:00+00:00",
    )


def test_service_delegates_list_get_by_domain() -> None:
    mock_repo = MagicMock(spec=ExternalDataCatalogRepository)
    mock_repo.list_all.return_value = [_entry("a")]
    mock_repo.get_by_series_id.return_value = _entry("a")
    mock_repo.list_by_domain.return_value = [_entry("a")]

    svc = ExternalDataService(mock_repo)
    assert svc.list_catalog() == [_entry("a")]
    assert svc.get_catalog_entry("a") == _entry("a")
    assert svc.list_by_domain("macro") == [_entry("a")]

    mock_repo.list_all.assert_called_once()
    mock_repo.get_by_series_id.assert_called_once_with("a")
    mock_repo.list_by_domain.assert_called_once_with("macro")
