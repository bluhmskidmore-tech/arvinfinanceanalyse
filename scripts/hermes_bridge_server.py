from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from typing import Any

TOKEN_HEADER = "X-Hermes-Bridge-Token"

# 与 backend/app/agent/runtime/toolset_policy.py 保持一致。此处必须在服务端再判一次：
# 调用方的 normalize 只约束 MOSS 自己发出的请求，直连本端口的进程不受其约束。
READ_ONLY_TOOLSETS: tuple[str, ...] = ("evidence", "query", "research")

# 该进程持有全部数据源凭据的宿主环境，而 hermes 由用户提问驱动，故凭据一律不下传。
# 与 backend/app/agent/runtime/subprocess_env.py 保持一致。
_SECRET_NAME_MARKERS: tuple[str, ...] = (
    "PASSWORD",
    "PASSWD",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "APIKEY",
    "ACCESS_KEY",
    "ACCESSKEY",
    "CREDENTIAL",
    "PRIVATE_KEY",
    "CONNECTION_STRING",
    "DSN",
    "AUTH",
    "COOKIE",
    "SESSION",
    "PASSFILE",
)

# 后缀匹配避免 "_PAT" 连带剥离所有 "*_PATH" 变量。
_SECRET_NAME_SUFFIXES: tuple[str, ...] = ("_PAT",)

# 值形如 scheme://user:password@host 的内嵌凭据（DATABASE_URL、带认证的代理地址等）。
# 密码段允许含 "/"（如 pa/ss）；字符类排除 "@"，不会吞掉 @ 后的主机段。
_EMBEDDED_CREDENTIAL_VALUE_PATTERN = re.compile(r"://[^/\s@]*:[^\s@]+@")


def _is_sensitive_env_name(name: str) -> bool:
    upper = str(name or "").upper()
    if upper.startswith("MOSS_") or upper.endswith(_SECRET_NAME_SUFFIXES):
        return True
    return any(marker in upper for marker in _SECRET_NAME_MARKERS)


def _is_sensitive_env_value(value: str) -> bool:
    return _EMBEDDED_CREDENTIAL_VALUE_PATTERN.search(str(value or "")) is not None


def normalize_read_only_toolsets(toolsets: str) -> str:
    requested = [part.strip().lower() for part in str(toolsets or "").split(",") if part.strip()]
    selected = [item for item in requested if item in set(READ_ONLY_TOOLSETS)]
    if not selected:
        selected = list(READ_ONLY_TOOLSETS)
    return ",".join(dict.fromkeys(selected))


def _loopback_host(value: str) -> bool:
    host = str(value or "").strip()
    if not host:
        return False
    if host.startswith("["):
        host = host[1 : host.find("]")] if "]" in host else host[1:]
    elif host.count(":") == 1:
        host = host.split(":", 1)[0]
    if host == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def require_loopback_bind(host: str) -> None:
    if not _loopback_host(host):
        raise SystemExit("Hermes bridge server must bind to loopback only.")


