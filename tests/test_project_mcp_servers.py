from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_SCRIPT = REPO_ROOT / "scripts" / "mcp" / "moss_project_mcp.py"
CODEX_CONFIG = REPO_ROOT / ".codex" / "config.toml"

ALL_SEEDED_RECORD_GAP_PAGE_IDS = [
    "PAGE-DASH-001",
    "PAGE-EXEC-OVERVIEW-001",
    "PAGE-EXEC-SUMMARY-001",
    "GAP-BANK-LEDGER-DASHBOARD-PAGE",
    "GAP-CONCENTRATION-MONITOR-PAGE",
    "GAP-TEAM-PERFORMANCE-PAGE",
    "GAP-PLATFORM-CONFIG-PAGE",
    "GAP-DECISION-ITEMS-PAGE",
    "PAGE-PNL-001",
    "PAGE-LEDGER-PNL-001",
    "PAGE-PNL-BY-BUSINESS-001",
    "PAGE-EXEC-PNL-ATTR-001",
    "PAGE-OPS-001",
    "PAGE-LIAB-ANALYTICS-001",
    "PAGE-BRIDGE-001",
    "PAGE-BOND-ANALYSIS-001",
    "PAGE-POS-001",
    "PAGE-MKT-001",
    "GAP-CROSS-ASSET-PAGE",
    "GAP-STOCK-ANALYSIS-PAGE",
    "PAGE-MACRO-TOOLKIT-001",
    "PAGE-MACRO-OBS-001",
    "PAGE-AGENT-001",
    "PAGE-CUBE-QUERY-001",
    "PAGE-PORTFOLIO-HOME-001",
    "PAGE-MARKET-HOME-001",
    "PAGE-RISK-HOME-001",
    "PAGE-PERFORMANCE-HOME-001",
    "GAP-KPI-PERFORMANCE-PAGE",
    "PAGE-REPORTS-HOME-001",
]

ALL_SEEDED_RECORD_GAP_PAGE_SLUGS = [
    "dashboard-home",
    "executive-overview",
    "executive-summary",
    "bank-ledger-dashboard",
    "concentration-monitor",
    "team-performance",
    "platform-config",
    "decision-items",
    "pnl",
    "ledger-pnl",
    "pnl-by-business",
    "executive-pnl-attribution",
    "operations-analysis",
    "liability-analytics",
    "pnl-bridge",
    "bond-analysis",
    "positions",
    "market-data",
    "cross-asset",
    "stock-analysis",
    "macro-toolkit",
    "macro-observation",
    "agent",
    "cube-query",
    "portfolio-home",
    "market-home",
    "risk-home",
    "performance-home",
    "kpi-performance",
    "reports-home",
]

ALL_SEEDED_CATALOG_DATE_LINEAGE_PAGE_IDS = [
    "PAGE-PROD-CAT-001",
    "PAGE-BALANCE-001",
    "PAGE-PNL-001",
    "PAGE-BRIDGE-001",
    "PAGE-RISK-001",
    "PAGE-DASH-001",
    "PAGE-EXEC-OVERVIEW-001",
    "GAP-CONCENTRATION-MONITOR-PAGE",
    "PAGE-BAL-MOVE-001",
    "PAGE-PNL-BY-BUSINESS-001",
    "PAGE-PNL-ATTR-WB-001",
    "PAGE-OPS-001",
    "PAGE-LIAB-ANALYTICS-001",
    "PAGE-BOND-001",
    "PAGE-BOND-ANALYSIS-001",
    "PAGE-CUBE-QUERY-001",
    "PAGE-PORTFOLIO-HOME-001",
    "PAGE-RISK-HOME-001",
    "PAGE-PERFORMANCE-HOME-001",
    "GAP-TEAM-PERFORMANCE-PAGE",
    "PAGE-REPORTS-HOME-001",
    "PAGE-LEDGER-PNL-001",
    "PAGE-POS-001",
    "PAGE-MKT-001",
    "GAP-CROSS-ASSET-PAGE",
    "GAP-PLATFORM-CONFIG-PAGE",
    "GAP-NEWS-EVENTS-PAGE",
    "PAGE-MARKET-HOME-001",
    "GAP-STOCK-ANALYSIS-PAGE",
    "PAGE-EXEC-SUMMARY-001",
    "PAGE-EXEC-PNL-ATTR-001",
    "PAGE-MACRO-TOOLKIT-001",
    "PAGE-MACRO-OBS-001",
    "PAGE-AGENT-001",
    "GAP-KPI-PERFORMANCE-PAGE",
]

ALL_SEEDED_CATALOG_DATE_LINEAGE_PAGE_SLUGS = [
    "product-category-pnl",
    "balance-analysis",
    "pnl",
    "pnl-bridge",
    "risk-tensor",
    "dashboard-home",
    "executive-overview",
    "concentration-monitor",
    "balance-movement-analysis",
    "pnl-by-business",
    "pnl-attribution",
    "operations-analysis",
    "liability-analytics",
    "bond-dashboard",
    "bond-analysis",
    "cube-query",
    "portfolio-home",
    "risk-home",
    "performance-home",
    "team-performance",
    "reports-home",
    "ledger-pnl",
    "positions",
    "market-data",
    "cross-asset",
    "platform-config",
    "news-events",
    "market-home",
    "stock-analysis",
    "executive-summary",
    "executive-pnl-attribution",
    "macro-toolkit",
    "macro-observation",
    "agent",
    "kpi-performance",
]

CONFIGURED_CATALOG_DATE_PAGE_SLUGS = ALL_SEEDED_CATALOG_DATE_LINEAGE_PAGE_SLUGS[:29]
DEFERRED_CATALOG_DATE_PAGE_SLUGS = ALL_SEEDED_CATALOG_DATE_LINEAGE_PAGE_SLUGS[29:]
CATALOG_DATE_RECORD_GAP_PAGE_IDS = [
    "PAGE-DASH-001",
    "PAGE-EXEC-OVERVIEW-001",
    "PAGE-EXEC-SUMMARY-001",
    "PAGE-PNL-001",
    "PAGE-LEDGER-PNL-001",
    "PAGE-PNL-BY-BUSINESS-001",
    "PAGE-EXEC-PNL-ATTR-001",
    "PAGE-OPS-001",
    "PAGE-LIAB-ANALYTICS-001",
    "PAGE-BRIDGE-001",
    "PAGE-POS-001",
    "PAGE-MKT-001",
    "GAP-CROSS-ASSET-PAGE",
    "PAGE-MACRO-TOOLKIT-001",
    "PAGE-MACRO-OBS-001",
    "PAGE-AGENT-001",
    "PAGE-CUBE-QUERY-001",
    "PAGE-PORTFOLIO-HOME-001",
    "PAGE-MARKET-HOME-001",
    "PAGE-RISK-HOME-001",
    "PAGE-PERFORMANCE-HOME-001",
    "PAGE-REPORTS-HOME-001",
]
CATALOG_DATE_RECORD_GAP_PAGE_SLUGS = [
    "dashboard-home",
    "executive-overview",
    "executive-summary",
    "pnl",
    "ledger-pnl",
    "pnl-by-business",
    "executive-pnl-attribution",
    "operations-analysis",
    "liability-analytics",
    "pnl-bridge",
    "positions",
    "market-data",
    "cross-asset",
    "macro-toolkit",
    "macro-observation",
    "agent",
    "cube-query",
    "portfolio-home",
    "market-home",
    "risk-home",
    "performance-home",
    "reports-home",
]

READY_FOR_AUDIT_PAGE_IDS = [
    "PAGE-PROD-CAT-001",
    "PAGE-BALANCE-001",
    "GAP-CONCENTRATION-MONITOR-PAGE",
    "PAGE-BAL-MOVE-001",
    "PAGE-PNL-ATTR-WB-001",
    "PAGE-RISK-001",
    "PAGE-BOND-001",
    "PAGE-BOND-ANALYSIS-001",
    "GAP-STOCK-ANALYSIS-PAGE",
    "GAP-PLATFORM-CONFIG-PAGE",
    "GAP-NEWS-EVENTS-PAGE",
    "GAP-TEAM-PERFORMANCE-PAGE",
    "GAP-KPI-PERFORMANCE-PAGE",
]

READY_FOR_AUDIT_PAGE_SLUGS = [
    "product-category-pnl",
    "balance-analysis",
    "concentration-monitor",
    "balance-movement-analysis",
    "pnl-attribution",
    "risk-tensor",
    "bond-dashboard",
    "bond-analysis",
    "stock-analysis",
    "platform-config",
    "news-events",
    "team-performance",
    "kpi-performance",
]

GOVERNANCE_READY_FOR_AUDIT_PAGE_IDS = [
    "PAGE-PROD-CAT-001",
    "PAGE-BALANCE-001",
    "GAP-AVERAGE-BALANCE-PAGE",
    "GAP-CASHFLOW-PROJECTION-PAGE",
    "GAP-CONCENTRATION-MONITOR-PAGE",
    "GAP-DECISION-ITEMS-PAGE",
    "PAGE-BAL-MOVE-001",
    "PAGE-PNL-ATTR-WB-001",
    "PAGE-RISK-001",
    "PAGE-BOND-001",
    "PAGE-BOND-ANALYSIS-001",
    "GAP-STOCK-ANALYSIS-PAGE",
    "GAP-PLATFORM-CONFIG-PAGE",
    "GAP-NEWS-EVENTS-PAGE",
    "GAP-TEAM-PERFORMANCE-PAGE",
    "GAP-KPI-PERFORMANCE-PAGE",
]

GOVERNANCE_READY_FOR_AUDIT_PAGE_SLUGS = [
    "product-category-pnl",
    "balance-analysis",
    "average-balance",
    "cashflow-projection",
    "concentration-monitor",
    "decision-items",
    "balance-movement-analysis",
    "pnl-attribution",
    "risk-tensor",
    "bond-dashboard",
    "bond-analysis",
    "stock-analysis",
    "platform-config",
    "news-events",
    "team-performance",
    "kpi-performance",
]


class McpProcess:
    def __init__(
        self,
        mode: str,
        env: dict[str, str] | None = None,
        *,
        command: list[str] | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        process_env = os.environ.copy()
        process_env.update(env or {})
        process_command = command or [sys.executable, str(MCP_SCRIPT), mode]
        self.process = subprocess.Popen(
            process_command,
            cwd=REPO_ROOT,
            env=process_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._next_id = 1
        self._timeout_seconds = timeout_seconds

    def close(self) -> None:
        _terminate_mcp_process(self.process)

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
        headers = _read_mcp_headers_with_timeout(
            self.process,
            timeout_seconds=self._timeout_seconds,
            timeout_message="Timed out waiting for MCP response",
        )
        length = None
        for header in headers:
            if header.lower().startswith("content-length:"):
                length = int(header.split(":", 1)[1].strip())
        assert length is not None
        body = _read_mcp_body_with_timeout(
            self.process,
            length=length,
            timeout_seconds=self._timeout_seconds,
            timeout_message="Timed out waiting for MCP response body",
        )
        return json.loads(body.decode("utf-8"))

    def _stderr(self) -> str:
        if self.process.stderr is None:
            return ""
        return self.process.stderr.read().decode("utf-8", errors="replace")


def _request_initialize(
    command: str,
    args: list[str],
    cwd: Path,
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    process = subprocess.Popen(
        [command, *args],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).encode("utf-8")
        assert process.stdin is not None
        process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        process.stdin.flush()

        assert process.stdout is not None
        headers = _read_mcp_headers_with_timeout(
            process,
            timeout_seconds=timeout_seconds,
            timeout_message="Timed out waiting for MCP initialize response",
        )
        length = None
        for header in headers:
            if header.lower().startswith("content-length:"):
                length = int(header.split(":", 1)[1].strip())
        assert length is not None
        body = _read_mcp_body_with_timeout(
            process,
            length=length,
            timeout_seconds=timeout_seconds,
            timeout_message="Timed out waiting for MCP initialize response body",
        )
        return dict(json.loads(body.decode("utf-8")))
    finally:
        _terminate_mcp_process(process)


def _terminate_mcp_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except OSError:
            pass


def _read_mcp_headers_with_timeout(
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
    timeout_message: str,
) -> list[str]:
    result_queue: queue.Queue[bytes] = queue.Queue()

    def _readline() -> None:
        assert process.stdout is not None
        result_queue.put(process.stdout.readline())

    headers: list[str] = []
    while True:
        reader = threading.Thread(target=_readline, daemon=True)
        reader.start()
        try:
            line = result_queue.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            _terminate_mcp_process(process)
            reader.join(timeout=1)
            raise TimeoutError(timeout_message) from exc
        assert line, process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        if line in (b"\r\n", b"\n"):
            return headers
        headers.append(line.decode("ascii").strip())


def _read_mcp_body_with_timeout(
    process: subprocess.Popen[bytes],
    *,
    length: int,
    timeout_seconds: float,
    timeout_message: str,
) -> bytes:
    result_queue: queue.Queue[bytes] = queue.Queue()

    def _read_body() -> None:
        assert process.stdout is not None
        result_queue.put(process.stdout.read(length))

    reader = threading.Thread(target=_read_body, daemon=True)
    reader.start()
    try:
        body = result_queue.get(timeout=timeout_seconds)
    except queue.Empty as exc:
        _terminate_mcp_process(process)
        reader.join(timeout=1)
        raise TimeoutError(timeout_message) from exc
    if len(body) != length:
        _terminate_mcp_process(process)
        reader.join(timeout=1)
        raise TimeoutError(timeout_message)
    return body


def _resolve_config_cwd(raw_cwd: str) -> Path:
    return (REPO_ROOT / raw_cwd).resolve()


def test_mcp_initialize_helper_times_out_when_server_is_silent(tmp_path: Path) -> None:
    silent_server = tmp_path / "silent_mcp_server.py"
    silent_server.write_text(
        "import time\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )

    with pytest.raises(TimeoutError, match="Timed out waiting for MCP initialize response"):
        _request_initialize(
            sys.executable,
            [str(silent_server)],
            tmp_path,
            timeout_seconds=0.25,
        )


def test_mcp_initialize_helper_times_out_when_server_body_is_incomplete(tmp_path: Path) -> None:
    partial_server = tmp_path / "partial_mcp_server.py"
    partial_server.write_text(
        "import sys, time\n"
        "sys.stdout.buffer.write(b'Content-Length: 20\\r\\n\\r\\n{}')\n"
        "sys.stdout.buffer.flush()\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )

    with pytest.raises(TimeoutError, match="Timed out waiting for MCP initialize response body"):
        _request_initialize(
            sys.executable,
            [str(partial_server)],
            tmp_path,
            timeout_seconds=0.25,
        )


def test_mcp_process_request_times_out_when_server_is_silent(tmp_path: Path) -> None:
    silent_server = tmp_path / "silent_mcp_server.py"
    silent_server.write_text(
        "import time\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    server = McpProcess(
        "unused",
        command=[sys.executable, str(silent_server)],
        timeout_seconds=0.25,
    )
    try:
        with pytest.raises(TimeoutError, match="Timed out waiting for MCP response"):
            server.request("initialize")
        assert server.process.poll() is not None
    finally:
        server.close()


def _expected_all_seeded_closure_execution_sequence() -> list[dict[str, Any]]:
    return [
        {
            "sequence": 1,
            "blocker_type": "record_gap_remediation",
            "next_step": "use_record_gap_execution_plan",
            "execution_plan": "record_gap_execution_plan",
            "execution_stage": "remediation_type_batches",
            "execution_stage_detail": {
                "stage": 1,
                "stage_type": "remediation_type_batches",
                "work_item_group": "record_remediation_work_items",
                "work_item_count": 2,
                "page_count": len(CATALOG_DATE_RECORD_GAP_PAGE_SLUGS),
                "record_gap_page_count": len(CATALOG_DATE_RECORD_GAP_PAGE_SLUGS),
                "ready_manual_review_page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
                "includes_ready_manual_review_pages": False,
                "suggested_tool_call_count": 4,
                "arguments": {
                    "page_slugs": CATALOG_DATE_RECORD_GAP_PAGE_SLUGS,
                },
                "next_step": "batch_requirements_and_blueprint_collection_by_remediation_type",
                "uses_work_item_groups": ["record_remediation_work_items"],
                "must_complete_before": [
                    "evidence_key_batches",
                    "review_lane_batches",
                ],
                "writes_governance_records": False,
                "executes_tool_calls": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
            },
            "page_count": len(CATALOG_DATE_RECORD_GAP_PAGE_SLUGS),
            "work_item_count": 15,
            "source_work_item_group_counts": {
                "record_remediation_work_items": 2,
                "record_remediation_evidence_work_items": 4,
                "record_remediation_review_lane_work_items": 9,
            },
            "arguments": {
                "page_slugs": CATALOG_DATE_RECORD_GAP_PAGE_SLUGS,
            },
            "must_complete_before": [
                "manual_audit_review",
                "business_owner_approval",
            ],
            "queue_grants_closure": False,
        },
        {
            "sequence": 2,
            "blocker_type": "catalog_date_lineage_evidence_collection",
            "next_step": "use_evidence_collection_execution_plan",
            "execution_plan": "evidence_collection_execution_plan",
            "execution_stage": "catalog_date_evidence_batches",
            "execution_stage_detail": {
                "stage": 1,
                "stage_type": "catalog_date_evidence_batches",
                "work_item_group": "suggested_tool_call_work_items",
                "tool": "moss-data-catalog.get_page_catalog_date_evidence",
                "work_item_count": 3,
                "page_count": len(CONFIGURED_CATALOG_DATE_PAGE_SLUGS),
                "suggested_tool_call_count": 3,
                "arguments": {
                    "page_slugs": CONFIGURED_CATALOG_DATE_PAGE_SLUGS,
                },
                "next_step": "collect_catalog_date_evidence_by_review_lane",
                "uses_work_item_groups": ["suggested_tool_call_work_items"],
                "must_complete_before": [
                    "lineage_evidence_batches",
                    "governance_validation_batches",
                ],
                "writes_governance_records": False,
                "executes_tool_calls": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
            },
            "page_count": len(ALL_SEEDED_CATALOG_DATE_LINEAGE_PAGE_SLUGS),
            "work_item_count": 14,
            "source_work_item_group_counts": {
                "suggested_tool_call_work_items": 14,
            },
            "arguments": {
                "page_slugs": ALL_SEEDED_CATALOG_DATE_LINEAGE_PAGE_SLUGS,
            },
            "must_complete_before": [
                "manual_audit_review",
                "business_owner_approval",
            ],
            "queue_grants_closure": False,
        },
        {
            "sequence": 3,
            "blocker_type": "manual_audit_review",
            "next_step": "use_manual_audit_review_execution_plan",
            "execution_plan": "manual_audit_review_execution_plan",
            "execution_stage": "audit_review_queue_batches",
            "execution_stage_detail": {
                "stage": 1,
                "stage_type": "audit_review_queue_batches",
                "work_item_group": "record_remediation_work_items",
                "tool": "moss-lineage-evidence.get_page_governance_audit_review_queue",
                "work_item_count": 1,
                "page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
                "suggested_tool_call_count": 1,
                "arguments": {
                    "page_slugs": READY_FOR_AUDIT_PAGE_SLUGS,
                },
                "next_step": "collect_manual_audit_review_queue_without_approval",
                "uses_work_item_groups": ["record_remediation_work_items"],
                "must_complete_before": [
                    "audit_evidence_packet_queue_batches",
                ],
                "writes_governance_records": False,
                "executes_tool_calls": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
            },
            "page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
            "work_item_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
            "source_work_item_group_counts": {
                "record_remediation_work_items": 2,
            },
            "arguments": {
                "page_slugs": READY_FOR_AUDIT_PAGE_SLUGS,
            },
            "must_complete_before": ["business_owner_approval"],
            "queue_grants_closure": False,
        },
        {
            "sequence": 4,
            "blocker_type": "business_owner_approval",
            "next_step": "use_business_owner_approval_execution_plan",
            "execution_plan": "business_owner_approval_execution_plan",
            "execution_stage": "owner_approval_request_batches",
            "execution_stage_detail": {
                "stage": 1,
                "stage_type": "owner_approval_request_batches",
                "work_item_group": "record_remediation_work_items",
                "work_item_count": 1,
                "page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
                "arguments": {
                    "page_slugs": READY_FOR_AUDIT_PAGE_SLUGS,
                },
                "next_step": "prepare_owner_approval_request_after_manual_audit_review",
                "uses_work_item_groups": ["record_remediation_work_items"],
                "must_complete_before": ["owner_approval_receipt_review_batches"],
                "writes_governance_records": False,
                "executes_tool_calls": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
            },
            "page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
            "work_item_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
            "source_work_item_group_counts": {
                "record_remediation_work_items": 2,
            },
            "arguments": {
                "page_slugs": READY_FOR_AUDIT_PAGE_SLUGS,
            },
            "must_complete_before": [],
            "queue_grants_closure": False,
        },
    ]


def _expected_closure_dispatch_packet(
    sequence: list[dict[str, Any]],
    *,
    status: str,
) -> dict[str, Any]:
    dispatch_steps = [
        {
            "sequence": step["sequence"],
            "blocker_type": step["blocker_type"],
            "dispatch_action": step["next_step"],
            "execution_plan": step["execution_plan"],
            "execution_stage": step["execution_stage"],
            "page_count": step["page_count"],
            "work_item_count": step["work_item_count"],
            "arguments": step["arguments"],
            "execution_stage_detail": step["execution_stage_detail"],
            "source_work_item_group_counts": step["source_work_item_group_counts"],
            "must_complete_before": step["must_complete_before"],
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": False,
        }
        for step in sequence
    ]
    return {
        "scope": "catalog_date_lineage_closure_dispatch_packet",
        "status": status,
        "dispatch_step_count": len(dispatch_steps),
        "next_dispatch_step": dispatch_steps[0] if dispatch_steps else None,
        "dispatch_steps": dispatch_steps,
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
        "queue_grants_closure": False,
    }


def _expected_clean_closure_dispatch_packet_scope_audit(
    work_item_count: int,
) -> dict[str, Any]:
    return {
        "work_item_count": work_item_count,
        "checked_work_item_group": "closure_dispatch_packet.dispatch_steps",
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
        "queue_grants_closure": False,
        "scope_violations": [],
        "execution_target_violations": [],
        "packet_consistency_violations": [],
        "source_consistency_violations": [],
    }


def _expected_clean_next_closure_action_scope_audit(
    work_item_count: int,
) -> dict[str, Any]:
    return {
        "work_item_count": work_item_count,
        "checked_work_item_group": "closure_readiness.next_closure_action",
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
        "queue_grants_closure": False,
        "scope_violations": [],
        "execution_target_violations": [],
        "source_consistency_violations": [],
    }


def _expected_no_closure_scope_flags() -> dict[str, bool]:
    return {
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
        "queue_grants_closure": False,
    }


def test_project_mcp_config_declares_read_only_surfaces() -> None:
    payload = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    servers = payload["mcpServers"]

    assert set(servers) >= {
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "moss-data-quality",
        "playwright",
    }
    assert servers["gitnexus"]["command"] == "node"
    assert servers["gitnexus"]["args"] == ["scripts/mcp/gitnexus_mcp_launcher.mjs"]
    if os.name != "nt":
        return
    assert servers["moss-metric-contracts"]["command"] == "cmd.exe"
    assert servers["moss-metric-contracts"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_contracts.cmd",
    ]
    assert servers["moss-lineage-evidence"]["command"] == "cmd.exe"
    assert servers["moss-lineage-evidence"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_lineage.cmd",
    ]
    assert servers["moss-data-catalog"]["command"] == "cmd.exe"
    assert servers["moss-data-catalog"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_catalog.cmd",
    ]
    assert servers["moss-data-quality"]["command"] == "cmd.exe"
    assert servers["moss-data-quality"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_data_quality.cmd",
    ]
    assert servers["playwright"]["args"][-1] == "@playwright/mcp@latest"


def test_project_mcp_config_pins_mcp_cwd_for_compatible_clients() -> None:
    if os.name != "nt":
        return

    payload = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    servers = payload["mcpServers"]

    for name in (
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "moss-data-quality",
        "playwright",
    ):
        assert _resolve_config_cwd(servers[name]["cwd"]) == REPO_ROOT


def test_project_codex_config_declares_read_only_surfaces() -> None:
    payload = tomllib.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    servers = payload["mcp_servers"]

    assert set(servers) >= {
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "moss-data-quality",
        "playwright",
    }
    assert servers["gitnexus"]["command"] == "node"
    assert servers["gitnexus"]["args"] == ["scripts/mcp/gitnexus_mcp_launcher.mjs"]
    if os.name != "nt":
        return
    assert servers["moss-metric-contracts"]["command"] == "cmd.exe"
    assert servers["moss-metric-contracts"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_contracts.cmd",
    ]
    assert servers["moss-lineage-evidence"]["command"] == "cmd.exe"
    assert servers["moss-lineage-evidence"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_lineage.cmd",
    ]
    assert servers["moss-data-catalog"]["command"] == "cmd.exe"
    assert servers["moss-data-catalog"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_catalog.cmd",
    ]
    assert servers["moss-data-quality"]["command"] == "cmd.exe"
    assert servers["moss-data-quality"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_data_quality.cmd",
    ]
    assert servers["playwright"]["command"] == "npx"
    assert servers["playwright"]["args"][-1] == "@playwright/mcp@latest"


def test_project_codex_config_pins_mcp_cwd_for_app_launches() -> None:
    if os.name != "nt":
        return

    payload = tomllib.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    servers = payload["mcp_servers"]

    for name in (
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "moss-data-quality",
        "playwright",
    ):
        assert _resolve_config_cwd(servers[name]["cwd"]) == REPO_ROOT


def test_moss_codex_mcp_entries_handshake_from_declared_cwd() -> None:
    if os.name != "nt":
        return

    payload = tomllib.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    servers = payload["mcp_servers"]

    for name, expected_server_info_name in (
        ("moss-metric-contracts", "moss-metric-contracts"),
        ("moss-lineage-evidence", "moss-lineage-evidence"),
        ("moss-data-catalog", "moss-data-catalog"),
        ("moss-data-quality", "moss-data-quality"),
    ):
        response = _request_initialize(
            servers[name]["command"],
            list(servers[name]["args"]),
            _resolve_config_cwd(servers[name]["cwd"]),
        )
        assert response["result"]["serverInfo"]["name"] == expected_server_info_name


def test_moss_launcher_handshake_is_cwd_independent() -> None:
    response = _request_initialize(
        sys.executable,
        [str(REPO_ROOT / "scripts" / "mcp" / "moss_mcp_launcher.py"), "metric-contracts"],
        REPO_ROOT / "tests",
    )
    assert response["result"]["serverInfo"]["name"] == "moss-metric-contracts"


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


@pytest.mark.parametrize(
    (
        "page_slug",
        "frontend_route",
        "primary_api",
        "truth_marker",
        "backend_touchpoint",
        "frontend_touchpoint",
        "test_touchpoint",
        "golden_sample",
        "guardrail_marker",
        "alias",
    ),
    [
        (
            "product-category-pnl",
            "/product-category-pnl",
            "/ui/pnl/product-category",
            "product_category_pnl_formal_read_model",
            "backend/app/services/product_category_source_service.py",
            "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx",
            "tests/test_product_category_pnl_flow.py",
            "tests/golden_samples/GS-PROD-CAT-PNL-A",
            "zqtz holdings-side logic",
            "/product-category-pnl",
        ),
        (
            "dashboard-home",
            "/",
            "/ui/home/snapshot",
            "home_snapshot_envelope",
            "backend/app/services/executive_service.py",
            "frontend/src/features/workbench/pages/DashboardPage.tsx",
            "tests/test_home_snapshot_endpoint.py",
            "tests/golden_samples/GS-EXEC-OVERVIEW-A",
            "formal metric truth",
            "/dashboard",
        ),
        (
            "risk-tensor",
            "/risk-tensor",
            "/api/risk/tensor",
            "RiskTensorPayload",
            "backend/app/services/risk_tensor_service.py",
            "frontend/src/features/risk-tensor/RiskTensorPage.tsx",
            "tests/test_risk_tensor_api.py",
            "tests/golden_samples/GS-RISK-A",
            "warning quality",
            "/risk-tensor",
        ),
        (
            "bond-dashboard",
            "/bond-dashboard",
            "/api/bond-dashboard/headline-kpis",
            "bond_dashboard.headline_kpis",
            "backend/app/services/bond_dashboard_service.py",
            "frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx",
            "tests/test_bond_dashboard_api_contract.py",
            "tests/golden_samples/GS-BOND-HEADLINE-A",
            "pending_confirmation=true",
            "PAGE-BOND-001",
        ),
        (
            "positions",
            "/positions",
            "/api/positions/bonds",
            "positions.bonds.list",
            "backend/app/services/positions_service.py",
            "frontend/src/features/positions/components/PositionsView.tsx",
            "tests/test_positions_api_contract.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "GAP-POS-LIST",
            "PAGE-POS-001",
        ),
        (
            "market-data",
            "/market-data",
            "/ui/preview/macro-foundation",
            "GAP-MKT-DATA",
            "backend/app/services/macro_vendor_service.py",
            "frontend/src/features/market-data/pages/MarketDataPage.tsx",
            "frontend/src/test/MarketDataPage.test.tsx",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "mixed-source",
            "PAGE-MKT-001",
        ),
        (
            "macro-toolkit",
            "/macro-toolkit",
            "/ui/macro/toolkit/analysis",
            "macro_toolkit.analysis",
            "backend/app/api/routes/macro_toolkit.py",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
            "frontend/src/test/MacroToolkitPage.test.tsx",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "tooling/analysis",
            "PAGE-MACRO-TOOLKIT-001",
        ),
        (
            "macro-observation",
            "/macro-observation",
            "/ui/macro/toolkit/analysis",
            "read-only macro observation",
            "backend/app/api/routes/macro_toolkit.py",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
            "frontend/src/test/MacroToolkitPage.test.tsx",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "read-only",
            "PAGE-MACRO-OBS-001",
        ),
        (
            "agent",
            "/agent",
            "POST /api/agent/runs",
            "AgentEnvelope",
            "backend/app/api/routes/agent.py",
            "frontend/src/features/agent/AgentWorkbenchPage.tsx",
            "tests/test_agent_api_contract.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "read-only",
            "PAGE-AGENT-001",
        ),
        (
            "cube-query",
            "/cube-query",
            "POST /api/cube/query",
            "CubeQueryResult",
            "backend/app/api/routes/cube_query.py",
            "frontend/src/features/cube-query/pages/CubeQueryPage.tsx",
            "tests/test_cube_query_api.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "candidate query surface",
            "PAGE-CUBE-QUERY-001",
        ),
        (
            "portfolio-home",
            "/portfolio",
            "frontend aggregation: module-home/portfolio",
            "PAGE-PORTFOLIO-HOME-001",
            "backend/app/api/routes/balance_analysis.py",
            "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
            "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
            "tests/golden_samples/GS-PORTFOLIO-HOME-A",
            "module home",
            "PAGE-PORTFOLIO-HOME-001",
        ),
        (
            "market-home",
            "/market-overview",
            "frontend aggregation: module-home/market",
            "PAGE-MARKET-HOME-001",
            "backend/app/api/routes/macro_vendor.py",
            "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
            "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "module home",
            "PAGE-MARKET-HOME-001",
        ),
        (
            "risk-home",
            "/risk-overview",
            "frontend aggregation: module-home/risk",
            "PAGE-RISK-HOME-001",
            "backend/app/api/routes/risk_tensor.py",
            "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
            "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "module home",
            "PAGE-RISK-HOME-001",
        ),
        (
            "performance-home",
            "/performance",
            "frontend aggregation: module-home/performance",
            "PAGE-PERFORMANCE-HOME-001",
            "backend/app/api/routes/kpi.py",
            "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
            "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "module home",
            "PAGE-PERFORMANCE-HOME-001",
        ),
        (
            "reports-home",
            "/reports",
            "frontend aggregation: module-home/governance",
            "PAGE-REPORTS-HOME-001",
            "backend/app/api/routes/health.py",
            "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
            "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "module home",
            "PAGE-REPORTS-HOME-001",
        ),
        (
            "pnl-bridge",
            "/pnl-bridge",
            "/api/pnl/bridge",
            "PnlBridgePayload",
            "backend/app/services/pnl_bridge_service.py",
            "frontend/src/features/pnl/PnlBridgePage.tsx",
            "tests/test_pnl_bridge_core.py",
            "tests/golden_samples/GS-BRIDGE-A",
            "bridge warnings",
            "/pnl-bridge",
        ),
        (
            "balance-analysis",
            "/balance-analysis",
            "/ui/balance-analysis/overview",
            "balance_analysis_overview_envelope",
            "backend/app/services/balance_analysis_service.py",
            "frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx",
            "tests/test_balance_analysis_api.py",
            "tests/golden_samples/GS-BAL-OVERVIEW-A",
            "formal balance truth",
            "/balance-analysis",
        ),
        (
            "pnl",
            "/pnl",
            "/api/pnl/overview",
            "pnl_overview_envelope",
            "backend/app/services/pnl_service.py",
            "frontend/src/features/pnl/PnlPage.tsx",
            "tests/test_pnl_api_contract.py",
            "tests/golden_samples/GS-PNL-OVERVIEW-A",
            "formal PnL truth",
            "/pnl",
        ),
        (
            "ledger-pnl",
            "/ledger-pnl",
            "/api/ledger-pnl/summary",
            "ledger_pnl.summary",
            "backend/app/services/ledger_pnl_service.py",
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
            "tests/test_ledger_pnl_service.py",
            "tests/golden_samples/GS-LEDGER-PNL-SUMMARY-A",
            "candidate display metrics",
            "PAGE-LEDGER-PNL-001",
        ),
        (
            "executive-overview",
            "/dashboard",
            "/ui/home/overview",
            "executive.overview",
            "backend/app/services/executive_service.py",
            "frontend/src/features/executive-dashboard/components/OverviewSection.tsx",
            "tests/test_executive_dashboard_endpoints.py",
            "tests/golden_samples/GS-EXEC-OVERVIEW-A",
            "analytical overlay",
            "PAGE-EXEC-OVERVIEW-001",
        ),
        (
            "executive-summary",
            "/dashboard",
            "/ui/home/summary",
            "executive.summary",
            "backend/app/services/executive_service.py",
            "frontend/src/features/executive-dashboard/components/SummarySection.tsx",
            "tests/test_executive_service_contract.py",
            "tests/golden_samples/GS-EXEC-SUMMARY-A",
            "narrative-only",
            "PAGE-EXEC-SUMMARY-001",
        ),
        (
            "executive-pnl-attribution",
            "/dashboard",
            "/ui/pnl/attribution",
            "executive.pnl-attribution",
            "backend/app/services/executive_service.py",
            "frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx",
            "tests/test_executive_dashboard_endpoints.py",
            "tests/golden_samples/GS-EXEC-PNL-ATTR-A",
            "analytical overlay",
            "PAGE-EXEC-PNL-ATTR-001",
        ),
        (
            "pnl-attribution",
            "/pnl-attribution",
            "/api/pnl-attribution/volume-rate",
            "VolumeRateAttributionPayload",
            "backend/app/services/pnl_attribution_service.py",
            "frontend/src/features/pnl-attribution/pages/PnlAttributionPage.tsx",
            "tests/test_pnl_attribution_workbench_contract.py",
            "tests/golden_samples/GS-PNL-ATTR-WB-A",
            "formal PnL overview",
            "/pnl-attribution",
        ),
        (
            "operations-analysis",
            "/operations-analysis",
            "/ui/pnl/product-category",
            "GAP-OPS-MACRO-FX",
            "backend/app/services/product_category_pnl_service.py",
            "frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx",
            "frontend/src/test/OperationsAnalysisPage.test.tsx",
            "tests/golden_samples/GS-PROD-CAT-PNL-A",
            "temporary-exception",
            "PAGE-OPS-001",
        ),
        (
            "balance-movement-analysis",
            "/balance-movement-analysis",
            "/ui/balance-movement-analysis",
            "AccountingAssetMovementPayload",
            "backend/app/services/accounting_asset_movement_service.py",
            "frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx",
            "tests/test_accounting_asset_movement_api.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "formal balance truth",
            "PAGE-BAL-MOVE-001",
        ),
        (
            "liability-analytics",
            "/liability-analytics",
            "/api/risk/buckets",
            "liability_analytics.risk_buckets",
            "backend/app/services/liability_analytics_service.py",
            "frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx",
            "tests/test_liability_analytics_api.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "mixed-source",
            "/liability-analytics",
        ),
    ],
)
def test_metric_contracts_mcp_exposes_seeded_page_trace_bundles(
    page_slug: str,
    frontend_route: str,
    primary_api: str,
    truth_marker: str,
    backend_touchpoint: str,
    frontend_touchpoint: str,
    test_touchpoint: str,
    golden_sample: str,
    guardrail_marker: str,
    alias: str,
) -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_trace_bundle" for tool in tools)

        result = server.request(
            "tools/call",
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": page_slug}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["page_slug"] == page_slug
        assert payload["frontend_route"] == frontend_route
        assert payload["primary_api"] == primary_api
        assert any(truth_marker in item for item in payload["truth_chain"])
        assert backend_touchpoint in payload["backend_touchpoints"]
        assert frontend_touchpoint in payload["frontend_touchpoints"]
        assert test_touchpoint in payload["test_touchpoints"]
        if golden_sample == "NO_DEDICATED_GOLDEN_SAMPLE":
            assert payload["golden_samples"] == []
            assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        else:
            assert golden_sample in payload["golden_samples"]
            assert all(str(sample).startswith("tests/golden_samples/") for sample in payload["golden_samples"])
        assert payload["contract_docs"]
        assert payload["supporting_apis"]
        assert payload["verification_focus"]
        assert payload["guardrails"]
        assert any(guardrail_marker in guardrail for guardrail in payload["guardrails"])
        if page_slug == "product-category-pnl":
            assert "docs/pnl/product-category-pnl-first-certification-packet.md" in payload["contract_docs"]
            assert "docs/pnl/product-category-pnl-owner-decision-packet.md" in payload["contract_docs"]
            assert "docs/pnl/product-category-pnl-business-owner-approval-template.md" in payload["contract_docs"]
            assert "docs/pnl/product-category-pnl-approval-runbook.md" in payload["contract_docs"]
            assert "docs/pnl/product-category-remaining-blockers.md" in payload["contract_docs"]
            assert any("without approving certification" in item for item in payload["truth_chain"])
            assert any("without capturing them" in item for item in payload["truth_chain"])
            assert any("remains unsigned" in item for item in payload["truth_chain"])
            assert any("closure_approved=false" in item for item in payload["truth_chain"])

        alias_result = server.request(
            "tools/call",
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
        )
        alias_payload = json.loads(alias_result["content"][0]["text"])
        assert alias_payload["page_slug"] == page_slug
    finally:
        server.close()


def test_liability_analytics_trace_bundle_preserves_mixed_source_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "liability-analytics",
            "/liability-analytics",
            "PAGE-LIAB-ANALYTICS-001",
            "/api/risk/buckets",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "liability-analytics"

        assert payload["page_id"] == "PAGE-LIAB-ANALYTICS-001"
        assert payload["primary_api"] == "/api/risk/buckets"
        assert "/api/analysis/yield_metrics" in payload["supporting_apis"]
        assert "/api/analysis/liabilities/counterparty" in payload["supporting_apis"]
        assert "/api/liabilities/monthly" in payload["supporting_apis"]
        assert "/ui/liability/business-context" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("MTR-LIAB-001" in item for item in payload["truth_chain"])
        assert any("MTR-LIAB-007" in item for item in payload["truth_chain"])
        assert any("liability_analytics.risk_buckets" in item for item in payload["truth_chain"])
        assert any("liability_analytics_compat" in item for item in payload["truth_chain"])
        assert any("mixed-source" in item for item in payload["guardrails"])
        assert any("compatibility" in item for item in payload["guardrails"])
        assert any("formal balance" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_formal_pnl_trace_bundle_preserves_formal_total_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in ("pnl", "/pnl", "PAGE-PNL-001", "/api/pnl/overview"):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "pnl"

        assert payload["page_id"] == "PAGE-PNL-001"
        assert payload["primary_api"] == "/api/pnl/overview"
        assert "/api/pnl/dates" in payload["supporting_apis"]
        assert "/api/pnl/data" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-PNL-OVERVIEW-A" in payload["golden_samples"]
        assert "tests/golden_samples/GS-PNL-DATA-A" in payload["golden_samples"]
        assert any("MTR-PNL-001" in item for item in payload["truth_chain"])
        assert any("MTR-PNL-104" in item for item in payload["truth_chain"])
        assert any("pnl_overview_envelope" in item for item in payload["truth_chain"])
        assert any("PnlDataPayload" in item for item in payload["truth_chain"])
        assert any("formal PnL truth" in item for item in payload["guardrails"])
        assert any("standardized total" in item for item in payload["guardrails"])
        assert any("executive analytical overlay" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_ledger_pnl_trace_bundle_preserves_candidate_source_contract_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "ledger-pnl",
            "/ledger-pnl",
            "PAGE-LEDGER-PNL-001",
            "/api/ledger-pnl/summary",
            "/api/ledger-pnl/formal-financial-indicators",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "ledger-pnl"

        assert payload["page_id"] == "PAGE-LEDGER-PNL-001"
        assert payload["primary_api"] == "/api/ledger-pnl/summary"
        assert "/api/ledger-pnl/dates" in payload["supporting_apis"]
        assert "/api/ledger-pnl/data" in payload["supporting_apis"]
        assert "/api/ledger-pnl/formal-financial-indicators" in payload["supporting_apis"]
        assert payload["golden_samples"] == ["tests/golden_samples/GS-LEDGER-PNL-SUMMARY-A"]
        assert any("MTR-LPN-001" in item for item in payload["truth_chain"])
        assert any("MTR-LPN-003" in item for item in payload["truth_chain"])
        assert any("ledger_pnl.formal_financial_indicator_source_contract" in item for item in payload["truth_chain"])
        assert any("GS-LEDGER-PNL-FIN-IND-202603-B" in item for item in payload["truth_chain"])
        assert "docs/pnl/ledger-pnl-owner-evidence-packet.md" in payload["contract_docs"]
        assert "docs/pnl/ledger-pnl-sign-off-packet.md" in payload["contract_docs"]
        assert "docs/pnl/ledger-pnl-governance-audit-packet.md" in payload["contract_docs"]
        assert "docs/pnl/ledger-pnl-business-owner-approval-template.md" in payload["contract_docs"]
        assert "docs/pnl/ledger-pnl-owner-signoff-runbook.md" in payload["contract_docs"]
        assert any("preserving formal_use_allowed=false" in item for item in payload["truth_chain"])
        assert any("candidate sign-off evidence only" in item for item in payload["truth_chain"])
        assert any("remains unsigned" in item for item in payload["truth_chain"])
        assert any("without promoting Ledger PnL to formal PnL truth" in item for item in payload["truth_chain"])
        assert any("pending_confirmation=true" in item for item in payload["guardrails"])
        assert any("formal PnL" in item for item in payload["guardrails"])
        assert any("formal financial indicator truth" in item for item in payload["guardrails"])
        assert any("zero" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_bond_analysis_trace_bundle_preserves_candidate_owner_handoff_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "bond-analysis",
            "/bond-analysis",
            "PAGE-BOND-ANALYSIS-001",
            "/api/bond-analytics/action-attribution",
            "GS-BOND-ANALYSIS-ACTION-ATTR-A",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "bond-analysis"

        assert payload["page_id"] == "PAGE-BOND-ANALYSIS-001"
        assert payload["primary_api"] == "/api/bond-analytics/action-attribution"
        assert "/api/bond-analytics/dv01-risk" in payload["supporting_apis"]
        assert "/api/bond-analytics/krd-curve-risk" in payload["supporting_apis"]
        assert payload["golden_samples"] == ["tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A"]
        assert "docs/pnl/bond-analysis-owner-evidence-packet.md" in payload["contract_docs"]
        assert "docs/pnl/bond-analysis-sign-off-packet.md" in payload["contract_docs"]
        assert "docs/pnl/bond-analysis-governance-audit-packet.md" in payload["contract_docs"]
        assert "docs/pnl/bond-analysis-business-owner-approval-template.md" in payload["contract_docs"]
        assert "docs/pnl/bond-analysis-fixed-income-convention-decision-draft.md" in payload["contract_docs"]
        assert "docs/pnl/bond-analysis-owner-signoff-runbook.md" in payload["contract_docs"]
        assert any("PAGE-BOND-ANALYSIS-001" in item for item in payload["truth_chain"])
        assert any("PAGE-BOND-001" in item and "must not certify /bond-analysis" in item for item in payload["truth_chain"])
        assert any("preserving formal_use_allowed=false" in item for item in payload["truth_chain"])
        assert any("candidate sign-off evidence only" in item for item in payload["truth_chain"])
        assert any("remains unsigned" in item for item in payload["truth_chain"])
        assert any("review-only convention evidence" in item for item in payload["truth_chain"])
        assert any("without promoting Bond Analysis to formal fixed-income metric truth" in item for item in payload["truth_chain"])
        assert any("do not certify /bond-analysis" in item for item in payload["guardrails"])
        assert any("Do not use PAGE-BOND-001" in item for item in payload["guardrails"])
        assert any("Do not promote DV01" in item for item in payload["guardrails"])
        assert any("result_meta" in item for item in payload["verification_focus"])
    finally:
        server.close()


def test_executive_overview_trace_bundle_preserves_analytical_overlay_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "executive-overview",
            "/ui/home/overview",
            "PAGE-EXEC-OVERVIEW-001",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "executive-overview"

        assert payload["page_id"] == "PAGE-EXEC-OVERVIEW-001"
        assert payload["primary_api"] == "/ui/home/overview"
        assert "tests/golden_samples/GS-EXEC-OVERVIEW-A" in payload["golden_samples"]
        assert any("MTR-EXEC-001" in item for item in payload["truth_chain"])
        assert any("MTR-EXEC-004" in item for item in payload["truth_chain"])
        assert any("executive.overview" in item for item in payload["truth_chain"])
        assert any("caliber_label" in item for item in payload["truth_chain"])
        assert any("analytical overlay" in item for item in payload["guardrails"])
        assert any("formal source-of-truth" in item for item in payload["guardrails"])
        assert any("silent downgrade" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_executive_summary_trace_bundle_preserves_narrative_contract_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "executive-summary",
            "/ui/home/summary",
            "PAGE-EXEC-SUMMARY-001",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "executive-summary"

        assert payload["page_id"] == "PAGE-EXEC-SUMMARY-001"
        assert payload["primary_api"] == "/ui/home/summary"
        assert "/ui/home/overview" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-EXEC-SUMMARY-A" in payload["golden_samples"]
        assert any("GS-EXEC-SUMMARY-A" in item for item in payload["truth_chain"])
        assert any("SummaryPayload" in item for item in payload["truth_chain"])
        assert any("executive.summary" in item for item in payload["truth_chain"])
        assert any("narrative-only" in item for item in payload["truth_chain"])
        assert any("title" in item and "points.length" in item for item in payload["truth_chain"])
        assert any("metric dictionary" in item for item in payload["guardrails"])
        assert any("narrative" in item and "formal" in item for item in payload["guardrails"])
        assert any("upstream metric" in item for item in payload["guardrails"])
        assert any("report_date" in item for item in payload["verification_focus"])
    finally:
        server.close()


def test_executive_pnl_attribution_trace_bundle_preserves_overlay_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "executive-pnl-attribution",
            "/ui/pnl/attribution",
            "PAGE-EXEC-PNL-ATTR-001",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "executive-pnl-attribution"

        assert payload["page_id"] == "PAGE-EXEC-PNL-ATTR-001"
        assert payload["primary_api"] == "/ui/pnl/attribution"
        assert "tests/golden_samples/GS-EXEC-PNL-ATTR-A" in payload["golden_samples"]
        assert any("MTR-EXEC-101" in item for item in payload["truth_chain"])
        assert any("MTR-EXEC-106" in item for item in payload["truth_chain"])
        assert any("executive.pnl-attribution" in item for item in payload["truth_chain"])
        assert any("analytical overlay" in item for item in payload["guardrails"])
        assert any("formal bridge" in item for item in payload["guardrails"])
        assert any("formal PnL truth" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_pnl_attribution_workbench_trace_bundle_preserves_workbench_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "pnl-attribution",
            "/pnl-attribution",
            "PAGE-PNL-ATTR-WB-001",
            "/api/pnl-attribution/volume-rate",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "pnl-attribution"

        assert payload["page_id"] == "PAGE-PNL-ATTR-WB-001"
        assert payload["primary_api"] == "/api/pnl-attribution/volume-rate"
        assert "/api/pnl-attribution/tpl-market" in payload["supporting_apis"]
        assert "/api/pnl-attribution/composition" in payload["supporting_apis"]
        assert "/api/pnl-attribution/advanced/summary" in payload["supporting_apis"]
        assert "/api/pnl-attribution/campisi/four-effects" in payload["supporting_apis"]
        assert payload["golden_samples"] == ["tests/golden_samples/GS-PNL-ATTR-WB-A"]
        assert any(
            "does not replace formal PnL overview" in item
            for item in payload["verification_focus"]
        )
        assert any("MTR-PAT-001" in item for item in payload["truth_chain"])
        assert any("MTR-PAT-304" in item for item in payload["truth_chain"])
        assert any("VolumeRateAttributionPayload" in item for item in payload["truth_chain"])
        assert any("Campisi" in item for item in payload["truth_chain"])
        assert "docs/pnl/pnl-attribution-owner-evidence-packet.md" in payload["contract_docs"]
        assert "docs/pnl/pnl-attribution-sign-off-packet.md" in payload["contract_docs"]
        assert "docs/pnl/pnl-attribution-governance-audit-packet.md" in payload["contract_docs"]
        assert "docs/pnl/pnl-attribution-business-owner-approval-template.md" in payload["contract_docs"]
        assert "docs/pnl/pnl-attribution-owner-signoff-runbook.md" in payload["contract_docs"]
        assert any("formal_use_allowed=false" in item for item in payload["truth_chain"])
        assert any("does not approve page closure" in item for item in payload["truth_chain"])
        assert any("remains unsigned" in item for item in payload["truth_chain"])
        assert any("without promoting formal PnL truth" in item for item in payload["truth_chain"])
        assert any("formal PnL overview" in item for item in payload["guardrails"])
        assert any("executive analytical overlay" in item for item in payload["guardrails"])
        assert any("front" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_operations_analysis_trace_bundle_preserves_mixed_source_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "operations-analysis",
            "/operations-analysis",
            "PAGE-OPS-001",
            "/ui/pnl/product-category",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "operations-analysis"

        assert payload["page_id"] == "PAGE-OPS-001"
        assert payload["primary_api"] == "/ui/pnl/product-category"
        assert "/ui/pnl/product-category/dates" in payload["supporting_apis"]
        assert "/ui/balance-analysis/overview" in payload["supporting_apis"]
        assert "/ui/preview/source-foundation" in payload["supporting_apis"]
        assert "/ui/macro/choice-series/latest" in payload["supporting_apis"]
        assert "/ui/market-data/fx/formal-status" in payload["supporting_apis"]
        assert "/ui/news/choice-events/latest" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-PROD-CAT-PNL-A" in payload["golden_samples"]
        assert "tests/golden_samples/GS-BAL-OVERVIEW-A" in payload["golden_samples"]
        assert any("MTR-PCP-001" in item for item in payload["truth_chain"])
        assert any("MTR-PCP-003" in item for item in payload["truth_chain"])
        assert any("GAP-OPS-MACRO-FX" in item for item in payload["truth_chain"])
        assert any("supplemental topic-entry" in item for item in payload["guardrails"])
        assert any("temporary-exception" in item for item in payload["guardrails"])
        assert any("Do not create or promote MTR-OPS-* metrics" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_balance_movement_trace_bundle_preserves_movement_explanation_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "balance-movement-analysis",
            "/balance-movement-analysis",
            "PAGE-BAL-MOVE-001",
            "/ui/balance-movement-analysis",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "balance-movement-analysis"

        assert payload["page_id"] == "PAGE-BAL-MOVE-001"
        assert payload["primary_api"] == "/ui/balance-movement-analysis"
        assert "/ui/balance-movement-analysis/dates" in payload["supporting_apis"]
        assert "/ui/balance-movement-analysis/refresh" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("MTR-BMV-001" in item for item in payload["truth_chain"])
        assert any("MTR-BMV-004" in item for item in payload["truth_chain"])
        assert any("AccountingAssetMovementPayload" in item for item in payload["truth_chain"])
        assert any("rv_accounting_asset_movement_v2" in item for item in payload["truth_chain"])
        assert any("formal balance truth" in item for item in payload["guardrails"])
        assert any("selected report dates" in item for item in payload["guardrails"])
        assert any("demo rows" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_balance_analysis_trace_bundle_preserves_formal_workbook_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "balance-analysis",
            "/balance-analysis",
            "PAGE-BALANCE-001",
            "/ui/balance-analysis/overview",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "balance-analysis"

        assert payload["page_id"] == "PAGE-BALANCE-001"
        assert payload["primary_api"] == "/ui/balance-analysis/overview"
        assert "/ui/balance-analysis/dates" in payload["supporting_apis"]
        assert "/ui/balance-analysis" in payload["supporting_apis"]
        assert "/ui/balance-analysis/workbook" in payload["supporting_apis"]
        assert "/ui/balance-analysis/summary" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-BAL-OVERVIEW-A" in payload["golden_samples"]
        assert "tests/golden_samples/GS-BAL-WORKBOOK-A" in payload["golden_samples"]
        assert "docs/pnl/balance-analysis-owner-evidence-packet.md" in payload["contract_docs"]
        assert "docs/pnl/balance-analysis-business-owner-approval-template.md" in payload["contract_docs"]
        assert "docs/pnl/balance-analysis-owner-signoff-runbook.md" in payload["contract_docs"]
        assert "docs/audits/2026-06-07-balance-analysis-live-smoke-evidence.md" in payload["contract_docs"]
        assert any("MTR-BAL-001" in item for item in payload["truth_chain"])
        assert any("MTR-BAL-203" in item for item in payload["truth_chain"])
        assert any("balance_analysis_overview_envelope" in item for item in payload["truth_chain"])
        assert any("BalanceAnalysisWorkbookPayload" in item for item in payload["truth_chain"])
        assert any("post-signing verification commands" in item for item in payload["truth_chain"])
        assert any("formal_use_allowed=true and closure_approved=false" in item for item in payload["truth_chain"])
        assert any("advanced_attribution" in item for item in payload["guardrails"])
        assert any("formal balance truth" in item for item in payload["guardrails"])
        assert any("frontend" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_pnl_bridge_trace_bundle_preserves_warning_and_source_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in ("pnl-bridge", "/pnl-bridge", "PAGE-BRIDGE-001", "/api/pnl/bridge"):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "pnl-bridge"

        assert payload["page_id"] == "PAGE-BRIDGE-001"
        assert payload["primary_api"] == "/api/pnl/bridge"
        assert "/api/pnl/dates" in payload["supporting_apis"]
        assert "/api/pnl/refresh" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-BRIDGE-A" in payload["golden_samples"]
        assert "tests/golden_samples/GS-BRIDGE-WARN-B" in payload["golden_samples"]
        assert any("MTR-BRG-001" in item for item in payload["truth_chain"])
        assert any("MTR-BRG-105" in item for item in payload["truth_chain"])
        assert any("PnlBridgePayload" in item for item in payload["truth_chain"])
        assert any("pnl_bridge_envelope" in item for item in payload["truth_chain"])
        assert any("bridge warnings" in item for item in payload["guardrails"])
        assert any("future-only" in item for item in payload["guardrails"])
        assert any("frontend" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_dashboard_home_trace_bundle_preserves_mixed_source_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in ("dashboard-home", "/", "/dashboard"):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "dashboard-home"

        supporting_apis = set(payload["supporting_apis"])
        assert "/ui/home/snapshot" == payload["primary_api"]
        assert "/ui/risk/overview" not in supporting_apis
        assert "/ui/home/alerts" not in supporting_apis
        assert "/ui/home/contribution" not in supporting_apis
        assert any("analytical/mixed-source" in item for item in payload["guardrails"])
        assert any("not a full-page formal sample" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_risk_tensor_trace_bundle_preserves_formal_warning_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in ("risk-tensor", "/risk-tensor", "PAGE-RISK-001"):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "risk-tensor"

        assert payload["page_id"] == "PAGE-RISK-001"
        assert payload["primary_api"] == "/api/risk/tensor"
        assert "/api/risk/tensor/dates" in payload["supporting_apis"]
        assert "/ui/risk/overview" not in payload["supporting_apis"]
        assert "tests/golden_samples/GS-RISK-A" in payload["golden_samples"]
        assert "tests/golden_samples/GS-RISK-WARN-B" in payload["golden_samples"]
        assert any("MTR-RSK-001" in item for item in payload["truth_chain"])
        assert any("fact_formal_risk_tensor_daily" in item for item in payload["truth_chain"])
        assert any("warning quality" in item for item in payload["guardrails"])
        assert any("duration denominator" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_bond_dashboard_trace_bundle_preserves_candidate_metric_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "bond-dashboard",
            "/bond-dashboard",
            "PAGE-BOND-001",
            "/api/bond-dashboard/headline-kpis",
            "/api/bond-dashboard/risk-indicators",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "bond-dashboard"

        assert payload["page_id"] == "PAGE-BOND-001"
        assert payload["primary_api"] == "/api/bond-dashboard/headline-kpis"
        assert "/api/bond-dashboard/dates" in payload["supporting_apis"]
        assert "/api/bond-dashboard/risk-indicators" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-BOND-HEADLINE-A" in payload["golden_samples"]
        assert any("MTR-BOND-001" in item for item in payload["truth_chain"])
        assert any("MTR-BOND-004" in item for item in payload["truth_chain"])
        assert any("GAP-BOND-DASH-HL" in item for item in payload["truth_chain"])
        assert any("GAP-BOND-DASH-RISK" in item for item in payload["truth_chain"])
        assert any("BondDashboardHeadlinePayload" in item for item in payload["truth_chain"])
        assert any("source_surface=\"bond_analytics\"" in item for item in payload["truth_chain"])
        assert any("pending_confirmation=true" in item for item in payload["guardrails"])
        assert any("GS-RISK-A" in item for item in payload["guardrails"])
        assert any("MTR-BAL" in item for item in payload["guardrails"])
        assert any("frontend" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_positions_trace_bundle_preserves_list_candidate_and_dual_date_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "positions",
            "/positions",
            "PAGE-POS-001",
            "/api/positions/bonds",
            "/api/positions/interbank",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "positions"

        assert payload["page_id"] == "PAGE-POS-001"
        assert payload["primary_api"] == "/api/positions/bonds"
        assert "/api/positions/bonds/sub_types" in payload["supporting_apis"]
        assert "/api/positions/interbank/product_types" in payload["supporting_apis"]
        assert "/api/positions/counterparty/bonds" in payload["supporting_apis"]
        assert "/api/positions/stats/rating" in payload["supporting_apis"]
        assert "/api/positions/customer/details" in payload["supporting_apis"]
        assert "GET /ui/balance-analysis/dates" in payload["truth_chain"]
        assert payload["golden_samples"] == []
        assert any("MTR-POS-001" in item for item in payload["truth_chain"])
        assert any("MTR-POS-002" in item for item in payload["truth_chain"])
        assert any("GAP-POS-LIST" in item for item in payload["truth_chain"])
        assert any("BondPositionsPageResponse" in item for item in payload["truth_chain"])
        assert any("InterbankPositionsPageResponse" in item for item in payload["truth_chain"])
        assert any("pending_confirmation=true" in item for item in payload["guardrails"])
        assert any("bound_sample_id=none" in item for item in payload["guardrails"])
        assert any("balance-analysis dates" in item for item in payload["guardrails"])
        assert any("formal PnL" in item for item in payload["guardrails"])
        assert any("frontend" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_market_data_trace_bundle_preserves_mixed_source_candidate_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "market-data",
            "/market-data",
            "PAGE-MKT-001",
            "/ui/preview/macro-foundation",
            "/ui/market-data/rates",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "market-data"

        assert payload["page_id"] == "PAGE-MKT-001"
        assert payload["primary_api"] == "/ui/preview/macro-foundation"
        assert "/ui/market-data/rates" in payload["supporting_apis"]
        assert "/ui/market-data/fx/formal-status" in payload["supporting_apis"]
        assert "/ui/market-data/fx/analytical" in payload["supporting_apis"]
        assert "/ui/market-data/ncd-funding-proxy" in payload["supporting_apis"]
        assert "/ui/market-data/livermore" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("MTR-MKT-001" in item for item in payload["truth_chain"])
        assert any("GAP-MKT-DATA" in item for item in payload["truth_chain"])
        assert any("formal rates fragment" in item for item in payload["truth_chain"])
        assert any("ncd-funding-proxy" in item for item in payload["truth_chain"])
        assert any("Livermore" in item for item in payload["truth_chain"])
        assert any("source-pending" in item for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("full-page formal truth" in item for item in payload["guardrails"])
        assert any("static demo" in item for item in payload["guardrails"])
        assert any("NCD" in item and "proxy" in item for item in payload["guardrails"])
        assert any("Livermore" in item and "risk_exit" in item for item in payload["guardrails"])
        assert any("MTR-" in item and "promote" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_cross_asset_trace_bundle_preserves_mixed_source_analytical_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "cross-asset",
            "/cross-asset",
            "GAP-CROSS-ASSET-PAGE",
            "/api/macro-bond-linkage/analysis",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "cross-asset"

        assert payload["page_id"] == "GAP-CROSS-ASSET-PAGE"
        assert payload["frontend_route"] == "/cross-asset"
        assert payload["primary_api"] == "frontend aggregation: cross-asset drivers"
        assert "/ui/macro/choice-series/latest" in payload["supporting_apis"]
        assert "/api/macro-bond-linkage/analysis" in payload["supporting_apis"]
        assert "/ui/market-data/ncd-funding-proxy" in payload["supporting_apis"]
        assert "/ui/market-data/livermore/signal-confluence" in payload["supporting_apis"]
        assert "/ui/news/choice-events/latest" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("temporary-exception" in item for item in payload["truth_chain"])
        assert any("macro-bond analytical linkage" in item for item in payload["truth_chain"])
        assert any("NCD" in item and "proxy" in item for item in payload["guardrails"])
        assert any("trading instructions" in item for item in payload["guardrails"])
        assert any("static demo" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_decision_items_trace_bundle_preserves_read_write_governance_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "decision-items",
            "/decision-items",
            "/ui/balance-analysis/decision-items/status",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "decision-items"

        assert payload["page_id"] == "GAP-DECISION-ITEMS-PAGE"
        assert payload["frontend_route"] == "/decision-items"
        assert payload["primary_api"] == "/ui/balance-analysis/decision-items"
        assert "/ui/balance-analysis/decision-items/status" in payload["supporting_apis"]
        assert "/ui/balance-analysis/current-user" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("temporary-exception" in item for item in payload["truth_chain"])
        assert any("balance_analysis_decision_status" in item for item in payload["truth_chain"])
        assert any("can_write_decision_status" in item for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("permissions" in item for item in payload["verification_focus"])
        assert any("read/write" in item for item in payload["guardrails"])
        assert any("MTR-*" in item and "promote" in item for item in payload["guardrails"])
        assert any("status updates" in item and "approval" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_kpi_performance_trace_bundle_preserves_scoring_write_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "kpi-performance",
            "/kpi",
            "GAP-KPI-PERFORMANCE-PAGE",
            "/api/kpi/values/summary",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "kpi-performance"

        assert payload["page_id"] == "GAP-KPI-PERFORMANCE-PAGE"
        assert payload["frontend_route"] == "/kpi"
        assert payload["primary_api"] == "/api/kpi/values/summary"
        assert "/api/kpi/owners" in payload["supporting_apis"]
        assert "/api/kpi/metrics" in payload["supporting_apis"]
        assert "/api/kpi/values/batch" in payload["supporting_apis"]
        assert "/api/kpi/fetch_and_recalc" in payload["supporting_apis"]
        assert "/api/kpi/report" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("temporary-exception" in item for item in payload["truth_chain"])
        assert any("MTR-KPI-001" in item and "candidate" in item for item in payload["truth_chain"])
        assert any("write" in item and "permission" in item for item in payload["verification_focus"])
        assert any("candidate read/write scoring workbench" in item for item in payload["guardrails"])
        assert any("write operations" in item and "approval" in item for item in payload["guardrails"])
        assert any("static demo" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_stock_analysis_trace_bundle_preserves_observational_livermore_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "stock-analysis",
            "/stock-analysis",
            "GAP-STOCK-ANALYSIS-PAGE",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "stock-analysis"

        assert payload["page_id"] == "GAP-STOCK-ANALYSIS-PAGE"
        assert payload["frontend_route"] == "/stock-analysis"
        assert payload["primary_api"] == "/ui/market-data/livermore"
        assert "/ui/market-data/livermore/signal-confluence" in payload["supporting_apis"]
        assert "/ui/market-data/livermore/stock-detail" in payload["supporting_apis"]
        assert "/ui/market-data/livermore/candidate-history" in payload["supporting_apis"]
        assert "/ui/market-data/livermore/strategy-score" in payload["supporting_apis"]
        assert "/ui/market-data/livermore/strategy-optimization" in payload["supporting_apis"]
        assert "/ui/market-data/livermore/cycle-proxy-backtest" in payload["supporting_apis"]
        assert "/ui/market-data/livermore/candidate-history-portfolio-backtest" in payload["supporting_apis"]
        assert "/ui/market-data/livermore/sector-rank-series" in payload["supporting_apis"]
        assert payload["golden_samples"] == ["tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A"]
        assert any("temporary-exception" in item for item in payload["truth_chain"])
        assert any("observation-only" in item for item in payload["truth_chain"])
        assert any("risk_exit" in item and "backend-owned" in item for item in payload["truth_chain"])
        assert any("GS-STOCK-ANALYSIS-OBS-A" in item for item in payload["verification_focus"])
        assert any("no PAGE-STOCK" in item for item in payload["verification_focus"])
        assert any("trading instructions" in item for item in payload["guardrails"])
        assert any("formal metric truth" in item for item in payload["guardrails"])
        assert any("MTR-*" in item and "promote" in item for item in payload["guardrails"])
        assert any("readiness" in item and "visible" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_metric_contracts_evidence_readiness_matrix_flags_candidate_pages_without_formal_promotion() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_evidence_readiness" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_evidence_readiness",
                "arguments": {
                    "page_slugs": [
                        "PAGE-LEDGER-PNL-001",
                        "PAGE-BOND-001",
                        "PAGE-POS-001",
                        "PAGE-MKT-001",
                        "GAP-STOCK-ANALYSIS-PAGE",
                        "PAGE-OPS-001",
                    ]
                },
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-trace-readiness"
        assert "does not prove live catalog, date, lineage, or formal metric approval" in payload["disclaimer"]
        rows = {row["page_id"]: row for row in payload["pages"]}
        assert set(rows) == {
            "PAGE-LEDGER-PNL-001",
            "PAGE-BOND-001",
            "PAGE-POS-001",
            "PAGE-MKT-001",
            "GAP-STOCK-ANALYSIS-PAGE",
            "PAGE-OPS-001",
        }

        ledger = rows["PAGE-LEDGER-PNL-001"]
        assert ledger["formal_use_allowed"] is False
        assert ledger["approval_status"] == "candidate_or_pending"
        assert ledger["checks"]["golden_sample"]["status"] == "page_dto_only"
        assert "tests/golden_samples/GS-LEDGER-PNL-SUMMARY-A" in ledger["checks"]["golden_sample"]["anchors"]
        assert any("MTR-LPN-001" in anchor for anchor in ledger["checks"]["lineage_mapping"]["anchors"])
        assert any("QDB" in anchor or "ledger" in anchor for anchor in ledger["checks"]["catalog_date"]["anchors"])
        assert any("dictionary-level approval" in gap for gap in ledger["residual_gaps"])

        bond = rows["PAGE-BOND-001"]
        assert bond["formal_use_allowed"] is False
        assert bond["approval_status"] == "candidate_or_pending"
        assert bond["checks"]["trace_bundle"]["status"] == "present"
        assert bond["checks"]["golden_sample"]["status"] == "page_dto_only"
        assert "tests/golden_samples/GS-BOND-HEADLINE-A" in bond["checks"]["golden_sample"]["anchors"]
        assert any("MTR-BOND-001" in anchor for anchor in bond["checks"]["lineage_mapping"]["anchors"])
        assert any("fact_formal_bond_analytics_daily" in anchor for anchor in bond["checks"]["catalog_date"]["anchors"])
        assert any("direct page-keyed governance" in gap for gap in bond["residual_gaps"])
        assert any("dictionary-level approval" in gap for gap in bond["residual_gaps"])

        positions = rows["PAGE-POS-001"]
        assert positions["formal_use_allowed"] is False
        assert positions["checks"]["golden_sample"]["status"] == "missing"
        assert any("MTR-POS-001" in anchor for anchor in positions["checks"]["lineage_mapping"]["anchors"])
        assert any("zqtz_bond_daily_snapshot" in anchor for anchor in positions["checks"]["catalog_date"]["anchors"])
        assert any("dedicated golden sample" in gap for gap in positions["residual_gaps"])

        market = rows["PAGE-MKT-001"]
        assert market["formal_use_allowed"] is False
        assert market["approval_status"] == "mixed_source_or_observational"
        assert any("GAP-MKT-DATA" in anchor for anchor in market["checks"]["lineage_mapping"]["anchors"])
        assert any("full data-catalog/date review" in gap for gap in market["residual_gaps"])

        stock = rows["GAP-STOCK-ANALYSIS-PAGE"]
        assert stock["formal_use_allowed"] is False
        assert stock["approval_status"] == "gap_or_observational"
        assert stock["checks"]["golden_sample"]["status"] == "page_dto_only"
        assert "tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A" in stock["checks"]["golden_sample"]["anchors"]
        assert any("formal stock-analysis truth" in gap for gap in stock["residual_gaps"])
        assert any("trading" in guardrail for guardrail in stock["guardrails"])

        ops = rows["PAGE-OPS-001"]
        assert ops["formal_use_allowed"] is False
        assert ops["approval_status"] == "mixed_source_or_observational"
        assert any("GAP-OPS-MACRO-FX" in anchor for anchor in ops["checks"]["lineage_mapping"]["anchors"])
        assert any("mixed-source" in gap for gap in ops["residual_gaps"])
        assert all("MTR-OPS" not in anchor for anchor in ops["checks"]["lineage_mapping"]["anchors"])

        assert payload["summary"] == {
            "page_count": 6,
            "formal_use_allowed_count": 0,
            "candidate_or_gap_count": 6,
            "direct_catalog_date_review_required_count": 6,
        }

        default_result = server.request("tools/call", {"name": "get_page_evidence_readiness", "arguments": {}})
        default_payload = json.loads(default_result["content"][0]["text"])
        assert [row["page_id"] for row in default_payload["pages"]] == [
            "PAGE-LEDGER-PNL-001",
            "PAGE-BOND-001",
            "PAGE-POS-001",
            "PAGE-MKT-001",
            "GAP-STOCK-ANALYSIS-PAGE",
            "PAGE-OPS-001",
        ]
        assert default_payload["summary"] == payload["summary"]
    finally:
        server.close()


def test_metric_contracts_evidence_readiness_matrix_reports_candidate_metric_watchlist() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_evidence_readiness", "arguments": {"page_slugs": ["PAGE-BOND-001"]}},
        )
        payload = json.loads(result["content"][0]["text"])

        watchlist = {item["metric_id"]: item for item in payload["candidate_metric_watchlist"]}
        assert set(watchlist) >= {
            "MTR-CFP-001",
            "MTR-CFP-002",
            "MTR-CFP-003",
            "MTR-CFP-004",
            "MTR-CON-001",
            "MTR-CON-002",
            "MTR-CON-003",
            "MTR-CON-004",
            "MTR-TEAM-001",
            "MTR-PLT-001",
            "MTR-PLT-002",
            "MTR-PLT-003",
        }
        assert watchlist["MTR-CFP-001"]["formal_use_allowed"] is False
        assert watchlist["MTR-CON-001"]["formal_use_allowed"] is False
        assert watchlist["MTR-PLT-001"]["formal_use_allowed"] is False
        assert "page-contract-pending" in watchlist["MTR-CFP-001"]["status"]
        assert "lineage records" in watchlist["MTR-CON-001"]["residual_gap"]
        assert "/platform-config" == watchlist["MTR-PLT-001"]["page"]
        assert "data-quality approval" in watchlist["MTR-PLT-001"]["residual_gap"]
    finally:
        server.close()


def test_metric_contracts_evidence_readiness_has_explicit_status_for_every_seeded_page() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        all_pages = [
            "product-category-pnl",
            "dashboard-home",
            "executive-overview",
            "executive-summary",
            "balance-analysis",
            "bank-ledger-dashboard",
            "cashflow-projection",
            "concentration-monitor",
            "balance-movement-analysis",
            "pnl",
            "ledger-pnl",
            "pnl-by-business",
            "executive-pnl-attribution",
            "pnl-attribution",
            "operations-analysis",
            "liability-analytics",
            "pnl-bridge",
            "risk-tensor",
            "bond-dashboard",
            "positions",
            "market-data",
            "stock-analysis",
            "macro-toolkit",
            "macro-observation",
            "agent",
            "cube-query",
            "news-events",
            "portfolio-home",
            "market-home",
            "risk-home",
            "performance-home",
            "reports-home",
        ]
        result = server.request(
            "tools/call",
            {"name": "get_page_evidence_readiness", "arguments": {"page_slugs": all_pages}},
        )
        payload = json.loads(result["content"][0]["text"])
        rows = {row["page_id"]: row for row in payload["pages"]}

        assert set(rows) == {
            "GAP-BANK-LEDGER-DASHBOARD-PAGE",
            "GAP-CASHFLOW-PROJECTION-PAGE",
            "GAP-CONCENTRATION-MONITOR-PAGE",
            "GAP-NEWS-EVENTS-PAGE",
            "GAP-STOCK-ANALYSIS-PAGE",
            "PAGE-AGENT-001",
            "PAGE-BAL-MOVE-001",
            "PAGE-BALANCE-001",
            "PAGE-BOND-001",
            "PAGE-BRIDGE-001",
            "PAGE-CUBE-QUERY-001",
            "PAGE-DASH-001",
            "PAGE-EXEC-OVERVIEW-001",
            "PAGE-EXEC-PNL-ATTR-001",
            "PAGE-EXEC-SUMMARY-001",
            "PAGE-LEDGER-PNL-001",
            "PAGE-LIAB-ANALYTICS-001",
            "PAGE-MACRO-OBS-001",
            "PAGE-MACRO-TOOLKIT-001",
            "PAGE-MARKET-HOME-001",
            "PAGE-MKT-001",
            "PAGE-OPS-001",
            "PAGE-PERFORMANCE-HOME-001",
            "PAGE-PNL-001",
            "PAGE-PNL-ATTR-WB-001",
            "PAGE-PNL-BY-BUSINESS-001",
            "PAGE-PORTFOLIO-HOME-001",
            "PAGE-POS-001",
            "PAGE-PROD-CAT-001",
            "PAGE-REPORTS-HOME-001",
            "PAGE-RISK-001",
            "PAGE-RISK-HOME-001",
        }
        assert rows["PAGE-PROD-CAT-001"]["approval_status"] == "formal_or_governed"
        assert rows["PAGE-PNL-001"]["approval_status"] == "formal_or_governed"
        assert rows["PAGE-BRIDGE-001"]["approval_status"] == "formal_or_governed"
        assert rows["PAGE-BALANCE-001"]["approval_status"] == "formal_or_governed"
        assert rows["PAGE-RISK-001"]["approval_status"] == "formal_or_governed"
        assert rows["GAP-BANK-LEDGER-DASHBOARD-PAGE"]["approval_status"] == "candidate_or_pending"
        assert rows["GAP-CASHFLOW-PROJECTION-PAGE"]["approval_status"] == "candidate_or_pending"
        assert rows["GAP-CONCENTRATION-MONITOR-PAGE"]["approval_status"] == "candidate_or_pending"
        assert rows["PAGE-BAL-MOVE-001"]["approval_status"] == "candidate_or_pending"
        assert rows["PAGE-PNL-ATTR-WB-001"]["approval_status"] == "candidate_or_pending"
        portfolio = rows["PAGE-PORTFOLIO-HOME-001"]
        assert portfolio["formal_use_allowed"] is False
        assert portfolio["approval_status"] == "mixed_source_or_observational"
        assert portfolio["checks"]["golden_sample"]["status"] == "supporting_or_fragment_only"
        assert "tests/golden_samples/GS-PORTFOLIO-HOME-A" in portfolio["checks"]["golden_sample"]["anchors"]
        assert not any("dedicated golden sample" in gap for gap in portfolio["residual_gaps"])
        assert {row["approval_status_source"] for row in rows.values()} == {"explicit_status_map"}
        assert payload["summary"]["formal_use_allowed_count"] == 5
    finally:
        server.close()


def test_metric_contracts_unmapped_approval_readiness_fails_closed() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_approval_readiness(
        {"page_id": "PAGE-NEW-001"},
        "candidate mixed-source observational only pending_confirmation=true no dedicated golden sample",
    )

    assert result == {
        "status": "unclassified_review_required",
        "source": "unclassified_fallback",
    }


def test_lineage_evidence_manual_review_mcp_work_items_use_explicit_mcp_allowlist() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_governance_manual_review_mcp_work_items(
        [
            {
                "audit_review_queue_item": {
                    "page_id": "PAGE-PROD-CAT-001",
                    "page_slug": "product-category-pnl",
                    "manual_review_steps": [
                        {
                            "check": "page_contract_review",
                            "evidence_to_collect": ["page contract"],
                            "suggested_tools": ["moss-metric-contracts.get_page_trace_bundle"],
                            "tool_calls": [
                                {
                                    "tool": "moss-metric-contracts.get_page_trace_bundle",
                                    "arguments": {"page_slug": "product-category-pnl"},
                                }
                            ],
                        },
                        {
                            "check": "business_owner_approval",
                            "evidence_to_collect": ["business owner review"],
                            "suggested_tools": ["manual sign-off"],
                            "tool_calls": [
                                {
                                    "tool": "manual-signoff.capture",
                                    "arguments": {"page_slug": "product-category-pnl"},
                                }
                            ],
                        },
                    ],
                },
            }
        ]
    )

    assert result == [
        {
            "check": "page_contract_review",
            "page_count": 1,
            "pages": [
                {
                    "page_id": "PAGE-PROD-CAT-001",
                    "page_slug": "product-category-pnl",
                    "tool_calls": [
                        {
                            "tool": "moss-metric-contracts.get_page_trace_bundle",
                            "arguments": {"page_slug": "product-category-pnl"},
                        }
                    ],
                }
            ],
            "evidence_to_collect": ["page contract"],
            "suggested_tools": ["moss-metric-contracts.get_page_trace_bundle"],
            "approval_boundary": "manual_review_mcp_evidence_collection_only",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
            },
        }
    ]


def test_lineage_evidence_manual_review_scope_audit_flags_missing_or_true_boundaries() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_governance_manual_review_scope_audit(
        [
            {
                "check": "ui_api_payload_review",
                "evidence_scope": {
                    "writes_governance_records": False,
                    "approves_metric_or_page": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": True,
                },
            },
            {
                "check": "business_owner_approval",
                "evidence_scope": {
                    "writes_governance_records": False,
                    "approves_metric_or_page": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                },
            },
        ]
    )

    assert result == {
        "work_item_count": 2,
        "checked_work_item_groups": ["manual_review_work_items"],
        "writes_governance_records": False,
        "approves_metric_or_page": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": True,
        "captures_business_owner_approval": False,
        "scope_violations": [
            {
                "work_item_group": "manual_review_work_items",
                "work_item_index": 0,
                "scope_key": "runs_ui_or_api_smoke",
                "scope_value": True,
            },
            {
                "work_item_group": "manual_review_work_items",
                "work_item_index": 0,
                "scope_key": "captures_business_owner_approval",
                "scope_value": None,
            },
        ],
    }


def test_lineage_evidence_direct_record_remediation_scope_audit_counts_next_steps() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_governance_direct_record_remediation_scope_audit(
        {
            "blocked_by_record_gap_next_steps": [
                {
                    "page_id": "PAGE-BOND-001",
                    "next_step": "complete_existing_direct_record_fields_then_preflight",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                }
            ],
            "direct_record_remediation_work_items": [
                {
                    "work_type": "complete_existing_direct_record",
                    "page_id": "PAGE-BOND-001",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                }
            ],
        }
    )

    assert result == {
        "work_item_count": 2,
        "checked_work_item_groups": [
            "blocked_by_record_gap_next_steps",
            "create_direct_record_evidence_work_items",
            "create_direct_record_table_anchor_work_items",
            "direct_record_remediation_work_items",
            "repair_direct_record_evidence_work_items",
        ],
        "writes_governance_records": False,
        "approves_metric_or_page": False,
        "proves_page_execution": False,
        "executes_tool_calls": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "scope_violations": [],
    }


def test_lineage_evidence_direct_record_remediation_scope_audit_flags_execution_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_governance_direct_record_remediation_scope_audit(
        {
            "blocked_by_record_gap_next_steps": [
                {
                    "page_id": "PAGE-BOND-001",
                    "next_step": "complete_existing_direct_record_fields_then_preflight",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": True,
                        "runs_ui_or_api_smoke": True,
                        "captures_business_owner_approval": True,
                    },
                }
            ],
        }
    )

    assert result == {
        "work_item_count": 1,
        "checked_work_item_groups": [
            "blocked_by_record_gap_next_steps",
            "create_direct_record_evidence_work_items",
            "create_direct_record_table_anchor_work_items",
            "direct_record_remediation_work_items",
            "repair_direct_record_evidence_work_items",
        ],
        "writes_governance_records": False,
        "approves_metric_or_page": False,
        "proves_page_execution": False,
        "executes_tool_calls": True,
        "runs_ui_or_api_smoke": True,
        "captures_business_owner_approval": True,
        "scope_violations": [
            {
                "work_item_group": "blocked_by_record_gap_next_steps",
                "work_item_index": 0,
                "scope_key": "executes_tool_calls",
                "scope_value": True,
            },
            {
                "work_item_group": "blocked_by_record_gap_next_steps",
                "work_item_index": 0,
                "scope_key": "runs_ui_or_api_smoke",
                "scope_value": True,
            },
            {
                "work_item_group": "blocked_by_record_gap_next_steps",
                "work_item_index": 0,
                "scope_key": "captures_business_owner_approval",
                "scope_value": True,
            },
        ],
    }


def test_lineage_evidence_queue_closure_readiness_aggregates_counts_without_granting_closure() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_governance_queue_closure_readiness(
        page_count=3,
        ready_for_audit_review_count=2,
        blocked_by_record_gaps_count=1,
        manual_review_mcp_work_item_count=0,
        manual_review_blocker_count=0,
        manual_review_evidence_present_count=0,
        closure_approved_count=1,
    )

    assert result == {
        "page_count": 3,
        "ready_for_audit_review_count": 2,
        "blocked_by_record_gaps_count": 1,
        "manual_review_mcp_work_item_count": 0,
        "manual_review_blocker_count": 0,
        "manual_review_evidence_present_needs_review_count": 0,
        "closure_approved_count": 1,
        "closure_ready_count": 1,
        "closure_blocked_count": 2,
        "queue_grants_closure": False,
        "status": "record_remediation_required",
        "residual_closure_requirements": [
            "record_gap_remediation",
            "business_owner_approval",
        ],
    }

    capped_result = module.page_governance_queue_closure_readiness(
        page_count=3,
        ready_for_audit_review_count=2,
        blocked_by_record_gaps_count=0,
        manual_review_mcp_work_item_count=0,
        manual_review_blocker_count=0,
        manual_review_evidence_present_count=0,
        closure_approved_count=5,
    )

    assert capped_result == {
        "page_count": 3,
        "ready_for_audit_review_count": 2,
        "blocked_by_record_gaps_count": 0,
        "manual_review_mcp_work_item_count": 0,
        "manual_review_blocker_count": 0,
        "manual_review_evidence_present_needs_review_count": 0,
        "closure_approved_count": 5,
        "closure_ready_count": 2,
        "closure_blocked_count": 1,
        "queue_grants_closure": False,
        "status": "closure_not_granted_by_queue",
        "residual_closure_requirements": [],
    }


def test_lineage_evidence_queue_closure_readiness_counts_mcp_evidence_collection() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_governance_queue_closure_readiness(
        page_count=2,
        ready_for_audit_review_count=2,
        blocked_by_record_gaps_count=0,
        manual_review_mcp_work_item_count=3,
        manual_review_blocker_count=0,
        manual_review_evidence_present_count=0,
        closure_approved_count=0,
    )

    assert result == {
        "page_count": 2,
        "ready_for_audit_review_count": 2,
        "blocked_by_record_gaps_count": 0,
        "manual_review_mcp_work_item_count": 3,
        "manual_review_blocker_count": 0,
        "manual_review_evidence_present_needs_review_count": 0,
        "closure_approved_count": 0,
        "closure_ready_count": 0,
        "closure_blocked_count": 2,
        "queue_grants_closure": False,
        "status": "manual_review_required",
        "residual_closure_requirements": [
            "mcp_evidence_collection",
            "business_owner_approval",
        ],
    }


def test_lineage_evidence_present_ui_api_work_item_uses_ready_record_api() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_governance_manual_review_evidence_present_work_items(
        [
            {
                "page_id": "PAGE-PROD-CAT-001",
                "page_slug": "product-category-pnl",
                "audit_review_queue_item": {
                    "page_id": "PAGE-PROD-CAT-001",
                    "page_slug": "product-category-pnl",
                    "frontend_route": "/product-category-pnl",
                    "primary_api": "/api/seeded-contract",
                    "direct_record_validations": [
                        {
                            "validation_status": "ready_for_audit_review",
                            "record": {"primary_api": "/ui/pnl/product-category"},
                        }
                    ],
                },
                "manual_review_evidence_present": [
                    {
                        "check": "ui_api_payload_review",
                        "evidence_field": "ui_api_payload_evidence",
                        "evidence_value": ".codex-tmp/product-category-pnl-ui-api-payload.json",
                        "status": "evidence_present_needs_review",
                    }
                ],
            }
        ]
    )

    assert result == [
        {
            "check": "ui_api_payload_review",
            "page_id": "PAGE-PROD-CAT-001",
            "page_slug": "product-category-pnl",
            "frontend_route": "/product-category-pnl",
            "primary_api": "/ui/pnl/product-category",
            "evidence_field": "ui_api_payload_evidence",
            "evidence_value": ".codex-tmp/product-category-pnl-ui-api-payload.json",
            "review_status": "evidence_present_needs_review",
            "approval_boundary": "manual_review_evidence_present_review_only",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
            },
        }
    ]


def test_lineage_evidence_live_smoke_work_item_uses_ready_record_api() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_governance_manual_review_work_items(
        [
            {
                "audit_review_queue_item": {
                    "page_id": "PAGE-RISK-001",
                    "page_slug": "risk-tensor",
                    "frontend_route": "/risk-tensor",
                    "primary_api": "/api/risk/tensor",
                    "direct_record_validations": [
                        {
                            "validation_status": "ready_for_audit_review",
                            "record": {"primary_api": "/api/risk-tensor/summary"},
                        }
                    ],
                },
                "manual_review_blocker_targets": [
                    {
                        "check": "live_smoke_evidence_review",
                        "page_id": "PAGE-RISK-001",
                        "page_slug": "risk-tensor",
                        "frontend_route": "/risk-tensor",
                        "primary_api": "/api/risk/tensor",
                        "review_targets": {
                            "frontend_route": "/risk-tensor",
                            "primary_api": "/api/risk/tensor",
                            "visible_state_review_required": True,
                            "contract_page_id": "PAGE-RISK-001",
                        },
                        "approval_boundary": "manual_review_only",
                    }
                ],
            }
        ]
    )

    assert result == [
        {
            "check": "live_smoke_evidence_review",
            "page_id": "PAGE-RISK-001",
            "page_slug": "risk-tensor",
            "frontend_route": "/risk-tensor",
            "primary_api": "/api/risk-tensor/summary",
            "review_targets": {
                "frontend_route": "/risk-tensor",
                "primary_api": "/api/risk-tensor/summary",
                "visible_state_review_required": True,
                "contract_page_id": "PAGE-RISK-001",
            },
            "approval_boundary": "manual_review_only",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
            },
        }
    ]


def test_metric_contracts_evidence_readiness_keeps_executive_overlays_non_formal() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_evidence_readiness",
                "arguments": {"page_slugs": ["PAGE-EXEC-OVERVIEW-001", "PAGE-EXEC-PNL-ATTR-001"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])
        rows = {row["page_id"]: row for row in payload["pages"]}

        overview = rows["PAGE-EXEC-OVERVIEW-001"]
        assert overview["approval_status"] == "mixed_source_or_observational"
        assert overview["formal_use_allowed"] is False
        assert any("formal truth" in gap for gap in overview["residual_gaps"])

        attribution = rows["PAGE-EXEC-PNL-ATTR-001"]
        assert attribution["approval_status"] == "mixed_source_or_observational"
        assert attribution["formal_use_allowed"] is False
        assert any("formal truth" in gap for gap in attribution["residual_gaps"])
    finally:
        server.close()


def test_metric_contracts_evidence_readiness_distinguishes_query_mapping_from_contract_anchors() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_evidence_readiness", "arguments": {"page_slugs": ["macro-toolkit"]}},
        )
        payload = json.loads(result["content"][0]["text"])
        row = payload["pages"][0]

        assert row["page_id"] == "PAGE-MACRO-TOOLKIT-001"
        assert row["approval_status"] == "mixed_source_or_observational"
        assert row["formal_use_allowed"] is False
        assert row["checks"]["lineage_mapping"]["status"] == "query_mapping_present"

        overlay_result = server.request(
            "tools/call",
            {"name": "get_page_evidence_readiness", "arguments": {"page_slugs": ["executive-pnl-attribution"]}},
        )
        overlay_payload = json.loads(overlay_result["content"][0]["text"])
        overlay_row = overlay_payload["pages"][0]
        overlay_anchors = overlay_row["checks"]["lineage_mapping"]["anchors"]
        assert overlay_row["page_id"] == "PAGE-EXEC-PNL-ATTR-001"
        assert overlay_row["checks"]["lineage_mapping"]["status"] == "query_mapping_present"
        assert "/ui/pnl/attribution" in overlay_anchors
        assert "executive.pnl-attribution" in overlay_anchors
        assert "GS-EXEC-PNL-ATTR-A" in overlay_anchors
        assert "/api/pnl-attribution/volume-rate" not in overlay_anchors
        assert "/api/pnl-attribution/advanced/summary" not in overlay_anchors
    finally:
        server.close()


def test_macro_toolkit_trace_bundle_preserves_tooling_non_metric_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "macro-toolkit",
            "/macro-toolkit",
            "PAGE-MACRO-TOOLKIT-001",
            "/ui/macro/toolkit/analysis",
            "/ui/macro/toolkit/scripts",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "macro-toolkit"

        assert payload["page_id"] == "PAGE-MACRO-TOOLKIT-001"
        assert payload["primary_api"] == "/ui/macro/toolkit/analysis"
        assert "/ui/macro/toolkit/analysis/strategy-summaries" in payload["supporting_apis"]
        assert "/ui/macro/toolkit/scripts" in payload["supporting_apis"]
        assert "POST /ui/macro/toolkit/scripts/{name}/run" in payload["supporting_apis"]
        assert "POST /ui/macro/toolkit/cffex-member-rank/refresh" in payload["supporting_apis"]
        assert "POST /ui/macro/toolkit/choice-stock/refresh" in payload["supporting_apis"]
        assert "GET /ui/macro/toolkit/choice-stock/refresh-status" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("PAGE-MACRO-TOOLKIT-001" in item for item in payload["truth_chain"])
        assert any("macro_toolkit.analysis" in item for item in payload["truth_chain"])
        assert any("macro_toolkit.scripts" in item for item in payload["truth_chain"])
        assert any("MTR-MACRO" in item and "no" in item.lower() for item in payload["truth_chain"])
        assert any("source/version/run_id" in item for item in payload["truth_chain"])
        assert any("MacroToolkitContractBoundary" in item for item in payload["truth_chain"])
        assert any("operation/script outputs" in item for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("formal metric truth" in item for item in payload["guardrails"])
        assert any("investment" in item and "trade signal" in item for item in payload["guardrails"])
        assert any("static demo" in item for item in payload["guardrails"])
        assert any("fallback" in item and "stale" in item and "source gaps" in item for item in payload["guardrails"])
        assert any("frontend" in item and "recompute" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_macro_observation_trace_bundle_preserves_readonly_non_metric_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "macro-observation",
            "/macro-observation",
            "PAGE-MACRO-OBS-001",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "macro-observation"

        assert payload["page_id"] == "PAGE-MACRO-OBS-001"
        assert payload["primary_api"] == "/ui/macro/toolkit/analysis"
        assert payload["supporting_apis"] == ["/ui/macro/toolkit/analysis/strategy-summaries"]
        assert payload["golden_samples"] == []
        assert any("PAGE-MACRO-OBS-001" in item for item in payload["truth_chain"])
        assert any("read-only macro observation" in item for item in payload["truth_chain"])
        assert any("macro-observation-readonly-boundary" in item for item in payload["truth_chain"])
        assert any("MTR-MACRO" in item and "no" in item.lower() for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("script" in item and "refresh" in item for item in payload["guardrails"])
        assert any("MTR" in item and "promote" in item for item in payload["guardrails"])
        assert any("read-only boundary" in item for item in payload["guardrails"])
        assert all("scripts" not in api for api in payload["supporting_apis"])
        assert all("refresh" not in api for api in payload["supporting_apis"])
    finally:
        server.close()


def test_agent_trace_bundle_preserves_readonly_formal_use_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "agent",
            "/agent",
            "PAGE-AGENT-001",
            "POST /api/agent/runs",
            "POST /api/agent/query",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "agent"

        assert payload["page_id"] == "PAGE-AGENT-001"
        assert payload["primary_api"] == "POST /api/agent/runs"
        assert "GET /api/agent/runs/{run_id}" in payload["supporting_apis"]
        assert "POST /api/agent/query" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("AgentEnvelope" in item for item in payload["truth_chain"])
        assert any("formal_use_allowed" in item for item in payload["truth_chain"])
        assert any("read-only" in item for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("formal financial result" in item for item in payload["guardrails"])
        assert any("mutating" in item for item in payload["guardrails"])
        assert any("source lineage" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_cube_query_trace_bundle_preserves_query_tool_non_metric_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "cube-query",
            "/cube-query",
            "PAGE-CUBE-QUERY-001",
            "POST /api/cube/query",
            "GET /api/cube/dimensions/{fact_table}",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "cube-query"

        assert payload["page_id"] == "PAGE-CUBE-QUERY-001"
        assert payload["primary_api"] == "POST /api/cube/query"
        assert "GET /api/cube/dimensions/{fact_table}" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("CubeQueryResult" in item for item in payload["truth_chain"])
        assert any("candidate query surface" in item for item in payload["truth_chain"])
        assert any("no standalone MTR" in item for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("new page-level KPI" in item for item in payload["guardrails"])
        assert any("fail closed" in item for item in payload["guardrails"])
        assert any("frontend" in item and "reinterpret" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_module_home_trace_bundles_preserve_downstream_truth_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        cases = [
            (
                "portfolio-home",
                "PAGE-PORTFOLIO-HOME-001",
                "/portfolio",
                "frontend aggregation: module-home/portfolio",
                ["/balance-analysis", "/bond-dashboard", "/positions", "/pnl-attribution"],
                "standalone formal metric page",
            ),
            (
                "market-home",
                "PAGE-MARKET-HOME-001",
                "/market-overview",
                "frontend aggregation: module-home/market",
                ["/market-data", "/macro-toolkit", "/stock-analysis", "/news-events"],
                "formal market data claims",
            ),
            (
                "risk-home",
                "PAGE-RISK-HOME-001",
                "/risk-overview",
                "frontend aggregation: module-home/risk",
                ["/risk-tensor", "/concentration-monitor", "/cashflow-projection"],
                "PAGE-RISK-001 formal risk truth",
            ),
            (
                "performance-home",
                "PAGE-PERFORMANCE-HOME-001",
                "/performance",
                "frontend aggregation: module-home/performance",
                ["/kpi", "/team-performance", "/pnl-by-business", "/product-category-pnl"],
                "KPI scoring",
            ),
            (
                "reports-home",
                "PAGE-REPORTS-HOME-001",
                "/reports",
                "frontend aggregation: module-home/governance",
                ["/platform-config", "/cube-query"],
                "data-quality approval",
            ),
        ]

        for page_slug, page_id, route, primary_api, downstream_pages, guardrail_marker in cases:
            for alias in (page_slug, route, page_id):
                result = server.request(
                    "tools/call",
                    {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
                )
                payload = json.loads(result["content"][0]["text"])
                assert payload["page_slug"] == page_slug

            assert payload["page_id"] == page_id
            assert payload["frontend_route"] == route
            assert payload["primary_api"] == primary_api
            if page_id == "PAGE-PORTFOLIO-HOME-001":
                assert payload["golden_samples"] == ["tests/golden_samples/GS-PORTFOLIO-HOME-A"]
                assert not any("No dedicated golden sample" in item for item in payload["verification_focus"])
            else:
                assert payload["golden_samples"] == []
                assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
            assert any(page_id in item for item in payload["truth_chain"])
            assert any("module home" in item for item in payload["truth_chain"])
            assert any("no standalone MTR" in item for item in payload["truth_chain"])
            assert any("downstream" in item for item in payload["guardrails"])
            assert any(guardrail_marker in item for item in payload["guardrails"])
            for downstream_page in downstream_pages:
                assert downstream_page in payload["supporting_apis"]
            if page_id == "PAGE-PORTFOLIO-HOME-001":
                assert "/api/risk/tensor/dates" in payload["supporting_apis"]
                assert "backend/app/api/routes/risk_tensor.py" in payload["backend_touchpoints"]
                assert any("risk.tensor.dates" in item for item in payload["truth_chain"])
                assert any("PAGE-RISK-001 risk tensor truth" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_business_pnl_trace_bundle_preserves_page_level_analysis_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "pnl-by-business",
            "/pnl-by-business",
            "PAGE-PNL-BY-BUSINESS-001",
            "/api/pnl/by-business-ytd",
            "/api/pnl/by-business-analysis",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "pnl-by-business"

        assert payload["page_id"] == "PAGE-PNL-BY-BUSINESS-001"
        assert payload["frontend_route"] == "/pnl-by-business"
        assert payload["primary_api"] == "/api/pnl/by-business-ytd"
        assert payload["golden_samples"] == []
        assert "/api/pnl/by-business-monthly" in payload["supporting_apis"]
        assert "/api/pnl/by-business" in payload["supporting_apis"]
        assert "/api/pnl/by-business-analysis" in payload["supporting_apis"]
        assert "/api/adb/comparison" in payload["supporting_apis"]
        assert any("YTD/monthly" in item for item in payload["truth_chain"])
        assert any("formal reconciliation evidence only" in item for item in payload["truth_chain"])
        assert any("no newly approved MTR" in item for item in payload["truth_chain"])
        assert any(
            "Manual adjustment" in item and "official metric" in item for item in payload["guardrails"]
        )
        assert any("Product-category truth" in item for item in payload["guardrails"])
        assert any("Ledger-account PnL truth" in item for item in payload["guardrails"])
        assert not any("MTR-" in item for item in payload["supporting_apis"])
        assert not any("GS-" in item for item in payload["supporting_apis"])
    finally:
        server.close()


def test_average_balance_trace_bundle_preserves_adb_candidate_boundary() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "average-balance",
            "/average-balance",
            "GAP-AVERAGE-BALANCE-PAGE",
            "/api/analysis/adb",
            "/api/analysis/adb/monthly",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "average-balance"

        assert payload["page_id"] == "GAP-AVERAGE-BALANCE-PAGE"
        assert payload["frontend_route"] == "/average-balance"
        assert payload["primary_api"] == "/api/analysis/adb"
        assert "/api/analysis/adb/comparison" in payload["supporting_apis"]
        assert "/api/analysis/adb/monthly" in payload["supporting_apis"]
        assert "docs/audits/2026-06-09-average-balance-live-smoke-evidence.md" in payload["contract_docs"]
        assert payload["golden_samples"] == [
            "tests/golden_samples/GS-AVERAGE-BALANCE-A",
            "tests/golden_samples/GS-AVERAGE-BALANCE-MONTHLY-A",
        ]
        assert any("MTR-ADB-001" in item for item in payload["truth_chain"])
        assert any("PAGE-CONTRACT-PENDING:/average-balance" in item for item in payload["truth_chain"])
        assert any("GS-AVERAGE-BALANCE-A" in item for item in payload["truth_chain"])
        assert any("GS-AVERAGE-BALANCE-MONTHLY-A" in item for item in payload["truth_chain"])
        assert any("live-smoke reference evidence only" in item for item in payload["truth_chain"])
        assert "tests/test_golden_samples_capture_ready.py" in payload["test_touchpoints"]
        assert any("not formal balance truth" in item for item in payload["guardrails"])
        assert any("dedicated capture-ready daily ADB DTO sample" in item for item in payload["verification_focus"])
        assert any("dedicated capture-ready monthly ADB/NIM DTO sample" in item for item in payload["verification_focus"])
        assert not any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert not any("formal_use_allowed=true" in item for item in payload["truth_chain"])
        assert not any("PAGE-BALANCE-001 formal truth" in item and "replace" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_bank_ledger_dashboard_trace_bundle_preserves_candidate_read_model_boundary() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "bank-ledger-dashboard",
            "/bank-ledger-dashboard",
            "GAP-BANK-LEDGER-DASHBOARD-PAGE",
            "/api/ledger/dashboard",
            "/api/ledger/positions",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "bank-ledger-dashboard"

        assert payload["page_id"] == "GAP-BANK-LEDGER-DASHBOARD-PAGE"
        assert payload["frontend_route"] == "/bank-ledger-dashboard"
        assert payload["primary_api"] == "/api/ledger/dashboard"
        assert "/api/ledger/dates" in payload["supporting_apis"]
        assert "/api/ledger/positions" in payload["supporting_apis"]
        assert "/api/ledger/export/positions" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("asset_face_amount" in item for item in payload["truth_chain"])
        assert any("liability_face_amount" in item for item in payload["truth_chain"])
        assert any("net_face_exposure" in item for item in payload["truth_chain"])
        assert any("position_snapshot" in item for item in payload["truth_chain"])
        assert any("GAP-BANK-LEDGER-DASHBOARD-PAGE" in item for item in payload["truth_chain"])
        assert any("not formal PnL" in item for item in payload["guardrails"])
        assert any("not formal balance truth" in item for item in payload["guardrails"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert not any("formal_use_allowed=true" in item for item in payload["truth_chain"])
    finally:
        server.close()


def test_cashflow_projection_trace_bundle_preserves_candidate_liquidity_boundary() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "cashflow-projection",
            "/cashflow-projection",
            "GAP-CASHFLOW-PROJECTION-PAGE",
            "/api/cashflow-projection",
            "cashflow_projection.overview",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "cashflow-projection"

        assert payload["page_id"] == "GAP-CASHFLOW-PROJECTION-PAGE"
        assert payload["frontend_route"] == "/cashflow-projection"
        assert payload["primary_api"] == "/api/cashflow-projection"
        assert payload["supporting_apis"] == ["/ui/balance-analysis/dates"]
        assert payload["golden_samples"] == ["tests/golden_samples/GS-CASHFLOW-PROJECTION-A"]
        assert any("MTR-CFP-001" in item for item in payload["truth_chain"])
        assert any("PAGE-CONTRACT-PENDING:/cashflow-projection" in item for item in payload["truth_chain"])
        assert any("GS-CASHFLOW-PROJECTION-A" in item for item in payload["truth_chain"])
        assert any("fact_formal_zqtz_balance_daily" in item for item in payload["truth_chain"])
        assert any("fact_formal_tyw_balance_daily" in item for item in payload["truth_chain"])
        assert any("formal liquidity truth" in item for item in payload["guardrails"])
        assert any("GS-CASHFLOW-PROJECTION-A" in item for item in payload["verification_focus"])
        assert not any("formal_use_allowed=true" in item for item in payload["truth_chain"])
    finally:
        server.close()


def test_concentration_monitor_trace_bundle_preserves_candidate_concentration_boundary() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "concentration-monitor",
            "/concentration-monitor",
            "GAP-CONCENTRATION-MONITOR-PAGE",
            "/api/bond-analytics/credit-spread-migration",
            "bond_analytics.credit_spread_migration",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "concentration-monitor"

        assert payload["page_id"] == "GAP-CONCENTRATION-MONITOR-PAGE"
        assert payload["frontend_route"] == "/concentration-monitor"
        assert payload["primary_api"] == "/api/bond-analytics/credit-spread-migration"
        assert payload["supporting_apis"] == ["/api/bond-analytics/dates"]
        assert payload["golden_samples"] == ["tests/golden_samples/GS-CONCENTRATION-MONITOR-A"]
        assert any("MTR-CON-001" in item for item in payload["truth_chain"])
        assert any("PAGE-CONTRACT-PENDING:/concentration-monitor" in item for item in payload["truth_chain"])
        assert any("GS-CONCENTRATION-MONITOR-A" in item for item in payload["truth_chain"])
        assert any("concentration_by_issuer" in item for item in payload["truth_chain"])
        assert any("top5_concentration" in item for item in payload["truth_chain"])
        assert any("fact_formal_bond_analytics_daily" in item for item in payload["truth_chain"])
        assert any("formal risk truth" in item for item in payload["guardrails"])
        assert any("GS-CONCENTRATION-MONITOR-A" in item for item in payload["verification_focus"])
        assert not any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert not any("formal_use_allowed=true" in item for item in payload["truth_chain"])
    finally:
        server.close()


def test_team_performance_trace_bundle_preserves_candidate_performance_boundary() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "team-performance",
            "/team-performance",
            "GAP-TEAM-PERFORMANCE-PAGE",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "team-performance"

        assert payload["page_id"] == "GAP-TEAM-PERFORMANCE-PAGE"
        assert payload["frontend_route"] == "/team-performance"
        assert payload["primary_api"] == "/api/pnl/by-business-ytd"
        assert "/api/pnl/by-business-ytd" not in payload["aliases"]
        assert "/ui/pnl/product-category" not in payload["aliases"]
        assert "/api/pnl/by-business-monthly" in payload["supporting_apis"]
        assert "/ui/pnl/product-category" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("MTR-TEAM-001" in item for item in payload["truth_chain"])
        assert any("PAGE-CONTRACT-PENDING:/team-performance" in item for item in payload["truth_chain"])
        assert any("page-local workbook mapping" in item for item in payload["truth_chain"])
        assert any("formal KPI" in item for item in payload["guardrails"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert not any("formal_use_allowed=true" in item for item in payload["truth_chain"])
    finally:
        server.close()


def test_platform_config_trace_bundle_preserves_diagnostic_boundary() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "platform-config",
            "/platform-config",
            "GAP-PLATFORM-CONFIG-PAGE",
            "/ui/preview/source-foundation",
            "/health/ready",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "platform-config"

        assert payload["page_id"] == "GAP-PLATFORM-CONFIG-PAGE"
        assert payload["frontend_route"] == "/platform-config"
        assert payload["primary_api"] == "/ui/preview/source-foundation"
        assert "/health/ready" in payload["supporting_apis"]
        assert "/health/live" in payload["supporting_apis"]
        assert "/health" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("MTR-PLT-001" in item for item in payload["truth_chain"])
        assert any("MTR-PLT-002" in item for item in payload["truth_chain"])
        assert any("MTR-PLT-003" in item for item in payload["truth_chain"])
        assert any("PAGE-CONTRACT-PENDING:/platform-config" in item for item in payload["truth_chain"])
        assert any("diagnostics" in item for item in payload["truth_chain"])
        assert any("data-quality approval" in item for item in payload["guardrails"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert not any("formal_use_allowed=true" in item for item in payload["truth_chain"])
    finally:
        server.close()


def test_news_events_trace_bundle_preserves_analytical_event_boundary() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "news-events",
            "/news-events",
            "GAP-NEWS-EVENTS-PAGE",
            "/ui/news/choice-events/latest",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "news-events"

        assert payload["page_id"] == "GAP-NEWS-EVENTS-PAGE"
        assert payload["frontend_route"] == "/news-events"
        assert payload["primary_api"] == "/ui/news/choice-events/latest"
        assert payload["supporting_apis"] == []
        assert payload["golden_samples"] == []
        assert any("analytical event context" in item for item in payload["truth_chain"])
        assert any("choice_news_event" in item for item in payload["truth_chain"])
        assert any("formal metric" in item for item in payload["guardrails"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert not any("formal_use_allowed=true" in item for item in payload["truth_chain"])
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_platform_config_to_diagnostic_anchors(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "result_kind": "preview.source-foundation",
                        "source_surface": "source_preview",
                        "source_version": "sv_platform_source_preview",
                        "rule_version": "rv_platform_source_preview",
                        "created_at": "2026-06-06T00:00:00Z",
                        "formal_use_allowed": False,
                    }
                ),
                json.dumps(
                    {
                        "result_kind": "health.ready",
                        "source_surface": "health",
                        "source_version": "sv_platform_health",
                        "rule_version": "rv_platform_health",
                        "created_at": "2026-06-06T00:00:00Z",
                        "formal_use_allowed": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for query in (
            "GAP-PLATFORM-CONFIG-PAGE",
            "platform-config",
            "/platform-config",
        ):
            found = server.request(
                "tools/call",
                {"name": "find_lineage_records", "arguments": {"query": query, "max_results": 10}},
            )
            payload = json.loads(found["content"][0]["text"])

            assert "GAP-PLATFORM-CONFIG-PAGE" in payload["expanded_queries"]
            assert "/ui/preview/source-foundation" in payload["expanded_queries"]
            assert "/health/ready" in payload["expanded_queries"]
            assert "preview.source-foundation" in payload["expanded_queries"]
            assert "health.ready" in payload["expanded_queries"]
            assert "MTR-PLT-001" in payload["expanded_queries"]
            assert "PAGE-CONTRACT-PENDING:/platform-config" in payload["expanded_queries"]
            assert all(record["record"]["formal_use_allowed"] is False for record in payload["records"])
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_news_events_to_analytical_event_anchors(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "result_kind": "news.choice.latest",
                "source_surface": "choice_news",
                "source_version": "sv_choice_news",
                "rule_version": "rv_choice_news_v1",
                "created_at": "2026-06-06T00:00:00Z",
                "formal_use_allowed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for query in (
            "GAP-NEWS-EVENTS-PAGE",
            "news-events",
            "/news-events",
        ):
            found = server.request(
                "tools/call",
                {"name": "find_lineage_records", "arguments": {"query": query, "max_results": 10}},
            )
            payload = json.loads(found["content"][0]["text"])

            assert "GAP-NEWS-EVENTS-PAGE" in payload["expanded_queries"]
            assert "/ui/news/choice-events/latest" in payload["expanded_queries"]
            assert "news.choice.latest" in payload["expanded_queries"]
            assert "choice_news_event" in payload["expanded_queries"]
            assert "PAGE-CONTRACT-PENDING:/news-events" in payload["expanded_queries"]
            assert all(record["record"]["formal_use_allowed"] is False for record in payload["records"])
    finally:
        server.close()


def test_metric_contracts_page_trace_bundle_accepts_aliases_and_rejects_unknown_pages() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in ("/product-category-pnl", "PAGE-PROD-CAT-PNL-001"):
            alias_result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
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
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": "unknown-page"}},
        )
        assert unknown_slug["code"] == -32602
        assert "Unknown page_slug: unknown-page" in unknown_slug["message"]
        assert "dashboard-home" in unknown_slug["message"]
        assert "product-category-pnl" in unknown_slug["message"]
        assert "risk-tensor" in unknown_slug["message"]
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


def test_lineage_evidence_mcp_maps_page_risk_contract_to_risk_tensor_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "agent_audit.jsonl").write_text(
        json.dumps(
            {
                "result_kind": "risk.tensor",
                "page_slug": "risk-tensor",
                "source_surface": "risk_tensor",
                "tables_used": ["fact_formal_risk_tensor_daily"],
                "report_date": "2026-04-30",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-RISK-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-RISK-001"
        assert "risk.tensor" in found_payload["expanded_queries"]
        assert "fact_formal_risk_tensor_daily" in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "fact_formal_risk_tensor_daily"
        assert found_payload["records"][0]["stream"] == "agent_audit"
        assert found_payload["records"][0]["record"]["result_kind"] == "risk.tensor"
    finally:
        server.close()


def test_lineage_evidence_page_lineage_summary_separates_direct_from_expanded_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "page_id": "PAGE-POS-001",
                        "api": "/api/positions/bonds",
                        "result_kind": "positions.bonds.list",
                        "report_date": "2026-05-31",
                    }
                ),
                json.dumps(
                    {
                        "table_name": "zqtz_bond_daily_snapshot",
                        "source_version": "sv_positions_snapshot",
                        "report_date": "2026-05-31",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_lineage_evidence" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_lineage_evidence",
                "arguments": {"page_slugs": ["PAGE-POS-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-lineage-evidence"
        assert "does not prove page execution completeness, metric definition, or formal approval" in payload[
            "disclaimer"
        ]
        assert payload["summary"] == {
            "page_count": 1,
            "direct_page_or_api_record_count": 1,
            "expanded_anchor_record_count": 1,
            "missing_direct_page_or_api_record_count": 0,
        }

        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-POS-001"
        assert page["lineage_status"] == "direct_page_or_api_records_present"
        assert page["direct_page_or_api_records"][0]["matched_query"] == "PAGE-POS-001"
        assert page["direct_page_or_api_records"][0]["record"]["result_kind"] == "positions.bonds.list"
        assert page["expanded_anchor_records"][0]["matched_query"] == "zqtz_bond_daily_snapshot"
        assert page["expanded_anchor_records"][0]["record"]["table_name"] == "zqtz_bond_daily_snapshot"
        assert any("verify page/API execution completeness" in action for action in page["recommended_next_actions"])
        assert all("formal approval" not in action for action in page["recommended_next_actions"])
        assert "formal_use_allowed" not in page
        assert "approval_status" not in page
    finally:
        server.close()


def test_lineage_evidence_page_lineage_summary_reports_expanded_only_as_gap(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "table_name": "fact_formal_bond_analytics_daily",
                "source_version": "sv_bond_analytics",
                "report_date": "2026-05-31",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_lineage_evidence",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-BOND-001"
        assert page["lineage_status"] == "expanded_anchor_only"
        assert page["direct_page_or_api_records"] == []
        assert page["expanded_anchor_records"][0]["matched_query"] == "fact_formal_bond_analytics_daily"
        assert any("direct page/API governance record is missing" in gap for gap in page["residual_gaps"])
        assert any("Add or locate a direct PAGE-BOND-001/API governance record" in action for action in page["recommended_next_actions"])
        assert any("Do not treat expanded anchor records as page execution proof" in action for action in page["recommended_next_actions"])
        assert payload["summary"]["missing_direct_page_or_api_record_count"] == 1
    finally:
        server.close()


def test_lineage_evidence_page_lineage_summary_reports_missing_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_lineage_evidence",
                "arguments": {"page_slugs": ["PAGE-LEDGER-PNL-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-LEDGER-PNL-001"
        assert page["lineage_status"] == "missing"
        assert page["direct_page_or_api_records"] == []
        assert page["expanded_anchor_records"] == []
        assert any("No direct page/API or expanded anchor governance records" in gap for gap in page["residual_gaps"])
        assert any("both direct PAGE-LEDGER-PNL-001/API governance records" in action for action in page["recommended_next_actions"])
        assert payload["summary"] == {
            "page_count": 1,
            "direct_page_or_api_record_count": 0,
            "expanded_anchor_record_count": 0,
            "missing_direct_page_or_api_record_count": 1,
        }
    finally:
        server.close()


def test_lineage_evidence_page_governance_requirements_describes_direct_records_without_approval() -> None:
    server = McpProcess("lineage-evidence")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_governance_record_requirements" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_record_requirements",
                "arguments": {"page_slugs": ["PAGE-BOND-001", "GAP-STOCK-ANALYSIS-PAGE"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-record-requirements"
        assert "does not create governance records" in payload["disclaimer"]
        assert payload["summary"] == {
            "page_count": 2,
            "direct_record_required_count": 2,
        }

        pages = {page["page_id"]: page for page in payload["pages"]}
        bond = pages["PAGE-BOND-001"]
        assert bond["approval_status"] == "candidate_or_pending"
        assert "formal_use_allowed" not in bond
        assert bond["record_formal_use_policy"] == "must_be_false_until_candidate_closure"
        assert bond["direct_record_required"] is True
        assert bond["direct_anchor_targets"]["page_id"] == "PAGE-BOND-001"
        assert bond["direct_anchor_targets"]["frontend_route"] == "/bond-dashboard"
        assert bond["direct_anchor_targets"]["primary_api"] == "/api/bond-dashboard/headline-kpis"
        assert "/api/bond-dashboard/dates" in bond["direct_anchor_targets"]["supporting_apis"]
        assert "/api/bond-dashboard/risk-indicators" in bond["direct_anchor_targets"]["supporting_apis"]
        assert "/api/bond-dashboard/business-type-metrics" in bond["direct_anchor_targets"]["supporting_apis"]
        assert bond["accepted_direct_terms"][:3] == [
            "PAGE-BOND-001",
            "/bond-dashboard",
            "/api/bond-dashboard/headline-kpis",
        ]
        assert "/api/bond-dashboard/dates" in bond["accepted_direct_terms"]
        assert "/api/bond-dashboard/risk-indicators" in bond["accepted_direct_terms"]
        assert "/api/bond-dashboard/headline-kpis" in bond["accepted_direct_terms"]
        assert "fact_formal_bond_analytics_daily" not in bond["accepted_direct_terms"]
        assert "page_id" in bond["required_fields"]
        assert "primary_api" in bond["required_fields"]
        assert "result_kind" not in bond["required_fields"]
        assert "result_kind" in bond["recommended_metadata_fields"]
        assert "report_date" in bond["required_fields"]
        assert "formal_use_allowed" not in bond["required_fields"]
        assert {
            "name": "record_formal_use_allowed",
            "one_of": ["formal_use_allowed=false"],
            "reason": "Candidate, mixed-source, GAP, and unclassified pages must not claim formal-use approval.",
        } in bond["required_field_groups"]
        assert "created_at" in bond["required_fields"]
        assert "cache_key_or_run_id" not in bond["required_fields"]
        assert {
            "name": "execution_identifier",
            "one_of": ["cache_key", "run_id"],
            "reason": "A direct record needs either a stable cache key or an execution/run identifier.",
        } in bond["required_field_groups"]
        assert any("candidate_or_pending" in note for note in bond["status_specific_requirements"])
        assert any("must remain false" in note for note in bond["status_specific_requirements"])
        assert any("expanded source-table anchors" in item for item in bond["insufficient_evidence_examples"])

        stock = pages["GAP-STOCK-ANALYSIS-PAGE"]
        assert stock["approval_status"] == "gap_or_observational"
        assert "formal_use_allowed" not in stock
        assert stock["record_formal_use_policy"] == "must_be_false_for_gap_or_observational"
        assert stock["primary_api"] == "/ui/market-data/livermore"
        assert any("GAP/observational" in note for note in stock["status_specific_requirements"])
        assert any("PAGE-STOCK" in note for note in stock["status_specific_requirements"])

        assert all("approval_status" in page for page in payload["pages"])
        assert all("formal_use_allowed" not in page for page in payload["pages"])
        assert all(page["evidence_scope"]["writes_governance_records"] is False for page in payload["pages"])
        assert all(page["evidence_scope"]["approves_metric_or_page"] is False for page in payload["pages"])
    finally:
        server.close()


def test_lineage_evidence_page_governance_requirements_never_grants_formal_page_approval() -> None:
    server = McpProcess("lineage-evidence")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_record_requirements",
                "arguments": {"page_slugs": ["PAGE-PROD-CAT-001"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["summary"] == {
            "page_count": 1,
            "direct_record_required_count": 1,
        }
        page = payload["pages"][0]
        assert page["approval_status"] == "formal_or_governed"
        assert "formal_use_allowed" not in page
        assert page["record_formal_use_policy"] == "may_be_true_only_after_direct_record_and_contract_evidence"
        assert {
            "name": "record_formal_use_allowed",
            "one_of": ["formal_use_allowed=true", "formal_use_allowed=false"],
            "reason": (
                "Formal/governed page status is not enough; the audited record still needs direct execution, "
                "contract, lineage, date/catalog, and result metadata evidence before true is allowed."
            ),
        } in page["required_field_groups"]
        assert page["evidence_scope"]["approves_metric_or_page"] is False
        assert page["evidence_scope"]["proves_page_execution"] is False
    finally:
        server.close()


def test_lineage_evidence_page_governance_requirements_defaults_to_high_risk_pages() -> None:
    server = McpProcess("lineage-evidence")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_governance_record_requirements", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert [page["page_id"] for page in payload["pages"]] == [
            "PAGE-LEDGER-PNL-001",
            "PAGE-BOND-001",
            "PAGE-POS-001",
            "PAGE-MKT-001",
            "GAP-STOCK-ANALYSIS-PAGE",
            "PAGE-OPS-001",
        ]
        assert payload["summary"] == {
            "page_count": 6,
            "direct_record_required_count": 6,
        }
        assert all(page["direct_record_required"] is True for page in payload["pages"])
        assert all("formal_use_allowed" not in page for page in payload["pages"])
        assert all(page["record_formal_use_policy"] != "may_be_true_only_after_direct_record_and_contract_evidence" for page in payload["pages"])
    finally:
        server.close()


def test_lineage_evidence_page_governance_record_validation_classifies_ready_and_incomplete_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "page_id": "PAGE-BOND-001",
                        "page_slug": "bond-dashboard",
                        "frontend_route": "/bond-dashboard",
                        "primary_api": "/api/bond-dashboard/headline-kpis",
                        "report_date": "2026-05-31",
                        "basis": "analytical",
                        "source_surface": "bond_analytics",
                        "tables_used": ["fact_formal_bond_analytics_daily"],
                        "source_version": "sv_bond_analytics",
                        "rule_version": "rv_bond_dashboard_headline_v1",
                        "created_at": "2026-06-04T12:00:00Z",
                        "cache_key": "bond_dashboard.headline:2026-05-31",
                        "formal_use_allowed": False,
                        "result_kind": "bond_dashboard.headline_kpis",
                    }
                ),
                json.dumps(
                    {
                        "api": "/api/bond-dashboard/headline-kpis",
                        "page_slug": "bond-dashboard",
                        "report_date": "2026-05-31",
                        "basis": "analytical",
                        "tables_used": ["fact_formal_bond_analytics_daily"],
                        "source_version": "sv_bond_analytics",
                        "created_at": "2026-06-04T12:05:00Z",
                        "formal_use_allowed": True,
                    }
                ),
                json.dumps(
                    {
                        "table_name": "fact_formal_bond_analytics_daily",
                        "source_version": "sv_bond_analytics",
                        "report_date": "2026-05-31",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "validate_page_governance_records" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "validate_page_governance_records",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-record-validation"
        assert "does not approve metric/page formal use" in payload["disclaimer"]
        assert payload["summary"] == {
            "page_count": 1,
            "ready_record_count": 1,
            "incomplete_record_count": 1,
            "missing_record_page_count": 0,
        }

        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-BOND-001"
        assert page["validation_status"] == "direct_records_present_with_gaps"
        assert page["expanded_anchor_records"][0]["matched_query"] == "fact_formal_bond_analytics_daily"
        assert page["expanded_anchor_records"][0]["record"]["table_name"] == "fact_formal_bond_analytics_daily"
        assert len(page["direct_record_validations"]) == 2

        ready = page["direct_record_validations"][0]
        assert ready["validation_status"] == "ready_for_audit_review"
        assert ready["missing_required_fields"] == []
        assert ready["failed_required_field_groups"] == []
        assert ready["record_formal_use_allowed"] is False
        assert ready["matched_query"] == "PAGE-BOND-001"
        assert ready["direct_anchor_match"] == {
            "anchor_type": "page_id",
            "matched_query": "PAGE-BOND-001",
            "proves_primary_page_anchor": True,
        }

        incomplete = page["direct_record_validations"][1]
        assert incomplete["validation_status"] == "incomplete"
        assert "page_id" in incomplete["missing_required_fields"]
        assert "primary_api" in incomplete["missing_required_fields"]
        assert "source_surface" in incomplete["missing_required_fields"]
        assert "rule_version" in incomplete["missing_required_fields"]
        assert any(group["name"] == "execution_identifier" for group in incomplete["failed_required_field_groups"])
        assert any(group["name"] == "record_formal_use_allowed" for group in incomplete["failed_required_field_groups"])
        assert incomplete["record_formal_use_allowed"] is True
        assert incomplete["direct_anchor_match"] == {
            "anchor_type": "primary_api",
            "matched_query": "/api/bond-dashboard/headline-kpis",
            "proves_primary_page_anchor": True,
        }
        assert any("does not prove page execution" in gap for gap in ready["residual_gaps"])
    finally:
        server.close()


def test_lineage_evidence_page_governance_record_validation_reports_missing_direct_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "table_name": "fact_formal_bond_analytics_daily",
                "source_version": "sv_bond_analytics",
                "report_date": "2026-05-31",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "validate_page_governance_records",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["summary"] == {
            "page_count": 1,
            "ready_record_count": 0,
            "incomplete_record_count": 0,
            "missing_record_page_count": 1,
        }
        page = payload["pages"][0]
        assert page["validation_status"] == "missing_direct_records"
        assert page["direct_record_validations"] == []
        assert page["expanded_anchor_records"][0]["matched_query"] == "fact_formal_bond_analytics_daily"
        assert any("direct page/API governance record is missing" in gap for gap in page["residual_gaps"])
    finally:
        server.close()


def test_lineage_evidence_page_governance_record_validation_does_not_treat_slash_as_direct_anchor(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "page_id": "PAGE-OTHER-001",
                        "page_slug": "other-page",
                        "frontend_route": "/other-page",
                        "primary_api": "/api/other/page",
                        "report_date": "2026-05-31",
                        "basis": "analytical",
                        "source_surface": "other",
                        "tables_used": ["fact_formal_zqtz_balance_daily"],
                        "source_version": "sv_other",
                        "rule_version": "rv_other",
                        "created_at": "2026-06-04T12:00:00Z",
                        "cache_key": "other:2026-05-31",
                        "formal_use_allowed": False,
                    }
                ),
                json.dumps(
                    {
                        "page_slug": "dashboard-home",
                        "frontend_route": "/dashboard",
                        "primary_api": "/api/bond-dashboard/headline-kpis",
                        "page_id": "PAGE-BOND-001",
                        "report_date": "2026-05-31",
                        "basis": "analytical",
                        "source_surface": "dashboard_home",
                        "tables_used": ["fact_formal_bond_analytics_daily"],
                        "source_version": "sv_dashboard_home",
                        "rule_version": "rv_dashboard_home",
                        "created_at": "2026-06-04T12:10:00Z",
                        "cache_key": "dashboard-home:supporting-bond:2026-05-31",
                        "formal_use_allowed": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "validate_page_governance_records",
                "arguments": {"page_slugs": ["PAGE-DASH-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["summary"] == {
            "page_count": 1,
            "ready_record_count": 0,
            "incomplete_record_count": 0,
            "missing_record_page_count": 0,
        }
        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-DASH-001"
        assert "/" in page["accepted_direct_terms"]
        assert page["validation_status"] == "direct_records_present_with_gaps"
        assert any("primary page/API anchor is missing" in gap for gap in page["residual_gaps"])
        assert len(page["direct_record_validations"]) == 1
        assert page["direct_record_validations"][0]["validation_status"] == "supporting_anchor_only"
        assert page["direct_record_validations"][0]["direct_anchor_match"] == {
            "anchor_type": "supporting_api",
            "matched_query": "/api/bond-dashboard/headline-kpis",
            "proves_primary_page_anchor": False,
        }
    finally:
        server.close()


def test_lineage_evidence_page_governance_record_validation_rejects_foreign_shared_api_record(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "page_id": "PAGE-PROD-CAT-001",
                "page_slug": "product-category-pnl",
                "frontend_route": "/product-category-pnl",
                "primary_api": "/ui/pnl/product-category",
                "report_date": "2026-05-31",
                "basis": "formal",
                "source_surface": "product_category_pnl",
                "tables_used": [
                    "product_category_pnl_formal_read_model",
                    "product_category_pnl_canonical_fact",
                ],
                "source_version": "sv_product_category_pnl",
                "rule_version": "rv_product_category_pnl_v1",
                "created_at": "2026-06-04T12:00:00Z",
                "run_id": "product-category-pnl:2026-05-31",
                "formal_use_allowed": True,
                "result_kind": "product_category_pnl.detail",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "validate_page_governance_records",
                "arguments": {"page_slugs": ["PAGE-OPS-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["summary"] == {
            "page_count": 1,
            "ready_record_count": 0,
            "incomplete_record_count": 0,
            "missing_record_page_count": 1,
        }
        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-OPS-001"
        assert page["validation_status"] == "missing_direct_records"
        assert page["direct_record_validations"] == []
        assert page["expanded_anchor_records"][0]["matched_query"] == "/ui/pnl/product-category"
        assert page["expanded_anchor_records"][0]["record"]["page_id"] == "PAGE-PROD-CAT-001"
        assert any("direct page/API governance record is missing" in gap for gap in page["residual_gaps"])
    finally:
        server.close()


def test_lineage_evidence_page_lineage_evidence_rejects_foreign_shared_api_record(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "page_id": "PAGE-PROD-CAT-001",
                "page_slug": "product-category-pnl",
                "frontend_route": "/product-category-pnl",
                "primary_api": "/ui/pnl/product-category",
                "report_date": "2026-05-31",
                "basis": "formal",
                "source_surface": "product_category_pnl",
                "tables_used": [
                    "product_category_pnl_formal_read_model",
                    "product_category_pnl_canonical_fact",
                ],
                "source_version": "sv_product_category_pnl",
                "rule_version": "rv_product_category_pnl_v1",
                "created_at": "2026-06-04T12:00:00Z",
                "run_id": "product-category-pnl:2026-05-31",
                "formal_use_allowed": True,
                "result_kind": "product_category_pnl.detail",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_lineage_evidence",
                "arguments": {"page_slugs": ["PAGE-OPS-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-OPS-001"
        assert page["lineage_status"] == "expanded_anchor_only"
        assert page["direct_page_or_api_records"] == []
        assert page["expanded_anchor_records"][0]["matched_query"] == "/ui/pnl/product-category"
        assert page["expanded_anchor_records"][0]["record"]["page_id"] == "PAGE-PROD-CAT-001"
        assert any("direct page/API governance record is missing" in gap for gap in page["residual_gaps"])
    finally:
        server.close()


def test_lineage_evidence_governance_audit_review_checklist_keeps_ready_record_unapproved(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "page_id": "PAGE-PROD-CAT-001",
                "page_slug": "product-category-pnl",
                "frontend_route": "/product-category-pnl",
                "primary_api": "/ui/pnl/product-category",
                "report_date": "2026-05-31",
                "basis": "formal",
                "source_surface": "product_category_pnl",
                "tables_used": [
                    "product_category_pnl_formal_read_model",
                    "product_category_pnl_canonical_fact",
                ],
                "source_version": "sv_product_category_pnl",
                "rule_version": "rv_product_category_pnl_v1",
                "created_at": "2026-06-04T12:00:00Z",
                "run_id": "product-category-pnl:2026-05-31",
                "formal_use_allowed": True,
                "result_kind": "product_category_pnl.detail",
                "ui_api_payload_evidence": ".codex-tmp/product-category-pnl-ui-api-payload.json",
                "live_smoke_evidence": ".codex-tmp/product-category-pnl-live-smoke.png",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_governance_audit_review_checklist" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_audit_review_checklist",
                "arguments": {"page_slugs": ["PAGE-PROD-CAT-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-audit-review-checklist"
        assert "does not approve metric/page formal use" in payload["disclaimer"]
        assert payload["summary"] == {
            "page_count": 1,
            "ready_for_audit_review_count": 1,
            "blocked_by_record_gaps_count": 0,
            "closure_approved_count": 0,
        }

        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-PROD-CAT-001"
        assert page["record_validation_status"] == "direct_records_ready_for_audit_review"
        assert page["audit_review_status"] == "ready_for_audit_review"
        assert page["closure_approved"] is False
        assert page["ready_record_count"] == 1
        assert page["incomplete_record_count"] == 0
        assert page["checks"][0] == {
            "name": "direct_page_api_record_fields",
            "status": "ready_for_audit_review",
            "evidence": "1 direct record(s) have required fields and field groups.",
        }
        assert page["review_evidence_hints"] == {
            "status": "direct_record_ready_for_manual_review",
            "record_location": {
                "stream": "cache_manifest",
                "line": 1,
                "matched_query": "PAGE-PROD-CAT-001",
            },
            "report_date": "2026-05-31",
            "basis": "formal",
            "source_surface": "product_category_pnl",
            "source_version": "sv_product_category_pnl",
            "rule_version": "rv_product_category_pnl_v1",
            "result_kind": "product_category_pnl.detail",
            "tables_used": [
                "product_category_pnl_formal_read_model",
                "product_category_pnl_canonical_fact",
            ],
            "execution_identifier": {
                "field": "run_id",
                "value": "product-category-pnl:2026-05-31",
            },
            "ui_api_payload_evidence": ".codex-tmp/product-category-pnl-ui-api-payload.json",
            "live_smoke_evidence": ".codex-tmp/product-category-pnl-live-smoke.png",
            "formal_use_allowed": True,
        }
        check_names = [check["name"] for check in page["checks"]]
        assert check_names == [
            "direct_page_api_record_fields",
            "page_contract_review",
            "catalog_date_sampling",
            "lineage_freshness_review",
            "ui_api_payload_review",
            "live_smoke_evidence_review",
            "business_owner_approval",
        ]
        assert all(check["status"] == "manual_review_required" for check in page["checks"][1:])
        assert any("page contract" in action for action in page["next_actions"])
        assert page["evidence_scope"]["writes_governance_records"] is False
        assert page["evidence_scope"]["approves_metric_or_page"] is False
        assert page["evidence_scope"]["proves_page_execution"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_audit_review_checklist_blocks_incomplete_direct_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "page_id": "PAGE-BOND-001",
                "page_slug": "bond-dashboard",
                "frontend_route": "/bond-dashboard",
                "primary_api": "/api/bond-dashboard/headline-kpis",
                "report_date": "2026-05-31",
                "basis": "analytical",
                "source_surface": "bond_analytics",
                "tables_used": ["fact_formal_bond_analytics_daily"],
                "source_version": "sv_bond_analytics",
                "created_at": "2026-06-04T12:05:00Z",
                "formal_use_allowed": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_audit_review_checklist",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["summary"] == {
            "page_count": 1,
            "ready_for_audit_review_count": 0,
            "blocked_by_record_gaps_count": 1,
            "closure_approved_count": 0,
        }

        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-BOND-001"
        assert page["record_validation_status"] == "direct_records_present_with_gaps"
        assert page["audit_review_status"] == "blocked_by_record_gaps"
        assert page["ready_record_count"] == 0
        assert page["incomplete_record_count"] == 1
        assert page["checks"][0]["name"] == "direct_page_api_record_fields"
        assert page["checks"][0]["status"] == "blocked"
        assert any("Complete direct page/API governance record fields" in action for action in page["next_actions"])
        assert page["evidence_scope"]["validates_required_fields"] is True
        assert page["evidence_scope"]["approves_metric_or_page"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_audit_review_queue_routes_ready_pages_without_closure(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "page_id": "PAGE-PROD-CAT-001",
            "page_slug": "product-category-pnl",
            "frontend_route": "/product-category-pnl",
            "primary_api": "/ui/pnl/product-category",
            "report_date": "2026-05-31",
            "basis": "formal",
            "source_surface": "product_category_pnl",
            "tables_used": [
                "product_category_pnl_formal_read_model",
                "product_category_pnl_canonical_fact",
            ],
            "source_version": "sv_product_category_pnl",
            "rule_version": "rv_product_category_pnl_v1",
            "created_at": "2026-06-04T12:00:00Z",
            "run_id": "product-category-pnl:2026-05-31",
            "formal_use_allowed": True,
            "result_kind": "product_category_pnl.detail",
            "live_smoke_evidence": ".codex-tmp/product-category-pnl-live-smoke.png",
        },
        {
            "page_id": "PAGE-RISK-001",
            "page_slug": "risk-tensor",
            "frontend_route": "/risk-tensor",
            "primary_api": "/api/risk-tensor/summary",
            "report_date": "2026-05-31",
            "basis": "formal",
            "source_surface": "risk_tensor",
            "tables_used": ["fact_formal_risk_tensor_daily"],
            "source_version": "sv_risk_tensor",
            "rule_version": "rv_risk_tensor_v1",
            "created_at": "2026-06-04T12:10:00Z",
            "cache_key": "risk-tensor:2026-05-31",
            "formal_use_allowed": True,
            "result_kind": "risk.tensor",
        },
        {
            "page_id": "PAGE-BOND-001",
            "page_slug": "bond-dashboard",
            "frontend_route": "/bond-dashboard",
            "primary_api": "/api/bond-dashboard/headline-kpis",
            "report_date": "2026-05-31",
            "basis": "analytical",
            "source_surface": "bond_analytics",
            "tables_used": ["fact_formal_bond_analytics_daily"],
            "source_version": "sv_bond_analytics",
            "created_at": "2026-06-04T12:05:00Z",
            "formal_use_allowed": True,
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_governance_audit_review_queue" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_audit_review_queue",
                "arguments": {
                    "page_slugs": [
                        "PAGE-PROD-CAT-001",
                        "PAGE-RISK-001",
                        "PAGE-BOND-001",
                    ],
                    "max_results": 10,
                },
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-audit-review-queue"
        assert "does not approve metric/page formal use" in payload["disclaimer"]
        assert payload["summary"] == {
            "page_count": 3,
            "ready_for_audit_review_count": 2,
            "blocked_by_record_gaps_count": 1,
            "closure_approved_count": 0,
            "queue_count": 2,
            "remaining_manual_check_count": 12,
        }

        assert [item["page_id"] for item in payload["items"]] == [
            "PAGE-PROD-CAT-001",
            "PAGE-RISK-001",
        ]
        first = payload["items"][0]
        assert first["closure_approved"] is False
        assert first["review_priority"] == "manual_review_required"
        assert first["remaining_manual_checks"] == [
            "page_contract_review",
            "catalog_date_sampling",
            "lineage_freshness_review",
            "ui_api_payload_review",
            "live_smoke_evidence_review",
            "business_owner_approval",
        ]
        assert first["manual_review_steps"] == [
            {
                "check": "page_contract_review",
                "evidence_to_collect": [
                    "page contract",
                    "metric dictionary",
                    "calculation rules",
                    "golden samples",
                ],
                "suggested_tools": [
                    "moss-metric-contracts.get_page_trace_bundle",
                    "moss-metric-contracts.search_contract_docs",
                ],
                "tool_calls": [
                    {
                        "tool": "moss-metric-contracts.get_page_trace_bundle",
                        "arguments": {"page_slug": "product-category-pnl"},
                    },
                    {
                        "tool": "moss-metric-contracts.search_contract_docs",
                        "arguments": {"query": "PAGE-PROD-CAT-001"},
                    },
                ],
                "approval_boundary": "manual_review_only",
            },
            {
                "check": "catalog_date_sampling",
                "evidence_to_collect": [
                    "configured page table descriptions",
                    "available report/as-of dates",
                    "date semantics comparison",
                ],
                "suggested_tools": [
                    "moss-data-catalog.get_page_catalog_date_evidence",
                    "moss-data-catalog.get_page_catalog_date_coverage",
                ],
                "tool_calls": [
                    {
                        "tool": "moss-data-catalog.get_page_catalog_date_evidence",
                        "arguments": {"page_slugs": ["product-category-pnl"]},
                    },
                    {
                        "tool": "moss-data-catalog.get_page_catalog_date_coverage",
                        "arguments": {"page_slugs": ["product-category-pnl"]},
                    },
                ],
                "approval_boundary": "manual_review_only",
            },
            {
                "check": "lineage_freshness_review",
                "evidence_to_collect": [
                    "direct lineage freshness",
                    "source version",
                    "rule version",
                    "cache/run identifier",
                    "fallback or stale status",
                ],
                "suggested_tools": [
                    "moss-lineage-evidence.find_lineage_records",
                    "moss-lineage-evidence.get_page_lineage_evidence",
                ],
                "tool_calls": [
                    {
                        "tool": "moss-lineage-evidence.find_lineage_records",
                        "arguments": {"query": "PAGE-PROD-CAT-001", "max_results": 8},
                    },
                    {
                        "tool": "moss-lineage-evidence.get_page_lineage_evidence",
                        "arguments": {"page_slugs": ["product-category-pnl"], "max_results": 8},
                    },
                ],
                "approval_boundary": "manual_review_only",
            },
            {
                "check": "ui_api_payload_review",
                "evidence_to_collect": [
                    "current API payload",
                    "result_meta",
                    "visible UI state",
                    "page contract comparison",
                ],
                "suggested_tools": [
                    "page-specific API smoke",
                    "frontend page/model tests",
                ],
                "approval_boundary": "manual_review_only",
            },
            {
                "check": "live_smoke_evidence_review",
                "evidence_to_collect": [
                    "live smoke output",
                    "browser evidence",
                    "visible stale/fallback/no-data state",
                ],
                "suggested_tools": [
                    "scripts/codex-verify-page.ps1",
                    "scripts/codex-page-smoke.ps1",
                ],
                "approval_boundary": "manual_review_only",
            },
            {
                "check": "business_owner_approval",
                "evidence_to_collect": [
                    "business owner review",
                    "approval record",
                    "remaining exception decision",
                ],
                "suggested_tools": [
                    "manual sign-off",
                ],
                "approval_boundary": "manual_review_only",
            },
        ]
        assert first["review_evidence_hints"]["execution_identifier"] == {
            "field": "run_id",
            "value": "product-category-pnl:2026-05-31",
        }
        assert first["evidence_scope"]["writes_governance_records"] is False
        assert first["evidence_scope"]["approves_metric_or_page"] is False
        assert first["evidence_scope"]["proves_page_execution"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_audit_evidence_packet_collects_mcp_backed_review_evidence(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    missing_duckdb = tmp_path / "missing.duckdb"
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "page_id": "PAGE-PROD-CAT-001",
                "page_slug": "product-category-pnl",
                "frontend_route": "/product-category-pnl",
                "primary_api": "/ui/pnl/product-category",
                "report_date": "2026-05-31",
                "basis": "formal",
                "source_surface": "product_category_pnl",
                "tables_used": [
                    "product_category_pnl_formal_read_model",
                    "product_category_pnl_canonical_fact",
                ],
                "source_version": "sv_product_category_pnl",
                "rule_version": "rv_product_category_pnl_v1",
                "created_at": "2026-06-04T12:00:00Z",
                "run_id": "product-category-pnl:2026-05-31",
                "formal_use_allowed": True,
                "result_kind": "product_category_pnl.detail",
                "ui_api_payload_evidence": ".codex-tmp/product-category-pnl-ui-api-payload.json",
                "live_smoke_evidence": ".codex-tmp/product-category-pnl-live-smoke.png",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess(
        "lineage-evidence",
        env={
            "MOSS_GOVERNANCE_PATH": str(governance),
            "MOSS_DUCKDB_PATH": str(missing_duckdb),
        },
    )
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_governance_audit_evidence_packet" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_audit_evidence_packet",
                "arguments": {"page_slug": "product-category-pnl", "max_results": 8},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-audit-evidence-packet"
        assert "does not approve metric/page formal use" in payload["disclaimer"]
        assert payload["page_id"] == "PAGE-PROD-CAT-001"
        assert payload["page_slug"] == "product-category-pnl"
        assert payload["closure_approved"] is False
        assert payload["audit_review_status"] == "ready_for_audit_review"
        assert payload["evidence_scope"] == {
            "writes_governance_records": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "aggregates_mcp_evidence": True,
        }

        assert payload["contract_trace"]["page_id"] == "PAGE-PROD-CAT-001"
        assert payload["contract_trace"]["page_slug"] == "product-category-pnl"
        assert payload["contract_trace"]["primary_api"] == "/ui/pnl/product-category"
        assert "tests/golden_samples/GS-PROD-CAT-PNL-A" in payload["contract_trace"]["golden_samples"]
        assert payload["contract_trace_summary"] == {
            "contract_doc_count": len(payload["contract_trace"]["contract_docs"]),
            "golden_sample_ids": ["GS-PROD-CAT-PNL-A"],
            "backend_touchpoint_count": len(payload["contract_trace"]["backend_touchpoints"]),
            "frontend_touchpoint_count": len(payload["contract_trace"]["frontend_touchpoints"]),
            "test_touchpoint_count": len(payload["contract_trace"]["test_touchpoints"]),
        }

        assert payload["catalog_date_evidence"]["duckdb_exists"] is False
        assert payload["catalog_date_evidence"]["summary"]["page_count"] == 1
        assert payload["catalog_date_evidence"]["pages"][0]["page_id"] == "PAGE-PROD-CAT-001"
        assert payload["catalog_date_evidence"]["pages"][0]["evidence_scope"]["page_execution_checked"] is False

        assert payload["lineage_evidence"]["summary"]["page_count"] == 1
        assert payload["lineage_evidence"]["pages"][0]["page_id"] == "PAGE-PROD-CAT-001"
        assert payload["lineage_evidence"]["pages"][0]["lineage_status"] == "direct_page_or_api_records_present"

        assert payload["audit_review_queue_item"]["remaining_manual_checks"] == [
            "page_contract_review",
            "catalog_date_sampling",
            "lineage_freshness_review",
            "ui_api_payload_review",
            "live_smoke_evidence_review",
            "business_owner_approval",
        ]
        assert payload["manual_review_blockers"] == [
            "business_owner_approval",
        ]
        assert payload["manual_review_blocker_targets"] == [
            {
                "check": "business_owner_approval",
                "page_id": "PAGE-PROD-CAT-001",
                "page_slug": "product-category-pnl",
                "frontend_route": "/product-category-pnl",
                "primary_api": "/ui/pnl/product-category",
                "evidence_to_collect": [
                    "business owner review",
                    "approval record",
                    "remaining exception decision",
                ],
                "suggested_tools": [
                    "manual sign-off",
                ],
                "review_targets": {
                    "approval_record_page_id": "PAGE-PROD-CAT-001",
                    "approval_record_page_slug": "product-category-pnl",
                    "closure_approved": False,
                },
                "approval_boundary": "manual_review_only",
            },
        ]
        assert payload["manual_review_evidence_present"] == [
            {
                "check": "ui_api_payload_review",
                "evidence_field": "ui_api_payload_evidence",
                "evidence_value": ".codex-tmp/product-category-pnl-ui-api-payload.json",
                "status": "evidence_present_needs_review",
            },
            {
                "check": "live_smoke_evidence_review",
                "evidence_field": "live_smoke_evidence",
                "evidence_value": ".codex-tmp/product-category-pnl-live-smoke.png",
                "status": "evidence_present_needs_review",
            }
        ]
        assert payload["summary"] == {
            "mcp_evidence_sections": [
                "contract_trace",
                "catalog_date_evidence",
                "lineage_evidence",
                "audit_review_queue_item",
            ],
            "manual_review_blocker_count": 1,
            "manual_review_evidence_present_count": 2,
            "closure_approved": False,
        }
    finally:
        server.close()


def test_lineage_evidence_governance_audit_evidence_packet_queue_collects_ready_pages_only(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    missing_duckdb = tmp_path / "missing.duckdb"
    records = [
        {
            "page_id": "PAGE-PROD-CAT-001",
            "page_slug": "product-category-pnl",
            "frontend_route": "/product-category-pnl",
            "primary_api": "/ui/pnl/product-category",
            "report_date": "2026-05-31",
            "basis": "formal",
            "source_surface": "product_category_pnl",
            "tables_used": [
                "product_category_pnl_formal_read_model",
                "product_category_pnl_canonical_fact",
            ],
            "source_version": "sv_product_category_pnl",
            "rule_version": "rv_product_category_pnl_v1",
            "created_at": "2026-06-04T12:00:00Z",
            "run_id": "product-category-pnl:2026-05-31",
            "formal_use_allowed": True,
            "result_kind": "product_category_pnl.detail",
            "live_smoke_evidence": ".codex-tmp/product-category-pnl-live-smoke.png",
        },
        {
            "page_id": "PAGE-RISK-001",
            "page_slug": "risk-tensor",
            "frontend_route": "/risk-tensor",
            "primary_api": "/api/risk-tensor/summary",
            "report_date": "2026-05-31",
            "basis": "formal",
            "source_surface": "risk_tensor",
            "tables_used": ["fact_formal_risk_tensor_daily"],
            "source_version": "sv_risk_tensor",
            "rule_version": "rv_risk_tensor_v1",
            "created_at": "2026-06-04T12:10:00Z",
            "cache_key": "risk-tensor:2026-05-31",
            "formal_use_allowed": True,
            "result_kind": "risk.tensor",
        },
        {
            "page_id": "PAGE-BOND-001",
            "page_slug": "bond-dashboard",
            "frontend_route": "/bond-dashboard",
            "primary_api": "/api/bond-dashboard/headline-kpis",
            "report_date": "2026-05-31",
            "basis": "analytical",
            "source_surface": "bond_analytics",
            "tables_used": ["fact_formal_bond_analytics_daily"],
            "source_version": "sv_bond_analytics",
            "created_at": "2026-06-04T12:05:00Z",
            "formal_use_allowed": True,
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess(
        "lineage-evidence",
        env={
            "MOSS_GOVERNANCE_PATH": str(governance),
            "MOSS_DUCKDB_PATH": str(missing_duckdb),
        },
    )
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_governance_audit_evidence_packet_queue" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_audit_evidence_packet_queue",
                "arguments": {
                    "page_slugs": [
                        "PAGE-PROD-CAT-001",
                        "PAGE-RISK-001",
                        "PAGE-BOND-001",
                        "PAGE-LEDGER-PNL-001",
                    ],
                    "max_results": 8,
                },
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-audit-evidence-packet-queue"
        assert "does not approve metric/page formal use" in payload["disclaimer"]
        ledger_creation_manual_fill_field_details = [
            {
                "kind": "field",
                "name": "page_id",
                "status": "prefilled",
                "value": "PAGE-LEDGER-PNL-001",
                "satisfying_values": [],
            },
            {
                "kind": "field",
                "name": "page_slug",
                "status": "prefilled",
                "value": "ledger-pnl",
                "satisfying_values": [],
            },
            {
                "kind": "field",
                "name": "frontend_route",
                "status": "prefilled",
                "value": "/ledger-pnl",
                "satisfying_values": [],
            },
            {
                "kind": "field",
                "name": "primary_api",
                "status": "prefilled",
                "value": "/api/ledger-pnl/summary",
                "satisfying_values": [],
            },
            {
                "kind": "field",
                "name": "report_date",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use catalog/date evidence or the audited page/API payload date binding for the reviewed run; do not infer the date from unrelated upstream tables.",
                ],
            },
            {
                "kind": "field",
                "name": "basis",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use explicit page contract, source basis, or approval-status evidence for the reviewed run; do not infer formal or analytical basis from the page slug alone.",
                ],
            },
            {
                "kind": "field",
                "name": "source_surface",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use page/API result metadata, route/service source-surface evidence, or direct lineage metadata for the reviewed run.",
                ],
            },
            {
                "kind": "field",
                "name": "tables_used",
                "status": "prefilled",
                "value": [
                    "qdb_general_ledger_workbook",
                    "ledger_import_batch",
                    "ledger_raw_row",
                ],
                "satisfying_values": [],
            },
            {
                "kind": "field",
                "name": "source_version",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use source manifest, cache, run, or vendor/feed evidence tied to the reviewed run; do not invent a source version.",
                ],
            },
            {
                "kind": "field",
                "name": "rule_version",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
                ],
            },
            {
                "kind": "field",
                "name": "created_at",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use the governance record creation or review timestamp; do not substitute the report date.",
                ],
            },
            {
                "kind": "group",
                "name": "direct_page_or_api_anchor",
                "status": "satisfied",
                "value": None,
                "satisfying_values": [
                    "PAGE-LEDGER-PNL-001",
                    "/ledger-pnl",
                    "/api/ledger-pnl/summary",
                    "/api/ledger-pnl/dates",
                    "/api/ledger-pnl/data",
                    "/api/ledger-pnl/formal-financial-indicators",
                ],
            },
            {
                "kind": "group",
                "name": "execution_identifier",
                "status": "failed",
                "value": None,
                "satisfying_values": ["cache_key", "run_id"],
                "evidence_hints": [
                    "Use a cache_key or run_id from the audited page/API execution evidence; expanded source-table or result-kind anchors are supporting evidence only.",
                ],
            },
            {
                "kind": "group",
                "name": "configured_table_anchor",
                "status": "satisfied",
                "value": None,
                "satisfying_values": [
                    "qdb_general_ledger_workbook",
                    "ledger_import_batch",
                    "ledger_raw_row",
                ],
            },
            {
                "kind": "group",
                "name": "record_formal_use_allowed",
                "status": "satisfied",
                "value": False,
                "satisfying_values": ["formal_use_allowed=false"],
            },
        ]
        bond_preflight_completion_template = {
            "tool": "moss-lineage-evidence.preflight_page_governance_record",
            "arguments": {
                "page_slug": "bond-dashboard",
                "record": {
                    "page_id": "PAGE-BOND-001",
                    "page_slug": "bond-dashboard",
                    "frontend_route": "/bond-dashboard",
                    "primary_api": "/api/bond-dashboard/headline-kpis",
                    "tables_used": ["fact_formal_bond_analytics_daily"],
                    "formal_use_allowed": False,
                    "report_date": "2026-05-31",
                    "basis": "analytical",
                    "source_surface": "bond_analytics",
                    "source_version": "sv_bond_analytics",
                    "rule_version": None,
                    "created_at": "2026-06-04T12:05:00Z",
                    "cache_key": None,
                    "run_id": None,
                },
            },
            "manual_placeholders": ["rule_version", "cache_key_or_run_id"],
            "approval_boundary": "preflight_only_no_write_no_approval",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "checks_record_existence": False,
            },
        }
        assert payload["summary"] == {
            "page_count": 4,
            "ready_for_audit_review_count": 2,
            "ready_for_audit_review_pages": [
                {"page_id": "PAGE-PROD-CAT-001", "page_slug": "product-category-pnl"},
                {"page_id": "PAGE-RISK-001", "page_slug": "risk-tensor"},
            ],
            "packet_count": 2,
            "blocked_by_record_gaps_count": 2,
            "closure_approved_count": 0,
            "manual_review_blocker_count": 5,
            "manual_review_evidence_present_count": 1,
            "closure_readiness": {
                "page_count": 4,
                "ready_for_audit_review_count": 2,
                "blocked_by_record_gaps_count": 2,
                "manual_review_mcp_work_item_count": 3,
                "manual_review_blocker_count": 5,
                "manual_review_evidence_present_needs_review_count": 1,
                "closure_approved_count": 0,
                "closure_ready_count": 0,
                "closure_blocked_count": 4,
                "queue_grants_closure": False,
                "status": "manual_review_and_record_remediation_required",
                "residual_closure_requirements": [
                    "record_gap_remediation",
                    "mcp_evidence_collection",
                    "manual_review_blockers",
                    "present_evidence_review",
                    "business_owner_approval",
                ],
            },
            "manual_review_blocker_breakdown": {
                "business_owner_approval": 2,
                "live_smoke_evidence_review": 1,
                "ui_api_payload_review": 2,
            },
            "manual_review_evidence_present_breakdown": {
                "live_smoke_evidence_review": 1,
            },
            "manual_review_blocker_pages": {
                "business_owner_approval": [
                    {"page_id": "PAGE-PROD-CAT-001", "page_slug": "product-category-pnl"},
                    {"page_id": "PAGE-RISK-001", "page_slug": "risk-tensor"},
                ],
                "live_smoke_evidence_review": [
                    {"page_id": "PAGE-RISK-001", "page_slug": "risk-tensor"},
                ],
                "ui_api_payload_review": [
                    {"page_id": "PAGE-PROD-CAT-001", "page_slug": "product-category-pnl"},
                    {"page_id": "PAGE-RISK-001", "page_slug": "risk-tensor"},
                ],
            },
            "manual_review_evidence_present_pages": {
                "live_smoke_evidence_review": [
                    {"page_id": "PAGE-PROD-CAT-001", "page_slug": "product-category-pnl"},
                ],
            },
            "manual_review_evidence_present_work_items": [
                {
                    "check": "live_smoke_evidence_review",
                    "page_id": "PAGE-PROD-CAT-001",
                    "page_slug": "product-category-pnl",
                    "frontend_route": "/product-category-pnl",
                    "primary_api": "/ui/pnl/product-category",
                    "evidence_field": "live_smoke_evidence",
                    "evidence_value": ".codex-tmp/product-category-pnl-live-smoke.png",
                    "review_status": "evidence_present_needs_review",
                    "approval_boundary": "manual_review_evidence_present_review_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
            ],
            "manual_review_mcp_work_items": [
                {
                    "check": "page_contract_review",
                    "page_count": 2,
                    "pages": [
                        {
                            "page_id": "PAGE-PROD-CAT-001",
                            "page_slug": "product-category-pnl",
                            "tool_calls": [
                                {
                                    "tool": "moss-metric-contracts.get_page_trace_bundle",
                                    "arguments": {"page_slug": "product-category-pnl"},
                                },
                                {
                                    "tool": "moss-metric-contracts.search_contract_docs",
                                    "arguments": {"query": "PAGE-PROD-CAT-001"},
                                },
                            ],
                        },
                        {
                            "page_id": "PAGE-RISK-001",
                            "page_slug": "risk-tensor",
                            "tool_calls": [
                                {
                                    "tool": "moss-metric-contracts.get_page_trace_bundle",
                                    "arguments": {"page_slug": "risk-tensor"},
                                },
                                {
                                    "tool": "moss-metric-contracts.search_contract_docs",
                                    "arguments": {"query": "PAGE-RISK-001"},
                                },
                            ],
                        },
                    ],
                    "evidence_to_collect": [
                        "page contract",
                        "metric dictionary",
                        "calculation rules",
                        "golden samples",
                    ],
                    "suggested_tools": [
                        "moss-metric-contracts.get_page_trace_bundle",
                        "moss-metric-contracts.search_contract_docs",
                    ],
                    "approval_boundary": "manual_review_mcp_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                    },
                },
                {
                    "check": "catalog_date_sampling",
                    "page_count": 2,
                    "pages": [
                        {
                            "page_id": "PAGE-PROD-CAT-001",
                            "page_slug": "product-category-pnl",
                            "tool_calls": [
                                {
                                    "tool": "moss-data-catalog.get_page_catalog_date_evidence",
                                    "arguments": {"page_slugs": ["product-category-pnl"]},
                                },
                                {
                                    "tool": "moss-data-catalog.get_page_catalog_date_coverage",
                                    "arguments": {"page_slugs": ["product-category-pnl"]},
                                },
                            ],
                        },
                        {
                            "page_id": "PAGE-RISK-001",
                            "page_slug": "risk-tensor",
                            "tool_calls": [
                                {
                                    "tool": "moss-data-catalog.get_page_catalog_date_evidence",
                                    "arguments": {"page_slugs": ["risk-tensor"]},
                                },
                                {
                                    "tool": "moss-data-catalog.get_page_catalog_date_coverage",
                                    "arguments": {"page_slugs": ["risk-tensor"]},
                                },
                            ],
                        },
                    ],
                    "evidence_to_collect": [
                        "configured page table descriptions",
                        "available report/as-of dates",
                        "date semantics comparison",
                    ],
                    "suggested_tools": [
                        "moss-data-catalog.get_page_catalog_date_evidence",
                        "moss-data-catalog.get_page_catalog_date_coverage",
                    ],
                    "approval_boundary": "manual_review_mcp_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                    },
                },
                {
                    "check": "lineage_freshness_review",
                    "page_count": 2,
                    "pages": [
                        {
                            "page_id": "PAGE-PROD-CAT-001",
                            "page_slug": "product-category-pnl",
                            "tool_calls": [
                                {
                                    "tool": "moss-lineage-evidence.find_lineage_records",
                                    "arguments": {"query": "PAGE-PROD-CAT-001", "max_results": 8},
                                },
                                {
                                    "tool": "moss-lineage-evidence.get_page_lineage_evidence",
                                    "arguments": {"page_slugs": ["product-category-pnl"], "max_results": 8},
                                },
                            ],
                        },
                        {
                            "page_id": "PAGE-RISK-001",
                            "page_slug": "risk-tensor",
                            "tool_calls": [
                                {
                                    "tool": "moss-lineage-evidence.find_lineage_records",
                                    "arguments": {"query": "PAGE-RISK-001", "max_results": 8},
                                },
                                {
                                    "tool": "moss-lineage-evidence.get_page_lineage_evidence",
                                    "arguments": {"page_slugs": ["risk-tensor"], "max_results": 8},
                                },
                            ],
                        },
                    ],
                    "evidence_to_collect": [
                        "direct lineage freshness",
                        "source version",
                        "rule version",
                        "cache/run identifier",
                        "fallback or stale status",
                    ],
                    "suggested_tools": [
                        "moss-lineage-evidence.find_lineage_records",
                        "moss-lineage-evidence.get_page_lineage_evidence",
                    ],
                    "approval_boundary": "manual_review_mcp_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                    },
                },
            ],
            "manual_review_mcp_scope_audit": {
                "work_item_count": 3,
                "checked_work_item_groups": ["manual_review_mcp_work_items"],
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
                "scope_violations": [],
            },
            "manual_review_work_items": [
                {
                    "check": "ui_api_payload_review",
                    "page_id": "PAGE-PROD-CAT-001",
                    "page_slug": "product-category-pnl",
                    "frontend_route": "/product-category-pnl",
                    "primary_api": "/ui/pnl/product-category",
                    "review_targets": {
                        "api_payload": "/ui/pnl/product-category",
                        "frontend_route": "/product-category-pnl",
                        "result_meta_required": True,
                        "contract_page_id": "PAGE-PROD-CAT-001",
                    },
                    "approval_boundary": "manual_review_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "check": "business_owner_approval",
                    "page_id": "PAGE-PROD-CAT-001",
                    "page_slug": "product-category-pnl",
                    "frontend_route": "/product-category-pnl",
                    "primary_api": "/ui/pnl/product-category",
                    "review_targets": {
                        "approval_record_page_id": "PAGE-PROD-CAT-001",
                        "approval_record_page_slug": "product-category-pnl",
                        "closure_approved": False,
                    },
                    "approval_boundary": "manual_review_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "check": "ui_api_payload_review",
                    "page_id": "PAGE-RISK-001",
                    "page_slug": "risk-tensor",
                    "frontend_route": "/risk-tensor",
                    "primary_api": "/api/risk-tensor/summary",
                    "review_targets": {
                        "api_payload": "/api/risk-tensor/summary",
                        "frontend_route": "/risk-tensor",
                        "result_meta_required": True,
                        "contract_page_id": "PAGE-RISK-001",
                    },
                    "approval_boundary": "manual_review_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "check": "live_smoke_evidence_review",
                    "page_id": "PAGE-RISK-001",
                    "page_slug": "risk-tensor",
                    "frontend_route": "/risk-tensor",
                    "primary_api": "/api/risk-tensor/summary",
                    "review_targets": {
                        "frontend_route": "/risk-tensor",
                        "primary_api": "/api/risk-tensor/summary",
                        "visible_state_review_required": True,
                        "contract_page_id": "PAGE-RISK-001",
                    },
                    "approval_boundary": "manual_review_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "check": "business_owner_approval",
                    "page_id": "PAGE-RISK-001",
                    "page_slug": "risk-tensor",
                    "frontend_route": "/risk-tensor",
                    "primary_api": "/api/risk-tensor/summary",
                    "review_targets": {
                        "approval_record_page_id": "PAGE-RISK-001",
                        "approval_record_page_slug": "risk-tensor",
                        "closure_approved": False,
                    },
                    "approval_boundary": "manual_review_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
            ],
            "manual_review_scope_audit": {
                "work_item_count": 6,
                "checked_work_item_groups": [
                    "manual_review_work_items",
                    "manual_review_evidence_present_work_items",
                ],
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "scope_violations": [],
            },
            "queue_boundary_audit": {
                "work_item_count": 24,
                "checked_scope_audits": [
                    "manual_review_mcp_scope_audit",
                    "manual_review_scope_audit",
                    "direct_record_remediation_scope_audit",
                ],
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "scope_violations": [],
            },
            "blocked_by_record_gap_remediation_breakdown": {
                "complete_direct_record_fields": 1,
                "create_direct_record": 1,
            },
            "blocked_by_record_gap_remediation_pages": {
                "complete_direct_record_fields": [
                    {"page_id": "PAGE-BOND-001", "page_slug": "bond-dashboard"},
                ],
                "create_direct_record": [
                    {"page_id": "PAGE-LEDGER-PNL-001", "page_slug": "ledger-pnl"},
                ],
            },
            "blocked_by_record_gap_next_step_breakdown": {
                "collect_direct_page_api_record_evidence_then_preflight_candidate": 1,
                "complete_existing_direct_record_fields_then_preflight": 1,
            },
            "blocked_by_record_gap_next_step_pages": {
                "collect_direct_page_api_record_evidence_then_preflight_candidate": [
                    {"page_id": "PAGE-LEDGER-PNL-001", "page_slug": "ledger-pnl"},
                ],
                "complete_existing_direct_record_fields_then_preflight": [
                    {"page_id": "PAGE-BOND-001", "page_slug": "bond-dashboard"},
                ],
            },
            "create_direct_record_table_anchor_work_items": [
                {
                    "table_anchor_status": "configured_table_anchor_available",
                    "page_count": 1,
                    "pages": [
                        {
                            "page_id": "PAGE-LEDGER-PNL-001",
                            "page_slug": "ledger-pnl",
                            "configured_table_names": [
                                "qdb_general_ledger_workbook",
                                "ledger_import_batch",
                                "ledger_raw_row",
                            ],
                        }
                    ],
                    "next_action": "collect_page_run_evidence_for_configured_table_anchors",
                    "approval_boundary": "record_creation_table_anchor_routing_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                }
            ],
            "direct_record_remediation_scope_audit": {
                "work_item_count": 15,
                "checked_work_item_groups": [
                    "blocked_by_record_gap_next_steps",
                    "create_direct_record_evidence_work_items",
                    "create_direct_record_table_anchor_work_items",
                    "direct_record_remediation_work_items",
                    "repair_direct_record_evidence_work_items",
                ],
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "scope_violations": [],
            },
            "blocked_by_record_gap_next_steps": [
                {
                    "page_id": "PAGE-BOND-001",
                    "page_slug": "bond-dashboard",
                    "remediation_type": "complete_direct_record_fields",
                    "next_step": "complete_existing_direct_record_fields_then_preflight",
                    "evidence_to_collect": [
                        "missing_required_fields",
                        "failed_required_field_groups",
                        "page_api_execution_identifier",
                    ],
                    "suggested_tool_calls": [
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
                            "arguments": {"page_slugs": ["bond-dashboard"]},
                        },
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_blueprint",
                            "arguments": {"page_slug": "bond-dashboard"},
                        },
                    ],
                    "approval_boundary": "record_remediation_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "page_id": "PAGE-LEDGER-PNL-001",
                    "page_slug": "ledger-pnl",
                    "remediation_type": "create_direct_record",
                    "next_step": "collect_direct_page_api_record_evidence_then_preflight_candidate",
                    "evidence_to_collect": [
                        "direct_page_or_primary_api_anchor",
                        "required_record_fields",
                        "page_api_execution_identifier",
                        "configured_or_deferred_table_anchors",
                    ],
                    "suggested_tool_calls": [
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
                            "arguments": {"page_slugs": ["ledger-pnl"]},
                        },
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_blueprint",
                            "arguments": {"page_slug": "ledger-pnl"},
                        },
                    ],
                    "approval_boundary": "record_remediation_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
            ],
            "create_direct_record_evidence_work_items": [
                {
                    "evidence_key": "basis",
                    "kind": "field",
                    "status": "missing",
                    "page_count": 1,
                    "pages": [
                        {"page_id": "PAGE-LEDGER-PNL-001", "page_slug": "ledger-pnl"},
                    ],
                    "evidence_hints": [
                        "Use explicit page contract, source basis, or approval-status evidence for the reviewed run; do not infer formal or analytical basis from the page slug alone.",
                    ],
                    "approval_boundary": "record_creation_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "evidence_key": "created_at",
                    "kind": "field",
                    "status": "missing",
                    "page_count": 1,
                    "pages": [
                        {"page_id": "PAGE-LEDGER-PNL-001", "page_slug": "ledger-pnl"},
                    ],
                    "evidence_hints": [
                        "Use the governance record creation or review timestamp; do not substitute the report date.",
                    ],
                    "approval_boundary": "record_creation_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "evidence_key": "execution_identifier",
                    "kind": "group",
                    "status": "failed",
                    "page_count": 1,
                    "pages": [
                        {"page_id": "PAGE-LEDGER-PNL-001", "page_slug": "ledger-pnl"},
                    ],
                    "evidence_hints": [
                        "Use a cache_key or run_id from the audited page/API execution evidence; expanded source-table or result-kind anchors are supporting evidence only.",
                    ],
                    "approval_boundary": "record_creation_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "evidence_key": "report_date",
                    "kind": "field",
                    "status": "missing",
                    "page_count": 1,
                    "pages": [
                        {"page_id": "PAGE-LEDGER-PNL-001", "page_slug": "ledger-pnl"},
                    ],
                    "evidence_hints": [
                        "Use catalog/date evidence or the audited page/API payload date binding for the reviewed run; do not infer the date from unrelated upstream tables.",
                    ],
                    "approval_boundary": "record_creation_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "evidence_key": "rule_version",
                    "kind": "field",
                    "status": "missing",
                    "page_count": 1,
                    "pages": [
                        {"page_id": "PAGE-LEDGER-PNL-001", "page_slug": "ledger-pnl"},
                    ],
                    "evidence_hints": [
                        "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
                    ],
                    "approval_boundary": "record_creation_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "evidence_key": "source_surface",
                    "kind": "field",
                    "status": "missing",
                    "page_count": 1,
                    "pages": [
                        {"page_id": "PAGE-LEDGER-PNL-001", "page_slug": "ledger-pnl"},
                    ],
                    "evidence_hints": [
                        "Use page/API result metadata, route/service source-surface evidence, or direct lineage metadata for the reviewed run.",
                    ],
                    "approval_boundary": "record_creation_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "evidence_key": "source_version",
                    "kind": "field",
                    "status": "missing",
                    "page_count": 1,
                    "pages": [
                        {"page_id": "PAGE-LEDGER-PNL-001", "page_slug": "ledger-pnl"},
                    ],
                    "evidence_hints": [
                        "Use source manifest, cache, run, or vendor/feed evidence tied to the reviewed run; do not invent a source version.",
                    ],
                    "approval_boundary": "record_creation_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
            ],
            "repair_direct_record_evidence_work_items": [
                {
                    "evidence_key": "execution_identifier",
                    "kind": "group",
                    "status": "failed",
                    "page_count": 1,
                    "pages": [
                        {"page_id": "PAGE-BOND-001", "page_slug": "bond-dashboard"},
                    ],
                    "remediation_types": ["complete_direct_record_fields"],
                    "record_locations": [
                        {
                            "page_id": "PAGE-BOND-001",
                            "page_slug": "bond-dashboard",
                            "record_location": {
                                "stream": "cache_manifest",
                                "line": 3,
                                "matched_query": "PAGE-BOND-001",
                            },
                        }
                    ],
                    "evidence_hints": [
                        "Use a cache_key or run_id from the audited page/API execution evidence; expanded source-table or result-kind anchors are supporting evidence only.",
                    ],
                    "approval_boundary": "record_repair_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "evidence_key": "record_formal_use_allowed",
                    "kind": "group",
                    "status": "failed",
                    "page_count": 1,
                    "pages": [
                        {"page_id": "PAGE-BOND-001", "page_slug": "bond-dashboard"},
                    ],
                    "remediation_types": ["complete_direct_record_fields"],
                    "record_locations": [
                        {
                            "page_id": "PAGE-BOND-001",
                            "page_slug": "bond-dashboard",
                            "record_location": {
                                "stream": "cache_manifest",
                                "line": 3,
                                "matched_query": "PAGE-BOND-001",
                            },
                        }
                    ],
                    "evidence_hints": [
                        "Set formal_use_allowed=false for candidate/pending pages until business-owner closure is separately approved; do not treat record repair as approval.",
                    ],
                    "approval_boundary": "record_repair_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "evidence_key": "rule_version",
                    "kind": "field",
                    "status": "missing",
                    "page_count": 1,
                    "pages": [
                        {"page_id": "PAGE-BOND-001", "page_slug": "bond-dashboard"},
                    ],
                    "remediation_types": ["complete_direct_record_fields"],
                    "record_locations": [
                        {
                            "page_id": "PAGE-BOND-001",
                            "page_slug": "bond-dashboard",
                            "record_location": {
                                "stream": "cache_manifest",
                                "line": 3,
                                "matched_query": "PAGE-BOND-001",
                            },
                        }
                    ],
                    "evidence_hints": [
                        "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
                    ],
                    "approval_boundary": "record_repair_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
            ],
            "direct_record_remediation_work_items": [
                {
                    "work_type": "complete_existing_direct_record",
                    "remediation_type": "complete_direct_record_fields",
                    "page_id": "PAGE-BOND-001",
                    "page_slug": "bond-dashboard",
                    "page_name": "Bond Dashboard",
                    "primary_api": "/api/bond-dashboard/headline-kpis",
                    "record_validation_status": "direct_records_present_with_gaps",
                    "direct_record_count": 1,
                    "incomplete_record_count": 1,
                    "remediation_tool_calls": [
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
                            "arguments": {"page_slugs": ["bond-dashboard"]},
                        },
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_blueprint",
                            "arguments": {"page_slug": "bond-dashboard"},
                        },
                    ],
                    "repair_targets": [
                        {
                            "record_location": {
                                "stream": "cache_manifest",
                                "line": 3,
                                "matched_query": "PAGE-BOND-001",
                            },
                            "missing_required_fields": ["rule_version"],
                            "failed_required_field_groups": [
                                "execution_identifier",
                                "record_formal_use_allowed",
                            ],
                            "direct_anchor_match": {
                                "anchor_type": "page_id",
                                "matched_query": "PAGE-BOND-001",
                                "proves_primary_page_anchor": True,
                            },
                            "record_formal_use_allowed": True,
                            "evidence_hints": {
                                "missing_required_fields": {
                                    "rule_version": [
                                        "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
                                    ],
                                },
                                "failed_required_field_groups": {
                                    "execution_identifier": [
                                        "Use a cache_key or run_id from the audited page/API execution evidence; expanded source-table or result-kind anchors are supporting evidence only.",
                                    ],
                                    "record_formal_use_allowed": [
                                        "Set formal_use_allowed=false for candidate/pending pages until business-owner closure is separately approved; do not treat record repair as approval.",
                                    ],
                                },
                            },
                            "preflight_completion_template": bond_preflight_completion_template,
                        },
                        ],
                        "residual_gaps": [
                            "At least one direct page/API governance record is present but missing required fields or required field-group constraints.",
                        ],
                        "approval_boundary": "record_remediation_only",
                        "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
                {
                    "work_type": "create_direct_record",
                    "remediation_type": "create_direct_record",
                    "page_id": "PAGE-LEDGER-PNL-001",
                    "page_slug": "ledger-pnl",
                    "page_name": "Ledger PnL",
                    "primary_api": "/api/ledger-pnl/summary",
                    "record_validation_status": "missing_direct_records",
                    "direct_record_count": 0,
                    "incomplete_record_count": 0,
                    "remediation_tool_calls": [
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
                            "arguments": {"page_slugs": ["ledger-pnl"]},
                        },
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_blueprint",
                            "arguments": {"page_slug": "ledger-pnl"},
                        },
                    ],
                    "repair_targets": [],
                        "creation_target": {
                            "manual_fill_priority": "create_direct_record_and_supporting_lineage",
                            "candidate_record": {
                                "page_id": "PAGE-LEDGER-PNL-001",
                            "page_slug": "ledger-pnl",
                            "frontend_route": "/ledger-pnl",
                            "primary_api": "/api/ledger-pnl/summary",
                            "tables_used": [
                                "qdb_general_ledger_workbook",
                                "ledger_import_batch",
                                "ledger_raw_row",
                            ],
                                "formal_use_allowed": False,
                            },
                            "preflight_submission_template": {
                                "tool": "moss-lineage-evidence.preflight_page_governance_record",
                                "arguments": {
                                    "page_slug": "ledger-pnl",
                                    "record": {
                                        "page_id": "PAGE-LEDGER-PNL-001",
                                        "page_slug": "ledger-pnl",
                                        "frontend_route": "/ledger-pnl",
                                        "primary_api": "/api/ledger-pnl/summary",
                                        "tables_used": [
                                            "qdb_general_ledger_workbook",
                                            "ledger_import_batch",
                                            "ledger_raw_row",
                                        ],
                                        "formal_use_allowed": False,
                                        "report_date": None,
                                        "basis": None,
                                        "source_surface": None,
                                        "source_version": None,
                                        "rule_version": None,
                                        "created_at": None,
                                        "cache_key": None,
                                        "run_id": None,
                                    },
                                },
                                "manual_placeholders": [
                                    "report_date",
                                    "basis",
                                    "source_surface",
                                    "source_version",
                                    "rule_version",
                                    "created_at",
                                    "cache_key_or_run_id",
                                ],
                                "approval_boundary": "preflight_only_no_write_no_approval",
                                "evidence_scope": {
                                    "writes_governance_records": False,
                                    "approves_metric_or_page": False,
                                    "proves_page_execution": False,
                                    "checks_record_existence": False,
                                },
                            },
                            "manual_fill_fields": [
                                "report_date",
                                "basis",
                            "source_surface",
                            "source_version",
                            "rule_version",
                            "created_at",
                            "cache_key_or_run_id",
                        ],
                        "manual_fill_field_details": ledger_creation_manual_fill_field_details,
                        "missing_required_fields": [
                            "report_date",
                            "basis",
                            "source_surface",
                            "source_version",
                            "rule_version",
                            "created_at",
                        ],
                        "failed_required_field_groups": ["execution_identifier"],
                        "direct_anchor_targets": {
                            "page_id": "PAGE-LEDGER-PNL-001",
                            "frontend_route": "/ledger-pnl",
                            "primary_api": "/api/ledger-pnl/summary",
                            "supporting_apis": [
                                "/api/ledger-pnl/dates",
                                "/api/ledger-pnl/data",
                                "/api/ledger-pnl/formal-financial-indicators",
                            ],
                        },
                        "configured_table_names": [
                            "qdb_general_ledger_workbook",
                            "ledger_import_batch",
                            "ledger_raw_row",
                        ],
                        },
                        "residual_gaps": [
                            "A direct page/API governance record is missing; expanded anchors cannot prove page/API execution.",
                        ],
                        "approval_boundary": "record_remediation_only",
                        "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
            ],
            "blocked_by_record_gap_pages": [
                {
                    "page_id": "PAGE-BOND-001",
                    "page_slug": "bond-dashboard",
                    "page_name": "Bond Dashboard",
                    "primary_api": "/api/bond-dashboard/headline-kpis",
                    "record_validation_status": "direct_records_present_with_gaps",
                    "direct_record_count": 1,
                    "incomplete_record_count": 1,
                    "remediation_type": "complete_direct_record_fields",
                    "remediation_tool_calls": [
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
                            "arguments": {"page_slugs": ["bond-dashboard"]},
                        },
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_blueprint",
                            "arguments": {"page_slug": "bond-dashboard"},
                        },
                    ],
                    "repair_targets": [
                        {
                            "record_location": {
                                "stream": "cache_manifest",
                                "line": 3,
                                "matched_query": "PAGE-BOND-001",
                            },
                            "missing_required_fields": ["rule_version"],
                            "failed_required_field_groups": [
                                "execution_identifier",
                                "record_formal_use_allowed",
                            ],
                            "direct_anchor_match": {
                                "anchor_type": "page_id",
                                "matched_query": "PAGE-BOND-001",
                                "proves_primary_page_anchor": True,
                            },
                            "record_formal_use_allowed": True,
                            "evidence_hints": {
                                "missing_required_fields": {
                                    "rule_version": [
                                        "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
                                    ],
                                },
                                "failed_required_field_groups": {
                                    "execution_identifier": [
                                        "Use a cache_key or run_id from the audited page/API execution evidence; expanded source-table or result-kind anchors are supporting evidence only.",
                                    ],
                                    "record_formal_use_allowed": [
                                        "Set formal_use_allowed=false for candidate/pending pages until business-owner closure is separately approved; do not treat record repair as approval.",
                                    ],
                                },
                            },
                            "preflight_completion_template": bond_preflight_completion_template,
                        },
                    ],
                    "residual_gaps": [
                        "At least one direct page/API governance record is present but missing required fields or required field-group constraints.",
                    ],
                },
                {
                    "page_id": "PAGE-LEDGER-PNL-001",
                    "page_slug": "ledger-pnl",
                    "page_name": "Ledger PnL",
                    "primary_api": "/api/ledger-pnl/summary",
                    "record_validation_status": "missing_direct_records",
                    "direct_record_count": 0,
                    "incomplete_record_count": 0,
                    "remediation_type": "create_direct_record",
                    "remediation_tool_calls": [
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
                            "arguments": {"page_slugs": ["ledger-pnl"]},
                        },
                        {
                            "tool": "moss-lineage-evidence.get_page_governance_record_blueprint",
                            "arguments": {"page_slug": "ledger-pnl"},
                        },
                    ],
                    "repair_targets": [],
                        "creation_target": {
                            "manual_fill_priority": "create_direct_record_and_supporting_lineage",
                            "candidate_record": {
                                "page_id": "PAGE-LEDGER-PNL-001",
                            "page_slug": "ledger-pnl",
                            "frontend_route": "/ledger-pnl",
                            "primary_api": "/api/ledger-pnl/summary",
                            "tables_used": [
                                "qdb_general_ledger_workbook",
                                "ledger_import_batch",
                                "ledger_raw_row",
                            ],
                                "formal_use_allowed": False,
                            },
                            "preflight_submission_template": {
                                "tool": "moss-lineage-evidence.preflight_page_governance_record",
                                "arguments": {
                                    "page_slug": "ledger-pnl",
                                    "record": {
                                        "page_id": "PAGE-LEDGER-PNL-001",
                                        "page_slug": "ledger-pnl",
                                        "frontend_route": "/ledger-pnl",
                                        "primary_api": "/api/ledger-pnl/summary",
                                        "tables_used": [
                                            "qdb_general_ledger_workbook",
                                            "ledger_import_batch",
                                            "ledger_raw_row",
                                        ],
                                        "formal_use_allowed": False,
                                        "report_date": None,
                                        "basis": None,
                                        "source_surface": None,
                                        "source_version": None,
                                        "rule_version": None,
                                        "created_at": None,
                                        "cache_key": None,
                                        "run_id": None,
                                    },
                                },
                                "manual_placeholders": [
                                    "report_date",
                                    "basis",
                                    "source_surface",
                                    "source_version",
                                    "rule_version",
                                    "created_at",
                                    "cache_key_or_run_id",
                                ],
                                "approval_boundary": "preflight_only_no_write_no_approval",
                                "evidence_scope": {
                                    "writes_governance_records": False,
                                    "approves_metric_or_page": False,
                                    "proves_page_execution": False,
                                    "checks_record_existence": False,
                                },
                            },
                            "manual_fill_fields": [
                                "report_date",
                                "basis",
                            "source_surface",
                            "source_version",
                            "rule_version",
                            "created_at",
                            "cache_key_or_run_id",
                        ],
                        "manual_fill_field_details": ledger_creation_manual_fill_field_details,
                        "missing_required_fields": [
                            "report_date",
                            "basis",
                            "source_surface",
                            "source_version",
                            "rule_version",
                            "created_at",
                        ],
                        "failed_required_field_groups": ["execution_identifier"],
                        "direct_anchor_targets": {
                            "page_id": "PAGE-LEDGER-PNL-001",
                            "frontend_route": "/ledger-pnl",
                            "primary_api": "/api/ledger-pnl/summary",
                            "supporting_apis": [
                                "/api/ledger-pnl/dates",
                                "/api/ledger-pnl/data",
                                "/api/ledger-pnl/formal-financial-indicators",
                            ],
                        },
                        "configured_table_names": [
                            "qdb_general_ledger_workbook",
                            "ledger_import_batch",
                            "ledger_raw_row",
                        ],
                    },
                    "residual_gaps": [
                        "A direct page/API governance record is missing; expanded anchors cannot prove page/API execution.",
                    ],
                },
            ],
        }
        assert [item["page_id"] for item in payload["items"]] == [
            "PAGE-PROD-CAT-001",
            "PAGE-RISK-001",
        ]
        assert all(item["closure_approved"] is False for item in payload["items"])
        assert payload["items"][0]["summary"]["mcp_evidence_sections"] == [
            "contract_trace",
            "catalog_date_evidence",
            "lineage_evidence",
            "audit_review_queue_item",
        ]
        assert payload["items"][0]["manual_review_blockers"] == [
            "ui_api_payload_review",
            "business_owner_approval",
        ]
        assert payload["items"][0]["manual_review_evidence_present"] == [
            {
                "check": "live_smoke_evidence_review",
                "evidence_field": "live_smoke_evidence",
                "evidence_value": ".codex-tmp/product-category-pnl-live-smoke.png",
                "status": "evidence_present_needs_review",
            }
        ]
        assert payload["evidence_scope"] == {
            "writes_governance_records": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "aggregates_mcp_evidence": True,
        }
    finally:
        server.close()


def test_lineage_evidence_audit_report_matches_current_all_seeded_packet_queue() -> None:
    server = McpProcess("lineage-evidence", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_audit_evidence_packet_queue",
                "arguments": {"all_seeded_pages": True},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["summary"]["page_count"] == (
            payload["summary"]["ready_for_audit_review_count"]
            + payload["summary"]["blocked_by_record_gaps_count"]
        )
        assert payload["summary"]["ready_for_audit_review_count"] == len(
            payload["summary"]["ready_for_audit_review_pages"]
        )
        assert payload["summary"]["packet_count"] == len(payload["items"])
        assert payload["summary"]["packet_count"] == payload["summary"]["ready_for_audit_review_count"]
        assert payload["summary"]["closure_approved_count"] == 0
        assert payload["summary"]["ready_for_audit_review_pages"] == [
            {"page_id": page_id, "page_slug": page_slug}
            for page_id, page_slug in zip(
                GOVERNANCE_READY_FOR_AUDIT_PAGE_IDS,
                GOVERNANCE_READY_FOR_AUDIT_PAGE_SLUGS,
                strict=True,
            )
        ]
        assert [item["page_id"] for item in payload["items"]] == GOVERNANCE_READY_FOR_AUDIT_PAGE_IDS

        report = (
            REPO_ROOT / "docs" / "audits" / "2026-06-02-system-audit-first-pass.md"
        ).read_text(encoding="utf-8")
        assert (
            "the all-seeded review state has 16 ready-for-audit-review pages, "
            "23 pages blocked by record gaps, "
            "and 0 closure-approved pages"
        ) in report
        assert "16 ready pages and 23 blocked pages" in report
        assert "5 ready pages and 27 blocked pages" not in report
        assert (
            "Against the current all-seeded repository snapshot it returns 16 packets, "
            "42 remaining manual blockers"
        ) in report
        assert (
            "23 direct-record remediation work items: 23 create-direct-record tasks"
        ) in report
        assert "23 seeded-page open gaps" in report
        assert "39 seeded-page open gaps" not in report
        assert (
            "A suggested-call scope-audit follow-up first failed because those "
            "grouped suggested-tool work items had per-item flags but no "
            "summary-level guard"
        ) in report
        assert (
            "A catalog/date-lineage queue-boundary follow-up first failed "
            "because remediation and suggested-call scope audits still had "
            "to be read separately"
        ) in report
        assert (
            "after adding `closure_dispatch_packet_scope_audit`, "
            "`queue_boundary_audit` now rolls up 50 assignment rows across "
            "record-gap execution-plan, remediation, suggested-call, "
            "evidence-collection execution-plan, manual-audit execution-plan, "
            "business-owner approval execution-plan, closure-blocker, and "
            "closure-dispatch packet scope audits"
        ) in report
        assert "with a 3/15/14/5/2/2/4/1/4 source split" in report
        assert (
            "A next-action scope-audit follow-up first failed because a stale "
            "`next_closure_action` pointer could still contradict "
            "`closure_execution_sequence[0]`"
        ) in report
        assert (
            "after adding `next_closure_action_scope_audit`, the queue boundary "
            "still rolls up 50 assignment rows with a 3/15/14/5/2/2/4/1/4 "
            "source split"
        ) in report
        assert (
            "Catalog/date-lineage `evidence_collection_execution_plan` proof: a "
            "follow-up regression first failed because the closure sequence still "
            "pointed directly at `suggested_tool_call_work_items`"
        ) in report
        assert (
            "after adding the plan, the queue reports 5 execution stages covering "
            "catalog/date evidence, lineage evidence, governance validation, "
            "deferred catalog/date coverage, and deferred governance gap queues"
        ) in report
        assert (
            "Catalog/date-lineage `manual_audit_review_execution_plan` proof: a "
            "follow-up regression first failed because the manual-audit closure "
            "step still pointed directly at the audit-review and evidence-packet "
            "queues"
        ) in report
        assert (
            "after adding the plan, the queue reports 2 execution stages covering "
            "audit-review queue collection and audit-evidence packet queue collection"
        ) in report
        assert (
            "Catalog/date-lineage `business_owner_approval_execution_plan` proof: "
            "a follow-up regression first failed because the business-owner "
            "closure step still pointed at the generic manual-audit/owner-approval "
            "handoff"
        ) in report
        assert (
            "after adding the plan, the queue reports 2 execution stages covering "
            "owner approval request batches and owner approval receipt review "
            "batches for the 13 ready pages"
        ) in report
        assert (
            "A catalog/date-lineage closure-readiness follow-up first failed "
            "because a clean `queue_boundary_audit` could still be mistaken "
            "for page closure readiness"
        ) in report
        assert (
            "the queue now reports `closure_readiness`: 35 pages, 0 "
            "closure-ready pages, 35 closure-blocked pages"
        ) in report
        assert "4 closure-blocker assignment rows" in report
        assert (
            "closure blocker breakdown of record gaps 22/15, "
            "catalog/date-lineage evidence 35/14, manual audit 13/13, "
            "and business-owner approval 13/13"
        ) in report
        assert (
            "residual closure requirements remain record-gap remediation, "
            "catalog/date-lineage evidence collection, manual audit review, "
            "and business-owner approval"
        ) in report
        assert (
            "`next_closure_action` now points dispatchers to the first open "
            "blocker, currently `record_gap_remediation`, with "
            "`execution_plan=record_gap_execution_plan`, "
            "`execution_stage=remediation_type_batches`, the blocked "
            "page-slug arguments, and `queue_grants_closure=false`"
        ) in report
        assert (
            "`next_closure_action` also embeds `execution_stage_detail` for "
            "the matching `record_gap_execution_plan` stage so dispatchers "
            "can see `record_remediation_work_items` without reopening the "
            "execution plan"
        ) in report
        assert (
            "`closure_blocker_work_items` now routes those residual closure "
            "requirements into 4 read-only assignment rows"
        ) in report
        assert (
            "closure blocker work items also carry page-slug arguments so "
            "each residual blocker can be routed back to page-slug MCP call "
            "inputs without remapping page IDs"
        ) in report
        assert (
            "and source work-item group counts so the 4 closure blocker rows "
            "point back to their remediation, evidence, lane, or suggested-call "
            "assignment batches without another manual join"
        ) in report
        assert (
            "`closure_blocker_routing_index` keys the same residual blockers "
            "by blocker type with next-step, page-slug arguments, source-group "
            "counts, and `queue_grants_closure=false` for dispatcher handoff"
        ) in report
        assert (
            "closure blocker rows and routing-index entries now carry the "
            "matching next-step, execution-plan, and execution-stage keys"
        ) in report
        assert (
            "closure blocker rows and routing-index entries now embed matching "
            "`execution_stage_detail` rows so dispatcher handoff can see the "
            "stage work-item group, counts, arguments, stage next-step, and "
            "no-closure flags without reopening the execution plan"
        ) in report
        assert (
            "the record-gap blocker now points to "
            "`use_record_gap_execution_plan` instead of routing dispatchers "
            "back to raw remediation work items"
        ) in report
        assert (
            "record remediation work items now expose suggested tool-call "
            "counts and tool names for requirements, blueprint, audit-review, "
            "and evidence-packet queue routing without executing those calls"
        ) in report
        assert (
            "`closure_execution_sequence` orders residual closure work as "
            "record-gap remediation, catalog/date-lineage evidence collection, "
            "manual audit review, and business-owner approval while keeping "
            "`queue_grants_closure=false`"
        ) in report
        assert (
            "each closure execution step carries page-slug arguments and "
            "source work-item group counts so dispatchers do not have to "
            "join back to the blocker routing index"
        ) in report
        assert (
            "`closure_execution_sequence` now embeds matching "
            "`execution_stage_detail` rows for each residual blocker"
        ) in report
        assert (
            "the catalog/date-lineage evidence step now points to "
            "`use_evidence_collection_execution_plan`"
        ) in report
        assert (
            "the record-gap execution step now points to "
            "`use_record_gap_execution_plan`"
        ) in report
        assert (
            "the manual audit step now points to "
            "`use_manual_audit_review_execution_plan`"
        ) in report
        assert (
            "the business-owner approval step now points to "
            "`use_business_owner_approval_execution_plan`"
        ) in report
        assert (
            "`closure_blocker_scope_audit` checks those 4 residual-blocker "
            "rows for no-write/no-execution/no-sampling/no-lineage-check/"
            "no-smoke/no-approval-capture/no-page-approval drift"
        ) in report
        assert (
            "`closure_blocker_scope_audit` also checks embedded "
            "`execution_stage_detail` stage-level scope flags for no-write, "
            "no-execution, no-sampling, no-lineage-check, no-smoke, "
            "no-approval-capture, and no-page-approval drift"
        ) in report
        assert (
            "`closure_blocker_scope_audit` also reports "
            "`execution_target_violations` when closure-blocker rows point "
            "at the wrong next step, execution plan, or execution stage"
        ) in report
        assert (
            "`closure_blocker_scope_audit` also reports embedded "
            "`execution_stage_detail.stage_type` and "
            "`execution_stage_detail.work_item_group` drift so stale stage "
            "details cannot silently contradict the blocker routing keys"
        ) in report
        assert (
            "`queue_boundary_audit` aggregates closure-blocker execution target "
            "drift alongside scope, suggested-tool, and "
            "closure-dispatch packet target/consistency/source-sequence violations"
        ) in report
        assert (
            "`queue_boundary_audit` now aggregates embedded stage-detail "
            "scope drift from `closure_blocker_scope_audit`, not only "
            "closure-blocker execution-target drift"
        ) in report
        assert (
            "`closure_dispatch_packet` now repackages "
            "`closure_execution_sequence` into 4 ordered dispatcher rows "
            "with `dispatch_action`, execution-plan/stage keys, stage "
            "detail, page-slug arguments, source work-item group counts, "
            "and no-closure scope flags"
        ) in report
        assert (
            "It does not execute tools, write governance records, capture "
            "owner approval, or grant closure"
        ) in report
        assert (
            "`closure_dispatch_packet_scope_audit` checks the packet and "
            "each dispatch row for no-write/no-execution/no-sampling/"
            "no-lineage-check/no-smoke/no-approval-capture/"
            "no-page-approval drift and dispatch-target drift, including "
            "execution plan/stage/action, embedded stage-detail drift, "
            "dispatch-step count, pointer, sequence consistency, and "
            "source execution-sequence consistency, including missing or "
            "extra dispatcher rows"
        ) in report
        assert (
            "record gaps, catalog/date-lineage evidence collection, manual "
            "audit review, and business-owner approval while keeping "
            "writes, tool execution, sampling, smoke runs, approval capture, "
            "and page approval disabled"
        ) in report
        assert (
            "Catalog/date-lineage `record_readiness` overlay proof: the current "
            "all-seeded catalog/date-lineage review queue reports 13 "
            "ready-for-audit-review pages and 22 pages blocked by record gaps"
        ) in report
        assert (
            "The overlay copies direct-record validation/checklist state only; "
            "it is not lineage freshness, catalog/date sampling, page/API "
            "execution proof, record writing, or closure approval"
        ) in report
        assert (
            "Catalog/date-lineage `record_remediation` routing proof: the "
            "current all-seeded queue exposes row-level `record_remediation` "
            "plus `record_remediation_breakdown`: 22 create-direct-record "
            "tasks and 13 none/ready rows"
        ) in report
        assert (
            "This is read-only assignment metadata only; it does not write "
            "records, execute suggested tool calls, sample catalog/date "
            "evidence, run smoke, capture business-owner approval, prove "
            "page/API execution, or approve closure"
        ) in report
        assert (
            "Catalog/date-lineage `record_remediation_work_items` proof: a "
            "follow-up regression first failed because remediation routing "
            "still had to be assigned from row-level entries; after adding the "
            "summary work items, the queue groups 22 create-direct-record "
            "pages and 13 ready/manual-review pages"
        ) in report
        assert (
            "The grouped remediation work items preserve page-slug arguments "
            "for read-only requirements and blueprint-queue collection, but "
            "still mark no writes, no tool execution, no DuckDB sampling, no "
            "lineage checks, no smoke, no owner-approval capture, no page/API "
            "execution proof, and no approval"
        ) in report
        assert (
            "The ready/manual-review remediation work item now preserves "
            "read-only suggested calls to "
            "`moss-lineage-evidence.get_page_governance_audit_review_queue` "
            "and "
            "`moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue` "
            "for the 13 ready pages without executing either call"
        ) in report
        assert (
            "Catalog/date-lineage `record_gap_execution_plan` proof: a "
            "follow-up regression first failed because the closure sequence "
            "pointed to record-remediation work items but did not package the "
            "first remediation stage into a dispatcher-ready execution plan"
        ) in report
        assert (
            "after adding the plan, the queue reports 3 execution stages "
            "covering remediation-type batches, evidence-key batches, and "
            "review-lane batches"
        ) in report
        assert (
            "It keeps `blocked_page_count=22`, "
            "`ready_manual_review_page_count=13`, the 2/4/9 source group "
            "counts, 4 read-only suggested tool calls, stage arguments "
            "limited to the 22 blocked pages, and `queue_grants_closure=false`"
        ) in report
        assert (
            "`record_gap_execution_plan_scope_audit` adds those 3 plan stages "
            "to the queue boundary audit so execution-plan drift is caught "
            "with the rest of the no-closure guards"
        ) in report
        assert (
            "The plan still does not write records, execute suggested calls, "
            "sample DuckDB, check lineage, run smoke, capture owner approval, "
            "prove page/API execution, or approve closure"
        ) in report
        assert (
            "Catalog/date-lineage `record_remediation_evidence_work_items` "
            "proof: a follow-up regression first failed because the catalog/"
            "date-lineage remediation queue still grouped blocked pages only "
            "by remediation type; after adding the evidence-key work items, "
            "the queue groups 4 evidence collection keys"
        ) in report
        assert (
            "`page_api_execution_identifier` routes 22 create-direct-record "
            "pages, while `direct_page_or_primary_api_anchor`, "
            "`required_record_fields`, and `configured_or_deferred_table_anchors` "
            "carry the matching blocked-page assignment set"
        ) in report
        assert (
            "These evidence work items are assignment metadata only; they do "
            "not write records, execute suggested tool calls, sample DuckDB, "
            "check lineage records, run smoke, capture owner approval, prove "
            "page/API execution, or approve closure"
        ) in report
        assert (
            "Catalog/date-lineage "
            "`record_remediation_review_lane_work_items` proof: a follow-up "
            "regression first failed because review lanes and remediation "
            "types still had to be cross-referenced manually; after adding "
            "the lane-remediation work items, the queue groups 9 review-lane "
            "remediation batches"
        ) in report
        assert (
            "The formal/governed lane now routes 2 P1 create-direct-record "
            "pages and 3 P1 ready/manual-review pages, while the candidate "
            "formal-source lane routes 10 P1 create-direct-record pages "
            "and 6 P1 ready/manual-review pages, the candidate-or-mixed "
            "lane routes 5 create-direct-record pages and 2 ready/manual-review "
            "pages, the deferred lane routes 5 create-direct-record pages and "
            "1 ready/manual-review page, and the GAP/observational lane keeps "
            "Stock Analysis separate despite its configured Livermore table anchors"
        ) in report
        assert (
            "These lane-remediation work items keep the same no-write, "
            "no-tool-execution, no-DuckDB-sampling, no-lineage-check, "
            "no-smoke, no-owner-approval-capture, no-page/API-execution-proof, "
            "and no-approval boundary"
        ) in report
        assert (
            "Catalog/date-lineage `record_remediation_scope_audit` proof: a "
            "follow-up regression first failed because the new remediation "
            "work items had per-item boundary flags but no summary-level "
            "drift guard; after adding the audit, the queue reports 15 checked "
            "remediation assignment rows across remediation, evidence, and "
            "lane-remediation work items, with zero scope violations"
        ) in report
        assert (
            "A drift regression now verifies that `executes_tool_calls=true` "
            "or a missing/unknown smoke boundary is reported as a scope "
            "violation instead of silently entering the assignment queue"
        ) in report
        assert (
            "A suggested-call allowlist follow-up first failed because nested "
            "`suggested_tool_calls` inside remediation work items were not "
            "included in the scope audit"
        ) in report
    finally:
        server.close()


def test_mcp_runbook_documents_current_seeded_page_scope() -> None:
    runbook = (REPO_ROOT / "docs" / "MCP_RUNBOOK.md").read_text(encoding="utf-8")
    seeded_section = runbook.split("Seeded pages:", 1)[1].split("Boundary:", 1)[0]

    assert "The current catalog/date-lineage seeded page universe is maintained by" in seeded_section
    for page_slug in ALL_SEEDED_CATALOG_DATE_LINEAGE_PAGE_SLUGS:
        assert f"- `{page_slug}`" in seeded_section
    assert seeded_section.count("- `") == len(ALL_SEEDED_CATALOG_DATE_LINEAGE_PAGE_SLUGS)

    assert "| Tool | Default scope |" in runbook
    assert (
        "| `moss-metric-contracts.get_page_evidence_readiness` | "
        "Seeded high-risk pages only"
    ) in runbook
    assert (
        "| `moss-data-catalog.get_page_catalog_date_evidence` | "
        "Seeded high-risk pages only"
    ) in runbook
    assert (
        "| `moss-data-catalog.get_page_catalog_date_lineage_review_queue` | "
        "Every catalog/date-lineage seeded page"
    ) in runbook
    assert "Current validated snapshot:" in runbook
    assert (
        "Snapshot counts are operational evidence from the current repository state; "
        "rerun the queue and its regression tests before treating them as current."
    ) in runbook


def test_lineage_evidence_governance_audit_evidence_packet_queue_routes_supporting_only_records_to_anchor_repair(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "page_slug": "dashboard-home",
                "frontend_route": "/dashboard",
                "primary_api": "/api/bond-dashboard/headline-kpis",
                "page_id": "PAGE-BOND-001",
                "report_date": "2026-05-31",
                "basis": "analytical",
                "source_surface": "dashboard_home",
                "tables_used": ["fact_formal_bond_analytics_daily"],
                "source_version": "sv_dashboard_home",
                "created_at": "2026-06-04T12:10:00Z",
                "cache_key": "dashboard-home:supporting-bond:2026-05-31",
                "formal_use_allowed": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_audit_evidence_packet_queue",
                "arguments": {"page_slugs": ["PAGE-DASH-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["summary"]["ready_for_audit_review_count"] == 0
        assert payload["summary"]["blocked_by_record_gap_remediation_breakdown"] == {
            "repair_primary_page_anchor": 1,
        }
        assert payload["summary"]["blocked_by_record_gap_next_step_breakdown"] == {
            "repair_primary_page_api_anchor_then_preflight_candidate": 1,
        }
        assert payload["summary"]["blocked_by_record_gap_next_step_pages"] == {
            "repair_primary_page_api_anchor_then_preflight_candidate": [
                {"page_id": "PAGE-DASH-001", "page_slug": "dashboard-home"},
            ],
        }
        assert payload["summary"]["blocked_by_record_gap_next_steps"] == [
            {
                "page_id": "PAGE-DASH-001",
                "page_slug": "dashboard-home",
                "remediation_type": "repair_primary_page_anchor",
                "next_step": "repair_primary_page_api_anchor_then_preflight_candidate",
                "evidence_to_collect": [
                    "primary_page_id_or_frontend_route_or_primary_api_anchor",
                    "supporting_record_reusable_execution_fields",
                    "remaining_missing_required_fields",
                ],
                "suggested_tool_calls": [
                    {
                        "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
                        "arguments": {"page_slugs": ["dashboard-home"]},
                    },
                    {
                        "tool": "moss-lineage-evidence.get_page_governance_record_blueprint",
                        "arguments": {"page_slug": "dashboard-home"},
                    },
                ],
                "approval_boundary": "record_remediation_only",
                "evidence_scope": {
                    "writes_governance_records": False,
                    "approves_metric_or_page": False,
                    "proves_page_execution": False,
                    "executes_tool_calls": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                },
            }
        ]
        work_item = payload["summary"]["direct_record_remediation_work_items"][0]
        assert work_item["work_type"] == "repair_primary_page_anchor"
        assert work_item["remediation_type"] == "repair_primary_page_anchor"
        assert work_item["repair_targets"][0]["direct_anchor_match"] == {
            "anchor_type": "supporting_api",
            "matched_query": "/api/bond-dashboard/headline-kpis",
            "proves_primary_page_anchor": False,
        }
        assert work_item["repair_targets"][0]["missing_required_fields"] == ["rule_version"]
        assert work_item["repair_targets"][0]["failed_required_field_groups"] == [
            "record_formal_use_allowed",
        ]
        assert work_item["repair_targets"][0]["evidence_hints"] == {
            "missing_required_fields": {
                "rule_version": [
                    "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
                ],
            },
            "failed_required_field_groups": {
                "record_formal_use_allowed": [
                    "Set formal_use_allowed=false for candidate/pending pages until business-owner closure is separately approved; do not treat record repair as approval.",
                ],
            },
        }
        anchor_repair_target = work_item["anchor_repair_target"]
        assert anchor_repair_target["required_primary_anchor_types"] == [
            "page_id",
            "frontend_route",
            "primary_api",
        ]
        assert anchor_repair_target["direct_anchor_targets"]["page_id"] == "PAGE-DASH-001"
        assert anchor_repair_target["direct_anchor_targets"]["frontend_route"] == "/"
        assert anchor_repair_target["direct_anchor_targets"]["primary_api"] == "/ui/home/snapshot"
        assert "/api/bond-dashboard/headline-kpis" in anchor_repair_target[
            "direct_anchor_targets"
        ]["supporting_apis"]
        assert anchor_repair_target["current_supporting_anchor_matches"] == [
            {
                "anchor_type": "supporting_api",
                "matched_query": "/api/bond-dashboard/headline-kpis",
                "proves_primary_page_anchor": False,
            }
        ]
        assert anchor_repair_target["preflight_repair_templates"] == [
            {
                "record_location": {
                    "stream": "cache_manifest",
                    "line": 1,
                    "matched_query": "/api/bond-dashboard/headline-kpis",
                },
                "tool": "moss-lineage-evidence.preflight_page_governance_record",
                "arguments": {
                    "page_slug": "dashboard-home",
                    "record": {
                        "page_id": "PAGE-DASH-001",
                        "page_slug": "dashboard-home",
                        "frontend_route": "/",
                        "primary_api": "/ui/home/snapshot",
                        "tables_used": ["fact_formal_bond_analytics_daily"],
                        "formal_use_allowed": False,
                        "report_date": "2026-05-31",
                        "basis": "analytical",
                        "source_surface": "dashboard_home",
                        "source_version": "sv_dashboard_home",
                        "rule_version": None,
                        "created_at": "2026-06-04T12:10:00Z",
                        "cache_key": "dashboard-home:supporting-bond:2026-05-31",
                        "run_id": None,
                    },
                },
                "manual_placeholders": ["rule_version"],
                "approval_boundary": "preflight_only_no_write_no_approval",
                "evidence_scope": {
                    "writes_governance_records": False,
                    "approves_metric_or_page": False,
                    "proves_page_execution": False,
                    "checks_record_existence": False,
                },
            }
        ]
        assert any("primary page/API anchor is missing" in gap for gap in work_item["residual_gaps"])
    finally:
        server.close()


def test_lineage_evidence_governance_audit_evidence_packet_queue_preflights_existing_direct_record_completion(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "page_id": "PAGE-BOND-001",
                "page_slug": "bond-dashboard",
                "frontend_route": "/bond-dashboard",
                "primary_api": "/api/bond-dashboard/headline-kpis",
                "report_date": "2026-05-31",
                "basis": "analytical",
                "source_surface": "bond_analytics",
                "tables_used": ["fact_formal_bond_analytics_daily"],
                "source_version": "sv_bond_analytics",
                "created_at": "2026-06-04T12:05:00Z",
                "formal_use_allowed": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_audit_evidence_packet_queue",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        work_item = payload["summary"]["direct_record_remediation_work_items"][0]
        repair_target = work_item["repair_targets"][0]
        assert repair_target["preflight_completion_template"] == {
            "tool": "moss-lineage-evidence.preflight_page_governance_record",
            "arguments": {
                "page_slug": "bond-dashboard",
                "record": {
                    "page_id": "PAGE-BOND-001",
                    "page_slug": "bond-dashboard",
                    "frontend_route": "/bond-dashboard",
                    "primary_api": "/api/bond-dashboard/headline-kpis",
                    "tables_used": ["fact_formal_bond_analytics_daily"],
                    "formal_use_allowed": False,
                    "report_date": "2026-05-31",
                    "basis": "analytical",
                    "source_surface": "bond_analytics",
                    "source_version": "sv_bond_analytics",
                    "rule_version": None,
                    "created_at": "2026-06-04T12:05:00Z",
                    "cache_key": None,
                    "run_id": None,
                },
            },
            "manual_placeholders": ["rule_version", "cache_key_or_run_id"],
            "approval_boundary": "preflight_only_no_write_no_approval",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "checks_record_existence": False,
            },
        }
    finally:
        server.close()


def test_lineage_evidence_governance_audit_evidence_packet_queue_groups_repair_evidence_work_items(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "page_id": "PAGE-BOND-001",
                "page_slug": "bond-dashboard",
                "frontend_route": "/bond-dashboard",
                "primary_api": "/api/bond-dashboard/headline-kpis",
                "report_date": "2026-05-31",
                "basis": "analytical",
                "source_surface": "bond_analytics",
                "tables_used": ["fact_formal_bond_analytics_daily"],
                "source_version": "sv_bond_analytics",
                "created_at": "2026-06-04T12:05:00Z",
                "formal_use_allowed": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_audit_evidence_packet_queue",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        work_items = {
            item["evidence_key"]: item
            for item in payload["summary"]["repair_direct_record_evidence_work_items"]
        }
        assert set(work_items) == {
            "execution_identifier",
            "record_formal_use_allowed",
            "rule_version",
        }
        assert work_items["rule_version"] == {
            "evidence_key": "rule_version",
            "kind": "field",
            "status": "missing",
            "page_count": 1,
            "pages": [{"page_id": "PAGE-BOND-001", "page_slug": "bond-dashboard"}],
            "remediation_types": ["complete_direct_record_fields"],
            "record_locations": [
                {
                    "page_id": "PAGE-BOND-001",
                    "page_slug": "bond-dashboard",
                    "record_location": {
                        "stream": "cache_manifest",
                        "line": 1,
                        "matched_query": "PAGE-BOND-001",
                    },
                }
            ],
            "evidence_hints": [
                "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
            ],
            "approval_boundary": "record_repair_evidence_collection_only",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
            },
        }
        assert work_items["execution_identifier"]["kind"] == "group"
        assert work_items["execution_identifier"]["status"] == "failed"
        assert work_items["execution_identifier"]["page_count"] == 1
        assert work_items["record_formal_use_allowed"]["kind"] == "group"
        assert work_items["record_formal_use_allowed"]["status"] == "failed"
        assert work_items["record_formal_use_allowed"]["page_count"] == 1
    finally:
        server.close()


def test_lineage_evidence_governance_audit_evidence_packet_queue_marks_deferred_table_anchor_creation_targets() -> None:
    server = McpProcess("lineage-evidence")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_audit_evidence_packet_queue",
                "arguments": {"page_slugs": ["PAGE-EXEC-SUMMARY-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["summary"]["blocked_by_record_gap_remediation_breakdown"] == {
            "create_direct_record": 1,
        }
        assert payload["summary"]["create_direct_record_table_anchor_work_items"] == [
            {
                "table_anchor_status": "deferred_no_direct_table_config",
                "page_count": 1,
                "pages": [
                    {
                        "page_id": "PAGE-EXEC-SUMMARY-001",
                        "page_slug": "executive-summary",
                        "deferred_reason": (
                            "Narrative-only summary endpoint; table/date review belongs to upstream overview and snapshot evidence."
                        ),
                    }
                ],
                "next_action": "resolve_without_inventing_tables_used",
                "approval_boundary": "record_creation_table_anchor_routing_only",
                "evidence_scope": {
                    "writes_governance_records": False,
                    "approves_metric_or_page": False,
                    "proves_page_execution": False,
                    "executes_tool_calls": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                },
            }
        ]
        work_item = payload["summary"]["direct_record_remediation_work_items"][0]
        assert work_item["page_id"] == "PAGE-EXEC-SUMMARY-001"
        creation_target = work_item["creation_target"]
        assert creation_target["configured_table_names"] == []
        assert creation_target["table_anchor_resolution_target"] == {
            "resolution_type": "deferred_no_direct_table_config",
            "deferred_reason": (
                "Narrative-only summary endpoint; table/date review belongs to upstream overview and snapshot evidence."
            ),
            "required_action": "do_not_invent_tables_used",
            "review_targets": [
                "upstream source pages",
                "direct page/API governance record",
                "visible stale/fallback/no-data state",
                "result_meta",
            ],
            "suggested_tool_calls": [
                {
                    "tool": "moss-data-catalog.get_page_catalog_date_coverage",
                    "arguments": {"page_slugs": ["executive-summary"]},
                },
            ],
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "samples_duckdb_tables": False,
            },
        }
        table_detail = next(
            detail
            for detail in creation_target["manual_fill_field_details"]
            if detail["name"] == "tables_used"
        )
        assert table_detail["status"] == "missing"
        assert table_detail["evidence_hints"] == [
            "This page has no direct table contract; do not invent tables_used. Resolve through the table_anchor_resolution_target and upstream/page-run evidence.",
        ]
        table_work_item = next(
            item
            for item in payload["summary"]["create_direct_record_evidence_work_items"]
            if item["evidence_key"] == "tables_used"
        )
        assert table_work_item["page_count"] == 1
        assert table_work_item["pages"] == [
            {"page_id": "PAGE-EXEC-SUMMARY-001", "page_slug": "executive-summary"},
        ]
    finally:
        server.close()


def test_lineage_evidence_candidate_governance_record_preflight_rejects_candidate_formal_use() -> None:
    server = McpProcess("lineage-evidence")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "preflight_page_governance_record" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "preflight_page_governance_record",
                "arguments": {
                    "page_slug": "PAGE-BOND-001",
                    "record": {
                        "page_id": "PAGE-BOND-001",
                        "page_slug": "bond-dashboard",
                        "frontend_route": "/bond-dashboard",
                        "primary_api": "/api/bond-dashboard/headline-kpis",
                        "report_date": "2026-05-31",
                        "basis": "analytical",
                        "source_surface": "bond_analytics",
                        "tables_used": ["fact_formal_bond_analytics_daily"],
                        "source_version": "sv_bond_analytics",
                        "rule_version": "rv_bond_dashboard_headline_v1",
                        "created_at": "2026-06-04T12:00:00Z",
                        "cache_key": "bond_dashboard.headline:2026-05-31",
                        "formal_use_allowed": True,
                        "result_kind": "bond_dashboard.headline_kpis",
                    },
                },
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-record-preflight"
        assert "does not write governance records" in payload["disclaimer"]
        assert payload["page_id"] == "PAGE-BOND-001"
        assert payload["approval_status"] == "candidate_or_pending"
        assert payload["validation"]["validation_status"] == "incomplete"
        assert payload["validation"]["missing_required_fields"] == []
        assert any(
            group["name"] == "record_formal_use_allowed"
            for group in payload["validation"]["failed_required_field_groups"]
        )
        assert payload["record_formal_use_policy"] == "must_be_false_until_candidate_closure"
        assert payload["evidence_scope"]["writes_governance_records"] is False
        assert payload["evidence_scope"]["approves_metric_or_page"] is False
        assert payload["evidence_scope"]["proves_page_execution"] is False
    finally:
        server.close()


def test_lineage_evidence_candidate_governance_record_preflight_accepts_complete_formal_record_without_approval() -> None:
    server = McpProcess("lineage-evidence")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "preflight_page_governance_record",
                "arguments": {
                    "page_slug": "PAGE-PROD-CAT-001",
                    "record": {
                        "page_id": "PAGE-PROD-CAT-001",
                        "page_slug": "product-category-pnl",
                        "frontend_route": "/product-category-pnl",
                        "primary_api": "/ui/pnl/product-category",
                        "report_date": "2026-05-31",
                        "basis": "formal",
                        "source_surface": "product_category_pnl",
                        "tables_used": [
                            "product_category_pnl_formal_read_model",
                            "product_category_pnl_canonical_fact",
                        ],
                        "source_version": "sv_product_category_pnl",
                        "rule_version": "rv_product_category_pnl_v1",
                        "created_at": "2026-06-04T12:00:00Z",
                        "run_id": "product-category-pnl:2026-05-31",
                        "formal_use_allowed": True,
                        "result_kind": "product_category_pnl.detail",
                    },
                },
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["page_id"] == "PAGE-PROD-CAT-001"
        assert payload["approval_status"] == "formal_or_governed"
        assert payload["validation"]["validation_status"] == "ready_for_audit_review"
        assert payload["validation"]["missing_required_fields"] == []
        assert payload["validation"]["failed_required_field_groups"] == []
        assert payload["record_formal_use_policy"] == "may_be_true_only_after_direct_record_and_contract_evidence"
        assert payload["evidence_scope"]["checks_record_existence"] is False
        assert payload["evidence_scope"]["approves_metric_or_page"] is False
        assert any("does not prove page execution" in gap for gap in payload["validation"]["residual_gaps"])
    finally:
        server.close()


def test_lineage_evidence_candidate_governance_record_preflight_requires_direct_anchor() -> None:
    server = McpProcess("lineage-evidence")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "preflight_page_governance_record",
                "arguments": {
                    "page_slug": "PAGE-BOND-001",
                    "record": {
                        "page_id": "PAGE-OTHER-001",
                        "page_slug": "other-page",
                        "frontend_route": "/other-page",
                        "primary_api": "/api/other-page",
                        "report_date": "2026-05-31",
                        "basis": "analytical",
                        "source_surface": "bond_analytics",
                        "tables_used": ["fact_formal_bond_analytics_daily"],
                        "source_version": "sv_bond_analytics",
                        "rule_version": "rv_bond_dashboard_headline_v1",
                        "created_at": "2026-06-04T12:00:00Z",
                        "cache_key": "bond_dashboard.headline:2026-05-31",
                        "formal_use_allowed": False,
                        "result_kind": "bond_dashboard.headline_kpis",
                    },
                },
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["page_id"] == "PAGE-BOND-001"
        assert payload["validation"]["validation_status"] == "incomplete"
        assert payload["validation"]["missing_required_fields"] == []
        assert any(
            group["name"] == "direct_page_or_api_anchor"
            for group in payload["validation"]["failed_required_field_groups"]
        )
        assert any("direct page/API anchor" in gap for gap in payload["validation"]["residual_gaps"])
    finally:
        server.close()


def test_lineage_evidence_candidate_governance_record_preflight_requires_configured_table_anchor() -> None:
    server = McpProcess("lineage-evidence")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "preflight_page_governance_record",
                "arguments": {
                    "page_slug": "PAGE-BOND-001",
                    "record": {
                        "page_id": "PAGE-BOND-001",
                        "page_slug": "bond-dashboard",
                        "frontend_route": "/bond-dashboard",
                        "primary_api": "/api/bond-dashboard/headline-kpis",
                        "report_date": "2026-05-31",
                        "basis": "analytical",
                        "source_surface": "bond_analytics",
                        "tables_used": ["fact_formal_pnl_fi"],
                        "source_version": "sv_bond_analytics",
                        "rule_version": "rv_bond_dashboard_headline_v1",
                        "created_at": "2026-06-04T12:00:00Z",
                        "cache_key": "bond_dashboard.headline:2026-05-31",
                        "formal_use_allowed": False,
                        "result_kind": "bond_dashboard.headline_kpis",
                    },
                },
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["configured_table_names"] == ["fact_formal_bond_analytics_daily"]
        assert payload["validation"]["validation_status"] == "incomplete"
        assert any(
            group["name"] == "configured_table_anchor"
            for group in payload["validation"]["failed_required_field_groups"]
        )
        assert any("configured table anchor" in gap for gap in payload["validation"]["residual_gaps"])
    finally:
        server.close()


def test_lineage_evidence_governance_record_blueprint_builds_candidate_template_without_writes() -> None:
    server = McpProcess("lineage-evidence")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_governance_record_blueprint" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_record_blueprint",
                "arguments": {"page_slug": "PAGE-BOND-001"},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-record-blueprint"
        assert "does not write governance records" in payload["disclaimer"]
        assert "does not approve metric/page formal use" in payload["disclaimer"]
        assert payload["page_id"] == "PAGE-BOND-001"
        assert payload["approval_status"] == "candidate_or_pending"
        assert payload["record_formal_use_policy"] == "must_be_false_until_candidate_closure"
        assert "PAGE-BOND-001" in payload["accepted_direct_terms"]
        assert "/bond-dashboard" in payload["accepted_direct_terms"]
        assert "/api/bond-dashboard/headline-kpis" in payload["accepted_direct_terms"]
        assert "fact_formal_bond_analytics_daily" not in payload["accepted_direct_terms"]
        assert payload["direct_anchor_targets"]["page_id"] == "PAGE-BOND-001"
        assert payload["direct_anchor_targets"]["frontend_route"] == "/bond-dashboard"
        assert payload["direct_anchor_targets"]["primary_api"] == "/api/bond-dashboard/headline-kpis"
        assert "/api/bond-dashboard/dates" in payload["direct_anchor_targets"]["supporting_apis"]
        assert "/api/bond-dashboard/risk-indicators" in payload["direct_anchor_targets"]["supporting_apis"]
        assert "/api/bond-dashboard/business-type-metrics" in payload["direct_anchor_targets"]["supporting_apis"]
        assert payload["configured_table_names"] == ["fact_formal_bond_analytics_daily"]

        candidate = payload["candidate_record"]
        assert candidate["page_id"] == "PAGE-BOND-001"
        assert candidate["page_slug"] == "bond-dashboard"
        assert candidate["frontend_route"] == "/bond-dashboard"
        assert candidate["primary_api"] == "/api/bond-dashboard/headline-kpis"
        assert candidate["tables_used"] == ["fact_formal_bond_analytics_daily"]
        assert candidate["formal_use_allowed"] is False
        assert candidate["report_date"] is None
        assert candidate["basis"] is None
        assert candidate["source_surface"] is None
        assert candidate["source_version"] is None
        assert candidate["rule_version"] is None
        assert candidate["created_at"] is None
        assert candidate["cache_key"] is None
        assert candidate["run_id"] is None

        assert payload["manual_fill_fields"] == [
            "report_date",
            "basis",
            "source_surface",
            "source_version",
            "rule_version",
            "created_at",
            "cache_key_or_run_id",
        ]
        assert payload["preflight"]["validation"]["validation_status"] == "incomplete"
        assert set(payload["preflight"]["validation"]["missing_required_fields"]) == {
            "report_date",
            "basis",
            "source_surface",
            "source_version",
            "rule_version",
            "created_at",
        }
        assert any(
            group["name"] == "execution_identifier"
            for group in payload["preflight"]["validation"]["failed_required_field_groups"]
        )
        assert payload["evidence_scope"]["writes_governance_records"] is False
        assert payload["evidence_scope"]["checks_record_existence"] is False
        assert payload["evidence_scope"]["proves_page_execution"] is False
        assert payload["evidence_scope"]["approves_metric_or_page"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_record_blueprint_for_formal_page_still_requires_audit_review() -> None:
    server = McpProcess("lineage-evidence")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_record_blueprint",
                "arguments": {"page_slug": "PAGE-PROD-CAT-001"},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["page_id"] == "PAGE-PROD-CAT-001"
        assert payload["approval_status"] == "formal_or_governed"
        assert payload["record_formal_use_policy"] == "may_be_true_only_after_direct_record_and_contract_evidence"
        assert payload["candidate_record"]["formal_use_allowed"] is False
        assert payload["candidate_record"]["tables_used"] == [
            "product_category_pnl_formal_read_model",
            "product_category_pnl_canonical_fact",
        ]
        assert payload["preflight"]["validation"]["validation_status"] == "incomplete"
        assert any(
            "Required checklist fields or field groups are missing" in gap
            for gap in payload["preflight"]["validation"]["residual_gaps"]
        )
        assert payload["evidence_scope"]["approves_metric_or_page"] is False
        assert payload["evidence_scope"]["proves_page_execution"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_record_blueprint_queue_covers_default_open_gaps(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_governance_record_blueprint_queue" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_record_blueprint_queue",
                "arguments": {"max_results": 5},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-record-blueprint-queue"
        assert "does not write governance records" in payload["disclaimer"]
        assert "does not approve metric/page formal use" in payload["disclaimer"]
        assert payload["summary"] == {
            "page_count": 6,
            "open_gap_count": 6,
            "blueprint_count": 6,
            "template_preflight_ready_count": 0,
            "template_preflight_incomplete_count": 6,
            "ready_blueprint_count": 0,
            "incomplete_blueprint_count": 6,
        }

        page_ids = [item["page_id"] for item in payload["items"]]
        assert page_ids == [
            "PAGE-LEDGER-PNL-001",
            "PAGE-BOND-001",
            "PAGE-POS-001",
            "PAGE-MKT-001",
            "GAP-STOCK-ANALYSIS-PAGE",
            "PAGE-OPS-001",
        ]

        ledger = payload["items"][0]
        assert ledger["gap_type"] == "missing_direct_and_expanded_records"
        assert ledger["priority"] == "P1"
        assert ledger["candidate_record_readiness"]["manual_fill_priority"] == (
            "create_direct_record_and_supporting_lineage"
        )
        assert ledger["candidate_record_readiness"]["validation_status"] == "incomplete"
        assert ledger["candidate_record_readiness"]["manual_fill_fields"] == ledger["blueprint"]["manual_fill_fields"]
        assert ledger["candidate_record_readiness"]["missing_required_fields"] == [
            "report_date",
            "basis",
            "source_surface",
            "source_version",
            "rule_version",
            "created_at",
        ]
        assert ledger["candidate_record_readiness"]["failed_required_field_groups"] == ["execution_identifier"]
        assert ledger["candidate_record_readiness"]["manual_fill_field_details"] == [
            {
                "kind": "field",
                "name": "page_id",
                "status": "prefilled",
                "value": "PAGE-LEDGER-PNL-001",
                "satisfying_values": [],
            },
            {
                "kind": "field",
                "name": "page_slug",
                "status": "prefilled",
                "value": "ledger-pnl",
                "satisfying_values": [],
            },
            {
                "kind": "field",
                "name": "frontend_route",
                "status": "prefilled",
                "value": "/ledger-pnl",
                "satisfying_values": [],
            },
            {
                "kind": "field",
                "name": "primary_api",
                "status": "prefilled",
                "value": "/api/ledger-pnl/summary",
                "satisfying_values": [],
            },
            {
                "kind": "field",
                "name": "report_date",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use catalog/date evidence or the audited page/API payload date binding for the reviewed run; do not infer the date from unrelated upstream tables.",
                ],
            },
            {
                "kind": "field",
                "name": "basis",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use explicit page contract, source basis, or approval-status evidence for the reviewed run; do not infer formal or analytical basis from the page slug alone.",
                ],
            },
            {
                "kind": "field",
                "name": "source_surface",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use page/API result metadata, route/service source-surface evidence, or direct lineage metadata for the reviewed run.",
                ],
            },
            {
                "kind": "field",
                "name": "tables_used",
                "status": "prefilled",
                "value": [
                    "qdb_general_ledger_workbook",
                    "ledger_import_batch",
                    "ledger_raw_row",
                ],
                "satisfying_values": [],
            },
            {
                "kind": "field",
                "name": "source_version",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use source manifest, cache, run, or vendor/feed evidence tied to the reviewed run; do not invent a source version.",
                ],
            },
            {
                "kind": "field",
                "name": "rule_version",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
                ],
            },
            {
                "kind": "field",
                "name": "created_at",
                "status": "missing",
                "value": None,
                "satisfying_values": [],
                "evidence_hints": [
                    "Use the governance record creation or review timestamp; do not substitute the report date.",
                ],
            },
            {
                "kind": "group",
                "name": "direct_page_or_api_anchor",
                "status": "satisfied",
                "value": None,
                "satisfying_values": ledger["candidate_record_readiness"]["accepted_direct_terms"],
            },
            {
                "kind": "group",
                "name": "execution_identifier",
                "status": "failed",
                "value": None,
                "satisfying_values": ["cache_key", "run_id"],
                "evidence_hints": [
                    "Use a cache_key or run_id from the audited page/API execution evidence; expanded source-table or result-kind anchors are supporting evidence only.",
                ],
            },
            {
                "kind": "group",
                "name": "configured_table_anchor",
                "status": "satisfied",
                "value": None,
                "satisfying_values": [
                    "qdb_general_ledger_workbook",
                    "ledger_import_batch",
                    "ledger_raw_row",
                ],
            },
            {
                "kind": "group",
                "name": "record_formal_use_allowed",
                "status": "satisfied",
                "value": False,
                "satisfying_values": ["formal_use_allowed=false"],
            },
        ]
        assert "Create a direct page/API governance record" in ledger["candidate_record_readiness"]["explanation"]
        assert "does not approve closure" in ledger["candidate_record_readiness"]["explanation"]
        assert ledger["blueprint"]["page_id"] == "PAGE-LEDGER-PNL-001"
        assert ledger["blueprint"]["candidate_record"]["formal_use_allowed"] is False
        assert ledger["blueprint"]["preflight"]["validation"]["validation_status"] == "incomplete"
        assert "cache_key_or_run_id" in ledger["blueprint"]["manual_fill_fields"]

        bond = next(item for item in payload["items"] if item["page_id"] == "PAGE-BOND-001")
        assert bond["gap_type"] == "missing_direct_and_expanded_records"
        assert bond["direct_anchor_targets"]["page_id"] == "PAGE-BOND-001"
        assert bond["direct_anchor_targets"]["frontend_route"] == "/bond-dashboard"
        assert bond["direct_anchor_targets"]["primary_api"] == "/api/bond-dashboard/headline-kpis"
        assert "/api/bond-dashboard/dates" in bond["direct_anchor_targets"]["supporting_apis"]
        assert "/api/bond-dashboard/risk-indicators" in bond["direct_anchor_targets"]["supporting_apis"]
        assert "/api/bond-dashboard/business-type-metrics" in bond["direct_anchor_targets"]["supporting_apis"]
        assert bond["candidate_record_readiness"]["direct_anchor_targets"] == bond["direct_anchor_targets"]
        assert bond["blueprint"]["candidate_record"]["tables_used"] == ["fact_formal_bond_analytics_daily"]
        assert bond["evidence_scope"]["writes_governance_records"] is False
        assert bond["evidence_scope"]["checks_record_existence"] is False
        assert bond["evidence_scope"]["proves_page_execution"] is False
        assert bond["evidence_scope"]["approves_metric_or_page"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_record_blueprint_queue_explains_incomplete_direct_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "page_id": "PAGE-BOND-001",
                "page_slug": "bond-dashboard",
                "frontend_route": "/bond-dashboard",
                "primary_api": "/api/bond-dashboard/headline-kpis",
                "report_date": "2026-05-31",
                "basis": "analytical",
                "source_surface": "bond_analytics",
                "tables_used": ["fact_formal_bond_analytics_daily"],
                "source_version": "sv_bond_analytics",
                "created_at": "2026-06-04T12:05:00Z",
                "formal_use_allowed": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_record_blueprint_queue",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        item = payload["items"][0]
        readiness = item["candidate_record_readiness"]
        assert item["gap_type"] == "direct_record_incomplete"
        assert readiness["manual_fill_priority"] == "complete_existing_direct_record"
        assert readiness["existing_direct_record_missing_fields"] == ["rule_version"]
        assert readiness["existing_direct_record_failed_field_groups"] == [
            "execution_identifier",
            "record_formal_use_allowed",
        ]
        assert readiness["repair_targets"] == [
            {
                "record_location": {
                    "stream": "cache_manifest",
                    "line": 1,
                    "matched_query": "PAGE-BOND-001",
                },
                "missing_required_fields": ["rule_version"],
                "failed_required_field_groups": [
                    "execution_identifier",
                    "record_formal_use_allowed",
                ],
                "direct_anchor_match": {
                    "anchor_type": "page_id",
                    "matched_query": "PAGE-BOND-001",
                    "proves_primary_page_anchor": True,
                },
                "record_formal_use_allowed": True,
                "evidence_hints": {
                    "missing_required_fields": {
                        "rule_version": [
                            "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
                        ],
                    },
                    "failed_required_field_groups": {
                        "execution_identifier": [
                            "Use a cache_key or run_id from the audited page/API execution evidence; expanded source-table or result-kind anchors are supporting evidence only.",
                        ],
                        "record_formal_use_allowed": [
                            "Set formal_use_allowed=false for candidate/pending pages until business-owner closure is separately approved; do not treat record repair as approval.",
                        ],
                    },
                },
            }
        ]
        assert "Complete the existing direct page/API governance record" in readiness["explanation"]
        assert "rule_version" in readiness["explanation"]
        assert "record_formal_use_allowed" in readiness["explanation"]
        assert readiness["configured_table_names"] == ["fact_formal_bond_analytics_daily"]
        assert readiness["accepted_direct_terms"] == item["accepted_direct_terms"]
        assert item["evidence_scope"]["writes_governance_records"] is False
        assert item["evidence_scope"]["approves_metric_or_page"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_record_blueprint_queue_keeps_multiple_repair_targets_separate(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "page_id": "PAGE-BOND-001",
            "page_slug": "bond-dashboard",
            "frontend_route": "/bond-dashboard",
            "primary_api": "/api/bond-dashboard/headline-kpis",
            "report_date": "2026-05-31",
            "basis": "analytical",
            "source_surface": "bond_analytics",
            "tables_used": ["fact_formal_bond_analytics_daily"],
            "source_version": "sv_bond_analytics",
            "created_at": "2026-06-04T12:05:00Z",
            "run_id": "bond-dashboard-run-1",
            "formal_use_allowed": False,
        },
        {
            "page_id": "PAGE-BOND-001",
            "page_slug": "bond-dashboard",
            "frontend_route": "/bond-dashboard",
            "primary_api": "/api/bond-dashboard/headline-kpis",
            "report_date": "2026-05-31",
            "basis": "analytical",
            "source_surface": "bond_analytics",
            "tables_used": ["fact_formal_bond_analytics_daily"],
            "source_version": "sv_bond_analytics",
            "rule_version": "rv_bond_analytics",
            "created_at": "2026-06-04T12:06:00Z",
            "formal_use_allowed": True,
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_record_blueprint_queue",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        readiness = payload["items"][0]["candidate_record_readiness"]
        assert readiness["manual_fill_priority"] == "complete_existing_direct_record"
        assert readiness["existing_direct_record_missing_fields"] == ["rule_version"]
        assert readiness["existing_direct_record_failed_field_groups"] == [
            "execution_identifier",
            "record_formal_use_allowed",
        ]
        assert readiness["repair_targets"] == [
            {
                "record_location": {
                    "stream": "cache_manifest",
                    "line": 1,
                    "matched_query": "PAGE-BOND-001",
                },
                "missing_required_fields": ["rule_version"],
                "failed_required_field_groups": [],
                "direct_anchor_match": {
                    "anchor_type": "page_id",
                    "matched_query": "PAGE-BOND-001",
                    "proves_primary_page_anchor": True,
                },
                "record_formal_use_allowed": False,
                "evidence_hints": {
                    "missing_required_fields": {
                        "rule_version": [
                            "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
                        ],
                    },
                },
            },
            {
                "record_location": {
                    "stream": "cache_manifest",
                    "line": 2,
                    "matched_query": "PAGE-BOND-001",
                },
                "missing_required_fields": [],
                "failed_required_field_groups": [
                    "execution_identifier",
                    "record_formal_use_allowed",
                ],
                "direct_anchor_match": {
                    "anchor_type": "page_id",
                    "matched_query": "PAGE-BOND-001",
                    "proves_primary_page_anchor": True,
                },
                "record_formal_use_allowed": True,
                "evidence_hints": {
                    "failed_required_field_groups": {
                        "execution_identifier": [
                            "Use a cache_key or run_id from the audited page/API execution evidence; expanded source-table or result-kind anchors are supporting evidence only.",
                        ],
                        "record_formal_use_allowed": [
                            "Set formal_use_allowed=false for candidate/pending pages until business-owner closure is separately approved; do not treat record repair as approval.",
                        ],
                    },
                },
            },
        ]
        assert "2 existing direct page/API governance records" in readiness["explanation"]
        assert payload["items"][0]["evidence_scope"]["proves_page_execution"] is False
        assert payload["items"][0]["evidence_scope"]["approves_metric_or_page"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_record_blueprint_queue_inherits_supporting_only_expanded_anchor_samples(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "table_name": "fact_formal_bond_analytics_daily",
                "source_version": "sv_bond_analytics",
                "report_date": "2026-05-31",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_record_blueprint_queue",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        item = payload["items"][0]
        assert item["gap_type"] == "missing_direct_record_expanded_only"
        assert item["candidate_record_readiness"]["manual_fill_priority"] == (
            "create_direct_record_from_existing_supporting_lineage"
        )
        assert item["expanded_anchor_samples"][0]["supporting_only"] is True
        assert item["expanded_anchor_samples"][0]["proves_page_execution"] is False
        assert item["expanded_anchor_samples"][0]["anchor_type"] == "source_table"
        assert item["expanded_anchor_samples"][0]["record_summary"] == {
            "table_name": "fact_formal_bond_analytics_daily",
            "source_version": "sv_bond_analytics",
            "report_date": "2026-05-31",
        }
        assert item["evidence_scope"]["writes_governance_records"] is False
        assert item["evidence_scope"]["proves_page_execution"] is False
        assert item["evidence_scope"]["approves_metric_or_page"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_record_blueprint_queue_can_cover_all_seeded_open_gaps(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_record_blueprint_queue",
                "arguments": {"all_seeded_pages": True, "max_results": 3},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["summary"]["page_count"] == 39
        assert payload["summary"]["open_gap_count"] == 39
        assert payload["summary"]["blueprint_count"] == 39
        assert payload["summary"]["template_preflight_ready_count"] == 0
        assert payload["summary"]["template_preflight_incomplete_count"] == 39
        assert payload["summary"]["ready_blueprint_count"] == 0
        assert payload["summary"]["incomplete_blueprint_count"] == 39

        page_ids = {item["page_id"] for item in payload["items"]}
        assert {
            "PAGE-PROD-CAT-001",
            "PAGE-CUBE-QUERY-001",
            "PAGE-PORTFOLIO-HOME-001",
            "PAGE-EXEC-SUMMARY-001",
            "PAGE-AGENT-001",
            "GAP-BANK-LEDGER-DASHBOARD-PAGE",
            "GAP-CASHFLOW-PROJECTION-PAGE",
            "GAP-CONCENTRATION-MONITOR-PAGE",
            "GAP-PLATFORM-CONFIG-PAGE",
            "GAP-NEWS-EVENTS-PAGE",
            "GAP-DECISION-ITEMS-PAGE",
            "GAP-KPI-PERFORMANCE-PAGE",
        }.issubset(page_ids)
        assert "PAGE-PROD-CAT-PNL-001" not in page_ids
        assert len(page_ids) == 39
        assert all(item["blueprint"]["candidate_record"]["formal_use_allowed"] is False for item in payload["items"])
        assert all(item["evidence_scope"]["writes_governance_records"] is False for item in payload["items"])
        assert all(item["evidence_scope"]["proves_page_execution"] is False for item in payload["items"])
    finally:
        server.close()


def test_lineage_evidence_governance_gap_queue_prioritizes_default_high_risk_pages(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_governance_gap_queue" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_gap_queue",
                "arguments": {"max_results": 5},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-gap-queue"
        assert "does not create governance records" in payload["disclaimer"]
        assert payload["summary"]["page_count"] == 6
        assert payload["summary"]["open_gap_count"] == 6
        assert payload["summary"]["missing_direct_record_count"] == 6
        assert payload["summary"]["ready_for_audit_review_count"] == 0

        page_ids = [item["page_id"] for item in payload["items"]]
        assert page_ids == [
            "PAGE-LEDGER-PNL-001",
            "PAGE-BOND-001",
            "PAGE-POS-001",
            "PAGE-MKT-001",
            "GAP-STOCK-ANALYSIS-PAGE",
            "PAGE-OPS-001",
        ]

        ledger = payload["items"][0]
        assert ledger["priority"] == "P1"
        assert ledger["gap_type"] == "missing_direct_and_expanded_records"
        assert ledger["validation_status"] == "missing_direct_records"
        assert ledger["direct_record_count"] == 0
        assert ledger["expanded_anchor_record_count"] == 0
        assert any("Add or locate a direct PAGE-LEDGER-PNL-001/API governance record" in action for action in ledger["next_actions"])

        bond = next(item for item in payload["items"] if item["page_id"] == "PAGE-BOND-001")
        assert bond["priority"] == "P1"
        assert bond["gap_type"] == "missing_direct_and_expanded_records"
        assert bond["direct_record_count"] == 0
        assert bond["expanded_anchor_record_count"] == 0
        assert any("Add supporting source-table/result-kind lineage records" in action for action in bond["next_actions"])
        assert bond["evidence_scope"]["writes_governance_records"] is False
        assert bond["evidence_scope"]["approves_metric_or_page"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_gap_queue_surfaces_supporting_only_expanded_anchor_samples(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "table_name": "fact_formal_bond_analytics_daily",
                        "source_version": "sv_bond_analytics",
                        "report_date": "2026-05-31",
                    }
                ),
                json.dumps(
                    {
                        "result_kind": "bond_dashboard.headline_kpis",
                        "source_surface": "bond_analytics",
                        "report_date": "2026-05-31",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_gap_queue",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        item = payload["items"][0]
        assert item["gap_type"] == "missing_direct_record_expanded_only"
        assert item["expanded_anchor_record_count"] == 2
        assert item["expanded_anchor_samples"] == [
            {
                "record_location": {
                    "stream": "cache_manifest",
                    "line": 1,
                    "matched_query": "fact_formal_bond_analytics_daily",
                },
                "anchor_type": "source_table",
                "supporting_only": True,
                "proves_page_execution": False,
                "record_summary": {
                    "table_name": "fact_formal_bond_analytics_daily",
                    "source_version": "sv_bond_analytics",
                    "report_date": "2026-05-31",
                },
            },
            {
                "record_location": {
                    "stream": "cache_manifest",
                    "line": 2,
                    "matched_query": "bond_dashboard.headline_kpis",
                },
                "anchor_type": "result_kind",
                "supporting_only": True,
                "proves_page_execution": False,
                "record_summary": {
                    "result_kind": "bond_dashboard.headline_kpis",
                    "source_surface": "bond_analytics",
                    "report_date": "2026-05-31",
                },
            },
        ]
        assert item["evidence_scope"]["proves_page_execution"] is False
        assert item["evidence_scope"]["approves_metric_or_page"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_gap_queue_uses_matched_query_when_expanded_record_lacks_anchor_fields(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "agent_audit.jsonl").write_text(
        json.dumps(
            {
                "source_version": "sv_bond_analytics",
                "report_date": "2026-05-31",
                "message": "refreshed fact_formal_bond_analytics_daily",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_gap_queue",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        sample = payload["items"][0]["expanded_anchor_samples"][0]
        assert sample["record_location"] == {
            "stream": "agent_audit",
            "line": 1,
            "matched_query": "fact_formal_bond_analytics_daily",
        }
        assert sample["anchor_type"] == "matched_query_anchor"
        assert sample["supporting_only"] is True
        assert sample["proves_page_execution"] is False
        assert sample["record_summary"] == {
            "matched_query": "fact_formal_bond_analytics_daily",
            "source_version": "sv_bond_analytics",
            "report_date": "2026-05-31",
        }
    finally:
        server.close()


def test_lineage_evidence_governance_gap_queue_surfaces_incomplete_direct_record_diagnostics(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "page_id": "PAGE-BOND-001",
                "page_slug": "bond-dashboard",
                "frontend_route": "/bond-dashboard",
                "primary_api": "/api/bond-dashboard/headline-kpis",
                "report_date": "2026-05-31",
                "basis": "analytical",
                "source_surface": "bond_analytics",
                "tables_used": ["fact_formal_bond_analytics_daily"],
                "source_version": "sv_bond_analytics",
                "created_at": "2026-06-04T12:05:00Z",
                "formal_use_allowed": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_gap_queue",
                "arguments": {"page_slugs": ["PAGE-BOND-001"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["summary"] == {
            "page_count": 1,
            "open_gap_count": 1,
            "missing_direct_record_count": 0,
            "ready_for_audit_review_count": 0,
            "incomplete_direct_record_page_count": 1,
            "missing_direct_and_expanded_record_count": 0,
            "missing_direct_record_expanded_only_count": 0,
        }
        item = payload["items"][0]
        assert item["gap_type"] == "direct_record_incomplete"
        assert item["direct_record_diagnostics"] == [
            {
                "record_location": {
                    "stream": "cache_manifest",
                    "line": 1,
                    "matched_query": "PAGE-BOND-001",
                },
                "validation_status": "incomplete",
                "missing_required_fields": ["rule_version"],
                "failed_required_field_groups": [
                    "execution_identifier",
                    "record_formal_use_allowed",
                ],
                "direct_anchor_match": {
                    "anchor_type": "page_id",
                    "matched_query": "PAGE-BOND-001",
                    "proves_primary_page_anchor": True,
                },
                "record_formal_use_allowed": True,
            }
        ]
        assert any(
            "Complete the existing direct PAGE-BOND-001/API governance record fields"
            in action
            for action in item["next_actions"]
        )
        assert item["evidence_scope"]["approves_metric_or_page"] is False
    finally:
        server.close()


def test_lineage_evidence_governance_gap_queue_can_cover_all_seeded_pages(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_governance_gap_queue",
                "arguments": {"all_seeded_pages": True, "max_results": 3},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-governance-gap-queue"
        assert payload["summary"]["page_count"] == 39
        assert payload["summary"]["open_gap_count"] == 39
        assert (
            payload["summary"]["missing_direct_record_count"]
            + payload["summary"]["incomplete_direct_record_page_count"]
            == 39
        )
        assert payload["summary"]["ready_for_audit_review_count"] == 0

        page_ids = {item["page_id"] for item in payload["items"]}
        assert {
            "PAGE-PROD-CAT-001",
            "PAGE-CUBE-QUERY-001",
            "PAGE-PORTFOLIO-HOME-001",
            "PAGE-EXEC-SUMMARY-001",
            "PAGE-AGENT-001",
            "GAP-BANK-LEDGER-DASHBOARD-PAGE",
            "GAP-CASHFLOW-PROJECTION-PAGE",
            "GAP-CONCENTRATION-MONITOR-PAGE",
            "GAP-PLATFORM-CONFIG-PAGE",
            "GAP-NEWS-EVENTS-PAGE",
            "GAP-DECISION-ITEMS-PAGE",
            "GAP-KPI-PERFORMANCE-PAGE",
        }.issubset(page_ids)
        assert "PAGE-PROD-CAT-PNL-001" not in page_ids
        assert len(page_ids) == 39

        assert all(item["gap_type"] == "missing_direct_and_expanded_records" for item in payload["items"])
        assert all(item["evidence_scope"]["writes_governance_records"] is False for item in payload["items"])
        assert all(item["evidence_scope"]["proves_page_execution"] is False for item in payload["items"])
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_agent_page_contract_to_agent_audit_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "agent_audit.jsonl").write_text(
        json.dumps(
            {
                "user_id": "agent_user",
                "query_text": "explain pnl",
                "tables_used": ["fact_formal_pnl_fi"],
                "result_meta": {
                    "result_kind": "agent.pnl_summary",
                    "formal_use_allowed": True,
                    "tables_used": ["fact_formal_pnl_fi"],
                },
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-AGENT-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-AGENT-001"
        assert "agent." in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "agent."
        assert found_payload["records"][0]["stream"] == "agent_audit"
        assert found_payload["records"][0]["record"]["result_meta"]["result_kind"] == "agent.pnl_summary"
        assert found_payload["records"][0]["record"]["result_meta"]["tables_used"] == ["fact_formal_pnl_fi"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_cube_query_page_to_allowed_source_tables(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "source_version": "sv_cube_pnl_fixture",
                "rule_version": "rv_cube_query_fixture",
                "tables_used": ["fact_formal_pnl_fi"],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-CUBE-QUERY-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-CUBE-QUERY-001"
        assert "/api/cube/query" in found_payload["expanded_queries"]
        assert "cube_query." in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "result_meta" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "fact_formal_pnl_fi"
        assert found_payload["records"][0]["stream"] == "source_manifest_latest"
        assert found_payload["records"][0]["record"]["tables_used"] == ["fact_formal_pnl_fi"]
    finally:
        server.close()


@pytest.mark.parametrize(
    ("page_id", "record", "required_anchors"),
    [
        (
            "PAGE-PORTFOLIO-HOME-001",
            {
                "result_kind": "bond_dashboard.headline_kpis",
                "primary_api": "/api/bond-dashboard/headline-kpis",
                "page_role": "module-home/portfolio",
                "tables_used": ["fact_formal_bond_analytics_daily"],
                "boundary": "module home no standalone MTR binding",
            },
            [
                "module-home/portfolio",
                "/api/bond-dashboard/headline-kpis",
                "bond_dashboard.headline_kpis",
                "fact_formal_bond_analytics_daily",
            ],
        ),
        (
            "PAGE-MARKET-HOME-001",
            {
                "result_kind": "market_data.rates",
                "primary_api": "/ui/market-data/rates",
                "page_role": "module-home/market",
                "tables_used": ["market_data_series_category"],
                "boundary": "module home observational market entry",
            },
            [
                "module-home/market",
                "/ui/market-data/rates",
                "market_data.rates",
                "market_data_series_category",
            ],
        ),
        (
            "PAGE-RISK-HOME-001",
            {
                "result_kind": "risk.tensor",
                "primary_api": "/api/risk/tensor",
                "page_role": "module-home/risk",
                "tables_used": ["fact_formal_risk_tensor_daily"],
                "boundary": "module home does not replace PAGE-RISK-001 formal risk truth",
            },
            [
                "module-home/risk",
                "/api/risk/tensor",
                "risk.tensor",
                "fact_formal_risk_tensor_daily",
            ],
        ),
        (
            "PAGE-PERFORMANCE-HOME-001",
            {
                "result_kind": "pnl.by_business_ytd",
                "primary_api": "/api/pnl/by-business-ytd",
                "page_role": "module-home/performance",
                "tables_used": ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"],
                "boundary": "module home does not rebuild KPI or team formulas",
            },
            [
                "module-home/performance",
                "/api/pnl/by-business-ytd",
                "pnl.by_business_ytd",
                "fact_formal_pnl_fi",
            ],
        ),
        (
            "PAGE-REPORTS-HOME-001",
            {
                "result_kind": "preview.source-foundation",
                "primary_api": "/ui/preview/source-foundation",
                "page_role": "module-home/governance",
                "tables_used": ["source_foundation"],
                "boundary": "module home diagnostics are not data-quality approval",
            },
            [
                "module-home/governance",
                "/ui/preview/source-foundation",
                "preview.source-foundation",
                "/api/cube/dimensions/bond_analytics",
            ],
        ),
    ],
)
def test_lineage_evidence_mcp_maps_module_home_pages_to_downstream_read_records(
    tmp_path: Path,
    page_id: str,
    record: dict[str, Any],
    required_anchors: list[str],
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(record) + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": page_id, "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == page_id
        for anchor in required_anchors:
            assert anchor in found_payload["expanded_queries"]
        assert not any(anchor.startswith("MTR-") for anchor in found_payload["expanded_queries"])
        if page_id == "PAGE-PORTFOLIO-HOME-001":
            assert "GS-PORTFOLIO-HOME-A" in found_payload["expanded_queries"]
            assert not any(
                anchor.startswith("GS-") and anchor != "GS-PORTFOLIO-HOME-A"
                for anchor in found_payload["expanded_queries"]
            )
        else:
            assert not any(anchor.startswith("GS-") for anchor in found_payload["expanded_queries"])
        assert found_payload["records"]
        assert found_payload["records"][0]["matched_query"] in required_anchors
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["result_kind"] == record["result_kind"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_business_pnl_page_to_page_level_read_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    record = {
        "result_kind": "pnl.by_business_ytd",
        "primary_api": "/api/pnl/by-business-ytd",
        "page_slug": "pnl-by-business",
        "tables_used": [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
        ],
        "boundary": "page-level analytical display no newly approved MTR binding",
    }
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(record) + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {
                "name": "find_lineage_records",
                "arguments": {"query": "PAGE-PNL-BY-BUSINESS-001", "max_results": 5},
            },
        )
        found_payload = json.loads(found["content"][0]["text"])

        required_anchors = [
            "pnl-by-business",
            "/api/pnl/by-business-ytd",
            "/api/pnl/by-business-monthly",
            "/api/pnl/by-business",
            "/api/pnl/by-business-analysis",
            "/api/adb/comparison",
            "pnl.by_business_ytd",
            "pnl.by_business_monthly",
            "pnl.by_business",
            "pnl.by_business_analysis",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
            "fact_pnl_by_business_precompute",
            "pnl_by_business_adjustments",
        ]
        excluded_anchors = [
            "product_category_pnl_formal_read_model",
            "qdb_general_ledger_workbook",
            "GS-PROD-CAT-PNL-A",
            "PAGE-PROD-CAT-PNL-001",
            "PAGE-LEDGER-PNL-001",
            "MTR-PCP-001",
            "MTR-LPN-001",
        ]

        assert found_payload["query"] == "PAGE-PNL-BY-BUSINESS-001"
        for anchor in required_anchors:
            assert anchor in found_payload["expanded_queries"]
        for anchor in excluded_anchors:
            assert anchor not in found_payload["expanded_queries"]
        assert not any(anchor.startswith("MTR-") for anchor in found_payload["expanded_queries"])
        assert not any(anchor.startswith("GS-") for anchor in found_payload["expanded_queries"])
        assert found_payload["records"][0]["matched_query"] == "/api/pnl/by-business-ytd"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["result_kind"] == "pnl.by_business_ytd"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_dashboard_home_page_to_mixed_snapshot_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "dashboard:home:snapshot",
            "result_kind": "home.snapshot",
            "source_surface": "executive_analytical",
            "basis": "analytical",
            "primary_api": "/ui/home/snapshot",
            "payload_schema": "HomeSnapshotPayload",
            "service": "home_snapshot_envelope",
            "domains_effective_date": {
                "balance": "2026-05-31",
                "pnl": "2026-05-31",
                "liability": "2026-05-31",
                "bond": "2026-05-31",
            },
            "domains_missing": [],
            "child_result_kinds": [
                "executive.overview",
                "executive.summary",
                "executive.pnl-attribution",
                "product_category_ytd",
                "product_category_monthly",
            ],
            "supplemental_result_kinds": [
                "dashboard.core_metrics",
                "dashboard.daily_changes",
                "bond_dashboard.headline_kpis",
                "bond_analytics.portfolio_headlines",
                "market_data.rates",
                "calendar.supply_auctions",
            ],
            "tables_used": [
                "fact_formal_zqtz_balance_daily",
                "fact_formal_tyw_balance_daily",
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
                "zqtz_bond_daily_snapshot",
                "tyw_interbank_daily_snapshot",
                "fact_formal_bond_analytics_daily",
                "product_category_pnl_formal_read_model",
                "product_category_pnl_canonical_fact",
                "fx_daily_mid",
            ],
        },
        {
            "cache_key": "dashboard:core-metrics",
            "result_kind": "dashboard.core_metrics",
            "source_surface": "dashboard_supplemental",
            "basis": "analytical",
            "role": "same_date_supplemental",
            "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
        },
        {
            "cache_key": "dashboard:bond-headline",
            "result_kind": "bond_dashboard.headline_kpis",
            "source_surface": "bond_analytics",
            "basis": "analytical",
            "role": "same_date_supplemental",
            "tables_used": ["fact_formal_bond_analytics_daily"],
        },
        {
            "cache_key": "executive:overview",
            "result_kind": "executive.overview",
            "page_id": "PAGE-EXEC-OVERVIEW-001",
            "golden_sample": "GS-EXEC-OVERVIEW-A",
        },
        {
            "cache_key": "bond_dashboard:headline",
            "result_kind": "bond_dashboard.headline_kpis",
            "page_id": "PAGE-BOND-001",
            "golden_sample": "GS-BOND-HEADLINE-A",
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-DASH-001", "max_results": 10}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-DASH-001"
        assert "/ui/home/snapshot" in found_payload["expanded_queries"]
        assert "home.snapshot" in found_payload["expanded_queries"]
        assert "dashboard-home" in found_payload["expanded_queries"]
        assert "HomeSnapshotPayload" in found_payload["expanded_queries"]
        assert "home_snapshot_envelope" in found_payload["expanded_queries"]
        assert "executive_analytical" in found_payload["expanded_queries"]
        assert "domains_effective_date" in found_payload["expanded_queries"]
        assert "domains_missing" in found_payload["expanded_queries"]
        assert "product_category_ytd" in found_payload["expanded_queries"]
        assert "product_category_monthly" in found_payload["expanded_queries"]
        assert "dashboard.core_metrics" in found_payload["expanded_queries"]
        assert "dashboard.daily_changes" in found_payload["expanded_queries"]
        assert "bond_dashboard.headline_kpis" in found_payload["expanded_queries"]
        assert "bond_analytics.portfolio_headlines" in found_payload["expanded_queries"]
        assert "market_data.rates" in found_payload["expanded_queries"]
        assert "calendar.supply_auctions" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_tyw_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" in found_payload["expanded_queries"]
        assert "fact_formal_bond_analytics_daily" in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" in found_payload["expanded_queries"]
        assert "fx_daily_mid" in found_payload["expanded_queries"]
        assert "PAGE-EXEC-OVERVIEW-001" not in found_payload["expanded_queries"]
        assert "GS-EXEC-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "PAGE-EXEC-PNL-ATTR-001" not in found_payload["expanded_queries"]
        assert "GS-EXEC-PNL-ATTR-A" not in found_payload["expanded_queries"]
        assert "PAGE-BOND-001" not in found_payload["expanded_queries"]
        assert "GS-BOND-HEADLINE-A" not in found_payload["expanded_queries"]
        assert "PAGE-PROD-CAT-PNL-001" not in found_payload["expanded_queries"]
        assert "GS-PROD-CAT-PNL-A" not in found_payload["expanded_queries"]
        assert "PAGE-MKT-001" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "/ui/home/snapshot"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["result_kind"] == "home.snapshot"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
        assert found_payload["records"][1]["matched_query"] == "dashboard.core_metrics"
        assert found_payload["records"][1]["record"]["role"] == "same_date_supplemental"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_executive_summary_page_to_narrative_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "executive:summary",
            "result_kind": "executive.summary",
            "source_surface": "executive_summary",
            "basis": "analytical",
            "primary_api": "/ui/home/summary",
            "payload_schema": "SummaryPayload",
            "golden_sample": "GS-EXEC-SUMMARY-A",
            "contract_scope": "narrative-only",
            "lineage_dependency": "executive.overview",
        },
        {
            "cache_key": "executive:summary:point-income",
            "result_kind": "executive.summary",
            "source_surface": "executive_summary",
            "basis": "analytical",
            "payload_schema": "SummaryPoint",
            "point_id": "income",
            "lineage_dependency": "executive.overview",
        },
        {
            "cache_key": "executive:overview",
            "result_kind": "executive.overview",
            "page_id": "PAGE-EXEC-OVERVIEW-001",
            "golden_sample": "GS-EXEC-OVERVIEW-A",
            "metric_ids": ["MTR-EXEC-001", "MTR-EXEC-002"],
        },
        {
            "cache_key": "executive:pnl-attribution",
            "result_kind": "executive.pnl-attribution",
            "page_id": "PAGE-EXEC-PNL-ATTR-001",
            "golden_sample": "GS-EXEC-PNL-ATTR-A",
            "metric_ids": ["MTR-EXEC-101"],
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {
                "name": "find_lineage_records",
                "arguments": {"query": "PAGE-EXEC-SUMMARY-001", "max_results": 10},
            },
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-EXEC-SUMMARY-001"
        assert "/ui/home/summary" in found_payload["expanded_queries"]
        assert "executive.summary" in found_payload["expanded_queries"]
        assert "executive-summary" in found_payload["expanded_queries"]
        assert "executive_summary" in found_payload["expanded_queries"]
        assert "SummaryPayload" in found_payload["expanded_queries"]
        assert "SummaryPoint" in found_payload["expanded_queries"]
        assert "GS-EXEC-SUMMARY-A" in found_payload["expanded_queries"]
        assert "narrative-only" in found_payload["expanded_queries"]
        assert "executive.overview" in found_payload["expanded_queries"]
        assert "PAGE-EXEC-OVERVIEW-001" not in found_payload["expanded_queries"]
        assert "GS-EXEC-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "MTR-EXEC-001" not in found_payload["expanded_queries"]
        assert "MTR-EXEC-101" not in found_payload["expanded_queries"]
        assert "PAGE-EXEC-PNL-ATTR-001" not in found_payload["expanded_queries"]
        assert "GS-EXEC-PNL-ATTR-A" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "/ui/home/summary"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["result_kind"] == "executive.summary"
        assert found_payload["records"][0]["record"]["contract_scope"] == "narrative-only"
        assert found_payload["records"][1]["matched_query"] == "executive.summary"
        assert found_payload["records"][1]["record"]["payload_schema"] == "SummaryPoint"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_macro_toolkit_page_to_tooling_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "macro-toolkit:analysis",
            "result_kind": "macro_toolkit.analysis",
            "source_surface": "macro_toolkit",
            "basis": "analytical",
            "primary_api": "/ui/macro/toolkit/analysis",
            "formal_use_allowed": False,
            "contract_scope": "candidate tooling surface",
            "coverage_hit_rate": 0.82,
            "source_version": "sv_macro_toolkit_analysis",
            "rule_version": "rv_macro_toolkit_analysis",
        },
        {
            "cache_key": "macro-toolkit:strategy-summaries",
            "result_kind": "macro_toolkit.analysis.strategy_summaries",
            "source_surface": "macro_toolkit",
            "basis": "analytical",
            "primary_api": "/ui/macro/toolkit/analysis/strategy-summaries",
            "formal_use_allowed": False,
            "strategy_count": 3,
        },
        {
            "cache_key": "macro-toolkit:scripts",
            "result_kind": "macro_toolkit.scripts",
            "source_surface": "macro_toolkit",
            "basis": "tooling",
            "primary_api": "/ui/macro/toolkit/scripts",
            "formal_use_allowed": False,
            "script_count": 4,
        },
        {
            "cache_key": "macro-toolkit:refresh",
            "result_kind": "macro_toolkit.choice_stock_refresh",
            "source_surface": "macro_toolkit",
            "basis": "operational",
            "primary_api": "/ui/macro/toolkit/choice-stock/refresh",
            "formal_use_allowed": False,
            "run_id": "macro-refresh-1",
        },
        {
            "metric_id": "MTR-MACRO-001",
            "result_kind": "formal.macro.metric",
            "basis": "formal",
            "formal_use_allowed": True,
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {
                "name": "find_lineage_records",
                "arguments": {"query": "PAGE-MACRO-TOOLKIT-001", "max_results": 10},
            },
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-MACRO-TOOLKIT-001"
        assert "/ui/macro/toolkit/analysis" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/analysis/strategy-summaries" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/scripts" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/scripts/" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/choice-stock/refresh-status" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/choice-stock/refresh" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/cffex-member-rank/refresh" in found_payload["expanded_queries"]
        assert "macro-toolkit" in found_payload["expanded_queries"]
        assert "macro_toolkit.analysis" in found_payload["expanded_queries"]
        assert "macro_toolkit.analysis.strategy_summaries" in found_payload["expanded_queries"]
        assert "macro_toolkit.scripts" in found_payload["expanded_queries"]
        assert "macro_toolkit.choice_stock_refresh" in found_payload["expanded_queries"]
        assert "macro_toolkit.cffex_member_rank_refresh" in found_payload["expanded_queries"]
        assert "MacroToolkitAnalysisPayload" in found_payload["expanded_queries"]
        assert "MacroToolkitPayload" in found_payload["expanded_queries"]
        assert "MacroToolkitRunResponse" in found_payload["expanded_queries"]
        assert "candidate tooling surface" in found_payload["expanded_queries"]
        assert "source/version/run_id" in found_payload["expanded_queries"]
        assert "MTR-MACRO-001" not in found_payload["expanded_queries"]
        assert "MTR-" not in found_payload["expanded_queries"]
        assert "GS-MACRO-TOOLKIT-A" not in found_payload["expanded_queries"]
        matched_records = {record["record"]["result_kind"]: record for record in found_payload["records"]}
        assert matched_records["macro_toolkit.analysis"]["matched_query"] == "/ui/macro/toolkit/analysis"
        assert matched_records["macro_toolkit.analysis"]["record"]["formal_use_allowed"] is False
        assert matched_records["macro_toolkit.analysis"]["record"]["contract_scope"] == "candidate tooling surface"
        assert (
            matched_records["macro_toolkit.analysis.strategy_summaries"]["record"]["primary_api"]
            == "/ui/macro/toolkit/analysis/strategy-summaries"
        )
        assert matched_records["macro_toolkit.scripts"]["record"]["primary_api"] == "/ui/macro/toolkit/scripts"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_macro_observation_page_to_readonly_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "macro-observation:analysis",
            "result_kind": "macro_toolkit.analysis",
            "source_surface": "macro_observation",
            "basis": "analytical",
            "primary_api": "/ui/macro/toolkit/analysis",
            "formal_use_allowed": False,
            "contract_scope": "read-only macro observation",
            "boundary": "macro-observation-readonly-boundary",
        },
        {
            "cache_key": "macro-observation:strategy-summaries",
            "result_kind": "macro_toolkit.analysis.strategy_summaries",
            "source_surface": "macro_observation",
            "basis": "analytical",
            "primary_api": "/ui/macro/toolkit/analysis/strategy-summaries",
            "formal_use_allowed": False,
            "contract_scope": "read-only macro observation",
        },
        {
            "cache_key": "macro-toolkit:scripts",
            "result_kind": "macro_toolkit.scripts",
            "source_surface": "macro_toolkit",
            "basis": "tooling",
            "primary_api": "/ui/macro/toolkit/scripts",
        },
        {
            "cache_key": "macro-toolkit:refresh",
            "result_kind": "macro_toolkit.choice_stock_refresh",
            "source_surface": "macro_toolkit",
            "basis": "operational",
            "primary_api": "/ui/macro/toolkit/choice-stock/refresh",
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {
                "name": "find_lineage_records",
                "arguments": {"query": "PAGE-MACRO-OBS-001", "max_results": 10},
            },
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-MACRO-OBS-001"
        assert "/ui/macro/toolkit/analysis" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/analysis/strategy-summaries" in found_payload["expanded_queries"]
        assert "macro-observation" in found_payload["expanded_queries"]
        assert "macro_observation" in found_payload["expanded_queries"]
        assert "macro_toolkit.analysis" in found_payload["expanded_queries"]
        assert "macro_toolkit.analysis.strategy_summaries" in found_payload["expanded_queries"]
        assert "MacroToolkitAnalysisPayload" in found_payload["expanded_queries"]
        assert "macro-observation-readonly-boundary" in found_payload["expanded_queries"]
        assert "read-only macro observation" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/scripts" not in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/scripts/" not in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/choice-stock/refresh" not in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/choice-stock/refresh-status" not in found_payload["expanded_queries"]
        assert "macro_toolkit.scripts" not in found_payload["expanded_queries"]
        assert "macro_toolkit.choice_stock_refresh" not in found_payload["expanded_queries"]
        assert "MTR-MACRO-001" not in found_payload["expanded_queries"]
        assert "MTR-" not in found_payload["expanded_queries"]
        matched_records = {record["record"]["result_kind"]: record for record in found_payload["records"]}
        assert matched_records["macro_toolkit.analysis"]["matched_query"] == "/ui/macro/toolkit/analysis"
        assert matched_records["macro_toolkit.analysis"]["record"]["contract_scope"] == "read-only macro observation"
        assert (
            matched_records["macro_toolkit.analysis.strategy_summaries"]["record"]["primary_api"]
            == "/ui/macro/toolkit/analysis/strategy-summaries"
        )
        assert matched_records["macro_toolkit.analysis.strategy_summaries"]["record"]["formal_use_allowed"] is False
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_executive_overview_page_to_overlay_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "executive:overview",
            "result_kind": "executive.overview",
            "source_surface": "executive_overview",
            "basis": "analytical",
            "golden_sample": "GS-EXEC-OVERVIEW-A",
            "metric_ids": [
                "MTR-EXEC-001",
                "MTR-EXEC-002",
                "MTR-EXEC-003",
                "MTR-EXEC-004",
                "MTR-EXEC-004A",
                "MTR-EXEC-004B",
                "MTR-EXEC-004C",
            ],
            "tables_used": [
                "fact_formal_zqtz_balance_daily",
                "fact_formal_tyw_balance_daily",
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
                "zqtz_bond_daily_snapshot",
                "tyw_interbank_daily_snapshot",
                "fact_formal_bond_analytics_daily",
            ],
        },
        {
            "cache_key": "executive:overview:aum",
            "result_kind": "executive.overview",
            "metric_id": "MTR-EXEC-001",
            "source_surface": "formal_balance",
            "basis": "analytical",
            "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
        },
        {
            "cache_key": "executive:overview:nim",
            "result_kind": "executive.overview",
            "metric_id": "MTR-EXEC-003",
            "source_surface": "liability_analytics.yield_metrics",
            "basis": "analytical",
            "tables_used": ["zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"],
        },
        {
            "cache_key": "balance:overview",
            "result_kind": "balance-analysis.overview",
            "page_id": "PAGE-BALANCE-001",
            "golden_sample": "GS-BAL-OVERVIEW-A",
        },
        {
            "cache_key": "pnl:overview",
            "result_kind": "pnl.overview",
            "page_id": "PAGE-PNL-001",
            "golden_sample": "GS-PNL-OVERVIEW-A",
        },
        {
            "cache_key": "risk:tensor",
            "result_kind": "risk.tensor",
            "page_id": "PAGE-RISK-001",
            "golden_sample": "GS-RISK-A",
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {
                "name": "find_lineage_records",
                "arguments": {"query": "PAGE-EXEC-OVERVIEW-001", "max_results": 10},
            },
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-EXEC-OVERVIEW-001"
        assert "/ui/home/overview" in found_payload["expanded_queries"]
        assert "executive.overview" in found_payload["expanded_queries"]
        assert "executive_overview" in found_payload["expanded_queries"]
        assert "OverviewPayload" in found_payload["expanded_queries"]
        assert "ExecutiveMetric" in found_payload["expanded_queries"]
        assert "ExecutiveMetric.caliber_label" in found_payload["expanded_queries"]
        assert "GS-EXEC-OVERVIEW-A" in found_payload["expanded_queries"]
        assert "MTR-EXEC-001" in found_payload["expanded_queries"]
        assert "MTR-EXEC-004C" in found_payload["expanded_queries"]
        assert "formal_balance" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_tyw_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" in found_payload["expanded_queries"]
        assert "liability_analytics.yield_metrics" in found_payload["expanded_queries"]
        assert "zqtz_bond_daily_snapshot" in found_payload["expanded_queries"]
        assert "tyw_interbank_daily_snapshot" in found_payload["expanded_queries"]
        assert "fact_formal_bond_analytics_daily" in found_payload["expanded_queries"]
        assert "PAGE-BALANCE-001" not in found_payload["expanded_queries"]
        assert "balance-analysis.overview" not in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "PAGE-PNL-001" not in found_payload["expanded_queries"]
        assert "pnl.overview" not in found_payload["expanded_queries"]
        assert "GS-PNL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "PAGE-RISK-001" not in found_payload["expanded_queries"]
        assert "risk.tensor" not in found_payload["expanded_queries"]
        assert "GS-RISK-A" not in found_payload["expanded_queries"]
        assert "executive.pnl-attribution" not in found_payload["expanded_queries"]
        assert "GS-EXEC-PNL-ATTR-A" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "executive.overview"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
        assert found_payload["records"][0]["record"]["golden_sample"] == "GS-EXEC-OVERVIEW-A"
        assert found_payload["records"][1]["matched_query"] == "executive.overview"
        assert found_payload["records"][1]["record"]["metric_id"] == "MTR-EXEC-001"
        assert found_payload["records"][1]["record"]["source_surface"] == "formal_balance"
        assert found_payload["records"][2]["matched_query"] == "executive.overview"
        assert found_payload["records"][2]["record"]["metric_id"] == "MTR-EXEC-003"
        assert found_payload["records"][2]["record"]["source_surface"] == "liability_analytics.yield_metrics"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_formal_pnl_page_to_formal_fact_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "source_version": "fi-shared-v1__nonstd-shared-v1",
                "rule_version": "rv_pnl_phase2_materialize_v1",
                "cache_version": "cv_pnl_formal__rv_pnl_phase2_materialize_v1",
                "tables_used": ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"],
                "golden_samples": ["GS-PNL-OVERVIEW-A", "GS-PNL-DATA-A"],
                "result_kind": "pnl.overview",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-PNL-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-PNL-001"
        assert "/api/pnl/overview" in found_payload["expanded_queries"]
        assert "/api/pnl/data" in found_payload["expanded_queries"]
        assert "pnl.overview" in found_payload["expanded_queries"]
        assert "pnl.data" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" in found_payload["expanded_queries"]
        assert "GS-PNL-OVERVIEW-A" in found_payload["expanded_queries"]
        assert "GS-PNL-DATA-A" in found_payload["expanded_queries"]
        assert "MTR-PNL-001" in found_payload["expanded_queries"]
        assert "MTR-PNL-104" in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "pnl.overview"
        assert found_payload["records"][0]["stream"] == "source_manifest_latest"
        assert found_payload["records"][0]["record"]["tables_used"] == [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
        ]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_pnl_bridge_page_to_bridge_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_key": "pnl:bridge:formal",
                "result_kind": "pnl.bridge",
                "source_surface": "pnl_bridge",
                "fact_tables": ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"],
                "golden_samples": ["GS-BRIDGE-A", "GS-BRIDGE-WARN-B"],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-BRIDGE-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-BRIDGE-001"
        assert "/api/pnl/bridge" in found_payload["expanded_queries"]
        assert "pnl.bridge" in found_payload["expanded_queries"]
        assert "pnl_bridge" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" in found_payload["expanded_queries"]
        assert "GS-BRIDGE-A" in found_payload["expanded_queries"]
        assert "GS-BRIDGE-WARN-B" in found_payload["expanded_queries"]
        assert "MTR-BRG-001" in found_payload["expanded_queries"]
        assert "MTR-BRG-105" in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "pnl.bridge"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["result_kind"] == "pnl.bridge"
        assert found_payload["records"][0]["record"]["source_surface"] == "pnl_bridge"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_balance_analysis_page_to_formal_balance_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "source_version": "sv_balance_fixture",
                "rule_version": "rv_balance_materialize_fixture",
                "result_kind": "balance-analysis.overview",
                "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
                "golden_samples": ["GS-BAL-OVERVIEW-A", "GS-BAL-WORKBOOK-A"],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-BALANCE-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-BALANCE-001"
        assert "/ui/balance-analysis/overview" in found_payload["expanded_queries"]
        assert "/ui/balance-analysis/workbook" in found_payload["expanded_queries"]
        assert "balance-analysis.overview" in found_payload["expanded_queries"]
        assert "balance-analysis.workbook" in found_payload["expanded_queries"]
        assert "balance_analysis" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_tyw_balance_daily" in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" in found_payload["expanded_queries"]
        assert "GS-BAL-WORKBOOK-A" in found_payload["expanded_queries"]
        assert "MTR-BAL-001" in found_payload["expanded_queries"]
        assert "MTR-BAL-203" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "balance-analysis.overview"
        assert found_payload["records"][0]["stream"] == "source_manifest_latest"
        assert found_payload["records"][0]["record"]["tables_used"] == [
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
        ]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_pnl_attribution_workbench_to_formal_attribution_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "source_version": "sv_pnl_attribution_fixture",
                "rule_version": "rv_pnl_attribution_workbench_v1",
                "cache_version": "cv_pnl_attribution_workbench_v1",
                "result_kind": "pnl_attribution.volume_rate",
                "tables_used": [
                    "fact_formal_pnl_fi",
                    "fact_nonstd_pnl_bridge",
                    "fact_formal_zqtz_balance_daily",
                ],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-PNL-ATTR-WB-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-PNL-ATTR-WB-001"
        assert "/api/pnl-attribution/volume-rate" in found_payload["expanded_queries"]
        assert "/api/pnl-attribution/tpl-market" in found_payload["expanded_queries"]
        assert "/api/pnl-attribution/composition" in found_payload["expanded_queries"]
        assert "/api/pnl-attribution/advanced/summary" in found_payload["expanded_queries"]
        assert "/api/pnl-attribution/campisi/four-effects" in found_payload["expanded_queries"]
        assert "pnl_attribution.volume_rate" in found_payload["expanded_queries"]
        assert "pnl_attribution.advanced_summary" in found_payload["expanded_queries"]
        assert "VolumeRateAttributionPayload" in found_payload["expanded_queries"]
        assert "AdvancedAttributionSummary" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_bond_analytics_daily" in found_payload["expanded_queries"]
        assert "yield_curve_daily" in found_payload["expanded_queries"]
        assert "MTR-PAT-001" in found_payload["expanded_queries"]
        assert "MTR-PAT-304" in found_payload["expanded_queries"]
        assert "executive.pnl-attribution" not in found_payload["expanded_queries"]
        assert "GS-EXEC-PNL-ATTR-A" not in found_payload["expanded_queries"]
        assert "MTR-EXEC-101" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "pnl_attribution.volume_rate"
        assert found_payload["records"][0]["stream"] == "source_manifest_latest"
        assert found_payload["records"][0]["record"]["tables_used"] == [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
        ]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_balance_movement_page_to_movement_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_key": "accounting_asset_movement.monthly",
                "cache_version": "cv_accounting_asset_movement_v1",
                "result_kind_family": "balance-analysis.movement",
                "module_name": "accounting_asset_movement",
                "rule_version": "rv_accounting_asset_movement_v2",
                "fact_tables": ["fact_accounting_asset_movement_monthly"],
                "input_sources": ["fact_formal_zqtz_balance_daily"],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-BAL-MOVE-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-BAL-MOVE-001"
        assert "/ui/balance-movement-analysis" in found_payload["expanded_queries"]
        assert "/ui/balance-movement-analysis/dates" in found_payload["expanded_queries"]
        assert "balance-analysis.movement.detail" in found_payload["expanded_queries"]
        assert "balance-analysis.movement.dates" in found_payload["expanded_queries"]
        assert "accounting_asset_movement" in found_payload["expanded_queries"]
        assert "fact_accounting_asset_movement_monthly" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "rv_accounting_asset_movement_v2" in found_payload["expanded_queries"]
        assert "AccountingAssetMovementPayload" in found_payload["expanded_queries"]
        assert "MTR-BMV-001" in found_payload["expanded_queries"]
        assert "MTR-BMV-004" in found_payload["expanded_queries"]
        assert "MTR-BAL-001" not in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "balance-analysis.movement"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["fact_tables"] == ["fact_accounting_asset_movement_monthly"]
        assert found_payload["records"][0]["record"]["input_sources"] == ["fact_formal_zqtz_balance_daily"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_liability_analytics_page_to_mixed_source_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_key": "liability_analytics:compat:daily",
                "result_kind": "liability_analytics.risk_buckets",
                "source_surface": "formal_liability",
                "basis": "analytical",
                "source_tables": [
                    "fact_formal_zqtz_balance_daily",
                    "fact_formal_tyw_balance_daily",
                    "zqtz_bond_daily_snapshot",
                    "tyw_interbank_daily_snapshot",
                ],
                "rule_version": "rv_liability_analytics_compat_v1",
                "cache_version": "cv_liability_analytics_v1",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-LIAB-ANALYTICS-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-LIAB-ANALYTICS-001"
        assert "/api/risk/buckets" in found_payload["expanded_queries"]
        assert "/api/analysis/yield_metrics" in found_payload["expanded_queries"]
        assert "/api/analysis/yield-by-period" in found_payload["expanded_queries"]
        assert "/api/analysis/liabilities/counterparty" in found_payload["expanded_queries"]
        assert "/api/liabilities/monthly" in found_payload["expanded_queries"]
        assert "/api/analysis/liabilities/cockpit-warnings" in found_payload["expanded_queries"]
        assert "/api/analysis/liabilities/contribution-split" in found_payload["expanded_queries"]
        assert "liability_analytics.risk_buckets" in found_payload["expanded_queries"]
        assert "liability_analytics.yield_metrics" in found_payload["expanded_queries"]
        assert "liability_analytics.yield_by_period" in found_payload["expanded_queries"]
        assert "liability_analytics.counterparty" in found_payload["expanded_queries"]
        assert "liability_analytics.monthly" in found_payload["expanded_queries"]
        assert "formal_liability" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_tyw_balance_daily" in found_payload["expanded_queries"]
        assert "zqtz_bond_daily_snapshot" in found_payload["expanded_queries"]
        assert "tyw_interbank_daily_snapshot" in found_payload["expanded_queries"]
        assert "MTR-LIAB-001" in found_payload["expanded_queries"]
        assert "MTR-LIAB-007" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "GS-EXEC-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "liability_analytics.risk_buckets"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["source_surface"] == "formal_liability"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_bond_dashboard_page_to_candidate_bond_analytics_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_key": "bond_dashboard:headline",
                "result_kind": "bond_dashboard.headline_kpis",
                "source_surface": "bond_analytics",
                "basis": "analytical",
                "tables_used": ["fact_formal_bond_analytics_daily"],
                "golden_sample": "GS-BOND-HEADLINE-A",
                "rule_version": "rv_bond_analytics_formal_materialize_v1",
                "cache_version": "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v1",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-BOND-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-BOND-001"
        assert "/api/bond-dashboard/headline-kpis" in found_payload["expanded_queries"]
        assert "/api/bond-dashboard/risk-indicators" in found_payload["expanded_queries"]
        assert "/api/bond-dashboard/business-type-metrics" in found_payload["expanded_queries"]
        assert "bond_dashboard.headline_kpis" in found_payload["expanded_queries"]
        assert "bond_dashboard.risk_indicators" in found_payload["expanded_queries"]
        assert "bond_dashboard.business_type_metrics" in found_payload["expanded_queries"]
        assert "bond_analytics" in found_payload["expanded_queries"]
        assert "fact_formal_bond_analytics_daily" in found_payload["expanded_queries"]
        assert "GS-BOND-HEADLINE-A" in found_payload["expanded_queries"]
        assert "MTR-BOND-001" in found_payload["expanded_queries"]
        assert "MTR-BOND-004" in found_payload["expanded_queries"]
        assert "MTR-BAL-001" not in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "PAGE-RISK-001" not in found_payload["expanded_queries"]
        assert "GS-RISK-A" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "bond_dashboard.headline_kpis"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
        assert found_payload["records"][0]["record"]["source_surface"] == "bond_analytics"
        assert found_payload["records"][0]["record"]["tables_used"] == ["fact_formal_bond_analytics_daily"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_positions_page_to_candidate_snapshot_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_key": "positions:bonds:list",
                "result_kind": "positions.bonds.list",
                "source_surface": "positions_snapshot",
                "basis": "analytical",
                "formal_use_allowed": False,
                "quality_flag": "warning",
                "date_basis": "positions_snapshot_report_date",
                "tables_used": ["zqtz_bond_daily_snapshot"],
                "rule_version": "rv_positions_snapshot_read_v1",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n"
        + json.dumps(
            {
                "cache_key": "positions:interbank:list",
                "result_kind": "positions.interbank.list",
                "source_surface": "positions_snapshot",
                "basis": "analytical",
                "formal_use_allowed": False,
                "quality_flag": "warning",
                "date_basis": "positions_snapshot_report_date",
                "tables_used": ["tyw_interbank_daily_snapshot"],
                "rule_version": "rv_positions_snapshot_read_v1",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-POS-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-POS-001"
        assert "/api/positions/bonds" in found_payload["expanded_queries"]
        assert "/api/positions/interbank" in found_payload["expanded_queries"]
        assert "/api/positions/bonds/sub_types" in found_payload["expanded_queries"]
        assert "/api/positions/interbank/product_types" in found_payload["expanded_queries"]
        assert "/api/positions/counterparty/bonds" in found_payload["expanded_queries"]
        assert "/api/positions/counterparty/interbank/split" in found_payload["expanded_queries"]
        assert "/api/positions/stats/rating" in found_payload["expanded_queries"]
        assert "/api/positions/stats/industry" in found_payload["expanded_queries"]
        assert "/api/positions/customer/details" in found_payload["expanded_queries"]
        assert "/api/positions/customer/trend" in found_payload["expanded_queries"]
        assert "positions.bonds.list" in found_payload["expanded_queries"]
        assert "positions.interbank.list" in found_payload["expanded_queries"]
        assert "positions.counterparty.bonds" in found_payload["expanded_queries"]
        assert "positions.counterparty.interbank.split" in found_payload["expanded_queries"]
        assert "positions.stats.rating" in found_payload["expanded_queries"]
        assert "positions.stats.industry" in found_payload["expanded_queries"]
        assert "positions.customer.details" in found_payload["expanded_queries"]
        assert "positions.customer.trend" in found_payload["expanded_queries"]
        assert "positions_snapshot" in found_payload["expanded_queries"]
        assert "zqtz_bond_daily_snapshot" in found_payload["expanded_queries"]
        assert "tyw_interbank_daily_snapshot" in found_payload["expanded_queries"]
        assert "MTR-POS-001" in found_payload["expanded_queries"]
        assert "MTR-POS-002" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
        assert "bond_dashboard.headline_kpis" not in found_payload["expanded_queries"]
        assert "fact_formal_bond_analytics_daily" not in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "MTR-BAL-001" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "positions.bonds.list"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
        assert found_payload["records"][0]["record"]["formal_use_allowed"] is False
        assert found_payload["records"][0]["record"]["quality_flag"] == "warning"
        assert found_payload["records"][0]["record"]["tables_used"] == ["zqtz_bond_daily_snapshot"]
        assert found_payload["records"][1]["matched_query"] == "positions.interbank.list"
        assert found_payload["records"][1]["record"]["tables_used"] == ["tyw_interbank_daily_snapshot"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_market_data_page_to_mixed_source_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "market_data:preview:macro_foundation",
            "result_kind": "preview.macro-foundation",
            "source_surface": "macro_preview",
            "basis": "analytical",
            "tables_used": ["fact_choice_macro_daily", "market_data_series_category"],
            "rule_version": "rv_phase1_macro_vendor_v1",
        },
        {
            "cache_key": "market_data:rates:formal_fragment",
            "result_kind": "market_data.rates",
            "source_surface": "market_data",
            "basis": "formal",
            "formal_use_allowed": True,
            "tables_used": ["fact_choice_macro_daily", "market_data_series_category"],
            "rule_version": "rv_market_data_rates_formal_v1",
        },
        {
            "cache_key": "market_data:fx:formal_status",
            "result_kind": "fx.formal.status",
            "source_surface": "formal_fx_status",
            "basis": "formal",
            "tables_used": ["fx_daily_mid"],
            "rule_version": "rv_fx_formal_mid_v1",
        },
        {
            "cache_key": "market_data:fx:analytical",
            "result_kind": "fx.analytical.groups",
            "source_surface": "fx_analytical",
            "basis": "analytical",
            "tables_used": ["fact_choice_macro_daily", "fx_daily_mid"],
            "rule_version": "rv_fx_analytical_v1",
        },
        {
            "cache_key": "market_data:ncd:proxy",
            "result_kind": "market_data.ncd_proxy",
            "source_surface": "ncd_funding_proxy",
            "basis": "analytical",
            "is_actual_ncd_matrix": False,
            "tables_used": ["fact_choice_macro_daily"],
            "rule_version": "rv_ncd_proxy_v1",
        },
        {
            "cache_key": "market_data:livermore:strategy",
            "result_kind": "market_data.livermore",
            "source_surface": "livermore_analytical",
            "basis": "analytical",
            "tables_used": [
                "fact_choice_macro_daily",
                "livermore_position_snapshot",
                "choice_stock_daily_observation",
                "fact_livermore_gate_supplement_daily",
            ],
            "rule_version": "rv_livermore_strategy_v1",
        },
        {
            "cache_key": "market_data:macro_bond_linkage",
            "result_kind": "macro_bond_linkage.analysis",
            "source_surface": "macro_bond_linkage",
            "basis": "analytical",
            "tables_used": ["fact_choice_macro_daily", "yield_curve_daily"],
            "rule_version": "rv_macro_bond_linkage_v1",
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-MKT-001", "max_results": 10}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-MKT-001"
        assert "/ui/preview/macro-foundation" in found_payload["expanded_queries"]
        assert "/ui/market-data/rates" in found_payload["expanded_queries"]
        assert "/ui/market-data/fx/formal-status" in found_payload["expanded_queries"]
        assert "/ui/market-data/fx/analytical" in found_payload["expanded_queries"]
        assert "/ui/market-data/ncd-funding-proxy" in found_payload["expanded_queries"]
        assert "/api/macro-bond-linkage" in found_payload["expanded_queries"]
        assert "/ui/market-data/livermore" in found_payload["expanded_queries"]
        assert "preview.macro-foundation" in found_payload["expanded_queries"]
        assert "market_data.rates" in found_payload["expanded_queries"]
        assert "market_data.catalog" in found_payload["expanded_queries"]
        assert "macro.choice.latest" in found_payload["expanded_queries"]
        assert "fx.formal.status" in found_payload["expanded_queries"]
        assert "fx.analytical.groups" in found_payload["expanded_queries"]
        assert "market_data.ncd_proxy" in found_payload["expanded_queries"]
        assert "market_data.livermore" in found_payload["expanded_queries"]
        assert "macro_bond_linkage.analysis" in found_payload["expanded_queries"]
        assert "fact_choice_macro_daily" in found_payload["expanded_queries"]
        assert "market_data_series_category" in found_payload["expanded_queries"]
        assert "fx_daily_mid" in found_payload["expanded_queries"]
        assert "livermore_position_snapshot" in found_payload["expanded_queries"]
        assert "choice_stock_daily_observation" in found_payload["expanded_queries"]
        assert "fact_livermore_gate_supplement_daily" in found_payload["expanded_queries"]
        assert "MTR-MKT-001" in found_payload["expanded_queries"]
        assert "GAP-MKT-DATA" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" not in found_payload["expanded_queries"]
        assert "positions.bonds.list" not in found_payload["expanded_queries"]
        assert "bond_dashboard.headline_kpis" not in found_payload["expanded_queries"]
        assert "GS-BOND-HEADLINE-A" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "preview.macro-foundation"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
        assert found_payload["records"][1]["matched_query"] == "market_data.rates"
        assert found_payload["records"][1]["record"]["basis"] == "formal"
        assert found_payload["records"][2]["matched_query"] == "fx.formal.status"
        assert found_payload["records"][3]["matched_query"] == "fx.analytical.groups"
        assert found_payload["records"][4]["matched_query"] == "market_data.ncd_proxy"
        assert found_payload["records"][4]["record"]["is_actual_ncd_matrix"] is False
        assert found_payload["records"][5]["matched_query"] == "market_data.livermore"
        assert "livermore_position_snapshot" in found_payload["records"][5]["record"]["tables_used"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_stock_analysis_gap_to_observational_livermore_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "livermore:strategy",
            "result_kind": "market_data.livermore",
            "source_surface": "livermore_observation",
            "basis": "analytical",
            "formal_use_allowed": False,
            "tables_used": [
                "fact_choice_macro_daily",
                "livermore_position_snapshot",
                "choice_stock_daily_observation",
                "fact_livermore_gate_supplement_daily",
            ],
            "rule_version": "rv_livermore_strategy_v1",
        },
        {
            "cache_key": "livermore:strategy-score",
            "result_kind": "market_data.livermore.strategy_score",
            "source_surface": "livermore_candidate_history",
            "basis": "analytical",
            "formal_use_allowed": False,
            "tables_used": ["livermore_candidate_history"],
            "rule_version": "rv_livermore_strategy_score_v1",
        },
        {
            "cache_key": "livermore:strategy-optimization",
            "result_kind": "market_data.livermore.strategy_optimization",
            "source_surface": "livermore_candidate_history",
            "basis": "analytical",
            "formal_use_allowed": False,
            "tables_used": ["livermore_candidate_history"],
            "rule_version": "rv_livermore_strategy_optimization_v1",
        },
        {
            "cache_key": "livermore:cycle-proxy-backtest",
            "result_kind": "market_data.livermore.cycle_proxy_backtest",
            "source_surface": "livermore_candidate_history",
            "basis": "analytical",
            "formal_use_allowed": False,
            "full_strategy_status": "blocked_missing_inputs",
            "tables_used": ["livermore_candidate_history", "choice_stock_daily_observation"],
            "rule_version": "rv_livermore_cycle_proxy_backtest_v1",
        },
        {
            "cache_key": "livermore:signal-confluence",
            "result_kind": "market_data.livermore.signal_confluence",
            "source_surface": "livermore_observation",
            "basis": "analytical",
            "formal_use_allowed": False,
            "tables_used": ["choice_stock_daily_observation", "fact_livermore_gate_supplement_daily"],
            "rule_version": "rv_livermore_signal_confluence_v1",
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for query in ("GAP-STOCK-ANALYSIS-PAGE", "stock-analysis", "/stock-analysis"):
            found = server.request(
                "tools/call",
                {"name": "find_lineage_records", "arguments": {"query": query, "max_results": 10}},
            )
            found_payload = json.loads(found["content"][0]["text"])

            assert found_payload["query"] == query
            assert "GAP-STOCK-ANALYSIS-PAGE" in found_payload["expanded_queries"]
            assert "/ui/market-data/livermore" in found_payload["expanded_queries"]
            assert "/ui/market-data/livermore/strategy-score" in found_payload["expanded_queries"]
            assert "/ui/market-data/livermore/strategy-optimization" in found_payload["expanded_queries"]
            assert "/ui/market-data/livermore/cycle-proxy-backtest" in found_payload["expanded_queries"]
            assert "/ui/market-data/livermore/candidate-history-portfolio-backtest" in found_payload["expanded_queries"]
            assert "/ui/market-data/livermore/signal-confluence" in found_payload["expanded_queries"]
            assert "market_data.livermore" in found_payload["expanded_queries"]
            assert "market_data.livermore.strategy_score" in found_payload["expanded_queries"]
            assert "market_data.livermore.strategy_optimization" in found_payload["expanded_queries"]
            assert "market_data.livermore.cycle_proxy_backtest" in found_payload["expanded_queries"]
            assert "market_data.livermore.signal_confluence" in found_payload["expanded_queries"]
            assert "livermore_position_snapshot" in found_payload["expanded_queries"]
            assert "choice_stock_daily_observation" in found_payload["expanded_queries"]
            assert "fact_livermore_gate_supplement_daily" in found_payload["expanded_queries"]
            assert "MTR-MKT-001" not in found_payload["expanded_queries"]
            assert "MTR-STOCK-001" not in found_payload["expanded_queries"]
            assert "PAGE-STOCK-ANALYSIS-001" not in found_payload["expanded_queries"]
            assert "GS-PNL-OVERVIEW-A" not in found_payload["expanded_queries"]
            assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
            assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
            assert "bond_dashboard.headline_kpis" not in found_payload["expanded_queries"]
            result_kinds = {item["record"].get("result_kind") for item in found_payload["records"]}
            assert "market_data.livermore" in result_kinds
            assert "market_data.livermore.strategy_score" in result_kinds
            assert "market_data.livermore.strategy_optimization" in result_kinds
            assert "market_data.livermore.cycle_proxy_backtest" in result_kinds
            assert "market_data.livermore.signal_confluence" in result_kinds
            assert any(item["record"].get("formal_use_allowed") is False for item in found_payload["records"])
            assert any(
                item["record"].get("full_strategy_status") == "blocked_missing_inputs"
                for item in found_payload["records"]
            )
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_operations_page_to_mixed_source_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "operations:product-category-headline",
            "result_kind": "product_category_pnl.detail",
            "source_surface": "product_category_pnl",
            "basis": "formal",
            "tables_used": [
                "product_category_pnl_formal_read_model",
                "product_category_pnl_canonical_fact",
            ],
            "golden_sample": "GS-PROD-CAT-PNL-A",
            "metric_ids": ["MTR-PCP-001", "MTR-PCP-002", "MTR-PCP-003"],
        },
        {
            "cache_key": "operations:balance-overview-supplemental",
            "result_kind": "balance-analysis.overview",
            "source_surface": "formal_balance",
            "basis": "formal",
            "role": "supplemental_topic_entry",
            "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
            "golden_sample": "GS-BAL-OVERVIEW-A",
        },
        {
            "cache_key": "operations:source-preview",
            "result_kind": "preview.source-foundation",
            "source_surface": "source_preview",
            "basis": "preview",
            "tables_used": ["source_preview_manifest"],
        },
        {
            "cache_key": "operations:macro-preview",
            "result_kind": "preview.macro-foundation",
            "source_surface": "macro_preview",
            "basis": "analytical",
            "tables_used": ["fact_choice_macro_daily"],
        },
        {
            "cache_key": "operations:fx-status",
            "result_kind": "fx.formal.status",
            "source_surface": "formal_fx_status",
            "basis": "formal",
            "tables_used": ["fx_daily_mid"],
        },
        {
            "cache_key": "operations:choice-news",
            "result_kind": "news.choice.latest",
            "source_surface": "choice_news",
            "basis": "analytical",
            "tables_used": ["choice_news_event"],
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-OPS-001", "max_results": 10}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-OPS-001"
        assert "/ui/pnl/product-category" in found_payload["expanded_queries"]
        assert "/ui/pnl/product-category/dates" in found_payload["expanded_queries"]
        assert "/ui/balance-analysis/overview" in found_payload["expanded_queries"]
        assert "/ui/preview/source-foundation" in found_payload["expanded_queries"]
        assert "/ui/preview/macro-foundation" in found_payload["expanded_queries"]
        assert "/ui/macro/choice-series/latest" in found_payload["expanded_queries"]
        assert "/ui/market-data/fx/formal-status" in found_payload["expanded_queries"]
        assert "/ui/news/choice-events/latest" in found_payload["expanded_queries"]
        assert "product_category_pnl.detail" in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" in found_payload["expanded_queries"]
        assert "product_category_pnl_canonical_fact" in found_payload["expanded_queries"]
        assert "GS-PROD-CAT-PNL-A" in found_payload["expanded_queries"]
        assert "MTR-PCP-001" in found_payload["expanded_queries"]
        assert "MTR-PCP-003" in found_payload["expanded_queries"]
        assert "balance-analysis.overview" in found_payload["expanded_queries"]
        assert "formal_balance" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_tyw_balance_daily" in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" in found_payload["expanded_queries"]
        assert "MTR-BAL-001" in found_payload["expanded_queries"]
        assert "MTR-BAL-102" in found_payload["expanded_queries"]
        assert "preview.source-foundation" in found_payload["expanded_queries"]
        assert "preview.macro-foundation" in found_payload["expanded_queries"]
        assert "macro.choice.latest" in found_payload["expanded_queries"]
        assert "fx.formal.status" in found_payload["expanded_queries"]
        assert "news.choice.latest" in found_payload["expanded_queries"]
        assert "choice_news_event" in found_payload["expanded_queries"]
        assert "GAP-OPS-MACRO-FX" in found_payload["expanded_queries"]
        assert "MTR-OPS-001" not in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "balance-analysis.workbook" not in found_payload["expanded_queries"]
        assert "GS-BAL-WORKBOOK-A" not in found_payload["expanded_queries"]
        assert "bond_dashboard.headline_kpis" not in found_payload["expanded_queries"]
        assert "positions.bonds.list" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "product_category_pnl.detail"
        assert found_payload["records"][0]["record"]["basis"] == "formal"
        assert found_payload["records"][1]["matched_query"] == "balance-analysis.overview"
        assert found_payload["records"][1]["record"]["role"] == "supplemental_topic_entry"
        assert found_payload["records"][2]["matched_query"] == "preview.source-foundation"
        assert found_payload["records"][3]["matched_query"] == "preview.macro-foundation"
        assert found_payload["records"][4]["matched_query"] == "fx.formal.status"
        assert found_payload["records"][5]["matched_query"] == "news.choice.latest"
    finally:
        server.close()


def test_lineage_evidence_mcp_validates_pnl_attribution_workbench_direct_record(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    record = {
        "page_id": "PAGE-PNL-ATTR-WB-001",
        "page_slug": "pnl-attribution",
        "frontend_route": "/pnl-attribution",
        "primary_api": "/api/pnl-attribution/volume-rate",
        "report_date": "2026-04-30",
        "basis": "formal",
        "source_surface": "formal_attribution",
        "tables_used": [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
        ],
        "source_version": "sv_pnl_by_business_gs_attr_wb",
        "rule_version": "rv_pnl_attribution_workbench_v1",
        "cache_version": "cv_pnl_attribution_workbench_v1",
        "cache_key": "pnl-attribution:volume-rate:2026-04-30:mom",
        "result_kind": "pnl_attribution.volume_rate",
        "golden_sample_id": "GS-PNL-ATTR-WB-A",
        "created_at": "2026-06-05T00:00:00Z",
        "formal_use_allowed": False,
    }
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(record, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "validate_page_governance_records",
                "arguments": {"page_slugs": ["pnl-attribution"], "max_results": 10},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-PNL-ATTR-WB-001"
        assert page["approval_status"] == "candidate_or_pending"
        assert page["record_formal_use_policy"] == "must_be_false_until_candidate_closure"
        assert page["validation_status"] == "direct_records_ready_for_audit_review"
        assert page["direct_record_validations"][0]["validation_status"] == "ready_for_audit_review"
        assert page["direct_record_validations"][0]["record_formal_use_allowed"] is False
        assert page["direct_record_validations"][0]["direct_anchor_match"] == {
            "anchor_type": "page_id",
            "matched_query": "PAGE-PNL-ATTR-WB-001",
            "proves_primary_page_anchor": True,
        }
        assert page["evidence_scope"]["approves_metric_or_page"] is False
        assert page["evidence_scope"]["proves_page_execution"] is False
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_ledger_pnl_page_to_ledger_source_contracts(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "source_version": "sv_ledger_pnl_fixture",
                "rule_version": "rv_ledger_pnl_fixture",
                "tables_used": ["qdb_general_ledger_workbook"],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-LEDGER-PNL-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-LEDGER-PNL-001"
        assert "/api/ledger-pnl/summary" in found_payload["expanded_queries"]
        assert "ledger_pnl." in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" in found_payload["expanded_queries"]
        assert "formal_financial_indicator_source_contract" in found_payload["expanded_queries"]
        assert "GS-LEDGER-PNL-FIN-IND-202603-B" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "qdb_general_ledger_workbook"
        assert found_payload["records"][0]["stream"] == "source_manifest_latest"
        assert found_payload["records"][0]["record"]["tables_used"] == ["qdb_general_ledger_workbook"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_product_category_page_aliases_to_formal_model_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_version": "cv_product_category_fixture",
                "table_name": "product_category_pnl_formal_read_model",
                "source_tables": ["product_category_pnl_canonical_fact"],
                "golden_sample": "GS-PROD-CAT-PNL-A",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for page_id in ("PAGE-PROD-CAT-PNL-001", "PAGE-PROD-CAT-001"):
            found = server.request(
                "tools/call",
                {"name": "find_lineage_records", "arguments": {"query": page_id, "max_results": 5}},
            )
            found_payload = json.loads(found["content"][0]["text"])

            assert found_payload["query"] == page_id
            assert "product-category-pnl" in found_payload["expanded_queries"]
            assert "/ui/pnl/product-category" in found_payload["expanded_queries"]
            assert "product_category_pnl.detail" in found_payload["expanded_queries"]
            assert "product_category_pnl_formal_read_model" in found_payload["expanded_queries"]
            assert "product_category_pnl_canonical_fact" in found_payload["expanded_queries"]
            assert "GS-PROD-CAT-PNL-A" in found_payload["expanded_queries"]
            assert "MTR-PCP-001" in found_payload["expanded_queries"]
            assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
            assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
            assert found_payload["records"][0]["matched_query"] == "product_category_pnl_formal_read_model"
            assert found_payload["records"][0]["stream"] == "cache_manifest"
            assert found_payload["records"][0]["record"]["table_name"] == "product_category_pnl_formal_read_model"
            assert found_payload["records"][0]["record"]["source_tables"] == ["product_category_pnl_canonical_fact"]
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


def test_data_catalog_page_catalog_date_coverage_prioritizes_missing_seeded_page_configs() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_catalog_date_coverage" for tool in tools)

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_coverage", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-catalog-date-coverage"
        assert "does not sample DuckDB tables" in payload["disclaimer"]
        assert "does not approve metric/page formal use" in payload["disclaimer"]
        pages = {page["page_id"]: page for page in payload["pages"]}
        assert "GAP-AVERAGE-BALANCE-PAGE" not in pages
        assert "GAP-BANK-LEDGER-DASHBOARD-PAGE" not in pages
        assert "GAP-CASHFLOW-PROJECTION-PAGE" not in pages
        assert "GAP-DECISION-ITEMS-PAGE" not in pages
        missing_pages = [
            page for page in payload["pages"] if page["coverage_status"] == "missing_explicit_table_config"
        ]
        deferred_pages = [
            page for page in payload["pages"] if page["coverage_status"] == "deferred_no_direct_table_config"
        ]
        assert payload["summary"] == {
            "page_count": len(payload["pages"]),
            "configured_page_count": sum(
                1 for page in payload["pages"] if page["coverage_status"] == "configured_direct_tables"
            ),
            "deferred_no_direct_table_config_count": len(deferred_pages),
            "missing_explicit_config_count": len(missing_pages),
            "formal_missing_explicit_config_count": sum(
                1 for page in missing_pages if page["approval_status"] == "formal_or_governed"
            ),
        }
        positions = pages["PAGE-POS-001"]
        assert positions["coverage_status"] == "configured_direct_tables"
        assert positions["configured_table_names"] == [
            "zqtz_bond_daily_snapshot",
            "tyw_interbank_daily_snapshot",
        ]
        assert positions["priority"] == "P3"
        assert positions["evidence_scope"]["samples_duckdb_tables"] is False
        assert positions["evidence_scope"]["approves_metric_or_page"] is False

        assert payload["missing_config_queue"] == []
        deferred_page_ids = [item["page_id"] for item in payload["deferred_config_queue"]]
        assert deferred_page_ids == [page["page_id"] for page in deferred_pages]

        executive_summary = payload["deferred_config_queue"][0]
        bond_analysis = pages["PAGE-BOND-ANALYSIS-001"]
        assert bond_analysis["coverage_status"] == "configured_direct_tables"
        assert bond_analysis["configured_table_names"] == ["fact_formal_bond_analytics_daily"]
        assert bond_analysis["deferred_no_direct_table_config_reason"] == ""
        cross_asset = pages["GAP-CROSS-ASSET-PAGE"]
        assert cross_asset["coverage_status"] == "configured_direct_tables"
        assert cross_asset["configured_table_names"] == [
            "fact_choice_macro_daily",
            "fx_daily_mid",
            "market_data_series_category",
            "livermore_position_snapshot",
            "choice_stock_daily_observation",
            "fact_livermore_gate_supplement_daily",
            "choice_news_event",
        ]
        assert cross_asset["evidence_scope"]["approves_metric_or_page"] is False

        concentration_monitor = pages["GAP-CONCENTRATION-MONITOR-PAGE"]
        assert concentration_monitor["coverage_status"] == "configured_direct_tables"
        assert concentration_monitor["approval_status"] == "candidate_or_pending"
        assert concentration_monitor["configured_table_names"] == [
            "fact_formal_bond_analytics_daily",
        ]
        assert concentration_monitor["evidence_scope"]["samples_duckdb_tables"] is False
        assert concentration_monitor["evidence_scope"]["approves_metric_or_page"] is False

        if "GAP-AVERAGE-BALANCE-PAGE" in pages:
            average_balance = pages["GAP-AVERAGE-BALANCE-PAGE"]
            assert average_balance["coverage_status"] == "configured_direct_tables"
            assert average_balance["approval_status"] == "candidate_or_pending"
            assert average_balance["evidence_scope"]["samples_duckdb_tables"] is False
            assert average_balance["evidence_scope"]["approves_metric_or_page"] is False

        if "GAP-KPI-PERFORMANCE-PAGE" in pages:
            kpi_performance = pages["GAP-KPI-PERFORMANCE-PAGE"]
            assert kpi_performance["coverage_status"] == "deferred_no_direct_table_config"
            assert kpi_performance["approval_status"] == "candidate_or_pending"
            assert kpi_performance["evidence_scope"]["samples_duckdb_tables"] is False
            assert kpi_performance["evidence_scope"]["approves_metric_or_page"] is False

        executive_summary = pages["PAGE-EXEC-SUMMARY-001"]
        assert executive_summary["priority"] == "P2"
        assert executive_summary["approval_status"] == "mixed_source_or_observational"
        assert executive_summary["coverage_status"] == "deferred_no_direct_table_config"
        assert executive_summary["deferred_no_direct_table_config_reason"]
        assert all("." not in table_name for table_name in executive_summary["candidate_table_names"])
        assert not any("Add explicit catalog/date table config" in action for action in executive_summary["next_actions"])
        assert executive_summary["evidence_scope"]["samples_duckdb_tables"] is False
        assert executive_summary["evidence_scope"]["proves_page_execution"] is False
    finally:
        server.close()


def test_data_catalog_page_catalog_date_coverage_keeps_bank_ledger_candidate_boundary_when_requested() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_catalog_date_coverage",
                "arguments": {"page_slugs": ["bank-ledger-dashboard"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-catalog-date-coverage"
        page = payload["pages"][0]
        assert page["page_id"] == "GAP-BANK-LEDGER-DASHBOARD-PAGE"
        assert page["page_slug"] == "bank-ledger-dashboard"
        assert page["approval_status"] == "candidate_or_pending"
        assert page["coverage_status"] == "configured_direct_tables"
        assert page["configured_table_names"] == [
            "ledger_import_batch",
            "ledger_raw_row",
            "position_snapshot",
            "position_snapshot_agg",
        ]
        assert page["evidence_scope"]["samples_duckdb_tables"] is False
        assert page["evidence_scope"]["approves_metric_or_page"] is False
        assert "GAP-BANK-LEDGER-DASHBOARD-PAGE" not in [
            item["page_id"] for item in payload["missing_config_queue"]
        ]
        assert payload["summary"] == {
            "page_count": 1,
            "configured_page_count": 1,
            "deferred_no_direct_table_config_count": 0,
            "missing_explicit_config_count": 0,
            "formal_missing_explicit_config_count": 0,
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_coverage_keeps_average_balance_excluded_candidate_boundary_when_requested() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_catalog_date_coverage",
                "arguments": {"page_slugs": ["average-balance"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-catalog-date-coverage"
        page = payload["pages"][0]
        assert page["page_id"] == "GAP-AVERAGE-BALANCE-PAGE"
        assert page["page_slug"] == "average-balance"
        assert page["approval_status"] == "candidate_or_pending"
        assert page["coverage_status"] == "configured_direct_tables"
        assert page["configured_table_names"] == [
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "zqtz_bond_daily_snapshot",
            "tyw_interbank_daily_snapshot",
        ]
        assert "ADB analytical route" in page["deferred_no_direct_table_config_reason"]
        assert "PAGE contract approval" in page["deferred_no_direct_table_config_reason"]
        assert "ADB denominator semantics" in page["deferred_no_direct_table_config_reason"]
        assert "owner review" in page["deferred_no_direct_table_config_reason"]
        assert page["candidate_table_names"] == []
        assert page["next_actions"] == [
            "Run page catalog/date evidence for GAP-AVERAGE-BALANCE-PAGE and review sampled table/date results before closure.",
        ]
        assert page["evidence_scope"]["samples_duckdb_tables"] is False
        assert page["evidence_scope"]["approves_metric_or_page"] is False
        assert payload["missing_config_queue"] == []
        assert payload["deferred_config_queue"] == []
        assert payload["summary"] == {
            "page_count": 1,
            "configured_page_count": 1,
            "deferred_no_direct_table_config_count": 0,
            "missing_explicit_config_count": 0,
            "formal_missing_explicit_config_count": 0,
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_coverage_keeps_cashflow_projection_candidate_boundary_when_requested() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_catalog_date_coverage",
                "arguments": {"page_slugs": ["cashflow-projection"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-catalog-date-coverage"
        page = payload["pages"][0]
        assert page["page_id"] == "GAP-CASHFLOW-PROJECTION-PAGE"
        assert page["page_slug"] == "cashflow-projection"
        assert page["approval_status"] == "candidate_or_pending"
        assert page["coverage_status"] == "configured_direct_tables"
        assert page["configured_table_names"] == [
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
        ]
        assert page["evidence_scope"]["samples_duckdb_tables"] is False
        assert page["evidence_scope"]["approves_metric_or_page"] is False
        assert payload["missing_config_queue"] == []
        assert payload["deferred_config_queue"] == []
        assert payload["summary"] == {
            "page_count": 1,
            "configured_page_count": 1,
            "deferred_no_direct_table_config_count": 0,
            "missing_explicit_config_count": 0,
            "formal_missing_explicit_config_count": 0,
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_coverage_configures_formal_seeded_pages() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_coverage", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        pages = {page["page_id"]: page for page in payload["pages"]}
        assert pages["PAGE-PROD-CAT-001"]["configured_table_names"] == [
            "product_category_pnl_formal_read_model",
            "product_category_pnl_canonical_fact",
        ]
        assert pages["PAGE-BALANCE-001"]["configured_table_names"] == [
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
        ]
        assert pages["PAGE-PNL-001"]["configured_table_names"] == [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
        ]
        assert pages["PAGE-BRIDGE-001"]["configured_table_names"] == [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
        ]
        assert pages["PAGE-RISK-001"]["configured_table_names"] == [
            "fact_formal_risk_tensor_daily",
        ]
        assert all(
            pages[page_id]["coverage_status"] == "configured_direct_tables"
            for page_id in (
                "PAGE-PROD-CAT-001",
                "PAGE-BALANCE-001",
                "PAGE-PNL-001",
                "PAGE-BRIDGE-001",
                "PAGE-RISK-001",
            )
        )
        assert "GAP-CASHFLOW-PROJECTION-PAGE" not in pages
        assert "GAP-DECISION-ITEMS-PAGE" not in pages
        assert payload["summary"]["configured_page_count"] == 29
        assert payload["summary"]["deferred_no_direct_table_config_count"] == 6
        assert payload["summary"]["missing_explicit_config_count"] == 0
        assert payload["summary"]["formal_missing_explicit_config_count"] == 0
    finally:
        server.close()


def test_data_catalog_page_catalog_date_coverage_configures_seeded_pages_with_clear_table_anchors() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_coverage", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        pages = {page["page_id"]: page for page in payload["pages"]}
        expected_tables = {
            "PAGE-DASH-001": [
                "fact_formal_zqtz_balance_daily",
                "fact_formal_tyw_balance_daily",
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
                "zqtz_bond_daily_snapshot",
                "tyw_interbank_daily_snapshot",
                "fact_formal_bond_analytics_daily",
                "fx_daily_mid",
            ],
            "PAGE-EXEC-OVERVIEW-001": [
                "fact_formal_zqtz_balance_daily",
                "fact_formal_tyw_balance_daily",
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
                "zqtz_bond_daily_snapshot",
                "tyw_interbank_daily_snapshot",
                "fact_formal_bond_analytics_daily",
            ],
            "PAGE-BAL-MOVE-001": [
                "fact_accounting_asset_movement_monthly",
                "fact_formal_zqtz_balance_daily",
            ],
            "PAGE-PNL-BY-BUSINESS-001": [
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
                "fact_formal_zqtz_balance_daily",
                "fact_pnl_by_business_precompute",
            ],
            "PAGE-PNL-ATTR-WB-001": [
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
                "fact_formal_zqtz_balance_daily",
                "fact_formal_bond_analytics_daily",
                "yield_curve_daily",
            ],
            "PAGE-LIAB-ANALYTICS-001": [
                "fact_formal_zqtz_balance_daily",
                "fact_formal_tyw_balance_daily",
                "zqtz_bond_daily_snapshot",
                "tyw_interbank_daily_snapshot",
            ],
            "PAGE-MARKET-HOME-001": [
                "fact_choice_macro_daily",
                "market_data_series_category",
                "fx_daily_mid",
            ],
            "PAGE-RISK-HOME-001": [
                "fact_formal_risk_tensor_daily",
                "fact_formal_zqtz_balance_daily",
                "fact_formal_tyw_balance_daily",
            ],
            "PAGE-PERFORMANCE-HOME-001": [
                "product_category_pnl_formal_read_model",
                "product_category_pnl_canonical_fact",
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
            ],
            "PAGE-REPORTS-HOME-001": [
                "fact_formal_bond_analytics_daily",
                "source_foundation",
            ],
            "PAGE-CUBE-QUERY-001": [
                "fact_formal_bond_analytics_daily",
                "fact_formal_pnl_fi",
                "fact_formal_zqtz_balance_daily",
                "product_category_pnl_formal_read_model",
            ],
            "PAGE-PORTFOLIO-HOME-001": [
                "fact_formal_zqtz_balance_daily",
                "fact_formal_tyw_balance_daily",
                "fact_formal_bond_analytics_daily",
                "zqtz_bond_daily_snapshot",
                "tyw_interbank_daily_snapshot",
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
                "fact_formal_risk_tensor_daily",
            ],
            "PAGE-BOND-ANALYSIS-001": [
                "fact_formal_bond_analytics_daily",
            ],
            "GAP-CROSS-ASSET-PAGE": [
                "fact_choice_macro_daily",
                "fx_daily_mid",
                "market_data_series_category",
                "livermore_position_snapshot",
                "choice_stock_daily_observation",
                "fact_livermore_gate_supplement_daily",
                "choice_news_event",
            ],
        }

        for page_id, table_names in expected_tables.items():
            assert pages[page_id]["configured_table_names"] == table_names
            assert pages[page_id]["coverage_status"] == "configured_direct_tables"
            assert pages[page_id]["evidence_scope"]["samples_duckdb_tables"] is False
            assert pages[page_id]["evidence_scope"]["approves_metric_or_page"] is False

        assert pages["PAGE-CUBE-QUERY-001"]["candidate_table_names"] == [
            "fact_formal_bond_analytics_daily",
            "fact_formal_pnl_fi",
            "fact_formal_zqtz_balance_daily",
            "product_category_pnl_formal_read_model",
        ]
        assert "fact_table" not in pages["PAGE-CUBE-QUERY-001"]["candidate_table_names"]
        assert "fact_table" not in pages["PAGE-CUBE-QUERY-001"]["configured_table_names"]

        assert "GAP-CASHFLOW-PROJECTION-PAGE" not in pages
        assert "GAP-DECISION-ITEMS-PAGE" not in pages
        assert payload["summary"]["configured_page_count"] == 29
        assert payload["summary"]["deferred_no_direct_table_config_count"] == 6
        assert payload["summary"]["missing_explicit_config_count"] == 0
        assert payload["summary"]["formal_missing_explicit_config_count"] == 0
        assert payload["missing_config_queue"] == []
        remaining_deferred = [item["page_id"] for item in payload["deferred_config_queue"]]
        assert remaining_deferred == [
            "PAGE-EXEC-SUMMARY-001",
            "PAGE-EXEC-PNL-ATTR-001",
            "PAGE-MACRO-TOOLKIT-001",
            "PAGE-MACRO-OBS-001",
            "PAGE-AGENT-001",
            "GAP-KPI-PERFORMANCE-PAGE",
        ]
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_prioritizes_formal_source_mix() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_catalog_date_lineage_review_queue" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_catalog_date_lineage_review_queue",
                "arguments": {
                    "page_slugs": [
                        "PAGE-BALANCE-001",
                        "PAGE-PNL-ATTR-WB-001",
                        "GAP-STOCK-ANALYSIS-PAGE",
                        "PAGE-EXEC-SUMMARY-001",
                        "PAGE-MACRO-TOOLKIT-001",
                    ]
                },
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-catalog-date-lineage-review-queue"
        assert "does not sample DuckDB tables" in payload["disclaimer"]
        assert "does not prove lineage or page/API execution" in payload["disclaimer"]
        assert "does not approve metric/page formal use" in payload["disclaimer"]
        summary_for_assertion = dict(payload["summary"])
        closure_readiness_for_assertion = dict(summary_for_assertion["closure_readiness"])
        closure_dispatch_packet = closure_readiness_for_assertion.pop("closure_dispatch_packet")
        assert closure_dispatch_packet == _expected_closure_dispatch_packet(
            closure_readiness_for_assertion["closure_execution_sequence"],
            status=closure_readiness_for_assertion["status"],
        )
        closure_dispatch_packet_scope_audit = closure_readiness_for_assertion.pop(
            "closure_dispatch_packet_scope_audit"
        )
        assert closure_dispatch_packet_scope_audit == _expected_clean_closure_dispatch_packet_scope_audit(4)
        next_closure_action_scope_audit = closure_readiness_for_assertion.pop(
            "next_closure_action_scope_audit"
        )
        assert next_closure_action_scope_audit == _expected_clean_next_closure_action_scope_audit(1)
        summary_for_assertion["closure_readiness"] = closure_readiness_for_assertion
        closure_sequence = closure_readiness_for_assertion["closure_execution_sequence"]
        record_gap_step = closure_sequence[0]
        catalog_date_step = closure_sequence[1]
        record_remediation_work_item_count = payload["record_remediation_scope_audit"]["work_item_count"]
        suggested_tool_call_work_item_count = payload["suggested_tool_call_scope_audit"]["work_item_count"]

        assert summary_for_assertion == {
            "page_count": 5,
            "review_item_count": 3,
            "deferred_review_item_count": 2,
            "p1_review_item_count": 2,
            "gap_or_observational_review_item_count": 1,
            "ready_for_audit_review_count": 3,
            "blocked_by_record_gaps_count": 2,
            "closure_readiness": {
                "page_count": 5,
                "ready_for_audit_review_count": 3,
                "blocked_by_record_gaps_count": 2,
                "record_remediation_work_item_count": record_remediation_work_item_count,
                "suggested_tool_call_work_item_count": suggested_tool_call_work_item_count,
                "closure_blocker_work_item_count": 4,
                "closure_blocker_work_item_breakdown": {
                    "record_gap_remediation": {
                        "page_count": 2,
                        "work_item_count": record_remediation_work_item_count,
                    },
                    "catalog_date_lineage_evidence_collection": {
                        "page_count": 5,
                        "work_item_count": suggested_tool_call_work_item_count,
                    },
                    "manual_audit_review": {
                        "page_count": 3,
                        "work_item_count": 3,
                    },
                    "business_owner_approval": {
                        "page_count": 3,
                        "work_item_count": 3,
                    },
                },
                "queue_boundary_work_item_count": closure_readiness_for_assertion["queue_boundary_work_item_count"],
                "closure_approved_count": 0,
                "closure_ready_count": 0,
                "closure_blocked_count": 5,
                "queue_grants_closure": False,
                "status": "record_remediation_and_catalog_date_lineage_review_required",
                "residual_closure_requirements": [
                    "record_gap_remediation",
                    "catalog_date_lineage_evidence_collection",
                    "manual_audit_review",
                    "business_owner_approval",
                ],
                "next_closure_action": {
                    "blocker_type": "record_gap_remediation",
                    "next_step": "use_record_gap_execution_plan",
                    "execution_plan": "record_gap_execution_plan",
                    "execution_stage": "remediation_type_batches",
                    "execution_stage_detail": {
                        "stage": 1,
                        "stage_type": "remediation_type_batches",
                        "work_item_group": "record_remediation_work_items",
                        "work_item_count": 2,
                        "page_count": 2,
                        "record_gap_page_count": 2,
                        "ready_manual_review_page_count": 3,
                        "includes_ready_manual_review_pages": False,
                        "suggested_tool_call_count": 4,
                        "arguments": {
                            "page_slugs": [
                                "executive-summary",
                                "macro-toolkit",
                            ],
                        },
                        "next_step": "batch_requirements_and_blueprint_collection_by_remediation_type",
                        "uses_work_item_groups": ["record_remediation_work_items"],
                        "must_complete_before": [
                            "evidence_key_batches",
                            "review_lane_batches",
                        ],
                        "writes_governance_records": False,
                        "executes_tool_calls": False,
                        "samples_duckdb_tables": False,
                        "checks_lineage_records": False,
                        "proves_page_execution": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                        "approves_metric_or_page": False,
                    },
                    "page_count": 2,
                    "work_item_count": record_remediation_work_item_count,
                    "arguments": {
                        "page_slugs": [
                            "executive-summary",
                            "macro-toolkit",
                        ],
                    },
                    "must_complete_before": [
                        "manual_audit_review",
                        "business_owner_approval",
                    ],
                    **_expected_no_closure_scope_flags(),
                },
                "closure_execution_sequence": [
                    {
                        "sequence": 1,
                        "blocker_type": "record_gap_remediation",
                        "next_step": "use_record_gap_execution_plan",
                        "execution_plan": "record_gap_execution_plan",
                        "execution_stage": "remediation_type_batches",
                        "execution_stage_detail": {
                            "stage": 1,
                            "stage_type": "remediation_type_batches",
                            "work_item_group": "record_remediation_work_items",
                            "work_item_count": 2,
                            "page_count": 2,
                            "record_gap_page_count": 2,
                            "ready_manual_review_page_count": 3,
                            "includes_ready_manual_review_pages": False,
                            "suggested_tool_call_count": 4,
                            "arguments": {
                                "page_slugs": [
                                    "executive-summary",
                                    "macro-toolkit",
                                ],
                            },
                            "next_step": "batch_requirements_and_blueprint_collection_by_remediation_type",
                            "uses_work_item_groups": ["record_remediation_work_items"],
                            "must_complete_before": [
                                "evidence_key_batches",
                                "review_lane_batches",
                            ],
                            "writes_governance_records": False,
                            "executes_tool_calls": False,
                            "samples_duckdb_tables": False,
                            "checks_lineage_records": False,
                            "proves_page_execution": False,
                            "runs_ui_or_api_smoke": False,
                            "captures_business_owner_approval": False,
                            "approves_metric_or_page": False,
                        },
                        "page_count": 2,
                        "work_item_count": record_remediation_work_item_count,
                        "source_work_item_group_counts": record_gap_step["source_work_item_group_counts"],
                        "arguments": {
                            "page_slugs": [
                                "executive-summary",
                                "macro-toolkit",
                            ],
                        },
                        "must_complete_before": [
                            "manual_audit_review",
                            "business_owner_approval",
                        ],
                        "queue_grants_closure": False,
                    },
                    {
                        "sequence": 2,
                        "blocker_type": "catalog_date_lineage_evidence_collection",
                        "next_step": "use_evidence_collection_execution_plan",
                        "execution_plan": "evidence_collection_execution_plan",
                        "execution_stage": "catalog_date_evidence_batches",
                        "execution_stage_detail": {
                            "stage": 1,
                            "stage_type": "catalog_date_evidence_batches",
                            "work_item_group": "suggested_tool_call_work_items",
                            "tool": "moss-data-catalog.get_page_catalog_date_evidence",
                            "work_item_count": 3,
                            "page_count": 3,
                            "suggested_tool_call_count": 3,
                            "arguments": {
                                "page_slugs": [
                                    "balance-analysis",
                                    "pnl-attribution",
                                    "stock-analysis",
                                ],
                            },
                            "next_step": "collect_catalog_date_evidence_by_review_lane",
                            "uses_work_item_groups": ["suggested_tool_call_work_items"],
                            "must_complete_before": [
                                "lineage_evidence_batches",
                                "governance_validation_batches",
                            ],
                            "writes_governance_records": False,
                            "executes_tool_calls": False,
                            "samples_duckdb_tables": False,
                            "checks_lineage_records": False,
                            "proves_page_execution": False,
                            "runs_ui_or_api_smoke": False,
                            "captures_business_owner_approval": False,
                            "approves_metric_or_page": False,
                        },
                        "page_count": 5,
                        "work_item_count": suggested_tool_call_work_item_count,
                        "source_work_item_group_counts": catalog_date_step["source_work_item_group_counts"],
                        "arguments": {
                            "page_slugs": [
                                "balance-analysis",
                                "pnl-attribution",
                                "stock-analysis",
                                "executive-summary",
                                "macro-toolkit",
                            ],
                        },
                        "must_complete_before": [
                            "manual_audit_review",
                            "business_owner_approval",
                        ],
                        "queue_grants_closure": False,
                    },
                    {
                        "sequence": 3,
                        "blocker_type": "manual_audit_review",
                        "next_step": "use_manual_audit_review_execution_plan",
                        "execution_plan": "manual_audit_review_execution_plan",
                        "execution_stage": "audit_review_queue_batches",
                        "execution_stage_detail": {
                            "stage": 1,
                            "stage_type": "audit_review_queue_batches",
                            "work_item_group": "record_remediation_work_items",
                            "tool": "moss-lineage-evidence.get_page_governance_audit_review_queue",
                            "work_item_count": 1,
                            "page_count": 3,
                            "suggested_tool_call_count": 1,
                            "arguments": {"page_slugs": ["balance-analysis", "pnl-attribution", "stock-analysis"]},
                            "next_step": "collect_manual_audit_review_queue_without_approval",
                            "uses_work_item_groups": ["record_remediation_work_items"],
                            "must_complete_before": [
                                "audit_evidence_packet_queue_batches",
                            ],
                            "writes_governance_records": False,
                            "executes_tool_calls": False,
                            "samples_duckdb_tables": False,
                            "checks_lineage_records": False,
                            "proves_page_execution": False,
                            "runs_ui_or_api_smoke": False,
                            "captures_business_owner_approval": False,
                            "approves_metric_or_page": False,
                        },
                        "page_count": 3,
                        "work_item_count": 3,
                        "source_work_item_group_counts": {
                            "record_remediation_work_items": 2,
                        },
                        "arguments": {"page_slugs": ["balance-analysis", "pnl-attribution", "stock-analysis"]},
                        "must_complete_before": ["business_owner_approval"],
                        "queue_grants_closure": False,
                    },
                    {
                        "sequence": 4,
                        "blocker_type": "business_owner_approval",
                        "next_step": "use_business_owner_approval_execution_plan",
                        "execution_plan": "business_owner_approval_execution_plan",
                        "execution_stage": "owner_approval_request_batches",
                        "execution_stage_detail": {
                            "stage": 1,
                            "stage_type": "owner_approval_request_batches",
                            "work_item_group": "record_remediation_work_items",
                            "work_item_count": 1,
                            "page_count": 3,
                            "arguments": {"page_slugs": ["balance-analysis", "pnl-attribution", "stock-analysis"]},
                            "next_step": "prepare_owner_approval_request_after_manual_audit_review",
                            "uses_work_item_groups": ["record_remediation_work_items"],
                            "must_complete_before": ["owner_approval_receipt_review_batches"],
                            "writes_governance_records": False,
                            "executes_tool_calls": False,
                            "samples_duckdb_tables": False,
                            "checks_lineage_records": False,
                            "proves_page_execution": False,
                            "runs_ui_or_api_smoke": False,
                            "captures_business_owner_approval": False,
                            "approves_metric_or_page": False,
                        },
                        "page_count": 3,
                        "work_item_count": 3,
                        "source_work_item_group_counts": {
                            "record_remediation_work_items": 2,
                        },
                        "arguments": {"page_slugs": ["balance-analysis", "pnl-attribution", "stock-analysis"]},
                        "must_complete_before": [],
                        "queue_grants_closure": False,
                    },
                ],
            },
        }

        review_items = {item["page_id"]: item for item in payload["review_queue"]}
        assert list(review_items) == [
            "PAGE-BALANCE-001",
            "PAGE-PNL-ATTR-WB-001",
            "GAP-STOCK-ANALYSIS-PAGE",
        ]

        balance = review_items["PAGE-BALANCE-001"]
        assert balance["review_priority"] == "P1"
        assert balance["review_lane"] == "formal_governed_catalog_date_lineage_review"
        assert balance["configured_table_names"] == [
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
        ]
        assert balance["formal_page_closure_allowed"] is False
        assert any(
            call["tool"] == "moss-data-catalog.get_page_catalog_date_evidence"
            and call["arguments"] == {"page_slugs": ["balance-analysis"]}
            for call in balance["suggested_tool_calls"]
        )
        assert any(
            call["tool"] == "moss-lineage-evidence.get_page_lineage_evidence"
            and call["arguments"] == {"page_slugs": ["balance-analysis"]}
            for call in balance["suggested_tool_calls"]
        )
        assert balance["evidence_scope"] == {
            "queues_evidence_collection": True,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "checks_data_quality": False,
            "checks_ui_api_payload": False,
            "proves_page_execution": False,
            "approves_metric_or_page": False,
        }

        pnl_attribution = review_items["PAGE-PNL-ATTR-WB-001"]
        assert pnl_attribution["review_priority"] == "P1"
        assert pnl_attribution["review_lane"] == "candidate_formal_source_mixed_review"
        assert pnl_attribution["record_readiness"]["audit_review_status"] == "ready_for_audit_review"
        assert "fact_formal_pnl_fi" in pnl_attribution["configured_table_names"]
        assert any("candidate or mixed-source page uses formal source tables" in reason for reason in pnl_attribution["risk_reasons"])
        assert any("do not promote candidate output" in action for action in pnl_attribution["next_actions"])

        stock = review_items["GAP-STOCK-ANALYSIS-PAGE"]
        assert stock["review_priority"] == "P2"
        assert stock["approval_status"] == "gap_or_observational"
        assert stock["configured_table_names"] == [
            "livermore_position_snapshot",
            "livermore_candidate_history",
            "choice_stock_daily_observation",
            "fact_livermore_gate_supplement_daily",
        ]
        assert stock["formal_page_closure_allowed"] is False
        assert not any(table.startswith("fact_formal_") for table in stock["configured_table_names"])
        assert stock["review_lane"] == "gap_observational_separate_review"
        assert stock["next_actions"] == [
            "Keep GAP/observational evidence separate from formal PAGE/MTR/golden-sample closure.",
            "Collect catalog/date and lineage evidence for GAP-STOCK-ANALYSIS-PAGE as observational support only.",
        ]
        assert stock["evidence_scope"] == {
            "queues_evidence_collection": True,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "checks_data_quality": False,
            "checks_ui_api_payload": False,
            "proves_page_execution": False,
            "approves_metric_or_page": False,
        }
        assert stock["record_remediation"]["evidence_scope"] == {
            "writes_governance_records": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "executes_tool_calls": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
        }
        assert all("formal_use_allowed" not in call.get("arguments", {}) for call in stock["suggested_tool_calls"])
        assert balance["record_readiness"]["audit_review_status"] == "ready_for_audit_review"

        deferred = {item["page_id"]: item for item in payload["deferred_review_queue"]}
        assert set(deferred) == {
            "PAGE-EXEC-SUMMARY-001",
            "PAGE-MACRO-TOOLKIT-001",
        }
        assert deferred["PAGE-EXEC-SUMMARY-001"]["review_lane"] == "deferred_no_direct_table_config_review"
        assert deferred["PAGE-EXEC-SUMMARY-001"]["suggested_tool_calls"] == [
            {
                "tool": "moss-data-catalog.get_page_catalog_date_coverage",
                "arguments": {"page_slugs": ["executive-summary"]},
            },
            {
                "tool": "moss-lineage-evidence.get_page_governance_gap_queue",
                "arguments": {"page_slugs": ["executive-summary"]},
            },
        ]
        assert any("do not invent tables_used" in action for action in deferred["PAGE-EXEC-SUMMARY-001"]["next_actions"])
        assert deferred["PAGE-MACRO-TOOLKIT-001"]["evidence_scope"]["samples_duckdb_tables"] is False
        assert deferred["PAGE-MACRO-TOOLKIT-001"]["evidence_scope"]["approves_metric_or_page"] is False
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_summarizes_all_seeded_lanes() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        summary_for_assertion = dict(payload["summary"])
        closure_readiness_for_assertion = dict(summary_for_assertion["closure_readiness"])
        closure_dispatch_packet = closure_readiness_for_assertion.pop("closure_dispatch_packet")
        assert closure_dispatch_packet == _expected_closure_dispatch_packet(
            closure_readiness_for_assertion["closure_execution_sequence"],
            status=closure_readiness_for_assertion["status"],
        )
        closure_dispatch_packet_scope_audit = closure_readiness_for_assertion.pop(
            "closure_dispatch_packet_scope_audit"
        )
        assert closure_dispatch_packet_scope_audit == _expected_clean_closure_dispatch_packet_scope_audit(4)
        next_closure_action_scope_audit = closure_readiness_for_assertion.pop(
            "next_closure_action_scope_audit"
        )
        assert next_closure_action_scope_audit == _expected_clean_next_closure_action_scope_audit(1)
        summary_for_assertion["closure_readiness"] = closure_readiness_for_assertion

        review_rows = payload["review_queue"] + payload["deferred_review_queue"]
        assert summary_for_assertion["page_count"] == len(review_rows)
        assert summary_for_assertion["review_item_count"] == len(payload["review_queue"])
        assert summary_for_assertion["deferred_review_item_count"] == len(payload["deferred_review_queue"])
        assert summary_for_assertion["page_count"] == 35
        assert summary_for_assertion["review_item_count"] == 29
        assert summary_for_assertion["deferred_review_item_count"] == 6
        assert summary_for_assertion["p1_review_item_count"] == sum(
            1 for row in review_rows if row["review_priority"] == "P1"
        )
        assert summary_for_assertion["gap_or_observational_review_item_count"] == sum(
            1 for row in review_rows if row["approval_status"] == "gap_or_observational"
        )
        assert summary_for_assertion["ready_for_audit_review_count"] == sum(
            1
            for row in review_rows
            if row["record_readiness"]["audit_review_status"] == "ready_for_audit_review"
        )
        assert summary_for_assertion["blocked_by_record_gaps_count"] == sum(
            1
            for row in review_rows
            if row["record_readiness"]["audit_review_status"] == "blocked_by_record_gaps"
        )

        closure = summary_for_assertion["closure_readiness"]
        closure_blocker_work_items = payload["closure_blocker_work_items"]
        closure_blocker_breakdown = {
            item["blocker_type"]: {
                "page_count": item["page_count"],
                "work_item_count": item["work_item_count"],
            }
            for item in closure_blocker_work_items
        }
        assert closure["page_count"] == summary_for_assertion["page_count"]
        assert closure["ready_for_audit_review_count"] == summary_for_assertion["ready_for_audit_review_count"]
        assert closure["blocked_by_record_gaps_count"] == summary_for_assertion["blocked_by_record_gaps_count"]
        assert closure["record_remediation_work_item_count"] == payload["record_remediation_scope_audit"][
            "work_item_count"
        ]
        assert closure["suggested_tool_call_work_item_count"] == payload["suggested_tool_call_scope_audit"][
            "work_item_count"
        ]
        assert closure["closure_blocker_work_item_count"] == len(closure_blocker_work_items)
        assert closure["closure_blocker_work_item_breakdown"] == closure_blocker_breakdown
        assert closure["queue_boundary_work_item_count"] == payload["queue_boundary_audit"]["work_item_count"]
        assert closure["closure_approved_count"] == 0
        assert closure["closure_ready_count"] == 0
        assert closure["closure_blocked_count"] == closure["page_count"]
        assert closure["queue_grants_closure"] is False
        assert closure["status"] == "record_remediation_and_catalog_date_lineage_review_required"
        assert closure["residual_closure_requirements"] == [
            "record_gap_remediation",
            "catalog_date_lineage_evidence_collection",
            "manual_audit_review",
            "business_owner_approval",
        ]
        assert closure["next_closure_action"]["blocker_type"] == "record_gap_remediation"
        assert closure["next_closure_action"]["execution_plan"] == "record_gap_execution_plan"
        assert closure["next_closure_action"]["execution_stage"] == "remediation_type_batches"
        assert closure["next_closure_action"]["execution_stage_detail"]["page_count"] == closure[
            "next_closure_action"
        ]["page_count"]
        assert closure["next_closure_action"]["execution_stage_detail"]["work_item_count"] == 2
        assert closure["next_closure_action"]["arguments"] == {
            "page_slugs": CATALOG_DATE_RECORD_GAP_PAGE_SLUGS,
        }
        assert closure["next_closure_action"]["queue_grants_closure"] is False
        assert [item["blocker_type"] for item in closure["closure_execution_sequence"]] == [
            "record_gap_remediation",
            "catalog_date_lineage_evidence_collection",
            "manual_audit_review",
            "business_owner_approval",
        ]
        assert closure["closure_execution_sequence"] == [
            item
            for item in sorted(
                closure["closure_execution_sequence"],
                key=lambda item: item["sequence"],
            )
        ]
        assert closure["closure_execution_sequence"][0]["execution_plan"] == "record_gap_execution_plan"
        assert closure["closure_execution_sequence"][1]["execution_plan"] == "evidence_collection_execution_plan"

        lane_breakdown = payload["review_lane_breakdown"]
        for lane, breakdown in lane_breakdown.items():
            lane_rows = [row for row in review_rows if row["review_lane"] == lane]
            assert breakdown == {
                "item_count": len(lane_rows),
                "page_ids": [row["page_id"] for row in lane_rows],
            }
        assert set(lane_breakdown) == {
            "formal_governed_catalog_date_lineage_review",
            "candidate_formal_source_mixed_review",
            "candidate_or_mixed_catalog_date_lineage_review",
            "gap_observational_separate_review",
            "deferred_no_direct_table_config_review",
        }
        assert {
            lane: breakdown["item_count"]
            for lane, breakdown in lane_breakdown.items()
        } == {
            "formal_governed_catalog_date_lineage_review": 5,
            "candidate_formal_source_mixed_review": 16,
            "candidate_or_mixed_catalog_date_lineage_review": 7,
            "gap_observational_separate_review": 1,
            "deferred_no_direct_table_config_review": 6,
        }
        assert all(row["formal_page_closure_allowed"] is False for row in review_rows)
        assert all(row["evidence_scope"]["samples_duckdb_tables"] is False for row in review_rows)
        assert all(row["evidence_scope"]["checks_lineage_records"] is False for row in review_rows)
        assert all(row["evidence_scope"]["proves_page_execution"] is False for row in review_rows)
        assert all(row["evidence_scope"]["approves_metric_or_page"] is False for row in review_rows)

        rows = {row["page_id"]: row for row in review_rows}
        assert rows["PAGE-DASH-001"]["record_readiness"] == {
            "record_validation_status": "missing_direct_records",
            "audit_review_status": "blocked_by_record_gaps",
            "ready_record_count": 0,
            "direct_record_count": 0,
            "incomplete_record_count": 0,
            "expanded_anchor_record_count": 20,
            "residual_gaps": [
                "A direct page/API governance record is missing; expanded anchors cannot prove page/API execution.",
            ],
        }
        assert rows["PAGE-PORTFOLIO-HOME-001"]["record_readiness"]["audit_review_status"] == "blocked_by_record_gaps"
        assert rows["PAGE-OPS-001"]["record_readiness"]["record_validation_status"] == "missing_direct_records"
        assert rows["PAGE-OPS-001"]["record_remediation"]["remediation_type"] == "create_direct_record"
        assert rows["PAGE-BOND-ANALYSIS-001"]["record_remediation"]["remediation_type"] == "none"
        assert rows["PAGE-BOND-ANALYSIS-001"]["record_remediation"]["approval_boundary"] == "review_routing_only"
        assert rows["PAGE-BOND-ANALYSIS-001"]["formal_page_closure_allowed"] is False
        assert rows["GAP-CROSS-ASSET-PAGE"]["record_remediation"]["remediation_type"] == "create_direct_record"
        stock = rows["GAP-STOCK-ANALYSIS-PAGE"]
        assert stock["review_lane"] == "gap_observational_separate_review"
        assert stock["page_id"] in lane_breakdown[stock["review_lane"]]["page_ids"]
        assert stock["approval_status"] == "gap_or_observational"
        assert stock["formal_page_closure_allowed"] is False
        assert stock["record_remediation"]["remediation_type"] == "none"
        assert stock["record_remediation"]["approval_boundary"] == "review_routing_only"
        assert rows["PAGE-BOND-001"]["record_readiness"] == {
            "record_validation_status": "direct_records_ready_for_audit_review",
            "audit_review_status": "ready_for_audit_review",
            "ready_record_count": 1,
            "direct_record_count": 1,
            "incomplete_record_count": 0,
            "expanded_anchor_record_count": 20,
            "residual_gaps": [
                "Direct record fields are present, but this still does not prove page execution completeness or metric/page approval.",
            ],
        }
        assert rows["PAGE-BOND-001"]["record_remediation"] == {
            "remediation_type": "none",
            "next_step": "manual_audit_review",
            "approval_boundary": "review_routing_only",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
            },
        }

        assert rows["PAGE-DASH-001"]["record_remediation"] == {
            "remediation_type": "create_direct_record",
            "next_step": "collect_direct_page_api_record_evidence_then_preflight_candidate",
            "evidence_to_collect": [
                "direct_page_or_primary_api_anchor",
                "required_record_fields",
                "page_api_execution_identifier",
                "configured_or_deferred_table_anchors",
            ],
            "suggested_tool_calls": [
                {
                    "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
                    "arguments": {"page_slugs": ["dashboard-home"]},
                },
                {
                    "tool": "moss-lineage-evidence.get_page_governance_record_blueprint",
                    "arguments": {"page_slug": "dashboard-home"},
                },
            ],
            "approval_boundary": "record_remediation_only",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
            },
        }
        assert rows["PAGE-LEDGER-PNL-001"]["record_remediation"]["remediation_type"] == "create_direct_record"
        assert rows["PAGE-BALANCE-001"]["record_remediation"] == {
            "remediation_type": "none",
            "next_step": "manual_audit_review",
            "approval_boundary": "review_routing_only",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
            },
        }

        remediation_breakdown = payload["record_remediation_breakdown"]
        expected_remediation_breakdown: dict[str, dict[str, Any]] = {}
        for row in review_rows:
            remediation_type = row["record_remediation"]["remediation_type"]
            group = expected_remediation_breakdown.setdefault(
                remediation_type,
                {"item_count": 0, "page_ids": []},
            )
            group["item_count"] += 1
            group["page_ids"].append(row["page_id"])
        assert set(remediation_breakdown) == set(expected_remediation_breakdown)
        for remediation_type, expected_group in expected_remediation_breakdown.items():
            actual_group = remediation_breakdown[remediation_type]
            assert actual_group["item_count"] == expected_group["item_count"]
            assert set(actual_group["page_ids"]) == set(expected_group["page_ids"])
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_groups_suggested_call_work_items() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        work_items = payload["suggested_tool_call_work_items"]
        assert payload["suggested_tool_call_scope_audit"]["work_item_count"] == len(work_items)

        by_lane_tool = {(item["review_lane"], item["tool"]): item for item in work_items}
        formal_catalog = by_lane_tool[
            (
                "formal_governed_catalog_date_lineage_review",
                "moss-data-catalog.get_page_catalog_date_evidence",
            )
        ]
        assert formal_catalog["page_ids"] == [
            "PAGE-PROD-CAT-001",
            "PAGE-BALANCE-001",
            "PAGE-PNL-001",
            "PAGE-BRIDGE-001",
            "PAGE-RISK-001",
        ]
        assert formal_catalog["arguments"] == {
            "page_slugs": [
                "product-category-pnl",
                "balance-analysis",
                "pnl",
                "pnl-bridge",
                "risk-tensor",
            ]
        }
        assert formal_catalog["work_item_count"] == 5
        assert formal_catalog["review_priority"] == "P1"

        candidate_validation = by_lane_tool[
            (
                "candidate_formal_source_mixed_review",
                "moss-lineage-evidence.validate_page_governance_records",
            )
        ]
        assert candidate_validation["work_item_count"] == 16
        assert candidate_validation["arguments"]["page_slugs"] == [
            "dashboard-home",
            "executive-overview",
            "concentration-monitor",
            "balance-movement-analysis",
            "pnl-by-business",
            "pnl-attribution",
            "operations-analysis",
            "liability-analytics",
            "bond-dashboard",
            "bond-analysis",
            "cube-query",
            "portfolio-home",
            "risk-home",
            "performance-home",
            "team-performance",
            "reports-home",
        ]

        candidate_or_mixed_catalog = by_lane_tool[
            (
                "candidate_or_mixed_catalog_date_lineage_review",
                "moss-data-catalog.get_page_catalog_date_evidence",
            )
        ]
        assert set(candidate_or_mixed_catalog["page_ids"]) >= {
            "PAGE-LEDGER-PNL-001",
            "PAGE-POS-001",
            "PAGE-MKT-001",
            "GAP-CROSS-ASSET-PAGE",
            "GAP-PLATFORM-CONFIG-PAGE",
            "GAP-NEWS-EVENTS-PAGE",
            "PAGE-MARKET-HOME-001",
        }
        catalog_items_by_page_id = {
            page_id: item
            for item in work_items
            if item["tool"] == "moss-data-catalog.get_page_catalog_date_evidence"
            for page_id in item["page_ids"]
        }
        stock_catalog_item = catalog_items_by_page_id["GAP-STOCK-ANALYSIS-PAGE"]
        assert "stock-analysis" in stock_catalog_item["arguments"]["page_slugs"]

        deferred_gap_queue = by_lane_tool[
            (
                "deferred_no_direct_table_config_review",
                "moss-lineage-evidence.get_page_governance_gap_queue",
            )
        ]
        assert deferred_gap_queue["work_item_count"] == 6
        assert deferred_gap_queue["arguments"]["page_slugs"] == [
            "executive-summary",
            "executive-pnl-attribution",
            "macro-toolkit",
            "macro-observation",
            "agent",
            "kpi-performance",
        ]

        assert all(item["executes_tool_call"] is False for item in work_items)
        assert all(item["samples_duckdb_tables"] is False for item in work_items)
        assert all(item["checks_lineage_records"] is False for item in work_items)
        assert all(item["proves_page_execution"] is False for item in work_items)
        assert all(item["approves_metric_or_page"] is False for item in work_items)

        assert payload["suggested_tool_call_scope_audit"] == {
            "work_item_count": len(work_items),
            "checked_work_item_group": "suggested_tool_call_work_items",
            "allowed_suggested_tools": [
                "moss-data-catalog.get_page_catalog_date_evidence",
                "moss-data-catalog.get_page_catalog_date_coverage",
                "moss-lineage-evidence.get_page_lineage_evidence",
                "moss-lineage-evidence.validate_page_governance_records",
                "moss-lineage-evidence.get_page_governance_gap_queue",
            ],
            "executes_tool_call": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "approves_metric_or_page": False,
            "suggested_tool_violations": [],
            "scope_violations": [],
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_suggested_tool_call_scope_audit_flags_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_catalog_date_lineage_suggested_tool_call_scope_audit(
        [
            {
                "review_lane": "formal_governed_catalog_date_lineage_review",
                "tool": "moss-data-catalog.get_page_catalog_date_evidence",
                "executes_tool_call": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": True,
                "proves_page_execution": False,
                "approves_metric_or_page": False,
            },
            {
                "review_lane": "formal_governed_catalog_date_lineage_review",
                "tool": "moss-lineage-evidence.preflight_page_governance_record",
                "executes_tool_call": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "approves_metric_or_page": False,
            },
        ]
    )

    assert result["work_item_count"] == 2
    assert result["checks_lineage_records"] is True
    assert result["scope_violations"] == [
        {
            "work_item_group": "suggested_tool_call_work_items",
            "work_item_index": 0,
            "scope_key": "checks_lineage_records",
            "scope_value": True,
        }
    ]
    assert result["suggested_tool_violations"] == [
        {
            "work_item_group": "suggested_tool_call_work_items",
            "work_item_index": 1,
            "tool": "moss-lineage-evidence.preflight_page_governance_record",
        }
    ]


def test_data_catalog_page_catalog_date_lineage_review_queue_builds_evidence_collection_execution_plan() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        plan = payload["evidence_collection_execution_plan"]
        assert plan["scope"] == "catalog_date_lineage_evidence_collection_dispatch_plan"
        assert plan["status"] == "catalog_date_lineage_evidence_collection_required"
        assert plan["page_count"] == payload["summary"]["page_count"]
        assert plan["execution_stage_count"] == 5
        assert plan["execution_stage_order"] == [
            "catalog_date_evidence_batches",
            "lineage_evidence_batches",
            "governance_validation_batches",
            "deferred_catalog_date_coverage_batches",
            "deferred_governance_gap_queue_batches",
        ]
        suggested_tool_call_count = payload["suggested_tool_call_scope_audit"][
            "work_item_count"
        ]
        assert plan["work_item_group_counts"] == {
            "suggested_tool_call_work_items": suggested_tool_call_count
        }
        assert plan["suggested_tool_call_count"] == suggested_tool_call_count
        expected_page_slugs = {
            row["page_slug"]
            for row in payload["review_queue"] + payload["deferred_review_queue"]
        }
        assert set(plan["collection_arguments"]["page_slugs"]) == expected_page_slugs
        assert "kpi-performance" in plan["collection_arguments"]["page_slugs"]

        expected_stage_tools = {
            "catalog_date_evidence_batches": "moss-data-catalog.get_page_catalog_date_evidence",
            "lineage_evidence_batches": "moss-lineage-evidence.get_page_lineage_evidence",
            "governance_validation_batches": "moss-lineage-evidence.validate_page_governance_records",
            "deferred_catalog_date_coverage_batches": "moss-data-catalog.get_page_catalog_date_coverage",
            "deferred_governance_gap_queue_batches": "moss-lineage-evidence.get_page_governance_gap_queue",
        }
        assert {
            stage["stage_type"]: stage["tool"]
            for stage in plan["execution_stages"]
        } == expected_stage_tools
        assert sum(
            stage["work_item_count"] for stage in plan["execution_stages"]
        ) == suggested_tool_call_count
        assert sum(
            stage["suggested_tool_call_count"] for stage in plan["execution_stages"]
        ) == suggested_tool_call_count
        for stage in plan["execution_stages"]:
            if stage["stage_type"].startswith("deferred_"):
                assert stage["page_count"] == len(DEFERRED_CATALOG_DATE_PAGE_SLUGS)
                assert stage["arguments"]["page_slugs"] == DEFERRED_CATALOG_DATE_PAGE_SLUGS
                assert "kpi-performance" in stage["arguments"]["page_slugs"]
            else:
                assert stage["page_count"] == len(CONFIGURED_CATALOG_DATE_PAGE_SLUGS)
                assert set(stage["arguments"]["page_slugs"]) == set(CONFIGURED_CATALOG_DATE_PAGE_SLUGS)
        assert all(stage["arguments"]["page_slugs"] for stage in plan["execution_stages"])
        assert all(stage["executes_tool_calls"] is False for stage in plan["execution_stages"])
        assert all(stage["samples_duckdb_tables"] is False for stage in plan["execution_stages"])
        assert all(stage["checks_lineage_records"] is False for stage in plan["execution_stages"])
        assert all(stage["proves_page_execution"] is False for stage in plan["execution_stages"])
        assert all(stage["approves_metric_or_page"] is False for stage in plan["execution_stages"])
        assert plan["queue_grants_closure"] is False
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_audits_evidence_collection_execution_plan_scope() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["evidence_collection_execution_plan_scope_audit"] == {
            "work_item_count": 5,
            "checked_work_item_group": "evidence_collection_execution_plan.execution_stages",
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": False,
            "scope_violations": [],
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_evidence_collection_execution_plan_scope_audit_flags_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_catalog_date_lineage_evidence_collection_execution_plan_scope_audit(
        {
            "execution_stages": [
                {
                    "writes_governance_records": False,
                    "executes_tool_calls": True,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                },
                {
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": None,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                },
            ],
            "queue_grants_closure": True,
        }
    )

    assert result["work_item_count"] == 2
    assert result["executes_tool_calls"] is True
    assert result["queue_grants_closure"] is True
    assert result["scope_violations"] == [
        {
            "work_item_group": "evidence_collection_execution_plan.execution_stages",
            "work_item_index": 0,
            "scope_key": "executes_tool_calls",
            "scope_value": True,
        },
        {
            "work_item_group": "evidence_collection_execution_plan.execution_stages",
            "work_item_index": 1,
            "scope_key": "checks_lineage_records",
            "scope_value": None,
        },
        {
            "work_item_group": "evidence_collection_execution_plan",
            "work_item_index": None,
            "scope_key": "queue_grants_closure",
            "scope_value": True,
        },
    ]


def test_data_catalog_page_catalog_date_lineage_review_queue_builds_manual_audit_review_execution_plan() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        plan = payload["manual_audit_review_execution_plan"]
        assert plan == {
            "scope": "manual_audit_review_dispatch_plan",
            "status": "manual_audit_review_required",
            "ready_page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
            "execution_stage_count": 2,
            "execution_stage_order": [
                "audit_review_queue_batches",
                "audit_evidence_packet_queue_batches",
            ],
            "work_item_group_counts": {"record_remediation_work_items": 1},
            "suggested_tool_call_count": 2,
            "suggested_tool_names": [
                "moss-lineage-evidence.get_page_governance_audit_review_queue",
                "moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue",
            ],
            "manual_review_arguments": {"page_slugs": READY_FOR_AUDIT_PAGE_SLUGS},
            "execution_stages": [
                {
                    "stage": 1,
                    "stage_type": "audit_review_queue_batches",
                    "work_item_group": "record_remediation_work_items",
                    "tool": "moss-lineage-evidence.get_page_governance_audit_review_queue",
                    "work_item_count": 1,
                    "page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
                    "suggested_tool_call_count": 1,
                    "arguments": {"page_slugs": READY_FOR_AUDIT_PAGE_SLUGS},
                    "next_step": "collect_manual_audit_review_queue_without_approval",
                    "uses_work_item_groups": ["record_remediation_work_items"],
                    "must_complete_before": ["audit_evidence_packet_queue_batches"],
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                },
                {
                    "stage": 2,
                    "stage_type": "audit_evidence_packet_queue_batches",
                    "work_item_group": "record_remediation_work_items",
                    "tool": "moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue",
                    "work_item_count": 1,
                    "page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
                    "suggested_tool_call_count": 1,
                    "arguments": {"page_slugs": READY_FOR_AUDIT_PAGE_SLUGS},
                    "next_step": "collect_manual_audit_evidence_packets_without_closure",
                    "uses_work_item_groups": ["record_remediation_work_items"],
                    "must_complete_before": [],
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                },
            ],
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": False,
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_audits_manual_audit_review_execution_plan_scope() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["manual_audit_review_execution_plan_scope_audit"] == {
            "work_item_count": 2,
            "checked_work_item_group": "manual_audit_review_execution_plan.execution_stages",
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": False,
            "scope_violations": [],
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_manual_audit_review_execution_plan_scope_audit_flags_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_catalog_date_lineage_manual_audit_review_execution_plan_scope_audit(
        {
            "execution_stages": [
                {
                    "writes_governance_records": False,
                    "executes_tool_calls": True,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                },
                {
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": True,
                    "approves_metric_or_page": False,
                },
            ],
            "queue_grants_closure": True,
        }
    )

    assert result["work_item_count"] == 2
    assert result["executes_tool_calls"] is True
    assert result["captures_business_owner_approval"] is True
    assert result["queue_grants_closure"] is True
    assert result["scope_violations"] == [
        {
            "work_item_group": "manual_audit_review_execution_plan.execution_stages",
            "work_item_index": 0,
            "scope_key": "executes_tool_calls",
            "scope_value": True,
        },
        {
            "work_item_group": "manual_audit_review_execution_plan.execution_stages",
            "work_item_index": 1,
            "scope_key": "captures_business_owner_approval",
            "scope_value": True,
        },
        {
            "work_item_group": "manual_audit_review_execution_plan",
            "work_item_index": None,
            "scope_key": "queue_grants_closure",
            "scope_value": True,
        },
    ]


def test_data_catalog_page_catalog_date_lineage_review_queue_builds_business_owner_approval_execution_plan() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        plan = payload["business_owner_approval_execution_plan"]
        assert plan == {
            "scope": "business_owner_approval_dispatch_plan",
            "status": "business_owner_approval_required",
            "ready_page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
            "execution_stage_count": 2,
            "execution_stage_order": [
                "owner_approval_request_batches",
                "owner_approval_receipt_review_batches",
            ],
            "work_item_group_counts": {"record_remediation_work_items": 1},
            "approval_arguments": {"page_slugs": READY_FOR_AUDIT_PAGE_SLUGS},
            "execution_stages": [
                {
                    "stage": 1,
                    "stage_type": "owner_approval_request_batches",
                    "work_item_group": "record_remediation_work_items",
                    "work_item_count": 1,
                    "page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
                    "arguments": {"page_slugs": READY_FOR_AUDIT_PAGE_SLUGS},
                    "next_step": "prepare_owner_approval_request_after_manual_audit_review",
                    "uses_work_item_groups": ["record_remediation_work_items"],
                    "must_complete_before": ["owner_approval_receipt_review_batches"],
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                },
                {
                    "stage": 2,
                    "stage_type": "owner_approval_receipt_review_batches",
                    "work_item_group": "record_remediation_work_items",
                    "work_item_count": 1,
                    "page_count": len(READY_FOR_AUDIT_PAGE_SLUGS),
                    "arguments": {"page_slugs": READY_FOR_AUDIT_PAGE_SLUGS},
                    "next_step": "review_external_owner_approval_receipt_without_granting_closure",
                    "uses_work_item_groups": ["record_remediation_work_items"],
                    "must_complete_before": [],
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                },
            ],
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": False,
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_audits_business_owner_approval_execution_plan_scope() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["business_owner_approval_execution_plan_scope_audit"] == {
            "work_item_count": 2,
            "checked_work_item_group": "business_owner_approval_execution_plan.execution_stages",
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": False,
            "scope_violations": [],
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_business_owner_approval_execution_plan_scope_audit_flags_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_catalog_date_lineage_business_owner_approval_execution_plan_scope_audit(
        {
            "execution_stages": [
                {
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": True,
                    "approves_metric_or_page": False,
                },
                {
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": True,
                },
            ],
            "queue_grants_closure": True,
        }
    )

    assert result["work_item_count"] == 2
    assert result["captures_business_owner_approval"] is True
    assert result["approves_metric_or_page"] is True
    assert result["queue_grants_closure"] is True
    assert result["scope_violations"] == [
        {
            "work_item_group": "business_owner_approval_execution_plan.execution_stages",
            "work_item_index": 0,
            "scope_key": "captures_business_owner_approval",
            "scope_value": True,
        },
        {
            "work_item_group": "business_owner_approval_execution_plan.execution_stages",
            "work_item_index": 1,
            "scope_key": "approves_metric_or_page",
            "scope_value": True,
        },
        {
            "work_item_group": "business_owner_approval_execution_plan",
            "work_item_index": None,
            "scope_key": "queue_grants_closure",
            "scope_value": True,
        },
    ]


def test_data_catalog_page_catalog_date_lineage_review_queue_audits_queue_boundary() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        closure_readiness = payload["summary"]["closure_readiness"]
        queue_boundary_counts = payload["queue_boundary_audit"][
            "checked_scope_audit_work_item_counts"
        ]
        expected_counts = {
            "record_gap_execution_plan_scope_audit": payload[
                "record_gap_execution_plan_scope_audit"
            ]["work_item_count"],
            "record_remediation_scope_audit": payload[
                "record_remediation_scope_audit"
            ]["work_item_count"],
            "suggested_tool_call_scope_audit": payload[
                "suggested_tool_call_scope_audit"
            ]["work_item_count"],
            "evidence_collection_execution_plan_scope_audit": payload[
                "evidence_collection_execution_plan_scope_audit"
            ]["work_item_count"],
            "manual_audit_review_execution_plan_scope_audit": payload[
                "manual_audit_review_execution_plan_scope_audit"
            ]["work_item_count"],
            "business_owner_approval_execution_plan_scope_audit": payload[
                "business_owner_approval_execution_plan_scope_audit"
            ]["work_item_count"],
            "closure_blocker_scope_audit": payload["closure_blocker_scope_audit"][
                "work_item_count"
            ],
            "next_closure_action_scope_audit": closure_readiness.get(
                "next_closure_action_scope_audit",
                {"work_item_count": queue_boundary_counts["next_closure_action_scope_audit"]},
            )["work_item_count"],
            "closure_dispatch_packet_scope_audit": closure_readiness.get(
                "closure_dispatch_packet_scope_audit",
                {"work_item_count": queue_boundary_counts["closure_dispatch_packet_scope_audit"]},
            )["work_item_count"],
        }
        assert payload["queue_boundary_audit"] == {
            "work_item_count": sum(expected_counts.values()),
            "checked_scope_audits": [
                "record_gap_execution_plan_scope_audit",
                "record_remediation_scope_audit",
                "suggested_tool_call_scope_audit",
                "evidence_collection_execution_plan_scope_audit",
                "manual_audit_review_execution_plan_scope_audit",
                "business_owner_approval_execution_plan_scope_audit",
                "closure_blocker_scope_audit",
                "next_closure_action_scope_audit",
                "closure_dispatch_packet_scope_audit",
            ],
            "checked_scope_audit_work_item_counts": expected_counts,
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": False,
            "scope_violations": [],
            "suggested_tool_violations": [],
            "execution_target_violations": [],
            "packet_consistency_violations": [],
            "source_consistency_violations": [],
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_audits_closure_blockers() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["closure_blocker_scope_audit"] == {
            "work_item_count": 4,
            "checked_work_item_group": "closure_blocker_work_items",
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": False,
            "scope_violations": [],
            "execution_target_violations": [],
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_summarizes_closure_readiness() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        summary = payload["summary"]
        closure = summary["closure_readiness"]
        closure_blocker_work_items = payload["closure_blocker_work_items"]
        closure_blocker_breakdown = {
            item["blocker_type"]: {
                "page_count": item["page_count"],
                "work_item_count": item["work_item_count"],
            }
            for item in closure_blocker_work_items
        }
        closure_execution_sequence = closure["closure_execution_sequence"]

        assert closure["page_count"] == summary["page_count"]
        assert closure["ready_for_audit_review_count"] == summary["ready_for_audit_review_count"]
        assert closure["blocked_by_record_gaps_count"] == summary["blocked_by_record_gaps_count"]
        assert closure["record_remediation_work_item_count"] == payload["record_remediation_scope_audit"][
            "work_item_count"
        ]
        assert closure["suggested_tool_call_work_item_count"] == payload["suggested_tool_call_scope_audit"][
            "work_item_count"
        ]
        assert closure["closure_blocker_work_item_count"] == len(closure_blocker_work_items)
        assert closure["closure_blocker_work_item_breakdown"] == closure_blocker_breakdown
        assert closure["queue_boundary_work_item_count"] == payload["queue_boundary_audit"]["work_item_count"]
        assert closure["closure_approved_count"] == 0
        assert closure["closure_ready_count"] == 0
        assert closure["closure_blocked_count"] == closure["page_count"]
        assert closure["queue_grants_closure"] is False
        assert closure["status"] == "record_remediation_and_catalog_date_lineage_review_required"
        assert closure["residual_closure_requirements"] == [
            "record_gap_remediation",
            "catalog_date_lineage_evidence_collection",
            "manual_audit_review",
            "business_owner_approval",
        ]
        assert closure["next_closure_action"] == {
            "blocker_type": "record_gap_remediation",
            "next_step": "use_record_gap_execution_plan",
            "execution_plan": "record_gap_execution_plan",
            "execution_stage": "remediation_type_batches",
            "execution_stage_detail": payload["record_gap_execution_plan"]["execution_stages"][0],
            "page_count": payload["record_gap_execution_plan"]["blocked_page_count"],
            "work_item_count": payload["record_remediation_scope_audit"]["work_item_count"],
            "arguments": payload["record_gap_execution_plan"]["record_gap_arguments"],
            "must_complete_before": [
                "manual_audit_review",
                "business_owner_approval",
            ],
            **_expected_no_closure_scope_flags(),
        }
        assert closure["next_closure_action_scope_audit"] == _expected_clean_next_closure_action_scope_audit(1)
        dispatch_packet = closure["closure_dispatch_packet"]
        assert dispatch_packet["status"] == "record_remediation_and_catalog_date_lineage_review_required"
        assert dispatch_packet["dispatch_step_count"] == len(closure_execution_sequence)
        assert dispatch_packet["queue_grants_closure"] is False
        assert [
            step["blocker_type"] for step in dispatch_packet["dispatch_steps"]
        ] == [step["blocker_type"] for step in closure_execution_sequence]
        assert dispatch_packet["next_dispatch_step"] == dispatch_packet["dispatch_steps"][0]
        assert closure["closure_dispatch_packet_scope_audit"] == _expected_clean_closure_dispatch_packet_scope_audit(4)
        assert [
            step["blocker_type"] for step in closure_execution_sequence
        ] == closure["residual_closure_requirements"]
        for index, step in enumerate(closure_execution_sequence, start=1):
            work_item = next(
                item
                for item in closure_blocker_work_items
                if item["blocker_type"] == step["blocker_type"]
            )
            assert step["sequence"] == index
            assert step["next_step"] == work_item["next_step"]
            assert step["execution_plan"] == work_item["execution_plan"]
            assert step["execution_stage"] == work_item["execution_stage"]
            assert step["execution_stage_detail"] == work_item["execution_stage_detail"]
            assert step["page_count"] == work_item["page_count"]
            assert step["work_item_count"] == work_item["work_item_count"]
            assert step["source_work_item_group_counts"] == work_item["source_work_item_group_counts"]
            assert step["arguments"] == work_item["arguments"]
            assert step["queue_grants_closure"] is False
        assert any(
            row["page_slug"] == "kpi-performance"
            for row in payload["deferred_review_queue"]
        )
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_routes_closure_blockers() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        work_items = {
            item["blocker_type"]: item
            for item in payload["closure_blocker_work_items"]
        }

        assert list(work_items) == [
            "record_gap_remediation",
            "catalog_date_lineage_evidence_collection",
            "manual_audit_review",
            "business_owner_approval",
        ]
        record_gap_item = work_items["record_gap_remediation"]
        record_gap_plan = payload["record_gap_execution_plan"]
        assert record_gap_item["next_step"] == "use_record_gap_execution_plan"
        assert record_gap_item["execution_plan"] == "record_gap_execution_plan"
        assert record_gap_item["execution_stage"] == "remediation_type_batches"
        assert record_gap_item["execution_stage_detail"] == record_gap_plan["execution_stages"][0]
        assert record_gap_item["source_work_item_groups"] == [
            "record_remediation_work_items",
            "record_remediation_evidence_work_items",
            "record_remediation_review_lane_work_items",
        ]
        assert record_gap_item["source_work_item_group_counts"] == record_gap_plan["work_item_group_counts"]
        assert record_gap_item["page_count"] == record_gap_plan["blocked_page_count"]
        assert record_gap_item["work_item_count"] == payload["record_remediation_scope_audit"][
            "work_item_count"
        ]
        create_item = next(
            item
            for item in payload["record_remediation_work_items"]
            if item["remediation_type"] == "create_direct_record"
        )
        assert record_gap_item["page_ids"] == create_item["page_ids"]
        assert record_gap_item["page_slugs"] == record_gap_plan["record_gap_arguments"]["page_slugs"]
        assert record_gap_item["arguments"] == record_gap_plan["record_gap_arguments"]
        assert record_gap_item["writes_governance_records"] is False
        assert record_gap_item["executes_tool_calls"] is False
        assert record_gap_item["samples_duckdb_tables"] is False
        assert record_gap_item["checks_lineage_records"] is False
        assert record_gap_item["proves_page_execution"] is False
        assert record_gap_item["runs_ui_or_api_smoke"] is False
        assert record_gap_item["captures_business_owner_approval"] is False
        assert record_gap_item["approves_metric_or_page"] is False
        assert record_gap_item["queue_grants_closure"] is False
        assert "kpi-performance" not in record_gap_item["arguments"]["page_slugs"]

        catalog_item = work_items["catalog_date_lineage_evidence_collection"]
        evidence_plan = payload["evidence_collection_execution_plan"]
        assert catalog_item["next_step"] == "use_evidence_collection_execution_plan"
        assert catalog_item["execution_plan"] == "evidence_collection_execution_plan"
        assert catalog_item["execution_stage"] == "catalog_date_evidence_batches"
        assert catalog_item["execution_stage_detail"] == evidence_plan["execution_stages"][0]
        assert catalog_item["source_work_item_groups"] == ["suggested_tool_call_work_items"]
        assert catalog_item["source_work_item_group_counts"] == evidence_plan["work_item_group_counts"]
        assert catalog_item["page_count"] == evidence_plan["page_count"]
        assert catalog_item["work_item_count"] == payload["suggested_tool_call_scope_audit"][
            "work_item_count"
        ]
        assert "PAGE-PROD-CAT-001" in catalog_item["page_ids"]
        assert "PAGE-BOND-ANALYSIS-001" in catalog_item["page_ids"]
        assert "GAP-CROSS-ASSET-PAGE" in catalog_item["page_ids"]
        assert "PAGE-AGENT-001" in catalog_item["page_ids"]
        assert "GAP-KPI-PERFORMANCE-PAGE" in catalog_item["page_ids"]
        assert "product-category-pnl" in catalog_item["page_slugs"]
        assert "bond-analysis" in catalog_item["page_slugs"]
        assert "agent" in catalog_item["arguments"]["page_slugs"]
        assert "kpi-performance" in catalog_item["arguments"]["page_slugs"]
        assert catalog_item["executes_tool_calls"] is False
        assert catalog_item["samples_duckdb_tables"] is False
        assert catalog_item["checks_lineage_records"] is False
        assert catalog_item["approves_metric_or_page"] is False
        assert catalog_item["queue_grants_closure"] is False

        ready_page_ids = READY_FOR_AUDIT_PAGE_IDS
        ready_page_slugs = READY_FOR_AUDIT_PAGE_SLUGS
        assert work_items["manual_audit_review"]["page_ids"] == ready_page_ids
        assert work_items["manual_audit_review"]["page_slugs"] == ready_page_slugs
        assert work_items["manual_audit_review"]["arguments"] == {
            "page_slugs": ready_page_slugs,
        }
        assert work_items["manual_audit_review"]["page_count"] == len(ready_page_slugs)
        assert work_items["manual_audit_review"]["work_item_count"] == len(ready_page_slugs)
        assert work_items["manual_audit_review"]["next_step"] == (
            "use_manual_audit_review_execution_plan"
        )
        assert work_items["manual_audit_review"]["execution_plan"] == (
            "manual_audit_review_execution_plan"
        )
        assert work_items["manual_audit_review"]["execution_stage"] == (
            "audit_review_queue_batches"
        )
        assert work_items["manual_audit_review"]["source_work_item_group_counts"] == {
            "record_remediation_work_items": 2,
        }
        assert work_items["manual_audit_review"]["queue_grants_closure"] is False
        assert work_items["business_owner_approval"]["page_ids"] == ready_page_ids
        assert work_items["business_owner_approval"]["page_slugs"] == ready_page_slugs
        assert work_items["business_owner_approval"]["arguments"] == {
            "page_slugs": ready_page_slugs,
        }
        assert work_items["business_owner_approval"]["page_count"] == len(ready_page_slugs)
        assert work_items["business_owner_approval"]["work_item_count"] == len(ready_page_slugs)
        assert work_items["business_owner_approval"]["next_step"] == (
            "use_business_owner_approval_execution_plan"
        )
        assert work_items["business_owner_approval"]["execution_plan"] == (
            "business_owner_approval_execution_plan"
        )
        assert work_items["business_owner_approval"]["execution_stage"] == (
            "owner_approval_request_batches"
        )
        assert work_items["business_owner_approval"]["source_work_item_group_counts"] == {
            "record_remediation_work_items": 2,
        }
        assert work_items["business_owner_approval"]["captures_business_owner_approval"] is False
        assert work_items["business_owner_approval"]["approves_metric_or_page"] is False

        routing_index = payload["closure_blocker_routing_index"]
        assert list(routing_index) == [
            "record_gap_remediation",
            "catalog_date_lineage_evidence_collection",
            "manual_audit_review",
            "business_owner_approval",
        ]
        assert routing_index["record_gap_remediation"] == {
            "next_step": record_gap_item["next_step"],
            "execution_plan": record_gap_item["execution_plan"],
            "execution_stage": record_gap_item["execution_stage"],
            "execution_stage_detail": record_gap_item["execution_stage_detail"],
            "page_count": record_gap_item["page_count"],
            "work_item_count": record_gap_item["work_item_count"],
            "source_work_item_group_counts": record_gap_item["source_work_item_group_counts"],
            "arguments": {"page_slugs": record_gap_item["page_slugs"]},
            "queue_grants_closure": False,
        }
        assert routing_index["catalog_date_lineage_evidence_collection"] == {
            "next_step": catalog_item["next_step"],
            "execution_plan": catalog_item["execution_plan"],
            "execution_stage": catalog_item["execution_stage"],
            "execution_stage_detail": catalog_item["execution_stage_detail"],
            "page_count": catalog_item["page_count"],
            "work_item_count": catalog_item["work_item_count"],
            "source_work_item_group_counts": catalog_item["source_work_item_group_counts"],
            "arguments": {
                "page_slugs": catalog_item["page_slugs"],
            },
            "queue_grants_closure": False,
        }
        assert routing_index["manual_audit_review"]["arguments"] == {
            "page_slugs": ready_page_slugs,
        }
        assert routing_index["manual_audit_review"]["execution_plan"] == (
            "manual_audit_review_execution_plan"
        )
        assert routing_index["manual_audit_review"]["execution_stage"] == (
            "audit_review_queue_batches"
        )
        assert routing_index["manual_audit_review"]["execution_stage_detail"] == (
            work_items["manual_audit_review"]["execution_stage_detail"]
        )
        assert routing_index["manual_audit_review"]["queue_grants_closure"] is False
        assert routing_index["business_owner_approval"]["arguments"] == {
            "page_slugs": ready_page_slugs,
        }
        assert routing_index["business_owner_approval"]["execution_plan"] == (
            "business_owner_approval_execution_plan"
        )
        assert routing_index["business_owner_approval"]["execution_stage"] == (
            "owner_approval_request_batches"
        )
        assert routing_index["business_owner_approval"]["execution_stage_detail"] == (
            work_items["business_owner_approval"]["execution_stage_detail"]
        )
        assert routing_index["business_owner_approval"]["queue_grants_closure"] is False
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_closure_blocker_scope_audit_flags_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_catalog_date_lineage_closure_blocker_scope_audit(
        [
            {
                "blocker_type": "record_gap_remediation",
                "execution_plan": "record_remediation_work_items",
                "next_step": "use_record_remediation_work_items",
                "source_work_item_groups": ["record_remediation_work_items"],
                "execution_stage_detail": {
                    "stage_type": "record_remediation_work_items",
                    "work_item_group": "record_remediation_evidence_work_items",
                    "writes_governance_records": False,
                    "executes_tool_calls": True,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                    "queue_grants_closure": False,
                },
                "writes_governance_records": False,
                "executes_tool_calls": True,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
                "queue_grants_closure": False,
            }
        ]
    )

    assert result["work_item_count"] == 1
    assert result["executes_tool_calls"] is True
    assert result["runs_ui_or_api_smoke"] is False
    assert result["execution_target_violations"] == [
        {
            "work_item_group": "closure_blocker_work_items",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "execution_plan",
            "target_value": "record_remediation_work_items",
            "expected_value": "record_gap_execution_plan",
        },
        {
            "work_item_group": "closure_blocker_work_items",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "execution_stage",
            "target_value": None,
            "expected_value": "remediation_type_batches",
        },
        {
            "work_item_group": "closure_blocker_work_items",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "next_step",
            "target_value": "use_record_remediation_work_items",
            "expected_value": "use_record_gap_execution_plan",
        },
        {
            "work_item_group": "closure_blocker_work_items",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "execution_stage_detail.stage_type",
            "target_value": "record_remediation_work_items",
            "expected_value": "remediation_type_batches",
        },
        {
            "work_item_group": "closure_blocker_work_items",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "execution_stage_detail.work_item_group",
            "target_value": "record_remediation_evidence_work_items",
            "expected_value": "record_remediation_work_items",
        },
    ]
    assert result["scope_violations"] == [
        {
            "work_item_group": "closure_blocker_work_items",
            "work_item_index": 0,
            "scope_key": "executes_tool_calls",
            "scope_value": True,
        },
        {
            "work_item_group": "closure_blocker_work_items",
            "work_item_index": 0,
            "scope_key": "runs_ui_or_api_smoke",
            "scope_value": None,
        },
        {
            "work_item_group": "closure_blocker_work_items.execution_stage_detail",
            "work_item_index": 0,
            "scope_key": "executes_tool_calls",
            "scope_value": True,
        },
    ]


def test_data_catalog_page_catalog_date_lineage_next_closure_action_returns_none_without_residual_steps() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.page_catalog_date_lineage_next_closure_action([]) is None


def test_data_catalog_page_catalog_date_lineage_closure_dispatch_packet_handles_empty_sequence() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.page_catalog_date_lineage_closure_dispatch_packet(
        [],
        status="no_residual_closure_requirements",
    ) == {
        "scope": "catalog_date_lineage_closure_dispatch_packet",
        "status": "no_residual_closure_requirements",
        "dispatch_step_count": 0,
        "next_dispatch_step": None,
        "dispatch_steps": [],
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
        "queue_grants_closure": False,
    }


def test_data_catalog_page_catalog_date_lineage_closure_dispatch_packet_scope_audit_flags_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_catalog_date_lineage_closure_dispatch_packet_scope_audit(
        {
            "dispatch_step_count": 99,
            "next_dispatch_step": {
                "blocker_type": "manual_audit_review",
                "dispatch_action": "use_manual_audit_review_execution_plan",
                "execution_plan": "manual_audit_review_execution_plan",
                "execution_stage": "audit_review_queue_batches",
            },
            "dispatch_steps": [
                {
                    "sequence": 42,
                    "blocker_type": "record_gap_remediation",
                    "dispatch_action": "use_record_remediation_work_items",
                    "execution_plan": "record_remediation_work_items",
                    "execution_stage": "record_remediation_work_items",
                    "source_work_item_group_counts": {
                        "record_remediation_work_items": 1,
                    },
                    "execution_stage_detail": {
                        "stage_type": "record_remediation_work_items",
                        "work_item_group": "record_remediation_evidence_work_items",
                    },
                    "writes_governance_records": False,
                    "executes_tool_calls": True,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                    "queue_grants_closure": False,
                },
                {
                    "sequence": 2,
                    "blocker_type": "manual_audit_review",
                    "dispatch_action": "use_manual_audit_review_execution_plan",
                    "execution_plan": "manual_audit_review_execution_plan",
                    "execution_stage": "audit_review_queue_batches",
                    "source_work_item_group_counts": {
                        "record_remediation_work_items": 1,
                    },
                    "execution_stage_detail": {
                        "stage_type": "audit_review_queue_batches",
                        "work_item_group": "record_remediation_work_items",
                    },
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": None,
                    "queue_grants_closure": False,
                },
            ],
            "writes_governance_records": True,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": True,
        }
    )

    assert result["work_item_count"] == 2
    assert result["checked_work_item_group"] == "closure_dispatch_packet.dispatch_steps"
    assert result["writes_governance_records"] is True
    assert result["executes_tool_calls"] is True
    assert result["approves_metric_or_page"] is False
    assert result["queue_grants_closure"] is True
    assert result["packet_consistency_violations"] == [
        {
            "packet_key": "dispatch_step_count",
            "expected_key": "len(dispatch_steps)",
            "packet_value": 99,
            "expected_value": 2,
        },
        {
            "packet_key": "next_dispatch_step",
            "expected_key": "dispatch_steps[0]",
            "packet_value": {
                "blocker_type": "manual_audit_review",
                "dispatch_action": "use_manual_audit_review_execution_plan",
                "execution_plan": "manual_audit_review_execution_plan",
                "execution_stage": "audit_review_queue_batches",
            },
            "expected_value": {
                "blocker_type": "record_gap_remediation",
                "sequence": 42,
                "dispatch_action": "use_record_remediation_work_items",
                "execution_plan": "record_remediation_work_items",
                "execution_stage": "record_remediation_work_items",
                "source_work_item_group_counts": {
                    "record_remediation_work_items": 1,
                },
                "execution_stage_detail": {
                    "stage_type": "record_remediation_work_items",
                    "work_item_group": "record_remediation_evidence_work_items",
                },
                "writes_governance_records": False,
                "executes_tool_calls": True,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
                "queue_grants_closure": False,
            },
        },
        {
            "packet_key": "dispatch_steps[0].sequence",
            "expected_key": "1-based dispatch step index",
            "packet_value": 42,
            "expected_value": 1,
        },
    ]
    assert result["execution_target_violations"] == [
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "execution_plan",
            "target_value": "record_remediation_work_items",
            "expected_value": "record_gap_execution_plan",
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "execution_stage",
            "target_value": "record_remediation_work_items",
            "expected_value": "remediation_type_batches",
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "dispatch_action",
            "target_value": "use_record_remediation_work_items",
            "expected_value": "use_record_gap_execution_plan",
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "execution_stage_detail.stage_type",
            "target_value": "record_remediation_work_items",
            "expected_value": "remediation_type_batches",
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "execution_stage_detail.work_item_group",
            "target_value": "record_remediation_evidence_work_items",
            "expected_value": "record_remediation_work_items",
        },
    ]
    assert result["scope_violations"] == [
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "scope_key": "executes_tool_calls",
            "scope_value": True,
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 1,
            "scope_key": "approves_metric_or_page",
            "scope_value": None,
        },
        {
            "work_item_group": "closure_dispatch_packet",
            "work_item_index": None,
            "scope_key": "writes_governance_records",
            "scope_value": True,
        },
        {
            "work_item_group": "closure_dispatch_packet",
            "work_item_index": None,
            "scope_key": "queue_grants_closure",
            "scope_value": True,
        },
    ]


def test_data_catalog_page_catalog_date_lineage_closure_dispatch_packet_scope_audit_flags_source_sequence_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    closure_execution_sequence = _expected_all_seeded_closure_execution_sequence()
    dispatch_packet = _expected_closure_dispatch_packet(
        closure_execution_sequence,
        status="blocked_by_record_gaps",
    )
    dispatch_packet["dispatch_steps"][0]["sequence"] = 99
    dispatch_packet["dispatch_steps"][0]["blocker_type"] = "manual_audit_review"
    dispatch_packet["dispatch_steps"][0]["execution_stage_detail"] = {
        **closure_execution_sequence[0]["execution_stage_detail"],
        "work_item_count": 99,
    }
    dispatch_packet["dispatch_steps"][0]["page_count"] = 99
    dispatch_packet["dispatch_steps"][0]["work_item_count"] = 88
    dispatch_packet["dispatch_steps"][0]["arguments"] = {"page_slugs": ["wrong-page"]}
    dispatch_packet["dispatch_steps"][0]["source_work_item_group_counts"] = {
        "record_remediation_work_items": 99,
        "record_remediation_evidence_work_items": 4,
        "record_remediation_review_lane_work_items": 7,
    }
    dispatch_packet["dispatch_steps"][0]["must_complete_before"] = [
        "business_owner_approval",
    ]

    result = module.page_catalog_date_lineage_closure_dispatch_packet_scope_audit(
        dispatch_packet,
        closure_execution_sequence=closure_execution_sequence,
    )

    assert result["source_consistency_violations"] == [
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "packet_key": "dispatch_steps[0].sequence",
            "expected_key": "closure_execution_sequence[0].sequence",
            "packet_value": 99,
            "expected_value": 1,
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "packet_key": "dispatch_steps[0].blocker_type",
            "expected_key": "closure_execution_sequence[0].blocker_type",
            "packet_value": "manual_audit_review",
            "expected_value": "record_gap_remediation",
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "packet_key": "dispatch_steps[0].execution_stage_detail",
            "expected_key": "closure_execution_sequence[0].execution_stage_detail",
            "packet_value": {
                **closure_execution_sequence[0]["execution_stage_detail"],
                "work_item_count": 99,
            },
            "expected_value": closure_execution_sequence[0]["execution_stage_detail"],
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "packet_key": "dispatch_steps[0].page_count",
            "expected_key": "closure_execution_sequence[0].page_count",
            "packet_value": 99,
            "expected_value": len(CATALOG_DATE_RECORD_GAP_PAGE_SLUGS),
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "packet_key": "dispatch_steps[0].work_item_count",
            "expected_key": "closure_execution_sequence[0].work_item_count",
            "packet_value": 88,
            "expected_value": closure_execution_sequence[0]["work_item_count"],
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "packet_key": "dispatch_steps[0].arguments",
            "expected_key": "closure_execution_sequence[0].arguments",
            "packet_value": {"page_slugs": ["wrong-page"]},
            "expected_value": closure_execution_sequence[0]["arguments"],
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "packet_key": "dispatch_steps[0].source_work_item_group_counts",
            "expected_key": "closure_execution_sequence[0].source_work_item_group_counts",
            "packet_value": {
                "record_remediation_work_items": 99,
                "record_remediation_evidence_work_items": 4,
                "record_remediation_review_lane_work_items": 7,
            },
            "expected_value": closure_execution_sequence[0]["source_work_item_group_counts"],
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "packet_key": "dispatch_steps[0].must_complete_before",
            "expected_key": "closure_execution_sequence[0].must_complete_before",
            "packet_value": ["business_owner_approval"],
            "expected_value": [
                "manual_audit_review",
                "business_owner_approval",
            ],
        },
    ]


def test_data_catalog_page_catalog_date_lineage_closure_dispatch_packet_scope_audit_flags_missing_source_step() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    closure_execution_sequence = _expected_all_seeded_closure_execution_sequence()
    dispatch_packet = _expected_closure_dispatch_packet(
        closure_execution_sequence,
        status="blocked_by_record_gaps",
    )
    dispatch_packet["dispatch_steps"] = dispatch_packet["dispatch_steps"][:-1]
    dispatch_packet["dispatch_step_count"] = len(dispatch_packet["dispatch_steps"])
    dispatch_packet["next_dispatch_step"] = dispatch_packet["dispatch_steps"][0]

    result = module.page_catalog_date_lineage_closure_dispatch_packet_scope_audit(
        dispatch_packet,
        closure_execution_sequence=closure_execution_sequence,
    )

    assert result["packet_consistency_violations"] == []
    assert result["source_consistency_violations"] == [
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": None,
            "packet_key": "len(dispatch_steps)",
            "expected_key": "len(closure_execution_sequence)",
            "packet_value": 3,
            "expected_value": 4,
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 3,
            "packet_key": "dispatch_steps[3]",
            "expected_key": "closure_execution_sequence[3]",
            "packet_value": None,
            "expected_value": closure_execution_sequence[3],
        },
    ]


def test_data_catalog_page_catalog_date_lineage_queue_boundary_audit_flags_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_catalog_date_lineage_queue_boundary_audit(
        {
            "record_gap_execution_plan_scope_audit": {
                "work_item_count": 1,
                "writes_governance_records": False,
                "executes_tool_calls": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
                "queue_grants_closure": False,
                "scope_violations": [],
            },
            "record_remediation_scope_audit": {
                "work_item_count": 1,
                "writes_governance_records": True,
                "executes_tool_calls": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
                "scope_violations": [
                    {
                        "work_item_group": "record_remediation_work_items",
                        "work_item_index": 0,
                        "scope_key": "writes_governance_records",
                        "scope_value": True,
                    }
                ],
                "suggested_tool_call_violations": [
                    {
                        "work_item_group": "record_remediation_work_items",
                        "work_item_index": 0,
                        "suggested_tool_call_index": 0,
                        "tool": "moss-lineage-evidence.preflight_page_governance_record",
                    }
                ],
            },
            "suggested_tool_call_scope_audit": {
                "work_item_count": 1,
                "executes_tool_call": True,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "approves_metric_or_page": False,
                "scope_violations": [
                    {
                        "work_item_group": "suggested_tool_call_work_items",
                        "work_item_index": 0,
                        "scope_key": "executes_tool_call",
                        "scope_value": True,
                    }
                ],
                "suggested_tool_violations": [
                    {
                        "work_item_group": "suggested_tool_call_work_items",
                        "work_item_index": 0,
                        "tool": "moss-lineage-evidence.preflight_page_governance_record",
                    }
                ],
            },
            "closure_blocker_scope_audit": {
                "work_item_count": 1,
                "writes_governance_records": False,
                "executes_tool_calls": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
                "queue_grants_closure": False,
                "scope_violations": [
                    {
                        "work_item_group": "closure_blocker_work_items.execution_stage_detail",
                        "work_item_index": 0,
                        "scope_key": "executes_tool_calls",
                        "scope_value": True,
                    }
                ],
                "execution_target_violations": [
                    {
                        "work_item_group": "closure_blocker_work_items",
                        "work_item_index": 0,
                        "blocker_type": "record_gap_remediation",
                        "target_key": "execution_stage",
                        "target_value": "record_remediation_work_items",
                        "expected_value": "remediation_type_batches",
                    },
                    {
                        "work_item_group": "closure_blocker_work_items",
                        "work_item_index": 0,
                        "blocker_type": "record_gap_remediation",
                        "target_key": "next_step",
                        "target_value": "use_record_remediation_work_items",
                        "expected_value": "use_record_gap_execution_plan",
                    },
                ],
            },
            "next_closure_action_scope_audit": {
                "work_item_count": 1,
                "writes_governance_records": False,
                "executes_tool_calls": True,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
                "queue_grants_closure": True,
                "scope_violations": [
                    {
                        "work_item_group": "closure_readiness.next_closure_action",
                        "work_item_index": None,
                        "scope_key": "executes_tool_calls",
                        "scope_value": True,
                    },
                    {
                        "work_item_group": "closure_readiness.next_closure_action",
                        "work_item_index": None,
                        "scope_key": "queue_grants_closure",
                        "scope_value": True,
                    },
                ],
                "execution_target_violations": [
                    {
                        "work_item_group": "closure_readiness.next_closure_action",
                        "work_item_index": None,
                        "blocker_type": "record_gap_remediation",
                        "target_key": "next_step",
                        "target_value": "use_record_remediation_work_items",
                        "expected_value": "use_record_gap_execution_plan",
                    }
                ],
                "source_consistency_violations": [
                    {
                        "work_item_group": "closure_readiness.next_closure_action",
                        "work_item_index": None,
                "action_key": "next_closure_action.page_count",
                "expected_key": "closure_execution_sequence[0].page_count",
                "action_value": 99,
                "expected_value": len(CATALOG_DATE_RECORD_GAP_PAGE_SLUGS),
            }
                ],
            },
            "closure_dispatch_packet_scope_audit": {
                "work_item_count": 1,
                "writes_governance_records": False,
                "executes_tool_calls": True,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
                "queue_grants_closure": True,
                "scope_violations": [
                    {
                        "work_item_group": "closure_dispatch_packet.dispatch_steps",
                        "work_item_index": 0,
                        "scope_key": "executes_tool_calls",
                        "scope_value": True,
                    },
                    {
                        "work_item_group": "closure_dispatch_packet",
                        "work_item_index": None,
                        "scope_key": "queue_grants_closure",
                        "scope_value": True,
                    },
                ],
            "execution_target_violations": [
                {
                    "work_item_group": "closure_dispatch_packet.dispatch_steps",
                    "work_item_index": 0,
                    "blocker_type": "record_gap_remediation",
                    "target_key": "dispatch_action",
                    "target_value": "use_record_remediation_work_items",
                    "expected_value": "use_record_gap_execution_plan",
                }
            ],
                "packet_consistency_violations": [
                    {
                        "packet_key": "dispatch_step_count",
                        "expected_key": "len(dispatch_steps)",
                        "packet_value": 99,
                        "expected_value": 1,
                    },
                    {
                        "packet_key": "next_dispatch_step",
                        "expected_key": "dispatch_steps[0]",
                        "packet_value": {"blocker_type": "manual_audit_review"},
                        "expected_value": {"blocker_type": "record_gap_remediation"},
                    },
                    {
                        "packet_key": "dispatch_steps[0].sequence",
                        "expected_key": "1-based dispatch step index",
                        "packet_value": 42,
                        "expected_value": 1,
                    }
                ],
                "source_consistency_violations": [
                    {
                        "work_item_group": "closure_dispatch_packet.dispatch_steps",
                        "work_item_index": None,
                        "packet_key": "len(dispatch_steps)",
                        "expected_key": "len(closure_execution_sequence)",
                        "packet_value": 3,
                        "expected_value": 4,
                    },
                    {
                        "work_item_group": "closure_dispatch_packet.dispatch_steps",
                        "work_item_index": 0,
                        "packet_key": "dispatch_steps[0].page_count",
                        "expected_key": "closure_execution_sequence[0].page_count",
                        "packet_value": 99,
                        "expected_value": len(CATALOG_DATE_RECORD_GAP_PAGE_SLUGS),
                    }
                ],
            },
        }
    )

    assert result["work_item_count"] == 6
    assert result["checked_scope_audit_work_item_counts"] == {
        "record_gap_execution_plan_scope_audit": 1,
        "record_remediation_scope_audit": 1,
        "suggested_tool_call_scope_audit": 1,
        "evidence_collection_execution_plan_scope_audit": 0,
        "manual_audit_review_execution_plan_scope_audit": 0,
        "business_owner_approval_execution_plan_scope_audit": 0,
        "closure_blocker_scope_audit": 1,
        "next_closure_action_scope_audit": 1,
        "closure_dispatch_packet_scope_audit": 1,
    }
    assert result["writes_governance_records"] is True
    assert result["executes_tool_calls"] is True
    assert result["queue_grants_closure"] is True
    assert result["scope_violations"] == [
        {
            "work_item_group": "record_remediation_work_items",
            "work_item_index": 0,
            "scope_key": "writes_governance_records",
            "scope_value": True,
            "scope_audit": "record_remediation_scope_audit",
        },
        {
            "work_item_group": "suggested_tool_call_work_items",
            "work_item_index": 0,
            "scope_key": "executes_tool_call",
            "scope_value": True,
            "scope_audit": "suggested_tool_call_scope_audit",
        },
        {
            "work_item_group": "closure_blocker_work_items.execution_stage_detail",
            "work_item_index": 0,
            "scope_key": "executes_tool_calls",
            "scope_value": True,
            "scope_audit": "closure_blocker_scope_audit",
        },
        {
            "work_item_group": "closure_readiness.next_closure_action",
            "work_item_index": None,
            "scope_key": "executes_tool_calls",
            "scope_value": True,
            "scope_audit": "next_closure_action_scope_audit",
        },
        {
            "work_item_group": "closure_readiness.next_closure_action",
            "work_item_index": None,
            "scope_key": "queue_grants_closure",
            "scope_value": True,
            "scope_audit": "next_closure_action_scope_audit",
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "scope_key": "executes_tool_calls",
            "scope_value": True,
            "scope_audit": "closure_dispatch_packet_scope_audit",
        },
        {
            "work_item_group": "closure_dispatch_packet",
            "work_item_index": None,
            "scope_key": "queue_grants_closure",
            "scope_value": True,
            "scope_audit": "closure_dispatch_packet_scope_audit",
        },
    ]
    assert result["suggested_tool_violations"] == [
        {
            "work_item_group": "record_remediation_work_items",
            "work_item_index": 0,
            "suggested_tool_call_index": 0,
            "tool": "moss-lineage-evidence.preflight_page_governance_record",
            "scope_audit": "record_remediation_scope_audit",
        },
        {
            "work_item_group": "suggested_tool_call_work_items",
            "work_item_index": 0,
            "tool": "moss-lineage-evidence.preflight_page_governance_record",
            "scope_audit": "suggested_tool_call_scope_audit",
        },
    ]
    assert result["execution_target_violations"] == [
        {
            "work_item_group": "closure_blocker_work_items",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "execution_stage",
            "target_value": "record_remediation_work_items",
            "expected_value": "remediation_type_batches",
            "scope_audit": "closure_blocker_scope_audit",
        },
        {
            "work_item_group": "closure_blocker_work_items",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "next_step",
            "target_value": "use_record_remediation_work_items",
            "expected_value": "use_record_gap_execution_plan",
            "scope_audit": "closure_blocker_scope_audit",
        },
        {
            "work_item_group": "closure_readiness.next_closure_action",
            "work_item_index": None,
            "blocker_type": "record_gap_remediation",
            "target_key": "next_step",
            "target_value": "use_record_remediation_work_items",
            "expected_value": "use_record_gap_execution_plan",
            "scope_audit": "next_closure_action_scope_audit",
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "blocker_type": "record_gap_remediation",
            "target_key": "dispatch_action",
            "target_value": "use_record_remediation_work_items",
            "expected_value": "use_record_gap_execution_plan",
            "scope_audit": "closure_dispatch_packet_scope_audit",
        },
    ]
    assert result["packet_consistency_violations"] == [
        {
            "packet_key": "dispatch_step_count",
            "expected_key": "len(dispatch_steps)",
            "packet_value": 99,
            "expected_value": 1,
            "scope_audit": "closure_dispatch_packet_scope_audit",
        },
        {
            "packet_key": "next_dispatch_step",
            "expected_key": "dispatch_steps[0]",
            "packet_value": {"blocker_type": "manual_audit_review"},
            "expected_value": {"blocker_type": "record_gap_remediation"},
            "scope_audit": "closure_dispatch_packet_scope_audit",
        },
        {
            "packet_key": "dispatch_steps[0].sequence",
            "expected_key": "1-based dispatch step index",
            "packet_value": 42,
            "expected_value": 1,
            "scope_audit": "closure_dispatch_packet_scope_audit",
        }
    ]
    assert result["source_consistency_violations"] == [
        {
            "work_item_group": "closure_readiness.next_closure_action",
            "work_item_index": None,
            "action_key": "next_closure_action.page_count",
            "expected_key": "closure_execution_sequence[0].page_count",
            "action_value": 99,
            "expected_value": len(CATALOG_DATE_RECORD_GAP_PAGE_SLUGS),
            "scope_audit": "next_closure_action_scope_audit",
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": None,
            "packet_key": "len(dispatch_steps)",
            "expected_key": "len(closure_execution_sequence)",
            "packet_value": 3,
            "expected_value": 4,
            "scope_audit": "closure_dispatch_packet_scope_audit",
        },
        {
            "work_item_group": "closure_dispatch_packet.dispatch_steps",
            "work_item_index": 0,
            "packet_key": "dispatch_steps[0].page_count",
            "expected_key": "closure_execution_sequence[0].page_count",
            "packet_value": 99,
            "expected_value": len(CATALOG_DATE_RECORD_GAP_PAGE_SLUGS),
            "scope_audit": "closure_dispatch_packet_scope_audit",
        }
    ]


def test_data_catalog_page_catalog_date_lineage_review_queue_groups_record_remediation_work_items() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        work_items = payload["record_remediation_work_items"]
        assert [item["remediation_type"] for item in work_items] == [
            "create_direct_record",
            "none",
        ]

        create_item = work_items[0]
        assert create_item["work_item_count"] == len(create_item["page_ids"])
        assert sorted(create_item["page_ids"]) == sorted(
            row["page_id"]
            for row in payload["review_queue"] + payload["deferred_review_queue"]
            if row["record_remediation"]["remediation_type"] == "create_direct_record"
        )
        assert create_item["next_step"] == "collect_direct_page_api_record_evidence_then_preflight_candidate"
        assert create_item["arguments"] == {
            "page_slugs": create_item["page_slugs"],
        }
        assert "GAP-KPI-PERFORMANCE-PAGE" not in create_item["page_ids"]
        assert "kpi-performance" not in create_item["page_slugs"]
        assert create_item["suggested_tool_calls"] == [
            {
                "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
                "arguments": create_item["arguments"],
            },
            {
                "tool": "moss-lineage-evidence.get_page_governance_record_blueprint_queue",
                "arguments": create_item["arguments"],
            },
        ]
        assert create_item["suggested_tool_call_count"] == 2
        assert create_item["suggested_tool_names"] == [
            "moss-lineage-evidence.get_page_governance_record_requirements",
            "moss-lineage-evidence.get_page_governance_record_blueprint_queue",
        ]

        ready_item = work_items[1]
        assert ready_item["remediation_type"] == "none"
        assert ready_item["next_step"] == "manual_audit_review"
        assert ready_item["approval_boundary"] == "review_routing_only"
        assert sorted(ready_item["page_ids"]) == sorted(
            row["page_id"]
            for row in payload["review_queue"] + payload["deferred_review_queue"]
            if row["record_remediation"]["remediation_type"] == "none"
        )
        assert ready_item["page_ids"] == READY_FOR_AUDIT_PAGE_IDS
        assert ready_item["suggested_tool_calls"] == [
            {
                "tool": "moss-lineage-evidence.get_page_governance_audit_review_queue",
                "arguments": ready_item["arguments"],
            },
            {
                "tool": "moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue",
                "arguments": ready_item["arguments"],
            },
        ]
        assert ready_item["suggested_tool_call_count"] == 2
        assert ready_item["suggested_tool_names"] == [
            "moss-lineage-evidence.get_page_governance_audit_review_queue",
            "moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue",
        ]

        assert all(item["executes_tool_calls"] is False for item in work_items)
        assert all(item["writes_governance_records"] is False for item in work_items)
        assert all(item["samples_duckdb_tables"] is False for item in work_items)
        assert all(item["proves_page_execution"] is False for item in work_items)
        assert all(item["runs_ui_or_api_smoke"] is False for item in work_items)
        assert all(item["captures_business_owner_approval"] is False for item in work_items)
        assert all(item["approves_metric_or_page"] is False for item in work_items)
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_builds_record_gap_execution_plan() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        plan = payload["record_gap_execution_plan"]
        record_gap_page_slugs = plan["record_gap_arguments"]["page_slugs"]
        expected_group_counts = {
            "record_remediation_work_items": len(payload["record_remediation_work_items"]),
            "record_remediation_evidence_work_items": len(
                payload["record_remediation_evidence_work_items"]
            ),
            "record_remediation_review_lane_work_items": len(
                payload["record_remediation_review_lane_work_items"]
            ),
        }
        review_lane_record_gap_page_slugs: list[str] = []
        for item in payload["record_remediation_review_lane_work_items"]:
            if item["remediation_type"] == "none":
                continue
            for page_slug in item["page_slugs"]:
                if page_slug not in review_lane_record_gap_page_slugs:
                    review_lane_record_gap_page_slugs.append(page_slug)
        assert plan["scope"] == "record_gap_remediation_dispatch_plan"
        assert plan["status"] == "record_gap_remediation_required"
        assert plan["blocked_page_count"] == len(record_gap_page_slugs)
        assert plan["ready_manual_review_page_count"] == len(READY_FOR_AUDIT_PAGE_SLUGS)
        assert plan["execution_stage_order"] == [
            "remediation_type_batches",
            "evidence_key_batches",
            "review_lane_batches",
        ]
        assert plan["work_item_group_counts"] == expected_group_counts
        assert plan["suggested_tool_call_count"] == payload["record_remediation_scope_audit"][
            "suggested_tool_call_count"
        ]
        assert plan["record_gap_arguments"] == {"page_slugs": record_gap_page_slugs}
        assert [
            (
                stage["stage_type"],
                stage["work_item_group"],
                stage["work_item_count"],
                stage["page_count"],
                stage["record_gap_page_count"],
                stage["suggested_tool_call_count"],
            )
            for stage in plan["execution_stages"]
        ] == [
            (
                "remediation_type_batches",
                "record_remediation_work_items",
                expected_group_counts["record_remediation_work_items"],
                len(record_gap_page_slugs),
                len(record_gap_page_slugs),
                payload["record_remediation_scope_audit"]["suggested_tool_call_count"],
            ),
            (
                "evidence_key_batches",
                "record_remediation_evidence_work_items",
                expected_group_counts["record_remediation_evidence_work_items"],
                len(record_gap_page_slugs),
                len(record_gap_page_slugs),
                0,
            ),
            (
                "review_lane_batches",
                "record_remediation_review_lane_work_items",
                expected_group_counts["record_remediation_review_lane_work_items"],
                len(record_gap_page_slugs),
                len(record_gap_page_slugs),
                0,
            ),
        ]
        assert plan["execution_stages"][0]["arguments"] == {
            "page_slugs": record_gap_page_slugs,
        }
        assert plan["execution_stages"][1]["arguments"] == {
            "page_slugs": record_gap_page_slugs,
        }
        assert plan["execution_stages"][2]["arguments"] == {
            "page_slugs": review_lane_record_gap_page_slugs,
        }
        assert "kpi-performance" not in plan["record_gap_arguments"]["page_slugs"]
        assert "kpi-performance" not in plan["execution_stages"][2]["arguments"]["page_slugs"]
        assert plan["queue_grants_closure"] is False
        assert all(stage["writes_governance_records"] is False for stage in plan["execution_stages"])
        assert all(stage["executes_tool_calls"] is False for stage in plan["execution_stages"])
        assert all(stage["proves_page_execution"] is False for stage in plan["execution_stages"])
        assert all(stage["approves_metric_or_page"] is False for stage in plan["execution_stages"])
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_audits_record_gap_execution_plan_scope() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["record_gap_execution_plan_scope_audit"] == {
            "work_item_count": 3,
            "checked_work_item_group": "record_gap_execution_plan.execution_stages",
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": False,
            "scope_violations": [],
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_record_gap_execution_plan_scope_audit_flags_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_catalog_date_lineage_record_gap_execution_plan_scope_audit(
        {
            "execution_stages": [
                {
                    "writes_governance_records": False,
                    "executes_tool_calls": True,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                },
                {
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                },
            ],
            "queue_grants_closure": True,
        }
    )

    assert result["work_item_count"] == 2
    assert result["executes_tool_calls"] is True
    assert result["queue_grants_closure"] is True
    assert result["scope_violations"] == [
        {
            "work_item_group": "record_gap_execution_plan.execution_stages",
            "work_item_index": 0,
            "scope_key": "executes_tool_calls",
            "scope_value": True,
        },
        {
            "work_item_group": "record_gap_execution_plan",
            "work_item_index": None,
            "scope_key": "queue_grants_closure",
            "scope_value": True,
        },
    ]


def test_data_catalog_page_catalog_date_lineage_review_queue_groups_record_remediation_evidence_work_items() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        work_items = payload["record_remediation_evidence_work_items"]
        assert [item["evidence_key"] for item in work_items] == [
            "configured_or_deferred_table_anchors",
            "direct_page_or_primary_api_anchor",
            "page_api_execution_identifier",
            "required_record_fields",
        ]

        by_key = {item["evidence_key"]: item for item in work_items}
        execution_identifier = by_key["page_api_execution_identifier"]
        expected_record_gap_page_ids = execution_identifier["page_ids"]
        queue_create_page_ids = [
            row["page_id"]
            for row in payload["review_queue"] + payload["deferred_review_queue"]
            if row["record_remediation"]["remediation_type"] == "create_direct_record"
        ]
        assert execution_identifier["work_item_count"] == len(expected_record_gap_page_ids)
        assert execution_identifier["remediation_types"] == ["create_direct_record"]
        assert execution_identifier["next_steps"] == [
            "collect_direct_page_api_record_evidence_then_preflight_candidate",
        ]
        assert set(execution_identifier["page_ids"]) == set(queue_create_page_ids)
        assert set(by_key["direct_page_or_primary_api_anchor"]["page_ids"]) == set(queue_create_page_ids)
        assert "GAP-KPI-PERFORMANCE-PAGE" not in execution_identifier["page_ids"]

        assert all(item["writes_governance_records"] is False for item in work_items)
        assert all(item["executes_tool_calls"] is False for item in work_items)
        assert all(item["samples_duckdb_tables"] is False for item in work_items)
        assert all(item["checks_lineage_records"] is False for item in work_items)
        assert all(item["proves_page_execution"] is False for item in work_items)
        assert all(item["runs_ui_or_api_smoke"] is False for item in work_items)
        assert all(item["captures_business_owner_approval"] is False for item in work_items)
        assert all(item["approves_metric_or_page"] is False for item in work_items)
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_groups_record_remediation_by_lane() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        work_items = payload["record_remediation_review_lane_work_items"]
        queue_rows = payload["review_queue"] + payload["deferred_review_queue"]
        assert {
            (item["review_lane"], item["remediation_type"])
            for item in work_items
        } == {
            (
                row["review_lane"],
                row["record_remediation"]["remediation_type"],
            )
            for row in queue_rows
        }
        for item in work_items:
            matching_rows = [
                row
                for row in queue_rows
                if row["review_lane"] == item["review_lane"]
                and row["record_remediation"]["remediation_type"] == item["remediation_type"]
            ]
            assert item["work_item_count"] == len(matching_rows)
            assert item["page_ids"] == [row["page_id"] for row in matching_rows]
            assert item["page_slugs"] == [row["page_slug"] for row in matching_rows]
            assert item["arguments"] == {
                "page_slugs": [row["page_slug"] for row in matching_rows]
            }

        by_lane_type = {
            (item["review_lane"], item["remediation_type"]): item
            for item in work_items
        }
        formal_create = by_lane_type[
            ("formal_governed_catalog_date_lineage_review", "create_direct_record")
        ]
        assert formal_create["page_ids"] == [
            "PAGE-PNL-001",
            "PAGE-BRIDGE-001",
        ]
        assert formal_create["next_steps"] == [
            "collect_direct_page_api_record_evidence_then_preflight_candidate",
        ]

        candidate_create = by_lane_type[
            ("candidate_formal_source_mixed_review", "create_direct_record")
        ]
        assert candidate_create["page_ids"] == [
            row["page_id"]
            for row in queue_rows
            if row["review_lane"] == "candidate_formal_source_mixed_review"
            and row["record_remediation"]["remediation_type"] == "create_direct_record"
        ]
        assert candidate_create["evidence_to_collect"] == [
            "direct_page_or_primary_api_anchor",
            "required_record_fields",
            "page_api_execution_identifier",
            "configured_or_deferred_table_anchors",
        ]

        candidate_or_mixed_create = by_lane_type[
            ("candidate_or_mixed_catalog_date_lineage_review", "create_direct_record")
        ]
        assert candidate_or_mixed_create["page_ids"] == [
            row["page_id"]
            for row in queue_rows
            if row["review_lane"] == "candidate_or_mixed_catalog_date_lineage_review"
            and row["record_remediation"]["remediation_type"] == "create_direct_record"
        ]
        stock_row = next(row for row in queue_rows if row["page_id"] == "GAP-STOCK-ANALYSIS-PAGE")
        stock_create = by_lane_type[
            (stock_row["review_lane"], stock_row["record_remediation"]["remediation_type"])
        ]
        assert "GAP-STOCK-ANALYSIS-PAGE" in stock_create["page_ids"]
        assert "stock-analysis" in stock_create["page_slugs"]
        assert stock_row["approval_status"] == "gap_or_observational"

        deferred_create = by_lane_type[
            ("deferred_no_direct_table_config_review", "create_direct_record")
        ]
        assert deferred_create["page_ids"] == [
            row["page_id"]
            for row in queue_rows
            if row["review_lane"] == "deferred_no_direct_table_config_review"
            and row["record_remediation"]["remediation_type"] == "create_direct_record"
        ]
        assert "kpi-performance" not in deferred_create["page_slugs"]
        assert deferred_create["approves_metric_or_page"] is False
        deferred_ready = by_lane_type[("deferred_no_direct_table_config_review", "none")]
        assert deferred_ready["page_ids"] == ["GAP-KPI-PERFORMANCE-PAGE"]
        assert deferred_ready["page_slugs"] == ["kpi-performance"]
        assert deferred_ready["approves_metric_or_page"] is False

        assert all(item["writes_governance_records"] is False for item in work_items)
        assert all(item["executes_tool_calls"] is False for item in work_items)
        assert all(item["samples_duckdb_tables"] is False for item in work_items)
        assert all(item["checks_lineage_records"] is False for item in work_items)
        assert all(item["proves_page_execution"] is False for item in work_items)
        assert all(item["runs_ui_or_api_smoke"] is False for item in work_items)
        assert all(item["captures_business_owner_approval"] is False for item in work_items)
        assert all(item["approves_metric_or_page"] is False for item in work_items)
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_review_queue_audits_record_remediation_scope() -> None:
    server = McpProcess("data-catalog", timeout_seconds=180.0)
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {"name": "get_page_catalog_date_lineage_review_queue", "arguments": {}},
        )
        payload = json.loads(result["content"][0]["text"])

        expected_checked_groups = [
            "record_remediation_work_items",
            "record_remediation_evidence_work_items",
            "record_remediation_review_lane_work_items",
        ]
        expected_work_item_count = sum(len(payload[group]) for group in expected_checked_groups)
        assert payload["record_remediation_scope_audit"] == {
            "work_item_count": expected_work_item_count,
            "checked_work_item_groups": expected_checked_groups,
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "suggested_tool_call_count": sum(
                len(item.get("suggested_tool_calls", []))
                for group in expected_checked_groups
                for item in payload[group]
            ),
            "allowed_suggested_tools": [
                "moss-lineage-evidence.get_page_governance_record_requirements",
                "moss-lineage-evidence.get_page_governance_record_blueprint_queue",
                "moss-lineage-evidence.get_page_governance_audit_review_queue",
                "moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue",
            ],
            "suggested_tool_call_violations": [],
            "scope_violations": [],
        }
    finally:
        server.close()


def test_data_catalog_page_catalog_date_lineage_record_remediation_scope_audit_flags_drift() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_catalog_date_lineage_record_remediation_scope_audit(
        [
            {
                "remediation_type": "create_direct_record",
                "writes_governance_records": False,
                "executes_tool_calls": True,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": None,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
            }
        ]
    )

    assert result["work_item_count"] == 1
    assert result["executes_tool_calls"] is True
    assert result["runs_ui_or_api_smoke"] is False
    assert result["scope_violations"] == [
        {
            "work_item_group": "record_remediation_work_items",
            "work_item_index": 0,
            "scope_key": "executes_tool_calls",
            "scope_value": True,
        },
        {
            "work_item_group": "record_remediation_work_items",
            "work_item_index": 0,
            "scope_key": "runs_ui_or_api_smoke",
            "scope_value": None,
        },
    ]


def test_data_catalog_page_catalog_date_lineage_record_remediation_scope_audit_flags_unsafe_suggested_calls() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("moss_project_mcp_for_test", MCP_SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    result = module.page_catalog_date_lineage_record_remediation_scope_audit(
        [
            {
                "remediation_type": "create_direct_record",
                "writes_governance_records": False,
                "executes_tool_calls": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
                "suggested_tool_calls": [
                    {
                        "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
                        "arguments": {"page_slugs": ["product-category-pnl"]},
                    },
                    {
                        "tool": "moss-lineage-evidence.preflight_page_governance_record",
                        "arguments": {"page_slug": "product-category-pnl"},
                    },
                ],
            }
        ]
    )

    assert result["suggested_tool_call_count"] == 2
    assert result["allowed_suggested_tools"] == [
        "moss-lineage-evidence.get_page_governance_record_requirements",
        "moss-lineage-evidence.get_page_governance_record_blueprint_queue",
        "moss-lineage-evidence.get_page_governance_audit_review_queue",
        "moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue",
    ]
    assert result["suggested_tool_call_violations"] == [
        {
            "work_item_group": "record_remediation_work_items",
            "work_item_index": 0,
            "suggested_tool_call_index": 1,
            "tool": "moss-lineage-evidence.preflight_page_governance_record",
        }
    ]


def test_data_catalog_page_catalog_date_evidence_skips_deferred_non_table_pages() -> None:
    server = McpProcess("data-catalog")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_catalog_date_evidence",
                "arguments": {"page_slugs": ["executive-summary", "agent"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        pages = {page["page_id"]: page for page in payload["pages"]}
        assert pages["PAGE-EXEC-SUMMARY-001"]["sampled_table_names"] == []
        assert pages["PAGE-AGENT-001"]["sampled_table_names"] == []
        assert pages["PAGE-EXEC-SUMMARY-001"]["table_evidence"] == []
        assert pages["PAGE-AGENT-001"]["table_evidence"] == []
    finally:
        server.close()


def test_data_catalog_page_catalog_date_evidence_samples_known_page_tables(tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            """
            create table zqtz_bond_daily_snapshot (
                report_date date,
                bond_code varchar,
                face_value double
            )
            """
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot values
                (date '2026-05-31', 'BOND-A', 100.0),
                (date '2026-04-30', 'BOND-B', 80.0)
            """
        )
        conn.execute(
            """
            create table tyw_interbank_daily_snapshot (
                as_of_date date,
                product_code varchar,
                carrying_amount double
            )
            """
        )
        conn.execute(
            """
            insert into tyw_interbank_daily_snapshot values
                (date '2026-05-30', 'IB-A', 20.0),
                (date '2026-05-29', 'IB-B', 30.0)
            """
        )
    finally:
        conn.close()

    server = McpProcess("data-catalog", env={"MOSS_DUCKDB_PATH": str(duckdb_path)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_catalog_date_evidence" for tool in tools)

        result = server.request(
            "tools/call",
            {
                "name": "get_page_catalog_date_evidence",
                "arguments": {"page_slugs": ["PAGE-POS-001"], "limit": 3},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-catalog-date-evidence"
        assert "does not prove page execution, governance lineage, metric definition, or formal approval" in payload[
            "disclaimer"
        ]
        assert payload["duckdb_exists"] is True
        assert payload["summary"]["page_count"] == 1
        assert payload["summary"]["present_table_count"] >= 2
        assert payload["summary"]["date_sampled_table_count"] >= 2

        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-POS-001"
        assert page["evidence_scope"]["catalog_describe_checked"] is True
        assert page["evidence_scope"]["date_sample_checked"] is True
        assert page["evidence_scope"]["quality_checked"] is False
        assert page["evidence_scope"]["lineage_checked"] is False
        assert page["evidence_scope"]["formal_metric_approval_checked"] is False
        assert page["evidence_scope"]["page_execution_checked"] is False
        assert "approval_status" not in page
        assert "formal_use_allowed" not in page

        by_table = {row["table_name"]: row for row in page["table_evidence"]}
        assert by_table["zqtz_bond_daily_snapshot"]["status"] == "present"
        assert by_table["zqtz_bond_daily_snapshot"]["date_column"] == "report_date"
        assert by_table["zqtz_bond_daily_snapshot"]["available_dates"] == ["2026-05-31", "2026-04-30"]
        assert by_table["tyw_interbank_daily_snapshot"]["status"] == "present"
        assert by_table["tyw_interbank_daily_snapshot"]["date_column"] == "as_of_date"
        assert by_table["tyw_interbank_daily_snapshot"]["available_dates"] == ["2026-05-30", "2026-05-29"]
    finally:
        server.close()


def test_data_catalog_page_catalog_date_evidence_reports_missing_duckdb_without_approval(
    tmp_path: Path,
) -> None:
    missing_duckdb = tmp_path / "missing.duckdb"
    server = McpProcess("data-catalog", env={"MOSS_DUCKDB_PATH": str(missing_duckdb)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_catalog_date_evidence",
                "arguments": {"page_slugs": ["PAGE-POS-001"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["scope"] == "page-catalog-date-evidence"
        assert payload["duckdb_exists"] is False
        assert payload["summary"]["present_table_count"] == 0
        assert payload["summary"]["date_sampled_table_count"] == 0

        page = payload["pages"][0]
        assert page["page_id"] == "PAGE-POS-001"
        assert page["table_evidence"]
        assert {row["status"] for row in page["table_evidence"]} == {"duckdb_missing"}
        assert page["evidence_scope"]["formal_metric_approval_checked"] is False
        assert "approval_status" not in page
        assert "formal_use_allowed" not in page
    finally:
        server.close()


def test_data_catalog_page_catalog_date_evidence_distinguishes_no_date_and_unknown_table(
    tmp_path: Path,
) -> None:
    duckdb = pytest.importorskip("duckdb")
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            """
            create table zqtz_bond_daily_snapshot (
                bond_code varchar,
                face_value double
            )
            """
        )
        conn.execute("insert into zqtz_bond_daily_snapshot values ('BOND-A', 100.0)")
    finally:
        conn.close()

    server = McpProcess("data-catalog", env={"MOSS_DUCKDB_PATH": str(duckdb_path)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_catalog_date_evidence",
                "arguments": {"page_slugs": ["positions"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])

        page = payload["pages"][0]
        assert page["page_slug"] == "positions"
        assert page["page_id"] == "PAGE-POS-001"
        assert "zqtz_bond_daily_snapshot" in page["sampled_table_names"]
        assert "tyw_interbank_daily_snapshot" in page["sampled_table_names"]

        by_table = {row["table_name"]: row for row in page["table_evidence"]}
        assert by_table["zqtz_bond_daily_snapshot"]["status"] == "present_no_date_column"
        assert by_table["zqtz_bond_daily_snapshot"]["date_column"] is None
        assert by_table["zqtz_bond_daily_snapshot"]["available_dates"] == []
        assert by_table["tyw_interbank_daily_snapshot"]["status"] == "unknown_table"
        assert by_table["tyw_interbank_daily_snapshot"]["available_dates"] == []
        assert "DuckDB file does not exist" not in by_table["tyw_interbank_daily_snapshot"]["error"]
        assert payload["summary"]["present_table_count"] == 1
        assert payload["summary"]["date_sampled_table_count"] == 0
        assert "approval_status" not in page
        assert "formal_use_allowed" not in page
    finally:
        server.close()


def test_data_catalog_page_catalog_date_evidence_samples_snapshot_as_of_date(
    tmp_path: Path,
) -> None:
    duckdb = pytest.importorskip("duckdb")
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
                snapshot_as_of_date varchar,
                stock_code varchar
            )
            """
        )
        conn.execute(
            "insert into livermore_candidate_history values ('2026-05-29', '000001.SZ')"
        )
    finally:
        conn.close()

    server = McpProcess("data-catalog", env={"MOSS_DUCKDB_PATH": str(duckdb_path)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_catalog_date_evidence",
                "arguments": {"page_slugs": ["stock-analysis"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])
        page = payload["pages"][0]
        by_table = {row["table_name"]: row for row in page["table_evidence"]}

        assert by_table["livermore_candidate_history"]["status"] == "present"
        assert by_table["livermore_candidate_history"]["date_column"] == "snapshot_as_of_date"
        assert by_table["livermore_candidate_history"]["available_dates"] == ["2026-05-29"]
    finally:
        server.close()


def test_data_catalog_page_catalog_date_evidence_samples_received_at(
    tmp_path: Path,
) -> None:
    duckdb = pytest.importorskip("duckdb")
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            """
            create table choice_news_event (
                event_key varchar,
                received_at varchar,
                payload_text varchar
            )
            """
        )
        conn.execute(
            "insert into choice_news_event values ('news-1', '2026-06-03T20:19:24+00:00', 'headline')"
        )
    finally:
        conn.close()

    server = McpProcess("data-catalog", env={"MOSS_DUCKDB_PATH": str(duckdb_path)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        result = server.request(
            "tools/call",
            {
                "name": "get_page_catalog_date_evidence",
                "arguments": {"page_slugs": ["news-events"]},
            },
        )
        payload = json.loads(result["content"][0]["text"])
        page = payload["pages"][0]
        by_table = {row["table_name"]: row for row in page["table_evidence"]}

        assert by_table["choice_news_event"]["status"] == "present"
        assert by_table["choice_news_event"]["date_column"] == "received_at"
        assert by_table["choice_news_event"]["available_dates"] == ["2026-06-03T20:19:24+00:00"]
    finally:
        server.close()
