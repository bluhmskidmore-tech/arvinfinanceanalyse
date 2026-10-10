from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any, BinaryIO, TextIO, cast
from uuid import uuid4

from backend.app.agent.runtime.subprocess_env import build_agent_subprocess_env
from backend.app.agent.runtime.toolset_policy import normalize_read_only_toolsets
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
from backend.app.services.agent_service import ensure_agent_execution_resources_allowed
from backend.app.services.dexter_research_context_builder import (
    build_dexter_research_context,
    resolve_dexter_research_read_resources,
)

RULE_VERSION = "rv_agent_dexter_v1"
_DEXTER_FALLBACK_REASON = "dexter_runtime_unavailable"
_DEXTER_AUDIT_FAILURE_COUNT = 0
_LOGGER = logging.getLogger(__name__)
_DEXTER_PROMPT_MAX_CHARS = 24_000
_DEXTER_REQUEST_CONTEXT_DROP_ORDER = (
    "page_context",
    "context",
    "filters",
    "currency_basis",
    "position_scope",
    "basis",
)
_DEXTER_RESEARCH_CONTEXT_DROP_ORDER = (
    ("stock", "news_events"),
    ("macro", "tushare_series"),
    ("macro", "choice_snapshots"),
    ("macro", "choice_series"),
    ("macro", "catalog"),
)


class DexterRunCancelled(RuntimeError):
    """A cancelled provider call must not produce a fallback answer or audit."""


def execute_dexter_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
    settings: Any,
    *,
    cancel_event: threading.Event | None = None,
) -> AgentEnvelope:
    # Authorization errors must propagate; they are not provider-runtime fallback.
    ensure_agent_execution_resources_allowed(
        request,
        settings=settings,
        resources=resolve_dexter_research_read_resources(request),
    )
    research_context: dict[str, Any] = {}
    prompt = ""
    try:
        research_context = build_dexter_research_context(
            request=request,
            duckdb_path=str(getattr(settings, "duckdb_path", "") or ""),
        )
        prompt = _build_dexter_prompt(request, research_context=research_context)
        result = run_dexter_agent(
            request=request,
            command=str(getattr(settings, "agent_dexter_command", "dexter") or "dexter"),
            transport=str(getattr(settings, "agent_dexter_transport", "cli") or "cli"),
            bridge_url=str(getattr(settings, "agent_dexter_bridge_url", "") or ""),
            model=str(getattr(settings, "agent_dexter_model", "") or ""),
            toolsets=str(getattr(settings, "agent_dexter_toolsets", "") or ""),
            timeout_seconds=float(getattr(settings, "agent_dexter_timeout_seconds", 180.0) or 180.0),
            prompt_override=prompt,
            cancel_event=cancel_event,
        )
        dropped_keys = _extract_prompt_context_dropped_keys(prompt)
        if dropped_keys:
            result["prompt_context_dropped_keys"] = dropped_keys
        envelope = build_dexter_envelope(request=request, result=result, research_context=research_context)
    except DexterRunCancelled:
        raise
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
        if cancel_event is not None and cancel_event.is_set():
            raise DexterRunCancelled("Dexter request was cancelled; provider stop remains unconfirmed.") from exc
        # 运行链任何失败（含研究上下文构建、子进程拉起、超时、bridge 响应解析）都收敛到
        # 同一条确定性兜底路径；裸异常穿透到路由层会被误映射成 404/500 且无审计。
        _LOGGER.warning(
            "Dexter provider runtime failed provider=dexter error_type=%s error_code=%s",
            exc.__class__.__name__,
            _DEXTER_FALLBACK_REASON,
        )
        result = {
            "answer": "",
            "stdout": "",
            "stderr": "",
            "command": str(getattr(settings, "agent_dexter_command", "dexter") or "dexter"),
            "tool_name": "dexter_local_fallback",
            "model": str(getattr(settings, "agent_dexter_model", "") or ""),
            "toolsets": str(getattr(settings, "agent_dexter_toolsets", "") or ""),
            "transport": str(getattr(settings, "agent_dexter_transport", "cli") or "cli"),
            "error": _truncate(str(exc), 2000),
            "error_code": _DEXTER_FALLBACK_REASON,
        }
        dropped_keys = _extract_prompt_context_dropped_keys(prompt)
        if dropped_keys:
            result["prompt_context_dropped_keys"] = dropped_keys
        envelope = build_dexter_fallback_envelope(
            request=request,
            result=result,
            research_context=research_context,
        )
    _append_dexter_audit(request, governance_dir, envelope, result)
    _append_dexter_prompt(request, governance_dir, envelope, result, prompt)
    return envelope


