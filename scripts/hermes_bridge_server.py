from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class HermesBridge:
    def __init__(self, *, model: str, toolsets: str, max_turns: int, hermes_root: str) -> None:
        os.chdir(Path(__file__).resolve().parents[1])
        self._model = model or "default"
        self._toolsets = ",".join(part.strip() for part in toolsets.split(",") if part.strip()) or "default"
        self._max_turns = max(max_turns, 1)
        self._hermes_home = os.environ.get("HERMES_HOME", "").strip() or "/home/hermes/.hermes"
        self._lock = threading.Lock()

    def query(self, prompt: str, *, model: str, toolsets: str, max_turns: int) -> dict[str, Any]:
        with self._lock:
            started = time.monotonic()
            effective_model = model or self._model or ""
            effective_toolsets = ",".join(part.strip() for part in toolsets.split(",") if part.strip()) or self._toolsets
            effective_max_turns = max(max_turns or self._max_turns, 1)
            args = [
                "/usr/local/bin/hermes",
                "chat",
                "-Q",
                "-q",
                prompt,
                "--max-turns",
                str(effective_max_turns),
                "--source",
                "tool",
            ]
            if effective_model and effective_model != "default":
                args.extend(["--model", effective_model])
            if effective_toolsets and effective_toolsets != "default":
                args.extend(["--toolsets", effective_toolsets])
            env = os.environ.copy()
            env.setdefault("PYTHONIOENCODING", "utf-8")
            env.setdefault("PYTHONUTF8", "1")
            env.setdefault("NO_COLOR", "1")
            env["HERMES_HOME"] = self._hermes_home
            completed = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(30, effective_max_turns * 15),
                env=env,
            )
            answer = _extract_final_answer(completed.stdout or "")
            stderr_text = (completed.stderr or "").strip()
            if completed.returncode != 0 and not (
                answer and (not stderr_text or stderr_text.startswith("session_id:"))
            ):
                detail = (completed.stderr or completed.stdout or "").strip()
                raise RuntimeError(detail or f"Hermes exited with code {completed.returncode}")
            return {
                "ok": True,
                "answer": answer,
                "model": effective_model or self._model,
                "toolsets": effective_toolsets or self._toolsets,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }


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
        if stripped.startswith("Resume this session with:"):
            break
        if stripped.startswith("Session:"):
            break
        if stripped.startswith("Duration:"):
            break
        if stripped.startswith("Messages:"):
            break
        content.append(line)
    answer = "\n".join(content).strip()
    return answer or stdout.strip()


def make_handler(bridge: HermesBridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path.rstrip("/") == "/health":
                self._send_json(200, {"ok": True})
                return
            self._send_json(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            if self.path.rstrip("/") != "/query":
                self._send_json(404, {"ok": False, "error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or "0")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                prompt = str(payload.get("prompt") or "").strip()
                if not prompt:
                    self._send_json(400, {"ok": False, "error": "prompt is required"})
                    return
                result = bridge.query(
                    prompt,
                    model=str(payload.get("model") or ""),
                    toolsets=str(payload.get("toolsets") or ""),
                    max_turns=int(payload.get("max_turns") or 1),
                )
                self._send_json(200, result)
            except Exception as exc:
                self._send_json(500, {"ok": False, "error": str(exc)})

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7891)
    parser.add_argument("--model", default="")
    parser.add_argument("--toolsets", default="")
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument("--hermes-root", default="/home/hermes/hermes-agent")
    args = parser.parse_args()

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("NO_COLOR", "1")

    bridge = HermesBridge(
        model=args.model,
        toolsets=args.toolsets,
        max_turns=args.max_turns,
        hermes_root=args.hermes_root,
    )
    server = ThreadingHTTPServer((args.host, args.port), make_handler(bridge))
    server.serve_forever()


if __name__ == "__main__":
    main()
