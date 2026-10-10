from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.agent.schemas.agent_response import AgentEnvelope


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_agent_mvp,
]


def _legacy_envelope_payload() -> dict[str, object]:
    return {
        "answer": "PnL summary is available.",
        "cards": [
            {
                "type": "metric",
                "title": "Total PnL",
                "value": "123.45",
                "data": None,
                "spec": None,
            }
        ],
        "evidence": {
            "tables_used": ["fact_formal_pnl_fi"],
            "filters_applied": {"report_date": "2026-03-31"},
            "sql_executed": [],
            "evidence_rows": 1,
            "quality_flag": "warning",
            "evidence_strength": "local_fallback",
        },
        "result_meta": {
            "trace_id": "tr_agent_semantic_contract",
            "basis": "formal",
            "result_kind": "agent.pnl_summary",
            "formal_use_allowed": False,
            "source_version": "sv_agent_test",
            "vendor_version": "vv_none",
            "rule_version": "rv_agent_semantic_v1",
            "cache_version": "cv_agent_semantic_v1",
            "quality_flag": "warning",
            "scenario_flag": False,
            "tables_used": ["fact_formal_pnl_fi"],
            "filters_applied": {"report_date": "2026-03-31"},
            "sql_executed": [],
            "evidence_rows": 1,
            "next_drill": [],
        },
        "next_drill": [],
        "suggested_actions": [],
    }


def test_legacy_agent_envelope_accepts_missing_or_null_semantic_fields() -> None:
    payload = _legacy_envelope_payload()

    missing = AgentEnvelope.model_validate(payload)
    assert missing.cards[0].metric_id is None
    assert missing.semantic_context is None

    payload["cards"][0]["metric_id"] = None  # type: ignore[index]
    payload["semantic_context"] = None
    explicit_null = AgentEnvelope.model_validate(payload)
    assert explicit_null.cards[0].metric_id is None
    assert explicit_null.semantic_context is None


def test_agent_semantic_context_round_trips_controlled_definition_snapshot() -> None:
    payload = _legacy_envelope_payload()
    payload["cards"][0]["metric_id"] = "MTR-PNL-003"  # type: ignore[index]
    payload["semantic_context"] = {
        "status": "resolved",
        "result_check": "matched",
        "references": [
            {
                "entity_id": "MTR-PNL-003",
                "name": "正式总损益",
                "business_definition": "正式损益口径下已核对的总损益指标。",
                "status": "approved",
                "unit": "yuan",
                "basis": "formal",
                "time_semantics": "report_date",
                "authority": [
                    "docs/metric_dictionary.md#7-formal-pnl",
                    "docs/calc_rules.md#3-formal-pnl",
                ],
            }
        ],
        "ontology_revision": "sha256:ontology-test",
        "binding_revision": "ontology-pnl-bindings-v1",
        "reason_code": None,
        "upstream_result_kind": "pnl.overview",
        "upstream_trace_id": "tr_formal_pnl_upstream",
    }

    envelope = AgentEnvelope.model_validate(payload)
    dumped = envelope.model_dump(mode="json")

    assert dumped["cards"][0]["metric_id"] == "MTR-PNL-003"
    assert dumped["semantic_context"] == payload["semantic_context"]
    assert AgentEnvelope.model_validate(dumped).semantic_context == envelope.semantic_context


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("status", "guessed"),
        ("result_check", "unchecked"),
    ],
)
def test_agent_semantic_context_rejects_unknown_contract_values(
    field: str,
    invalid_value: str,
) -> None:
    payload = _legacy_envelope_payload()
    semantic_context = {
        "status": "resolved",
        "result_check": "matched",
        "references": [],
    }
    semantic_context[field] = invalid_value
    payload["semantic_context"] = semantic_context

    with pytest.raises(ValidationError):
        AgentEnvelope.model_validate(payload)
