from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal

import duckdb
import pytest
from backend.app.governance.settings import get_settings
from backend.app.repositories.yield_curve_repo import ensure_yield_curve_tables
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers import load_module

REPORT_DATE = date(2026, 4, 10)


def _core_module():
    return load_module(
        "backend.app.core_finance.macro_bond_linkage",
        "backend/app/core_finance/macro_bond_linkage.py",
    )


def _route_client() -> TestClient:
    route_module = load_module(
        "backend.app.api.routes.macro_bond_linkage",
        "backend/app/api/routes/macro_bond_linkage.py",
    )
    app = FastAPI()
    app.include_router(route_module.router)
    return TestClient(app)


def _service_module():
    return load_module(
        "backend.app.services.macro_bond_linkage_service",
        "backend/app/services/macro_bond_linkage_service.py",
    )


def _seed_macro_and_curve_inputs(
    duckdb_path: str,
    *,
    macro_points: int,
    rising_rates: bool,
) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
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
        ensure_yield_curve_tables(conn)
        conn.execute(
            """
            create table if not exists fact_formal_risk_tensor_daily (
              report_date varchar,
              portfolio_dv01 decimal(24, 8),
              krd_1y decimal(24, 8),
              krd_3y decimal(24, 8),
              krd_5y decimal(24, 8),
              krd_7y decimal(24, 8),
              krd_10y decimal(24, 8),
              krd_30y decimal(24, 8),
              cs01 decimal(24, 8),
              portfolio_convexity decimal(24, 8),
              portfolio_modified_duration decimal(24, 8),
              issuer_concentration_hhi decimal(24, 8),
              issuer_top5_weight decimal(24, 8),
              asset_cashflow_30d decimal(24, 8),
              asset_cashflow_90d decimal(24, 8),
              liability_cashflow_30d decimal(24, 8),
              liability_cashflow_90d decimal(24, 8),
              liquidity_gap_30d decimal(24, 8),
              liquidity_gap_90d decimal(24, 8),
              liquidity_gap_30d_ratio decimal(24, 8),
              total_market_value decimal(24, 8),
              bond_count integer,
              quality_flag varchar,
              warnings_json varchar,
              source_version varchar,
              upstream_source_version varchar,
              rule_version varchar,
              cache_version varchar,
              trace_id varchar
            )
            """
        )

        macro_series = {
            "EMM00166466": ("中债国债到期收益率:10年", "daily", "pct"),
            "EMM00166462": ("中债国债到期收益率:5年", "daily", "pct"),
            "EMM00166458": ("中债国债到期收益率:1年", "daily", "pct"),
            "EMM00166252": ("SHIBOR:隔夜", "daily", "pct"),
            "EMM00166253": ("SHIBOR:1周", "daily", "pct"),
            "EMM00166216": ("银行间质押式回购加权利率", "daily", "pct"),
            "EMM00008445": ("工业增加值:当月同比", "monthly", "pct"),
            "EMM00619381": ("中国:GDP:现价:当季值", "quarterly", "cny"),
            "EMM00072301": ("CPI:当月同比", "monthly", "pct"),
        }
        conn.executemany(
            """
            insert into phase1_macro_vendor_catalog (
              series_id, series_name, vendor_name, vendor_version, frequency, unit
            ) values (?, ?, ?, ?, ?, ?)
            """,
            [
                (series_id, series_name, "choice", "vv_choice_macro_test", frequency, unit)
                for series_id, (series_name, frequency, unit) in macro_series.items()
            ],
        )

        start_date = REPORT_DATE - timedelta(days=macro_points - 1)
        macro_rows: list[tuple[object, ...]] = []
        for offset in range(macro_points):
            trade_date = (start_date + timedelta(days=offset)).isoformat()
            progress = offset / max(macro_points - 1, 1)
            rate_shift = 0.35 * progress if rising_rates else 0.35 * (1 - progress)
            liquidity_shift = 0.30 * progress if rising_rates else -0.30 * progress
            growth_shift = 1.2 + (0.3 * progress if rising_rates else -0.3 * progress)
            inflation_shift = 3.2 if rising_rates else 0.8
            rows_for_day = {
                "EMM00166466": 2.10 + rate_shift,
                "EMM00166462": 1.95 + rate_shift * 0.8,
                "EMM00166458": 1.55 + rate_shift * 0.6,
                "EMM00166252": 1.70 + liquidity_shift,
                "EMM00166253": 1.75 + liquidity_shift * 0.9,
                "EMM00166216": 1.80 + liquidity_shift * 0.85,
                "EMM00008445": growth_shift,
                "EMM00619381": 100.0 + growth_shift * 8,
                "EMM00072301": inflation_shift,
            }
            for series_id, value_numeric in rows_for_day.items():
                series_name, frequency, unit = macro_series[series_id]
                macro_rows.append(
                    (
                        series_id,
                        series_name,
                        trade_date,
                        value_numeric,
                        frequency,
                        unit,
                        "sv_macro_linkage_test",
                        "vv_choice_macro_test",
                        "rv_macro_linkage_test",
                        "ok",
                        "macro-linkage-run",
                    )
                )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            macro_rows,
        )

        curve_rows: list[tuple[object, ...]] = []
        for offset in range(macro_points):
            trade_date = (start_date + timedelta(days=offset)).isoformat()
            progress = offset / max(macro_points - 1, 1)
            treasury_base = 2.20 + (0.30 * progress if rising_rates else 0.30 * (1 - progress))
            curve_rows.extend(
                [
                    (trade_date, "treasury", "1Y", treasury_base - 0.70, "choice", "vv_curve_test", "sv_curve_test", "rv_curve_test"),
                    (trade_date, "treasury", "5Y", treasury_base - 0.15, "choice", "vv_curve_test", "sv_curve_test", "rv_curve_test"),
                    (trade_date, "treasury", "10Y", treasury_base, "choice", "vv_curve_test", "sv_curve_test", "rv_curve_test"),
                    (trade_date, "cdb", "5Y", treasury_base + 0.18, "choice", "vv_curve_test", "sv_curve_test", "rv_curve_test"),
                    (trade_date, "aaa_credit", "3Y", treasury_base + 0.42, "choice", "vv_curve_test", "sv_curve_test", "rv_curve_test"),
                ]
            )
        conn.executemany(
            """
            insert into fact_formal_yield_curve_daily values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            curve_rows,
        )

        conn.execute(
            """
            insert into fact_formal_risk_tensor_daily (
              report_date, portfolio_dv01, krd_1y, krd_3y, krd_5y, krd_7y, krd_10y, krd_30y,
              cs01, portfolio_convexity, portfolio_modified_duration, issuer_concentration_hhi, issuer_top5_weight,
              asset_cashflow_30d, asset_cashflow_90d, liability_cashflow_30d, liability_cashflow_90d,
              liquidity_gap_30d, liquidity_gap_90d, liquidity_gap_30d_ratio, total_market_value, bond_count,
              quality_flag, warnings_json, source_version, upstream_source_version, liability_source_version, liability_rule_version,
              rule_version, cache_version, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                REPORT_DATE.isoformat(),
                Decimal("12.50000000"),
                Decimal("1.00000000"),
                Decimal("2.00000000"),
                Decimal("3.00000000"),
                Decimal("2.50000000"),
                Decimal("2.00000000"),
                Decimal("2.00000000"),
                Decimal("8.75000000"),
                Decimal("95.00000000"),
                Decimal("4.25000000"),
                Decimal("0.20000000"),
                Decimal("0.65000000"),
                Decimal("10.00000000"),
                Decimal("12.00000000"),
                Decimal("0"),
                Decimal("0"),
                Decimal("10.00000000"),
                Decimal("12.00000000"),
                Decimal("0.05000000"),
                Decimal("1500.00000000"),
                12,
                "ok",
                "[]",
                "sv_risk_tensor_test",
                "sv_risk_tensor_upstream",
                "",
                "",
                "rv_risk_tensor_test",
                "cv_risk_tensor_test",
                "tr_risk_tensor_test",
            ],
        )
    finally:
        conn.close()


