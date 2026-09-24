from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CoreDataUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: date
    wait_for_inputs: bool = False
    workflow: Literal["balance_daily", "core_financial"] = "core_financial"
