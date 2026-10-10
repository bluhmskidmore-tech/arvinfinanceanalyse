from pathlib import Path

import duckdb
import pytest

from backend.app.services import macro_vendor_service

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_market_data,
]


@pytest.mark.parametrize(
    ("series_name", "expected"),
    [
        ("存款类机构质押式回购加权利率:DR007", "存款类机构质押式回购加权利率"),
        ("公开市场操作:逆回购:7天:中标利率", "逆回购:7天:中标利率"),
        ("公开市场操作:逆回购:14天:交易量", "逆回购:14天:交易量"),
        ("中国:GDP:现价", "GDP:现价"),
        ("中国:GDP:现价:当季值", "GDP:现价:当季值"),
        ("Brent spot price", "布伦特原油现货"),
        ("CSI 500 index close", "中证500收盘"),
        ("Shibor fixing", "Shibor 定盘"),
    ],
)
def test_macro_series_display_name_cleans_known_names(
    series_name: str,
    expected: str,
) -> None:
    assert macro_vendor_service.macro_series_display_name(series_name) == expected


def test_macro_series_display_name_preserves_unknown_english_name() -> None:
    assert (
        macro_vendor_service.macro_series_display_name("Unverified vendor label")
        == "Unverified vendor label"
    )
    assert (
        macro_vendor_service.macro_series_display_name(" Unverified vendor label ")
        == " Unverified vendor label "
    )


def test_macro_latest_and_catalog_expose_display_name_and_catalog_unit(tmp_path: Path) -> None:
    duckdb_path = tmp_path / "macro-display-name.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
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
            create table phase1_macro_vendor_catalog (
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
            insert into fact_choice_macro_daily values (
              'M0',
              '中国:流通中现金M0',
              '2026-07-01',
              131800.0,
              'monthly',
              'unknown',
              'sv',
              'vv',
              'rv',
              'ok',
              'run'
            )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values (
              'M0',
              '中国:流通中现金M0',
              'choice',
              'vv',
              'monthly',
              '亿元'
            )
            """
        )
    finally:
        conn.close()

    latest = macro_vendor_service.load_choice_macro_latest_payload(str(duckdb_path)).series[0]
    catalog = macro_vendor_service.load_macro_vendor_payload(str(duckdb_path)).series[0]

    assert latest.series_name == "中国:流通中现金M0"
    assert latest.display_name == "流通中现金M0"
    assert latest.unit == "亿元"
    assert catalog.series_name == "中国:流通中现金M0"
    assert catalog.display_name == "流通中现金M0"
    assert catalog.unit == "亿元"
