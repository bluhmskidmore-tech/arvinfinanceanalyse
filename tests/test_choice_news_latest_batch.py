"""`/ui/news/choice-events/latest-batch` 契约测试：批量结果必须与逐个单查逐字段一致。"""
from __future__ import annotations

import duckdb

from backend.app.governance.settings import get_settings
from tests.test_choice_news_routes import _choice_news_read_client

import pytest

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_choice_news,
]

_BATCH_PATH = "/ui/news/choice-events/latest-batch"
_SINGLE_PATH = "/ui/news/choice-events/latest"

def _seed_choice_news_batch_events(tmp_path) -> None:
    conn = duckdb.connect(str(tmp_path / "moss.duckdb"), read_only=False)
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
            "insert into choice_news_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("ev_a1", "2026-05-08T09:00:00Z", "g1", "sectornews", 1, 1, 0, "", "TOPIC_A", 0, "topic a oldest", None),
                ("ev_a2", "2026-05-08T10:00:00Z", "g1", "sectornews", 2, 1, 0, "", "TOPIC_A", 0, "topic a middle", None),
                (
                    "ev_a3",
                    "2026-05-08T11:00:00Z",
                    "g1",
                    "sectornews",
                    3,
                    1,
                    0,
                    "",
                    "TOPIC_A",
                    0,
                    None,
                    '{"headline":"Topic A headline","summary":"Topic A summary"}',
                ),
                ("ev_b1", "2026-05-08T09:30:00Z", "g1", "sectornews", 4, 1, 0, "", "TOPIC_B", 0, "topic b oldest", None),
                ("ev_b2", "2026-05-08T12:00:00Z", "g1", "sectornews", 5, 1, 0, "", "TOPIC_B", 0, "topic b newest", None),
                ("ev_c1", "2026-05-08T10:30:00Z", "g2", "sectornews", 6, 1, 0, "", "TOPIC_C", 0, "group two first", None),
                ("ev_c2", "2026-05-08T13:00:00Z", "g2", "sectornews", 7, 1, 0, "", "TOPIC_C", 0, "group two newest", None),
                ("ev_d1", "2026-05-08T08:00:00Z", "g2", "sectornews", 8, 1, 0, "", "TOPIC_D", 0, "group two oldest", None),
                ("ev_future_a", "2099-01-01T00:00:00+08:00", "g1", "sectornews", 9, 1, 0, "", "TOPIC_A", 0, "future dated", None),
            ],
        )
    finally:
        conn.close()

def _single_events(client, *, topic_code: str | None = None, group_id: str | None = None, limit: int) -> list[dict]:
    params: dict[str, object] = {"limit": limit, "offset": 0, "include_payload_json": True}
    if topic_code is not None:
        params["topic_code"] = topic_code
    if group_id is not None:
        params["group_id"] = group_id
    response = client.get(_SINGLE_PATH, params=params)
    assert response.status_code == 200
    return response.json()["result"]["events"]

