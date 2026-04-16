from __future__ import annotations

import sys
from collections.abc import Mapping

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


def test_choice_news_service_received_to_invokes_temporal_guard(tmp_path, monkeypatch):
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
    service_module = load_module(
        "backend.app.services.choice_news_service",
        "backend/app/services/choice_news_service.py",
    )

    repo = governance_module.GovernanceRepository(base_dir=tmp_path / "governance")
    _append_choice_news_events(repo)
    task_module.materialize_choice_news_events.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    observed: dict[str, object] = {}
    original = service_module.filter_rows_as_of

    def _spy_filter_rows_as_of(*, rows, contract, as_of_date):
        observed["called"] = True
        observed["row_count"] = len(rows)
        observed["as_of_date"] = as_of_date
        observed["dataset_name"] = contract.dataset_name
        observed["published_at_field"] = contract.published_at_field
        observed["effective_from_field"] = contract.effective_from_field
        observed["effective_to_field"] = contract.effective_to_field
        return original(rows=rows, contract=contract, as_of_date=as_of_date)

    monkeypatch.setattr(service_module, "filter_rows_as_of", _spy_filter_rows_as_of)

    payload = service_module.choice_news_latest_envelope(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        received_to="2026-04-10T10:21:00Z",
    )

    assert observed == {
        "called": True,
        "row_count": 3,
        "as_of_date": "2026-04-10T10:21:00Z",
        "dataset_name": "choice_news_event",
        "published_at_field": "received_at",
        "effective_from_field": "received_at",
        "effective_to_field": None,
    }
    assert payload["result"]["total_rows"] == 2
    assert [row["topic_code"] for row in payload["result"]["events"]] == ["S888010007API", "C000022"]
    get_settings.cache_clear()


def test_choice_news_latest_api_fails_closed_when_received_at_is_missing(tmp_path, monkeypatch):
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
    repo.append(
        "choice_news_event",
        {
            "received_at": None,
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
    task_module.materialize_choice_news_events.fn(
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
    )

    main_module = load_module("backend.app.main", "backend/app/main.py")
    client = TestClient(main_module.app)
    response = client.get(
        "/ui/news/choice-events/latest",
        params={"received_to": "2026-04-10T10:21:00Z"},
    )

    assert response.status_code == 503
    assert "received_at" in response.json()["detail"]
    get_settings.cache_clear()


def test_choice_news_latest_envelope_marks_missing_storage_as_warning(tmp_path):
    service_module = load_module(
        "backend.app.services.choice_news_service",
        "backend/app/services/choice_news_service.py",
    )

    payload = service_module.choice_news_latest_envelope(
        duckdb_path=str(tmp_path / "missing.duckdb"),
    )

    assert payload["result_meta"]["result_kind"] == "news.choice.latest"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert payload["result"]["total_rows"] == 0
    assert payload["result"]["events"] == []


def test_choice_news_latest_envelope_keeps_ok_for_filtered_empty_result(tmp_path, monkeypatch):
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
    service_module = load_module(
        "backend.app.services.choice_news_service",
        "backend/app/services/choice_news_service.py",
    )

    repo = governance_module.GovernanceRepository(base_dir=tmp_path / "governance")
    _append_choice_news_events(repo)
    duckdb_path = tmp_path / "moss.duckdb"
    task_module.materialize_choice_news_events.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(tmp_path / "governance"),
    )

    payload = service_module.choice_news_latest_envelope(
        duckdb_path=str(duckdb_path),
        topic_code="NO_MATCH_TOPIC",
    )

    assert payload["result_meta"]["quality_flag"] == "ok"
    assert payload["result_meta"]["vendor_status"] == "ok"
    assert payload["result"]["total_rows"] == 0
    assert payload["result"]["events"] == []
