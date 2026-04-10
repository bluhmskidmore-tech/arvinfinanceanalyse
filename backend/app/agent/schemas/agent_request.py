from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    basis: Literal["formal", "scenario", "analytical"] = "formal"
    filters: dict[str, Any] = Field(default_factory=dict)
    position_scope: str = "all"
    currency_basis: str = "CNX"
    context: dict[str, Any] = Field(default_factory=dict)

