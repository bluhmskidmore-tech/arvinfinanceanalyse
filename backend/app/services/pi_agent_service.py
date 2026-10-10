"""Pi RPC provider with a bounded, read-only MOSS harness boundary."""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.app.agent.runtime.local_request_resolution import (
    LocalRequestResolution,
    resolve_local_request,
)
from backend.app.agent.runtime.subprocess_env import build_agent_subprocess_env
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import (
    AgentCard,
    AgentEnvelope,
    AgentEvidence,
    AgentResultMeta,
)
from backend.app.core_finance.calibers.enums import Basis
from backend.app.governance.agent_audit import AgentAuditPayload, append_agent_audit
from backend.app.governance.agent_prompt import AgentPromptPayload, append_agent_prompt
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services.jev_decision_service import JevDecision, decide_jev

RULE_VERSION = "rv_agent_pi_v1"
_PI_RUNTIME_ERROR = "pi_runtime_unavailable"
_PI_CANCELLED_ERROR = "pi_cancelled"
_PI_PROMPT_MAX_CHARS = 16_000
_PI_OUTPUT_MAX_CHARS = 16_000
_PI_STDERR_MAX_CHARS = 2_000
_DEFAULT_PI_COMMAND = "pi.cmd" if os.name == "nt" else "pi"
_PI_PROVIDER_ENV_KEYS: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
    "xai": ("XAI_API_KEY",),
    "minimax": ("MINIMAX_API_KEY",),
}
_LOGGER = logging.getLogger(__name__)


def execute_pi_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
    settings: Any,
    *,
    cancel_event: threading.Event | None = None,
) -> AgentEnvelope:
    """Execute one Pi turn, or return a governed local fallback envelope."""

    prompt = ""
    result: dict[str, Any] = _runtime_defaults(request=request, settings=settings)
    resolution: LocalRequestResolution | None = None
    decision: JevDecision | None = None
    try:
        resolution = resolve_local_request(request)
        decision = decide_jev(request, settings, resolution=resolution)
        if not decision.allowed:
            result.update(
                {
                    "error_code": decision.error_code or decision.reason_code,
                    "error": decision.reason_code,
                }
            )
            envelope = build_pi_fallback_envelope(
                request=request,
                result=result,
                decision=decision,
                resolution=resolution,
            )
        else:
            prompt = _build_pi_prompt(request, resolution=resolution, decision=decision)
            result.update(
                run_pi_agent(
                    command=str(
                        getattr(settings, "agent_pi_command", _DEFAULT_PI_COMMAND)
                        or _DEFAULT_PI_COMMAND
                    ),
                    model=str(request.model or getattr(settings, "agent_pi_model", "") or ""),
                    timeout_seconds=float(
                        getattr(settings, "agent_pi_timeout_seconds", 120.0) or 120.0
                    ),
                    max_turns=int(getattr(settings, "agent_pi_max_turns", 1) or 1),
                    prompt=prompt,
                    forward_api_key=bool(
                        getattr(settings, "agent_pi_forward_api_key", False)
                    ),
                    cancel_event=cancel_event,
                )
            )
            result.update(_jev_result_fields(decision))
            envelope = build_pi_envelope(
                request=request,
                result=result,
                decision=decision,
                resolution=resolution,
            )
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        error_code = _PI_CANCELLED_ERROR if "cancel" in str(exc).lower() else _PI_RUNTIME_ERROR
        _LOGGER.warning(
            "Pi provider runtime failed provider=pi error_type=%s error_code=%s",
            exc.__class__.__name__,
            error_code,
        )
        result.update({"error_code": error_code, "error": _truncate(str(exc), 2000)})
        envelope = build_pi_fallback_envelope(
            request=request,
            result=result,
            decision=decision,
            resolution=resolution,
        )

    _append_pi_audit(request, governance_dir, envelope, result, decision=decision)
    _append_pi_prompt(request, governance_dir, envelope, result, prompt)
    return envelope


