from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.ontology.loader import load_ontology_document, load_ontology_index
from backend.app.ontology import validators as ontology_validators
from backend.app.ontology.validators import validate_ontology_authority_files, validate_ontology_index

ROOT = Path(__file__).resolve().parents[1]


def test_ontology_seed_parses_and_validates() -> None:
    document = load_ontology_document()

    assert document.version == 1
    assert document.entities
    assert validate_ontology_index(load_ontology_index()) == []


def test_ontology_seed_validates_against_checked_json_schema() -> None:
    schema = json.loads((ROOT / "docs" / "ontology" / "ontology_schema.v1.json").read_text(encoding="utf-8"))
    payload = json.loads((ROOT / "docs" / "ontology" / "moss_ontology.v1.json").read_text(encoding="utf-8"))

    _assert_matches_json_schema(payload, schema)


def test_checked_json_schema_rejects_unknown_entity_fields() -> None:
    schema = json.loads((ROOT / "docs" / "ontology" / "ontology_schema.v1.json").read_text(encoding="utf-8"))
    payload = json.loads((ROOT / "docs" / "ontology" / "moss_ontology.v1.json").read_text(encoding="utf-8"))
    payload["entities"][0]["unexpected"] = True

    with pytest.raises(AssertionError, match="unexpected property"):
        _assert_matches_json_schema(payload, schema)


def test_ontology_authority_files_exist() -> None:
    assert validate_ontology_authority_files(ROOT) == []


def test_ontology_authority_validator_rejects_missing_markdown_fragment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority_path = tmp_path / "docs" / "authority.md"
    authority_path.parent.mkdir(parents=True)
    authority_path.write_text("# Existing Anchor\n", encoding="utf-8")
    entity = SimpleNamespace(
        entity_id="CONCEPT-test",
        authority=["docs/authority.md#missing-anchor"],
        tests=[],
        golden_samples=[],
    )
    monkeypatch.setattr(
        ontology_validators,
        "load_ontology_index",
        lambda: SimpleNamespace(document=SimpleNamespace(entities=[entity])),
    )

    errors = validate_ontology_authority_files(tmp_path)

    assert any("Missing authority anchor" in error for error in errors)


def test_approved_metrics_have_required_semantics() -> None:
    metrics = [
        entity
        for entity in load_ontology_index().document.entities
        if entity.entity_type == "Metric" and entity.status == "approved"
    ]

    assert metrics
    for metric in metrics:
        assert metric.basis
        assert metric.unit
        assert metric.precision is not None
        assert metric.time_semantics
        assert metric.fallback_allowed is not None
        assert metric.authority
        assert metric.source_fields
        assert metric.tests


def test_metric_ids_are_present_in_metric_dictionary() -> None:
    dictionary = (ROOT / "docs" / "metric_dictionary.md").read_text(encoding="utf-8")
    metric_ids = [
        entity.entity_id
        for entity in load_ontology_index().document.entities
        if entity.entity_type == "Metric"
    ]

    assert metric_ids
    for metric_id in metric_ids:
        assert metric_id in dictionary


def test_resolve_from_text_uses_ids_names_and_aliases_in_text_order() -> None:
    index = load_ontology_index()

    matched = index.resolve_from_text("请解释正式PnL里的 MTR-PNL-001 和公允价值变动")

    assert [entity.entity_id for entity in matched[:3]] == [
        "CONCEPT-formal_pnl",
        "MTR-PNL-001",
        "MTR-PNL-002",
    ]


def test_resolve_from_text_does_not_match_bare_numeric_account_codes() -> None:
    index = load_ontology_index()

    matched = index.resolve_from_text("Meeting room 516 is available.")

    assert matched == []


def test_formal_metric_rules_are_references_not_inline_formulas() -> None:
    index = load_ontology_index()
    formula_markers = (" = ", " + ", " - ", " * ", " × ")
    formal_metrics = [
        entity
        for entity in index.document.entities
        if entity.entity_type == "Metric" and entity.basis == "formal"
    ]

    assert formal_metrics
    for metric in formal_metrics:
        assert not any(marker in metric.business_definition for marker in formula_markers)
        for rule_id in metric.calculation_rules:
            rule = index.get_entity(rule_id)
            assert rule is not None
            assert rule.entity_type == "CalculationRule"
            assert any(authority.startswith("docs/calc_rules.md") for authority in rule.authority)


def _assert_matches_json_schema(value, schema: dict[str, object], *, path: str = "$") -> None:
    if "const" in schema:
        assert value == schema["const"], f"{path}: expected const {schema['const']!r}"
    if "enum" in schema:
        assert value in schema["enum"], f"{path}: value {value!r} is not in enum"

    expected_types = schema.get("type")
    if expected_types is not None:
        type_names = [expected_types] if isinstance(expected_types, str) else list(expected_types)
        assert any(_matches_json_type(value, type_name) for type_name in type_names), (
            f"{path}: value {value!r} does not match JSON type {type_names!r}"
        )

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for required_key in schema.get("required", []):
            assert required_key in value, f"{path}: missing required property {required_key!r}"
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(value) - set(properties))
            assert not unexpected, f"{path}: unexpected property {unexpected[0]!r}"
        for key, child in value.items():
            child_schema = properties.get(key)
            if child_schema is not None:
                _assert_matches_json_schema(child, child_schema, path=f"{path}.{key}")
    elif isinstance(value, list) and "items" in schema:
        for index, child in enumerate(value):
            _assert_matches_json_schema(child, schema["items"], path=f"{path}[{index}]")


def _matches_json_type(value, type_name: str) -> bool:
    if type_name == "null":
        return value is None
    if type_name == "object":
        return isinstance(value, dict)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    raise AssertionError(f"Unsupported JSON schema type in test validator: {type_name}")
