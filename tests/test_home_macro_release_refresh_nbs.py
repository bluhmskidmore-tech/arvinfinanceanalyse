from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.app.tasks import home_macro_release_refresh as refresh_module


NBS_GDP = "nbs.macro.cn_gdp.quarterly"
TUSHARE_GDP = "tushare.macro.cn_gdp.quarterly"


@dataclass
class _Settings:
    duckdb_path: str = "test.duckdb"


def _tushare_success() -> dict[str, object]:
    series = [
        "tushare.macro.cn_cpi.monthly",
        "tushare.macro.cn_ppi.monthly",
        TUSHARE_GDP,
    ]
    return {
        "status": "success",
        "ingest_batch_id": "tushare-batch",
        "succeeded": series,
        "failed": [],
        "results": [{"series_id": item, "materialized_rows": 2} for item in series],
    }


def _pmi_success(**_kwargs: object) -> dict[str, object]:
    return {
        "status": "completed",
        "total_added": 1,
        "results": {"PMI": 1},
        "errors": {},
        "source_by_series": {"M0017126": "tushare_macro"},
        "vendor_versions": {"M0017126": "vv_tushare"},
    }


def _gdp(result: dict[str, object]) -> dict[str, object]:
    return next(item for item in result["series"] if item["label"] == "China GDP YoY")


def test_nbs_runs_first_and_fresh_official_gdp_is_selected(monkeypatch) -> None:
    calls: list[str] = []
    snapshots = iter(
        [
            {},
            {
                NBS_GDP: "2026-06-30",
                TUSHARE_GDP: "2026-03-31",
                "tushare.macro.cn_cpi.monthly": "2026-06-01",
                "tushare.macro.cn_ppi.monthly": "2026-06-01",
                "M0017126": "2026-06-01",
            },
        ]
    )
    monkeypatch.setattr(refresh_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(refresh_module, "_read_latest_observations", lambda _path: next(snapshots))
    monkeypatch.setattr(
        refresh_module,
        "run_nbs_gdp_release_ingest_once",
        lambda **_kwargs: calls.append("nbs")
        or {
            "status": "success",
            "ingest_batch_id": "nbs-batch",
            "materialized_rows": 2,
        },
    )
    monkeypatch.setattr(
        refresh_module,
        "run_tushare_macro_ingest_once",
        lambda: calls.append("tushare") or _tushare_success(),
    )
    monkeypatch.setattr(
        refresh_module,
        "backfill_macro_series",
        lambda **kwargs: calls.append("pmi") or _pmi_success(**kwargs),
    )

    result = refresh_module.refresh_home_macro_release_sources(today=date(2026, 7, 17))

    assert calls == ["nbs", "tushare", "pmi"]
    assert result["status"] == "success"
    assert result["nbs_ingest_batch_id"] == "nbs-batch"
    assert _gdp(result)["selected_series_id"] == NBS_GDP
    assert _gdp(result)["selected_vendor"] == "NBS official release"
    assert _gdp(result)["selection_status"] == "ready"


def test_nbs_failure_keeps_fresh_tushare_as_visible_fallback(monkeypatch) -> None:
    snapshots = iter(
        [
            {},
            {
                TUSHARE_GDP: "2026-06-30",
                "tushare.macro.cn_cpi.monthly": "2026-06-01",
                "tushare.macro.cn_ppi.monthly": "2026-06-01",
                "M0017126": "2026-06-01",
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
    monkeypatch.setattr(refresh_module, "run_tushare_macro_ingest_once", _tushare_success)
    monkeypatch.setattr(refresh_module, "backfill_macro_series", _pmi_success)

    result = refresh_module.refresh_home_macro_release_sources(today=date(2026, 7, 17))

    assert result["status"] == "success"
    assert _gdp(result)["status"] == "success"
    assert _gdp(result)["selected_series_id"] == TUSHARE_GDP
    assert _gdp(result)["selection_status"] == "fallback"
    assert any("official unavailable" in warning for warning in result["warnings"])


def test_dry_run_reports_both_gdp_candidates_without_nbs_fetch(monkeypatch) -> None:
    monkeypatch.setattr(refresh_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(refresh_module, "_read_latest_observations", lambda _path: {})
    monkeypatch.setattr(
        refresh_module,
        "run_nbs_gdp_release_ingest_once",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("dry-run must not fetch NBS")),
    )
    monkeypatch.setattr(
        refresh_module,
        "run_tushare_macro_ingest_once",
        lambda: (_ for _ in ()).throw(AssertionError("dry-run must not fetch Tushare")),
    )
    monkeypatch.setattr(
        refresh_module,
        "backfill_macro_series",
        lambda **_kwargs: {"status": "planned", "series_plans": []},
    )

    result = refresh_module.refresh_home_macro_release_sources(
        today=date(2026, 7, 17),
        dry_run=True,
    )

    assert _gdp(result)["source_candidates"] == [NBS_GDP, TUSHARE_GDP]
