from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.app.agent.schemas.agent_request import AgentQueryRequest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WINDOWS_PATH_RE = re.compile(r"([A-Za-z]:\\[^\s\"'<>|?*]+)")


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

    quality_flag = "ok" if mcp_configured else "warning"
    repo_name = repo_path.name or str(repo_path)
    return {
        "answer": (
            f"GitNexus 索引状态已返回。仓库 {repo_name} 最近索引时间 {indexed_at}，"
            f"当前包含 {int(stats.get('nodes') or 0)} 个节点、{int(stats.get('edges') or 0)} 条关系、"
            f"{int(stats.get('processes') or 0)} 条执行流程。可继续下钻 Context 与 Processes 资源。"
        ),
        "cards": [
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
        ],
        "tables_used": [".gitnexus/meta.json", ".mcp.json", ".gitnexus/wiki"],
        "filters_applied": {"repo_path": str(repo_path)},
        "row_count": len(wiki_docs),
        "quality_flag": quality_flag,
        "basis": "analytical",
        "formal_use_allowed": False,
        "scenario_flag": False,
        "source_version": f"sv_gitnexus_{_slug(indexed_at)}",
        "vendor_version": "vv_gitnexus_local",
        "rule_version": "rv_agent_gitnexus_v1",
        "cache_version": "cv_agent_gitnexus_status_v1",
        "vendor_status": "ok" if mcp_configured else "vendor_unavailable",
        "fallback_mode": "none",
        "next_drill": [
            {"dimension": "context", "label": "查看 Context"},
            {"dimension": "processes", "label": "查看 Processes"},
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
