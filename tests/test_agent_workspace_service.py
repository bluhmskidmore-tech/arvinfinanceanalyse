from __future__ import annotations

from threading import Event, Thread
from types import SimpleNamespace

import pytest
from backend.app.agent.schemas.agent_workspace import (
    AgentConversationCreateRequest,
    AgentProjectCreateRequest,
    AgentProjectUpdateRequest,
)
from backend.app.repositories.agent_workspace_repo import (
    AGENT_RUN_STREAM,
    AGENT_WORKSPACE_PROJECT_STREAM,
    AgentWorkspaceRepository,
)
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.services.agent_workspace_service import (
    AgentWorkspaceStateConflict,
    assert_conversation_owned,
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
from pydantic import ValidationError


def _settings(tmp_path):
    return SimpleNamespace(governance_path=tmp_path)


def _create_project(settings, *, owner: str = "user-1", name: str = "Rates"):
    return create_project(
        settings=settings,
        owner_user_id=owner,
        request=AgentProjectCreateRequest(name=name),
    )


def _create_conversation(settings, project_id: str, *, owner: str = "user-1"):
    return create_conversation(
        settings=settings,
        owner_user_id=owner,
        project_id=project_id,
        request=AgentConversationCreateRequest(title="Daily review"),
    )


def _envelope_payload(answer: str = "Duration drove the move.") -> dict[str, object]:
    return {
        "answer": answer,
        "cards": [],
        "evidence": {
            "tables_used": ["fact_formal_pnl"],
            "filters_applied": {"report_date": "2099-01-31"},
            "sql_executed": [],
            "evidence_rows": 1,
            "quality_flag": "ok",
            "evidence_strength": "governed",
        },
        "result_meta": {
            "trace_id": "trace-workspace-1",
            "basis": "formal",
            "result_kind": "agent.workspace_projection",
            "formal_use_allowed": False,
            "source_version": "sv-test",
            "vendor_version": "vv-none",
            "rule_version": "rv-test",
            "cache_version": "cv-test",
            "quality_flag": "warning",
            "scenario_flag": False,
            "generated_at": "2099-01-31T10:01:00+00:00",
            "tables_used": ["fact_formal_pnl"],
            "filters_applied": {"report_date": "2099-01-31"},
            "sql_executed": [],
            "evidence_rows": 1,
            "evidence_strength": "governed",
        },
        "next_drill": [],
        "suggested_actions": [],
    }


def _run_record(
    *,
    run_id: str,
    owner: str,
    conversation_id: str,
    status: str,
    queued_at: str,
    finished_at: str | None = None,
    result: dict[str, object] | None = None,
    error_message: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        "job_name": "agent_run",
        "run_id": run_id,
        "status": status,
        "question": "What moved the portfolio?",
        "request": {
            "question": "What moved the portfolio?",
            "basis": "formal",
            "filters": {},
            "position_scope": "all",
            "currency_basis": "CNX",
            "context": {
                "user_id": owner,
                "conversation_id": conversation_id,
            },
        },
        "provider": "local",
        "model": "default",
        "transport": "inline",
        "toolsets": "default",
        "queued_at": queued_at,
    }
    if finished_at is not None:
        record["finished_at"] = finished_at
    if result is not None:
        record["result"] = result
    if error_message is not None:
        record["error_message"] = error_message
    return record


def test_workspace_request_dtos_forbid_owner_spoofing() -> None:
    with pytest.raises(ValidationError):
        AgentProjectCreateRequest.model_validate(
            {"name": "Rates", "owner_user_id": "attacker"}
        )
    with pytest.raises(ValidationError):
        AgentProjectUpdateRequest.model_validate(
            {"archived": True, "owner_user_id": "attacker"}
        )
    with pytest.raises(ValidationError):
        AgentConversationCreateRequest.model_validate(
            {"title": "Review", "owner_user_id": "attacker"}
        )


def test_project_lifecycle_is_append_only_owner_scoped_and_archive_aware(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    project = _create_project(settings)
    other = _create_project(settings, owner="user-2", name="Credit")

    owned = list_projects(settings=settings, owner_user_id="user-1")
    assert [item.project_id for item in owned.items] == [project.project_id]
    assert get_project(
        settings=settings,
        owner_user_id="user-2",
        project_id=other.project_id,
    ).name == "Credit"
    with pytest.raises(PermissionError):
        get_project(
            settings=settings,
            owner_user_id="user-2",
            project_id=project.project_id,
        )
    with pytest.raises(ValueError):
        get_project(
            settings=settings,
            owner_user_id="user-1",
            project_id="project:missing",
        )

    renamed = update_project(
        settings=settings,
        owner_user_id="user-1",
        project_id=project.project_id,
        request=AgentProjectUpdateRequest(name="Rates and FX"),
    )
    archived = update_project(
        settings=settings,
        owner_user_id="user-1",
        project_id=project.project_id,
        request=AgentProjectUpdateRequest(archived=True),
    )
    assert renamed.name == "Rates and FX"
    assert archived.archived_at is not None
    assert list_projects(settings=settings, owner_user_id="user-1").items == []
    assert [
        item.project_id
        for item in list_projects(
            settings=settings,
            owner_user_id="user-1",
            include_archived=True,
        ).items
    ] == [project.project_id]
    assert get_project(
        settings=settings,
        owner_user_id="user-1",
        project_id=project.project_id,
    ).archived_at == archived.archived_at

    project_events = GovernanceRepository(base_dir=tmp_path).read_all(
        AGENT_WORKSPACE_PROJECT_STREAM
    )
    matching = [
        event for event in project_events if event["project_id"] == project.project_id
    ]
    assert [event["name"] for event in matching] == [
        "Rates",
        "Rates and FX",
        "Rates and FX",
    ]


def test_conversation_lifecycle_enforces_owner_and_archived_write_boundary(
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    project = _create_project(settings)
    conversation = _create_conversation(settings, project.project_id)

    assert list_conversations(
        settings=settings,
        owner_user_id="user-1",
        project_id=project.project_id,
    ).items == [conversation]
    assert get_conversation(
        settings=settings,
        owner_user_id="user-1",
        conversation_id=conversation.conversation_id,
    ) == conversation
    with pytest.raises(PermissionError):
        get_conversation(
            settings=settings,
            owner_user_id="user-2",
            conversation_id=conversation.conversation_id,
        )
    with pytest.raises(ValueError):
        get_conversation(
            settings=settings,
            owner_user_id="user-1",
            conversation_id="conversation:missing",
        )

    update_project(
        settings=settings,
        owner_user_id="user-1",
        project_id=project.project_id,
        request=AgentProjectUpdateRequest(archived=True),
    )
    assert get_conversation(
        settings=settings,
        owner_user_id="user-1",
        conversation_id=conversation.conversation_id,
    ).conversation_id == conversation.conversation_id
    with pytest.raises(AgentWorkspaceStateConflict):
        assert_conversation_owned(
            settings=settings,
            owner_user_id="user-1",
            conversation_id=conversation.conversation_id,
            require_active=True,
        )
    with pytest.raises(AgentWorkspaceStateConflict):
        create_conversation(
            settings=settings,
            owner_user_id="user-1",
            project_id=project.project_id,
            request=AgentConversationCreateRequest(title="Blocked"),
        )


def test_archive_serializes_against_new_conversation(
    monkeypatch,
    tmp_path,
) -> None:
    settings = _settings(tmp_path)
    project = _create_project(settings)
    archive_append_started = Event()
    allow_archive_append = Event()
    archive_done = Event()
    conversation_done = Event()
    archive_errors: list[BaseException] = []
    conversation_errors: list[BaseException] = []
    original_append_project = AgentWorkspaceRepository.append_project

    def blocking_append_project(
        repository: AgentWorkspaceRepository,
        payload: dict[str, object],
    ) -> dict[str, object]:
        if payload.get("archived_at"):
            archive_append_started.set()
            if not allow_archive_append.wait(timeout=2.0):
                raise AssertionError("Timed out waiting to release archive append.")
        return original_append_project(repository, payload)

    monkeypatch.setattr(
        AgentWorkspaceRepository,
        "append_project",
        blocking_append_project,
    )

    def archive_project() -> None:
        try:
            update_project(
                settings=settings,
                owner_user_id="user-1",
                project_id=project.project_id,
                request=AgentProjectUpdateRequest(archived=True),
            )
        except BaseException as exc:  # pragma: no cover - assertion reports below
            archive_errors.append(exc)
        finally:
            archive_done.set()

    def create_after_archive_starts() -> None:
        try:
            create_conversation(
                settings=settings,
                owner_user_id="user-1",
                project_id=project.project_id,
                request=AgentConversationCreateRequest(title="Must be blocked"),
            )
        except BaseException as exc:  # pragma: no cover - assertion reports below
            conversation_errors.append(exc)
        finally:
            conversation_done.set()

    archive_thread = Thread(target=archive_project)
    conversation_thread = Thread(target=create_after_archive_starts)
    archive_thread.start()
    assert archive_append_started.wait(timeout=2.0)
    conversation_thread.start()
    assert not conversation_done.wait(timeout=0.1)

    allow_archive_append.set()
    archive_thread.join(timeout=2.0)
    conversation_thread.join(timeout=2.0)

    assert archive_done.is_set()
    assert conversation_done.is_set()
    assert archive_errors == []
    assert len(conversation_errors) == 1
    assert isinstance(conversation_errors[0], AgentWorkspaceStateConflict)
    assert list_conversations(
        settings=settings,
        owner_user_id="user-1",
        project_id=project.project_id,
    ).items == []


def test_messages_and_artifacts_are_authoritative_run_projections(tmp_path) -> None:
    settings = _settings(tmp_path)
    project = _create_project(settings)
    conversation = _create_conversation(settings, project.project_id)
    governance = GovernanceRepository(base_dir=tmp_path)

    run_id = "agent_run:workspace:one"
    governance.append(
        AGENT_RUN_STREAM,
        _run_record(
            run_id=run_id,
            owner="user-1",
            conversation_id=conversation.conversation_id,
            status="queued",
            queued_at="2099-01-31T10:00:00+00:00",
        ),
    )
    governance.append(
        AGENT_RUN_STREAM,
        _run_record(
            run_id=run_id,
            owner="user-1",
            conversation_id=conversation.conversation_id,
            status="completed",
            queued_at="2099-01-31T10:00:00+00:00",
            finished_at="2099-01-31T10:01:00+00:00",
            result=_envelope_payload(),
        ),
    )
    failed_run_id = "agent_run:workspace:failed"
    governance.append(
        AGENT_RUN_STREAM,
        _run_record(
            run_id=failed_run_id,
            owner="user-1",
            conversation_id=conversation.conversation_id,
            status="failed",
            queued_at="2099-01-31T11:00:00+00:00",
            finished_at="2099-01-31T11:01:00+00:00",
            error_message="Provider unavailable.",
        ),
    )
    governance.append(
        AGENT_RUN_STREAM,
        _run_record(
            run_id="agent_run:workspace:foreign",
            owner="user-2",
            conversation_id=conversation.conversation_id,
            status="completed",
            queued_at="2099-01-31T12:00:00+00:00",
            finished_at="2099-01-31T12:01:00+00:00",
            result=_envelope_payload(answer="Must not leak."),
        ),
    )

    projected = get_conversation(
        settings=settings,
        owner_user_id="user-1",
        conversation_id=conversation.conversation_id,
    )
    assert projected.last_run_id == failed_run_id
    assert projected.updated_at == "2099-01-31T11:01:00+00:00"

    messages = list_conversation_messages(
        settings=settings,
        owner_user_id="user-1",
        conversation_id=conversation.conversation_id,
    ).items
    assert [message.role for message in messages] == [
        "user",
        "assistant",
        "user",
        "system_notice",
    ]
    assistant = messages[1]
    assert assistant.message_id == f"message:{run_id}:assistant"
    assert assistant.artifact_refs == [f"artifact:{run_id}"]
    assert assistant.result is not None
    assert assistant.result.result_meta.trace_id == "trace-workspace-1"
    assert assistant.result.result_meta.formal_use_allowed is False
    assert messages[-1].content == "Provider unavailable."
    assert all(message.run_id != "agent_run:workspace:foreign" for message in messages)

    artifacts = list_conversation_artifacts(
        settings=settings,
        owner_user_id="user-1",
        conversation_id=conversation.conversation_id,
    ).items
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.artifact_id == f"artifact:{run_id}"
    assert artifact.content.answer == "Duration drove the move."
    assert artifact.result_meta == artifact.content.result_meta
    assert artifact.result_meta.formal_use_allowed is False
    assert (
        get_artifact(
            settings=settings,
            owner_user_id="user-1",
            artifact_id=artifact.artifact_id,
        )
        == artifact
    )

    with pytest.raises(PermissionError):
        get_artifact(
            settings=settings,
            owner_user_id="user-2",
            artifact_id=artifact.artifact_id,
        )
    with pytest.raises(ValueError):
        get_artifact(
            settings=settings,
            owner_user_id="user-1",
            artifact_id=f"artifact:{failed_run_id}",
        )
    with pytest.raises(ValueError):
        get_artifact(
            settings=settings,
            owner_user_id="user-1",
            artifact_id="artifact:missing",
        )
