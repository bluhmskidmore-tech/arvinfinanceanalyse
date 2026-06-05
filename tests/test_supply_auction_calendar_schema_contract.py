from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError


def test_research_calendar_event_forbids_extra_fields() -> None:
    from backend.app.schemas.research_calendar import ResearchCalendarEvent

    with pytest.raises(ValidationError):
        ResearchCalendarEvent(
            event_id="evt-1",
            series_id="research.calendar.supply_auction",
            event_date="2026-04-24",
            event_kind="auction",
            title="国开债 3Y 招标",
            source_family="research_supply_auction",
            severity="high",
            extra_field="not-allowed",
        )


def test_research_calendar_event_enforces_narrow_enums() -> None:
    from backend.app.schemas.research_calendar import ResearchCalendarEvent

    with pytest.raises(ValidationError):
        ResearchCalendarEvent(
            event_id="evt-1",
            series_id="research.calendar.supply_auction",
            event_date="2026-04-24",
            event_kind="surprise",
            title="国开债 3Y 招标",
            source_family="research_supply_auction",
            severity="high",
        )


def test_supply_auction_calendar_service_keeps_v1_boundaries() -> None:
    text = Path("backend/app/services/research_calendar_service.py").read_text(encoding="utf-8")
    assert "choice_news_event" not in text
    assert "choice_news_service" not in text
    assert "event_calendar" not in text
    assert "balance_workbook" not in text
