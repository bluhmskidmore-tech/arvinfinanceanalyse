from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_SCRIPT = REPO_ROOT / "scripts" / "mcp" / "moss_project_mcp.py"


class McpProcess:
    def __init__(self, mode: str, env: dict[str, str] | None = None) -> None:
        process_env = os.environ.copy()
        process_env.update(env or {})
        self.process = subprocess.Popen(
            [sys.executable, str(MCP_SCRIPT), mode],
            cwd=REPO_ROOT,
            env=process_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._next_id = 1

    def close(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        response = self._read()
        assert response["id"] == request_id
        assert "error" not in response, response.get("error")
        return dict(response["result"])

    def request_error(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        response = self._read()
        assert response["id"] == request_id
        assert "error" in response, response
        return dict(response["error"])

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _send(self, payload: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        body = json.dumps(payload).encode("utf-8")
        self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        self.process.stdin.flush()

    def _read(self) -> dict[str, Any]:
        assert self.process.stdout is not None
        headers = []
        while True:
            line = self.process.stdout.readline()
            assert line, self._stderr()
            if line in (b"\r\n", b"\n"):
                break
            headers.append(line.decode("ascii").strip())
        length = None
        for header in headers:
            if header.lower().startswith("content-length:"):
                length = int(header.split(":", 1)[1].strip())
        assert length is not None
        return json.loads(self.process.stdout.read(length).decode("utf-8"))

    def _stderr(self) -> str:
        if self.process.stderr is None:
            return ""
        return self.process.stderr.read().decode("utf-8", errors="replace")


def test_data_quality_mcp_exposes_summary_and_tools() -> None:
    server = McpProcess("data-quality")
    try:
        init = server.request("initialize")
        server.notify("notifications/initialized")
        assert init["serverInfo"]["name"] == "moss-data-quality"

        resources = server.request("resources/list")["resources"]
        assert any(item["uri"] == "moss://data-quality/summary" for item in resources)

        tools = server.request("tools/list")["tools"]
        assert {tool["name"] for tool in tools} >= {"get_quality_summary", "list_quality_targets"}
    finally:
        server.close()


def test_data_quality_mcp_is_safe_when_duckdb_is_missing(tmp_path: Path) -> None:
    missing_duckdb = tmp_path / "missing.duckdb"
    server = McpProcess("data-quality", env={"MOSS_DUCKDB_PATH": str(missing_duckdb)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        summary = server.request("resources/read", {"uri": "moss://data-quality/summary"})
        payload = json.loads(summary["contents"][0]["text"])
        assert payload["duckdb_exists"] is False
        assert payload["targets"] == []
    finally:
        server.close()


def test_data_quality_mcp_rejects_invalid_and_unknown_table_names(tmp_path: Path) -> None:
    db_path = _build_quality_duckdb(tmp_path)
    server = McpProcess("data-quality", env={"MOSS_DUCKDB_PATH": str(db_path)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        invalid = server.request_error(
            "tools/call",
            {"name": "get_quality_summary", "arguments": {"table_name": "main.positions;drop table x"}},
        )
        assert invalid["code"] == -32602
        assert "table_name must be an identifier" in invalid["message"]

        unknown = server.request_error(
            "tools/call",
            {"name": "get_quality_summary", "arguments": {"table_name": "main.unknown_table"}},
        )
        assert unknown["code"] == -32602
        assert "Unknown table" in unknown["message"]
    finally:
        server.close()


def test_data_quality_mcp_reports_quality_summary_for_known_view(tmp_path: Path) -> None:
    db_path = _build_quality_duckdb(tmp_path)
    server = McpProcess("data-quality", env={"MOSS_DUCKDB_PATH": str(db_path)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        targets = server.request("tools/call", {"name": "list_quality_targets", "arguments": {"limit": 10}})
        targets_payload = json.loads(targets["content"][0]["text"])
        assert any(item["table_name"] == "main.positions_view" and item["type"] == "VIEW" for item in targets_payload["targets"])

        result = server.request(
            "tools/call",
            {"name": "get_quality_summary", "arguments": {"table_name": "main.positions_view"}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["table_name"] == "main.positions_view"
        assert payload["object_type"] == "VIEW"
        assert payload["row_count"] == 3
        assert payload["null_counts"]["amount"] == 1
        assert payload["null_counts"]["as_of_date"] == 1
        assert payload["date_coverage"]["report_date"]["min"] == "2026-05-01"
        assert payload["date_coverage"]["report_date"]["max"] == "2026-05-03"
        assert payload["date_coverage"]["report_date"]["null_count"] == 1
        assert payload["date_coverage"]["as_of_date"]["max"].startswith("2026-05-02")
        assert "golden_sample_matches" in payload
    finally:
        server.close()


def _build_quality_duckdb(tmp_path: Path) -> Path:
    duckdb = pytest.importorskip("duckdb")
    db_path = tmp_path / "quality.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table positions (
                id integer,
                report_date date,
                as_of_date timestamp,
                amount integer
            )
            """
        )
        conn.execute(
            """
            insert into positions values
                (1, '2026-05-01', '2026-05-01 09:00:00', 10),
                (2, null, '2026-05-02 10:00:00', null),
                (3, '2026-05-03', null, 30)
            """
        )
        conn.execute("create view positions_view as select report_date, as_of_date, amount from positions")
    finally:
        conn.close()
    return db_path
