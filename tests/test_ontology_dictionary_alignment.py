from __future__ import annotations

from pathlib import Path

from backend.app.ontology.loader import load_ontology_index

ROOT = Path(__file__).resolve().parents[1]

SEEDED_APPROVED_METRIC_IDS = frozenset(
    {
        "MTR-BAL-001",
        "MTR-PNL-001",
        "MTR-PNL-002",
        "MTR-PNL-005",
        "MTR-BRG-011",
        "MTR-BRG-012",
        "MTR-BRG-013",
        "MTR-RSK-001",
        "MTR-PCP-001",
        "MTR-PCP-002",
        "MTR-PCP-003",
    }
)
SEEDED_MONEY_METRIC_IDS = SEEDED_APPROVED_METRIC_IDS - {"MTR-RSK-001"}
SEEDED_PRODUCT_CATEGORY_HEADLINES = frozenset({"MTR-PCP-001", "MTR-PCP-002", "MTR-PCP-003"})


def test_seeded_approved_metric_set_matches_dictionary_rows() -> None:
    ontology_metric_ids = {
        entity.entity_id
        for entity in load_ontology_index().document.entities
        if entity.entity_type == "Metric" and entity.status == "approved"
    }
    dictionary_metric_ids = set(_dictionary_rows_by_metric_id()).intersection(SEEDED_APPROVED_METRIC_IDS)

    assert ontology_metric_ids == SEEDED_APPROVED_METRIC_IDS
    assert dictionary_metric_ids == SEEDED_APPROVED_METRIC_IDS


def test_seeded_dictionary_basis_matches_ontology() -> None:
    dictionary_rows = _dictionary_rows_by_metric_id()
    ontology = load_ontology_index()

    for metric_id in SEEDED_APPROVED_METRIC_IDS:
        entity = ontology.get_entity(metric_id)
        assert entity is not None
        assert dictionary_rows[metric_id]["basis"].strip("`") == entity.basis


def test_seeded_money_metric_units_match_dictionary_display_rule() -> None:
    dictionary_rows = _dictionary_rows_by_metric_id()
    ontology = load_ontology_index()

    for metric_id in SEEDED_MONEY_METRIC_IDS:
        entity = ontology.get_entity(metric_id)
        assert entity is not None
        assert entity.unit == "yuan"
        assert "金额" in dictionary_rows[metric_id]["display_rule"]


def test_product_category_seed_is_headline_only() -> None:
    ontology_metric_ids = {
        entity.entity_id
        for entity in load_ontology_index().document.entities
        if entity.entity_type == "Metric" and entity.entity_id.startswith("MTR-PCP-")
    }

    assert ontology_metric_ids == SEEDED_PRODUCT_CATEGORY_HEADLINES


def _dictionary_rows_by_metric_id() -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in (ROOT / "docs" / "metric_dictionary.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `MTR-"):
            continue
        columns = [column.strip() for column in line.strip().strip("|").split("|")]
        if len(columns) < 8:
            continue
        metric_id = columns[0].strip("`")
        rows[metric_id] = {
            "name": columns[1],
            "type": columns[2],
            "basis": columns[3],
            "authority": columns[4],
            "surface": columns[5],
            "display_rule": columns[6],
            "fallback_time": columns[7],
        }
    return rows
