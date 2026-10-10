from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PnlBasisBridgeComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    amount: Decimal
    evidence_status: Literal[
        "source_traced",
        "rounding_control",
        "source_derived",
        "mapping_pending",
    ]
    note: str


class PnlBasisBridgePath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_code: str
    start_value: Decimal
    components: list[PnlBasisBridgeComponent]
    end_code: str
    end_value: Decimal
    closure_residual: Decimal
    # Core calculation fails loudly before construction; reaching this schema means closed.
    arithmetic_status: Literal["closed"]
    mapping_status: Literal["not_required", "pending_crosswalk"]


class PnlBasisBridgeInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_gross_pnl: Decimal
    system_manual_adjustment: Decimal
    system_unallocated_pnl: Decimal
    system_ftp_cost: Decimal
    system_ftp_net_pnl: Decimal
    formal_recognized_pnl: Decimal
    product_gross_cash_income: Decimal
    product_ftp_cost: Decimal
    product_ftp_net_income: Decimal
    system_identity_residual: Decimal
    product_identity_residual: Decimal


class PnlBasisBridgePeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: Literal["monthly", "ytd"]
    period_start_date: str
    period_end_date: str
    inputs: PnlBasisBridgeInputs
    system_to_formal_gross: PnlBasisBridgePath
    system_to_product_ftp_net: PnlBasisBridgePath


class PnlBasisBridgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    currency_basis: Literal["CNY"] = "CNY"
    unit: Literal["yuan"] = "yuan"
    periods: list[PnlBasisBridgePeriod]
    arithmetic_status: Literal["closed"] = "closed"
    mapping_status: Literal["pending_crosswalk"] = "pending_crosswalk"
    pending_mapping: list[str] = Field(default_factory=list)
