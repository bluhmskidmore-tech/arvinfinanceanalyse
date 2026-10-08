"""BD-019: legacy cache hits must retain physical and system-read identity.

All databases and governance streams are synthetic temporary fixtures. Real
repositories, service orchestration, calculations and envelopes are exercised;
only settings are replaced. A manually selected system context is used here,
not the publisher or production HTTP/authentication flow.
"""
from __future__ import annotations

from datetime import date
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.repositories.duckdb_read_context import DuckDBReadSelection, DuckDBReadSelectionError, duckdb_read_scope
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM, GovernanceRepository
from backend.app.repositories.system_read_publication_repo import SystemReadContext, _deep_freeze, _system_read_context_scope
from backend.app.services import adb_analysis_service as adb
from backend.app.services import bond_analytics_service as bond

CURRENT = "2026-09-30"
START = "2026-09-01"
PREVIOUS = "2026-08-31"


def _insert(conn, table, row):
    conn.execute(f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})", list(row.values()))


def _seed(path, number):
    schema_root = Path(__file__).resolve().parents[1] / "backend/app/schema_registry/duckdb"
    with duckdb.connect(str(path)) as conn:
        for name in ("02_bond_analytics.sql", "03_yield_curve.sql", "05_balance_analysis.sql", "07_pnl_materialize.sql"):
            for statement in (schema_root / name).read_text(encoding='utf-8').split("-- MOSS:STMT"):
                if statement.strip():
                    conn.execute(statement)
        for day, amount in ((CURRENT, 1000), (PREVIOUS, 700 + number * 100)):
            _insert(conn, "fact_formal_bond_analytics_daily", {
                "report_date": day, "instrument_code": "SYNTH-BOND", "instrument_name": "Synthetic treasury",
                "portfolio_name": "synthetic-book", "cost_center": "synthetic-center",
                "asset_class_raw": "treasury", "asset_class_std": "rates", "bond_type": "treasury",
                "accounting_class": "AC", "currency_code": "CNY", "face_value": amount,
                "market_value_native": amount, "market_value": amount, "amortized_cost": amount,
                "accrued_interest": 0, "coupon_rate": 3, "ytm": 3,
                "maturity_date": "2030-09-30", "years_to_maturity": 4, "tenor_bucket": "3-5Y",
                "macaulay_duration": 3, "modified_duration": 3, "convexity": 10, "dv01": 0.3,
                "is_credit": False, "spread_dv01": 0, "source_version": "sv_bond_fixed",
                "rule_version": bond.RULE_VERSION, "interest_payment_frequency": "annual",
                "interest_rate_style": "fixed", "duration_quality_flag": "ok",
            })
        for curve_type in ("treasury", "cdb", "aaa_credit"):
            for day, rate in ((START, 3), (CURRENT, 3 + number / 10)):
                for tenor in ("1Y", "3Y", "5Y", "10Y"):
                    _insert(conn, "fact_formal_yield_curve_daily", {
                        "trade_date": day, "curve_type": curve_type, "tenor": tenor, "rate_pct": rate,
                        "vendor_name": "synthetic", "vendor_version": "vv_synthetic",
                        "source_version": f"sv_curve_G{number}", "rule_version": "rv_synthetic_curve",
                    })
        adb_row = {
            "report_date": CURRENT, "instrument_code": "SYNTH-BOND", "instrument_name": "Synthetic treasury",
            "position_scope": "asset", "market_value_amount": number * 1000, "ytm_value": 3, "coupon_rate": 3,
            "asset_class": "treasury", "bond_type": "treasury", "is_issuance_like": False,
            "accounting_basis": "AC", "currency_basis": "CNY", "currency_code": "CNY",
            "source_version": f"sv_adb_G{number}", "rule_version": "rv_synthetic_adb",
        }
        _insert(conn, "fact_formal_zqtz_balance_daily", adb_row)
        _insert(conn, "fact_formal_zqtz_balance_daily", {**adb_row, "report_date": PREVIOUS, "market_value_amount": 500})
        _insert(conn, "fact_formal_pnl_fi", {
            "report_date": CURRENT, "instrument_code": "SYNTH-BOND", "portfolio_name": "synthetic-book",
            "cost_center": "synthetic-center", "accounting_basis": "AC", "currency_basis": "CNY",
            "capital_gain_517": number * 10, "source_version": f"sv_pnl_G{number}",
        })


