from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.app.agent.schemas.agent_response import AgentEnvelope
from backend.app.agent.schemas.agent_workspace import (
    AgentArtifact,
    AgentArtifactListResponse,
    AgentConversation,
    AgentConversationCreateRequest,
    AgentConversationListResponse,
    AgentMessage,
    AgentMessageListResponse,
    AgentProject,
    AgentProjectCreateRequest,
    AgentProjectListResponse,
    AgentProjectUpdateRequest,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.repositories.agent_workspace_repo import AgentWorkspaceRepository
from pydantic import ValidationError

AGENT_WORKSPACE_LIFECYCLE_LOCK = LockDefinition(
    key="lock:agent-workspace:lifecycle",
    ttl_seconds=30,
)

_LOGGER = logging.getLogger(__name__)


class AgentWorkspaceStateConflict(RuntimeError):
    """Raised when a Workspace write conflicts with the current lifecycle state."""


class AgentWorkspaceRecordCorrupt(RuntimeError):
    """Raised when a stored Workspace record exists but can no longer be deserialized.

    Deliberately not a ValueError: the API layer maps ValueError to 404, and a
    corrupt-but-present record must not be reported as missing.
    """


def _corrupt_reason(exc: Exception) -> str:
    """Compact reason string for logs; never includes stored field values."""
    if isinstance(exc, ValidationError):
        parts = [
            f"{'.'.join(str(part) for part in error.get('loc', ())) or '<root>'}"
            f":{error.get('type', 'invalid')}"
            for error in exc.errors()
        ]
        return "; ".join(parts) or "validation_error"
    return type(exc).__name__


def _log_corrupt_record(*, kind: str, identifier: str, reason: str) -> None:
    _LOGGER.warning(
        "Corrupt agent workspace record kind=%s identifier=%s reason=%s",
        kind,
        identifier or "<unknown>",
        reason,
    )


def _corrupt_record_error(
    *,
    kind: str,
    identifier: str,
    reason: str,
) -> AgentWorkspaceRecordCorrupt:
    _log_corrupt_record(kind=kind, identifier=identifier, reason=reason)
    return AgentWorkspaceRecordCorrupt(
        f"Agent workspace {kind} record {identifier or '<unknown>'} is corrupt "
        "and cannot be read."
    )


@contextmanager
def agent_workspace_lifecycle_lock(*, settings: Any) -> Iterator[None]:
    try:
        with acquire_lock(
            AGENT_WORKSPACE_LIFECYCLE_LOCK,
            base_dir=settings.governance_path,
            timeout_seconds=5.0,
        ):
            yield
    except TimeoutError as exc:
        raise AgentWorkspaceStateConflict(
            "Agent workspace lifecycle is busy; retry the request."
        ) from exc


def create_project(
    *,
    settings: Any,
    owner_user_id: str,
    request: AgentProjectCreateRequest,
) -> AgentProject:
    owner = _required_owner(owner_user_id)
    now = _utc_now()
    project = AgentProject(
        project_id=_build_identifier("project"),
        owner_user_id=owner,
        name=request.name,
        default_scope=request.default_scope,
        default_currency_basis=request.default_currency_basis,
        created_at=now,
        updated_at=now,
    )
    _repository(settings).append_project(project.model_dump(mode="json"))
    return project


def list_projects(
    *,
    settings: Any,
    owner_user_id: str,
    include_archived: bool = False,
) -> AgentProjectListResponse:
    owner = _required_owner(owner_user_id)
    # Ownership is decided on the raw record before validation so corrupt
    # records are never surfaced (or counted) across users.
    owned_records = [
        record
        for record in _repository(settings).list_latest_projects()
        if str(record.get("owner_user_id") or "").strip() == owner
        and (include_archived or not record.get("archived_at"))
    ]
    projects: list[AgentProject] = []
    corrupt_records = 0
    for record in owned_records:
        try:
            projects.append(AgentProject.model_validate(record))
        except ValidationError as exc:
            corrupt_records += 1
            _log_corrupt_record(
                kind="project",
                identifier=str(record.get("project_id") or ""),
                reason=_corrupt_reason(exc),
            )
    projects.sort(key=lambda project: _parse_utc(project.updated_at), reverse=True)
    return AgentProjectListResponse(items=projects, corrupt_records=corrupt_records)


def get_project(
    *,
    settings: Any,
    owner_user_id: str,
    project_id: str,
) -> AgentProject:
    owner = _required_owner(owner_user_id)
    record = _repository(settings).get_latest_project(project_id)
    if record is None:
        raise ValueError(f"Unknown agent project_id={project_id}")
    if str(record.get("owner_user_id") or "").strip() != owner:
        raise PermissionError(f"Agent project {project_id} is owned by another user.")
    try:
        return AgentProject.model_validate(record)
    except ValidationError as exc:
        raise _corrupt_record_error(
            kind="project",
            identifier=project_id,
            reason=_corrupt_reason(exc),
        ) from exc


def update_project(
    *,
    settings: Any,
    owner_user_id: str,
    project_id: str,
    request: AgentProjectUpdateRequest,
) -> AgentProject:
    with agent_workspace_lifecycle_lock(settings=settings):
        project = get_project(
            settings=settings,
            owner_user_id=owner_user_id,
            project_id=project_id,
        )
        now = _utc_now()
        archived_at = project.archived_at
        if request.archived is True and archived_at is None:
            archived_at = now
        elif request.archived is False:
            archived_at = None

        updated = project.model_copy(
            update={
                "name": request.name if request.name is not None else project.name,
                "archived_at": archived_at,
                "updated_at": now,
            }
        )
        if updated.model_dump(exclude={"updated_at"}) == project.model_dump(
            exclude={"updated_at"}
        ):
            return project
        _repository(settings).append_project(updated.model_dump(mode="json"))
        return updated


def create_conversation(
    *,
    settings: Any,
    owner_user_id: str,
    project_id: str,
    request: AgentConversationCreateRequest,
) -> AgentConversation:
    with agent_workspace_lifecycle_lock(settings=settings):
        project = get_project(
            settings=settings,
            owner_user_id=owner_user_id,
            project_id=project_id,
        )
        if project.archived_at is not None:
            raise AgentWorkspaceStateConflict(
                f"Agent project {project_id} is archived and cannot accept new conversations."
            )
        now = _utc_now()
        conversation = AgentConversation(
            conversation_id=_build_identifier("conversation"),
            project_id=project.project_id,
            owner_user_id=project.owner_user_id,
            title=request.title,
            created_at=now,
            updated_at=now,
        )
        _repository(settings).append_conversation(
            conversation.model_dump(mode="json")
        )
        return conversation


def list_conversations(
    *,
    settings: Any,
    owner_user_id: str,
    project_id: str,
) -> AgentConversationListResponse:
    project = get_project(
        settings=settings,
        owner_user_id=owner_user_id,
        project_id=project_id,
    )
    repository = _repository(settings)
    # Ownership/project scoping is decided on the raw record before validation
    # so corrupt records are never surfaced (or counted) across users.
    scoped_records = [
        record
        for record in repository.list_latest_conversations()
        if str(record.get("project_id") or "").strip() == project.project_id
        and str(record.get("owner_user_id") or "").strip() == project.owner_user_id
    ]
    conversations: list[AgentConversation] = []
    corrupt_records = 0
    for record in scoped_records:
        try:
            conversations.append(AgentConversation.model_validate(record))
        except ValidationError as exc:
            corrupt_records += 1
            _log_corrupt_record(
                kind="conversation",
                identifier=str(record.get("conversation_id") or ""),
                reason=_corrupt_reason(exc),
            )
    runs = repository.list_latest_run_records()
    projected = [
        _with_latest_run(conversation=conversation, runs=runs)
        for conversation in conversations
    ]
    projected.sort(
        key=lambda conversation: _parse_utc(conversation.updated_at),
        reverse=True,
    )
    return AgentConversationListResponse(
        items=projected,
        corrupt_records=corrupt_records,
    )


def get_conversation(
    *,
    settings: Any,
    owner_user_id: str,
    conversation_id: str,
) -> AgentConversation:
    owner = _required_owner(owner_user_id)
    repository = _repository(settings)
    record = repository.get_latest_conversation(conversation_id)
    if record is None:
        raise ValueError(f"Unknown agent conversation_id={conversation_id}")
    if str(record.get("owner_user_id") or "").strip() != owner:
        raise PermissionError(
            f"Agent conversation {conversation_id} is owned by another user."
        )
    try:
        conversation = AgentConversation.model_validate(record)
    except ValidationError as exc:
        raise _corrupt_record_error(
            kind="conversation",
            identifier=conversation_id,
            reason=_corrupt_reason(exc),
        ) from exc
    get_project(
        settings=settings,
        owner_user_id=owner,
        project_id=conversation.project_id,
    )
    return _with_latest_run(
        conversation=conversation,
        runs=repository.list_latest_run_records(),
    )


def assert_conversation_owned(
    *,
    settings: Any,
    owner_user_id: str,
    conversation_id: str,
    require_active: bool = False,
) -> AgentConversation:
    conversation = get_conversation(
        settings=settings,
        owner_user_id=owner_user_id,
        conversation_id=conversation_id,
    )
    if require_active:
        project = get_project(
            settings=settings,
            owner_user_id=owner_user_id,
            project_id=conversation.project_id,
        )
        if project.archived_at is not None:
            raise AgentWorkspaceStateConflict(
                f"Agent project {project.project_id} is archived and cannot accept new runs."
            )
    return conversation


def list_conversation_messages(
    *,
    settings: Any,
    owner_user_id: str,
    conversation_id: str,
) -> AgentMessageListResponse:
    conversation = assert_conversation_owned(
        settings=settings,
        owner_user_id=owner_user_id,
        conversation_id=conversation_id,
    )
    runs = _owned_conversation_runs(
        repository=_repository(settings),
        owner_user_id=conversation.owner_user_id,
        conversation_id=conversation.conversation_id,
    )
    messages: list[AgentMessage] = []
    corrupt_records = 0
    for run in runs:
        run_id = str(run.get("run_id") or "").strip()
        question = _run_question(run)
        created_at = _run_created_at(run)
        messages.append(
            AgentMessage(
                message_id=f"message:{run_id}:user",
                conversation_id=conversation.conversation_id,
                role="user",
                content=question,
                run_id=run_id,
                created_at=created_at,
            )
        )

        status = str(run.get("status") or "").strip()
        if status == "completed":
            try:
                envelope = _validated_run_envelope(run)
            except AgentWorkspaceRecordCorrupt:
                corrupt_records += 1
            else:
                artifact_id = _artifact_id(run_id)
                messages.append(
                    AgentMessage(
                        message_id=f"message:{run_id}:assistant",
                        conversation_id=conversation.conversation_id,
                        role="assistant",
                        content=envelope.answer,
                        run_id=run_id,
                        artifact_refs=[artifact_id],
                        created_at=_run_updated_at(run),
                        result=envelope,
                    )
                )
        elif status in {"failed", "cancelled"}:
            messages.append(
                AgentMessage(
                    message_id=f"message:{run_id}:system_notice",
                    conversation_id=conversation.conversation_id,
                    role="system_notice",
                    content=_terminal_notice(run),
                    run_id=run_id,
                    created_at=_run_updated_at(run),
                )
            )
    messages.sort(key=lambda message: _parse_utc(message.created_at))
    return AgentMessageListResponse(items=messages, corrupt_records=corrupt_records)


def list_conversation_artifacts(
    *,
    settings: Any,
    owner_user_id: str,
    conversation_id: str,
) -> AgentArtifactListResponse:
    conversation = assert_conversation_owned(
        settings=settings,
        owner_user_id=owner_user_id,
        conversation_id=conversation_id,
    )
    runs = _owned_conversation_runs(
        repository=_repository(settings),
        owner_user_id=conversation.owner_user_id,
        conversation_id=conversation.conversation_id,
    )
    artifacts: list[AgentArtifact] = []
    corrupt_records = 0
    for run in runs:
        try:
            artifact = _artifact_from_run(run, conversation.conversation_id)
        except AgentWorkspaceRecordCorrupt:
            corrupt_records += 1
            continue
        if artifact is not None:
            artifacts.append(artifact)
    artifacts.sort(key=lambda artifact: _parse_utc(artifact.created_at))
    return AgentArtifactListResponse(items=artifacts, corrupt_records=corrupt_records)


def get_artifact(
    *,
    settings: Any,
    owner_user_id: str,
    artifact_id: str,
) -> AgentArtifact:
    owner = _required_owner(owner_user_id)
    run_id = _run_id_from_artifact_id(artifact_id)
    repository = _repository(settings)
    run = repository.get_latest_run_record(run_id)
    if run is None:
        raise ValueError(f"Unknown agent artifact_id={artifact_id}")
    if _run_owner_user_id(run) != owner:
        raise PermissionError(f"Agent artifact {artifact_id} is owned by another user.")
    conversation_id = _run_conversation_id(run)
    if conversation_id is None:
        raise ValueError(f"Unknown agent artifact_id={artifact_id}")
    assert_conversation_owned(
        settings=settings,
        owner_user_id=owner,
        conversation_id=conversation_id,
    )
    artifact = _artifact_from_run(run, conversation_id)
    if artifact is None or artifact.artifact_id != artifact_id:
        raise ValueError(f"Unknown agent artifact_id={artifact_id}")
    return artifact


def _repository(settings: Any) -> AgentWorkspaceRepository:
    return AgentWorkspaceRepository(
        governance_dir=getattr(settings, "governance_path", "data/governance")
    )


def _required_owner(owner_user_id: str) -> str:
    owner = str(owner_user_id or "").strip()
    if not owner:
        raise ValueError("owner_user_id is required")
    return owner


def _with_latest_run(
    *,
    conversation: AgentConversation,
    runs: list[dict[str, object]],
) -> AgentConversation:
    related = [
        run
        for run in runs
        if _run_conversation_id(run) == conversation.conversation_id
        and _run_owner_user_id(run) == conversation.owner_user_id
    ]
    if not related:
        return conversation
    latest = max(related, key=_run_sort_datetime)
    most_recent_update = max(related, key=_run_updated_datetime)
    updated_at = _run_updated_at(most_recent_update)
    if _parse_utc(updated_at) < _parse_utc(conversation.updated_at):
        updated_at = conversation.updated_at
    return conversation.model_copy(
        update={
            "last_run_id": str(latest.get("run_id") or "").strip() or None,
            "updated_at": updated_at,
        }
    )


def _owned_conversation_runs(
    *,
    repository: AgentWorkspaceRepository,
    owner_user_id: str,
    conversation_id: str,
) -> list[dict[str, object]]:
    runs = [
        run
        for run in repository.list_latest_run_records()
        if _run_conversation_id(run) == conversation_id
        and _run_owner_user_id(run) == owner_user_id
    ]
    runs.sort(key=_run_sort_datetime)
    return runs


def _run_owner_user_id(run: dict[str, object]) -> str | None:
    return _run_context_text(run, "user_id")


def _run_conversation_id(run: dict[str, object]) -> str | None:
    direct = str(run.get("conversation_id") or "").strip()
    return direct or _run_context_text(run, "conversation_id")


def _run_context_text(run: dict[str, object], key: str) -> str | None:
    request = run.get("request")
    if not isinstance(request, dict):
        return None
    context = request.get("context")
    if not isinstance(context, dict):
        return None
    value = context.get(key)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _run_question(run: dict[str, object]) -> str:
    direct = str(run.get("question") or "").strip()
    if direct:
        return direct
    request = run.get("request")
    if isinstance(request, dict):
        question = str(request.get("question") or "").strip()
        if question:
            return question
    return "Agent request"


def _validated_run_envelope(run: dict[str, object]) -> AgentEnvelope:
    """Envelope of a completed run.

    Raises AgentWorkspaceRecordCorrupt when the stored result is missing or no
    longer satisfies the current envelope contract.
    """
    run_id = str(run.get("run_id") or "").strip()
    result = run.get("result")
    if not isinstance(result, dict):
        raise _corrupt_record_error(
            kind="run_result",
            identifier=run_id,
            reason="missing_result",
        )
    try:
        return AgentEnvelope.model_validate(result)
    except ValidationError as exc:
        raise _corrupt_record_error(
            kind="run_result",
            identifier=run_id,
            reason=_corrupt_reason(exc),
        ) from exc


def _artifact_from_run(
    run: dict[str, object],
    conversation_id: str,
) -> AgentArtifact | None:
    """Return None when the run yields no artifact.

    Raises AgentWorkspaceRecordCorrupt when a completed run's stored result is
    unreadable, so callers can distinguish "no artifact" from "broken record".
    """
    if str(run.get("status") or "").strip() != "completed":
        return None
    run_id = str(run.get("run_id") or "").strip()
    if not run_id:
        return None
    envelope = _validated_run_envelope(run)
    return AgentArtifact(
        artifact_id=_artifact_id(run_id),
        conversation_id=conversation_id,
        run_id=run_id,
        title=_run_question(run),
        content=envelope,
        result_meta=envelope.result_meta,
        created_at=_run_updated_at(run),
    )


def _artifact_id(run_id: str) -> str:
    return f"artifact:{run_id}"


def _run_id_from_artifact_id(artifact_id: str) -> str:
    normalized = str(artifact_id or "").strip()
    prefix = "artifact:"
    if not normalized.startswith(prefix) or normalized == prefix:
        raise ValueError(f"Unknown agent artifact_id={artifact_id}")
    return normalized[len(prefix) :]


def _terminal_notice(run: dict[str, object]) -> str:
    status = str(run.get("status") or "").strip()
    error_message = str(run.get("error_message") or "").strip()
    if error_message:
        return error_message
    if status == "cancelled":
        return "This Agent run was cancelled."
    return "This Agent run failed."


def _run_created_at(run: dict[str, object]) -> str:
    return _first_timestamp(run, "queued_at", "started_at", "finished_at")


def _run_updated_at(run: dict[str, object]) -> str:
    return _first_timestamp(run, "finished_at", "started_at", "queued_at")


def _run_sort_datetime(run: dict[str, object]) -> datetime:
    return _parse_utc(_run_created_at(run))


def _run_updated_datetime(run: dict[str, object]) -> datetime:
    return _parse_utc(_run_updated_at(run))


def _first_timestamp(run: dict[str, object], *fields: str) -> str:
    for field in fields:
        value = str(run.get(field) or "").strip()
        if value and _try_parse_utc(value) is not None:
            return value
    return datetime.min.replace(tzinfo=UTC).isoformat()


def _parse_utc(value: str) -> datetime:
    parsed = _try_parse_utc(value)
    return parsed or datetime.min.replace(tzinfo=UTC)


def _try_parse_utc(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _build_identifier(prefix: str) -> str:
    return f"{prefix}:{uuid4().hex}"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