def run_pi_agent(
    *,
    command: str,
    model: str,
    timeout_seconds: float,
    max_turns: int,
    prompt: str,
    forward_api_key: bool = False,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Run one JSONL Pi RPC prompt with all Pi-side tools disabled."""

    args = _build_pi_rpc_command(command=command, model=model)
    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=_build_pi_subprocess_env(forward_api_key=forward_api_key, model=model),
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Pi command not found: {command}") from exc
    except OSError as exc:
        raise RuntimeError(f"Pi command failed to start: {exc}") from exc

    if process.stdin is None or process.stdout is None:
        _terminate_process(process)
        raise RuntimeError("Pi RPC pipes were not available.")
    stdout = process.stdout

    output_queue: queue.Queue[str | None] = queue.Queue()
    stderr_parts: list[str] = []
    stdout_parts: list[str] = []

    def _read_stdout() -> None:
        try:
            for line in stdout:
                output_queue.put(line)
        finally:
            output_queue.put(None)

    def _read_stderr() -> None:
        if process.stderr is None:
            return
        for line in process.stderr:
            if sum(len(item) for item in stderr_parts) < _PI_STDERR_MAX_CHARS:
                stderr_parts.append(line)

    stdout_thread = threading.Thread(target=_read_stdout, name="pi-rpc-stdout", daemon=True)
    stderr_thread = threading.Thread(target=_read_stderr, name="pi-rpc-stderr", daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    try:
        process.stdin.write(json.dumps({"type": "prompt", "message": prompt}, ensure_ascii=False) + "\n")
        process.stdin.flush()
    except (OSError, ValueError) as exc:
        _terminate_process(process)
        raise RuntimeError("Pi RPC prompt could not be sent.") from exc

    text_deltas: list[str] = []
    authoritative_answer = ""
    terminal_event_seen = False
    deadline = time.monotonic() + max(float(timeout_seconds), 1.0)
    try:
        while time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("Pi run cancelled.")
            try:
                line = output_queue.get(timeout=min(0.25, max(deadline - time.monotonic(), 0.01)))
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if line is None:
                break
            stdout_parts.append(line)
            event = _parse_rpc_event(line)
            if event is None:
                continue
            event_type = str(event.get("type") or "").strip().lower()
            if event_type == "message_update":
                delta_event = event.get("assistantMessageEvent") or event.get("message")
                delta = _extract_text(delta_event)
                if delta:
                    text_deltas.append(delta)
            elif event_type == "message_end":
                message = event.get("message")
                if _rpc_value_has_error(message):
                    raise RuntimeError("Pi RPC reported an execution error.")
                answer = _extract_assistant_text(message)
                if answer:
                    authoritative_answer = answer
            elif event_type == "agent_end":
                if _rpc_value_has_error(event):
                    raise RuntimeError("Pi RPC reported an execution error.")
                answer = _extract_assistant_text(event.get("message")) or _extract_assistant_text(
                    event.get("messages")
                )
                if answer:
                    authoritative_answer = answer
                terminal_event_seen = True
                break
            elif event_type == "agent_settled":
                terminal_event_seen = True
                break
            elif event_type in {"error", "agent_error"}:
                raise RuntimeError("Pi RPC reported an execution error.")

        if not terminal_event_seen and time.monotonic() >= deadline:
            raise RuntimeError(f"Pi timed out after {timeout_seconds:g}s")

        answer = authoritative_answer.strip() or "".join(text_deltas).strip()
        if not answer:
            detail = _truncate("".join(stderr_parts).strip(), _PI_STDERR_MAX_CHARS)
            raise RuntimeError(f"Pi returned no assistant text{': ' + detail if detail else '.'}")
        return {
            "answer": _truncate(answer, _PI_OUTPUT_MAX_CHARS),
            "stdout": _truncate("".join(stdout_parts), _PI_OUTPUT_MAX_CHARS),
            "stderr": _truncate("".join(stderr_parts), _PI_STDERR_MAX_CHARS),
            "command": command,
            "model": model or "default",
            "toolsets": "none",
            "transport": "rpc",
            "max_turns": max(int(max_turns), 1),
            "turns": 1,
            "tool_calls": 0,
        }
    finally:
        _terminate_process(process)
        stdout_thread.join(timeout=0.5)
        stderr_thread.join(timeout=0.5)


def build_pi_envelope(
    *,
    request: AgentQueryRequest,
    result: dict[str, Any],
    decision: JevDecision,
    resolution: LocalRequestResolution | None = None,
) -> AgentEnvelope:
    trace_id = f"tr_agent_pi_{uuid4().hex[:12]}"
    filters_applied = _runtime_filters(request=request, result=result, decision=decision)
    if resolution is not None:
        filters_applied["routing_reason"] = resolution.reason
    evidence = AgentEvidence(
        tables_used=["pi_rpc"],
        filters_applied=filters_applied,
        sql_executed=[],
        evidence_rows=0,
        quality_flag="warning",
        evidence_strength="provider_runtime",
    )
    result_meta = AgentResultMeta(
        trace_id=trace_id,
        basis=request.basis,
        result_kind="agent.pi",
        formal_use_allowed=False,
        source_version="sv_pi_rpc",
        vendor_version="vv_pi",
        rule_version=RULE_VERSION,
        cache_version="cv_agent_pi_v1",
        quality_flag="warning",
        vendor_status="ok",
        fallback_mode="none",
        scenario_flag=request.basis == Basis.SCENARIO.value,
        generated_at=datetime.now(UTC),
        tables_used=evidence.tables_used,
        filters_applied=filters_applied,
        sql_executed=[],
        evidence_rows=0,
        evidence_strength="provider_runtime",
    )
    return AgentEnvelope(
        answer=str(result.get("answer") or ""),
        cards=[
            AgentCard(type="status", title="Pi Runtime", value="completed"),
            AgentCard(type="metric", title="Provider", value="pi"),
            AgentCard(type="metric", title="Jev Decision", value=decision.route),
        ],
        evidence=evidence,
        result_meta=result_meta,
        next_drill=[],
        suggested_actions=[],
    )


def build_pi_fallback_envelope(
    *,
    request: AgentQueryRequest,
    result: dict[str, Any],
    decision: JevDecision | None = None,
    resolution: LocalRequestResolution | None = None,
) -> AgentEnvelope:
    trace_id = f"tr_agent_pi_fallback_{uuid4().hex[:12]}"
    filters_applied = _runtime_filters(request=request, result=result, decision=decision)
    filters_applied["fallback_provider"] = "local"
    filters_applied["fallback_reason"] = str(result.get("error_code") or _PI_RUNTIME_ERROR)
    if resolution is not None:
        filters_applied["routing_reason"] = resolution.reason
    evidence = AgentEvidence(
        tables_used=["pi_local_fallback"],
        filters_applied=filters_applied,
        sql_executed=[],
        evidence_rows=0,
        quality_flag="warning",
        evidence_strength="local_fallback",
    )
    result_meta = AgentResultMeta(
        trace_id=trace_id,
        basis=request.basis,
        result_kind="agent.pi_fallback",
        formal_use_allowed=False,
        source_version="sv_pi_local_fallback",
        vendor_version="vv_pi_unavailable",
        rule_version=RULE_VERSION,
        cache_version="cv_agent_pi_fallback_v1",
        quality_flag="warning",
        vendor_status="vendor_unavailable",
        fallback_mode="none",
        scenario_flag=request.basis == Basis.SCENARIO.value,
        generated_at=datetime.now(UTC),
        tables_used=evidence.tables_used,
        filters_applied=filters_applied,
        sql_executed=[],
        evidence_rows=0,
        evidence_strength="local_fallback",
    )
    error_code = str(result.get("error_code") or "")
    if error_code.startswith("jev_") or (decision is not None and not decision.allowed):
        answer = "Jev 安全判定未允许 Pi 执行，本轮已停止；不会进入正式金融计算。"
    else:
        answer = "Pi 运行通道当前不可用，本轮已使用本地稳定兜底；不会进入正式金融计算。"
    return AgentEnvelope(
        answer=answer,
        cards=[
            AgentCard(type="status", title="Pi Runtime", value="local fallback"),
            AgentCard(type="metric", title="Provider", value="pi"),
        ],
        evidence=evidence,
        result_meta=result_meta,
        next_drill=[],
        suggested_actions=[],
    )


def _build_pi_rpc_command(*, command: str, model: str) -> list[str]:
    args = [
        command,
        "--mode",
        "rpc",
        "--no-session",
        "--no-tools",
        "--no-extensions",
        "--no-skills",
        "--no-context-files",
    ]
    if model:
        args.extend(["--model", model])
    return args


def _build_pi_subprocess_env(*, forward_api_key: bool, model: str) -> dict[str, str]:
    """Build Pi's environment with an explicit, model-scoped key opt-in."""

    env = build_agent_subprocess_env(PI_SESSION_SOURCE="moss")
    if not forward_api_key:
        return env

    provider = str(model or "").split("/", 1)[0].strip().lower()
    for env_name in _PI_PROVIDER_ENV_KEYS.get(provider, ()):
        api_key = str(os.environ.get(env_name, "") or "").strip()
        if api_key:
            env[env_name] = api_key
            break
    return env


def _build_pi_prompt(
    request: AgentQueryRequest,
    *,
    resolution: LocalRequestResolution,
    decision: JevDecision,
) -> str:
    prompt = (
        "You are the bounded narrative assistant inside the MOSS harness.\n"
        "The server has already performed routing and Jev safety checks.\n"
        "Answer the user's question clearly, but do not calculate, invent, or certify a formal financial metric.\n"
        "Do not request tools, read files, execute commands, or claim that a provider response is formal evidence.\n"
        f"Routing reason: {resolution.reason}\n"
        f"Request basis: {request.basis}\n"
        f"Jev route: {decision.route}\n"
        f"User question:\n{request.question}\n"
    )
    return _truncate(prompt, _PI_PROMPT_MAX_CHARS)


def _runtime_defaults(*, request: AgentQueryRequest, settings: Any) -> dict[str, Any]:
    return {
        "answer": "",
        "command": str(
            getattr(settings, "agent_pi_command", _DEFAULT_PI_COMMAND)
            or _DEFAULT_PI_COMMAND
        ),
        "model": str(request.model or getattr(settings, "agent_pi_model", "") or "default"),
        "toolsets": "none",
        "transport": "rpc",
    }


def _runtime_filters(
    *,
    request: AgentQueryRequest,
    result: dict[str, Any],
    decision: JevDecision | None,
) -> dict[str, Any]:
    filters_applied = {
        key: value for key, value in request.filters.items() if value not in (None, "")
    }
    filters_applied.update(
        {
            "provider": "pi",
            "transport": str(result.get("transport") or "rpc"),
            "tool_policy": "no_tools",
            "model": str(result.get("model") or "default"),
        }
    )
    if decision is not None:
        filters_applied["jev_mode"] = decision.mode
        filters_applied["jev_route"] = decision.route
        filters_applied["jev_source"] = decision.source
        if decision.confidence is not None:
            filters_applied["jev_confidence"] = decision.confidence
        if decision.external_route is not None:
            filters_applied["jev_external_route"] = decision.external_route
        if decision.external_confidence is not None:
            filters_applied["jev_external_confidence"] = decision.external_confidence
        if decision.error_code:
            filters_applied["jev_error_code"] = decision.error_code
    return filters_applied


def _jev_result_fields(decision: JevDecision) -> dict[str, Any]:
    return {
        "jev_mode": decision.mode,
        "jev_route": decision.route,
        "jev_source": decision.source,
    }


def _append_pi_audit(
    request: AgentQueryRequest,
    governance_dir: str,
    envelope: AgentEnvelope,
    result: dict[str, Any],
    *,
    decision: JevDecision | None,
) -> None:
    result_meta = envelope.result_meta.model_dump(mode="json")
    if result.get("error_code"):
        result_meta["error_code"] = str(result["error_code"])
    if decision is not None:
        result_meta["jev_decision"] = decision.model_dump(mode="json", exclude_none=True)
    append_agent_audit(
        GovernanceRepository(base_dir=governance_dir),
        AgentAuditPayload(
            user_id=str(request.context.get("user_id") or "unknown"),
            query_text=request.question,
            tools_used=["pi_rpc", "tool_policy:no_tools"],
            tables_used=envelope.evidence.tables_used,
            filters_applied=envelope.evidence.filters_applied,
            trace_id=envelope.result_meta.trace_id,
            run_id=str(request.context.get("run_id") or "").strip() or None,
            result_meta=result_meta,
        ),
    )


def _append_pi_prompt(
    request: AgentQueryRequest,
    governance_dir: str,
    envelope: AgentEnvelope,
    result: dict[str, Any],
    prompt: str,
) -> None:
    if not prompt:
        return
    append_agent_prompt(
        GovernanceRepository(base_dir=governance_dir),
        AgentPromptPayload(
            provider="pi",
            user_id=str(request.context.get("user_id") or "unknown"),
            trace_id=envelope.result_meta.trace_id,
            prompt=prompt,
            prompt_chars=len(prompt),
            run_id=str(request.context.get("run_id") or "").strip() or None,
            model=str(result.get("model") or ""),
            toolsets="none",
            transport="rpc",
            error_code=str(result.get("error_code") or "").strip() or None,
        ),
    )


def _parse_rpc_event(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(str(line or ""))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("delta", "text", "answer", "content"):
            if key in value:
                text = _extract_text(value[key])
                if text:
                    return text
        return ""
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        parts = [_extract_text(item) for item in value]
        return "".join(part for part in parts if part)
    return ""


def _extract_assistant_text(value: Any) -> str:
    if isinstance(value, dict):
        role = str(value.get("role") or "").strip().lower()
        if role and role != "assistant":
            return ""
        if "message" in value:
            return _extract_assistant_text(value["message"])
        if "messages" in value:
            return _extract_assistant_text(value["messages"])
        return _extract_text(value)
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        for item in reversed(list(value)):
            answer = _extract_assistant_text(item)
            if answer:
                return answer
        return ""
    return _extract_text(value)


def _rpc_value_has_error(value: Any) -> bool:
    if isinstance(value, dict):
        if str(value.get("stopReason") or "").strip().lower() == "error":
            return True
        if value.get("errorMessage"):
            return True
        return any(
            _rpc_value_has_error(value[key])
            for key in ("message", "messages", "assistantMessageEvent")
            if key in value
        )
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, str)):
        return any(_rpc_value_has_error(item) for item in value)
    return False


def _terminate_process(process: Any) -> None:
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                process.wait(timeout=1.0)
    except (OSError, subprocess.SubprocessError):
        return


def _truncate(value: str, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(limit - 3, 0)] + "..."
