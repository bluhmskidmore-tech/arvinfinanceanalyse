from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.agent.runtime.research_workflow_catalog import get_research_workflow
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.repositories.market_read_repo import (
    CHOICE_NEWS_EVENTS_SQL as _CHOICE_NEWS_EVENTS_SQL,
)
from backend.app.repositories.market_read_repo import MarketReadRepository
from backend.app.services.research_radar_compare import build_choice_news_compare_payload

# rule/cache 版本以 research_workflow_catalog 为单一事实来源，避免 handler 与 catalog 漂移。
_CATALOG_WORKFLOW = get_research_workflow("research_radar_brief")
RULE_VERSION = _CATALOG_WORKFLOW.rule_version if _CATALOG_WORKFLOW else "rv_research_radar_v1"
CACHE_VERSION = _CATALOG_WORKFLOW.cache_version if _CATALOG_WORKFLOW else "cv_research_radar_v1"

def research_radar_brief_payload(
    request: AgentQueryRequest,
    duckdb_path: str,
) -> dict[str, Any]:
    limit = _requested_limit(request)
    events = _load_choice_news_events(duckdb_path, limit=limit)
    compare = build_choice_news_compare_payload(events)
    next_checks = _next_check_rows(events)
    compare_rows = _compare_card_rows(compare)

    return {
        "answer": f"研究速读已返回 {len(events)} 条新闻事件，候选情景均需人工复核。",
        "cards": [
            {"type": "metric", "title": "事件数", "value": str(len(events))},
            {"type": "table", "title": "原始事件证据", "data": events},
            {"type": "table", "title": "跨篇对比", "data": compare_rows},
            {"type": "table", "title": "候选情景建议", "data": compare["candidate_scenarios"]},
            {"type": "table", "title": "下一步检查", "data": next_checks},
        ],
        "tables_used": ["choice_news_event"],
        "filters_applied": {"limit": limit},
        "row_count": len(events),
        "sql_executed": [_CHOICE_NEWS_EVENTS_SQL],
        "quality_flag": "warning",
        "basis": "analytical",
        "formal_use_allowed": False,
        "scenario_flag": False,
        "source_version": f"sv_research_radar_{len(events)}",
        "rule_version": RULE_VERSION,
        "cache_version": CACHE_VERSION,
        "result_kind": "agent.research_radar_brief",
        "vendor_status": "ok",
        "fallback_mode": "none",
        "next_drill": [{"dimension": "topic_code", "label": "按主题查看新闻事件"}],
        "suggested_actions": [
            {
                "type": "inspect_news_events",
                "label": "查看新闻事件明细",
                "payload": {"href": "/news-events"},
                "requires_confirmation": True,
            }
        ],
    }


def _requested_limit(request: AgentQueryRequest) -> int:
    raw_limit = request.filters.get("limit", request.context.get("limit", 20))
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return 20
    return max(1, min(limit, 100))


def _load_choice_news_events(duckdb_path: str, *, limit: int) -> list[dict[str, Any]]:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return []

    return MarketReadRepository(str(duckdb_file)).fetch_choice_news_events(limit=limit)


def _compare_card_rows(compare: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for compare_type in ("same_direction", "conflicting", "review_needed"):
        for row in compare.get(compare_type, []):
            rows.append({"compare_type": compare_type, **row})
    if rows:
        return rows
    return [
        {
            "compare_type": "none",
            "reason": "no_comparable_events",
            "human_review_required": True,
        }
    ]


def _next_check_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "label": "查看新闻事件明细",
            "href": "/news-events",
            "reason": "核对原始新闻、主题与接收时间",
        }
    ]
    first_topic = next((str(event.get("topic_code") or "").strip() for event in events if event.get("topic_code")), "")
    if first_topic:
        rows.append(
            {
                "label": "按主题过滤",
                "href": f"/news-events?topic_code={first_topic}",
                "reason": "检查同主题事件是否支持候选情景",
            }
        )
    return rows
