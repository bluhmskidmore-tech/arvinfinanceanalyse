from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DUCKDB_PATH = REPO_ROOT / "data" / "moss.duckdb"
DEFAULT_GOVERNANCE_DIR = REPO_ROOT / "data" / "governance"


class McpError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only project MCP servers for MOSS.")
    parser.add_argument(
        "mode",
        choices=("metric-contracts", "lineage-evidence", "data-catalog", "data-quality"),
        help="Project MCP surface to expose.",
    )
    args = parser.parse_args()

    server = ProjectMcpServer(build_provider(args.mode))
    server.serve()
    return 0


class ProjectMcpServer:
    def __init__(self, provider: "McpProvider") -> None:
        self._provider = provider
        self._next_request_id = 0

    def serve(self) -> None:
        while True:
            message = self._read_message()
            if message is None:
                return
            if "id" not in message:
                self._handle_notification(message)
                continue
            response = self._handle_request(message)
            self._write_message(response)

    def _handle_notification(self, message: dict[str, Any]) -> None:
        if message.get("method") == "notifications/initialized":
            return

    def _handle_request(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("id")
        method = str(message.get("method") or "")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        try:
            result = self._dispatch(method, params)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except McpError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": exc.code, "message": exc.message},
            }
        except Exception as exc:  # pragma: no cover - final protocol safety net
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(exc)},
            }

    def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"resources": {}, "tools": {}},
                "serverInfo": {"name": self._provider.name, "version": "0.1.0"},
            }
        if method == "resources/list":
            return {"resources": self._provider.resources()}
        if method == "resources/read":
            uri = str(params.get("uri") or "")
            return {"contents": [self._provider.read_resource(uri)]}
        if method == "tools/list":
            return {"tools": self._provider.tools()}
        if method == "tools/call":
            name = str(params.get("name") or "")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            return self._provider.call_tool(name, arguments)
        raise McpError(-32601, f"Unsupported method: {method}")

    def _read_message(self) -> dict[str, Any] | None:
        header_lines: list[bytes] = []
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            if line in (b"\r\n", b"\n"):
                break
            header_lines.append(line.rstrip(b"\r\n"))

        content_length = None
        for raw_line in header_lines:
            line = raw_line.decode("ascii", errors="ignore")
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
                break
        if content_length is None:
            raise McpError(-32600, "Missing Content-Length header.")

        body = sys.stdin.buffer.read(content_length)
        if not body:
            return None
        return json.loads(body.decode("utf-8"))

    def _write_message(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()


class McpProvider:
    name: str

    def resources(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def read_resource(self, uri: str) -> dict[str, Any]:
        raise NotImplementedError

    def tools(self) -> list[dict[str, Any]]:
        return []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise McpError(-32602, f"Unknown tool: {name}")


class MetricContractsProvider(McpProvider):
    name = "moss-metric-contracts"

    def __init__(self) -> None:
        self._docs = {
            "page_contracts": REPO_ROOT / "docs" / "page_contracts.md",
            "calc_rules": REPO_ROOT / "docs" / "calc_rules.md",
            "metric_dictionary": REPO_ROOT / "docs" / "metric_dictionary.md",
            "product_category_truth": REPO_ROOT
            / "docs"
            / "pnl"
            / "product-category-page-truth-contract.md",
            "golden_sample_catalog": REPO_ROOT / "docs" / "golden_sample_catalog.md",
        }
        self._page_trace_bundles = product_page_trace_bundles()

    def resources(self) -> list[dict[str, Any]]:
        resources = [
            text_resource(
                "moss://metric-contracts/summary",
                "MOSS metric/page contract summary",
                "High-level index of contract documents and golden samples.",
            )
        ]
        for key, path in self._docs.items():
            resources.append(
                text_resource(
                    f"moss://metric-contracts/doc/{key}",
                    key.replace("_", " "),
                    str(path.relative_to(REPO_ROOT)),
                )
            )
        return resources

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "moss://metric-contracts/summary":
            payload = {
                "repo": str(REPO_ROOT),
                "documents": [
                    {
                        "key": key,
                        "path": str(path.relative_to(REPO_ROOT)),
                        "exists": path.is_file(),
                    }
                    for key, path in self._docs.items()
                ],
                "golden_samples": list_golden_samples(limit=80),
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")

        prefix = "moss://metric-contracts/doc/"
        if uri.startswith(prefix):
            key = uri.removeprefix(prefix)
            path = self._docs.get(key)
            if path is None:
                raise McpError(-32602, f"Unknown contract document: {key}")
            return resource_content(uri, read_text(path), "text/markdown")
        raise McpError(-32602, f"Unknown resource: {uri}")

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "search_contract_docs",
                "description": "Search page contracts, metric dictionary, calc rules, and golden-sample docs.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_page_trace_bundle",
                "description": "Return the read-only contract, lineage, code, and test touchpoints for one seeded MOSS page.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slug": {
                            "type": "string",
                            "description": "Seeded page slug or route alias, for example product-category-pnl or dashboard-home.",
                        }
                    },
                    "required": ["page_slug"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "search_contract_docs":
            query = str(arguments.get("query") or "").strip()
            if not query:
                raise McpError(-32602, "query is required.")
            max_results = int(arguments.get("max_results") or 20)
            matches = search_files(self._docs.values(), query=query, max_results=max_results)
            return tool_text(json.dumps({"query": query, "matches": matches}, ensure_ascii=False, indent=2))
        if name == "get_page_trace_bundle":
            page_slug = str(arguments.get("page_slug") or "").strip()
            payload = page_trace_bundle(self._page_trace_bundles, page_slug)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return super().call_tool(name, arguments)


class LineageEvidenceProvider(McpProvider):
    name = "moss-lineage-evidence"
    _QUERY_EXPANSIONS = {
        "page-agent-001": [
            "agent.",
            "AgentEnvelope",
            "agent_audit",
            "/api/agent/runs",
            "/api/agent/query",
        ],
        "page-balance-001": [
            "/ui/balance-analysis/overview",
            "/ui/balance-analysis/workbook",
            "balance-analysis.overview",
            "balance-analysis.workbook",
            "balance_analysis",
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "GS-BAL-OVERVIEW-A",
            "GS-BAL-WORKBOOK-A",
            "MTR-BAL-001",
            "MTR-BAL-002",
            "MTR-BAL-003",
            "MTR-BAL-004",
            "MTR-BAL-005",
            "MTR-BAL-006",
            "MTR-BAL-101",
            "MTR-BAL-102",
            "MTR-BAL-103",
            "MTR-BAL-104",
            "MTR-BAL-105",
            "MTR-BAL-201",
            "MTR-BAL-202",
            "MTR-BAL-203",
        ],
        "page-bridge-001": [
            "/api/pnl/bridge",
            "pnl.bridge",
            "pnl_bridge",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "GS-BRIDGE-A",
            "GS-BRIDGE-WARN-B",
            "MTR-BRG-001",
            "MTR-BRG-002",
            "MTR-BRG-003",
            "MTR-BRG-004",
            "MTR-BRG-005",
            "MTR-BRG-006",
            "MTR-BRG-007",
            "MTR-BRG-008",
            "MTR-BRG-009",
            "MTR-BRG-010",
            "MTR-BRG-011",
            "MTR-BRG-012",
            "MTR-BRG-013",
            "MTR-BRG-014",
            "MTR-BRG-101",
            "MTR-BRG-102",
            "MTR-BRG-103",
            "MTR-BRG-104",
            "MTR-BRG-105",
        ],
        "page-cube-query-001": [
            "/api/cube/query",
            "cube_query.",
            "fact_formal_bond_analytics_daily",
            "fact_formal_pnl_fi",
            "fact_formal_zqtz_balance_daily",
            "product_category_pnl_formal_read_model",
        ],
        "page-ledger-pnl-001": [
            "/api/ledger-pnl/summary",
            "/api/ledger-pnl/data",
            "/api/ledger-pnl/formal-financial-indicators",
            "ledger_pnl.",
            "qdb_general_ledger_workbook",
            "formal_financial_indicator_source_contract",
            "GS-LEDGER-PNL-FIN-IND-202603-B",
        ],
        "page-pnl-001": [
            "/api/pnl/overview",
            "/api/pnl/data",
            "pnl.overview",
            "pnl.data",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "GS-PNL-OVERVIEW-A",
            "GS-PNL-DATA-A",
            "MTR-PNL-001",
            "MTR-PNL-002",
            "MTR-PNL-003",
            "MTR-PNL-004",
            "MTR-PNL-005",
            "MTR-PNL-101",
            "MTR-PNL-102",
            "MTR-PNL-103",
            "MTR-PNL-104",
        ],
        "page-prod-cat-001": [
            "product-category-pnl",
            "/ui/pnl/product-category",
            "product_category_pnl.detail",
            "product_category_pnl_formal_read_model",
            "product_category_pnl_canonical_fact",
            "GS-PROD-CAT-PNL-A",
            "MTR-PCP-001",
            "MTR-PCP-002",
            "MTR-PCP-003",
        ],
        "page-prod-cat-pnl-001": [
            "product-category-pnl",
            "/ui/pnl/product-category",
            "product_category_pnl.detail",
            "product_category_pnl_formal_read_model",
            "product_category_pnl_canonical_fact",
            "GS-PROD-CAT-PNL-A",
            "MTR-PCP-001",
            "MTR-PCP-002",
            "MTR-PCP-003",
        ],
        "page-risk-001": [
            "fact_formal_risk_tensor_daily",
            "agent.risk_tensor",
            "risk_tensor",
            "risk.tensor",
            "risk-tensor",
        ],
    }

    def __init__(self) -> None:
        self._governance_dir = resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR)
        self._streams = {
            "agent_audit": self._governance_dir / "agent_audit.jsonl",
            "cache_build_run": self._governance_dir / "cache_build_run.jsonl",
            "cache_manifest": self._governance_dir / "cache_manifest.jsonl",
            "snapshot_manifest": self._governance_dir / "snapshot_manifest.jsonl",
            "source_manifest": self._governance_dir / "source_manifest.jsonl",
            "source_manifest_latest": self._governance_dir / "source_manifest_latest.jsonl",
            "vendor_version_registry": self._governance_dir / "vendor_version_registry.jsonl",
        }

    def resources(self) -> list[dict[str, Any]]:
        resources = [
            text_resource(
                "moss://lineage/summary",
                "MOSS lineage/evidence summary",
                "Governance stream status and latest records.",
            ),
            text_resource(
                "moss://lineage/streams",
                "MOSS governance streams",
                "Known governance JSONL streams.",
            ),
        ]
        for name in self._streams:
            resources.append(
                text_resource(
                    f"moss://lineage/stream/{name}",
                    name,
                    f"Latest records from {name}.",
                    mime_type="application/json",
                )
            )
        return resources

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "moss://lineage/summary":
            payload = {
                "governance_dir": str(self._governance_dir),
                "streams": {
                    name: stream_status(path)
                    for name, path in self._streams.items()
                },
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        if uri == "moss://lineage/streams":
            payload = {
                name: str(path.relative_to(REPO_ROOT)) if is_relative_to(path, REPO_ROOT) else str(path)
                for name, path in self._streams.items()
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")

        prefix = "moss://lineage/stream/"
        if uri.startswith(prefix):
            stream = uri.removeprefix(prefix)
            path = self._stream_path(stream)
            payload = {
                "stream": stream,
                "path": str(path),
                "latest_records": read_jsonl_tail(path, limit=5),
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        raise McpError(-32602, f"Unknown resource: {uri}")

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "read_governance_stream",
                "description": "Read the latest records from a whitelisted governance JSONL stream.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "stream": {"type": "string", "enum": sorted(self._streams)},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["stream"],
                },
            },
            {
                "name": "find_lineage_records",
                "description": "Find lineage/evidence records by report_date, source_version, rule_version, or result kind.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "streams": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(self._streams)},
                        },
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": ["query"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "read_governance_stream":
            stream = str(arguments.get("stream") or "")
            limit = int(arguments.get("limit") or 10)
            path = self._stream_path(stream)
            payload = {"stream": stream, "records": read_jsonl_tail(path, limit=limit)}
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "find_lineage_records":
            query = str(arguments.get("query") or "").strip()
            if not query:
                raise McpError(-32602, "query is required.")
            query_terms = lineage_query_terms(query, self._QUERY_EXPANSIONS)
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            max_results = int(arguments.get("max_results") or 40)
            records = []
            seen_records: set[tuple[str, int]] = set()
            for stream in stream_names:
                path = self._stream_path(stream)
                for query_term in query_terms:
                    stream_records = find_jsonl_records(
                        path,
                        stream=stream,
                        query=query_term,
                        max_results=max_results,
                    )
                    for record in stream_records:
                        record_key = (str(record.get("stream") or stream), int(record.get("line") or 0))
                        if record_key in seen_records:
                            continue
                        seen_records.add(record_key)
                        records.append({"matched_query": query_term, **record})
                        if len(records) >= max_results:
                            break
                    if len(records) >= max_results:
                        break
                if len(records) >= max_results:
                    break
            payload = {
                "query": query,
                "expanded_queries": query_terms,
                "records": records[:max_results],
            }
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return super().call_tool(name, arguments)

    def _stream_path(self, stream: str) -> Path:
        path = self._streams.get(stream)
        if path is None:
            raise McpError(-32602, f"Unknown governance stream: {stream}")
        return path


class DataCatalogProvider(McpProvider):
    name = "moss-data-catalog"

    def __init__(self) -> None:
        self._duckdb_path = resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)
        self._schema_dir = REPO_ROOT / "backend" / "app" / "schema_registry" / "duckdb"

    def resources(self) -> list[dict[str, Any]]:
        return [
            text_resource(
                "moss://data-catalog/summary",
                "MOSS read-only data catalog summary",
                "DuckDB path, schema registry, table inventory, and available report-date hints.",
                mime_type="application/json",
            ),
            text_resource(
                "moss://data-catalog/schema-registry",
                "MOSS DuckDB schema registry",
                "SQL files under backend/app/schema_registry/duckdb.",
                mime_type="application/json",
            ),
            text_resource(
                "moss://data-catalog/tables",
                "MOSS DuckDB tables",
                "Read-only table inventory from information_schema.",
                mime_type="application/json",
            ),
        ]

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "moss://data-catalog/summary":
            payload = {
                "duckdb_path": str(self._duckdb_path),
                "duckdb_exists": self._duckdb_path.is_file(),
                "schema_registry": schema_registry_summary(self._schema_dir),
                "tables": duckdb_tables(self._duckdb_path, limit=80),
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        if uri == "moss://data-catalog/schema-registry":
            payload = schema_registry_summary(self._schema_dir)
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        if uri == "moss://data-catalog/tables":
            payload = {"tables": duckdb_tables(self._duckdb_path, limit=500)}
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        raise McpError(-32602, f"Unknown resource: {uri}")

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "describe_table",
                "description": "Describe one DuckDB table using information_schema only.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"table_name": {"type": "string"}},
                    "required": ["table_name"],
                },
            },
            {
                "name": "list_available_dates",
                "description": "List distinct dates for a known date column on one DuckDB table.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "date_column": {"type": "string", "default": "report_date"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                    "required": ["table_name"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "describe_table":
            table_name = str(arguments.get("table_name") or "").strip()
            payload = describe_duckdb_table(self._duckdb_path, table_name)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "list_available_dates":
            table_name = str(arguments.get("table_name") or "").strip()
            date_column = str(arguments.get("date_column") or "report_date").strip()
            limit = int(arguments.get("limit") or 50)
            payload = list_available_dates(self._duckdb_path, table_name, date_column, limit=limit)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return super().call_tool(name, arguments)


class DataQualityProvider(McpProvider):
    name = "moss-data-quality"

    def __init__(self) -> None:
        self._duckdb_path = resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)

    def resources(self) -> list[dict[str, Any]]:
        return [
            text_resource(
                "moss://data-quality/summary",
                "MOSS DuckDB data-quality summary",
                "Read-only table/view quality targets and DuckDB availability.",
                mime_type="application/json",
            ),
            text_resource(
                "moss://data-quality/targets",
                "MOSS DuckDB quality targets",
                "Read-only list of table/view targets eligible for quality profiling.",
                mime_type="application/json",
            ),
        ]

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "moss://data-quality/summary":
            payload = {
                "duckdb_path": str(self._duckdb_path),
                "duckdb_exists": self._duckdb_path.is_file(),
                "targets": duckdb_quality_targets(self._duckdb_path, limit=80),
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        if uri == "moss://data-quality/targets":
            payload = {"targets": duckdb_quality_targets(self._duckdb_path, limit=500)}
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        raise McpError(-32602, f"Unknown resource: {uri}")

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "list_quality_targets",
                "description": "List read-only DuckDB tables/views eligible for quality summaries.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                },
            },
            {
                "name": "get_quality_summary",
                "description": "Compute a read-only quality summary for one known DuckDB table or view.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": ["table_name"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "list_quality_targets":
            limit = int(arguments.get("limit") or 50)
            payload = {"targets": duckdb_quality_targets(self._duckdb_path, limit=limit)}
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_quality_summary":
            table_name = str(arguments.get("table_name") or "").strip()
            column_limit = int(arguments.get("column_limit") or 25)
            payload = duckdb_quality_summary(self._duckdb_path, table_name, column_limit=column_limit)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return super().call_tool(name, arguments)


def build_provider(mode: str) -> McpProvider:
    providers: dict[str, Callable[[], McpProvider]] = {
        "metric-contracts": MetricContractsProvider,
        "lineage-evidence": LineageEvidenceProvider,
        "data-catalog": DataCatalogProvider,
        "data-quality": DataQualityProvider,
    }
    return providers[mode]()


def text_resource(uri: str, name: str, description: str, *, mime_type: str = "text/plain") -> dict[str, Any]:
    return {"uri": uri, "name": name, "description": description, "mimeType": mime_type}


def resource_content(uri: str, text: str, mime_type: str) -> dict[str, Any]:
    return {"uri": uri, "mimeType": mime_type, "text": text}


def tool_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def read_text(path: Path) -> str:
    safe_path = assert_repo_path(path)
    if not safe_path.is_file():
        raise McpError(-32602, f"File does not exist: {safe_path}")
    return safe_path.read_text(encoding="utf-8", errors="replace")


def assert_repo_path(path: Path) -> Path:
    resolved = path.resolve()
    if not is_relative_to(resolved, REPO_ROOT):
        raise McpError(-32602, f"Path is outside repo: {resolved}")
    return resolved


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def resolve_path_env(env_name: str, fallback: Path) -> Path:
    raw = str(os.environ.get(env_name) or "").strip()
    if not raw:
        return fallback.resolve()
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def product_page_trace_bundles() -> dict[str, dict[str, Any]]:
    product_category_bundle = {
        "page_slug": "product-category-pnl",
        "page_id": "PAGE-PROD-CAT-001",
        "page_name": "Product-category PnL",
        "aliases": [
            "product-category-pnl",
            "/product-category-pnl",
            "product_category_pnl",
            "PAGE-PROD-CAT-001",
            "PAGE-PROD-CAT-PNL-001",
        ],
        "frontend_route": "/product-category-pnl",
        "primary_api": "/ui/pnl/product-category",
        "supporting_apis": [
            "/ui/pnl/product-category/dates",
            "/ui/pnl/product-category/refresh",
            "/ui/pnl/product-category/refresh-status",
            "/ui/pnl/product-category/manual-adjustments",
            "/ui/pnl/product-category/manual-adjustments/export",
        ],
        "contract_docs": [
            "docs/pnl/product-category-page-truth-contract.md",
            "docs/pnl/adr-product-category-truth-chain.md",
            "docs/pnl/product-category-golden-sample-a.md",
            "docs/pnl/product-category-closure-checklist.md",
            "docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md",
        ],
        "truth_chain": [
            "paired ledger reconciliation workbook + daily average workbook",
            "backend/app/services/product_category_source_service.py",
            "backend/app/core_finance/product_category_pnl.py",
            "product_category_pnl_formal_read_model",
            "backend/app/services/product_category_pnl_service.py",
            "/ui/pnl/product-category",
            "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/services/product_category_source_service.py",
            "backend/app/core_finance/config/product_category_mapping.py",
            "backend/app/core_finance/product_category_pnl.py",
            "backend/app/services/product_category_pnl_service.py",
            "backend/app/api/routes/product_category_pnl.py",
            "backend/app/schemas/product_category_pnl.py",
            "backend/app/repositories/product_category_pnl_repo.py",
            "backend/app/tasks/product_category_pnl.py",
            "backend/app/schema_registry/duckdb/08_product_category_pnl.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx",
            "frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts",
            "frontend/src/features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage.tsx",
        ],
        "test_touchpoints": [
            "tests/test_product_category_pnl_flow.py",
            "tests/test_product_category_mapping_contract.py",
            "frontend/src/test/ProductCategoryPnlPage.test.tsx",
            "frontend/src/test/ProductCategoryBranchSwitcher.test.tsx",
            "frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx",
            "frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts",
            "tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-PROD-CAT-PNL-A"],
        "verification_focus": [
            "Trace API response through adapter/model state into ProductCategoryPnlPage before changing display logic.",
            "Check units, precision, null-vs-zero semantics, report_date resolution, fallback/stale flags, and result_meta visibility.",
            "Keep baseline and scenario row identity stable; scenario_rate_pct must not redefine the category tree.",
            "Do not recompute governed totals in the frontend; display backend totals.",
        ],
        "guardrails": [
            "Do not infer product-category row meaning from zqtz holdings-side logic, holdings buckets, or research-style bond categories.",
            "Use the paired ledger reconciliation + daily average source chain as the row authority.",
            "Use backend/app/core_finance/config/product_category_mapping.py and backend/app/core_finance/product_category_pnl.py for governed row meaning.",
            "Do not add qtd or year_to_report_month_end to the main page selector without updating the page contract, closure checklist, and tests.",
            "Treat missing standalone as_of_date as an explicit contract gap, not an assumption.",
        ],
    }
    dashboard_home_bundle = {
        "page_slug": "dashboard-home",
        "page_id": "PAGE-DASH-001",
        "page_name": "Dashboard Home",
        "aliases": [
            "dashboard-home",
            "dashboard",
            "/dashboard",
            "/",
            "PAGE-DASH-001",
        ],
        "frontend_route": "/",
        "primary_api": "/ui/home/snapshot",
        "supporting_apis": [
            "/ui/home/overview",
            "/ui/home/summary",
            "/api/dashboard/core_metrics",
            "/api/dashboard/daily-changes",
            "/api/bond-dashboard/headline-kpis",
            "/api/bond-analytics/portfolio-headlines",
            "/ui/market-data/rates",
            "/ui/calendar/supply-auctions",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/dashboard_cockpit_contract.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-DASH-001",
            "docs/dashboard_cockpit_contract.md",
            "backend/app/services/executive_service.py home_snapshot_envelope",
            "backend/app/api/routes/executive.py GET /ui/home/snapshot",
            "frontend/src/api/executiveHomeSnapshotFetch.ts",
            "frontend/src/features/workbench/pages/useDashboardSnapshotBoundary.ts",
            "frontend/src/features/workbench/pages/DashboardPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/executive.py",
            "backend/app/services/executive_service.py",
            "backend/app/services/dashboard_service.py",
            "backend/app/services/bond_dashboard_service.py",
            "backend/app/schemas/executive_dashboard.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/router/routes.tsx",
            "frontend/src/api/executiveClient.ts",
            "frontend/src/api/executiveHomeSnapshotFetch.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/workbench/pages/DashboardPage.tsx",
            "frontend/src/features/workbench/pages/useDashboardSnapshotBoundary.ts",
            "frontend/src/features/workbench/dashboard/dashboardHomeModel.ts",
            "frontend/src/features/workbench/dashboard/dashboardCockpitHomeModel.ts",
            "frontend/src/features/workbench/dashboard/sections/DashboardCockpitHeader.tsx",
            "frontend/src/features/workbench/dashboard/sections/DashboardJudgmentStrip.tsx",
        ],
        "test_touchpoints": [
            "tests/test_home_snapshot_endpoint.py",
            "tests/test_dashboard_api_contract.py",
            "tests/test_executive_dashboard_endpoints.py",
            "tests/test_executive_service_contract.py",
            "frontend/src/test/DashboardPage.test.tsx",
            "frontend/src/features/workbench/pages/useDashboardSnapshotBoundary.test.tsx",
            "frontend/src/features/workbench/dashboard/dashboardHomeModel.test.ts",
            "frontend/src/features/workbench/dashboard/dashboardCockpitHomeModel.test.ts",
            "frontend/src/features/workbench/dashboard/sections/DashboardCockpitHeader.test.tsx",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-EXEC-OVERVIEW-A",
            "tests/golden_samples/GS-EXEC-PNL-ATTR-A",
            "tests/golden_samples/GS-EXEC-SUMMARY-A",
        ],
        "verification_focus": [
            "Treat /ui/home/snapshot as the primary report-date, verdict, governance-status, and lineage source.",
            "Trace snapshot result through getHomeSnapshot, useDashboardSnapshotBoundary, dashboardHomeModel, dashboardCockpitHomeModel, and DashboardPage before changing display logic.",
            "Keep supplemental surfaces gated by report_date equality with the snapshot report_date before first-screen trust.",
            "Check analytical basis, partial-mode domains, stale/fallback/vendor flags, mock fallback warnings, and reserved endpoint visibility.",
        ],
        "guardrails": [
            "Do not promote dashboard-home aggregate values to formal metric truth without updating metric_dictionary and page contracts.",
            "Do not request or render reserved /ui/risk/overview, /ui/home/alerts, or /ui/home/contribution as normal first-screen conclusions.",
            "Do not fill missing homepage snapshot fields with demo, reserved, or stale figures in real mode.",
            "Do not recompute formal business metrics in the frontend; consume backend-owned snapshot and supplemental payloads.",
            "Treat the aggregate homepage as analytical/mixed-source; its executive golden samples cover sub-surfaces, not a full-page formal sample.",
        ],
    }
    executive_overview_bundle = {
        "page_slug": "executive-overview",
        "page_id": "PAGE-EXEC-OVERVIEW-001",
        "page_name": "Executive Overview",
        "aliases": [
            "executive-overview",
            "executive_overview",
            "/ui/home/overview",
            "PAGE-EXEC-OVERVIEW-001",
        ],
        "frontend_route": "/dashboard",
        "primary_api": "/ui/home/overview",
        "supporting_apis": [
            "/ui/home/snapshot",
            "/ui/home/summary",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/dashboard_cockpit_contract.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-EXEC-OVERVIEW-001",
            "docs/metric_dictionary.md MTR-EXEC-001 through MTR-EXEC-004 and MTR-EXEC-004A/B/C",
            "backend/app/services/executive_service.py executive_overview",
            "backend/app/schemas/executive_dashboard.py OverviewPayload and ExecutiveMetric.caliber_label",
            "executive.overview result_meta",
            "/ui/home/overview",
            "frontend/src/features/executive-dashboard/components/OverviewSection.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/executive.py",
            "backend/app/services/executive_service.py",
            "backend/app/schemas/executive_dashboard.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/executiveClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/executive-dashboard/components/OverviewSection.tsx",
            "frontend/src/features/executive-dashboard/selectors/executiveDashboardSelectors.ts",
            "frontend/src/features/executive-dashboard/adapters/executiveDashboardAdapter.ts",
        ],
        "test_touchpoints": [
            "tests/test_executive_dashboard_endpoints.py",
            "tests/test_executive_service_contract.py",
            "tests/test_executive_release_contract.py",
            "tests/test_executive_dashboard_numeric_migration.py",
            "tests/test_golden_samples_capture_ready.py",
            "frontend/src/test/OverviewSection.test.tsx",
            "frontend/src/features/executive-dashboard/components/OverviewSection.states.test.tsx",
            "frontend/src/features/executive-dashboard/selectors/executiveDashboardSelectors.test.ts",
            "frontend/src/features/executive-dashboard/adapters/executiveDashboardAdapter.test.ts",
            "tests/golden_samples/GS-EXEC-OVERVIEW-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-EXEC-OVERVIEW-A"],
        "verification_focus": [
            "Trace /ui/home/overview result_meta through executive_overview, getOverview, the dashboard adapter/selectors, and OverviewSection before changing display logic.",
            "Check analytical basis, report_date selection, metric IDs, caliber_label display, domain effective-date labels, and no silent mock fallback.",
            "Verify GS-EXEC-OVERVIEW-A remains an executive analytical overlay sample and does not redefine formal balance, formal PnL, or risk-tensor truth.",
        ],
        "guardrails": [
            "Treat this as an analytical overlay for management summary, not a formal source-of-truth page.",
            "Do not replace formal balance, formal PnL, risk tensor, or PnL bridge evidence with executive overview cards.",
            "Do not hide metric caliber_label, result_meta, quality, fallback, vendor, or date-resolution boundaries.",
            "Do not allow silent downgrade to mock/demo values when /ui/home/overview cannot resolve governed inputs.",
            "Keep MTR-EXEC-004A/B/C as management-risk split components; do not collapse them into a new formal risk metric without updating contracts and tests.",
        ],
    }
    executive_summary_bundle = {
        "page_slug": "executive-summary",
        "page_id": "PAGE-EXEC-SUMMARY-001",
        "page_name": "Executive Summary",
        "aliases": [
            "executive-summary",
            "executive_summary",
            "/ui/home/summary",
            "PAGE-EXEC-SUMMARY-001",
        ],
        "frontend_route": "/dashboard",
        "primary_api": "/ui/home/summary",
        "supporting_apis": [
            "/ui/home/overview",
            "/ui/home/snapshot",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/dashboard_cockpit_contract.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-EXEC-SUMMARY-001",
            "docs/metric_dictionary.md GS-EXEC-SUMMARY-A is narrative-only and does not enter the business metric dictionary main table",
            "docs/golden_sample_catalog.md GS-EXEC-SUMMARY-A freezes title, points.length, and point labels for /ui/home/summary",
            "backend/app/services/executive_service.py executive_summary",
            "backend/app/schemas/executive_dashboard.py SummaryPayload title/report_date/narrative/points",
            "executive.summary result_meta",
            "/ui/home/summary",
            "frontend/src/api/executiveClient.ts getSummary",
            "frontend/src/features/executive-dashboard/components/SummarySection.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/executive.py",
            "backend/app/services/executive_service.py",
            "backend/app/schemas/executive_dashboard.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/executiveClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/executive-dashboard/components/SummarySection.tsx",
        ],
        "test_touchpoints": [
            "tests/test_executive_service_contract.py",
            "tests/test_executive_dashboard_endpoints.py",
            "tests/test_executive_release_contract.py",
            "tests/test_golden_samples_capture_ready.py",
            "tests/golden_samples/GS-EXEC-SUMMARY-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-EXEC-SUMMARY-A"],
        "verification_focus": [
            "Trace /ui/home/summary through executive_summary, SummaryPayload, getSummary, SummarySection, and GS-EXEC-SUMMARY-A before changing narrative display logic.",
            "Check report_date selection, narrative text, title, points length, point labels, result_meta.result_kind=executive.summary, source_version, and rule_version.",
            "Verify summary narrative does not hide upstream overview, formal balance, formal PnL, risk, or attribution no-data/fallback/stale states.",
        ],
        "guardrails": [
            "Treat PAGE-EXEC-SUMMARY-001 as a narrative-only contract, not a formal business metric surface.",
            "Do not add executive summary narrative fields to the metric dictionary main table or promote them to MTR-* rows.",
            "Do not use narrative text as formal source-of-truth evidence or as a substitute for formal balance, formal PnL, risk tensor, PnL bridge, or attribution truth.",
            "Do not use narrative text to cover upstream metric missing-data, stale, fallback, vendor, no-data, or error states.",
            "Keep GS-EXEC-SUMMARY-A scoped to title, points.length, point labels, and result_meta lineage for the summary endpoint.",
        ],
    }
    balance_analysis_bundle = {
        "page_slug": "balance-analysis",
        "page_id": "PAGE-BALANCE-001",
        "page_name": "Balance Analysis",
        "aliases": [
            "balance-analysis",
            "/balance-analysis",
            "balance_analysis",
            "PAGE-BALANCE-001",
            "/ui/balance-analysis/overview",
        ],
        "frontend_route": "/balance-analysis",
        "primary_api": "/ui/balance-analysis/overview",
        "supporting_apis": [
            "/ui/balance-analysis/dates",
            "/ui/balance-analysis",
            "/ui/balance-analysis/workbook",
            "/ui/balance-analysis/summary",
            "/ui/balance-analysis/summary-by-basis",
            "/ui/balance-analysis/decision-items",
            "/ui/balance-analysis/current-user",
            "/ui/balance-analysis/advanced-attribution",
            "/ui/balance-analysis/refresh",
            "/ui/balance-analysis/refresh-status",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/calc_rules.md",
            "docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md",
            "docs/balance_analysis_field_trace.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-BALANCE-001",
            "docs/metric_dictionary.md MTR-BAL-001 through MTR-BAL-006, MTR-BAL-101 through MTR-BAL-105, and MTR-BAL-201 through MTR-BAL-203",
            "backend/app/schema_registry/duckdb/05_balance_analysis.sql fact_formal_zqtz_balance_daily + fact_formal_tyw_balance_daily",
            "backend/app/tasks/balance_analysis_materialize.py materialize_balance_analysis_facts",
            "backend/app/services/balance_analysis_service.py balance_analysis_overview_envelope",
            "BalanceAnalysisWorkbookPayload",
            "/ui/balance-analysis/overview",
            "frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/balance_analysis.py",
            "backend/app/services/balance_analysis_service.py",
            "backend/app/services/balance_analysis_workbook_service.py",
            "backend/app/core_finance/balance_analysis.py",
            "backend/app/core_finance/balance_analysis_workbook.py",
            "backend/app/schemas/balance_analysis.py",
            "backend/app/repositories/balance_analysis_repo.py",
            "backend/app/repositories/balance_analysis_decision_repo.py",
            "backend/app/tasks/balance_analysis_materialize.py",
            "backend/app/schema_registry/duckdb/05_balance_analysis.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/client.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx",
            "frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.ts",
            "frontend/src/features/balance-analysis/components/BalanceAnalysisWorkbenchLayout.tsx",
        ],
        "test_touchpoints": [
            "tests/test_balance_analysis_api.py",
            "tests/test_balance_analysis_contracts.py",
            "tests/test_balance_analysis_core.py",
            "tests/test_balance_analysis_materialize_flow.py",
            "tests/test_balance_analysis_service.py",
            "tests/test_balance_analysis_boundary_guards.py",
            "tests/test_balance_analysis_workbook_contract.py",
            "tests/test_balance_analysis_module_registration_flow.py",
            "frontend/src/test/BalanceAnalysisPage.test.tsx",
            "tests/test_golden_samples_capture_ready.py",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-BAL-OVERVIEW-A",
            "tests/golden_samples/GS-BAL-WORKBOOK-A",
        ],
        "verification_focus": [
            "Trace /ui/balance-analysis/overview result_meta through getBalanceAnalysisOverview, buildBalanceAnalysisPageModel, BalanceAnalysisPage, and the formal meta panel before changing display logic.",
            "Check report_date, position_scope, currency_basis, source_version, rule_version, cache_version, trace_id, and fallback/stale visibility.",
            "Check units and null-vs-zero semantics for total market value, amortized cost, accrued interest, detail rows, summary rows, workbook sections, and basis breakdown.",
            "Keep workbook structural truth separate from advanced attribution; advanced_attribution is an analytical/scenario boundary, not formal balance truth.",
        ],
        "guardrails": [
            "Do not replace formal balance truth with snapshot, preview, ADB analytical preview, or advanced_attribution_bundle output.",
            "Do not write advanced_attribution_bundle as a currently governed workbook section.",
            "Do not recompute governed balance metrics, row counts, position_scope, currency_basis, invest_type_std, accounting_basis, or source_family in the frontend.",
            "Keep fallback_mode, stale/vendor status, result_meta, and no-data states visible on the frontend.",
            "Use fact_formal_zqtz_balance_daily and fact_formal_tyw_balance_daily as the formal balance read authority.",
        ],
    }
    balance_movement_analysis_bundle = {
        "page_slug": "balance-movement-analysis",
        "page_id": "PAGE-BAL-MOVE-001",
        "page_name": "Balance Movement Analysis",
        "aliases": [
            "balance-movement-analysis",
            "balance_movement_analysis",
            "/balance-movement-analysis",
            "PAGE-BAL-MOVE-001",
            "/ui/balance-movement-analysis",
        ],
        "frontend_route": "/balance-movement-analysis",
        "primary_api": "/ui/balance-movement-analysis",
        "supporting_apis": [
            "/ui/balance-movement-analysis/dates",
            "/ui/balance-movement-analysis/refresh",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
            "docs/plans/2026-05-14-balance-movement-analysis-diagnostics-mvp.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-BAL-MOVE-001",
            "docs/page_contracts.md MTR-BMV-001 through MTR-BMV-004",
            "backend/app/schema_registry/duckdb/18_accounting_asset_movement.sql fact_accounting_asset_movement_monthly",
            "backend/app/tasks/accounting_asset_movement.py rv_accounting_asset_movement_v2",
            "backend/app/services/accounting_asset_movement_service.py accounting_asset_movement_envelope",
            "AccountingAssetMovementPayload",
            "AccountingAssetMovementSummaryPayload",
            "/ui/balance-movement-analysis",
            "frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/accounting_asset_movement.py",
            "backend/app/services/accounting_asset_movement_service.py",
            "backend/app/repositories/accounting_asset_movement_repo.py",
            "backend/app/tasks/accounting_asset_movement.py",
            "backend/app/core_finance/accounting_asset_movement.py",
            "backend/app/schemas/accounting_asset_movement.py",
            "backend/app/schema_registry/duckdb/18_accounting_asset_movement.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/balanceMovementClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx",
            "frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.css",
            "frontend/src/mocks/navigation.ts",
        ],
        "test_touchpoints": [
            "tests/test_accounting_asset_movement_api.py",
            "tests/test_accounting_asset_movement_service.py",
            "tests/test_accounting_asset_movement_core.py",
            "tests/test_accounting_asset_movement_materialize.py",
            "tests/test_result_meta_on_all_ui_endpoints.py",
            "tests/test_live_route_page_contract_completeness.py",
            "tests/test_write_route_auth_contract.py",
            "frontend/src/test/BalanceMovementAnalysisPage.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-BAL-MOVE-001; verify through page contract, route/service/core/materialize tests, result_meta checks, and frontend page tests.",
            "Trace /ui/balance-movement-analysis summary fields through balanceMovementClient, BalanceMovementAnalysisPage, summary cards, reconciliation strip, and movement diagnostics before changing display logic.",
            "Check selected report dates, currency_basis, previous/current/change/reconciliation totals, refresh authorization, stale/fallback metadata, and no-data/error states.",
            "Keep balance movement explanation separate from PAGE-BALANCE-001 formal balance truth; this page explains movement for selected report dates and currency basis.",
        ],
        "guardrails": [
            "Do not use balance movement explanation to replace PAGE-BALANCE-001 formal balance truth.",
            "Do not hide selected report dates, currency_basis, result_meta, source/rule/cache versions, refresh status, stale/fallback states, or no-data/error states.",
            "Do not backfill missing movement rows with demo rows, mock rows, or previous page values in real mode.",
            "Do not recompute governed previous/current/change/reconciliation summary totals in the frontend.",
            "Keep unsupported valuation, FX translation, low-coverage, residual, and diagnostic caveats visible when present.",
        ],
    }
    pnl_bundle = {
        "page_slug": "pnl",
        "page_id": "PAGE-PNL-001",
        "page_name": "Formal PnL",
        "aliases": [
            "pnl",
            "/pnl",
            "formal-pnl",
            "formal_pnl",
            "PAGE-PNL-001",
            "/api/pnl/overview",
        ],
        "frontend_route": "/pnl",
        "primary_api": "/api/pnl/overview",
        "supporting_apis": [
            "/api/pnl/dates",
            "/api/pnl/data",
            "/api/data/refresh_pnl",
            "/api/data/import_status/pnl",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/calc_rules.md",
            "docs/data_contracts.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-PNL-001",
            "docs/metric_dictionary.md MTR-PNL-001 through MTR-PNL-005 and MTR-PNL-101 through MTR-PNL-104",
            "backend/app/schema_registry/duckdb/07_pnl_materialize.sql fact_formal_pnl_fi + fact_nonstd_pnl_bridge",
            "backend/app/core_finance/pnl.py build_formal_pnl_fi_fact_rows",
            "backend/app/tasks/pnl_materialize.py materialize_formal_pnl_facts",
            "backend/app/services/pnl_service.py pnl_overview_envelope",
            "PnlOverviewPayload",
            "PnlDataPayload",
            "/api/pnl/overview",
            "frontend/src/features/pnl/PnlPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/pnl.py",
            "backend/app/services/pnl_service.py",
            "backend/app/core_finance/pnl.py",
            "backend/app/schemas/pnl.py",
            "backend/app/repositories/pnl_repo.py",
            "backend/app/tasks/pnl_materialize.py",
            "backend/app/schema_registry/duckdb/07_pnl_materialize.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlCoreClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/pnl/PnlPage.tsx",
        ],
        "test_touchpoints": [
            "tests/test_pnl_api_contract.py",
            "tests/test_pnl_formal_semantics_contract.py",
            "tests/test_pnl_core_finance_contract.py",
            "tests/test_pnl_materialize_flow.py",
            "frontend/src/test/PnlPage.test.tsx",
            "frontend/src/test/PnlRoutesSmoke.test.tsx",
            "tests/test_golden_samples_capture_ready.py",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-PNL-OVERVIEW-A",
            "tests/golden_samples/GS-PNL-DATA-A",
        ],
        "verification_focus": [
            "Trace /api/pnl/overview result_meta through getFormalPnlOverview, PnlPage state, overview cards, formal row table, and the meta panel before changing display logic.",
            "Check report_date, basis, source_version, rule_version, cache_version, trace_id, fallback/stale visibility, and report-date-specific build lineage preference.",
            "Check units and null-vs-zero semantics for 514 interest income, 516 fair value change, 517 capital gain, manual adjustment, total_pnl, and row counts.",
            "Verify GS-PNL-OVERVIEW-A can be reconciled back to GS-PNL-DATA-A row aggregation.",
        ],
        "guardrails": [
            "Do not replace formal PnL truth with PnL Bridge reconciliation, executive analytical overlay, or product-category operating PnL.",
            "Do not treat standardized total as formal PnL total; fact_formal_pnl_fi.total_pnl is the formal recognized total.",
            "Do not redo 516 sign logic, formal recognition, invest_type_std, accounting_basis, or row-count calculations in the frontend.",
            "Keep non-formal basis selections visibly distinct from the formal main chain.",
            "Keep missing data, 404 no-data states, fallback lineage, and result_meta visible instead of filling with mock or stale figures.",
        ],
    }
    ledger_pnl_bundle = {
        "page_slug": "ledger-pnl",
        "page_id": "PAGE-LEDGER-PNL-001",
        "page_name": "Ledger PnL",
        "aliases": [
            "ledger-pnl",
            "ledger_pnl",
            "/ledger-pnl",
            "PAGE-LEDGER-PNL-001",
            "/api/ledger-pnl/summary",
            "/api/ledger-pnl/formal-financial-indicators",
        ],
        "frontend_route": "/ledger-pnl",
        "primary_api": "/api/ledger-pnl/summary",
        "supporting_apis": [
            "/api/ledger-pnl/dates",
            "/api/ledger-pnl/data",
            "/api/ledger-pnl/formal-financial-indicators",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/audits/2026-05-16-ledger-pnl-formal-financial-indicator-source-gap.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-LEDGER-PNL-001",
            "docs/metric_dictionary.md MTR-LPN-001 through MTR-LPN-003 as candidate metrics with pending_confirmation=true",
            "backend/app/services/ledger_pnl_service.py ledger_pnl.summary / ledger_pnl.data / ledger_pnl.dates",
            "backend/app/services/ledger_pnl_service.py ledger_pnl.formal_financial_indicator_source_contract",
            "backend/app/core_finance/formal_financial_indicators.py GS-LEDGER-PNL-FIN-IND-202603-B contract fixture builder",
            "tests/fixtures/formal_financial_indicators/ledger_pnl_202603_financial_indicator_golden.json GS-LEDGER-PNL-FIN-IND-202603-B",
            "LedgerPnlSummaryPayload",
            "LedgerPnlDataPayload",
            "LedgerPnlFormalFinancialIndicatorContractPayload",
            "/api/ledger-pnl/summary",
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/ledger_pnl.py",
            "backend/app/services/ledger_pnl_service.py",
            "backend/app/core_finance/formal_financial_indicators.py",
            "backend/app/core_finance/config/classification_rules.py",
            "backend/app/services/product_category_source_service.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlCoreClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.css",
            "frontend/src/mocks/ledgerPnlMocks.ts",
        ],
        "test_touchpoints": [
            "tests/test_ledger_pnl_service.py",
            "tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py",
            "tests/test_governance_doc_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/test/LedgerPnlPage.test.tsx",
            "frontend/src/test/LedgerPnlRoutesSmoke.test.tsx",
            "tests/fixtures/formal_financial_indicators/ledger_pnl_202603_financial_indicator_golden.json",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-LEDGER-PNL-001 summary metrics; verify summary cards through page contract, metric dictionary, ledger service tests, and frontend page tests.",
            "Trace /api/ledger-pnl/summary, /api/ledger-pnl/data, and /api/ledger-pnl/formal-financial-indicators through pnlCoreClient, LedgerPnlPage, summary cards, detail tables, source-contract panel, and result_meta display before changing display logic.",
            "Check report_date, report_month, currency filter, yuan-to-yi display conversion, signed amount display, source_version, rule_version, cache_version, trace_id, as_of_date, and date_basis.",
            "Keep GS-LEDGER-PNL-FIN-IND-202603-B as a formal financial indicator source-contract fixture only; it freezes source status and Excel sample values but does not approve system values for formal use.",
        ],
        "guardrails": [
            "Treat MTR-LPN-001 through MTR-LPN-003 as candidate display metrics with pending_confirmation=true.",
            "Do not use ledger summary cards to replace formal PnL, product-category PnL, PnL bridge, or formal financial indicator truth.",
            "Do not render formal_pending financial indicator values as zero; keep value null and show missing-source status until a governed production source is approved.",
            "Do not promote candidate_qdb_aligned values or reconciliation probes into formal financial indicator truth without updating contracts, samples, and tests.",
            "Do not hide result_meta, report_month/report_date binding, stale/fallback/vendor degradation, no-data states, or missing-source states.",
            "Do not recompute ledger summary totals in the frontend; consume /api/ledger-pnl/summary and keep currency filtering bound to the backend read chain.",
        ],
    }
    executive_pnl_attribution_bundle = {
        "page_slug": "executive-pnl-attribution",
        "page_id": "PAGE-EXEC-PNL-ATTR-001",
        "page_name": "Executive PnL Attribution",
        "aliases": [
            "executive-pnl-attribution",
            "executive-pnl-attr",
            "executive_pnl_attribution",
            "PAGE-EXEC-PNL-ATTR-001",
            "/ui/pnl/attribution",
        ],
        "frontend_route": "/dashboard",
        "primary_api": "/ui/pnl/attribution",
        "supporting_apis": [
            "/ui/home/snapshot",
            "/ui/home/overview",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/dashboard_cockpit_contract.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-EXEC-PNL-ATTR-001",
            "docs/metric_dictionary.md MTR-EXEC-101 through MTR-EXEC-106",
            "backend/app/services/executive_service.py executive_pnl_attribution",
            "executive.pnl-attribution result_meta",
            "PnlAttributionPayload",
            "/ui/pnl/attribution",
            "frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/executive.py",
            "backend/app/services/executive_service.py",
            "backend/app/schemas/executive_dashboard.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlAttributionClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx",
            "frontend/src/features/executive-dashboard/selectors/executiveDashboardSelectors.ts",
        ],
        "test_touchpoints": [
            "tests/test_executive_dashboard_endpoints.py",
            "tests/test_executive_service_contract.py",
            "tests/test_executive_release_contract.py",
            "tests/test_golden_samples_capture_ready.py",
            "frontend/src/test/PnlAttributionSection.test.tsx",
            "frontend/src/features/executive-dashboard/components/PnlAttributionSection.states.test.tsx",
            "tests/golden_samples/GS-EXEC-PNL-ATTR-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-EXEC-PNL-ATTR-A"],
        "verification_focus": [
            "Trace /ui/pnl/attribution result_meta through executive_pnl_attribution, getPnlAttribution, PnlAttributionSection, and dashboard snapshot consumers before changing display logic.",
            "Check report_date, analytical basis, segment identity, signed amount display, fallback/stale states, and result_meta.result_kind.",
            "Verify GS-EXEC-PNL-ATTR-A remains an overlay sample and does not redefine formal PnL or bridge totals.",
        ],
        "guardrails": [
            "Treat this as an analytical overlay for management explanation, not formal PnL truth.",
            "Do not use executive analytical overlay values to replace formal bridge evidence or formal PnL totals.",
            "Do not merge this surface with the /pnl-attribution workbench; they have different routes, tests, and metric dictionaries.",
            "Keep analytical overlay wording and result_meta visible even when upstream data is missing.",
            "Do not recompute carry, roll-down, credit, trading, or other segments in the frontend.",
        ],
    }
    pnl_attribution_workbench_bundle = {
        "page_slug": "pnl-attribution",
        "page_id": "PAGE-PNL-ATTR-WB-001",
        "page_name": "PnL Attribution Workbench",
        "aliases": [
            "pnl-attribution",
            "pnl_attribution",
            "/pnl-attribution",
            "PAGE-PNL-ATTR-WB-001",
            "/api/pnl-attribution/volume-rate",
        ],
        "frontend_route": "/pnl-attribution",
        "primary_api": "/api/pnl-attribution/volume-rate",
        "supporting_apis": [
            "/api/pnl-attribution/tpl-market",
            "/api/pnl-attribution/composition",
            "/api/pnl-attribution/summary",
            "/api/pnl-attribution/advanced/carry-rolldown",
            "/api/pnl-attribution/advanced/spread",
            "/api/pnl-attribution/advanced/krd",
            "/api/pnl-attribution/advanced/summary",
            "/api/pnl-attribution/advanced/campisi",
            "/api/pnl-attribution/campisi/four-effects",
            "/api/pnl-attribution/campisi/enhanced",
            "/api/pnl-attribution/campisi/maturity-buckets",
            "/api/pnl-attribution/campisi/decision-grade",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
            "docs/plans/2026-05-15-campisi-attribution-audit.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-PNL-ATTR-WB-001",
            "docs/metric_dictionary.md MTR-PAT-001 through MTR-PAT-006, MTR-PAT-101 through MTR-PAT-103, MTR-PAT-201 through MTR-PAT-205, and MTR-PAT-301 through MTR-PAT-304",
            "backend/app/core_finance/pnl_attribution/workbench.py build_volume_rate_attribution / build_tpl_market_correlation / build_pnl_composition",
            "backend/app/services/pnl_attribution_service.py volume_rate_attribution_envelope and advanced attribution envelopes",
            "backend/app/api/routes/pnl_attribution.py /api/pnl-attribution/*",
            "backend/app/api/routes/campisi_attribution.py Campisi endpoints",
            "VolumeRateAttributionPayload",
            "TPLMarketCorrelationPayload",
            "PnlCompositionPayload",
            "AdvancedAttributionSummary",
            "frontend/src/api/pnlAttributionClient.ts",
            "frontend/src/features/pnl-attribution/pages/PnlAttributionPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/pnl_attribution.py",
            "backend/app/api/routes/campisi_attribution.py",
            "backend/app/services/pnl_attribution_service.py",
            "backend/app/services/campisi_attribution_service.py",
            "backend/app/core_finance/pnl_attribution/workbench.py",
            "backend/app/core_finance/campisi.py",
            "backend/app/schemas/pnl_attribution.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlAttributionClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/pnl-attribution/pages/PnlAttributionPage.tsx",
            "frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx",
            "frontend/src/features/pnl-attribution/components/AdvancedAttributionChart.tsx",
            "frontend/src/features/pnl-attribution/components/TPLMarketChart.tsx",
            "frontend/src/features/pnl-attribution/components/CampisiAttributionPanel.tsx",
        ],
        "test_touchpoints": [
            "tests/test_pnl_attribution_api_contract.py",
            "tests/test_pnl_attribution_workbench_contract.py",
            "tests/test_pnl_attribution_service_explicit_numeric.py",
            "tests/test_pnl_attribution_numeric_migration.py",
            "tests/test_advanced_attribution_contract.py",
            "tests/test_result_meta_source_surface.py",
            "backend/tests/services/test_pnl_attribution_campisi.py",
            "frontend/src/test/PnlAttributionPage.test.tsx",
            "frontend/src/features/pnl-attribution/components/PnlAttributionView.test.ts",
            "frontend/src/test/PnlCompositionChart.test.tsx",
            "frontend/src/test/TPLMarketChart.test.tsx",
            "frontend/src/test/AdvancedAttributionChart.test.tsx",
            "frontend/src/test/CampisiAttributionPanel.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-PNL-ATTR-WB-001; verify through page contract, metric dictionary, route/service tests, result_meta checks, and frontend workbench tests.",
            "Trace active-tab payloads through pnlAttributionClient, PnlAttributionView state, current_view_meta, charts, tables, and advanced/Campisi panels before changing display logic.",
            "Check amount, percent, bp, current/previous period, generated_at, quality_flag, fallback_mode, and null-vs-zero semantics for each workbench tab.",
            "Keep product-category, formal attribution, advanced attribution, and Campisi panels visibly scoped to their own basis and provenance.",
        ],
        "guardrails": [
            "Do not use this workbench to replace the formal PnL overview or the executive analytical overlay.",
            "Do not merge /pnl-attribution with /ui/pnl/attribution; they have different consumers, basis labels, and tests.",
            "Do not recompute volume-rate, TPL-market, composition, advanced, KRD, or Campisi outputs in the frontend.",
            "Do not hide generated_at, quality_flag, fallback_mode, no-data, stale, or provenance boundaries on the active tab.",
            "Treat KRD yield_change unit wording as a known follow-up gap unless the field contract is updated with explicit bp naming.",
        ],
    }
    operations_analysis_bundle = {
        "page_slug": "operations-analysis",
        "page_id": "PAGE-OPS-001",
        "page_name": "Operations Analysis",
        "aliases": [
            "operations-analysis",
            "/operations-analysis",
            "operations_analysis",
            "PAGE-OPS-001",
            "/ui/pnl/product-category",
        ],
        "frontend_route": "/operations-analysis",
        "primary_api": "/ui/pnl/product-category",
        "supporting_apis": [
            "/ui/pnl/product-category/dates",
            "/ui/balance-analysis/dates",
            "/ui/balance-analysis/overview",
            "/ui/preview/source-foundation",
            "/ui/preview/macro-foundation",
            "/ui/macro/choice-series/latest",
            "/ui/market-data/fx/formal-status",
            "/ui/news/choice-events/latest",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/golden_sample_plan.md",
            "docs/live_route_maturity.md",
            "docs/GPT55_FRONTEND_DESIGN_CONTEXT.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-OPS-001",
            "docs/metric_dictionary.md PAGE-OPS-001 reuses MTR-PCP-001 through MTR-PCP-003 from product-category headline truth",
            "docs/metric_dictionary.md balance overview is supplemental topic-entry evidence with MTR-BAL-001, MTR-BAL-002, MTR-BAL-003, MTR-BAL-101, and MTR-BAL-102",
            "docs/metric_dictionary.md GAP-OPS-MACRO-FX keeps source preview, macro, FX, news, and operational strips outside formal metric promotion",
            "backend/app/services/product_category_pnl_service.py ProductCategoryPnlPayload headline totals",
            "backend/app/services/balance_analysis_service.py BalanceAnalysisOverviewPayload supplemental topic-entry evidence",
            "backend/app/services/macro_vendor_service.py preview and Choice macro analytical evidence",
            "backend/app/services/choice_news_service.py Choice news analytical evidence",
            "frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/product_category_pnl.py",
            "backend/app/services/product_category_pnl_service.py",
            "backend/app/api/routes/balance_analysis.py",
            "backend/app/services/balance_analysis_service.py",
            "backend/app/api/routes/source_preview.py",
            "backend/app/api/routes/macro_vendor.py",
            "backend/app/api/routes/choice_news.py",
            "backend/app/schemas/product_category_pnl.py",
            "backend/app/schemas/balance_analysis.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/productCategoryClient.ts",
            "frontend/src/api/balanceAnalysisClient.ts",
            "frontend/src/api/marketDataClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx",
            "frontend/src/features/workbench/pages/OperationsAnalysisPage.css",
            "frontend/src/mocks/navigation.ts",
        ],
        "test_touchpoints": [
            "frontend/src/test/OperationsAnalysisPage.test.tsx",
            "frontend/src/test/OperationsAnalysisPage.governed.test.tsx",
            "frontend/src/test/navigation.test.ts",
            "frontend/src/test/RouteRegistry.test.tsx",
            "frontend/src/test/WorkbenchShell.test.tsx",
            "tests/test_governance_doc_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "tests/test_product_category_pnl_flow.py",
            "tests/test_balance_analysis_api.py",
            "tests/test_golden_samples_capture_ready.py",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-PROD-CAT-PNL-A",
            "tests/golden_samples/GS-BAL-OVERVIEW-A",
        ],
        "verification_focus": [
            "Trace /ui/pnl/product-category headline totals through OperationsAnalysisPage primary KPI cards before changing PAGE-OPS-001 display logic.",
            "Verify balance overview remains supplemental topic-entry evidence and routes users to /balance-analysis for formal workbook/detail truth.",
            "Check source preview, macro, FX, and news sections keep analytical/preview/vendor/result_meta context and do not promote new MTR-OPS-* metrics.",
            "Keep temporary-exception labels and static/mixed-source section boundaries visible until PAGE-OPS-001 exits the live-route maturity exception.",
        ],
        "guardrails": [
            "PAGE-OPS-001 is a temporary-exception mixed-source page; do not claim full page-level formal closure from its aggregate first screen.",
            "Do not create or promote MTR-OPS-* metrics; the current formal operating KPI cards reuse MTR-PCP-001, MTR-PCP-002, and MTR-PCP-003.",
            "Balance overview is supplemental topic-entry evidence, not a replacement for PAGE-BALANCE-001 workbook/detail truth.",
            "Do not treat source preview, macro, FX, Choice news, static watch items, or calendar examples as formal business metric truth.",
            "Do not hide GAP-OPS-MACRO-FX, mock-mode, static-example, result_meta, fallback, stale, or vendor-status boundaries.",
        ],
    }
    liability_analytics_bundle = {
        "page_slug": "liability-analytics",
        "page_id": "PAGE-LIAB-ANALYTICS-001",
        "page_name": "Liability Analytics",
        "aliases": [
            "liability-analytics",
            "/liability-analytics",
            "liability_analytics",
            "PAGE-LIAB-ANALYTICS-001",
            "/api/risk/buckets",
        ],
        "frontend_route": "/liability-analytics",
        "primary_api": "/api/risk/buckets",
        "supporting_apis": [
            "/api/analysis/yield_metrics",
            "/api/analysis/yield-by-period",
            "/api/analysis/liabilities/counterparty",
            "/api/liabilities/monthly",
            "/ui/liability/business-context",
            "/api/analysis/liabilities/cockpit-warnings",
            "/api/analysis/liabilities/contribution-split",
            "/ui/balance-analysis/dates",
            "/ui/balance-analysis/overview",
            "/api/analysis/adb/monthly",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
            "docs/DOCUMENT_AUTHORITY.md",
            "docs/V2_V3_PARITY_MATRIX.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-LIAB-ANALYTICS-001",
            "docs/metric_dictionary.md MTR-LIAB-001 through MTR-LIAB-007",
            "docs/live_route_maturity.md governed-mixed-source / compatibility boundary",
            "backend/app/core_finance/liability_analytics_compat.py compute_liability_risk_buckets / compute_liability_yield_metrics",
            "backend/app/services/liability_analytics_service.py liability_analytics.risk_buckets",
            "backend/app/api/routes/liability_analytics.py /api/risk/buckets and compatibility routes",
            "frontend/src/api/liabilityAdbClient.ts liability API client",
            "frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/liability_analytics.py",
            "backend/app/services/liability_analytics_service.py",
            "backend/app/core_finance/liability_analytics_compat.py",
            "backend/app/schemas/liability_analytics.py",
            "backend/app/repositories/liability_analytics_repo.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/liabilityAdbClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx",
            "frontend/src/features/liability-analytics/pages/liabilityAnalyticsPageModel.ts",
            "frontend/src/features/liability-analytics/adapters/liabilityAdapter.ts",
        ],
        "test_touchpoints": [
            "tests/test_liability_analytics_api.py",
            "tests/test_liability_analytics_envelope_contract.py",
            "tests/test_liability_analytics_compat_contract.py",
            "tests/test_liability_analytics_unit_semantics.py",
            "tests/test_liability_analytics_numeric_migration.py",
            "tests/test_result_meta_on_all_ui_endpoints.py",
            "tests/test_result_meta_source_surface_followup.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/test/LiabilityAnalyticsPage.test.tsx",
            "frontend/src/features/liability-analytics/adapters/liabilityAdapter.test.ts",
            "frontend/src/features/liability-analytics/pages/liabilityAnalyticsPageModel.test.ts",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-LIAB-ANALYTICS-001; verify via page contract, metric dictionary, route/service tests, result_meta checks, and frontend page tests.",
            "Trace risk, yield, counterparty, monthly, business-context, cockpit-warning, and contribution payloads through liabilityAdbClient, adapters, page read model, and LiabilityAnalyticsPage before changing display logic.",
            "Check amount display conversion, percent/bp semantics, report_date binding, monthly average-balance semantics, fallback_mode, vendor_status, quality_flag, and missing-result-meta states.",
            "Keep actual compatibility API paths distinct from the page-contract /ui liability target paths until the routing contract is reconciled.",
        ],
        "guardrails": [
            "Treat the page as governed-mixed-source and compatibility analytical, not formal balance truth or formal PnL truth.",
            "Do not hide mixed-source, compatibility, synthetic, fallback, stale, or pending-definition boundaries from users.",
            "Do not promote reserved or compatibility endpoints to formal truth without updating page contracts, metric dictionary, lineage, and tests.",
            "Do not recompute liability cost, NIM, maturity pressure, counterparty concentration, monthly averages, or bucket definitions in the frontend.",
            "Use result_meta and no-data/error states to distinguish backend-owned values from compatibility or derived sections.",
        ],
    }
    pnl_bridge_bundle = {
        "page_slug": "pnl-bridge",
        "page_id": "PAGE-BRIDGE-001",
        "page_name": "PnL Bridge",
        "aliases": [
            "pnl-bridge",
            "/pnl-bridge",
            "pnl_bridge",
            "PAGE-BRIDGE-001",
            "/api/pnl/bridge",
        ],
        "frontend_route": "/pnl-bridge",
        "primary_api": "/api/pnl/bridge",
        "supporting_apis": [
            "/api/pnl/dates",
            "/api/pnl/refresh",
            "/api/pnl/refresh-status",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/calc_rules.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-BRIDGE-001",
            "docs/metric_dictionary.md MTR-BRG-001 through MTR-BRG-014 and MTR-BRG-101 through MTR-BRG-105",
            "backend/app/schema_registry/duckdb/07_pnl_materialize.sql fact_formal_pnl_fi + fact_nonstd_pnl_bridge",
            "backend/app/core_finance/pnl_bridge.py build_pnl_bridge_rows",
            "backend/app/services/pnl_bridge_service.py pnl_bridge_envelope",
            "PnlBridgePayload",
            "/api/pnl/bridge",
            "frontend/src/features/pnl/PnlBridgePage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/pnl.py",
            "backend/app/services/pnl_bridge_service.py",
            "backend/app/core_finance/pnl_bridge.py",
            "backend/app/schemas/pnl_bridge.py",
            "backend/app/repositories/pnl_repo.py",
            "backend/app/repositories/balance_analysis_repo.py",
            "backend/app/repositories/yield_curve_repo.py",
            "backend/app/tasks/pnl_materialize.py",
            "backend/app/schema_registry/duckdb/07_pnl_materialize.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlCoreClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/pnl/PnlBridgePage.tsx",
            "frontend/src/features/pnl/adapters/pnlBridgeAdapter.ts",
        ],
        "test_touchpoints": [
            "tests/test_pnl_api_contract.py",
            "tests/test_pnl_bridge_core.py",
            "tests/test_pnl_bridge_curve_effects.py",
            "tests/test_pnl_bridge_fx_translation.py",
            "tests/test_pnl_bridge_with_curve.py",
            "tests/test_pnl_bridge_numeric_migration.py",
            "tests/test_pnl_bridge_service_boundaries.py",
            "frontend/src/test/PnlBridgePage.test.tsx",
            "tests/test_golden_samples_capture_ready.py",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-BRIDGE-A",
            "tests/golden_samples/GS-BRIDGE-WARN-B",
        ],
        "verification_focus": [
            "Trace /api/pnl/bridge result_meta through getPnlBridge, adaptPnlBridge, PnlBridgePage, and the formal meta panel before changing display logic.",
            "Check report_date, requested/resolved date behavior, source_version, rule_version, cache_version, trace_id, and curve/balance fallback visibility.",
            "Check units and null-vs-zero semantics for beginning/ending dirty market value, carry, roll-down, curve effects, FX, actual, explained, residual, and residual ratio.",
            "Keep bridge warnings and warning-profile golden samples visible; warning quality is valid governed output, not an error to hide.",
        ],
        "guardrails": [
            "Do not hide bridge warnings, balance lineage fallback warnings, curve fallback, vendor stale, or quality_flag=warning states.",
            "Do not use PnL Bridge to replace the formal PnL detail page or ledger-level PnL evidence.",
            "Do not synthesize future-only attribution sections as current governed bridge output.",
            "Do not recompute governed totals, residuals, or quality flags in the frontend; consume backend-owned PnlBridgePayload values.",
            "Preserve balance-analysis current/prior input lineage and yield-curve fallback/vendor-stale visibility when auditing this page.",
        ],
    }
    risk_tensor_bundle = {
        "page_slug": "risk-tensor",
        "page_id": "PAGE-RISK-001",
        "page_name": "Risk Tensor",
        "aliases": [
            "risk-tensor",
            "/risk-tensor",
            "risk_tensor",
            "PAGE-RISK-001",
            "/api/risk/tensor",
        ],
        "frontend_route": "/risk-tensor",
        "primary_api": "/api/risk/tensor",
        "supporting_apis": [
            "/api/risk/tensor/dates",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/calc_rules.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-RISK-001",
            "docs/metric_dictionary.md MTR-RSK-001 / MTR-RSK-001R / MTR-RSK-021-023",
            "backend/app/schema_registry/duckdb/04_risk_tensor.sql fact_formal_risk_tensor_daily",
            "backend/app/tasks/risk_tensor_materialize.py materialize_risk_tensor_facts",
            "backend/app/services/risk_tensor_service.py risk_tensor_envelope",
            "RiskTensorPayload",
            "/api/risk/tensor",
            "frontend/src/features/risk-tensor/RiskTensorPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/risk_tensor.py",
            "backend/app/services/risk_tensor_service.py",
            "backend/app/repositories/risk_tensor_repo.py",
            "backend/app/schemas/risk_tensor.py",
            "backend/app/core_finance/risk_tensor.py",
            "backend/app/core_finance/risk_tensor_regulatory_scope.py",
            "backend/app/tasks/risk_tensor_materialize.py",
            "backend/app/schema_registry/duckdb/04_risk_tensor.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/executiveClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/risk-tensor/RiskTensorPage.tsx",
            "frontend/src/features/risk-tensor/RiskTensorPage.css",
        ],
        "test_touchpoints": [
            "tests/test_risk_tensor_api.py",
            "tests/test_risk_tensor_service.py",
            "tests/test_risk_tensor_repo.py",
            "tests/test_risk_tensor_core.py",
            "tests/test_risk_tensor_materialize.py",
            "tests/test_risk_tensor_numeric_migration.py",
            "tests/test_risk_tensor_liquidity.py",
            "frontend/src/test/RiskTensorPage.test.tsx",
            "tests/test_golden_samples_capture_ready.py",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-RISK-A",
            "tests/golden_samples/GS-RISK-WARN-B",
        ],
        "verification_focus": [
            "Trace /api/risk/tensor result_meta through getRiskTensor, RiskTensorPage, and the quality/detail surfaces before changing display logic.",
            "Check report_date, source_version, upstream_source_version, liability_source_version, rule_version, cache_version, and trace_id visibility.",
            "Check units and null-vs-zero semantics for DV01, regulatory_dv01, KRD, CS01, convexity, HHI, liquidity gaps, and duration-scope fields.",
            "Keep warning quality visible; latest data can be formal while still requiring user-visible warning context.",
        ],
        "guardrails": [
            "Do not recompute KRD, DV01, CS01, convexity, liquidity gaps, or issuer concentration in the frontend.",
            "Do not use /ui/risk/overview as formal PAGE-RISK-001 evidence; it is a separate overview surface.",
            "Do not backfill regulatory_dv01 from portfolio_dv01 or hide missing regulatory scope.",
            "Keep warning quality and warnings visible, including tenor remaps, unsupported tenor exclusions, and stale/fallback report-date blocks.",
            "Do not synthesize maturity dates for no-maturity rows; preserve duration denominator exclusions and disclose excluded market value/count.",
            "DV01 totals remain row-DV01 sourced even when duration denominator excludes rows.",
        ],
    }
    bond_dashboard_bundle = {
        "page_slug": "bond-dashboard",
        "page_id": "PAGE-BOND-001",
        "page_name": "Bond Dashboard",
        "aliases": [
            "bond-dashboard",
            "bond_dashboard",
            "/bond-dashboard",
            "PAGE-BOND-001",
            "/api/bond-dashboard/headline-kpis",
            "/api/bond-dashboard/risk-indicators",
        ],
        "frontend_route": "/bond-dashboard",
        "primary_api": "/api/bond-dashboard/headline-kpis",
        "supporting_apis": [
            "/api/bond-dashboard/dates",
            "/api/bond-dashboard/asset-structure",
            "/api/bond-dashboard/yield-distribution",
            "/api/bond-dashboard/portfolio-comparison",
            "/api/bond-dashboard/spread-analysis",
            "/api/bond-dashboard/maturity-structure",
            "/api/bond-dashboard/industry-distribution",
            "/api/bond-dashboard/risk-indicators",
            "/api/bond-dashboard/business-type-metrics",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/data_contracts.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-BOND-001",
            "docs/metric_dictionary.md MTR-BOND-001 through MTR-BOND-004 as candidate metrics with pending_confirmation=true",
            "docs/metric_dictionary.md GAP-BOND-DASH-HL and GAP-BOND-DASH-RISK",
            "docs/golden_sample_catalog.md GS-BOND-HEADLINE-A freezes page-level DTO truth only",
            "backend/app/services/bond_dashboard_service.py bond_dashboard.headline_kpis with source_surface=\"bond_analytics\"",
            "backend/app/services/bond_dashboard_service.py bond_dashboard.risk_indicators",
            "backend/app/schemas/bond_dashboard.py BondDashboardHeadlinePayload",
            "backend/app/schemas/bond_dashboard.py BondDashboardRiskIndicatorsPayload",
            "backend/app/repositories/bond_analytics_repo.py fact_formal_bond_analytics_daily read model",
            "/api/bond-dashboard/headline-kpis",
            "frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/bond_dashboard.py",
            "backend/app/services/bond_dashboard_service.py",
            "backend/app/schemas/bond_dashboard.py",
            "backend/app/repositories/bond_analytics_repo.py",
            "backend/app/schema_registry/duckdb/05_bond_analytics.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/bondAnalyticsClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx",
            "frontend/src/features/bond-dashboard/components/HeadlineKpis.tsx",
            "frontend/src/features/bond-dashboard/components/RiskIndicatorsPanel.tsx",
        ],
        "test_touchpoints": [
            "tests/test_bond_dashboard_api_contract.py",
            "tests/test_bond_dashboard_headlines_contract.py",
            "tests/test_bond_analytics_api.py",
            "tests/test_result_meta_source_surface_followup.py",
            "tests/test_golden_samples_capture_ready.py",
            "frontend/src/test/BondDashboardPage.test.tsx",
            "tests/golden_samples/GS-BOND-HEADLINE-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-BOND-HEADLINE-A"],
        "verification_focus": [
            "Trace /api/bond-dashboard/headline-kpis result_meta through get_bond_dashboard_headline_kpis, getBondDashboardHeadlineKpis, HeadlineKpis, the candidate-boundary notice, and first-screen conclusion before changing display logic.",
            "Check report_date, previous report date, source_surface, basis/formal_use_allowed, source/rule/cache versions, data_source, yuan-to-yi display, pct/ratio semantics, DV01 display, and empty-state behavior.",
            "Verify GS-BOND-HEADLINE-A remains a page-level DTO sample for headline_kpis and does not approve dictionary-level MTR-BOND-* binding or risk-card equivalence.",
            "Trace /api/bond-dashboard/risk-indicators separately before comparing with PAGE-RISK-001; risk-card fields are not automatically GS-RISK-A / risk-tensor truth.",
        ],
        "guardrails": [
            "Treat MTR-BOND-001 through MTR-BOND-004 as candidate display metrics with pending_confirmation=true.",
            "Do not use GS-BOND-HEADLINE-A to approve dictionary-level MTR-BOND-* bindings; it freezes the page headline DTO and empty-state behavior only.",
            "Do not claim bond-dashboard headline totals are equivalent to MTR-BAL-* formal balance metrics without a separate approved contract.",
            "Do not claim bond-dashboard risk indicators are equivalent to GS-RISK-A or PAGE-RISK-001 risk tensor metrics without a separate approved contract.",
            "Do not recompute headline, risk, duration, yield, DV01, spread, asset-structure, maturity, or industry totals in the frontend.",
            "Keep result_meta, source_surface, data_source, stale/fallback/vendor degradation, empty states, and candidate-boundary messaging visible.",
        ],
    }
    positions_bundle = {
        "page_slug": "positions",
        "page_id": "PAGE-POS-001",
        "page_name": "Positions",
        "aliases": [
            "positions",
            "/positions",
            "PAGE-POS-001",
            "/api/positions/bonds",
            "/api/positions/interbank",
        ],
        "frontend_route": "/positions",
        "primary_api": "/api/positions/bonds",
        "supporting_apis": [
            "/api/positions/bonds/sub_types",
            "/api/positions/interbank/product_types",
            "/api/positions/interbank",
            "/api/positions/counterparty/bonds",
            "/api/positions/counterparty/interbank/split",
            "/api/positions/stats/rating",
            "/api/positions/stats/industry",
            "/api/positions/customer/details",
            "/api/positions/customer/trend",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-POS-001",
            "docs/metric_dictionary.md MTR-POS-001 and MTR-POS-002 as candidate metrics with pending_confirmation=true and bound_sample_id=none",
            "docs/metric_dictionary.md GAP-POS-LIST",
            "GET /ui/balance-analysis/dates",
            "balance-analysis dates supply the default report_dates selector for this page",
            "backend/app/services/positions_service.py positions.bonds.list / positions.interbank.list",
            "backend/app/services/positions_service.py positions.counterparty.bonds / positions.stats.rating / positions.customer.details",
            "backend/app/schemas/positions.py BondPositionsPageResponse",
            "backend/app/schemas/positions.py InterbankPositionsPageResponse",
            "backend/app/repositories/positions_repo.py snapshot read model",
            "/api/positions/bonds",
            "frontend/src/features/positions/components/PositionsView.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/positions.py",
            "backend/app/services/positions_service.py",
            "backend/app/schemas/positions.py",
            "backend/app/repositories/positions_repo.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/positionsClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/positions/pages/PositionsPage.tsx",
            "frontend/src/features/positions/components/PositionsView.tsx",
            "frontend/src/features/positions/components/CustomerDetailModal.tsx",
            "frontend/src/features/positions/components/RatingDistributionCard.tsx",
            "frontend/src/features/positions/components/IndustryDistributionCard.tsx",
        ],
        "test_touchpoints": [
            "tests/test_positions_api_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "tests/test_governance_doc_contract.py",
            "frontend/src/test/PositionsView.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
            "frontend/src/test/CustomerDetailModal.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-POS-001; verify list/count behavior through page contract, metric dictionary, positions API contract tests, and frontend page tests.",
            "Trace /api/positions/bonds and /api/positions/interbank through positions_service, positionsClient, PositionsView, table totals, candidate-boundary copy, and result_meta display before changing display logic.",
            "Check report_date selection from balance-analysis dates, explicit URL report_date behavior, list request gating, start_date/end_date interval semantics for counterparty/stat endpoints, and customer drilldown report_date behavior.",
            "Verify GAP-POS-LIST remains explicit: positions list/stat DTOs are page evidence but not approved formal business metric truth or dedicated sample truth.",
        ],
        "guardrails": [
            "Treat MTR-POS-001 and MTR-POS-002 as candidate display metrics with pending_confirmation=true and bound_sample_id=none.",
            "Keep GAP-POS-LIST visible in the page contract and do not promote positions list/count DTOs into formal metric truth without new contracts, samples, and tests.",
            "Do not use positions list totals to replace formal PnL, product-category PnL, bond-dashboard headline truth, or balance-analysis truth.",
            "Do not fire list requests without an explicit report_date; preserve balance-analysis dates as the default selector source and keep that dual-source boundary visible.",
            "Do not recompute cross-page scale, PnL, rating, industry, counterparty, or customer metrics in the frontend; consume positions_service envelopes and show result_meta/stale/fallback states.",
            "Keep filter context fields excluded from MTR-* promotion, including date ranges, business type, product type, customer search, direction, and counterparty filters.",
        ],
    }
    market_data_bundle = {
        "page_slug": "market-data",
        "page_id": "PAGE-MKT-001",
        "page_name": "Market Data",
        "aliases": [
            "market-data",
            "market_data",
            "/market-data",
            "PAGE-MKT-001",
            "/ui/preview/macro-foundation",
            "/ui/market-data/rates",
            "/ui/market-data/fx/formal-status",
            "/ui/market-data/ncd-funding-proxy",
            "/ui/market-data/livermore",
        ],
        "frontend_route": "/market-data",
        "primary_api": "/ui/preview/macro-foundation",
        "supporting_apis": [
            "/ui/market-data/rates",
            "/ui/macro/choice-series/latest",
            "/ui/market-data/fx/formal-status",
            "/ui/market-data/fx/analytical",
            "/ui/market-data/ncd-funding-proxy",
            "/api/macro-bond-linkage",
            "/ui/macro/choice-refresh/status/{run_id}",
            "/ui/market-data/livermore",
            "/ui/market-data/livermore/stock-detail",
            "/ui/market-data/livermore/candidate-history",
            "/ui/market-data/livermore/sector-rank-series",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/DOCUMENT_AUTHORITY.md",
            "docs/plans/market-workbench-cursor-prompts.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-MKT-001",
            "docs/metric_dictionary.md MTR-MKT-001 macro catalog count is candidate with pending_confirmation=true and bound_sample_id=none",
            "docs/metric_dictionary.md GAP-MKT-DATA: no full-page formal metric dictionary and no full-page capture-ready golden sample",
            "GET /ui/market-data/rates is a formal rates fragment only, not full-page formal truth",
            "backend/app/services/macro_vendor_service.py market_data_rates / macro_foundation / Choice macro analytical evidence",
            "backend/app/services/market_data_ncd_proxy_service.py ncd-funding-proxy returns Shibor funding proxy evidence, not an actual NCD matrix",
            "backend/app/services/market_data_livermore_service.py Livermore analytical surface with backend unsupported_outputs, rule_readiness, and data_gaps",
            "BondFuturesTable / BondTradeDetail / CreditBondTradesTable remain source-pending terminal surfaces",
            "frontend/src/api/marketDataClient.ts getMacroFoundation, getMarketDataRates, getFxAnalytical, getNcdFundingProxy, getMacroBondLinkageAnalysis, and getLivermoreStrategy",
            "frontend/src/features/market-data/hooks/useMarketDataPageData.ts mounted page queries",
            "frontend/src/features/market-data/pages/MarketDataPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/macro_vendor.py",
            "backend/app/api/routes/macro_bond_linkage.py",
            "backend/app/api/routes/market_data_ncd_proxy.py",
            "backend/app/api/routes/market_data_livermore.py",
            "backend/app/services/macro_vendor_service.py",
            "backend/app/services/macro_bond_linkage_service.py",
            "backend/app/services/market_data_ncd_proxy_service.py",
            "backend/app/services/market_data_livermore_service.py",
            "backend/app/services/livermore_signal_confluence_service.py",
            "backend/app/schemas/macro_vendor.py",
            "backend/app/schemas/macro_bond_linkage.py",
            "backend/app/schemas/ncd_proxy.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/marketDataClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/market-data/hooks/useMarketDataPageData.ts",
            "frontend/src/features/market-data/pages/MarketDataPage.tsx",
            "frontend/src/features/market-data/pages/marketDataPageModel.ts",
            "frontend/src/features/market-data/pages/MarketDataHeroSection.tsx",
            "frontend/src/features/market-data/components/RateQuoteTable.tsx",
            "frontend/src/features/market-data/components/MoneyMarketTable.tsx",
            "frontend/src/features/market-data/components/NcdMatrix.tsx",
            "frontend/src/features/market-data/components/LivermoreStrategyPanel.tsx",
            "frontend/src/features/market-data/components/LiveResultMetaStrip.tsx",
        ],
        "test_touchpoints": [
            "tests/test_result_meta_on_all_ui_endpoints.py",
            "tests/test_market_data_ncd_proxy_api.py",
            "tests/test_market_data_livermore_api.py",
            "tests/test_market_data_livermore_risk_exit_source.py",
            "tests/test_macro_bond_linkage.py",
            "tests/test_fx_analytical_view_api.py",
            "frontend/src/test/MarketDataPage.test.tsx",
            "frontend/src/features/market-data/pages/marketDataPageModel.test.ts",
            "frontend/src/test/RouteRegistry.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-MKT-001; verify through page contract, metric dictionary, result_meta endpoint checks, market-data route tests, and frontend page/model tests.",
            "Trace macro catalog count through /ui/preview/macro-foundation, getMacroFoundation, useMarketDataPageData, marketDataPageModel, and MarketDataPage before changing MTR-MKT-001 display logic.",
            "Trace /ui/market-data/rates separately as a formal rates fragment and keep result_meta.basis / formal_use_allowed / emptyReason visible; do not use it as full-page formal proof.",
            "Check analytical, preview, proxy, stale, fallback, blocked, source-pending, and no-data states across FX, NCD proxy, macro-bond linkage, terminal tables, and Livermore panels.",
        ],
        "guardrails": [
            "PAGE-MKT-001 is mixed-source; do not claim full-page formal truth from macro preview, formal rates fragment, FX analytical, NCD proxy, or Livermore outputs.",
            "Do not promote new MTR-* rows, formal rates values, filter context fields, source-pending panels, or analytical/proxy outputs without approved metric dictionary, lineage, sample, and tests.",
            "Do not fill missing rate quote, money market, bond futures, bond trade detail, credit trade, FX, or macro rows with static demo backfill in real mode.",
            "Treat NCD output as Shibor funding proxy evidence unless a separate approved actual NCD term-by-rating matrix contract exists.",
            "Treat Livermore risk_exit as backend-owned and gated by unsupported_outputs, rule_readiness, data_gaps, ACTIVE A-share holdings, entry-cost, and K-line supplement readiness.",
            "Keep getFxFormalStatus scoped as a formal FX status endpoint; the current MarketDataPage implementation does not independently mount it as full-page formal truth.",
        ],
    }
    macro_toolkit_bundle = {
        "page_slug": "macro-toolkit",
        "page_id": "PAGE-MACRO-TOOLKIT-001",
        "page_name": "Macro Toolkit",
        "aliases": [
            "macro-toolkit",
            "macro_toolkit",
            "/macro-toolkit",
            "PAGE-MACRO-TOOLKIT-001",
            "/ui/macro/toolkit/analysis",
            "/ui/macro/toolkit/scripts",
            "/ui/macro/toolkit/analysis/strategy-summaries",
        ],
        "frontend_route": "/macro-toolkit",
        "primary_api": "/ui/macro/toolkit/analysis",
        "supporting_apis": [
            "/ui/macro/toolkit/analysis/strategy-summaries",
            "/ui/macro/toolkit/scripts",
            "/ui/macro/toolkit/adversarial-signal",
            "POST /ui/macro/toolkit/scripts/{name}/run",
            "POST /ui/macro/toolkit/cffex-member-rank/refresh",
            "POST /ui/macro/toolkit/choice-stock/refresh",
            "GET /ui/macro/toolkit/choice-stock/refresh-status",
            "POST /ui/macro/toolkit/source-backfill/refresh",
            "POST /ui/macro/toolkit/commodity-futures/refresh",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
            "docs/golden_sample_catalog.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-MACRO-TOOLKIT-001 candidate tooling surface",
            "docs/metric_dictionary.md /macro-toolkit has no MTR-* and no MTR-MACRO-*; tooling/analysis status evidence is not formal metric truth",
            "docs/metric_dictionary.md coverage.hit_rate, script counts, strategy counts, real-chain counts, refresh row counts, and source/version/run_id are status/tracing evidence only",
            "GET /ui/macro/toolkit/analysis?detail=core returns macro_toolkit.analysis for analytical/tooling evidence",
            "GET /ui/macro/toolkit/analysis/strategy-summaries returns macro_toolkit.analysis.strategy_summaries for strategy supply evidence",
            "GET /ui/macro/toolkit/scripts returns macro_toolkit.scripts for script registry and operation/script outputs",
            "POST refresh and script-run endpoints return operation/script outputs only; run_id, started_at, and finished_at are operational trace fields",
            "backend/app/api/routes/macro_toolkit.py macro_toolkit.analysis / macro_toolkit.scripts / macro_toolkit.choice_stock_refresh / macro_toolkit.cffex_member_rank_refresh",
            "backend/app/services/macro_toolkit_service.py script registry, refresh status, and run payload helpers",
            "frontend/src/api/macroToolkitClient.ts getMacroToolkitAnalysis, getMacroToolkitStrategySummaries, getMacroToolkitScripts, runMacroToolkitScript, and refresh clients",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx MacroToolkitContractBoundary keeps formal_use_allowed=false visible",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/macro_toolkit.py",
            "backend/app/services/macro_toolkit_service.py",
            "backend/app/core_finance/macro",
            "backend/app/core_finance/macro/toolkit/scripts",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/macroToolkitClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_macro_toolkit_scripts.py",
            "tests/test_macro_toolkit_choice_stock_refresh_overview.py",
            "tests/test_macro_toolkit_factor_snapshot_dates.py",
            "tests/test_macro_toolkit_a_share_risk.py",
            "tests/test_macro_query_contract_smoke.py",
            "tests/test_write_route_auth_contract.py",
            "tests/test_governance_doc_contract.py",
            "frontend/src/test/MacroToolkitPage.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
            "frontend/src/test/navigation.test.ts",
            "frontend/src/test/macroToolkitClient.test.ts",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-MACRO-TOOLKIT-001; verify through page contract, metric dictionary, route tests, macro toolkit API tests, auth tests, and frontend MacroToolkitPage tests.",
            "Trace analysis through /ui/macro/toolkit/analysis, macro_toolkit.analysis result_meta, getMacroToolkitAnalysis, MacroToolkitPage query state, and MacroToolkitContractBoundary before changing display logic.",
            "Trace script registry, script run, refresh, and refresh-status behavior separately as operational evidence; do not use operation/script outputs as formal metric truth.",
            "Check loading, empty, stale, fallback, source/version/run_id, deferred section, permission, and no-data states across analysis, strategy, script, and refresh sections.",
        ],
        "guardrails": [
            "PAGE-MACRO-TOOLKIT-001 is tooling/analysis only; do not claim formal metric truth from macro analysis, script registry, refresh status, strategy summaries, or operation/script outputs.",
            "Do not treat analysis cards, sample strategies, script outputs, vendor reads, refresh counts, source/version/run_id, or coverage.hit_rate as investment recommendations or an executable trade signal.",
            "Do not promote any macro toolkit field to MTR-* or MTR-MACRO-* without approved metric dictionary rows, units, precision/null rules, lineage, samples or candidate decision, and tests.",
            "Do not fill missing macro analysis, strategy, script, vendor, or refresh evidence with static demo backfill in real mode.",
            "Do not hide fallback, stale, source gaps, permission failures, no-data, or deferred-section states behind a successful page shell.",
            "Do not recompute macro indicators, strategy counts, refresh row counts, or script-derived measures in the frontend; consume backend envelopes and keep result_meta visible.",
        ],
    }
    macro_observation_bundle = {
        "page_slug": "macro-observation",
        "page_id": "PAGE-MACRO-OBS-001",
        "page_name": "Macro Observation",
        "aliases": [
            "macro-observation",
            "macro_observation",
            "/macro-observation",
            "PAGE-MACRO-OBS-001",
        ],
        "frontend_route": "/macro-observation",
        "primary_api": "/ui/macro/toolkit/analysis",
        "supporting_apis": [
            "/ui/macro/toolkit/analysis/strategy-summaries",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
            "docs/golden_sample_catalog.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-MACRO-OBS-001 read-only macro observation surface",
            "docs/metric_dictionary.md /macro-observation has no MTR-* and no MTR-MACRO-*; read-only macro evidence is not formal metric truth",
            "docs/metric_dictionary.md core signals, crowding risk, strategy supply status, and source/version/run_id are analysis evidence only",
            "GET /ui/macro/toolkit/analysis?detail=core is reused for read-only macro observation evidence",
            "GET /ui/macro/toolkit/analysis/strategy-summaries supplies read-only strategy evidence",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx mode='observation'",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx macro-observation-readonly-boundary keeps read-only macro observation visible",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx MacroToolkitContractBoundary keeps formal_use_allowed=false visible",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/macro_toolkit.py",
            "backend/app/services/macro_toolkit_service.py",
            "backend/app/core_finance/macro",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/macroToolkitClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_governance_doc_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/test/MacroToolkitPage.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
            "frontend/src/test/navigation.test.ts",
            "frontend/src/test/macroToolkitClient.test.ts",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-MACRO-OBS-001; verify through page contract, metric dictionary, route tests, and frontend MacroToolkitPage observation-mode tests.",
            "Trace observation display through /ui/macro/toolkit/analysis, /ui/macro/toolkit/analysis/strategy-summaries, getMacroToolkitAnalysis, getMacroToolkitStrategySummaries, and MacroToolkitPage mode='observation'.",
            "Confirm macro-observation-readonly-boundary remains visible in normal and error states and that script registry, run, refresh, and refresh-status controls stay absent.",
            "Check loading, empty, stale, fallback, source/version/run_id, deferred-section, and no-data states without inheriting operational actions from /macro-toolkit.",
        ],
        "guardrails": [
            "PAGE-MACRO-OBS-001 is read-only; do not expose script registry, script run, refresh actions, refresh-status controls, or operational registries on /macro-observation.",
            "Do not promote read-only observation evidence to MTR-* or MTR-MACRO-* without approved metric dictionary rows, lineage, sample or candidate decision, and tests.",
            "Keep the read-only boundary and macro-observation-readonly-boundary visible in normal and error states.",
            "Do not use macro observation to replace market-data rates/macros, stock-analysis decisions, formal PnL, balance, risk, or executive truth.",
            "Do not hide fallback, stale, source gaps, no-data, or analysis failure states behind the shared MacroToolkitPage shell.",
        ],
    }

    agent_bundle = {
        "page_slug": "agent",
        "page_id": "PAGE-AGENT-001",
        "page_name": "Agent Workbench",
        "aliases": [
            "agent",
            "/agent",
            "PAGE-AGENT-001",
            "POST /api/agent/runs",
            "GET /api/agent/runs/{run_id}",
            "POST /api/agent/query",
        ],
        "frontend_route": "/agent",
        "primary_api": "POST /api/agent/runs",
        "supporting_apis": [
            "GET /api/agent/runs/{run_id}",
            "POST /api/agent/query",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-AGENT-001 active Agent Workbench",
            "docs/metric_dictionary.md PAGE-AGENT-001 has no standalone MTR-*; agent answers are analytical/read-only unless result_meta explicitly allows formal use",
            "backend/app/api/routes/agent.py enforces read-only agent request context before executing managed runs or compatibility query calls",
            "POST /api/agent/runs creates managed agent runs; GET /api/agent/runs/{run_id} polls status and ownership",
            "POST /api/agent/query is a local/synchronous compatibility path, not a page metric endpoint",
            "AgentEnvelope carries answer, cards, evidence, result_meta, next_drill, and suggested_actions",
            "AgentResultMeta.formal_use_allowed gates whether an answer may be presented as a formal financial result",
            "frontend/src/api/agentClient.ts queryAgent",
            "frontend/src/features/agent/AgentWorkbenchPage.tsx builds AgentQueryRequest and displays evidence/result metadata",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/agent.py",
            "backend/app/services/agent_run_service.py",
            "backend/app/services/agent_service.py",
            "backend/app/agent/schemas/agent_request.py",
            "backend/app/agent/schemas/agent_response.py",
            "backend/app/agent/schemas/agent_run.py",
            "backend/app/governance/agent_audit.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/agentClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/agent/AgentWorkbenchPage.tsx",
            "frontend/src/features/agent/components/AgentEvidencePanel.tsx",
            "frontend/src/features/agent/components/AgentResultMetaPanel.tsx",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_agent_api_contract.py",
            "tests/test_agent_enabled_path_smoke.py",
            "tests/test_agent_runs_api.py",
            "tests/test_agent_intent_routing.py",
            "tests/test_agent_audit_log_contract.py",
            "frontend/src/test/AgentWorkbenchPage.test.tsx",
            "frontend/src/test/AgentPlaceholderPage.test.tsx",
            "frontend/src/test/AgentClient.test.ts",
            "frontend/src/test/RouteRegistry.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-AGENT-001; verify through page contract, agent API contract, run ownership/status tests, frontend AgentWorkbenchPage tests, and route registry tests.",
            "Trace answers through AgentQueryRequest, /api/agent/runs or /api/agent/query, AgentEnvelope, evidence/result_meta panels, and formal_use_allowed before changing display logic.",
            "Check disabled-provider, rejected request, failed run, forbidden run ownership, empty answer, stale/fallback, and vendor degradation states remain visible.",
        ],
        "guardrails": [
            "PAGE-AGENT-001 is read-only analytical workbench surface; do not treat an agent answer as a formal financial result unless result_meta.formal_use_allowed explicitly allows it.",
            "Do not allow mutating or write-route actions through agent page context, suggested actions, or run payloads without a separate approved write contract.",
            "Do not use agent answers to replace formal metrics, source lineage, page contracts, result_meta evidence, or governed downstream page truth.",
            "Keep disabled-provider, permission, stale, fallback, vendor degradation, and no-data states visible instead of smoothing them into a successful answer.",
        ],
    }
    cube_query_bundle = {
        "page_slug": "cube-query",
        "page_id": "PAGE-CUBE-QUERY-001",
        "page_name": "Cube Query",
        "aliases": [
            "cube-query",
            "cube_query",
            "/cube-query",
            "PAGE-CUBE-QUERY-001",
            "POST /api/cube/query",
            "GET /api/cube/dimensions/{fact_table}",
        ],
        "frontend_route": "/cube-query",
        "primary_api": "POST /api/cube/query",
        "supporting_apis": [
            "GET /api/cube/dimensions/{fact_table}",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-CUBE-QUERY-001 active candidate query surface",
            "docs/metric_dictionary.md PAGE-CUBE-QUERY-001 has no standalone MTR-* and no standalone MTR binding; formal semantics are scoped to the returned query result_meta",
            "POST /api/cube/query returns CubeQueryResult / CubeQueryResponse rows, columns, summary, drill path, and result_meta for the selected query",
            "GET /api/cube/dimensions/{fact_table} describes allowed dimensions for backend-approved fact tables",
            "backend/app/api/routes/cube_query.py delegates to AnalyticalBridgeService and CubeQueryService",
            "backend/app/services/cube_query_service.py keeps allowed table/dimension semantics backend-owned",
            "frontend/src/api/cubeClient.ts executeCubeQuery and getCubeDimensions",
            "frontend/src/features/cube-query/pages/CubeQueryPage.tsx builds CubeQueryRequest",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/cube_query.py",
            "backend/app/services/cube_query_service.py",
            "backend/app/services/analytical_bridge_service.py",
            "backend/app/repositories/cube_query_repo.py",
            "backend/app/schemas/cube_query.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/cubeClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/cube-query/pages/CubeQueryPage.tsx",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_cube_query_api.py",
            "tests/test_cube_query_service.py",
            "tests/test_cube_query_schema_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/test/CubeQueryPage.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-CUBE-QUERY-001; verify through cube query API/service/schema tests, page contract, route registry, and CubeQueryPage tests.",
            "Trace a query through CubeQueryRequest, /api/cube/query, backend-approved fact table/dimensions/measures, CubeQueryResult, result_meta, and the rendered query table before changing query display logic.",
            "Check invalid table, invalid dimension, invalid measure, invalid filter, unavailable storage, empty result, stale/fallback, and quality states fail closed or stay visible.",
        ],
        "guardrails": [
            "PAGE-CUBE-QUERY-001 is a candidate query surface; do not create a new page-level KPI, metric definition, or formal business conclusion outside the returned query result_meta.",
            "Unsupported fact tables, dimensions, measures, filters, or storage states must fail closed with visible errors.",
            "Do not let the frontend reinterpret measure units, date semantics, formal basis, stale/fallback status, or query result_meta.",
            "Do not render demo rows for empty query results in real mode.",
        ],
    }

    def module_home_bundle(
        *,
        page_slug: str,
        page_id: str,
        page_name: str,
        frontend_route: str,
        kind: str,
        downstream_pages: list[str],
        supporting_apis: list[str],
        backend_touchpoints: list[str],
        truth_detail: str,
        guardrail_detail: str,
    ) -> dict[str, Any]:
        return {
            "page_slug": page_slug,
            "page_id": page_id,
            "page_name": page_name,
            "aliases": [
                page_slug,
                page_slug.replace("-", "_"),
                frontend_route,
                page_id,
            ],
            "frontend_route": frontend_route,
            "primary_api": f"frontend aggregation: module-home/{kind}",
            "supporting_apis": [*downstream_pages, *supporting_apis],
            "contract_docs": [
                "docs/page_contracts.md",
                "docs/metric_dictionary.md",
                "docs/live_route_maturity.md",
            ],
            "truth_chain": [
                f"docs/page_contracts.md {page_id} active module home",
                f"docs/metric_dictionary.md {frontend_route} is a module home route with no standalone MTR-* and no standalone MTR binding",
                f"frontend/src/features/workbench/module-home/moduleHomeConfig.ts kind={kind}",
                f"frontend/src/features/workbench/module-home/moduleHomeModel.ts buildModuleHomeView kind={kind}",
                "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx mounts module-home queries and source statuses",
                truth_detail,
            ],
            "backend_touchpoints": backend_touchpoints,
            "frontend_touchpoints": [
                "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
                "frontend/src/features/workbench/module-home/moduleHomeModel.ts",
                "frontend/src/features/workbench/module-home/moduleHomeConfig.ts",
                "frontend/src/router/routes.tsx",
            ],
            "test_touchpoints": [
                "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
                "frontend/src/test/ModuleWorkbenchHomePage.test.tsx",
                "frontend/src/test/RouteRegistry.test.tsx",
                "tests/test_live_route_page_contract_completeness.py",
                "tests/test_page_contract_metric_dictionary_completeness.py",
            ],
            "golden_samples": [],
            "verification_focus": [
                f"No dedicated golden sample is currently registered for {page_id}; verify through the page contract, module home model/page tests, route registry tests, and downstream page/API tests when changing displayed fields.",
                f"Trace {frontend_route} through moduleHomeConfig, ModuleWorkbenchHomePage queries, buildModuleHomeView, source statuses, and downstream page result_meta before changing module-home display logic.",
                "Check mixed dates, no-data, partial child-query failure, stale/fallback, source metadata, and downstream page ownership remain visible.",
            ],
            "guardrails": [
                f"{page_id} is a module home and navigation summary, not a standalone formal metric page.",
                "Keep formal-use claims scoped to downstream pages, endpoint result_meta, page contracts, and approved metric dictionary rows.",
                guardrail_detail,
                "Do not backfill missing child-query data with static demo values in real mode.",
                "Do not hide stale, fallback, source gaps, no-data, or child-query errors behind a successful module home shell.",
            ],
        }

    portfolio_home_bundle = module_home_bundle(
        page_slug="portfolio-home",
        page_id="PAGE-PORTFOLIO-HOME-001",
        page_name="Portfolio Workbench Home",
        frontend_route="/portfolio",
        kind="portfolio",
        downstream_pages=["/balance-analysis", "/bond-dashboard", "/positions", "/pnl-attribution"],
        supporting_apis=[
            "/ui/balance-analysis/overview",
            "/api/bond-dashboard/headline-kpis",
            "/api/positions/bonds",
            "/api/pnl-attribution/analysis-summary",
        ],
        backend_touchpoints=[
            "backend/app/api/routes/balance_analysis.py",
            "backend/app/api/routes/bond_dashboard.py",
            "backend/app/api/routes/positions.py",
            "backend/app/api/routes/pnl_attribution.py",
        ],
        truth_detail="Portfolio module home aggregates balance, bond dashboard, positions, and attribution evidence only to guide drilldown.",
        guardrail_detail="Do not use portfolio module-home cards as a standalone formal metric page or as replacements for balance, bond, positions, or attribution truth.",
    )
    market_home_bundle = module_home_bundle(
        page_slug="market-home",
        page_id="PAGE-MARKET-HOME-001",
        page_name="Market Workbench Home",
        frontend_route="/market-overview",
        kind="market",
        downstream_pages=["/market-data", "/macro-toolkit", "/stock-analysis", "/news-events"],
        supporting_apis=[
            "/ui/macro/choice-series/latest",
            "/ui/market-data/rates",
            "/ui/market-data/catalog",
            "/ui/macro/toolkit/analysis",
            "/ui/macro/toolkit/analysis/strategy-summaries",
        ],
        backend_touchpoints=[
            "backend/app/api/routes/macro_vendor.py",
            "backend/app/api/routes/macro_toolkit.py",
            "backend/app/api/routes/market_data_livermore.py",
        ],
        truth_detail="Market module home aggregates market data, macro toolkit, stock observation, and news/event readiness only to guide market drilldown.",
        guardrail_detail="Do not promote observational, vendor-readiness, macro-toolkit, stock, news, or event summaries into formal market data claims.",
    )
    risk_home_bundle = module_home_bundle(
        page_slug="risk-home",
        page_id="PAGE-RISK-HOME-001",
        page_name="Risk Workbench Home",
        frontend_route="/risk-overview",
        kind="risk",
        downstream_pages=["/risk-tensor", "/concentration-monitor", "/cashflow-projection"],
        supporting_apis=[
            "/api/risk/tensor/dates",
            "/api/risk/tensor",
            "/api/cashflow-projection",
        ],
        backend_touchpoints=[
            "backend/app/api/routes/risk_tensor.py",
            "backend/app/api/routes/cashflow_projection.py",
        ],
        truth_detail="Risk module home summarizes risk tensor and cashflow readiness only to guide risk drilldown.",
        guardrail_detail="Do not replace PAGE-RISK-001 formal risk truth, regulatory DV01, liquidity pressure, or concentration limits with frontend module-home estimates.",
    )
    performance_home_bundle = module_home_bundle(
        page_slug="performance-home",
        page_id="PAGE-PERFORMANCE-HOME-001",
        page_name="Performance Workbench Home",
        frontend_route="/performance",
        kind="performance",
        downstream_pages=["/kpi", "/team-performance", "/pnl-by-business", "/product-category-pnl"],
        supporting_apis=[
            "/api/kpi/owners",
            "/api/kpi/values/summary",
            "/api/pnl/by-business-ytd",
            "/ui/pnl/product-category",
        ],
        backend_touchpoints=[
            "backend/app/api/routes/kpi.py",
            "backend/app/api/routes/pnl.py",
            "backend/app/api/routes/product_category_pnl.py",
        ],
        truth_detail="Performance module home aggregates KPI, team, business PnL, and product PnL entry-point evidence only to guide performance review drilldown.",
        guardrail_detail="Do not rebuild KPI scoring, team allocation, business PnL, or product PnL formulas on the module home.",
    )
    reports_home_bundle = module_home_bundle(
        page_slug="reports-home",
        page_id="PAGE-REPORTS-HOME-001",
        page_name="Reports And Data Home",
        frontend_route="/reports",
        kind="governance",
        downstream_pages=["/platform-config", "/cube-query"],
        supporting_apis=[
            "/health/live",
            "/health/summary",
            "/ui/preview/source-foundation",
            "/api/cube/dimensions/bond_analytics",
        ],
        backend_touchpoints=[
            "backend/app/api/routes/health.py",
            "backend/app/api/routes/source_preview.py",
            "backend/app/api/routes/cube_query.py",
        ],
        truth_detail="Reports/data module home aggregates health, source preview, cube capability, and report-planning status only to guide data governance drilldown.",
        guardrail_detail="Do not convert diagnostics, source preview, cube capability, or planned reports into data-quality approval.",
    )

    bundles = [
        product_category_bundle,
        dashboard_home_bundle,
        executive_overview_bundle,
        executive_summary_bundle,
        balance_analysis_bundle,
        balance_movement_analysis_bundle,
        pnl_bundle,
        ledger_pnl_bundle,
        executive_pnl_attribution_bundle,
        pnl_attribution_workbench_bundle,
        operations_analysis_bundle,
        liability_analytics_bundle,
        pnl_bridge_bundle,
        risk_tensor_bundle,
        bond_dashboard_bundle,
        positions_bundle,
        market_data_bundle,
        macro_toolkit_bundle,
        macro_observation_bundle,
        agent_bundle,
        cube_query_bundle,
        portfolio_home_bundle,
        market_home_bundle,
        risk_home_bundle,
        performance_home_bundle,
        reports_home_bundle,
    ]
    return {
        alias.casefold(): bundle
        for bundle in bundles
        for alias in bundle["aliases"]
    }


def page_trace_bundle(bundles: dict[str, dict[str, Any]], page_slug: str) -> dict[str, Any]:
    if not page_slug:
        raise McpError(-32602, "page_slug is required.")
    bundle = bundles.get(page_slug.casefold())
    if bundle is None:
        supported = sorted({bundle["page_slug"] for bundle in bundles.values()})
        raise McpError(-32602, f"Unknown page_slug: {page_slug}. Supported pages: {', '.join(supported)}")
    return bundle


def list_golden_samples(*, limit: int) -> list[dict[str, Any]]:
    root = REPO_ROOT / "tests" / "golden_samples"
    if not root.is_dir():
        return []
    samples = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        samples.append(
            {
                "sample_id": path.name,
                "request": (path / "request.json").is_file(),
                "response": (path / "response.json").is_file(),
                "assertions": (path / "assertions.md").is_file(),
                "approval": (path / "approval.md").is_file(),
            }
        )
        if len(samples) >= limit:
            break
    return samples


def search_files(paths: Any, *, query: str, max_results: int) -> list[dict[str, Any]]:
    needle = query.casefold()
    matches: list[dict[str, Any]] = []
    for path in paths:
        safe_path = assert_repo_path(Path(path))
        if not safe_path.is_file():
            continue
        for lineno, line in enumerate(safe_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if needle in line.casefold():
                matches.append(
                    {
                        "path": str(safe_path.relative_to(REPO_ROOT)),
                        "line": lineno,
                        "text": line.strip()[:500],
                    }
                )
                if len(matches) >= max_results:
                    return matches
    return matches


def stream_status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "latest_records": read_jsonl_tail(path, limit=2) if path.is_file() else [],
    }


def read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = tail_lines(path, limit=limit)
    records = []
    for line in lines:
        record = parse_json_line(line)
        if record is not None:
            records.append(record)
    return records


def tail_lines(path: Path, *, limit: int) -> list[str]:
    # Governance streams are append-only JSONL. A bounded backward scan avoids
    # loading large lineage indices into memory.
    block_size = 8192
    data = b""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        while position > 0 and data.count(b"\n") <= limit:
            read_size = min(block_size, position)
            position -= read_size
            handle.seek(position)
            data = handle.read(read_size) + data
    lines = [line for line in data.decode("utf-8", errors="replace").splitlines() if line.strip()]
    return lines[-limit:]


def find_jsonl_records(path: Path, *, stream: str, query: str, max_results: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    needle = query.casefold()
    matches: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if needle not in line.casefold():
                continue
            record = parse_json_line(line) or {"raw": line.strip()}
            matches.append({"stream": stream, "line": line_number, "record": record})
            if len(matches) >= max_results:
                break
    return matches


def lineage_query_terms(query: str, expansions: dict[str, list[str]]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for term in [query, *expansions.get(query.casefold(), [])]:
        normalized = term.strip()
        if not normalized or normalized.casefold() in seen:
            continue
        seen.add(normalized.casefold())
        terms.append(normalized)
    return terms


def parse_json_line(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else {"value": value}


def schema_registry_summary(schema_dir: Path) -> dict[str, Any]:
    if not schema_dir.is_dir():
        return {"path": str(schema_dir), "exists": False, "files": []}
    files = []
    for path in sorted(schema_dir.glob("*.sql")):
        files.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "bytes": path.stat().st_size,
            }
        )
    manifest = schema_dir / "manifest.json"
    return {
        "path": str(schema_dir.relative_to(REPO_ROOT)),
        "exists": True,
        "manifest": read_json_file(manifest) if manifest.is_file() else None,
        "files": files,
    }


def read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def duckdb_tables(duckdb_path: Path, *, limit: int) -> list[dict[str, Any]]:
    conn = open_duckdb_read_only(duckdb_path)
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            select table_schema, table_name, table_type
            from information_schema.tables
            where table_schema not in ('information_schema', 'pg_catalog')
            order by table_schema, table_name
            limit ?
            """,
            [limit],
        ).fetchall()
        return [
            {"schema": str(schema), "table": str(table), "type": str(table_type)}
            for schema, table, table_type in rows
        ]
    finally:
        conn.close()


def duckdb_quality_targets(duckdb_path: Path, *, limit: int) -> list[dict[str, Any]]:
    conn = open_duckdb_read_only(duckdb_path)
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            with date_columns as (
                select
                    table_schema,
                    table_name,
                    string_agg(column_name, ', ' order by column_name) as date_columns
                from information_schema.columns
                where column_name in ('report_date', 'as_of_date')
                group by table_schema, table_name
            )
            select
                t.table_schema,
                t.table_name,
                t.table_type,
                coalesce(d.date_columns, '') as date_columns
            from information_schema.tables t
            left join date_columns d
                on d.table_schema = t.table_schema
               and d.table_name = t.table_name
            where t.table_schema not in ('information_schema', 'pg_catalog')
            order by t.table_schema, t.table_name
            limit ?
            """,
            [limit],
        ).fetchall()
        return [
            {
                "table_name": f"{schema}.{table}",
                "schema": str(schema),
                "table": str(table),
                "type": str(table_type),
                "date_columns": [part.strip() for part in str(date_columns).split(",") if part.strip()],
            }
            for schema, table, table_type, date_columns in rows
        ]
    finally:
        conn.close()


def describe_duckdb_table(duckdb_path: Path, table_name: str) -> dict[str, Any]:
    validate_identifier(table_name, "table_name")
    conn = require_duckdb(duckdb_path)
    try:
        metadata = duckdb_table_metadata(conn, table_name)
        return {
            "table_name": table_name,
            "columns": [
                {"name": item["name"], "type": item["type"], "nullable": item["nullable"]}
                for item in metadata["columns"]
            ],
        }
    finally:
        conn.close()


def list_available_dates(duckdb_path: Path, table_name: str, date_column: str, *, limit: int) -> dict[str, Any]:
    validate_identifier(table_name, "table_name")
    validate_identifier(date_column, "date_column")
    describe_duckdb_table(duckdb_path, table_name)
    conn = require_duckdb(duckdb_path)
    try:
        quoted_table = ".".join(quote_identifier(part) for part in split_table_name(table_name))
        quoted_column = quote_identifier(date_column)
        rows = conn.execute(
            f"select distinct cast({quoted_column} as varchar) as value from {quoted_table} "
            "where {column} is not null order by value desc limit ?".format(column=quoted_column),
            [limit],
        ).fetchall()
        return {
            "table_name": table_name,
            "date_column": date_column,
            "values": [str(row[0]) for row in rows],
        }
    finally:
        conn.close()


def open_duckdb_read_only(duckdb_path: Path) -> Any | None:
    if not duckdb_path.is_file():
        return None
    try:
        import duckdb  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return duckdb.connect(str(duckdb_path), read_only=True)
    except Exception:
        return None


def require_duckdb(duckdb_path: Path) -> Any:
    if not duckdb_path.is_file():
        raise McpError(-32602, f"DuckDB file does not exist: {duckdb_path}")
    try:
        import duckdb  # type: ignore[import-not-found]
    except ImportError as exc:
        raise McpError(-32603, "duckdb package is not installed in this Python environment.") from exc
    try:
        return duckdb.connect(str(duckdb_path), read_only=True)
    except Exception as exc:
        raise McpError(-32603, f"Could not open DuckDB read-only: {exc}") from exc


def duckdb_table_metadata(conn: Any, table_name: str) -> dict[str, Any]:
    schema_name, bare_table_name = split_table_name(table_name)
    object_rows = conn.execute(
        """
        select table_type
        from information_schema.tables
        where table_schema = ? and table_name = ?
        """,
        [schema_name, bare_table_name],
    ).fetchall()
    if not object_rows:
        raise McpError(-32602, f"Unknown table: {table_name}")

    column_rows = conn.execute(
        """
        select column_name, data_type, is_nullable
        from information_schema.columns
        where table_schema = ? and table_name = ?
        order by ordinal_position
        """,
        [schema_name, bare_table_name],
    ).fetchall()
    if not column_rows:
        raise McpError(-32602, f"Unknown table: {table_name}")

    return {
        "schema_name": schema_name,
        "table_name": bare_table_name,
        "object_type": str(object_rows[0][0]),
        "columns": [
            {"name": str(column), "type": str(data_type), "nullable": str(nullable)}
            for column, data_type, nullable in column_rows
        ],
    }


def duckdb_quality_summary(duckdb_path: Path, table_name: str, *, column_limit: int) -> dict[str, Any]:
    validate_identifier(table_name, "table_name")
    if column_limit < 1 or column_limit > 100:
        raise McpError(-32602, "column_limit must be between 1 and 100.")

    conn = require_duckdb(duckdb_path)
    try:
        metadata = duckdb_table_metadata(conn, table_name)
        qualified_table = ".".join(
            quote_identifier(part) for part in (metadata["schema_name"], metadata["table_name"])
        )
        columns = metadata["columns"]
        preview_columns = columns[:column_limit]

        row_count = int(conn.execute(f"select count(*) from {qualified_table}").fetchone()[0])
        null_counts = duckdb_null_counts(conn, qualified_table, preview_columns)
        date_coverage = duckdb_date_coverage(conn, qualified_table, columns)

        return {
            "table_name": f'{metadata["schema_name"]}.{metadata["table_name"]}',
            "object_type": metadata["object_type"],
            "row_count": row_count,
            "column_count": len(columns),
            "profiled_columns": [column["name"] for column in preview_columns],
            "columns": columns,
            "null_counts": null_counts,
            "date_coverage": date_coverage,
            "golden_sample_matches": find_golden_sample_mentions(metadata["table_name"], limit=10),
        }
    finally:
        conn.close()


def duckdb_null_counts(conn: Any, qualified_table: str, columns: list[dict[str, Any]]) -> dict[str, int]:
    if not columns:
        return {}
    expressions = []
    aliases = []
    for index, column in enumerate(columns):
        alias = f"c{index}"
        aliases.append((alias, column["name"]))
        expressions.append(
            f"sum(case when {quote_identifier(column['name'])} is null then 1 else 0 end) as {quote_identifier(alias)}"
        )
    row = conn.execute(f"select {', '.join(expressions)} from {qualified_table}").fetchone()
    return {column_name: int(row[index]) for index, (_, column_name) in enumerate(aliases)}


def duckdb_date_coverage(conn: Any, qualified_table: str, columns: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    for column in columns:
        column_name = column["name"]
        if column_name not in {"report_date", "as_of_date"}:
            continue
        quoted_column = quote_identifier(column_name)
        row = conn.execute(
            f"""
            select
                cast(min({quoted_column}) as varchar),
                cast(max({quoted_column}) as varchar),
                sum(case when {quoted_column} is null then 1 else 0 end),
                count(distinct {quoted_column}) filter (where {quoted_column} is not null)
            from {qualified_table}
            """
        ).fetchone()
        coverage[column_name] = {
            "min": row[0],
            "max": row[1],
            "null_count": int(row[2]),
            "distinct_non_null_count": int(row[3]),
        }
    return coverage


def find_golden_sample_mentions(query: str, *, limit: int) -> list[dict[str, Any]]:
    paths = []
    catalog = REPO_ROOT / "docs" / "golden_sample_catalog.md"
    if catalog.is_file():
        paths.append(catalog)

    root = REPO_ROOT / "tests" / "golden_samples"
    if root.is_dir():
        for sample_dir in sorted(root.iterdir()):
            if not sample_dir.is_dir():
                continue
            for name in ("request.json", "response.json", "assertions.md"):
                path = sample_dir / name
                if path.is_file():
                    paths.append(path)

    return search_files(paths, query=query, max_results=limit)


def validate_identifier(value: str, field: str) -> None:
    if not value:
        raise McpError(-32602, f"{field} is required.")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?", value):
        raise McpError(-32602, f"{field} must be an identifier, optionally schema-qualified.")


def split_table_name(table_name: str) -> tuple[str, str]:
    if "." in table_name:
        schema_name, bare_table_name = table_name.split(".", 1)
        return schema_name, bare_table_name
    return "main", table_name


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


if __name__ == "__main__":
    raise SystemExit(main())
