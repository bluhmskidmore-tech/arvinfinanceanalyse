from __future__ import annotations

from decimal import Decimal
from datetime import date
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest

from backend.app.repositories.yield_curve_repo import (
    FORMAL_FACT_TABLE,
    YieldCurveRepository,
    ensure_yield_curve_tables,
)
from backend.app.services import campisi_attribution_service as campisi_svc
from backend.app.services.campisi_attribution_service import (
    _add_market_curve_quality,
    _decision_residual_ratio,
    _build_formal_closure,
    _build_input_quality,
    _fetch_spread_data,
    _merge_positions,
)


def _bond_row(
    *,
    code: str,
    portfolio: str = "FIOA",
    cost_center: str = "5010",
    accounting_class: str = "FVOCI",
    currency: str = "CNY",
    market_value: Decimal = Decimal("0"),
    face_value: Decimal = Decimal("0"),
    accrued_interest: Decimal = Decimal("0"),
    coupon_rate: Decimal | None = Decimal("0.0300"),
    ytm: Decimal | None = Decimal("0.0320"),
    maturity_date: str | None = "2030-12-31",
    asset_class: str = "credit",
    rating: str | None = "AAA",
) -> dict[str, object]:
    return {
        "instrument_code": code,
        "portfolio_name": portfolio,
        "cost_center": cost_center,
        "accounting_class": accounting_class,
        "currency_code": currency,
        "market_value": market_value,
        "face_value": face_value,
        "accrued_interest": accrued_interest,
        "coupon_rate": coupon_rate,
        "ytm": ytm,
        "maturity_date": maturity_date,
        "asset_class_std": asset_class,
        "rating": rating,
    }


class _FakeBondAnalyticsRepository:
    def __init__(
        self,
        dates: list[str],
        rows_by_date: dict[str, list[dict[str, object]]],
    ) -> None:
        self._dates = dates
        self._rows_by_date = rows_by_date

    def list_report_dates(self) -> list[str]:
        return list(self._dates)

    def fetch_bond_analytics_rows(self, *, report_date: str, **_kwargs: Any) -> list[dict[str, object]]:
        return list(self._rows_by_date.get(report_date, []))


class _FakeYieldCurveRepository:
    path = "missing-choice-campisi.duckdb"

    def __init__(self, curves: dict[tuple[str, str], dict[str, object]]) -> None:
        self._curves = curves

    def fetch_curve(self, trade_date: str, curve_type: str) -> dict[str, object]:
        return dict(self._curves.get((trade_date, curve_type), {}))

    def fetch_latest_trade_date_on_or_before(self, _curve_type: str, _trade_date: str) -> str | None:
        return None


def _install_full_service_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dates: list[str],
    rows_by_date: dict[str, list[dict[str, object]]],
    curves: dict[tuple[str, str], dict[str, object]],
    closure_status: str = "closed",
    duckdb_path: str = "unused.duckdb",
) -> None:
    monkeypatch.setattr(
        campisi_svc,
        "BondAnalyticsRepository",
        lambda _path: _FakeBondAnalyticsRepository(dates, rows_by_date),
    )
    monkeypatch.setattr(
        campisi_svc,
        "YieldCurveRepository",
        lambda _path: _FakeYieldCurveRepository(curves),
    )
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=duckdb_path, governance_path="unused-governance"),
    )

    def fake_formal_closure(*, report_date: str, campisi_total_return: Decimal, **_kwargs: Any) -> dict[str, object]:
        residual = Decimal("0") if closure_status == "closed" else Decimal("10")
        return {
            "basis": "pnl.bridge.total_actual_pnl",
            "report_date": report_date,
            "status": closure_status,
            "campisi_total_return": float(campisi_total_return),
            "formal_actual_pnl": float(campisi_total_return + residual),
            "residual_to_formal_pnl": float(residual),
            "residual_ratio": 0.0 if closure_status == "closed" else 1.0,
            "bridge_quality_flag": "ok",
            "bridge_vendor_status": "ok",
            "bridge_fallback_mode": "none",
            "message": (
                "Campisi total return closes to formal PnL."
                if closure_status == "closed"
                else "Campisi total return does not close to formal PnL; residual_to_formal_pnl is required."
            ),
        }

    monkeypatch.setattr(campisi_svc, "_fetch_formal_closure", fake_formal_closure)


def _clear_four_effects_cache() -> None:
    campisi_svc.clear_campisi_four_effects_runtime_cache()


def _flat_treasury(rate: Decimal) -> dict[str, object]:
    return {
        "1Y": rate,
        "3Y": rate,
        "5Y": rate,
        "7Y": rate,
        "10Y": rate,
        "30Y": rate,
    }


def test_merge_positions_keeps_same_bond_in_different_business_positions():
    rows_start = [
        _bond_row(code="BOND1", cost_center="5010", market_value=Decimal("100"), face_value=Decimal("100")),
        _bond_row(code="BOND1", cost_center="5020", market_value=Decimal("200"), face_value=Decimal("200")),
    ]
    rows_end = [
        _bond_row(code="BOND1", cost_center="5010", market_value=Decimal("110"), face_value=Decimal("100")),
        _bond_row(code="BOND1", cost_center="5020", market_value=Decimal("220"), face_value=Decimal("200")),
    ]

    positions = _merge_positions(rows_start, rows_end)

    assert len(positions) == 2
    assert sum(Decimal(str(row["market_value_start"])) for row in positions) == Decimal("300")
    assert sum(Decimal(str(row["market_value_end"])) for row in positions) == Decimal("330")


