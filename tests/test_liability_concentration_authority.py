from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.core_finance.liability_analytics_compat import (
    compute_liabilities_monthly,
    compute_liability_counterparty,
)
from backend.app.schemas.liability_analytics import (
    LiabilityCounterpartyPayload,
    LiabilityMonthlyItem,
)
from backend.app.services import liability_analytics_service as service
from tests.test_liability_analytics_api import _build_client

GOLDEN_BALANCES = [40, 20, 10, 10, 5, 5, 3, 2, 2, 1, 1, 1]


def _counterparty_rows(*, report_date: str | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, balance in enumerate(GOLDEN_BALANCES, start=1):
        row: dict[str, object] = {
            "is_asset_side": False,
            "counterparty_name": f"Counterparty {index:02d}",
            "principal_native": balance,
            "funding_cost_rate": "2.0",
            "position_id": f"P{index:02d}",
        }
        if report_date is not None:
            row["report_date"] = report_date
        rows.append(row)
    return rows


def test_daily_concentration_uses_full_population_when_rows_are_truncated() -> None:
    payload = compute_liability_counterparty(
        "2026-01-31",
        _counterparty_rows(),
        top_n=3,
    )

    assert len(payload["top_10"]) == 3
    assert payload["population_count"] == 12
    assert payload["top10_share"] == pytest.approx(0.98)
    assert payload["hhi"] == pytest.approx(2270.0)
    assert payload["is_truncated"] is True


def test_daily_concentration_reports_untruncated_full_population() -> None:
    payload = compute_liability_counterparty(
        "2026-01-31",
        _counterparty_rows(),
        top_n=20,
    )

    assert len(payload["top_10"]) == 12
    assert payload["population_count"] == 12
    assert payload["top10_share"] == pytest.approx(0.98)
    assert payload["hhi"] == pytest.approx(2270.0)
    assert payload["is_truncated"] is False


def test_daily_concentration_keeps_empty_metrics_null() -> None:
    payload = compute_liability_counterparty("2026-01-31", [], top_n=10)

    assert payload["top10_share"] is None
    assert payload["hhi"] is None
    assert payload["population_count"] == 0
    assert payload["is_truncated"] is False


def test_monthly_concentration_uses_full_population_but_exposes_fixed_top10() -> None:
    payload = compute_liabilities_monthly(
        2026,
        zqtz_rows=[],
        tyw_rows=_counterparty_rows(report_date="2026-01-31"),
    )

    month = payload["months"][0]
    assert len(month["counterparty_top10"]) == 10
    assert len(month["counterparty_details"]) == 12
    assert month["population_count"] == 12
    assert month["top10_share"] == pytest.approx(0.98)
    assert month["hhi"] == pytest.approx(2270.0)
    assert month["is_truncated"] is True


def test_monthly_issued_only_liabilities_keep_concentration_unknown() -> None:
    payload = compute_liabilities_monthly(
        2026,
        zqtz_rows=[
            {
                "report_date": "2026-01-31",
                "is_issuance_like": True,
                "amortized_cost_native": 100,
                "bond_type": "Issued",
                "coupon_rate": "2.0",
                "maturity_date": "2027-01-31",
            }
        ],
        tyw_rows=[],
    )

    month = payload["months"][0]
    assert month["counterparty_top10"] == []
    assert month["counterparty_details"] == []
    assert month["top10_share"] is None
    assert month["hhi"] is None
    assert month["population_count"] == 0
    assert month["is_truncated"] is False


def test_counterparty_schema_promotes_authoritative_concentration_units() -> None:
    payload = LiabilityCounterpartyPayload(
        report_date="2026-01-31",
        total_value=100,
        top10_share=0.98,
        hhi=2270,
        population_count=12,
        is_truncated=True,
        top_10=[],
        by_type=[],
    )

    assert payload.top10_share is not None
    assert payload.top10_share.unit == "pct"
    assert payload.top10_share.raw == pytest.approx(0.98)
    assert payload.hhi is not None
    assert payload.hhi.unit == "count"
    assert payload.hhi.raw == pytest.approx(2270)
    assert payload.population_count == 12
    assert payload.is_truncated is True


def test_monthly_schema_promotes_authoritative_concentration_units() -> None:
    month = LiabilityMonthlyItem(
        month="2026-01",
        month_label="2026-01",
        top10_share=0.98,
        hhi=2270,
        population_count=12,
        is_truncated=True,
        num_days=1,
    )

    assert month.top10_share is not None
    assert month.top10_share.unit == "pct"
    assert month.top10_share.raw == pytest.approx(0.98)
    assert month.hhi is not None
    assert month.hhi.unit == "count"
    assert month.hhi.raw == pytest.approx(2270)


def test_service_no_report_date_returns_explicit_null_concentration(monkeypatch) -> None:
    class EmptyRepo:
        def __init__(self, _duckdb_path: str) -> None:
            pass

        def resolve_latest_report_date(self) -> None:
            return None

    monkeypatch.setattr(service, "LiabilityAnalyticsRepository", EmptyRepo)

    envelope = service.liability_counterparty_payload(
        duckdb_path="unused.duckdb",
        report_date=None,
        top_n=10,
    )

    assert envelope["result"]["top10_share"] is None
    assert envelope["result"]["hhi"] is None
    assert envelope["result"]["population_count"] == 0
    assert envelope["result"]["is_truncated"] is False


def test_empty_counterparty_api_returns_null_concentration(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _build_client(tmp_path, monkeypatch)

    response = client.get(
        "/api/analysis/liabilities/counterparty",
        params={"report_date": "2026-01-31", "top_n": "10"},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["top10_share"] is None
    assert result["hhi"] is None
    assert result["population_count"] == 0
    assert result["is_truncated"] is False


def test_counterparty_population_count_must_be_nonnegative() -> None:
    with pytest.raises(ValueError):
        LiabilityCounterpartyPayload(
            report_date="2026-01-31",
            total_value=0,
            top10_share=None,
            hhi=None,
            population_count=-1,
            is_truncated=False,
            top_10=[],
            by_type=[],
        )


def test_monthly_population_count_must_be_nonnegative() -> None:
    with pytest.raises(ValueError):
        LiabilityMonthlyItem(
            month="2026-01",
            month_label="2026-01",
            top10_share=None,
            hhi=None,
            population_count=-1,
            is_truncated=False,
            num_days=1,
        )
