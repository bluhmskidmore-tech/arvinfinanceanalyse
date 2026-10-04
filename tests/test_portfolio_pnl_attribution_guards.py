"""Portfolio summary keeps the same formal evidence gates as its source detail."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.governance.formal_compute_lineage import (
    FormalLineageMalformedError,
    FormalLineageUnavailableError,
)
from backend.app.repositories.pnl_repo import PNL_FORMAL_FACT_RULE_VERSION, PnlRepository
from backend.app.services import pnl_attribution_service as service
from backend.app.services import pnl_service
from backend.app.services.runtime_cache import InMemoryTTLCache


def _business_row(report_date: str, amount: float) -> dict[str, object]:
    return {
        "report_date": report_date,
        "business_type_primary": "treasury",
        "interest_income_514": amount,
        "fair_value_change_516": 0,
        "capital_gain_517": 0,
        "manual_adjustment": 0,
        "total_pnl": amount,
        "scale_amount": 1000,
        "pnl_row_count": 1,
        "balance_row_count": 1,
    }


def _write_manifests(directory: Path, dates: list[str], *, quality: str = "ok") -> None:
    directory.mkdir(exist_ok=True)
    rows = [
        {
            "cache_key": pnl_service.PNL_CACHE_KEY,
            "report_date": report_date,
            "source_version": f"sv_verified_{report_date}",
            "rule_version": PNL_FORMAL_FACT_RULE_VERSION,
            "vendor_version": "vv_test",
            "quality_flag": quality,
        }
        for report_date in dates
    ]
    (directory / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


@pytest.fixture
def summary_source(tmp_path, monkeypatch):
    def create(dates=None, *, stale_date=None, untraced_date=None):
        selected_dates = dates or ["2026-04-30", "2026-03-31"]
        database = tmp_path / "portfolio-pnl.duckdb"
        with duckdb.connect(str(database)) as connection:
            connection.execute(
                """create table fact_formal_pnl_fi (
                    report_date varchar, rule_version varchar, instrument_code varchar,
                    portfolio_name varchar, cost_center varchar, currency_basis varchar
                )"""
            )
            connection.execute(
                """create table fact_formal_zqtz_balance_daily (
                    report_date varchar, instrument_code varchar, portfolio_name varchar,
                    cost_center varchar, currency_basis varchar, position_scope varchar,
                    business_type_primary varchar
                )"""
            )
            for report_date in selected_dates:
                connection.execute(
                    "insert into fact_formal_pnl_fi values (?, ?, 'BOND-1', 'Desk', 'CC', 'CNY')",
                    [report_date, "obsolete_fact_rule" if report_date == stale_date else PNL_FORMAL_FACT_RULE_VERSION],
                )
                if report_date != untraced_date:
                    connection.execute(
                        "insert into fact_formal_zqtz_balance_daily values (?, 'BOND-1', 'Desk', 'CC', 'CNY', 'asset', 'treasury')",
                        [report_date],
                    )
        governance = tmp_path / "governance"
        _write_manifests(governance, selected_dates)
        settings = SimpleNamespace(duckdb_path=database, governance_path=governance, governance_backend="jsonl")
        monkeypatch.setattr(service, "get_settings", lambda: settings)
        repo = PnlRepository(str(database))
        monkeypatch.setattr(service, "_pnl_repo", lambda: repo)
        monkeypatch.setattr(service, "_pnl_attribution_runtime_cache_enabled", lambda: False)
        monkeypatch.setattr(repo, "list_formal_fi_report_dates", lambda: selected_dates)
        batch_calls = []

        def batch(report_dates):
            batch_calls.append(tuple(report_dates))
            return {day: [_business_row(day, 20 if day == selected_dates[0] else 10)] for day in report_dates}

        monkeypatch.setattr(repo, "fetch_by_business_summary_rows_by_report_date", batch)
        # The market component is held healthy to isolate FI evidence from market availability.
        monkeypatch.setattr(
            service, "_tpl_market_summary_components",
            lambda **_: ({"correlation_coefficient": 0.5}, {"warning": False, "evidence_rows": 2}),
        )
        return repo, governance, batch_calls

    return create


@pytest.mark.parametrize(
    ("dates", "stale_date"),
    [
        (["2026-04-30", "2026-03-31"], "2026-04-30"),
        (["2026-01-31", "2025-12-31"], "2025-12-31"),
        (["2026-04-30", "2026-03-31", "2025-12-31"], "2025-12-31"),
    ],
    ids=["current", "prior-cross-year", "market-window-cross-year"],
)
def test_summary_rejects_old_formal_rules(summary_source, dates, stale_date):
    repo, _, _ = summary_source(dates, stale_date=stale_date)
    with pytest.raises(RuntimeError, match="stale rule versions"):
        repo.require_current_formal_pnl_rule_version(year=int(stale_date[:4]), as_of_date=stale_date)
    with pytest.raises(RuntimeError, match="stale rule versions"):
        service.attribution_analysis_summary_envelope(report_date=dates[0])


@pytest.mark.parametrize("untraced_date", ["2026-04-30", "2026-03-31"])
def test_summary_discloses_unmatched_formal_rows(summary_source, untraced_date):
    repo, _, batch_calls = summary_source(untraced_date=untraced_date)
    assert repo.count_untraced_formal_fi_rows_for_dates([untraced_date])[untraced_date] == 1
    envelope = service.attribution_analysis_summary_envelope(report_date="2026-04-30")
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result"]["warnings"]
    assert envelope["result_meta"]["filters_applied"]["untraced_pnl_rows_by_report_date"][untraced_date] == 1
    assert batch_calls == [("2026-04-30", "2026-03-31")]


@pytest.mark.parametrize("kind", ["missing", "malformed"])
def test_summary_requires_real_canonical_lineage(summary_source, kind):
    _, governance, _ = summary_source()
    path = governance / "cache_manifest.jsonl"
    path.write_text("" if kind == "missing" else json.dumps({"cache_key": pnl_service.PNL_CACHE_KEY}), encoding="utf-8")
    error = FormalLineageUnavailableError if kind == "missing" else FormalLineageMalformedError
    with pytest.raises(error):
        service.attribution_analysis_summary_envelope(report_date="2026-04-30")


def test_summary_propagates_prior_lineage_fallback(summary_source):
    _, governance, _ = summary_source()
    _write_manifests(governance, ["2026-04-30", "2026-02-28"])
    envelope = service.attribution_analysis_summary_envelope(report_date="2026-04-30")
    meta = envelope["result_meta"]
    assert meta["quality_flag"] == "stale"
    assert meta["fallback_mode"] == "latest_snapshot"
    assert meta["fallback_date"] == "2026-02-28"
    assert "sv_verified_2026-02-28" in meta["source_version"]


@pytest.mark.parametrize("quality", ["warning", "stale", "error"])
def test_summary_propagates_canonical_source_quality(summary_source, quality):
    _, governance, _ = summary_source()
    _write_manifests(governance, ["2026-04-30", "2026-03-31"], quality=quality)
    envelope = service.attribution_analysis_summary_envelope(report_date="2026-04-30")
    assert envelope["result_meta"]["quality_flag"] == quality


@pytest.mark.parametrize("requested", [None, "2026-04-15", "2026-04-30"])
def test_summary_dates_describe_requested_and_actual_snapshot(summary_source, requested):
    _, _, batch_calls = summary_source(["2026-04-30", "2026-04-15", "2026-03-31"])
    envelope = service.attribution_analysis_summary_envelope(report_date=requested)
    meta = envelope["result_meta"]
    assert meta["requested_report_date"] == requested
    assert meta["resolved_report_date"] == meta["as_of_date"] == envelope["result"]["report_date"] == "2026-04-30"
    assert "sv_verified_2026-04-30" in meta["source_version"]
    assert "sv_verified_2026-03-31" in meta["source_version"]
    assert meta["quality_flag"] == "ok"
    assert batch_calls == [("2026-04-30", "2026-03-31")]


def test_summary_cache_does_not_hide_invalidated_lineage(summary_source, monkeypatch):
    _, governance, _ = summary_source()
    from backend.app.services.runtime_cache import InMemoryTTLCache

    monkeypatch.setattr(service, "_PNL_ATTRIBUTION_CACHE", InMemoryTTLCache(ttl_seconds=300))
    monkeypatch.setattr(service, "_pnl_attribution_runtime_cache_enabled", lambda: True)
    assert service.attribution_analysis_summary_envelope(report_date="2026-04-30")["result_meta"]["quality_flag"] == "ok"
    (governance / "cache_manifest.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(FormalLineageUnavailableError):
        service.attribution_analysis_summary_envelope(report_date="2026-04-30")


@pytest.mark.parametrize("endpoint", ["summary", "volume_rate"])
def test_sql_lineage_is_rechecked_instead_of_using_jsonl_cache_identity(summary_source, monkeypatch, endpoint):
    summary_source()
    service.get_settings().governance_backend = "sql-authority"
    monkeypatch.setattr(service, "_pnl_attribution_runtime_cache_enabled", lambda: True)
    assert service._pnl_attribution_cache_key(endpoint, "2026-04-30") is None


@pytest.mark.parametrize("requested", [None, "2026-04-15", "2026-04-30"])
def test_volume_rate_dates_preserve_month_selection(summary_source, monkeypatch, requested):
    summary_source(["2026-04-30", "2026-04-15", "2026-03-31"])
    monkeypatch.setattr(
        service, "_pnl_by_business_snapshot",
        lambda day: {
            "rows": [_business_row(day, 20 if day == "2026-04-30" else 10)],
            "quality_flag": "ok", "source_version": f"sv_verified_{day}",
            "tables_used": ["fact_formal_pnl_fi"], "evidence_rows": 2,
        },
    )
    meta = service.volume_rate_attribution_envelope(report_date=requested)["result_meta"]
    assert meta["requested_report_date"] == requested
    assert meta["resolved_report_date"] == meta["as_of_date"] == "2026-04-30"


@pytest.mark.parametrize("quality", ["stale", "error"])
def test_volume_rate_keeps_prior_source_quality_and_fallback(summary_source, monkeypatch, quality):
    summary_source()

    def snapshot(day):
        prior = day == "2026-03-31"
        return {
            "rows": [_business_row(day, 10 if prior else 20)],
            "quality_flag": quality if prior else "ok",
            "source_version": f"sv_verified_{day}",
            "tables_used": ["fact_formal_pnl_fi"], "evidence_rows": 2,
            "meta": {
                "fallback_mode": "latest_snapshot" if prior else "none",
                "fallback_date": "2026-02-28" if prior else None,
            },
        }

    monkeypatch.setattr(service, "_pnl_by_business_snapshot", snapshot)
    meta = service.volume_rate_attribution_envelope(report_date="2026-04-30")["result_meta"]
    assert meta["quality_flag"] == quality
    assert meta["fallback_mode"] == "latest_snapshot"
    assert meta["fallback_date"] == "2026-02-28"
    assert "sv_verified_2026-03-31" in meta["source_version"]


@pytest.mark.parametrize("endpoint", ["summary", "volume_rate"])
def test_empty_attribution_keeps_requested_date_without_inventing_actual_date(monkeypatch, endpoint):
    monkeypatch.setattr(service, "_pnl_repo", lambda: SimpleNamespace(list_formal_fi_report_dates=lambda: []))
    monkeypatch.setattr(service, "_pnl_attribution_runtime_cache_enabled", lambda: False)
    reader = service.attribution_analysis_summary_envelope if endpoint == "summary" else service.volume_rate_attribution_envelope
    meta = reader(report_date="2026-04-30")["result_meta"]
    assert meta["requested_report_date"] == "2026-04-30"
    assert meta["resolved_report_date"] is None
    assert meta["as_of_date"] is None


@pytest.fixture(params=["summary", "volume_rate"])
def refreshing_attribution_reader(request, monkeypatch, tmp_path):
    endpoint = request.param
    database = tmp_path / "cache-identity.duckdb"
    database.write_bytes(b"initial-database")
    governance = tmp_path / "governance"
    _write_manifests(governance, ["2026-04-30"])
    settings = SimpleNamespace(duckdb_path=database, governance_path=governance, governance_backend="jsonl")
    now = [0.0]
    cache = InMemoryTTLCache(ttl_seconds=300, clock=lambda: now[0])
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    monkeypatch.setattr(service, "_pnl_attribution_runtime_cache_enabled", lambda: True)
    monkeypatch.setattr(service, "_PNL_ATTRIBUTION_CACHE", cache)
    producer_name = (
        "_attribution_analysis_summary_envelope_uncached"
        if endpoint == "summary"
        else "_volume_rate_attribution_envelope_uncached"
    )
    reader = (
        service.attribution_analysis_summary_envelope
        if endpoint == "summary"
        else service.volume_rate_attribution_envelope
    )
    builds = []

    def producer(**_kwargs):
        builds.append(len(builds) + 1)
        return {"result": {"build": builds[-1]}, "result_meta": {"trace_id": "cached-trace"}}

    monkeypatch.setattr(service, producer_name, producer)
    parts = ("2026-04-30",) if endpoint == "summary" else ("2026-04-30", "mom")
    return SimpleNamespace(
        read=lambda **kwargs: reader(report_date="2026-04-30", **kwargs),
        producer_name=producer_name, producer=producer, builds=builds,
        cache=cache, now=now, database=database, governance=governance, settings=settings,
        key=lambda: service._pnl_attribution_cache_key(endpoint, *parts),
    )


def test_force_refresh_renews_attribution_cache_before_expiry(refreshing_attribution_reader):
    context = refreshing_attribution_reader
    assert context.read()["result"]["build"] == 1
    context.now[0] = 240
    refreshed = context.read(force_refresh=True)
    assert refreshed["result"]["build"] == 2
    context.now[0] = 301
    cached = context.read()
    assert cached["result"]["build"] == 2
    assert refreshed["result_meta"]["trace_id"] != cached["result_meta"]["trace_id"]
    assert context.builds == [1, 2]
    refreshed["result"]["build"] = "caller-mutated"
    assert context.read()["result"]["build"] == 2


def test_force_refresh_keeps_valid_attribution_cache_readable(refreshing_attribution_reader, monkeypatch):
    context = refreshing_attribution_reader
    assert context.read()["result"]["build"] == 1
    started, release = Event(), Event()

    def producer(**kwargs):
        started.set()
        assert release.wait(timeout=5)
        return context.producer(**kwargs)

    monkeypatch.setattr(service, context.producer_name, producer)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(context.read, force_refresh=True)
        try:
            assert started.wait(timeout=5)
            assert context.read()["result"]["build"] == 1
        finally:
            release.set()
        assert future.result(timeout=5)["result"]["build"] == 2
    assert context.read()["result"]["build"] == 2


def test_force_refresh_does_not_restore_cleared_attribution_cache(refreshing_attribution_reader, monkeypatch):
    context = refreshing_attribution_reader
    assert context.read()["result"]["build"] == 1

    def producer(**kwargs):
        service.invalidate_pnl_attribution_read_cache()
        return context.producer(**kwargs)

    monkeypatch.setattr(service, context.producer_name, producer)
    assert context.read(force_refresh=True)["result"]["build"] == 2
    assert context.cache.get(context.key()) == (False, None)
    monkeypatch.setattr(service, context.producer_name, context.producer)
    assert context.read()["result"]["build"] == 3


@pytest.mark.parametrize("changed_identity", ["database", "governance"])
def test_force_refresh_does_not_fill_changed_attribution_identity(
    refreshing_attribution_reader, monkeypatch, changed_identity,
):
    context = refreshing_attribution_reader
    assert context.read()["result"]["build"] == 1
    previous_key = context.key()

    def producer(**kwargs):
        if changed_identity == "database":
            context.database.write_bytes(b"replaced-database-generation")
        else:
            _write_manifests(context.governance, ["2026-04-30"], quality="warning")
        return context.producer(**kwargs)

    monkeypatch.setattr(service, context.producer_name, producer)
    assert context.read(force_refresh=True)["result"]["build"] == 2
    assert context.key() != previous_key
    assert context.cache.get(previous_key)[1]["result"]["build"] == 1
    assert context.cache.get(context.key()) == (False, None)
    monkeypatch.setattr(service, context.producer_name, context.producer)
    assert context.read()["result"]["build"] == 3


def test_failed_force_refresh_preserves_valid_attribution_cache(refreshing_attribution_reader, monkeypatch):
    context = refreshing_attribution_reader
    assert context.read()["result"]["build"] == 1

    def producer(**_kwargs):
        raise FormalLineageUnavailableError("refreshed evidence is unavailable")

    monkeypatch.setattr(service, context.producer_name, producer)
    with pytest.raises(FormalLineageUnavailableError):
        context.read(force_refresh=True)
    assert context.read()["result"]["build"] == 1


def test_force_refresh_does_not_enable_sql_attribution_cache(refreshing_attribution_reader):
    context = refreshing_attribution_reader
    context.settings.governance_backend = "sql-authority"
    assert context.key() is None
    assert context.read(force_refresh=True)["result"]["build"] == 1
    assert context.read()["result"]["build"] == 2
