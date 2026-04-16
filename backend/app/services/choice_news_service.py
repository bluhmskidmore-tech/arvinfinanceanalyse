from __future__ import annotations

from backend.app.governance.temporal_guard import (
    TemporalDatasetContract,
    filter_rows_as_of,
)
from backend.app.repositories.choice_news_repo import ChoiceNewsRepository
from backend.app.services.formal_result_runtime import build_result_envelope

RULE_VERSION = "rv_choice_news_v1"
CACHE_VERSION = "cv_choice_news_v1"


def choice_news_latest_envelope(
    duckdb_path: str,
    limit: int = 100,
    offset: int = 0,
    group_id: str | None = None,
    topic_code: str | None = None,
    error_only: bool = False,
    received_from: str | None = None,
    received_to: str | None = None,
) -> dict[str, object]:
    repo = ChoiceNewsRepository(duckdb_path)
    if received_to is not None:
        storage_ready, _, raw_rows = repo.fetch_events(
            limit=limit,
            offset=offset,
            group_id=group_id,
            topic_code=topic_code,
            error_only=error_only,
            received_from=received_from,
            received_to=None,
            paginate=False,
        )
        temporal_rows = _rows_to_dicts(raw_rows)
        guarded_rows = filter_rows_as_of(
            rows=temporal_rows,
            contract=TemporalDatasetContract(
                dataset_name="choice_news_event",
                published_at_field="received_at",
                effective_from_field="received_at",
            ),
            as_of_date=received_to,
        )
        total_rows = len(guarded_rows)
        payload_rows = guarded_rows[offset : offset + limit]
    else:
        storage_ready, total_rows, rows = repo.fetch_events(
            limit=limit,
            offset=offset,
            group_id=group_id,
            topic_code=topic_code,
            error_only=error_only,
            received_from=received_from,
            received_to=received_to,
            paginate=True,
        )
        payload_rows = _rows_to_dicts(rows)

    return build_result_envelope(
        basis="analytical",
        trace_id="tr_choice_news_latest",
        result_kind="news.choice.latest",
        cache_version=CACHE_VERSION,
        source_version=f"sv_choice_news_{len(payload_rows)}",
        rule_version=RULE_VERSION,
        quality_flag="ok" if storage_ready else "warning",
        vendor_status="ok" if storage_ready else "vendor_unavailable",
        result_payload={
            "total_rows": int(total_rows),
            "limit": limit,
            "offset": offset,
            "events": payload_rows,
        },
    )


def _rows_to_dicts(rows: list[tuple[object, ...]]) -> list[dict[str, object]]:
    return [
        {
            "event_key": str(event_key),
            "received_at": None if received_at is None else str(received_at),
            "group_id": str(group_id),
            "content_type": str(content_type),
            "serial_id": int(serial_id),
            "request_id": int(request_id),
            "error_code": int(error_code),
            "error_msg": str(error_msg),
            "topic_code": str(topic_code),
            "item_index": int(item_index),
            "payload_text": payload_text,
            "payload_json": payload_json,
        }
        for event_key, received_at, group_id, content_type, serial_id, request_id, error_code, error_msg, topic_code, item_index, payload_text, payload_json in rows
    ]