class HermesBridge:
    def __init__(self, *, model: str, toolsets: str, max_turns: int, hermes_root: str) -> None:
        os.chdir(Path(__file__).resolve().parents[1])
        self._model = model or "default"
        self._toolsets = normalize_read_only_toolsets(toolsets)
        self._max_turns = max(max_turns, 1)
        self._hermes_home = os.environ.get("HERMES_HOME", "").strip() or "/home/hermes/.hermes"
        self._lock = threading.Lock()

    def _effective_toolsets(self, requested: str) -> str:
        """Never widen past the toolsets this bridge was started with.

        Falling back to the global read-only set would let a caller escape a
        deliberately narrow startup configuration by sending an unknown name.
        """
        allowed = {part for part in self._toolsets.split(",") if part}
        picked = [part.strip().lower() for part in str(requested or "").split(",") if part.strip()]
        selected = [part for part in picked if part in allowed]
        return ",".join(dict.fromkeys(selected)) or self._toolsets

    def query(
        self,
        prompt: str,
        *,
        model: str,
        toolsets: str,
        max_turns: int,
        timeout_seconds: float = 0.0,
    ) -> dict[str, Any]:
        with self._lock:
            started = time.monotonic()
            effective_model = model or self._model or ""
            effective_toolsets = self._effective_toolsets(toolsets)
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
            env = {
                key: value
                for key, value in os.environ.items()
                if not _is_sensitive_env_name(key) and not _is_sensitive_env_value(value)
            }
            env.setdefault("PYTHONIOENCODING", "utf-8")
            env.setdefault("PYTHONUTF8", "1")
            env.setdefault("NO_COLOR", "1")
            env["HERMES_HOME"] = self._hermes_home
            # 以 min(自身上限, 调用方预算-5s 余量) 执行：调用方 urlopen 的 socket
            # 超时先到就会放弃连接，bridge 必须赶在其之前结束子进程并返回结构化
            # 错误，否则单飞锁被占满自身上限、后续请求连环降级。
            own_cap = max(30.0, float(effective_max_turns) * 15.0)
            caller_budget = float(timeout_seconds or 0.0)
            if caller_budget > 0:
                effective_timeout = min(own_cap, max(caller_budget - 5.0, 1.0))
            else:
                effective_timeout = own_cap
            completed = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=effective_timeout,
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


# 与 backend/app/services/hermes_agent_service.py::_extract_final_answer 保持逐字相同
# （本脚本独立运行无法 import backend；一致性由源码对照测试守护）。
# 不做 `or stdout.strip()` 兜底：那会把已过滤的 banner 原样返回给用户。
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


def make_handler(bridge: HermesBridge, expected_token: str):
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

        def _transport_allowed(self) -> bool:
            try:
                client_is_loopback = ip_address(str(self.client_address[0])).is_loopback
            except ValueError:
                client_is_loopback = False
            if not client_is_loopback:
                self._send_json(403, {"ok": False, "error": "client must connect from loopback"})
                return False
            if not _loopback_host(str(self.headers.get("Host") or "")):
                self._send_json(403, {"ok": False, "error": "HTTP host must be loopback"})
                return False
            return True

        def _authorized(self) -> bool:
            supplied = str(self.headers.get(TOKEN_HEADER) or "")
            if not secrets.compare_digest(supplied, expected_token):
                self._send_json(403, {"ok": False, "error": "invalid bridge token"})
                return False
            return True

        def do_GET(self) -> None:
            if not self._transport_allowed():
                return
            if self.path.rstrip("/") == "/health":
                # ``authorized`` lets a client tell "reachable" from "reachable and will
                # accept my token", so a stale bridge is not mistaken for a usable one.
                supplied = str(self.headers.get(TOKEN_HEADER) or "")
                self._send_json(
                    200,
                    {"ok": True, "authorized": secrets.compare_digest(supplied, expected_token)},
                )
                return
            self._send_json(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            if not self._transport_allowed():
                return
            if self.path.rstrip("/") != "/query":
                self._send_json(404, {"ok": False, "error": "not found"})
                return
            if not self._authorized():
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
                    timeout_seconds=float(payload.get("timeout_seconds") or 0.0),
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
    parser.add_argument("--token", default="")
    args = parser.parse_args()

    require_loopback_bind(args.host)
    expected_token = str(args.token or os.environ.get("HERMES_BRIDGE_TOKEN") or "").strip()
    if not expected_token:
        raise SystemExit(
            "Hermes bridge token not configured; set HERMES_BRIDGE_TOKEN or pass --token."
        )

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("NO_COLOR", "1")

    bridge = HermesBridge(
        model=args.model,
        toolsets=args.toolsets,
        max_turns=args.max_turns,
        hermes_root=args.hermes_root,
    )
    server = ThreadingHTTPServer((args.host, args.port), make_handler(bridge, expected_token))
    server.serve_forever()


if __name__ == "__main__":
    main()
