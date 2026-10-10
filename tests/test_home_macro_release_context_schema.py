from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from backend.app.schemas.home_macro_release_context import (
    HomeMacroCoverage,
    HomeMacroHistoryItem,
    HomeMacroMetric,
    HomeMacroReleaseContextEnvelope,
    HomeMacroReleaseContextMeta,
    HomeMacroReleaseContextResult,
)


def _metric(**overrides: object) -> HomeMacroMetric:
    payload: dict[str, object] = {
        "metric_key": "manufacturing_pmi",
        "label": "制造业 PMI",
        "actual_value": 0.0,
        "previous_value": None,
        "change_value": 0.0,
        "display_unit": "index",
        "change_unit": "index_point",
        "precision": 1,
        "direction": "flat",
    }
    payload.update(overrides)
    return HomeMacroMetric.model_validate(payload)


def _item(**overrides: object) -> HomeMacroHistoryItem:
    payload: dict[str, object] = {
        "indicator_key": "cn_pmi",
        "title": "中国 PMI",
        "region": "CN",
        "category": "activity",
        "importance": "high",
        "observation_date": date(2026, 6, 1),
        "previous_observation_date": date(2026, 5, 1),
        "reference_period": "2026-06",
        "previous_reference_period": "2026-05",
        "release_date": None,
        "source_status": "partial",
        "source_name": "National Bureau of Statistics of China",
        "metrics": [_metric()],
        "notes": [],
    }
    payload.update(overrides)
    return HomeMacroHistoryItem.model_validate(payload)


def _meta() -> HomeMacroReleaseContextMeta:
    return HomeMacroReleaseContextMeta(
        source_version="sv_home_macro_release_context_test",
        vendor_version="vv_home_macro_release_context_test",
        rule_version="rv_home_macro_release_context_v1",
        cache_version="cv_home_macro_release_context_v1",
        as_of_date="2026-06-01",
        date_basis="macro_observation_period",
    )


def test_schema_preserves_zero_null_and_compound_metrics() -> None:
    item = _item(
        metrics=[
            _metric(),
            _metric(
                metric_key="ppi_yoy",
                label="PPI YoY",
                actual_value=None,
                previous_value=2.8,
                change_value=None,
                display_unit="pct",
                change_unit="pct_point",
                direction="unavailable",
            ),
        ]
    )

    assert item.metrics[0].actual_value == 0.0
    assert item.metrics[0].change_value == 0.0
    assert item.metrics[0].previous_value is None
    assert item.metrics[1].actual_value is None
    assert len(item.metrics) == 2


def test_release_date_stays_null_when_observation_date_exists() -> None:
    item = _item(release_date=None, observation_date=date(2026, 6, 1))

    assert item.observation_date == date(2026, 6, 1)
    assert item.release_date is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("display_unit", "%"),
        ("change_unit", "percent"),
        ("direction", "sideways"),
    ],
)
def test_metric_rejects_unknown_contract_literals(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        _metric(**{field: value})


def test_history_item_rejects_unknown_status_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _item(source_status="empty")

    payload = _item().model_dump()
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        HomeMacroHistoryItem.model_validate(payload)


def test_envelope_is_strictly_result_meta_plus_result() -> None:
    result = HomeMacroReleaseContextResult(
        window_start_date=date(2026, 7, 16),
        window_end_date=date(2026, 8, 30),
        history_items=[_item()],
        coverage=HomeMacroCoverage(
            configured_count=8,
            ready_count=0,
            partial_count=1,
            stale_count=0,
            fallback_count=0,
            source_pending_count=5,
            error_count=2,
        ),
        warnings=[],
    )
    envelope = HomeMacroReleaseContextEnvelope(result_meta=_meta(), result=result)

    dumped = envelope.model_dump(mode="json")
    assert set(dumped) == {"result_meta", "result"}
    assert dumped["result"]["history_items"][0]["release_date"] is None

    with pytest.raises(ValidationError):
        HomeMacroReleaseContextEnvelope.model_validate({**dumped, "calibration": {}})


def test_result_meta_rejects_wrong_home_contract_or_extra_fields() -> None:
    payload = _meta().model_dump()
    payload["basis"] = "formal"
    with pytest.raises(ValidationError):
        HomeMacroReleaseContextMeta.model_validate(payload)

    payload = _meta().model_dump()
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        HomeMacroReleaseContextMeta.model_validate(payload)
