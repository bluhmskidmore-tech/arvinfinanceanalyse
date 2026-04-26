from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

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


def test_project_mcp_config_declares_read_only_surfaces() -> None:
    payload = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    servers = payload["mcpServers"]

    assert set(servers) >= {
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "playwright",
    }
    assert servers["moss-metric-contracts"]["args"] == [
        "scripts/mcp/moss_project_mcp.py",
        "metric-contracts",
    ]
    assert servers["moss-lineage-evidence"]["args"][-1] == "lineage-evidence"
    assert servers["moss-data-catalog"]["args"][-1] == "data-catalog"
    assert servers["gitnexus"]["command"] == "node"
    assert servers["gitnexus"]["args"] == [
        ".tmp-gitnexus-v13/node_modules/gitnexus/dist/cli/index.js",
        "mcp",
    ]
    assert servers["playwright"]["args"][-1] == "@playwright/mcp@latest"


def test_metric_contracts_mcp_exposes_contract_docs() -> None:
    server = McpProcess("metric-contracts")
    try:
        init = server.request("initialize")
        server.notify("notifications/initialized")
        assert init["serverInfo"]["name"] == "moss-metric-contracts"

        resources = server.request("resources/list")["resources"]
        assert any(item["uri"] == "moss://metric-contracts/summary" for item in resources)

        summary = server.request("resources/read", {"uri": "moss://metric-contracts/summary"})
        summary_payload = json.loads(summary["contents"][0]["text"])
        assert any(doc["key"] == "page_contracts" and doc["exists"] for doc in summary_payload["documents"])

        search = server.request(
            "tools/call",
            {"name": "search_contract_docs", "arguments": {"query": "product-category", "max_results": 5}},
        )
        search_payload = json.loads(search["content"][0]["text"])
        assert search_payload["matches"]
    finally:
        server.close()


def test_metric_contracts_mcp_exposes_product_category_page_trace_bundle() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_trace_bundle" for tool in tools)

        result = server.request(
            "tools/call",
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": "product-category-pnl"}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["page_slug"] == "product-category-pnl"
        assert payload["frontend_route"] == "/product-category-pnl"
        assert payload["primary_api"] == "/ui/pnl/product-category"
        assert "product_category_pnl_formal_read_model" in payload["truth_chain"]
        assert "backend/app/services/product_category_source_service.py" in payload["backend_touchpoints"]
        assert "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx" in payload[
            "frontend_touchpoints"
        ]
        assert "tests/test_product_category_pnl_flow.py" in payload["test_touchpoints"]
        assert any("zqtz holdings-side logic" in guardrail for guardrail in payload["guardrails"])
    finally:
        server.close()


def test_metric_contracts_page_trace_bundle_accepts_aliases_and_rejects_unknown_pages() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        alias_result = server.request(
            "tools/call",
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": "/product-category-pnl"}},
        )
        alias_payload = json.loads(alias_result["content"][0]["text"])
        assert alias_payload["page_slug"] == "product-category-pnl"

        missing_slug = server.request_error(
            "tools/call",
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": ""}},
        )
        assert missing_slug["code"] == -32602
        assert "page_slug is required" in missing_slug["message"]

        unknown_slug = server.request_error(
            "tools/call",
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": "risk-tensor"}},
        )
        assert unknown_slug["code"] == -32602
        assert "Unknown page_slug: risk-tensor" in unknown_slug["message"]
        assert "product-category-pnl" in unknown_slug["message"]
    finally:
        server.close()


def test_lineage_evidence_mcp_reads_governance_stream_status(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps({"report_date": "2026-03-31", "source_version": "sv_test"}) + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        summary = server.request("resources/read", {"uri": "moss://lineage/summary"})
        payload = json.loads(summary["contents"][0]["text"])
        assert payload["streams"]["cache_manifest"]["exists"] is True

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "2026-03-31", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])
        assert found_payload["records"][0]["stream"] == "cache_manifest"
    finally:
        server.close()


def test_data_catalog_mcp_is_safe_when_duckdb_is_missing(tmp_path: Path) -> None:
    missing_duckdb = tmp_path / "missing.duckdb"
    server = McpProcess("data-catalog", env={"MOSS_DUCKDB_PATH": str(missing_duckdb)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        summary = server.request("resources/read", {"uri": "moss://data-catalog/summary"})
        payload = json.loads(summary["contents"][0]["text"])
        assert payload["duckdb_exists"] is False
        assert payload["tables"] == []
        assert payload["schema_registry"]["exists"] is True
    finally:
        server.close()
