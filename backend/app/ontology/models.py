from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OntologyEntityType = Literal[
    "Page",
    "Metric",
    "BusinessConcept",
    "DataField",
    "CalculationRule",
    "SourceSurface",
    "ResultKind",
    "Table",
    "GoldenSample",
    "TestAnchor",
]

OntologyStatus = Literal["approved", "gap", "candidate", "deprecated"]

OntologyRelationshipType = Literal[
    "page_displays_metric",
    "metric_governed_by_rule",
    "metric_bound_to_golden_sample",
    "metric_protected_by_test",
    "result_kind_requires_source_surface",
    "table_supports_metric",
]


class OntologyEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(..., min_length=1)
    entity_type: OntologyEntityType
    name: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    business_definition: str = Field(..., min_length=1)
    unit: str | None = None
    basis: str | None = None
    precision: int | None = None
    time_semantics: str | None = None
    null_semantics: str | None = None
    fallback_allowed: bool | None = None
    authority: list[str] = Field(default_factory=list)
    source_fields: list[str] = Field(default_factory=list)
    calculation_rules: list[str] = Field(default_factory=list)
    result_meta_requirements: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    golden_samples: list[str] = Field(default_factory=list)
    status: OntologyStatus


class OntologyRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., min_length=1)
    type: OntologyRelationshipType
    target: str = Field(..., min_length=1)


class OntologyDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    generated_from: list[str]
    entities: list[OntologyEntity]
    relationships: list[OntologyRelationship] = Field(default_factory=list)