def test_merge_positions_keeps_credit_rating_for_spread_bucket_selection():
    positions = _merge_positions(
        rows_start=[
            _bond_row(
                code="BOND1",
                asset_class="other",
                rating="AA+",
                market_value=Decimal("100"),
                face_value=Decimal("100"),
            )
        ],
        rows_end=[
            _bond_row(
                code="BOND1",
                asset_class="credit",
                rating="AA+",
                market_value=Decimal("100"),
                face_value=Decimal("100"),
            )
        ],
    )

    assert positions[0]["asset_class_start"] == "credit AA+"


def test_merge_positions_aggregates_same_position_key_and_reports_input_quality():
    rows_start = [
        _bond_row(
            code="BOND2",
            market_value=Decimal("100"),
            face_value=Decimal("80"),
            accrued_interest=Decimal("1.5"),
            coupon_rate=Decimal("0.0300"),
            ytm=None,
        ),
        _bond_row(
            code="BOND2",
            market_value=Decimal("300"),
            face_value=Decimal("120"),
            accrued_interest=Decimal("2.5"),
            coupon_rate=Decimal("0.0500"),
            ytm=Decimal("0.0400"),
        ),
    ]
    rows_end = [
        _bond_row(
            code="BOND2",
            market_value=Decimal("430"),
            face_value=Decimal("200"),
            accrued_interest=Decimal("5.0"),
            coupon_rate=Decimal("0.0420"),
            ytm=Decimal("0.0410"),
        )
    ]

    positions = _merge_positions(rows_start, rows_end)
    quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)

    assert len(positions) == 1
    position = positions[0]
    assert Decimal(str(position["market_value_start"])) == Decimal("400")
    assert Decimal(str(position["market_value_end"])) == Decimal("430")
    assert Decimal(str(position["face_value_start"])) == Decimal("200")
    assert Decimal(str(position["accrued_interest_start"])) == Decimal("4.0")
    assert Decimal(str(position["accrued_interest_end"])) == Decimal("5.0")
    assert Decimal(str(position["coupon_rate_start"])) == Decimal("0.0420")
    assert quality["missing_fields"]["start"]["ytm"]["rows"] == 1
    assert quality["duplicate_instrument_codes"]["start"]["instrument_codes"] == 1
    assert quality["duplicate_position_keys"]["start"]["position_keys"] == 1
    assert quality["warnings"]


def test_input_quality_reports_missing_credit_spread_curve_coverage():
    rows_start = [
        _bond_row(code="BOND_AA_PLUS", rating="AA+", asset_class="credit", market_value=Decimal("100")),
        _bond_row(code="BOND_AA", rating="AA", asset_class="credit", market_value=Decimal("200")),
    ]
    rows_end = [
        _bond_row(code="BOND_AA_PLUS", rating="AA+", asset_class="credit", market_value=Decimal("110")),
        _bond_row(code="BOND_AA", rating="AA", asset_class="credit", market_value=Decimal("210")),
    ]
    positions = _merge_positions(rows_start, rows_end)
    quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)

    _add_market_curve_quality(
        quality,
        positions=positions,
        market_start={"credit_spread_aaa_3y": 35.0},
        market_end={"credit_spread_aaa_3y": 36.0},
    )

    missing = quality["market_curve_coverage"]["missing_credit_spread_3y"]
    assert [row["rating"] for row in missing] == ["AA+", "AA"]
    assert missing[0]["field"] == "credit_spread_aa_plus_3y"
    assert missing[0]["missing_sides"] == ["start", "end"]
    assert missing[1]["field"] == "credit_spread_aa_3y"
    assert any("AA+, AA" in warning for warning in quality["warnings"])


def test_input_quality_reports_treasury_tenor_coverage_gaps():
    rows_start = [
        _bond_row(code="BOND_AAA", rating="AAA", asset_class="credit", market_value=Decimal("100")),
    ]
    rows_end = [
        _bond_row(code="BOND_AAA", rating="AAA", asset_class="credit", market_value=Decimal("110")),
    ]
    positions = _merge_positions(rows_start, rows_end)
    quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)
    full_curve = {
        "treasury_1y": 2.0,
        "treasury_3y": 2.5,
        "treasury_5y": 3.0,
        "treasury_7y": 3.2,
        "treasury_10y": 3.5,
        "treasury_30y": 4.5,
        "credit_spread_aaa_3y": 60.0,
    }
    end_missing_30y = {key: value for key, value in full_curve.items() if key != "treasury_30y"}

    _add_market_curve_quality(
        quality,
        positions=positions,
        market_start=full_curve,
        market_end=end_missing_30y,
    )

    tenors = quality["market_curve_coverage"]["treasury_tenors"]
    assert tenors["start_missing"] == []
    assert tenors["end_missing"] == ["treasury_30y"]
    assert tenors["shared_positive_tenors"] == 5
    assert any("shared-tenor subset" in warning for warning in quality["warnings"])


def test_input_quality_flags_degraded_treasury_period_below_two_shared_tenors():
    rows_start = [
        _bond_row(code="BOND_AAA", rating="AAA", asset_class="credit", market_value=Decimal("100")),
    ]
    rows_end = [
        _bond_row(code="BOND_AAA", rating="AAA", asset_class="credit", market_value=Decimal("110")),
    ]
    positions = _merge_positions(rows_start, rows_end)
    quality = _build_input_quality(rows_start=rows_start, rows_end=rows_end, positions=positions)

    _add_market_curve_quality(
        quality,
        positions=positions,
        market_start={"treasury_1y": 2.0, "credit_spread_aaa_3y": 60.0},
        market_end={"treasury_30y": 4.5, "credit_spread_aaa_3y": 61.0},
    )

    tenors = quality["market_curve_coverage"]["treasury_tenors"]
    assert tenors["shared_positive_tenors"] == 0
    assert any("degrade to 0" in warning for warning in quality["warnings"])


