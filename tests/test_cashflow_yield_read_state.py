from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.governance.settings import get_settings
from tests.helpers import load_module


def test_duration_fallback_uses_decimal_rates_and_semiannual_frequency():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    bond_duration_mod = load_module(
        "backend.app.core_finance.bond_duration",
        "backend/app/core_finance/bond_duration.py",
    )
    row = {
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2031, 1, 1),
        "instrument_code": "BOND-SEMI-001",
        "coupon_rate": Decimal("0.03"),
        "ytm": Decimal("0.035"),
        "interest_mode": "semi-annual",
        "macaulay_duration": None,
    }

    expected = bond_duration_mod.estimate_duration(
        date(2031, 1, 1),
        date(2026, 1, 1),
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.035"),
        bond_code="BOND-SEMI-001",
        coupon_frequency=2,
    )

    assert service_mod._recompute_macaulay_duration(row) == expected


@pytest.mark.parametrize("interest_mode", ["annual", "bullet"])
@pytest.mark.parametrize(
    ("yield_fields", "effective_ytm"),
    [
        pytest.param({}, Decimal("0.03"), id="absent"),
        pytest.param({"ytm": None, "ytm_value": None}, Decimal("0.03"), id="null"),
        pytest.param({"ytm": "", "ytm_value": ""}, Decimal("0.03"), id="empty"),
        pytest.param({"ytm": " "}, Decimal("0.03"), id="whitespace"),
        pytest.param({"ytm": "not-a-yield"}, Decimal("0.03"), id="invalid-primary"),
        pytest.param({"ytm_value": "not-a-yield"}, Decimal("0.03"), id="invalid-alias"),
        pytest.param({"ytm": Decimal("NaN")}, Decimal("0.03"), id="nan"),
        pytest.param({"ytm": "Infinity"}, Decimal("0.03"), id="infinity"),
        pytest.param({"ytm_value": float("-inf")}, Decimal("0.03"), id="negative-infinity"),
        pytest.param({"ytm": Decimal("0")}, Decimal("0"), id="observed-zero"),
        pytest.param({"ytm": "0.03500001"}, Decimal("0.03500001"), id="observed-positive"),
        pytest.param({"ytm": Decimal("-0.01")}, Decimal("-0.01"), id="observed-negative"),
        pytest.param({"ytm": None, "ytm_value": "0"}, Decimal("0"), id="alias-zero"),
        pytest.param({"ytm": "", "ytm_value": "0.035"}, Decimal("0.035"), id="alias-positive"),
        pytest.param({"ytm_value": "-0.01"}, Decimal("-0.01"), id="alias-negative"),
        pytest.param(
            {"ytm": Decimal("0"), "ytm_value": Decimal("0.035")},
            Decimal("0"),
            id="primary-zero-precedes-alias",
        ),
    ],
)
def test_duration_fallback_distinguishes_missing_and_observed_yields(
    yield_fields, effective_ytm, interest_mode
):
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    row = {
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2028, 1, 1),
        "instrument_code": "SYNTHETIC-YIELD-SEMANTICS",
        "coupon_rate": Decimal("0.03"),
        "interest_mode": interest_mode,
        **yield_fields,
    }

    if interest_mode == "bullet":
        expected = Decimal("2")
    else:
        # Independent two-cashflow PV weighting, with decimal annual rates.
        first_pv = Decimal("0.03") / (Decimal("1") + effective_ytm)
        final_pv = Decimal("1.03") / (Decimal("1") + effective_ytm) ** 2
        expected = (first_pv + Decimal("2") * final_pv) / (first_pv + final_pv)

    assert service_mod._recompute_macaulay_duration(row) == expected


@pytest.mark.parametrize("duration", [Decimal("0"), Decimal("1.25000001")])
def test_attach_duration_prefers_valid_materialized_value_over_invalid_yield(
    duration, monkeypatch
):
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key_fields = {
        "instrument_code": "SYNTHETIC-MATERIALIZED-DURATION",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }

    def unexpected_recompute(_row):
        pytest.fail("A valid materialized duration must not be recomputed.")

    monkeypatch.setattr(service_mod, "_recompute_macaulay_duration_with_assumption", unexpected_recompute)
    enriched = service_mod._attach_macaulay_duration(
        [{**key_fields, "position_scope": "asset"}],
        [{**key_fields, "macaulay_duration": duration, "ytm": "not-a-yield"}],
    )

    assert enriched[0]["macaulay_duration"] == duration


