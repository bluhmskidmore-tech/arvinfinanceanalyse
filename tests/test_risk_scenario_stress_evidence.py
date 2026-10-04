from copy import deepcopy

import pytest

from backend.app.services import risk_scenario_stress_service as service


@pytest.fixture
def evidence_sources(monkeypatch):
    result = {"report_date": "2026-09-04", "bond_count": 2, "regulatory_dv01": {"raw": 1000}}
    meta = {
        "resolved_report_date": "2026-09-04", "as_of_date": "2026-09-04",
        "fallback_mode": "none", "source_version": "risk-v1",
    }
    fact = {
        "report_date": "2026-09-04", "bond_count": 2, "source_version": "risk-v1",
        "upstream_source_version": "bond-v1", "upstream_rule_version": "rule-v1",
    }
    rows = [
        {
            "report_date": "2026-09-04", "dv01": amount,
            "source_version": "bond-v1", "rule_version": "rule-v1",
            "duration_quality_flag": "observed", "coupon_rate_input_status": "observed",
            "ytm_input_status": "observed",
        }
        for amount in (400, 600)
    ]
    monkeypatch.setattr(service.RiskTensorRepository, "fetch_risk_tensor_row", lambda *_: fact)
    monkeypatch.setattr(service.BondAnalyticsRepository, "fetch_bond_analytics_rows", lambda *_, **__: rows)
    return result, meta, fact, rows


def evidence(sources, requested="2026-09-04"):
    result, meta, _, _ = sources
    return service._scenario_evidence("unused", requested, result, meta)


def test_complete_formal_scope_has_verifiable_date_and_preserves_zero(evidence_sources):
    actual = evidence(evidence_sources)
    assert actual["actual_risk_date"] == "2026-09-04"
    assert actual["coverage"]["status"] == "complete"
    assert actual["coverage"]["included_position_count"] == 2
    assert actual["coverage"]["excluded_position_count"] == 0
    assert actual["amount_display_allowed"] is True
    evidence_sources[0]["regulatory_dv01"]["raw"] = 0
    assert evidence(evidence_sources)["amount_display_allowed"] is True


@pytest.mark.parametrize("missing", [None, "NaN", "Infinity", "bad"])
def test_nonempty_scenario_does_not_prove_position_coverage(evidence_sources, missing):
    evidence_sources[3][0]["dv01"] = missing
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "incomplete"
    assert actual["coverage"]["missing_risk_position_count"] == 1
    assert actual["amount_display_allowed"] is False


def test_unavailable_zero_is_missing_risk_and_is_not_a_scope_exclusion(evidence_sources):
    evidence_sources[3][0].update(dv01=0, duration_quality_flag="maturity_unavailable")
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "incomplete"
    assert actual["coverage"]["included_position_count"] == 2
    assert actual["coverage"]["excluded_position_count"] == 0
    assert actual["coverage"]["missing_risk_position_count"] == 1
    assert actual["coverage"]["reasons"] == ["适用范围内有 1 项缺少到期日，DV01 零占位不能证明零风险。"]
    assert actual["amount_display_allowed"] is False


@pytest.mark.parametrize("quality", ["observed", "no_remaining_term"])
def test_verified_zero_remains_usable(evidence_sources, quality):
    evidence_sources[3][0].update(dv01=0, duration_quality_flag=quality)
    evidence_sources[0]["regulatory_dv01"]["raw"] = 600
    if quality == "no_remaining_term":
        evidence_sources[3][0].update(coupon_rate_input_status="missing", ytm_input_status="missing")
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "complete"
    assert actual["coverage"]["missing_risk_position_count"] == 0
    assert actual["amount_display_allowed"] is True


@pytest.mark.parametrize("quality", [
    "ytm_unavailable", "coupon_unavailable", None, "", "unknown", "future_quality",
])
def test_finite_risk_with_unverified_or_assumed_inputs_cannot_display(evidence_sources, quality):
    evidence_sources[3][0]["duration_quality_flag"] = quality
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "unknown"
    assert actual["coverage"]["missing_risk_position_count"] == 0
    assert len(actual["coverage"]["reasons"]) == 1
    assert actual["amount_display_allowed"] is False


@pytest.mark.parametrize("ytm_status", ["observed", "missing", "dirty"])
def test_approved_par_assumption_is_disclosed_without_rejecting_valid_risk(evidence_sources, ytm_status):
    evidence_sources[3][0].update(duration_quality_flag="ytm_par_fallback", ytm_input_status=ytm_status)
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "complete"
    assert actual["coverage"]["missing_risk_position_count"] == 0
    assert "1 项采用既有平价收益率假设" in actual["coverage"]["reasons"][0]
    assert actual["amount_display_allowed"] is True