def _seed_choice_market_equity_axes(duckdb_path: str) -> None:
    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        conn.execute(
            """
            create table if not exists choice_market_snapshot (
              series_id varchar,
              series_name varchar,
              vendor_series_code varchar,
              vendor_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        rows = [
            ("CA.CSI300", "沪深300指数收盘价", "000300.SH", "tushare", REPORT_DATE.isoformat(), 4799.6270, "daily", "index"),
            ("CA.CSI300_PCT_CHG", "沪深300指数涨跌幅", "000300.SH", "tushare", REPORT_DATE.isoformat(), 0.6634, "daily", "pct"),
            ("CA.CSI300_PE", "沪深300市盈率", "000300.SH", "tushare", REPORT_DATE.isoformat(), 14.64, "daily", "ratio"),
            (
                "CA.MEGA_CAP_WEIGHT",
                "沪深300前十大权重合计",
                "000300.SH",
                "tushare",
                REPORT_DATE.isoformat(),
                23.5367,
                "daily",
                "pct",
            ),
            (
                "CA.MEGA_CAP_TOP5_WEIGHT",
                "沪深300前五大权重合计",
                "000300.SH",
                "tushare",
                REPORT_DATE.isoformat(),
                15.5320,
                "daily",
                "pct",
            ),
        ]
        conn.executemany(
            """
            insert into choice_market_snapshot values (
              ?, ?, ?, ?, ?, ?, ?, ?, 'sv_landed_equity_axes', 'vv_landed_equity_axes', 'rv_landed_equity_axes', 'run_landed'
            )
            """,
            rows,
        )
    finally:
        conn.close()


def test_pearson_correlation_basic():
    mod = _core_module()

    assert mod.pearson_correlation([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == 1.0
    assert mod.pearson_correlation([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]) == -1.0


def test_lead_lag_detection():
    mod = _core_module()
    start = date(2026, 1, 1)
    macro_values = [math.sin(index / 18.0) for index in range(50)]
    macro_series = {
        "macro_series": [
            (start + timedelta(days=index), value)
            for index, value in enumerate(macro_values)
        ]
    }
    yield_series = {
        "treasury_10Y": [
            (start + timedelta(days=index), macro_values[index - 5] if index >= 5 else 0.0)
            for index in range(50)
        ]
    }

    results = mod.compute_macro_bond_correlations(
        macro_series,
        yield_series,
        lookback_days=90,
    )

    assert len(results) == 1
    assert results[0].target_yield == "treasury_10Y"
    assert results[0].lead_lag_days == 5
    assert results[0].direction == "positive"
    assert results[0].correlation_3m is not None
    assert results[0].correlation_3m > 0.8
    assert results[0].sample_size is not None and results[0].sample_size >= 2
    assert results[0].lead_lag_confidence is not None
    assert results[0].winsorized is False
    assert results[0].zscore_applied is False


def test_alignment_modes_differ_for_low_frequency_macro_vs_daily_yield():
    mod = _core_module()
    start = date(2026, 1, 1)
    macro_series = {
        "macro_series": [
            (date(2026, 1, 1), 1.0),
            (date(2026, 2, 1), 2.0),
            (date(2026, 3, 1), 3.0),
        ]
    }
    yield_series = {
        "treasury_10Y": [
            (
                start + timedelta(days=offset),
                0.0 if offset in {0, 31, 59} else (1.0 if offset < 31 else 2.0 if offset < 59 else 3.0),
            )
            for offset in range(90)
        ]
    }

    conservative = mod.compute_macro_bond_correlations(
        macro_series,
        yield_series,
        lookback_days=120,
        alignment_mode="conservative",
    )
    market_timing = mod.compute_macro_bond_correlations(
        macro_series,
        yield_series,
        lookback_days=120,
        alignment_mode="market_timing",
    )

    assert len(conservative) == 1
    assert len(market_timing) == 1
    assert conservative[0].correlation_3m is None
    assert market_timing[0].correlation_3m is not None
    assert market_timing[0].correlation_3m > 0.9
    assert market_timing[0].direction == "positive"


def test_compute_macro_bond_correlations_is_scale_invariant_without_zscore_flag():
    mod = _core_module()
    start = date(2026, 1, 1)
    macro_values = [float(index) for index in range(1, 31)]
    macro_series = {
        "macro_series": [
            (start + timedelta(days=index), value)
            for index, value in enumerate(macro_values)
        ]
    }
    small_scale = mod.compute_macro_bond_correlations(
        macro_series,
        {
            "treasury_10Y": [
                (start + timedelta(days=index), value * 2.0 + 5.0)
                for index, value in enumerate(macro_values)
            ]
        },
        lookback_days=60,
    )
    large_scale = mod.compute_macro_bond_correlations(
        macro_series,
        {
            "treasury_10Y": [
                (start + timedelta(days=index), value * 200.0 + 500.0)
                for index, value in enumerate(macro_values)
            ]
        },
        lookback_days=60,
    )

    assert len(small_scale) == 1
    assert len(large_scale) == 1
    assert small_scale[0].correlation_3m == pytest.approx(large_scale[0].correlation_3m)
    assert small_scale[0].correlation_6m == pytest.approx(large_scale[0].correlation_6m)
    assert small_scale[0].correlation_1y == pytest.approx(large_scale[0].correlation_1y)
    assert small_scale[0].lead_lag_days == large_scale[0].lead_lag_days == 0


def test_winsorization_improves_outlier_distorted_correlation():
    mod = _core_module()
    start = date(2026, 1, 1)
    macro_values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    macro_series = {
        "macro_series": [
            (start + timedelta(days=index), value)
            for index, value in enumerate(macro_values)
        ]
    }
    yield_series = {
        "treasury_10Y": [
            (start + timedelta(days=index), value)
            for index, value in enumerate([1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
        ]
    }

    raw = mod.compute_macro_bond_correlations(
        macro_series,
        yield_series,
        lookback_days=30,
    )
    winsorized = mod.compute_macro_bond_correlations(
        macro_series,
        yield_series,
        lookback_days=30,
        winsorize_tail_fraction=0.2,
    )

    assert len(raw) == 1
    assert len(winsorized) == 1
    assert raw[0].correlation_3m is not None
    assert winsorized[0].correlation_3m is not None
    assert winsorized[0].correlation_3m > raw[0].correlation_3m
    assert winsorized[0].correlation_3m == 1.0
    assert raw[0].winsorized is False
    assert winsorized[0].winsorized is True


@pytest.mark.parametrize("tail_fraction", [float("nan"), float("inf"), -0.01, 0.0, 0.5, 0.6])
def test_winsorize_tail_fraction_validation_rejects_invalid_values(tail_fraction: float):
    mod = _core_module()
    start = date(2026, 1, 1)
    macro_series = {
        "macro_series": [
            (start + timedelta(days=index), float(index + 1))
            for index in range(6)
        ]
    }
    yield_series = {
        "treasury_10Y": [
            (start + timedelta(days=index), float(index + 2))
            for index in range(6)
        ]
    }

    with pytest.raises(ValueError, match="winsorize_tail_fraction must be finite and satisfy 0 < tail_fraction < 0.5"):
        mod.compute_macro_bond_correlations(
            macro_series,
            yield_series,
            lookback_days=30,
            winsorize_tail_fraction=tail_fraction,
        )


def test_winsorize_tail_fraction_accepts_strict_upper_boundary_margin():
    mod = _core_module()
    start = date(2026, 1, 1)
    macro_series = {
        "macro_series": [
            (start + timedelta(days=index), float(index + 1))
            for index in range(6)
        ]
    }
    yield_series = {
        "treasury_10Y": [
            (start + timedelta(days=index), float(index + 1))
            for index in range(6)
        ]
    }

    results = mod.compute_macro_bond_correlations(
        macro_series,
        yield_series,
        lookback_days=30,
        winsorize_tail_fraction=0.499,
    )

    assert len(results) == 1
    assert results[0].correlation_3m == 1.0


def test_lead_lag_confidence_weakens_with_smaller_sample_or_ambiguous_runner_up():
    mod = _core_module()
    start = date(2026, 1, 1)

    def build_series(length: int, ambiguous: bool = False) -> tuple[dict[date, float], dict[date, float]]:
        macro_values = [
            math.sin(index / 4.3) + 0.35 * math.cos(index / 2.1)
            for index in range(length)
        ]
        macro_map = {
            start + timedelta(days=index): value
            for index, value in enumerate(macro_values)
        }
        target_map: dict[date, float] = {}
        for index in range(length):
            current_date = start + timedelta(days=index)
            lag_5 = macro_values[index - 5] if index >= 5 else 0.0
            lag_6 = macro_values[index - 6] if index >= 6 else lag_5
            target_map[current_date] = (0.55 * lag_5 + 0.45 * lag_6) if ambiguous else lag_5
        return macro_map, target_map

    high_macro, high_target = build_series(120)
    small_macro, small_target = build_series(18)
    ambiguous_macro, ambiguous_target = build_series(120, ambiguous=True)

    high_confidence = mod._best_lead_lag_details(high_macro, high_target)
    small_sample_confidence = mod._best_lead_lag_details(small_macro, small_target)
    ambiguous_confidence = mod._best_lead_lag_details(ambiguous_macro, ambiguous_target)

    assert high_confidence["lag_days"] == 5
    assert 0 <= high_confidence["confidence"] <= 1
    assert small_sample_confidence["confidence"] < high_confidence["confidence"]
    assert ambiguous_confidence["confidence"] < high_confidence["confidence"]


def test_environment_score_uses_continuous_rate_signal_below_legacy_threshold():
    mod = _core_module()
    start = REPORT_DATE - timedelta(days=89)
    history = {
        "EMM00166466": [(start, 2.00), (REPORT_DATE - timedelta(days=30), 2.06), (REPORT_DATE, 2.12)],
        "EMM00166462": [(start, 1.80), (REPORT_DATE - timedelta(days=30), 1.85), (REPORT_DATE, 1.91)],
        "EMM00166458": [(start, 1.55), (REPORT_DATE - timedelta(days=30), 1.60), (REPORT_DATE, 1.66)],
        "EMM00166252": [(start, 1.80), (REPORT_DATE, 1.80)],
        "EMM00166253": [(start, 1.82), (REPORT_DATE, 1.82)],
        "EMM00166216": [(start, 1.84), (REPORT_DATE, 1.84)],
        "EMM00008445": [(start, 1.2), (REPORT_DATE, 1.2)],
        "EMM00619381": [(start, 100.0), (REPORT_DATE, 100.0)],
        "EMM00072301": [(REPORT_DATE, 2.0)],
    }
    latest = {series_id: points[-1] for series_id, points in history.items()}

    score = mod.compute_macro_environment_score(latest, history, lookback_days=90)

    assert score.rate_direction == "rising"
    assert score.rate_direction_score > 0
    assert score.rate_direction_score != 0


def test_environment_score_liquidity_is_robust_to_baseline_outlier():
    mod = _core_module()
    start = REPORT_DATE - timedelta(days=24)
    baseline_dates = [start + timedelta(days=index) for index in range(20)]
    recent_dates = [REPORT_DATE - timedelta(days=4 - index) for index in range(5)]

    def build_liquidity_history(base_value: float, outlier_value: float, recent_value: float):
        values = [(current_date, base_value) for current_date in baseline_dates]
        values.append((REPORT_DATE - timedelta(days=5), outlier_value))
        values.extend((current_date, recent_value) for current_date in recent_dates)
        return values

    history = {
        "EMM00166466": [(REPORT_DATE - timedelta(days=90), 2.0), (REPORT_DATE, 2.0)],
        "EMM00166462": [(REPORT_DATE - timedelta(days=90), 1.8), (REPORT_DATE, 1.8)],
        "EMM00166458": [(REPORT_DATE - timedelta(days=90), 1.6), (REPORT_DATE, 1.6)],
        "EMM00166252": build_liquidity_history(1.00, 10.0, 1.40),
        "EMM00166253": build_liquidity_history(1.05, 10.5, 1.45),
        "EMM00166216": build_liquidity_history(1.10, 11.0, 1.50),
        "EMM00008445": [(REPORT_DATE - timedelta(days=30), 1.2), (REPORT_DATE, 1.2)],
        "EMM00619381": [(REPORT_DATE - timedelta(days=90), 100.0), (REPORT_DATE, 100.0)],
        "EMM00072301": [(REPORT_DATE, 2.0)],
    }
    latest = {series_id: points[-1] for series_id, points in history.items()}

    score = mod.compute_macro_environment_score(latest, history, lookback_days=90)

    assert score.liquidity_score < 0


def test_environment_score_contributing_factors_include_method_metadata():
    mod = _core_module()
    start = REPORT_DATE - timedelta(days=89)
    history = {
        "EMM00166466": [(start, 2.00), (REPORT_DATE - timedelta(days=30), 2.08), (REPORT_DATE, 2.16)],
        "EMM00166462": [(start, 1.80), (REPORT_DATE - timedelta(days=30), 1.88), (REPORT_DATE, 1.96)],
        "EMM00166458": [(start, 1.50), (REPORT_DATE - timedelta(days=30), 1.58), (REPORT_DATE, 1.66)],
        "EMM00166252": [(start, 1.70), (REPORT_DATE, 1.90)],
        "EMM00166253": [(start, 1.72), (REPORT_DATE, 1.94)],
        "EMM00166216": [(start, 1.76), (REPORT_DATE, 1.98)],
        "EMM00008445": [(start, 1.2), (REPORT_DATE, 1.5)],
        "EMM00619381": [(start, 100.0), (REPORT_DATE, 104.0)],
        "EMM00072301": [(REPORT_DATE, 2.2)],
    }
    latest = {series_id: points[-1] for series_id, points in history.items()}

    score = mod.compute_macro_environment_score(latest, history, lookback_days=90)

    assert score.contributing_factors
    rate_factor = next(
        factor for factor in score.contributing_factors if factor["category"] == "rate"
    )
    assert "scoring_method" in rate_factor
    assert "observation_count" in rate_factor
    assert "winsorized" in rate_factor
    assert "normalized_signal" in rate_factor


def test_environment_score_rising_rates():
    mod = _core_module()
    start = REPORT_DATE - timedelta(days=89)
    history = {
        "EMM00166466": [(start, 2.00), (REPORT_DATE, 2.35)],
        "EMM00166462": [(start, 1.80), (REPORT_DATE, 2.08)],
        "EMM00166458": [(start, 1.50), (REPORT_DATE, 1.74)],
        "EMM00166252": [(start, 1.70), (REPORT_DATE - timedelta(days=1), 1.72), (REPORT_DATE, 2.10)],
        "EMM00166253": [(start, 1.72), (REPORT_DATE - timedelta(days=1), 1.75), (REPORT_DATE, 2.08)],
        "EMM00166216": [(start, 1.76), (REPORT_DATE - timedelta(days=1), 1.80), (REPORT_DATE, 2.12)],
        "EMM00008445": [(start, 1.2), (REPORT_DATE, 1.8)],
        "EMM00619381": [(start, 100.0), (REPORT_DATE, 108.0)],
        "EMM00072301": [(REPORT_DATE, 3.2)],
    }
    latest = {series_id: points[-1] for series_id, points in history.items()}

    score = mod.compute_macro_environment_score(latest, history, lookback_days=90)

    assert score.report_date == REPORT_DATE
    assert score.rate_direction == "rising"
    assert score.rate_direction_score > 0
    assert score.composite_score > 0.3
    assert "缩短久期" in score.signal_description


def test_environment_score_falling_rates():
    mod = _core_module()
    start = REPORT_DATE - timedelta(days=89)
    history = {
        "EMM00166466": [(start, 2.40), (REPORT_DATE, 2.05)],
        "EMM00166462": [(start, 2.15), (REPORT_DATE, 1.85)],
        "EMM00166458": [(start, 1.80), (REPORT_DATE, 1.55)],
        "EMM00166252": [(start, 1.95), (REPORT_DATE - timedelta(days=1), 1.88), (REPORT_DATE, 1.45)],
        "EMM00166253": [(start, 1.98), (REPORT_DATE - timedelta(days=1), 1.90), (REPORT_DATE, 1.48)],
        "EMM00166216": [(start, 2.02), (REPORT_DATE - timedelta(days=1), 1.93), (REPORT_DATE, 1.50)],
        "EMM00008445": [(start, 1.8), (REPORT_DATE, 1.1)],
        "EMM00619381": [(start, 108.0), (REPORT_DATE, 101.0)],
        "EMM00072301": [(REPORT_DATE, 0.8)],
    }
    latest = {series_id: points[-1] for series_id, points in history.items()}

    score = mod.compute_macro_environment_score(latest, history, lookback_days=90)

    assert score.rate_direction == "falling"
    assert score.rate_direction_score < 0
    assert score.composite_score < -0.3
    assert "拉长久期" in score.signal_description


def test_portfolio_impact_estimation():
    mod = _core_module()
    macro_environment = mod.MacroEnvironmentScore(
        report_date=REPORT_DATE,
        rate_direction="rising",
        rate_direction_score=0.8,
        liquidity_score=-0.5,
        growth_score=0.5,
        inflation_score=0.0,
        composite_score=0.37,
        signal_description="test",
        contributing_factors=[],
        warnings=[],
    )

    impact = mod.estimate_macro_impact_on_portfolio(
        macro_environment=macro_environment,
        portfolio_dv01=Decimal("10"),
        portfolio_cs01=Decimal("5"),
        portfolio_market_value=Decimal("1000"),
    )

    assert impact["estimated_rate_change_bps"] == Decimal("24.0")
    assert impact["estimated_spread_widening_bps"] == Decimal("10.0")
    assert impact["estimated_rate_pnl_impact"] == Decimal("-240.0")
    assert impact["estimated_spread_pnl_impact"] == Decimal("-50.0")
    assert impact["total_estimated_impact"] == Decimal("-290.0")


def test_target_identity_parsing_preserves_multiword_family():
    mod = _service_module()

    assert mod._split_target_identity("credit_spread_3Y") == ("credit_spread", "3Y")
    assert mod._split_target_identity("treasury_10Y") == ("treasury", "10Y")
    assert mod._split_target_identity("treasury") == ("treasury", None)


def test_api_returns_envelope(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-linkage.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=True)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    client = _route_client()
    response = client.get(
        "/api/macro-bond-linkage/analysis",
        params={"report_date": REPORT_DATE.isoformat()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["result_kind"] == "macro_bond_linkage.analysis"
    assert payload["result"]["report_date"] == REPORT_DATE.isoformat()
    assert "environment_score" in payload["result"]
    assert "portfolio_impact" in payload["result"]
    assert len(payload["result"]["top_correlations"]) > 0
    first_correlation = payload["result"]["top_correlations"][0]
    assert "target_yield" in first_correlation
    assert "target_family" in first_correlation
    assert "target_tenor" in first_correlation
    assert first_correlation["target_yield"] == (
        f"{first_correlation['target_family']}_{first_correlation['target_tenor']}"
    )
    assert payload["result"]["warnings"] == []
    assert "method_variants" in payload["result"]
    assert payload["result"]["top_correlations"] == payload["result"]["method_variants"]["conservative"][
        "top_correlations"
    ]
    assert payload["result"]["method_variants"]["conservative"]["method_meta"]["variant"] == "conservative"
    assert payload["result"]["method_variants"]["market_timing"]["method_meta"]["variant"] == "market_timing"

    get_settings.cache_clear()


def test_api_cross_layer_exposes_correlation_statistical_metadata(tmp_path, monkeypatch):
    """Schema → service → HTTP：相关性元数据字段在 API JSON 中可见。"""
    duckdb_path = tmp_path / "macro-bond-cross-layer.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=True)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    client = _route_client()
    response = client.get(
        "/api/macro-bond-linkage/analysis",
        params={"report_date": REPORT_DATE.isoformat()},
    )
    assert response.status_code == 200
    payload = response.json()
    result = payload["result"]
    assert result["top_correlations"]
    meta_keys = (
        "alignment_mode",
        "sample_size",
        "winsorized",
        "zscore_applied",
        "lead_lag_confidence",
        "effective_observation_span_days",
    )
    for track in ("conservative", "market_timing"):
        rows = result["method_variants"][track]["top_correlations"]
        assert rows, track
        row = rows[0]
        for key in meta_keys:
            assert key in row
        assert row["alignment_mode"] == track
    assert result["top_correlations"][0]["alignment_mode"] == "conservative"
    assert result["top_correlations"] == result["method_variants"]["conservative"]["top_correlations"]
    top0 = result["top_correlations"][0]
    assert top0["sample_size"] is not None and top0["sample_size"] >= 2
    assert top0["lead_lag_confidence"] is not None
    assert top0["zscore_applied"] is False
    assert isinstance(top0["winsorized"], bool)

    get_settings.cache_clear()


def test_api_exposes_investment_research_additive_fields(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-research.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=True)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    payload = _route_client().get(
        "/api/macro-bond-linkage/analysis",
        params={"report_date": REPORT_DATE.isoformat()},
    ).json()

    assert "research_views" in payload["result"]
    assert "transmission_axes" in payload["result"]
    assert {"duration", "curve", "credit", "instrument"} <= {
        row["key"] for row in payload["result"]["research_views"]
    }

    get_settings.cache_clear()


def test_macro_bond_linkage_marks_missing_equity_axes_as_pending_signal(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-pending-signal.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=True)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_ENABLE_TUSHARE_RESEARCH_AXES", "1")
    get_settings.cache_clear()

    payload = _route_client().get(
        "/api/macro-bond-linkage/analysis",
        params={"report_date": REPORT_DATE.isoformat()},
    ).json()["result"]

    axes = {row["axis_key"]: row for row in payload["transmission_axes"]}
    assert axes["equity_bond_spread"]["status"] == "pending_signal"
    assert axes["mega_cap_equities"]["status"] == "pending_signal"

    get_settings.cache_clear()


def test_macro_bond_linkage_reads_landed_equity_axes_with_live_env_ignored(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-landed-equity-axes.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=False)
    _seed_choice_market_equity_axes(str(duckdb_path))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_ENABLE_TUSHARE_RESEARCH_AXES", "1")
    get_settings.cache_clear()

    svc = _service_module()

    payload = svc.get_macro_bond_linkage(REPORT_DATE)["result"]

    axes = {row["axis_key"]: row for row in payload["transmission_axes"]}
    assert axes["equity_bond_spread"]["status"] == "ready"
    assert axes["mega_cap_equities"]["status"] == "ready"

    get_settings.cache_clear()


def test_macro_bond_linkage_emits_supported_research_views(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-research-views.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=False)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    payload = _route_client().get(
        "/api/macro-bond-linkage/analysis",
        params={"report_date": REPORT_DATE.isoformat()},
    ).json()["result"]

    views = {row["key"]: row for row in payload["research_views"]}
    assert views["duration"]["status"] == "ready"
    assert views["curve"]["status"] == "ready"
    assert views["credit"]["status"] == "ready"
    assert views["instrument"]["status"] == "ready"
    assert views["duration"]["affected_targets"] == ["rates", "ncd", "high_grade_credit"]
    assert views["curve"]["affected_targets"] == ["rates", "ncd"]
    assert views["credit"]["affected_targets"] == ["high_grade_credit"]
    assert views["instrument"]["affected_targets"] == ["rates", "ncd", "high_grade_credit"]

    get_settings.cache_clear()


def test_macro_bond_linkage_promotes_equity_axes_to_ready_when_landed_signals_are_available(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "macro-bond-landed-equity-ready.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=False)
    _seed_choice_market_equity_axes(str(duckdb_path))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_ENABLE_TUSHARE_RESEARCH_AXES", "1")
    get_settings.cache_clear()

    svc = _service_module()

    payload = svc.get_macro_bond_linkage(REPORT_DATE)["result"]
    axes = {row["axis_key"]: row for row in payload["transmission_axes"]}
    assert axes["equity_bond_spread"]["status"] == "ready"
    assert axes["equity_bond_spread"]["stance"] == "restrictive"
    assert axes["mega_cap_equities"]["status"] == "ready"
    assert axes["mega_cap_equities"]["stance"] == "restrictive"

    get_settings.cache_clear()


def test_macro_bond_linkage_landed_equity_axes_flow_into_research_view_evidence(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-landed-equity-view.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=False)
    _seed_choice_market_equity_axes(str(duckdb_path))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_ENABLE_TUSHARE_RESEARCH_AXES", "1")
    get_settings.cache_clear()

    svc = _service_module()

    payload = svc.get_macro_bond_linkage(REPORT_DATE)["result"]
    views = {row["key"]: row for row in payload["research_views"]}
    assert any("股债：" in item for item in views["duration"]["evidence"])
    assert any("股债：" in item for item in views["credit"]["evidence"])
    assert any("大票结构：" in item for item in views["credit"]["evidence"])
    assert any("股债：" in item for item in views["instrument"]["evidence"])
    assert any("大票结构：" in item for item in views["instrument"]["evidence"])
    assert "股" in views["duration"]["summary"]
    assert "股" in views["credit"]["summary"]
    assert "2026-04-10" in next(
        row for row in payload["transmission_axes"] if row["axis_key"] == "mega_cap_equities"
    )["summary"]

    get_settings.cache_clear()


def test_equity_bond_spread_axis_uses_explicit_rule_table_thresholds():
    mod = _core_module()

    assert [rule.stance for rule in mod.EQUITY_BOND_SPREAD_RULES] == [
        "restrictive",
        "conflicted",
        "supportive",
    ]

    restrictive = mod._build_equity_bond_spread_axis(
        mod.EquityBondSpreadSignal(
            trade_date=REPORT_DATE,
            index_code="000300.SH",
            index_close=4800.0,
            index_pct_change=0.35,
            pe=14.0,
            earnings_yield_pct=7.14,
            bond_yield_pct=1.90,
            spread_pct=5.24,
        )
    )
    conflicted = mod._build_equity_bond_spread_axis(
        mod.EquityBondSpreadSignal(
            trade_date=REPORT_DATE,
            index_code="000300.SH",
            index_close=4700.0,
            index_pct_change=-0.30,
            pe=14.0,
            earnings_yield_pct=7.14,
            bond_yield_pct=1.90,
            spread_pct=5.24,
        )
    )
    supportive = mod._build_equity_bond_spread_axis(
        mod.EquityBondSpreadSignal(
            trade_date=REPORT_DATE,
            index_code="000300.SH",
            index_close=4600.0,
            index_pct_change=0.05,
            pe=28.0,
            earnings_yield_pct=3.57,
            bond_yield_pct=1.90,
            spread_pct=1.67,
        )
    )
    neutral = mod._build_equity_bond_spread_axis(
        mod.EquityBondSpreadSignal(
            trade_date=REPORT_DATE,
            index_code="000300.SH",
            index_close=4700.0,
            index_pct_change=0.10,
            pe=18.0,
            earnings_yield_pct=5.56,
            bond_yield_pct=1.90,
            spread_pct=3.66,
        )
    )

    assert restrictive.stance == "restrictive"
    assert conflicted.stance == "conflicted"
    assert supportive.stance == "supportive"
    assert neutral.stance == "neutral"


def test_duration_summary_mentions_equity_when_supportive_equity_axis_promotes_bullish_stance():
    mod = _core_module()

    view = mod._build_duration_view(
        mod.MacroEnvironmentScore(
            report_date=REPORT_DATE,
            rate_direction="neutral",
            rate_direction_score=0.0,
            liquidity_score=0.0,
            growth_score=0.0,
            inflation_score=0.0,
            composite_score=0.0,
            signal_description="neutral setup",
            contributing_factors=[],
            warnings=[],
        ),
        {
            "global_rates": mod.MacroBondTransmissionAxisResult(
                axis_key="global_rates",
                status="ready",
                stance="neutral",
                summary="global neutral",
                impacted_views=["duration"],
                required_series_ids=[],
                warnings=[],
            ),
            "liquidity": mod.MacroBondTransmissionAxisResult(
                axis_key="liquidity",
                status="ready",
                stance="neutral",
                summary="liquidity neutral",
                impacted_views=["duration"],
                required_series_ids=[],
                warnings=[],
            ),
            "equity_bond_spread": mod.MacroBondTransmissionAxisResult(
                axis_key="equity_bond_spread",
                status="ready",
                stance="supportive",
                summary="equity supportive",
                impacted_views=["duration"],
                required_series_ids=[],
                warnings=[],
            ),
            "commodities_inflation": mod.MacroBondTransmissionAxisResult(
                axis_key="commodities_inflation",
                status="ready",
                stance="neutral",
                summary="inflation neutral",
                impacted_views=["duration"],
                required_series_ids=[],
                warnings=[],
            ),
            "mega_cap_equities": mod.MacroBondTransmissionAxisResult(
                axis_key="mega_cap_equities",
                status="pending_signal",
                stance="neutral",
                summary="pending",
                impacted_views=["instrument"],
                required_series_ids=[],
                warnings=[],
            ),
        },
        [],
    )

    assert view.stance == "bullish"
    assert "股债" in view.summary


def test_duration_summary_does_not_overattribute_to_equity_when_global_rates_already_make_it_bullish():
    mod = _core_module()

    view = mod._build_duration_view(
        mod.MacroEnvironmentScore(
            report_date=REPORT_DATE,
            rate_direction="falling",
            rate_direction_score=-0.4,
            liquidity_score=0.2,
            growth_score=0.0,
            inflation_score=0.0,
            composite_score=-0.1,
            signal_description="supportive rates",
            contributing_factors=[],
            warnings=[],
        ),
        {
            "global_rates": mod.MacroBondTransmissionAxisResult(
                axis_key="global_rates",
                status="ready",
                stance="supportive",
                summary="global supportive",
                impacted_views=["duration"],
                required_series_ids=[],
                warnings=[],
            ),
            "liquidity": mod.MacroBondTransmissionAxisResult(
                axis_key="liquidity",
                status="ready",
                stance="neutral",
                summary="liquidity neutral",
                impacted_views=["duration"],
                required_series_ids=[],
                warnings=[],
            ),
            "equity_bond_spread": mod.MacroBondTransmissionAxisResult(
                axis_key="equity_bond_spread",
                status="ready",
                stance="supportive",
                summary="equity supportive",
                impacted_views=["duration"],
                required_series_ids=[],
                warnings=[],
            ),
            "commodities_inflation": mod.MacroBondTransmissionAxisResult(
                axis_key="commodities_inflation",
                status="ready",
                stance="neutral",
                summary="inflation neutral",
                impacted_views=["duration"],
                required_series_ids=[],
                warnings=[],
            ),
            "mega_cap_equities": mod.MacroBondTransmissionAxisResult(
                axis_key="mega_cap_equities",
                status="pending_signal",
                stance="neutral",
                summary="pending",
                impacted_views=["instrument"],
                required_series_ids=[],
                warnings=[],
            ),
        },
        [],
    )

    assert view.stance == "bullish"
    assert "股债相对估值传导轴偏有利" not in view.summary


def test_mega_cap_equity_axis_uses_explicit_rule_table_thresholds():
    mod = _core_module()

    assert [rule.stance for rule in mod.MEGA_CAP_EQUITY_RULES] == [
        "restrictive",
        "supportive",
    ]

    restrictive = mod._build_mega_cap_equities_axis(
        mod.MegaCapEquitySignal(
            weight_trade_date=REPORT_DATE,
            index_code="000300.SH",
            top10_weight_sum=23.6,
            top5_weight_sum=15.5,
            leading_constituents=["300750.SZ", "600519.SH", "300308.SZ"],
            index_pct_change=0.60,
        )
    )
    supportive = mod._build_mega_cap_equities_axis(
        mod.MegaCapEquitySignal(
            weight_trade_date=REPORT_DATE,
            index_code="000300.SH",
            top10_weight_sum=23.6,
            top5_weight_sum=15.5,
            leading_constituents=["300750.SZ", "600519.SH", "300308.SZ"],
            index_pct_change=-0.60,
        )
    )
    neutral = mod._build_mega_cap_equities_axis(
        mod.MegaCapEquitySignal(
            weight_trade_date=REPORT_DATE,
            index_code="000300.SH",
            top10_weight_sum=21.0,
            top5_weight_sum=13.0,
            leading_constituents=["300750.SZ", "600519.SH", "300308.SZ"],
            index_pct_change=0.10,
        )
    )

    assert restrictive.stance == "restrictive"
    assert supportive.stance == "supportive"
    assert neutral.stance == "neutral"
    assert "2026-04-10" in restrictive.summary


def test_schema_method_variants_additive_shape():
    """Cursor schema pass: additive method_variants contract validates and round-trips."""
    from backend.app.schemas.macro_bond_linkage import (
        MacroBondCorrelationItem,
        MacroBondLinkageMethodMeta,
        MacroBondLinkageMethodVariant,
        MacroBondLinkageMethodVariants,
        MacroBondLinkageResponse,
    )

    item_c = MacroBondCorrelationItem(
        series_id="S",
        series_name="Name",
        target_yield="treasury_10Y",
        target_family="treasury",
        target_tenor="10Y",
        lead_lag_days=3,
        direction="positive",
        alignment_mode="conservative",
        sample_size=42,
        winsorized=True,
        zscore_applied=True,
        lead_lag_confidence=0.85,
        effective_observation_span_days=200,
    )
    item_m = item_c.model_copy(update={"alignment_mode": "market_timing"})
    mv = MacroBondLinkageMethodVariants(
        conservative=MacroBondLinkageMethodVariant(
            method_meta=MacroBondLinkageMethodMeta(variant="conservative"),
            top_correlations=[item_c],
        ),
        market_timing=MacroBondLinkageMethodVariant(
            method_meta=MacroBondLinkageMethodMeta(variant="market_timing"),
            top_correlations=[item_m],
        ),
    )
    resp = MacroBondLinkageResponse(
        report_date=REPORT_DATE,
        computed_at="2026-04-13T00:00:00+00:00",
        environment_score={"k": 1},
        portfolio_impact={},
        top_correlations=[item_c],
        method_variants=mv,
        warnings=[],
    )
    dumped = resp.model_dump(mode="json")
    assert dumped["method_variants"]["conservative"]["top_correlations"][0]["alignment_mode"] == "conservative"
    assert dumped["method_variants"]["market_timing"]["top_correlations"][0]["alignment_mode"] == "market_timing"
    assert dumped["top_correlations"] == dumped["method_variants"]["conservative"]["top_correlations"]
    assert MacroBondLinkageResponse.model_validate(dumped).method_variants.conservative.method_meta.variant == "conservative"


def test_service_conservative_top_correlations_mirror_method_variant(tmp_path, monkeypatch):
    """Cursor service pass: default top_correlations track mirrors conservative variant."""
    duckdb_path = tmp_path / "macro-bond-service-contract.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=45, rising_rates=True)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    svc = _service_module()
    envelope = svc.get_macro_bond_linkage(REPORT_DATE)
    result = envelope["result"]
    assert result["top_correlations"] == result["method_variants"]["conservative"]["top_correlations"]
    assert result["method_variants"]["conservative"]["method_meta"]["variant"] == "conservative"
    assert result["method_variants"]["market_timing"]["method_meta"]["variant"] == "market_timing"
    assert result["method_variants"]["market_timing"]["top_correlations"][0]["alignment_mode"] == "market_timing"
    assert result["top_correlations"][0]["alignment_mode"] == "conservative"
    assert "environment_score" in result
    assert result["report_date"] == REPORT_DATE.isoformat()
    assert "computed_at" in result

    get_settings.cache_clear()


def test_api_returns_warning_when_macro_history_is_insufficient(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "macro-bond-linkage-insufficient.duckdb"
    _seed_macro_and_curve_inputs(str(duckdb_path), macro_points=20, rising_rates=True)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    get_settings.cache_clear()

    client = _route_client()
    response = client.get(
        "/api/macro-bond-linkage/analysis",
        params={"report_date": REPORT_DATE.isoformat()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"]["environment_score"] == {}
    assert payload["result"]["portfolio_impact"] == {}
    assert payload["result"]["top_correlations"] == []
    assert payload["result"]["method_variants"]["conservative"]["top_correlations"] == []
    assert payload["result"]["method_variants"]["market_timing"]["top_correlations"] == []
    assert any("不足" in warning for warning in payload["result"]["warnings"])

    get_settings.cache_clear()
