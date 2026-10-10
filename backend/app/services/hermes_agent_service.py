from __future__ import annotations

import json
import logging
import os
import queue
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.agent.runtime.local_request_resolution import resolve_local_request
from backend.app.agent.runtime.subprocess_env import build_agent_subprocess_env
from backend.app.agent.runtime.toolset_policy import (
    normalize_hermes_read_only_toolsets,
    normalize_read_only_toolsets,
)
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
from backend.app.services.agent_service import execute_agent_query

RULE_VERSION = "rv_agent_hermes_v1"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HERMES_BRIDGE_LOCK = threading.Lock()
_HERMES_FALLBACK_REASON = "hermes_runtime_unavailable"
_HERMES_FALLBACK_MESSAGE = "Hermes runtime unavailable; local fallback used."
# 运维可区分的失败分类码。只进入日志与审计 payload；对外 envelope 的
# fallback_reason 保持 _HERMES_FALLBACK_REASON 粗粒度契约不变。
_HERMES_ERROR_TIMEOUT = "hermes_timeout"
_HERMES_ERROR_SPAWN = "hermes_spawn_failed"
_HERMES_ERROR_EXIT = "hermes_exit_failed"
_HERMES_ERROR_BRIDGE_UNAUTHORIZED = "hermes_bridge_unauthorized"
_HERMES_ERROR_CANCELLED = "hermes_cancelled"
_HERMES_ERROR_STREAM_CANCELLED = "hermes_stream_cancelled"
_HERMES_ERROR_LOCAL_RECOVERY = "hermes_local_recovery_failed"
# WSL 内定向清理的 pkill -f 特征（匹配 WSL 内完整命令行，不影响宿主进程）。
_HERMES_BRIDGE_WSL_PKILL_PATTERN = "hermes_bridge_server.py"
_HERMES_CLI_INSTANCE_ENV = "MOSS_HERMES_CLI_INSTANCE"
_HERMES_STREAM_WSL_PKILL_PATTERN = "hermes_stream_runner.py"
_HERMES_STREAM_FLUSH_INTERVAL_SECONDS = 0.08
_HERMES_STREAM_CONTINUE_CHECK_SECONDS = 0.1
_HERMES_STREAM_FLUSH_BYTES = 1024
_HERMES_STREAM_MAX_FRAME_BYTES = 4096
_HERMES_STREAM_STDERR_MAX_CHARS = 4096
_HERMES_STREAM_READY_TIMEOUT_SECONDS = 30.0
_HERMES_AUDIT_FAILURE_COUNT = 0
_LOGGER = logging.getLogger(__name__)


class HermesRuntimeError(RuntimeError):
    """Hermes 链路分类失败异常。

    ``error_code`` 面向日志与审计（timeout/spawn/exit/bridge_unauthorized），
    使运维可区分失败通道；异常 message 可含 detail，但绝不允许进入日志或
    对外 envelope（execute_hermes_agent_query 只记类名与 error_code）。
    """

    def __init__(self, message: str, *, error_code: str = _HERMES_FALLBACK_REASON) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class HermesBridgeConfig:
    command: str
    wsl_distro: str
    hermes_home: str
    bridge_url: str
    model: str
    toolsets: str
    max_turns: int


@dataclass(frozen=True)
class HermesStreamConfig:
    command: str
    wsl_distro: str
    hermes_home: str
    model: str
    max_turns: int


@dataclass
class ManagedHermesStreamProcess:
    process: subprocess.Popen[Any]
    stdout_thread: threading.Thread
    stderr_thread: threading.Thread
    event_queue: queue.Queue[tuple[str, str | None]]
    instance_id: str
    ready: bool = False


_HERMES_BRIDGE_PROCESS: subprocess.Popen | None = None
_HERMES_BRIDGE_CONFIG: HermesBridgeConfig | None = None
_HERMES_STREAM_PROCESS: ManagedHermesStreamProcess | None = None
_HERMES_STREAM_CONFIG: HermesStreamConfig | None = None
_HERMES_STREAM_LOCK = threading.Lock()
_HERMES_STREAM_REQUEST_SEQ = 0
_HERMES_STREAM_LIFECYCLE_SEQ = 0
_BRIDGE_TOKEN_HEADER = "X-Hermes-Bridge-Token"
# 供运维指向一个外部已启动的 bridge；未设置时每个后端进程自带一次性令牌。
_CONFIGURED_BRIDGE_TOKEN = bool(os.environ.get("HERMES_BRIDGE_TOKEN", "").strip())
_PROCESS_BRIDGE_TOKEN = os.environ.get("HERMES_BRIDGE_TOKEN", "").strip() or secrets.token_hex(32)
_LOCAL_OPEN_CHAT_EXACT = {
    "?",
    "？",
    "??",
    "？？",
    "在吗",
    "在么",
    "你好",
    "您好",
    "hello",
    "hi",
    "hey",
    "ping",
}
_LOCAL_OPEN_CHAT_PATTERNS = (
    "你能做什么",
    "能做什么",
    "你会什么",
    "怎么用",
    "如何使用",
    "你是谁",
    "你是什么",
    "随便聊",
    "聊聊天",
    "闲聊",
    "帮我想想",
    "给点建议",
    "有什么建议",
    "该关注什么",
    "需要关注什么",
    "早上好",
    "晚上好",
    "谢谢",
    "没事",
    "what can you do",
    "who are you",
    "help me think",
)
# 高误伤英文词只做全词/整句匹配（"chat" 子串会吞掉 wechat/chatham 等业务词，
# "how do i use" 前缀会吞掉具体功能提问）；中文子串模式保持原样。
_LOCAL_OPEN_CHAT_WORD_PATTERNS = (
    "chat",
    "how do i use",
)
_BUSINESS_QUERY_HINTS = (
    "组合",
    "损益",
    "久期",
    "信用",
    "风险",
    "债",
    "股票",
    "宏观",
    "利率",
    "估值",
    "报表",
    "资产",
    "收益",
    "仓位",
    "情景",
    "压力",
    "数据",
    "查询",
    "指标",
    "ifrs9",
    "pnl",
    "portfolio",
    "duration",
    "credit",
    "risk",
    "bond",
    "stock",
    "macro",
    "market",
)
_ONTOLOGY_CONTEXT_MAX_CHARS = 1500
_ONTOLOGY_CONTEXT_MAX_ENTITIES = 3
_ONTOLOGY_DEFINITION_MAX_CHARS = 240
# request context（filters/page_context.selected_rows 等无界字段）序列化后的预算。
# question(<=8000) + context(<=4000) + ontology(<=1500) + 样板文案，总量远低于
# Windows CreateProcess ~32K argv 上限，避免超长 prompt 触发 OSError 静默降级。
_PROMPT_CONTEXT_MAX_CHARS = 4000
_PROMPT_CONTEXT_TRUNCATION_NOTE = (
    "[context truncated: dropped keys {keys}]"
)
_PROMPT_CONTEXT_DROP_ORDER = (
    "page_context",
    "context",
    "filters",
    "currency_basis",
    "position_scope",
    "basis",
)


def execute_hermes_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
    settings: Any,
    *,
    stream_delta_callback: Callable[[str], bool] | None = None,
    stream_should_continue: Callable[[], bool] | None = None,
    cancel_event: threading.Event | None = None,
) -> AgentEnvelope:
    conversation = request.context.get("conversation")
    has_history = isinstance(conversation, dict) and bool(conversation.get("recent_turns"))
    if not has_history and request.model is None and request.reasoning_effort is None and _should_answer_open_chat_locally(request.question):
        result = {
            "answer": "",
            "stdout": "",
            "stderr": "",
            "command": "local_open_chat",
            "model": "local",
            "toolsets": "",
            "transport": "sync",
            "reason": "short_open_chat",
        }
        envelope = build_local_open_chat_envelope(request=request)
        _append_hermes_audit(request, governance_dir, envelope, result)
        return envelope

    prompt = _build_hermes_prompt(request)
    try:
        configured_transport = str(getattr(settings, "agent_hermes_transport", "cli") or "cli")
        transport, transport_reason = _select_hermes_transport(
            configured_transport=configured_transport,
            has_delta_callback=stream_delta_callback is not None,
            has_reasoning_effort=request.reasoning_effort is not None,
            has_model=request.model is not None,
        )
        _log_hermes_transport_override(
            configured_transport=configured_transport,
            selected_transport=transport,
            reason=transport_reason,
        )
        result = run_hermes_agent(
            request=request,
            command=str(settings.agent_hermes_command),
            wsl_distro=str(settings.agent_hermes_wsl_distro or ""),
            hermes_home=str(getattr(settings, "agent_hermes_home", "") or ""),
            transport=transport,
            bridge_url=str(getattr(settings, "agent_hermes_bridge_url", "") or ""),
            model=request.model or str(settings.agent_hermes_model or ""),
            toolsets=str(getattr(settings, "agent_hermes_toolsets", "") or ""),
            max_turns=int(settings.agent_hermes_max_turns),
            timeout_seconds=float(settings.agent_hermes_timeout_seconds),
            stream_delta_callback=stream_delta_callback,
            stream_should_continue=stream_should_continue,
            prompt_override=prompt,
            cancel_event=cancel_event,
            **({"reasoning_effort": request.reasoning_effort} if request.reasoning_effort is not None else {}),
        )
        if request.reasoning_effort is not None:
            result["reasoning_effort"] = request.reasoning_effort
        envelope = build_hermes_envelope(request=request, result=result)
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        # 运行链任何失败（含 JSON 解析、子进程拉起、超时）都收敛到同一条确定性兜底路径，
        # 不允许裸异常穿透到路由层变成 500。error_code 取分类码（HermesRuntimeError）
        # 供运维区分，日志仍只记异常类名、不落原始 detail。
        error_code = str(getattr(exc, "error_code", "") or "").strip() or _HERMES_FALLBACK_REASON
        if error_code in {_HERMES_ERROR_CANCELLED, _HERMES_ERROR_STREAM_CANCELLED}:
            raise
        _LOGGER.warning(
            "Hermes provider runtime failed provider=hermes error_type=%s error_code=%s",
            exc.__class__.__name__,
            error_code,
        )
        result = {
            "answer": "",
            "stdout": "",
            "stderr": "",
            "command": str(settings.agent_hermes_command),
            "model": request.model or str(settings.agent_hermes_model or ""),
            "toolsets": str(getattr(settings, "agent_hermes_toolsets", "") or ""),
            "transport": str(getattr(settings, "agent_hermes_transport", "cli") or "cli"),
            "error": _HERMES_FALLBACK_MESSAGE,
            "error_code": error_code,
        }
        recovered = build_local_recovery_envelope(
            request=request,
            governance_dir=governance_dir,
            settings=settings,
        )
        envelope = (
            recovered
            if recovered is not None
            else build_hermes_fallback_envelope(request=request, result=result)
        )
    _append_hermes_audit(request, governance_dir, envelope, result)
    _append_hermes_prompt(request, governance_dir, envelope, result, prompt)
    return envelope


