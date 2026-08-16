from __future__ import annotations

import re
from pathlib import Path
from typing import get_args
from urllib.parse import unquote

from backend.app.ontology.loader import OntologyIndex, load_ontology_index
from backend.app.schemas.result_meta import ResultMeta, SourceSurface

_RELATIONSHIP_ENDPOINT_TYPES = {
    "page_displays_metric": ("Page", "Metric"),
    "metric_governed_by_rule": ("Metric", "CalculationRule"),
    "metric_bound_to_golden_sample": ("Metric", "GoldenSample"),
    "metric_protected_by_test": ("Metric", "TestAnchor"),
    "result_kind_requires_source_surface": ("ResultKind", "SourceSurface"),
    "table_supports_metric": ("Table", "Metric"),
}
_MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")


def validate_ontology_index(index: OntologyIndex | None = None) -> list[str]:
    resolved = index or load_ontology_index()
    errors: list[str] = []
    entity_ids = resolved.entity_ids()

    if len(entity_ids) != len(resolved.document.entities):
        errors.append("Duplicate ontology entity_id values are not allowed.")

    for relationship in resolved.document.relationships:
        if relationship.source not in entity_ids:
            errors.append(f"Relationship source not found: {relationship.source}")
        if relationship.target not in entity_ids:
            errors.append(f"Relationship target not found: {relationship.target}")
        if relationship.source in entity_ids and relationship.target in entity_ids:
            expected_source_type, expected_target_type = _RELATIONSHIP_ENDPOINT_TYPES[relationship.type]
            source_type = resolved.get_entity(relationship.source).entity_type
            target_type = resolved.get_entity(relationship.target).entity_type
            if source_type != expected_source_type:
                errors.append(
                    f"Relationship {relationship.type} source must be {expected_source_type}: "
                    f"{relationship.source} is {source_type}"
                )
            if target_type != expected_target_type:
                errors.append(
                    f"Relationship {relationship.type} target must be {expected_target_type}: "
                    f"{relationship.target} is {target_type}"
                )

    source_surfaces = set(get_args(SourceSurface))
    bases = set(get_args(ResultMeta.model_fields["basis"].annotation))
    for entity in resolved.document.entities:
        if entity.basis is not None and entity.basis not in bases:
            errors.append(f"Unknown ResultMeta basis: {entity.basis}")
        if entity.entity_type == "SourceSurface" and entity.name not in source_surfaces:
            errors.append(f"Unknown ResultMeta source_surface: {entity.name}")
        if entity.entity_type == "Metric" and entity.status == "approved":
            errors.extend(_approved_metric_errors(entity_id=entity.entity_id, entity=entity))
            if entity.basis == "formal":
                errors.extend(_formal_metric_rule_errors(entity_id=entity.entity_id, entity=entity))

    return errors


def validate_ontology_authority_files(repo_root: Path) -> list[str]:
    errors: list[str] = []
    index = load_ontology_index()
    for entity in index.document.entities:
        for authority in entity.authority:
            path_text, separator, fragment = authority.partition("#")
            if not path_text:
                errors.append(f"Empty authority path on {entity.entity_id}")
                continue
            authority_path = repo_root / path_text
            if not authority_path.exists():
                errors.append(f"Missing authority path on {entity.entity_id}: {path_text}")
                continue
            if separator and authority_path.suffix.casefold() == ".md":
                anchors = _markdown_heading_anchors(authority_path)
                if unquote(fragment).casefold() not in anchors:
                    errors.append(f"Missing authority anchor on {entity.entity_id}: {authority}")
        for test_path in entity.tests:
            if not (repo_root / test_path).exists():
                errors.append(f"Missing test anchor on {entity.entity_id}: {test_path}")
        for sample_path in entity.golden_samples:
            if not (repo_root / sample_path).exists():
                errors.append(f"Missing golden sample anchor on {entity.entity_id}: {sample_path}")
    return errors


def _approved_metric_errors(*, entity_id: str, entity) -> list[str]:
    required = {
        "basis": entity.basis,
        "business_definition": entity.business_definition,
        "unit": entity.unit,
        "time_semantics": entity.time_semantics,
        "fallback_allowed": entity.fallback_allowed,
        "authority": entity.authority,
        "tests": entity.tests,
    }
    errors = []
    for field_name, value in required.items():
        if value is None or value == "" or value == []:
            errors.append(f"Approved metric {entity_id} missing {field_name}")
    return errors


def _formal_metric_rule_errors(*, entity_id: str, entity) -> list[str]:
    if not entity.calculation_rules:
        return []
    if any(str(authority).startswith("docs/calc_rules.md") for authority in entity.authority):
        return []
    return [f"Formal metric {entity_id} references calculation_rules without docs/calc_rules.md authority"]


def _markdown_heading_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _MARKDOWN_HEADING_PATTERN.match(line)
        if match is None:
            continue
        base = _github_markdown_slug(match.group(1))
        duplicate_index = counts.get(base, 0)
        counts[base] = duplicate_index + 1
        anchors.add(base if duplicate_index == 0 else f"{base}-{duplicate_index}")
    return anchors


def _github_markdown_slug(heading: str) -> str:
    normalized = re.sub(r"[^\w\- ]", "", heading.strip().casefold())
    return normalized.replace(" ", "-")
