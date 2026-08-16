from __future__ import annotations

from typing import get_args

from backend.app.ontology.loader import load_ontology_index
from backend.app.schemas.result_meta import SourceSurface, infer_source_surface_for_result_kind


def test_source_surface_entities_align_with_result_meta_literal() -> None:
    valid_surfaces = set(get_args(SourceSurface))
    surfaces = [
        entity
        for entity in load_ontology_index().document.entities
        if entity.entity_type == "SourceSurface"
    ]

    assert surfaces
    for surface in surfaces:
        assert surface.name in valid_surfaces


def test_result_kind_source_surface_relationships_reference_known_entities() -> None:
    index = load_ontology_index()
    entity_ids = index.entity_ids()
    relationships = [
        item
        for item in index.document.relationships
        if item.type == "result_kind_requires_source_surface"
    ]

    assert relationships
    for relationship in relationships:
        assert relationship.source in entity_ids
        assert relationship.target in entity_ids
        source = index.get_entity(relationship.source)
        target = index.get_entity(relationship.target)
        assert source.entity_type == "ResultKind"
        assert target.entity_type == "SourceSurface"
        assert infer_source_surface_for_result_kind(source.name.removesuffix("*")) == target.name