def test_four_effects_envelope_anchors_dates_aggregates_and_surfaces_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_rows = [
        _bond_row(
            code="BOND_DUP",
            cost_center="5010",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=None,
            rating="AA+",
            asset_class="credit",
        ),
        _bond_row(
            code="BOND_DUP",
            cost_center="5010",
            market_value=Decimal("500"),
            face_value=Decimal("500"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AA+",
            asset_class="credit",
        ),
        _bond_row(
            code="GOV_OK",
            cost_center="5020",
            market_value=Decimal("800"),
            face_value=Decimal("800"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0400"),
            rating="AAA",
            asset_class="国债",
        ),
    ]
    end_rows = [
        _bond_row(
            code="BOND_DUP",
            cost_center="5010",
            market_value=Decimal("1475"),
            face_value=Decimal("1500"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AA+",
            asset_class="credit",
        ),
        _bond_row(
            code="GOV_OK",
            cost_center="5020",
            market_value=Decimal("795"),
            face_value=Decimal("800"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0400"),
            rating="AAA",
            asset_class="国债",
        ),
    ]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-15", "2026-01-01"],
        rows_by_date={
            "2026-01-01": start_rows,
            "2026-01-31": end_rows,
        },
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("2.10")),
            ("2026-01-01", "credit_spread_aaa"): {"3Y": 30.0},
            ("2026-01-31", "credit_spread_aaa"): {"3Y": 30.0},
        },
        closure_status="warning",
    )

    envelope = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-10",
        end_date="2026-02-01",
    )
    result = envelope["result"]
    quality = result["input_quality"]

    assert result["period_start"] == "2026-01-01"
    assert result["period_end"] == "2026-01-31"
    assert quality["start_rows"] == 3
    assert quality["end_rows"] == 2
    assert quality["merged_positions"] == 2
    assert quality["missing_fields"]["start"]["ytm"]["rows"] == 1
    assert quality["duplicate_instrument_codes"]["start"]["instrument_codes"] == 1
    assert quality["duplicate_position_keys"]["start"]["position_keys"] == 1
    assert quality["market_curve_coverage"]["missing_credit_spread_3y"][0]["rating"] == "AA+"
    assert result["formal_closure"]["status"] == "warning"
    assert any("duplicate instrument_code" in warning for warning in result["warnings"])
    assert any("credit spread curve coverage is incomplete" in warning for warning in result["warnings"])
    assert any("does not close to formal PnL" in warning for warning in result["warnings"])
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result_meta"]["as_of_date"] == "2026-01-31"
    assert envelope["result_meta"]["evidence_rows"] == 5
    assert envelope["result_meta"]["filters_applied"] == {
        "requested_start_date": "2026-01-10",
        "requested_end_date": "2026-02-01",
        "resolved_start_date": "2026-01-01",
        "resolved_end_date": "2026-01-31",
        "lookback_days": 30,
    }
    assert "fact_formal_bond_analytics_daily" in envelope["result_meta"]["tables_used"]
    assert "yield_curve_daily" in envelope["result_meta"]["tables_used"]

    assert result["totals"]["total_return"] == pytest.approx(
        sum(row["total_return"] for row in result["by_bond"])
    )
    assert result["totals"]["income_return"] == pytest.approx(
        sum(row["income_return"] for row in result["by_asset_class"])
    )
    assert result["totals"]["treasury_effect"] == pytest.approx(
        sum(row["treasury_effect"] for row in result["by_asset_class"])
    )
    assert result["totals"]["spread_effect"] == pytest.approx(
        sum(row["spread_effect"] for row in result["by_asset_class"])
    )
    assert result["totals"]["selection_effect"] == pytest.approx(
        sum(row["selection_effect"] for row in result["by_asset_class"])
    )


def test_four_effects_envelope_caches_by_report_dates_and_returns_defensive_copy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_four_effects_cache()
    duckdb_path = tmp_path / "campisi-cache.duckdb"
    duckdb_path.write_text("seed", encoding="utf-8")
    start_rows = [
        _bond_row(
            code="CACHE_BOND",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AAA",
            asset_class="credit",
        )
    ]
    end_rows = [{**start_rows[0], "market_value": Decimal("990")}]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={
            "2026-01-01": start_rows,
            "2026-01-31": end_rows,
        },
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("2.10")),
            ("2026-01-01", "credit_spread_aaa"): {"3Y": 30.0},
            ("2026-01-31", "credit_spread_aaa"): {"3Y": 30.0},
        },
        duckdb_path=str(duckdb_path),
    )
    calls = {"count": 0}
    real_campisi_attribution = campisi_svc.campisi_attribution

    def counting_campisi_attribution(**kwargs: Any) -> Any:
        calls["count"] += 1
        return real_campisi_attribution(**kwargs)

    monkeypatch.setattr(campisi_svc, "campisi_attribution", counting_campisi_attribution)

    first = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    first["result"]["totals"]["total_return"] = 999999.0
    second = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    assert calls["count"] == 1
    assert second["result"]["totals"]["total_return"] != 999999.0
    assert second["result_meta"]["filters_applied"]["resolved_end_date"] == "2026-01-31"


