import json
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from urllib.parse import quote

import pytest

import scripts.hermes_team_dispatch_server as dispatch_module
from scripts.hermes_team_dispatch_server import (
    HermesTeamDispatch,
    make_handler,
    require_loopback_bind,
)

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


TOKEN = "unit-dispatch-token"
AUTH_HEADERS = {"X-Hermes-Dispatch-Token": TOKEN}
JSON_AUTH_HEADERS = {"Content-Type": "application/json", **AUTH_HEADERS}


def make_team(tmp_path: Path, *, with_launchers: bool = False) -> Path:
    team_dir = tmp_path / "team"
    for name in ["inbox", "outbox", "sessions", "prompts", "launch", "workspaces"]:
        (team_dir / name).mkdir(parents=True, exist_ok=True)
    roles = [
        {
            "slug": "lead",
            "title": "Leader",
            "workspace": str(team_dir / "workspaces" / "lead"),
        },
        {
            "slug": "developer",
            "title": "Developer",
            "workspace": str(team_dir / "workspaces" / "developer"),
        },
    ]
    if with_launchers:
        for role in roles:
            launcher = team_dir / "launch" / f"{role['slug']}.ps1"
            launcher.write_text("$ErrorActionPreference = 'Stop'\n", encoding="utf-8")
            role["launcher"] = str(launcher)
    (team_dir / "manifest.json").write_text(
        json.dumps(
            {
                "team_id": "unit-team",
                "roles": roles,
            }
        ),
        encoding="utf-8",
    )
    return team_dir


def load_queue(team_dir: Path) -> list[dict]:
    return json.loads((team_dir / "queue" / "tasks.json").read_text(encoding="utf-8"))


