"""Refresh Tushare news backup rows for the dashboard news fallback.

This is an operator entry point, not a public API surface. The UI/API ingest
routes stay reserved; schedule this script or enqueue the actor from trusted
ops automation when Tushare credentials are available.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from backend.app.governance.settings import get_settings  # noqa: E402
from backend.app.tasks.choice_news import ingest_tushare_news_to_choice_news  # noqa: E402

TUSHARE_BACKUP_TOPICS = ("tushare.major_news", "tushare.news.sina", "tushare.npr")


def _actor_kwargs(
    *,
    duckdb_path: str | Path | None = None,
    limit: int = 20,
    news_limit: int = 100,
    news_src: str | None = None,
    news_lookback_hours: int = 48,
    cctv_lookback_days: int = 3,
    major_lookback_hours: int = 48,
    research_lookback_days: int = 3,
) -> dict[str, object]:
    resolved_path = Path(duckdb_path) if duckdb_path is not None else get_settings().duckdb_path
    return {
        "duckdb_path": str(resolved_path),
        "limit": int(limit),
        "news_limit": int(news_limit),
        "news_src": news_src.strip() if isinstance(news_src, str) and news_src.strip() else None,
        "news_lookback_hours": int(news_lookback_hours),
        "cctv_lookback_days": int(cctv_lookback_days),
        "major_lookback_hours": int(major_lookback_hours),
        "research_lookback_days": int(research_lookback_days),
    }


def refresh_tushare_news_backup(
    *,
    duckdb_path: str | Path | None = None,
    limit: int = 20,
    news_limit: int = 100,
    news_src: str | None = None,
    news_lookback_hours: int = 48,
    cctv_lookback_days: int = 3,
    major_lookback_hours: int = 48,
    research_lookback_days: int = 3,
    enqueue: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    kwargs = _actor_kwargs(
        duckdb_path=duckdb_path,
        limit=limit,
        news_limit=news_limit,
        news_src=news_src,
        news_lookback_hours=news_lookback_hours,
        cctv_lookback_days=cctv_lookback_days,
        major_lookback_hours=major_lookback_hours,
        research_lookback_days=research_lookback_days,
    )
    if dry_run:
        return {
            "status": "dry_run",
            "would_call": kwargs,
            "current_backup_state": inspect_tushare_news_backup_state(kwargs["duckdb_path"]),
        }
    if enqueue:
        message = ingest_tushare_news_to_choice_news.send(**kwargs)
        return {
            "status": "queued",
            "actor": ingest_tushare_news_to_choice_news.actor_name,
            "message_id": getattr(message, "message_id", None),
        }
    return ingest_tushare_news_to_choice_news.fn(**kwargs)


def inspect_tushare_news_backup_state(duckdb_path: str | Path) -> dict[str, object]:
    path = Path(duckdb_path)
    if not path.exists():
        return {"status": "missing_database", "duckdb_path": str(path), "topics": []}

    conn = duckdb.connect(str(path), read_only=True)
    try:
        table_exists = conn.execute(
            "select count(*) from information_schema.tables where table_name = 'choice_news_event'"
        ).fetchone()
        if int(table_exists[0] if table_exists is not None else 0) == 0:
            return {"status": "missing_table", "duckdb_path": str(path), "topics": []}

        rows = conn.execute(
            """
            select
              topic_code,
              count(*) as rows,
              max(received_at) as latest_received_at,
              sum(case when error_code <> 0 then 1 else 0 end) as error_rows,
              sum(case when payload_text is null or trim(payload_text) = '' then 1 else 0 end) as blank_payload_rows
            from choice_news_event
            where topic_code in (?, ?, ?)
            group by topic_code
            order by topic_code
            """,
            TUSHARE_BACKUP_TOPICS,
        ).fetchall()
    finally:
        conn.close()

    return {
        "status": "available",
        "duckdb_path": str(path),
        "topics": [
            {
                "topic_code": str(row[0]),
                "rows": int(row[1]),
                "latest_received_at": row[2],
                "error_rows": int(row[3] or 0),
                "blank_payload_rows": int(row[4] or 0),
            }
            for row in rows
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh Tushare news backup rows for dashboard fallback.")
    parser.add_argument("--duckdb-path", default=None)
    parser.add_argument("--limit", type=int, default=20, help="Tushare npr row limit")
    parser.add_argument("--news-limit", type=int, default=100, help="Tushare pro.news row limit")
    parser.add_argument("--news-src", default=None, help="Tushare pro.news src, default from settings/env")
    parser.add_argument("--news-lookback-hours", type=int, default=48)
    parser.add_argument("--cctv-lookback-days", type=int, default=3)
    parser.add_argument("--major-lookback-hours", type=int, default=48)
    parser.add_argument("--research-lookback-days", type=int, default=3)
    parser.add_argument("--enqueue", action="store_true", help="Send the actor to the worker instead of running sync")
    parser.add_argument("--dry-run", action="store_true", help="Inspect current backup state without running ingest")
    args = parser.parse_args(argv)

    result = refresh_tushare_news_backup(
        duckdb_path=args.duckdb_path,
        limit=args.limit,
        news_limit=args.news_limit,
        news_src=args.news_src,
        news_lookback_hours=args.news_lookback_hours,
        cctv_lookback_days=args.cctv_lookback_days,
        major_lookback_hours=args.major_lookback_hours,
        research_lookback_days=args.research_lookback_days,
        enqueue=args.enqueue,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    status = str(result.get("status") or "").lower()
    return 0 if status in {"completed", "dry_run", "queued"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
