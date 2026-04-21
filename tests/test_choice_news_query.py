from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _append_choice_news_events(repo) -> None:
    repo.append(
        "choice_news_event",
        {
            "received_at": "2026-04-10T10:20:00Z",
            "group_id": "news_cmd1",
            "content_type": "sectornews",
            "serial_id": 1,
            "request_id": 10002,
            "error_code": 0,
            "error_msg": "success",
            "topic_code": "C000022",
            "item_index": 0,
            "payload_text": "headline-a",
            "payload_json": None,
        },
    )
    repo.append(
        "choice_news_event",
        {
            "received_at": "2026-04-10T10:21:00Z",
            "group_id": "news_cmd1",
            "content_type": "sectornews",
            "serial_id": 2,
            "request_id": 10002,
            "error_code": 0,
            "error_msg": "success",
            "topic_code": "S888010007API",
            "item_index": 0,
            "payload_text": None,
            "payload_json": "{\"title\":\"macro-data\"}",
        },
    )
    repo.append(
        "choice_news_event",
        {
            "received_at": "2026-04-10T10:22:00Z",
            "group_id": "news_cmd2",
            "content_type": "sectornews",
            "serial_id": 3,
            "request_id": 10002,
            "error_code": 10003013,
            "error_msg": "subscription limit",
            "topic_code": "__callback__",
            "item_index": -1,
            "payload_text": None,
            "payload_json": None,
        },
    )


