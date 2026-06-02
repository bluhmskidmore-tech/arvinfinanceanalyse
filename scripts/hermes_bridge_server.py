from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class HermesBridge:
    def __init__(self, *, model: str, toolsets: str, max_turns: int, hermes_root: str) -> None:
        root = Path(hermes_root)
        sys.path.insert(0, str(root))
        os.chdir(Path(__file__).resolve().parents[1])

        from cli import HermesCLI

        toolset_list = [part.strip() for part in toolsets.split(",") if part.strip()] or None
        self._cli = HermesCLI(
            model=model or "",
            toolsets=toolset_list,
            max_turns=max(max_turns, 1),
            verbose=False,
            compact=True,
        )
        self._model = model or "default"
        self._toolsets = ",".join(toolset_list or []) or "default"
        self._lock = threading.Lock()

    def query(self, prompt: str, *, model: str, toolsets: str, max_turns: int) -> dict[str, Any]:
        with self._lock:
            started = time.monotonic()
            cli = self._cli
            if max_turns:
                cli.max_turns = max(max_turns, 1)
            effective_model = model or cli.model or ""
            effective_toolsets = [part.strip() for part in toolsets.split(",") if part.strip()]
            if effective_toolsets:
                cli.enabled_toolsets = effective_toolsets

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                if not cli._ensure_runtime_credentials():
                    raise RuntimeError("Hermes credentials are not available.")
                route = cli._resolve_turn_agent_config(prompt)
                if effective_model:
                    route["model"] = effective_model
                if route["signature"] != cli._active_agent_route_signature:
                    cli.agent = None
                if not cli._init_agent(
                    model_override=route["model"],
                    runtime_override=route["runtime"],
                    route_label=route["label"],
                    request_overrides=route.get("request_overrides"),
                ):
                    raise RuntimeError("Hermes agent initialization failed.")
                cli.agent.quiet_mode = True
                cli.agent.suppress_status_output = True
                cli.agent.stream_delta_callback = None
                cli.agent.tool_gen_callback = None
                result = cli.agent.run_conversation(
                    user_message=prompt,
                    conversation_history=[],
                    task_id=cli.session_id,
                )

            answer = result.get("final_response", "") if isinstance(result, dict) else str(result)
            return {
                "ok": True,
                "answer": answer,
                "model": route.get("model") or self._model,
                "toolsets": ",".join(cli.enabled_toolsets or []) or self._toolsets,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }


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