def test_attach_duration_preserves_par_fallback_quality_flag_after_recomputation():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key_fields = {
        "instrument_code": "SYNTHETIC-PAR-FALLBACK",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }
    analytics_row = {
        **key_fields,
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2028, 1, 1),
        "coupon_rate": Decimal("0.03"),
        "interest_mode": "annual",
        "ytm": None,
        "macaulay_duration": None,
        "duration_quality_flag": "ytm_par_fallback",
    }

    enriched = service_mod._attach_macaulay_duration(
        [{**key_fields, "position_scope": "asset"}], [analytics_row]
    )

    assert enriched[0]["duration_quality_flag"] == "ytm_par_fallback"
    assert enriched[0]["macaulay_duration"] == Decimal("1.970873786407766990291262136")


def test_cashflow_par_recompute_without_source_flag_discloses_assumption(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key = {
        "instrument_code": "SYNTHETIC-PAR-NO-FLAG",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }
    zqtz_row = {
        **key,
        "position_scope": "asset",
        "maturity_date": date(2028, 1, 1),
        "face_value_amount": Decimal("100"),
        "market_value_amount": Decimal("100"),
        "coupon_rate": Decimal("3"),
        "interest_mode": "annual",
    }
    analytics_row = {
        **key,
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2028, 1, 1),
        "coupon_rate": Decimal("0.03"),
        "interest_mode": "annual",
        "ytm": None,
        "macaulay_duration": None,
    }
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_zqtz_rows",
        lambda *_args, **_kwargs: [zqtz_row],
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        lambda *_args, **_kwargs: [analytics_row],
    )

    result = service_mod.get_cashflow_projection(date(2026, 1, 1))["result"]

    assert result["asset_duration"]["raw"] == float(Decimal("1.970873786407766990291262136"))
    assert any("par assumption" in warning for warning in result["warnings"])
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("ytm", "materialized", "interest_mode", "uses_par"),
    [
        pytest.param(None, None, "annual", True, id="missing-annual"),
        pytest.param("invalid", None, "annual", True, id="dirty-annual"),
        pytest.param(Decimal("0"), None, "annual", False, id="observed-zero"),
        pytest.param(Decimal("-0.01"), None, "annual", False, id="observed-negative"),
        pytest.param(Decimal("0.035"), None, "annual", False, id="observed-positive"),
        pytest.param(None, Decimal("0"), "annual", False, id="materialized-zero"),
        pytest.param(None, Decimal("1.25"), "annual", False, id="materialized-positive"),
        pytest.param(None, Decimal("NaN"), "annual", True, id="invalid-materialized"),
        pytest.param(None, None, "bullet", True, id="missing-bullet"),
        pytest.param(Decimal("0"), None, "bullet", False, id="observed-zero-bullet"),
    ],
)
def test_par_duration_warning_tracks_used_yield_and_materialized_duration(
    ytm, materialized, interest_mode, uses_par
):
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key = {
        "instrument_code": "SYNTHETIC-PAR-CASE",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }
    asset = {**key, "position_scope": "asset", "market_value_amount": Decimal("100")}
    analytics = {
        **key,
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2028, 1, 1),
        "coupon_rate": Decimal("0.03"),
        "interest_mode": interest_mode,
        "ytm": ytm,
        "macaulay_duration": materialized,
    }
    original_asset, original_analytics = asset.copy(), analytics.copy()

    enriched = service_mod._attach_macaulay_duration([asset], [analytics])
    par_warnings = [
        warning
        for warning in service_mod._cashflow_projection_quality_disclosures(enriched)["warnings"]
        if "par assumption" in warning
    ]

    assert asset == original_asset
    assert analytics == original_analytics
    if uses_par:
        assert enriched[0]["_par_duration_assumption_used"] is True
    else:
        assert enriched[0]["_par_duration_assumption_used"] is False
    assert len(par_warnings) == int(uses_par)
    if uses_par:
        assert enriched[0]["duration_quality_flag"] == "ytm_par_fallback"
        assert "market_value=100" in par_warnings[0]
    elif materialized is not None and materialized.is_finite():
        assert enriched[0]["macaulay_duration"] == materialized


