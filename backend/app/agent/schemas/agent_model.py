from typing import Literal

from pydantic import BaseModel, Field

AgentReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"]


class AgentModelOption(BaseModel):
    id: str = Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]*$")
    label: str = Field(min_length=1, max_length=128)
    reasoning_efforts: list[AgentReasoningEffort] = Field(default_factory=list, max_length=8)
    default_reasoning_effort: AgentReasoningEffort | None = None


class AgentModelCatalog(BaseModel):
    provider: str
    default_model: str
    models: list[AgentModelOption] = Field(default_factory=list, max_length=100)
    source: Literal["live", "cache", "configured"] = "configured"
