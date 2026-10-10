from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from backend.app.core_finance.macro_bond_linkage import MacroBondCorrelation
from backend.app.services import macro_bond_linkage_service as svc
from tests.test_macro_bond_linkage import REPORT_DATE, _seed_macro_and_curve_inputs

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_macro_data]


def test_service_limits_lead_lag_search_to_visible_pairs(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-linkage-service.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=True)
    original = svc.compute_macro_bond_correlations
    calls: list[tuple[bool, int]] = []

    def recording_compute(macro_series, yield_series, **kwargs):
        calls.append((kwargs.get("include_lead_lag", True), len(macro_series) * len(yield_series)))
        return original(macro_series, yield_series, **kwargs)

    monkeypatch.setattr(svc, "compute_macro_bond_correlations", recording_compute)
    envelope = svc._get_macro_bond_linkage_uncached(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
    )

    assert len(envelope["result"]["top_correlations"]) == 10
    assert [pair_count for includes_lag, pair_count in calls if not includes_lag] == [45, 45]
    assert 0 < sum(pair_count for includes_lag, pair_count in calls if includes_lag) <= 23


def test_service_envelope_matches_full_lag_search_reference(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-linkage-reference.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=True)
    optimized = svc._get_macro_bond_linkage_uncached(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
    )

    def complete_all_pairs(correlations, macro_series, yield_series, *, alignment_mode, include_research):
        return svc.compute_macro_bond_correlations(
            macro_series,
            yield_series,
            lookback_days=svc.LOOKBACK_DAYS,
            alignment_mode=alignment_mode,
        )

    monkeypatch.setattr(svc, "_complete_visible_correlations", complete_all_pairs)
    reference = svc._get_macro_bond_linkage_uncached(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
    )

    for envelope in (optimized, reference):
        for field in ("trace_id", "generated_at"):
            envelope["result_meta"].pop(field, None)
        for field in ("computed_at", "served_at", "cache_hit"):
            envelope["result"].pop(field, None)
    assert optimized == reference


def _correlation(series_id: str, target_yield: str, strength: float | None) -> MacroBondCorrelation:
    return MacroBondCorrelation(
        series_id=series_id,
        series_name=series_id,
        target_yield=target_yield,
        correlation_3m=strength,
        correlation_6m=strength,
        correlation_1y=strength,
        lead_lag_days=0,
        direction="unavailable",
    )


@pytest.mark.parametrize(
    ("alignment_mode", "include_research"),
    [("conservative", True), ("market_timing", False)],
)
def test_service_keeps_research_family_outside_top_ten_and_stable_ties(
    monkeypatch, alignment_mode, include_research
):
    preliminary = [
        _correlation(f"S{index:02d}", f"other_{index:02d}", 1.0 - index * 0.01)
        for index in range(11)
    ] + [
        _correlation("T0", "treasury_10Y", 0.4),
        _correlation("T1", "treasury_5Y", 0.4),
        _correlation("C0", "aaa_credit_3Y", 0.3),
        _correlation("C1", "credit_spread_3Y", 0.2),
    ]
    by_pair = {(row.series_id, row.target_yield): row for row in preliminary}
    points = [(date(2026, 4, 1), 1.0), (date(2026, 4, 2), 2.0)]
    macro_series = {row.series_id: points for row in preliminary}
    yield_series = {row.target_yield: points for row in preliminary}
    completed_pairs: list[tuple[str, str]] = []

    def complete_one(macro_input, yield_input, **kwargs):
        assert kwargs["alignment_mode"] == alignment_mode
        assert kwargs.get("include_lead_lag", True)
        series_id = next(iter(macro_input))
        target_yield = next(iter(yield_input))
        completed_pairs.append((series_id, target_yield))
        return [replace(by_pair[(series_id, target_yield)], lead_lag_days=5, direction="positive")]

    monkeypatch.setattr(svc, "compute_macro_bond_correlations", complete_one)
    result = svc._complete_visible_correlations(
        preliminary,
        macro_series,
        yield_series,
        alignment_mode=alignment_mode,
        include_research=include_research,
    )

    expected = {(f"S{index:02d}", f"other_{index:02d}") for index in range(10)}
    if include_research:
        expected.update({("T0", "treasury_10Y"), ("C0", "aaa_credit_3Y")})
    assert set(completed_pairs) == expected
    assert [row.lead_lag_days for row in result if (row.series_id, row.target_yield) in expected] == [5] * len(
        expected
    )
    assert next(row for row in result if row.series_id == "T1").lead_lag_days == 0
    assert next(row for row in result if row.series_id == "C1").lead_lag_days == 0


def test_service_completes_best_lag_direction_when_windows_are_empty(monkeypatch):
    preliminary = [_correlation("EMPTY", "treasury_10Y", None)]
    macro_series = {"EMPTY": [(date(2026, 4, 1), 1.0), (date(2026, 4, 2), 2.0)]}
    yield_series = {"treasury_10Y": [(date(2026, 4, 6), 1.0), (date(2026, 4, 7), 2.0)]}

    def complete_one(macro_input, yield_input, **kwargs):
        assert kwargs["alignment_mode"] == "market_timing"
        return [
            replace(
                preliminary[0],
                lead_lag_days=5,
                direction="positive",
                direction_source_window="best_lag",
                sample_size=2,
                lead_lag_confidence=1.0,
            )
        ]

    monkeypatch.setattr(svc, "compute_macro_bond_correlations", complete_one)
    result = svc._complete_visible_correlations(
        preliminary,
        macro_series,
        yield_series,
        alignment_mode="market_timing",
        include_research=False,
    )

    assert result[0].direction == "positive"
    assert result[0].direction_source_window == "best_lag"
    assert result[0].lead_lag_days == 5
