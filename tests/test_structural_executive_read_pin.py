"""BD-007: executive lineage must share its amounts' system generation.

Only synthetic temporary JSONL/DuckDB data is used. Governance and YTD/DV01
repositories, read scopes, overview orchestration, and metadata are real.
Unrelated AUM/NIM/KPI inputs are explicit test doubles in the overview test.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import HTTPException

from backend.app.repositories.financial_result_publication_repo import FinancialPublicationInvalid
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.system_read_publication_repo import (
    SystemReadContext,
    _deep_freeze,
    _system_read_context_scope,
    active_system_read_scope,
    current_system_read_context,
)
from backend.app.services import executive_service as executive
from backend.app.services.runtime_cache import InMemoryTTLCache

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_executive]

CURRENT = "2026-09-30"
PREVIOUS = "2026-08-31"
DATES = [CURRENT, PREVIOUS]


def _runs(generation):
    return [
        {
            "cache_key": cache_key,
            "job_name": job_name,
            "status": "completed",
            "report_date": report_date,
            "source_version": f"sv_{domain}_{generation}",
            "rule_version": f"rv_{domain}_{generation}",
            "cache_version": f"cv_{domain}_{generation}",
            "vendor_version": "vv_none",
        }
        for domain, cache_key, job_name in (
            ("pnl", executive.PNL_CACHE_KEY, executive.PNL_JOB_NAME),
            ("bond", executive.BOND_ANALYTICS_CACHE_KEY, "bond_analytics_materialize"),
        )
        for report_date in DATES
    ]


@pytest.fixture
def chain(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_ENVIRONMENT", "test")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setattr(executive, "_HOME_CACHE_BUILD_RUNS_CACHE", InMemoryTTLCache(ttl_seconds=300))
    repo = GovernanceRepository(base_dir=tmp_path / "governance", backend_mode="jsonl")
    for row in _runs("G1"):
        repo.append(CACHE_BUILD_RUN_STREAM, row)
    expected_g1 = repo.read_all(CACHE_BUILD_RUN_STREAM)
    frozen_rows = tuple(_deep_freeze(row) for row in expected_g1)
    for row in _runs("G2"):
        repo.append(CACHE_BUILD_RUN_STREAM, row)
    active = tmp_path / "active.duckdb"
    snapshot = tmp_path / "G1.duckdb"
    # Identity-only marker in read-boundary tests; the consumer test creates
    # real databases before opening a pinned read scope.
    snapshot.write_bytes(b"synthetic snapshot marker")
    publication = SimpleNamespace(database_path=snapshot, generation="G1", manifest_sha256="synthetic-G1")
    context = SystemReadContext(
        publication=publication,
        pnl_publication=publication,
        active_database_identity=str(active),
        governance_base_identity=str(repo.base_dir),
        governance_streams={CACHE_BUILD_RUN_STREAM: frozen_rows},
        coverage_dates={},
        data_update_run_id=None,
        global_run_id=None,
        writer_run_id="synthetic-writer",
        writer_receipt_sha256=None,
        workflow="synthetic-regression",
        report_date=CURRENT,
        pretrade_availability={},
    )
    return SimpleNamespace(
        repo=repo, context=context, settings=SimpleNamespace(duckdb_path=active),
        active=active, snapshot=snapshot, governance=str(repo.base_dir),
        live=repo.base_dir / f"{CACHE_BUILD_RUN_STREAM}.jsonl",
        expected_g1=expected_g1, expected_live=repo.read_all(CACHE_BUILD_RUN_STREAM),
    )


@pytest.mark.parametrize("live_state", ["changed", "missing"])
def test_pinned_reader_uses_frozen_rows_regardless_of_live_file(chain, live_state):
    if live_state == "missing":
        chain.live.unlink()
    with _system_read_context_scope(chain.settings, chain.context):
        rows = executive._read_cache_build_runs_for_executive_overview(chain.governance)
        assert rows == chain.expected_g1
        assert rows.is_partial is False
        rows[0]["source_version"] = "mutated-copy"
        assert executive._read_cache_build_runs_for_executive_overview(chain.governance) == chain.expected_g1
    assert current_system_read_context() is None


def test_pinned_reader_never_fingerprints_or_tails_the_live_file(chain, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A pinned governance read touched the live-file optimization")
    monkeypatch.setattr(executive, "_governance_file_fingerprint", forbidden)
    monkeypatch.setattr(executive, "_read_recent_cache_build_runs_for_executive_overview", forbidden)
    with _system_read_context_scope(chain.settings, chain.context):
        assert executive._read_cache_build_runs_for_executive_overview(chain.governance) == chain.expected_g1


@pytest.mark.parametrize("reader_name", [
    "_read_cache_build_runs_for_executive_overview",
    "_read_all_cache_build_runs_for_executive_overview",
])
@pytest.mark.parametrize("streams", [{}, {CACHE_BUILD_RUN_STREAM: None}])
def test_missing_or_invalid_frozen_stream_fails_closed(chain, reader_name, streams):
    context = replace(chain.context, governance_streams=streams)
    with _system_read_context_scope(chain.settings, context):
        with pytest.raises(FinancialPublicationInvalid, match="governance stream is unavailable"):
            getattr(executive, reader_name)(chain.governance)


def test_valid_empty_frozen_stream_does_not_fall_back_to_live(chain):
    context = replace(chain.context, governance_streams={CACHE_BUILD_RUN_STREAM: ()})
    with _system_read_context_scope(chain.settings, context):
        rows = executive._read_cache_build_runs_for_executive_overview(chain.governance)
        assert rows == []
        assert rows.is_partial is False
        assert executive._completed_formal_build_lineage_from_rows(
            rows, governance_dir=chain.governance, cache_key=executive.PNL_CACHE_KEY,
            job_name=executive.PNL_JOB_NAME, report_date=CURRENT,
        ) is None
        assert executive._bond_analytics_lineage_from_rows(
            rows, governance_dir=chain.governance, report_date=CURRENT,
        ) is None


def test_unbound_and_explicit_active_reads_keep_live_tail_cache(chain, monkeypatch):
    calls = []
    original = executive._read_recent_cache_build_runs_for_executive_overview
    def observed(governance):
        calls.append(governance)
        return original(governance)
    monkeypatch.setattr(executive, "_read_recent_cache_build_runs_for_executive_overview", observed)
    expected = chain.expected_live
    assert executive._read_cache_build_runs_for_executive_overview(chain.governance) == expected
    assert executive._read_cache_build_runs_for_executive_overview(chain.governance) == expected
    assert calls == [chain.governance]
    with _system_read_context_scope(chain.settings, chain.context):
        with active_system_read_scope():
            assert executive._read_cache_build_runs_for_executive_overview(chain.governance) == expected
        assert executive._read_cache_build_runs_for_executive_overview(chain.governance) == chain.expected_g1
    assert calls == [chain.governance]


def test_active_tail_keeps_partial_full_fallback(chain, monkeypatch):
    monkeypatch.setattr(executive, "_HOME_CACHE_BUILD_RUN_TAIL_BYTES", 500)
    rows = executive._read_cache_build_runs_for_executive_overview(chain.governance)
    assert rows.is_partial is True
    assert not any(row["cache_key"] == executive.PNL_CACHE_KEY for row in rows)
    lineage = executive._completed_formal_build_lineage_from_rows(
        rows, governance_dir=chain.governance, cache_key=executive.PNL_CACHE_KEY,
        job_name=executive.PNL_JOB_NAME, report_date=CURRENT,
    )
    assert lineage["source_version"] == "sv_pnl_G2"
    assert rows.full_rows == chain.expected_live


def test_active_full_reader_preserves_unavailable_result(chain, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("synthetic unavailable store")
    monkeypatch.setattr(GovernanceRepository, "read_all", unavailable)
    assert executive._read_all_cache_build_runs_for_executive_overview(chain.governance) is None


def _seed_amounts(path: Path, multiplier: int):
    with duckdb.connect(str(path)) as conn:
        conn.execute("CREATE TABLE fact_formal_pnl_fi(report_date VARCHAR, total_pnl DECIMAL(20,2))")
        conn.execute("CREATE TABLE fact_nonstd_pnl_bridge(report_date VARCHAR, total_pnl DECIMAL(20,2))")
        conn.executemany("INSERT INTO fact_formal_pnl_fi VALUES (?, ?)", [
            (PREVIOUS, 100 * multiplier), (CURRENT, 200 * multiplier),
        ])
        conn.execute("""CREATE TABLE fact_formal_bond_analytics_daily(
            report_date VARCHAR, maturity_date DATE, market_value DOUBLE,
            modified_duration DOUBLE, years_to_maturity DOUBLE, dv01 DOUBLE,
            accounting_class VARCHAR, is_credit BOOLEAN)""")
        conn.executemany("INSERT INTO fact_formal_bond_analytics_daily VALUES (?, '2030-01-01', 1000, 2, 3, ?, 'AC', false)", [
            (PREVIOUS, 10 * multiplier), (CURRENT, 20 * multiplier),
        ])


def _configure_overview_support(chain, monkeypatch):
    # AUM/NIM/KPI are outside this regression; they supply complete neutral
    # lineage so a missing unrelated metric cannot conceal the YTD/DV01 labels.
    monkeypatch.setattr(executive, "get_settings", lambda: SimpleNamespace(
        duckdb_path=chain.active, governance_path=chain.repo.base_dir,
    ))
    monkeypatch.setattr(executive, "_fetch_aum_context", lambda *a, **k: ({
        d: {"total_market_value_amount": 1000, "source_version": "sv_support", "rule_version": "rv_support"}
        for d in DATES
    }, [1000.0, 1000.0]))
    monkeypatch.setattr(executive, "_fetch_nim_context", lambda *a, **k: ({
        d: {"kpi": {"nim": 0.02}, "source_version": "sv_support", "rule_version": "rv_support"}
        for d in DATES
    }, {}, {}, [0.02, 0.02]))
    monkeypatch.setattr(executive.BondAnalyticsRepository, "fetch_dashboard_headline_kpis", lambda *a, **k: None)
    monkeypatch.setattr(executive, "_resolve_kpi_authority_gate_for_overview", lambda **k: {"status": "blocked"})


@pytest.mark.parametrize("live_state", ["changed", "missing"])
def test_overview_ytd_and_dv01_amount_source_and_rule_share_the_pin(chain, monkeypatch, live_state):
    chain.snapshot.unlink()
    _seed_amounts(chain.snapshot, 1)
    _seed_amounts(chain.active, 10)
    _configure_overview_support(chain, monkeypatch)
    if live_state == "missing":
        chain.live.unlink()
    with _system_read_context_scope(chain.settings, chain.context):
        result = executive._compute_executive_overview(
            CURRENT, date_context={domain: DATES for domain in ("balance", "pnl", "liability", "bond")},
            history_points=2,
        )
    metrics = {item["id"]: item for item in result["result"]["metrics"]}
    assert metrics["yield"]["value"]["raw"] == 300.0
    assert metrics["yield"]["value"]["unit"] == "yuan"
    assert metrics["yield"]["history"] == [100.0, 300.0]
    assert metrics["dv01"]["value"]["raw"] == 20.0
    assert metrics["dv01"]["value"]["unit"] == "dv01"
    assert metrics["dv01"]["history"] == [10.0, 20.0]
    meta = result["result_meta"]
    assert meta["source_version"] == "sv_bond_G1__sv_exec_dashboard_v1__sv_pnl_G1__sv_support"
    assert meta["rule_version"] == "rv_bond_G1__rv_exec_dashboard_v1__rv_pnl_G1__rv_support"
    assert meta["quality_flag"] == "ok"
    assert meta["resolved_report_date"] == CURRENT
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False


def test_reserved_executive_guard_remains_closed():
    from backend.app.api.routes.executive import _raise_executive_reserved_surface
    for route_name in ("risk_overview", "contribution", "alerts"):
        with pytest.raises(HTTPException) as error:
            _raise_executive_reserved_surface(route_name)
        assert error.value.status_code == 503
