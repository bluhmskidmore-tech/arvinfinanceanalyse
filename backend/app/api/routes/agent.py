from __future__ import annotations

import logging
import re
from typing import Annotated

from backend.app.agent.runtime.action_token import (
    action_requires_server_confirmation,
    agent_action_confirmation_token_matches,
)
from backend.app.agent.runtime.local_request_resolution import resolve_local_request
from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_response import AgentDisabledResponse, AgentEnvelope
from backend.app.agent.schemas.agent_run import (
    AgentRunCreateResponse,
    AgentRunListResponse,
    AgentRunStatusResponse,
)
from backend.app.api.routes.agent_workspace import (
    _dev_bypass_allowed,
    agent_disabled_json_response,
    router as workspace_router,
    workspace_record_corrupt_error_detail,
)
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
)
from backend.app.services.agent_workspace_service import (
    AgentWorkspaceRecordCorrupt,
    AgentWorkspaceStateConflict,
    agent_workspace_lifecycle_lock,
    assert_conversation_owned,
)
from backend.app.services.dexter_agent_service import execute_dexter_agent_query
from backend.app.services.hermes_agent_service import execute_hermes_agent_query
from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
_SUGGESTED_ACTION_SCOPE_USER_DETAIL = (
    "Suggested action confirmation token is bound to a different user."
)
_SUGGESTED_ACTION_CONFIRMATION_TOKEN_PATTERN = re.compile(
    r"^agent_action:v1:\d{1,12}:[0-9a-f]{64}$"
)
_PROVIDER_EXECUTION_FAILURE_CODE = "AGENT_PROVIDER_EXECUTION_FAILED"
_PROVIDER_EXECUTION_FAILURE_DETAIL = "Agent provider execution failed."
_LOGGER = logging.getLogger(__name__)


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
    return resolve_local_request(request).route == "local"


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
    """Shared /query and /runs dispatch: governed local paths win, then provider."""
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


def _enforce_suggested_action_confirmation(
    request: AgentQueryRequest,
    auth: AuthContext,
) -> None:
    action = request.context.get("suggested_action")
    # 确认要求由服务端目录决定：命中目录的动作即使客户端剥离
    # requires_confirmation 声明也必须携带有效 token。客户端声明仅作为
    # 向后兼容的额外触发条件保留（只收紧，不放宽）。
    server_requires_confirmation = isinstance(action, dict) and action_requires_server_confirmation(
        str(action.get("type") or "")
    )
    client_declares_confirmation = (
        request.context.get("suggested_action_requires_confirmation") is True
        or (isinstance(action, dict) and action.get("requires_confirmation") is True)
    )
    if not server_requires_confirmation and not client_declares_confirmation:
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
    _enforce_confirmation_scope_user(action_payload, auth)


def _enforce_confirmation_scope_user(
    action_payload: dict[str, object],
    auth: AuthContext,
) -> None:
    """纵深防御：签发用户与提交者必须一致（token HMAC 已保证 scope 未被篡改）。

    工具执行层（AnalysisViewTool）有同语义校验；本检查在 token 校验点兜底，
    覆盖未来绕过工具层的新执行路径。无 confirmation_scope 的历史 token 与
    未填 user_id 的 scope 保持放行（向后兼容，仅收紧不放宽）。
    """
    scope = action_payload.get("confirmation_scope")
    if not isinstance(scope, dict):
        return
    issued_user = str(scope.get("user_id") or "").strip()
    if not issued_user:
        return
    if issued_user != str(auth.user_id or "").strip():
        raise HTTPException(status_code=403, detail=_SUGGESTED_ACTION_SCOPE_USER_DETAIL)


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
    http_request: Request,
    action: str,
) -> None:
    if _dev_bypass_allowed(http_request, settings, action=action):
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


def _ensure_agent_read_allowed(
    auth: AuthContext,
    settings: object,
    *,
    http_request: Request,
) -> None:
    _ensure_agent_action_allowed(
        auth,
        settings,
        http_request=http_request,
        action="read",
    )


def _ensure_agent_execute_allowed(
    auth: AuthContext,
    settings: object,
    *,
    http_request: Request,
) -> None:
    _ensure_agent_action_allowed(
        auth,
        settings,
        http_request=http_request,
        action="execute",
    )


