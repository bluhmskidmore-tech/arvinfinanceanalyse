from __future__ import annotations

from pathlib import Path

import duckdb
from backend.app.services.formal_result_runtime import build_result_envelope

RULE_VERSION = "rv_choice_news_v1"
CACHE_VERSION = "cv_choice_news_v1"


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
) -> dict[str, object]:
    duckdb_file = Path(duckdb_path)
    normalized_stock_code = stock_code.strip().upper() if stock_code and stock_code.strip() else None
    stock_filter_tokens = _choice_news_stock_filter_tokens(normalized_stock_code)
    rows: list[tuple[object, ...]]
    if not duckdb_file.exists():
        total_rows = 0
        rows = []
    else:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
        try:
            tables = {row[0] for row in conn.execute("show tables").fetchall()}
            if "choice_news_event" not in tables:
                total_rows = 0
                rows = []
            else:
                where_clause, params = _choice_news_filters(
                    group_id=group_id,
                    topic_code=topic_code,
                    stock_filter_tokens=stock_filter_tokens,
                    error_only=error_only,
                    received_from=received_from,
                    received_to=received_to,
                )
                total_row = conn.execute(
                    f"select count(*) from choice_news_event {where_clause}",
                    params,
                ).fetchone()
                total_rows = int(total_row[0]) if total_row is not None else 0
                rows = conn.execute(
                    """
                    select event_key, received_at, group_id, content_type, serial_id, request_id, error_code, error_msg, topic_code, item_index, payload_text, payload_json
                    from choice_news_event
                    """
                    + where_clause
                    + """
                    order by received_at desc, topic_code asc, item_index asc
                    limit ? offset ?
                    """,
                    [*params, limit, offset],
                ).fetchall()
        except duckdb.Error:
            total_rows = 0
            rows = []
        finally:
            conn.close()

    payload_rows = [
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
        }
        for event_key, received_at, group_id, content_type, serial_id, request_id, error_code, error_msg, topic_code, item_index, payload_text, payload_json in rows
    ]

    result_payload: dict[str, object] = {
        "total_rows": int(total_rows),
        "limit": limit,
        "offset": offset,
        "events": payload_rows,
    }
    if normalized_stock_code is not None:
        result_payload["stock_code"] = normalized_stock_code
        result_payload["stock_filter_mode"] = "payload_text_or_json_best_effort"
        result_payload["stock_filter_tokens"] = stock_filter_tokens

    return build_result_envelope(
        basis="analytical",
        trace_id="tr_choice_news_latest",
        result_kind="news.choice.latest",
        cache_version=CACHE_VERSION,
        source_version=f"sv_choice_news_{len(payload_rows)}",
        rule_version=RULE_VERSION,
        quality_flag="ok",
        result_payload=result_payload,
    )


def _choice_news_filters(
    group_id: str | None,
    topic_code: str | None,
    stock_filter_tokens: list[str],
    error_only: bool,
    received_from: str | None,
    received_to: str | None,
) -> tuple[str, list[object]]:
    filters: list[str] = []
    params: list[object] = []
    if group_id is not None:
        filters.append("group_id = ?")
        params.append(group_id)
    if topic_code is not None:
        filters.append("topic_code = ?")
        params.append(topic_code)
    if stock_filter_tokens:
        stock_clauses: list[str] = []
        for token in stock_filter_tokens:
            stock_clauses.append(
                "(upper(coalesce(payload_text, '')) like ? or upper(coalesce(payload_json, '')) like ?)"
            )
            params.extend([f"%{token.upper()}%", f"%{token.upper()}%"])
        filters.append("(" + " or ".join(stock_clauses) + ")")
    if error_only:
        filters.append("error_code != 0")
    if received_from is not None:
        filters.append("received_at >= ?")
        params.append(received_from)
    if received_to is not None:
        filters.append("received_at <= ?")
        params.append(received_to)
    if not filters:
        return "", params
    return "where " + " and ".join(filters), params


def _choice_news_stock_filter_tokens(stock_code: str | None) -> list[str]:
    if not stock_code:
        return []
    tokens = [stock_code]
    stem = stock_code.split(".", 1)[0]
    if len(stem) == 6 and stem.isdigit():
        tokens.append(stem)
    return list(dict.fromkeys(tokens))
