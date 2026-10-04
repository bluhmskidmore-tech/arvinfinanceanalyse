"""TPL monthly flows and market moves must cover the same calendar window."""
from __future__ import annotations

import importlib
from decimal import Decimal
from typing import Any

import pytest

from backend.app.core_finance.pnl_attribution.workbench import (
    build_tpl_market_correlation,
    tpl_monthly_treasury_change_bp,
)


def _point(period: str, change: object | None, amount: object = Decimal("10")) -> dict[str, Any]:
    return {
        "period": period,
        "tpl_fair_value_change": amount,
        "treasury_10y": Decimal("2"),
        "treasury_10y_change": change,
    }


@pytest.mark.parametrize(
    ("periods", "changes", "expected"),
    [
        (["2026-01"], ["2.26"], "2.26"),
        (["2026-01", "2026-02", "2026-03"], ["2.26", "-1", "-7.22"], "-5.96"),
        (["2025-12", "2026-01", "2026-02"], ["-3", "1.25", "4.5"], "2.75"),
        (
            [f"2025-{month:02d}" for month in range(9, 13)]
            + [f"2026-{month:02d}" for month in range(1, 9)],
            ["2.26"] + ["-1"] * 10 + ["-7.22"],
            "-14.96",
        ),
    ],
)
def test_total_treasury_change_includes_every_month_and_preserves_bp(
    periods: list[str], changes: list[str], expected: str
) -> None:
    points = [_point(period, Decimal(change)) for period, change in zip(periods, changes, strict=True)]
    payload = build_tpl_market_correlation(
        monthly_points=points, start_period=periods[0], end_period=periods[-1]
    )

    assert payload["treasury_10y_total_change_bp"] == float(Decimal(expected))
    assert payload["total_tpl_fv_change"] == len(periods) * 10


@pytest.mark.parametrize("missing_index", [0, 1, 2])
@pytest.mark.parametrize("missing_value", [None, float("nan"), float("inf")])
def test_incomplete_market_window_never_sums_only_available_changes(
    missing_index: int, missing_value: object
) -> None:
    points = [_point(f"2026-{month:02d}", Decimal(month)) for month in range(1, 4)]
    points[missing_index]["treasury_10y_change"] = missing_value
    payload = build_tpl_market_correlation(
        monthly_points=points, start_period="2026-01", end_period="2026-03"
    )

    assert payload["treasury_10y_total_change_bp"] is None
    assert payload["total_tpl_fv_change"] == 30


@pytest.mark.parametrize("periods", [["2026-01", "2026-03"], ["2026-01", "2026-01", "2026-03"]])
def test_missing_or_duplicate_calendar_month_nulls_both_cumulative_values(periods: list[str]) -> None:
    payload = build_tpl_market_correlation(
        monthly_points=[_point(period, Decimal("1")) for period in periods],
        start_period="2026-01",
        end_period="2026-03",
    )

    assert payload["treasury_10y_total_change_bp"] is None
    assert payload["total_tpl_fv_change"] is None


def test_missing_fv_is_not_silently_omitted_from_total() -> None:
    payload = build_tpl_market_correlation(
        monthly_points=[_point("2026-01", 1, None), _point("2026-02", 2, 10)],
        start_period="2026-01",
        end_period="2026-02",
    )

    assert payload["total_tpl_fv_change"] is None
    assert payload["treasury_10y_total_change_bp"] == 3
    assert payload["correlation_coefficient"] is None


def test_cumulative_fix_does_not_change_pearson_pairs() -> None:
    changes = [Decimal("2.26"), Decimal("-1"), Decimal("-7.22")]
    payload = build_tpl_market_correlation(
        monthly_points=[
            _point(f"2026-{index:02d}", change, -change * 100)
            for index, change in enumerate(changes, 1)
        ],
        start_period="2026-01",
        end_period="2026-03",
    )

    assert payload["correlation_coefficient"] == -1
    assert payload["treasury_10y_total_change_bp"] == -5.96


def test_monthly_delta_keeps_decimal_precision_until_float_boundary() -> None:
    assert tpl_monthly_treasury_change_bp(Decimal("2.0226"), Decimal("2.0000")) == 2.26
    assert tpl_monthly_treasury_change_bp("0", "0") == 0
    assert tpl_monthly_treasury_change_bp("2.0226", None) is None
    assert tpl_monthly_treasury_change_bp(float("nan"), "2") is None


