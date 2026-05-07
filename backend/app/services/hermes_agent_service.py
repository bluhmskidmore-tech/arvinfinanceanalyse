from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import (
    AgentCard,
    AgentEnvelope,
    AgentEvidence,
    AgentResultMeta,
)
from backend.app.governance.agent_audit import AgentAuditPayload, append_agent_audit
from backend.app.repositories.governance_repo import GovernanceRepository

RULE_VERSION = "rv_agent_hermes_v1"


def execute_hermes_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
    settings: Any,
) -> AgentEnvelope:
    result = run_hermes_agent(
        request=request,
        command=str(settings.agent_hermes_command),
        wsl_distro=str(settings.agent_hermes_wsl_distro or ""),
        model=str(settings.agent_hermes_model or ""),
        max_turns=int(settings.agent_hermes_max_turns),
        timeout_seconds=float(settings.agent_hermes_timeout_seconds),
    )
    envelope = build_hermes_envelope(request=request, result=result)
    _append_hermes_audit(request, governance_dir, envelope, result)
    return envelope


def run_hermes_agent(
    *,
    request: AgentQueryRequest,
    command: str,
    wsl_distro: str,
    model: str,
    max_turns: int,
    timeout_seconds: float,
) -> dict[str, str]:
    prompt = _build_hermes_prompt(request)
    args = _build_hermes_command(
        command=command,
        wsl_distro=wsl_distro,
        model=model,
        max_turns=max_turns,
        prompt=prompt,
    )
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("NO_COLOR", "1")
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(timeout_seconds, 1.0),
            env=env,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Hermes command not found: {command}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Hermes timed out after {timeout_seconds:g}s") from exc

    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    if completed.returncode != 0:
        detail = _truncate((stderr or stdout).strip(), 2000)
        raise RuntimeError(f"Hermes failed with exit code {completed.returncode}: {detail}")

    return {
        "answer": _extract_final_answer(stdout),
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
        "model": model or "default",
    }


def build_hermes_envelope(
    *,
    request: AgentQueryRequest,
    result: dict[str, str],
) -> AgentEnvelope:
    trace_id = f"tr_agent_hermes_{uuid4().hex[:12]}"
    generated_at = datetime.now(timezone.utc)
    filters_applied = {
        key: value for key, value in request.filters.items() if value not in (None, "")
    }
    filters_applied["provider"] = "hermes"
    if result.get("model"):
        filters_applied["model"] = result["model"]

    evidence = AgentEvidence(
        tables_used=["hermes_cli"],
        filters_applied=filters_applied,
        sql_executed=[],
        evidence_rows=1,
        quality_flag="ok",
    )
    result_meta = AgentResultMeta(
        trace_id=trace_id,
        basis=request.basis,
        result_kind="agent.hermes",
        formal_use_allowed=False,
        source_version="sv_hermes_cli",
        vendor_version="vv_hermes",
        rule_version=RULE_VERSION,
        cache_version="cv_agent_hermes_v1",
        quality_flag="ok",
        vendor_status="ok",
        fallback_mode="none",
        scenario_flag=request.basis == "scenario",
        generated_at=generated_at,
        tables_used=evidence.tables_used,
        filters_applied=evidence.filters_applied,
        sql_executed=[],
        evidence_rows=evidence.evidence_rows,
    )
    return AgentEnvelope(
        answer=result["answer"],
        cards=[
            AgentCard(type="text", title="Hermes Agent", value=result["answer"]),
            AgentCard(type="metric", title="Provider", value="hermes"),
            AgentCard(type="metric", title="Model", value=result.get("model") or "default"),
        ],
        evidence=evidence,
        result_meta=result_meta,
        next_drill=[],
        suggested_actions=[],
    )


def _build_hermes_command(
    *,
    command: str,
    wsl_distro: str,
    model: str,
    max_turns: int,
    prompt: str,
) -> list[str]:
    hermes_args = [
        "chat",
        "-Q",
        "-q",
        prompt,
        "--max-turns",
        str(max(max_turns, 1)),
        "--source",
        "tool",
    ]
    if model:
        hermes_args.extend(["--model", model])

    if command.lower().endswith("wsl.exe") or command.lower() == "wsl":
        args = [command]
        if wsl_distro:
            args.extend(["-d", wsl_distro])
        args.extend(["-e", "/usr/local/bin/hermes"])
        args.extend(hermes_args)
        return args

    return [command, *hermes_args]


def _build_hermes_prompt(request: AgentQueryRequest) -> str:
    context = {
        "basis": request.basis,
        "filters": request.filters,
        "position_scope": request.position_scope,
        "currency_basis": request.currency_basis,
        "context": request.context,
        "page_context": request.page_context.model_dump(mode="json") if request.page_context else None,
    }
    return (
        "You are Hermes Agent connected to the MOSS business analytics system. "
        "Answer the user's question directly. If you use tools or evidence, summarize the evidence and limitations. "
        "Do not claim formal financial correctness unless the provided evidence proves it.\n\n"
        f"User question:\n{request.question}\n\n"
        f"MOSS request context:\n{context}"
    )


def _extract_final_answer(stdout: str) -> str:
    lines = [line.rstrip() for line in stdout.splitlines()]
    content: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if content:
                content.append("")
            continue
        if stripped.startswith("Secure MCP Filesystem Server"):
            continue
        if stripped.startswith("Client does not support MCP Roots"):
            continue
        if stripped.startswith("session_id:"):
            continue
        content.append(line)
    answer = "\n".join(content).strip()
    return answer or stdout.strip()


def _append_hermes_audit(
    request: AgentQueryRequest,
    governance_dir: str,
    envelope: AgentEnvelope,
    result: dict[str, str],
) -> None:
    repo = GovernanceRepository(base_dir=governance_dir)
    append_agent_audit(
        repo,
        AgentAuditPayload(
            user_id=str(request.context.get("user_id") or "unknown"),
            query_text=request.question,
            tools_used=["hermes_cli"],
            tables_used=envelope.evidence.tables_used,
            filters_applied=envelope.evidence.filters_applied,
            trace_id=envelope.result_meta.trace_id,
            result_meta={
                **envelope.result_meta.model_dump(mode="json"),
                "stdout_excerpt": _truncate(result.get("stdout", ""), 1000),
                "stderr_excerpt": _truncate(result.get("stderr", ""), 1000),
            },
        ),
    )


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