def run_dexter_agent(
    *,
    request: AgentQueryRequest,
    command: str,
    transport: str,
    bridge_url: str,
    model: str,
    toolsets: str,
    timeout_seconds: float,
    prompt_override: str | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    if cancel_event is not None and cancel_event.is_set():
        raise DexterRunCancelled("Dexter request was cancelled before dispatch.")
    prompt = prompt_override or _build_dexter_prompt(request)
    normalized_transport = str(transport or "").strip().lower() or "cli"
    normalized_toolsets = _normalize_toolsets(toolsets)
    if normalized_transport in {"sidecar", "bridge"}:
        result = _post_dexter_bridge_query(
            bridge_url=str(bridge_url or "").strip() or "http://127.0.0.1:7892",
            prompt=prompt,
            model=model,
            toolsets=normalized_toolsets,
            timeout_seconds=timeout_seconds,
        )
        if cancel_event is not None and cancel_event.is_set():
            raise DexterRunCancelled("Dexter bridge request was cancelled; remote provider stop remains unconfirmed.")
        return result

    args = _build_dexter_command(
        command=command,
        prompt=prompt,
        model=model,
        toolsets=normalized_toolsets,
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
                env=build_agent_subprocess_env(),
            )
        else:
            completed = _run_dexter_cli_with_cancel(
                args=args, timeout_seconds=timeout_seconds, cancel_event=cancel_event,
            )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Dexter command not found: {command}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Dexter timed out after {timeout_seconds:g}s") from exc
    except OSError as exc:
        # 覆盖 PermissionError、Windows argv 超长（WinError 206）等启动失败。
        raise RuntimeError(f"Dexter command failed to start: {exc}") from exc

    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    if completed.returncode != 0:
        detail = _truncate((stderr or stdout).strip(), 2000)
        raise RuntimeError(f"Dexter failed with exit code {completed.returncode}: {detail}")

    payload = _parse_dexter_output(stdout)
    return {
        "answer": str(payload.get("answer") or stdout.strip()),
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
        "tool_name": str(payload.get("tool_name") or "dexter_cli"),
        "model": str(payload.get("model") or model or "default"),
        "toolsets": str(payload.get("toolsets") or normalized_toolsets or "default"),
        "transport": "cli",
        "tables_used": _normalize_tables_used(payload.get("tables_used"), fallback="dexter_cli"),
        **_structured_research_fields(payload),
    }


def _run_dexter_cli_with_cancel(
    *, args: list[str], timeout_seconds: float, cancel_event: threading.Event,
) -> subprocess.CompletedProcess[str]:
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
    process = subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=sys.platform != "win32",
        encoding="utf-8" if sys.platform != "win32" else None,
        errors="replace" if sys.platform != "win32" else None, env=build_agent_subprocess_env(),
        creationflags=creationflags,
        start_new_session=sys.platform != "win32",
    )
    try:
        deadline = time.monotonic() + max(timeout_seconds, 1.0)
        output = [bytearray(), bytearray()]
        eof = [False, False]
        while True:
            if cancel_event.is_set():
                try:
                    _stop_dexter_cli_process_tree(process)
                except (OSError, subprocess.SubprocessError) as exc:
                    raise DexterRunCancelled("Dexter CLI cancellation requested; process stop remains unconfirmed.") from exc
                raise DexterRunCancelled("Dexter CLI was cancelled; local process tree stopped.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _stop_dexter_cli_process_tree(process)
                raise subprocess.TimeoutExpired(args, max(timeout_seconds, 1.0))
            if sys.platform == "win32":
                for index, pipe in enumerate((process.stdout, process.stderr)):
                    if not eof[index]:
                        chunk = _read_dexter_windows_pipe(cast(BinaryIO, pipe))
                        if chunk is None:
                            eof[index] = True
                        else:
                            output[index].extend(chunk)
                returncode = process.poll()
                if all(eof) and returncode is not None:
                    return subprocess.CompletedProcess(args, returncode, *(bytes(part).decode("utf-8", errors="replace") for part in output))
                cancel_event.wait(min(0.05, remaining))
                continue
            try:
                stdout, stderr = process.communicate(timeout=min(0.05, remaining))
            except subprocess.TimeoutExpired:
                continue
            return subprocess.CompletedProcess(args, process.wait(), stdout, stderr)
    finally:
        # Windows reads synchronously without communicate's reader-thread close lock.
        cast(TextIO, process.stdout).close()
        cast(TextIO, process.stderr).close()


def _read_dexter_windows_pipe(pipe: BinaryIO) -> bytes | None:
    if sys.platform != "win32":
        raise RuntimeError("Windows pipe reading requires win32.")
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    peek = kernel32.PeekNamedPipe
    peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    peek.restype = wintypes.BOOL
    available = wintypes.DWORD()
    if not peek(msvcrt.get_osfhandle(pipe.fileno()), None, 0, None, ctypes.byref(available), None):
        error = ctypes.get_last_error()
        if error == 109:  # ERROR_BROKEN_PIPE: all inherited write handles closed.
            return None
        raise ctypes.WinError(error)
    return os.read(pipe.fileno(), available.value) if available.value else b""


def _stop_dexter_cli_process_tree(process: subprocess.Popen[Any]) -> None:
    # Same bounded tree termination used by yield_curve_fetch, kept in the
    # provider layer so services do not import materialization tasks.
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5.0, creationflags=subprocess.CREATE_NO_WINDOW, check=True,
        )
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=5.0)


