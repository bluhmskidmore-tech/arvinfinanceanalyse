from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any

import duckdb
from backend.app.repositories.news_warehouse_repo import purge_expired_news_events, upsert_news_event
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.tasks.choice_news import ensure_choice_news_event_schema

logger = logging.getLogger(__name__)

TUSHARE_GROUP_POLICY = "tushare_policy"
TUSHARE_GROUP_NEWS = "tushare_news"
TUSHARE_GROUP_CCTV = "tushare_cctv"
TUSHARE_GROUP_MAJOR = "tushare_major"
TUSHARE_GROUP_RESEARCH = "tushare_research"
CONTENT_POLICY = "npr"
CONTENT_NEWS = "news"
CONTENT_CCTV = "cctv_news"
CONTENT_MAJOR = "major_news"
CONTENT_RESEARCH = "research_report"

URL_KEY_CANDIDATES = (
    "url",
    "report_url",
    "pdf_url",
    "ann_pdf_url",
    "ann_url",
    "link",
    "source_url",
    "doc_url",
)

CHOICE_NEWS_EVENT_RETENTION_DAYS = 30


def materialize_tushare_news_to_choice_news(
    *,
    duckdb_path: str,
    pro: object,
    news_src: str,
    limit: int = 20,
    news_limit: int = 100,
    news_lookback_hours: int = 48,
    cctv_lookback_days: int = 3,
    major_lookback_hours: int = 48,
    research_lookback_days: int = 3,
) -> dict[str, object]:
    duckdb_file = Path(duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)

    empty: dict[str, int] = {"inserted": 0, "skipped_duplicates": 0, "fetched": 0}
    policy_stats: dict[str, int] = dict(empty)
    news_stats: dict[str, int] = dict(empty)
    cctv_stats: dict[str, int] = dict(empty)
    major_stats: dict[str, int] = dict(empty)
    research_stats: dict[str, int] = dict(empty)
    policy_error: str | None = None
    news_error: str | None = None
    cctv_error: str | None = None
    major_error: str | None = None
    research_error: str | None = None

    purged = 0
    purged_warehouse = 0
    conn = duckdb.connect(str(duckdb_file), read_only=False)
    try:
        with repository_task_write_scope(__name__):
            ensure_choice_news_event_schema(conn)
            try:
                policy_stats = _ingest_policy_block(conn, pro, limit=limit)
            except Exception as exc:
                policy_error = str(exc)
            try:
                news_stats = _ingest_news_block(
                    conn,
                    pro,
                    src=news_src,
                    limit=news_limit,
                    lookback_hours=news_lookback_hours,
                )
            except Exception as exc:
                news_error = str(exc)
            try:
                cctv_stats = _ingest_cctv_news_block(conn, pro, lookback_days=cctv_lookback_days)
            except Exception as exc:
                cctv_error = str(exc)
            try:
                major_stats = _ingest_major_news_block(conn, pro, lookback_hours=major_lookback_hours)
            except Exception as exc:
                major_error = str(exc)
            try:
                research_stats = _ingest_research_report_block(
                    conn, pro, lookback_days=research_lookback_days
                )
            except Exception as exc:
                research_error = str(exc)
            try:
                purged = _purge_expired_choice_news_events(conn)
            except Exception:
                logger.warning("Failed to purge expired choice_news_event rows", exc_info=True)
                purged = 0
            try:
                purged_warehouse = purge_expired_news_events(conn)
            except Exception:
                logger.warning("Failed to purge expired warehouse news events", exc_info=True)
                purged_warehouse = 0
    finally:
        conn.close()

    blocks = [policy_stats, news_stats, cctv_stats, major_stats, research_stats]
    total_ins = sum(block["inserted"] for block in blocks)
    total_skip = sum(block["skipped_duplicates"] for block in blocks)
    total_fetch = sum(block["fetched"] for block in blocks)

    def _block_payload(stats: dict[str, int], error: str | None, **extra: object) -> dict[str, object]:
        out: dict[str, object] = {
            "inserted": stats["inserted"],
            "skipped_duplicates": stats["skipped_duplicates"],
            "fetched": stats["fetched"],
        }
        out.update(extra)
        if error is not None:
            out["error"] = error
        return out

    return {
        "status": "completed",
        "inserted": total_ins,
        "skipped_duplicates": total_skip,
        "fetched": total_fetch,
        "purged_expired": int(purged),
        "purged_expired_warehouse": int(purged_warehouse),
        "policy": _block_payload(policy_stats, policy_error),
        "news": _block_payload(news_stats, news_error, src=news_src),
        "cctv": _block_payload(cctv_stats, cctv_error),
        "major": _block_payload(major_stats, major_error),
        "research": _block_payload(research_stats, research_error),
    }