def test_latest_batch_matches_individual_single_queries_field_by_field(tmp_path, monkeypatch) -> None:
    _seed_choice_news_batch_events(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)

    response = client.get(
        _BATCH_PATH,
        params={"topics": "TOPIC_A:2,TOPIC_B:5", "groups": "g2:3"},
    )

    assert response.status_code == 200
    payload = response.json()
    batches = payload["result"]["batches"]
    assert [batch["key"] for batch in batches] == ["topic:TOPIC_A", "topic:TOPIC_B", "group:g2"]
    assert [batch["topic_code"] for batch in batches] == ["TOPIC_A", "TOPIC_B", None]
    assert [batch["group_id"] for batch in batches] == [None, None, "g2"]
    assert all(set(batch.keys()) == {"key", "topic_code", "group_id", "events"} for batch in batches)

    # 逐字段与单查端点比较（同一 fixture DuckDB）。
    assert batches[0]["events"] == _single_events(client, topic_code="TOPIC_A", limit=2)
    assert batches[1]["events"] == _single_events(client, topic_code="TOPIC_B", limit=5)
    assert batches[2]["events"] == _single_events(client, group_id="g2", limit=3)

    assert len(batches[0]["events"]) == 2
    assert [event["event_key"] for event in batches[0]["events"]] == ["ev_a3", "ev_a2"]
    assert batches[0]["events"][0]["display_text"] == "Topic A headline - Topic A summary"
    assert batches[0]["events"][0]["payload_json"] is not None
    assert [event["event_key"] for event in batches[1]["events"]] == ["ev_b2", "ev_b1"]
    assert [event["event_key"] for event in batches[2]["events"]] == ["ev_c2", "ev_c1", "ev_d1"]

    meta = payload["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["result_kind"] == "news.choice.latest_batch"
    assert meta["source_surface"] == "choice_news"
    assert meta["tables_used"] == ["choice_news_event"]
    assert meta["quality_flag"] == "warning"
    assert meta["filters_applied"]["future_rows_excluded"] == 1
    assert all(event["event_key"] != "ev_future_a" for event in batches[0]["events"])
    get_settings.cache_clear()

def test_latest_batch_applies_per_entry_limit(tmp_path, monkeypatch) -> None:
    _seed_choice_news_batch_events(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)

    response = client.get(_BATCH_PATH, params={"topics": "TOPIC_A:1", "groups": "g2:2"})

    assert response.status_code == 200
    batches = response.json()["result"]["batches"]
    assert [event["event_key"] for event in batches[0]["events"]] == ["ev_a3"]
    assert [event["event_key"] for event in batches[1]["events"]] == ["ev_c2", "ev_c1"]
    assert batches[0]["events"] == _single_events(client, topic_code="TOPIC_A", limit=1)
    assert batches[1]["events"] == _single_events(client, group_id="g2", limit=2)
    get_settings.cache_clear()

def test_latest_batch_unknown_topic_returns_empty_events(tmp_path, monkeypatch) -> None:
    _seed_choice_news_batch_events(tmp_path)
    client = _choice_news_read_client(tmp_path, monkeypatch)

    response = client.get(_BATCH_PATH, params={"topics": "TOPIC_MISSING:4"})

    assert response.status_code == 200
    batches = response.json()["result"]["batches"]
    assert batches[0]["key"] == "topic:TOPIC_MISSING"
    assert batches[0]["events"] == []
    assert batches[0]["events"] == _single_events(client, topic_code="TOPIC_MISSING", limit=4)
    get_settings.cache_clear()

def test_latest_batch_forbidden_without_read_grant(tmp_path, monkeypatch) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch, grant_read=False)
    response = client.get(_BATCH_PATH, params={"topics": "TOPIC_A:2"})
    assert response.status_code == 403
    get_settings.cache_clear()

def test_latest_batch_rejects_invalid_entry_formats(tmp_path, monkeypatch) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch)
    invalid_params = [
        {"topics": "TOPIC_A"},
        {"topics": "TOPIC_A:abc"},
        {"topics": "TOPIC_A:0"},
        {"topics": "TOPIC_A:501"},
        {"topics": ":5"},
        {"topics": "TOPIC_A:"},
        {"groups": "g1"},
        {"groups": "g1:-1"},
    ]
    for params in invalid_params:
        response = client.get(_BATCH_PATH, params=params)
        assert response.status_code == 400, f"{params} -> {response.status_code} {response.text}"
        assert "Invalid" in response.json()["detail"]
    get_settings.cache_clear()

def test_latest_batch_rejects_more_than_sixteen_entries(tmp_path, monkeypatch) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch)

    sixteen = client.get(
        _BATCH_PATH,
        params={
            "topics": ",".join(f"T{i}:1" for i in range(8)),
            "groups": ",".join(f"G{i}:1" for i in range(8)),
        },
    )
    assert sixteen.status_code == 200
    assert len(sixteen.json()["result"]["batches"]) == 16

    seventeen = client.get(
        _BATCH_PATH,
        params={
            "topics": ",".join(f"T{i}:1" for i in range(9)),
            "groups": ",".join(f"G{i}:1" for i in range(8)),
        },
    )
    assert seventeen.status_code == 400
    assert "Too many batch entries" in seventeen.json()["detail"]
    get_settings.cache_clear()

def test_latest_batch_requires_topics_or_groups(tmp_path, monkeypatch) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch)
    for params in ({}, {"topics": "", "groups": ""}, {"topics": "  "}, {"topics": ","}):
        response = client.get(_BATCH_PATH, params=params)
        assert response.status_code == 400, f"{params} -> {response.status_code} {response.text}"
    get_settings.cache_clear()

def test_latest_batch_missing_duckdb_returns_empty_batches(tmp_path, monkeypatch) -> None:
    client = _choice_news_read_client(tmp_path, monkeypatch)

    response = client.get(_BATCH_PATH, params={"topics": "TOPIC_A:2", "groups": "g2:3"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert payload["result_meta"]["quality_flag"] == "warning"
    batches = payload["result"]["batches"]
    assert [batch["key"] for batch in batches] == ["topic:TOPIC_A", "group:g2"]
    assert all(batch["events"] == [] for batch in batches)
    get_settings.cache_clear()