def build_dexter_envelope(
    *,
    request: AgentQueryRequest,
    result: dict[str, Any],
    research_context: dict[str, Any] | None = None,
) -> AgentEnvelope:
    research_context = research_context or {}
    has_research_context = bool(research_context.get("domain"))
    trace_id = f"tr_agent_dexter_{uuid4().hex[:12]}"
    generated_at = datetime.now(UTC)
    filters_applied = {
        key: value for key, value in request.filters.items() if value not in (None, "")
    }
    if has_research_context:
        filters_applied.update(
            {
                key: value
                for key, value in dict(research_context.get("filters_applied") or {}).items()
                if value not in (None, "")
            }
        )
    # 运行时披露键最后写入：request/research filters 里的同名键不得覆写 provider 事实。
    filters_applied["provider"] = "dexter"
    if result.get("model"):
        filters_applied["model"] = result["model"]
    if result.get("toolsets"):
        filters_applied["toolsets"] = _normalize_toolsets(str(result["toolsets"]))
    if result.get("transport"):
        filters_applied["transport"] = result["transport"]
    dropped_keys = _normalize_string_list(result.get("prompt_context_dropped_keys"))
    if dropped_keys:
        filters_applied["prompt_context_dropped_keys"] = dropped_keys

    is_bridge_transport = str(result.get("transport") or "").strip().lower() in {"sidecar", "bridge"}
    tables_used = _normalize_tables_used(
        result.get("tables_used"),
        fallback="dexter_sidecar" if is_bridge_transport else "dexter_cli",
    )
    if has_research_context:
        tables_used = _dedupe([*tables_used, *list(research_context.get("tables_used") or [])])
    sql_executed = _research_sql_disclosure(research_context if has_research_context else None)
    evidence_rows = int(research_context.get("evidence_rows") or 0) if has_research_context else 0
    evidence_strength = (
        "mixed"
        if has_research_context and (sql_executed or evidence_rows > 0)
        else "provider_runtime"
    )
    quality_flag = _provider_runtime_quality_flag(
        str(research_context.get("quality_flag") or "warning") if has_research_context else "warning"
    )
    evidence = AgentEvidence(
        tables_used=tables_used,
        filters_applied=filters_applied,
        sql_executed=sql_executed,
        evidence_rows=evidence_rows,
        quality_flag=quality_flag,
        evidence_strength=evidence_strength,
    )
    # 用运行时 transport 判定来源版本：sidecar 自报真实表名时 tables_used 不含
    # "dexter_sidecar"，按表名判定会误标 sv_dexter_cli。
    source_suffix = "sidecar" if is_bridge_transport else "cli"
    result_meta = AgentResultMeta(
        trace_id=trace_id,
        basis=request.basis,
        result_kind="agent.dexter",
        formal_use_allowed=False,
        source_version=f"sv_dexter_{source_suffix}",
        vendor_version="vv_dexter",
        rule_version=RULE_VERSION,
        cache_version="cv_agent_dexter_v1",
        quality_flag=quality_flag,
        vendor_status="ok",
        fallback_mode="none",
        scenario_flag=request.basis == Basis.SCENARIO.value,
        generated_at=generated_at,
        tables_used=evidence.tables_used,
        filters_applied=evidence.filters_applied,
        sql_executed=evidence.sql_executed,
        evidence_rows=evidence.evidence_rows,
        evidence_strength=evidence.evidence_strength,
    )
    return AgentEnvelope(
        answer=str(result.get("answer") or ""),
        cards=_build_dexter_cards(result=result, research_context=research_context),
        evidence=evidence,
        result_meta=result_meta,
        next_drill=_build_next_drill(result.get("next_drill")),
        suggested_actions=[],
    )


