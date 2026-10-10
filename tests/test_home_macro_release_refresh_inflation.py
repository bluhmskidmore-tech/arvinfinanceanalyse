from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from backend.app.repositories.home_macro_release_context_repo import (
    HomeMacroObservation,
    HomeMacroSeriesRead,
)
from backend.app.services.home_macro_release_context_service import (
    HomeMacroReleaseContextService,
)
from backend.app.tasks import home_macro_release_refresh as refresh_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_data,
]
ROOT = Path(__file__).resolve().parents[1]


@dataclass
class _Settings:
    duckdb_path: str = "test.duckdb"


def _cycle_success(**_kwargs: object) -> dict[str, object]:
    return {
        "status": "completed",
        "total_added": 3,
        "results": {
            "制造业PMI": 1,
            "社会融资规模存量:同比": 1,
            "M2:同比": 1,
        },
        "errors": {},
        "source_by_series": {},
        "vendor_versions": {},
    }


def _series(result: dict[str, object], series_id: str) -> dict[str, object]:
    return next(item for item in result["series"] if item["series_id"] == series_id)


def test_fresh_official_inflation_succeeds_when_tushare_fetch_fails(monkeypatch) -> None:
    snapshots = iter(
        [
            {
                "tushare.macro.cn_cpi.monthly": "2026-07-01",
                "tushare.macro.cn_ppi.monthly": "2026-07-01",
            },
            {
                "nbs.macro.cn_cpi.monthly": "2026-08-01",
                "nbs.macro.cn_ppi.monthly": "2026-08-01",
                "nbs.macro.cn_gdp.quarterly": "2026-06-30",
                "M0017126": "2026-08-01",
                "M5525763": "2026-08-01",
                "M0001385": "2026-08-01",
            },
        ]
    )
    monkeypatch.setattr(refresh_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(refresh_module, "_read_latest_observations", lambda _path: next(snapshots))
    monkeypatch.setattr(
        refresh_module,
        "run_nbs_gdp_release_ingest_once",
        lambda **_kwargs: {
            "status": "success",
            "ingest_batch_id": "nbs-gdp-batch",
            "materialized_rows": 1,
        },
    )
    monkeypatch.setattr(
        refresh_module,
        "run_nbs_inflation_release_ingest_once",
        lambda **_kwargs: {
            "status": "success",
            "ingest_batch_id": "nbs-inflation-batch",
            "results": [
                {"series_id": "nbs.macro.cn_cpi.monthly", "materialized_rows": 2},
                {"series_id": "nbs.macro.cn_ppi.monthly", "materialized_rows": 2},
            ],
        },
    )
    monkeypatch.setattr(
        refresh_module,
        "run_tushare_macro_ingest_once",
        lambda: (_ for _ in ()).throw(RuntimeError("tushare unavailable")),
    )
    monkeypatch.setattr(refresh_module, "backfill_macro_series", _cycle_success)

    result = refresh_module.refresh_home_macro_release_sources(today=date(2026, 9, 16))

    assert result["status"] == "success"
    for tushare_id, nbs_id in (
        ("tushare.macro.cn_cpi.monthly", "nbs.macro.cn_cpi.monthly"),
        ("tushare.macro.cn_ppi.monthly", "nbs.macro.cn_ppi.monthly"),
    ):
        item = _series(result, tushare_id)
        assert item["status"] == "success"
        assert item["latest_observation"] == "2026-08-01"
        assert item["selected_series_id"] == nbs_id
        assert item["selected_vendor"] == "NBS official release"
        assert item["selection_status"] == "ready"
        assert item["materialized_rows"] == 2
    assert any("Tushare macro ingest error" in warning for warning in result["warnings"])


class _ContextRepository:
    def __init__(self, reads: dict[str, HomeMacroSeriesRead]) -> None:
        self._reads = reads

    def read_recent_observations(
        self,
        *,
        table: str,
        series_id: str,
        cutoff_date: date,
        limit: int = 2,
    ) -> HomeMacroSeriesRead:
        del cutoff_date, limit
        return self._reads.get(
            series_id,
            HomeMacroSeriesRead(
                table=table,
                series_id=series_id,
                observations=[],
                error="source_missing",
            ),
        )


def _monthly_read(
    series_id: str,
    vendor_name: str,
    current: tuple[date, float],
    previous: tuple[date, float],
) -> HomeMacroSeriesRead:
    observations = [
        HomeMacroObservation(
            table="std_external_macro_daily",
            series_id=series_id,
            observation_date=observation_date,
            value=value,
            cadence="monthly",
            unit="pct",
            source_version=f"sv-{series_id}-{observation_date.isoformat()}",
            vendor_version=f"vv-{vendor_name}",
            rule_version="rv-test",
            vendor_name=vendor_name,
            ingest_batch_id="batch-test",
        )
        for observation_date, value in (current, previous)
    ]
    return HomeMacroSeriesRead(
        table="std_external_macro_daily",
        series_id=series_id,
        observations=observations,
    )


def test_home_context_uses_two_official_periods_without_cross_vendor_mixing() -> None:
    reads = {
        "nbs.macro.cn_cpi.monthly": _monthly_read(
            "nbs.macro.cn_cpi.monthly",
            "nbs",
            (date(2026, 8, 1), 0.8),
            (date(2026, 7, 1), 0.5),
        ),
        "nbs.macro.cn_ppi.monthly": _monthly_read(
            "nbs.macro.cn_ppi.monthly",
            "nbs",
            (date(2026, 8, 1), 3.8),
            (date(2026, 7, 1), 3.5),
        ),
        "tushare.macro.cn_cpi.monthly": _monthly_read(
            "tushare.macro.cn_cpi.monthly",
            "tushare",
            (date(2026, 7, 1), 99.0),
            (date(2026, 6, 1), 98.0),
        ),
        "tushare.macro.cn_ppi.monthly": _monthly_read(
            "tushare.macro.cn_ppi.monthly",
            "tushare",
            (date(2026, 7, 1), 97.0),
            (date(2026, 6, 1), 96.0),
        ),
    }
    envelope = HomeMacroReleaseContextService(
        repository=_ContextRepository(reads),
        bindings_path=ROOT / "config" / "home_macro_release_bindings.json",
    ).build_envelope(
        window_start_date=date(2026, 9, 16),
        window_end_date=date(2026, 10, 31),
    )
    item = next(
        history_item
        for history_item in envelope.result.history_items
        if history_item.indicator_key == "cn_inflation"
    )

    assert item.source_status == "ready"
    assert item.observation_date == date(2026, 8, 1)
    assert item.previous_observation_date == date(2026, 7, 1)
    assert [
        (metric.actual_value, metric.previous_value, metric.change_value)
        for metric in item.metrics
    ] == [(0.8, 0.5, 0.3), (3.8, 3.5, 0.3)]
    assert all("99.0" not in note and "97.0" not in note for note in item.notes)


@pytest.mark.parametrize("failure_stage", ["gdp", "inflation", "tushare", "cycle"])
def test_macro_refresh_failure_receipt_omits_private_payload(monkeypatch, failure_stage):
    from unittest.mock import Mock
    marker = "synthetic-macro-refresh-private-token"
    monkeypatch.setattr(refresh_module, "get_settings", lambda: _Settings())
    monkeypatch.setattr(refresh_module, "_read_latest_observations", lambda _: {})
    mocks = {
        "gdp": Mock(return_value={"status": "success", "materialized_rows": 0}),
        "inflation": Mock(return_value={"status": "success", "results": []}),
        "tushare": Mock(return_value={"status": "success", "results": [], "failed": []}),
        "cycle": Mock(side_effect=_cycle_success),
    }
    mocks[failure_stage].side_effect = TypeError(marker)
    for key, symbol in [("gdp", "run_nbs_gdp_release_ingest_once"), ("inflation", "run_nbs_inflation_release_ingest_once"), ("tushare", "run_tushare_macro_ingest_once"), ("cycle", "backfill_macro_series")]:
        monkeypatch.setattr(refresh_module, symbol, mocks[key])
    result = refresh_module.refresh_home_macro_release_sources(today=date(2026, 9, 16))
    for mock in mocks.values():
        mock.assert_called_once()
    assert result["status"] != "success"
    assert result["warnings"]
    assert marker not in str(result)
    assert "TypeError" in str(result["warnings"])