def test_choice_news_materialize_task_builds_duckdb_event_table(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    governance_dir = tmp_path / "governance"
    duckdb_path = tmp_path / "moss.duckdb"
    repo = governance_module.GovernanceRepository(base_dir=governance_dir)
    _append_choice_news_events(repo)

    payload = task_module.materialize_choice_news_events.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["event_count"] == 3
    assert payload["inserted_count"] == 3

    import duckdb

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        rows = conn.execute(
            """
            select topic_code, payload_text, payload_json, event_key
            from choice_news_event
            order by received_at
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows[0][:3] == ("C000022", "headline-a", None)
    assert rows[1][:3] == ("S888010007API", None, "{\"title\":\"macro-data\"}")
    assert rows[2][:3] == ("__callback__", None, None)
    assert all(row[3] for row in rows)


def test_choice_news_materialize_is_incremental_and_dedupes_by_event_key(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    governance_dir = tmp_path / "governance"
    duckdb_path = tmp_path / "moss.duckdb"
    repo = governance_module.GovernanceRepository(base_dir=governance_dir)

    base_event = {
        "received_at": "2026-04-10T10:20:00Z",
        "group_id": "news_cmd1",
        "content_type": "sectornews",
        "serial_id": 1,
        "request_id": 10002,
        "error_code": 0,
        "error_msg": "success",
        "topic_code": "C000022",
        "item_index": 0,
        "payload_text": "headline-a",
        "payload_json": None,
    }
    repo.append("choice_news_event", base_event)
    repo.append(
        "choice_news_event",
        {
            **base_event,
            "received_at": "2026-04-10T10:25:00Z",
            "serial_id": 9,
        },
    )

    first = task_module.materialize_choice_news_events.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    assert first["event_count"] == 1
    assert first["inserted_count"] == 1

    repo.append(
        "choice_news_event",
        {
            "received_at": "2026-04-10T10:30:00Z",
            "group_id": "news_cmd1",
            "content_type": "sectornews",
            "serial_id": 2,
            "request_id": 10002,
            "error_code": 0,
            "error_msg": "success",
            "topic_code": "S888010007API",
            "item_index": 0,
            "payload_text": None,
            "payload_json": "{\"title\":\"macro-data\"}",
        },
    )

    second = task_module.materialize_choice_news_events.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    assert second["event_count"] == 2
    assert second["inserted_count"] == 1


def test_choice_news_pull_snapshot_fetches_recent_sectornews_and_materializes(tmp_path, monkeypatch):
    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    governance_dir = tmp_path / "governance"
    duckdb_path = tmp_path / "moss.duckdb"
    topics_file = tmp_path / "choice_news_topics.json"
    topics_file.write_text(
        """
        {
          "catalog_version": "2026-04-10.choice-news.v1",
          "vendor_name": "choice",
          "generated_at": "2026-04-10T18:10:00+08:00",
          "generated_from": "tests.fixture.choice_news_topics",
          "subscription_mode": "cnq",
          "content_type": "sectornews",
          "callback_name": "cnqCallback",
          "groups": [
            {
              "group_id": "news_cmd1",
              "group_name": "core-news",
              "is_core": true,
              "tags": ["choice", "news"],
              "topics": [
                {"topic_code": "C000022", "topic_name": "热门资讯"}
              ]
            }
          ]
        }
        """.strip(),
        encoding="utf-8",
    )

    class FakeCfnResult:
        ErrorCode = 0
        ErrorMsg = "success"
        SerialID = 0
        RequestID = 7001
        Indicators = [
            "DATETIME",
            "EITIME",
            "CODE",
            "CONTENT",
            "TITLE",
            "INFOCODE",
            "MEDIANAME",
            "URL",
            "TYPE",
            "LABEL",
        ]
        Data = {
            "C000022": [
                [
                    "2026-04-20 20:35:01",
                    "2026-04-20 20:43:30",
                    "C000022",
                    "sectornews",
                    "headline-a",
                    "NW1",
                    "Choice",
                    "https://example.com/a",
                    "未判断",
                    "无事件标签",
                ],
                [
                    "2026-04-20 19:50:13",
                    "2026-04-20 19:50:40",
                    "C000022",
                    "sectornews",
                    "headline-b",
                    "NW2",
                    "Choice",
                    "https://example.com/b",
                    "未判断",
                    "无事件标签",
                ],
            ]
        }

    observed: dict[str, object] = {}

    class FakeChoiceClient:
        def cfn(self, codes, content, mode, options=""):
            observed["codes"] = codes
            observed["content"] = content
            observed["mode"] = mode
            observed["options"] = options
            return FakeCfnResult()

    monkeypatch.setattr(task_module, "_init_runtime", lambda: None)
    monkeypatch.setattr(task_module, "ChoiceClient", lambda: FakeChoiceClient())

    payload = task_module.pull_choice_sectornews_snapshot.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        topics_file=str(topics_file),
        count=2,
    )

    assert payload["status"] == "completed"
    assert payload["fetched_row_count"] == 2
    assert payload["inserted_count"] == 2
    assert payload["materialize"]["inserted_count"] == 2
    assert observed == {
        "codes": "C000022",
        "content": "sectornews",
        "mode": 2,
        "options": "count=2,Ispandas=1,RECVtimeout=5",
    }

    repo = governance_module.GovernanceRepository(base_dir=governance_dir)
    rows = repo.read_all(task_module.CHOICE_NEWS_EVENT_STREAM)
    assert len(rows) == 2
    assert rows[0]["topic_code"] == "C000022"
    assert rows[0]["payload_text"] == "headline-a"
    assert "\"INFOCODE\":\"NW1\"" in rows[0]["payload_json"]

    import duckdb

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        db_rows = conn.execute(
            "select topic_code, payload_text from choice_news_event order by payload_text"
        ).fetchall()
    finally:
        conn.close()

    assert db_rows == [("C000022", "headline-a"), ("C000022", "headline-b")]


def test_choice_news_latest_api_returns_result_meta_and_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    repo = governance_module.GovernanceRepository(base_dir=tmp_path / "governance")
    _append_choice_news_events(repo)
    task_module.materialize_choice_news_events.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get("/ui/news/choice-events/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["result_kind"] == "news.choice.latest"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert len(payload["result"]["events"]) == 3
    assert payload["result"]["events"][0]["topic_code"] == "__callback__"
    get_settings.cache_clear()


def test_choice_news_latest_api_supports_pagination_and_group_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    repo = governance_module.GovernanceRepository(base_dir=tmp_path / "governance")
    _append_choice_news_events(repo)
    task_module.materialize_choice_news_events.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    page = client.get("/ui/news/choice-events/latest", params={"limit": 1, "offset": 1, "group_id": "news_cmd1"})
    assert page.status_code == 200
    payload = page.json()
    assert payload["result"]["total_rows"] == 2
    assert payload["result"]["limit"] == 1
    assert payload["result"]["offset"] == 1
    assert len(payload["result"]["events"]) == 1
    assert payload["result"]["events"][0]["topic_code"] == "C000022"
    get_settings.cache_clear()


def test_choice_news_latest_api_supports_topic_time_and_error_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )
    governance_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    repo = governance_module.GovernanceRepository(base_dir=tmp_path / "governance")
    _append_choice_news_events(repo)
    task_module.materialize_choice_news_events.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)

    by_topic = client.get(
        "/ui/news/choice-events/latest",
        params={"topic_code": "S888010007API", "received_from": "2026-04-10T10:20:30Z"},
    )
    assert by_topic.status_code == 200
    topic_payload = by_topic.json()
    assert topic_payload["result"]["total_rows"] == 1
    assert topic_payload["result"]["events"][0]["topic_code"] == "S888010007API"

    only_errors = client.get(
        "/ui/news/choice-events/latest",
        params={"error_only": True},
    )
    assert only_errors.status_code == 200
    error_payload = only_errors.json()
    assert error_payload["result"]["total_rows"] == 1
    assert error_payload["result"]["events"][0]["error_code"] == 10003013
    assert error_payload["result"]["events"][0]["topic_code"] == "__callback__"
    get_settings.cache_clear()
