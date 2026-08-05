import duckdb

from backend.app.repositories.cffex_member_rank_repo import ensure_cffex_member_rank_schema
from backend.app.services.macro_vendor_service import (
    macro_foundation_formal_envelope,
    market_data_bond_futures_rankings_envelope,
    market_data_coverage_summary_envelope,
    tushare_supplement_envelope,
)


def test_tushare_supplement_envelope_reads_landed_tables(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table std_tushare_money_supply_monthly (
              month varchar,
              m0 double,
              m0_yoy double,
              m0_mom double,
              m1 double,
              m1_yoy double,
              m1_mom double,
              m2 double,
              m2_yoy double,
              m2_mom double,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into std_tushare_money_supply_monthly values
              ('2026-05-01', 1.0, 1.1, 1.2, 2.0, 2.1, 2.2, 3.0, 3.1, 3.2, 'sv-money', 'vv-money'),
              ('2026-04-01', 0.9, 1.0, 1.1, 1.9, 2.0, 2.1, 2.9, 3.0, 3.1, 'sv-money', 'vv-money')
            """
        )
        conn.execute(
            """
            create table std_tushare_eco_cal_event (
              event_id varchar,
              event_date varchar,
              event_time varchar,
              currency varchar,
              country varchar,
              event varchar,
              value varchar,
              pre_value varchar,
              fore_value varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into std_tushare_eco_cal_event values
              ('eco-1', '20260612', '09:30:00', 'CNY', 'CN', 'CPI', '0.2', '0.1', '0.3', 'sv-eco', 'vv-eco')
            """
        )
    finally:
        conn.close()

    envelope = tushare_supplement_envelope(str(duckdb_path), money_supply_limit=1, eco_cal_limit=1)

    assert envelope["result_meta"]["result_kind"] == "market_data.tushare_supplement"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["quality_flag"] == "ok"
    assert envelope["result_meta"]["tables_used"] == [
        "std_tushare_money_supply_monthly",
        "std_tushare_eco_cal_event",
    ]
    assert envelope["result"]["money_supply_rows"] == [
        {
            "month": "2026-05-01",
            "m0": 1.0,
            "m0_yoy": 1.1,
            "m0_mom": 1.2,
            "m1": 2.0,
            "m1_yoy": 2.1,
            "m1_mom": 2.2,
            "m2": 3.0,
            "m2_yoy": 3.1,
            "m2_mom": 3.2,
        }
    ]
    assert envelope["result"]["eco_cal_rows"] == [
        {
            "event_id": "eco-1",
            "event_date": "20260612",
            "event_time": "09:30:00",
            "currency": "CNY",
            "country": "CN",
            "event": "CPI",
            "value": "0.2",
            "pre_value": "0.1",
            "fore_value": "0.3",
        }
    ]


def test_bond_futures_rankings_envelope_reads_cffex_member_rank_table(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_cffex_member_rank_schema(conn)
        conn.execute(
            """
            insert into fact_cffex_member_rank_daily (
              trade_date,
              contract,
              product_code,
              exchange,
              member_name,
              source_vendor,
              source_row_no,
              volume,
              volume_change,
              long_holding,
              long_change,
              short_holding,
              short_change,
              source_version,
              vendor_version,
              rule_version,
              ingest_batch_id,
              raw_payload_json
            )
            values
              ('2026-06-11', 'T.CFE', 'T', 'CFFEX', '中信期货', 'tushare', 1,
               12345, 101, 23456, 202, 21000, -50,
               'sv_test_cffex_rank', 'vv_test_tushare', 'rv_cffex_member_rank_choice_tushare_v1',
               'batch-1', '{}'),
              ('2026-06-11', 'T.CFE', 'T', 'CFFEX', '国泰君安', 'tushare', 2,
               8901, -10, 11000, 12, 12000, -30,
               'sv_test_cffex_rank', 'vv_test_tushare', 'rv_cffex_member_rank_choice_tushare_v1',
               'batch-1', '{}')
            """
        )
    finally:
        conn.close()

    envelope = market_data_bond_futures_rankings_envelope(
        str(duckdb_path),
        contract="T.CFE",
        limit=1,
    )

    assert envelope["result_meta"]["result_kind"] == "market_data.bond_futures_rankings"
    assert envelope["result_meta"]["source_surface"] == "market_data"
    assert envelope["result_meta"]["quality_flag"] == "ok"
    assert envelope["result_meta"]["evidence_rows"] == 1
    assert envelope["result"]["as_of_date"] == "2026-06-11"
    assert envelope["result"]["rows"] == [
        {
            "trade_date": "2026-06-11",
            "contract": "T.CFE",
            "product_code": "T",
            "exchange": "CFFEX",
            "member_name": "中信期货",
            "source_vendor": "tushare",
            "source_row_no": 1,
            "volume": 12345.0,
            "volume_change": 101.0,
            "long_holding": 23456.0,
            "long_change": 202.0,
            "short_holding": 21000.0,
            "short_change": -50.0,
            "source_version": "sv_test_cffex_rank",
            "vendor_version": "vv_test_tushare",
            "rule_version": "rv_cffex_member_rank_choice_tushare_v1",
        }
    ]


def test_macro_foundation_exposes_catalog_theme_and_safely_parsed_tags(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              vendor_name varchar,
              vendor_version varchar,
              frequency varchar,
              unit varchar,
              theme varchar,
              tags_json varchar,
              refresh_tier varchar
            )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              (
                'rates-1',
                'Rates series',
                'choice',
                'vv-rates',
                'daily',
                '%',
                'rates',
                '["rates", "liquidity", 7, null, "  curve  "]',
                'stable'
              ),
              (
                'bad-tags',
                'Bad tags series',
                'choice',
                'vv-bad',
                'daily',
                '%',
                null,
                '{not-json',
                'stable'
              )
            """
        )
    finally:
        conn.close()

    envelope = macro_foundation_formal_envelope(str(duckdb_path))
    rows = {row["series_id"]: row for row in envelope["result"]["series"]}

    assert rows["rates-1"]["theme"] == "rates"
    assert rows["rates-1"]["tags"] == ["rates", "liquidity", "curve"]
    assert rows["bad-tags"]["theme"] == "unknown"
    assert rows["bad-tags"]["tags"] == []


def test_coverage_summary_marks_bond_futures_ready_when_rankings_exist(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_cffex_member_rank_schema(conn)
        conn.execute(
            """
            insert into fact_cffex_member_rank_daily (
              trade_date,
              contract,
              product_code,
              exchange,
              member_name,
              source_vendor,
              source_row_no,
              volume,
              volume_change,
              long_holding,
              long_change,
              short_holding,
              short_change,
              source_version,
              vendor_version,
              rule_version,
              ingest_batch_id,
              raw_payload_json
            )
            values (
              '2026-06-11', 'T.CFE', 'T', 'CFFEX', '中信期货', 'tushare', 1,
              12345, 101, 23456, 202, 21000, -50,
              'sv_test_cffex_rank', 'vv_test_tushare', 'rv_cffex_member_rank_choice_tushare_v1',
              'batch-1', '{}'
            )
            """
        )
    finally:
        conn.close()

    envelope = market_data_coverage_summary_envelope(str(duckdb_path))

    sections = {section["key"]: section for section in envelope["result"]["sections"]}
    assert envelope["result_meta"]["result_kind"] == "market_data.coverage_summary"
    assert sections["bond_futures"]["status"] == "ready"
    assert sections["bond_futures"]["row_count"] == 1
    assert sections["bond_futures"]["source_pending"] is False
    assert sections["cash_bond_trades"]["source_pending"] is True
    assert sections["credit_trades"]["source_pending"] is True
