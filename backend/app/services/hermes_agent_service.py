from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

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
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services.agent_error_sanitization import scrub_agent_runtime_error

RULE_VERSION = "rv_agent_hermes_v1"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HERMES_BRIDGE_LOCK = threading.Lock()
_HERMES_FALLBACK_REASON = "hermes_runtime_unavailable"
_HERMES_FALLBACK_MESSAGE = "Hermes runtime unavailable; local fallback used."
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HermesBridgeConfig:
    command: str
    wsl_distro: str
    hermes_home: str
    bridge_url: str
    model: str
    toolsets: str
    max_turns: int


_HERMES_BRIDGE_PROCESS: subprocess.Popen | None = None
_HERMES_BRIDGE_CONFIG: HermesBridgeConfig | None = None
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
    "how do i use",
    "help me think",
    "chat",
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


def execute_hermes_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
    settings: Any,
) -> AgentEnvelope:
    if _should_answer_open_chat_locally(request.question):
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

    try:
        result = run_hermes_agent(
            request=request,
            command=str(settings.agent_hermes_command),
            wsl_distro=str(settings.agent_hermes_wsl_distro or ""),
            hermes_home=str(getattr(settings, "agent_hermes_home", "") or ""),
            transport=str(getattr(settings, "agent_hermes_transport", "cli") or "cli"),
            bridge_url=str(getattr(settings, "agent_hermes_bridge_url", "") or ""),
            model=str(settings.agent_hermes_model or ""),
            toolsets=str(getattr(settings, "agent_hermes_toolsets", "") or ""),
            max_turns=int(settings.agent_hermes_max_turns),
            timeout_seconds=float(settings.agent_hermes_timeout_seconds),
        )
        envelope = build_hermes_envelope(request=request, result=result)
    except RuntimeError as exc:
        _LOGGER.warning(
            "Hermes provider runtime failed error_type=%s detail=%s",
            exc.__class__.__name__,
            scrub_agent_runtime_error(exc),
        )
        result = {
            "answer": "",
            "stdout": "",
            "stderr": "",
            "command": str(settings.agent_hermes_command),
            "model": str(settings.agent_hermes_model or ""),
            "toolsets": str(getattr(settings, "agent_hermes_toolsets", "") or ""),
            "transport": str(getattr(settings, "agent_hermes_transport", "cli") or "cli"),
            "error": _HERMES_FALLBACK_MESSAGE,
            "error_code": _HERMES_FALLBACK_REASON,
        }
        envelope = build_hermes_fallback_envelope(request=request, result=result)
    _append_hermes_audit(request, governance_dir, envelope, result)
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
) -> dict[str, str]:
    prompt = _build_hermes_prompt(request)
    normalized_toolsets = _normalize_toolsets(toolsets)
    if str(transport or "").strip().lower() == "bridge":
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

    args = _build_hermes_command(
        command=command,
        wsl_distro=wsl_distro,
        hermes_home=hermes_home,
        model=model,
        toolsets=toolsets,
        max_turns=max_turns,
        prompt=prompt,
    )
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("NO_COLOR", "1")
    normalized_home = str(hermes_home or "").strip()
    if normalized_home and not _is_wsl_command(command):
        env["HERMES_HOME"] = normalized_home
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
        raise RuntimeError(f"Hermes failed with exit code {completed.returncode}: {detail}")
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
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout = (log_dir / "hermes-bridge.out.log").open("ab")
        stderr = (log_dir / "hermes-bridge.err.log").open("ab")
        _HERMES_BRIDGE_PROCESS = subprocess.Popen(
            args,
            cwd=str(_REPO_ROOT),
            stdout=stdout,
            stderr=stderr,
            env=_build_hermes_subprocess_env(
                desired.hermes_home if not _is_wsl_command(desired.command) else ""
            ),
        )
        _HERMES_BRIDGE_CONFIG = desired
        _wait_for_hermes_bridge_ready_locked(
            bridge_url=desired.bridge_url,
            timeout_seconds=timeout_seconds,
        )


def _stop_managed_hermes_bridge_locked() -> None:
    global _HERMES_BRIDGE_PROCESS, _HERMES_BRIDGE_CONFIG
    process = _HERMES_BRIDGE_PROCESS
    _HERMES_BRIDGE_PROCESS = None
    _HERMES_BRIDGE_CONFIG = None
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _wait_for_hermes_bridge_ready_locked(*, bridge_url: str, timeout_seconds: float) -> None:
    global _HERMES_BRIDGE_PROCESS, _HERMES_BRIDGE_CONFIG
    deadline = time.monotonic() + min(max(timeout_seconds, 1.0), 30.0)
    while time.monotonic() < deadline:
        if _hermes_bridge_healthy(bridge_url):
            return
        if _HERMES_BRIDGE_PROCESS is not None and _HERMES_BRIDGE_PROCESS.poll() is not None:
            _HERMES_BRIDGE_PROCESS = None
            _HERMES_BRIDGE_CONFIG = None
            raise RuntimeError("Hermes bridge exited before it became ready.")
        time.sleep(0.25)
    raise RuntimeError(f"Hermes bridge did not become ready at {bridge_url}")


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
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Hermes bridge failed: {_truncate(detail, 2000)}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Hermes bridge unavailable: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Hermes bridge returned an invalid payload.")
    if not payload.get("ok", False):
        raise RuntimeError(str(payload.get("error") or "Hermes bridge query failed."))

    answer = str(payload.get("answer") or "")
    return {
        "answer": answer,
        "stdout": answer,
        "stderr": "",
        "command": "hermes_bridge",
        "model": str(payload.get("model") or model or "default"),
        "toolsets": _normalize_toolsets(str(payload.get("toolsets") or toolsets)),
        "transport": "bridge",
    }


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
    if result.get("model"):
        filters_applied["model"] = result["model"]
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
    hermes_args.extend(["--toolsets", _normalize_toolsets(toolsets)])

    if _is_wsl_command(command):
        args = [command]
        if wsl_distro:
            args.extend(["-d", wsl_distro])
        args.extend(["-e"])
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

    python_path = "/home/hermes/hermes-agent/venv/bin/python"
    if _is_wsl_command(command):
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


