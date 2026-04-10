from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def _write_choice_news_topics(path: Path) -> None:
    path.write_text(
        json.dumps(
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
                        "is_core": True,
                        "tags": ["choice", "news", "macro"],
                        "topics": [
                            {"topic_code": "C000022", "topic_name": "热门资讯"},
                            {"topic_code": "S888010007API", "topic_name": "经济数据"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_choice_client_cnq_and_cancel_wrap_sdk_calls(tmp_path, monkeypatch):
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )
    client_module = load_module(
        "backend.app.repositories.choice_client",
        "backend/app/repositories/choice_client.py",
    )

    em_parent = tmp_path / "EMQuantAPI_Python" / "python3"
    package_dir = em_parent / "EmQuantAPI"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "c.py").write_text(
        "\n".join(
            [
                "calls = []",
                "class Result:",
                "    def __init__(self, code=0, msg='success', serial=0):",
                "        self.ErrorCode = code",
                "        self.ErrorMsg = msg",
                "        self.SerialID = serial",
                "def start(options, *args, **kwargs):",
                "    calls.append(('start', options))",
                "    return Result()",
                "def cnq(codes, content, options='', callback=None, userparams=None):",
                "    calls.append(('cnq', codes, content, options, callback is not None))",
                "    return Result(0, 'success', 4321)",
                "def cnqcancel(serial_id):",
                "    calls.append(('cnqcancel', serial_id))",
                "    return Result()",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CHOICE_EMQUANT_PARENT", str(em_parent))
    monkeypatch.setenv("CHOICE_MACRO_CHOICE_START_OPTIONS", "UserName=demo,PassWord=demo,ForceLogin=1")
    settings = runtime_module.AppSettings(
        choice_emquant_parent=str(em_parent),
        choice_start_options="UserName=demo,PassWord=demo,ForceLogin=1",
        choice_request_options="Ispandas=1,RECVtimeout=5",
        log_level="INFO",
        log_path="",
    )

    client = client_module.ChoiceClient(settings=settings)
    result = client.cnq("C000022,S888010007API", "sectornews")
    cancel = client.cnqcancel(result.SerialID)
    cmod = runtime_module._get_em_c()

    assert result.SerialID == 4321
    assert cmod.calls[0][0] == "start"
    assert cmod.calls[1][:4] == ("cnq", "C000022,S888010007API", "sectornews", "Ispandas=1,RECVtimeout=5")
    assert cmod.calls[2] == ("cnqcancel", 4321)
    assert cancel.ErrorCode == 0


def test_choice_news_topics_loader_reads_structured_asset(tmp_path):
    task_module = load_module(
        "backend.app.tasks.choice_news",
        "backend/app/tasks/choice_news.py",
    )

    asset_file = tmp_path / "choice_news_topics.json"
    _write_choice_news_topics(asset_file)

    asset = task_module.load_choice_news_topics(asset_file)

    assert asset.catalog_version == "2026-04-10.choice-news.v1"
    assert asset.content_type == "sectornews"
    assert asset.groups[0].group_id == "news_cmd1"
    assert asset.groups[0].topics[0].topic_code == "C000022"
    assert asset.groups[0].topics[0].topic_name == "热门资讯"


def test_subscribe_choice_sectornews_uses_structured_topics_asset(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    topics_file = tmp_path / "choice_news_topics.json"
    _write_choice_news_topics(topics_file)
    monkeypatch.setenv("MOSS_CHOICE_NEWS_TOPICS_FILE", str(topics_file))
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )

    observed: dict[str, object] = {}

    class FakeResult:
        ErrorCode = 0
        ErrorMsg = "success"
        SerialID = 7788

    class FakeChoiceClient:
        def cnq(self, codes: str, content: str, options: str = "", callback=None, userparams=None):
            observed["codes"] = codes
            observed["content"] = content
            observed["options"] = options
            return FakeResult()

        def cnqcancel(self, serial_id: int):
            observed["cancel_serial_id"] = serial_id
            return FakeResult()

    monkeypatch.setattr(task_module, "_init_runtime", lambda: observed.setdefault("init_runtime", True))
    monkeypatch.setattr(task_module, "ChoiceClient", lambda: FakeChoiceClient())

    payload = task_module.subscribe_choice_sectornews.fn(governance_dir=str(tmp_path / "governance"))

    assert observed["init_runtime"] is True
    expected_codes = "C000022,S888010007API"
    assert observed["codes"].startswith(expected_codes)
    assert observed["content"] == "sectornews"
    assert observed["cancel_serial_id"] == 7788
    assert payload["status"] == "completed"
    assert payload["subscription_count"] == 1
    assert payload["subscriptions"][0]["serial_id"] == 7788
    get_settings.cache_clear()


def test_subscribe_choice_sectornews_chunks_large_group_by_vendor_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    topics_file = tmp_path / "choice_news_topics.json"
    topics_file.write_text(
        json.dumps(
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
                        "is_core": True,
                        "tags": ["choice", "news"],
                        "topics": [
                            {"topic_code": "T1", "topic_name": "n1"},
                            {"topic_code": "T2", "topic_name": "n2"},
                            {"topic_code": "T3", "topic_name": "n3"},
                            {"topic_code": "T4", "topic_name": "n4"},
                            {"topic_code": "T5", "topic_name": "n5"},
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOSS_CHOICE_NEWS_TOPICS_FILE", str(topics_file))
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )

    observed_calls: list[tuple[str, str]] = []
    canceled: list[int] = []

    class FakeResult:
        ErrorCode = 0
        ErrorMsg = "success"

        def __init__(self, serial_id: int):
            self.SerialID = serial_id

    class FakeChoiceClient:
        def __init__(self):
            self._serial = 100

        def cnq(self, codes: str, content: str, options: str = "", callback=None, userparams=None):
            observed_calls.append((codes, content))
            self._serial += 1
            return FakeResult(self._serial)

        def cnqcancel(self, serial_id: int):
            canceled.append(serial_id)
            return FakeResult(serial_id)

    monkeypatch.setattr(task_module, "_init_runtime", lambda: None)
    monkeypatch.setattr(task_module, "ChoiceClient", lambda: FakeChoiceClient())

    payload = task_module.subscribe_choice_sectornews.fn(governance_dir=str(tmp_path / "governance"))

    assert observed_calls == [
        ("T1,T2,T3,T4", "sectornews"),
        ("T5", "sectornews"),
    ]
    assert canceled == [101, 102]
    assert payload["subscription_count"] == 2
    get_settings.cache_clear()


def test_choice_news_callback_appends_event_records_to_governance(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )
    repo_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    repo = repo_module.GovernanceRepository(base_dir=tmp_path / "governance")
    callback = task_module.build_choice_news_callback(
        repo=repo,
        group_id="news_cmd1",
        content_type="sectornews",
        serial_id=4321,
    )

    class FakeQuantData:
        ErrorCode = 0
        ErrorMsg = "success"
        RequestID = 10002
        SerialID = 4321
        Data = {
            "C000022": ["headline-a", "headline-b"],
            "S888010007API": [{"title": "macro-data"}],
        }

    result = callback(FakeQuantData())
    rows = repo.read_all(task_module.CHOICE_NEWS_EVENT_STREAM)

    assert result == 1
    assert len(rows) == 3
    assert rows[0]["event_key"]
    assert rows[0]["group_id"] == "news_cmd1"
    assert rows[0]["content_type"] == "sectornews"
    assert rows[0]["serial_id"] == 4321
    assert rows[0]["topic_code"] == "C000022"
    assert rows[0]["item_index"] == 0
    assert rows[0]["payload_text"] == "headline-a"
    assert rows[2]["payload_json"] == "{\"title\":\"macro-data\"}"


def test_subscribe_choice_sectornews_passes_callback_and_persists_callback_events(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    topics_file = tmp_path / "choice_news_topics.json"
    _write_choice_news_topics(topics_file)
    monkeypatch.setenv("MOSS_CHOICE_NEWS_TOPICS_FILE", str(topics_file))
    get_settings.cache_clear()

    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )
    repo_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    class FakeResult:
        ErrorCode = 0
        ErrorMsg = "success"
        SerialID = 7788

    class FakeChoiceClient:
        def cnq(self, codes: str, content: str, options: str = "", callback=None, userparams=None):
            callback(
                type(
                    "FakeQuantData",
                    (),
                    {
                        "ErrorCode": 0,
                        "ErrorMsg": "success",
                        "RequestID": 10002,
                        "SerialID": 7788,
                        "Data": {"C000022": ["headline-a"]},
                    },
                )()
            )
            return FakeResult()

        def cnqcancel(self, serial_id: int):
            return FakeResult()

    monkeypatch.setattr(task_module, "_init_runtime", lambda: None)
    monkeypatch.setattr(task_module, "ChoiceClient", lambda: FakeChoiceClient())

    payload = task_module.subscribe_choice_sectornews.fn(governance_dir=str(tmp_path / "governance"))
    rows = repo_module.GovernanceRepository(base_dir=tmp_path / "governance").read_all(task_module.CHOICE_NEWS_EVENT_STREAM)

    assert payload["status"] == "completed"
    assert payload["subscriptions"][0]["serial_id"] == 7788
    assert rows[0]["topic_code"] == "C000022"
    assert rows[0]["payload_text"] == "headline-a"
    get_settings.cache_clear()


def test_choice_news_callback_persists_error_envelope_even_without_data(tmp_path):
    task_module = sys.modules.get("backend.app.tasks.choice_news")
    if task_module is None:
        task_module = load_module(
            "backend.app.tasks.choice_news",
            "backend/app/tasks/choice_news.py",
        )
    repo_module = load_module(
        "backend.app.repositories.governance_repo",
        "backend/app/repositories/governance_repo.py",
    )

    repo = repo_module.GovernanceRepository(base_dir=tmp_path / "governance")
    callback = task_module.build_choice_news_callback(
        repo=repo,
        group_id="news_cmd1",
        content_type="sectornews",
        serial_id=8888,
    )

    class FakeQuantData:
        ErrorCode = 10003013
        ErrorMsg = "subscription limit"
        RequestID = 10002
        SerialID = 8888
        Data = {}

    result = callback(FakeQuantData())
    rows = repo.read_all(task_module.CHOICE_NEWS_EVENT_STREAM)

    assert result == 1
    assert rows == [
        {
            "received_at": rows[0]["received_at"],
            "event_key": rows[0]["event_key"],
            "group_id": "news_cmd1",
            "content_type": "sectornews",
            "serial_id": 8888,
            "request_id": 10002,
            "error_code": 10003013,
            "error_msg": "subscription limit",
            "topic_code": "__callback__",
            "item_index": -1,
            "payload_text": None,
            "payload_json": None,
        }
    ]
