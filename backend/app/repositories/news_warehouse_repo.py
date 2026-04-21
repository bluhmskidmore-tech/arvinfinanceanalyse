"""DuckDB `fact_news_event` — normalized news warehouse (Tushare + Choice backfill)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import duckdb

from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection

_URL_KEY_CANDIDATES = (
    "url",
    "report_url",
    "pdf_url",
    "ann_pdf_url",
    "ann_url",
    "link",
    "source_url",
    "doc_url",
    "_url",
)

_RETENTION_DAYS = 30


def ensure_news_warehouse_schema(conn: duckdb.DuckDBPyConnection) -> None:
    apply_pending_migrations_on_connection(conn)


def _news_key_digest(source: str, identity: str, pub_time_iso: str) -> str:
    seed = f"{source}{identity}{pub_time_iso}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def _parse_pub_time(pub_time_iso: str | None) -> datetime | None:
    raw = str(pub_time_iso or "").strip()
    if not raw:
        return None
    candidate = raw.replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(candidate[:19])
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _retention_until(pub_time: datetime | None, ingested_at: datetime) -> datetime:
    base = pub_time if pub_time is not None else ingested_at
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    return base.astimezone(UTC).replace(tzinfo=None) + timedelta(days=_RETENTION_DAYS)


def _extract_url_from_payload(payload: dict[str, Any]) -> str:
    for key in _URL_KEY_CANDIDATES:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower().startswith(("http://", "https://")):
            return text
    return ""


def _extract_title_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("title", "report_title"):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return None


def _extract_content_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("content", "content_html", "abstr", "abstract", "summary"):
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return None


def infer_source_kind(group_id: str) -> str:
    g = str(group_id or "").strip().lower()
    if g in ("tushare_policy", "tushare_npr"):
        return "policy"
    if g == "tushare_news":
        return "news"
    if g == "tushare_cctv":
        return "cctv"
    if g == "tushare_major":
        return "major"
    if g == "tushare_research":
        return "research"
    if g.startswith("choice_"):
        return "choice"
    return "choice"


def upsert_news_event(
    conn: duckdb.DuckDBPyConnection,
    *,
    source: str,
    source_kind: str,
    title: str | None,
    url: str | None,
    content: str | None,
    summary: str | None,
    pub_time_iso: str | None,
    extra: dict[str, object],
) -> bool:
    extra_json = json.dumps(extra, ensure_ascii=False, default=str)
    identity = (url or title or summary or extra_json or "").strip()
    key_seed_pt = str(pub_time_iso or "").strip()
    news_key = _news_key_digest(source, identity, key_seed_pt)

    exists_row = conn.execute(
        "select count(*) from fact_news_event where news_key = ?",
        [news_key],
    ).fetchone()
    if int(exists_row[0] if exists_row is not None else 0) > 0:
        return False

    now_utc = datetime.now(UTC)
    ingested_at = now_utc.replace(tzinfo=None)
    pub_dt = _parse_pub_time(pub_time_iso)
    pub_store = pub_dt.replace(tzinfo=None) if pub_dt is not None else None
    ret_until = _retention_until(pub_dt, now_utc)

    conn.execute(
        """
        insert into fact_news_event (
          news_key, source, source_kind, title, url, content, summary,
          pub_time, ingested_at, retention_until, extra_json
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            news_key,
            source,
            source_kind,
            title,
            url,
            content,
            summary,
            pub_store,
            ingested_at,
            ret_until,
            extra_json,
        ],
    )
    return True


def purge_expired_news_events(conn: duckdb.DuckDBPyConnection) -> int:
    before_row = conn.execute(
        "select count(*) from fact_news_event where retention_until < now()",
    ).fetchone()
    before = int(before_row[0]) if before_row is not None else 0
    if before == 0:
        return 0
    conn.execute("delete from fact_news_event where retention_until < now()")
    return before


def list_news_latest(
    conn: duckdb.DuckDBPyConnection,
    *,
    source: str | None = None,
    source_kind: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, object]]:
    clauses: list[str] = []
    params: list[object] = []
    if source is not None:
        clauses.append("source = ?")
        params.append(source)
    if source_kind is not None:
        clauses.append("source_kind = ?")
        params.append(source_kind)
    where_sql = f"where {' and '.join(clauses)}" if clauses else ""
    lim = max(1, int(limit))
    off = max(0, int(offset))
    params.extend([lim, off])
    sql = f"""
        select news_key, source, source_kind, title, url, content, summary,
               pub_time, ingested_at, retention_until, extra_json
        from fact_news_event
        {where_sql}
        order by pub_time desc nulls last, ingested_at desc
        limit ? offset ?
    """
    rows = conn.execute(sql, params).fetchall()
    colnames = (
        "news_key",
        "source",
        "source_kind",
        "title",
        "url",
        "content",
        "summary",
        "pub_time",
        "ingested_at",
        "retention_until",
        "extra_json",
    )
    out: list[dict[str, object]] = []
    for row in rows:
        item: dict[str, object] = {}
        for name, cell in zip(colnames, row, strict=True):
            if isinstance(cell, datetime):
                item[name] = cell
            else:
                item[name] = cell
        out.append(item)
    return out


def backfill_from_choice_news_event(
    conn: duckdb.DuckDBPyConnection,
    *,
    max_rows: int | None = None,
) -> int:
    ensure_news_warehouse_schema(conn)
    sql = "select group_id, payload_text, payload_json, received_at from choice_news_event"
    params: list[object] = []
    if max_rows is not None:
        sql += " limit ?"
        params.append(int(max_rows))
    fetched = conn.execute(sql, params).fetchall()
    inserted = 0
    for group_id, payload_text, payload_json, received_at in fetched:
        source = str(group_id or "")
        sk = infer_source_kind(source)
        raw_json = str(payload_json or "")
        try:
            payload = json.loads(raw_json) if raw_json.strip() else {}
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload_typed = {str(k): v for k, v in payload.items()}
        title = _extract_title_from_payload(payload_typed)
        url_val = _extract_url_from_payload(payload_typed)
        url = url_val or None
        content = _extract_content_from_payload(payload_typed)
        summary = str(payload_text or "").strip() or None
        pub_iso = str(received_at or "").strip() or None
        if upsert_news_event(
            conn,
            source=source,
            source_kind=sk,
            title=title,
            url=url,
            content=content,
            summary=summary,
            pub_time_iso=pub_iso,
            extra=payload_typed,
        ):
            inserted += 1
    return inserted
