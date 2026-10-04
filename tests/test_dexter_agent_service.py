from __future__ import annotations

import io
import json
import subprocess
import sys
import threading
import time
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.agent.runtime.subprocess_env import is_sensitive_env_name
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.services import dexter_agent_service as service
from backend.app.services import dexter_research_context_builder as context_builder

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_agent_mvp,
]


def test_cancelled_dexter_request_does_not_spawn_cli(monkeypatch):
    event = threading.Event()
    event.set()
    monkeypatch.setattr(service.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("cancelled request must not launch"))
    monkeypatch.setattr(service.subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("cancelled request must not launch"))
    with pytest.raises(RuntimeError, match="cancelled"):
        service.run_dexter_agent(request=AgentQueryRequest(question="cancel"), command="dexter", transport="cli", bridge_url="", model="", toolsets="", timeout_seconds=5, cancel_event=event)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows inherited pipe ownership")
@pytest.mark.parametrize("cancel", [False, True])
def test_exited_launcher_inherited_pipes_remain_bounded(monkeypatch, tmp_path, cancel):
    pid_file = tmp_path / "launcher-child.pid"
    child_code = "import time; time.sleep(8)" if cancel else "import os, time; time.sleep(0.3); p = '{\"answer\": \"完整中文\"}'.encode('utf-8'); os.write(1, p[:14]); time.sleep(0.1); os.write(1, p[14:])"
    launcher = tmp_path / "launcher.py"
    launcher.write_text("import subprocess, sys\nfrom pathlib import Path\np = subprocess.Popen([sys.executable, '-c', sys.argv[2]])\nPath(sys.argv[1]).write_text(str(p.pid))\n", encoding="utf-8")
    monkeypatch.setattr(service, "_build_dexter_command", lambda **kwargs: [sys.executable, str(launcher), str(pid_file), child_code])
    processes = []
    real_popen = subprocess.Popen

    def spawn(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(service.subprocess, "Popen", spawn)
    event = threading.Event()
    outcomes = []

    def run():
        try:
            outcomes.append(service.run_dexter_agent(request=AgentQueryRequest(question="synthetic launcher"), command=sys.executable, transport="cli", bridge_url="", model="", toolsets="", timeout_seconds=10, cancel_event=event))
        except Exception as exc:
            outcomes.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        deadline = time.monotonic() + 3
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert pid_file.exists()
        processes[0].wait(timeout=3)
        if cancel:
            event.set()
        thread.join(timeout=1.5)
        assert not thread.is_alive(), "inherited child pipe blocked the cancelled launcher"
        if cancel:
            assert isinstance(outcomes[0], service.DexterRunCancelled)
            assert "stop remains unconfirmed" in str(outcomes[0])
        else:
            assert outcomes[0]["answer"] == "完整中文"
        assert processes[0].stdout.closed and processes[0].stderr.closed
    finally:
        event.set()
        if pid_file.exists():
            subprocess.run(["taskkill", "/PID", pid_file.read_text(), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        thread.join(timeout=5)


def test_dexter_cli_cancel_stops_real_local_process_tree(monkeypatch, tmp_path):
    pid_file = tmp_path / "child.pid"
    script = tmp_path / "local_cli.py"
    script.write_text("import subprocess, sys, time\nfrom pathlib import Path\nchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\nPath(sys.argv[1]).write_text(str(child.pid))\ntime.sleep(30)\n", encoding="utf-8")
    monkeypatch.setattr(service, "_build_dexter_command", lambda **_kwargs: [sys.executable, str(script), str(pid_file)])
    processes = []
    real_popen = subprocess.Popen
    def spawn(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(service.subprocess, "Popen", spawn)
    event = threading.Event()
    outcomes = []

    def run():
        try:
            service.run_dexter_agent(request=AgentQueryRequest(question="local synthetic"), command=sys.executable, transport="cli", bridge_url="", model="", toolsets="", timeout_seconds=10, cancel_event=event)
        except Exception as exc:
            outcomes.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not pid_file.exists() and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pid_file.exists(), f"local CLI did not start: {outcomes}"
        child_pid = int(pid_file.read_text())
        event.set()
        thread.join(timeout=5)
        assert not thread.is_alive()
        assert len(outcomes) == 1 and "cancelled" in str(outcomes[0])
        assert processes[0].returncode is not None
        assert processes[0].stdout.closed and processes[0].stderr.closed
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel32.WaitForSingleObject.restype = wintypes.DWORD
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(0x00100000, False, child_pid)
            if handle:
                try:
                    assert kernel32.WaitForSingleObject(handle, 2000) == 0
                finally:
                    kernel32.CloseHandle(handle)
            else:
                assert ctypes.get_last_error() == 87  # PID no longer exists.
        else:
            import os
            deadline = time.monotonic() + 2
            while True:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                # A killed Linux grandchild may await init reaping as a zombie;
                # it has stopped execution even though its PID still exists.
                stat = Path(f"/proc/{child_pid}/stat")
                if sys.platform == "linux":
                    try:
                        if stat.read_text().rsplit(")", 1)[1].split()[0] == "Z":
                            break
                    except FileNotFoundError:
                        break
                assert time.monotonic() < deadline, "child process is still running"
                time.sleep(0.02)
    finally:
        event.set()
        thread.join(timeout=5)


@pytest.mark.parametrize("mode", ["normal", "timeout", "eof_timeout"])
def test_dexter_cancellable_cli_completion_and_timeout_close_pipes(monkeypatch, mode):
    code = "print('{\"answer\": \"local done\"}')" if mode == "normal" else "import time; time.sleep(30)"
    if mode == "eof_timeout":
        code = "import os, time; os.close(1); os.close(2); time.sleep(30)"
    monkeypatch.setattr(service, "_build_dexter_command", lambda **_kwargs: [sys.executable, "-c", code])
    processes = []
    real_popen = subprocess.Popen
    def spawn(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(service.subprocess, "Popen", spawn)
    options = dict(request=AgentQueryRequest(question="local synthetic"), command=sys.executable, transport="cli", bridge_url="", model="", toolsets="", timeout_seconds=0.1, cancel_event=threading.Event())
    if mode == "normal":
        assert service.run_dexter_agent(**options)["answer"] == "local done"
    else:
        with pytest.raises(RuntimeError, match="timed out"):
            service.run_dexter_agent(**options)
    assert processes[0].returncode is not None
    assert processes[0].stdout.closed and processes[0].stderr.closed


@pytest.mark.parametrize("bridge_fails", [False, True])
def test_bridge_cancel_never_claims_remote_stop_or_appends_fallback_audit(monkeypatch, tmp_path, bridge_fails):
    event = threading.Event()
    monkeypatch.setattr(service, "ensure_agent_execution_resources_allowed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "build_dexter_research_context", lambda **_kwargs: {})
    monkeypatch.setattr(service, "_append_dexter_audit", lambda *_args: pytest.fail("cancelled request must not append provider audit"))
    def bridge(**_kwargs):
        event.set()
        if bridge_fails:
            raise RuntimeError("synthetic bridge failure")
        return {"answer": "late bridge answer"}
    monkeypatch.setattr(service, "_post_dexter_bridge_query", bridge)
    with pytest.raises(service.DexterRunCancelled, match="stop remains unconfirmed"):
        service.execute_dexter_agent_query(AgentQueryRequest(question="synthetic bridge"), str(tmp_path), SimpleNamespace(agent_dexter_transport="bridge"), cancel_event=event)


def test_build_dexter_envelope_exposes_sidecar_runtime_evidence():
    envelope = service.build_dexter_envelope(
        request=AgentQueryRequest(question="ping"),
        result={
            "answer": "pong",
            "stdout": "pong",
            "stderr": "",
            "command": "dexter",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "sql,files",
            "transport": "sidecar",
            "tables_used": ["dexter_sidecar"],
        },
    )

    assert envelope.result_meta.result_kind == "agent.dexter"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.source_version == "sv_dexter_sidecar"
    assert envelope.result_meta.vendor_version == "vv_dexter"
    assert envelope.result_meta.rule_version == "rv_agent_dexter_v1"
    assert envelope.result_meta.cache_version == "cv_agent_dexter_v1"
    assert envelope.evidence.tables_used == ["dexter_sidecar"]
    assert envelope.evidence.filters_applied["provider"] == "dexter"
    assert envelope.evidence.filters_applied["model"] == "dexter-test"
    assert envelope.evidence.filters_applied["transport"] == "sidecar"
    assert envelope.evidence.filters_applied["toolsets"] == "evidence,query,research"
    assert envelope.evidence.quality_flag == "warning"
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.evidence.evidence_rows == 0
    assert envelope.evidence.evidence_strength == "provider_runtime"
    assert envelope.result_meta.evidence_strength == "provider_runtime"
    assert envelope.evidence.sql_executed == []
    assert envelope.result_meta.sql_executed == []


def test_build_dexter_envelope_marks_provider_answer_with_governed_context_as_mixed():
    envelope = service.build_dexter_envelope(
        request=AgentQueryRequest(question="stock research"),
        result={
            "answer": "Provider answer over landed context",
            "stdout": "ok",
            "stderr": "",
            "command": "dexter",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "evidence,research",
            "transport": "sidecar",
            "tables_used": ["dexter_sidecar"],
        },
        research_context={
            "domain": "stock",
            "tables_used": ["choice_stock_daily_observation"],
            "filters_applied": {"research_domain": "stock", "stock_code": "000001.SZ"},
            "sql_executed": [
                (
                    "select trade_date, stock_code, close_value "
                    "from choice_stock_daily_observation "
                    "where stock_code = ? and (? = '' or trade_date <= ?) "
                    "order by trade_date desc limit 1"
                )
            ],
            "evidence_rows": 1,
            "quality_flag": "ok",
            "limitations": [],
        },
    )

    assert envelope.evidence.evidence_strength == "mixed"
    assert envelope.result_meta.evidence_strength == "mixed"
    assert envelope.evidence.evidence_rows == 1
    assert envelope.evidence.quality_flag == "warning"
    assert envelope.result_meta.quality_flag == "warning"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.evidence.sql_executed
    assert envelope.result_meta.sql_executed == envelope.evidence.sql_executed
    assert all(
        sql.lower().startswith(("select", "with"))
        for sql in envelope.evidence.sql_executed
    )
    assert "000001.SZ" not in envelope.evidence.sql_executed[0]


def test_run_dexter_agent_invokes_subprocess_and_parses_json_payload(monkeypatch):
    calls = []

    class Completed:
        returncode = 0
        stdout = json.dumps(
            {
                "answer": "Dexter says hello",
                "tool_name": "portfolio.scan",
                "tables_used": ["dexter_cli"],
                "model": "dexter-test",
            }
        )
        stderr = "warning: sample"

    def fake_run(args, **kwargs):
        calls.append({"args": args, **kwargs})
        return Completed()

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    result = service.run_dexter_agent(
        request=AgentQueryRequest(question="ping"),
        command="dexter",
        transport="cli",
        bridge_url="http://127.0.0.1:7892",
        model="dexter-test",
        toolsets=" sql , files ",
        timeout_seconds=5,
    )

    assert result["answer"] == "Dexter says hello"
    assert result["tool_name"] == "portfolio.scan"
    assert result["tables_used"] == ["dexter_cli"]
    assert result["model"] == "dexter-test"
    assert result["toolsets"] == "evidence,query,research"
    assert result["transport"] == "cli"
    assert calls[0]["args"][0] == "dexter"


def test_run_dexter_agent_restricts_toolsets_to_read_only_allowlist(monkeypatch):
    calls = []

    class Completed:
        returncode = 0
        stdout = json.dumps({"answer": "ok"})
        stderr = ""

    def fake_run(args, **kwargs):
        calls.append({"args": args, **kwargs})
        return Completed()

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    result = service.run_dexter_agent(
        request=AgentQueryRequest(question="probe"),
        command="dexter",
        transport="cli",
        bridge_url="",
        model="",
        toolsets=" sql , files , evidence, research, terminal ",
        timeout_seconds=5,
    )

    assert result["toolsets"] == "evidence,research"
    assert "--toolsets" in calls[0]["args"]
    assert calls[0]["args"][calls[0]["args"].index("--toolsets") + 1] == "evidence,research"


def test_run_dexter_agent_preserves_structured_research_fields(monkeypatch):
    class Completed:
        returncode = 0
        stdout = json.dumps(
            {
                "answer": "Research answer",
                "summary": "Summary",
                "findings": ["Finding"],
                "evidence": ["Evidence"],
                "risks": ["Risk"],
                "limitations": ["Limitation"],
                "next_drill": ["Drill"],
            }
        )
        stderr = ""

    monkeypatch.setattr(service.subprocess, "run", lambda *args, **kwargs: Completed())

    result = service.run_dexter_agent(
        request=AgentQueryRequest(question="stock research"),
        command="dexter",
        transport="cli",
        bridge_url="",
        model="",
        toolsets="",
        timeout_seconds=5,
    )

    assert result["summary"] == "Summary"
    assert result["findings"] == ["Finding"]
    assert result["evidence"] == ["Evidence"]
    assert result["risks"] == ["Risk"]
    assert result["limitations"] == ["Limitation"]
    assert result["next_drill"] == ["Drill"]


def test_run_dexter_agent_passes_expected_subprocess_argv_and_timeout(monkeypatch):
    calls = []

    class Completed:
        returncode = 0
        stdout = json.dumps({"answer": "ok"})
        stderr = ""

    def fake_run(args, **kwargs):
        calls.append({"args": args, **kwargs})
        return Completed()

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    service.run_dexter_agent(
        request=AgentQueryRequest(question="probe"),
        command="dexter-cli",
        transport="CLI",
        bridge_url="",
        model="dexter-model",
        toolsets=" sql , files , ",
        timeout_seconds=0.25,
    )

    assert len(calls) == 1
    call = calls[0]
    assert call["args"] == [
        "dexter-cli",
        "query",
        "--json",
        "--prompt",
        call["args"][4],
        "--model",
        "dexter-model",
        "--toolsets",
        "evidence,query,research",
    ]
    assert {
        key: value for key, value in call.items() if key not in {"args", "env"}
    } == {
        "check": False,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": 1.0,
    }
    assert not [name for name in call["env"] if is_sensitive_env_name(name)]
    assert "User question:\nprobe" in calls[0]["args"][4]


def test_run_dexter_agent_returns_plain_stdout_when_output_is_not_json(monkeypatch):
    class Completed:
        returncode = 0
        stdout = "plain text answer"
        stderr = ""

    monkeypatch.setattr(service.subprocess, "run", lambda *args, **kwargs: Completed())

    result = service.run_dexter_agent(
        request=AgentQueryRequest(question="ping"),
        command="dexter",
        transport="cli",
        bridge_url="",
        model="",
        toolsets="",
        timeout_seconds=5,
    )

    assert result["answer"] == "plain text answer"
    assert result["tool_name"] == "dexter_cli"
    assert result["tables_used"] == ["dexter_cli"]


def test_run_dexter_agent_raises_with_stderr_detail_on_nonzero_exit(monkeypatch):
    class Completed:
        returncode = 7
        stdout = "stdout detail"
        stderr = "stderr detail"

    monkeypatch.setattr(service.subprocess, "run", lambda *args, **kwargs: Completed())

    with pytest.raises(RuntimeError, match="Dexter failed with exit code 7: stderr detail"):
        service.run_dexter_agent(
            request=AgentQueryRequest(question="ping"),
            command="dexter",
            transport="cli",
            bridge_url="",
            model="",
            toolsets="",
            timeout_seconds=5,
        )


def test_run_dexter_agent_raises_with_stdout_detail_when_stderr_is_empty(monkeypatch):
    class Completed:
        returncode = 9
        stdout = "stdout only detail"
        stderr = ""

    monkeypatch.setattr(service.subprocess, "run", lambda *args, **kwargs: Completed())

    with pytest.raises(RuntimeError, match="Dexter failed with exit code 9: stdout only detail"):
        service.run_dexter_agent(
            request=AgentQueryRequest(question="ping"),
            command="dexter",
            transport="cli",
            bridge_url="",
            model="",
            toolsets="",
            timeout_seconds=5,
        )


def test_run_dexter_agent_raises_clear_error_when_subprocess_times_out(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise service.subprocess.TimeoutExpired(cmd=["dexter"], timeout=3)

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Dexter timed out after 3s"):
        service.run_dexter_agent(
            request=AgentQueryRequest(question="ping"),
            command="dexter",
            transport="cli",
            bridge_url="",
            model="",
            toolsets="",
            timeout_seconds=3,
        )


def test_execute_dexter_agent_query_appends_dexter_audit(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        service,
        "run_dexter_agent",
        lambda **kwargs: {
            "answer": "Dexter answer",
            "stdout": "line1\nline2",
            "stderr": "warn",
            "command": "dexter",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "sql,files",
            "transport": "sidecar",
            "tables_used": ["dexter_sidecar"],
        },
    )

    envelope = service.execute_dexter_agent_query(
        request=AgentQueryRequest(
            question="ping",
            context={"user_id": "u_dexter", "run_id": "agent_run:dexter-audit"},
        ),
        governance_dir=str(tmp_path / "governance"),
        settings=type(
            "SettingsStub",
            (),
            {
                "agent_dexter_command": "dexter",
                "agent_dexter_transport": "sidecar",
                "agent_dexter_bridge_url": "http://127.0.0.1:7892",
                "agent_dexter_model": "dexter-test",
                "agent_dexter_toolsets": "sql,files",
                "agent_dexter_timeout_seconds": 9.0,
            },
        )(),
    )

    assert envelope.answer == "Dexter answer"
    assert envelope.evidence.evidence_rows == 0

    audit_path = tmp_path / "governance" / "agent_audit.jsonl"
    rows = audit_path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(rows[-1])
    assert payload["run_id"] == "agent_run:dexter-audit"
    assert payload["tools_used"] == ["portfolio.scan"]
    assert payload["tables_used"] == ["dexter_sidecar"]
    assert payload["filters_applied"]["provider"] == "dexter"
    assert payload["result_meta"]["dexter_tool_name"] == "portfolio.scan"
    assert "stdout_excerpt" not in payload["result_meta"]
    assert "stderr_excerpt" not in payload["result_meta"]
    assert "dexter_error" not in payload["result_meta"]
    assert "dexter_error_code" not in payload["result_meta"]


def test_execute_dexter_agent_query_fails_closed_when_audit_write_fails(
    tmp_path: Path,
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(
        service,
        "run_dexter_agent",
        lambda **_kwargs: {
            "answer": "Dexter answer",
            "stdout": "",
            "stderr": "",
            "command": "dexter",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "evidence,research",
            "transport": "sidecar",
        },
    )
    monkeypatch.setattr(
        service,
        "append_agent_audit",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("governance dir is read-only")
        ),
    )
    monkeypatch.setattr(service, "_DEXTER_AUDIT_FAILURE_COUNT", 0, raising=False)

    with caplog.at_level("ERROR"), pytest.raises(RuntimeError, match="unaudited response"):
        service.execute_dexter_agent_query(
            request=AgentQueryRequest(
                question="ping",
                context={"run_id": "agent_run:dexter-audit-failure"},
            ),
            governance_dir=str(tmp_path / "governance"),
            settings=_dexter_settings_stub(tmp_path),
        )

    assert service._DEXTER_AUDIT_FAILURE_COUNT == 1
    assert any(record.levelname == "ERROR" for record in caplog.records)
    assert "error_code=dexter_audit_append_failed" in caplog.text
    assert "failure_count=1" in caplog.text
    assert "run_id=agent_run:dexter-audit-failure" in caplog.text
    assert "read-only" not in caplog.text


def test_execute_dexter_agent_query_appends_sent_prompt(tmp_path: Path, monkeypatch):
    captured: dict[str, str] = {}

    def fake_run(**kwargs):
        captured["prompt"] = str(kwargs.get("prompt_override") or "")
        return {
            "answer": "Dexter answer",
            "stdout": "",
            "stderr": "",
            "command": "dexter",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "sql,files",
            "transport": "sidecar",
        }

    monkeypatch.setattr(service, "run_dexter_agent", fake_run)

    envelope = service.execute_dexter_agent_query(
        request=AgentQueryRequest(
            question="研究雷达最新进展",
            context={"user_id": "u_dexter", "run_id": "agent_run:dexter-prompt"},
        ),
        governance_dir=str(tmp_path / "governance"),
        settings=_dexter_settings_stub(tmp_path),
    )

    payload = json.loads(
        (tmp_path / "governance" / "agent_prompt.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[-1]
    )
    assert payload["provider"] == "dexter"
    assert payload["user_id"] == "u_dexter"
    assert payload["run_id"] == "agent_run:dexter-prompt"
    # trace_id 是与 agent_audit 对账的唯一键，两条流必须写同一个值。
    assert payload["trace_id"] == envelope.result_meta.trace_id
    # 落盘的必须是真正送给 provider 的那一份，不是事后重建的近似值。
    assert payload["prompt"] == captured["prompt"]
    assert "研究雷达最新进展" in payload["prompt"]
    assert payload["prompt_chars"] == len(payload["prompt"])
    assert "error_code" not in payload


def test_execute_dexter_agent_query_appends_prompt_when_runtime_fails(
    tmp_path: Path, monkeypatch
):
    def raise_runtime(**_kwargs):
        raise RuntimeError("dexter unavailable")

    monkeypatch.setattr(service, "run_dexter_agent", raise_runtime)

    service.execute_dexter_agent_query(
        request=AgentQueryRequest(
            question="组合久期",
            context={"user_id": "u_dexter"},
        ),
        governance_dir=str(tmp_path / "governance"),
        settings=_dexter_settings_stub(tmp_path),
    )

    payload = json.loads(
        (tmp_path / "governance" / "agent_prompt.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[-1]
    )
    # 通道故障这一轮同样构建并尝试送出了 prompt，留痕不能因为失败而缺席。
    assert "组合久期" in payload["prompt"]
    assert payload["error_code"] == "dexter_runtime_unavailable"


def _dexter_settings_stub(tmp_path: Path, **overrides):
    attrs = {
        "duckdb_path": str(tmp_path / "missing.duckdb"),
        "agent_dexter_command": "dexter",
        "agent_dexter_transport": "sidecar",
        "agent_dexter_bridge_url": "http://127.0.0.1:7892",
        "agent_dexter_model": "dexter-test",
        "agent_dexter_toolsets": "sql,files",
        "agent_dexter_timeout_seconds": 9.0,
        **overrides,
    }
    return type("SettingsStub", (), attrs)()


def test_execute_dexter_agent_query_falls_back_and_audits_when_runtime_fails(
    tmp_path: Path, monkeypatch
):
    def raise_runtime(**_kwargs):
        raise RuntimeError("Dexter timed out after 9s")

    monkeypatch.setattr(service, "run_dexter_agent", raise_runtime)

    envelope = service.execute_dexter_agent_query(
        request=AgentQueryRequest(
            question="ping",
            context={"user_id": "u_dexter", "run_id": "agent_run:dexter-fallback"},
        ),
        governance_dir=str(tmp_path / "governance"),
        settings=_dexter_settings_stub(tmp_path),
    )

    assert envelope.result_meta.result_kind == "agent.dexter_fallback"
    assert envelope.result_meta.trace_id.startswith("tr_agent_dexter_fallback_")
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.source_version == "sv_dexter_local_fallback"
    assert envelope.result_meta.vendor_version == "vv_dexter_unavailable"
    assert envelope.result_meta.cache_version == "cv_agent_dexter_fallback_v1"
    assert envelope.result_meta.vendor_status == "vendor_unavailable"
    assert envelope.evidence.quality_flag == "warning"
    assert envelope.evidence.evidence_strength == "local_fallback"
    assert envelope.evidence.tables_used == ["dexter_local_fallback"]
    assert envelope.evidence.sql_executed == []
    assert envelope.evidence.evidence_rows == 0
    assert envelope.evidence.filters_applied["provider"] == "dexter"
    assert envelope.evidence.filters_applied["fallback_provider"] == "local"
    assert envelope.evidence.filters_applied["fallback_reason"] == "dexter_runtime_unavailable"
    assert envelope.answer
    assert "Dexter timed out after 9s" not in envelope.answer
    assert any(card.title == "Dexter Status" and card.value == "unavailable" for card in envelope.cards)
    assert envelope.suggested_actions == []

    audit_path = tmp_path / "governance" / "agent_audit.jsonl"
    rows = audit_path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(rows[-1])
    assert payload["run_id"] == "agent_run:dexter-fallback"
    assert payload["tools_used"] == ["dexter_local_fallback"]
    assert payload["tables_used"] == ["dexter_local_fallback"]
    assert payload["filters_applied"]["provider"] == "dexter"
    assert payload["filters_applied"]["fallback_reason"] == "dexter_runtime_unavailable"
    assert payload["result_meta"]["result_kind"] == "agent.dexter_fallback"
    assert payload["result_meta"]["dexter_tool_name"] == "dexter_local_fallback"
    assert payload["result_meta"]["dexter_error"] == "Dexter timed out after 9s"
    assert payload["result_meta"]["dexter_error_code"] == "dexter_runtime_unavailable"


def test_execute_dexter_agent_query_fallback_preserves_research_context_evidence(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        service,
        "build_dexter_research_context",
        lambda **kwargs: {
            "domain": "stock",
            "as_of_date": "2026-04-29",
            "tables_used": ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
            "filters_applied": {
                "research_domain": "stock",
                "stock_code": "000001.SZ",
                "as_of_date": "2026-04-29",
            },
            "sql_executed": [
                (
                    "select trade_date, stock_code, close_value "
                    "from choice_stock_daily_observation "
                    "where stock_code = ? and (? = '' or trade_date <= ?) "
                    "order by trade_date desc limit 1"
                )
            ],
            "evidence_rows": 2,
            "quality_flag": "warning",
            "limitations": ["choice_news_event is not landed."],
            "stale_sources": [
                "choice_stock_daily_observation is stale: trade_date 2026-04-29 is 30 days "
                "behind 2026-05-29 (threshold 14d)."
            ],
            "stock": {"daily_observation": {"stock_code": "000001.SZ", "close_value": 21.9}},
            "macro": {},
        },
    )

    def raise_runtime(**_kwargs):
        raise RuntimeError("Dexter sidecar unavailable: connection refused")

    monkeypatch.setattr(service, "run_dexter_agent", raise_runtime)

    envelope = service.execute_dexter_agent_query(
        request=AgentQueryRequest(
            question="分析这只股票",
            filters={"research_domain": "stock"},
            context={"user_id": "u_dexter"},
        ),
        governance_dir=str(tmp_path / "governance"),
        settings=_dexter_settings_stub(tmp_path),
    )

    assert envelope.result_meta.result_kind == "agent.dexter_fallback"
    assert envelope.evidence.tables_used == [
        "dexter_local_fallback",
        "choice_stock_daily_observation",
        "choice_stock_factor_snapshot",
    ]
    assert envelope.evidence.evidence_rows == 2
    assert envelope.evidence.evidence_strength == "local_fallback"
    assert envelope.evidence.filters_applied["research_domain"] == "stock"
    assert envelope.evidence.filters_applied["stock_code"] == "000001.SZ"
    assert envelope.evidence.sql_executed
    assert all(
        sql.lower().startswith(("select", "with"))
        for sql in envelope.evidence.sql_executed
    )
    assert "000001.SZ" not in envelope.evidence.sql_executed[0]
    assert envelope.result_meta.sql_executed == envelope.evidence.sql_executed
    limitations_card = next(card for card in envelope.cards if card.title == "Research Limitations")
    assert any("is stale" in item["item"] for item in limitations_card.data)

    audit_path = tmp_path / "governance" / "agent_audit.jsonl"
    payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["tables_used"] == envelope.evidence.tables_used
    assert payload["result_meta"]["dexter_error_code"] == "dexter_runtime_unavailable"


def test_execute_dexter_agent_query_cli_timeout_reaches_fallback_end_to_end(
    tmp_path: Path, monkeypatch
):
    def fake_run(*_args, **_kwargs):
        raise service.subprocess.TimeoutExpired(cmd=["dexter"], timeout=9)

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    envelope = service.execute_dexter_agent_query(
        request=AgentQueryRequest(question="ping", context={"user_id": "u_dexter"}),
        governance_dir=str(tmp_path / "governance"),
        settings=_dexter_settings_stub(tmp_path, agent_dexter_transport="cli"),
    )

    assert envelope.result_meta.result_kind == "agent.dexter_fallback"
    assert envelope.result_meta.vendor_status == "vendor_unavailable"
    assert envelope.evidence.filters_applied["transport"] == "cli"
    payload = json.loads(
        (tmp_path / "governance" / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert payload["result_meta"]["dexter_error"].startswith("Dexter timed out after")


def test_execute_dexter_agent_query_injects_research_context_into_prompt(tmp_path: Path, monkeypatch):
    from tests.test_agent_api_contract import _agent_auth_fields, _configure_agent_scope_store

    scope_store = _configure_agent_scope_store(tmp_path, monkeypatch)
    for resource in ("market_data.livermore", "choice_news.data"):
        scope_store.grant_scope(user_id="u_dexter", role=None, resource=resource, action="read")
    calls = []

    monkeypatch.setattr(
        service,
        "build_dexter_research_context",
        lambda **kwargs: {
            "domain": "stock",
            "as_of_date": "2026-04-29",
            "tables_used": ["choice_stock_daily_observation", "choice_stock_factor_snapshot"],
            "filters_applied": {
                "provider": "dexter",
                "research_domain": "stock",
                "stock_code": "000001.SZ",
                "as_of_date": "2026-04-29",
            },
            "sql_executed": [
                (
                    "select trade_date, stock_code, close_value "
                    "from choice_stock_daily_observation "
                    "where stock_code = ? and (? = '' or trade_date <= ?) "
                    "order by trade_date desc limit 1"
                )
            ],
            "evidence_rows": 2,
            "quality_flag": "warning",
            "limitations": ["choice_news_event is not landed."],
            "stock": {
                "daily_observation": {
                    "stock_code": "000001.SZ",
                    "close_value": 21.9,
                    "source_version": "sv_price",
                }
            },
            "macro": {},
        },
    )

    def fake_run_dexter_agent(**kwargs):
        calls.append(kwargs)
        return {
            "answer": "Stock research answer",
            "summary": "Alpha is strong but news is missing.",
            "findings": ["Close is 21.9"],
            "evidence": ["choice_stock_daily_observation close_value=21.9"],
            "risks": ["Momentum can reverse"],
            "limitations": ["choice_news_event is not landed."],
            "next_drill": ["Refresh Choice news"],
            "stdout": "ok",
            "stderr": "",
            "command": "dexter",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "sql,files",
            "transport": "sidecar",
            "tables_used": ["dexter_sidecar"],
        }

    monkeypatch.setattr(service, "run_dexter_agent", fake_run_dexter_agent)

    envelope = service.execute_dexter_agent_query(
        request=AgentQueryRequest(
            question="分析这只股票",
            filters={"research_domain": "stock"},
            context={"user_id": "u_dexter", "user_role": "reviewer"},
            page_context={
                "page_id": "stock-analysis",
                "current_filters": {"as_of_date": "2026-04-29"},
                "selected_rows": [{"stock_code": "000001.SZ"}],
            },
        ),
        governance_dir=str(tmp_path / "governance"),
        settings=type(
            "SettingsStub",
            (),
            {
                "duckdb_path": str(tmp_path / "moss.duckdb"),
                "agent_dexter_command": "dexter",
                "agent_dexter_transport": "sidecar",
                "agent_dexter_bridge_url": "http://127.0.0.1:7892",
                "agent_dexter_model": "dexter-test",
                "agent_dexter_toolsets": "sql,files",
                "agent_dexter_timeout_seconds": 9.0,
                **_agent_auth_fields(tmp_path),
            },
        )(),
    )

    assert "MOSS research context" in calls[0]["prompt_override"]
    assert "choice_stock_daily_observation" in calls[0]["prompt_override"]
    assert "000001.SZ" in calls[0]["prompt_override"]
    assert envelope.evidence.tables_used == [
        "dexter_sidecar",
        "choice_stock_daily_observation",
        "choice_stock_factor_snapshot",
    ]
    assert envelope.evidence.filters_applied["research_domain"] == "stock"
    assert envelope.evidence.filters_applied["stock_code"] == "000001.SZ"
    assert envelope.evidence.evidence_rows == 2
    assert envelope.evidence.evidence_strength == "mixed"
    assert envelope.evidence.quality_flag == "warning"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.result_kind == "agent.dexter"
    assert envelope.evidence.sql_executed
    assert envelope.result_meta.sql_executed == envelope.evidence.sql_executed
    assert all(
        sql.lower().startswith(("select", "with"))
        for sql in envelope.evidence.sql_executed
    )
    assert "000001.SZ" not in envelope.evidence.sql_executed[0]
    assert any(card.title == "Research Summary" for card in envelope.cards)
    assert any(card.title == "Research Limitations" for card in envelope.cards)


def test_dexter_prompt_budget_drops_low_priority_context_keys_and_discloses(
    tmp_path: Path, monkeypatch
):
    calls = []
    monkeypatch.setattr(service, "_DEXTER_PROMPT_MAX_CHARS", 2500)
    monkeypatch.setattr(
        service,
        "build_dexter_research_context",
        lambda **_kwargs: {
            "domain": "stock",
            "as_of_date": "2026-04-29",
            "tables_used": ["choice_stock_daily_observation"],
            "filters_applied": {"research_domain": "stock", "stock_code": "000001.SZ"},
            "sql_executed": [],
            "evidence_rows": 1,
            "quality_flag": "warning",
            "limitations": [],
            "stock": {"daily_observation": {"stock_code": "000001.SZ", "close_value": 21.9}},
            "macro": {},
        },
    )

    def fake_run_dexter_agent(**kwargs):
        calls.append(kwargs)
        return {
            "answer": "Stock research answer",
            "stdout": "ok",
            "stderr": "",
            "command": "dexter",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "research",
            "transport": "cli",
            "tables_used": ["dexter_cli"],
        }

    monkeypatch.setattr(service, "run_dexter_agent", fake_run_dexter_agent)

    envelope = service.execute_dexter_agent_query(
        request=AgentQueryRequest(
            question="分析这只股票",
            filters={"research_domain": "stock"},
            context={"conversation": {"recent_turns": ["x" * 2000]}},
            page_context={
                "page_id": "stock-analysis",
                "current_filters": {"as_of_date": "2026-04-29"},
                "selected_rows": [{"payload": "y" * 4000}],
            },
        ),
        governance_dir=str(tmp_path / "governance"),
        settings=_dexter_settings_stub(tmp_path, agent_dexter_transport="cli"),
    )

    prompt = calls[0]["prompt_override"]
    assert len(prompt) <= service._DEXTER_PROMPT_MAX_CHARS
    assert '"page_context"' not in prompt
    assert "[context truncated: dropped keys page_context" in prompt
    assert envelope.evidence.filters_applied["prompt_context_dropped_keys"][0] == "page_context"


def _create_stock_daily_table(conn, *, trade_date: str) -> None:
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar, stock_code varchar, open_value double, high_value double,
          low_value double, close_value double, volume double, amount double,
          pctchange double, turn double, amplitude double, tradestatus varchar,
          highlimit varchar, lowlimit varchar, source_version varchar,
          vendor_version varchar, rule_version varchar, run_id varchar
        )
        """
    )
    conn.execute(
        f"""
        insert into choice_stock_daily_observation values
        ('{trade_date}','000001.SZ',20,22,19,21.9,1000,2000,3.2,1.5,4.1,
         '交易','N','N','sv_price','vv_choice_stock_20260429_0123456789ab','rv_price','run-price')
        """
    )


def test_research_context_truncates_oversized_news_payload_fields(tmp_path: Path):
    duckdb_path = tmp_path / "news-budget.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            """
            create table choice_news_event (
              event_key varchar, received_at varchar, group_id varchar, content_type varchar,
              serial_id bigint, request_id bigint, error_code bigint, error_msg varchar,
              topic_code varchar, item_index bigint, payload_text varchar, payload_json varchar
            )
            """
        )
        conn.execute(
            "insert into choice_news_event values "
            "('n1','2026-04-29T08:00:00Z','tushare_news','text',1,1,0,'','000001.SZ',0,?,?)",
            ["Alpha " + "x" * 5000, "{\"body\": \"" + "y" * 5000 + "\"}"],
        )
    finally:
        conn.close()

    context = context_builder.build_dexter_research_context(
        request=AgentQueryRequest(
            question="分析这只股票",
            filters={
                "research_domain": "stock",
                "stock_code": "000001.SZ",
                "as_of_date": "2026-04-29",
            },
        ),
        duckdb_path=str(duckdb_path),
    )

    news = context["stock"]["news_events"][0]
    marker = "...[truncated]"
    limit = context_builder.MAX_NEWS_PAYLOAD_FIELD_CHARS
    assert news["payload_text"].endswith(marker)
    assert news["payload_json"].endswith(marker)
    assert len(news["payload_text"]) == limit + len(marker)
    assert len(news["payload_json"]) == limit + len(marker)
    assert any("truncated" in item for item in context["limitations"])
    assert (
        len(json.dumps(context, ensure_ascii=False, default=str, indent=2))
        <= context_builder.MAX_CONTEXT_SERIALIZED_CHARS
    )


def test_research_context_budget_drops_rows_and_discloses(tmp_path: Path):
    context = {
        "domain": "stock",
        "as_of_date": "2026-04-29",
        "tables_used": ["choice_news_event"],
        "filters_applied": {"research_domain": "stock", "stock_code": "000001.SZ"},
        "sql_executed": [],
        "evidence_rows": 40,
        "quality_flag": "ok",
        "limitations": [],
        "stock": {
            "news_events": [
                {"event_key": f"n{index}", "payload_text": "z" * 1000}
                for index in range(40)
            ]
        },
        "macro": {},
    }

    context_builder._enforce_context_budget(context)

    remaining = len(context["stock"]["news_events"])
    assert remaining < 40
    assert (
        len(json.dumps(context, ensure_ascii=False, default=str, indent=2))
        <= context_builder.MAX_CONTEXT_SERIALIZED_CHARS
    )
    assert context["evidence_rows"] == remaining
    assert any("budget" in item and "news_events" in item for item in context["limitations"])


def test_research_context_marks_stale_sources_without_touching_limitations(tmp_path: Path):
    duckdb_path = tmp_path / "stale.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        _create_stock_daily_table(conn, trade_date="2026-01-05")
    finally:
        conn.close()

    context = context_builder.build_dexter_research_context(
        request=AgentQueryRequest(
            question="分析这只股票",
            filters={
                "research_domain": "stock",
                "stock_code": "000001.SZ",
                "as_of_date": "2026-08-01",
            },
        ),
        duckdb_path=str(duckdb_path),
    )

    assert context["stock"]["daily_observation"]["stale"] is True
    assert context["stale_sources"]
    assert context["stale_sources"][0].startswith("choice_stock_daily_observation is stale")
    assert "2026-01-05" in context["stale_sources"][0]
    assert context["filters_applied"]["research_stale_sources"] == context["stale_sources"]
    assert all("is stale" not in item for item in context["limitations"])


def test_research_context_fresh_data_has_no_stale_sources(tmp_path: Path):
    duckdb_path = tmp_path / "fresh.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        _create_stock_daily_table(conn, trade_date="2026-08-01")
    finally:
        conn.close()

    context = context_builder.build_dexter_research_context(
        request=AgentQueryRequest(
            question="分析这只股票",
            filters={
                "research_domain": "stock",
                "stock_code": "000001.SZ",
                "as_of_date": "2026-08-01",
            },
        ),
        duckdb_path=str(duckdb_path),
    )

    assert "stale" not in context["stock"]["daily_observation"]
    assert "stale_sources" not in context
    assert "research_stale_sources" not in context["filters_applied"]


def _fake_urlopen_response(body: bytes):
    class _Response:
        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    return _Response()


def _bridge_query_kwargs(**overrides):
    kwargs = {
        "bridge_url": "http://127.0.0.1:7892",
        "prompt": "probe",
        "model": "dexter-test",
        "toolsets": "evidence",
        "timeout_seconds": 5.0,
    }
    kwargs.update(overrides)
    return kwargs


def test_post_dexter_bridge_query_returns_normalized_payload(monkeypatch):
    body = json.dumps(
        {
            "ok": True,
            "answer": "bridge answer",
            "tool_name": "portfolio.scan",
            "tables_used": ["choice_news_event"],
        }
    ).encode("utf-8")
    monkeypatch.setattr(
        service.urllib.request, "urlopen", lambda *_args, **_kwargs: _fake_urlopen_response(body)
    )

    result = service._post_dexter_bridge_query(**_bridge_query_kwargs())

    assert result["answer"] == "bridge answer"
    assert result["transport"] == "sidecar"
    assert result["tool_name"] == "portfolio.scan"
    assert result["tables_used"] == ["choice_news_event"]


def test_post_dexter_bridge_query_wraps_malformed_json_as_runtime_error(monkeypatch):
    monkeypatch.setattr(
        service.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _fake_urlopen_response(b"<html>bad gateway</html>"),
    )

    with pytest.raises(RuntimeError, match="invalid JSON"):
        service._post_dexter_bridge_query(**_bridge_query_kwargs())


def test_post_dexter_bridge_query_wraps_non_utf8_garbage_as_runtime_error(monkeypatch):
    monkeypatch.setattr(
        service.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _fake_urlopen_response(b"\xff\xfe\xfa garbage"),
    )

    with pytest.raises(RuntimeError, match="invalid JSON"):
        service._post_dexter_bridge_query(**_bridge_query_kwargs())


def test_post_dexter_bridge_query_replaces_invalid_utf8_inside_valid_json(monkeypatch):
    monkeypatch.setattr(
        service.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _fake_urlopen_response(b'{"ok": true, "answer": "caf\xe9"}'),
    )

    result = service._post_dexter_bridge_query(**_bridge_query_kwargs())

    assert result["answer"] == "caf\ufffd"


def test_post_dexter_bridge_query_wraps_http_error_detail_as_runtime_error(monkeypatch):
    def raise_http_error(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            url="http://127.0.0.1:7892/query",
            code=502,
            msg="Bad Gateway",
            hdrs=None,
            fp=io.BytesIO(b"bridge exploded"),
        )

    monkeypatch.setattr(service.urllib.request, "urlopen", raise_http_error)

    with pytest.raises(RuntimeError, match="Dexter sidecar failed: bridge exploded"):
        service._post_dexter_bridge_query(**_bridge_query_kwargs())


def test_post_dexter_bridge_query_raises_runtime_error_when_bridge_reports_not_ok(monkeypatch):
    body = json.dumps({"ok": False, "error": "toolset rejected"}).encode("utf-8")
    monkeypatch.setattr(
        service.urllib.request, "urlopen", lambda *_args, **_kwargs: _fake_urlopen_response(body)
    )

    with pytest.raises(RuntimeError, match="toolset rejected"):
        service._post_dexter_bridge_query(**_bridge_query_kwargs())


def test_post_dexter_bridge_query_rejects_non_dict_payload(monkeypatch):
    monkeypatch.setattr(
        service.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _fake_urlopen_response(b"[1, 2]"),
    )

    with pytest.raises(RuntimeError, match="invalid payload"):
        service._post_dexter_bridge_query(**_bridge_query_kwargs())


def test_execute_dexter_agent_query_converges_malformed_bridge_json_to_fallback(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        service.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _fake_urlopen_response(b"<html>bad gateway</html>"),
    )

    envelope = service.execute_dexter_agent_query(
        request=AgentQueryRequest(
            question="ping",
            context={"user_id": "u_dexter", "run_id": "agent_run:dexter-bad-json"},
        ),
        governance_dir=str(tmp_path / "governance"),
        settings=_dexter_settings_stub(tmp_path),
    )

    assert envelope.result_meta.result_kind == "agent.dexter_fallback"
    assert envelope.result_meta.vendor_status == "vendor_unavailable"

    audit_path = tmp_path / "governance" / "agent_audit.jsonl"
    payload = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["run_id"] == "agent_run:dexter-bad-json"
    assert payload["result_meta"]["dexter_error"] == "Dexter sidecar returned invalid JSON."


def test_run_dexter_agent_wraps_cli_oserror_as_runtime_error(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise PermissionError("dexter is not executable")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Dexter command failed to start"):
        service.run_dexter_agent(
            request=AgentQueryRequest(question="ping"),
            command="dexter",
            transport="cli",
            bridge_url="",
            model="",
            toolsets="",
            timeout_seconds=5,
        )


def test_execute_dexter_agent_query_cli_oserror_reaches_fallback_end_to_end(
    tmp_path: Path, monkeypatch
):
    def fake_run(*_args, **_kwargs):
        raise OSError(206, "The filename or extension is too long")

    monkeypatch.setattr(service.subprocess, "run", fake_run)

    envelope = service.execute_dexter_agent_query(
        request=AgentQueryRequest(question="ping", context={"user_id": "u_dexter"}),
        governance_dir=str(tmp_path / "governance"),
        settings=_dexter_settings_stub(tmp_path, agent_dexter_transport="cli"),
    )

    assert envelope.result_meta.result_kind == "agent.dexter_fallback"
    assert envelope.result_meta.vendor_status == "vendor_unavailable"
    payload = json.loads(
        (tmp_path / "governance" / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert payload["result_meta"]["dexter_error"].startswith("Dexter command failed to start")


def test_execute_dexter_agent_query_converges_research_context_failure_to_fallback(
    tmp_path: Path, monkeypatch
):
    def raise_value_error(**_kwargs):
        raise ValueError("research context blew up")

    monkeypatch.setattr(service, "build_dexter_research_context", raise_value_error)

    envelope = service.execute_dexter_agent_query(
        request=AgentQueryRequest(question="ping", context={"user_id": "u_dexter"}),
        governance_dir=str(tmp_path / "governance"),
        settings=_dexter_settings_stub(tmp_path),
    )

    assert envelope.result_meta.result_kind == "agent.dexter_fallback"
    assert envelope.evidence.tables_used == ["dexter_local_fallback"]
    payload = json.loads(
        (tmp_path / "governance" / "agent_audit.jsonl").read_text(encoding="utf-8").splitlines()[-1]
    )
    assert payload["result_meta"]["dexter_error"] == "research context blew up"


def test_build_dexter_envelope_uses_transport_for_source_version_when_sidecar_reports_real_tables():
    envelope = service.build_dexter_envelope(
        request=AgentQueryRequest(question="ping"),
        result={
            "answer": "pong",
            "stdout": "pong",
            "stderr": "",
            "command": "dexter_sidecar",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "evidence,research",
            "transport": "sidecar",
            "tables_used": ["choice_news_event"],
        },
    )

    assert envelope.result_meta.source_version == "sv_dexter_sidecar"
    assert envelope.evidence.tables_used == ["choice_news_event"]


def test_build_dexter_envelope_research_filters_cannot_override_runtime_disclosure():
    envelope = service.build_dexter_envelope(
        request=AgentQueryRequest(
            question="stock research",
            filters={"provider": "spoofed", "transport": "spoofed"},
        ),
        result={
            "answer": "Provider answer",
            "stdout": "ok",
            "stderr": "",
            "command": "dexter",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "evidence,research",
            "transport": "sidecar",
            "tables_used": ["dexter_sidecar"],
        },
        research_context={
            "domain": "stock",
            "tables_used": ["choice_stock_daily_observation"],
            "filters_applied": {
                "provider": "spoofed",
                "model": "spoofed-model",
                "toolsets": "terminal",
                "transport": "spoofed",
                "research_domain": "stock",
            },
            "sql_executed": [],
            "evidence_rows": 1,
            "quality_flag": "ok",
            "limitations": [],
        },
    )

    assert envelope.evidence.filters_applied["provider"] == "dexter"
    assert envelope.evidence.filters_applied["model"] == "dexter-test"
    assert envelope.evidence.filters_applied["toolsets"] == "evidence,research"
    assert envelope.evidence.filters_applied["transport"] == "sidecar"
    assert envelope.evidence.filters_applied["research_domain"] == "stock"


def test_build_dexter_fallback_envelope_research_filters_cannot_override_fallback_disclosure():
    envelope = service.build_dexter_fallback_envelope(
        request=AgentQueryRequest(
            question="stock research",
            filters={"fallback_reason": "spoofed"},
        ),
        result={
            "answer": "",
            "stdout": "",
            "stderr": "",
            "command": "dexter",
            "tool_name": "dexter_local_fallback",
            "model": "dexter-test",
            "toolsets": "evidence,research",
            "transport": "sidecar",
            "error": "boom",
            "error_code": "dexter_runtime_unavailable",
        },
        research_context={
            "domain": "stock",
            "tables_used": ["choice_stock_daily_observation"],
            "filters_applied": {
                "provider": "spoofed",
                "fallback_provider": "spoofed",
                "fallback_reason": "spoofed",
                "research_domain": "stock",
            },
            "sql_executed": [],
            "evidence_rows": 1,
            "quality_flag": "warning",
            "limitations": [],
        },
    )

    assert envelope.evidence.filters_applied["provider"] == "dexter"
    assert envelope.evidence.filters_applied["fallback_provider"] == "local"
    assert envelope.evidence.filters_applied["fallback_reason"] == "dexter_runtime_unavailable"
    assert envelope.evidence.filters_applied["research_domain"] == "stock"


def test_build_dexter_envelope_discloses_stale_sources_in_card_and_filters():
    stale_note = (
        "choice_stock_daily_observation is stale: trade_date 2026-01-05 is 209 days "
        "behind 2026-08-01 (threshold 14d)."
    )
    envelope = service.build_dexter_envelope(
        request=AgentQueryRequest(question="stock research"),
        result={
            "answer": "Provider answer",
            "stdout": "ok",
            "stderr": "",
            "command": "dexter",
            "tool_name": "portfolio.scan",
            "model": "dexter-test",
            "toolsets": "evidence,research",
            "transport": "sidecar",
            "tables_used": ["dexter_sidecar"],
        },
        research_context={
            "domain": "stock",
            "tables_used": ["choice_stock_daily_observation"],
            "filters_applied": {
                "research_domain": "stock",
                "stock_code": "000001.SZ",
                "research_stale_sources": [stale_note],
            },
            "sql_executed": [],
            "evidence_rows": 1,
            "quality_flag": "warning",
            "limitations": [],
            "stale_sources": [stale_note],
        },
    )

    assert envelope.evidence.filters_applied["research_stale_sources"] == [stale_note]
    assert envelope.result_meta.filters_applied["research_stale_sources"] == [stale_note]
    limitations_card = next(card for card in envelope.cards if card.title == "Research Limitations")
    assert {"item": stale_note} in limitations_card.data