@pytest.mark.parametrize("mutation", [
    {"coupon_rate_input_status": "missing"}, {"ytm_input_status": "unknown"}, {"ytm_input_status": None},
])
def test_par_assumption_cannot_certify_conflicting_or_unknown_inputs(evidence_sources, mutation):
    evidence_sources[3][0].update(duration_quality_flag="ytm_par_fallback", **mutation)
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "unknown"
    assert actual["coverage"]["missing_risk_position_count"] == 0
    assert actual["amount_display_allowed"] is False


def test_unavailable_zero_and_approved_assumption_have_separate_counts(evidence_sources):
    evidence_sources[3][0].update(duration_quality_flag="maturity_unavailable", dv01=0)
    evidence_sources[3][1].update(duration_quality_flag="ytm_par_fallback", ytm_input_status="missing")
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "incomplete"
    assert actual["coverage"]["missing_risk_position_count"] == 1
    assert len(actual["coverage"]["reasons"]) == 2
    assert "1 项采用既有平价收益率假设" in actual["coverage"]["reasons"][1]
    assert actual["amount_display_allowed"] is False


@pytest.mark.parametrize("field", ["coupon_rate_input_status", "ytm_input_status"])
@pytest.mark.parametrize("status", [None, "missing", "dirty", "unknown"])
def test_observed_quality_requires_matching_input_statuses(evidence_sources, field, status):
    evidence_sources[3][0][field] = status
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "unknown"
    assert actual["coverage"]["missing_risk_position_count"] == 0
    assert actual["amount_display_allowed"] is False


def test_nonzero_risk_cannot_be_certified_by_matured_zero_quality(evidence_sources):
    evidence_sources[3][0]["duration_quality_flag"] = "no_remaining_term"
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "unknown"
    assert actual["coverage"]["missing_risk_position_count"] == 0
    assert actual["amount_display_allowed"] is False


def test_regulatory_scope_exclusions_are_separate_from_unavailable_inputs(evidence_sources, monkeypatch):
    from backend.app.core_finance.risk_tensor_regulatory_scope import (
        DEFAULT_REGULATORY_DV01_SCOPE_RULE,
        RegulatoryDv01ScopeRule,
        row_in_regulatory_dv01_scope,
    )

    # Exercise the existing scope evaluator with an explicit test-only rule;
    # production retains its current include-all rule, including unavailable rows.
    rules = (
        DEFAULT_REGULATORY_DV01_SCOPE_RULE,
        RegulatoryDv01ScopeRule("test_explicit_exclusion", "v1", False, {"instrument_code": ("excluded",)}),
    )
    monkeypatch.setattr(service, "row_in_regulatory_dv01_scope", lambda row: row_in_regulatory_dv01_scope(row, rules))
    evidence_sources[3][0].update(instrument_code="excluded", dv01=0, duration_quality_flag="maturity_unavailable")
    evidence_sources[0]["regulatory_dv01"]["raw"] = 600
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "complete"
    assert actual["coverage"]["included_position_count"] == 1
    assert actual["coverage"]["excluded_position_count"] == 1
    assert actual["coverage"]["missing_risk_position_count"] == 0
    assert actual["amount_display_allowed"] is True


@pytest.mark.parametrize("mutation", ["row_count", "source_version", "row_date", "risk_version"])
def test_mismatched_formal_evidence_is_unknown(evidence_sources, mutation):
    if mutation == "row_count":
        evidence_sources[0]["bond_count"] = 3
    elif mutation == "source_version":
        evidence_sources[3][0]["source_version"] = "different"
    elif mutation == "row_date":
        evidence_sources[3][0]["report_date"] = "2026-09-03"
    else:
        evidence_sources[2]["source_version"] = "newer"
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "unknown"
    assert actual["amount_display_allowed"] is False


def test_missing_and_conflicting_dates_are_not_echoed_from_request(evidence_sources):
    evidence_sources[1].pop("resolved_report_date")
    assert evidence(evidence_sources)["actual_risk_date"] is None
    evidence_sources[1]["resolved_report_date"] = "2026-09-03"
    assert evidence(evidence_sources)["date_status"] == "conflict"
    assert evidence(evidence_sources)["amount_display_allowed"] is False


def test_historical_date_requires_an_explicit_new_request(evidence_sources):
    actual = evidence(evidence_sources, requested="2026-09-07")
    assert actual["actual_risk_date"] == "2026-09-04"
    assert actual["fallback_status"] == "fallback"
    assert actual["amount_display_allowed"] is False
    assert evidence(evidence_sources)["amount_display_allowed"] is True


def test_missing_fallback_provenance_fails_closed(evidence_sources):
    evidence_sources[1].pop("fallback_mode")
    assert evidence(evidence_sources)["fallback_status"] == "unknown"
    assert evidence(evidence_sources)["amount_display_allowed"] is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_aggregate_regulatory_dv01_cannot_display_amount(evidence_sources, value):
    evidence_sources[0]["regulatory_dv01"]["raw"] = value
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "complete"
    assert actual["amount_display_allowed"] is False
    assert "监管口径 DV01 不可用。" in actual["coverage"]["reasons"]