def build_local_recovery_envelope(
    *,
    request: AgentQueryRequest,
    governance_dir: str,
    settings: Any,
) -> AgentEnvelope | None:
    """Hermes 不可用时改由本地受治理工具重答；本地也接不住则返回 None。

    只处理 standalone workbench 把分析类问题上送 provider 的情形。其余到达
    provider 的请求已被 resolve_local_request 判定为本地接不住，重跑本地工具
    只会得到 agent.unknown，不如确定性兜底文案诚实。
    """
    if request.routing_surface is None:
        return None
    local_request = request.model_copy(update={"routing_surface": None})
    if resolve_local_request(local_request).route != "local":
        return None
    from backend.app.services.agent_service import (
        ensure_agent_execution_resources_allowed,
        resolve_agent_intent_read_resources,
    )

    # Check outside the runtime fallback handler so a denied read cannot become a success.
    ensure_agent_execution_resources_allowed(
        local_request,
        settings=settings,
        resources=resolve_agent_intent_read_resources(local_request),
    )
    try:
        envelope = execute_agent_query(
            local_request,
            str(getattr(settings, "duckdb_path", "") or ""),
            governance_dir,
        )
    except Exception as exc:  # noqa: BLE001 - 恢复链路失败不得覆盖原始 provider 故障
        _LOGGER.warning(
            "Hermes local recovery failed error_type=%s error_code=%s",
            exc.__class__.__name__,
            _HERMES_ERROR_LOCAL_RECOVERY,
        )
        return None
    return _mark_local_recovery(envelope)


def _mark_local_recovery(envelope: AgentEnvelope) -> AgentEnvelope:
    """标注 provider 降级来源，供前端与审计区分本地重答与正常本地路由。

    不改 vendor_status / fallback_mode：前者描述数据供应方，后者描述报告日
    回退到最近快照，都与 agent provider 的可用性无关。
    """
    markers = {
        "requested_provider": "hermes",
        "fallback_provider": "local",
        "fallback_reason": _HERMES_FALLBACK_REASON,
    }
    envelope.evidence.filters_applied.update(markers)
    envelope.result_meta.filters_applied.update(markers)
    envelope.cards.insert(
        0,
        AgentCard(
            type="status",
            title="Hermes 通道不可用",
            value="外部模型通道本轮不可用，本轮改由本地受治理路径回答。",
        ),
    )
    return envelope


def build_local_open_chat_envelope(*, request: AgentQueryRequest) -> AgentEnvelope:
    trace_id = f"tr_agent_local_chat_{uuid4().hex[:12]}"
    generated_at = datetime.now(UTC)
    filters_applied = {
        key: value for key, value in request.filters.items() if value not in (None, "")
    }
    filters_applied["provider"] = "local"
    filters_applied["requested_provider"] = "hermes"
    filters_applied["transport"] = "sync"
    filters_applied["fallback_reason"] = "short_open_chat"
    evidence = AgentEvidence(
        tables_used=["agent_local_chat"],
        filters_applied=filters_applied,
        sql_executed=[],
        evidence_rows=0,
        quality_flag="warning",
        evidence_strength="local_fallback",
    )
    result_meta = AgentResultMeta(
        trace_id=trace_id,
        basis=request.basis,
        result_kind="agent.local_chat",
        formal_use_allowed=False,
        source_version="sv_agent_local_chat",
        vendor_version="vv_none",
        rule_version=RULE_VERSION,
        cache_version="cv_agent_local_chat_v1",
        quality_flag=evidence.quality_flag,
        vendor_status="ok",
        fallback_mode="none",
        scenario_flag=request.basis == Basis.SCENARIO.value,
        generated_at=generated_at,
        tables_used=evidence.tables_used,
        filters_applied=evidence.filters_applied,
        sql_executed=[],
        evidence_rows=evidence.evidence_rows,
        evidence_strength=evidence.evidence_strength,
    )
    answer = _build_local_open_chat_answer(request.question)
    return AgentEnvelope(
        answer=answer,
        cards=[
            AgentCard(type="text", title="本地对话", value=answer),
            AgentCard(type="metric", title="Provider", value="local"),
        ],
        evidence=evidence,
        result_meta=result_meta,
        next_drill=[],
        suggested_actions=[],
    )


def warm_hermes_bridge_if_configured(settings: Any) -> bool:
    if not bool(getattr(settings, "agent_enabled", False)):
        return False
    if str(getattr(settings, "agent_provider", "") or "").strip().lower() != "hermes":
        return False
    if str(getattr(settings, "agent_hermes_transport", "") or "").strip().lower() != "bridge":
        return False

    thread = threading.Thread(
        target=_warm_hermes_bridge_quietly,
        kwargs={
            "command": str(getattr(settings, "agent_hermes_command", "wsl.exe") or "wsl.exe"),
            "wsl_distro": str(getattr(settings, "agent_hermes_wsl_distro", "") or ""),
            "hermes_home": str(getattr(settings, "agent_hermes_home", "") or ""),
            "bridge_url": str(getattr(settings, "agent_hermes_bridge_url", "") or "")
            or "http://127.0.0.1:7891",
            "model": str(getattr(settings, "agent_hermes_model", "") or ""),
            "toolsets": _normalize_toolsets(str(getattr(settings, "agent_hermes_toolsets", "") or "")),
            "max_turns": int(getattr(settings, "agent_hermes_max_turns", 20) or 20),
            "timeout_seconds": float(getattr(settings, "agent_hermes_timeout_seconds", 180.0) or 180.0),
        },
        daemon=True,
        name="moss-hermes-bridge-warmup",
    )
    thread.start()
    return True


def _warm_hermes_bridge_quietly(**kwargs: Any) -> None:
    try:
        _ensure_hermes_bridge(**kwargs)
    except Exception:
        return


def warm_hermes_stream_if_configured(settings: Any) -> bool:
    """Preload the Lab-only Hermes stream runtime in the worker process."""
    if not bool(getattr(settings, "agent_enabled", False)):
        return False
    if str(getattr(settings, "agent_provider", "") or "").strip().lower() != "hermes":
        return False
    with _HERMES_STREAM_LOCK:
        _ensure_managed_hermes_stream_process_locked(
            command=str(getattr(settings, "agent_hermes_command", "wsl.exe") or "wsl.exe"),
            wsl_distro=str(getattr(settings, "agent_hermes_wsl_distro", "") or ""),
            hermes_home=str(getattr(settings, "agent_hermes_home", "") or ""),
            model=str(getattr(settings, "agent_hermes_model", "") or ""),
            max_turns=max(int(getattr(settings, "agent_hermes_max_turns", 1) or 1), 1),
        )
    return True


def run_hermes_agent(
    *,
    request: AgentQueryRequest,
    command: str,
    wsl_distro: str,
    hermes_home: str,
    transport: str = "cli",
    bridge_url: str = "",
    model: str,
    toolsets: str,
    max_turns: int,
    timeout_seconds: float,
    stream_delta_callback: Callable[[str], bool] | None = None,
    stream_should_continue: Callable[[], bool] | None = None,
    prompt_override: str | None = None,
    reasoning_effort: str | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, str]:
    # 调用方传入 prompt 才能在通道故障时也留下送模原文；缺省时自建，保持既有直调行为。
    prompt = prompt_override or _build_hermes_prompt(request)
    normalized_toolsets = _normalize_toolsets(toolsets)
    selected_transport, transport_reason = _select_hermes_transport(
        configured_transport=transport,
        has_delta_callback=stream_delta_callback is not None,
        has_reasoning_effort=reasoning_effort is not None,
        has_model=request.model is not None,
    )
    _log_hermes_transport_override(
        configured_transport=transport,
        selected_transport=selected_transport,
        reason=transport_reason,
    )
    if stream_delta_callback is not None or request.model is not None:
        return _run_hermes_agent_streaming(
            command=command,
            wsl_distro=wsl_distro,
            hermes_home=hermes_home,
            prompt=prompt,
            model=model,
            normalized_toolsets=normalized_toolsets,
            max_turns=max_turns,
            timeout_seconds=timeout_seconds,
            stream_delta_callback=stream_delta_callback or (lambda _delta: True),
            stream_should_continue=stream_should_continue,
            reasoning_effort=reasoning_effort or "low",
            cancel_event=cancel_event,
        )
    if selected_transport == "bridge":
        normalized_bridge_url = str(bridge_url or "").strip() or "http://127.0.0.1:7891"
        _ensure_hermes_bridge(
            command=command,
            wsl_distro=wsl_distro,
            hermes_home=hermes_home,
            bridge_url=normalized_bridge_url,
            model=model,
            toolsets=normalized_toolsets,
            max_turns=max_turns,
            timeout_seconds=timeout_seconds,
        )
        return _post_hermes_bridge_query(
            bridge_url=normalized_bridge_url,
            prompt=prompt,
            model=model,
            toolsets=normalized_toolsets,
            max_turns=max_turns,
            timeout_seconds=timeout_seconds,
        )

    cli_instance_id = uuid4().hex if _is_wsl_command(command) else ""
    args = _build_hermes_command(
        command=command,
        wsl_distro=wsl_distro,
        hermes_home=hermes_home,
        model=model,
        toolsets=toolsets,
        max_turns=max_turns,
        prompt=prompt,
        reasoning_effort=reasoning_effort,
        instance_id=cli_instance_id,
    )
    normalized_home = str(hermes_home or "").strip()
    env = build_agent_subprocess_env(
        HERMES_HOME=normalized_home if not _is_wsl_command(command) else "",
    )
    try:
        if cancel_event is None:
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
        else:
            completed = _run_hermes_cli_with_cancel(
                args=args,
                command=command,
                wsl_distro=wsl_distro,
                timeout_seconds=timeout_seconds,
                env=env,
                cancel_event=cancel_event,
                instance_id=cli_instance_id,
            )
    except FileNotFoundError as exc:
        raise HermesRuntimeError(
            f"Hermes command not found: {command}",
            error_code=_HERMES_ERROR_SPAWN,
        ) from exc
    except subprocess.TimeoutExpired as exc:
        if cancel_event is None:
            _cleanup_wsl_cli_instance(
                command=command, wsl_distro=wsl_distro, instance_id=cli_instance_id,
            )
        raise HermesRuntimeError(
            f"Hermes timed out after {timeout_seconds:g}s",
            error_code=_HERMES_ERROR_TIMEOUT,
        ) from exc
    except OSError as exc:
        raise HermesRuntimeError(
            f"Hermes command failed to start: {exc}",
            error_code=_HERMES_ERROR_SPAWN,
        ) from exc

    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    answer = _extract_final_answer(stdout)
    if completed.returncode != 0:
        if _is_nonfatal_hermes_mcp_shutdown(
            returncode=completed.returncode,
            stderr=stderr,
            answer=answer,
        ):
            return {
                "answer": answer,
                "stdout": stdout,
                "stderr": stderr,
                "command": command,
                "model": model or "default",
                "toolsets": normalized_toolsets,
                "transport": "cli",
            }
        detail = _truncate((stderr or stdout).strip(), 2000)
        raise HermesRuntimeError(
            f"Hermes failed with exit code {completed.returncode}: {detail}",
            error_code=_HERMES_ERROR_EXIT,
        )
    if not answer:
        detail = _truncate((stderr or stdout).strip(), 2000)
        raise RuntimeError(f"Hermes returned no answer: {detail or 'empty output'}")

    return {
        "answer": answer,
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
        "model": model or "default",
        "toolsets": normalized_toolsets,
        "transport": "cli",
    }


