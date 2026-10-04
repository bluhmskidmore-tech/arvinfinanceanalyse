"""Synthetic formal-bridge coverage survives full/summary strict read contracts."""
from __future__ import annotations

from copy import deepcopy

import pytest

from backend.app.schemas.campisi_attribution_read import CampisiFourEffectsReadEnvelope
from backend.app.services import campisi_attribution_service as service
from tests.test_campisi_four_effects_detail_summary import _install_four_effects_bridge_fixture


@pytest.fixture
def bridge(monkeypatch):
    _install_four_effects_bridge_fixture(monkeypatch)
    envelope = service._fetch_formal_bridge()
    envelope["result"]["summary"]["row_count"] = 1
    yield envelope
    service.clear_campisi_four_effects_runtime_cache()


def _read(detail):
    endpoint = (
        service.campisi_four_effects_summary_envelope
        if detail == "summary" else service.campisi_four_effects_envelope
    )
    envelope = endpoint(start_date="2026-01-01", end_date="2026-01-31")
    return CampisiFourEffectsReadEnvelope.model_validate(envelope).model_dump(exclude_unset=True)


@pytest.mark.parametrize("detail", ["full", "summary"])
def test_formal_bridge_row_inclusion_survives_strict_schema(bridge, detail):
    envelope = _read(detail)
    result = envelope["result"]
    assert result["input_quality"]["formal_bridge_coverage"] == {
        "source": "pnl.bridge.rows",
        "basis": "formal_report_pnl_bridge",
        "status": "ok",
        "bridge_rows": 1,
        "attributed_rows": 1,
    }
    assert "position_change" not in result["input_quality"]
    assert "principal_evidence" not in result["input_quality"]
    assert result["formal_closure"]["status"] == "closed"
    assert result["totals"]["total_return"] == 35.0
    assert len(result["by_bond"]) == (0 if detail == "summary" else 1)


@pytest.mark.parametrize("count,status,reason", [
    (2, "partial", "bridge_row_count_mismatch"),
    (0, "unavailable", "bridge_rows_empty"),
    (None, "unavailable", "bridge_row_count_unavailable"),
    (-1, "unavailable", "bridge_row_count_unavailable"),
    (1.5, "unavailable", "bridge_row_count_unavailable"),
    (True, "unavailable", "bridge_row_count_unavailable"),
    ("1", "unavailable", "bridge_row_count_unavailable"),
])
def test_invalid_or_incomplete_bridge_population_never_reports_complete(bridge, count, status, reason):
    bridge["result"]["summary"]["row_count"] = count
    envelope = _read("summary")
    coverage = envelope["result"]["input_quality"]["formal_bridge_coverage"]
    assert coverage["status"] == status
    assert coverage["reason"] == reason
    assert coverage["attributed_rows"] == 1
    assert coverage["bridge_rows"] == (count if type(count) is int and count >= 0 else None)
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result"]["formal_closure"]["status"] == "closed"


