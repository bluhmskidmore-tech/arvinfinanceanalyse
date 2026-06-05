from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any


class GitNexusMcpClient:
    def __init__(self, repo_path: Path, timeout_seconds: float = 10.0) -> None:
        self._repo_path = Path(repo_path)
        self._timeout_seconds = timeout_seconds
        self._command = _resolve_gitnexus_command(self._repo_path)

    def read_bundle(self, process_name: str | None = None) -> dict[str, Any]:
        with _GitNexusMcpSession(self._command, timeout_seconds=self._timeout_seconds) as session:
            repos_text = session.read_resource("gitnexus://repos")
            repo_entry = _find_repo_entry(repos_text, self._repo_path)
            if repo_entry is None:
                raise ValueError(f"Repo {self._repo_path} is not registered in GitNexus MCP.")

            repo_name = str(repo_entry.get("name") or self._repo_path.name)
            context = _parse_context_resource(
                session.read_resource(f"gitnexus://repo/{repo_name}/context")
            )
            processes = _parse_processes_resource(
                session.read_resource(f"gitnexus://repo/{repo_name}/processes")
            )
            process = None
            if process_name:
                process = _parse_process_resource(
                    session.read_resource(f"gitnexus://repo/{repo_name}/process/{process_name}")
                )
            return {
                "repo_name": repo_name,
                "context": context,
                "processes": processes,
                "process": process,
            }