def _normalize_received_at(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return datetime.now(UTC).isoformat()
    candidate = raw.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(candidate[:19])
    except ValueError:
        return raw
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()


def _event_key_policy(record: dict[str, Any], item_index: int) -> str:
    seed = "|".join(
        [
            TUSHARE_GROUP_POLICY,
            CONTENT_POLICY,
            str(record.get("pubtime", "")),
            str(record.get("title", "")),
            str(record.get("pcode", "")),
            str(item_index),
        ]
    )
    return "tpol_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def _event_key_generic(record: dict[str, Any], item_index: int, group: str, content: str) -> str:
    seed = "|".join(
        [
            group,
            content,
            str(record.get("date", "") or record.get("datetime", "") or record.get("pub_date", "")),
            str(record.get("title", "")),
            str(record.get("content", ""))[:200],
            str(item_index),
        ]
    )
    return f"{group[:6]}_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def _event_key_news(record: dict[str, Any], item_index: int, src: str) -> str:
    seed = "|".join(
        [
            TUSHARE_GROUP_NEWS,
            CONTENT_NEWS,
            src,
            str(record.get("datetime", "")),
            str(record.get("title", "")),
            str(record.get("content", ""))[:200],
            str(item_index),
        ]
    )
    return "tnews_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def _first_nonempty(record: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return ""


def _strip_html(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", unescape(text))
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_content_for_warehouse(record: dict[str, Any]) -> str:
    for key in ("content", "content_html", "abstr", "abstract", "summary"):
        value = record.get(key)
        if value is None:
            continue
        text = _strip_html(str(value).strip())
        if text and text.lower() != "nan":
            return text
    return ""


def _extract_url(record: dict[str, Any]) -> str:
    for key in URL_KEY_CANDIDATES:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower().startswith(("http://", "https://")):
            return text
    return ""


def _ingest_simple_block(
    conn: duckdb.DuckDBPyConnection,
    *,
    fetcher,
    group_id: str,
    content_type: str,
    topic_prefix: str,
    title_keys: list[str],
    body_keys: list[str],
    time_keys: list[str],
    warehouse_source_kind: str,
) -> dict[str, int]:
    frame = fetcher()
    if frame is None or len(frame) == 0:
        return {"inserted": 0, "skipped_duplicates": 0, "fetched": 0}

    records = frame.to_dict(orient="records")
    inserted = 0
    skipped = 0
    for item_index, raw in enumerate(records):
        record = {str(k): v for k, v in raw.items()}
        event_key = _event_key_generic(record, item_index, group_id, content_type)
        exists_row = conn.execute(
            "select count(*) from choice_news_event where event_key = ?",
            [event_key],
        ).fetchone()
        if int(exists_row[0] if exists_row is not None else 0) > 0:
            skipped += 1
            continue
        title = _strip_html(_first_nonempty(record, title_keys))
        body = _strip_html(_first_nonempty(record, body_keys))
        if title and body:
            payload_text = f"{title} — {body[:280]}{'…' if len(body) > 280 else ''}"
        else:
            payload_text = title or body or "（空内容）"
        url = _extract_url(record)
        record_with_url = dict(record)
        if url:
            record_with_url["_url"] = url
        payload_json = json.dumps(record_with_url, ensure_ascii=False, default=str)
        received_at = _normalize_received_at(_first_nonempty(record, time_keys))
        conn.execute(
            """
            insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event_key,
                received_at,
                group_id,
                content_type,
                0,
                0,
                0,
                "",
                topic_prefix,
                item_index,
                payload_text,
                payload_json,
            ],
        )
        upsert_news_event(
            conn,
            source=group_id,
            source_kind=warehouse_source_kind,
            title=title or None,
            url=url or None,
            content=_extract_content_for_warehouse(record) or None,
            summary=payload_text or None,
            pub_time_iso=received_at,
            extra=dict(record_with_url),
        )
        inserted += 1
    return {"inserted": inserted, "skipped_duplicates": skipped, "fetched": len(records)}


def _ingest_policy_block(
    conn: duckdb.DuckDBPyConnection,
    pro: object,
    *,
    limit: int,
) -> dict[str, int]:
    lim = max(1, min(int(limit), 500))
    frame = pro.npr(
        limit=lim,
        fields="pubtime,title,pcode,puborg,url,ptype",
    )
    if frame is None or len(frame) == 0:
        return {"inserted": 0, "skipped_duplicates": 0, "fetched": 0}

    records = frame.to_dict(orient="records")
    inserted = 0
    skipped = 0
    for item_index, raw in enumerate(records):
        record = {str(k): v for k, v in raw.items()}
        event_key = _event_key_policy(record, item_index)
        exists_row = conn.execute(
            "select count(*) from choice_news_event where event_key = ?",
            [event_key],
        ).fetchone()
        if int(exists_row[0] if exists_row is not None else 0) > 0:
            skipped += 1
            continue
        title = str(record.get("title") or "").strip()
        puborg = str(record.get("puborg") or "").strip()
        payload_text = title if not puborg else f"{title} · {puborg}"
        url = _extract_url(record)
        record_with_url = dict(record)
        if url:
            record_with_url["_url"] = url
        payload_json = json.dumps(record_with_url, ensure_ascii=False, default=str)
        received_at = _normalize_received_at(record.get("pubtime"))
        pcode = str(record.get("pcode") or "")
        conn.execute(
            """
            insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event_key,
                received_at,
                TUSHARE_GROUP_POLICY,
                CONTENT_POLICY,
                0,
                0,
                0,
                "",
                pcode or "tushare.npr",
                item_index,
                payload_text,
                payload_json,
            ],
        )
        upsert_news_event(
            conn,
            source=TUSHARE_GROUP_POLICY,
            source_kind="policy",
            title=title or None,
            url=url or None,
            content=_extract_content_for_warehouse(record) or None,
            summary=payload_text or None,
            pub_time_iso=received_at,
            extra=dict(record_with_url),
        )
        inserted += 1
    return {"inserted": inserted, "skipped_duplicates": skipped, "fetched": len(records)}


def _ingest_news_block(
    conn: duckdb.DuckDBPyConnection,
    pro: object,
    *,
    src: str,
    limit: int,
    lookback_hours: int = 48,
) -> dict[str, int]:
    end = datetime.now()
    start = end - timedelta(hours=max(1, int(lookback_hours)))
    start_date = start.strftime("%Y-%m-%d %H:%M:%S")
    end_date = end.strftime("%Y-%m-%d %H:%M:%S")
    lim = max(1, min(int(limit), 1500))

    frame = pro.news(
        src=src,
        start_date=start_date,
        end_date=end_date,
        limit=lim,
        offset=0,
        fields=["datetime", "content", "title"],
    )
    if frame is None or len(frame) == 0:
        return {"inserted": 0, "skipped_duplicates": 0, "fetched": 0}

    records = frame.to_dict(orient="records")
    inserted = 0
    skipped = 0
    for item_index, raw in enumerate(records):
        record = {str(k): v for k, v in raw.items()}
        event_key = _event_key_news(record, item_index, src)
        exists_row = conn.execute(
            "select count(*) from choice_news_event where event_key = ?",
            [event_key],
        ).fetchone()
        if int(exists_row[0] if exists_row is not None else 0) > 0:
            skipped += 1
            continue
        title = _strip_html(str(record.get("title") or "").strip())
        content = _strip_html(str(record.get("content") or "").strip())
        payload_text = title if not content else f"{title} — {content[:280]}{'…' if len(content) > 280 else ''}"
        payload_json = json.dumps(record, ensure_ascii=False, default=str)
        received_at = _normalize_received_at(record.get("datetime"))
        topic = f"tushare.news.{src}"
        conn.execute(
            """
            insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event_key,
                received_at,
                TUSHARE_GROUP_NEWS,
                CONTENT_NEWS,
                0,
                0,
                0,
                "",
                topic,
                item_index,
                payload_text,
                payload_json,
            ],
        )
        upsert_news_event(
            conn,
            source=TUSHARE_GROUP_NEWS,
            source_kind="news",
            title=title or None,
            url=_extract_url(record) or None,
            content=_extract_content_for_warehouse(record) or None,
            summary=payload_text or None,
            pub_time_iso=received_at,
            extra=dict(record),
        )
        inserted += 1
    return {"inserted": inserted, "skipped_duplicates": skipped, "fetched": len(records)}


def _ingest_cctv_news_block(
    conn: duckdb.DuckDBPyConnection,
    pro: object,
    *,
    lookback_days: int = 3,
) -> dict[str, int]:
    aggregate: dict[str, int] = {"inserted": 0, "skipped_duplicates": 0, "fetched": 0}
    today = datetime.now().date()
    for offset in range(max(1, int(lookback_days))):
        target = today - timedelta(days=offset)
        date_str = target.strftime("%Y%m%d")
        topic_prefix = f"tushare.cctv_news.{date_str}"

        def _fetch(_ds: str = date_str):
            return pro.cctv_news(date=_ds)

        try:
            block = _ingest_simple_block(
                conn,
                fetcher=_fetch,
                group_id=TUSHARE_GROUP_CCTV,
                content_type=CONTENT_CCTV,
                topic_prefix=topic_prefix,
                title_keys=["title"],
                body_keys=["content"],
                time_keys=["date", "datetime"],
                warehouse_source_kind="cctv",
            )
        except Exception:
            logger.debug("CCTV news ingest failed for date %s, skipping", date_str, exc_info=True)
            continue
        for key in aggregate:
            aggregate[key] += block[key]
    return aggregate


def _ingest_major_news_block(
    conn: duckdb.DuckDBPyConnection,
    pro: object,
    *,
    lookback_hours: int = 48,
) -> dict[str, int]:
    end = datetime.now()
    start = end - timedelta(hours=max(1, int(lookback_hours)))
    start_date = start.strftime("%Y-%m-%d %H:%M:%S")
    end_date = end.strftime("%Y-%m-%d %H:%M:%S")
    topic_prefix = "tushare.major_news"

    def _fetch():
        return pro.major_news(
            src="",
            start_date=start_date,
            end_date=end_date,
            fields="title,content,pub_time,src",
        )

    return _ingest_simple_block(
        conn,
        fetcher=_fetch,
        group_id=TUSHARE_GROUP_MAJOR,
        content_type=CONTENT_MAJOR,
        topic_prefix=topic_prefix,
        title_keys=["title"],
        body_keys=["content", "abstract", "summary"],
        time_keys=["pub_time", "datetime", "date"],
        warehouse_source_kind="major",
    )


def _ingest_research_report_block(
    conn: duckdb.DuckDBPyConnection,
    pro: object,
    *,
    lookback_days: int = 3,
) -> dict[str, int]:
    end = datetime.now().date()
    start = end - timedelta(days=max(1, int(lookback_days)))
    start_date = start.strftime("%Y%m%d")
    end_date = end.strftime("%Y%m%d")
    topic_prefix = f"tushare.research_report.{start_date}_{end_date}"

    def _fetch():
        return pro.research_report(
            start_date=start_date,
            end_date=end_date,
            fields="trade_date,title,abstr,inst_csname,name,ts_code,ind_name,url,report_type,author",
        )

    return _ingest_simple_block(
        conn,
        fetcher=_fetch,
        group_id=TUSHARE_GROUP_RESEARCH,
        content_type=CONTENT_RESEARCH,
        topic_prefix=topic_prefix,
        title_keys=["title", "report_title"],
        body_keys=["abstr", "abstract", "summary", "content", "name"],
        time_keys=["trade_date", "pub_date", "report_date", "date"],
        warehouse_source_kind="research",
    )


def _purge_expired_choice_news_events(
    conn: duckdb.DuckDBPyConnection,
    *,
    retention_days: int = CHOICE_NEWS_EVENT_RETENTION_DAYS,
) -> int:
    days = max(1, int(retention_days))
    cutoff_iso = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    before_row = conn.execute(
        "select count(*) from choice_news_event where received_at < ?",
        [cutoff_iso],
    ).fetchone()
    before = int(before_row[0]) if before_row is not None else 0
    if before == 0:
        return 0
    conn.execute(
        "delete from choice_news_event where received_at < ?",
        [cutoff_iso],
    )
    return before