def old_timestamp() -> str:
    return (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")


def test_dispatch_appends_task_to_role_inbox(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)

    result = dispatch.dispatch_task(
        role="developer",
        title="Fix dashboard dispatch",
        body="Add a button that writes to inbox.",
        sender="human",
    )

    assert result["ok"] is True
    inbox = (team_dir / "inbox" / "developer.md").read_text(encoding="utf-8")
    assert "Fix dashboard dispatch" in inbox
    assert "Add a button that writes to inbox." in inbox
    assert "sender: human" in inbox
    assert result["role"] == "developer"
    queue = load_queue(team_dir)
    assert len(queue) == 1
    task = queue[0]
    assert task["task_id"] == result["task_id"]
    assert task["role"] == "developer"
    assert task["title"] == "Fix dashboard dispatch"
    assert task["sender"] == "human"
    assert task["state"] == "queued"
    assert task["attempts"] == 0
    assert task["last_error"] == "launcher_not_configured"
    assert task["claimed_by"] == ""
    assert task["claim_token"] == ""
    assert task["lease_expires_at"] == ""
    assert task["heartbeat_at"] == ""
    assert task["inbox"] == str(team_dir / "inbox" / "developer.md")
    assert task["dispatch_log"] == str(
        team_dir / "logs" / f"developer-{result['task_id']}.log"
    )
    assert task["workspace"] == str(team_dir / "workspaces" / "developer")
    assert [event["type"] for event in task["events"]] == ["queued", "wake_failed"]


def test_dispatch_preserves_chinese_task_text(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)

    result = dispatch.dispatch_task(
        role="developer",
        title="修复资产负债页面证据条",
        body="检查 report_date、source_version、fallback 状态，不要猜口径。",
        sender="控制台",
    )

    inbox = (team_dir / "inbox" / "developer.md").read_text(encoding="utf-8")
    queue = load_queue(team_dir)
    assert result["title"] == "修复资产负债页面证据条"
    assert "修复资产负债页面证据条" in inbox
    assert "检查 report_date、source_version、fallback 状态，不要猜口径。" in inbox
    assert "sender: 控制台" in inbox
    assert queue[0]["title"] == "修复资产负债页面证据条"
    assert queue[0]["sender"] == "控制台"


def test_dispatch_generates_unique_task_ids_for_fast_tasks(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)

    first = dispatch.dispatch_task(
        role="developer",
        title="Fast task A",
        body="Audit one page.",
    )
    second = dispatch.dispatch_task(
        role="lead",
        title="Fast task B",
        body="Audit another page.",
    )

    queue = load_queue(team_dir)
    task_ids = [task["task_id"] for task in queue]
    assert first["task_id"] != second["task_id"]
    assert len(task_ids) == len(set(task_ids))
    assert first["task_id"].startswith(datetime.now().strftime("%Y%m%d-"))
    assert second["task_id"].startswith(datetime.now().strftime("%Y%m%d-"))


def test_dispatch_wakes_role_launcher_when_manifest_has_launcher(tmp_path, monkeypatch):
    team_dir = make_team(tmp_path, with_launchers=True)
    calls = []

    class FakeProcess:
        pid = 12345

    def fake_popen(args, **kwargs):
        stdout = kwargs.pop("stdout", None)
        if stdout:
            kwargs["stdout_name"] = stdout.name
            stdout.close()
        calls.append((args, kwargs))
        return FakeProcess()

    monkeypatch.setattr(dispatch_module.subprocess, "Popen", fake_popen)
    dispatch = HermesTeamDispatch(team_dir)

    result = dispatch.dispatch_task(
        role="developer",
        title="Inspect status",
        body="Read the repo status and report back.",
        sender="human",
    )

    launcher = team_dir / "launch" / "developer.ps1"
    log_path = team_dir / "logs" / f"developer-{result['task_id']}.log"
    inbox = (team_dir / "inbox" / "developer.md").read_text(encoding="utf-8")
    queue = load_queue(team_dir)
    assert f"dispatch_log: {log_path}" in inbox
    assert result["wake"] == {
        "ok": True,
        "pid": 12345,
        "launcher": str(launcher),
        "log": str(log_path),
    }
    assert calls[0][0] == [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(launcher),
        "-AutoTaskId",
        result["task_id"],
        "-TaskClaimToken",
        queue[0]["claim_token"],
    ]
    assert calls[0][1]["cwd"] == str(team_dir)
    assert calls[0][1]["stdin"] == subprocess.DEVNULL
    assert calls[0][1]["stdout_name"] == str(log_path)
    assert calls[0][1]["stderr"] == subprocess.STDOUT
    assert calls[0][1]["env"]["PYTHONIOENCODING"] == "utf-8"
    assert calls[0][1]["env"]["PYTHONUTF8"] == "1"
    assert queue[0]["task_id"] == result["task_id"]
    assert queue[0]["state"] == "running"
    assert queue[0]["attempts"] == 1
    assert queue[0]["dispatch_log"] == str(log_path)
    assert queue[0]["claimed_by"] == "developer"
    assert queue[0]["claim_token"]
    assert queue[0]["lease_expires_at"]
    assert queue[0]["heartbeat_at"]
    assert [event["type"] for event in queue[0]["events"]] == [
        "queued",
        "claimed",
        "running",
    ]


def test_retry_task_wakes_role_again_and_increments_attempts(tmp_path, monkeypatch):
    team_dir = make_team(tmp_path, with_launchers=True)
    calls = []

    class FakeProcess:
        pid = 12345

    def fake_popen(args, **kwargs):
        stdout = kwargs.pop("stdout", None)
        if stdout:
            kwargs["stdout_name"] = stdout.name
            stdout.close()
        calls.append((args, kwargs))
        return FakeProcess()

    monkeypatch.setattr(dispatch_module.subprocess, "Popen", fake_popen)
    dispatch = HermesTeamDispatch(team_dir)
    result = dispatch.dispatch_task(
        role="developer",
        title="Retry me",
        body="Run once, then retry.",
        sender="human",
    )

    retry = dispatch.retry_task(result["task_id"])

    retry_log = team_dir / "logs" / f"developer-{result['task_id']}-attempt2.log"
    queue = load_queue(team_dir)
    assert retry["ok"] is True
    assert retry["task_id"] == result["task_id"]
    assert retry["attempts"] == 2
    assert retry["wake"]["log"] == str(retry_log)
    assert calls[-1][0] == [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(team_dir / "launch" / "developer.ps1"),
        "-AutoTaskId",
        result["task_id"],
        "-TaskClaimToken",
        queue[0]["claim_token"],
    ]
    assert calls[-1][1]["stdout_name"] == str(retry_log)
    assert queue[0]["attempts"] == 2
    assert queue[0]["state"] == "running"
    assert queue[0]["dispatch_log"] == str(retry_log)
    assert queue[0]["claimed_by"] == "developer"
    assert queue[0]["claim_token"]
    assert queue[0]["lease_expires_at"]
    assert [event["type"] for event in queue[0]["events"]][-2:] == [
        "claimed",
        "running",
    ]


def test_status_reports_wake_failure_as_intervention(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)
    result = dispatch.dispatch_task(
        role="developer",
        title="Needs a launcher",
        body="This cannot wake without a launcher.",
        sender="human",
    )

    status = dispatch.status()

    assert status["roles"]["developer"]["task_state"] == "needs_attention"
    assert status["roles"]["developer"]["attention"][0]["reason"] == "wake_failed"
    assert status["interventions"] == [
        {
            "task_id": result["task_id"],
            "role": "developer",
            "title": "Needs a launcher",
            "reason": "wake_failed",
            "state": "queued",
            "last_error": "launcher_not_configured",
            "updated_at": status["interventions"][0]["updated_at"],
        }
    ]


def test_status_reports_expired_running_task_as_intervention(tmp_path):
    team_dir = make_team(tmp_path, with_launchers=True)
    expired = old_timestamp()
    (team_dir / "queue").mkdir()
    (team_dir / "queue" / "tasks.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "20260607-111216",
                    "role": "developer",
                    "title": "Stuck task",
                    "sender": "dashboard",
                    "created_at": expired,
                    "updated_at": expired,
                    "state": "running",
                    "attempts": 1,
                    "last_error": "",
                    "claimed_by": "developer",
                    "claim_token": "claim-1",
                    "lease_expires_at": expired,
                    "heartbeat_at": expired,
                    "inbox": str(team_dir / "inbox" / "developer.md"),
                    "dispatch_log": str(
                        team_dir / "logs" / "developer-20260607-111216.log"
                    ),
                    "workspace": str(team_dir / "workspaces" / "developer"),
                    "events": [{"at": expired, "type": "running"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    dispatch = HermesTeamDispatch(team_dir)

    status = dispatch.status()

    developer = status["roles"]["developer"]
    assert developer["task_state"] == "needs_attention"
    assert developer["attention"][0]["reason"] == "lease_expired"
    assert status["interventions"][0]["task_id"] == "20260607-111216"
    assert status["interventions"][0]["reason"] == "lease_expired"


def test_task_heartbeat_and_completion_update_queue(tmp_path, monkeypatch):
    team_dir = make_team(tmp_path, with_launchers=True)

    class FakeProcess:
        pid = 12345

    def fake_popen(args, **kwargs):
        stdout = kwargs.get("stdout")
        if stdout:
            stdout.close()
        return FakeProcess()

    monkeypatch.setattr(dispatch_module.subprocess, "Popen", fake_popen)
    dispatch = HermesTeamDispatch(team_dir)
    result = dispatch.dispatch_task(
        role="developer",
        title="Heartbeat me",
        body="Send status while running.",
        sender="human",
    )

    heartbeat = dispatch.record_task_heartbeat(result["task_id"])
    task_after_heartbeat = load_queue(team_dir)[0]
    complete = dispatch.complete_task(result["task_id"], exit_code=0)
    task_after_complete = load_queue(team_dir)[0]

    assert heartbeat["ok"] is True
    assert task_after_heartbeat["state"] == "running"
    assert task_after_heartbeat["heartbeat_at"]
    assert task_after_heartbeat["lease_expires_at"]
    assert task_after_heartbeat["events"][-1]["type"] == "heartbeat"
    assert complete["ok"] is True
    assert task_after_complete["state"] == "completed"
    assert task_after_complete["completed_at"]
    assert task_after_complete["last_error"] == ""
    assert task_after_complete["events"][-1]["type"] == "completed"
    assert dispatch.status()["interventions"] == []


def test_dispatch_rejects_unknown_role(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)

    with pytest.raises(ValueError, match="Unknown role"):
        dispatch.dispatch_task(role="hacker", title="Bad", body="Nope")


def test_dispatch_requires_non_empty_body(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)

    with pytest.raises(ValueError, match="body is required"):
        dispatch.dispatch_task(role="lead", title="Empty", body=" ")


def test_health_reports_team_and_roles(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)

    health = dispatch.health()

    assert health == {
        "ok": True,
        "team_id": "unit-team",
        "roles": ["lead", "developer"],
    }


def test_dispatch_server_rejects_non_loopback_bind():
    with pytest.raises(SystemExit, match="loopback only"):
        require_loopback_bind("0.0.0.0")

    require_loopback_bind("127.0.0.1")
    require_loopback_bind("localhost")
    require_loopback_bind("::1")


def test_status_reports_recent_task_log_and_outbox(tmp_path):
    team_dir = make_team(tmp_path, with_launchers=True)
    log_path = team_dir / "logs" / "developer-20260607-111213.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("started\nread inbox\n", encoding="utf-8")
    (team_dir / "inbox" / "developer.md").write_text(
        "\n".join(
            [
                "# Inbox: Developer",
                "",
                "## Task 20260607-111213: Inspect status",
                "",
                "sender: dashboard",
                "assigned_role: developer",
                "created_at: 2026-06-07 11:12:13",
                "",
                f"dispatch_log: {log_path}",
                "",
                "Check the current state.",
            ]
        ),
        encoding="utf-8",
    )
    (team_dir / "outbox" / "developer.md").write_text(
        "# Outbox: Developer\n\nStatus: completed\n",
        encoding="utf-8",
    )
    dispatch = HermesTeamDispatch(team_dir)

    status = dispatch.status()

    developer = status["roles"]["developer"]
    assert developer["workspace"] == str(team_dir / "workspaces" / "developer")
    assert developer["queue"] == []
    assert developer["task_state"] == "completed"
    assert developer["recent_task"]["task_id"] == "20260607-111213"
    assert developer["recent_task"]["title"] == "Inspect status"
    assert developer["recent_task"]["dispatch_log"] == str(log_path)
    assert developer["log_tail"] == "started\nread inbox\n"
    assert developer["outbox_preview"] == "# Outbox: Developer\n\nStatus: completed\n"


def test_status_marks_running_when_log_is_newer_than_outbox(tmp_path):
    team_dir = make_team(tmp_path, with_launchers=True)
    log_path = team_dir / "logs" / "developer-20260607-111214.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("running\n", encoding="utf-8")
    (team_dir / "inbox" / "developer.md").write_text(
        "\n".join(
            [
                "# Inbox: Developer",
                "",
                "## Task 20260607-111214: Running task",
                "",
                "created_at: 2026-06-07 11:12:14",
                "",
                f"dispatch_log: {log_path}",
                "",
                "Still running.",
            ]
        ),
        encoding="utf-8",
    )
    dispatch = HermesTeamDispatch(team_dir)

    status = dispatch.status()

    assert status["roles"]["developer"]["task_state"] == "running"


def test_status_marks_completed_when_task_outbox_block_is_completed_even_if_log_is_newer(tmp_path):
    team_dir = make_team(tmp_path, with_launchers=True)
    log_path = team_dir / "logs" / "developer-20260607-111216.log"
    log_path.parent.mkdir(parents=True)
    (team_dir / "outbox" / "developer.md").write_text(
        "\n".join(
            [
                "# Outbox: Developer",
                "",
                "## Task 20260607-111216: Summarize audit",
                "",
                "Status: completed",
                "",
                "Findings:",
                "- Wrote the summary.",
            ]
        ),
        encoding="utf-8",
    )
    log_path.write_text("final callback still pending\n", encoding="utf-8")
    (team_dir / "queue").mkdir()
    (team_dir / "queue" / "tasks.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "20260607-111216",
                    "role": "developer",
                    "title": "Summarize audit",
                    "sender": "dashboard",
                    "created_at": "2026-06-07 11:12:16",
                    "updated_at": "2026-06-07 11:12:17",
                    "state": "running",
                    "attempts": 1,
                    "last_error": "",
                    "claimed_by": "developer",
                    "claim_token": "claim-1",
                    "lease_expires_at": (datetime.now() + timedelta(minutes=5)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    "heartbeat_at": "2026-06-07 11:12:17",
                    "inbox": str(team_dir / "inbox" / "developer.md"),
                    "dispatch_log": str(log_path),
                    "workspace": str(team_dir / "workspaces" / "developer"),
                    "events": [{"at": "2026-06-07 11:12:17", "type": "running"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    dispatch = HermesTeamDispatch(team_dir)

    status = dispatch.status()

    assert status["roles"]["developer"]["task_state"] == "completed"


def test_status_reports_running_task_with_exited_process_as_intervention(
    tmp_path, monkeypatch
):
    team_dir = make_team(tmp_path, with_launchers=True)
    lease_expires_at = (datetime.now() + timedelta(minutes=5)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    (team_dir / "queue").mkdir()
    (team_dir / "queue" / "tasks.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "20260607-111217",
                    "role": "developer",
                    "title": "Lost callback",
                    "sender": "dashboard",
                    "created_at": "2026-06-07 11:12:17",
                    "updated_at": "2026-06-07 11:12:18",
                    "state": "running",
                    "attempts": 1,
                    "last_error": "",
                    "claimed_by": "developer",
                    "claim_token": "claim-1",
                    "lease_expires_at": lease_expires_at,
                    "heartbeat_at": "2026-06-07 11:12:18",
                    "process_id": 987654,
                    "inbox": str(team_dir / "inbox" / "developer.md"),
                    "dispatch_log": str(
                        team_dir / "logs" / "developer-20260607-111217.log"
                    ),
                    "workspace": str(team_dir / "workspaces" / "developer"),
                    "events": [{"at": "2026-06-07 11:12:18", "type": "running"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    dispatch = HermesTeamDispatch(team_dir)
    monkeypatch.setattr(dispatch, "is_process_running", lambda pid: False, raising=False)

    status = dispatch.status()

    developer = status["roles"]["developer"]
    assert developer["task_state"] == "needs_attention"
    assert developer["attention"][0]["reason"] == "process_exited_without_completion"
    assert status["interventions"][0]["task_id"] == "20260607-111217"


def test_status_reports_queue_attempts_and_workspace(tmp_path):
    team_dir = make_team(tmp_path, with_launchers=True)
    log_path = team_dir / "logs" / "developer-20260607-111215-attempt2.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("retry running\n", encoding="utf-8")
    (team_dir / "queue").mkdir()
    (team_dir / "queue" / "tasks.json").write_text(
        json.dumps(
            [
                {
                    "task_id": "20260607-111215",
                    "role": "developer",
                    "title": "Retry status",
                    "sender": "dashboard",
                    "created_at": "2026-06-07 11:12:15",
                    "updated_at": "2026-06-07 11:13:15",
                    "state": "running",
                    "attempts": 2,
                    "last_error": "",
                    "inbox": str(team_dir / "inbox" / "developer.md"),
                    "dispatch_log": str(log_path),
                    "workspace": str(team_dir / "workspaces" / "developer"),
                }
            ]
        ),
        encoding="utf-8",
    )
    dispatch = HermesTeamDispatch(team_dir)

    status = dispatch.status()

    developer = status["roles"]["developer"]
    assert developer["task_state"] == "running"
    assert developer["recent_task"]["task_id"] == "20260607-111215"
    assert developer["recent_task"]["attempts"] == 2
    assert "claim_token" not in developer["recent_task"]
    assert developer["queue_count"] == 1
    assert developer["queue"][0]["title"] == "Retry status"
    assert "claim_token" not in developer["queue"][0]
    assert developer["workspace"] == str(team_dir / "workspaces" / "developer")


def test_log_endpoint_rejects_paths_outside_team(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)
    outside = tmp_path / "outside.log"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError, match="outside team directory"):
        dispatch.read_text_inside_team(str(outside))


def test_http_status_endpoint_returns_role_status(tmp_path):
    team_dir = make_team(tmp_path)
    (team_dir / "outbox" / "developer.md").write_text(
        "# Outbox: Developer\n\nStatus: ready\n",
        encoding="utf-8",
    )
    dispatch = HermesTeamDispatch(team_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", "/api/status", headers=AUTH_HEADERS)
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 200
    assert payload["ok"] is True
    assert payload["roles"]["developer"]["outbox_preview"] == (
        "# Outbox: Developer\n\nStatus: ready\n"
    )


def test_http_status_endpoint_rejects_missing_or_wrong_token(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", "/api/status")
        missing_response = connection.getresponse()
        missing_payload = json.loads(missing_response.read().decode("utf-8"))

        connection.request(
            "GET",
            "/api/status",
            headers={"X-Hermes-Dispatch-Token": "wrong-token"},
        )
        wrong_response = connection.getresponse()
        wrong_payload = json.loads(wrong_response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    assert missing_response.status == 403
    assert missing_payload["ok"] is False
    assert missing_payload["error"] == "invalid dispatch token"
    assert wrong_response.status == 403
    assert wrong_payload["ok"] is False
    assert wrong_payload["error"] == "invalid dispatch token"


def test_http_api_rejects_cross_origin_even_with_token(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(
            "GET",
            "/api/status",
            headers={**AUTH_HEADERS, "Origin": "http://attacker.example"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 403
    assert payload["ok"] is False
    assert payload["error"] == "cross-origin API access is not allowed"


def test_http_api_rejects_rebinding_host_even_when_origin_matches(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(
            "GET",
            "/api/status",
            headers={
                **AUTH_HEADERS,
                "Host": "evil.example",
                "Origin": "http://evil.example",
            },
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 403
    assert payload["ok"] is False
    assert payload["error"] == "HTTP host must be loopback"


def test_http_api_rejects_non_loopback_client_even_with_loopback_host(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)
    handler = make_handler(dispatch, TOKEN)

    class FakeRequest:
        def makefile(self, *args, **kwargs):
            raise RuntimeError("not used")

    request = object.__new__(handler)
    request.headers = {
        "Host": "127.0.0.1",
        "Origin": "http://127.0.0.1",
        "X-Hermes-Dispatch-Token": TOKEN,
    }
    request.client_address = ("203.0.113.9", 54321)
    request._send_forbidden = lambda message: setattr(request, "forbidden_message", message)

    assert request._api_authorized() is False
    assert request.forbidden_message == "client must connect from loopback"


def test_http_options_rejects_cors_preflight(tmp_path):
    team_dir = make_team(tmp_path)
    dispatch = HermesTeamDispatch(team_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(
            "OPTIONS",
            "/api/status",
            headers={
                "Origin": "http://attacker.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        allow_origin = response.getheader("Access-Control-Allow-Origin")
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 403
    assert payload["ok"] is False
    assert allow_origin is None


def test_http_static_files_do_not_expose_manifest_or_dashboard_token(tmp_path):
    team_dir = make_team(tmp_path)
    (team_dir / "manifest.json").write_text(
        json.dumps({"team_id": "unit-team", "roles": [], "dispatch_token": TOKEN}),
        encoding="utf-8",
    )
    (team_dir / "dashboard.html").write_text(
        "<html><body>dashboard without token</body></html>",
        encoding="utf-8",
    )
    dispatch = HermesTeamDispatch(team_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", "/manifest.json")
        manifest_response = connection.getresponse()
        manifest_payload = json.loads(manifest_response.read().decode("utf-8"))

        connection.request("GET", "/")
        dashboard_response = connection.getresponse()
        dashboard_text = dashboard_response.read().decode("utf-8")
        cookie = dashboard_response.getheader("Set-Cookie")
    finally:
        server.shutdown()
        server.server_close()

    assert manifest_response.status == 403
    assert manifest_payload["ok"] is False
    assert TOKEN not in json.dumps(manifest_payload)
    assert dashboard_response.status == 200
    assert TOKEN not in dashboard_text
    assert cookie and "hermes_dispatch_token=" in cookie
    assert "HttpOnly" in cookie


def test_http_static_files_reject_rebinding_host(tmp_path):
    team_dir = make_team(tmp_path)
    (team_dir / "dashboard.html").write_text("dashboard", encoding="utf-8")
    dispatch = HermesTeamDispatch(team_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request("GET", "/", headers={"Host": "evil.example"})
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 403
    assert payload["ok"] is False
    assert payload["error"] == "HTTP host must be loopback"


def test_http_log_endpoint_rejects_paths_outside_team_with_token(tmp_path):
    team_dir = make_team(tmp_path)
    outside = tmp_path / "outside.log"
    outside.write_text("secret", encoding="utf-8")
    dispatch = HermesTeamDispatch(team_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(
            "GET",
            f"/api/log?path={quote(str(outside))}",
            headers=AUTH_HEADERS,
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 403
    assert payload["ok"] is False
    assert payload["error"] == "path is outside team directory"


def test_http_log_endpoint_rejects_sensitive_team_files_with_token(tmp_path):
    team_dir = make_team(tmp_path)
    (team_dir / "dashboard.html").write_text("dashboard", encoding="utf-8")
    dispatch = HermesTeamDispatch(team_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(
            "GET",
            f"/api/log?path={quote(str(team_dir / 'manifest.json'))}",
            headers=AUTH_HEADERS,
        )
        manifest_response = connection.getresponse()
        manifest_payload = json.loads(manifest_response.read().decode("utf-8"))

        connection.request(
            "GET",
            f"/api/log?path={quote(str(team_dir / 'queue' / 'tasks.json'))}",
            headers=AUTH_HEADERS,
        )
        queue_response = connection.getresponse()
        queue_payload = json.loads(queue_response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    assert manifest_response.status == 403
    assert manifest_payload["error"] == "path is not readable through the dashboard API"
    assert queue_response.status == 403
    assert queue_payload["error"] == "path is not readable through the dashboard API"


def test_http_retry_endpoint_returns_retry_result(tmp_path, monkeypatch):
    team_dir = make_team(tmp_path, with_launchers=True)

    class FakeProcess:
        pid = 54321

    def fake_popen(args, **kwargs):
        stdout = kwargs.get("stdout")
        if stdout:
            stdout.close()
        return FakeProcess()

    monkeypatch.setattr(dispatch_module.subprocess, "Popen", fake_popen)
    dispatch = HermesTeamDispatch(team_dir)
    task = dispatch.dispatch_task(
        role="developer",
        title="Retry over HTTP",
        body="Wake me twice.",
        sender="human",
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(
            "POST",
            "/api/retry",
            body=json.dumps({"task_id": task["task_id"]}).encode("utf-8"),
            headers=JSON_AUTH_HEADERS,
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    assert response.status == 200
    assert payload["ok"] is True
    assert payload["task_id"] == task["task_id"]
    assert payload["attempts"] == 2


def test_http_task_heartbeat_and_complete_endpoints_update_task(tmp_path, monkeypatch):
    team_dir = make_team(tmp_path, with_launchers=True)

    class FakeProcess:
        pid = 54321

    def fake_popen(args, **kwargs):
        stdout = kwargs.get("stdout")
        if stdout:
            stdout.close()
        return FakeProcess()

    monkeypatch.setattr(dispatch_module.subprocess, "Popen", fake_popen)
    dispatch = HermesTeamDispatch(team_dir)
    task = dispatch.dispatch_task(
        role="developer",
        title="HTTP status callbacks",
        body="Report status through the local API.",
        sender="human",
    )
    claim_token = load_queue(team_dir)[0]["claim_token"]
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(dispatch, TOKEN))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        connection.request(
            "POST",
            "/api/task/heartbeat",
            body=json.dumps(
                {"task_id": task["task_id"], "claim_token": "wrong-claim"}
            ).encode("utf-8"),
            headers=JSON_AUTH_HEADERS,
        )
        wrong_heartbeat_response = connection.getresponse()
        wrong_heartbeat_payload = json.loads(
            wrong_heartbeat_response.read().decode("utf-8")
        )

        connection.request(
            "POST",
            "/api/task/heartbeat",
            body=json.dumps(
                {"task_id": task["task_id"], "claim_token": claim_token}
            ).encode("utf-8"),
            headers=JSON_AUTH_HEADERS,
        )
        heartbeat_response = connection.getresponse()
        heartbeat_payload = json.loads(heartbeat_response.read().decode("utf-8"))

        connection.request(
            "POST",
            "/api/task/complete",
            body=json.dumps({"task_id": task["task_id"], "exit_code": 0}).encode(
                "utf-8"
            ),
            headers=JSON_AUTH_HEADERS,
        )
        missing_complete_response = connection.getresponse()
        missing_complete_payload = json.loads(
            missing_complete_response.read().decode("utf-8")
        )

        connection.request(
            "POST",
            "/api/task/complete",
            body=json.dumps(
                {
                    "task_id": task["task_id"],
                    "claim_token": claim_token,
                    "exit_code": 0,
                }
            ).encode("utf-8"),
            headers=JSON_AUTH_HEADERS,
        )
        complete_response = connection.getresponse()
        complete_payload = json.loads(complete_response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    queue = load_queue(team_dir)
    assert wrong_heartbeat_response.status == 400
    assert wrong_heartbeat_payload["error"] == "invalid task claim token"
    assert heartbeat_response.status == 200
    assert heartbeat_payload["ok"] is True
    assert missing_complete_response.status == 400
    assert missing_complete_payload["error"] == "invalid task claim token"
    assert complete_response.status == 200
    assert complete_payload["state"] == "completed"
    assert queue[0]["state"] == "completed"
    assert [event["type"] for event in queue[0]["events"]][-2:] == [
        "heartbeat",
        "completed",
    ]