def test_par_duration_warning_respects_scope_coverage_and_existing_quality():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )

    def pair(code, *, scope="asset", market_value=Decimal("100"), maturity=True, flag=None):
        key = {
            "instrument_code": code,
            "portfolio_name": "P1",
            "cost_center": "C1",
            "currency_code": "CNY",
        }
        asset = {
            **key,
            "position_scope": scope,
            "market_value": market_value,
            "market_value_amount": Decimal("100"),
        }
        analytics = {
            **key,
            "report_date": date(2026, 1, 1),
            "maturity_date": date(2028, 1, 1) if maturity else None,
            "coupon_rate": Decimal("0.03"),
            "interest_mode": "annual",
            "ytm": None,
            "macaulay_duration": None,
        }
        if flag is not None:
            analytics["duration_quality_flag"] = flag
        return asset, analytics

    cases = [
        pair("USED-PAR"),
        pair("ZERO-MARKET", market_value=Decimal("0")),
        pair("NEGATIVE-MARKET", market_value=Decimal("-5")),
        pair("LIABILITY", scope="liability"),
        pair("NO-MATURITY", maturity=False),
        pair("UNAVAILABLE", flag="maturity_unavailable"),
        pair("OTHER-QUALITY", flag="floating_rate_fixed_coupon_proxy"),
    ]
    matured_asset, matured_analytics = pair("MATURED")
    matured_analytics["maturity_date"] = date(2025, 12, 31)
    cases.append((matured_asset, matured_analytics))
    unmatched_asset, _ = pair("NO-MATCH")
    reused_asset, _ = pair("REUSED-INPUT")
    reused_asset["_par_duration_assumption_used"] = True
    rows = [asset for asset, _ in cases] + [unmatched_asset, reused_asset]
    analytics_rows = [analytics for _, analytics in cases]

    enriched = service_mod._attach_macaulay_duration(rows, analytics_rows)
    by_code = {row["instrument_code"]: row for row in enriched}
    par_warnings = [
        warning
        for warning in service_mod._cashflow_projection_quality_disclosures(enriched)["warnings"]
        if "par assumption" in warning
    ]

    assert len(par_warnings) == 1
    assert "2 asset rows with market_value=200" in par_warnings[0]
    assert by_code["OTHER-QUALITY"]["duration_quality_flag"] == "floating_rate_fixed_coupon_proxy"
    assert by_code["OTHER-QUALITY"]["_par_duration_assumption_used"] is True
    assert by_code["UNAVAILABLE"]["duration_quality_flag"] == "maturity_unavailable"
    assert by_code["UNAVAILABLE"]["_par_duration_assumption_used"] is False
    assert by_code["MATURED"]["_par_duration_assumption_used"] is False
    assert "macaulay_duration" not in by_code["NO-MATURITY"]
    assert "_par_duration_assumption_used" not in by_code["LIABILITY"]
    assert "_par_duration_assumption_used" not in by_code["NO-MATCH"]
    assert by_code["REUSED-INPUT"]["_par_duration_assumption_used"] is False
    assert reused_asset["_par_duration_assumption_used"] is True


def test_duration_fallback_uses_single_cashflow_path_for_bullet_bonds():
    """bullet（到期一次还本付息）唯一现金流在到期日：Macaulay 恒等于剩余年限。

    修复前该路径按年付多期贴现（coupon_frequency_per_year("bullet") == 1），
    把 Macaulay 拉向虚构的中途票息时点、低估久期；现与 bond_analytics.engine
    的 single_cashflow_at_maturity 口径对齐。
    """
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    bond_duration_mod = load_module(
        "backend.app.core_finance.bond_duration",
        "backend/app/core_finance/bond_duration.py",
    )
    report_date = date(2026, 1, 1)
    maturity_date = date(2031, 1, 1)
    row = {
        "report_date": report_date,
        "maturity_date": maturity_date,
        "instrument_code": "BOND-BULLET-001",
        "coupon_rate": Decimal("0.03"),
        "ytm": Decimal("0.035"),
        "interest_mode": "到期一次还本付息",
        "macaulay_duration": None,
    }

    expected_remaining_years = (
        Decimal((maturity_date - report_date).days) / Decimal("365")
    )
    legacy_annual_multi_period = bond_duration_mod.estimate_duration(
        maturity_date,
        report_date,
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.035"),
        bond_code="BOND-BULLET-001",
        coupon_frequency=1,
    )

    assert service_mod._recompute_macaulay_duration(row) == expected_remaining_years
    assert legacy_annual_multi_period < expected_remaining_years
