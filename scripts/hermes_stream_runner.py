#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import Any

READ_ONLY_TOOLSETS = frozenset({"evidence", "query", "research"})
_RUNTIME_PREPARED = False
_LOGGER = logging.getLogger(__name__)


class PreparedRequestRuntime:
    def __init__(self, *, cli: Any, finalize_single_query: Any, model: str, max_turns: int):
        self.cli = cli
        self.finalize_single_query = finalize_single_query
        self.model = model
        self.max_turns = max_turns


def _validate_request_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("request must be an object")
    request_id = str(payload.get("request_id") or "").strip()
    if len(request_id) > 128:
        raise ValueError("request_id is too long")
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    if len(prompt) > 16000:
        raise ValueError("prompt is too long")
    model = str(payload.get("model") or "").strip()
    if len(model) > 256:
        raise ValueError("model is too long")
    toolsets = str(payload.get("toolsets") or "").strip()
    if len(toolsets) > 256:
        raise ValueError("toolsets is too long")
    selected_toolsets = [part.strip().lower() for part in toolsets.split(",") if part.strip()]
    if not selected_toolsets:
        selected_toolsets = ["evidence", "query", "research"]
    if any(toolset not in READ_ONLY_TOOLSETS for toolset in selected_toolsets):
        raise ValueError("toolsets are not allowed")
    max_turns = max(int(payload.get("max_turns") or 1), 1)
    if max_turns > 100:
        raise ValueError("max_turns is too large")
    return {
        "request_id": request_id,
        "prompt": prompt,
        "model": model,
        "toolsets": selected_toolsets,
        "max_turns": max_turns,
    }


def _load_request() -> dict[str, Any]:
    raw = sys.stdin.buffer.read()
    payload = json.loads(raw.decode("utf-8"))
    return _validate_request_payload(payload)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-root", required=True)
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--instance-id", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--max-turns", type=int, default=1)
    return parser.parse_args()


def _build_emitter():
    protocol_stdout = sys.stdout
    emit_lock = threading.Lock()

    def emit(payload: dict[str, Any]) -> None:
        with emit_lock:
            protocol_stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            protocol_stdout.flush()

    return emit


def _emit_with_request_id(emit, request_id: str, payload: dict[str, Any]) -> None:
    materialized = dict(payload)
    if request_id:
        materialized["request_id"] = request_id
    emit(materialized)


def _report_cleanup_failure(operation: str, exc: Exception) -> None:
    _LOGGER.warning(
        "Hermes stream cleanup failed operation=%s "
        "error_type=%s error_code=hermes_stream_cleanup_failed",
        operation,
        exc.__class__.__name__,
    )


def _prepare_hermes_runtime(hermes_root: Path) -> None:
    global _RUNTIME_PREPARED
    if _RUNTIME_PREPARED:
        return
    with redirect_stdout(sys.stderr):
        from hermes_cli.main import _prepare_agent_startup

        os.chdir(hermes_root)
        _prepare_agent_startup(
            SimpleNamespace(
                command="chat",
                yolo=False,
                safe_mode=False,
                tui=False,
                accept_hooks=False,
            )
        )
    _RUNTIME_PREPARED = True


