from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from backend.app.ontology.models import OntologyDocument, OntologyEntity

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_ONTOLOGY_PATH = _REPO_ROOT / "docs" / "ontology" / "moss_ontology.v1.json"
_NEGATION_PREFIXES = ("non-", "non ", "not ", "非")


class OntologyIndex:
    def __init__(self, document: OntologyDocument) -> None:
        self.document = document
        self._by_id = {entity.entity_id: entity for entity in document.entities}

    def get_entity(self, entity_id: str) -> OntologyEntity | None:
        return self._by_id.get(str(entity_id or "").strip())

    def entity_ids(self) -> frozenset[str]:
        return frozenset(self._by_id)

    def resolve_from_text(self, text: str) -> list[OntologyEntity]:
        normalized = str(text or "").casefold()
        if not normalized:
            return []

        matches: list[tuple[int, int, OntologyEntity]] = []
        for order, entity in enumerate(self.document.entities):
            best_position: int | None = None
            for term in _entity_terms(entity):
                candidate = term.casefold()
                if not candidate:
                    continue
                position = _find_term_position(normalized, candidate)
                if position is not None and (best_position is None or position < best_position):
                    best_position = position
            if best_position is not None:
                matches.append((best_position, order, entity))

        matches.sort(key=lambda item: (item[0], item[1]))
        seen: set[str] = set()
        resolved: list[OntologyEntity] = []
        for _, _, entity in matches:
            if entity.entity_id in seen:
                continue
            seen.add(entity.entity_id)
            resolved.append(entity)
        return resolved


def _entity_terms(entity: OntologyEntity) -> tuple[str, ...]:
    return (entity.entity_id, entity.name, *entity.aliases)


def _find_term_position(normalized_text: str, candidate: str) -> int | None:
    search_from = 0
    while True:
        position = normalized_text.find(candidate, search_from)
        if position < 0:
            return None
        if not _is_negated_match(normalized_text, position):
            return position
        search_from = position + 1


def _is_negated_match(normalized_text: str, position: int) -> bool:
    return any(
        position >= len(prefix) and normalized_text[position - len(prefix) : position] == prefix
        for prefix in _NEGATION_PREFIXES
    )


@lru_cache(maxsize=1)
def load_ontology_index() -> OntologyIndex:
    return OntologyIndex(load_ontology_document())


def load_ontology_document(path: Path | None = None) -> OntologyDocument:
    source = path or _DEFAULT_ONTOLOGY_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    return OntologyDocument.model_validate(payload)
