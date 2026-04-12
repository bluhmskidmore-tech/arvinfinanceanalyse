from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.services.gitnexus_mcp_client import GitNexusMcpClient

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WINDOWS_PATH_RE = re.compile(r"([A-Za-z]:\\[^\s\"'<>|?*]+)")
_PROCESS_NAME_RE = re.compile(r"gitnexus\s+process(?:/|\s+)(?P<name>[^\r\n]+)", re.IGNORECASE)
_GITNEXUS_TRACE_COLUMNS = ["step", "symbol", "file", "module_group", "edge_label"]


def build_gitnexus_status_payload(request: AgentQueryRequest) -> dict[str, Any]:
    repo_path = _resolve_repo_path(request)
    meta_path = repo_path / ".gitnexus" / "meta.json"
    if not meta_path.is_file():
        raise ValueError(f"GitNexus index was not found under {repo_path}.")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    stats = dict(meta.get("stats") or {})
    meta_repo_path = str(meta.get("repoPath") or repo_path)
    indexed_at = str(meta.get("indexedAt") or "unknown")
    last_commit = str(meta.get("lastCommit") or "unknown")
    mcp_configured = _gitnexus_mcp_configured(repo_path)
    wiki_docs = _list_wiki_docs(repo_path)
    resource_repo_name = Path(meta_repo_path).name or repo_path.name
    context_uri = f"gitnexus://repo/{resource_repo_name}/context"
    processes_uri = f"gitnexus://repo/{resource_repo_name}/processes"
    process_name = _resolve_process_name(request)
    mcp_bundle = None
    mcp_error = None
    try:
        mcp_bundle = GitNexusMcpClient(repo_path).read_bundle(process_name=process_name)
        if mcp_bundle.get("repo_name"):
            resource_repo_name = str(mcp_bundle["repo_name"])
            context_uri = f"gitnexus://repo/{resource_repo_name}/context"
            processes_uri = f"gitnexus://repo/{resource_repo_name}/processes"
    except Exception as exc:  # pragma: no cover - exercised via fallback assertions
        mcp_error = str(exc)

    quality_flag = "ok" if mcp_bundle else ("warning" if mcp_configured else "warning")
    repo_name = repo_path.name or str(repo_path)
    cards: list[dict[str, Any]] = [
        {"type": "metric", "title": "Repo", "value": meta_repo_path},
        {"type": "metric", "title": "Indexed At", "value": indexed_at},
        {"type": "metric", "title": "Last Commit", "value": last_commit},
        {"type": "metric", "title": "Nodes", "value": str(int(stats.get("nodes") or 0))},
        {"type": "metric", "title": "Edges", "value": str(int(stats.get("edges") or 0))},
        {"type": "metric", "title": "Communities", "value": str(int(stats.get("communities") or 0))},
        {"type": "metric", "title": "Processes", "value": str(int(stats.get("processes") or 0))},
        {"type": "resource", "title": "GitNexus Context", "value": context_uri},
        {"type": "resource", "title": "GitNexus Processes", "value": processes_uri},
        {"type": "metric", "title": "MCP GitNexus", "value": "enabled" if mcp_configured else "missing"},
        {"type": "metric", "title": "Wiki Documents", "value": str(len(wiki_docs))},
        {"type": "resource", "title": "Context Docs", "value": _summarize_docs(wiki_docs, keyword="context")},
        {"type": "resource", "title": "Process Docs", "value": _summarize_docs(wiki_docs, keyword="process")},
    ]
    tables_used = [".gitnexus/meta.json", ".mcp.json", ".gitnexus/wiki"]

    if mcp_bundle:
        tables_used.extend(
            [context_uri, processes_uri]
            + ([f"gitnexus://repo/{resource_repo_name}/process/{process_name}"] if process_name else [])
        )
        context = dict(mcp_bundle.get("context") or {})
        processes = list(mcp_bundle.get("processes") or [])
        process = dict(mcp_bundle.get("process") or {})
        if context.get("tools"):
            cards.append(
                {
                    "type": "table",
                    "title": "GitNexus Tools",
                    "data": [
                        {
                            "tool": str(item.get("tool") or item.get("name") or ""),
                            "description": str(item.get("description") or ""),
                        }
                        for item in list(context["tools"])
                    ],
                    "spec": {"columns": ["tool", "description"]},
                }
            )
        if context.get("resources"):
            cards.append(
                {
                    "type": "table",
                    "title": "GitNexus Resources",
                    "data": [
                        {
                            "uri": str(item.get("uri") or ""),
                            "description": str(item.get("description") or ""),
                        }
                        for item in list(context["resources"])
                    ],
                    "spec": {"columns": ["uri", "description"]},
                }
            )
        if processes:
            cards.append(
                {
                    "type": "table",
                    "title": "GitNexus Processes Table",
                    "data": processes[:10],
                    "spec": {"columns": ["name", "type", "steps"]},
                }
            )
        if process:
            if process.get("error"):
                cards.append(
                    {
                        "type": "status",
                        "title": "GitNexus Process",
                        "value": str(process["error"]),
                    }
                )
            elif process.get("trace"):
                trace_rows = _build_trace_rows(list(process["trace"]))
                cards.append(
                    {
                        "type": "table",
                        "title": "GitNexus Process Trace",
                        "data": trace_rows,
                        "spec": {"columns": _GITNEXUS_TRACE_COLUMNS},
                    }
                )
    elif mcp_error:
        cards.append(
            {
                "type": "status",
                "title": "GitNexus MCP Fallback",
                "value": mcp_error,
            }
        )

    return {
        "answer": (
            f"GitNexus 索引状态已返回。仓库 {repo_name} 最近索引时间 {indexed_at}，"
            f"当前包含 {int(stats.get('nodes') or 0)} 个节点、{int(stats.get('edges') or 0)} 条关系、"
            f"{int(stats.get('processes') or 0)} 条执行流程。"
            + (" 已叠加 GitNexus MCP 的 Context/Processes 结构化读取。" if mcp_bundle else " 当前回退为本地索引状态视图。")
        ),
        "cards": cards,
        "tables_used": tables_used,
        "filters_applied": {
            "repo_path": str(repo_path),
            **({"process_name": process_name} if process_name else {}),
        },
        "row_count": len(wiki_docs) + len(list((mcp_bundle or {}).get("processes") or [])),
        "quality_flag": quality_flag,
        "basis": "analytical",
        "formal_use_allowed": False,
        "scenario_flag": False,
        "source_version": f"sv_gitnexus_{_slug(indexed_at)}",
        "vendor_version": "vv_gitnexus_local",
        "rule_version": "rv_agent_gitnexus_v1",
        "cache_version": "cv_agent_gitnexus_status_v1",
        "vendor_status": "ok" if mcp_bundle else "vendor_unavailable",
        "fallback_mode": "none",
        "next_drill": [
            {"dimension": "context", "label": "查看 Context"},
            {"dimension": "processes", "label": "查看 Processes"},
            *([{"dimension": "process", "label": f"查看 Process: {process_name}"}] if process_name else []),
            {"dimension": "wiki_docs", "label": "查看 Wiki 文档"},
        ],
    }


