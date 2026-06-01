from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChoiceNewsTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_code: str
    topic_name: str


class ChoiceNewsGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    group_name: str
    is_core: bool = False
    tags: list[str] = Field(default_factory=list)
    topics: list[ChoiceNewsTopic]


class ChoiceNewsTopicsAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    vendor_name: str
    generated_at: datetime
    generated_from: str
    subscription_mode: str
    content_type: str
    callback_name: str
    groups: list[ChoiceNewsGroup]
