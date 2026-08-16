from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.app.tasks import home_macro_release_refresh as refresh_module


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


def test_refresh_orchestrates_tushare_ingest_and_tushare_only_pmi_backfill(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    snapshots = iter(
        [
            {
                "tushare.macro.cn_cpi.monthly": "2026-05-01",
                "tushare.macro.cn_ppi.monthly": "2026-05-01",
                "tushare.macro.cn_gdp.quarterly": "2026-03-31",
                "M0017126": "2026-05-01",
            },
            {
                "tushare.macro.cn_cpi.monthly": "2026-06-01",
                "tushare.macro.cn_ppi.monthly": "2026-06-01",
                "tushare.macro.cn_gdp.quarterly": "2026-06-30",
                "nbs.macro.cn_gdp.quarterly": "2026-06-30",
                "M0017126": "2026-06-01",
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
            "total_added": 1,
            "results": {"制造业PMI": 1},
            "errors": {},
            "source_by_series": {"M0017126": "tushare_macro"},
            "vendor_versions": {"M0017126": "vv_backfill_macro_tushare_macro_20260716_abcd"},
        }

    monkeypatch.setattr(refresh_module, "backfill_macro_series", _backfill)

    result = refresh_module.refresh_home_macro_release_sources(today=date(2026, 7, 16))

    assert calls[0][0] == "nbs"
    assert calls[1][0] == "ingest"
    assert calls[2] == (
        "backfill",
        {
            "duckdb_path": "test.duckdb",
            "series_names": ["制造业PMI"],
            "sources_filter": ["tushare_macro"],
            "start_date": "2026-04-17",
            "end_date": "2026-07-16",
            "dry_run": False,
        },
    )
    assert result["status"] == "success"
    assert result["run_id"].startswith("home-macro-release-")
    assert result["materialized_rows"] == 7
    assert result["source_by_series"] == {"M0017126": "tushare_macro"}
    assert "tushare_macro" in " ".join(result["warnings"])
    assert "NBS" in " ".join(result["warnings"])
    assert all(item["status"] == "success" for item in result["series"])


def test_refresh_is_success_when_required_series_is_unchanged_but_current(monkeypatch) -> None:
    unchanged = {
        "tushare.macro.cn_cpi.monthly": "2026-06-01",
        "tushare.macro.cn_ppi.monthly": "2026-06-01",
        "tushare.macro.cn_gdp.quarterly": "2026-06-30",
        "M0017126": "2026-06-01",
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
            "results": {"制造业PMI": 0},
            "errors": {},
            "source_by_series": {"M0017126": "tushare_macro"},
            "vendor_versions": {"M0017126": "vv_tushare"},
        },
    )

    result = refresh_module.refresh_home_macro_release_sources(today=date(2026, 7, 16))

    assert result["status"] == "success"
    assert all(item["status"] == "success" for item in result["series"])


def test_monthly_refresh_freshness_uses_report_period_end() -> None:
    freshness = refresh_module._freshness("2026-06-01", today=date(2026, 7, 17), cadence="monthly")

    assert freshness == {"status": "ready", "age_days": 17}


def test_dry_run_never_calls_writing_ingest_and_keeps_explicit_pmi_scope(monkeypatch) -> None:
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
            "series_names": ["制造业PMI"],
            "sources_filter": ["tushare_macro"],
            "start_date": "2026-04-17",
            "end_date": "2026-07-16",
            "dry_run": True,
        }
    ]


def test_refresh_actor_has_stable_worker_name() -> None:
    assert refresh_module.refresh_home_macro_release_sources_actor.actor_name == (
        "refresh_home_macro_release_sources"
    )
