from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductCategoryRefreshScope(BaseModel):
    """Public execution scope; source discovery is not result certification."""

    model_config = ConfigDict(extra="ignore")

    scanned_report_dates: list[date]
    scanned_years: list[Annotated[str, Field(pattern=r"^[0-9]{4}$")]]
    scanned_date_count: int = Field(ge=0, strict=True)
    rebuilt_report_dates: list[date]
    rebuilt_years: list[Annotated[str, Field(pattern=r"^[0-9]{4}$")]]
    rebuilt_date_count: int = Field(ge=0, strict=True)
    reused_report_dates: list[date]
    reused_years: list[Annotated[str, Field(pattern=r"^[0-9]{4}$")]]
    reused_date_count: int = Field(ge=0, strict=True)
    removed_report_dates: list[date]
    removed_years: list[Annotated[str, Field(pattern=r"^[0-9]{4}$")]]
    removed_date_count: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def check_date_counts(self) -> "ProductCategoryRefreshScope":
        for name in ("scanned", "rebuilt", "reused", "removed"):
            report_dates = getattr(self, f"{name}_report_dates")
            if len(report_dates) != len(set(report_dates)) or getattr(self, f"{name}_date_count") != len(report_dates):
                raise ValueError("Execution scope must contain distinct dates and matching counts.")
        return self


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
