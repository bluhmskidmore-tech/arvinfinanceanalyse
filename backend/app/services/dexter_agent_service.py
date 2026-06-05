from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import (
    AgentCard,
    AgentEnvelope,
    AgentEvidence,
    AgentResultMeta,
)
from backend.app.core_finance.calibers.enums import Basis
from backend.app.governance.agent_audit import AgentAuditPayload, append_agent_audit
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services.dexter_research_context_builder import build_dexter_research_context

RULE_VERSION = "rv_agent_dexter_v1"


def execute_dexter_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
    settings: Any,
) -> AgentEnvelope:
    research_context = build_dexter_research_context(
        request=request,
        duckdb_path=str(getattr(settings, "duckdb_path", "") or ""),
    )
    prompt = _build_dexter_prompt(request, research_context=research_context)
    result = run_dexter_agent(
        request=request,
        command=str(getattr(settings, "agent_dexter_command", "dexter") or "dexter"),
        transport=str(getattr(settings, "agent_dexter_transport", "cli") or "cli"),
        bridge_url=str(getattr(settings, "agent_dexter_bridge_url", "") or ""),
        model=str(getattr(settings, "agent_dexter_model", "") or ""),
        toolsets=str(getattr(settings, "agent_dexter_toolsets", "") or ""),
        timeout_seconds=float(getattr(settings, "agent_dexter_timeout_seconds", 180.0) or 180.0),
        prompt_override=prompt,
    )
    envelope = build_dexter_envelope(request=request, result=result, research_context=research_context)
    _append_dexter_audit(request, governance_dir, envelope, result)
    return envelope


def run_dexter_agent(
    *,
    request: AgentQueryRequest,
    command: str,
    transport: str,
    bridge_url: str,
    model: str,
    toolsets: str,
    timeout_seconds: float,
    prompt_override: str | None = None,
) -> dict[str, Any]:
    prompt = prompt_override or _build_dexter_prompt(request)
    normalized_transport = str(transport or "").strip().lower() or "cli"
    normalized_toolsets = _normalize_toolsets(toolsets)
    if normalized_transport in {"sidecar", "bridge"}:
        return _post_dexter_bridge_query(
            bridge_url=str(bridge_url or "").strip() or "http://127.0.0.1:7892",
            prompt=prompt,
            model=model,
            toolsets=normalized_toolsets,
            timeout_seconds=timeout_seconds,
        )

    args = _build_dexter_command(
        command=command,
        prompt=prompt,
        model=model,
        toolsets=normalized_toolsets,
    )
    try:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(timeout_seconds, 1.0),
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Dexter command not found: {command}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Dexter timed out after {timeout_seconds:g}s") from exc

    stdout = str(completed.stdout or "")
    stderr = str(completed.stderr or "")
    if completed.returncode != 0:
        detail = _truncate((stderr or stdout).strip(), 2000)
        raise RuntimeError(f"Dexter failed with exit code {completed.returncode}: {detail}")

    payload = _parse_dexter_output(stdout)
    return {
        "answer": str(payload.get("answer") or stdout.strip()),
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
        "tool_name": str(payload.get("tool_name") or "dexter_cli"),
        "model": str(payload.get("model") or model or "default"),
        "toolsets": str(payload.get("toolsets") or normalized_toolsets or "default"),
        "transport": "cli",
        "tables_used": _normalize_tables_used(payload.get("tables_used"), fallback="dexter_cli"),
        **_structured_research_fields(payload),
    }


