from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.app.repositories.governance_repo import GovernanceRepository

AGENT_WORKSPACE_PROJECT_STREAM = "agent_workspace_project"
AGENT_WORKSPACE_CONVERSATION_STREAM = "agent_workspace_conversation"
AGENT_RUN_STREAM = "agent_run"


@dataclass
class AgentWorkspaceRepository:
    governance_dir: Path | str

    def __post_init__(self) -> None:
        self.governance_dir = Path(self.governance_dir).resolve()

    def append_project(self, payload: dict[str, object]) -> dict[str, object]:
        GovernanceRepository(base_dir=self.governance_dir).append(
            AGENT_WORKSPACE_PROJECT_STREAM,
            payload,
        )
        return payload

    def list_latest_projects(self) -> list[dict[str, object]]:
        return self._latest_records(
            stream=AGENT_WORKSPACE_PROJECT_STREAM,
            identifier_field="project_id",
        )

    def get_latest_project(self, project_id: str) -> dict[str, object] | None:
        return self._latest_record(
            stream=AGENT_WORKSPACE_PROJECT_STREAM,
            identifier_field="project_id",
            identifier=project_id,
        )

    def append_conversation(self, payload: dict[str, object]) -> dict[str, object]:
        GovernanceRepository(base_dir=self.governance_dir).append(
            AGENT_WORKSPACE_CONVERSATION_STREAM,
            payload,
        )
        return payload

    def list_latest_conversations(self) -> list[dict[str, object]]:
        return self._latest_records(
            stream=AGENT_WORKSPACE_CONVERSATION_STREAM,
            identifier_field="conversation_id",
        )

    def get_latest_conversation(
        self,
        conversation_id: str,
    ) -> dict[str, object] | None:
        return self._latest_record(
            stream=AGENT_WORKSPACE_CONVERSATION_STREAM,
            identifier_field="conversation_id",
            identifier=conversation_id,
        )

    def list_latest_run_records(self) -> list[dict[str, object]]:
        return self._latest_records(
            stream=AGENT_RUN_STREAM,
            identifier_field="run_id",
        )

    def get_latest_run_record(self, run_id: str) -> dict[str, object] | None:
        return self._latest_record(
            stream=AGENT_RUN_STREAM,
            identifier_field="run_id",
            identifier=run_id,
        )

    def _latest_records(
        self,
        *,
        stream: str,
        identifier_field: str,
    ) -> list[dict[str, object]]:
        latest: dict[str, dict[str, object]] = {}
        for record in GovernanceRepository(base_dir=self.governance_dir).read_all(stream):
            identifier = str(record.get(identifier_field) or "").strip()
            if identifier:
                latest[identifier] = record
        return [dict(record) for record in latest.values()]

    def _latest_record(
        self,
        *,
        stream: str,
        identifier_field: str,
        identifier: str,
    ) -> dict[str, object] | None:
        normalized_identifier = str(identifier or "").strip()
        if not normalized_identifier:
            return None
        latest: dict[str, object] | None = None
        for record in GovernanceRepository(base_dir=self.governance_dir).read_all(stream):
            if str(record.get(identifier_field) or "").strip() == normalized_identifier:
                latest = record
        return dict(latest) if latest is not None else None
