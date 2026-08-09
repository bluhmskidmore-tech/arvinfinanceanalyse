from __future__ import annotations

import sys

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.services.choice_news_service import choice_news_latest_sql_disclosure
from tests.helpers import load_module


def _choice_news_read_client(
    tmp_path, monkeypatch, *, grant_read: bool = True
) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    sqlite_path = tmp_path / "auth-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_USER_ID", "choice-news-test-user")
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
                (
                    "ev_stock_full",
                    "2026-05-08T11:00:00Z",
                    "g1",
                    "sectornews",
                    3,
                    1,
                    0,
                    "",
                    "TOPIC_STOCK_FULL",
                    0,
                    "000001.SZ earnings watch headline",
                    None,
                ),
                (
                    "ev_stock_stem",
                    "2026-05-08T12:00:00Z",
                    "g1",
                    "sectornews",
                    4,
                    1,
                    0,
                    "",
                    "TOPIC_STOCK_STEM",
                    0,
                    "headline with stem only",
                    '{"stock_code":"000001","title":"stem match"}',
                ),
                (
                    "ev_stock_other",
                    "2026-05-08T13:00:00Z",
                    "g1",
                    "sectornews",
                    5,
                    1,
                    0,
                    "",
                    "TOPIC_STOCK_OTHER",
                    0,
                    "600000.SH unrelated headline",
                    None,
                ),
                (
                    "ev_stock_name",
                    "2026-05-08T12:30:00Z",
                    "g1",
                    "sectornews",
                    6,
                    1,
                    0,
                    "",
                    "TOPIC_STOCK_NAME",
                    0,
                    "Ping An Bank quarterly outlook",
                    None,
                ),
                (
                    "ev_future",
                    "2099-01-01T00:00:00+08:00",
                    "g1",
                    "sectornews",
                    7,
                    1,
                    0,
                    "",
                    "TOPIC_FUTURE",
                    0,
                    "future dated headline",
                    None,
                ),
            ],
        )
    finally:
        conn.close()


