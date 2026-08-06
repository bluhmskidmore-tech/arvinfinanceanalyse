import duckdb

from backend.app.governance.settings import get_settings
from backend.app.repositories.cffex_member_rank_repo import ensure_cffex_member_rank_schema
from backend.app.services.macro_vendor_service import (
    macro_foundation_formal_envelope,
    market_data_bond_futures_rankings_envelope,
    market_data_coverage_summary_envelope,
    tushare_supplement_envelope,
)
from backend.app.services.market_data_ncd_proxy_service import ncd_funding_proxy_envelope


def _set_temp_duckdb_settings(monkeypatch, duckdb_path) -> None:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    getattr(get_settings, "cache_clear")()


def _write_ncd_shibor_fixture(duckdb_path, *, trade_date: str, source_version: str) -> None:
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
              quality_flag varchar
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
              unit varchar,
              refresh_tier varchar
            )
            """
        )
        conn.executemany(
            """
            insert into phase1_macro_vendor_catalog values (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"ncd.shibor.{tenor.lower()}",
                    f"Shibor {tenor}",
                    "tushare",
                    "vv-tushare",
                    "daily",
                    "%",
                    "fallback",
                )
                for tenor in ("1M", "3M", "6M", "9M", "1Y")
            ],
        )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"ncd.shibor.{tenor.lower()}",
                    f"Shibor {tenor}",
                    trade_date,
                    value,
                    "daily",
                    "%",
                    source_version,
                    "vv-tushare",
                    "ok",
                )
                for tenor, value in zip(
                    ("1M", "3M", "6M", "9M", "1Y"),
                    (1.1, 1.2, 1.3, 1.4, 1.5),
                    strict=True,
                )
            ],
        )
    finally:
        conn.close()


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
              ('eco-1', '20260612', '09:30:00', 'CNY', 'CN', 'CPI', '0.2', '0.1', '0.3', 'sv-eco', 'vv-eco'),
              ('eco-2', '20260611', '08:00:00', 'USD', 'US', 'PPI', '1.1', '1.0', '1.2', 'sv-eco', 'vv-eco')
            """
        )
    finally:
        conn.close()

    envelope = tushare_supplement_envelope(str(duckdb_path), money_supply_limit=1, eco_cal_limit=1)

    assert envelope["result_meta"]["result_kind"] == "market_data.tushare_supplement"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["quality_flag"] == "ok"
    assert envelope["result_meta"]["as_of_date"] == "2026-06-12"
    assert envelope["result_meta"]["resolved_report_date"] == "2026-06-12"
    assert envelope["result_meta"]["tables_used"] == [
        "std_tushare_money_supply_monthly",
        "std_tushare_eco_cal_event",
    ]
    assert envelope["result"]["money_supply_total_count"] == 2
    assert envelope["result"]["money_supply_truncated"] is True
    assert envelope["result"]["eco_cal_total_count"] == 2
    assert envelope["result"]["eco_cal_truncated"] is True
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
            "event_date": "2026-06-12",
            "event_time": "09:30:00",
            "currency": "CNY",
            "country": "CN",
            "event": "CPI",
            "value": "0.2",
            "pre_value": "0.1",
            "fore_value": "0.3",
        }
    ]


def test_tushare_supplement_dedupes_batches_and_applies_limit_after_dedupe(tmp_path):
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
              vendor_version varchar,
              created_at varchar,
              ingest_batch_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into std_tushare_money_supply_monthly values
              ('20260601', 1.0, 1.1, 1.2, 2.0, 2.1, 2.2, 3.0, 3.1, 3.2, 'sv-money-june-old', 'vv-money-june-old', '2026-06-10T08:00:00Z', 'batch-1'),
              ('2026-06-01', 9.0, 9.1, 9.2, 8.0, 8.1, 8.2, 7.0, 7.1, 7.2, 'sv-money-june-new', 'vv-money-june-new', '2026-06-10T09:00:00Z', 'batch-2'),
              ('20260501', 4.0, 4.1, 4.2, 5.0, 5.1, 5.2, 6.0, 6.1, 6.2, 'sv-money-may', 'vv-money-may', '2026-05-10T09:00:00Z', 'batch-1')
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
              vendor_version varchar,
              created_at varchar,
              ingest_batch_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into std_tushare_eco_cal_event values
              ('eco-1', '20260612', '09:30:00', 'CNY', 'CN', 'CPI', '0.2', '0.1', '0.3', 'sv-eco-old', 'vv-eco-old', '2026-06-12T09:30:00Z', 'batch-1'),
              ('eco-1', '2026-06-12', '09:30:00', 'CNY', 'CN', 'CPI', '0.4', '0.3', '0.5', 'sv-eco-new', 'vv-eco-new', '2026-06-12T10:30:00Z', 'batch-2'),
              ('eco-2', '20260611', '08:00:00', 'USD', 'US', 'PPI', '1.1', '1.0', '1.2', 'sv-eco-2', 'vv-eco-2', '2026-06-11T08:30:00Z', 'batch-1')
            """
        )
    finally:
        conn.close()

    envelope = tushare_supplement_envelope(str(duckdb_path), money_supply_limit=2, eco_cal_limit=2)

    assert envelope["result_meta"]["as_of_date"] == "2026-06-12"
    assert envelope["result_meta"]["evidence_rows"] == 4
    assert envelope["result"]["money_supply_total_count"] == 2
    assert envelope["result"]["money_supply_truncated"] is False
    assert envelope["result"]["eco_cal_total_count"] == 2
    assert envelope["result"]["eco_cal_truncated"] is False
    assert envelope["result"]["money_supply_rows"] == [
        {
            "month": "2026-06-01",
            "m0": 9.0,
            "m0_yoy": 9.1,
            "m0_mom": 9.2,
            "m1": 8.0,
            "m1_yoy": 8.1,
            "m1_mom": 8.2,
            "m2": 7.0,
            "m2_yoy": 7.1,
            "m2_mom": 7.2,
        },
        {
            "month": "2026-05-01",
            "m0": 4.0,
            "m0_yoy": 4.1,
            "m0_mom": 4.2,
            "m1": 5.0,
            "m1_yoy": 5.1,
            "m1_mom": 5.2,
            "m2": 6.0,
            "m2_yoy": 6.1,
            "m2_mom": 6.2,
        },
    ]
    assert envelope["result"]["eco_cal_rows"] == [
        {
            "event_id": "eco-1",
            "event_date": "2026-06-12",
            "event_time": "09:30:00",
            "currency": "CNY",
            "country": "CN",
            "event": "CPI",
            "value": "0.4",
            "pre_value": "0.3",
            "fore_value": "0.5",
        },
        {
            "event_id": "eco-2",
            "event_date": "2026-06-11",
            "event_time": "08:00:00",
            "currency": "USD",
            "country": "US",
            "event": "PPI",
            "value": "1.1",
            "pre_value": "1.0",
            "fore_value": "1.2",
        },
    ]
    assert envelope["result_meta"]["source_version"] == (
        "sv-eco-2__sv-eco-new__sv-money-june-new__sv-money-may"
    )


