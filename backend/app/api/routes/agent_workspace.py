from __future__ import annotations

from typing import Annotated

from backend.app.agent.schemas.agent_workspace import (
    AgentArtifact,
    AgentArtifactListResponse,
    AgentConversation,
    AgentConversationCreateRequest,
    AgentConversationListResponse,
    AgentMessageListResponse,
    AgentProject,
    AgentProjectCreateRequest,
    AgentProjectListResponse,
    AgentProjectUpdateRequest,
)
from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import (
    AuthContext,
    ensure_user_allowed,
    get_auth_context,
)
from backend.app.services.agent_service import phase1_disabled_response
from backend.app.services.agent_workspace_service import (
    AgentWorkspaceStateConflict,
    create_conversation,
    create_project,
    get_artifact,
    get_conversation,
    get_project,
    list_conversation_artifacts,
    list_conversation_messages,
    list_conversations,
    list_projects,
    update_project,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter()


def _ensure_agent_workspace_allowed(
    auth: AuthContext,
    settings: object,
    *,
    action: str,
) -> None:
    if getattr(settings, "agent_enabled", False) is not True:
        raise HTTPException(status_code=503, detail=phase1_disabled_response().detail)
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


def _raise_workspace_http_error(exc: Exception) -> None:
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, AgentWorkspaceStateConflict):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise exc


@router.post("/projects", response_model=AgentProject)
def create_agent_project_endpoint(
    request: AgentProjectCreateRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentProject:
    settings = get_settings()
    _ensure_agent_workspace_allowed(auth, settings, action="write")
    try:
        return create_project(
            settings=settings,
            owner_user_id=auth.user_id,
            request=request,
        )
    except (PermissionError, ValueError, AgentWorkspaceStateConflict) as exc:
        _raise_workspace_http_error(exc)
        raise AssertionError("unreachable")


@router.get("/projects", response_model=AgentProjectListResponse)
def list_agent_projects_endpoint(
    auth: Annotated[AuthContext, Depends(get_auth_context)],
    include_archived: Annotated[bool, Query()] = False,
) -> AgentProjectListResponse:
    settings = get_settings()
    _ensure_agent_workspace_allowed(auth, settings, action="read")
    return list_projects(
        settings=settings,
        owner_user_id=auth.user_id,
        include_archived=include_archived,
    )


@router.get("/projects/{project_id}", response_model=AgentProject)
def get_agent_project_endpoint(
    project_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentProject:
    settings = get_settings()
    _ensure_agent_workspace_allowed(auth, settings, action="read")
    try:
        return get_project(
            settings=settings,
            owner_user_id=auth.user_id,
            project_id=project_id,
        )
    except (PermissionError, ValueError, AgentWorkspaceStateConflict) as exc:
        _raise_workspace_http_error(exc)
        raise AssertionError("unreachable")


@router.patch("/projects/{project_id}", response_model=AgentProject)
def update_agent_project_endpoint(
    project_id: str,
    request: AgentProjectUpdateRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentProject:
    settings = get_settings()
    _ensure_agent_workspace_allowed(auth, settings, action="write")
    try:
        return update_project(
            settings=settings,
            owner_user_id=auth.user_id,
            project_id=project_id,
            request=request,
        )
    except (PermissionError, ValueError, AgentWorkspaceStateConflict) as exc:
        _raise_workspace_http_error(exc)
        raise AssertionError("unreachable")


@router.post(
    "/projects/{project_id}/conversations",
    response_model=AgentConversation,
)
def create_agent_conversation_endpoint(
    project_id: str,
    request: AgentConversationCreateRequest,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentConversation:
    settings = get_settings()
    _ensure_agent_workspace_allowed(auth, settings, action="write")
    try:
        return create_conversation(
            settings=settings,
            owner_user_id=auth.user_id,
            project_id=project_id,
            request=request,
        )
    except (PermissionError, ValueError, AgentWorkspaceStateConflict) as exc:
        _raise_workspace_http_error(exc)
        raise AssertionError("unreachable")


@router.get(
    "/projects/{project_id}/conversations",
    response_model=AgentConversationListResponse,
)
def list_agent_conversations_endpoint(
    project_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentConversationListResponse:
    settings = get_settings()
    _ensure_agent_workspace_allowed(auth, settings, action="read")
    try:
        return list_conversations(
            settings=settings,
            owner_user_id=auth.user_id,
            project_id=project_id,
        )
    except (PermissionError, ValueError, AgentWorkspaceStateConflict) as exc:
        _raise_workspace_http_error(exc)
        raise AssertionError("unreachable")


@router.get(
    "/conversations/{conversation_id}",
    response_model=AgentConversation,
)
def get_agent_conversation_endpoint(
    conversation_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentConversation:
    settings = get_settings()
    _ensure_agent_workspace_allowed(auth, settings, action="read")
    try:
        return get_conversation(
            settings=settings,
            owner_user_id=auth.user_id,
            conversation_id=conversation_id,
        )
    except (PermissionError, ValueError, AgentWorkspaceStateConflict) as exc:
        _raise_workspace_http_error(exc)
        raise AssertionError("unreachable")


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=AgentMessageListResponse,
)
def list_agent_conversation_messages_endpoint(
    conversation_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentMessageListResponse:
    settings = get_settings()
    _ensure_agent_workspace_allowed(auth, settings, action="read")
    try:
        return list_conversation_messages(
            settings=settings,
            owner_user_id=auth.user_id,
            conversation_id=conversation_id,
        )
    except (PermissionError, ValueError, AgentWorkspaceStateConflict) as exc:
        _raise_workspace_http_error(exc)
        raise AssertionError("unreachable")


@router.get(
    "/conversations/{conversation_id}/artifacts",
    response_model=AgentArtifactListResponse,
)
def list_agent_conversation_artifacts_endpoint(
    conversation_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentArtifactListResponse:
    settings = get_settings()
    _ensure_agent_workspace_allowed(auth, settings, action="read")
    try:
        return list_conversation_artifacts(
            settings=settings,
            owner_user_id=auth.user_id,
            conversation_id=conversation_id,
        )
    except (PermissionError, ValueError, AgentWorkspaceStateConflict) as exc:
        _raise_workspace_http_error(exc)
        raise AssertionError("unreachable")


@router.get("/artifacts/{artifact_id}", response_model=AgentArtifact)
def get_agent_artifact_endpoint(
    artifact_id: str,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AgentArtifact:
    settings = get_settings()
    _ensure_agent_workspace_allowed(auth, settings, action="read")
    try:
        return get_artifact(
            settings=settings,
            owner_user_id=auth.user_id,
            artifact_id=artifact_id,
        )
    except (PermissionError, ValueError, AgentWorkspaceStateConflict) as exc:
        _raise_workspace_http_error(exc)
        raise AssertionError("unreachable")