def _resolve_repo_path(request: AgentQueryRequest) -> Path:
    for container in (request.filters, request.context):
        value = container.get("repo_path")
        if value:
            return _normalize_repo_path(str(value))

    question_match = _WINDOWS_PATH_RE.search(request.question)
    if question_match:
        return _normalize_repo_path(question_match.group(1))

    return _REPO_ROOT


def _resolve_process_name(request: AgentQueryRequest) -> str | None:
    for container in (request.filters, request.context):
        value = container.get("process_name")
        if value is not None and str(value).strip():
            return str(value).strip()
    match = _PROCESS_NAME_RE.search(request.question)
    if match:
        return match.group("name").strip()
    return None


def _normalize_repo_path(raw_path: str) -> Path:
    candidate = Path(raw_path.strip().strip("\"'"))
    if candidate.name == ".gitnexus":
        return candidate.parent
    return candidate


def _gitnexus_mcp_configured(repo_path: Path) -> bool:
    mcp_path = repo_path / ".mcp.json"
    if not mcp_path.is_file():
        return False
    payload = json.loads(mcp_path.read_text(encoding="utf-8"))
    servers = payload.get("mcpServers")
    return isinstance(servers, dict) and "gitnexus" in servers


def _list_wiki_docs(repo_path: Path) -> list[str]:
    wiki_dir = repo_path / ".gitnexus" / "wiki"
    if not wiki_dir.is_dir():
        return []
    return sorted(path.name for path in wiki_dir.iterdir() if path.is_file())


def _summarize_docs(doc_names: list[str], *, keyword: str) -> str:
    matching = [name for name in doc_names if keyword.lower() in name.lower()]
    if matching:
        return ", ".join(matching[:3])
    if doc_names:
        return ", ".join(doc_names[:3])
    return "none"


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").lower()
    return slug or "unknown"


def _build_trace_rows(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, raw_row in enumerate(trace):
        row = dict(raw_row)
        module_group = _trace_module_group(row)
        edge_label = _trace_edge_label(row, trace[index + 1] if index < len(trace) - 1 else None)
        row["module_group"] = module_group
        row["edge_label"] = edge_label
        rows.append(row)
    return rows


def _trace_module_group(row: dict[str, Any]) -> str:
    explicit = str(row.get("module_group") or "").strip().lower()
    if explicit:
        return explicit

    file_path = str(row.get("file") or "").replace("\\", "/").lower()
    if "/api/" in file_path or file_path.endswith("/api.py"):
        return "api"
    if "/services/" in file_path:
        return "services"
    if "/repositories/" in file_path:
        return "repositories"
    if "/governance/" in file_path:
        return "governance"
    if "/core/" in file_path or "/core_finance/" in file_path:
        return "core"
    if "/tasks/" in file_path:
        return "tasks"
    if "/schemas/" in file_path:
        return "schemas"
    return "unknown"


def _trace_edge_label(row: dict[str, Any], next_row: dict[str, Any] | None) -> str:
    explicit = str(row.get("edge_label") or "").strip()
    if explicit:
        return explicit
    if next_row is None:
        return ""
    return f"{_trace_module_group(row)} -> {_trace_module_group(next_row)}"