def build_dexter_fallback_envelope(
    *,
    request: AgentQueryRequest,
    result: dict[str, Any],
    research_context: dict[str, Any] | None = None,
) -> AgentEnvelope:
    research_context = research_context or {}
    has_research_context = bool(research_context.get("domain"))
    trace_id = f"tr_agent_dexter_fallback_{uuid4().hex[:12]}"
    generated_at = datetime.now(UTC)
    filters_applied = {
        key: value for key, value in request.filters.items() if value not in (None, "")
    }
    if has_research_context:
        filters_applied.update(
            {
                key: value
                for key, value in dict(research_context.get("filters_applied") or {}).items()
                if value not in (None, "")
            }
        )
    # 运行时披露键最后写入：request/research filters 里的同名键不得覆写 fallback 事实。
    filters_applied["provider"] = "dexter"
    filters_applied["fallback_provider"] = "local"
    filters_applied["fallback_reason"] = str(result.get("error_code") or _DEXTER_FALLBACK_REASON)
    if result.get("model"):
        filters_applied["model"] = result["model"]
    if result.get("toolsets"):
        filters_applied["toolsets"] = _normalize_toolsets(str(result["toolsets"]))
    if result.get("transport"):
        filters_applied["transport"] = result["transport"]
    dropped_keys = _normalize_string_list(result.get("prompt_context_dropped_keys"))
    if dropped_keys:
        filters_applied["prompt_context_dropped_keys"] = dropped_keys

    # 研究上下文在 provider 失败前已真实执行过只读查询：表访问与 SQL 披露必须保留在证据里。
    tables_used = ["dexter_local_fallback"]
    if has_research_context:
        tables_used = _dedupe([*tables_used, *list(research_context.get("tables_used") or [])])
    sql_executed = _research_sql_disclosure(research_context if has_research_context else None)
    evidence_rows = int(research_context.get("evidence_rows") or 0) if has_research_context else 0

    evidence = AgentEvidence(
        tables_used=tables_used,
        filters_applied=filters_applied,
        sql_executed=sql_executed,
        evidence_rows=evidence_rows,
        quality_flag="warning",
        evidence_strength="local_fallback",
    )
    result_meta = AgentResultMeta(
        trace_id=trace_id,
        basis=request.basis,
        result_kind="agent.dexter_fallback",
        formal_use_allowed=False,
        source_version="sv_dexter_local_fallback",
        vendor_version="vv_dexter_unavailable",
        rule_version=RULE_VERSION,
        cache_version="cv_agent_dexter_fallback_v1",
        quality_flag=evidence.quality_flag,
        vendor_status="vendor_unavailable",
        fallback_mode="none",
        scenario_flag=request.basis == Basis.SCENARIO.value,
        generated_at=generated_at,
        tables_used=evidence.tables_used,
        filters_applied=evidence.filters_applied,
        sql_executed=evidence.sql_executed,
        evidence_rows=evidence.evidence_rows,
        evidence_strength=evidence.evidence_strength,
    )
    answer = _build_dexter_fallback_answer(
        request.question,
        has_research_context=has_research_context,
    )
    cards = [
        AgentCard(type="status", title="本地稳定兜底", value=answer),
        AgentCard(type="metric", title="Provider", value="local fallback"),
        AgentCard(type="metric", title="Dexter Status", value="unavailable"),
    ]
    if has_research_context:
        _append_list_card(
            cards,
            title="Research Limitations",
            card_type="research_limitations",
            value=[
                *_normalize_string_list(research_context.get("limitations")),
                *_normalize_string_list(research_context.get("stale_sources")),
            ],
        )
    return AgentEnvelope(
        answer=answer,
        cards=cards,
        evidence=evidence,
        result_meta=result_meta,
        next_drill=[],
        suggested_actions=[],
    )


