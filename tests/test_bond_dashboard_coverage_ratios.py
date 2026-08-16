from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository


_FACT_COLUMNS = (
    "report_date",
    "bond_type",
    "market_value",
    "ytm",
    "modified_duration",
    "asset_class_std",
    "maturity_date",
    "dv01",
    "is_credit",
    "convexity",
    "spread_dv01",
    "face_value",
    "years_to_maturity",
)


def _insert_fact_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
                report_date varchar,
                bond_type varchar,
                market_value decimal(24, 8),
                ytm decimal(18, 8),
                modified_duration decimal(18, 8),
                asset_class_std varchar,
                maturity_date date,
                dv01 decimal(24, 8),
                is_credit boolean,
                convexity decimal(18, 8),
                spread_dv01 decimal(24, 8),
                face_value decimal(24, 8),
                years_to_maturity decimal(18, 8)
            )
            """
        )
        placeholders = ", ".join("?" for _ in _FACT_COLUMNS)
        conn.executemany(
            f"""
            insert into fact_formal_bond_analytics_daily ({", ".join(_FACT_COLUMNS)})
            values ({placeholders})
            """,
            [[row.get(column) for column in _FACT_COLUMNS] for row in rows],
        )
    finally:
        conn.close()


def _assert_bounded_ratio(value: object, expected: Decimal) -> None:
    assert value is not None
    ratio = Decimal(str(value))
    assert ratio == expected
    assert Decimal("0") <= ratio <= Decimal("1")


def test_business_type_coverage_uses_gross_absolute_market_value(tmp_path: Path) -> None:
    db_path = tmp_path / "business-type-coverage.duckdb"
    report_date = "2026-07-31"
    _insert_fact_rows(
        db_path,
        [
            {
                "report_date": report_date,
                "bond_type": "含负市值未覆盖",
                "market_value": Decimal("100"),
                "ytm": Decimal("0.02"),
                "modified_duration": Decimal("2"),
            },
            {
                "report_date": report_date,
                "bond_type": "含负市值未覆盖",
                "market_value": Decimal("-25"),
            },
            {
                "report_date": report_date,
                "bond_type": "正负净额相抵",
                "market_value": Decimal("100"),
                "ytm": Decimal("0.03"),
                "modified_duration": Decimal("3"),
            },
            {
                "report_date": report_date,
                "bond_type": "正负净额相抵",
                "market_value": Decimal("-100"),
            },
            {
                "report_date": report_date,
                "bond_type": "零绝对暴露",
                "market_value": Decimal("0"),
                "ytm": Decimal("0.04"),
                "modified_duration": Decimal("4"),
            },
        ],
    )

    rows = BondAnalyticsRepository(str(db_path)).fetch_business_type_metrics(report_date)
    by_name = {str(row["name"]): row for row in rows}

    for key in ("weighted_avg_ytm_coverage_ratio", "weighted_avg_duration_coverage_ratio"):
        _assert_bounded_ratio(by_name["含负市值未覆盖"][key], Decimal("0.8"))
        _assert_bounded_ratio(by_name["正负净额相抵"][key], Decimal("0.5"))
        assert by_name["零绝对暴露"][key] is None


def test_convexity_coverage_uses_gross_absolute_market_value(tmp_path: Path) -> None:
    db_path = tmp_path / "convexity-coverage.duckdb"
    _insert_fact_rows(
        db_path,
        [
            {
                "report_date": "2026-07-31",
                "market_value": Decimal("100"),
                "convexity": Decimal("0.20"),
            },
            {
                "report_date": "2026-07-31",
                "market_value": Decimal("-25"),
            },
            {
                "report_date": "2026-08-01",
                "market_value": Decimal("100"),
                "convexity": Decimal("0.20"),
            },
            {
                "report_date": "2026-08-01",
                "market_value": Decimal("-100"),
            },
        ],
    )
    repo = BondAnalyticsRepository(str(db_path))

    _assert_bounded_ratio(
        repo.fetch_dashboard_risk_indicators("2026-07-31")["weighted_convexity_coverage_ratio"],
        Decimal("0.8"),
    )
    _assert_bounded_ratio(
        repo.fetch_dashboard_risk_indicators("2026-08-01")["weighted_convexity_coverage_ratio"],
        Decimal("0.5"),
    )