def _select_hermes_transport(
    *,
    configured_transport: str,
    has_delta_callback: bool,
    has_reasoning_effort: bool,
    has_model: bool,
) -> tuple[str, str]:
    normalized = str(configured_transport or "").strip().lower() or "cli"
    if normalized == "sidecar":
        normalized = "bridge"
    if normalized not in {"cli", "bridge"}:
        normalized = "cli"
    if has_delta_callback:
        return "cli", "stream_delta_callback_requires_cli"
    if has_reasoning_effort:
        return "cli", "reasoning_effort_requires_cli"
    if has_model:
        return "cli", "request_model_requires_streaming_cli"
    if normalized == "bridge":
        return "bridge", "configured_bridge"
    return "cli", "configured_cli"


def _log_hermes_transport_override(
    *,
    configured_transport: str,
    selected_transport: str,
    reason: str,
) -> None:
    normalized = str(configured_transport or "").strip().lower() or "cli"
    if normalized == "sidecar":
        normalized = "bridge"
    if normalized == selected_transport:
        return
    _LOGGER.info(
        "Hermes transport selected configured_transport=%s selected_transport=%s reason=%s",
        normalized,
        selected_transport,
        reason,
    )


def _run_hermes_cli_with_cancel(
    *,
    args: list[str],
    command: str,
    wsl_distro: str,
    timeout_seconds: float,
    env: dict[str, str],
    cancel_event: threading.Event,
    instance_id: str = "",
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    deadline = time.monotonic() + max(timeout_seconds, 1.0)
    while True:
        if cancel_event.is_set():
            _terminate_stream_process(
                process=process,
                command=command,
                wsl_distro=wsl_distro,
                pattern="",
            )
            _cleanup_wsl_cli_instance(
                command=command, wsl_distro=wsl_distro, instance_id=instance_id,
            )
            try:
                process.communicate(timeout=1.0)
            except (OSError, subprocess.TimeoutExpired):
                pass
            raise HermesRuntimeError(
                "Hermes CLI was cancelled before completion.",
                error_code=_HERMES_ERROR_CANCELLED,
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate_stream_process(
                process=process,
                command=command,
                wsl_distro=wsl_distro,
                pattern="",
            )
            _cleanup_wsl_cli_instance(
                command=command, wsl_distro=wsl_distro, instance_id=instance_id,
            )
            try:
                process.communicate(timeout=1.0)
            except (OSError, subprocess.TimeoutExpired):
                pass
            raise subprocess.TimeoutExpired(cmd=args, timeout=max(timeout_seconds, 1.0))
        try:
            # communicate drains both pipes while waiting. Retrying after a short
            # timeout preserves buffered output, including Windows reader threads.
            stdout, stderr = process.communicate(timeout=min(0.05, remaining))
        except subprocess.TimeoutExpired:
            continue
        return subprocess.CompletedProcess(
            args=args,
            returncode=int(process.returncode or 0),
            stdout=str(stdout or ""),
            stderr=str(stderr or ""),
        )


def _run_hermes_agent_streaming(
    *,
    command: str,
    wsl_distro: str,
    hermes_home: str,
    prompt: str,
    model: str,
    normalized_toolsets: str,
    max_turns: int,
    timeout_seconds: float,
    stream_delta_callback: Callable[[str], bool],
    stream_should_continue: Callable[[], bool] | None,
    reasoning_effort: str = "low",
    cancel_event: threading.Event | None = None,
) -> dict[str, str]:
    base_should_continue = stream_should_continue or (lambda: True)

    def should_continue() -> bool:
        return not (cancel_event is not None and cancel_event.is_set()) and bool(base_should_continue())

    with _HERMES_STREAM_LOCK:
        request_id = _next_hermes_stream_request_id()
        request_body = json.dumps(
            {
                "request_id": request_id,
                "prompt": prompt,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "toolsets": normalized_toolsets,
                "max_turns": max(max_turns, 1),
            },
            ensure_ascii=False,
        ) + "\n"
        manager = _ensure_managed_hermes_stream_process_locked(
            command=command,
            wsl_distro=wsl_distro,
            hermes_home=hermes_home,
            model=model,
            max_turns=max(max_turns, 1),
        )
        if not manager.ready:
            try:
                _wait_for_managed_hermes_stream_ready(manager)
            except Exception:
                _stop_managed_hermes_stream_locked(
                    command=command,
                    wsl_distro=wsl_distro,
                )
                raise
        manager.ready = False
        process = manager.process
        stdin_stream = process.stdin
        if stdin_stream is None:
            _stop_managed_hermes_stream_locked(command=command, wsl_distro=wsl_distro)
            raise RuntimeError("Hermes stream stdin unavailable.")
        try:
            stdin_stream.write(request_body)
            stdin_stream.flush()
        except OSError as exc:
            _stop_managed_hermes_stream_locked(command=command, wsl_distro=wsl_distro)
            raise HermesRuntimeError(
                "Hermes stream request failed to start.",
                error_code=_HERMES_ERROR_SPAWN,
            ) from exc

        stderr_parts: list[str] = []
        pending_deltas: list[str] = []
        pending_bytes = 0
        last_flush = time.monotonic()
        last_continue_check = 0.0
        continue_allowed = True
        final_answer = ""
        final_session_id = ""
        error_code = ""
        last_delta_seq = 0
        deadline = time.monotonic() + max(timeout_seconds, 1.0)

        def still_running(*, force: bool = False) -> bool:
            nonlocal continue_allowed, last_continue_check
            now = time.monotonic()
            if force or now - last_continue_check >= _HERMES_STREAM_CONTINUE_CHECK_SECONDS:
                continue_allowed = bool(should_continue())
                last_continue_check = now
            return continue_allowed

        def flush_pending(*, force: bool = False) -> bool:
            nonlocal pending_bytes, last_flush
            if not pending_deltas:
                return True
            now = time.monotonic()
            if (
                not force
                and pending_bytes < _HERMES_STREAM_FLUSH_BYTES
                and now - last_flush < _HERMES_STREAM_FLUSH_INTERVAL_SECONDS
            ):
                return True
            text = "".join(pending_deltas)
            pending_deltas.clear()
            pending_bytes = 0
            last_flush = now
            for frame in _chunk_text_by_utf8_bytes(text, _HERMES_STREAM_MAX_FRAME_BYTES):
                if not still_running():
                    return False
                if stream_delta_callback(frame) is False:
                    return False
            return True

        cancelled = False
        try:
            while True:
                now = time.monotonic()
                if now >= deadline:
                    raise HermesRuntimeError(
                        f"Hermes timed out after {timeout_seconds:g}s",
                        error_code=_HERMES_ERROR_TIMEOUT,
                    )
                if not still_running():
                    cancelled = True
                    break
                wait_seconds = min(0.05, max(deadline - now, 0.01))
                try:
                    kind, payload = manager.event_queue.get(timeout=wait_seconds)
                except queue.Empty:
                    if not flush_pending():
                        cancelled = True
                        break
                    if process.poll() is not None:
                        break
                    continue

                if kind == "stdout":
                    record = _parse_hermes_stream_record(payload or "")
                    record_request_id = str(record.get("request_id") or "")
                    if record_request_id != request_id:
                        raise RuntimeError("Hermes stream record had an unexpected request id.")
                    record_type = str(record.get("type") or "")
                    if record_type == "delta":
                        text = str(record.get("text") or "")
                        delta_seq = int(record.get("seq") or 0)
                        if delta_seq != last_delta_seq + 1:
                            raise RuntimeError("Hermes stream delta sequence was invalid.")
                        last_delta_seq = delta_seq
                        if text:
                            pending_deltas.append(text)
                            pending_bytes += len(text.encode("utf-8"))
                            if not flush_pending():
                                cancelled = True
                                break
                    elif record_type == "final":
                        if not flush_pending(force=True):
                            cancelled = True
                            break
                        final_answer = str(record.get("answer") or "")
                        final_session_id = str(record.get("session_id") or "")
                        break
                    elif record_type == "error":
                        error_code = str(record.get("code") or "runtime_failed")
                    else:
                        raise RuntimeError("Hermes stream returned an invalid record.")
                elif kind == "stderr":
                    if payload and len("".join(stderr_parts)) < _HERMES_STREAM_STDERR_MAX_CHARS:
                        stderr_parts.append(payload)
                        if len("".join(stderr_parts)) > _HERMES_STREAM_STDERR_MAX_CHARS:
                            joined = "".join(stderr_parts)[:_HERMES_STREAM_STDERR_MAX_CHARS]
                            stderr_parts[:] = [joined]
                elif kind in {"stdout_eof", "stderr_eof"}:
                    if process.poll() is not None:
                        break

                if error_code:
                    raise RuntimeError("Hermes stream returned an error record.")
            if cancelled:
                raise HermesRuntimeError(
                    "Hermes stream was cancelled before completion.",
                    error_code=_HERMES_ERROR_STREAM_CANCELLED,
                )
            stderr = _truncate("".join(stderr_parts).strip(), _HERMES_STREAM_STDERR_MAX_CHARS)
            returncode = process.poll()
            if returncode is not None and returncode != 0:
                if _is_nonfatal_hermes_mcp_shutdown(
                    returncode=returncode,
                    stderr=stderr,
                    answer=final_answer,
                ):
                    return {
                        "answer": final_answer,
                        "stdout": final_answer,
                        "stderr": stderr,
                        "command": command,
                        "model": model or "default",
                        "toolsets": normalized_toolsets,
                        "transport": "cli_stream",
                        "session_id": final_session_id,
                    }
                _stop_managed_hermes_stream_locked(command=command, wsl_distro=wsl_distro)
                raise HermesRuntimeError(
                    f"Hermes failed with exit code {returncode}: stream wrapper exited",
                    error_code=_HERMES_ERROR_EXIT,
                )
            if not final_answer:
                _stop_managed_hermes_stream_locked(command=command, wsl_distro=wsl_distro)
                raise RuntimeError("Hermes stream returned no final answer.")
            return {
                "answer": final_answer,
                "stdout": final_answer,
                "stderr": stderr,
                "command": command,
                "model": model or "default",
                "toolsets": normalized_toolsets,
                "transport": "cli_stream",
                "session_id": final_session_id,
            }
        except Exception as exc:
            _stop_managed_hermes_stream_locked(command=command, wsl_distro=wsl_distro)
            if getattr(exc, "error_code", "") == _HERMES_ERROR_STREAM_CANCELLED:
                _schedule_managed_hermes_stream_warmup_locked(
                    command=command,
                    wsl_distro=wsl_distro,
                    hermes_home=hermes_home,
                    model=model,
                    max_turns=max(max_turns, 1),
                )
            raise


def _ensure_hermes_bridge(
    *,
    command: str,
    wsl_distro: str,
    hermes_home: str,
    bridge_url: str,
    model: str,
    toolsets: str,
    max_turns: int,
    timeout_seconds: float,
) -> None:
    desired = HermesBridgeConfig(
        command=str(command or ""),
        wsl_distro=str(wsl_distro or ""),
        hermes_home=str(hermes_home or ""),
        bridge_url=str(bridge_url or "").strip() or "http://127.0.0.1:7891",
        model=str(model or ""),
        toolsets=_normalize_toolsets(str(toolsets or "")),
        max_turns=max(int(max_turns or 1), 1),
    )

    with _HERMES_BRIDGE_LOCK:
        global _HERMES_BRIDGE_PROCESS, _HERMES_BRIDGE_CONFIG

        if _HERMES_BRIDGE_PROCESS is not None and _HERMES_BRIDGE_PROCESS.poll() is not None:
            _HERMES_BRIDGE_PROCESS = None
            _HERMES_BRIDGE_CONFIG = None

        managed_alive = (
            _HERMES_BRIDGE_PROCESS is not None and _HERMES_BRIDGE_PROCESS.poll() is None
        )
        healthy = _hermes_bridge_healthy(desired.bridge_url)

        if managed_alive and _HERMES_BRIDGE_CONFIG == desired and healthy:
            return

        if managed_alive and _HERMES_BRIDGE_CONFIG != desired:
            _stop_managed_hermes_bridge_locked()
            managed_alive = False
            healthy = _hermes_bridge_healthy(desired.bridge_url)

        if not managed_alive and healthy:
            # External bridge we do not own — never terminate it.
            authorization = _hermes_bridge_authorized(desired.bridge_url)
            if authorization is False or (_CONFIGURED_BRIDGE_TOKEN and authorization is None):
                raise HermesRuntimeError(
                    f"Hermes bridge at {desired.bridge_url} is running but rejects this "
                    "process's token; set HERMES_BRIDGE_TOKEN to that bridge's token or stop it.",
                    error_code=_HERMES_ERROR_BRIDGE_UNAUTHORIZED,
                )
            return

        if managed_alive and _HERMES_BRIDGE_CONFIG == desired and not healthy:
            _wait_for_hermes_bridge_ready_locked(
                bridge_url=desired.bridge_url,
                timeout_seconds=timeout_seconds,
            )
            return

        args = _build_hermes_bridge_command(
            command=desired.command,
            wsl_distro=desired.wsl_distro,
            hermes_home=desired.hermes_home,
            bridge_url=desired.bridge_url,
            model=desired.model,
            toolsets=desired.toolsets,
            max_turns=desired.max_turns,
        )
        log_dir = _REPO_ROOT / "tmp-governance" / "runtime-clean" / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            stdout = (log_dir / "hermes-bridge.out.log").open("ab")
            stderr = (log_dir / "hermes-bridge.err.log").open("ab")
        except OSError as exc:
            raise RuntimeError(f"Hermes bridge log files unavailable: {exc}") from exc
        try:
            _HERMES_BRIDGE_PROCESS = subprocess.Popen(
                args,
                cwd=str(_REPO_ROOT),
                stdout=stdout,
                stderr=stderr,
                env=_build_hermes_subprocess_env(
                    desired.hermes_home if not _is_wsl_command(desired.command) else ""
                ),
            )
        except OSError as exc:
            stdout.close()
            stderr.close()
            raise HermesRuntimeError(
                f"Hermes bridge failed to start: {exc}",
                error_code=_HERMES_ERROR_SPAWN,
            ) from exc
        _HERMES_BRIDGE_CONFIG = desired
        _wait_for_hermes_bridge_ready_locked(
            bridge_url=desired.bridge_url,
            timeout_seconds=timeout_seconds,
        )


def stop_managed_hermes_bridge() -> None:
    """backend 关停时终止本进程托管的 bridge；无托管进程时为幂等 no-op。

    外部自行启动的 bridge 从不进入 ``_HERMES_BRIDGE_PROCESS``
    （见 _ensure_hermes_bridge 的 external 分支），因此不会被本函数终止。
    """
    with _HERMES_BRIDGE_LOCK:
        _stop_managed_hermes_bridge_locked()


def _stop_managed_hermes_bridge_locked() -> None:
    global _HERMES_BRIDGE_PROCESS, _HERMES_BRIDGE_CONFIG
    process = _HERMES_BRIDGE_PROCESS
    config = _HERMES_BRIDGE_CONFIG
    _HERMES_BRIDGE_PROCESS = None
    _HERMES_BRIDGE_CONFIG = None
    if process is None:
        return
    try:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _LOGGER.warning(
                    "Hermes bridge process did not exit after kill "
                    "error_code=hermes_bridge_stop_timeout"
                )
    finally:
        # terminate/kill 只作用于 Windows 侧 wsl.exe 中继；WSL 内 python bridge
        # 会残留并继续占用端口（backend 重启后新随机 token 被旧 bridge 拒绝，
        # Hermes 全量永久降级），必须穿透补杀。
        if config is not None:
            _cleanup_wsl_processes(
                command=config.command,
                wsl_distro=config.wsl_distro,
                pattern=_HERMES_BRIDGE_WSL_PKILL_PATTERN,
            )


def _cleanup_wsl_processes(*, command: str, wsl_distro: str, pattern: str) -> None:
    """按命令行特征定向终止 WSL 内残留进程；非 WSL 命令为 no-op。

    只在托管进程关停/超时后调用。pkill 无匹配时退出码为 1，属正常情况；
    任何失败只记分类日志，不得阻断关停或超时兜底主路径。
    """
    if not pattern or not _is_wsl_command(command):
        return
    args = [command]
    if wsl_distro:
        args.extend(["-d", wsl_distro])
    args.extend(["--exec", "pkill", "-f", pattern])
    try:
        subprocess.run(args, check=False, capture_output=True, timeout=15.0)
    except Exception as exc:  # noqa: BLE001 - 清理失败不得影响主路径
        _LOGGER.warning(
            "Hermes WSL cleanup failed error_type=%s error_code=hermes_wsl_cleanup_failed",
            exc.__class__.__name__,
        )


def _cleanup_wsl_cli_instance(*, command: str, wsl_distro: str, instance_id: str) -> None:
    """Stop only the isolated WSL process groups carrying this request's marker."""
    if not instance_id or not _is_wsl_command(command):
        return
    script = (
        "import os,pathlib,signal,sys\n"
        "marker=(sys.argv[1]+'='+sys.argv[2]).encode()\n"
        "groups=set()\n"
        "for entry in pathlib.Path('/proc').iterdir():\n"
        " if not entry.name.isdigit(): continue\n"
        " try:\n"
        "  if marker in (entry/'environ').read_bytes().split(b'\\0'):\n"
        "   groups.add(os.getpgid(int(entry.name)))\n"
        " except (OSError,ValueError): pass\n"
        "for group in groups:\n"
        " try: os.killpg(group,signal.SIGKILL)\n"
        " except OSError: pass\n"
    )
    args = [command]
    if wsl_distro:
        args.extend(["-d", wsl_distro])
    args.extend([
        "--exec", _hermes_bridge_python_path(), "-c", script,
        _HERMES_CLI_INSTANCE_ENV, instance_id,
    ])
    try:
        subprocess.run(args, check=False, capture_output=True, timeout=15.0)
    except Exception as exc:  # noqa: BLE001 - cleanup must preserve the original failure
        _LOGGER.warning(
            "Hermes CLI cleanup failed error_type=%s error_code=hermes_wsl_cleanup_failed",
            exc.__class__.__name__,
        )


def _wait_for_hermes_bridge_ready_locked(*, bridge_url: str, timeout_seconds: float) -> None:
    global _HERMES_BRIDGE_PROCESS, _HERMES_BRIDGE_CONFIG
    deadline = time.monotonic() + min(max(timeout_seconds, 1.0), 30.0)
    while time.monotonic() < deadline:
        if _hermes_bridge_healthy(bridge_url):
            return
        if _HERMES_BRIDGE_PROCESS is not None and _HERMES_BRIDGE_PROCESS.poll() is not None:
            _HERMES_BRIDGE_PROCESS = None
            _HERMES_BRIDGE_CONFIG = None
            raise HermesRuntimeError(
                "Hermes bridge exited before it became ready.",
                error_code=_HERMES_ERROR_EXIT,
            )
        time.sleep(0.25)
    raise HermesRuntimeError(
        f"Hermes bridge did not become ready at {bridge_url}",
        error_code=_HERMES_ERROR_TIMEOUT,
    )


def _post_hermes_bridge_query(
    *,
    bridge_url: str,
    prompt: str,
    model: str,
    toolsets: str,
    max_turns: int,
    timeout_seconds: float,
) -> dict[str, str]:
    url = urllib.parse.urljoin(bridge_url.rstrip("/") + "/", "query")
    body = json.dumps(
        {
            "prompt": prompt,
            "model": model,
            "toolsets": _normalize_toolsets(toolsets),
            "max_turns": max(max_turns, 1),
            # 透传调用方超时预算：bridge 以 min(自身上限, 该预算-余量) 执行子进程，
            # 避免 bridge 侧上限（max_turns*15s）超过 urlopen 超时造成连环降级。
            "timeout_seconds": max(timeout_seconds, 1.0),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            _BRIDGE_TOKEN_HEADER: _PROCESS_BRIDGE_TOKEN,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(timeout_seconds, 1.0)) as response:
            raw_body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 403:
            raise HermesRuntimeError(
                f"Hermes bridge rejected the request: {_truncate(detail, 2000)}",
                error_code=_HERMES_ERROR_BRIDGE_UNAUTHORIZED,
            ) from exc
        raise RuntimeError(f"Hermes bridge failed: {_truncate(detail, 2000)}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        if isinstance(exc, TimeoutError) or isinstance(
            getattr(exc, "reason", None), TimeoutError
        ):
            raise HermesRuntimeError(
                f"Hermes bridge timed out after {timeout_seconds:g}s",
                error_code=_HERMES_ERROR_TIMEOUT,
            ) from exc
        raise RuntimeError(f"Hermes bridge unavailable: {exc}") from exc

    try:
        payload = json.loads(raw_body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Hermes bridge returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Hermes bridge returned an invalid payload.")
    if not payload.get("ok", False):
        raise RuntimeError(str(payload.get("error") or "Hermes bridge query failed."))

    answer = str(payload.get("answer") or "")
    if not answer.strip():
        # bridge 版 _extract_final_answer 收紧后不再回退原始 stdout；
        # 空答案与 CLI 路径同语义，进入确定性兜底而非渲染空 envelope。
        raise RuntimeError("Hermes bridge returned no answer.")
    return {
        "answer": answer,
        "stdout": answer,
        "stderr": "",
        "command": "hermes_bridge",
        "model": str(payload.get("model") or model or "default"),
        "toolsets": _normalize_toolsets(str(payload.get("toolsets") or toolsets)),
        "transport": "bridge",
    }


def _hermes_bridge_authorized(bridge_url: str) -> bool | None:
    """Whether a reachable bridge accepts this process's token.

    ``None`` means "could not tell" only when the probe failed or no bridge token is
    configured. If an operator configured ``HERMES_BRIDGE_TOKEN``, a health payload
    without ``authorized`` is not a valid authorization verdict and must fail closed.
    """
    url = urllib.parse.urljoin(bridge_url.rstrip("/") + "/", "health")
    request = urllib.request.Request(
        url,
        headers={_BRIDGE_TOKEN_HEADER: _PROCESS_BRIDGE_TOKEN},
    )
    try:
        with urllib.request.urlopen(request, timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - any health transport/response failure leaves authorization unknown; configured-token callers reject that verdict before querying.
        return None
    if not isinstance(payload, dict) or "authorized" not in payload:
        if os.environ.get("HERMES_BRIDGE_TOKEN", "").strip():
            return False
        return None
    return bool(payload.get("authorized"))


def _hermes_bridge_healthy(bridge_url: str) -> bool:
    url = urllib.parse.urljoin(bridge_url.rstrip("/") + "/", "health")
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def build_hermes_envelope(
    *,
    request: AgentQueryRequest,
    result: dict[str, str],
) -> AgentEnvelope:
    trace_id = f"tr_agent_hermes_{uuid4().hex[:12]}"
    generated_at = datetime.now(UTC)
    filters_applied = {
        key: value for key, value in request.filters.items() if value not in (None, "")
    }
    filters_applied["provider"] = "hermes"
    filters_applied["capability_scope"] = normalize_read_only_toolsets("")
    if result.get("model"):
        filters_applied["model"] = result["model"]
    if result.get("reasoning_effort"):
        filters_applied["reasoning_effort"] = result["reasoning_effort"]
    if result.get("toolsets"):
        filters_applied["toolsets"] = _normalize_toolsets(result["toolsets"])
    if result.get("transport"):
        filters_applied["transport"] = result["transport"]

    evidence = AgentEvidence(
        tables_used=["hermes_cli"],
        filters_applied=filters_applied,
        sql_executed=[],
        evidence_rows=0,
        quality_flag="warning",
        evidence_strength="provider_runtime",
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
        quality_flag=evidence.quality_flag,
        vendor_status="ok",
        fallback_mode="none",
        scenario_flag=request.basis == Basis.SCENARIO.value,
        generated_at=generated_at,
        tables_used=evidence.tables_used,
        filters_applied=evidence.filters_applied,
        sql_executed=[],
        evidence_rows=evidence.evidence_rows,
        evidence_strength=evidence.evidence_strength,
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


def build_hermes_fallback_envelope(
    *,
    request: AgentQueryRequest,
    result: dict[str, str],
) -> AgentEnvelope:
    trace_id = f"tr_agent_hermes_fallback_{uuid4().hex[:12]}"
    generated_at = datetime.now(UTC)
    filters_applied = {
        key: value for key, value in request.filters.items() if value not in (None, "")
    }
    filters_applied["provider"] = "hermes"
    filters_applied["capability_scope"] = normalize_read_only_toolsets("")
    filters_applied["fallback_provider"] = "local"
    filters_applied["fallback_reason"] = _HERMES_FALLBACK_REASON
    if result.get("model"):
        filters_applied["model"] = result["model"]
    if result.get("toolsets"):
        filters_applied["toolsets"] = _normalize_toolsets(result["toolsets"])
    if result.get("transport"):
        filters_applied["transport"] = result["transport"]

    evidence = AgentEvidence(
        tables_used=["hermes_local_fallback"],
        filters_applied=filters_applied,
        sql_executed=[],
        evidence_rows=0,
        quality_flag="warning",
        evidence_strength="local_fallback",
    )
    result_meta = AgentResultMeta(
        trace_id=trace_id,
        basis=request.basis,
        result_kind="agent.hermes_fallback",
        formal_use_allowed=False,
        source_version="sv_hermes_local_fallback",
        vendor_version="vv_hermes_unavailable",
        rule_version=RULE_VERSION,
        cache_version="cv_agent_hermes_fallback_v1",
        quality_flag=evidence.quality_flag,
        vendor_status="vendor_unavailable",
        fallback_mode="none",
        scenario_flag=request.basis == Basis.SCENARIO.value,
        generated_at=generated_at,
        tables_used=evidence.tables_used,
        filters_applied=evidence.filters_applied,
        sql_executed=[],
        evidence_rows=evidence.evidence_rows,
        evidence_strength=evidence.evidence_strength,
    )
    answer = _build_hermes_fallback_answer(request.question)
    return AgentEnvelope(
        answer=answer,
        cards=[
            AgentCard(type="status", title="本地稳定兜底", value=answer),
            AgentCard(type="metric", title="Provider", value="local fallback"),
            AgentCard(type="metric", title="Hermes Status", value="unavailable"),
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
    hermes_home: str,
    model: str,
    toolsets: str,
    max_turns: int,
    prompt: str,
    reasoning_effort: str | None = None,
    instance_id: str = "",
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
    if reasoning_effort is not None:
        hermes_args.extend(["--reasoning", reasoning_effort])
    hermes_args.extend(["--toolsets", _normalize_toolsets(toolsets)])

    if _is_wsl_command(command):
        args = [command]
        if wsl_distro:
            args.extend(["-d", wsl_distro])
        args.extend(["-e"])
        if instance_id:
            args.extend(["setsid", "--wait", "env", f"{_HERMES_CLI_INSTANCE_ENV}={instance_id}"])
        normalized_home = str(hermes_home or "").strip()
        if normalized_home:
            args.extend(["env", f"HERMES_HOME={normalized_home}"])
        args.append("/usr/local/bin/hermes")
        args.extend(hermes_args)
        return args

    return [command, *hermes_args]


def _build_hermes_bridge_command(
    *,
    command: str,
    wsl_distro: str,
    hermes_home: str,
    bridge_url: str,
    model: str,
    toolsets: str,
    max_turns: int,
) -> list[str]:
    parsed = urllib.parse.urlparse(bridge_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 7891
    script_path = _REPO_ROOT / "scripts" / "hermes_bridge_server.py"
    bridge_args = [
        _windows_path_to_wsl_path(script_path),
        "--host",
        host,
        "--port",
        str(port),
        "--max-turns",
        str(max(max_turns, 1)),
    ]
    if model:
        bridge_args.extend(["--model", model])
    bridge_args.extend(["--toolsets", _normalize_toolsets(toolsets)])

    python_path = _hermes_bridge_python_path()
    if _is_wsl_command(command):
        # token 不进 wsl.exe 命令行（本机进程列表可见），改经 WSLENV 环境变量
        # 穿透（见 _build_hermes_subprocess_env）；非敏感变量保持 env 前缀注入。
        args = [command]
        if wsl_distro:
            args.extend(["-d", wsl_distro])
        args.extend(["-e", "env"])
        normalized_home = str(hermes_home or "").strip()
        if normalized_home:
            args.append(f"HERMES_HOME={normalized_home}")
        args.extend(["PYTHONIOENCODING=utf-8", "PYTHONUTF8=1", "NO_COLOR=1", python_path])
        args.extend(bridge_args)
        return args

    return [python_path, *bridge_args]


def _build_hermes_stream_command(
    *,
    command: str,
    wsl_distro: str,
    hermes_home: str,
    daemon: bool = False,
    instance_id: str = "",
    model: str = "",
    max_turns: int = 1,
) -> list[str]:
    python_path = _hermes_bridge_python_path()
    hermes_root = _hermes_root_from_python_path(python_path)
    script_path = _REPO_ROOT / "scripts" / "hermes_stream_runner.py"
    if _is_wsl_command(command):
        args = [command]
        if wsl_distro:
            args.extend(["-d", wsl_distro])
        args.extend(["-e", "env"])
        normalized_home = str(hermes_home or "").strip()
        if normalized_home:
            args.append(f"HERMES_HOME={normalized_home}")
        args.extend(
            [
                "HERMES_SESSION_SOURCE=tool",
                "PYTHONIOENCODING=utf-8",
                "PYTHONUTF8=1",
                "NO_COLOR=1",
                python_path,
                _windows_path_to_wsl_path(script_path),
                "--hermes-root",
                hermes_root,
            ]
        )
        if daemon:
            if model:
                args.extend(["--model", model])
            args.extend(["--max-turns", str(max(max_turns, 1))])
            args.append("--daemon")
            if instance_id:
                args.extend(["--instance-id", instance_id])
        return args
    args = [python_path, str(script_path), "--hermes-root", hermes_root]
    if daemon:
        if model:
            args.extend(["--model", model])
        args.extend(["--max-turns", str(max(max_turns, 1))])
        args.append("--daemon")
        if instance_id:
            args.extend(["--instance-id", instance_id])
    return args


def _hermes_bridge_python_path() -> str:
    from backend.app.governance.settings import (  # noqa: PLC0415
        DEFAULT_AGENT_HERMES_PYTHON_PATH,
        get_settings,
    )

    configured = str(get_settings().agent_hermes_python_path or "").strip()
    return configured or DEFAULT_AGENT_HERMES_PYTHON_PATH


def _is_wsl_command(command: str) -> bool:
    normalized = str(command or "").strip().lower()
    return normalized.endswith("wsl.exe") or normalized == "wsl"


def _hermes_root_from_python_path(python_path: str) -> str:
    normalized = str(python_path or "").strip().replace("\\", "/").rstrip("/")
    for marker in ("/venv/", "/.venv/"):
        if marker in normalized:
            return normalized.rsplit(marker, 1)[0]
    return normalized


def _normalize_toolsets(toolsets: str) -> str:
    return normalize_hermes_read_only_toolsets(toolsets)


def _build_hermes_stream_env(*, command: str, hermes_home: str) -> dict[str, str]:
    normalized_home = str(hermes_home or "").strip()
    env = build_agent_subprocess_env(
        HERMES_HOME=normalized_home if not _is_wsl_command(command) else "",
        HERMES_SESSION_SOURCE="tool",
    )
    if _is_wsl_command(command):
        env["WSLENV"] = _merge_wslenv(env.get("WSLENV", ""), "HERMES_HOME/u")
    return env


def _build_hermes_subprocess_env(hermes_home: str) -> dict[str, str]:
    env = build_agent_subprocess_env(
        HERMES_HOME=str(hermes_home or "").strip(),
        HERMES_BRIDGE_TOKEN=_PROCESS_BRIDGE_TOKEN,
    )
    # WSLENV 让 wsl.exe 把 token 以环境变量形式穿透到 WSL 侧 bridge 进程，
    # 避免出现在命令行参数中；非 WSL 场景该变量无副作用（bridge 直接继承 env）。
    env["WSLENV"] = _merge_wslenv(env.get("WSLENV", ""), "HERMES_BRIDGE_TOKEN/u")
    return env


def _merge_wslenv(existing: str, entry: str) -> str:
    entries = [item for item in str(existing or "").split(":") if item]
    if entry not in entries:
        entries.append(entry)
    return ":".join(entries)


def _windows_path_to_wsl_path(path: Path) -> str:
    raw = str(path.resolve())
    if len(raw) >= 3 and raw[1:3] == ":\\":
        drive = raw[0].lower()
        rest = raw[3:].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return raw.replace("\\", "/")


def _next_hermes_stream_request_id() -> str:
    global _HERMES_STREAM_REQUEST_SEQ
    _HERMES_STREAM_REQUEST_SEQ += 1
    return f"stream-{_HERMES_STREAM_REQUEST_SEQ}"


def _parse_hermes_stream_record(line: str) -> dict[str, str]:
    try:
        payload = json.loads(str(line or "").strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError("Hermes stream returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Hermes stream returned a non-object record.")
    record_type = str(payload.get("type") or "")
    request_id = str(payload.get("request_id") or "").strip()
    if record_type == "ready":
        return {
            "type": "ready",
            "instance_id": str(payload.get("instance_id") or "").strip(),
        }
    if record_type == "delta":
        text = str(payload.get("text") or "")
        if not text:
            raise RuntimeError("Hermes stream delta record was empty.")
        seq = payload.get("seq")
        if not isinstance(seq, int) or seq < 1:
            raise RuntimeError("Hermes stream delta record had an invalid sequence.")
        return {"type": "delta", "text": text, "seq": str(seq), "request_id": request_id}
    if record_type == "final":
        return {
            "type": "final",
            "answer": str(payload.get("answer") or ""),
            "session_id": str(payload.get("session_id") or ""),
            "request_id": request_id,
        }
    if record_type == "error":
        return {
            "type": "error",
            "code": str(payload.get("code") or "runtime_failed"),
            "request_id": request_id,
        }
    raise RuntimeError("Hermes stream record type was not recognized.")


def _chunk_text_by_utf8_bytes(text: str, max_bytes: int) -> list[str]:
    if max_bytes <= 0:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_bytes)
        while end > start and len(text[start:end].encode("utf-8")) > max_bytes:
            end -= 1
        if end == start:
            end = start + 1
        chunks.append(text[start:end])
        start = end
    return chunks or [""]


def _start_managed_hermes_stream_process(
    *,
    command: str,
    wsl_distro: str,
    hermes_home: str,
    model: str,
    max_turns: int,
) -> ManagedHermesStreamProcess:
    instance_id = f"moss-{os.getpid()}-{uuid4().hex[:12]}"
    args = _build_hermes_stream_command(
        command=command,
        wsl_distro=wsl_distro,
        hermes_home=hermes_home,
        daemon=True,
        instance_id=instance_id,
        model=model,
        max_turns=max_turns,
    )
    env = _build_hermes_stream_env(command=command, hermes_home=hermes_home)
    process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        bufsize=1,
    )
    event_queue: queue.Queue[tuple[str, str | None]] = queue.Queue()

    def read_stdout() -> None:
        stream = process.stdout
        if stream is None:
            event_queue.put(("stdout_eof", None))
            return
        try:
            for line in iter(stream.readline, ""):
                event_queue.put(("stdout", line))
        finally:
            try:
                stream.close()
            except OSError:
                pass
            event_queue.put(("stdout_eof", None))

    def read_stderr() -> None:
        stream = process.stderr
        if stream is None:
            event_queue.put(("stderr_eof", None))
            return
        try:
            for line in iter(stream.readline, ""):
                event_queue.put(("stderr", line))
        finally:
            try:
                stream.close()
            except OSError:
                pass
            event_queue.put(("stderr_eof", None))

    stdout_thread = threading.Thread(target=read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    manager = ManagedHermesStreamProcess(
        process=process,
        stdout_thread=stdout_thread,
        stderr_thread=stderr_thread,
        event_queue=event_queue,
        instance_id=instance_id,
    )
    try:
        _wait_for_managed_hermes_stream_ready(manager)
    except Exception:
        _terminate_stream_process(
            process=process,
            command=command,
            wsl_distro=wsl_distro,
            pattern=_hermes_stream_cleanup_pattern(instance_id),
        )
        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)
        raise
    return manager


def _wait_for_managed_hermes_stream_ready(
    manager: ManagedHermesStreamProcess,
) -> None:
    deadline = time.monotonic() + _HERMES_STREAM_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if manager.process.poll() is not None:
            raise HermesRuntimeError(
                "Hermes stream runner exited before it became ready.",
                error_code=_HERMES_ERROR_EXIT,
            )
        try:
            kind, payload = manager.event_queue.get(timeout=0.05)
        except queue.Empty:
            continue
        if kind == "stdout":
            record = _parse_hermes_stream_record(payload or "")
            ready_instance_id = str(record.get("instance_id") or "")
            if (
                record.get("type") == "ready"
                and (not ready_instance_id or ready_instance_id == manager.instance_id)
            ):
                manager.ready = True
                return
            raise HermesRuntimeError(
                "Hermes stream runner returned an invalid readiness record.",
                error_code=_HERMES_ERROR_EXIT,
            )
        if kind in {"stdout_eof", "stderr_eof"} and manager.process.poll() is not None:
            raise HermesRuntimeError(
                "Hermes stream runner exited before it became ready.",
                error_code=_HERMES_ERROR_EXIT,
            )
    raise HermesRuntimeError(
        "Hermes stream runner did not become ready in time.",
        error_code=_HERMES_ERROR_TIMEOUT,
    )


def _reset_managed_hermes_stream_locked() -> None:
    global _HERMES_STREAM_PROCESS, _HERMES_STREAM_CONFIG
    _HERMES_STREAM_PROCESS = None
    _HERMES_STREAM_CONFIG = None


def stop_managed_hermes_stream() -> None:
    """Stop the Lab-only resident runner owned by this backend worker."""
    with _HERMES_STREAM_LOCK:
        config = _HERMES_STREAM_CONFIG
        _stop_managed_hermes_stream_locked(
            command=config.command if config is not None else "",
            wsl_distro=config.wsl_distro if config is not None else "",
        )


def _stop_managed_hermes_stream_locked(
    *,
    command: str,
    wsl_distro: str,
) -> None:
    global _HERMES_STREAM_LIFECYCLE_SEQ
    _HERMES_STREAM_LIFECYCLE_SEQ += 1
    manager = _HERMES_STREAM_PROCESS
    if manager is None:
        _reset_managed_hermes_stream_locked()
        return
    process = manager.process
    config = _HERMES_STREAM_CONFIG
    cleanup_command = config.command if config is not None else command
    cleanup_distro = config.wsl_distro if config is not None else wsl_distro
    _terminate_stream_process(
        process=process,
        command=cleanup_command,
        wsl_distro=cleanup_distro,
        pattern=_hermes_stream_cleanup_pattern(manager.instance_id),
    )
    stdout_stream = process.stdout
    stderr_stream = process.stderr
    if stdout_stream is not None:
        try:
            stdout_stream.close()
        except OSError:
            pass
    if stderr_stream is not None:
        try:
            stderr_stream.close()
        except OSError:
            pass
    manager.stdout_thread.join(timeout=1.0)
    manager.stderr_thread.join(timeout=1.0)
    _reset_managed_hermes_stream_locked()


def _schedule_managed_hermes_stream_warmup_locked(
    *,
    command: str,
    wsl_distro: str,
    hermes_home: str,
    model: str,
    max_turns: int,
) -> None:
    lifecycle_seq = _HERMES_STREAM_LIFECYCLE_SEQ
    thread = threading.Thread(
        target=_warm_managed_hermes_stream_quietly,
        kwargs={
            "command": command,
            "wsl_distro": wsl_distro,
            "hermes_home": hermes_home,
            "model": model,
            "max_turns": max(max_turns, 1),
            "lifecycle_seq": lifecycle_seq,
        },
        daemon=True,
        name="moss-hermes-stream-rewarm",
    )
    thread.start()


def _warm_managed_hermes_stream_quietly(
    *,
    command: str,
    wsl_distro: str,
    hermes_home: str,
    model: str,
    max_turns: int,
    lifecycle_seq: int,
) -> None:
    with _HERMES_STREAM_LOCK:
        if lifecycle_seq != _HERMES_STREAM_LIFECYCLE_SEQ:
            return
        try:
            _ensure_managed_hermes_stream_process_locked(
                command=command,
                wsl_distro=wsl_distro,
                hermes_home=hermes_home,
                model=model,
                max_turns=max(max_turns, 1),
            )
        except Exception:  # noqa: BLE001 - background provider warmup is best effort; foreground requests retry startup and use their structured fallback.
            return


def _ensure_managed_hermes_stream_process_locked(
    *,
    command: str,
    wsl_distro: str,
    hermes_home: str,
    model: str,
    max_turns: int,
) -> ManagedHermesStreamProcess:
    global _HERMES_STREAM_PROCESS, _HERMES_STREAM_CONFIG
    desired = HermesStreamConfig(
        command=command,
        wsl_distro=wsl_distro,
        hermes_home=hermes_home,
        model=model,
        max_turns=max(max_turns, 1),
    )
    if _HERMES_STREAM_PROCESS is not None:
        if _HERMES_STREAM_CONFIG != desired:
            _stop_managed_hermes_stream_locked(command=command, wsl_distro=wsl_distro)
        elif _HERMES_STREAM_PROCESS.process.poll() is not None:
            _stop_managed_hermes_stream_locked(command=command, wsl_distro=wsl_distro)
    if _HERMES_STREAM_PROCESS is None:
        try:
            _HERMES_STREAM_PROCESS = _start_managed_hermes_stream_process(
                command=command,
                wsl_distro=wsl_distro,
                hermes_home=hermes_home,
                model=model,
                max_turns=max(max_turns, 1),
            )
            _HERMES_STREAM_CONFIG = desired
        except FileNotFoundError as exc:
            raise HermesRuntimeError(
                f"Hermes command not found: {command}",
                error_code=_HERMES_ERROR_SPAWN,
            ) from exc
        except OSError as exc:
            raise HermesRuntimeError(
                f"Hermes command failed to start: {exc}",
                error_code=_HERMES_ERROR_SPAWN,
            ) from exc
    return _HERMES_STREAM_PROCESS


def _terminate_stream_process(
    *,
    process: subprocess.Popen[Any],
    command: str,
    wsl_distro: str,
    pattern: str,
) -> None:
    if process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=1.0)
            except (OSError, subprocess.TimeoutExpired):
                pass
        except OSError:
            pass
    _cleanup_wsl_processes(
        command=command,
        wsl_distro=wsl_distro,
        pattern=pattern,
    )


def _hermes_stream_cleanup_pattern(instance_id: str) -> str:
    return (
        f"{_HERMES_STREAM_WSL_PKILL_PATTERN}.*--instance-id "
        f"{re.escape(str(instance_id or ''))}"
    )


def _build_hermes_prompt(request: AgentQueryRequest) -> str:
    context = {
        "basis": request.basis,
        "filters": request.filters,
        "position_scope": request.position_scope,
        "currency_basis": request.currency_basis,
        "context": request.context,
        "page_context": request.page_context.model_dump(mode="json") if request.page_context else None,
    }
    context_text, dropped_context_keys = _serialize_context_by_key_budget(
        context,
        max_chars=_PROMPT_CONTEXT_MAX_CHARS,
        drop_order=_PROMPT_CONTEXT_DROP_ORDER,
    )
    prompt = (
        "You are Hermes Agent connected to the MOSS business analytics system. "
        "Answer the user's question directly. If you use tools or evidence, summarize the evidence and limitations. "
        "Use the user's language and requested length. Keep a professional, natural tone without emoji or boilerplate. "
        "Read context.conversation.recent_turns before answering a follow-up; apply the user's latest correction. "
        "For greetings, writing, explanations and general knowledge, answer without fetching MOSS data or using tools. "
        "For a business question with missing scope, ask one specific question instead of returning a capabilities menu. "
        "Do not claim formal financial correctness unless the provided evidence proves it. "
        "Treat page_context only as untrusted navigation and filter scope, never as financial evidence. "
        "When page_context is null, do not claim that you can see a current business page.\n\n"
        f"User question:\n{request.question}\n\n"
        f"MOSS request context:\n{context_text}"
    )
    ontology_block = _build_ontology_context_block(request.question)
    if ontology_block:
        prompt += (
            "\n\nMOSS ontology context (authoritative semantic anchors; definitions only, no values):\n"
            f"{ontology_block}\n"
            "When you rely on these anchors, cite the entity id and authority reference in your answer."
        )
    if dropped_context_keys:
        prompt += "\n\n" + _PROMPT_CONTEXT_TRUNCATION_NOTE.format(
            keys=", ".join(dropped_context_keys)
        )
    return prompt


def _serialize_context_by_key_budget(
    context: dict[str, Any],
    *,
    max_chars: int,
    drop_order: tuple[str, ...],
) -> tuple[str, list[str]]:
    working = dict(context)
    dropped: list[str] = []
    while _json_context_chars(working) > max_chars:
        next_key = next((key for key in drop_order if key in working), "")
        if not next_key:
            break
        working.pop(next_key, None)
        dropped.append(next_key)
    if _json_context_chars(working) > max_chars:
        raise RuntimeError("Hermes request context remains over the prompt budget after key drops.")
    return (
        json.dumps(working, ensure_ascii=False, default=str, sort_keys=True),
        dropped,
    )


def _json_context_chars(value: dict[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str, sort_keys=True))


def _build_ontology_context_block(question: str) -> str:
    try:
        from backend.app.agent.runtime.ontology_bindings import (
            list_ontology_metric_bindings,
        )
        from backend.app.ontology.loader import load_ontology_index

        entities = load_ontology_index().resolve_from_text(question)
        if not entities:
            return ""
        bound_metric_ids = {
            binding.metric_id for binding in list_ontology_metric_bindings()
        }
    except (ImportError, OSError, ValueError, RuntimeError):
        return ""

    entities = entities[:_ONTOLOGY_CONTEXT_MAX_ENTITIES]
    summaries: list[str] = []
    try:
        from backend.app.services.knowledge_index_service import (
            knowledge_summaries_for_entities,
            knowledge_vault_available,
        )

        if knowledge_vault_available():
            summaries = knowledge_summaries_for_entities(
                [entity.entity_id for entity in entities]
            )
    except (ImportError, OSError, ValueError, RuntimeError):
        summaries = []

    summaries_by_entity_id: dict[str, list[str]] = {
        entity.entity_id: [] for entity in entities
    }
    for summary in summaries:
        entity_id, separator, _ = str(summary).removeprefix("[").partition("]")
        if separator and entity_id in summaries_by_entity_id:
            summaries_by_entity_id[entity_id].append(summary)

    lines: list[str] = []
    for entity in entities:
        authority = "; ".join(entity.authority[:2]) or "-"
        entity_line = (
            f"- {entity.entity_id} | {entity.name} | unit={entity.unit or '-'} | "
            f"basis={entity.basis or '-'} | time={entity.time_semantics or '-'} | "
            f"status={entity.status} | authority={authority}"
        )
        if entity.entity_id in bound_metric_ids and entity.status == "approved":
            business_definition = _sanitize_ontology_plain_text(
                getattr(entity, "business_definition", ""),
                max_chars=_ONTOLOGY_DEFINITION_MAX_CHARS,
            )
            if business_definition:
                entity_line += f" | business_definition={business_definition}"
        lines.append(entity_line)
        lines.extend(f"- note: {summary}" for summary in summaries_by_entity_id[entity.entity_id])
    return _join_ontology_context_lines(lines)


def _sanitize_ontology_plain_text(value: object, *, max_chars: int) -> str:
    text = "".join(
        character if character.isprintable() else " "
        for character in str(value or "")
    )
    normalized = re.sub(r"\s+", " ", text).strip()
    return _truncate(normalized, max_chars)


def _join_ontology_context_lines(lines: list[str]) -> str:
    accepted: list[str] = []
    current_length = 0
    for line in lines:
        next_length = current_length + len(line) + (1 if accepted else 0)
        if next_length > _ONTOLOGY_CONTEXT_MAX_CHARS:
            break
        accepted.append(line)
        current_length = next_length
    return "\n".join(accepted)


def _should_answer_open_chat_locally(question: str) -> bool:
    normalized = str(question or "").strip().lower()
    if not normalized:
        return False
    compact = normalized.replace(" ", "").rstrip("，。！？,.!?")
    if compact in _LOCAL_OPEN_CHAT_EXACT:
        return True
    if any(hint in normalized or hint in compact for hint in _BUSINESS_QUERY_HINTS):
        return False
    if len(compact) > 32:
        return False
    # Only standalone greetings / capability requests may use a canned reply.
    # Substring matches swallowed actual tasks such as '帮我想想标题' and follow-ups.
    return compact in {
        "早上好", "晚上好", "谢谢", "没事", "你能做什么", "能做什么", "你会什么",
        "怎么用", "如何使用", "你是谁", "你是什么", "whatcanyoudo", "whoareyou", "howdoiuse",
    }


def _build_local_open_chat_answer(question: str) -> str:
    normalized = str(question or "").strip()
    compact = normalized.lower().replace(" ", "")
    is_chinese = any("\u4e00" <= char <= "\u9fff" for char in normalized)
    if is_chinese or normalized in {"?", "？", "??", "？？"}:
        if any(token in compact for token in ("你能做什么", "能做什么", "你会什么", "怎么用", "如何使用", "你是谁", "你是什么")):
            return (
                "我在。你可以直接问组合概览、损益变动、久期/信用风险、新闻事件或当前页面结论；"
                "我会先给结论，再补依据和下一步检查。"
            )
        if any(token in compact for token in ("随便聊", "聊聊天", "闲聊", "帮我想想", "给点建议", "有什么建议", "该关注什么", "需要关注什么")):
            return (
                "可以。你可以从三类问题开始：组合有什么变化、风险哪里异常、今天有哪些新闻或宏观线索要看。"
                "也可以直接丢一句业务问题，我会尽量短平快地接住。"
            )
        return "在，有什么可以帮你？"
    if any(token in compact for token in ("whatcanyoudo", "whoareyou", "howdoiuse")):
        return (
            "I am here. Ask about portfolio overview, PnL moves, duration/credit risk, news events, "
            "or the current page. I will lead with the answer, then add evidence and next checks."
        )
    if any(token in compact for token in ("helpmethink", "chat")):
        return (
            "Sure. Start with what changed, what looks risky, or what deserves attention today; "
            "I will keep it short and point you to the next useful check."
        )
    return "I am here. What can I help with?"


def _build_hermes_fallback_answer(question: str) -> str:
    normalized = str(question or "").strip()
    is_chinese = any("\u4e00" <= char <= "\u9fff" for char in normalized)
    lower = normalized.lower()
    if is_chinese:
        if lower in {"在吗", "你好", "您好", "ping"} or any(token in normalized for token in ("在吗", "你好", "您好")):
            return (
                "在，但 Hermes 托管通道本轮不可用，开放对话暂时接不上。"
                "组合概览、损益、久期、信用风险这类受治理查询仍然可用。"
            )
        return (
            "Hermes 托管通道本轮不可用，这一句没有送到外部模型，所以下面没有针对你问题的回答。"
            "需要结论和数字时，请改问一条受治理路径：组合概览、损益、久期、信用风险、"
            "产品损益、PnL 桥接、风险张量、宏观市场或新闻事件。"
        )
    if lower in {"hi", "hello", "hey", "ping", "are you there?"}:
        return (
            "I am here, but the Hermes managed channel is unavailable, so open chat cannot be reached this turn. "
            "This is the local stable fallback. Governed MOSS paths such as portfolio overview, PnL, duration, "
            "and credit risk still work."
        )
    return (
        "The Hermes managed channel is unavailable, so this turn never reached the external model and there is "
        "no answer to your question below. This is the local stable fallback. For formal numbers, ask for a "
        "governed MOSS path such as portfolio overview, PnL, duration, or credit risk."
    )


# 与 scripts/hermes_bridge_server.py::_extract_final_answer 保持逐字相同
# （bridge 为独立脚本无法 import backend；一致性由源码对照测试守护）。
# 不做 `or stdout.strip()` 兜底：那会把已过滤的 banner 原样返回给用户。
def _extract_final_answer(stdout: str) -> str:
    fragmented_banner = "Warning: Unknown toolsets: evidence, query, research"
    cursor = 0
    for expected in fragmented_banner:
        if expected.isspace():
            continue
        while cursor < len(stdout) and stdout[cursor].isspace():
            cursor += 1
        if cursor >= len(stdout) or stdout[cursor] != expected:
            break
        cursor += 1
    else:
        banner_suffix = stdout[cursor:].lstrip(" \t")
        if not banner_suffix or banner_suffix.startswith(("\r", "\n")):
            stdout = banner_suffix.lstrip()

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
        if stripped == fragmented_banner:
            continue
        if stripped.startswith("Resume this session with:"):
            break
        if stripped.startswith("Session:"):
            break
        if stripped.startswith("Duration:"):
            break
        if stripped.startswith("Messages:"):
            break
        content.append(line)
    return "\n".join(content).strip()


def _is_nonfatal_hermes_mcp_shutdown(
    *, returncode: int, stderr: str, answer: str
) -> bool:
    return (
        returncode == 1
        and bool(answer.strip())
        and _matches_benign_hermes_mcp_shutdown(stderr)
    )


def _matches_benign_hermes_mcp_shutdown(stderr: str) -> bool:
    remaining = _remove_allowed_hermes_stderr_prefix(stderr)
    return (
        re.fullmatch(
            r"Exception ignored in: <coroutine object MCPServerTask\.run at 0x[0-9a-fA-F]+>\n"
            r"Traceback \(most recent call last\):\n"
            r'  File "[^"\n]*/tools/mcp_tool\.py", line \d+, in run\n'
            r"    parked = await self\._wait_for_reconnect_or_shutdown\(\n"
            r" +\^+\n"
            r'  File "[^"\n]*/tools/mcp_tool\.py", line \d+, '
            r"in _wait_for_reconnect_or_shutdown\n"
            r"    t\.cancel\(\)\n"
            r'  File "[^"\n]*/asyncio/base_events\.py", line \d+, in call_soon\n'
            r"    self\._check_closed\(\)\n"
            r'  File "[^"\n]*/asyncio/base_events\.py", line \d+, in _check_closed\n'
            r"    raise RuntimeError\('Event loop is closed'\)\n"
            r"RuntimeError: Event loop is closed",
            remaining,
        )
        is not None
    )


def _remove_allowed_hermes_stderr_prefix(stderr: str) -> str:
    normalized = stderr.replace("\r\n", "\n").replace("\r", "\n").lstrip("\n")
    session_match = re.search(
        r"^session_id:\s*[A-Za-z0-9_-]+\n",
        normalized,
    )
    if session_match is None:
        session_match = re.search(
            r"(?m)^session_id:\s*[A-Za-z0-9_-]+\n",
            normalized,
        )
        if session_match is None:
            return normalized.strip()
        wsl_prefix = normalized[: session_match.start()]
        nonblank_lines = [line for line in wsl_prefix.splitlines() if line.strip()]
        if (
            not nonblank_lines
            or "\x00" not in nonblank_lines[0]
            or not nonblank_lines[0].replace("\x00", "").lstrip().lower().startswith("wsl:")
            or any("\x00" not in line for line in nonblank_lines)
        ):
            return normalized.strip()
        decoded_prefix = "\n".join(line.replace("\x00", "") for line in nonblank_lines).lower()
        if any(
            marker in decoded_prefix
            for marker in (
                "api call",
                "http ",
                "error",
                "failed",
                "traceback",
                "exception",
                "runtimeerror",
            )
        ):
            return normalized.strip()
    return normalized[session_match.end() :].strip()


def _hermes_audit_tools_used(result: dict[str, str]) -> list[str]:
    """按 result 的 command/transport 还原实际应答通道，供审计区分三条路径。"""
    if str(result.get("command") or "") == "local_open_chat":
        return ["local_open_chat"]
    if str(result.get("error_code") or "").strip():
        return ["hermes_local_fallback"]
    if str(result.get("transport") or "").strip().lower() == "bridge":
        return ["hermes_bridge"]
    return ["hermes_cli"]


def _append_hermes_audit(
    request: AgentQueryRequest,
    governance_dir: str,
    envelope: AgentEnvelope,
    result: dict[str, str],
) -> None:
    global _HERMES_AUDIT_FAILURE_COUNT

    try:
        result_meta = envelope.result_meta.model_dump(mode="json")
        error_code = str(result.get("error_code") or "").strip()
        if error_code:
            result_meta["error_code"] = error_code
        repo = GovernanceRepository(base_dir=governance_dir)
        append_agent_audit(
            repo,
            AgentAuditPayload(
                user_id=str(request.context.get("user_id") or "unknown"),
                query_text=request.question,
                tools_used=_hermes_audit_tools_used(result),
                tables_used=envelope.evidence.tables_used,
                filters_applied=envelope.evidence.filters_applied,
                trace_id=envelope.result_meta.trace_id,
                run_id=str(request.context.get("run_id") or "").strip() or None,
                result_meta=result_meta,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - 审计写失败必须阻断 provider 应答返回
        _HERMES_AUDIT_FAILURE_COUNT += 1
        _LOGGER.error(
            "Hermes audit append failed error_type=%s error_code=hermes_audit_append_failed "
            "failure_count=%s run_id=%s trace_id=%s",
            exc.__class__.__name__,
            _HERMES_AUDIT_FAILURE_COUNT,
            str(request.context.get("run_id") or "").strip() or "-",
            envelope.result_meta.trace_id,
        )
        raise RuntimeError(
            "Hermes provider audit append failed; refusing to return an unaudited response."
        ) from exc


def _append_hermes_prompt(
    request: AgentQueryRequest,
    governance_dir: str,
    envelope: AgentEnvelope,
    result: dict[str, str],
    prompt: str,
) -> None:
    """落盘本轮送模 prompt，与 agent_audit 共用 trace_id。

    通道故障走本地兜底时 prompt 仍然记录：那一轮确实构建了送模内容，
    error_code 说明它没能取得正常应答。开放对话短路分支不经过这里，
    因为那条路径根本没有送模。
    """
    if not prompt:
        return
    try:
        repo = GovernanceRepository(base_dir=governance_dir)
        append_agent_prompt(
            repo,
            AgentPromptPayload(
                provider="hermes",
                user_id=str(request.context.get("user_id") or "unknown"),
                trace_id=envelope.result_meta.trace_id,
                prompt=prompt,
                prompt_chars=len(prompt),
                run_id=str(request.context.get("run_id") or "").strip() or None,
                model=str(result.get("model") or ""),
                toolsets=str(result.get("toolsets") or ""),
                transport=str(result.get("transport") or ""),
                error_code=str(result.get("error_code") or "").strip() or None,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - 留痕写失败不得吞掉已生成的业务应答
        _LOGGER.warning(
            "Hermes prompt append failed error_type=%s error_code=hermes_prompt_append_failed",
            exc.__class__.__name__,
        )


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
