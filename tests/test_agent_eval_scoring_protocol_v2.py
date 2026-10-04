from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_eval,
]

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_DIR = REPO_ROOT / "docs" / "paper" / "moss-financial-agent-paper" / "experiment"
PROTOCOL_PATH = EXPERIMENT_DIR / "decision-chain-scoring-protocol-v2.json"
MAIN_TASKS_PATH = EXPERIMENT_DIR / "decision-chain-pilot-tasks-v1.jsonl"
RED_TEAM_TASKS_PATH = EXPERIMENT_DIR / "decision-chain-red-team-mini-v1.jsonl"
RECORDS_TEMPLATE_PATH = EXPERIMENT_DIR / "records-template.csv"


def _load_protocol() -> dict[str, object]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def _load_task_ids(path: Path) -> list[str]:
    return [json.loads(line)["task_id"] for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_scoring_protocol_v2_covers_every_pilot_task() -> None:
    protocol = _load_protocol()
    covered = set(protocol["scope"]["covered_task_ids"])
    matrix_ids = set(protocol["task_matrix"])
    main_ids = set(_load_task_ids(MAIN_TASKS_PATH))
    red_team_ids = set(_load_task_ids(RED_TEAM_TASKS_PATH))
    expected = main_ids | red_team_ids

    assert covered == expected
    assert matrix_ids == expected


def test_scoring_protocol_v2_uses_positive_grounding_and_split_tracks() -> None:
    protocol = _load_protocol()
    catalog = protocol["field_catalog"]

    assert "hallucination" not in catalog
    assert catalog["answer_grounding_score"]["replaces_legacy_field"] == "hallucination"
    assert all(field["direction"] == "higher_is_better" for field in catalog.values())
    assert catalog["answer_grounding_score"]["track"] == "answer_grounding"
    assert catalog["wrapper_contract_complete"]["track"] == "system_wrapper_contract"
    assert catalog["answer_grounding_score"]["track"] != catalog["wrapper_contract_complete"]["track"]


def test_scoring_protocol_v2_field_shape_and_na_rules_are_consistent() -> None:
    protocol = _load_protocol()
    field_names = set(protocol["field_catalog"])
    required_keys = {
        "applicable",
        "legal_na",
        "denominator_policy",
        "direction",
        "track",
        "notes",
    }

    for task_id, task in protocol["task_matrix"].items():
        assert set(task["fields"]) == field_names, task_id
        for field_name, field in task["fields"].items():
            assert required_keys <= set(field), (task_id, field_name)
            assert field["direction"] == "higher_is_better", (task_id, field_name)
            if field_name == "numeric_score":
                assert field["applicable"] is False, task_id
                assert field["legal_na"] is True, task_id
                assert field["track"] == "numeric_admin_only", task_id
            if field["applicable"] is False:
                assert field["legal_na"] is True, (task_id, field_name)
                assert str(field["denominator_policy"]).startswith("exclude_"), (task_id, field_name)


def test_scoring_protocol_v2_separates_main_and_red_team_denominators() -> None:
    protocol = _load_protocol()
    aggregate_rules = protocol["aggregate_rules"]

    assert aggregate_rules["ordinary_answer_quality_total"]["primary_for_task_kind"] == ["main_decision_chain"]
    assert aggregate_rules["red_team_defense_total"]["primary_for_task_kind"] == ["red_team"]

    for task_id, task in protocol["task_matrix"].items():
        fields = task["fields"]
        if task["task_kind"] == "main_decision_chain":
            assert task["primary_aggregate"] == "ordinary_answer_quality_total", task_id
            assert fields["decision_support_score"]["applicable"] is True, task_id
            assert fields["decision_support_score"]["denominator_policy"] == "include_in_ordinary_answer_quality_total", task_id
            assert fields["defense_success"]["applicable"] is False, task_id
            assert fields["defense_success"]["denominator_policy"] == "exclude_from_non_red_team_tasks", task_id
            assert fields["wrapper_contract_complete"]["denominator_policy"] == "exclude_from_ordinary_total_report_separately", task_id
        else:
            assert task["primary_aggregate"] == "red_team_defense_total", task_id
            assert fields["decision_support_score"]["applicable"] is False, task_id
            assert fields["decision_support_score"]["legal_na"] is True, task_id
            assert fields["defense_success"]["applicable"] is True, task_id
            assert fields["defense_success"]["denominator_policy"] == "include_in_red_team_defense_total", task_id
            assert "not_in_red_team_primary_total" in fields["basis_score"]["denominator_policy"], task_id
            assert fields["wrapper_contract_complete"]["denominator_policy"] == "exclude_from_red_team_primary_total_report_separately", task_id


def test_scoring_protocol_v2_keeps_dc08_unit_date_rule_access_aware() -> None:
    protocol = _load_protocol()
    dc08 = protocol["task_matrix"]["DC08"]

    assert dc08["report_date_required"] is False
    assert dc08["fields"]["unit_date_score"]["applicable"] is True
    assert "Do not invent report_date" in dc08["fields"]["unit_date_score"]["notes"]


def test_semantic_records_template_uses_v2_fields_without_method_truth() -> None:
    header = RECORDS_TEMPLATE_PATH.read_text(encoding="utf-8").splitlines()[0].split(",")

    assert "method" not in header
    assert "hallucination" not in header
    assert "arm_guess" in header
    assert "decision_support_score" in header
    assert "answer_grounding_score" in header
    assert "defense_success" in header
