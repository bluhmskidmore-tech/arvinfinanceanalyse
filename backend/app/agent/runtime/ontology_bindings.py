from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import Literal

from backend.app.ontology.loader import load_ontology_index
from backend.app.ontology.models import OntologyEntity
from backend.app.schemas.pnl import PnlOverviewPayload

OntologyMetricOperation = Literal["definition", "value"]

ONTOLOGY_BINDING_REVISION = "ontology-pnl-bindings-v1"
_EXPECTED_CALCULATION_RULES = ("CALC-PNL-FORMAL-MATRIX",)
_EXPECTED_RESULT_META_REQUIREMENTS = (
    "basis=formal",
    "source_surface=formal_pnl",
    "fallback_mode=none",
)
_EXPECTED_NULL_SEMANTICS = "missing formal source is not zero"


@dataclass(frozen=True)
class OntologyMetricBinding:
    metric_id: str
    intent: str
    upstream_result_kind: str
    result_field: str
    allowed_operations: tuple[OntologyMetricOperation, ...] = ("definition", "value")
    required_parameters: tuple[str, ...] = ("report_date",)
    required_resource: str = "pnl"


_BINDINGS: tuple[OntologyMetricBinding, ...] = (
    OntologyMetricBinding(
        metric_id="MTR-PNL-001",
        intent="pnl_summary",
        upstream_result_kind="pnl.overview",
        result_field="interest_income_514",
    ),
    OntologyMetricBinding(
        metric_id="MTR-PNL-002",
        intent="pnl_summary",
        upstream_result_kind="pnl.overview",
        result_field="fair_value_change_516",
    ),
    OntologyMetricBinding(
        metric_id="MTR-PNL-005",
        intent="pnl_summary",
        upstream_result_kind="pnl.overview",
        result_field="total_pnl",
    ),
)

_BINDINGS_BY_ID = {binding.metric_id: binding for binding in _BINDINGS}


def list_ontology_metric_bindings() -> tuple[OntologyMetricBinding, ...]:
    return _BINDINGS


def get_ontology_metric_binding(metric_id: str | None) -> OntologyMetricBinding | None:
    return _BINDINGS_BY_ID.get(str(metric_id or "").strip().upper())


def get_bound_metric_entity(metric_id: str | None) -> OntologyEntity | None:
    binding = get_ontology_metric_binding(metric_id)
    if binding is None:
        return None
    entity = load_ontology_index().get_entity(binding.metric_id)
    if entity is None or entity.entity_type != "Metric" or entity.status != "approved":
        return None
    expected_source_field = f"PnlOverviewPayload.{binding.result_field}"
    if expected_source_field not in entity.source_fields:
        return None
    if (
        entity.basis != "formal"
        or entity.time_semantics != "report_date"
        or entity.fallback_allowed is not False
        or entity.unit != "yuan"
        or entity.precision != 2
        or entity.null_semantics != _EXPECTED_NULL_SEMANTICS
        or tuple(entity.calculation_rules) != _EXPECTED_CALCULATION_RULES
        or tuple(entity.result_meta_requirements)
        != _EXPECTED_RESULT_META_REQUIREMENTS
    ):
        return None
    overview_field = PnlOverviewPayload.model_fields.get(binding.result_field)
    if overview_field is None or overview_field.annotation is not Decimal:
        return None
    return entity


def validate_ontology_metric_bindings() -> list[str]:
    errors: list[str] = []
    for binding in _BINDINGS:
        entity = load_ontology_index().get_entity(binding.metric_id)
        if entity is None:
            errors.append(f"{binding.metric_id}: ontology entity is missing")
            continue
        if entity.entity_type != "Metric":
            errors.append(f"{binding.metric_id}: entity_type must be Metric")
        if entity.status != "approved":
            errors.append(f"{binding.metric_id}: status must be approved")
        expected_source_field = f"PnlOverviewPayload.{binding.result_field}"
        if expected_source_field not in entity.source_fields:
            errors.append(
                f"{binding.metric_id}: source_fields must include {expected_source_field}"
            )
        if entity.basis != "formal":
            errors.append(f"{binding.metric_id}: basis must be formal")
        if entity.time_semantics != "report_date":
            errors.append(f"{binding.metric_id}: time_semantics must be report_date")
        if entity.fallback_allowed is not False:
            errors.append(f"{binding.metric_id}: fallback_allowed must be false")
        if entity.unit != "yuan":
            errors.append(f"{binding.metric_id}: unit must be yuan")
        if entity.precision != 2:
            errors.append(f"{binding.metric_id}: precision must be 2")
        if entity.null_semantics != _EXPECTED_NULL_SEMANTICS:
            errors.append(
                f"{binding.metric_id}: null_semantics must be {_EXPECTED_NULL_SEMANTICS}"
            )
        if tuple(entity.calculation_rules) != _EXPECTED_CALCULATION_RULES:
            errors.append(
                f"{binding.metric_id}: calculation_rules must equal "
                f"{list(_EXPECTED_CALCULATION_RULES)}"
            )
        if (
            tuple(entity.result_meta_requirements)
            != _EXPECTED_RESULT_META_REQUIREMENTS
        ):
            errors.append(
                f"{binding.metric_id}: result_meta_requirements must equal "
                f"{list(_EXPECTED_RESULT_META_REQUIREMENTS)}"
            )
        overview_field = PnlOverviewPayload.model_fields.get(binding.result_field)
        if overview_field is None or overview_field.annotation is not Decimal:
            errors.append(
                f"{binding.metric_id}: PnlOverviewPayload.{binding.result_field} "
                "must be a Decimal field"
            )
    return errors


@lru_cache(maxsize=1)
def ontology_content_revision() -> str:
    document = load_ontology_index().document
    canonical = json.dumps(
        document.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def ontology_reference_payload(metric_id: str) -> dict[str, object]:
    entity = get_bound_metric_entity(metric_id)
    if entity is None:
        raise ValueError(f"Metric binding is not backed by an approved ontology entity: {metric_id}")
    return {
        "entity_id": entity.entity_id,
        "name": entity.name,
        "business_definition": entity.business_definition,
        "status": entity.status,
        "unit": entity.unit,
        "basis": entity.basis,
        "time_semantics": entity.time_semantics,
        "authority": list(entity.authority),
    }
