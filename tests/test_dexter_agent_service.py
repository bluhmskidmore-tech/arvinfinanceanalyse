from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.services import dexter_agent_service as service


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
    assert envelope.evidence.filters_applied["toolsets"] == "sql,files"


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
    assert result["toolsets"] == "sql,files"
    assert result["transport"] == "cli"
    assert calls[0]["args"][0] == "dexter"


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

    assert calls == [
        {
            "args": [
                "dexter-cli",
                "query",
                "--json",
                "--prompt",
                calls[0]["args"][4],
                "--model",
                "dexter-model",
                "--toolsets",
                "sql,files",
            ],
            "check": False,
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": 1.0,
        }
    ]
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
        request=AgentQueryRequest(question="ping", context={"user_id": "u_dexter"}),
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
    assert envelope.evidence.evidence_rows == 1

    audit_path = tmp_path / "governance" / "agent_audit.jsonl"
    rows = audit_path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(rows[-1])
    assert payload["tools_used"] == ["portfolio.scan"]
    assert payload["tables_used"] == ["dexter_sidecar"]
    assert payload["filters_applied"]["provider"] == "dexter"
    assert payload["result_meta"]["stdout_excerpt"] == "line1\nline2"
    assert payload["result_meta"]["stderr_excerpt"] == "warn"


def test_execute_dexter_agent_query_injects_research_context_into_prompt(tmp_path: Path, monkeypatch):
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
    assert envelope.evidence.quality_flag == "warning"
    assert envelope.result_meta.formal_use_allowed is False
    assert envelope.result_meta.result_kind == "agent.dexter"
    assert any(card.title == "Research Summary" for card in envelope.cards)
    assert any(card.title == "Research Limitations" for card in envelope.cards)
