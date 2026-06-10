from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DATE = "2026-06-10"
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "audits"
    / f"{AUDIT_DATE}-direct-app-mcp-gitnexus-tool-surface-snapshot.json"
)
REFRESH_COMMAND = (
    "python scripts\\refresh_direct_app_mcp_gitnexus_tool_surface_snapshot.py"
)
PRIMARY_QUERY = "moss metric contracts lineage evidence data catalog gitnexus MCP tools"
GITNEXUS_QUERY = "gitnexus MCP impact call path symbol repository evidence"
MOSS_GENERAL_QUERY = "moss metric contracts lineage evidence data catalog MCP tools"
MOSS_NAMED_QUERY = "moss-data-catalog moss-lineage-evidence moss-metric-contracts"
EXPECTED_DIRECT_SERVERS = (
    "gitnexus",
    "moss-metric-contracts",
    "moss-lineage-evidence",
    "moss-data-catalog",
    "moss-data-quality",
)
SERVER_KEYWORDS = {
    "gitnexus": ("gitnexus",),
    "moss-metric-contracts": ("mossmetriccontracts", "metriccontracts"),
    "moss-lineage-evidence": ("mosslineageevidence", "lineageevidence"),
    "moss-data-catalog": ("mossdatacatalog", "datacatalog"),
    "moss-data-quality": ("mossdataquality", "dataquality"),
}


def _now_shanghai() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _classify_tool(name: str) -> str:
    if name in {"codex_app.handoff_thread", "codex_app.fork_thread"}:
        return "codex_app_thread_management"
    if name == "codex_app.automation_update":
        return "codex_app_automation_management"
    if _relevant_direct_tool(name):
        return "direct_moss_or_gitnexus_evidence_tool"
    return "unrelated_app_tool"


def _server_hits(tool_names: list[str]) -> set[str]:
    hits: set[str] = set()
    for tool_name in tool_names:
        normalised = _normalise(tool_name)
        if tool_name.startswith("codex_app."):
            continue
        for server, keywords in SERVER_KEYWORDS.items():
            if any(keyword in normalised for keyword in keywords):
                hits.add(server)
    return hits


def _relevant_direct_tool(name: str) -> bool:
    return bool(_server_hits([name]))


def _tool_rows(tool_names: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "classification": _classify_tool(name),
            "relevant_direct_moss_or_gitnexus_evidence": _relevant_direct_tool(name),
        }
        for name in tool_names
    ]


def _focused_recheck(
    *,
    query: str,
    checked_at: str,
    tool_names: list[str],
) -> dict[str, Any]:
    rows = _tool_rows(tool_names)
    relevant_count = sum(
        1 for row in rows if row["relevant_direct_moss_or_gitnexus_evidence"]
    )
    if relevant_count:
        interpretation = (
            "query exposed direct MOSS/GitNexus tool names, but no direct App evidence "
            "has been captured or compared yet"
        )
    elif tool_names:
        interpretation = (
            "query returned only Codex App thread or automation management tools; "
            "no direct GitNexus or MOSS evidence tools exposed"
        )
    else:
        interpretation = "no direct MOSS MCP evidence tools exposed"
    return {
        "tool": "tool_search",
        "query": query,
        "checked_at": checked_at,
        "returned_tool_count": len(tool_names),
        "returned_tools": rows,
        "relevant_direct_tool_count": relevant_count,
        "interpretation": interpretation,
    }


