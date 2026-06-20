from __future__ import annotations

import json
from pathlib import Path

import duckdb

from tests.helpers import load_module


def _load_script_module():
    return load_module(
        "scripts.refresh_tushare_news_backup",
        "scripts/refresh_tushare_news_backup.py",
    )


class _FakeActor:
    actor_name = "ingest_tushare_news_to_choice_news"

    def __init__(self) -> None:
        self.fn_calls: list[dict[str, object]] = []
        self.send_calls: list[dict[str, object]] = []

    def fn(self, **kwargs: object) -> dict[str, object]:
        self.fn_calls.append(kwargs)
        return {"status": "completed", "inserted": 2, "fetched": 3}

    def send(self, **kwargs: object) -> object:
        self.send_calls.append(kwargs)
        return type("Message", (), {"message_id": "msg-1"})()


def test_refresh_tushare_news_backup_runs_actor_sync(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    actor = _FakeActor()
    monkeypatch.setattr(module, "ingest_tushare_news_to_choice_news", actor)

    db = tmp_path / "moss.duckdb"
    result = module.refresh_tushare_news_backup(
        duckdb_path=db,
        limit=7,
        news_limit=13,
        news_src="sina",
        news_lookback_hours=6,
        cctv_lookback_days=2,
        major_lookback_hours=4,
        research_lookback_days=1,
        enqueue=False,
    )

    assert result == {"status": "completed", "inserted": 2, "fetched": 3}
    assert actor.fn_calls == [
        {
            "duckdb_path": str(db),
            "limit": 7,
            "news_limit": 13,
            "news_src": "sina",
            "news_lookback_hours": 6,
            "cctv_lookback_days": 2,
            "major_lookback_hours": 4,
            "research_lookback_days": 1,
        }
    ]
    assert actor.send_calls == []


def test_refresh_tushare_news_backup_can_enqueue_actor(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    actor = _FakeActor()
    monkeypatch.setattr(module, "ingest_tushare_news_to_choice_news", actor)

    db = tmp_path / "moss.duckdb"
    result = module.refresh_tushare_news_backup(
        duckdb_path=db,
        limit=5,
        news_limit=11,
        enqueue=True,
    )

    assert result == {
        "status": "queued",
        "actor": "ingest_tushare_news_to_choice_news",
        "message_id": "msg-1",
    }
    assert actor.send_calls == [
        {
            "duckdb_path": str(db),
            "limit": 5,
            "news_limit": 11,
            "news_src": None,
            "news_lookback_hours": 48,
            "cctv_lookback_days": 3,
            "major_lookback_hours": 48,
            "research_lookback_days": 3,
        }
    ]
    assert actor.fn_calls == []


def test_refresh_tushare_news_backup_dry_run_profiles_current_backup_without_actor_call(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_script_module()
    actor = _FakeActor()
    monkeypatch.setattr(module, "ingest_tushare_news_to_choice_news", actor)
    db = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        conn.execute(
            """
            create table choice_news_event (
              event_key varchar,
              received_at varchar,
              group_id varchar,
              content_type varchar,
              serial_id integer,
              request_id integer,
              error_code integer,
              error_msg varchar,
              topic_code varchar,
              item_index integer,
              payload_text varchar,
              payload_json varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_news_event values
            ('n1','2026-06-01T08:00:00+00:00','tushare_news','news',0,0,0,'','tushare.news.sina',0,'央行公开市场操作','{}'),
            ('n2','2026-05-31T08:00:00+00:00','tushare_major','major_news',0,0,0,'','tushare.major_news',0,'宏观新闻','{}'),
            ('n3','2026-05-19T08:50:00+00:00','tushare_policy','npr',0,0,0,'','tushare.npr',0,'政策新闻','{}')
            """
        )
    finally:
        conn.close()

    result = module.refresh_tushare_news_backup(
        duckdb_path=db,
        limit=9,
        news_limit=15,
        news_src="sina",
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["would_call"]["limit"] == 9
    assert result["would_call"]["news_limit"] == 15
    assert result["would_call"]["news_src"] == "sina"
    assert result["current_backup_state"]["status"] == "available"
    assert result["current_backup_state"]["topics"] == [
        {
            "topic_code": "tushare.major_news",
            "rows": 1,
            "latest_received_at": "2026-05-31T08:00:00+00:00",
            "error_rows": 0,
            "blank_payload_rows": 0,
        },
        {
            "topic_code": "tushare.news.sina",
            "rows": 1,
            "latest_received_at": "2026-06-01T08:00:00+00:00",
            "error_rows": 0,
            "blank_payload_rows": 0,
        },
        {
            "topic_code": "tushare.npr",
            "rows": 1,
            "latest_received_at": "2026-05-19T08:50:00+00:00",
            "error_rows": 0,
            "blank_payload_rows": 0,
        },
    ]
    assert actor.fn_calls == []
    assert actor.send_calls == []


def test_refresh_tushare_news_backup_cli_dry_run_emits_json_without_actor_call(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = _load_script_module()
    actor = _FakeActor()
    monkeypatch.setattr(module, "ingest_tushare_news_to_choice_news", actor)
    missing_db = tmp_path / "missing.duckdb"

    exit_code = module.main(
        [
            "--duckdb-path",
            str(missing_db),
            "--news-src",
            "sina",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "dry_run"
    assert payload["would_call"]["duckdb_path"] == str(missing_db)
    assert payload["would_call"]["news_src"] == "sina"
    assert payload["current_backup_state"] == {
        "status": "missing_database",
        "duckdb_path": str(missing_db),
        "topics": [],
    }
    assert actor.fn_calls == []
    assert actor.send_calls == []
