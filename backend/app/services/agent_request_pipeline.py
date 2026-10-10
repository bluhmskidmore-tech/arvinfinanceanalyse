"""Server-side request preparation shared by the Agent entrypoints.

The multi-turn conversation context is rebuilt here from the Workspace message
projection instead of trusting the client payload: a direct API caller would
otherwise have no memory between turns, and any caller could forge prior
answers by sending its own ``context.conversation.recent_turns``.

Key name and turn shape must stay identical to what the workbench sends and
what the providers read (``hermes_agent_service._build_hermes_prompt``,
``local_request_resolution._conversation_intent``,
``analysis_view_tool``): ``context["conversation"]["recent_turns"]`` with
``question`` / ``answer`` / ``run_id`` / ``trace_id`` / ``result_kind``.
"""

from __future__ import annotations

from typing import Any

from backend.app.agent.schemas.agent_request import AgentQueryRequest
from backend.app.agent.schemas.agent_workspace import AgentMessage
from backend.app.services.agent_workspace_service import list_conversation_messages

AGENT_CONVERSATION_CONTEXT_KEY = "conversation"
# Same bounds as the workbench composer (frontend agentWorkbenchModel.ts):
# 4 completed turns, question <= 800 chars, answer <= 1400 chars.
MAX_SERVER_CONVERSATION_TURNS = 4
MAX_SERVER_CONVERSATION_QUESTION_CHARS = 800
MAX_SERVER_CONVERSATION_ANSWER_CHARS = 1400
_TRUNCATION_SUFFIX = "..."


def apply_server_conversation_context(
    *,
    request: AgentQueryRequest,
    settings: Any,
    owner_user_id: str,
    conversation_id: str,
) -> AgentQueryRequest:
    """Replace ``context.conversation`` with the server-owned history.

    The client value is always dropped: an empty conversation yields a request
    without the key at all, so a forged history can never survive. Ownership is
    enforced by `list_conversation_messages`; its exceptions
    (`PermissionError`, `ValueError`, `AgentWorkspaceRecordCorrupt`) propagate
    to the caller for HTTP mapping.
    """
    turns = build_server_conversation_turns(
        settings=settings,
        owner_user_id=owner_user_id,
        conversation_id=conversation_id,
    )
    context = {
        key: value
        for key, value in request.context.items()
        if key != AGENT_CONVERSATION_CONTEXT_KEY
    }
    if turns:
        context[AGENT_CONVERSATION_CONTEXT_KEY] = {"recent_turns": turns}
    return request.model_copy(update={"context": context})


def build_server_conversation_turns(
    *,
    settings: Any,
    owner_user_id: str,
    conversation_id: str,
) -> list[dict[str, object]]:
    """Bounded ``recent_turns`` rebuilt from completed runs of one conversation."""
    messages = list_conversation_messages(
        settings=settings,
        owner_user_id=owner_user_id,
        conversation_id=conversation_id,
    ).items
    questions = {
        message.run_id: message.content
        for message in messages
        if message.role == "user" and message.run_id
    }
    turns: list[dict[str, object]] = []
    for message in messages:
        if message.role != "assistant" or message.result is None:
            continue
        question = _trimmed(
            questions.get(message.run_id, ""),
            MAX_SERVER_CONVERSATION_QUESTION_CHARS,
        )
        answer = _trimmed(message.content, MAX_SERVER_CONVERSATION_ANSWER_CHARS)
        if not question or not answer:
            continue
        turns.append(_turn(question=question, answer=answer, message=message))
    return turns[-MAX_SERVER_CONVERSATION_TURNS:]


def _turn(
    *,
    question: str,
    answer: str,
    message: AgentMessage,
) -> dict[str, object]:
    result_meta = message.result.result_meta if message.result is not None else None
    return {
        "question": question,
        "answer": answer,
        "run_id": message.run_id or None,
        "trace_id": _optional_text(getattr(result_meta, "trace_id", None)),
        "result_kind": _optional_text(getattr(result_meta, "result_kind", None)),
    }


def _trimmed(value: object, limit: int) -> str:
    normalized = str(value or "").strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - len(_TRUNCATION_SUFFIX)]}{_TRUNCATION_SUFFIX}"


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None
