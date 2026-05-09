from __future__ import annotations

import os
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

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

RULE_VERSION = "rv_agent_hermes_v1"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_HERMES_BRIDGE_PROCESS: subprocess.Popen | None = None
_HERMES_BRIDGE_LOCK = threading.Lock()


def execute_hermes_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
    settings: Any,
) -> AgentEnvelope:
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
    _append_hermes_audit(request, governance_dir, envelope, result)
    return envelope


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
            "toolsets": str(getattr(settings, "agent_hermes_toolsets", "") or ""),
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
    if str(transport or "").strip().lower() == "bridge":
        normalized_bridge_url = str(bridge_url or "").strip() or "http://127.0.0.1:7891"
        _ensure_hermes_bridge(
            command=command,
            wsl_distro=wsl_distro,
            hermes_home=hermes_home,
            bridge_url=normalized_bridge_url,
            model=model,
            toolsets=toolsets,
            max_turns=max_turns,
            timeout_seconds=timeout_seconds,
        )
        return _post_hermes_bridge_query(
            bridge_url=normalized_bridge_url,
            prompt=prompt,
            model=model,
            toolsets=toolsets,
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
    if completed.returncode != 0:
        detail = _truncate((stderr or stdout).strip(), 2000)
        raise RuntimeError(f"Hermes failed with exit code {completed.returncode}: {detail}")

    return {
        "answer": _extract_final_answer(stdout),
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
        "model": model or "default",
        "toolsets": _normalize_toolsets(toolsets) or "default",
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
    if _hermes_bridge_healthy(bridge_url):
        return

    with _HERMES_BRIDGE_LOCK:
        if _hermes_bridge_healthy(bridge_url):
            return

        global _HERMES_BRIDGE_PROCESS
        if _HERMES_BRIDGE_PROCESS is not None and _HERMES_BRIDGE_PROCESS.poll() is None:
            pass
        else:
            args = _build_hermes_bridge_command(
                command=command,
                wsl_distro=wsl_distro,
                hermes_home=hermes_home,
                bridge_url=bridge_url,
                model=model,
                toolsets=toolsets,
                max_turns=max_turns,
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
                env=_build_hermes_subprocess_env(hermes_home if not _is_wsl_command(command) else ""),
            )

        deadline = time.monotonic() + min(max(timeout_seconds, 1.0), 30.0)
        while time.monotonic() < deadline:
            if _hermes_bridge_healthy(bridge_url):
                return
            if _HERMES_BRIDGE_PROCESS is not None and _HERMES_BRIDGE_PROCESS.poll() is not None:
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
        "toolsets": str(payload.get("toolsets") or _normalize_toolsets(toolsets) or "default"),
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
    generated_at = datetime.now(timezone.utc)
    filters_applied = {
        key: value for key, value in request.filters.items() if value not in (None, "")
    }
    filters_applied["provider"] = "hermes"
    if result.get("model"):
        filters_applied["model"] = result["model"]
    if result.get("toolsets"):
        filters_applied["toolsets"] = result["toolsets"]
    if result.get("transport"):
        filters_applied["transport"] = result["transport"]

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
        scenario_flag=request.basis == Basis.SCENARIO.value,
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
    normalized_toolsets = _normalize_toolsets(toolsets)
    if normalized_toolsets:
        hermes_args.extend(["--toolsets", normalized_toolsets])

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
    normalized_toolsets = _normalize_toolsets(toolsets)
    if normalized_toolsets:
        bridge_args.extend(["--toolsets", normalized_toolsets])

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
    return ",".join(part.strip() for part in str(toolsets or "").split(",") if part.strip())


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
