"""Synthetic regression evidence for period, coverage and missing-field repairs."""
from calendar import monthrange
from contextlib import nullcontext
from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import MagicMock

import duckdb
import pytest

from backend.app.core_finance.action_attribution import compute_action_attribution_bonds, select_action_attribution_pnl_report_dates
from backend.app.core_finance.bond_analytics.common import resolve_period
from backend.app.core_finance.campisi_decision_grade import compute_decision_grade_row
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.services import bond_analytics_service as bonds
from backend.app.services import campisi_attribution_service as campisi


def month_ends(year, month, count):
    return [date((year * 12 + month - 1 + i) // 12, (year * 12 + month - 1 + i) % 12 + 1,
                 monthrange((year * 12 + month - 1 + i) // 12, (year * 12 + month - 1 + i) % 12 + 1)[1]).isoformat()
            for i in range(count)]


@pytest.mark.parametrize("end", [date(2026, 3, 31), date(2024, 2, 29), date(2025, 2, 28), date(2026, 1, 31)])
def test_ttm_is_twelve_calendar_months(end):
    start, _ = resolve_period(end, "TTM")
    available = month_ends(end.year - 1, end.month, 13)
    selected, _ = select_action_attribution_pnl_report_dates(available_report_dates=available,
        period_type="TTM", period_start=start, period_end=end)
    assert selected == available[1:]
    assert sum(D("100") for _ in selected) == D("1200")


def test_ttm_missing_month_is_partial_and_does_not_backfill():
    dates = month_ends(2025, 3, 13)
    dates.remove("2025-11-30")
    selected, warnings = select_action_attribution_pnl_report_dates(available_report_dates=dates,
        period_type="TTM", period_start=date(2025, 3, 31), period_end=date(2026, 3, 31))
    assert len(selected) == 11 and "2025-03-31" not in selected
    assert "ACTION_ATTRIBUTION_PNL517_MISSING_MONTH:2025-11" in warnings


def test_ttm_non_month_end_is_explicitly_pending():
    selected, warnings = select_action_attribution_pnl_report_dates(available_report_dates=["2026-03-15"],
        period_type="TTM", period_start=date(2025, 3, 15), period_end=date(2026, 3, 15))
    assert selected == []
    assert "ACTION_ATTRIBUTION_TTM_NON_MONTH_END_PENDING" in warnings


def test_multiple_dates_in_month_cannot_be_guessed_or_added():
    dates = month_ends(2025, 4, 12) + ["2026-03-30"]
    selected, warnings = select_action_attribution_pnl_report_dates(available_report_dates=dates,
        period_type="TTM", period_start=date(2025, 3, 31), period_end=date(2026, 3, 31))
    assert "2026-03-30" not in selected and "2026-03-31" not in selected
    assert "ACTION_ATTRIBUTION_PNL517_MONTH_AUTHORITY_PENDING:2026-03" in warnings


def position(code="HOLD"):
    return {"bond_code": code, "book_id": "P::C", "market_value": D("1000000"),
            "modified_duration": D("2"), "asset_class": "FVTPL"}


@pytest.mark.parametrize("amounts", [{"ROUNDTRIP::P::C": D("100000")},
                                  {"WIN::P::C": D("100000"), "LOSS::P::C": D("-100000")}])
def test_pnl_only_input_remains_visible_even_when_net_zero(amounts):
    pnl = {"HOLD::P::C": D("10"), **amounts}
    result = compute_action_attribution_bonds(period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
        positions_start=[position()], positions_end=[position()], pnl_by_key=pnl)
    assert result["total_pnl_from_actions"] == float(sum(pnl.values()))
    assert result["total_actions"] == 0
    coverage = result["pnl_coverage"]
    assert coverage["pnl_only_key_count"] == len(amounts)
    assert coverage["pnl_only_absolute_pnl"] == float(sum(map(abs, amounts.values())))
    assert coverage["unallocated_absolute_pnl"] == float(sum(map(abs, pnl.values())))
    assert coverage["status"] == "partial"
    assert sum(row["total_pnl_economic"] for row in result["by_action_type"]) == result["total_pnl_from_actions"]
    assert "ACTION_ATTRIBUTION_PNL_ONLY_KEYS" in result["warnings"]


def test_all_sold_snapshot_keeps_pnl_and_sell_action():
    result = compute_action_attribution_bonds(period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
        positions_start=[position()], positions_end=[], pnl_by_key={"HOLD::P::C": D("-100")})
    assert result["total_pnl_from_actions"] == -100
    assert result["total_actions"] == 1
    assert result["action_details"][0]["action_type"] == "TIMING_SELL"


def test_no_beginning_snapshot_does_not_invent_new_purchase():
    result = compute_action_attribution_bonds(period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
        positions_start=[], positions_end=[position()], pnl_by_key={"HOLD::P::C": D("100")},
        start_snapshot_available=False)
    assert result["total_actions"] == 0
    assert result["pnl_coverage"]["unallocated_pnl"] == 100
    assert result["period_start_duration"] is None


def test_ytd_anchor_is_before_flow_start_not_latest_snapshot():
    repo = MagicMock()
    repo.list_report_dates.return_value = ["2025-12-31", "2026-02-28", "2026-03-31"]
    repo.fetch_bond_analytics_rows.side_effect = lambda **kw: [{"report_date": kw["report_date"]}]
    _, start, actual = bonds._fetch_action_attribution_snapshots(repo=repo,
        period_start="2026-01-01", period_end="2026-03-31")
    assert actual == "2025-12-31" and start[0]["report_date"] == actual


@pytest.fixture
def ttm_action_service(monkeypatch):
    from backend.app.schemas.result_meta import ResultMeta

    row = {"instrument_code": "HOLD", "portfolio_name": "P", "cost_center": "C",
           "market_value": D("1000000"), "modified_duration": D("2"), "accounting_class": "FVTPL"}
    snapshots = {
        "2024-02-28": [{**row, "instrument_code": "OUTSIDE"}],
        "2024-02-29": [row],
        "2025-02-28": [{**row, "modified_duration": D("4")}],
    }
    repo, pnl_repo = MagicMock(), MagicMock()
    repo.list_report_dates.return_value = list(snapshots)
    repo.fetch_bond_analytics_rows.side_effect = lambda *, report_date: snapshots[report_date]
    pnl_repo.list_union_report_dates.return_value = month_ends(2024, 2, 13)
    pnl_repo.merged_capital_gain_517_by_position_for_dates.side_effect = (
        lambda dates: {"HOLD::P::C": D("100") * len(dates)}
    )
    build = {"run_id": "ttm-build", "source_version": "sv_ttm_synthetic",
             "rule_version": bonds.RULE_VERSION, "cache_version": bonds.CACHE_VERSION}
    cache = bonds._TTLCache()
    monkeypatch.setattr(bonds, "_action_attribution_cache", cache)
    monkeypatch.setattr(bonds, "_repo", lambda: repo)
    monkeypatch.setattr(bonds, "PnlRepository", lambda *_: pnl_repo)
    monkeypatch.setattr(bonds, "get_settings", lambda: SimpleNamespace(duckdb_path=":memory:"))
    monkeypatch.setattr(bonds, "_require_latest_completed_bond_analytics_run", lambda *a, **kw: build)
    monkeypatch.setattr(bonds, "_duckdb_cache_version_token", lambda: ("ttm-test",))
    monkeypatch.setattr(bonds, "_meta", lambda kind, rd, rows: ResultMeta(
        trace_id="ttm-synthetic", result_kind=kind, source_surface="bond_analytics",
        source_version=build["source_version"], rule_version=build["rule_version"],
        cache_version=build["cache_version"], as_of_date=rd.isoformat(), evidence_rows=len(rows),
    ))
    return repo, pnl_repo, cache, build


def test_ttm_service_after_leap_year_aligns_snapshot_actions_and_monthly_flow(ttm_action_service):
    repo, pnl_repo, _, _ = ttm_action_service
    result = bonds.get_action_attribution(date(2025, 2, 28), "TTM")["result"]

    assert result["period_start"] == "2024-03-01"
    assert result["snapshot_window"]["requested_start"] == "2024-03-01"
    assert result["snapshot_window"]["resolved_start"] == "2024-02-29"
    assert result["snapshot_window"]["start_gap_days"] == 1
    assert result["snapshot_window"]["staleness_limit_status"] == "PENDING"
    assert [call.kwargs["report_date"] for call in repo.fetch_bond_analytics_rows.call_args_list] == [
        "2025-02-28", "2024-02-29",
    ]
    pnl_repo.merged_capital_gain_517_by_position_for_dates.assert_called_once_with(month_ends(2024, 3, 12))
    assert D(result["total_pnl_from_actions"]) == 1200
    assert [row["action_type"] for row in result["action_details"]] == ["ADD_DURATION"]
    assert D(result["action_details"][0]["pnl_economic"]) == 1200
    assert sum(D(row["total_pnl_economic"]) for row in result["by_action_type"]) == 1200
    assert result["pnl_coverage"]["identified_pnl"] == 1200
    assert result["pnl_coverage"]["unallocated_pnl"] == 0
    assert result["pnl_coverage"]["reconciliation_difference"] == 0


def test_ttm_service_query_version_does_not_reuse_old_calendar_cache(ttm_action_service):
    repo, pnl_repo, cache, build = ttm_action_service
    old_key = ("2025-02-28", "TTM", "cv_action_attribution_calendar_coverage_v2",
               "ttm-test", *bonds._completed_build_cache_token(build))
    old_result = {"result_meta": {
        "source_version": build["source_version"],
        "rule_version": f"{bonds.RULE_VERSION}__rv_action_attribution_calendar_coverage_v2",
        "cache_version": f"{bonds.CACHE_VERSION}__cv_action_attribution_calendar_coverage_v2",
    }, "result": {"period_start": "2024-02-29"}}
    cache.set(old_key, old_result)

    result = bonds.get_action_attribution(date(2025, 2, 28), "TTM")
    assert result is not old_result
    assert result["result"]["period_start"] == "2024-03-01"
    assert result["result_meta"]["rule_version"] == f"{bonds.RULE_VERSION}__rv_action_attribution_calendar_coverage_v3"
    assert result["result_meta"]["cache_version"] == f"{bonds.CACHE_VERSION}__cv_action_attribution_calendar_coverage_v3"
    assert result["result_meta"]["formal_use_allowed"] is False
    assert bonds.get_action_attribution(date(2025, 2, 28), "TTM") is result
    assert repo.fetch_bond_analytics_rows.call_count == 2
    assert pnl_repo.merged_capital_gain_517_by_position_for_dates.call_count == 1


@pytest.mark.parametrize("period_type,end,expected_start", [
    ("TTM", date(2025, 2, 28), date(2024, 3, 1)),
    ("TTM", date(2024, 2, 29), date(2023, 3, 1)),
    ("TTM", date(2026, 1, 31), date(2025, 2, 1)),
    ("TTM", date(2026, 3, 31), date(2025, 4, 1)),
    ("TTM", date(2025, 2, 27), date(2024, 2, 27)),
    ("MoM", date(2025, 2, 28), date(2025, 2, 1)),
    ("YTD", date(2025, 2, 28), date(2025, 1, 1)),
])
def test_action_flow_start_keeps_calendar_and_compatibility_boundaries(period_type, end, expected_start):
    start, period_end = resolve_period(end, period_type)
    assert bonds.resolve_action_attribution_flow_start(
        period_type=period_type, period_start=start, period_end=period_end,
    ) == expected_start


def decision_row(**changes):
    row = {"actual_pnl": D("100000"), "carry": D("0"), "realized_trading": D("0"),
           "manual_adjustment": D("0"), "market_value": D("100000000"),
           "modified_duration": D("0"), "convexity": D("0"), "spread_dv01": D("0"),
           "years_to_maturity": D("3"), "is_credit": False, "missing_analytics": False,
           "include_market_effects_in_formal_pnl": True}
    row.update(changes)
    return compute_decision_grade_row(row, treasury_start={"3Y": D("2")}, treasury_end={"3Y": D("1.9")},
        credit_start_by_rating={}, credit_end_by_rating={})


@pytest.mark.parametrize("amount", [D("100000"), D("-100000")])
@pytest.mark.parametrize("missing", [None, float("nan")])
def test_missing_duration_is_residual_and_lowers_confidence(amount, missing):
    result = decision_row(actual_pnl=amount, modified_duration=missing)
    assert result["components"]["selection_proxy"] == 0
    assert result["components"]["residual_noise"] == amount
    assert "missing_modified_duration" in result["residual_reasons"]
    assert campisi._decision_ability_matrix([result])[0]["confidence"] == "low"
    assert sum(result["components"].values()) == amount


def test_explicit_zero_duration_is_an_observation():
    result = decision_row(modified_duration=D("0"))
    assert not result["residual_reasons"]
    assert result["components"]["selection_proxy"] == D("100000")


def test_partial_duration_coverage_cannot_scale_full_market_value():
    result = decision_row(modified_duration=D("2"), modified_duration_coverage_ratio=D("0.5"))
    assert result["components"]["rate_level_effect"] == 0
    assert result["components"]["residual_noise"] == D("100000")
    assert "partial_modified_duration_coverage" in result["residual_reasons"]


def test_ac_exempts_market_sensitivities_and_tenor():
    result = decision_row(actual_pnl=D("100"), carry=D("100"), modified_duration=None,
                          convexity=None, spread_dv01=None, years_to_maturity=None,
                          missing_analytics=True, include_market_effects_in_formal_pnl=False)
    assert result["residual_reasons"] == []
    assert result["components"]["carry"] == D("100")


def test_campisi_unmatched_scope_amounts_are_visible(monkeypatch):
    old = {"instrument_code": "OLD", "portfolio_name": "P", "cost_center": "C",
           "accounting_basis": "AC", "currency_basis": "CNY", "total_pnl": D("100"),
           "interest_income_514": D("100"), "fair_value_change_516": D("0"),
           "capital_gain_517": D("0"), "manual_adjustment": D("0")}
    pnl, bond, balance = MagicMock(), MagicMock(), MagicMock()
    pnl.fetch_campisi_decision_pnl_rows.return_value = [old, {**old, "instrument_code": "NEW", "total_pnl": D("100000")}]
    bond.fetch_campisi_decision_analytics_rows.return_value = [{"instrument_code": "OLD", "portfolio_name": "P",
        "cost_center": "C", "accounting_class": "AC", "currency_code": "CNY", "market_value": D("1000000"),
        "modified_duration": D("2"), "convexity": D("3"), "years_to_maturity": D("3"), "source_row_count": 1}]
    balance.fetch_campisi_decision_balance_rows.return_value = []
    overrides = {"get_settings": lambda: SimpleNamespace(duckdb_path=":memory:"), "PnlRepository": lambda *_: pnl,
        "BondAnalyticsRepository": lambda *_: bond, "BalanceAnalysisRepository": lambda *_: balance,
        "YieldCurveRepository": lambda *_: MagicMock(), "RiskTensorRepository": lambda *_: MagicMock(),
        "read_only_connection": lambda *_: nullcontext(object()),
        "_resolve_decision_dates": lambda **_: ("2025-12-31", "2026-01-31", "2025-12-31", "2026-01-31"),
        "_fetch_decision_curves": lambda *a, **k: ({"treasury_start": {}, "treasury_end": {},
            "credit_start_by_rating": {}, "credit_end_by_rating": {}}, [], 0, {"discarded": []}),
        "_decision_window_disclosure": lambda **_: None, "_fetch_decision_risk_tensor_check": lambda *a, **k: {},
        "build_formal_result_envelope": lambda **kw: kw}
    for name, value in overrides.items():
        monkeypatch.setattr(campisi, name, value)
    result = campisi.campisi_decision_grade_envelope(start_date="2025-12-31", end_date="2026-01-31")
    payload = result["result_payload"]
    assert payload["summary"]["formal_actual_pnl"] == 100
    scope = payload["scope_disclosure"]
    assert scope["full_input_pnl"] == 100100 and scope["unmatched_pnl"] == 100000
    assert scope["matched_input_pnl"] == scope["included_pnl"] == 100
    assert scope["input_row_count"] == 2 and scope["unmatched_row_count"] == 1
    assert scope["scope_decision_status"] == "PENDING" and scope["full_month_coverage"] is False
    assert payload["formal_pnl_view"]["closure"]["scope"] == "matched_beginning_positions"
    assert payload["warnings"] and result["result_meta"].quality_flag == "warning"


@pytest.mark.parametrize("method", ["merged_capital_gain_517_by_position_for_dates", "merged_capital_gain_517_by_position_and_accounting_for_dates"])
def test_duplicate_published_natural_key_is_not_summed_or_lexically_selected(tmp_path, method):
    from pathlib import Path
    path = tmp_path / "pnl.duckdb"
    with duckdb.connect(str(path)) as conn:
        conn.execute(Path("backend/app/schema_registry/duckdb/07_pnl_materialize.sql").read_text(encoding="utf-8").split("-- MOSS:STMT")[1])
        conn.execute("insert into fact_formal_pnl_fi (report_date,instrument_code,portfolio_name,cost_center,accounting_basis,currency_basis,capital_gain_517,source_version) values ('2026-03-31','B','P','C','AC','CNY',100,'v9'),('2026-03-31','B','P','C','AC','CNY',200,'v10')")
    with pytest.raises(ValueError, match="duplicate_natural_key"):
        getattr(PnlRepository(str(path)), method)(["2026-03-31"])


def test_distinct_accounting_legs_with_equal_and_negative_pnl_are_not_deduplicated(tmp_path):
    from pathlib import Path
    path = tmp_path / "pnl.duckdb"
    with duckdb.connect(str(path)) as conn:
        conn.execute(Path("backend/app/schema_registry/duckdb/07_pnl_materialize.sql").read_text(encoding="utf-8").split("-- MOSS:STMT")[1])
        conn.execute("insert into fact_formal_pnl_fi (report_date,instrument_code,portfolio_name,cost_center,accounting_basis,currency_basis,capital_gain_517) values ('2026-03-31','B','P','C','AC','CNY',100),('2026-03-31','B','P','C','FVOCI','CNY',100),('2026-03-31','B','P','C','FVTPL','CNY',-50)")
    assert PnlRepository(str(path)).merged_capital_gain_517_by_position_for_dates(["2026-03-31", "2026-03-31"])["B::P::C"] == 150


@pytest.mark.parametrize("field", ["convexity", "spread_dv01"])
def test_missing_applicable_sensitivity_preserves_signed_residual(field):
    result = decision_row(**{field: None, "is_credit": field == "spread_dv01"})
    assert result["components"]["selection_proxy"] == 0
    assert f"missing_{field}" in result["residual_reasons"]
    assert sum(result["components"].values()) == D("100000")


def test_nonfinite_duration_remains_dirty_input():
    from backend.app.core_finance.campisi_decision_grade import DirtyNumericInputError
    with pytest.raises(DirtyNumericInputError):
        decision_row(modified_duration=D("Infinity"))


def test_scope_net_zero_unmatched_does_not_claim_coverage():
    from backend.app.core_finance.campisi_decision_grade import compute_decision_scope_disclosure
    unmatched = [{"total_pnl": D("100000")}, {"total_pnl": D("-100000")}]
    scope = compute_decision_scope_disclosure(unmatched, [], unmatched, [])
    assert scope["unmatched_pnl"] == 0
    assert scope["unmatched_absolute_pnl"] == 200000
    assert scope["unmatched_row_count"] == 2
    assert scope["full_month_coverage"] is False


def test_action_serialized_response_retains_missing_anchor_and_coverage():
    from backend.app.core_finance.action_attribution import build_action_attribution_success_payload
    from backend.app.schemas.bond_analytics import ActionAttributionResponse
    from backend.app.services.explicit_numeric import promote_flat_payload
    raw = compute_action_attribution_bonds(period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
        positions_start=[], positions_end=[position()], pnl_by_key={"HOLD::P::C": D("100")}, start_snapshot_available=False)
    payload = build_action_attribution_success_payload(report_date=date(2026, 3, 31), period_type="YTD",
        raw=raw, prior_snapshot_date=None, pnl_by_key={"HOLD::P::C": D("100")}, pnl_warning_codes=[], computed_at="2026-09-05T00:00:00Z")
    serialized = ActionAttributionResponse.model_validate(promote_flat_payload(payload, ActionAttributionResponse)).model_dump(mode="json")
    assert serialized["snapshot_window"]["resolved_start"] is None
    assert serialized["period_start_duration"] is None
    assert serialized["pnl_coverage"]["unallocated_pnl"] == 100


@pytest.mark.parametrize("spread", [None, D("0"), D("-10")])
def test_campisi_repository_preserves_spread_missing_zero_and_negative(tmp_path, spread):
    from tests.test_bond_analytics_missing_rate_weighting import _position, _seed, REPORT_DATE
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
    path = str(tmp_path / "spread.duckdb")
    _seed(path, [_position(market_value=D("100"), spread_dv01=spread)])
    row = BondAnalyticsRepository(path).fetch_campisi_decision_analytics_rows(REPORT_DATE)[0]
    assert row["spread_dv01"] == spread
    assert row["spread_dv01_coverage_ratio"] == (0 if spread is None else 1)


@pytest.mark.parametrize("snapshot_state", ["held", "sold", "missing", "wrong_date", "wrong_rule", "wrong_source", "changed_input"])
def test_action_service_uses_period_anchor_and_versioned_cache_still_invalidates_by_date(monkeypatch, snapshot_state):
    sold = snapshot_state != "held"
    repo = MagicMock()
    repo.list_report_dates.return_value = ["2025-12-31", "2026-02-28", "2026-03-31"]
    row = {"instrument_code": "HOLD", "portfolio_name": "P", "cost_center": "C",
           "market_value": D("1000000"), "modified_duration": D("2"), "accounting_class": "FVTPL"}
    repo.fetch_bond_analytics_rows.side_effect = lambda *, report_date: [] if sold and report_date == "2026-03-31" else [row]
    cache = bonds._TTLCache()
    monkeypatch.setattr(bonds, "_action_attribution_cache", cache)
    monkeypatch.setattr(bonds, "_repo", lambda: repo)
    build = {"report_date": "2026-03-31", "status": "completed", "cache_key": bonds.CACHE_KEY,
             "job_name": bonds.JOB_NAME, "source_version": bonds.EMPTY_SOURCE_VERSION,
             "rule_version": bonds.RULE_VERSION, "cache_version": bonds.CACHE_VERSION}
    if snapshot_state == "missing":
        build = {}
    elif snapshot_state == "wrong_date":
        build["report_date"] = "2026-02-28"
    elif snapshot_state == "wrong_rule":
        build["rule_version"] = "old"
    elif snapshot_state == "wrong_source":
        build["source_version"] = "old"
    repo.load_snapshot_rows.return_value = [row] if snapshot_state == "changed_input" else []
    monkeypatch.setattr(bonds, "_require_latest_completed_bond_analytics_run", lambda *a, **kw: build)
    monkeypatch.setattr(bonds, "_duckdb_cache_version_token", lambda: ("test",))
    monkeypatch.setattr(bonds, "PnlRepository", lambda *a: object())
    monkeypatch.setattr(bonds, "_build_action_attribution_pnl_by_key", lambda *a, **kw: ({"HOLD::P::C": D("100")}, []))
    captured = []
    def response(**kw):
        captured.append(kw)
        return {"result_meta": {}, "result": kw["raw"]}
    monkeypatch.setattr(bonds, "_build_action_attribution_success_response", response)
    payload = bonds.get_action_attribution(date(2026, 3, 31), "YTD")
    assert captured[0]["prior_rd"] == "2025-12-31"
    assert payload["result"]["total_pnl_from_actions"] == 100
    assert payload["result"]["total_actions"] == (1 if snapshot_state == "sold" else 0)
    if snapshot_state not in {"held", "sold"}:
        assert payload["result"]["period_end_duration"] is None
        assert payload["result"]["duration_change_from_actions"] is None
        assert payload["result"]["pnl_coverage"]["unallocated_pnl"] == 100
        assert "ACTION_ATTRIBUTION_NO_END_SNAPSHOT" in payload["result"]["warnings"]
    assert list(cache._store)[0][0] == "2026-03-31"
    bonds._invalidate_bond_analytics_caches_for_report_date("2026-03-31")
    assert not cache._store


@pytest.mark.parametrize("end_rows", [[], [{**position(), "modified_duration": D("4")} ]])
def test_missing_end_snapshot_preserves_pnl_without_inventing_sells_or_duration(end_rows):
    from backend.app.core_finance.action_attribution import build_action_attribution_success_payload
    from backend.app.schemas.bond_analytics import ActionAttributionResponse
    from backend.app.services.explicit_numeric import promote_flat_payload
    raw = compute_action_attribution_bonds(period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
        positions_start=[position()], positions_end=end_rows, pnl_by_key={"HOLD::P::C": D("100")}, end_snapshot_available=False)
    assert raw["total_actions"] == 0
    assert raw["pnl_coverage"]["unallocated_pnl"] == 100
    assert raw["period_end_duration"] is None
    assert raw["duration_change_from_actions"] is None
    payload = build_action_attribution_success_payload(report_date=date(2026, 3, 31), period_type="YTD",
        raw=raw, prior_snapshot_date="2025-12-31", pnl_by_key={"HOLD::P::C": D("100")},
        pnl_warning_codes=[], computed_at="2026-09-05T00:00:00Z")
    serialized = ActionAttributionResponse.model_validate(promote_flat_payload(payload, ActionAttributionResponse)).model_dump(mode="json")
    assert serialized["snapshot_window"]["resolved_end"] is None
    assert serialized["period_end_duration"] is None


@pytest.mark.parametrize("case", ["non_month_end", "same_month_dates", "duplicate_version"])
def test_pending_monthly_authority_makes_action_and_trading_overlay_unavailable(monkeypatch, case):
    from backend.app.repositories.pnl_repo import Pnl517AuthorityError
    repo = MagicMock()
    repo.list_union_report_dates.return_value = ["2026-03-30", "2026-03-31"] if case == "same_month_dates" else ["2026-03-31"]
    repo.merged_capital_gain_517_by_position_for_dates.side_effect = Pnl517AuthorityError("duplicate_natural_key")
    repo.merged_capital_gain_517_by_position_and_accounting_for_dates.side_effect = Pnl517AuthorityError("duplicate_natural_key")
    end = date(2026, 3, 15) if case == "non_month_end" else date(2026, 3, 31)
    period = "MoM" if case == "duplicate_version" else "TTM"
    monkeypatch.setattr(bonds, "PnlRepository", lambda *a: repo)
    for action in (True, False):
        with pytest.raises(bonds.ActionAttributionPnlUnavailableError, match="PENDING"):
            if action:
                bonds._build_action_attribution_pnl_by_key(repo, period_type=period, period_start=date(2025, 3, 31), period_end=end)
            else:
                bonds._overlay_return_decomposition_trading_pnl517({"trading_total": D("999")},
                    period_type=period, period_start=date(2025, 3, 31), period_end=end, duckdb_path="unused")


def test_missing_month_remains_partial_and_separate_from_complete_key_assignment():
    from backend.app.core_finance.action_attribution import build_action_attribution_success_payload
    raw = compute_action_attribution_bonds(period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
        positions_start=[position()], positions_end=[], pnl_by_key={"HOLD::P::C": D("100")})
    assert raw["pnl_coverage"]["status"] == "complete"
    result = build_action_attribution_success_payload(report_date=date(2026, 3, 31), period_type="YTD", raw=raw,
        prior_snapshot_date="2025-12-31", pnl_by_key={"HOLD::P::C": D("100")},
        pnl_warning_codes=["ACTION_ATTRIBUTION_PNL517_MISSING_MONTH:2026-02"], computed_at="2026-09-05T00:00:00Z")
    assert result["pnl_coverage"]["status"] == result["pnl_coverage"]["period_status"] == "partial"
    assert result["pnl_coverage"]["missing_months"] == ["2026-02"]
    assert result["pnl_coverage"]["key_coverage_ratio"] == 1


@pytest.mark.parametrize("path", ["/action-attribution", "/return-decomposition?detail=full", "/return-decomposition?detail=summary"])
def test_pending_pnl_http_is_explicit_503_and_auth_runs_first(monkeypatch, path):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from backend.app.api.routes import bond_analytics as routes
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_auth_context] = lambda: object()
    queried = []
    def unavailable(*a, **kw):
        queried.append(True)
        raise routes.ActionAttributionPnlUnavailableError("ACTION_ATTRIBUTION_TTM_NON_MONTH_END_PENDING")
    for name in ("get_action_attribution", "get_return_decomposition", "get_return_decomposition_summary"):
        monkeypatch.setattr(routes, name, unavailable)
    monkeypatch.setattr(routes, "_ensure_bond_analytics_read_allowed", lambda auth: None)
    url = "/api/bond-analytics" + path + ("&" if "?" in path else "?") + "report_date=2026-03-15&period_type=TTM"
    with TestClient(app) as client:
        response = client.get(url)
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "pnl517_period_unavailable"
        assert "PENDING" in response.json()["detail"]["message"]
        assert "result" not in response.json()
        def denied(auth):
            raise HTTPException(status_code=403, detail="denied")
        monkeypatch.setattr(routes, "_ensure_bond_analytics_read_allowed", denied)
        count = len(queried)
        assert client.get(url).status_code == 403
        assert len(queried) == count


@pytest.mark.parametrize("sensitivity,expected", [(D("0"), D("0")), (D("-10"), D("100")), (None, D("0"))])
def test_credit_sensitivity_zero_is_not_a_duration_proxy(sensitivity, expected):
    row = {"actual_pnl": D("100000"), "carry": 0, "realized_trading": 0, "manual_adjustment": 0,
           "market_value": D("10000000"), "modified_duration": D("2"), "convexity": 0,
           "spread_dv01": sensitivity, "years_to_maturity": 3, "rating": "AAA", "is_credit": True}
    result = compute_decision_grade_row(row, treasury_start={"3Y": D("2")}, treasury_end={"3Y": D("2")},
        credit_start_by_rating={"AAA": {"3Y": D("3")}}, credit_end_by_rating={"AAA": {"3Y": D("3.1")}})
    assert result["components"]["credit_spread_effect"] == expected
    assert sum(result["components"].values()) == D("100000")
    if sensitivity is None:
        assert result["components"]["selection_proxy"] == 0
        assert result["components"]["residual_noise"] == D("100000")
    else:
        assert not result["residual_reasons"]


def test_campisi_empty_and_computed_closure_have_distinct_disclosures():
    empty = campisi._empty_decision_grade_payload("", "")
    assert "不能核对" in empty["formal_pnl_view"]["closure"]["message"]
    closure = campisi._decision_pnl_closure(explained_pnl=D("100"), formal_actual_pnl=D("100"))
    assert "内部" in closure["message"] and "未取到" not in closure["message"]


def test_missing_month_service_keeps_eleven_months_without_pending_error():
    dates = month_ends(2025, 3, 13)
    dates.remove("2025-11-30")
    repo = MagicMock()
    repo.list_union_report_dates.return_value = dates
    def merge(selected):
        assert len(selected) == 11
        assert "2025-03-31" not in selected and "2025-11-30" not in selected
        return {"B::P::C": D("100") * len(selected)}
    repo.merged_capital_gain_517_by_position_for_dates.side_effect = merge
    result, warnings = bonds._build_action_attribution_pnl_by_key(repo, period_type="TTM",
        period_start=date(2025, 3, 31), period_end=date(2026, 3, 31))
    assert result["B::P::C"] == 1100
    assert "ACTION_ATTRIBUTION_PNL517_MISSING_MONTH:2025-11" in warnings


def test_unrelated_pnl_value_error_is_not_reclassified_as_authority_pending():
    repo = MagicMock()
    repo.merged_capital_gain_517_by_position_for_dates.side_effect = ValueError("invalid parameter")
    with pytest.raises(ValueError, match="invalid parameter"):
        bonds._build_action_attribution_pnl_by_key(repo, period_type="MoM", period_start=date(2026, 3, 1), period_end=date(2026, 3, 31))


@pytest.mark.parametrize("values,expected_mv,coverage", [([None], None, 0), ([None, D("100")], D("100"), D("0.5")), ([D("0")], D("0"), 1)])
def test_campisi_repository_market_value_coverage_reaches_core(tmp_path, values, expected_mv, coverage):
    from tests.test_bond_analytics_missing_rate_weighting import _position, _seed, REPORT_DATE
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
    path = str(tmp_path / "mv.duckdb")
    _seed(path, [_position(market_value=value, modified_duration=D("2"), convexity=D("3"), years_to_maturity=D("3")) for value in values])
    row = BondAnalyticsRepository(path).fetch_campisi_decision_analytics_rows(REPORT_DATE)[0]
    assert row["market_value"] == expected_mv
    assert row["market_value_coverage_ratio"] == coverage
    result = decision_row(**{k: row[k] for k in ("market_value", "market_value_coverage_ratio", "modified_duration", "convexity", "years_to_maturity")})
    if coverage < 1:
        assert result["components"]["selection_proxy"] == 0
        assert result["components"]["residual_noise"] == D("100000")
        assert result["components"]["rate_level_effect"] == 0
    else:
        assert not result["residual_reasons"]


@pytest.mark.parametrize("fallback", [None, D("0"), D("10000000")])
def test_campisi_real_repository_missing_mv_reaches_service_with_balance_fallback(tmp_path, monkeypatch, fallback):
    from tests.test_bond_analytics_missing_rate_weighting import _position, _seed, REPORT_DATE
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
    from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
    path = str(tmp_path / "service-mv.duckdb")
    _seed(path, [_position(accounting_class="FVTPL", market_value=None, modified_duration=D("2"), convexity=0, years_to_maturity=3)])
    with duckdb.connect(path) as conn:
        conn.execute("insert into fact_formal_zqtz_balance_daily (report_date,instrument_code,portfolio_name,cost_center,accounting_basis,currency_basis,currency_code,market_value_amount) values (?, 'BOND-MIX','FIOA','5010','FVTPL','CNY','CNY',?)", [REPORT_DATE, fallback])
    analytics_rows = BondAnalyticsRepository(path).fetch_campisi_decision_analytics_rows(REPORT_DATE)
    balance_rows = BalanceAnalysisRepository(path).fetch_campisi_decision_balance_rows(REPORT_DATE)
    assert analytics_rows[0]["market_value"] is None
    assert balance_rows[0]["market_value_amount"] == fallback
    assert balance_rows[0]["market_value_coverage_ratio"] == (0 if fallback is None else 1)
    pnl_row = {"instrument_code": "BOND-MIX", "portfolio_name": "FIOA", "cost_center": "5010",
               "accounting_basis": "FVTPL", "currency_basis": "CNY", "total_pnl": D("100000"),
               "interest_income_514": 0, "capital_gain_517": 0, "fair_value_change_516": D("100000"), "manual_adjustment": 0}
    pnl, bond, balance = MagicMock(), MagicMock(), MagicMock()
    pnl.fetch_campisi_decision_pnl_rows.return_value = [pnl_row]
    bond.fetch_campisi_decision_analytics_rows.return_value = analytics_rows
    balance.fetch_campisi_decision_balance_rows.return_value = balance_rows
    overrides = {"get_settings": lambda: SimpleNamespace(duckdb_path=path), "PnlRepository": lambda *_: pnl,
        "BondAnalyticsRepository": lambda *_: bond, "BalanceAnalysisRepository": lambda *_: balance,
        "YieldCurveRepository": lambda *_: MagicMock(), "RiskTensorRepository": lambda *_: MagicMock(),
        "read_only_connection": lambda *_: nullcontext(object()),
        "_resolve_decision_dates": lambda **_: (REPORT_DATE, "2026-04-30", REPORT_DATE, "2026-04-30"),
        "_fetch_decision_curves": lambda *a, **k: ({"treasury_start": {"3Y": D("2")}, "treasury_end": {"3Y": D("1.9")},
            "credit_start_by_rating": {}, "credit_end_by_rating": {}}, [], 0, {"discarded": []}),
        "_decision_window_disclosure": lambda **_: None, "_fetch_decision_risk_tensor_check": lambda *a, **k: {},
        "build_formal_result_envelope": lambda **kw: kw}
    for name, value in overrides.items():
        monkeypatch.setattr(campisi, name, value)
    payload = campisi.campisi_decision_grade_envelope()["result_payload"]
    assert payload["formal_pnl_view"]["total_actual_pnl"] == 100000
    components = payload["formal_pnl_view"]["components"]
    if fallback is None:
        assert components["selection_proxy"] == 0 and components["residual_noise"] == 100000
        assert any("missing_market_value" in message for message in payload["warnings"])
        assert payload["residual_diagnostics"]["market_value_source_counts"]["missing"] == 1
    else:
        assert components["residual_noise"] == 0
        assert components["rate_level_effect"] == float(fallback * D("2") * D("0.001"))
        assert payload["residual_diagnostics"]["market_value_source_counts"]["formal_balance"] == 1
