from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, cast

import duckdb
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.schemas.research_calendar import (
    ResearchCalendarEvent,
    ResearchCalendarEventKind,
    ResearchCalendarSeverity,
    ResearchCalendarStatus,
)

SUPPLY_AUCTION_SERIES_ID = "research.calendar.supply_auction"
SUPPLY_AUCTION_STD_TABLE = "std_external_supply_auction_calendar"
SUPPLY_AUCTION_VIEW = "vw_external_supply_auction_calendar"


def ensure_supply_auction_calendar_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "17_external_supply_auction_calendar.sql").read_text(
        encoding="utf-8"
    )
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


@dataclass(frozen=True)
class ResearchCalendarPage:
    events: list[ResearchCalendarEvent]
    total_rows: int
    limit: int
    offset: int
    table_name: str
    source_version: str
    vendor_version: str
    rule_version: str


class ResearchCalendarRepository:
    def __init__(
        self,
        *,
        path: str | None = None,
        conn: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        if (path is None) == (conn is None):
            msg = "Exactly one of path= or conn= must be provided."
            raise ValueError(msg)
        self._path = path
        self._conn = conn

    @contextmanager
    def _connection(self):
        if self._conn is not None:
            yield self._conn
            return
        c = duckdb.connect(self._path or ":memory:", read_only=True)
        try:
            yield c
        finally:
            c.close()

    @staticmethod
    def _relation_exists(conn: duckdb.DuckDBPyConnection, relation: str) -> bool:
        row = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_schema = 'main' and table_name = ?
            limit 1
            """,
            [relation],
        ).fetchone()
        return row is not None

    @staticmethod
    def _where_clause(
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[str, list[object]]:
        filters = ["series_id = ?"]
        params: list[object] = [SUPPLY_AUCTION_SERIES_ID]
        if start_date is not None:
            filters.append("try_cast(event_date as date) >= ?")
            params.append(start_date.isoformat())
        if end_date is not None:
            filters.append("try_cast(event_date as date) <= ?")
            params.append(end_date.isoformat())
        return "where " + " and ".join(filters), params

    @staticmethod
    def _row_to_event(row: tuple[object, ...]) -> ResearchCalendarEvent:
        (
            event_id,
            series_id,
            event_date,
            event_kind,
            title,
            source_family,
            severity,
            issuer,
            market,
            instrument_type,
            term_label,
            amount_numeric,
            amount_unit,
            currency,
            status,
            headline_text,
            headline_url,
            headline_published_at,
        ) = row
        return ResearchCalendarEvent(
            event_id=str(event_id),
            series_id=str(series_id),
            event_date=_coerce_event_date(event_date),
            event_kind=_coerce_event_kind(event_kind),
            title=str(title),
            source_family=str(source_family),
            severity=_coerce_severity(severity),
            issuer=None if issuer is None else str(issuer),
            market=None if market is None else str(market),
            instrument_type=None if instrument_type is None else str(instrument_type),
            term_label=None if term_label is None else str(term_label),
            amount=None if amount_numeric is None else float(cast(Any, amount_numeric)),
            amount_unit=None if amount_unit is None else str(amount_unit),
            currency=None if currency is None else str(currency),
            status=_coerce_status(status),
            headline_text=None if headline_text is None else str(headline_text),
            headline_url=None if headline_url is None else str(headline_url),
            headline_published_at=_coerce_published_at(headline_published_at),
        )

    def fetch_supply_auction_page(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
        limit: int,
        offset: int,
    ) -> ResearchCalendarPage:
        lim = max(1, min(limit, 500))
        off = max(0, offset)
        with self._connection() as conn:
            if not self._relation_exists(conn, SUPPLY_AUCTION_VIEW):
                return ResearchCalendarPage(
                    events=[],
                    total_rows=0,
                    limit=lim,
                    offset=off,
                    table_name=SUPPLY_AUCTION_VIEW,
                    source_version="sv_supply_auction_empty",
                    vendor_version="vv_none",
                    rule_version="rv_supply_auction_v1",
                )

            where_sql, where_params = self._where_clause(
                start_date=start_date,
                end_date=end_date,
            )
            total_row = conn.execute(
                f"select count(*) from {SUPPLY_AUCTION_VIEW} {where_sql}",
                where_params,
            ).fetchone()
            total_rows = int(total_row[0]) if total_row is not None else 0
            version_row = conn.execute(
                f"""
                select
                  coalesce(max(source_version), 'sv_supply_auction_empty'),
                  coalesce(max(vendor_version), 'vv_none'),
                  coalesce(max(rule_version), 'rv_supply_auction_v1')
                from {SUPPLY_AUCTION_VIEW}
                {where_sql}
                """,
                where_params,
            ).fetchone()
            rows = conn.execute(
                f"""
                select
                  event_id,
                  series_id,
                  event_date,
                  event_kind,
                  title,
                  source_family,
                  severity,
                  issuer,
                  market,
                  instrument_type,
                  term_label,
                  amount_numeric,
                  amount_unit,
                  currency,
                  status,
                  headline_text,
                  headline_url,
                  headline_published_at
                from {SUPPLY_AUCTION_VIEW}
                {where_sql}
                order by
                  try_cast(event_date as date) asc nulls last,
                  case severity
                    when 'high' then 0
                    when 'medium' then 1
                    else 2
                  end asc,
                  title asc,
                  event_id asc
                limit ? offset ?
                """,
                [*where_params, lim, off],
            ).fetchall()
        source_version = str(version_row[0]) if version_row is not None else "sv_supply_auction_empty"
        vendor_version = str(version_row[1]) if version_row is not None else "vv_none"
        rule_version = str(version_row[2]) if version_row is not None else "rv_supply_auction_v1"
        return ResearchCalendarPage(
            events=[self._row_to_event(tuple(row)) for row in rows],
            total_rows=total_rows,
            limit=lim,
            offset=off,
            table_name=SUPPLY_AUCTION_VIEW,
            source_version=source_version,
            vendor_version=vendor_version,
            rule_version=rule_version,
        )


def _coerce_event_date(value: object) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value))


def _coerce_event_kind(value: object) -> ResearchCalendarEventKind:
    raw = str(value).strip().lower()
    if raw not in {"auction", "supply"}:
        raise ValueError(f"Unsupported research calendar event_kind: {value!r}")
    return cast(ResearchCalendarEventKind, raw)


def _coerce_severity(value: object) -> ResearchCalendarSeverity:
    raw = str(value).strip().lower()
    if raw not in {"high", "medium", "low"}:
        raise ValueError(f"Unsupported research calendar severity: {value!r}")
    return cast(ResearchCalendarSeverity, raw)


def _coerce_status(value: object) -> ResearchCalendarStatus:
    raw = "unknown" if value is None else str(value).strip().lower()
    if raw not in {"scheduled", "completed", "cancelled", "unknown"}:
        raise ValueError(f"Unsupported research calendar status: {value!r}")
    return cast(ResearchCalendarStatus, raw)


def _coerce_published_at(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))