def _build_dexter_fallback_answer(question: str, *, has_research_context: bool) -> str:
    normalized = str(question or "").strip()
    is_chinese = any("\u4e00" <= char <= "\u9fff" for char in normalized)
    if is_chinese:
        answer = (
            f"我收到了：{normalized}。Dexter 研究通道刚才不可用，这轮先用本地稳定兜底接住，"
            "不会返回 503 或红框。"
        )
        if has_research_context:
            answer += "已落地的 Choice/TuShare 研究证据仍在下方披露，可先据此判断，稍后重试 Dexter。"
        else:
            answer += "稍后可以重试 Dexter，或改问受治理的 MOSS 正式路径。"
        return answer
    answer = (
        f"I received: {normalized}. The Dexter research channel is unavailable, so this turn is "
        "handled by the local stable fallback instead of returning an error."
    )
    if has_research_context:
        answer += (
            " The landed Choice/TuShare research evidence is still disclosed below; "
            "retry Dexter later for the full research response."
        )
    else:
        answer += " Retry Dexter later, or ask for a governed MOSS path."
    return answer


def _research_sql_disclosure(research_context: dict[str, Any] | None) -> list[str]:
    disclosed: list[str] = []
    for statement in (research_context or {}).get("sql_executed") or []:
        text = " ".join(str(statement or "").split())
        if text.lower().startswith(("select", "with")):
            disclosed.append(text)
    return disclosed


def _build_dexter_command(
    *,
    command: str,
    prompt: str,
    model: str,
    toolsets: str,
) -> list[str]:
    args = [command, "query", "--json", "--prompt", prompt]
    if model:
        args.extend(["--model", model])
    if toolsets:
        args.extend(["--toolsets", toolsets])
    return args


def _provider_runtime_quality_flag(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"error", "stale"}:
        return normalized
    return "warning"


