from __future__ import annotations

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


ROOT = Path(__file__).resolve().parents[1]
BINDINGS_PATH = ROOT / "config" / "home_macro_release_bindings.json"


class _FakeRepository:
    def __init__(self, reads: dict[str, HomeMacroSeriesRead]) -> None:
        self.reads = reads
        self.calls: list[tuple[str, str, date, int]] = []

    def read_recent_observations(
        self,
        *,
        table: str,
        series_id: str,
        cutoff_date: date,
        limit: int = 2,
    ) -> HomeMacroSeriesRead:
        self.calls.append((table, series_id, cutoff_date, limit))
        return self.reads.get(
            series_id,
            HomeMacroSeriesRead(
                table=table,
                series_id=series_id,
                observations=[],
                error="relation_missing",
            ),
        )


def _observation(
    *,
    table: str,
    series_id: str,
    observation_date: date,
    value: float | None,
    cadence: str,
    unit: str,
    version_suffix: str,
    vendor_name: str | None = None,
) -> HomeMacroObservation:
    return HomeMacroObservation(
        table=table,
        series_id=series_id,
        observation_date=observation_date,
        value=value,
        cadence=cadence,
        unit=unit,
        source_version=f"sv-{version_suffix}",
        vendor_version=f"vv-{version_suffix}",
        rule_version=f"rv-{version_suffix}",
        vendor_name=vendor_name,
        ingest_batch_id=f"batch-{version_suffix}" if table == "std_external_macro_daily" else None,
        quality_flag="ok" if table == "fact_choice_macro_daily" else None,
        run_id=f"run-{version_suffix}" if table == "fact_choice_macro_daily" else None,
    )


def _series_read(
    *,
    table: str,
    series_id: str,
    current_date: date,
    current_value: float | None,
    previous_date: date | None,
    previous_value: float | None,
    cadence: str,
    unit: str,
    vendor_name: str | None,
    vendor_version_hint: str | None = None,
) -> HomeMacroSeriesRead:
    current = _observation(
        table=table,
        series_id=series_id,
        observation_date=current_date,
        value=current_value,
        cadence=cadence,
        unit=unit,
        version_suffix=vendor_version_hint or f"{series_id}-current",
        vendor_name=vendor_name,
    )
    observations = [current]
    if previous_date is not None:
        observations.append(
            _observation(
                table=table,
                series_id=series_id,
                observation_date=previous_date,
                value=previous_value,
                cadence=cadence,
                unit=unit,
                version_suffix=f"{series_id}-previous",
                vendor_name=vendor_name,
            )
        )
    return HomeMacroSeriesRead(table=table, series_id=series_id, observations=observations)


def _ready_reads() -> dict[str, HomeMacroSeriesRead]:
    return {
        "M0017126": _series_read(
            table="fact_choice_macro_daily",
            series_id="M0017126",
            current_date=date(2026, 6, 1),
            current_value=0.0,
            previous_date=date(2026, 5, 1),
            previous_value=0.0,
            cadence="monthly",
            unit="index",
            vendor_name=None,
            vendor_version_hint="backfill_macro_tushare_macro-current",
        ),
        "tushare.macro.cn_cpi.monthly": _series_read(
            table="std_external_macro_daily",
            series_id="tushare.macro.cn_cpi.monthly",
            current_date=date(2026, 6, 1),
            current_value=1.2,
            previous_date=date(2026, 5, 1),
            previous_value=1.2,
            cadence="monthly",
            unit="pct",
            vendor_name="tushare",
        ),
        "tushare.macro.cn_ppi.monthly": _series_read(
            table="std_external_macro_daily",
            series_id="tushare.macro.cn_ppi.monthly",
            current_date=date(2026, 6, 1),
            current_value=3.9,
            previous_date=date(2026, 5, 1),
            previous_value=2.8,
            cadence="monthly",
            unit="pct",
            vendor_name="tushare",
        ),
        "nbs.macro.cn_gdp.quarterly": _series_read(
            table="std_external_macro_daily",
            series_id="nbs.macro.cn_gdp.quarterly",
            current_date=date(2026, 6, 30),
            current_value=4.3,
            previous_date=date(2026, 3, 31),
            previous_value=5.0,
            cadence="quarterly",
            unit="pct",
            vendor_name="nbs",
        ),
        "tushare.macro.cn_gdp.quarterly": _series_read(
            table="std_external_macro_daily",
            series_id="tushare.macro.cn_gdp.quarterly",
            current_date=date(2026, 6, 30),
            current_value=5.0,
            previous_date=date(2026, 3, 31),
            previous_value=5.2,
            cadence="quarterly",
            unit="pct",
            vendor_name="tushare",
        ),
    }