def test_four_effects_envelope_cache_isolated_by_report_date_and_duckdb_storage_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_four_effects_cache()
    duckdb_path = tmp_path / "campisi-cache.duckdb"
    duckdb_path.write_text("seed", encoding="utf-8")
    start_rows = [
        _bond_row(
            code="CACHE_BOND",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AAA",
            asset_class="credit",
        )
    ]
    end_jan_rows = [{**start_rows[0], "market_value": Decimal("990")}]
    end_feb_rows = [{**start_rows[0], "market_value": Decimal("980")}]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-02-28", "2026-01-31", "2026-01-01"],
        rows_by_date={
            "2026-01-01": start_rows,
            "2026-01-31": end_jan_rows,
            "2026-02-28": end_feb_rows,
        },
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("2.10")),
            ("2026-02-28", "treasury"): _flat_treasury(Decimal("2.20")),
            ("2026-01-01", "credit_spread_aaa"): {"3Y": 30.0},
            ("2026-01-31", "credit_spread_aaa"): {"3Y": 30.0},
            ("2026-02-28", "credit_spread_aaa"): {"3Y": 30.0},
        },
        duckdb_path=str(duckdb_path),
    )
    calls = {"count": 0}
    real_campisi_attribution = campisi_svc.campisi_attribution

    def counting_campisi_attribution(**kwargs: Any) -> Any:
        calls["count"] += 1
        return real_campisi_attribution(**kwargs)

    monkeypatch.setattr(campisi_svc, "campisi_attribution", counting_campisi_attribution)

    campisi_svc.campisi_four_effects_envelope(start_date="2026-01-01", end_date="2026-01-31")
    campisi_svc.campisi_four_effects_envelope(start_date="2026-01-01", end_date="2026-02-28")
    assert calls["count"] == 2

    campisi_svc.campisi_four_effects_envelope(start_date="2026-01-01", end_date="2026-01-31")
    assert calls["count"] == 2

    original_mtime = duckdb_path.stat().st_mtime_ns
    duckdb_path.touch()
    if duckdb_path.stat().st_mtime_ns == original_mtime:
        duckdb_path.write_text("changed", encoding="utf-8")
    campisi_svc.campisi_four_effects_envelope(start_date="2026-01-01", end_date="2026-01-31")

    assert calls["count"] == 3

    campisi_svc.campisi_four_effects_envelope(start_date="2026-01-01", end_date="2026-01-31")
    assert calls["count"] == 3

    sidecar_path = duckdb_path.with_name(f"{duckdb_path.name}.wal")
    sidecar_path.write_text("sidecar", encoding="utf-8")
    campisi_svc.campisi_four_effects_envelope(start_date="2026-01-01", end_date="2026-01-31")

    assert calls["count"] == 4


def test_four_effects_cache_does_not_hide_formal_bridge_changes_after_duckdb_fingerprint_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_four_effects_cache()
    duckdb_path = tmp_path / "campisi-cache.duckdb"
    duckdb_path.write_text("seed", encoding="utf-8")
    start_rows = [
        _bond_row(
            code="BRIDGE_BOND",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AAA",
            asset_class="credit",
        )
    ]
    end_rows = [{**start_rows[0], "market_value": Decimal("1100")}]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={
            "2026-01-01": start_rows,
            "2026-01-31": end_rows,
        },
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-01", "credit_spread_aaa"): {"3Y": 30.0},
            ("2026-01-31", "credit_spread_aaa"): {"3Y": 30.0},
        },
        duckdb_path=str(duckdb_path),
    )
    bridge_actual_pnl = {"value": 35.0}

    def bridge_envelope(**_kwargs: Any) -> dict[str, Any]:
        actual = bridge_actual_pnl["value"]
        return {
            "result_meta": {
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
            "result": {
                "summary": {
                    "total_actual_pnl": {"raw": actual},
                },
                "rows": [
                    {
                        "instrument_code": "BRIDGE_BOND",
                        "portfolio_name": "FIOA",
                        "cost_center": "5010",
                        "accounting_basis": "FVTPL",
                        "beginning_dirty_mv": {"raw": 1000.0},
                        "ending_dirty_mv": {"raw": 1100.0},
                        "carry": {"raw": 5.0},
                        "roll_down": {"raw": 1.0},
                        "treasury_curve": {"raw": 2.0},
                        "credit_spread": {"raw": 3.0},
                        "fx_translation": {"raw": 0.0},
                        "realized_trading": {"raw": 0.0},
                        "unrealized_fv": {"raw": actual - 11.0},
                        "manual_adjustment": {"raw": 0.0},
                        "actual_pnl": {"raw": actual},
                        "residual": {"raw": actual - 11.0},
                        "quality_flag": "ok",
                    }
                ],
            },
        }

    monkeypatch.setattr(campisi_svc, "_fetch_formal_bridge", bridge_envelope, raising=False)

    first = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]
    bridge_actual_pnl["value"] = 45.0
    duckdb_path.write_text("bridge changed", encoding="utf-8")
    second = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]

    assert first["formal_closure"]["formal_actual_pnl"] == 35.0
    assert second["formal_closure"]["formal_actual_pnl"] == 45.0
    assert second["totals"]["total_return"] == 45.0