def _codex_config_servers(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    return re.findall(r"^\[mcp_servers\.([^\]]+)\]", text, flags=re.MULTILINE)


def _mcp_json_servers(path: Path) -> list[str]:
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sorted((payload.get("mcpServers") or {}).keys())


def _expected_declared(declared_servers: list[str]) -> list[str]:
    declared = set(declared_servers)
    return [server for server in EXPECTED_DIRECT_SERVERS if server in declared]


def _local_registration_sources(
    *,
    codex_config_path: Path,
    mcp_json_path: Path,
    runbook_path: Path,
) -> list[dict[str, Any]]:
    codex_servers = _codex_config_servers(codex_config_path)
    mcp_servers = _mcp_json_servers(mcp_json_path)
    runbook_text = runbook_path.read_text(encoding="utf-8") if runbook_path.is_file() else ""
    return [
        {
            "path": ".codex/config.toml",
            "declares_expected_servers": set(EXPECTED_DIRECT_SERVERS)
            <= set(codex_servers),
            "declared_servers": _expected_declared(codex_servers),
            "all_declared_server_count": len(codex_servers),
        },
        {
            "path": ".mcp.json",
            "declares_expected_servers": set(EXPECTED_DIRECT_SERVERS)
            <= set(mcp_servers),
            "declared_servers": _expected_declared(mcp_servers),
            "all_declared_server_count": len(mcp_servers),
        },
        {
            "path": "docs/MCP_RUNBOOK.md",
            "documents_app_surface_fallback": "## App Surface Fallback"
            in runbook_text,
            "documents_fresh_session_retry": "fresh session"
            in runbook_text.lower(),
        },
    ]


def _status_overall(hit_servers: set[str]) -> str:
    if not hit_servers:
        return "tool_surface_unavailable_in_current_codex_app_session"
    if set(EXPECTED_DIRECT_SERVERS) <= hit_servers:
        return "tool_surface_exposed_evidence_capture_required"
    return "partial_tool_surface_exposed_evidence_capture_required"


def build_snapshot(
    *,
    generated_at: str | None = None,
    primary_tool_names: list[str] | None = None,
    gitnexus_tool_names: list[str] | None = None,
    moss_general_tool_names: list[str] | None = None,
    moss_named_tool_names: list[str] | None = None,
    codex_config_path: Path = ROOT / ".codex" / "config.toml",
    mcp_json_path: Path = ROOT / ".mcp.json",
    runbook_path: Path = ROOT / "docs" / "MCP_RUNBOOK.md",
) -> dict[str, Any]:
    generated_at = generated_at or _now_shanghai()
    primary_tool_names = list(primary_tool_names or [])
    gitnexus_tool_names = list(gitnexus_tool_names or [])
    moss_general_tool_names = list(moss_general_tool_names or [])
    moss_named_tool_names = list(moss_named_tool_names or [])
    all_tool_names = (
        primary_tool_names
        + gitnexus_tool_names
        + moss_general_tool_names
        + moss_named_tool_names
    )
    hit_servers = _server_hits(all_tool_names)
    discovery_rows = _tool_rows(primary_tool_names)
    relevant_discovery_count = sum(
        1 for row in discovery_rows if row["relevant_direct_moss_or_gitnexus_evidence"]
    )
    return {
        "report_kind": "direct_app_mcp_gitnexus_tool_surface_snapshot",
        "generated_at": generated_at,
        "repo_root": str(ROOT),
        "audit_date": AUDIT_DATE,
        "refresh_command": REFRESH_COMMAND,
        "observation_source": "caller_supplied_tool_search_results",
        "status": {
            "overall": _status_overall(hit_servers),
            "fail_closed": True,
            "direct_app_mcp_evidence_captured": False,
            "direct_gitnexus_evidence_captured": False,
            "approves_metrics": False,
            "approves_pages": False,
            "captures_business_owner_approval": False,
            "writes_governance_records": False,
            "certifies_routes": False,
        },
        "tool_discovery": {
            "tool": "tool_search",
            "query": PRIMARY_QUERY,
            "checked_at": generated_at,
            "discovered_tool_count": len(primary_tool_names),
            "discovered_tools": discovery_rows,
            "relevant_direct_tool_count": relevant_discovery_count,
        },
        "focused_rechecks": [
            _focused_recheck(
                query=GITNEXUS_QUERY,
                checked_at=generated_at,
                tool_names=gitnexus_tool_names,
            ),
            _focused_recheck(
                query=MOSS_GENERAL_QUERY,
                checked_at=generated_at,
                tool_names=moss_general_tool_names,
            ),
            _focused_recheck(
                query=MOSS_NAMED_QUERY,
                checked_at=generated_at,
                tool_names=moss_named_tool_names,
            ),
        ],
        "expected_direct_servers": list(EXPECTED_DIRECT_SERVERS),
        "detected_direct_servers": [server for server in EXPECTED_DIRECT_SERVERS if server in hit_servers],
        "missing_direct_servers": [server for server in EXPECTED_DIRECT_SERVERS if server not in hit_servers],
        "local_registration_sources": _local_registration_sources(
            codex_config_path=codex_config_path,
            mcp_json_path=mcp_json_path,
            runbook_path=runbook_path,
        ),
        "interpretation": {
            "repo_configuration_status": "expected_servers_declared_locally",
            "current_app_tool_surface_status": (
                "direct_moss_and_gitnexus_tools_not_exposed"
                if not hit_servers
                else "direct_tool_names_exposed_but_evidence_not_captured"
            ),
            "local_stdio_evidence_status": "fallback_only_not_direct_app_surface_evidence",
            "closure_effect": "none",
        },
        "direct_evidence_gap": {
            server: (
                "direct_tool_exposed_but_evidence_not_captured"
                if server in hit_servers
                else "not_callable_as_direct_codex_app_tool_in_this_session"
            )
            for server in EXPECTED_DIRECT_SERVERS
        },
        "closure_gate": [
            "start a fresh Codex App session or otherwise reload MCP registrations",
            "repeat direct App tool discovery for MOSS MCP and GitNexus",
            "collect direct App-surface evidence and compare it against local stdio MCP evidence",
            "keep owner, metric, route, governance-record, and formal-use gates fail-closed until independent closure criteria pass",
        ],
        "boundary": (
            "This snapshot records current direct App tool discovery only. It does not "
            "approve metrics, does not approve pages, does not certify routes, does not "
            "write governance records, does not prove live page/API execution, does not "
            "replace GitNexus impact evidence, and does not capture business-owner approval."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh the direct App MCP/GitNexus tool-surface snapshot from caller-supplied "
            "tool_search observations without granting closure."
        ),
    )
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--primary-tool-names", nargs="*", default=[])
    parser.add_argument("--gitnexus-tool-names", nargs="*", default=[])
    parser.add_argument("--moss-general-tool-names", nargs="*", default=[])
    parser.add_argument("--moss-named-tool-names", nargs="*", default=[])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--require-direct-evidence-captured",
        action="store_true",
        help=(
            "Exit non-zero unless all expected direct MOSS/GitNexus tools are exposed "
            "and direct App/GitNexus evidence is captured. The default remains a "
            "non-closing tool-surface snapshot."
        ),
    )
    args = parser.parse_args(argv)

    snapshot = build_snapshot(
        generated_at=args.generated_at,
        primary_tool_names=args.primary_tool_names,
        gitnexus_tool_names=args.gitnexus_tool_names,
        moss_general_tool_names=args.moss_general_tool_names,
        moss_named_tool_names=args.moss_named_tool_names,
    )
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    if args.require_direct_evidence_captured:
        status = snapshot["status"]
        if (
            snapshot["missing_direct_servers"]
            or not status["direct_app_mcp_evidence_captured"]
            or not status["direct_gitnexus_evidence_captured"]
        ):
            print(
                (
                    "Direct App MCP/GitNexus evidence is not captured: "
                    f"missing_direct_servers={snapshot['missing_direct_servers']}, "
                    f"direct_app_mcp_evidence_captured={status['direct_app_mcp_evidence_captured']}, "
                    f"direct_gitnexus_evidence_captured={status['direct_gitnexus_evidence_captured']}"
                ),
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
