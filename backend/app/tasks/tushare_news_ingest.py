from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
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
PROVIDER_ID_KEY_CANDIDATES = (
    "id",
    "news_id",
    "article_id",
    "doc_id",
    "report_id",
    "ann_id",
)

CHOICE_NEWS_EVENT_RETENTION_DAYS = 30


def _empty_block_stats() -> dict[str, object]:
    return {"inserted": 0, "skipped_duplicates": 0, "fetched": 0}


def _format_block_error(exc: BaseException) -> str:
    message = " ".join(str(exc).split()) or "no error details"
    return f"{type(exc).__name__}: {message}"


def _run_news_block_transaction(
    conn: duckdb.DuckDBPyConnection,
    block: Callable[[], dict[str, object]],
) -> tuple[dict[str, object], str | None]:
    conn.execute("begin transaction")
    try:
        stats = block()
        conn.execute("commit")
        return dict(stats), None
    except Exception as exc:  # noqa: BLE001 - isolate a failed ingest block
        conn.execute("rollback")
        return _empty_block_stats(), _format_block_error(exc)


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

    policy_stats: dict[str, object] = _empty_block_stats()
    news_stats: dict[str, object] = _empty_block_stats()
    cctv_stats: dict[str, object] = _empty_block_stats()
    major_stats: dict[str, object] = _empty_block_stats()
    research_stats: dict[str, object] = _empty_block_stats()
    policy_error: str | None = None
    news_error: str | None = None
    cctv_error: str | None = None
    major_error: str | None = None
    research_error: str | None = None

    purged = 0
    purged_warehouse = 0
    with acquire_lock(resolve_duckdb_writer_lock(duckdb_file), base_dir=duckdb_file.parent):
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        try:
            with repository_task_write_scope(__name__):
                ensure_choice_news_event_schema(conn)
                policy_stats, policy_error = _run_news_block_transaction(
                    conn,
                    lambda: _ingest_policy_block(conn, pro, limit=limit),
                )
                news_stats, news_error = _run_news_block_transaction(
                    conn,
                    lambda: _ingest_news_block(
                        conn,
                        pro,
                        src=news_src,
                        limit=news_limit,
                        lookback_hours=news_lookback_hours,
                    ),
                )
                cctv_stats, cctv_error = _run_news_block_transaction(
                    conn,
                    lambda: _ingest_cctv_news_block(conn, pro, lookback_days=cctv_lookback_days),
                )
                major_stats, major_error = _run_news_block_transaction(
                    conn,
                    lambda: _ingest_major_news_block(conn, pro, lookback_hours=major_lookback_hours),
                )
                research_stats, research_error = _run_news_block_transaction(
                    conn,
                    lambda: _ingest_research_report_block(conn, pro, lookback_days=research_lookback_days),
                )
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
    total_ins = sum(int(block.get("inserted") or 0) for block in blocks)
    total_skip = sum(int(block.get("skipped_duplicates") or 0) for block in blocks)
    total_fetch = sum(int(block.get("fetched") or 0) for block in blocks)
    block_failures = [
        error
        for error in (policy_error, news_error, cctv_error, major_error, research_error)
        if error is not None
    ]
    cctv_day_errors = cctv_stats.get("errors")
    if isinstance(cctv_day_errors, list) and cctv_day_errors:
        block_failures.append("cctv day errors")

    def _block_payload(stats: dict[str, object], error: str | None, **extra: object) -> dict[str, object]:
        out: dict[str, object] = {
            "inserted": int(stats.get("inserted") or 0),
            "skipped_duplicates": int(stats.get("skipped_duplicates") or 0),
            "fetched": int(stats.get("fetched") or 0),
        }
        for key, value in stats.items():
            if key not in out:
                out[key] = value
        out.update(extra)
        if error is not None:
            out["error"] = error
        return out

    return {
        "status": "partial" if block_failures else "completed",
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


def _stable_tushare_event_key(
    *,
    record: dict[str, Any],
    group: str,
    content: str,
    prefix: str,
    time_keys: list[str],
    title_keys: list[str],
    provider_id_keys: tuple[str, ...] = PROVIDER_ID_KEY_CANDIDATES,
    scope: str = "",
) -> str:
    provider_id = _first_nonempty(record, list(provider_id_keys))
    if provider_id:
        seed = "|".join([group, content, scope, "provider_id", provider_id])
    else:
        title = _strip_html(_first_nonempty(record, title_keys))
        title_hash = hashlib.sha256(title.encode("utf-8")).hexdigest()[:16]
        seed = "|".join(
            [
                group,
                content,
                scope,
                _extract_url(record),
                _first_nonempty(record, time_keys),
                title_hash,
            ]
        )
    return prefix + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def _event_key_policy(record: dict[str, Any], item_index: int) -> str:
    _ = item_index
    return _stable_tushare_event_key(
        record=record,
        group=TUSHARE_GROUP_POLICY,
        content=CONTENT_POLICY,
        prefix="tpol_",
        time_keys=["pubtime", "date", "datetime"],
        title_keys=["title"],
        provider_id_keys=("pcode", *PROVIDER_ID_KEY_CANDIDATES),
    )


def _event_key_generic(record: dict[str, Any], item_index: int, group: str, content: str) -> str:
    _ = item_index
    return _stable_tushare_event_key(
        record=record,
        group=group,
        content=content,
        prefix=f"{group[:6]}_",
        time_keys=["date", "datetime", "pub_date", "pub_time", "trade_date", "report_date"],
        title_keys=["title", "report_title", "name"],
    )


def _event_key_news(record: dict[str, Any], item_index: int, src: str) -> str:
    _ = item_index
    return _stable_tushare_event_key(
        record=record,
        group=TUSHARE_GROUP_NEWS,
        content=CONTENT_NEWS,
        prefix="tnews_",
        time_keys=["datetime", "date", "pub_date"],
        title_keys=["title"],
        scope=src,
    )


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
) -> dict[str, object]:
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
) -> dict[str, object]:
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
) -> dict[str, object]:
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
) -> dict[str, object]:
    aggregate: dict[str, object] = {"inserted": 0, "skipped_duplicates": 0, "fetched": 0}
    errors: list[dict[str, object]] = []
    successful_dates: list[str] = []
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
        except Exception as exc:  # noqa: BLE001 - retain per-day CCTV failures in the result
            logger.warning("CCTV news ingest failed for date %s, skipping", date_str, exc_info=True)
            errors.append(
                {
                    "date": date_str,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            continue
        for key in ("inserted", "skipped_duplicates", "fetched"):
            aggregate[key] = int(aggregate[key]) + int(block[key])
        successful_dates.append(date_str)
    if errors:
        aggregate["errors"] = errors
    if successful_dates:
        aggregate["successful_dates"] = successful_dates
    return aggregate


def _ingest_major_news_block(
    conn: duckdb.DuckDBPyConnection,
    pro: object,
    *,
    lookback_hours: int = 48,
) -> dict[str, object]:
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
) -> dict[str, object]:
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
