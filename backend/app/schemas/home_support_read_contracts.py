"""Typed homepage supplemental reads, retaining the existing domain payloads."""

from backend.app.schemas.macro_vendor import ChoiceMacroLatestPayload
from backend.app.schemas.research_calendar import ResearchCalendarResult
from backend.app.schemas.result_meta import ResultMeta
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr


class HomeSupportReadMeta(ResultMeta):
    # Unknown disclosures should fail validation instead of disappearing from JSON.
    model_config = ConfigDict(extra="forbid")


class MarketDataRatesEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_meta: HomeSupportReadMeta
    result: ChoiceMacroLatestPayload


class SupplyAuctionCalendarEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_meta: HomeSupportReadMeta
    result: ResearchCalendarResult


class ChoiceNewsBatchEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_key: StrictStr
    # Keep the repository's timestamp text and timezone without normalizing it.
    received_at: StrictStr
    group_id: StrictStr
    content_type: StrictStr
    serial_id: StrictInt
    request_id: StrictInt
    error_code: StrictInt
    error_msg: StrictStr
    topic_code: StrictStr
    item_index: StrictInt
    payload_text: StrictStr | None
    # This is serialized vendor JSON text, not an arbitrary JSON object.
    payload_json: StrictStr | None
    display_text: StrictStr | None


class ChoiceNewsBatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: StrictStr
    topic_code: StrictStr | None
    group_id: StrictStr | None
    events: list[ChoiceNewsBatchEvent]


class ChoiceNewsBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batches: list[ChoiceNewsBatchItem]


class ChoiceNewsLatestBatchEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_meta: HomeSupportReadMeta
    result: ChoiceNewsBatchPayload
