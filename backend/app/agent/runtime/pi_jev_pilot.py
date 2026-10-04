"""Minimal local pilot for the Pi + Jev + Ontology + MOSS harness boundary.

This module deliberately does not call an external Pi or Jev service.  It
provides the smallest contract-compatible slice so that the integration can
be verified without exporting MOSS data or changing the production provider
router:

* Ontology resolves and pins the request on the server side.
* The Jev-compatible decision is a closed-set, fail-closed decision.
* The Pi-compatible runtime has one bounded turn and one read-only MOSS call.
* MOSS remains responsible for the final ``AgentEnvelope`` and audit record.

The only enabled pilot route is an ontology metric definition.  Numeric
financial execution is intentionally outside this first slice.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from backend.app.agent.runtime.local_request_resolution import (
    SEMANTIC_EXECUTION_CONTEXT_KEY,
    LocalRequestResolution,
    pin_semantic_execution_request,
    resolve_local_request,
    validate_semantic_execution_request,
    validate_semantic_execution_snapshot,
)
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentEnvelope
from backend.app.services.agent_service import execute_agent_query
from pydantic import BaseModel, ConfigDict, Field

JevPilotRoute = Literal["ontology_definition", "blocked"]
JevPilotStopReason = Literal[
    "moss_envelope_returned",
    "semantic_blocked",
    "pilot_scope_blocked",
]


class JevPilotDecision(BaseModel):
    """Closed-set decision returned by the local Jev-compatible adapter."""

    model_config = ConfigDict(extra="forbid")

    route: JevPilotRoute
    allowed: bool
    reason_code: str = Field(min_length=1)
    semantic_status: str | None = None
    semantic_operation: str | None = None
    metric_id: str | None = None
    ontology_revision: str | None = None
    binding_revision: str | None = None


class PiPilotTrace(BaseModel):
    """Bounded execution trace for the local Pi-compatible runtime."""

    model_config = ConfigDict(extra="forbid")

    runtime: Literal["pi_local_pilot"] = "pi_local_pilot"
    max_turns: int = Field(default=1, ge=1, le=1)
    turns_used: int = Field(default=1, ge=0, le=1)
    max_tool_calls: int = Field(default=1, ge=0, le=1)
    tool_calls: int = Field(default=0, ge=0, le=1)
    stop_reason: JevPilotStopReason


@dataclass(frozen=True)
class PiJevPilotResult:
    """Result of the minimal local vertical slice."""

    request: AgentQueryRequest
    decision: JevPilotDecision
    trace: PiPilotTrace
    envelope: AgentEnvelope | None


MossAgentExecutor = Callable[..., AgentEnvelope]


def _server_pin_request(
    request: AgentQueryRequest,
) -> tuple[AgentQueryRequest, LocalRequestResolution]:
    """Accept a server-pinned request or pin an unpinned local request."""

    snapshot = request.context.get(SEMANTIC_EXECUTION_CONTEXT_KEY)
    if snapshot is None:
        return pin_semantic_execution_request(request)

    validate_semantic_execution_snapshot(snapshot)
    validate_semantic_execution_request(request)
    return request, resolve_local_request(request)


def _build_decision(
    resolution: LocalRequestResolution,
    *,
    ontology_revision: str | None,
    binding_revision: str | None,
) -> JevPilotDecision:
    common = {
        "semantic_status": resolution.semantic_status,
        "semantic_operation": resolution.semantic_operation,
        "metric_id": resolution.metric_id,
    }

    if resolution.route != "local" or resolution.semantic_status is None:
        return JevPilotDecision(
            route="blocked",
            allowed=False,
            reason_code="pilot_requires_local_ontology_route",
            **common,
        )

    if resolution.semantic_status != "resolved":
        return JevPilotDecision(
            route="blocked",
            allowed=False,
            reason_code=resolution.semantic_reason_code
            or f"semantic_{resolution.semantic_status}",
            **common,
        )

    if (
        resolution.intent != "ontology_definition"
        or resolution.semantic_operation != "definition"
    ):
        return JevPilotDecision(
            route="blocked",
            allowed=False,
            reason_code="pilot_scope_only_ontology_definition",
            **common,
        )

    return JevPilotDecision(
        route="ontology_definition",
        allowed=True,
        reason_code="ontology_definition_resolved",
        **{
            **common,
            "ontology_revision": ontology_revision,
            "binding_revision": binding_revision,
        },
    )


def run_pi_jev_pilot(
    request: AgentQueryRequest,
    *,
    duckdb_path: str | Path,
    governance_dir: str | Path,
    execute_moss: MossAgentExecutor = execute_agent_query,
) -> PiJevPilotResult:
    """Run one bounded local Pi/Jev/Ontology/MOSS proof.

    The callback is injectable for contract tests, while the default executes
    the real local MOSS agent service.  A blocked Jev decision never reaches a
    MOSS tool, which keeps the pilot fail-closed.
    """

    pinned_request, resolution = _server_pin_request(request)
    snapshot = pinned_request.context.get(SEMANTIC_EXECUTION_CONTEXT_KEY)
    decision = _build_decision(
        resolution,
        ontology_revision=(
            str(snapshot.get("ontology_revision"))
            if isinstance(snapshot, dict) and snapshot.get("ontology_revision")
            else None
        ),
        binding_revision=(
            str(snapshot.get("binding_revision"))
            if isinstance(snapshot, dict) and snapshot.get("binding_revision")
            else None
        ),
    )
    if not decision.allowed:
        stop_reason: JevPilotStopReason = (
            "pilot_scope_blocked"
            if decision.reason_code.startswith("pilot_")
            else "semantic_blocked"
        )
        return PiJevPilotResult(
            request=pinned_request,
            decision=decision,
            trace=PiPilotTrace(stop_reason=stop_reason),
            envelope=None,
        )

    envelope = execute_moss(
        request=pinned_request,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    return PiJevPilotResult(
        request=pinned_request,
        decision=decision,
        trace=PiPilotTrace(tool_calls=1, stop_reason="moss_envelope_returned"),
        envelope=envelope,
    )