def test_unknown_fallback_is_disclosed_by_complete_envelope(evidence_sources, monkeypatch):
    result, meta, _, _ = evidence_sources
    meta.pop("fallback_mode")
    monkeypatch.setattr(service, "risk_tensor_envelope", lambda **_: {"result": result, "result_meta": meta})
    actual = service.risk_scenario_stress_envelope("unused", "unused", "2026-09-04")
    assert actual["result"]["evidence"]["fallback_status"] == "unknown"
    assert actual["result"]["evidence"]["amount_display_allowed"] is False
    assert "来源回退状态未核验，情景金额暂不可展示。" in actual["result"]["source_warnings"]
    assert actual["result_meta"]["formal_use_allowed"] is False


def test_multiple_snapshot_sources_use_materialized_union_not_rule_equality(evidence_sources):
    evidence_sources[2]["upstream_source_version"] = "bond-a__bond-b"
    evidence_sources[3][0].update(source_version="bond-b", rule_version="snapshot-rule")
    evidence_sources[3][1].update(source_version="bond-a", rule_version="snapshot-rule")
    assert evidence(evidence_sources)["coverage"]["status"] == "complete"


def test_empty_source_rows_do_not_mean_zero_risk(evidence_sources):
    evidence_sources[3].clear()
    actual = evidence(evidence_sources)
    assert actual["coverage"]["status"] == "unknown"
    assert actual["coverage"]["missing_risk_position_count"] is None
    assert actual["amount_display_allowed"] is False


def test_envelope_carries_actual_date_without_changing_fixed_scenario(evidence_sources, monkeypatch):
    result, meta, _, _ = evidence_sources
    meta.update(result_kind="risk.tensor", quality_flag="ok")
    monkeypatch.setattr(service, "risk_tensor_envelope", lambda **_: {"result": deepcopy(result), "result_meta": meta})
    actual = service.risk_scenario_stress_envelope("unused", "unused", "2026-09-07")
    assert actual["result_meta"]["requested_report_date"] == "2026-09-07"
    assert actual["result_meta"]["resolved_report_date"] == "2026-09-04"
    assert actual["result"]["evidence"]["amount_display_allowed"] is False
    rate = next(row for row in actual["result"]["scenarios"] if row["scenario_key"] == "parallel_rate_up_10bp")
    assert rate["estimated_impact"]["raw"] == -10000
    assert rate["calculation"] == "-regulatory_dv01 * shock_bp"


def test_quality_gate_preserves_every_existing_scenario_value(evidence_sources, monkeypatch):
    result, meta, _, rows = evidence_sources
    rows[0]["dv01"] = 0
    rows[1]["dv01"] = 1000
    result.update(
        cs01={"raw": 250}, asset_cashflow_30d={"raw": 2000}, liability_cashflow_30d={"raw": 1000},
        liquidity_gap_30d={"raw": 1000}, total_market_value={"raw": 10000},
    )
    monkeypatch.setattr(service, "risk_tensor_envelope", lambda **_: {"result": result, "result_meta": meta})
    before = service.risk_scenario_stress_envelope("unused", "unused", "2026-09-04")["result"]
    rows[0]["duration_quality_flag"] = "maturity_unavailable"
    after = service.risk_scenario_stress_envelope("unused", "unused", "2026-09-04")["result"]
    assert before["evidence"]["amount_display_allowed"] is True
    assert after["evidence"]["amount_display_allowed"] is False
    assert after["scenarios"] == before["scenarios"]
    assert before["summary"]["comparison_measure"] == "estimated_pnl_impact"
    assert before["summary"]["worst_scenario_key"] == "parallel_rate_up_10bp"
    assert before["summary"]["worst_estimated_impact"]["raw"] == -10000
    assert after["summary"]["worst_scenario_key"] is None
    assert after["summary"]["worst_estimated_impact"]["raw"] is None
    assert [row["estimated_impact"]["raw"] for row in after["scenarios"]] == [-10000, -2500, -300, None]


def test_scenario_summary_does_not_compare_liquidity_gap_delta_with_pnl():
    scenarios = [
        {
            "scenario_key": "rate",
            "data_status": "available",
            "measure": "estimated_pnl_impact",
            "estimated_impact": {"raw": -100},
            "human_review_required": True,
        },
        {
            "scenario_key": "credit",
            "data_status": "available",
            "measure": "estimated_pnl_impact",
            "estimated_impact": {"raw": -50},
            "human_review_required": True,
        },
        {
            "scenario_key": "liquidity",
            "data_status": "available",
            "measure": "stressed_30d_liquidity_gap_delta",
            "estimated_impact": {"raw": -1000},
            "human_review_required": True,
        },
    ]

    actual = service._scenario_summary(scenarios)

    assert actual["comparison_measure"] == "estimated_pnl_impact"
    assert actual["worst_scenario_key"] == "rate"
    assert actual["worst_estimated_impact"]["raw"] == -100
