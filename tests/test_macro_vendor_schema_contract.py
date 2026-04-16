from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.schemas.macro_vendor import (
    ChoiceMacroBatchConfig,
    ChoiceMacroCatalogAsset,
    ChoiceMacroCatalogBatchConfig,
    ChoiceMacroLatestPayload,
    ChoiceMacroLatestPoint,
    ChoiceMacroPoint,
    ChoiceMacroRecentPoint,
    ChoiceMacroSeriesConfig,
    ChoiceMacroSnapshot,
    FxAnalyticalGroup,
    FxAnalyticalPayload,
    FxAnalyticalSeriesPoint,
    FxFormalStatusPayload,
    FxFormalStatusRow,
    MacroVendorPayload,
    MacroVendorSeries,
)


def _minimal_series() -> ChoiceMacroSeriesConfig:
    return ChoiceMacroSeriesConfig(
        series_id="s1",
        series_name="S1",
        vendor_series_code="V1",
        frequency="daily",
        unit="pct",
    )


def test_choice_macro_series_config_defaults():
    s = _minimal_series()
    assert s.theme == "unknown"
    assert s.is_core is False
    assert s.tags == []


def test_choice_macro_batch_config_defaults():
    batch = ChoiceMacroBatchConfig(
        batch_id="b1",
        request_options="IsLatest=1",
        series=[_minimal_series()],
    )
    assert batch.fetch_mode == "date_slice"
    assert batch.fetch_granularity == "batch"
    assert batch.refresh_tier == "stable"


def test_choice_macro_catalog_batch_config_request_options_dict_and_extra_forbidden():
    batch = ChoiceMacroCatalogBatchConfig(
        batch_id="b1",
        request_options={"IsLatest": 1, "Flag": True},
        series=[_minimal_series()],
    )
    assert batch.request_options == {"IsLatest": 1, "Flag": True}

    with pytest.raises(ValidationError):
        ChoiceMacroCatalogBatchConfig(
            batch_id="b1",
            request_options="not-a-dict",  # type: ignore[arg-type]
            series=[_minimal_series()],
        )

    with pytest.raises(ValidationError):
        ChoiceMacroCatalogBatchConfig(
            batch_id="b1",
            request_options={},
            series=[_minimal_series()],
            unexpected_field=1,  # type: ignore[call-arg]
        )


def test_choice_macro_catalog_asset_nests_batches():
    asset = ChoiceMacroCatalogAsset(
        catalog_version="cv1",
        vendor_name="choice",
        generated_at=datetime(2026, 4, 11, 9, 0, tzinfo=timezone.utc),
        generated_from="test",
        batches=[
            ChoiceMacroCatalogBatchConfig(
                batch_id="b1",
                request_options={},
                series=[_minimal_series()],
            )
        ],
    )
    assert len(asset.batches) == 1
    assert asset.batches[0].batch_id == "b1"


def test_choice_macro_snapshot_accepts_datetime_and_raw_payload():
    captured = datetime(2026, 4, 9, 14, 0, tzinfo=timezone.utc)
    raw: dict[str, object] = {"k": 1, "nested": {"a": "b"}}
    snap = ChoiceMacroSnapshot(
        vendor_name="choice",
        vendor_version="vv1",
        captured_at=captured,
        series=[
            ChoiceMacroPoint(
                series_id="s1",
                series_name="S1",
                vendor_series_code="V1",
                vendor_name="choice",
                trade_date="2026-04-09",
                value_numeric=1.0,
                frequency="daily",
                unit="pct",
                vendor_version="vv1",
            )
        ],
        raw_payload=raw,
    )
    assert snap.captured_at is captured
    assert snap.raw_payload == raw


def test_macro_vendor_payload_default_read_target():
    payload = MacroVendorPayload(
        series=[
            MacroVendorSeries(
                series_id="s1",
                series_name="S1",
                vendor_name="choice",
                vendor_version="vv1",
                frequency="daily",
                unit="pct",
            )
        ],
    )
    assert payload.read_target == "duckdb"


def test_choice_macro_recent_point_default_quality_flag():
    p = ChoiceMacroRecentPoint(
        trade_date="2026-04-09",
        value_numeric=1.0,
        source_version="sv1",
        vendor_version="vv1",
    )
    assert p.quality_flag == "warning"


def test_choice_macro_latest_point_defaults():
    p = ChoiceMacroLatestPoint(
        series_id="s1",
        series_name="S1",
        trade_date="2026-04-09",
        value_numeric=1.0,
        frequency="daily",
        unit="pct",
        source_version="sv1",
        vendor_version="vv1",
    )
    assert p.quality_flag == "warning"
    assert p.recent_points == []


def test_choice_macro_latest_payload_default_read_target():
    payload = ChoiceMacroLatestPayload(
        series=[
            ChoiceMacroLatestPoint(
                series_id="s1",
                series_name="S1",
                trade_date="2026-04-09",
                value_numeric=1.0,
                frequency="daily",
                unit="pct",
                source_version="sv1",
                vendor_version="vv1",
            )
        ],
    )
    assert payload.read_target == "duckdb"


def test_fx_formal_status_payload_defaults():
    p = FxFormalStatusPayload(
        candidate_count=2,
        materialized_count=1,
        rows=[],
    )
    assert p.read_target == "duckdb"
    assert p.vendor_priority == ["choice", "akshare", "fail_closed"]
    assert p.carry_forward_count == 0


def test_fx_analytical_payload_default_read_target():
    payload = FxAnalyticalPayload(
        groups=[
            FxAnalyticalGroup(
                group_key="middle_rate",
                title="t",
                description="d",
                series=[
                    FxAnalyticalSeriesPoint(
                        group_key="middle_rate",
                        series_id="s1",
                        series_name="S1",
                        trade_date="2026-04-09",
                        value_numeric=1.0,
                        frequency="daily",
                        unit="pct",
                        source_version="sv1",
                        vendor_version="vv1",
                    )
                ],
            )
        ],
    )
    assert payload.read_target == "duckdb"


def test_literal_quality_flag_rejected_when_invalid():
    with pytest.raises(ValidationError):
        ChoiceMacroRecentPoint(
            trade_date="2026-04-09",
            value_numeric=1.0,
            source_version="sv1",
            vendor_version="vv1",
            quality_flag="nope",  # type: ignore[arg-type]
        )


def test_macro_vendor_payload_extra_forbidden():
    with pytest.raises(ValidationError):
        MacroVendorPayload(
            read_target="duckdb",
            series=[],
            extra_key=1,  # type: ignore[call-arg]
        )


def test_fx_formal_status_row_status_literal_rejected_when_invalid():
    with pytest.raises(ValidationError):
        FxFormalStatusRow(
            base_currency="USD",
            quote_currency="CNY",
            pair_label="USD/CNY",
            series_id="s1",
            series_name="S1",
            vendor_series_code="V1",
            status="maybe",  # type: ignore[arg-type]
        )
