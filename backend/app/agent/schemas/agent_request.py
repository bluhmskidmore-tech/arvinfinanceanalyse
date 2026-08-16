from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentPageContext(BaseModel):
    page_id: str = Field(..., min_length=1, max_length=128)
    current_filters: dict[str, Any] = Field(default_factory=dict)
    selected_rows: list[dict[str, Any]] = Field(default_factory=list)
    context_note: str | None = Field(default=None, max_length=1000)


class AgentQueryRequest(BaseModel):
    # max_length 与 Hermes prompt 预算联动：超长 question 会在 Windows 上触发
    # CreateProcess ~32K argv 上限，OSError 被吞成静默降级（只加约束不改字段名）。
    question: str = Field(..., min_length=1, max_length=8000)
    basis: Literal["formal", "scenario", "analytical"] = "formal"
    filters: dict[str, Any] = Field(default_factory=dict)
    position_scope: str = "all"
    currency_basis: str = "CNX"
    context: dict[str, Any] = Field(default_factory=dict)
    page_context: AgentPageContext | None = None