class _PnlRepo:
    def __init__(self, amounts: dict[str, Decimal]):
        self.amounts = amounts
        self.batch_calls: list[list[str]] = []

    def list_formal_fi_report_dates(self) -> list[str]:
        return sorted(self.amounts, reverse=True)

    def fetch_formal_fi_rows(self, report_date: str) -> list[dict[str, Any]]:
        return [{
            "accounting_basis": "FVTPL",
            "fair_value_change_516": self.amounts[report_date],
            "total_pnl": self.amounts[report_date],
        }]

    def fetch_tpl_pnl_summary_by_report_date(self, report_dates: list[str]) -> dict[str, dict[str, Any]]:
        self.batch_calls.append(report_dates)
        return {
            day: {"tpl_fair_value_change": self.amounts[day], "tpl_total_pnl": self.amounts[day]}
            for day in report_dates
        }


class _CurveRepo:
    path = "tpl-window-fixture.duckdb"

    def __init__(self, levels: dict[str, object]):
        self.levels = levels
        self.batch_calls: list[list[str]] = []

    def fetch_tenor_on_or_before_many(
        self, *, curve_type: str, tenor: str, trade_dates: list[str]
    ) -> dict[str, tuple[object | None, str | None]]:
        assert (curve_type, tenor) == ("treasury", "10Y")
        self.batch_calls.append(trade_dates)
        observations: dict[str, tuple[object | None, str | None]] = {}
        for day in trade_dates:
            resolved = max((candidate for candidate in self.levels if candidate <= day), default=None)
            observations[day] = (self.levels[resolved], resolved) if resolved else (None, None)
        return observations


class _BondRepo:
    def list_report_dates(self) -> list[str]:
        return []


class _MacroRepo:
    def dr007_on_or_before(self, trade_date: str) -> tuple[float, str]:
        return 1.5, trade_date

    def dr007_on_or_before_many(self, trade_dates: list[str]) -> dict[str, tuple[float, str]]:
        return {day: (1.5, day) for day in trade_dates}


@pytest.fixture
def service_fixture(monkeypatch: pytest.MonkeyPatch):
    def configure(amounts: dict[str, Decimal], levels: dict[str, object]):
        service = importlib.import_module("backend.app.services.pnl_attribution_service")
        pnl = _PnlRepo(amounts)
        curve = _CurveRepo(levels)
        monkeypatch.setattr(service, "_pnl_repo", lambda: pnl)
        monkeypatch.setattr(service, "_curve_repo", lambda: curve)
        monkeypatch.setattr(service, "_bond_repo", _BondRepo)
        monkeypatch.setattr(service, "_choice_macro_repo", lambda _path=None: _MacroRepo())
        return service, pnl, curve

    return configure


def test_first_baseline_does_not_require_prior_fi_snapshot(service_fixture) -> None:
    service, _, curve = service_fixture(
        {"2026-01-31": Decimal("10"), "2026-02-28": Decimal("20")},
        {"2025-12-30": "2", "2026-01-30": "2.0226", "2026-02-27": "2.0126"},
    )
    envelope = service._tpl_market_correlation_envelope_uncached(months=2, report_date="2026-02-28")
    payload = envelope["result"]

    assert payload["treasury_10y_total_change_bp"]["raw"] == 1.26
    assert payload["treasury_10y_total_change_bp"]["unit"] == "bp"
    assert payload["data_points"][0]["treasury_10y_change"]["raw"] == 2.26
    assert payload["data_points"][0]["treasury_10y"]["raw"] == pytest.approx(0.020226)
    assert payload["total_tpl_fv_change"]["raw_text"] == "30"
    assert envelope["result_meta"]["quality_flag"] == "ok"
    assert "2025-12-31" in curve.batch_calls[0]


def test_single_month_total_is_its_first_month_move(service_fixture) -> None:
    service, _, _ = service_fixture(
        {"2026-01-31": Decimal("10")}, {"2025-12-31": "2", "2026-01-31": "2.0226"}
    )
    payload = service._tpl_market_correlation_envelope_uncached(months=1, report_date="2026-01-31")["result"]

    assert payload["treasury_10y_total_change_bp"]["raw"] == 2.26
    assert payload["correlation_coefficient"] is None


