"""External-data catalog read surface for API (M1)."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.app.governance.settings import get_settings
from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.schemas.external_data import (
    ExternalDataCatalogEntry,
    ExternalDataWatermarkEntry,
    ExternalDataWatermarkLedger,
    ExternalDataWatermarkSummary,
)
from backend.app.services.external_data_query_service import (
    SeriesDataPage,
    SeriesWatermark,
)


def _max_loaded_at_text(values: list[str]) -> str | None:
    """Latest ``latest_loaded_at`` across series (derived last-successful-ingest marker).

    Values are DuckDB varchar timestamps whose separators can differ per relation
    ("2026-04-21 08:00:00" vs "2026-04-21T08:00:00+00:00"), so compare parsed
    datetimes (normalized to naive UTC) and only fall back to lexicographic max
    for values ``fromisoformat`` cannot read.
    """
    best_key: datetime | None = None
    best_raw: str | None = None
    unparsed: list[str] = []
    for raw in values:
        try:
            parsed = datetime.fromisoformat(str(raw).strip())
        except ValueError:
            unparsed.append(raw)
            continue
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(UTC).replace(tzinfo=None)
        if best_key is None or parsed > best_key:
            best_key = parsed
            best_raw = raw
    if best_raw is not None:
        return best_raw
    return max(unparsed) if unparsed else None


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

    def get_watermark_ledger(self) -> ExternalDataWatermarkLedger:
        self._require_series_read_capability()
        entries = self.list_catalog()
        results = self._repo.fetch_series_watermarks(entries)
        watermark_entries = [
            self._watermark_entry_from_result(entry, result)
            for entry, result in zip(entries, results, strict=True)
        ]
        return ExternalDataWatermarkLedger(
            summary=self._summarize_watermarks(watermark_entries),
            entries=watermark_entries,
        )

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
        self._require_series_read_capability()
        if recent_days is None:
            return self._repo.fetch_series_data_page(entry, limit=limit, offset=offset)
        return self._repo.fetch_series_data_recent(entry, days=recent_days, limit=limit)

    def _require_series_read_capability(self) -> None:
        # Series reads go through the catalog repo (path= or conn=). Keep the
        # historical duckdb_path guard for callers that construct the service
        # without a usable repository handle.
        if getattr(self._repo, "_path", None) is not None:
            return
        if getattr(self._repo, "_conn", None) is not None:
            return
        if self._duckdb_path is None:
            msg = "duckdb_path is required for external data series reads"
            raise RuntimeError(msg)
        msg = "catalog repository path= or conn= is required for external data series reads"
        raise RuntimeError(msg)

    def _watermark_entry_from_result(
        self,
        entry: ExternalDataCatalogEntry,
        result: object,
    ) -> ExternalDataWatermarkEntry:
        if isinstance(result, Exception):
            return self._watermark_entry(entry, error_message=str(result))
        if isinstance(result, SeriesWatermark):
            return self._watermark_entry(entry, watermark=result)
        return self._watermark_entry(entry, error_message=f"unexpected watermark result: {type(result)!r}")

    @staticmethod
    def _watermark_entry(
        entry: ExternalDataCatalogEntry,
        *,
        watermark: SeriesWatermark | None = None,
        error_message: str | None = None,
    ) -> ExternalDataWatermarkEntry:
        if error_message is not None:
            data_status = "unavailable"
        elif watermark is not None and watermark.row_count > 0 and watermark.latest_business_date:
            data_status = "available"
        else:
            data_status = "no_data"

        return ExternalDataWatermarkEntry(
            series_id=entry.series_id,
            series_name=entry.series_name,
            vendor_name=entry.vendor_name,
            source_family=entry.source_family,
            domain=entry.domain,
            frequency=entry.frequency,
            unit=entry.unit,
            refresh_tier=entry.refresh_tier,
            fetch_mode=entry.fetch_mode,
            relation_name=None if watermark is None else watermark.relation_name,
            date_column=None if watermark is None else watermark.date_column,
            row_count=0 if watermark is None else watermark.row_count,
            latest_business_date=None if watermark is None else watermark.latest_business_date,
            latest_loaded_at=None if watermark is None else watermark.latest_loaded_at,
            age_days=None if watermark is None else watermark.age_days,
            freshness_tier="unknown" if watermark is None else watermark.freshness_tier,
            data_status=data_status,
            error_message=error_message,
        )

    @staticmethod
    def _summarize_watermarks(
        entries: list[ExternalDataWatermarkEntry],
    ) -> ExternalDataWatermarkSummary:
        available_dates = [
            entry.latest_business_date
            for entry in entries
            if entry.data_status == "available" and entry.latest_business_date is not None
        ]
        return ExternalDataWatermarkSummary(
            catalog_count=len(entries),
            available_count=sum(1 for entry in entries if entry.data_status == "available"),
            no_data_count=sum(1 for entry in entries if entry.data_status == "no_data"),
            unavailable_count=sum(1 for entry in entries if entry.data_status == "unavailable"),
            oldest_available_business_date=min(available_dates) if available_dates else None,
            newest_available_business_date=max(available_dates) if available_dates else None,
            last_successful_ingest=_max_loaded_at_text(
                [entry.latest_loaded_at for entry in entries if entry.latest_loaded_at]
            ),
        )


def default_service() -> ExternalDataService:
    settings = get_settings()
    repo = ExternalDataCatalogRepository(path=settings.duckdb_path)
    return ExternalDataService(repo, duckdb_path=str(settings.duckdb_path))