def _is_wsl_command(command: str) -> bool:
    normalized = str(command or "").strip().lower()
    return normalized.endswith("wsl.exe") or normalized == "wsl"


def _normalize_toolsets(toolsets: str) -> str:
    return normalize_read_only_toolsets(toolsets)


def _build_hermes_subprocess_env(hermes_home: str) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("NO_COLOR", "1")
    normalized_home = str(hermes_home or "").strip()
    if normalized_home:
        env["HERMES_HOME"] = normalized_home
    return env


def _windows_path_to_wsl_path(path: Path) -> str:
    raw = str(path.resolve())
    if len(raw) >= 3 and raw[1:3] == ":\\":
        drive = raw[0].lower()
        rest = raw[3:].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    return raw.replace("\\", "/")


def _build_hermes_prompt(request: AgentQueryRequest) -> str:
    context = {
        "basis": request.basis,
        "filters": request.filters,
        "position_scope": request.position_scope,
        "currency_basis": request.currency_basis,
        "context": request.context,
        "page_context": request.page_context.model_dump(mode="json") if request.page_context else None,
    }
    prompt = (
        "You are Hermes Agent connected to the MOSS business analytics system. "
        "Answer the user's question directly. If you use tools or evidence, summarize the evidence and limitations. "
        "Do not claim formal financial correctness unless the provided evidence proves it.\n\n"
        f"User question:\n{request.question}\n\n"
        f"MOSS request context:\n{context}"
    )
    ontology_block = _build_ontology_context_block(request.question)
    if ontology_block:
        prompt += (
            "\n\nMOSS ontology context (authoritative semantic anchors; definitions only, no values):\n"
            f"{ontology_block}\n"
            "When you rely on these anchors, cite the entity id and authority reference in your answer."
        )
    return prompt


def _build_ontology_context_block(question: str) -> str:
    try:
        from backend.app.ontology.loader import load_ontology_index
        from backend.app.services.knowledge_index_service import (
            knowledge_summaries_for_entities,
            knowledge_vault_available,
        )

        entities = load_ontology_index().resolve_from_text(question)
        if not entities:
            return ""
        if not knowledge_vault_available():
            return ""
    except Exception:
        return ""

    entities = entities[:_ONTOLOGY_CONTEXT_MAX_ENTITIES]
    try:
        summaries = knowledge_summaries_for_entities([entity.entity_id for entity in entities])
    except Exception:
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
        lines.append(
            f"- {entity.entity_id} | {entity.name} | unit={entity.unit or '-'} | "
            f"basis={entity.basis or '-'} | time={entity.time_semantics or '-'} | "
            f"status={entity.status} | authority={authority}"
        )
        lines.extend(f"- note: {summary}" for summary in summaries_by_entity_id[entity.entity_id])
    return _join_ontology_context_lines(lines)


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
    compact = normalized.replace(" ", "")
    if compact in _LOCAL_OPEN_CHAT_EXACT:
        return True
    if any(hint in normalized or hint in compact for hint in _BUSINESS_QUERY_HINTS):
        return False
    return len(compact) <= 32 and any(
        pattern in normalized or pattern in compact for pattern in _LOCAL_OPEN_CHAT_PATTERNS
    )


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
                "在。Hermes 托管通道刚才不可用，我已切到本地稳定兜底；"
                "你可以继续问组合概览、损益、久期、信用风险，也可以继续普通对话。"
            )
        return (
            f"我收到了：{normalized}。Hermes 托管通道刚才不可用，所以这轮先用本地稳定兜底接住，"
            "不会返回 503 或红框。涉及正式业务数字时，请直接问组合概览、损益、久期或信用风险。"
        )
    if lower in {"hi", "hello", "hey", "ping", "are you there?"}:
        return (
            "I am here. The Hermes managed channel is unavailable, so I switched to the local stable fallback. "
            "You can keep chatting or ask for governed MOSS paths such as portfolio overview, PnL, duration, or credit risk."
        )
    return (
        f"I received: {normalized}. The Hermes managed channel is unavailable, so this turn is handled by the local "
        "stable fallback instead of returning an error. For formal numbers, ask for a governed MOSS path."
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
        if stripped.startswith("Warning: Unknown toolsets:"):
            continue
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
            run_id=str(request.context.get("run_id") or "").strip() or None,
            result_meta={
                **envelope.result_meta.model_dump(mode="json"),
                "stdout_excerpt": scrub_agent_runtime_error(
                    result.get("stdout", ""),
                    limit=1000,
                ),
                "stderr_excerpt": scrub_agent_runtime_error(
                    result.get("stderr", ""),
                    limit=1000,
                ),
            },
        ),
    )


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