def _build(
    reads: dict[str, HomeMacroSeriesRead],
    *,
    history_limit: int = 8,
    window_start_date: date = date(2026, 7, 16),
):
    repository = _FakeRepository(reads)
    envelope = HomeMacroReleaseContextService(
        repository=repository,
        bindings_path=BINDINGS_PATH,
    ).build_envelope(
        window_start_date=window_start_date,
        window_end_date=date(2026, 8, 30),
        history_limit=history_limit,
    )
    return envelope, repository


def _item(envelope, indicator_key: str):
    return next(item for item in envelope.result.history_items if item.indicator_key == indicator_key)


def test_service_builds_automatic_metrics_and_explicit_source_pending_groups() -> None:
    envelope, repository = _build(_ready_reads())

    assert len(repository.calls) == 5
    assert all(call[2] == date(2026, 7, 16) for call in repository.calls)
    pmi = _item(envelope, "cn_pmi")
    assert pmi.source_status == "ready"
    assert pmi.metrics[0].actual_value == 0.0
    assert pmi.metrics[0].previous_value == 0.0
    assert pmi.metrics[0].change_value == 0.0
    assert pmi.metrics[0].direction == "flat"
    assert any("Tushare" in note for note in pmi.notes)

    inflation = _item(envelope, "cn_inflation")
    assert [metric.change_value for metric in inflation.metrics] == [0.0, 1.1]
    assert [metric.change_unit for metric in inflation.metrics] == ["pct_point", "pct_point"]

    growth = _item(envelope, "cn_growth")
    assert growth.metrics[0].change_value == -0.7
    assert growth.metrics[0].direction == "down"

    pending_items = [item for item in envelope.result.history_items if item.region == "US"]
    assert len(pending_items) == 5
    assert all(item.source_status == "source_pending" for item in pending_items)
    assert all(
        metric.actual_value is None and metric.previous_value is None and metric.change_value is None
        for item in pending_items
        for metric in item.metrics
    )
    assert envelope.result.coverage.configured_count == 8
    assert envelope.result.coverage.ready_count == 3
    assert envelope.result.coverage.source_pending_count == 5


def test_monthly_freshness_uses_report_period_end_instead_of_first_day() -> None:
    envelope, _ = _build(
        _ready_reads(),
        window_start_date=date(2026, 7, 17),
    )

    assert _item(envelope, "cn_pmi").source_status == "ready"
    assert _item(envelope, "cn_inflation").source_status == "ready"


def test_service_uses_stable_traceable_meta_across_mixed_sources() -> None:
    first, _ = _build(_ready_reads())
    second, _ = _build(_ready_reads())

    assert first.result_meta.as_of_date == "2026-06-30"
    assert first.result_meta.date_basis == "macro_observation_period"
    assert first.result_meta.tables_used == [
        "fact_choice_macro_daily",
        "std_external_macro_daily",
    ]
    assert first.result_meta.evidence_rows == 8
    assert first.result_meta.rule_version == "rv_home_macro_release_context_v1"
    assert first.result_meta.cache_version == "cv_home_macro_release_context_v1"
    assert first.result_meta.source_version.startswith("sv_home_macro_release_context_")
    assert first.result_meta.vendor_version.startswith("vv_home_macro_release_context_")
    assert first.result_meta.source_version == second.result_meta.source_version
    assert first.result_meta.vendor_version == second.result_meta.vendor_version
    assert first.result_meta.formal_use_allowed is False
    assert first.result_meta.fallback_mode == "none"