def _agent_disabled_response_if_off(settings: object) -> JSONResponse | None:
    """Fail closed before any run authorization, lookup, or dispatch work.

    Every agent endpoint shares the same flat 503 AgentDisabledResponse body so
    clients can detect the disabled state with a single contract.
    """
    if getattr(settings, "agent_enabled", False) is not True:
        return agent_disabled_json_response()
    return None


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
    except AgentWorkspaceRecordCorrupt as exc:
        raise HTTPException(
            status_code=409,
            detail=workspace_record_corrupt_error_detail(),
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentWorkspaceStateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/query", response_model=AgentEnvelope | AgentDisabledResponse)
def query_agent(
    request: AgentQueryRequest,
    http_request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentEnvelope | JSONResponse:
    request = _apply_auth_context(request, auth)
    _enforce_read_only_agent_request(request)
    _enforce_suggested_action_confirmation(request, auth)
    settings = get_settings()
    if not settings.agent_enabled:
        audit_disabled_agent_query(
            request=request,
            governance_dir=str(settings.governance_path),
        )
        return agent_disabled_json_response()

    _ensure_agent_read_allowed(auth, settings, http_request=http_request)

    provider = "local"
    try:
        provider, executor = _resolve_agent_executor(request, settings)
        return executor(request, str(settings.governance_path), settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        if provider != "local":
            _LOGGER.error(
                "Agent provider query failed provider=%s error_type=%s error_code=%s",
                provider,
                exc.__class__.__name__,
                _PROVIDER_EXECUTION_FAILURE_CODE,
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "code": _PROVIDER_EXECUTION_FAILURE_CODE,
                    "message": _PROVIDER_EXECUTION_FAILURE_DETAIL,
                },
            ) from None
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/runs",
    response_model=AgentRunCreateResponse | AgentEnvelope | AgentDisabledResponse,
    response_model_exclude_none=True,
)
def create_agent_run_endpoint(
    request: AgentQueryRequest,
    http_request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunCreateResponse | AgentEnvelope | JSONResponse:
    request = _apply_auth_context(request, auth)
    _enforce_read_only_agent_request(request)
    _enforce_suggested_action_confirmation(request, auth)
    settings = get_settings()
    if not settings.agent_enabled:
        audit_disabled_agent_query(
            request=request,
            governance_dir=str(settings.governance_path),
        )
        return agent_disabled_json_response()
    _ensure_agent_read_allowed(auth, settings, http_request=http_request)
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
    http_request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    conversation_id: Annotated[str | None, Query(min_length=1)] = None,
) -> AgentRunListResponse | JSONResponse:
    settings = get_settings()
    disabled = _agent_disabled_response_if_off(settings)
    if disabled is not None:
        return disabled
    _ensure_agent_read_allowed(auth, settings, http_request=http_request)
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
    http_request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunStatusResponse | JSONResponse:
    settings = get_settings()
    disabled = _agent_disabled_response_if_off(settings)
    if disabled is not None:
        return disabled
    _ensure_agent_execute_allowed(auth, settings, http_request=http_request)
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
    http_request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunCreateResponse | JSONResponse:
    settings = get_settings()
    disabled = _agent_disabled_response_if_off(settings)
    if disabled is not None:
        return disabled
    _ensure_agent_execute_allowed(auth, settings, http_request=http_request)
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
    http_request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentRunStatusResponse | JSONResponse:
    settings = get_settings()
    disabled = _agent_disabled_response_if_off(settings)
    if disabled is not None:
        return disabled
    _ensure_agent_read_allowed(auth, settings, http_request=http_request)
    try:
        _ensure_agent_run_owned_by_auth(
            run_id=run_id,
            auth=auth,
            settings=settings,
        )
        return get_agent_run_status(run_id=run_id, settings=settings)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs/{run_id}/events", response_model=None)
def get_agent_run_events_endpoint(
    run_id: str,
    http_request: Request,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> StreamingResponse | JSONResponse:
    settings = get_settings()
    disabled = _agent_disabled_response_if_off(settings)
    if disabled is not None:
        return disabled
    _ensure_agent_read_allowed(auth, settings, http_request=http_request)
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
