from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from backend.app.tasks import home_macro_release_refresh as refresh_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_data,
]


@pytest.fixture(autouse=True)
def _stub_nbs_inflation(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        refresh_module,
        "run_nbs_inflation_release_ingest_once",
        lambda **kwargs: captured.update(kwargs)
        or {
            "status": "success",
            "ingest_batch_id": "nbs-inflation-batch",
            "results": [],
        },
    )
    return captured


@dataclass
class _Settings:
    duckdb_path: str = "test.duckdb"


def _successful_ingest() -> dict[str, object]:
    series = [
        "tushare.macro.cn_cpi.monthly",
        "tushare.macro.cn_ppi.monthly",
        "tushare.macro.cn_gdp.quarterly",
        "tushare.macro.cn_money.monthly",
    ]
    return {
        "status": "success",
        "ingest_batch_id": "batch-1",
        "succeeded": series,
        "failed": [],
        "results": [{"series_id": item, "materialized_rows": 2} for item in series],
    }


def test_refresh_orchestrates_tushare_ingest_and_cycle_macro_backfill(
    monkeypatch,
    _stub_nbs_inflation: dict[str, object],
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    snapshots = iter(
        [
            {
                "tushare.macro.cn_cpi.monthly": "2026-05-01",
                "tushare.macro.cn_ppi.monthly": "2026-05-01",
                "tushare.macro.cn_gdp.quarterly": "2026-03-31",
                "M0017126": "2026-05-01",
                "M5525763": "2026-05-01",
                "M0001385": "2026-05-01",
            },
            {
                "tushare.macro.cn_cpi.monthly": "2026-06-01",
                "tushare.macro.cn_ppi.monthly": "2026-06-01",
                "tushare.macro.cn_gdp.quarterly": "2026-06-30",
                "nbs.macro.cn_gdp.quarterly": "2026-06-30",
                "M0017126": "2026-06-01",
                "M5525763": "2026-06-01",
                "M0001385": "2026-06-01",
            },
        ]
    )
    monkeypatch.setattr(refresh_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(refresh_module, "_read_latest_observations", lambda _path: next(snapshots))
    monkeypatch.setattr(
        refresh_module,
        "run_nbs_gdp_release_ingest_once",
        lambda **_kwargs: calls.append(("nbs", {}))
        or {
            "status": "success",
            "ingest_batch_id": "nbs-batch",
            "materialized_rows": 2,
        },
    )
    monkeypatch.setattr(
        refresh_module,
        "run_tushare_macro_ingest_once",
        lambda: calls.append(("ingest", {})) or _successful_ingest(),
    )

    def _backfill(**kwargs: object) -> dict[str, object]:
        calls.append(("backfill", kwargs))
        return {
            "status": "completed",
            "total_added": 3,
            "results": {
                "制造业PMI": 1,
                "社会融资规模存量:同比": 1,
                "M2:同比": 1,
            },
            "errors": {},
            "source_by_series": {
                "M0017126": "nbs_pmi_release",
                "M5525763": "pbc_financial_statistics_release",
                "M0001385": "pbc_financial_statistics_release",
            },
            "vendor_versions": {
                "M0017126": "vv_backfill_macro_nbs_pmi_release_20260716_abcd",
                "M5525763": "vv_backfill_macro_pbc_financial_statistics_release_20260716_efgh",
                "M0001385": "vv_backfill_macro_pbc_financial_statistics_release_20260716_ijkl",
            },
        }

    monkeypatch.setattr(refresh_module, "backfill_macro_series", _backfill)

    result = refresh_module.refresh_home_macro_release_sources(
        today=date(2026, 7, 16),
        nbs_inflation_source_ip="192.0.2.10",
    )

    assert calls[0][0] == "nbs"
    assert calls[1][0] == "ingest"
    assert calls[2] == (
        "backfill",
        {
            "duckdb_path": "test.duckdb",
            "series_names": ["制造业PMI", "社会融资规模存量:同比", "M2:同比"],
            "start_date": "2026-04-17",
            "end_date": "2026-07-16",
            "dry_run": False,
        },
    )
    assert _stub_nbs_inflation == {
        "reference_date": date(2026, 7, 16),
        "source_ip": "192.0.2.10",
    }
    assert result["status"] == "success"
    assert result["run_id"].startswith("home-macro-release-")
    assert result["materialized_rows"] == 9
    assert result["source_by_series"] == {
        "M0017126": "nbs_pmi_release",
        "M5525763": "pbc_financial_statistics_release",
        "M0001385": "pbc_financial_statistics_release",
    }
    warnings = " ".join(result["warnings"])
    assert "official-first" in warnings
    assert "fallback" in warnings
    assert "actual vendor tushare_macro" not in warnings
    assert "M0017126=nbs_pmi_release" in warnings
    assert "M5525763=pbc_financial_statistics_release" in warnings
    assert "NBS" in " ".join(result["warnings"])
    assert all(item["status"] == "success" for item in result["series"])


def test_refresh_is_success_when_required_series_is_unchanged_but_current(monkeypatch) -> None:
    unchanged = {
        "tushare.macro.cn_cpi.monthly": "2026-06-01",
        "tushare.macro.cn_ppi.monthly": "2026-06-01",
        "tushare.macro.cn_gdp.quarterly": "2026-06-30",
        "M0017126": "2026-06-01",
        "M5525763": "2026-06-01",
        "M0001385": "2026-06-01",
    }
    monkeypatch.setattr(refresh_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        refresh_module,
        "run_nbs_gdp_release_ingest_once",
        lambda **_kwargs: {"status": "blocked", "error": "not available"},
    )
    monkeypatch.setattr(refresh_module, "_read_latest_observations", lambda _path: unchanged)
    monkeypatch.setattr(refresh_module, "run_tushare_macro_ingest_once", _successful_ingest)
    monkeypatch.setattr(
        refresh_module,
        "backfill_macro_series",
        lambda **_kwargs: {
            "status": "completed",
            "total_added": 0,
            "results": {
                "制造业PMI": 0,
                "社会融资规模存量:同比": 0,
                "M2:同比": 0,
            },
            "errors": {},
            "source_by_series": {
                "M0017126": "tushare_macro",
                "M5525763": "tushare_macro",
                "M0001385": "tushare_macro",
            },
            "vendor_versions": {
                "M0017126": "vv_tushare_pmi",
                "M5525763": "vv_tushare_social_financing",
                "M0001385": "vv_tushare_m2",
            },
        },
    )

    result = refresh_module.refresh_home_macro_release_sources(today=date(2026, 7, 16))

    assert result["status"] == "success"
    assert all(item["status"] == "success" for item in result["series"])


def test_monthly_refresh_freshness_uses_report_period_end() -> None:
    freshness = refresh_module._freshness("2026-06-01", today=date(2026, 7, 17), cadence="monthly")

    assert freshness == {"status": "ready", "age_days": 17}


def test_dry_run_never_calls_writing_ingest_and_keeps_explicit_cycle_scope(monkeypatch) -> None:
    monkeypatch.setattr(refresh_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(
        refresh_module,
        "run_nbs_gdp_release_ingest_once",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("dry-run must not fetch NBS")
        ),
    )
    monkeypatch.setattr(refresh_module, "_read_latest_observations", lambda _path: {})
    monkeypatch.setattr(
        refresh_module,
        "run_tushare_macro_ingest_once",
        lambda: (_ for _ in ()).throw(AssertionError("dry-run must not ingest")),
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        refresh_module,
        "backfill_macro_series",
        lambda **kwargs: calls.append(kwargs) or {"status": "planned", "series_plans": []},
    )

    result = refresh_module.refresh_home_macro_release_sources(
        today=date(2026, 7, 16),
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert calls == [
        {
            "duckdb_path": "test.duckdb",
            "series_names": ["制造业PMI", "社会融资规模存量:同比", "M2:同比"],
            "start_date": "2026-04-17",
            "end_date": "2026-07-16",
            "dry_run": True,
        }
    ]
    assert "official-first backfill plan" in " ".join(result["warnings"])


def test_refresh_discloses_governed_tushare_fallback_without_pretending_official(monkeypatch) -> None:
    snapshots = iter(
        [
            {
                "tushare.macro.cn_cpi.monthly": "2026-05-01",
                "tushare.macro.cn_ppi.monthly": "2026-05-01",
                "tushare.macro.cn_gdp.quarterly": "2026-03-31",
                "M0017126": "2026-05-01",
                "M5525763": "2026-05-01",
                "M0001385": "2026-05-01",
            },
            {
                "tushare.macro.cn_cpi.monthly": "2026-06-01",
                "tushare.macro.cn_ppi.monthly": "2026-06-01",
                "tushare.macro.cn_gdp.quarterly": "2026-06-30",
                "M0017126": "2026-06-01",
                "M5525763": "2026-06-01",
                "M0001385": "2026-06-01",
            },
        ]
    )
    monkeypatch.setattr(refresh_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(refresh_module, "_read_latest_observations", lambda _path: next(snapshots))
    monkeypatch.setattr(
        refresh_module,
        "run_nbs_gdp_release_ingest_once",
        lambda **_kwargs: {"status": "blocked", "error": "official unavailable"},
    )
    monkeypatch.setattr(refresh_module, "run_tushare_macro_ingest_once", _successful_ingest)
    monkeypatch.setattr(
        refresh_module,
        "backfill_macro_series",
        lambda **_kwargs: {
            "status": "completed",
            "total_added": 3,
            "results": {
                "制造业PMI": 1,
                "社会融资规模存量:同比": 1,
                "M2:同比": 1,
            },
            "errors": {},
            "source_by_series": {
                "M0017126": "tushare_macro",
                "M5525763": "tushare_macro",
                "M0001385": "tushare_macro",
            },
            "vendor_versions": {
                "M0017126": "vv_tushare_pmi",
                "M5525763": "vv_tushare_social_financing",
                "M0001385": "vv_tushare_m2",
            },
        },
    )

    result = refresh_module.refresh_home_macro_release_sources(today=date(2026, 7, 16))

    warnings = " ".join(result["warnings"])
    assert result["source_by_series"] == {
        "M0017126": "tushare_macro",
        "M5525763": "tushare_macro",
        "M0001385": "tushare_macro",
    }
    assert "official-first" in warnings
    assert "fallback" in warnings
    assert "actual vendor tushare_macro" not in warnings
    assert "M0017126=tushare_macro" in warnings


def test_refresh_actor_has_stable_worker_name() -> None:
    assert refresh_module.refresh_home_macro_release_sources_actor.actor_name == (
        "refresh_home_macro_release_sources"
    )
