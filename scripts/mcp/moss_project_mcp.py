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
        choices=("metric-contracts", "lineage-evidence", "data-catalog"),
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
                            "description": "Seeded page slug or route alias, for example product-category-pnl.",
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
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            max_results = int(arguments.get("max_results") or 40)
            records = []
            for stream in stream_names:
                path = self._stream_path(stream)
                records.extend(find_jsonl_records(path, stream=stream, query=query, max_results=max_results))
                if len(records) >= max_results:
                    break
            payload = {"query": query, "records": records[:max_results]}
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


def build_provider(mode: str) -> McpProvider:
    providers: dict[str, Callable[[], McpProvider]] = {
        "metric-contracts": MetricContractsProvider,
        "lineage-evidence": LineageEvidenceProvider,
        "data-catalog": DataCatalogProvider,
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
    return {alias.casefold(): product_category_bundle for alias in product_category_bundle["aliases"]}


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


def describe_duckdb_table(duckdb_path: Path, table_name: str) -> dict[str, Any]:
    validate_identifier(table_name, "table_name")
    conn = require_duckdb(duckdb_path)
    try:
        schema_name, bare_table_name = split_table_name(table_name)
        rows = conn.execute(
            """
            select column_name, data_type, is_nullable
            from information_schema.columns
            where table_schema = ? and table_name = ?
            order by ordinal_position
            """,
            [schema_name, bare_table_name],
        ).fetchall()
        if not rows:
            raise McpError(-32602, f"Unknown table: {table_name}")
        return {
            "table_name": table_name,
            "columns": [
                {"name": str(column), "type": str(data_type), "nullable": str(nullable)}
                for column, data_type, nullable in rows
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