def test_four_effects_cache_does_not_hide_formal_bridge_changes_after_governance_fingerprint_changes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_four_effects_cache()
    duckdb_path = tmp_path / "campisi-cache.duckdb"
    duckdb_path.write_text("seed", encoding="utf-8")
    governance_path = tmp_path / "governance"
    governance_path.mkdir()
    (governance_path / "cache_manifest.jsonl").write_text("manifest v1", encoding="utf-8")
    (governance_path / "cache_build_run.jsonl").write_text("build v1", encoding="utf-8")
    start_rows = [
        _bond_row(
            code="BRIDGE_BOND",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AAA",
            asset_class="credit",
        )
    ]
    end_rows = [{**start_rows[0], "market_value": Decimal("1100")}]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={
            "2026-01-01": start_rows,
            "2026-01-31": end_rows,
        },
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-01", "credit_spread_aaa"): {"3Y": 30.0},
            ("2026-01-31", "credit_spread_aaa"): {"3Y": 30.0},
        },
        duckdb_path=str(duckdb_path),
    )
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(duckdb_path), governance_path=governance_path),
    )
    bridge_actual_pnl = {"value": 35.0}

    def bridge_envelope(**_kwargs: Any) -> dict[str, Any]:
        actual = bridge_actual_pnl["value"]
        return {
            "result_meta": {
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
            "result": {
                "summary": {
                    "total_actual_pnl": {"raw": actual},
                },
                "rows": [
                    {
                        "instrument_code": "BRIDGE_BOND",
                        "portfolio_name": "FIOA",
                        "cost_center": "5010",
                        "accounting_basis": "FVTPL",
                        "beginning_dirty_mv": {"raw": 1000.0},
                        "ending_dirty_mv": {"raw": 1100.0},
                        "carry": {"raw": 5.0},
                        "roll_down": {"raw": 1.0},
                        "treasury_curve": {"raw": 2.0},
                        "credit_spread": {"raw": 3.0},
                        "fx_translation": {"raw": 0.0},
                        "realized_trading": {"raw": 0.0},
                        "unrealized_fv": {"raw": actual - 11.0},
                        "manual_adjustment": {"raw": 0.0},
                        "actual_pnl": {"raw": actual},
                        "residual": {"raw": actual - 11.0},
                        "quality_flag": "ok",
                    }
                ],
            },
        }

    monkeypatch.setattr(campisi_svc, "_fetch_formal_bridge", bridge_envelope, raising=False)

    first = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]
    bridge_actual_pnl["value"] = 45.0
    (governance_path / "cache_build_run.jsonl").write_text("build v2 changed", encoding="utf-8")
    second = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]

    assert first["formal_closure"]["formal_actual_pnl"] == 35.0
    assert second["formal_closure"]["formal_actual_pnl"] == 45.0
    assert second["totals"]["total_return"] == 45.0


def test_enhanced_and_maturity_bucket_envelopes_close_to_same_four_effect_totals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_rows = [
        _bond_row(
            code="GOV_BUCKET",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AAA",
            asset_class="国债",
        ),
        _bond_row(
            code="AAA_BUCKET",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AAA",
            asset_class="credit",
        ),
    ]
    end_rows = [
        {**start_rows[0], "market_value": Decimal("990")},
        {**start_rows[1], "market_value": Decimal("995")},
    ]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={
            "2026-01-01": start_rows,
            "2026-01-31": end_rows,
        },
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("3.00")),
            ("2026-01-01", "credit_spread_aaa"): {"3Y": 50.0},
            ("2026-01-31", "credit_spread_aaa"): {"3Y": 100.0},
            ("2026-01-01", "credit_spread_aa_plus"): {"3Y": 80.0},
            ("2026-01-31", "credit_spread_aa_plus"): {"3Y": 80.0},
            ("2026-01-01", "credit_spread_aa"): {"3Y": 100.0},
            ("2026-01-31", "credit_spread_aa"): {"3Y": 100.0},
        },
    )

    four = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]
    enhanced = campisi_svc.campisi_enhanced_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]
    maturity = campisi_svc.campisi_maturity_bucket_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]

    enhanced_components = (
        enhanced["totals"]["income_return"]
        + enhanced["totals"]["treasury_effect"]
        + enhanced["totals"]["spread_effect"]
        + enhanced["totals"]["convexity_effect"]
        + enhanced["totals"]["cross_effect"]
        + enhanced["totals"]["reinvestment_effect"]
        + enhanced["totals"]["selection_effect"]
    )
    bucket_total = sum(bucket["total_return"] for bucket in maturity["buckets"].values())

    assert enhanced_components == pytest.approx(enhanced["totals"]["total_return"])
    assert bucket_total == pytest.approx(four["totals"]["total_return"])
    assert enhanced["input_quality"]["start_rows"] == 2
    assert maturity["input_quality"]["end_rows"] == 2
    assert sum(bucket["income_return"] for bucket in maturity["buckets"].values()) == pytest.approx(
        four["totals"]["income_return"]
    )
    assert sum(bucket["treasury_effect"] for bucket in maturity["buckets"].values()) == pytest.approx(
        four["totals"]["treasury_effect"]
    )
    assert sum(bucket["spread_effect"] for bucket in maturity["buckets"].values()) == pytest.approx(
        four["totals"]["spread_effect"]
    )
    assert sum(bucket["selection_effect"] for bucket in maturity["buckets"].values()) == pytest.approx(
        four["totals"]["selection_effect"]
    )


def test_maturity_bucket_envelope_reuses_cached_four_effects_state_without_recompute(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _clear_four_effects_cache()
    duckdb_path = tmp_path / "campisi-cache.duckdb"
    duckdb_path.write_text("seed", encoding="utf-8")
    start_rows = [
        _bond_row(
            code="GOV_BUCKET",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AAA",
            asset_class="国债",
        ),
        _bond_row(
            code="AAA_BUCKET",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AAA",
            asset_class="credit",
        ),
    ]
    end_rows = [
        {**start_rows[0], "market_value": Decimal("990")},
        {**start_rows[1], "market_value": Decimal("995")},
    ]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={
            "2026-01-01": start_rows,
            "2026-01-31": end_rows,
        },
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("3.00")),
            ("2026-01-01", "credit_spread_aaa"): {"3Y": 50.0},
            ("2026-01-31", "credit_spread_aaa"): {"3Y": 100.0},
        },
        duckdb_path=str(duckdb_path),
    )

    cold_buckets = campisi_svc.campisi_maturity_bucket_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]["buckets"]

    _clear_four_effects_cache()
    campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )

    calls = {"campisi_attribution": 0, "maturity_bucket_attribution": 0}
    real_campisi_attribution = campisi_svc.campisi_attribution
    real_maturity_bucket_attribution = campisi_svc.maturity_bucket_attribution

    def counting_campisi_attribution(**kwargs: Any) -> Any:
        calls["campisi_attribution"] += 1
        return real_campisi_attribution(**kwargs)

    def counting_maturity_bucket_attribution(**kwargs: Any) -> Any:
        calls["maturity_bucket_attribution"] += 1
        return real_maturity_bucket_attribution(**kwargs)

    monkeypatch.setattr(campisi_svc, "campisi_attribution", counting_campisi_attribution)
    monkeypatch.setattr(campisi_svc, "maturity_bucket_attribution", counting_maturity_bucket_attribution)

    warm_buckets = campisi_svc.campisi_maturity_bucket_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]["buckets"]

    assert calls["campisi_attribution"] == 0
    assert calls["maturity_bucket_attribution"] == 0
    assert warm_buckets == cold_buckets