def _post_dexter_bridge_query(
    *,
    bridge_url: str,
    prompt: str,
    model: str,
    toolsets: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    url = urllib.parse.urljoin(bridge_url.rstrip("/") + "/", "query")
    body = json.dumps(
        {
            "prompt": prompt,
            "model": model,
            "toolsets": toolsets,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(timeout_seconds, 1.0)) as response:
            raw_body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Dexter sidecar failed: {_truncate(detail, 2000)}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Dexter sidecar unavailable: {exc}") from exc

    # 解析失败必须收敛为 RuntimeError：JSONDecodeError 是 ValueError 子类，裸穿透会被
    # 路由层 except ValueError 误映射成 404。decode 用 errors="replace" 排除 UnicodeDecodeError。
    try:
        payload = json.loads(raw_body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Dexter sidecar returned invalid JSON.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Dexter sidecar returned an invalid payload.")
    if not payload.get("ok", True):
        raise RuntimeError(str(payload.get("error") or "Dexter sidecar query failed."))

    return {
        "answer": str(payload.get("answer") or ""),
        "stdout": str(payload.get("stdout") or payload.get("answer") or ""),
        "stderr": str(payload.get("stderr") or ""),
        "command": "dexter_sidecar",
        "tool_name": str(payload.get("tool_name") or "dexter_sidecar"),
        "model": str(payload.get("model") or model or "default"),
        "toolsets": _normalize_toolsets(str(payload.get("toolsets") or toolsets)),
        "transport": "sidecar",
        "tables_used": _normalize_tables_used(payload.get("tables_used"), fallback="dexter_sidecar"),
        **_structured_research_fields(payload),
    }


def _build_dexter_prompt(
    request: AgentQueryRequest,
    *,
    research_context: dict[str, Any] | None = None,
) -> str:
    context = {
        "basis": request.basis,
        "filters": request.filters,
        "position_scope": request.position_scope,
        "currency_basis": request.currency_basis,
        "context": request.context,
        "page_context": request.page_context.model_dump(mode="json") if request.page_context else None,
    }
    research_payload = research_context if research_context and research_context.get("domain") else None
    prompt, dropped_keys = _build_dexter_prompt_with_budget(
        question=request.question,
        request_context=context,
        research_context=research_payload,
    )
    if dropped_keys and isinstance(research_context, dict):
        filters_applied = research_context.setdefault("filters_applied", {})
        if isinstance(filters_applied, dict):
            filters_applied["prompt_context_dropped_keys"] = dropped_keys
        research_context.setdefault("limitations", []).append(
            "Dexter prompt exceeded the CLI argv budget; dropped context keys: "
            + ", ".join(dropped_keys)
        )
    return prompt


def _build_dexter_prompt_with_budget(
    *,
    question: str,
    request_context: dict[str, Any],
    research_context: dict[str, Any] | None,
) -> tuple[str, list[str]]:
    request_payload = dict(request_context)
    dropped: list[str] = []

    def render() -> str:
        prompt = (
            "You are Dexter connected to the MOSS business analytics system. "
            "Answer the user's question directly and summarize any evidence or limitations. "
            "When research context is available, use only the landed MOSS Choice/TuShare data shown there. "
            "Do not provide trading instructions, buy/sell ratings, target prices, or formal financial metric conclusions. "
            "Return a concise research response with summary, findings, evidence, risks, limitations, and next_drill.\n\n"
            f"User question:\n{question}\n\n"
            "MOSS request context:\n"
            + json.dumps(request_payload, ensure_ascii=False, default=str, sort_keys=True)
        )
        if research_context is not None:
            prompt += "\n\nMOSS research context:\n" + json.dumps(
                research_context,
                ensure_ascii=False,
                default=str,
                indent=2,
            )
        if dropped:
            prompt += "\n\n[context truncated: dropped keys " + ", ".join(dropped) + "]"
        return prompt

    prompt = render()
    for key in _DEXTER_REQUEST_CONTEXT_DROP_ORDER:
        if len(prompt) <= _DEXTER_PROMPT_MAX_CHARS:
            return prompt, dropped
        if key in request_payload:
            request_payload.pop(key, None)
            dropped.append(key)
            prompt = render()
    if research_context is not None:
        for section, key in _DEXTER_RESEARCH_CONTEXT_DROP_ORDER:
            if len(prompt) <= _DEXTER_PROMPT_MAX_CHARS:
                return prompt, dropped
            section_payload = research_context.get(section)
            if isinstance(section_payload, dict) and key in section_payload:
                section_payload.pop(key, None)
                dropped.append(f"{section}.{key}")
                prompt = render()
    if len(prompt) > _DEXTER_PROMPT_MAX_CHARS:
        raise RuntimeError("Dexter prompt remains over the CLI argv budget after context key drops.")
    return prompt, dropped


def _extract_prompt_context_dropped_keys(prompt: str) -> list[str]:
    marker = "[context truncated: dropped keys "
    text = str(prompt or "")
    start = text.rfind(marker)
    if start < 0:
        return []
    start += len(marker)
    end = text.find("]", start)
    if end < 0:
        return []
    return [part.strip() for part in text[start:end].split(",") if part.strip()]


def _append_dexter_audit(
    request: AgentQueryRequest,
    governance_dir: str,
    envelope: AgentEnvelope,
    result: dict[str, Any],
) -> None:
    global _DEXTER_AUDIT_FAILURE_COUNT

    try:
        repo = GovernanceRepository(base_dir=governance_dir)
        append_agent_audit(
            repo,
            AgentAuditPayload(
                user_id=str(request.context.get("user_id") or "unknown"),
                query_text=request.question,
                tools_used=[str(result.get("tool_name") or "dexter_cli")],
                tables_used=envelope.evidence.tables_used,
                filters_applied=envelope.evidence.filters_applied,
                trace_id=envelope.result_meta.trace_id,
                run_id=str(request.context.get("run_id") or "").strip() or None,
                result_meta={
                    **envelope.result_meta.model_dump(mode="json"),
                    "dexter_tool_name": str(result.get("tool_name") or "dexter_cli"),
                    **(
                        {
                            "dexter_error": str(result.get("error")),
                            "dexter_error_code": str(
                                result.get("error_code") or _DEXTER_FALLBACK_REASON
                            ),
                        }
                        if result.get("error")
                        else {}
                    ),
                },
            ),
        )
    except Exception as exc:  # noqa: BLE001 - 审计写失败必须阻断 provider 应答返回
        _DEXTER_AUDIT_FAILURE_COUNT += 1
        _LOGGER.error(
            "Dexter audit append failed error_type=%s error_code=dexter_audit_append_failed "
            "failure_count=%s run_id=%s trace_id=%s",
            exc.__class__.__name__,
            _DEXTER_AUDIT_FAILURE_COUNT,
            str(request.context.get("run_id") or "").strip() or "-",
            envelope.result_meta.trace_id,
        )
        raise RuntimeError(
            "Dexter provider audit append failed; refusing to return an unaudited response."
        ) from exc


def _append_dexter_prompt(
    request: AgentQueryRequest,
    governance_dir: str,
    envelope: AgentEnvelope,
    result: dict[str, Any],
    prompt: str,
) -> None:
    """落盘本轮送模 prompt。

    空 prompt 表示研究上下文构建阶段就失败了，本轮没有任何内容送到模型，
    此时不写记录：本流的语义是"模型看到过什么"，不是"我们打算发什么"。
    """
    if not prompt:
        return
    try:
        repo = GovernanceRepository(base_dir=governance_dir)
        append_agent_prompt(
            repo,
            AgentPromptPayload(
                provider="dexter",
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
            "Dexter prompt append failed error_type=%s error_code=dexter_prompt_append_failed",
            exc.__class__.__name__,
        )


def _parse_dexter_output(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"answer": text}
    return payload if isinstance(payload, dict) else {"answer": text}


def _structured_research_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in ("summary", "findings", "evidence", "risks", "limitations", "next_drill")
        if key in payload
    }


def _build_dexter_cards(
    *,
    result: dict[str, Any],
    research_context: dict[str, Any] | None,
) -> list[AgentCard]:
    cards = [
        AgentCard(type="text", title="Dexter Agent", value=str(result.get("answer") or "")),
        AgentCard(type="metric", title="Provider", value="dexter"),
        AgentCard(type="metric", title="Model", value=str(result.get("model") or "default")),
        AgentCard(type="metric", title="Tool", value=str(result.get("tool_name") or "dexter_cli")),
    ]
    if not research_context or not research_context.get("domain"):
        return cards

    summary = str(result.get("summary") or result.get("answer") or "").strip()
    if summary:
        cards.append(AgentCard(type="research_summary", title="Research Summary", value=summary))
    _append_list_card(cards, title="Research Findings", card_type="research_findings", value=result.get("findings"))
    _append_list_card(cards, title="Research Evidence", card_type="research_evidence", value=result.get("evidence"))
    _append_list_card(cards, title="Research Risks", card_type="research_risks", value=result.get("risks"))
    limitations = [
        *_normalize_string_list(result.get("limitations") or research_context.get("limitations")),
        *_normalize_string_list(research_context.get("stale_sources")),
    ]
    _append_list_card(cards, title="Research Limitations", card_type="research_limitations", value=limitations)
    _append_list_card(cards, title="Next Drill", card_type="research_next_drill", value=result.get("next_drill"))
    return cards


def _append_list_card(
    cards: list[AgentCard],
    *,
    title: str,
    card_type: str,
    value: Any,
) -> None:
    items = _normalize_string_list(value)
    if not items:
        return
    cards.append(
        AgentCard(
            type=card_type,
            title=title,
            data=[{"item": item} for item in items],
            spec={"columns": ["item"]},
        )
    )


def _build_next_drill(value: Any) -> list[Any]:
    return [{"dimension": "research", "label": item} for item in _normalize_string_list(value)]


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_toolsets(toolsets: str) -> str:
    return normalize_read_only_toolsets(toolsets)


def _normalize_tables_used(value: Any, *, fallback: str) -> list[str]:
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if normalized:
            return normalized
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return [fallback]


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