def _clear():
    adb.clear_adb_comparison_cache()
    adb.clear_adb_insights_cache()
    bond._benchmark_excess_cache.clear()
    bond._action_attribution_cache.clear()


@pytest.fixture
def chain(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    active = tmp_path / "active.duckdb"
    snapshots = {f"G{number}": tmp_path / f"G{number}.duckdb" for number in (1, 2)}
    for number in (1, 2):
        _seed(snapshots[f"G{number}"], number)
    _seed(active, 2)
    repo = GovernanceRepository(base_dir=tmp_path / "governance", backend_mode="jsonl")
    terminal = {
        "run_id": "synthetic-shared-end-terminal", "report_date": CURRENT, "status": "completed",
        "cache_key": bond.CACHE_KEY, "job_name": bond.JOB_NAME,
        "source_version": "sv_bond_fixed", "rule_version": bond.RULE_VERSION,
        "cache_version": bond.CACHE_VERSION, "finished_at": "2026-09-30T23:00:00Z",
    }
    repo.append(CACHE_BUILD_RUN_STREAM, terminal)
    repo.append(CACHE_MANIFEST_STREAM, terminal)
    streams = {name: tuple(_deep_freeze(row) for row in repo.read_all(name))
               for name in (CACHE_BUILD_RUN_STREAM, CACHE_MANIFEST_STREAM)}
    settings = SimpleNamespace(duckdb_path=active, governance_path=repo.base_dir)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(active))
    monkeypatch.setattr(adb, "get_settings", lambda: settings)
    monkeypatch.setattr(bond, "get_settings", lambda: settings)
    contexts = {}
    for generation, path in snapshots.items():
        publication = SimpleNamespace(database_path=path, generation=generation, manifest_sha256="synthetic-" + generation)
        contexts[generation] = SystemReadContext(
            publication=publication, pnl_publication=publication,
            active_database_identity=str(active), governance_base_identity=str(repo.base_dir),
            governance_streams=streams, coverage_dates={}, data_update_run_id=None, global_run_id=None,
            writer_run_id="synthetic-writer", writer_receipt_sha256=None, workflow="synthetic-cache-regression",
            report_date=CURRENT, pretrade_availability={},
        )
    _clear()
    yield SimpleNamespace(active=active, snapshots=snapshots, contexts=contexts, settings=settings)
    _clear()


def _call(endpoint):
    if endpoint == "adb_comparison":
        return adb.adb_comparison_envelope(START, CURRENT)
    if endpoint == "adb_insights":
        return adb.adb_insights_envelope(START, CURRENT)
    if endpoint == "benchmark_many":
        return bond.get_benchmark_excess_many([date.fromisoformat(CURRENT)])[CURRENT]
    if endpoint == "benchmark":
        return bond.get_benchmark_excess(date.fromisoformat(CURRENT))
    return bond.get_action_attribution(date.fromisoformat(CURRENT))


ENDPOINTS = ["adb_comparison", "adb_insights", "benchmark", "benchmark_many", "action"]


