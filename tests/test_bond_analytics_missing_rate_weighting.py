"""缺失≠0：正式债分析聚合的加权平均不得把缺失字段当成 0 拉低。

每个用例都构造「有值 / 缺失 / 显式 0」三行同组数据：
- 有值行按市值（或面值）加权；
- 缺失行同时退出分子与分母；
- 显式 0 行仍参与加权（零息券、零凸性是合法观测）；
- ``*_coverage_ratio`` 如实暴露参与加权的市值占比。
"""

from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from backend.app.repositories.bond_analytics_repo import (
    BondAnalyticsRepository,
    ensure_bond_analytics_tables,
)

pytestmark = pytest.mark.unit

REPORT_DATE = "2026-03-31"

_INSERT_COLUMNS = (
    "report_date",
    "instrument_code",
    "portfolio_name",
    "cost_center",
    "asset_class_std",
    "bond_type",
    "accounting_class",
    "currency_code",
    "face_value",
    "market_value",
    "amortized_cost",
    "accrued_interest",
    "coupon_rate",
    "ytm",
    "years_to_maturity",
    "modified_duration",
    "convexity",
    "dv01",
    "is_credit",
    "spread_dv01",
)


def _seed(db_path: str, rows: list[dict[str, object]]) -> None:
    conn = duckdb.connect(db_path, read_only=False)
    try:
        ensure_bond_analytics_tables(conn)
        placeholders = ", ".join(["?"] * len(_INSERT_COLUMNS))
        conn.executemany(
            f"insert into fact_formal_bond_analytics_daily "
            f"({', '.join(_INSERT_COLUMNS)}) values ({placeholders})",
            [tuple(row.get(column) for column in _INSERT_COLUMNS) for row in rows],
        )
    finally:
        conn.close()


def _position(**overrides: object) -> dict[str, object]:
    """同一分组键的一行持仓；只有度量字段按用例覆盖。"""
    row: dict[str, object] = {
        "report_date": REPORT_DATE,
        "instrument_code": "BOND-MIX",
        "portfolio_name": "FIOA",
        "cost_center": "5010",
        "asset_class_std": "rate",
        "bond_type": "treasury",
        "accounting_class": "AC",
        "currency_code": "CNY",
        "face_value": Decimal("0"),
        "market_value": Decimal("0"),
        "amortized_cost": Decimal("0"),
        "accrued_interest": Decimal("0"),
        "is_credit": False,
        "dv01": Decimal("0"),
        "spread_dv01": Decimal("0"),
    }
    row.update(overrides)
    return row


def test_campisi_decision_analytics_rows_exclude_missing_metrics_from_weighted_avg(tmp_path) -> None:
    """缺 coupon/ytm/期限/久期/凸性的行不进分母；显式 0 仍参与加权。"""
    db_path = str(tmp_path / "campisi_decision_analytics.duckdb")
    _seed(
        db_path,
        [
            _position(
                market_value=Decimal("100"),
                coupon_rate=Decimal("0.04"),
                ytm=Decimal("0.05"),
                years_to_maturity=Decimal("5"),
                modified_duration=Decimal("4"),
                convexity=Decimal("20"),
            ),
            _position(
                market_value=Decimal("100"),
                coupon_rate=None,
                ytm=None,
                years_to_maturity=None,
                modified_duration=None,
                convexity=None,
            ),
            _position(
                market_value=Decimal("50"),
                coupon_rate=Decimal("0"),
                ytm=Decimal("0"),
                years_to_maturity=Decimal("0"),
                modified_duration=Decimal("0"),
                convexity=Decimal("0"),
            ),
        ],
    )

    rows = BondAnalyticsRepository(db_path).fetch_campisi_decision_analytics_rows(REPORT_DATE)

    assert len(rows) == 1
    row = rows[0]
    assert row["market_value"] == Decimal("250")
    # 有值市值 100 + 显式零值市值 50 = 150 进分母；缺失的 100 退出。
    assert float(row["coupon_rate"]) == pytest.approx(0.04 * 100 / 150)
    assert float(row["ytm"]) == pytest.approx(0.05 * 100 / 150)
    assert float(row["years_to_maturity"]) == pytest.approx(5 * 100 / 150)
    assert float(row["modified_duration"]) == pytest.approx(4 * 100 / 150)
    assert float(row["convexity"]) == pytest.approx(20 * 100 / 150)
    for field in (
        "coupon_rate_coverage_ratio",
        "ytm_coverage_ratio",
        "years_to_maturity_coverage_ratio",
        "modified_duration_coverage_ratio",
        "convexity_coverage_ratio",
    ):
        assert float(row[field]) == pytest.approx(0.6), field
    # 旧口径 coalesce(rate, 0)/全量分母会得到 0.04*100/250 = 0.016。
    assert float(row["coupon_rate"]) != pytest.approx(0.016)
    assert float(row["modified_duration"]) != pytest.approx(4 * 100 / 250)


def test_campisi_decision_analytics_rows_keep_full_weight_when_no_value_is_missing(tmp_path) -> None:
    """全覆盖分组的加权值不受修复影响，覆盖率为 1。"""
    db_path = str(tmp_path / "campisi_decision_full_coverage.duckdb")
    _seed(
        db_path,
        [
            _position(market_value=Decimal("100"), coupon_rate=Decimal("0.04"), convexity=Decimal("20")),
            _position(market_value=Decimal("100"), coupon_rate=Decimal("0.02"), convexity=Decimal("10")),
        ],
    )

    row = BondAnalyticsRepository(db_path).fetch_campisi_decision_analytics_rows(REPORT_DATE)[0]

    assert float(row["coupon_rate"]) == pytest.approx(0.03)
    assert float(row["convexity"]) == pytest.approx(15)
    assert float(row["coupon_rate_coverage_ratio"]) == pytest.approx(1.0)
    assert float(row["convexity_coverage_ratio"]) == pytest.approx(1.0)