def test_campisi_envelopes_close_to_formal_report_pnl_when_bridge_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_rows = [
        _bond_row(
            code="BOND_FORMAL",
            market_value=Decimal("1000"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AAA",
            asset_class="credit",
        )
    ]
    end_rows = [
        _bond_row(
            code="BOND_FORMAL",
            market_value=Decimal("1100"),
            face_value=Decimal("1000"),
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.0000"),
            ytm=Decimal("0.0500"),
            rating="AAA",
            asset_class="credit",
        )
    ]
    _install_full_service_fakes(
        monkeypatch,
        dates=["2026-01-31", "2026-01-01"],
        rows_by_date={
            "2026-01-01": start_rows,
            "2026-01-31": end_rows,
        },
        curves={
            ("2026-01-01", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-31", "treasury"): _flat_treasury(Decimal("2.00")),
            ("2026-01-01", "credit_spread_aaa"): {"3Y": 30.0},
            ("2026-01-31", "credit_spread_aaa"): {"3Y": 30.0},
        },
        closure_status="warning",
    )

    bridge = {
        "result_meta": {
            "quality_flag": "ok",
            "vendor_status": "ok",
            "fallback_mode": "none",
        },
        "result": {
            "summary": {
                "total_actual_pnl": {"raw": 35.0},
            },
            "rows": [
                {
                    "instrument_code": "BOND_FORMAL",
                    "portfolio_name": "FIOA",
                    "cost_center": "5010",
                    "accounting_basis": "FVTPL",
                    "beginning_dirty_mv": {"raw": 1000.0},
                    "ending_dirty_mv": {"raw": 1100.0},
                    "carry": {"raw": 5.0},
                    "roll_down": {"raw": 1.0},
                    "treasury_curve": {"raw": 2.0},
                    "credit_spread": {"raw": 3.0},
                    "fx_translation": {"raw": 4.0},
                    "realized_trading": {"raw": 6.0},
                    "unrealized_fv": {"raw": 14.0},
                    "manual_adjustment": {"raw": 0.0},
                    "actual_pnl": {"raw": 35.0},
                    "residual": {"raw": 14.0},
                    "quality_flag": "ok",
                }
            ],
        },
    }

    monkeypatch.setattr(
        campisi_svc,
        "_fetch_formal_bridge",
        lambda **_kwargs: bridge,
        raising=False,
    )

    def fake_formal_closure(*, report_date: str, campisi_total_return: Decimal, **_kwargs: Any) -> dict[str, object]:
        formal_actual = Decimal("35")
        residual = formal_actual - campisi_total_return
        return {
            "basis": "pnl.bridge.total_actual_pnl",
            "report_date": report_date,
            "status": "closed" if abs(residual) <= Decimal("1.00") else "warning",
            "campisi_total_return": float(campisi_total_return),
            "formal_actual_pnl": float(formal_actual),
            "residual_to_formal_pnl": float(residual),
            "residual_ratio": 0.0,
            "bridge_quality_flag": "ok",
            "bridge_vendor_status": "ok",
            "bridge_fallback_mode": "none",
            "message": "Campisi total return closes to formal PnL.",
        }

    monkeypatch.setattr(campisi_svc, "_fetch_formal_closure", fake_formal_closure)

    four = campisi_svc.campisi_four_effects_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]
    enhanced = campisi_svc.campisi_enhanced_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]
    maturity = campisi_svc.campisi_maturity_bucket_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]

    assert four["basis"] == "formal_report_pnl_bridge"
    assert four["formal_closure"]["status"] == "closed"
    assert four["formal_closure"]["residual_to_formal_pnl"] == pytest.approx(0.0)
    assert four["totals"]["total_return"] == pytest.approx(35.0)
    assert four["totals"]["income_return"] == pytest.approx(5.0)
    assert four["totals"]["treasury_effect"] == pytest.approx(3.0)
    assert four["totals"]["spread_effect"] == pytest.approx(3.0)
    assert four["totals"]["realized_trading"] == pytest.approx(6.0)
    assert four["totals"]["fx_translation"] == pytest.approx(4.0)
    assert four["totals"]["manual_adjustment"] == pytest.approx(0.0)
    assert four["totals"]["selection_effect"] == pytest.approx(14.0)
    assert four["decomposition_basis"] == campisi_svc.FORMAL_BRIDGE_DECOMPOSITION_BASIS
    assert (
        four["totals"]["income_return"]
        + four["totals"]["treasury_effect"]
        + four["totals"]["spread_effect"]
        + four["totals"]["realized_trading"]
        + four["totals"]["fx_translation"]
        + four["totals"]["manual_adjustment"]
        + four["totals"]["selection_effect"]
    ) == pytest.approx(four["totals"]["total_return"])
    assert enhanced["basis"] == "formal_report_pnl_bridge"
    assert enhanced["decomposition_basis"] == campisi_svc.FORMAL_BRIDGE_DECOMPOSITION_BASIS
    assert enhanced["totals"]["total_return"] == pytest.approx(35.0)
    assert enhanced["totals"]["selection_effect"] == pytest.approx(14.0)
    assert sum(bucket["total_return"] for bucket in maturity["buckets"].values()) == pytest.approx(35.0)
    bond_row = four["by_bond"][0]
    assert bond_row["realized_trading"] == pytest.approx(6.0)
    assert bond_row["fx_translation"] == pytest.approx(4.0)
    assert bond_row["selection_effect"] == pytest.approx(14.0)


