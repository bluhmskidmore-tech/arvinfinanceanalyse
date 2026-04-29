from __future__ import annotations

from decimal import Decimal

import duckdb

from backend.app.repositories.yield_curve_repo import FORMAL_FACT_TABLE, YieldCurveRepository, ensure_yield_curve_tables
from backend.app.services.campisi_attribution_service import (
    _add_market_curve_quality,
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
    assert "AA+, AA" in quality["warnings"][-1]


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
