from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CoreDataUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: date
    wait_for_inputs: bool = False
    workflow: Literal["balance_daily", "core_financial"] = "core_financial"


class ChoiceStockPitPreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    report_date: date
    source_duckdb_path: str = Field(min_length=1, max_length=1024)
    expected_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ChoiceStockPitHistoryRequest(ChoiceStockPitPreflightRequest):
    expected_plan_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_backup_path: str = Field(min_length=1, max_length=1024)