def test_build_formal_closure_reports_residual_to_actual_pnl():
    closure = _build_formal_closure(
        report_date="2026-04-30",
        campisi_total_return=Decimal("7776186475.628492"),
        bridge_envelope={
            "result_meta": {
                "quality_flag": "ok",
                "vendor_status": "vendor_stale",
                "fallback_mode": "latest_snapshot",
            },
            "result": {
                "summary": {
                    "total_actual_pnl": {
                        "raw": 535945018.042292,
                    },
                },
            },
        },
    )

    assert closure["status"] == "warning"
    assert closure["basis"] == "pnl.bridge.total_actual_pnl"
    assert closure["formal_actual_pnl"] == 535945018.042292
    assert closure["campisi_total_return"] == 7776186475.628492
    assert closure["residual_to_formal_pnl"] == -7240241457.5862
    assert closure["bridge_quality_flag"] == "ok"
    assert closure["bridge_vendor_status"] == "vendor_stale"
    assert closure["bridge_fallback_mode"] == "latest_snapshot"
    assert abs(
        closure["campisi_total_return"]
        + closure["residual_to_formal_pnl"]
        - closure["formal_actual_pnl"]
    ) < 0.01


def test_formal_bridge_bond_rows_exposes_bridge_detail_fields_and_closes():
    bridge = {
        "result": {
            "rows": [
                {
                    "instrument_code": "BOND001",
                    "portfolio_name": "FIOA",
                    "cost_center": "5010",
                    "accounting_basis": "FVTPL",
                    "beginning_dirty_mv": {"raw": 1000.0},
                    "carry": {"raw": 5.0},
                    "roll_down": {"raw": 1.0},
                    "treasury_curve": {"raw": 2.0},
                    "credit_spread": {"raw": 3.0},
                    "fx_translation": {"raw": 4.0},
                    "realized_trading": {"raw": 6.0},
                    "manual_adjustment": {"raw": 1.0},
                    "actual_pnl": {"raw": 36.0},
                    "residual": {"raw": 14.0},
                }
            ]
        }
    }
    rows = campisi_svc._formal_bridge_bond_rows(
        bridge_envelope=bridge,
        positions=[
            {
                "instrument_code": "BOND001",
                "portfolio_name": "FIOA",
                "cost_center": "5010",
                "asset_class_start": "credit",
                "maturity_date_start": "2031-01-01",
                "market_value_start": 1000.0,
            }
        ],
        start_date=date(2026, 1, 1),
    )
    row = rows[0]
    assert row["realized_trading"] == pytest.approx(6.0)
    assert row["fx_translation"] == pytest.approx(4.0)
    assert row["manual_adjustment"] == pytest.approx(1.0)
    assert row["selection_effect"] == pytest.approx(14.0)
    assert (
        row["income_return"]
        + row["treasury_effect"]
        + row["spread_effect"]
        + row["realized_trading"]
        + row["fx_translation"]
        + row["manual_adjustment"]
        + row["selection_effect"]
    ) == pytest.approx(row["total_return"])


def _bridge_row_with_residual(
    *,
    actual_pnl: float,
    residual: float | None,
) -> dict[str, Any]:
    """固定分量合计 22 的桥行；residual 由调用方独立给定。

    selection = actual_pnl − 22，与 pnl_bridge 的 residual = actual_pnl − explained_pnl
    应当是同一个量；两者不一致即为桥接口径漂移。
    """
    row: dict[str, Any] = {
        "instrument_code": "BOND_RESIDUAL",
        "portfolio_name": "FIOA",
        "cost_center": "5010",
        "accounting_basis": "FVTPL",
        "beginning_dirty_mv": {"raw": 1000.0},
        "carry": {"raw": 5.0},
        "roll_down": {"raw": 1.0},
        "treasury_curve": {"raw": 2.0},
        "credit_spread": {"raw": 3.0},
        "fx_translation": {"raw": 4.0},
        "realized_trading": {"raw": 6.0},
        "manual_adjustment": {"raw": 1.0},
        "unrealized_fv": {"raw": actual_pnl - 22.0},
        "actual_pnl": {"raw": actual_pnl},
    }
    if residual is not None:
        row["residual"] = {"raw": residual}
    return row


def _formal_bridge_row_from(row: dict[str, Any]) -> dict[str, Any]:
    return campisi_svc._formal_bridge_bond_rows(
        bridge_envelope={"result": {"rows": [row]}},
        positions=[
            {
                "instrument_code": "BOND_RESIDUAL",
                "portfolio_name": "FIOA",
                "cost_center": "5010",
                "asset_class_start": "credit",
                "maturity_date_start": "2031-01-01",
                "market_value_start": 1000.0,
            }
        ],
        start_date=date(2026, 1, 1),
    )[0]


def test_formal_bridge_row_closure_raises_when_bridge_residual_disagrees_with_selection():
    """负向：桥行自身 residual 与重算 selection 差 1000 时必须抛。

    修复前断言用与 selection 完全相同的减法自证，恒为 0，本用例不会抛。
    """
    drifted = _bridge_row_with_residual(actual_pnl=1036.0, residual=14.0)

    with pytest.raises(ValueError) as excinfo:
        _formal_bridge_row_from(drifted)

    assert "residual" in str(excinfo.value)


