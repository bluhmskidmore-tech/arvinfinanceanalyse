from __future__ import annotations

import json
from collections import defaultdict
from typing import Any


def build_choice_news_compare_payload(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    normalized_events = [_normalize_event(event) for event in events]
    return {
        "same_direction": _same_direction_rows(normalized_events),
        "conflicting": _conflicting_rows(normalized_events),
        "review_needed": _review_needed_rows(normalized_events),
        "candidate_scenarios": _candidate_scenario_rows(normalized_events),
    }


def _normalize_event(event: dict[str, Any]) -> dict[str, str]:
    topic_code = str(event.get("topic_code") or "").strip()
    headline = _event_headline(event)
    return {
        "event_key": str(event.get("event_key") or "").strip(),
        "received_at": str(event.get("received_at") or "").strip(),
        "topic_code": topic_code,
        "theme": _event_theme(topic_code=topic_code, headline=headline),
        "headline": headline,
        "polarity": _event_polarity(headline),
    }


def _same_direction_rows(events: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_theme: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in events:
        by_theme[event["theme"]].append(event)

    rows: list[dict[str, Any]] = []
    for theme in sorted(by_theme):
        theme_events = by_theme[theme]
        if len(theme_events) < 2:
            continue
        rows.append(
            {
                "theme": theme,
                "event_count": len(theme_events),
                "event_keys": [event["event_key"] for event in theme_events if event["event_key"]],
                "summary": _join_headlines(theme_events),
            }
        )
    return rows


def _conflicting_rows(events: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_theme: dict[str, list[dict[str, str]]] = defaultdict(list)
    for event in events:
        by_theme[event["theme"]].append(event)

    rows: list[dict[str, Any]] = []
    for theme in sorted(by_theme):
        polarities = {event["polarity"] for event in by_theme[theme]}
        if not {"positive", "negative"}.issubset(polarities):
            continue
        rows.append(
            {
                "theme": theme,
                "reason": "mixed_positive_negative_language",
                "event_keys": [event["event_key"] for event in by_theme[theme] if event["event_key"]],
                "human_review_required": True,
            }
        )
    return rows


def _review_needed_rows(events: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "event_key": event["event_key"],
            "topic_code": event["topic_code"],
            "theme": event["theme"],
            "reason": "analytical_news_signal_requires_human_review",
            "headline": event["headline"],
            "human_review_required": True,
        }
        for event in events[:5]
    ]


def _candidate_scenario_rows(events: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": f"research_radar_{index:02d}",
            "theme": event["theme"],
            "trigger_event_key": event["event_key"],
            "received_at": event["received_at"],
            "summary": event["headline"],
            "human_review_required": True,
        }
        for index, event in enumerate(events[:5], start=1)
    ]


def _event_headline(event: dict[str, Any]) -> str:
    payload_text = str(event.get("payload_text") or "").strip()
    if payload_text:
        return payload_text

    payload_json = event.get("payload_json")
    if not payload_json:
        return ""
    try:
        parsed = json.loads(str(payload_json))
    except json.JSONDecodeError:
        return str(payload_json)
    for key in ("title", "TITLE", "headline", "CONTENT", "content"):
        value = parsed.get(key) if isinstance(parsed, dict) else None
        if value:
            return str(value).strip()
    return str(payload_json)


def _event_theme(*, topic_code: str, headline: str) -> str:
    haystack = f"{topic_code} {headline}".lower()
    if any(token in haystack for token in ("rate", "rates", "yield", "central bank", "利率", "央行")):
        return "rates"
    if any(token in haystack for token in ("credit", "default", "spread", "信用", "地产")):
        return "credit"
    if any(token in haystack for token in ("stock", "equity", "earnings", "股票", "权益")):
        return "equity"
    if any(token in haystack for token in ("macro", "cpi", "pmi", "宏观")):
        return "macro"
    return "general"


def _event_polarity(headline: str) -> str:
    normalized = headline.lower()
    if any(token in normalized for token in ("risk", "down", "decline", "default", "风险", "下行", "回落")):
        return "negative"
    if any(token in normalized for token in ("up", "rise", "improve", "增长", "上行", "改善")):
        return "positive"
    return "neutral"


def _join_headlines(events: list[dict[str, str]]) -> str:
    headlines = [event["headline"] for event in events if event["headline"]]
    return " | ".join(headlines[:3])
