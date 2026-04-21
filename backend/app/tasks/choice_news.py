from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import duckdb
from backend.app.config.choice_runtime import _init_runtime
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM, GovernanceRepository
from backend.app.schemas.choice_news import ChoiceNewsTopicsAsset
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.build_runs import BuildRunRecord

MAX_CNQ_TOPIC_CODES = 4
CHOICE_NEWS_EVENT_STREAM = "choice_news_event"
CHOICE_NEWS_PULL_MODE_END_COUNT = 2
CHOICE_NEWS_VENDOR_TZ = timezone(timedelta(hours=8))


def _subscribe_choice_sectornews(
    topics_file: str | None = None,
    governance_dir: str | None = None,
) -> dict[str, object]:
    _init_runtime()
    settings = get_settings()
    governance_path = Path(governance_dir or settings.governance_path)
    repo = GovernanceRepository(base_dir=governance_path)
    asset = load_choice_news_topics(Path(topics_file or settings.choice_news_topics_file))
    client = ChoiceClient()

    subscriptions = []
    for group in asset.groups:
        for chunk_index, chunk in enumerate(_chunk_topics(group.topics, MAX_CNQ_TOPIC_CODES), start=1):
            codes = ",".join(topic.topic_code for topic in chunk)
            callback = build_choice_news_callback(
                repo=repo,
                group_id=group.group_id,
                content_type=asset.content_type,
            )
            result = client.cnq(codes, asset.content_type, callback=callback)
            client.cnqcancel(int(getattr(result, "SerialID", 0)))
            subscriptions.append(
                {
                    "group_id": group.group_id,
                    "chunk_index": chunk_index,
                    "topic_count": len(chunk),
                    "serial_id": int(getattr(result, "SerialID", 0)),
                    "error_code": int(getattr(result, "ErrorCode", 0)),
                    "error_msg": str(getattr(result, "ErrorMsg", "")),
                }
            )

    return {
        "status": "completed",
        "subscription_count": len(subscriptions),
        "subscriptions": subscriptions,
    }


def _pull_choice_sectornews_snapshot(
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    topics_file: str | None = None,
    count: int = 20,
) -> dict[str, object]:
    _init_runtime()
    settings = get_settings()
    governance_path = Path(governance_dir or settings.governance_path)
    repo = GovernanceRepository(base_dir=governance_path)
    asset = load_choice_news_topics(Path(topics_file or settings.choice_news_topics_file))
    client = ChoiceClient()

    count = max(1, int(count))
    fetched_row_count = 0
    inserted_count = 0
    fetches: list[dict[str, object]] = []

    for group in asset.groups:
        for topic in group.topics:
            result = client.cfn(
                topic.topic_code,
                asset.content_type,
                CHOICE_NEWS_PULL_MODE_END_COUNT,
                options=f"count={count},Ispandas=1,RECVtimeout=5",
            )
            topic_rows = _persist_choice_news_cfn_result(
                repo=repo,
                result=result,
                group_id=group.group_id,
                content_type=asset.content_type,
                requested_topic_code=topic.topic_code,
            )
            fetched_row_count += topic_rows
            inserted_count += topic_rows
            fetches.append(
                {
                    "group_id": group.group_id,
                    "topic_code": topic.topic_code,
                    "fetched_row_count": topic_rows,
                    "error_code": int(getattr(result, "ErrorCode", 0)),
                    "error_msg": str(getattr(result, "ErrorMsg", "")),
                }
            )

    materialize = _materialize_choice_news_events(
        duckdb_path=duckdb_path,
        governance_dir=str(governance_path),
    )
    return {
        "status": "completed",
        "fetched_row_count": fetched_row_count,
        "inserted_count": inserted_count,
        "fetches": fetches,
        "materialize": materialize,
    }


def load_choice_news_topics(path: Path) -> ChoiceNewsTopicsAsset:
    return ChoiceNewsTopicsAsset.model_validate_json(path.read_text(encoding="utf-8"))


def _chunk_topics(topics, size: int):
    for start in range(0, len(topics), size):
        yield topics[start : start + size]


def ensure_choice_news_event_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)


