from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QdbGlLineage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_file: str
    source_kind: Literal["ledger_reconciliation", "average_balance", "unknown"]
    report_month: str | None = None
    source_version: str
    rule_version: str
    trace_id: str
    sheet_names: list[str] = Field(default_factory=list)


class QdbGlContractFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    sheet_name: str | None = None
    row_locator: int | None = None
    cell_ref: str | None = None


class QdbGlContractCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    status_label: Literal["pass", "fail", "not_applicable"]
    findings: list[QdbGlContractFinding] = Field(default_factory=list)


class QdbGlBaselineBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["ledger_reconciliation", "average_balance"]
    report_month: str
    path: Path
    source_version: str


class QdbGlBaselineValidationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_status: Literal["bound", "rejected"]
    source_kind: Literal["ledger_reconciliation", "average_balance", "unknown"]
    report_month: str | None = None
    admissible: bool
    status_label: Literal["pass", "fail"]
    source_version: str
    rule_version: str
    trace_id: str
    bound_currency_groups: list[str] = Field(default_factory=list)
    lineage: QdbGlLineage
    checks: list[QdbGlContractCheck] = Field(default_factory=list)