class _GitNexusMcpSession:
    def __init__(self, command: list[str], timeout_seconds: float) -> None:
        self._command = command
        self._timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[bytes] | None = None
        self._next_id = 1

    def __enter__(self) -> "_GitNexusMcpSession":
        self._process = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._process.kill()

    def read_resource(self, uri: str) -> str:
        response = self._request("resources/read", {"uri": uri})
        contents = (
            response.get("result", {}).get("contents", [])
            if isinstance(response.get("result"), dict)
            else []
        )
        if not contents:
            raise ValueError(f"GitNexus MCP returned no contents for {uri}.")
        payload = contents[0]
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str):
            raise ValueError(f"GitNexus MCP returned a non-text resource for {uri}.")
        return text

    def _initialize(self) -> None:
        response = self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "moss-agent", "version": "0.1"},
            },
        )
        if "result" not in response:
            raise RuntimeError("GitNexus MCP initialize failed.")
        self._notify("notifications/initialized", {})

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        response = self._read_message()
        if response.get("id") != request_id:
            raise RuntimeError(f"Unexpected GitNexus MCP response id for {method}.")
        return response

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _send(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("GitNexus MCP process is not available.")
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self._process.stdin.write(header + body)
        self._process.stdin.flush()

    def _read_message(self) -> dict[str, Any]:
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("GitNexus MCP stdout is not available.")
        deadline = time.time() + self._timeout_seconds
        buffer = b""
        while time.time() < deadline:
            chunk = self._process.stdout.peek(32768)
            if chunk:
                buffer += self._process.stdout.read(len(chunk))
                if b"\r\n\r\n" in buffer:
                    header, _, rest = buffer.partition(b"\r\n\r\n")
                    length = _parse_content_length(header)
                    while len(rest) < length and time.time() < deadline:
                        time.sleep(0.05)
                        chunk = self._process.stdout.peek(32768)
                        if chunk:
                            rest += self._process.stdout.read(len(chunk))
                    if len(rest) < length:
                        raise TimeoutError("Timed out while reading GitNexus MCP response body.")
                    return json.loads(rest[:length].decode("utf-8"))
            time.sleep(0.05)
        raise TimeoutError("Timed out while waiting for GitNexus MCP response.")


def _resolve_gitnexus_command(repo_path: Path) -> list[str]:
    mcp_path = repo_path / ".mcp.json"
    if mcp_path.is_file():
        payload = json.loads(mcp_path.read_text(encoding="utf-8"))
        gitnexus_config = (
            payload.get("mcpServers", {}).get("gitnexus", {})
            if isinstance(payload, dict)
            else {}
        )
        command = gitnexus_config.get("command")
        args = gitnexus_config.get("args")
        if isinstance(command, str) and isinstance(args, list):
            return [command, *[str(arg) for arg in args]]
    return ["npx", "-y", "gitnexus@latest", "mcp"]


def _parse_content_length(header: bytes) -> int:
    for line in header.decode("ascii", errors="ignore").split("\r\n"):
        if line.lower().startswith("content-length:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError("GitNexus MCP response is missing Content-Length header.")


def _find_repo_entry(repos_text: str, repo_path: Path) -> dict[str, Any] | None:
    normalized_repo_path = str(repo_path).casefold()
    for entry in _parse_named_entries(repos_text, root_key="repos"):
        if str(entry.get("path") or "").casefold() == normalized_repo_path:
            return entry
        if str(entry.get("name") or "").casefold() == repo_path.name.casefold():
            return entry
    return None


def _parse_context_resource(text: str) -> dict[str, Any]:
    project = ""
    stats: dict[str, int] = {}
    tools: list[dict[str, str]] = []
    resources: list[dict[str, str]] = []
    section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("project:"):
            project = _clean_value(line.split(":", 1)[1].strip())
            section = None
            continue
        if stripped.endswith(":") and stripped[:-1] in {"stats", "tools_available", "resources_available"}:
            section = stripped[:-1]
            continue
        if section == "stats" and line.startswith("  "):
            key, value = [part.strip() for part in stripped.split(":", 1)]
            try:
                stats[key] = int(_clean_value(value))
            except ValueError:
                continue
        elif section == "tools_available" and stripped.startswith("- "):
            key, value = [part.strip() for part in stripped[2:].split(":", 1)]
            tools.append({"tool": key, "description": _clean_value(value)})
        elif section == "resources_available" and stripped.startswith("- "):
            key, value = [part.strip() for part in stripped[2:].split(":", 1)]
            resources.append({"uri": key, "description": _clean_value(value)})
    return {"project": project, "stats": stats, "tools": tools, "resources": resources}


def _parse_processes_resource(text: str) -> list[dict[str, Any]]:
    return _parse_named_entries(text, root_key="processes")


def _parse_process_resource(text: str) -> dict[str, Any] | None:
    if text.startswith("error:"):
        return {"error": text.strip()}
    process: dict[str, Any] = {"trace": []}
    section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("trace:"):
            section = "trace"
            continue
        if section == "trace" and line.startswith("  "):
            if ":" not in stripped:
                continue
            step_text, remainder = stripped.split(":", 1)
            symbol_part = remainder.strip()
            if " (" in symbol_part and symbol_part.endswith(")"):
                symbol, file_path = symbol_part.rsplit(" (", 1)
                process["trace"].append(
                    {
                        "step": int(step_text),
                        "symbol": symbol.strip(),
                        "file": file_path[:-1],
                    }
                )
            continue
        if ":" in stripped:
            key, value = [part.strip() for part in stripped.split(":", 1)]
            cleaned = _clean_value(value)
            if key == "step_count":
                process[key] = int(cleaned)
            else:
                process[key] = cleaned
    return process


def _parse_named_entries(text: str, *, root_key: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_section = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            break
        if stripped == f"{root_key}:":
            in_section = True
            continue
        if not in_section:
            continue
        if stripped.startswith("- "):
            if current:
                entries.append(current)
            current = {}
            remainder = stripped[2:]
            if ":" in remainder:
                key, value = [part.strip() for part in remainder.split(":", 1)]
                current[key] = _coerce_value(_clean_value(value))
            continue
        if current is not None and ":" in stripped:
            key, value = [part.strip() for part in stripped.split(":", 1)]
            current[key] = _coerce_value(_clean_value(value))
    if current:
        entries.append(current)
    return entries


def _clean_value(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith('"') and cleaned.endswith('"'):
        return cleaned[1:-1]
    return cleaned


def _coerce_value(value: str) -> Any:
    if value.isdigit():
        return int(value)
    return value
