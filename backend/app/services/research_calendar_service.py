from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.app.repositories.research_calendar_repo import (
    SUPPLY_AUCTION_SERIES_ID,
    SUPPLY_AUCTION_VIEW,
    ResearchCalendarPage,
    ResearchCalendarRepository,
)
from backend.app.schemas.research_calendar import ResearchCalendarResult
from backend.app.services.formal_result_runtime import QualityFlag, build_result_envelope

CACHE_VERSION = "cv_supply_auction_v1"
DEFAULT_RULE_VERSION = "rv_supply_auction_v1"


def supply_auction_calendar_envelope(
    duckdb_path: str,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    duckdb_file = Path(duckdb_path)
    if duckdb_file.exists():
        page = ResearchCalendarRepository(path=str(duckdb_file)).fetch_supply_auction_page(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
    else:
        page = ResearchCalendarPage(
            events=[],
            total_rows=0,
            limit=max(1, min(limit, 500)),
            offset=max(0, offset),
            table_name=SUPPLY_AUCTION_VIEW,
            source_version="sv_supply_auction_empty",
            vendor_version="vv_none",
            rule_version=DEFAULT_RULE_VERSION,
        )

    payload = ResearchCalendarResult(
        series_id=SUPPLY_AUCTION_SERIES_ID,
        total_rows=page.total_rows,
        limit=page.limit,
        offset=page.offset,
        events=page.events,
    ).model_dump(mode="json")
    quality_flag: QualityFlag = "ok" if page.total_rows > 0 else "warning"
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_supply_auction_calendar",
        result_kind="calendar.supply_auctions",
        cache_version=CACHE_VERSION,
        source_version=page.source_version,
        rule_version=page.rule_version or DEFAULT_RULE_VERSION,
        vendor_version=page.vendor_version,
        quality_flag=quality_flag,
        filters_applied={
            "start_date": None if start_date is None else start_date.isoformat(),
            "end_date": None if end_date is None else end_date.isoformat(),
            "limit": page.limit,
            "offset": page.offset,
        },
        tables_used=[page.table_name],
        evidence_rows=page.total_rows,
        result_payload=payload,
    )