def _prepare_request_runtime(
    *,
    hermes_root: Path,
    model: str,
    max_turns: int,
    prompt: str = "MOSS Agent Lab runtime prewarm",
    persistent: bool = False,
) -> PreparedRequestRuntime:
    _prepare_hermes_runtime(hermes_root)
    with redirect_stdout(sys.stderr):
        from cli import HermesCLI

        if persistent:
            finalize_single_query = _finalize_persistent_query
        else:
            from cli import _finalize_single_query as finalize_single_query

        cli = HermesCLI(
            model=model or None,
            # Hermes uses None for its broad default and [] as an explicit empty
            # allowlist. MOSS toolset labels are governance labels, not Hermes
            # runtime toolset names, so Lab streaming intentionally exposes no
            # Hermes tools.
            toolsets=[],
            reasoning="low",
            max_turns=max_turns,
            compact=True,
        )
        cli._single_query_mode = True
        cli.tool_progress_mode = "off"
        if not cli._ensure_runtime_credentials():
            raise RuntimeError("runtime_unavailable")
        turn_route = cli._resolve_turn_agent_config(prompt)
        if not cli._init_agent(
            model_override=turn_route.get("model"),
            runtime_override=turn_route.get("runtime"),
            request_overrides=turn_route.get("request_overrides"),
        ):
            raise RuntimeError("runtime_unavailable")
        agent = cli.agent
        if agent is None:
            raise RuntimeError("runtime_unavailable")
        agent.quiet_mode = True
        agent.suppress_status_output = True
        agent.reasoning_callback = None
        agent.tool_gen_callback = None
    return PreparedRequestRuntime(
        cli=cli,
        finalize_single_query=finalize_single_query,
        model=model,
        max_turns=max_turns,
    )


def _finalize_persistent_query(cli: Any) -> None:
    """Release one agent slot without invoking Hermes' process-wide cleanup."""
    agent = getattr(cli, "agent", None)
    session_id = str(
        getattr(agent, "session_id", None) or getattr(cli, "session_id", None) or ""
    )
    try:
        from hermes_cli.lifecycle import finalize_session

        finalize_session(
            session_id=session_id or None,
            platform=getattr(agent, "platform", None) or "cli",
            reason="shutdown",
        )
    except Exception as exc:  # noqa: BLE001 - cleanup must not mask the request result
        _report_cleanup_failure("finalize_session", exc)
    if agent is not None:
        try:
            session_messages = getattr(agent, "_session_messages", None)
            if isinstance(session_messages, list):
                agent.shutdown_memory_provider(session_messages)
            else:
                agent.shutdown_memory_provider()
        except Exception as exc:  # noqa: BLE001 - cleanup must not mask the request result
            _report_cleanup_failure("shutdown_memory_provider", exc)
        try:
            agent.close()
        except Exception as exc:  # noqa: BLE001 - cleanup must not mask the request result
            _report_cleanup_failure("agent.close", exc)
    session_db = getattr(cli, "_session_db", None)
    if session_db is not None:
        try:
            session_db.close()
        except Exception as exc:  # noqa: BLE001 - cleanup must not mask the request result
            _report_cleanup_failure("session_db.close", exc)
    try:
        import cli as cli_module

        if getattr(cli_module, "_active_agent_ref", None) is agent:
            cli_module._active_agent_ref = None
    except Exception as exc:  # noqa: BLE001 - cleanup must not mask the request result
        _report_cleanup_failure("clear_active_agent_ref", exc)
    try:
        cli.agent = None
        cli._session_db = None
    except Exception as exc:  # noqa: BLE001 - cleanup must not mask the request result
        _report_cleanup_failure("clear_cli_runtime_refs", exc)
    try:
        cli._release_active_session()
    except Exception as exc:  # noqa: BLE001 - cleanup must not mask the request result
        _report_cleanup_failure("release_active_session", exc)


