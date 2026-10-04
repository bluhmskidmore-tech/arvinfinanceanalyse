from __future__ import annotations

from datetime import UTC, datetime

from backend.app.repositories.governance_repo import GovernanceRepository
from pydantic import BaseModel, Field

AGENT_PROMPT_STREAM = "agent_prompt"


class AgentPromptPayload(BaseModel):
    """外部 provider 本轮实际送模的 prompt 全文。

    与 agent_audit 用同一个 trace_id 关联：audit 记业务口径的问题与证据，
    本流记模型当时看到的原文。分开存是因为 prompt 含 ontology / research
    context 注入，体积比 audit 摘要高一到两个数量级，保留期也应独立。

    prompt 全文而非"从 request 重建"：Hermes 的注入随 ontology 索引变化，
    Dexter 的 research_context 随新闻与宏观数据变化，两者都无法事后复现；
    重建还会随构建函数改版而漂移，届时历史记录不再是模型看过的那一份。
    """

    provider: str
    user_id: str
    trace_id: str
    prompt: str
    prompt_chars: int
    run_id: str | None = None
    model: str = ""
    toolsets: str = ""
    transport: str = ""
    # 非空表示本轮 prompt 已构建但未取得正常应答（通道故障、超时、解析失败）。
    error_code: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def append_agent_prompt(repo: GovernanceRepository, payload: AgentPromptPayload) -> str:
    return str(
        repo.append(
            AGENT_PROMPT_STREAM,
            payload.model_dump(mode="json", exclude_none=True),
        )
    )
