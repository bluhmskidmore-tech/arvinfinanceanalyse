from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentPageContext(BaseModel):
    page_id: str = Field(..., min_length=1, max_length=128)
    current_filters: dict[str, Any] = Field(default_factory=dict)
    selected_rows: list[dict[str, Any]] = Field(default_factory=list)
    context_note: str | None = Field(default=None, max_length=1000)


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    basis: Literal["formal", "scenario", "analytical"] = "formal"
    filters: dict[str, Any] = Field(default_factory=dict)
    position_scope: str = "all"
    currency_basis: str = "CNX"
    context: dict[str, Any] = Field(default_factory=dict)
    page_context: AgentPageContext | None = None

