from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.repositories.home_macro_release_context_repo import (
    HomeMacroObservation,
    HomeMacroSeriesRead,
)
from backend.app.services.home_macro_release_context_service import (
    HomeMacroReleaseContextService,
)


NBS_SERIES = "nbs.macro.cn_gdp.quarterly"
TUSHARE_SERIES = "tushare.macro.cn_gdp.quarterly"
TABLE = "std_external_macro_daily"


class _Repository:
    def __init__(self, reads: dict[str, HomeMacroSeriesRead]) -> None:
        self.reads = reads

    def read_recent_observations(
        self,
        *,
        table: str,
        series_id: str,
        cutoff_date: date,
        limit: int = 2,
    ) -> HomeMacroSeriesRead:
        del cutoff_date, limit
        return self.reads.get(
            series_id,
            HomeMacroSeriesRead(
                table=table,
                series_id=series_id,
                observations=[],
                error="relation_missing",
            ),
        )


def _read(
    series_id: str,
    vendor: str,
    current_date: date,
    current_value: float,
    previous_date: date,
    previous_value: float,
    *,
    unit: str = "pct",
    version: str = "v1",
) -> HomeMacroSeriesRead:
    def observation(observation_date: date, value: float, suffix: str) -> HomeMacroObservation:
        return HomeMacroObservation(
            table=TABLE,
            series_id=series_id,
            observation_date=observation_date,
            value=value,
            cadence="quarterly",
            unit=unit,
            source_version=f"sv-{version}-{suffix}",
            vendor_version=f"vv-{version}-{suffix}",
            rule_version="rv-test",
            vendor_name=vendor,
            ingest_batch_id=f"batch-{version}",
        )

    return HomeMacroSeriesRead(
        table=TABLE,
        series_id=series_id,
        observations=[
            observation(current_date, current_value, "current"),
            observation(previous_date, previous_value, "previous"),
        ],
    )