def _run_single_request(
    *,
    request: dict[str, Any],
    emit,
    hermes_root: Path,
    prepared_runtime: PreparedRequestRuntime | None = None,
) -> int:
    cli = None
    runtime = prepared_runtime
    finalized = False
    seq = 0
    request_id = str(request.get("request_id") or "").strip()

    def on_delta(text: str | None) -> None:
        nonlocal seq
        if not text:
            return
        seq += 1
        _emit_with_request_id(emit, request_id, {"type": "delta", "seq": seq, "text": text})

    def finalize_single_query():
        nonlocal finalized
        if finalized or cli is None or runtime is None:
            return
        finalized = True
        with redirect_stdout(sys.stderr):
            runtime.finalize_single_query(cli)

    try:
        if runtime is None:
            runtime = _prepare_request_runtime(
                hermes_root=hermes_root,
                model=request["model"],
                max_turns=request["max_turns"],
                prompt=request["prompt"],
            )
        if runtime.model != request["model"] or runtime.max_turns != request["max_turns"]:
            raise ValueError("request runtime does not match the prepared runtime")
        cli = runtime.cli
        with redirect_stdout(sys.stderr):
            if not cli._claim_active_session("cli", stderr=True):
                _emit_with_request_id(emit, request_id, {"type": "error", "code": "session_unavailable"})
                return 1
            agent = cli.agent
            if agent is None:
                _emit_with_request_id(emit, request_id, {"type": "error", "code": "runtime_unavailable"})
                finalize_single_query()
                return 1
            agent.stream_delta_callback = on_delta
            result = agent.run_conversation(
                user_message=request["prompt"],
                conversation_history=[],
            )
            if getattr(agent, "session_id", None):
                cli.session_id = str(agent.session_id)
            final_answer = str(result.get("final_response") or "")
            session_id = str(getattr(cli, "session_id", "") or "")
            _emit_with_request_id(
                emit,
                request_id,
                {"type": "final", "answer": final_answer, "session_id": session_id},
            )
            return 0
    except KeyboardInterrupt:
        _emit_with_request_id(emit, request_id, {"type": "error", "code": "interrupted"})
        return 130
    except Exception:
        _emit_with_request_id(emit, request_id, {"type": "error", "code": "runtime_failed"})
        return 1
    finally:
        try:
            finalize_single_query()
        except Exception as exc:  # noqa: BLE001 - cleanup must not mask the request result
            _report_cleanup_failure("finalize_single_query", exc)


def main() -> int:
    emit = _build_emitter()
    args = _parse_args()
    hermes_root = Path(args.hermes_root)
    if str(hermes_root) not in sys.path:
        sys.path.insert(0, str(hermes_root))

    if not getattr(args, "daemon", False):
        try:
            request = _load_request()
        except Exception:
            emit({"type": "error", "code": "invalid_request"})
            return 1
        return _run_single_request(request=request, emit=emit, hermes_root=hermes_root)

    try:
        daemon_model = str(getattr(args, "model", "") or "").strip()
        daemon_max_turns = max(int(getattr(args, "max_turns", 1) or 1), 1)
        if len(daemon_model) > 256 or daemon_max_turns > 100:
            raise ValueError("invalid daemon runtime configuration")
        prepared_runtime = _prepare_request_runtime(
            hermes_root=hermes_root,
            model=daemon_model,
            max_turns=daemon_max_turns,
            persistent=True,
        )
    except Exception:
        emit({"type": "error", "request_id": "", "code": "runtime_unavailable"})
        return 1
    emit(
        {
            "type": "ready",
            "instance_id": str(getattr(args, "instance_id", "") or ""),
        }
    )

    while True:
        raw_line = sys.stdin.readline()
        if raw_line == "":
            return 0
        try:
            request = _validate_request_payload(json.loads(raw_line))
        except Exception:
            emit({"type": "error", "request_id": "", "code": "invalid_request"})
            continue
        if (
            request["model"] != daemon_model
            or request["max_turns"] != daemon_max_turns
        ):
            _emit_with_request_id(
                emit,
                request["request_id"],
                {"type": "error", "code": "runtime_mismatch"},
            )
            return 1
        result_code = _run_single_request(
            request=request,
            emit=emit,
            hermes_root=hermes_root,
            prepared_runtime=prepared_runtime,
        )
        if result_code != 0:
            return result_code
        try:
            prepared_runtime = _prepare_request_runtime(
                hermes_root=hermes_root,
                model=daemon_model,
                max_turns=daemon_max_turns,
                persistent=True,
            )
        except Exception:
            emit({"type": "error", "request_id": "", "code": "runtime_unavailable"})
            return 1
        emit(
            {
                "type": "ready",
                "instance_id": str(getattr(args, "instance_id", "") or ""),
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
