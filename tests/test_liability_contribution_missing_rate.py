"""Missing rates must never extrapolate known contribution to the full balance."""

import pytest

from backend.app.core_finance.liability_cockpit import compute_contribution_split

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_liability_analytics]


def _row(rate, *, amount="100000000", category="同业负债"):
    return {"principal_native": amount, "funding_cost_rate": rate, "product_type": category, "is_asset_side": False}


def test_partial_rate_coverage_exposes_known_part_without_reporting_total():
    rows = [_row("2"), _row(None, amount="900000000")]
    entry = compute_contribution_split("2026-09-22", [], rows)["contributions"][0]
    assert entry["amount_yi"] == 10
    assert entry["contribution_yi"] is None
    assert entry["yield_or_cost"] is None
    assert entry["known_contribution_yi"] == pytest.approx(0.02)
    assert entry["missing_rate_amount_yi"] == 9
    assert entry["rate_coverage_pct"] == 10


def test_known_contribution_is_invariant_to_category_partition():
    rows = [_row("2"), _row(None, amount="900000000")]
    combined = compute_contribution_split("2026-09-22", [], rows)["contributions"]
    rows[1]["product_type"] = "另一分类"
    separated = compute_contribution_split("2026-09-22", [], rows)["contributions"]
    assert sum(row["known_contribution_yi"] or 0 for row in combined) == pytest.approx(0.02)
    assert sum(row["known_contribution_yi"] or 0 for row in separated) == pytest.approx(0.02)
    assert next(row for row in separated if row["category"] == "另一分类")["contribution_yi"] is None


@pytest.mark.parametrize(("rate", "expected"), [("0", 0), ("2", 0.02)])
def test_complete_coverage_preserves_observed_zero_and_nonzero_rates(rate, expected):
    entry = compute_contribution_split("2026-09-22", [], [_row(rate)])["contributions"][0]
    assert entry["yield_or_cost"] == expected
    assert entry["contribution_yi"] == expected
    assert entry["known_contribution_yi"] == expected
    assert entry["rate_coverage_pct"] == 100
    assert entry["missing_rate_amount_yi"] == 0


def test_service_marks_incomplete_contribution_as_analytical_warning(monkeypatch):
    from backend.app.services import liability_analytics_service as service

    class Repository:
        def __init__(self, _path):
            pass

        def fetch_zqtz_rows(self, _report_date):
            return []

        def fetch_tyw_rows(self, _report_date):
            return [_row("2"), _row(None, amount="900000000")]

    monkeypatch.setattr(service, "LiabilityAnalyticsRepository", Repository)
    monkeypatch.setattr(service, "_resolve_report_date", lambda _repo, report_date: report_date)
    payload = service.contribution_split_payload(duckdb_path="unused", report_date="2026-09-22")
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result"]["contributions"][0]["contribution_yi"] is None


@pytest.mark.parametrize(
    ("source_rules", "resolved_date", "has_rows"),
    [
        (["rv_source_bond_v3", "rv_source_interbank_v4"], "2026-09-22", True),
        ([None, None], "2026-09-22", True),
        ([], "2026-09-22", False),
        ([], None, False),
    ],
    ids=["upstream-rules", "missing-upstream-rule", "empty-population", "no-report-date"],
)
def test_contribution_versions_identify_calculation_and_preserve_source_rules(
    monkeypatch, source_rules, resolved_date, has_rows
):
    from backend.app.services import liability_analytics_service as service

    rows = [dict(_row(rate), rule_version=rule, source_version="sv_synthetic")
            for rate, rule in zip(("2", None), source_rules)] if has_rows else []

    class Repository:
        def __init__(self, _path):
            pass

        def fetch_zqtz_rows(self, _report_date):
            return []

        def fetch_tyw_rows(self, _report_date):
            return rows

    monkeypatch.setattr(service, "LiabilityAnalyticsRepository", Repository)
    monkeypatch.setattr(service, "_resolve_report_date", lambda _repo, _date: resolved_date)
    payload = service.contribution_split_payload(duckdb_path="unused", report_date="2026-09-22")
    meta = payload["result_meta"]
    expected_source_rules = {rule for rule in source_rules if rule} or {service.LIABILITY_ANALYTICS_RULE_VERSION}
    assert set(meta["rule_version"].split("__")) == expected_source_rules | {"rv_liability_contribution_split_v2"}
    assert meta["cache_version"] == "cv_liability_contribution_split_v2"
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["source_version"] == ("sv_synthetic" if has_rows else service.LIABILITY_ANALYTICS_EMPTY_SOURCE_VERSION)


def test_other_liability_envelopes_keep_existing_version_behavior():
    from backend.app.services import liability_analytics_service as service

    payload = service._envelope(
        result_kind="liability_analytics.cockpit_warnings",
        result_payload={},
        source_rows=[{"source_version": "sv_source", "rule_version": "rv_source"}],
    )
    assert payload["result_meta"]["rule_version"] == "rv_source"
    assert payload["result_meta"]["cache_version"] == service.LIABILITY_ANALYTICS_CACHE_VERSION
