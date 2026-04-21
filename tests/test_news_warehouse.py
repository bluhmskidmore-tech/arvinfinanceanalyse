from __future__ import annotations

from datetime import datetime

import duckdb

from backend.app.repositories.news_warehouse_repo import (
    backfill_from_choice_news_event,
    ensure_news_warehouse_schema,
    list_news_latest,
    purge_expired_news_events,
    upsert_news_event,
)
from backend.app.tasks.choice_news import ensure_choice_news_event_schema


def test_upsert_idempotent(tmp_path) -> None:
    db = tmp_path / "wh.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        ensure_news_warehouse_schema(conn)
        a = upsert_news_event(
            conn,
            source="tushare_news",
            source_kind="news",
            title="T",
            url="https://example.com/a",
            content=None,
            summary="S",
            pub_time_iso="2026-04-21T10:00:00+00:00",
            extra={"k": 1},
        )
        b = upsert_news_event(
            conn,
            source="tushare_news",
            source_kind="news",
            title="T",
            url="https://example.com/a",
            content=None,
            summary="S",
            pub_time_iso="2026-04-21T10:00:00+00:00",
            extra={"k": 1},
        )
        assert a is True
        assert b is False
    finally:
        conn.close()


def test_list_news_latest_orders_by_pub_time_desc(tmp_path) -> None:
    db = tmp_path / "wh2.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        ensure_news_warehouse_schema(conn)
        upsert_news_event(
            conn,
            source="tushare_news",
            source_kind="news",
            title="older",
            url=None,
            content=None,
            summary="a",
            pub_time_iso="2026-04-20T10:00:00+00:00",
            extra={},
        )
        upsert_news_event(
            conn,
            source="tushare_news",
            source_kind="news",
            title="newer",
            url=None,
            content=None,
            summary="b",
            pub_time_iso="2026-04-21T10:00:00+00:00",
            extra={},
        )
        rows = list_news_latest(conn, limit=10)
        pts = [r.get("pub_time") for r in rows]
        assert len(pts) == 2
        assert pts[0] is not None and pts[1] is not None
        assert pts[0] >= pts[1]
    finally:
        conn.close()


def test_purge_expired_deletes_rows(tmp_path) -> None:
    db = tmp_path / "wh3.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        ensure_news_warehouse_schema(conn)
        conn.execute(
            """
            insert into fact_news_event (
              news_key, source, source_kind, title, url, content, summary,
              pub_time, ingested_at, retention_until, extra_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "deadbeefdeadbeefdeadbeef",
                "tushare_news",
                "news",
                "x",
                None,
                None,
                "s",
                datetime(2020, 1, 1),
                datetime(2020, 1, 1),
                datetime(2020, 1, 5),
                "{}",
            ],
        )
        n = purge_expired_news_events(conn)
        assert n == 1
        left = conn.execute("select count(*) from fact_news_event").fetchone()
        assert int(left[0]) == 0
    finally:
        conn.close()


def test_backfill_tushare_npr_maps_policy(tmp_path) -> None:
    db = tmp_path / "wh4.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        ensure_choice_news_event_schema(conn)
        conn.execute(
            """
            insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "ev1",
                "2026-04-21T12:00:00+00:00",
                "tushare_npr",
                "npr",
                0,
                0,
                0,
                "",
                "topic",
                0,
                "摘要",
                '{"title": "国务院通知", "url": "https://gov.example/p", "content": "正文"}',
            ],
        )
        n = backfill_from_choice_news_event(conn)
        assert n == 1
        row = conn.execute(
            "select source, source_kind, title from fact_news_event limit 1"
        ).fetchone()
        assert row is not None
        assert row[0] == "tushare_npr"
        assert row[1] == "policy"
        assert row[2] == "国务院通知"
    finally:
        conn.close()


def test_backfill_respects_max_rows(tmp_path) -> None:
    db = tmp_path / "wh5.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        ensure_choice_news_event_schema(conn)
        for i in range(3):
            conn.execute(
                """
                insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    f"ev{i}",
                    "2026-04-21T12:00:00+00:00",
                    "tushare_news",
                    "news",
                    0,
                    0,
                    0,
                    "",
                    "topic",
                    i,
                    "s",
                    f'{{"title": "t{i}"}}',
                ],
            )
        n = backfill_from_choice_news_event(conn, max_rows=2)
        assert n == 2
        total = conn.execute("select count(*) from fact_news_event").fetchone()
        assert int(total[0]) == 2
    finally:
        conn.close()