def test_missing_first_baseline_nulls_market_total_and_warns(service_fixture) -> None:
    service, _, _ = service_fixture(
        {"2026-01-31": Decimal("10"), "2026-02-28": Decimal("20")},
        {"2026-01-31": "2.0226", "2026-02-28": "2.0126"},
    )
    envelope = service._tpl_market_correlation_envelope_uncached(months=2, report_date="2026-02-28")
    payload = envelope["result"]

    assert payload["data_points"][0]["treasury_10y_change"] is None
    assert payload["data_points"][1]["treasury_10y_change"]["raw"] == -1
    assert payload["treasury_10y_total_change_bp"] is None
    assert payload["total_tpl_fv_change"]["raw"] == 30
    assert service.TPL_WINDOW_WARN in payload["warnings"]
    assert envelope["result_meta"]["quality_flag"] == "warning"


def test_missing_fi_month_keeps_window_and_does_not_create_cross_month_pair(service_fixture) -> None:
    service, pnl, _ = service_fixture(
        {"2025-12-31": Decimal("500"), "2026-01-31": Decimal("10"), "2026-03-31": Decimal("30")},
        {"2025-12-31": "2", "2026-01-31": "2.02", "2026-02-28": "2.04", "2026-03-31": "2.07"},
    )
    envelope = service._tpl_market_correlation_envelope_uncached(months=3, report_date="2026-03-31")
    payload = envelope["result"]
    summary, meta = service._tpl_market_summary_components(
        dates=pnl.list_formal_fi_report_dates(), report_date="2026-03-31", months=3
    )

    assert (payload["start_period"], payload["end_period"]) == ("2026-01", "2026-03")
    assert [point["period"] for point in payload["data_points"]] == ["2026-01", "2026-03"]
    assert payload["data_points"][1]["treasury_10y_change"]["raw"] == 3
    assert payload["total_tpl_fv_change"]["raw"] is None
    assert "raw_text" not in payload["total_tpl_fv_change"]
    assert payload["treasury_10y_total_change_bp"] is None
    assert service.TPL_WINDOW_WARN in payload["warnings"]
    assert summary["data_points"][1]["treasury_10y_change"] == 3
    assert summary["total_tpl_fv_change"] is None
    assert summary["treasury_10y_total_change_bp"] is None
    assert meta["warning"] is True


def test_missing_curve_month_is_not_forward_filled_into_correlation(service_fixture) -> None:
    service, pnl, curve = service_fixture(
        {f"2026-{month:02d}-{day}": Decimal(month * 10) for month, day in [(1, 31), (2, 28), (3, 31), (4, 30)]},
        {"2025-12-31": "2", "2026-01-31": "2.02", "2026-03-31": "2.09", "2026-04-30": "2.12"},
    )
    envelope = service._tpl_market_correlation_envelope_uncached(months=4, report_date="2026-04-30")
    payload = envelope["result"]
    summary, meta = service._tpl_market_summary_components(
        dates=pnl.list_formal_fi_report_dates(), report_date="2026-04-30", months=4
    )

    assert payload["data_points"][1]["treasury_10y"] is None
    assert payload["data_points"][1]["treasury_10y_change"] is None
    assert payload["data_points"][2]["treasury_10y_change"] is None
    assert payload["data_points"][3]["treasury_10y_change"]["raw"] == 3
    assert payload["treasury_10y_total_change_bp"] is None
    assert payload["correlation_coefficient"]["raw"] == 1
    assert summary["correlation_coefficient"] == payload["correlation_coefficient"]["raw"]
    assert summary["treasury_10y_total_change_bp"] is None
    assert meta["warning"] is True
    assert len(pnl.batch_calls) == 1
    assert len(curve.batch_calls) == 2


def test_requested_report_date_does_not_read_later_snapshot_in_same_month(service_fixture) -> None:
    service, _, _ = service_fixture(
        {"2026-03-15": Decimal("10"), "2026-03-31": Decimal("90")},
        {"2026-02-28": "2", "2026-03-15": "2.01", "2026-03-31": "2.09"},
    )
    payload = service._tpl_market_correlation_envelope_uncached(months=1, report_date="2026-03-15")["result"]

    assert payload["total_tpl_fv_change"]["raw"] == 10
    assert payload["treasury_10y_total_change_bp"]["raw"] == 1


def test_no_fi_data_keeps_null_numeric_instead_of_zero_total(service_fixture) -> None:
    service, _, _ = service_fixture({}, {})
    payload = service._tpl_market_correlation_envelope_uncached(months=12, report_date=None)["result"]

    assert payload["total_tpl_fv_change"]["raw"] is None
    assert payload["total_tpl_fv_change"]["unit"] == "yuan"
    assert payload["treasury_10y_total_change_bp"] is None
