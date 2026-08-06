from __future__ import annotations

import re
from typing import Annotated

from backend.app.agent.runtime.action_token import agent_action_confirmation_token_matches
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentDisabledResponse, AgentEnvelope
from backend.app.agent.schemas.agent_run import (
    AgentRunCreateResponse,
    AgentRunListResponse,
    AgentRunStatusResponse,
)
from backend.app.agent.tools.analysis_view_tool import (
    has_explicit_local_agent_context,
    is_plain_analysis_chat_question,
)
from backend.app.api.routes.agent_workspace import router as workspace_router
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import AuthContext, ensure_user_allowed, get_auth_context
from backend.app.services.agent_run_service import (
    AgentRunDispatchError,
    AgentRunStateConflict,
    cancel_agent_run,
    create_agent_run,
    get_agent_run_owner,
    get_agent_run_status,
    iter_agent_run_events,
    list_agent_runs,
    retry_agent_run,
)
from backend.app.services.agent_service import (
    audit_disabled_agent_query,
    execute_agent_query,
    phase1_disabled_response,
)
from backend.app.services.agent_workspace_service import (
    AgentWorkspaceStateConflict,
    agent_workspace_lifecycle_lock,
    assert_conversation_owned,
)
from backend.app.services.dexter_agent_service import execute_dexter_agent_query
from backend.app.services.hermes_agent_service import execute_hermes_agent_query
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(prefix="/api/agent")


_MUTATING_ACTION_CONTEXT_KEYS = {
    "action",
    "action_type",
    "requested_action",
    "side_effect",
    "tool_action",
}
_MUTATING_ACTION_TOKENS = {
    "command",
    "delete",
    "export",
    "file_write",
    "import",
    "mutate",
    "refresh",
    "shell",
    "write",
    "删除",
    "刷新",
    "导入",
    "导出",
    "命令",
    "写入",
}
_READ_ONLY_AGENT_DETAIL = "Agent endpoints are read-only; mutating actions are not allowed."
_SUGGESTED_ACTION_CONFIRMATION_DETAIL = (
    "Suggested action execution requires a confirmation token."
)
_SUGGESTED_ACTION_CONFIRMATION_TOKEN_PATTERN = re.compile(
    r"^agent_action:v1:\d{1,12}:[0-9a-f]{64}$"
)


def _provider_name(settings: object) -> str:
    return str(getattr(settings, "agent_provider", "local")).strip().lower() or "local"


def _run_executor_for_provider(settings: object):
    provider = _provider_name(settings)
    if provider == "hermes":
        return execute_hermes_agent_query
    if provider == "dexter":
        return execute_dexter_agent_query
    return None


def _should_execute_local_query(request: AgentQueryRequest) -> bool:
    return has_explicit_local_agent_context(request.context) or is_plain_analysis_chat_question(request.question)


def _execute_local_agent_query(
    request: AgentQueryRequest,
    governance_dir: str,
    settings: object,
) -> AgentEnvelope:
    return execute_agent_query(
        request=request,
        duckdb_path=str(getattr(settings, "duckdb_path", "")),
        governance_dir=governance_dir,
    )


def _resolve_agent_executor(request: AgentQueryRequest, settings: object):
    """Shared /query and /runs dispatch: forced-local contexts win, then provider."""
    if _should_execute_local_query(request):
        return "local", _execute_local_agent_query
    executor = _run_executor_for_provider(settings)
    if executor is None:
        return "local", _execute_local_agent_query
    return _provider_name(settings), executor


