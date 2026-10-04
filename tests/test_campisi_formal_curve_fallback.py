"""Formal treasury snapshots must remain traceable through Campisi's HTTP reads."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from backend.app.repositories.bond_analytics_repo import ensure_bond_analytics_tables
from backend.app.repositories.yield_curve_repo import ensure_yield_curve_tables
from backend.app.services import campisi_attribution_service as campisi_svc
from tests.test_campisi_four_effects_detail_summary import _campisi_route_client_with_read_scope


def _seed_formal_facts(db_path: Path, *, start_curve_date: str, end_rate_shift: Decimal) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        ensure_bond_analytics_tables(conn)
        ensure_yield_curve_tables(conn)
        for report_date in ("2026-08-01", "2026-08-31"):
            conn.execute(
                """
                insert into fact_formal_bond_analytics_daily (
                    report_date, instrument_code, instrument_name, portfolio_name, cost_center,
                    asset_class_raw, asset_class_std, accounting_class, currency_code,
                    face_value, market_value, accrued_interest, coupon_rate, ytm,
                    maturity_date, years_to_maturity, modified_duration,
                    source_version, rule_version
                ) values (?, 'BOND1', 'BOND1', 'FIOA', '5010', '国债', '国债', 'FVOCI', 'CNY',
                          1000, 1000, 0, 0.03, 0.03, '2030-08-31', 4, 2,
                          'sv_test_formal_bond', 'rv_test_formal_bond')
                """,
                [report_date],
            )
        for trade_date, shift in ((start_curve_date, Decimal("0")), ("2026-08-31", end_rate_shift)):
            for tenor, base in (("1Y", Decimal("2.00")), ("3Y", Decimal("2.30"))):
                conn.execute(
                    """
                    insert into fact_formal_yield_curve_daily
                    (trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version,
                     source_version, rule_version)
                    values (?, 'treasury', ?, ?, 'fixture', 'vv_fixture',
                            'sv_fixture_treasury', 'rv_yield_curve_formal_materialize_v1')
                    """,
                    [trade_date, tenor, base + shift],
                )
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("start_curve_date", "end_rate_shift", "expected_resolved", "expected_used"),
    [
        pytest.param("2026-07-31", Decimal("0.10"), "2026-07-31", True, id="accepted_previous_day"),
        pytest.param("2026-07-25", Decimal("0.10"), "2026-07-25", True, id="seven_days_accepted"),
        pytest.param("2026-07-24", Decimal("0.10"), "2026-07-24", False, id="eight_days_rejected"),
        pytest.param("2026-07-20", Decimal("0.10"), "2026-07-20", False, id="stale_rejected"),
        pytest.param("2026-08-02", Decimal("0.10"), None, False, id="future_not_used"),
        pytest.param("2026-07-31", Decimal("0"), "2026-07-31", True, id="observed_zero"),
    ],
)
def test_formal_curve_resolution_survives_service_and_strict_http_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    start_curve_date: str,
    end_rate_shift: Decimal,
    expected_resolved: str | None,
    expected_used: bool,
) -> None:
    work_dir = tmp_path
    try:
        db_path = work_dir / "formal-facts.duckdb"
        _seed_formal_facts(db_path, start_curve_date=start_curve_date, end_rate_shift=end_rate_shift)
        monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
        monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(work_dir / "governance"))
        get_settings.cache_clear()
        campisi_svc.clear_campisi_four_effects_runtime_cache()
        campisi_svc.clear_campisi_four_effects_envelope_runtime_cache()
        client, route = _campisi_route_client_with_read_scope(work_dir, monkeypatch)
        try:
            response = client.get(
                "/api/pnl-attribution/campisi/four-effects",
                params={"end_date": "2026-08-31", "lookback_days": 30, "detail": "summary"},
            )
            assert response.status_code == 200, response.text
            envelope = response.json()
            result = envelope["result"]
            quality = result["input_quality"]["market_curve_coverage"]["treasury_effect"]
            assert result["period_start"] == "2026-08-01"
            assert result["period_end"] == "2026-08-31"
            assert envelope["result_meta"]["requested_report_date"] == "2026-08-31"
            assert envelope["result_meta"]["resolved_report_date"] == "2026-08-31"
            assert quality["start_requested_date"] == "2026-08-01"
            assert quality["start_resolved_date"] == expected_resolved
            assert quality["end_requested_date"] == "2026-08-31"
            assert quality["end_resolved_date"] == "2026-08-31"
            assert quality["start_curve_used"] is expected_used
            assert quality["end_curve_used"] is True
            assert quality["start_curve_rows_present"] is False
            assert quality["end_curve_rows_present"] is True

            if expected_used:
                assert quality["status"] == "ok"
                assert quality["shared_positive_tenors"] == 2
                assert result["effect_availability"]["treasury_effect"]["status"] == "ok"
                assert envelope["result_meta"]["fallback_mode"] == "latest_snapshot"
                assert envelope["result_meta"]["fallback_date"] == expected_resolved
                assert envelope["result_meta"]["quality_flag"] == "stale"
                assert envelope["result_meta"]["vendor_status"] == "vendor_stale"
                if end_rate_shift:
                    # The curve move is 0.10 percentage point / 100. The service's
                    # duration and roll-down decomposition leaves an effect of
                    # several currency units, not hundredths from double scaling.
                    assert -10.0 < result["totals"]["treasury_effect"] < -1.0
                else:
                    assert result["totals"]["treasury_effect"] == pytest.approx(0.0)
                for endpoint in ("enhanced", "maturity-buckets"):
                    sibling = client.get(
                        f"/api/pnl-attribution/campisi/{endpoint}",
                        params={"end_date": "2026-08-31", "lookback_days": 30},
                    )
                    assert sibling.status_code == 200, sibling.text
                    sibling_envelope = sibling.json()
                    sibling_quality = sibling_envelope["result"]["input_quality"]["market_curve_coverage"]["treasury_effect"]
                    assert sibling_quality["start_resolved_date"] == expected_resolved
                    assert sibling_quality["start_curve_used"] is True
                    assert sibling_envelope["result_meta"]["quality_flag"] == "stale"
                    assert sibling_envelope["result_meta"]["vendor_status"] == "vendor_stale"
            else:
                assert quality["status"] == "unavailable"
                assert quality["shared_positive_tenors"] == 0
                assert result["effect_availability"]["treasury_effect"]["status"] == "unavailable"
                assert envelope["result_meta"]["fallback_mode"] == "none"
                assert envelope["result_meta"]["fallback_date"] is None
                if expected_resolved:
                    assert any(
                        expected_resolved in warning and "7-day" in warning and "discarded" in warning
                        for warning in result["warnings"]
                    )
        finally:
            client.close()
            route.market_home_response_cache.invalidate()
            campisi_svc.clear_campisi_four_effects_runtime_cache()
            campisi_svc.clear_campisi_four_effects_envelope_runtime_cache()
            get_settings.cache_clear()
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    ("upstream_quality", "upstream_vendor", "expected_quality", "expected_vendor"),
    [
        ("ok", "ok", "stale", "vendor_stale"),
        ("error", "vendor_unavailable", "error", "vendor_unavailable"),
    ],
)
def test_adopted_curve_fallback_preserves_worse_upstream_quality(
    upstream_quality: str,
    upstream_vendor: str,
    expected_quality: str,
    expected_vendor: str,
) -> None:
    input_quality = {
        "warnings": ["Formal treasury curve was resolved to an earlier date."],
        "market_curve_coverage": {
            "treasury_effect": {
                "start_requested_date": "2026-08-01",
                "start_resolved_date": "2026-07-31",
                "start_curve_used": True,
            },
        },
    }
    meta = campisi_svc._meta_with_quality(
        "campisi.four_effects",
        input_quality,
        upstream_meta={
            "quality_flag": upstream_quality,
            "vendor_status": upstream_vendor,
            "fallback_mode": "none",
        },
        filters_applied={
            "requested_end_date": "2026-08-31",
            "resolved_end_date": "2026-08-31",
        },
    )
    assert meta.quality_flag == expected_quality
    assert meta.vendor_status == expected_vendor
    assert meta.fallback_mode == "latest_snapshot"
    assert meta.fallback_date == "2026-07-31"
    assert meta.requested_report_date == "2026-08-31"
    assert meta.resolved_report_date == "2026-08-31"

    report_fallback = campisi_svc._meta_with_quality(
        "campisi.four_effects",
        input_quality,
        filters_applied={
            "requested_end_date": "2026-09-01",
            "resolved_end_date": "2026-08-31",
        },
    )
    assert report_fallback.fallback_date == "2026-08-31"
