from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.schemas.result_meta import ResultMeta


AnalysisBasis = Literal["formal", "scenario", "analytical"]


class AnalysisQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consumer: str
    analysis_key: str
    report_date: str
    basis: AnalysisBasis
    view: str | None = None
    scenario_rate_pct: float | None = None
    filters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_basis_inputs(self) -> "AnalysisQuery":
        if self.basis == "scenario" and self.scenario_rate_pct is None:
            raise ValueError("scenario_rate_pct is required when basis=scenario")
        if self.basis != "scenario" and self.scenario_rate_pct is not None:
            raise ValueError("scenario_rate_pct is only allowed when basis=scenario")
        return self


class AnalysisWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    level: Literal["info", "warning", "error"] = "warning"
    message: str


class DrillTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_kind: str
    target_id: str
    label: str


class AttributionSlice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slice_id: str
    label: str
    dimension: str
    value: str
    share_pct: str = "0"
    tone: Literal["positive", "neutral", "negative"] = "neutral"
    drill_targets: list[DrillTarget] = Field(default_factory=list)


class AnalysisResultPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_date: str
    analysis_key: str
    basis: AnalysisBasis
    view: str | None = None
    scenario_rate_pct: float | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    facets: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    attribution: list[AttributionSlice] = Field(default_factory=list)
    warnings: list[AnalysisWarning] = Field(default_factory=list)
    drill_targets: list[DrillTarget] = Field(default_factory=list)


class AnalysisResultEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_meta: ResultMeta
    result: AnalysisResultPayload

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_models(cls, data: Any) -> Any:
        if isinstance(data, dict):
            result_meta = data.get("result_meta")
            if hasattr(result_meta, "model_dump"):
                data = {
                    **data,
                    "result_meta": result_meta.model_dump(mode="python"),
                }
        return data