def test_campisi_decision_analytics_rows_fall_back_to_avg_when_coverage_is_zero(tmp_path) -> None:
    """全组缺失时不得除零：退回 avg()，覆盖率为 0。"""
    db_path = str(tmp_path / "campisi_decision_zero_coverage.duckdb")
    _seed(
        db_path,
        [
            _position(market_value=Decimal("100"), coupon_rate=None, convexity=None),
            _position(market_value=Decimal("50"), coupon_rate=None, convexity=None),
        ],
    )

    row = BondAnalyticsRepository(db_path).fetch_campisi_decision_analytics_rows(REPORT_DATE)[0]

    assert row["coupon_rate"] is None
    assert row["convexity"] is None
    assert float(row["coupon_rate_coverage_ratio"]) == pytest.approx(0.0)
    assert float(row["convexity_coverage_ratio"]) == pytest.approx(0.0)


def test_business_type_metrics_exclude_missing_ytm_and_duration_from_weighted_avg(tmp_path) -> None:
    db_path = str(tmp_path / "business_type_metrics.duckdb")
    _seed(
        db_path,
        [
            _position(
                market_value=Decimal("100"),
                ytm=Decimal("0.05"),
                modified_duration=Decimal("4"),
            ),
            _position(market_value=Decimal("100"), ytm=None, modified_duration=None),
            _position(
                market_value=Decimal("50"),
                ytm=Decimal("0"),
                modified_duration=Decimal("0"),
            ),
        ],
    )

    rows = BondAnalyticsRepository(db_path).fetch_business_type_metrics(REPORT_DATE)

    assert len(rows) == 1
    row = rows[0]
    assert row["market_value"] == Decimal("250")
    assert float(row["weighted_avg_ytm"]) == pytest.approx(0.05 * 100 / 150)
    assert float(row["weighted_avg_duration"]) == pytest.approx(4 * 100 / 150)
    assert float(row["weighted_avg_ytm_coverage_ratio"]) == pytest.approx(0.6)
    assert float(row["weighted_avg_duration_coverage_ratio"]) == pytest.approx(0.6)
    # 旧口径全量分母会得到 0.05*100/250 = 0.02 与 4*100/250 = 1.6。
    assert float(row["weighted_avg_ytm"]) != pytest.approx(0.02)
    assert float(row["weighted_avg_duration"]) != pytest.approx(1.6)


def test_dashboard_risk_indicators_exclude_missing_convexity_from_weighted_avg(tmp_path) -> None:
    db_path = str(tmp_path / "risk_indicators.duckdb")
    _seed(
        db_path,
        [
            _position(market_value=Decimal("100"), convexity=Decimal("20")),
            _position(market_value=Decimal("100"), convexity=None),
            _position(market_value=Decimal("50"), convexity=Decimal("0")),
        ],
    )

    row = BondAnalyticsRepository(db_path).fetch_dashboard_risk_indicators(REPORT_DATE)

    assert row["total_market_value"] == Decimal("250")
    assert float(row["weighted_convexity"]) == pytest.approx(20 * 100 / 150)
    assert float(row["weighted_convexity_coverage_ratio"]) == pytest.approx(0.6)
    # 旧口径全量分母会得到 20*100/250 = 8。
    assert float(row["weighted_convexity"]) != pytest.approx(8.0)


def test_dashboard_headline_weighted_coupon_excludes_missing_coupon_from_face_weighting(tmp_path) -> None:
    db_path = str(tmp_path / "headline_kpis.duckdb")
    _seed(
        db_path,
        [
            _position(face_value=Decimal("100"), coupon_rate=Decimal("0.04")),
            _position(face_value=Decimal("100"), coupon_rate=None),
            _position(face_value=Decimal("50"), coupon_rate=Decimal("0")),
        ],
    )

    current = BondAnalyticsRepository(db_path).fetch_dashboard_headline_kpis(REPORT_DATE)["current"]

    assert current["total_face_value"] == Decimal("250")
    assert float(current["weighted_coupon"]) == pytest.approx(0.04 * 100 / 150)
    assert float(current["weighted_coupon_coverage_ratio"]) == pytest.approx(0.6)
    # 旧口径全量面值分母会得到 0.04*100/250 = 0.016。
    assert float(current["weighted_coupon"]) != pytest.approx(0.016)


def test_dashboard_headline_weighted_coupon_is_zero_without_crashing_when_all_missing(tmp_path) -> None:
    """全缺票息时旧口径会返回 NULL 并在 Decimal 转换处抛错；修复后归零并由覆盖率披露。"""
    db_path = str(tmp_path / "headline_kpis_all_missing.duckdb")
    _seed(
        db_path,
        [
            _position(face_value=Decimal("100"), coupon_rate=None),
            _position(face_value=Decimal("50"), coupon_rate=None),
        ],
    )

    current = BondAnalyticsRepository(db_path).fetch_dashboard_headline_kpis(REPORT_DATE)["current"]

    assert current["weighted_coupon"] == Decimal("0")
    assert float(current["weighted_coupon_coverage_ratio"]) == pytest.approx(0.0)