def build_dexter_envelope(
    *,
    request: AgentQueryRequest,
    result: dict[str, Any],
    research_context: dict[str, Any] | None = None,
) -> AgentEnvelope:
    has_research_context = bool(research_context and research_context.get("domain"))
    trace_id = f"tr_agent_dexter_{uuid4().hex[:12]}"
    generated_at = datetime.now(timezone.utc)
    filters_applied = {
        key: value for key, value in request.filters.items() if value not in (None, "")
    }
    filters_applied["provider"] = "dexter"
    if result.get("model"):
        filters_applied["model"] = result["model"]
    if result.get("toolsets"):
        filters_applied["toolsets"] = result["toolsets"]
    if result.get("transport"):
        filters_applied["transport"] = result["transport"]
    if has_research_context:
        filters_applied.update(
            {
                key: value
                for key, value in dict(research_context.get("filters_applied") or {}).items()
                if value not in (None, "")
            }
        )

    tables_used = _normalize_tables_used(
        result.get("tables_used"),
        fallback="dexter_sidecar" if str(result.get("transport") or "").strip().lower() in {"sidecar", "bridge"} else "dexter_cli",
    )
    if has_research_context:
        tables_used = _dedupe([*tables_used, *list(research_context.get("tables_used") or [])])
    evidence_rows = int(research_context.get("evidence_rows") or 0) if has_research_context else 1
    quality_flag = str(research_context.get("quality_flag") or "ok") if has_research_context else "ok"
    evidence = AgentEvidence(
        tables_used=tables_used,
        filters_applied=filters_applied,
        sql_executed=[],
        evidence_rows=evidence_rows,
        quality_flag=quality_flag,
    )
    source_suffix = "sidecar" if "dexter_sidecar" in tables_used else "cli"
    result_meta = AgentResultMeta(
        trace_id=trace_id,
        basis=request.basis,
        result_kind="agent.dexter",
        formal_use_allowed=False,
        source_version=f"sv_dexter_{source_suffix}",
        vendor_version="vv_dexter",
        rule_version=RULE_VERSION,
        cache_version="cv_agent_dexter_v1",
        quality_flag=quality_flag,
        vendor_status="ok",
        fallback_mode="none",
        scenario_flag=request.basis == Basis.SCENARIO.value,
        generated_at=generated_at,
        tables_used=evidence.tables_used,
        filters_applied=evidence.filters_applied,
        sql_executed=[],
        evidence_rows=evidence.evidence_rows,
    )
    return AgentEnvelope(
        answer=str(result.get("answer") or ""),
        cards=_build_dexter_cards(result=result, research_context=research_context),
        evidence=evidence,
        result_meta=result_meta,
        next_drill=_build_next_drill(result.get("next_drill")),
        suggested_actions=[],
    )


def _build_dexter_command(
    *,
    command: str,
    prompt: str,
    model: str,
    toolsets: str,
) -> list[str]:
    args = [command, "query", "--json", "--prompt", prompt]
    if model:
        args.extend(["--model", model])
    if toolsets:
        args.extend(["--toolsets", toolsets])
    return args