def test_tushare_legacy_conflicts_fail_closed_independent_of_insertion_order(tmp_path):
    envelopes = []
    for reverse in (False, True):
        duckdb_path = tmp_path / f"legacy-{reverse}.duckdb"
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
            money_rows = [
                (
                    "20260601",
                    1.0,
                    1.1,
                    1.2,
                    2.0,
                    2.1,
                    2.2,
                    3.0,
                    3.1,
                    3.2,
                    "sv-old",
                    "vv-old",
                ),
                (
                    "2026-06-01",
                    9.0,
                    9.1,
                    9.2,
                    8.0,
                    8.1,
                    8.2,
                    7.0,
                    7.1,
                    7.2,
                    "sv-new",
                    "vv-new",
                ),
                (
                    "20260501",
                    4.0,
                    4.1,
                    4.2,
                    5.0,
                    5.1,
                    5.2,
                    6.0,
                    6.1,
                    6.2,
                    "sv-may",
                    "vv-may",
                ),
            ]
            conn.executemany(
                "insert into std_tushare_money_supply_monthly values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                list(reversed(money_rows)) if reverse else money_rows,
            )
            conn.execute(
                """
                create table std_tushare_eco_cal_event (
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
            eco_rows = [
                (
                    "20260612",
                    "09:30:00",
                    "CNY",
                    "CN",
                    "CPI",
                    "0.2",
                    "0.1",
                    "0.3",
                    "sv-eco-old",
                    "vv-eco-old",
                ),
                (
                    "2026-06-12",
                    "09:30:00",
                    "CNY",
                    "CN",
                    "CPI",
                    "0.4",
                    "0.3",
                    "0.5",
                    "sv-eco-new",
                    "vv-eco-new",
                ),
                (
                    "20260611",
                    "08:00:00",
                    "USD",
                    "US",
                    "PPI",
                    "1.1",
                    "1.0",
                    "1.2",
                    "sv-eco-unique",
                    "vv-eco-unique",
                ),
            ]
            conn.executemany(
                "insert into std_tushare_eco_cal_event values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                list(reversed(eco_rows)) if reverse else eco_rows,
            )
        finally:
            conn.close()

        envelopes.append(
            tushare_supplement_envelope(
                str(duckdb_path),
                money_supply_limit=10,
                eco_cal_limit=10,
            )
        )

    assert envelopes[0]["result"] == envelopes[1]["result"]
    assert envelopes[0]["result_meta"]["quality_flag"] == "warning"
    assert envelopes[0]["result_meta"]["evidence_rows"] == 2
    assert envelopes[0]["result"]["money_supply_total_count"] == 1
    assert envelopes[0]["result"]["money_supply_truncated"] is False
    assert envelopes[0]["result"]["eco_cal_total_count"] == 1
    assert envelopes[0]["result"]["eco_cal_truncated"] is False
    assert [row["month"] for row in envelopes[0]["result"]["money_supply_rows"]] == [
        "2026-05-01"
    ]
    assert len(envelopes[0]["result"]["eco_cal_rows"]) == 1
    assert envelopes[0]["result"]["eco_cal_rows"][0]["event_id"].startswith("natural-")
    warnings = envelopes[0]["result"]["warnings"]
    assert any(
        "money supply month 2026-06-01" in warning
        and "without created_at/ingest_batch_id" in warning
        for warning in warnings
    )
    assert any(
        "economic calendar event" in warning
        and "without created_at/ingest_batch_id" in warning
        for warning in warnings
    )


def test_tushare_external_macro_conflict_does_not_use_physical_row_order(tmp_path):
    envelopes = []
    for reverse in (False, True):
        duckdb_path = tmp_path / f"external-{reverse}.duckdb"
        conn = duckdb.connect(str(duckdb_path), read_only=False)
        try:
            conn.execute(
                """
                create table std_external_macro_daily (
                  series_id varchar,
                  trade_date varchar,
                  value_numeric double,
                  source_version varchar,
                  vendor_version varchar
                )
                """
            )
            rows = [
                ("tushare.macro.cn_money.monthly", "20260601", 7.1, "sv-old", "vv-old"),
                ("tushare.macro.cn_money.monthly", "2026-06-01", 7.9, "sv-new", "vv-new"),
            ]
            conn.executemany(
                "insert into std_external_macro_daily values (?, ?, ?, ?, ?)",
                list(reversed(rows)) if reverse else rows,
            )
        finally:
            conn.close()

        envelopes.append(
            tushare_supplement_envelope(
                str(duckdb_path),
                money_supply_limit=10,
                eco_cal_limit=0,
            )
        )

    assert envelopes[0]["result"] == envelopes[1]["result"]
    assert envelopes[0]["result"]["money_supply_rows"] == []
    assert envelopes[0]["result"]["money_supply_total_count"] == 0
    assert envelopes[0]["result"]["money_supply_truncated"] is False
    assert envelopes[0]["result_meta"]["quality_flag"] == "warning"
    assert any(
        "fallback money supply month 2026-06-01" in warning
        and "without created_at/ingest_batch_id" in warning
        for warning in envelopes[0]["result"]["warnings"]
    )



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


def test_macro_foundation_formal_envelope_keeps_only_stable_catalog_rows(tmp_path):
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
              refresh_tier varchar
            )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              ('stable-1', 'Stable series', 'choice', 'vv-stable', 'daily', '%', 'stable'),
              ('fallback-1', 'Fallback series', 'choice', 'vv-fallback', 'daily', '%', 'fallback'),
              ('isolated-1', 'Isolated series', 'choice', 'vv-isolated', 'daily', '%', 'isolated')
            """
        )
        conn.execute(
            """
            create table choice_market_snapshot (
              series_id varchar,
              source_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_market_snapshot values
              ('stable-1', 'sv-stable'),
              ('fallback-1', 'sv-fallback'),
              ('isolated-1', 'sv-isolated')
            """
        )
    finally:
        conn.close()

    envelope = macro_foundation_formal_envelope(str(duckdb_path))

    assert envelope["result_meta"]["formal_use_allowed"] is True
    assert envelope["result_meta"]["source_version"] == "sv-stable"
    assert envelope["result_meta"]["vendor_version"] == "vv-stable"
    assert [row["series_id"] for row in envelope["result"]["series"]] == ["stable-1"]
    assert [row["refresh_tier"] for row in envelope["result"]["series"]] == ["stable"]
    assert envelope["result"]["series"][0]["theme"] == "unknown"
    assert envelope["result"]["series"][0]["tags"] == []


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