def _append_research_radar_events(tmp_path) -> None:
    conn = duckdb.connect(str(tmp_path / "moss.duckdb"), read_only=False)
    try:
        conn.executemany(
            """
            insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "ev_rates_review",
                    "2026-05-08T14:00:00Z",
                    "g1",
                    "sectornews",
                    7,
                    1,
                    0,
                    "",
                    "rates",
                    0,
                    "央行表态引发利率预期调整",
                    None,
                ),
                (
                    "ev_credit_review",
                    "2026-05-08T15:00:00Z",
                    "g1",
                    "sectornews",
                    8,
                    1,
                    0,
                    "",
                    "credit",
                    0,
                    "地产信用风险再度受关注",
                    None,
                ),
            ],
        )
    finally:
        conn.close()


def test_choice_events_latest_authorized_returns_envelope(
    tmp_path, monkeypatch
) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/news/choice-events/latest", params={"limit": 10, "offset": 0}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["result_kind"] == "news.choice.latest"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["source_surface"] == "choice_news"
    assert payload["result_meta"]["tables_used"] == ["choice_news_event"]
    assert payload["result"]["payload_json_included"] is True
    assert isinstance(payload["result"]["events"], list)
    assert payload["result"]["total_rows"] >= 0
    get_settings.cache_clear()


def test_choice_events_latest_excludes_future_rows_by_default(
    tmp_path, monkeypatch
) -> None:
    _seed_choice_news_topics(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/news/choice-events/latest", params={"limit": 10, "offset": 0}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"]["excluded_future_rows"] == 1
    assert payload["result_meta"]["filters_applied"]["future_rows_excluded"] == 1
    assert all(item["event_key"] != "ev_future" for item in payload["result"]["events"])
    get_settings.cache_clear()


def test_choice_events_latest_no_duckdb_file_returns_empty_envelope(
    tmp_path, monkeypatch
) -> None:
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
    assert body["result"]["payload_json_included"] is True
    assert body["result"]["events"] == []
    assert body["result"]["total_rows"] == 0
    get_settings.cache_clear()


def test_choice_events_latest_no_duckdb_file_compact_mode_returns_empty_envelope(tmp_path, monkeypatch) -> None:
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
    response = client.get("/ui/news/choice-events/latest", params={"include_payload_json": "false"})
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["payload_json_included"] is False
    assert body["result"]["events"] == []
    assert body["result"]["total_rows"] == 0
    get_settings.cache_clear()


def test_choice_events_latest_forbidden_without_read_grant(
    tmp_path, monkeypatch
) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch, grant_read=False)
    response = client.get("/ui/news/choice-events/latest")
    assert response.status_code == 403
    get_settings.cache_clear()


def test_choice_events_latest_topic_code_param_filters(tmp_path, monkeypatch) -> None:
    _seed_choice_news_topics(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/news/choice-events/latest", params={"topic_code": "TOPIC_FILTER_A"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["total_rows"] == 1
    assert len(body["result"]["events"]) == 1
    assert body["result"]["events"][0]["topic_code"] == "TOPIC_FILTER_A"
    assert "alpha" in body["result"]["events"][0]["payload_text"]
    get_settings.cache_clear()


def test_choice_events_latest_returns_deterministic_research_compare(
    tmp_path, monkeypatch
) -> None:
    _seed_choice_news_topics(tmp_path)
    _append_research_radar_events(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)

    first = client.get(
        "/ui/news/choice-events/latest", params={"limit": 10, "offset": 0}
    )
    second = client.get(
        "/ui/news/choice-events/latest", params={"limit": 10, "offset": 0}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_compare = first.json()["result"]["compare"]
    second_compare = second.json()["result"]["compare"]
    assert first_compare == second_compare
    assert set(first_compare) >= {
        "same_direction",
        "conflicting",
        "review_needed",
        "candidate_scenarios",
    }
    assert all(
        row["human_review_required"] is True
        for row in first_compare["candidate_scenarios"]
    )
    get_settings.cache_clear()


def test_choice_events_latest_stock_code_filters_payload_text_and_json(
    tmp_path, monkeypatch
) -> None:
    _seed_choice_news_topics(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/news/choice-events/latest", params={"stock_code": "000001.SZ", "limit": 10}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["stock_code"] == "000001.SZ"
    assert body["result"]["stock_filter_mode"] == "payload_text_or_json_best_effort"
    assert body["result"]["stock_filter_tokens"] == ["000001.SZ", "000001"]
    assert body["result"]["payload_json_included"] is True
    assert body["result"]["total_rows"] == 2
    assert [event["topic_code"] for event in body["result"]["events"]] == [
        "TOPIC_STOCK_STEM",
        "TOPIC_STOCK_FULL",
    ]
    assert body["result"]["events"][0]["payload_json"] is not None
    get_settings.cache_clear()


def test_choice_events_latest_compact_returns_whitelisted_display_text(
    tmp_path,
    monkeypatch,
) -> None:
    _seed_choice_news_topics(tmp_path)
    path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute(
            """
            insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "ev_structured_only",
                "2026-05-08T13:30:00Z",
                "g1",
                "sectornews",
                8,
                1,
                0,
                "",
                "TOPIC_STRUCTURED_ONLY",
                0,
                None,
                '{"headline":"Policy follow-up","summary":"PBOC commentary"}',
            ],
        )
    finally:
        conn.close()

    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/news/choice-events/latest",
        params={
            "topic_code": "TOPIC_STRUCTURED_ONLY",
            "include_payload_json": False,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["payload_json_included"] is False
    assert result["events"][0]["payload_json"] is None
    assert result["events"][0]["payload_text"] is None
    assert result["events"][0]["display_text"] == "Policy follow-up - PBOC commentary"
    get_settings.cache_clear()


def test_choice_events_latest_visible_text_compact_excludes_json_only_match(
    tmp_path,
    monkeypatch,
) -> None:
    _seed_choice_news_topics(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/news/choice-events/latest",
        params={
            "stock_code": "000001.SZ",
            "stock_match_mode": "visible_text",
            "include_payload_json": False,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["stock_code"] == "000001.SZ"
    assert result["stock_filter_mode"] == "payload_text_only_strict_visible_text"
    assert result["stock_filter_tokens"] == ["000001.SZ", "000001"]
    assert result["payload_json_included"] is False
    assert result["total_rows"] == 1
    assert [event["topic_code"] for event in result["events"]] == ["TOPIC_STOCK_FULL"]
    assert all(event["payload_json"] is None for event in result["events"])
    assert all(
        any(
            token in str(event["payload_text"] or "").upper()
            for token in result["stock_filter_tokens"]
        )
        for event in result["events"]
    )

    disclosed_sql = choice_news_latest_sql_disclosure(
        stock_code="000001.SZ",
        stock_match_mode="visible_text",
        include_payload_json=False,
    )[0].lower()
    assert "cast(null as varchar) as payload_json" in disclosed_sql
    assert "upper(coalesce(payload_json" not in disclosed_sql
    get_settings.cache_clear()


def test_choice_events_latest_stock_name_alias_recovers_visible_name_only_match(
    tmp_path,
    monkeypatch,
) -> None:
    _seed_choice_news_topics(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)

    response = client.get(
        "/ui/news/choice-events/latest",
        params={
            "stock_code": "000001.SZ",
            "stock_name": "  Ping An Bank  ",
            "stock_match_mode": "visible_text",
            "include_payload_json": False,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["stock_filter_tokens"] == ["000001.SZ", "000001", "PING AN BANK"]
    assert result["total_rows"] == 2
    assert [event["topic_code"] for event in result["events"]] == [
        "TOPIC_STOCK_NAME",
        "TOPIC_STOCK_FULL",
    ]
    assert "TOPIC_STOCK_STEM" not in {event["topic_code"] for event in result["events"]}
    assert all(event["payload_json"] is None for event in result["events"])

    wildcard_response = client.get(
        "/ui/news/choice-events/latest",
        params={
            "stock_code": "000001.SZ",
            "stock_name": "%_",
            "stock_match_mode": "visible_text",
            "include_payload_json": False,
            "limit": 10,
        },
    )
    assert wildcard_response.status_code == 200
    wildcard_result = wildcard_response.json()["result"]
    assert wildcard_result["stock_filter_tokens"] == ["000001.SZ", "000001", "%_"]
    assert [event["topic_code"] for event in wildcard_result["events"]] == [
        "TOPIC_STOCK_FULL"
    ]

    alias_only_response = client.get(
        "/ui/news/choice-events/latest",
        params={"stock_name": "Ping An Bank"},
    )
    assert alias_only_response.status_code == 400
    get_settings.cache_clear()


def test_choice_events_latest_stock_code_returns_empty_without_global_fallback(
    tmp_path, monkeypatch
) -> None:
    _seed_choice_news_topics(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/news/choice-events/latest", params={"stock_code": "000999.SZ"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["stock_code"] == "000999.SZ"
    assert body["result"]["events"] == []
    assert body["result"]["total_rows"] == 0
    get_settings.cache_clear()


def test_choice_events_latest_rejects_invalid_stock_code(tmp_path, monkeypatch) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/news/choice-events/latest", params={"stock_code": "bad code!"}
    )
    assert response.status_code == 400
    assert "Invalid stock_code" in response.json()["detail"]
    get_settings.cache_clear()


def test_choice_events_latest_rejects_invalid_stock_match_mode(
    tmp_path, monkeypatch
) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.get(
        "/ui/news/choice-events/latest",
        params={"stock_match_mode": "payload_json"},
    )
    assert response.status_code == 422
    get_settings.cache_clear()


def test_tushare_npr_ingest_ui_still_503_reserved(tmp_path, monkeypatch) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch)
    response = client.post("/ui/news/tushare-npr/ingest", params={"limit": 5})
    assert response.status_code == 503
    detail = str(response.json().get("detail", "")).lower()
    assert "reserved" in detail
    get_settings.cache_clear()