def test_formal_bridge_row_closure_raises_when_bridge_residual_field_is_absent():
    """负向：缺 residual 字段就没有独立对照，不得静默放行。"""
    with pytest.raises(ValueError):
        _formal_bridge_row_from(_bridge_row_with_residual(actual_pnl=36.0, residual=None))


def test_formal_bridge_row_closure_passes_when_bridge_residual_matches_selection():
    """正向：residual 与 selection 一致时照常通过，证明门禁不是恒失败。"""
    row = _formal_bridge_row_from(_bridge_row_with_residual(actual_pnl=1036.0, residual=1014.0))

    assert row["selection_effect"] == pytest.approx(1014.0)
    assert row["total_return"] == pytest.approx(1036.0)


def test_formal_bridge_row_closure_tolerates_float_round_trip_at_billion_scale():
    """亿元级分量经 Numeric.raw(float) 往返后仍判闭合：容差不得把噪音判成漂移。"""
    carry = Decimal("123456789.37")
    roll_down = Decimal("2345678.91")
    treasury_curve = Decimal("-3456789.13")
    credit_spread = Decimal("456789.57")
    fx_translation = Decimal("-56789.11")
    realized_trading = Decimal("6789012.29")
    manual_adjustment = Decimal("789.33")
    actual_pnl = Decimal("987654321.19")
    residual = actual_pnl - (
        carry + roll_down + treasury_curve + credit_spread + fx_translation + realized_trading + manual_adjustment
    )

    row = _formal_bridge_row_from(
        {
            "instrument_code": "BOND_RESIDUAL",
            "portfolio_name": "FIOA",
            "cost_center": "5010",
            "accounting_basis": "FVTPL",
            "beginning_dirty_mv": {"raw": 1_000_000_000.0},
            "carry": {"raw": float(carry)},
            "roll_down": {"raw": float(roll_down)},
            "treasury_curve": {"raw": float(treasury_curve)},
            "credit_spread": {"raw": float(credit_spread)},
            "fx_translation": {"raw": float(fx_translation)},
            "realized_trading": {"raw": float(realized_trading)},
            "manual_adjustment": {"raw": float(manual_adjustment)},
            "actual_pnl": {"raw": float(actual_pnl)},
            "residual": {"raw": float(residual)},
        }
    )

    assert row["selection_effect"] == pytest.approx(float(residual))


def test_decision_residual_ratio_is_null_when_actual_zero_and_residual_nonzero():
    ratio = _decision_residual_ratio(
        formal_actual_pnl=Decimal("0"),
        residual_noise=Decimal("10"),
    )

    assert ratio is None


def test_decision_residual_ratio_is_zero_when_actual_and_residual_zero():
    ratio = _decision_residual_ratio(
        formal_actual_pnl=Decimal("0"),
        residual_noise=Decimal("0"),
    )

    assert ratio == 0.0


def test_decision_residual_ratio_uses_absolute_actual_pnl():
    ratio = _decision_residual_ratio(
        formal_actual_pnl=Decimal("-100"),
        residual_noise=Decimal("10"),
    )

    assert ratio == pytest.approx(0.1)


def _seed_formal_curve(duckdb_path, rows: list[tuple[object, ...]]) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_yield_curve_tables(conn)
        conn.executemany(
            f"""
            insert into {FORMAL_FACT_TABLE} (
              trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    finally:
        conn.close()


def test_fetch_spread_data_derives_aaa_spread_from_formal_curves_when_legacy_curve_type_has_no_rows(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_formal_curve(
        duckdb_path,
        [
            ("2026-02-28", "treasury", "3Y", Decimal("2.70"), "choice", "vv_t", "sv_t", "rv"),
            ("2026-02-28", "aaa_credit", "3Y", Decimal("3.05"), "choice", "vv_a", "sv_a", "rv"),
        ],
    )

    spread = _fetch_spread_data(YieldCurveRepository(str(duckdb_path)), "2026-02-28")

    assert spread["credit_spread_aaa_3y"] == 35.0


def test_fetch_spread_data_derives_aa_plus_and_aa_from_choice_macro_tables(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    _seed_formal_curve(
        duckdb_path,
        [
            ("2026-02-28", "treasury", "3Y", Decimal("2.70"), "choice", "vv_t", "sv_t", "rv"),
        ],
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              vendor_name varchar,
              vendor_version varchar,
              frequency varchar,
              unit varchar
            )
            """
        )
        conn.execute(
            """
            create table if not exists fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.execute("delete from phase1_macro_vendor_catalog")
        conn.execute("delete from fact_choice_macro_daily")
        conn.executemany(
            """
            insert into phase1_macro_vendor_catalog (
              series_id, series_name, vendor_name, vendor_version, frequency, unit
            ) values (?, ?, ?, ?, ?, ?)
            """,
            [
                ("CHOICE_AA_PLUS_3Y", "China enterprise bond yield curve (AA+):3Y", "choice", "vv_choice", "daily", "%"),
                ("EMM00166681", "China enterprise bond yield curve (AA):3Y", "choice", "vv_choice", "daily", "%"),
            ],
        )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("CHOICE_AA_PLUS_3Y", "", "2026-02-28", 3.30, "daily", "%", "sv_choice", "vv_choice", "rv_choice", "ok", "run-1"),
                ("EMM00166681", "", "2026-02-28", 3.50, "daily", "%", "sv_choice", "vv_choice", "rv_choice", "ok", "run-1"),
            ],
        )
    finally:
        conn.close()

    spread = _fetch_spread_data(YieldCurveRepository(str(duckdb_path)), "2026-02-28")

    assert spread["credit_spread_aa_plus_3y"] == 60.0
    assert spread["credit_spread_aa_3y"] == 80.0