def test_coverage_summary_reads_complete_tushare_domains_up_to_supported_maximum(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    _set_temp_duckdb_settings(monkeypatch, duckdb_path)
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
        conn.executemany(
            """
            insert into std_tushare_money_supply_monthly
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"{2024 + index // 12}-{index % 12 + 1:02d}-01",
                    float(index),
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "sv-money",
                    "vv-money",
                )
                for index in range(22)
            ],
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
        conn.executemany(
            """
            insert into std_tushare_eco_cal_event
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"eco-{index + 1}",
                    f"2026-{index // 28 + 1:02d}-{index % 28 + 1:02d}",
                    "09:30:00",
                    "CNY",
                    "CN",
                    f"Event {index + 1}",
                    str(index + 1),
                    None,
                    None,
                    "sv-eco",
                    "vv-eco",
                )
                for index in range(100)
            ],
        )
    finally:
        conn.close()

    try:
        supplement = tushare_supplement_envelope(
            str(duckdb_path),
            money_supply_limit=120,
            eco_cal_limit=300,
        )
        envelope = market_data_coverage_summary_envelope(str(duckdb_path))
    finally:
        getattr(get_settings, "cache_clear")()

    assert len(supplement["result"]["money_supply_rows"]) == 22
    assert supplement["result"]["money_supply_total_count"] == 22
    assert supplement["result"]["money_supply_truncated"] is False
    assert len(supplement["result"]["eco_cal_rows"]) == 100
    assert supplement["result"]["eco_cal_total_count"] == 100
    assert supplement["result"]["eco_cal_truncated"] is False
    sections = {section["key"]: section for section in envelope["result"]["sections"]}
    assert sections["tushare_supplement"]["row_count"] == 122
    expected_evidence_rows = 0
    for section in sections.values():
        for key in ("row_count", "series_count", "group_count"):
            value = section.get(key)
            if isinstance(value, int) and value > 0:
                expected_evidence_rows += value
                break
    assert envelope["result_meta"]["evidence_rows"] == expected_evidence_rows