def _assert_result(result, endpoint, number):
    payload, meta = result["result"], result["result_meta"]
    if endpoint.startswith("adb"):
        assert meta["source_version"] == f"sv_adb_G{number}"
        assert meta["formal_use_allowed"] is False
        if endpoint == "adb_comparison":
            assert payload["total_avg_assets"] == number * 1000
            assert payload["total_spot_assets"] == number * 1000
        else:
            assert payload["windows"]["qoq"]["available"] is True
            totals = payload["scale_attribution"]["qoq"]["side_totals"]["assets"]
            assert totals["current_avg"] == number * 1000
            assert totals["prior_avg"] == 500
            assert totals["delta"] == number * 1000 - 500
    elif endpoint.startswith("benchmark"):
        assert f"sv_curve_G{number}" in meta["source_version"]
        assert "sv_bond_fixed" in meta["source_version"]
        assert Decimal(payload["benchmark_return"]) == Decimal("-0.005") * number
    else:
        assert Decimal(payload["total_pnl_from_actions"]) == number * 10
        assert payload["pnl_coverage"]["input_pnl"] == number * 10
        expected_change = "25.0%" if number == 1 else "11.1%"
        assert expected_change in payload["action_details"][0]["description"]
        # Existing candidate disclosure is preserved; this patch does not add
        # missing composite PnL/prior lineage to the end-bond-only metadata.
        assert meta["source_version"] == "sv_bond_fixed"
        assert meta["formal_use_allowed"] is False
        assert "independent_accounting_pnl_reconciliation" in payload["blocked_components"]


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("order", [(1, 2), (2, 1)])
def test_generations_with_same_end_terminal_keep_their_inputs(chain, endpoint, order):
    active_stat = chain.active.stat()
    for number in (*order, order[0]):
        with _system_read_context_scope(chain.settings, chain.contexts[f"G{number}"]):
            result = _call(endpoint)
            _assert_result(result, endpoint, number)
            assert _call(endpoint) is result  # A real warm hit, not cache bypass.
    assert chain.active.stat() == active_stat


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_direct_physical_pin_without_system_context_is_also_isolated(chain, endpoint):
    for number in (1, 2, 1):
        selection = DuckDBReadSelection(chain.active, chain.snapshots[f"G{number}"], f"G{number}")
        with duckdb_read_scope(selection, required_online=True):
            _assert_result(_call(endpoint), endpoint, number)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_deleted_snapshot_is_rejected_before_warm_hit(chain, endpoint):
    with _system_read_context_scope(chain.settings, chain.contexts["G1"]):
        _assert_result(_call(endpoint), endpoint, 1)
        chain.snapshots["G1"].unlink()
        with pytest.raises(DuckDBReadSelectionError):
            _call(endpoint)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_required_selection_cannot_reuse_warm_active_result(chain, endpoint):
    _assert_result(_call(endpoint), endpoint, 2)
    with duckdb_read_scope(None, required_online=True, active_path=chain.active):
        with pytest.raises(DuckDBReadSelectionError):
            _call(endpoint)


def _update_active_to_g1(active):
    with duckdb.connect(str(active)) as conn:
        conn.execute("UPDATE fact_formal_zqtz_balance_daily SET market_value_amount=1000 WHERE report_date=?", [CURRENT])
        conn.execute("UPDATE fact_formal_zqtz_balance_daily SET source_version='sv_adb_G1'")
        conn.execute("UPDATE fact_formal_yield_curve_daily SET rate_pct=3.1 WHERE trade_date=?", [CURRENT])
        conn.execute("UPDATE fact_formal_yield_curve_daily SET source_version='sv_curve_G1'")
        conn.execute("UPDATE fact_formal_pnl_fi SET capital_gain_517=10, source_version='sv_pnl_G1'")
        conn.execute("UPDATE fact_formal_bond_analytics_daily SET market_value=800, face_value=800 WHERE report_date=?", [PREVIOUS])


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_active_updates_do_not_reuse_previous_inputs(chain, endpoint):
    _assert_result(_call(endpoint), endpoint, 2)
    old_stat = chain.active.stat()
    _update_active_to_g1(chain.active)
    assert chain.active.stat().st_mtime_ns != old_stat.st_mtime_ns
    _assert_result(_call(endpoint), endpoint, 1)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_live_updates_do_not_change_frozen_cache_identity(chain, endpoint):
    with _system_read_context_scope(chain.settings, chain.contexts["G1"]):
        frozen = _call(endpoint)
        _update_active_to_g1(chain.active)
        assert _call(endpoint) is frozen
        _assert_result(frozen, endpoint, 1)


@pytest.mark.parametrize("endpoint", ENDPOINTS)
def test_system_generation_identity_is_part_of_key_even_with_same_physical_path(chain, endpoint):
    with _system_read_context_scope(chain.settings, chain.contexts["G1"]):
        original = _call(endpoint)
    alternate = replace(chain.contexts["G1"], publication=SimpleNamespace(
        database_path=chain.snapshots["G1"], generation="another-synthetic-context", manifest_sha256="another-manifest"))
    with _system_read_context_scope(chain.settings, alternate):
        another = _call(endpoint)
        _assert_result(another, endpoint, 1)
    assert another is not original


def test_existing_date_invalidation_still_matches_all_generation_entries(chain):
    for generation in ("G1", "G2"):
        with _system_read_context_scope(chain.settings, chain.contexts[generation]):
            _call("benchmark")
            _call("action")
    assert len(bond._benchmark_excess_cache._store) == 2
    assert len(bond._action_attribution_cache._store) == 2
    bond._invalidate_bond_analytics_caches_for_report_date(CURRENT)
    assert bond._benchmark_excess_cache._store == {}
    assert bond._action_attribution_cache._store == {}
