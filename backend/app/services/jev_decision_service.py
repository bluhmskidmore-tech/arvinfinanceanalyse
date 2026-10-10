"""Small, fail-closed Jev decision adapter for the MOSS agent boundary.

The default mode is local/off.  When shadow or active mode is explicitly
configured, the optional Typesafe endpoint receives only routing metadata; the
user question, filters, page rows, and financial values never leave MOSS from
this adapter.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Literal

from backend.app.agent.runtime.local_request_resolution import LocalRequestResolution
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from pydantic import BaseModel, ConfigDict, Field

JevMode = Literal["off", "shadow", "active"]
JevRoute = Literal["allow_pi", "fallback_local", "clarify", "reject"]

_DEFAULT_API_URL = "https://api.typesafe.ai/v1/systemone"
_DEFAULT_MODEL = "jev-latest"
_ROUTES: tuple[JevRoute, ...] = ("allow_pi", "fallback_local", "clarify", "reject")


class JevDecision(BaseModel):
    """Governed Jev output consumed by the Pi adapter and audit layer."""

    model_config = ConfigDict(extra="forbid")

    mode: JevMode
    route: JevRoute
    allowed: bool
    reason_code: str = Field(min_length=1)
    source: Literal["local", "external"] = "local"
    model: str = "local"
    confidence: float | None = Field(default=None, ge=0, le=1)
    probabilities: dict[str, float] = Field(default_factory=dict)
    external_route: JevRoute | None = None
    external_confidence: float | None = Field(default=None, ge=0, le=1)
    external_model: str | None = None
    external_probabilities: dict[str, float] = Field(default_factory=dict)
    error_code: str | None = None


class JevExternalError(RuntimeError):
    """An external Jev call failed without exposing response contents."""

    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


def build_jev_state(
    request: AgentQueryRequest,
    resolution: LocalRequestResolution,
) -> dict[str, Any]:
    """Build a structural decision state with no user or financial payload."""

    question = str(request.question or "")
    return {
        "route": resolution.route,
        "reason": resolution.reason,
        "basis": request.basis,
        "routing_surface": request.routing_surface,
        "question_class": "cjk" if any("\u4e00" <= char <= "\u9fff" for char in question) else "latin",
        "question_chars": len(question),
        "has_page_context": request.page_context is not None,
        "semantic_status": resolution.semantic_status,
        "semantic_operation": resolution.semantic_operation,
        "metric_id": resolution.metric_id,
    }


def decide_jev(
    request: AgentQueryRequest,
    settings: Any,
    *,
    resolution: LocalRequestResolution,
) -> JevDecision:
    """Return a local decision or an explicitly configured external decision.

    Shadow mode never changes execution.  Active mode refuses Pi execution if
    Jev is not configured, unavailable, ambiguous, or below the confidence
    threshold.
    """

    mode = _configured_mode(settings)
    local_decision = _local_decision(mode=mode, resolution=resolution)
    if mode == "off":
        return local_decision

    api_key = str(os.environ.get("TYPESAFE_API_KEY") or "").strip()
    if not api_key:
        if mode == "shadow":
            return local_decision.model_copy(
                update={
                    "reason_code": "jev_shadow_not_configured",
                    "error_code": "jev_api_key_missing",
                }
            )
        return JevDecision(
            mode="active",
            route="reject",
            allowed=False,
            reason_code="jev_api_key_missing",
            error_code="jev_api_key_missing",
        )

    try:
        external = _call_external_jev(
            state=build_jev_state(request, resolution),
            api_url=str(getattr(settings, "agent_jev_api_url", _DEFAULT_API_URL) or _DEFAULT_API_URL),
            api_key=api_key,
            model=str(getattr(settings, "agent_jev_model", _DEFAULT_MODEL) or _DEFAULT_MODEL),
            timeout_seconds=float(getattr(settings, "agent_jev_timeout_seconds", 2.0) or 2.0),
            min_confidence=float(getattr(settings, "agent_jev_min_confidence", 0.85) or 0.85),
        )
    except JevExternalError as exc:
        if mode == "shadow":
            return local_decision.model_copy(
                update={
                    "reason_code": "jev_shadow_external_failed",
                    "error_code": exc.error_code,
                }
            )
        return JevDecision(
            mode="active",
            route="reject",
            allowed=False,
            reason_code="jev_external_failed",
            error_code=exc.error_code,
        )

    if mode == "shadow":
        return local_decision.model_copy(
            update={
                "reason_code": "jev_shadow_observed",
                "external_route": external.route,
                "external_confidence": external.confidence,
                "external_model": external.model,
                "external_probabilities": external.probabilities,
                "error_code": external.error_code,
            }
        )
    return external


def _configured_mode(settings: Any) -> JevMode:
    value = str(getattr(settings, "agent_jev_mode", "off") or "off").strip().lower()
    return value if value in {"off", "shadow", "active"} else "off"  # type: ignore[return-value]


def _local_decision(*, mode: JevMode, resolution: LocalRequestResolution) -> JevDecision:
    if resolution.route != "provider":
        return JevDecision(
            mode=mode,
            route="fallback_local",
            allowed=False,
            reason_code="local_route_not_pi",
        )
    return JevDecision(
        mode=mode,
        route="allow_pi",
        allowed=True,
        reason_code="provider_route_allowed",
    )


def _call_external_jev(
    *,
    state: dict[str, Any],
    api_url: str,
    api_key: str,
    model: str,
    timeout_seconds: float,
    min_confidence: float,
) -> JevDecision:
    payload = {
        "model": model,
        "state": state,
        "questions": {
            "route": {
                "type": "choice",
                "instructions": "Choose the safest route for this structural MOSS request.",
                "criteria": {
                    "allow_pi": "The request may use the bounded Pi narrative provider.",
                    "fallback_local": "The request belongs on a governed local path.",
                    "clarify": "The request is ambiguous and needs clarification.",
                    "reject": "The request must not be executed by an agent provider.",
                },
            }
        },
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        str(api_url).strip() or _DEFAULT_API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=max(float(timeout_seconds), 0.1),
        ) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise JevExternalError(f"jev_http_{exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise JevExternalError("jev_transport_unavailable") from exc

    try:
        response_payload = json.loads(raw.decode("utf-8", errors="replace"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise JevExternalError("jev_invalid_json") from exc
    if not isinstance(response_payload, dict):
        raise JevExternalError("jev_invalid_payload")

    choice, confidence, probabilities = _extract_route_answer(response_payload)
    route = _normalize_route(choice)
    if route is None:
        raise JevExternalError("jev_invalid_route")
    if confidence is None:
        raise JevExternalError("jev_confidence_missing")
    if confidence < max(min(float(min_confidence), 1.0), 0.0):
        return JevDecision(
            mode="active",
            route="reject",
            allowed=False,
            reason_code="jev_confidence_below_threshold",
            source="external",
            model=model,
            confidence=confidence,
            probabilities=probabilities,
            error_code="jev_low_confidence",
        )
    return JevDecision(
        mode="active",
        route=route,
        allowed=route == "allow_pi",
        reason_code=f"jev_external_{route}",
        source="external",
        model=model,
        confidence=confidence,
        probabilities=probabilities,
    )


def _extract_route_answer(payload: dict[str, Any]) -> tuple[str, float | None, dict[str, float]]:
    answers = payload.get("answers") or payload.get("results") or payload.get("data")
    answer: Any = answers.get("route") if isinstance(answers, dict) else None
    if answer is None and isinstance(answers, list):
        for item in answers:
            if not isinstance(item, dict):
                continue
            if str(item.get("id") or item.get("question") or item.get("name") or "").strip() == "route":
                answer = item
                break
    if answer is None:
        answer = payload.get("route")

    if isinstance(answer, dict):
        choice = str(answer.get("choice") or answer.get("answer") or answer.get("value") or "")
        confidence = _optional_probability(answer.get("confidence"))
        probabilities = _probabilities(answer.get("probabilities"))
    else:
        choice = str(answer or "")
        confidence = _optional_probability(payload.get("confidence"))
        probabilities = _probabilities(payload.get("probabilities"))
    if confidence is None and probabilities:
        confidence = max(probabilities.values())
    return choice.strip().lower(), confidence, probabilities


def _normalize_route(value: Any) -> JevRoute | None:
    normalized = str(value or "").strip().lower().replace("-", "_")
    return normalized if normalized in _ROUTES else None


def _optional_probability(value: Any) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    return min(max(normalized, 0.0), 1.0)


def _probabilities(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, float] = {}
    for key, raw_value in value.items():
        probability = _optional_probability(raw_value)
        if probability is not None:
            result[str(key)] = probability
    return result
