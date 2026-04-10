from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from backend.app.config.choice_runtime import _init_runtime
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM, GovernanceRepository
from backend.app.schemas.choice_news import ChoiceNewsTopicsAsset
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.build_runs import BuildRunRecord

MAX_CNQ_TOPIC_CODES = 4
CHOICE_NEWS_EVENT_STREAM = "choice_news_event"


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


def load_choice_news_topics(path: Path) -> ChoiceNewsTopicsAsset:
    return ChoiceNewsTopicsAsset.model_validate_json(path.read_text(encoding="utf-8"))


def _chunk_topics(topics, size: int):
    for start in range(0, len(topics), size):
        yield topics[start : start + size]


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
        conn.execute(
            """
            create table if not exists choice_news_event (
              event_key varchar,
              received_at varchar,
              group_id varchar,
              content_type varchar,
              serial_id bigint,
              request_id bigint,
              error_code bigint,
              error_msg varchar,
              topic_code varchar,
              item_index bigint,
              payload_text varchar,
              payload_json varchar
            )
            """
        )
        conn.execute("alter table choice_news_event add column if not exists event_key varchar")
        for event in events:
            event_key = str(event.get("event_key") or _build_choice_news_event_key(event))
            exists = conn.execute(
                "select count(*) from choice_news_event where event_key = ?",
                [event_key],
            ).fetchone()[0]
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
        total_rows = int(conn.execute("select count(*) from choice_news_event").fetchone()[0])
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
                        "received_at": datetime.now(timezone.utc).isoformat(),
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
                    "received_at": datetime.now(timezone.utc).isoformat(),
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