def _post_dexter_bridge_query(
    *,
    bridge_url: str,
    prompt: str,
    model: str,
    toolsets: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    url = urllib.parse.urljoin(bridge_url.rstrip("/") + "/", "query")
    body = json.dumps(
        {
            "prompt": prompt,
            "model": model,
            "toolsets": toolsets,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(timeout_seconds, 1.0)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Dexter sidecar failed: {_truncate(detail, 2000)}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Dexter sidecar unavailable: {exc}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Dexter sidecar returned an invalid payload.")
    if not payload.get("ok", True):
        raise RuntimeError(str(payload.get("error") or "Dexter sidecar query failed."))

    return {
        "answer": str(payload.get("answer") or ""),
        "stdout": str(payload.get("stdout") or payload.get("answer") or ""),
        "stderr": str(payload.get("stderr") or ""),
        "command": "dexter_sidecar",
        "tool_name": str(payload.get("tool_name") or "dexter_sidecar"),
        "model": str(payload.get("model") or model or "default"),
        "toolsets": str(payload.get("toolsets") or toolsets or "default"),
        "transport": "sidecar",
        "tables_used": _normalize_tables_used(payload.get("tables_used"), fallback="dexter_sidecar"),
        **_structured_research_fields(payload),
    }


def _build_dexter_prompt(
    request: AgentQueryRequest,
    *,
    research_context: dict[str, Any] | None = None,
) -> str:
    context = {
        "basis": request.basis,
        "filters": request.filters,
        "position_scope": request.position_scope,
        "currency_basis": request.currency_basis,
        "context": request.context,
        "page_context": request.page_context.model_dump(mode="json") if request.page_context else None,
    }
    prompt = (
        "You are Dexter connected to the MOSS business analytics system. "
        "Answer the user's question directly and summarize any evidence or limitations. "
        "When research context is available, use only the landed MOSS Choice/TuShare data shown there. "
        "Do not provide trading instructions, buy/sell ratings, target prices, or formal financial metric conclusions. "
        "Return a concise research response with summary, findings, evidence, risks, limitations, and next_drill.\n\n"
        f"User question:\n{request.question}\n\n"
        f"MOSS request context:\n{context}"
    )
    if research_context and research_context.get("domain"):
        prompt += "\n\nMOSS research context:\n" + json.dumps(
            research_context,
            ensure_ascii=False,
            default=str,
            indent=2,
        )
    return prompt


def _append_dexter_audit(
    request: AgentQueryRequest,
    governance_dir: str,
    envelope: AgentEnvelope,
    result: dict[str, Any],
) -> None:
    repo = GovernanceRepository(base_dir=governance_dir)
    append_agent_audit(
        repo,
        AgentAuditPayload(
            user_id=str(request.context.get("user_id") or "unknown"),
            query_text=request.question,
            tools_used=[str(result.get("tool_name") or "dexter_cli")],
            tables_used=envelope.evidence.tables_used,
            filters_applied=envelope.evidence.filters_applied,
            trace_id=envelope.result_meta.trace_id,
            result_meta={
                **envelope.result_meta.model_dump(mode="json"),
                "dexter_tool_name": str(result.get("tool_name") or "dexter_cli"),
                "stdout_excerpt": _truncate(str(result.get("stdout") or ""), 1000),
                "stderr_excerpt": _truncate(str(result.get("stderr") or ""), 1000),
            },
        ),
    )


def _parse_dexter_output(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"answer": text}
    return payload if isinstance(payload, dict) else {"answer": text}


def _structured_research_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: payload[key]
        for key in ("summary", "findings", "evidence", "risks", "limitations", "next_drill")
        if key in payload
    }


def _build_dexter_cards(
    *,
    result: dict[str, Any],
    research_context: dict[str, Any] | None,
) -> list[AgentCard]:
    cards = [
        AgentCard(type="text", title="Dexter Agent", value=str(result.get("answer") or "")),
        AgentCard(type="metric", title="Provider", value="dexter"),
        AgentCard(type="metric", title="Model", value=str(result.get("model") or "default")),
        AgentCard(type="metric", title="Tool", value=str(result.get("tool_name") or "dexter_cli")),
    ]
    if not research_context or not research_context.get("domain"):
        return cards

    summary = str(result.get("summary") or result.get("answer") or "").strip()
    if summary:
        cards.append(AgentCard(type="research_summary", title="Research Summary", value=summary))
    _append_list_card(cards, title="Research Findings", card_type="research_findings", value=result.get("findings"))
    _append_list_card(cards, title="Research Evidence", card_type="research_evidence", value=result.get("evidence"))
    _append_list_card(cards, title="Research Risks", card_type="research_risks", value=result.get("risks"))
    limitations = result.get("limitations") or research_context.get("limitations")
    _append_list_card(cards, title="Research Limitations", card_type="research_limitations", value=limitations)
    _append_list_card(cards, title="Next Drill", card_type="research_next_drill", value=result.get("next_drill"))
    return cards


def _append_list_card(
    cards: list[AgentCard],
    *,
    title: str,
    card_type: str,
    value: Any,
) -> None:
    items = _normalize_string_list(value)
    if not items:
        return
    cards.append(
        AgentCard(
            type=card_type,
            title=title,
            data=[{"item": item} for item in items],
            spec={"columns": ["item"]},
        )
    )


def _build_next_drill(value: Any) -> list[Any]:
    return [{"dimension": "research", "label": item} for item in _normalize_string_list(value)]


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_toolsets(toolsets: str) -> str:
    return ",".join(part.strip() for part in str(toolsets or "").split(",") if part.strip())


def _normalize_tables_used(value: Any, *, fallback: str) -> list[str]:
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if normalized:
            return normalized
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return [fallback]


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
