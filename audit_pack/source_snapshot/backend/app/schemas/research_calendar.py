from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ResearchCalendarEventKind = Literal["auction", "supply"]
ResearchCalendarSeverity = Literal["high", "medium", "low"]
ResearchCalendarStatus = Literal["scheduled", "completed", "cancelled", "unknown"]


class ResearchCalendarEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., min_length=1)
    series_id: str = Field(..., min_length=1)
    event_date: date
    event_kind: ResearchCalendarEventKind
    title: str = Field(..., min_length=1)
    source_family: str = Field(..., min_length=1)
    severity: ResearchCalendarSeverity
    issuer: str | None = None
    market: str | None = None
    instrument_type: str | None = None
    term_label: str | None = None
    amount: float | None = None
    amount_unit: str | None = None
    currency: str | None = None
    status: ResearchCalendarStatus = "scheduled"
    headline_text: str | None = None
    headline_url: str | None = None
    headline_published_at: datetime | None = None


class ResearchCalendarResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_id: str = Field(..., min_length=1)
    total_rows: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    events: list[ResearchCalendarEvent]