def _contains_mutating_action(value: object) -> bool:
    if isinstance(value, str):
        normalized = value.strip().lower()
        return any(token in normalized for token in _MUTATING_ACTION_TOKENS)
    if isinstance(value, dict):
        return any(_contains_mutating_action(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_mutating_action(item) for item in value)
    return False


def _enforce_read_only_agent_request(request: AgentQueryRequest) -> None:
    for key, value in request.context.items():
        if key.strip().lower() in _MUTATING_ACTION_CONTEXT_KEYS and _contains_mutating_action(value):
            raise HTTPException(status_code=403, detail=_READ_ONLY_AGENT_DETAIL)


def _enforce_suggested_action_confirmation(request: AgentQueryRequest) -> None:
    action = request.context.get("suggested_action")
    action_requires_confirmation = (
        isinstance(action, dict) and action.get("requires_confirmation") is True
    )
    if request.context.get("suggested_action_requires_confirmation") is not True and not action_requires_confirmation:
        return
    token = str(request.context.get("suggested_action_confirmation_token") or "").strip()
    if not _SUGGESTED_ACTION_CONFIRMATION_TOKEN_PATTERN.fullmatch(token):
        raise HTTPException(status_code=403, detail=_SUGGESTED_ACTION_CONFIRMATION_DETAIL)
    if action is None:
        raise HTTPException(status_code=403, detail=_SUGGESTED_ACTION_CONFIRMATION_DETAIL)
    if not isinstance(action, dict):
        raise HTTPException(status_code=403, detail=_SUGGESTED_ACTION_CONFIRMATION_DETAIL)
    action_payload = action.get("payload")
    if not isinstance(action_payload, dict):
        raise HTTPException(status_code=403, detail=_SUGGESTED_ACTION_CONFIRMATION_DETAIL)
    if not agent_action_confirmation_token_matches(
        token=token,
        action_type=str(action.get("type") or ""),
        label=str(action.get("label") or ""),
        payload=action_payload,
    ):
        raise HTTPException(status_code=403, detail=_SUGGESTED_ACTION_CONFIRMATION_DETAIL)


def _apply_auth_context(
    request: AgentQueryRequest,
    auth: AuthContext,
) -> AgentQueryRequest:
    client_context = {
        key: value
        for key, value in request.context.items()
        if key.strip().lower()
        not in {"run_id", "retry_of_run_id", "artifact_refs"}
    }
    return request.model_copy(
        update={
            "context": {
                **client_context,
                "user_id": auth.user_id,
                "user_role": auth.role,
                "identity_source": auth.identity_source,
            }
        }
    )


def _ensure_agent_action_allowed(
    auth: AuthContext,
    settings: object,
    *,
    action: str,
) -> None:
    if (
        str(getattr(settings, "environment", "")).strip().lower() == "development"
        and getattr(settings, "agent_dev_scope_bypass", False) is True
    ):
        return
    try:
        ensure_user_allowed(
            auth=auth,
            settings=settings,
            resource="agent",
            action=action,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _ensure_agent_read_allowed(auth: AuthContext, settings: object) -> None:
    _ensure_agent_action_allowed(auth, settings, action="read")


def _ensure_agent_execute_allowed(auth: AuthContext, settings: object) -> None:
    _ensure_agent_action_allowed(auth, settings, action="execute")


def _ensure_agent_enabled(settings: object) -> None:
    """Fail closed before any run authorization, lookup, or dispatch work."""
    if getattr(settings, "agent_enabled", False) is not True:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=phase1_disabled_response().detail,
        )


def _ensure_agent_run_owned_by_auth(
    *,
    run_id: str,
    auth: AuthContext,
    settings: object,
) -> None:
    owner = get_agent_run_owner(run_id=run_id, settings=settings)
    if owner != auth.user_id:
        raise HTTPException(status_code=403, detail="Agent run belongs to a different user.")


def _conversation_id_from_request(request: AgentQueryRequest) -> str | None:
    if "conversation_id" not in request.context:
        return None
    value = request.context.get("conversation_id")
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(
            status_code=422,
            detail="context.conversation_id must be a non-empty string.",
        )
    return value.strip()


def _ensure_agent_conversation_owned_by_auth(
    *,
    conversation_id: str,
    auth: AuthContext,
    settings: object,
    require_active: bool,
) -> None:
    try:
        assert_conversation_owned(
            settings=settings,
            owner_user_id=auth.user_id,
            conversation_id=conversation_id,
            require_active=require_active,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentWorkspaceStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/query", response_model=AgentEnvelope | AgentDisabledResponse)
def query_agent(
    request: AgentQueryRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentEnvelope | JSONResponse:
    request = _apply_auth_context(request, auth)
    _enforce_read_only_agent_request(request)
    _enforce_suggested_action_confirmation(request)
    settings = get_settings()
    if not settings.agent_enabled:
        audit_disabled_agent_query(
            request=request,
            governance_dir=str(settings.governance_path),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=phase1_disabled_response().model_dump(mode="json"),
        )

    _ensure_agent_read_allowed(auth, settings)

    try:
        _provider, executor = _resolve_agent_executor(request, settings)
        return executor(request, str(settings.governance_path), settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/runs",
    response_model=AgentRunCreateResponse | AgentEnvelope | AgentDisabledResponse,
    response_model_exclude_none=True,
)
def create_agent_run_endpoint(
    request: AgentQueryRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunCreateResponse | AgentEnvelope | JSONResponse:
    request = _apply_auth_context(request, auth)
    _enforce_read_only_agent_request(request)
    _enforce_suggested_action_confirmation(request)
    settings = get_settings()
    if not settings.agent_enabled:
        audit_disabled_agent_query(
            request=request,
            governance_dir=str(settings.governance_path),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=phase1_disabled_response().model_dump(mode="json"),
        )
    _ensure_agent_read_allowed(auth, settings)
    conversation_id = _conversation_id_from_request(request)
    if conversation_id is not None:
        request = request.model_copy(
            update={
                "context": {
                    **request.context,
                    "conversation_id": conversation_id,
                }
            }
        )
    provider, _executor = _resolve_agent_executor(request, settings)

    try:
        if conversation_id is not None:
            with agent_workspace_lifecycle_lock(settings=settings):
                _ensure_agent_conversation_owned_by_auth(
                    conversation_id=conversation_id,
                    auth=auth,
                    settings=settings,
                    require_active=True,
                )
                return create_agent_run(
                    request=request,
                    settings=settings,
                    provider=provider,
                )
        return create_agent_run(
            request=request,
            settings=settings,
            provider=provider,
        )
    except AgentWorkspaceStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AgentRunDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/runs",
    response_model=AgentRunListResponse,
    response_model_exclude_none=True,
)
def list_agent_runs_endpoint(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    conversation_id: Annotated[str | None, Query(min_length=1)] = None,
) -> AgentRunListResponse:
    settings = get_settings()
    _ensure_agent_enabled(settings)
    _ensure_agent_read_allowed(auth, settings)
    normalized_conversation_id = (
        str(conversation_id or "").strip() or None
    )
    if conversation_id is not None and normalized_conversation_id is None:
        raise HTTPException(
            status_code=422,
            detail="conversation_id must be a non-empty string.",
        )
    if normalized_conversation_id is not None:
        _ensure_agent_conversation_owned_by_auth(
            conversation_id=normalized_conversation_id,
            auth=auth,
            settings=settings,
            require_active=False,
        )
    return list_agent_runs(
        settings=settings,
        owner_user_id=auth.user_id,
        limit=limit,
        conversation_id=normalized_conversation_id,
    )


@router.post(
    "/runs/{run_id}/cancel",
    response_model=AgentRunStatusResponse,
    response_model_exclude_none=True,
)
def cancel_agent_run_endpoint(
    run_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunStatusResponse:
    settings = get_settings()
    _ensure_agent_enabled(settings)
    _ensure_agent_execute_allowed(auth, settings)
    try:
        _ensure_agent_run_owned_by_auth(
            run_id=run_id,
            auth=auth,
            settings=settings,
        )
        return cancel_agent_run(run_id=run_id, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentRunStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/runs/{run_id}/retry",
    response_model=AgentRunCreateResponse,
    response_model_exclude_none=True,
)
def retry_agent_run_endpoint(
    run_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunCreateResponse:
    settings = get_settings()
    _ensure_agent_enabled(settings)
    _ensure_agent_execute_allowed(auth, settings)
    try:
        _ensure_agent_run_owned_by_auth(
            run_id=run_id,
            auth=auth,
            settings=settings,
        )
        run = get_agent_run_status(run_id=run_id, settings=settings)
        if run.conversation_id is not None:
            with agent_workspace_lifecycle_lock(settings=settings):
                _ensure_agent_conversation_owned_by_auth(
                    conversation_id=run.conversation_id,
                    auth=auth,
                    settings=settings,
                    require_active=True,
                )
                return retry_agent_run(run_id=run_id, settings=settings)
        return retry_agent_run(run_id=run_id, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentRunStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AgentWorkspaceStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AgentRunDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunStatusResponse,
    response_model_exclude_none=True,
)
def get_agent_run_endpoint(
    run_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunStatusResponse:
    settings = get_settings()
    _ensure_agent_enabled(settings)
    _ensure_agent_read_allowed(auth, settings)
    try:
        _ensure_agent_run_owned_by_auth(
            run_id=run_id,
            auth=auth,
            settings=settings,
        )
        return get_agent_run_status(run_id=run_id, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/events")
def get_agent_run_events_endpoint(
    run_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> StreamingResponse:
    settings = get_settings()
    _ensure_agent_enabled(settings)
    _ensure_agent_read_allowed(auth, settings)
    try:
        _ensure_agent_run_owned_by_auth(
            run_id=run_id,
            auth=auth,
            settings=settings,
        )
        initial_status = get_agent_run_status(run_id=run_id, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return StreamingResponse(
        iter_agent_run_events(
            run_id=run_id,
            settings=settings,
            initial_status=initial_status,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


router.include_router(workspace_router)