@pytest.mark.parametrize("detail", ["full", "summary"])
def test_bridge_market_effect_availability_keeps_its_own_denominator(bridge, detail):
    bridge["result_meta"]["quality_flag"] = "warning"
    summary = bridge["result"]["summary"]
    summary.update({
        "roll_down_availability": {"status": "unavailable", "unavailable_rows": 1,
                                   "applicable_rows": 1, "reasons": ["curve_unavailable"]},
        "treasury_curve_availability": {"status": "not_applicable", "unavailable_rows": 0,
                                        "applicable_rows": 0, "reasons": ["non_fvtpl_basis"]},
        "credit_spread_availability": {"status": "unavailable", "unavailable_rows": 1,
                                       "applicable_rows": 1, "reasons": ["curve_unavailable"]},
    })
    row = bridge["result"]["rows"][0]
    row.update({"roll_down_availability": "unavailable",
                "treasury_curve_availability": "not_applicable",
                "credit_spread_availability": "unavailable"})
    # A second, structurally exempt bridge row increases the population but
    # must not become part of either market effect's applicable-row denominator.
    exempt = {**deepcopy(row), "instrument_code": "SUMMARY_EXEMPT", "accounting_basis": "AC",
              "roll_down_availability": "not_applicable",
              "credit_spread_availability": "not_applicable"}
    bridge["result"]["rows"].append(exempt)
    summary.update({"row_count": 2, "total_actual_pnl": {"raw": 70.0}})
    envelope = _read(detail)
    availability = envelope["result"]["effect_availability"]
    for key in ("roll_down_availability", "treasury_curve_availability", "credit_spread_availability"):
        assert availability[key] == summary[key]
    assert availability["bonds"] == 2
    assert availability["treasury_effect"]["status"] == "partial"
    assert availability["spread_effect"]["status"] == "partial"
    assert envelope["result"]["totals"]["total_return"] == 70.0
    assert envelope["result"]["formal_closure"]["status"] == "closed"
    assert envelope["result_meta"]["quality_flag"] == "warning"


@pytest.mark.parametrize("quality", ["error", "stale"])
def test_row_inclusion_cannot_promote_upstream_quality(bridge, quality):
    bridge["result_meta"]["quality_flag"] = quality
    bridge["result"]["summary"]["row_count"] = 2
    envelope = _read("summary")
    assert envelope["result"]["input_quality"]["formal_bridge_coverage"]["status"] == "partial"
    assert envelope["result_meta"]["quality_flag"] == quality
    assert envelope["result"]["formal_closure"]["bridge_quality_flag"] == quality


def test_more_attributed_rows_than_authoritative_population_is_unavailable(bridge):
    bridge["result"]["rows"].append({
        **deepcopy(bridge["result"]["rows"][0]), "instrument_code": "SUMMARY_OTHER",
    })
    bridge["result"]["summary"]["total_actual_pnl"] = {"raw": 70.0}

    envelope = _read("summary")

    assert envelope["result"]["input_quality"]["formal_bridge_coverage"] == {
        "source": "pnl.bridge.rows", "basis": "formal_report_pnl_bridge",
        "status": "unavailable", "bridge_rows": 1, "attributed_rows": 2,
        "reason": "bridge_row_count_mismatch",
    }
    assert envelope["result"]["formal_closure"]["status"] == "closed"
    assert envelope["result_meta"]["quality_flag"] == "warning"


@pytest.mark.parametrize("detail", ["full", "summary"])
def test_missing_sensitivity_reason_survives_bridge_projection(bridge, detail):
    bridge["result_meta"]["quality_flag"] = "warning"
    upstream = {
        "status": "unavailable", "unavailable_rows": 1, "applicable_rows": 1,
        "reasons": ["sensitivity_input_unavailable"],
    }
    bridge["result"]["summary"]["treasury_curve_availability"] = deepcopy(upstream)
    bridge["result"]["rows"][0].update({
        "treasury_curve_availability": "unavailable",
        "treasury_curve_availability_reason": "sensitivity_input_unavailable",
    })

    envelope = _read(detail)

    availability = envelope["result"]["effect_availability"]
    assert availability["treasury_curve_availability"] == upstream
    assert availability["treasury_effect"]["status"] == "unavailable"
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result"]["formal_closure"]["status"] == "closed"
    assert envelope["result"]["totals"]["total_return"] == 35.0


def test_summary_projection_preserves_population_and_source_availability_without_mutation(bridge):
    full = _read("full")
    before = deepcopy(full)
    projected = service._project_campisi_four_effects_summary(full)
    CampisiFourEffectsReadEnvelope.model_validate(projected)
    assert projected["result"]["input_quality"]["formal_bridge_coverage"] == before["result"]["input_quality"]["formal_bridge_coverage"]
    assert projected["result"]["effect_availability"] == before["result"]["effect_availability"]
    assert full == before