def _bindings(tmp_path: Path, *, include_legacy_source: bool = False) -> Path:
    metric = {
        "metric_key": "gdp_yoy",
        "label": "GDP YoY",
        "source_candidates": [
            {
                "table": TABLE,
                "series_id": NBS_SERIES,
                "vendor_name": "NBS official release",
                "priority": 1,
            },
            {
                "table": TABLE,
                "series_id": TUSHARE_SERIES,
                "vendor_name": "Tushare",
                "priority": 2,
            },
        ],
        "cadence": "quarterly",
        "display_unit": "pct",
        "change_unit": "pct_point",
        "precision": 1,
    }
    if include_legacy_source:
        metric.update({"table": TABLE, "series_id": TUSHARE_SERIES})
    path = tmp_path / "bindings.json"
    path.write_text(
        json.dumps(
            {
                "rule_version": "rv_home_macro_release_context_v1",
                "groups": [
                    {
                        "indicator_key": "cn_growth",
                        "title": "China growth",
                        "region": "CN",
                        "category": "growth",
                        "importance": "high",
                        "priority": 1,
                        "availability": "automatic",
                        "publisher_name": "National Bureau of Statistics of China",
                        "vendor_name": "NBS official release",
                        "metrics": [metric],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _build(tmp_path: Path, reads: dict[str, HomeMacroSeriesRead], cutoff: date):
    return HomeMacroReleaseContextService(
        repository=_Repository(reads),
        bindings_path=_bindings(tmp_path),
    ).build_envelope(
        window_start_date=cutoff,
        window_end_date=cutoff,
    )


def test_newer_official_gdp_is_selected_without_cross_vendor_value_mixing(tmp_path: Path) -> None:
    reads = {
        NBS_SERIES: _read(
            NBS_SERIES,
            "nbs",
            date(2026, 6, 30),
            4.3,
            date(2026, 3, 31),
            5.0,
            version="nbs",
        ),
        TUSHARE_SERIES: _read(
            TUSHARE_SERIES,
            "tushare",
            date(2026, 3, 31),
            5.0,
            date(2025, 12, 31),
            99.0,
            version="tushare",
        ),
    }

    envelope = _build(tmp_path, reads, date(2026, 7, 17))
    item = envelope.result.history_items[0]
    metric = item.metrics[0]

    assert item.source_status == "ready"
    assert item.source_name == "NBS official release"
    assert item.observation_date == date(2026, 6, 30)
    assert (metric.actual_value, metric.previous_value, metric.change_value) == (4.3, 5.0, -0.7)
    assert any("Selected vendor: NBS official release" in note for note in item.notes)
    assert any("Rejected vendor: Tushare" in note for note in item.notes)
    assert envelope.result_meta.evidence_rows == 2

    changed_fallback = dict(reads)
    changed_fallback[TUSHARE_SERIES] = _read(
        TUSHARE_SERIES,
        "tushare",
        date(2026, 3, 31),
        -100.0,
        date(2025, 12, 31),
        -200.0,
        version="changed-fallback",
    )
    second = _build(tmp_path, changed_fallback, date(2026, 7, 17))
    assert envelope.result_meta.source_version == second.result_meta.source_version
    assert envelope.result_meta.vendor_version == second.result_meta.vendor_version


def test_missing_official_source_uses_fresh_tushare_as_visible_fallback(tmp_path: Path) -> None:
    envelope = _build(
        tmp_path,
        {
            TUSHARE_SERIES: _read(
                TUSHARE_SERIES,
                "tushare",
                date(2026, 6, 30),
                4.4,
                date(2026, 3, 31),
                5.1,
            )
        },
        date(2026, 7, 17),
    )
    item = envelope.result.history_items[0]

    assert item.source_status == "fallback"
    assert item.source_name == "Tushare"
    assert item.metrics[0].change_value == -0.7
    assert envelope.result.coverage.fallback_count == 1
    assert any("official source unavailable" in note.lower() for note in item.notes)


def test_fresh_newer_fallback_beats_stale_official_candidate(tmp_path: Path) -> None:
    envelope = _build(
        tmp_path,
        {
            NBS_SERIES: _read(
                NBS_SERIES,
                "nbs",
                date(2026, 3, 31),
                5.0,
                date(2025, 12, 31),
                5.2,
            ),
            TUSHARE_SERIES: _read(
                TUSHARE_SERIES,
                "tushare",
                date(2026, 6, 30),
                4.4,
                date(2026, 3, 31),
                5.0,
            ),
        },
        date(2026, 7, 17),
    )

    item = envelope.result.history_items[0]
    assert item.source_status == "fallback"
    assert item.source_name == "Tushare"
    assert item.observation_date == date(2026, 6, 30)


def test_both_stale_candidates_choose_latest_period_and_keep_stale_status(tmp_path: Path) -> None:
    envelope = _build(
        tmp_path,
        {
            NBS_SERIES: _read(
                NBS_SERIES,
                "nbs",
                date(2026, 6, 30),
                4.3,
                date(2026, 3, 31),
                5.0,
            ),
            TUSHARE_SERIES: _read(
                TUSHARE_SERIES,
                "tushare",
                date(2026, 3, 31),
                5.0,
                date(2025, 12, 31),
                5.2,
            ),
        },
        date(2026, 11, 1),
    )

    item = envelope.result.history_items[0]
    assert item.source_status == "stale"
    assert item.source_name == "NBS official release"
    assert item.observation_date == date(2026, 6, 30)


def test_invalid_official_unit_is_excluded_instead_of_converted(tmp_path: Path) -> None:
    envelope = _build(
        tmp_path,
        {
            NBS_SERIES: _read(
                NBS_SERIES,
                "nbs",
                date(2026, 6, 30),
                4.3,
                date(2026, 3, 31),
                5.0,
                unit="index",
            ),
            TUSHARE_SERIES: _read(
                TUSHARE_SERIES,
                "tushare",
                date(2026, 6, 30),
                4.4,
                date(2026, 3, 31),
                5.1,
            ),
        },
        date(2026, 7, 17),
    )

    item = envelope.result.history_items[0]
    assert item.source_status == "fallback"
    assert item.metrics[0].actual_value == 4.4
    assert any("unit mismatch" in note.lower() for note in item.notes)


def test_metric_binding_rejects_legacy_source_mixed_with_candidates(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        HomeMacroReleaseContextService(
            repository=_Repository({}),
            bindings_path=_bindings(tmp_path, include_legacy_source=True),
        )