def test_previous_null_makes_group_partial_without_losing_actual_value() -> None:
    reads = _ready_reads()
    reads["tushare.macro.cn_cpi.monthly"] = _series_read(
        table="std_external_macro_daily",
        series_id="tushare.macro.cn_cpi.monthly",
        current_date=date(2026, 6, 1),
        current_value=1.2,
        previous_date=date(2026, 5, 1),
        previous_value=None,
        cadence="monthly",
        unit="pct",
        vendor_name="tushare",
    )

    envelope, _ = _build(reads)
    inflation = _item(envelope, "cn_inflation")

    assert inflation.source_status == "partial"
    assert inflation.metrics[0].actual_value == 1.2
    assert inflation.metrics[0].previous_value is None
    assert inflation.metrics[0].change_value is None
    assert envelope.result.coverage.partial_count == 1


def test_unit_mismatch_fails_closed_without_misleading_values() -> None:
    reads = _ready_reads()
    reads["tushare.macro.cn_cpi.monthly"] = _series_read(
        table="std_external_macro_daily",
        series_id="tushare.macro.cn_cpi.monthly",
        current_date=date(2026, 6, 1),
        current_value=1.2,
        previous_date=date(2026, 5, 1),
        previous_value=1.0,
        cadence="monthly",
        unit="index",
        vendor_name="tushare",
    )

    envelope, _ = _build(reads)
    inflation = _item(envelope, "cn_inflation")
    invalid_metric = inflation.metrics[0]

    assert inflation.source_status == "error"
    assert invalid_metric.actual_value is None
    assert invalid_metric.previous_value is None
    assert invalid_metric.change_value is None
    assert any("unit" in note.lower() for note in inflation.notes)


def test_monthly_and_quarterly_old_observations_are_never_marked_ready() -> None:
    reads = _ready_reads()
    reads["M0017126"] = _series_read(
        table="fact_choice_macro_daily",
        series_id="M0017126",
        current_date=date(2026, 5, 31),
        current_value=50.3,
        previous_date=date(2026, 4, 30),
        previous_value=50.0,
        cadence="monthly",
        unit="index",
        vendor_name=None,
    )
    reads["nbs.macro.cn_gdp.quarterly"] = _series_read(
        table="std_external_macro_daily",
        series_id="nbs.macro.cn_gdp.quarterly",
        current_date=date(2026, 4, 6),
        current_value=5.0,
        previous_date=date(2026, 1, 6),
        previous_value=5.2,
        cadence="quarterly",
        unit="pct",
        vendor_name="nbs",
    )
    reads["tushare.macro.cn_gdp.quarterly"] = _series_read(
        table="std_external_macro_daily",
        series_id="tushare.macro.cn_gdp.quarterly",
        current_date=date(2026, 4, 6),
        current_value=5.0,
        previous_date=date(2026, 1, 6),
        previous_value=5.2,
        cadence="quarterly",
        unit="pct",
        vendor_name="tushare",
    )

    envelope, _ = _build(reads)

    assert _item(envelope, "cn_pmi").source_status == "stale"
    assert _item(envelope, "cn_growth").source_status == "stale"
    assert envelope.result.coverage.stale_count == 2
    assert envelope.result_meta.vendor_status == "vendor_stale"


def test_all_relations_missing_returns_explicit_errors_without_fake_as_of_date() -> None:
    envelope, _ = _build({})

    china_items = [item for item in envelope.result.history_items if item.region == "CN"]
    assert all(item.source_status == "error" for item in china_items)
    assert all(item.source_status == "source_pending" for item in envelope.result.history_items[3:])
    assert envelope.result.coverage.error_count == 3
    assert envelope.result.coverage.source_pending_count == 5
    assert envelope.result_meta.as_of_date is None
    assert envelope.result_meta.date_basis is None
    assert envelope.result_meta.evidence_rows == 0
    assert envelope.result_meta.tables_used == []
    assert envelope.result_meta.vendor_status == "vendor_unavailable"


def test_history_limit_does_not_hide_full_coverage_counts() -> None:
    envelope, _ = _build(_ready_reads(), history_limit=3)

    assert len(envelope.result.history_items) == 3
    assert envelope.result.coverage.configured_count == 8
    assert envelope.result.coverage.ready_count == 3
    assert envelope.result.coverage.source_pending_count == 5


def test_invalid_binding_file_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        '{"rule_version":"rv_home_macro_release_context_v1","groups":[],"history":[]}',
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        HomeMacroReleaseContextService(repository=_FakeRepository({}), bindings_path=path)