def _materialize_choice_news_events(
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    repo = GovernanceRepository(base_dir=governance_path)
    events = repo.read_all(CHOICE_NEWS_EVENT_STREAM)
    run = BuildRunRecord(job_name="choice_news_materialize", status="running", cache_key="choice_news.latest")
    run_id = f"{run.job_name}:{run.created_at}"
    inserted_count = 0

    conn = duckdb.connect(str(duckdb_file), read_only=False)
    try:
        ensure_choice_news_event_schema(conn)
        for event in events:
            event_key = str(event.get("event_key") or _build_choice_news_event_key(event))
            exists_row = conn.execute(
                "select count(*) from choice_news_event where event_key = ?",
                [event_key],
            ).fetchone()
            exists = int(exists_row[0]) if exists_row is not None else 0
            if exists:
                continue
            conn.execute(
                """
                insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    event_key,
                    event.get("received_at"),
                    event.get("group_id"),
                    event.get("content_type"),
                    event.get("serial_id"),
                    event.get("request_id"),
                    event.get("error_code"),
                    event.get("error_msg"),
                    event.get("topic_code"),
                    event.get("item_index"),
                    event.get("payload_text"),
                    event.get("payload_json"),
                ],
            )
            inserted_count += 1
    finally:
        total_row = conn.execute("select count(*) from choice_news_event").fetchone()
        total_rows = int(total_row[0]) if total_row is not None else 0
        conn.close()

    source_version = f"sv_choice_news_{total_rows}"

    repo.append_many_atomic(
        [
            (
                CACHE_MANIFEST_STREAM,
                CacheManifestRecord(
                    cache_key=run.cache_key,
                    source_version=source_version,
                    vendor_version="vv_none",
                    rule_version="rv_choice_news_v1",
                ).model_dump(),
            ),
            (
                CACHE_BUILD_RUN_STREAM,
                CacheBuildRunRecord(
                    run_id=run_id,
                    job_name=run.job_name,
                    status="completed",
                    cache_key=run.cache_key,
                    lock="lock:duckdb:choice-news",
                    source_version=source_version,
                    vendor_version="vv_none",
                ).model_dump(),
            ),
        ]
    )

    return {
        "status": "completed",
        "event_count": total_rows,
        "inserted_count": inserted_count,
        "run_id": run_id,
    }


subscribe_choice_sectornews = register_actor_once(
    "subscribe_choice_sectornews",
    _subscribe_choice_sectornews,
)
materialize_choice_news_events = register_actor_once(
    "materialize_choice_news_events",
    _materialize_choice_news_events,
)
pull_choice_sectornews_snapshot = register_actor_once(
    "pull_choice_sectornews_snapshot",
    _pull_choice_sectornews_snapshot,
)


def build_choice_news_callback(
    repo: GovernanceRepository,
    group_id: str,
    content_type: str,
    serial_id: int | None = None,
):
    def _callback(quantdata) -> int:
        payloads = getattr(quantdata, "Data", {}) or {}
        wrote_rows = False
        for topic_code, items in payloads.items():
            for index, item in enumerate(items):
                payload_text = None
                payload_json = None
                if isinstance(item, (dict, list)):
                    payload_json = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
                else:
                    payload_text = str(item)
                repo.append(
                    CHOICE_NEWS_EVENT_STREAM,
                    {
                        "received_at": datetime.now(UTC).isoformat(),
                        "event_key": _build_choice_news_event_key(
                            {
                                "group_id": group_id,
                                "content_type": content_type,
                                "error_code": int(getattr(quantdata, "ErrorCode", 0)),
                                "error_msg": str(getattr(quantdata, "ErrorMsg", "")),
                                "topic_code": str(topic_code),
                                "item_index": index,
                                "payload_text": payload_text,
                                "payload_json": payload_json,
                            }
                        ),
                        "group_id": group_id,
                        "content_type": content_type,
                        "serial_id": int(getattr(quantdata, "SerialID", serial_id or 0)),
                        "request_id": int(getattr(quantdata, "RequestID", 0)),
                        "error_code": int(getattr(quantdata, "ErrorCode", 0)),
                        "error_msg": str(getattr(quantdata, "ErrorMsg", "")),
                        "topic_code": str(topic_code),
                        "item_index": index,
                        "payload_text": payload_text,
                        "payload_json": payload_json,
                    },
                )
                wrote_rows = True
        if not wrote_rows:
            repo.append(
                CHOICE_NEWS_EVENT_STREAM,
                {
                    "received_at": datetime.now(UTC).isoformat(),
                    "event_key": _build_choice_news_event_key(
                        {
                            "group_id": group_id,
                            "content_type": content_type,
                            "error_code": int(getattr(quantdata, "ErrorCode", 0)),
                            "error_msg": str(getattr(quantdata, "ErrorMsg", "")),
                            "topic_code": "__callback__",
                            "item_index": -1,
                            "payload_text": None,
                            "payload_json": None,
                        }
                    ),
                    "group_id": group_id,
                    "content_type": content_type,
                    "serial_id": int(getattr(quantdata, "SerialID", serial_id or 0)),
                    "request_id": int(getattr(quantdata, "RequestID", 0)),
                    "error_code": int(getattr(quantdata, "ErrorCode", 0)),
                    "error_msg": str(getattr(quantdata, "ErrorMsg", "")),
                    "topic_code": "__callback__",
                    "item_index": -1,
                    "payload_text": None,
                    "payload_json": None,
                },
            )
        return 1

    return _callback


def _persist_choice_news_cfn_result(
    repo: GovernanceRepository,
    result,
    group_id: str,
    content_type: str,
    requested_topic_code: str,
) -> int:
    error_code = int(getattr(result, "ErrorCode", 0))
    error_msg = str(getattr(result, "ErrorMsg", ""))
    if error_code != 0:
        repo.append(
            CHOICE_NEWS_EVENT_STREAM,
            {
                "received_at": datetime.now(UTC).isoformat(),
                "event_key": _build_choice_news_event_key(
                    {
                        "group_id": group_id,
                        "content_type": content_type,
                        "error_code": error_code,
                        "error_msg": error_msg,
                        "topic_code": requested_topic_code,
                        "item_index": -1,
                        "payload_text": None,
                        "payload_json": None,
                    }
                ),
                "group_id": group_id,
                "content_type": content_type,
                "serial_id": int(getattr(result, "SerialID", 0)),
                "request_id": int(getattr(result, "RequestID", 0)),
                "error_code": error_code,
                "error_msg": error_msg,
                "topic_code": requested_topic_code,
                "item_index": -1,
                "payload_text": None,
                "payload_json": None,
            },
        )
        return 1

    indicators = [str(item) for item in (getattr(result, "Indicators", None) or [])]
    payloads = getattr(result, "Data", {}) or {}
    inserted = 0
    for topic_code, items in payloads.items():
        for index, item in enumerate(items):
            row = _coerce_choice_news_cfn_row(indicators, item)
            payload_text = str(row.get("TITLE") or row.get("title") or "").strip() or None
            payload_json = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            repo.append(
                CHOICE_NEWS_EVENT_STREAM,
                {
                    "received_at": _normalize_choice_news_received_at(
                        row.get("DATETIME") or row.get("EITIME")
                    ),
                    "event_key": _build_choice_news_event_key(
                        {
                            "group_id": group_id,
                            "content_type": content_type,
                            "error_code": 0,
                            "error_msg": error_msg,
                            "topic_code": str(topic_code),
                            "item_index": index,
                            "payload_text": payload_text,
                            "payload_json": payload_json,
                        }
                    ),
                    "group_id": group_id,
                    "content_type": content_type,
                    "serial_id": int(getattr(result, "SerialID", 0)),
                    "request_id": int(getattr(result, "RequestID", 0)),
                    "error_code": 0,
                    "error_msg": error_msg,
                    "topic_code": str(topic_code),
                    "item_index": index,
                    "payload_text": payload_text,
                    "payload_json": payload_json,
                },
            )
            inserted += 1
    return inserted


def _coerce_choice_news_cfn_row(indicators: list[str], item) -> dict[str, object]:
    if isinstance(item, dict):
        return {str(key): value for key, value in item.items()}
    if isinstance(item, (list, tuple)):
        return {
            indicators[index] if index < len(indicators) else f"FIELD_{index}": value
            for index, value in enumerate(item)
        }
    return {"VALUE": item}


def _normalize_choice_news_received_at(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return datetime.now(UTC).isoformat()
    candidate = raw.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return raw
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CHOICE_NEWS_VENDOR_TZ)
    return parsed.isoformat()


def _build_choice_news_event_key(event: dict[str, object]) -> str:
    seed = "|".join(
        [
            str(event.get("group_id", "")),
            str(event.get("content_type", "")),
            str(event.get("topic_code", "")),
            str(event.get("item_index", "")),
            str(event.get("error_code", "")),
            str(event.get("error_msg", "")),
            str(event.get("payload_text", "")),
            str(event.get("payload_json", "")),
        ]
    )
    return "ce_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
