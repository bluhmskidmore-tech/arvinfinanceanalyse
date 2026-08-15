from __future__ import annotations

from datetime import date
from typing import Literal

from backend.app.repositories.choice_news_repo import (
    ChoiceNewsRepository,
    choice_news_latest_sql_text,
    choice_news_stock_filter_tokens,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.research_radar_compare import build_choice_news_compare_payload

RULE_VERSION = "rv_choice_news_v2"
CACHE_VERSION = "cv_choice_news_v2"

StockMatchMode = Literal["best_effort", "visible_text"]


def choice_news_latest_sql_disclosure(
    *,
    group_id: str | None = None,
    topic_code: str | None = None,
    stock_code: str | None = None,
    stock_name: str | None = None,
    stock_match_mode: StockMatchMode = "best_effort",
    include_payload_json: bool = True,
    error_only: bool = False,
    received_from: str | None = None,
    received_to: str | None = None,
) -> list[str]:
    """仅用于证据披露：返回 choice_news_latest_envelope 实际执行的主干只读语句（同一模板），不执行 SQL。"""
    return choice_news_latest_sql_text(
        group_id=group_id,
        topic_code=topic_code,
        stock_code=stock_code,
        stock_name=stock_name,
        stock_match_mode=stock_match_mode,
        include_payload_json=include_payload_json,
        error_only=error_only,
        received_from=received_from,
        received_to=received_to,
    )


def _choice_news_event_payload_rows(
    rows: list[tuple[object, ...]],
) -> list[dict[str, object]]:
    """把主干事件查询的行映射为 API events 元素（单查与批量共用，保证逐字段一致）。"""
    return [
        {
            "event_key": str(event_key),
            "received_at": str(received_at),
            "group_id": str(group_id),
            "content_type": str(content_type),
            "serial_id": int(str(serial_id)),
            "request_id": int(str(request_id)),
            "error_code": int(str(error_code)),
            "error_msg": str(error_msg),
            "topic_code": str(topic_code),
            "item_index": int(str(item_index)),
            "payload_text": payload_text,
            "payload_json": payload_json,
            "display_text": _choice_news_display_text(
                payload_text,
                display_headline,
                display_summary,
            ),
        }
        for (
            event_key,
            received_at,
            group_id,
            content_type,
            serial_id,
            request_id,
            error_code,
            error_msg,
            topic_code,
            item_index,
            payload_text,
            payload_json,
            display_headline,
            display_summary,
        ) in rows
    ]


def _choice_news_display_text(
    payload_text: object,
    display_headline: object,
    display_summary: object,
) -> str | None:
    normalized_payload_text = str(payload_text).strip() if payload_text is not None else ""
    if normalized_payload_text:
        return normalized_payload_text
    headline = str(display_headline).strip() if display_headline is not None else ""
    summary = str(display_summary).strip() if display_summary is not None else ""
    if headline and summary and headline != summary:
        return f"{headline} - {summary}"
    if headline:
        return headline
    if summary:
        return summary
    return None


def choice_news_latest_envelope(
    duckdb_path: str,
    limit: int = 100,
    offset: int = 0,
    group_id: str | None = None,
    topic_code: str | None = None,
    stock_code: str | None = None,
    error_only: bool = False,
    received_from: str | None = None,
    received_to: str | None = None,
    stock_name: str | None = None,
    stock_match_mode: StockMatchMode = "best_effort",
    include_payload_json: bool = True,
) -> dict[str, object]:
    as_of_date = date.today().isoformat()
    effective_received_to = received_to or as_of_date
    normalized_stock_code = stock_code.strip().upper() if stock_code and stock_code.strip() else None
    normalized_stock_name = (
        stock_name.strip().upper() if normalized_stock_code is not None and stock_name and stock_name.strip() else None
    )
    stock_filter_tokens = choice_news_stock_filter_tokens(
        normalized_stock_code,
        normalized_stock_name,
    )
    raw = ChoiceNewsRepository(path=duckdb_path, guard_path_exists=True).fetch_latest(
        limit=limit,
        offset=offset,
        group_id=group_id,
        topic_code=topic_code,
        stock_filter_tokens=stock_filter_tokens,
        stock_match_mode=stock_match_mode,
        error_only=error_only,
        received_from=received_from,
        received_to=effective_received_to,
        include_payload_json=include_payload_json,
        as_of_date=as_of_date,
    )
    payload_rows = _choice_news_event_payload_rows(raw.rows)

    result_payload: dict[str, object] = {
        "total_rows": int(raw.total_rows),
        "limit": limit,
        "offset": offset,
        "as_of_date": as_of_date,
        "excluded_future_rows": raw.excluded_future_rows,
        "payload_json_included": include_payload_json,
        "compare": build_choice_news_compare_payload(payload_rows),
        "events": payload_rows,
    }
    if normalized_stock_code is not None:
        result_payload["stock_code"] = normalized_stock_code
        result_payload["stock_filter_mode"] = (
            "payload_text_only_strict_visible_text"
            if stock_match_mode == "visible_text"
            else "payload_text_or_json_best_effort"
        )
        result_payload["stock_filter_tokens"] = stock_filter_tokens

    return build_result_envelope(
        basis="analytical",
        trace_id="tr_choice_news_latest",
        result_kind="news.choice.latest",
        cache_version=CACHE_VERSION,
        source_version=f"sv_choice_news_{len(payload_rows)}",
        rule_version=RULE_VERSION,
        quality_flag="warning" if raw.source_unavailable or raw.excluded_future_rows else "ok",
        vendor_status="vendor_unavailable" if raw.source_unavailable else "ok",
        filters_applied={
            "received_to": effective_received_to,
            "future_rows_excluded": raw.excluded_future_rows,
        },
        result_payload=result_payload,
        source_surface="choice_news",
        tables_used=["choice_news_event"],
        evidence_rows=len(payload_rows),
        as_of_date=as_of_date,
        date_basis="received_at_as_of_filter",
    )


def choice_news_latest_batch_envelope(
    duckdb_path: str,
    *,
    topic_requests: list[tuple[str, int]],
    group_requests: list[tuple[str, int]],
) -> dict[str, object]:
    """在一次只读连接内执行多个 topic/group 子查询。

    每个子查询的过滤/排序/limit 语义与 choice_news_latest_envelope 的单 topic/group
    查询完全一致（include_payload_json=True、offset=0、无 stock 过滤、无 received 时间过滤）。
    batches 顺序与请求顺序一致（先 topics 后 groups）。
    """
    as_of_date = date.today().isoformat()
    requests: list[dict[str, object]] = [
        {"key": f"topic:{code}", "topic_code": code, "group_id": None, "limit": limit}
        for code, limit in topic_requests
    ]
    requests.extend(
        {"key": f"group:{gid}", "topic_code": None, "group_id": gid, "limit": limit}
        for gid, limit in group_requests
    )

    raw = ChoiceNewsRepository(path=duckdb_path, guard_path_exists=True).fetch_latest_batch(
        topic_requests=topic_requests,
        group_requests=group_requests,
        as_of_date=as_of_date,
    )
    events_per_request = [
        _choice_news_event_payload_rows(rows) for rows in raw.events_per_request
    ]

    batches = [
        {
            "key": request["key"],
            "topic_code": request["topic_code"],
            "group_id": request["group_id"],
            "events": events,
        }
        for request, events in zip(requests, events_per_request, strict=True)
    ]
    total_events = sum(len(events) for events in events_per_request)
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_choice_news_latest_batch",
        result_kind="news.choice.latest_batch",
        cache_version=CACHE_VERSION,
        source_version=f"sv_choice_news_{total_events}",
        rule_version=RULE_VERSION,
        quality_flag="warning" if raw.source_unavailable or raw.excluded_future_rows else "ok",
        vendor_status="vendor_unavailable" if raw.source_unavailable else "ok",
        filters_applied={
            "received_to": as_of_date,
            "future_rows_excluded": raw.excluded_future_rows,
        },
        result_payload={"batches": batches},
        source_surface="choice_news",
        tables_used=["choice_news_event"],
        evidence_rows=total_events,
        as_of_date=as_of_date,
        date_basis="received_at_as_of_filter",
    )
