from __future__ import annotations

from datetime import date, timedelta

import duckdb
import pytest

from backend.app.core_finance.macro.a_share_stampede_risk import (
    compute_a_share_stampede_risk,
)
from backend.app.core_finance.macro.equity_strategies import (
    classify_low_crowding_market_regime,
)
from backend.app.services import macro_toolkit_service

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_macro_toolkit,
]


def _seed_choice_stock_history(path: str, *, include_vendor_version: bool = True) -> None:
    vendor_column = ", vendor_version varchar" if include_vendor_version else ""
    conn = duckdb.connect(path)
    try:
        conn.execute(
            f"""
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              high_value double,
              low_value double,
              close_value double,
              amount double,
              pctchange double,
              turn double,
              amplitude double,
              tradestatus varchar,
              highlimit double,
              lowlimit double,
              source_version varchar
              {vendor_column}
            )
            """
        )
        rows: list[tuple[object, ...]] = []
        for offset in range(20):
            trade_date = (date(2025, 12, 12) + timedelta(days=offset)).isoformat()
            rows.append(
                (
                    trade_date,
                    "000001.SZ",
                    10.0,
                    10.2,
                    9.8,
                    10.0,
                    100_000.0,
                    0.0,
                    1.0,
                    4.0,
                    "Trading",
                    11.0,
                    9.0,
                    "sv_tushare",
                    "vv_choice_tushare_stock_20251231",
                )
            )
        rows.append(
            (
                "2026-01-05",
                "000001.SZ",
                10.0,
                10.2,
                9.8,
                10.0,
                100_000_000.0,
                0.0,
                1.0,
                4.0,
                "Trading",
                11.0,
                9.0,
                "sv_choice",
                "vv_choice_stock_20260105",
            )
        )
        if include_vendor_version:
            conn.executemany(
                """
                insert into choice_stock_daily_observation
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        else:
            conn.executemany(
                """
                insert into choice_stock_daily_observation
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [row[:-1] for row in rows],
            )
    finally:
        conn.close()


def test_macro_choice_stock_loaders_remove_cross_generation_amount_break(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "mixed-units.duckdb"
    _seed_choice_stock_history(str(duckdb_path))
    monkeypatch.setattr(macro_toolkit_service, "EQUITY_PRICE_MIN_OBSERVATIONS", 2)

    price_context = macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)
    risk_context = macro_toolkit_service.load_a_share_stampede_risk_context(duckdb_path)

    assert price_context is not None
    assert risk_context is not None
    assert set(price_context["observations"]["amount"]) == {100_000_000.0}
    assert set(risk_context["observations"]["amount"]) == {100_000_000.0}

    regime = classify_low_crowding_market_regime(
        price_context["prices"],
        price_context["observations"],
    )
    stampede = compute_a_share_stampede_risk(risk_context["observations"])
    assert regime["amount_change_20"] == pytest.approx(0.0)
    assert stampede["metrics"]["turnover_ratio_ma20"] == pytest.approx(1.0)


def test_macro_choice_stock_loaders_fail_closed_to_null_amount_when_vendor_column_missing(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "legacy-schema.duckdb"
    _seed_choice_stock_history(str(duckdb_path), include_vendor_version=False)
    monkeypatch.setattr(macro_toolkit_service, "EQUITY_PRICE_MIN_OBSERVATIONS", 2)

    price_context = macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)
    risk_context = macro_toolkit_service.load_a_share_stampede_risk_context(duckdb_path)

    assert price_context is not None
    assert risk_context is not None
    assert price_context["observations"]["amount"].isna().all()
    assert risk_context["observations"]["amount"].isna().all()
    assert any("vendor_version" in warning for warning in price_context["warnings"])
    assert any("vendor_version" in warning for warning in risk_context["warnings"])


def test_equity_strategy_summary_warnings_merges_context_unit_warnings(
    tmp_path,
    monkeypatch,
) -> None:
    """低拥挤/多因子等策略 summary 若改用本 helper 拼装 warnings，应能带出
    price_context 里的单位降级告警（专家 14 断链修复的最小接线点）。"""
    duckdb_path = tmp_path / "legacy-schema-summary-warnings.duckdb"
    _seed_choice_stock_history(str(duckdb_path), include_vendor_version=False)
    monkeypatch.setattr(macro_toolkit_service, "EQUITY_PRICE_MIN_OBSERVATIONS", 2)

    price_context = macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)
    assert price_context is not None
    assert price_context["warnings"]

    strategy_own_warning = "FACTOR_SNAPSHOT_DATE_FALLBACK"
    merged = macro_toolkit_service.equity_strategy_summary_warnings(
        price_context,
        [strategy_own_warning],
    )

    assert strategy_own_warning in merged
    assert any("vendor_version" in warning for warning in merged)
    # 去重：策略自身告警与 context 告警重复时只保留一份。
    assert len(merged) == len(set(merged))

    # price_context 为 None（如上游加载失败）时不应报错，退化为仅保留传入告警。
    assert macro_toolkit_service.equity_strategy_summary_warnings(None, [strategy_own_warning]) == [
        strategy_own_warning
    ]
    assert macro_toolkit_service.equity_strategy_summary_warnings(None, None) == []


def test_macro_choice_stock_loaders_null_vendor_row_propagates_none_with_warning(
    tmp_path,
    monkeypatch,
) -> None:
    duckdb_path = tmp_path / "null-vendor-row.duckdb"
    _seed_choice_stock_history(str(duckdb_path))
    monkeypatch.setattr(macro_toolkit_service, "EQUITY_PRICE_MIN_OBSERVATIONS", 2)
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute(
            "update choice_stock_daily_observation set vendor_version = NULL "
            "where trade_date = '2026-01-05'"
        )
    finally:
        conn.close()

    price_context = macro_toolkit_service.load_equity_strategy_price_context(duckdb_path)
    risk_context = macro_toolkit_service.load_a_share_stampede_risk_context(duckdb_path)

    assert price_context is not None
    assert risk_context is not None
    assert price_context["observations"]["amount"].isna().sum() == 1
    assert risk_context["observations"]["amount"].isna().sum() == 1
    assert any("vendor_version" in warning for warning in price_context["warnings"])
    assert any("vendor_version" in warning for warning in risk_context["warnings"])