def test_coverage_summary_uses_live_ncd_proxy_and_fx_series_dates(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    _set_temp_duckdb_settings(monkeypatch, duckdb_path)
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
              quality_flag varchar
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
              unit varchar,
              refresh_tier varchar
            )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
              ('fx.swap.1y', 'USD/CNY Swap 1Y', 'choice', 'vv-choice', 'daily', '%', 'fallback'),
              ('ncd.shibor.1m', 'Shibor 1M', 'tushare', 'vv-tushare', 'daily', '%', 'fallback'),
              ('ncd.shibor.3m', 'Shibor 3M', 'tushare', 'vv-tushare', 'daily', '%', 'fallback'),
              ('ncd.shibor.6m', 'Shibor 6M', 'tushare', 'vv-tushare', 'daily', '%', 'fallback'),
              ('ncd.shibor.9m', 'Shibor 9M', 'tushare', 'vv-tushare', 'daily', '%', 'fallback'),
              ('ncd.shibor.1y', 'Shibor 1Y', 'tushare', 'vv-tushare', 'daily', '%', 'fallback')
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
              ('fx.swap.1y', 'USD/CNY Swap 1Y', '2026-06-01', 2.5, 'daily', '%', 'sv-fx', 'vv-choice', 'ok'),
              ('fx.swap.1y', 'USD/CNY Swap 1Y', '2026-05-31', 2.4, 'daily', '%', 'sv-fx', 'vv-choice', 'ok'),
              ('ncd.shibor.1m', 'Shibor 1M', '2026-06-15', 1.1, 'daily', '%', 'sv-shibor', 'vv-tushare', 'ok'),
              ('ncd.shibor.3m', 'Shibor 3M', '2026-06-15', 1.2, 'daily', '%', 'sv-shibor', 'vv-tushare', 'ok'),
              ('ncd.shibor.6m', 'Shibor 6M', '2026-06-15', 1.3, 'daily', '%', 'sv-shibor', 'vv-tushare', 'ok'),
              ('ncd.shibor.9m', 'Shibor 9M', '2026-06-15', 1.4, 'daily', '%', 'sv-shibor', 'vv-tushare', 'ok'),
              ('ncd.shibor.1y', 'Shibor 1Y', '2026-06-15', 1.5, 'daily', '%', 'sv-shibor', 'vv-tushare', 'ok')
            """
        )
    finally:
        conn.close()

    try:
        envelope = market_data_coverage_summary_envelope(str(duckdb_path))
    finally:
        getattr(get_settings, "cache_clear")()

    sections = {section["key"]: section for section in envelope["result"]["sections"]}
    assert sections["fx_analytical"]["latest_trade_date"] == "2026-06-01"
    assert sections["ncd_proxy"]["status"] == "proxy_only"
    assert sections["ncd_proxy"]["row_count"] == 1
    assert sections["ncd_proxy"]["latest_trade_date"] == "2026-06-15"
    assert sections["ncd_proxy"]["as_of_date"] == "2026-06-15"
    assert sections["ncd_proxy"]["quality_flag"] == "ok"


def test_coverage_summary_ncd_uses_parameter_database_not_global_settings(tmp_path, monkeypatch):
    settings_duckdb_path = tmp_path / "settings-a.duckdb"
    parameter_duckdb_path = tmp_path / "parameter-b.duckdb"
    _write_ncd_shibor_fixture(
        settings_duckdb_path,
        trade_date="2026-06-01",
        source_version="sv-settings-a",
    )
    _write_ncd_shibor_fixture(
        parameter_duckdb_path,
        trade_date="2026-07-15",
        source_version="sv-parameter-b",
    )
    _set_temp_duckdb_settings(monkeypatch, settings_duckdb_path)

    try:
        ncd_envelope = ncd_funding_proxy_envelope(str(parameter_duckdb_path))
        coverage = market_data_coverage_summary_envelope(str(parameter_duckdb_path))
    finally:
        getattr(get_settings, "cache_clear")()

    assert ncd_envelope["result"]["as_of_date"] == "2026-07-15"
    assert ncd_envelope["result_meta"]["as_of_date"] == "2026-07-15"
    assert ncd_envelope["result_meta"]["resolved_report_date"] == "2026-07-15"
    assert ncd_envelope["result_meta"]["tables_used"] == [
        "fact_choice_macro_daily",
        "phase1_macro_vendor_catalog",
    ]
    assert ncd_envelope["result_meta"]["evidence_rows"] == 1
    assert ncd_envelope["result_meta"]["source_version"] == "sv-parameter-b"

    sections = {section["key"]: section for section in coverage["result"]["sections"]}
    assert sections["ncd_proxy"]["latest_trade_date"] == "2026-07-15"
    assert sections["ncd_proxy"]["row_count"] == 1
    assert "sv-settings-a" not in coverage["result_meta"]["source_version"]
    assert "sv-parameter-b" in coverage["result_meta"]["source_version"]


def test_coverage_summary_marks_missing_parameter_ncd_as_empty(tmp_path, monkeypatch):
    settings_duckdb_path = tmp_path / "settings-a.duckdb"
    parameter_duckdb_path = tmp_path / "parameter-empty.duckdb"
    _write_ncd_shibor_fixture(
        settings_duckdb_path,
        trade_date="2026-06-01",
        source_version="sv-settings-a",
    )
    conn = duckdb.connect(str(parameter_duckdb_path), read_only=False)
    conn.close()
    _set_temp_duckdb_settings(monkeypatch, settings_duckdb_path)

    try:
        coverage = market_data_coverage_summary_envelope(str(parameter_duckdb_path))
    finally:
        getattr(get_settings, "cache_clear")()

    sections = {section["key"]: section for section in coverage["result"]["sections"]}
    ncd_section = sections["ncd_proxy"]
    assert ncd_section["status"] == "empty"
    assert ncd_section["row_count"] == 0
    assert ncd_section["source_pending"] is True
    assert ncd_section["proxy_only"] is False
    assert ncd_section["vendor_status"] == "vendor_unavailable"
    assert ncd_section["quality_flag"] == "warning"
    assert ncd_section["latest_trade_date"] is None
    assert ncd_section["as_of_date"] is None
    assert "No NCD funding proxy rows are available" in ncd_section["message"]
    assert "proxy-only" not in ncd_section["message"].lower()
    assert coverage["result"]["headline"]["readable_count"] == 0
    assert coverage["result"]["headline"]["empty_count"] == 5
    assert "sv-settings-a" not in coverage["result_meta"]["source_version"]


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
