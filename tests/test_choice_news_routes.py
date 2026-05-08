from __future__ import annotations

import sys

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from tests.helpers import load_module


def _choice_news_read_client(tmp_path, monkeypatch, *, grant_read: bool = True) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()
    if grant_read:
        UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
            user_id="*",
            role=None,
            resource="choice_news.data",
            action="read",
        )
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def _seed_choice_news_topics(tmp_path) -> None:
    path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_news_event (
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
        conn.executemany(
            """
            insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "ev_filter_a",
                    "2026-05-08T09:00:00Z",
                    "g1",
                    "sectornews",
                    1,
                    1,
                    0,
                    "",
                    "TOPIC_FILTER_A",
                    0,
                    "headline alpha summary text",
                    None,
                ),
                (
                    "ev_filter_b",
                    "2026-05-08T10:00:00Z",
                    "g1",
                    "sectornews",
                    2,
                    1,
                    0,
                    "",
                    "TOPIC_FILTER_B",
                    0,
                    "headline beta",
                    None,
                ),
            ],
        )
    finally:
        conn.close()


def test_choice_events_latest_authorized_returns_envelope(tmp_path, monkeypatch) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.get("/ui/news/choice-events/latest", params={"limit": 10, "offset": 0})
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["result_kind"] == "news.choice.latest"
    assert isinstance(payload["result"]["events"], list)
    assert payload["result"]["total_rows"] >= 0
    get_settings.cache_clear()


def test_choice_events_latest_no_duckdb_file_returns_empty_envelope(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "nonexistent.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    get_settings.cache_clear()
    UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id="*",
        role=None,
        resource="choice_news.data",
        action="read",
    )
    for mod in ("backend.app.main", "backend.app.api"):
        sys.modules.pop(mod, None)
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/ui/news/choice-events/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["events"] == []
    assert body["result"]["total_rows"] == 0
    get_settings.cache_clear()


def test_choice_events_latest_forbidden_without_read_grant(tmp_path, monkeypatch) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch, grant_read=False)
    response = client.get("/ui/news/choice-events/latest")
    assert response.status_code == 403
    get_settings.cache_clear()


def test_choice_events_latest_topic_code_param_filters(tmp_path, monkeypatch) -> None:
    _seed_choice_news_topics(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.get("/ui/news/choice-events/latest", params={"topic_code": "TOPIC_FILTER_A"})
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["total_rows"] == 1
    assert len(body["result"]["events"]) == 1
    assert body["result"]["events"][0]["topic_code"] == "TOPIC_FILTER_A"
    assert "alpha" in body["result"]["events"][0]["payload_text"]
    get_settings.cache_clear()


def test_tushare_npr_ingest_ui_still_503_reserved(tmp_path, monkeypatch) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.post("/ui/news/tushare-npr/ingest", params={"limit": 5})
    assert response.status_code == 503
    detail = str(response.json().get("detail", "")).lower()
    assert "reserved" in detail
    get_settings.cache_clear()
