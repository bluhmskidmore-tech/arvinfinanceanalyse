from __future__ import annotations

from datetime import date

import pytest

from backend.app.services import macro_toolkit_route_support

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_macro_toolkit,
]


def _evidence_item(
    latest_date: object,
    *,
    report_date: date = date(2026, 8, 21),
    cadence: str = "monthly",
) -> dict[str, object]:
    alias = "monthly.test.series"
    return macro_toolkit_route_support._capability_input_evidence_item(
        {
            "field": "pmi" if cadence == "monthly" else "policy_rate_7d",
            "label": "测试序列",
            "aliases": (alias,),
            "warning": "TEST_SERIES_MISSING",
            "required": True,
            "cadence": cadence,
        },
        duckdb_path="unused.duckdb",
        report_date=report_date,
        wide_rows=[],
        source_check_cache={
            alias: {
                "alias": alias,
                "row_count": 1,
                "latest": {
                    "date": latest_date,
                    "series_id": alias,
                    "vendor_name": "test",
                    "value": 50.0,
                },
            }
        },
    )


def test_monthly_period_start_uses_period_end_for_freshness_only() -> None:
    item = _evidence_item("2026-07-01")

    assert item["latest_date"] == "2026-07-01"
    assert item["freshness_reference_date"] == "2026-07-31"
    assert item["freshness_basis"] == "observation_period_end"
    assert item["freshness_tier"] == "fresh"
    assert item["stale"] is False
    assert item["stale_days"] is None


@pytest.mark.parametrize(
    ("latest_date", "expected_tier"),
    [
        ("2026-06-01", "stale"),
        ("2026-04-01", "expired"),
    ],
)
def test_old_monthly_periods_remain_stale_or_expired(
    latest_date: str,
    expected_tier: str,
) -> None:
    item = _evidence_item(latest_date)

    assert item["latest_date"] == latest_date
    assert item["freshness_tier"] == expected_tier
    assert item["stale"] is True
    assert item["stale_days"] is not None


def test_daily_freshness_behavior_and_payload_are_unchanged() -> None:
    item = _evidence_item("2026-08-10", cadence="daily")

    assert item["latest_date"] == "2026-08-10"
    assert item["freshness_tier"] == "stale"
    assert item["stale_days"] == 11
    assert "freshness_reference_date" not in item
    assert "freshness_basis" not in item


def test_monthly_non_period_start_keeps_actual_observation_date() -> None:
    item = _evidence_item("2026-08-20")

    assert item["latest_date"] == "2026-08-20"
    assert item["freshness_reference_date"] == "2026-08-20"
    assert item["freshness_basis"] == "observation_date"
    assert item["freshness_tier"] == "fresh"
    assert item["stale"] is False


def test_unparseable_monthly_date_stays_unknown() -> None:
    item = _evidence_item("not-a-date")

    assert item["latest_date"] == "not-a-date"
    assert item["freshness_reference_date"] is None
    assert item["freshness_basis"] == "unknown"
    assert item["freshness_tier"] == "unknown"
    assert item["stale"] is False
    assert item["stale_days"] is None


def test_future_month_keeps_observation_date_as_lookahead_anchor() -> None:
    item = _evidence_item("2026-09-01")

    assert item["latest_date"] == "2026-09-01"
    assert item["freshness_reference_date"] == "2026-09-01"
    assert item["freshness_basis"] == "observation_date"
    assert item["freshness_tier"] == "fresh"
    assert item["stale"] is False

    assessment = macro_toolkit_route_support.assess_freshness(
        item["freshness_reference_date"],
        date(2026, 8, 21),
        cadence="monthly",
    )
    assert assessment.lookahead is True
    assert assessment.age_days == -11
