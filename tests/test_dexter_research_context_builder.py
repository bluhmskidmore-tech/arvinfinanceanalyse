from __future__ import annotations

import duckdb

from backend.app.agent.schemas.agent_request import AgentPageContext, AgentQueryRequest
from backend.app.services.dexter_research_context_builder import (
    ResearchContextBuilder,
    build_dexter_research_context,
)


def _connect(path):
    return duckdb.connect(str(path))


def test_build_stock_research_context_reads_choice_stock_tables_and_news(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = _connect(duckdb_path)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar, stock_code varchar, open_value double, high_value double,
              low_value double, close_value double, volume double, amount double,
              pctchange double, turn double, amplitude double, tradestatus varchar,
              highlimit varchar, lowlimit varchar, field_keys_json varchar,
              source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_stock_daily_observation values
            ('2026-04-29','000001.SZ',20,22,19,21.9,1000,2000,3.2,1.5,4.1,'交易','N','N','[]','sv_price','vv_choice','rv_price','run-price')
            """
        )
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date varchar, stock_code varchar, pe double, pb double, ps double,
              roe double, gross_margin double, three_month_return double, twelve_month_return double,
              volatility double, dividend_yield double, industry varchar,
              source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_stock_factor_snapshot values
            ('2026-04-29','000001.SZ',12.3,1.4,2.1,0.15,0.42,0.08,0.21,0.18,0.03,'AI','sv_factor','vv_choice','rv_factor','run-factor')
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar, stock_code varchar, sw2021 varchar, sw2021code varchar,
              field_key varchar, source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_stock_sector_membership values
            ('2026-04-29','000001.SZ','AI','801001','sw2021','sv_sector','vv_choice','rv_sector','run-sector')
            """
        )
        conn.execute(
            """
            create table choice_news_event (
              event_key varchar, received_at varchar, group_id varchar, content_type varchar,
              serial_id bigint, request_id bigint, error_code bigint, error_msg varchar,
              topic_code varchar, item_index bigint, payload_text varchar, payload_json varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_news_event values
            ('n1','2026-04-29T08:00:00Z','tushare_news','text',1,1,0,'','000001.SZ',0,'Alpha earnings beat','{}')
            """
        )
    finally:
        conn.close()

    context = build_dexter_research_context(
        request=AgentQueryRequest(
            question="分析这只股票",
            filters={"research_domain": "stock"},
            page_context=AgentPageContext(
                page_id="stock-analysis",
                current_filters={"as_of_date": "2026-04-29"},
                selected_rows=[{"stock_code": "000001.SZ", "stock_name": "Alpha"}],
            ),
        ),
        duckdb_path=str(duckdb_path),
    )

    assert context["domain"] == "stock"
    assert context["as_of_date"] == "2026-04-29"
    assert context["filters_applied"]["stock_code"] == "000001.SZ"
    assert context["tables_used"] == [
        "choice_stock_daily_observation",
        "choice_stock_factor_snapshot",
        "choice_stock_sector_membership",
        "choice_news_event",
    ]
    assert context["quality_flag"] == "ok"
    assert context["stock"]["daily_observation"]["close_value"] == 21.9
    assert context["stock"]["factor_snapshot"]["pe"] == 12.3
    assert context["stock"]["sector_membership"]["sw2021code"] == "801001"
    assert context["stock"]["news_events"][0]["payload_text"] == "Alpha earnings beat"
    assert context["limitations"] == []


def test_research_context_builder_class_matches_function_wrapper(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = _connect(duckdb_path)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar, stock_code varchar, open_value double, high_value double,
              low_value double, close_value double, volume double, amount double,
              pctchange double, turn double, amplitude double, tradestatus varchar,
              highlimit varchar, lowlimit varchar, field_keys_json varchar,
              source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_stock_daily_observation values
            ('2026-04-29','000001.SZ',20,22,19,21.9,1000,2000,3.2,1.5,4.1,'open','N','N','[]','sv_price','vv_choice','rv_price','run-price')
            """
        )
    finally:
        conn.close()

    request = AgentQueryRequest(
        question="review stock",
        filters={"research_domain": "stock", "stock_code": "000001.SZ"},
    )

    class_context = ResearchContextBuilder(duckdb_path=str(duckdb_path)).build(request)
    function_context = build_dexter_research_context(request=request, duckdb_path=str(duckdb_path))

    assert class_context == function_context
    assert class_context["tables_used"] == ["choice_stock_daily_observation"]
    assert class_context["quality_flag"] == "warning"
    assert "choice_stock_factor_snapshot is not landed." in class_context["limitations"]


def test_build_macro_research_context_reads_choice_and_tushare_series(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = _connect(duckdb_path)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar, series_name varchar, trade_date varchar, value_numeric double,
              frequency varchar, unit varchar, source_version varchar, vendor_version varchar,
              rule_version varchar, quality_flag varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('legacy.yield.choice.treasury.10Y','10Y treasury','2026-04-29',2.12,'daily','pct','sv_choice','vv_choice','rv_choice','ok','run-choice')
            """
        )
        conn.execute(
            """
            create table choice_market_snapshot (
              series_id varchar, series_name varchar, vendor_series_code varchar, vendor_name varchar,
              trade_date varchar, value_numeric double, frequency varchar, unit varchar,
              source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_market_snapshot values
            ('legacy.yield.choice.treasury.10Y','10Y treasury','S0059749','choice','2026-04-29',2.12,'daily','pct','sv_snap','vv_choice','rv_choice','run-snap')
            """
        )
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar, series_name varchar, vendor_name varchar, vendor_version varchar,
              frequency varchar, unit varchar, vendor_series_code varchar, batch_id varchar,
              catalog_version varchar, theme varchar, is_core boolean, tags_json varchar,
              request_options varchar, fetch_mode varchar, fetch_granularity varchar,
              refresh_tier varchar, policy_note varchar
            )
            """
        )
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog values
            ('legacy.yield.choice.treasury.10Y','10Y treasury','choice','vv_choice','daily','pct','S0059749','b1','cat1','rates',true,'[]','','edb','daily','stable','')
            """
        )
        conn.execute(
            """
            create table std_external_macro_daily (
              series_id varchar, vendor_name varchar, domain varchar, trade_date varchar,
              value_numeric double, frequency varchar, unit varchar, source_version varchar,
              vendor_version varchar, rule_version varchar, ingest_batch_id varchar,
              raw_zone_path varchar, created_at timestamp
            )
            """
        )
        conn.execute(
            """
            create view vw_external_macro_daily as
            select series_id, vendor_name, domain, trade_date, value_numeric, frequency, unit,
                   source_version, vendor_version, rule_version, ingest_batch_id, raw_zone_path, created_at
            from std_external_macro_daily
            """
        )
        conn.execute(
            """
            insert into std_external_macro_daily values
            ('tushare.macro.cn_cpi.monthly','tushare','macro','2026-03-31',1.8,'monthly','pct','sv_tushare','vv_tushare','rv_tushare','batch-1','raw.json','2026-04-30 00:00:00')
            """
        )
    finally:
        conn.close()

    context = build_dexter_research_context(
        request=AgentQueryRequest(
            question="宏观怎么看",
            filters={
                "research_domain": "macro",
                "macro_series_ids": [
                    "legacy.yield.choice.treasury.10Y",
                    "tushare.macro.cn_cpi.monthly",
                ],
            },
        ),
        duckdb_path=str(duckdb_path),
    )

    assert context["domain"] == "macro"
    assert context["quality_flag"] == "ok"
    assert context["tables_used"] == [
        "fact_choice_macro_daily",
        "choice_market_snapshot",
        "phase1_macro_vendor_catalog",
        "vw_external_macro_daily",
    ]
    assert context["macro"]["choice_series"][0]["series_id"] == "legacy.yield.choice.treasury.10Y"
    assert context["macro"]["choice_series"][0]["unit"] == "pct"
    assert context["macro"]["tushare_series"][0]["series_id"] == "tushare.macro.cn_cpi.monthly"
    assert context["macro"]["tushare_series"][0]["source_version"] == "sv_tushare"


def test_macro_research_context_respects_as_of_date(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = _connect(duckdb_path)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar, series_name varchar, trade_date varchar, value_numeric double,
              frequency varchar, unit varchar, source_version varchar, vendor_version varchar,
              rule_version varchar, quality_flag varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('legacy.yield.choice.treasury.10Y','10Y treasury','2026-04-29',2.12,'daily','pct','sv_choice_old','vv_choice','rv_choice','ok','run-choice-old'),
            ('legacy.yield.choice.treasury.10Y','10Y treasury','2026-05-02',2.48,'daily','pct','sv_choice_future','vv_choice','rv_choice','ok','run-choice-future')
            """
        )
        conn.execute(
            """
            create table choice_market_snapshot (
              series_id varchar, series_name varchar, vendor_series_code varchar, vendor_name varchar,
              trade_date varchar, value_numeric double, frequency varchar, unit varchar,
              source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_market_snapshot values
            ('legacy.yield.choice.treasury.10Y','10Y treasury','S0059749','choice','2026-04-29',2.12,'daily','pct','sv_snap_old','vv_choice','rv_choice','run-snap-old'),
            ('legacy.yield.choice.treasury.10Y','10Y treasury','S0059749','choice','2026-05-02',2.48,'daily','pct','sv_snap_future','vv_choice','rv_choice','run-snap-future')
            """
        )
        conn.execute(
            """
            create table std_external_macro_daily (
              series_id varchar, vendor_name varchar, domain varchar, trade_date varchar,
              value_numeric double, frequency varchar, unit varchar, source_version varchar,
              vendor_version varchar, rule_version varchar, ingest_batch_id varchar,
              raw_zone_path varchar, created_at timestamp
            )
            """
        )
        conn.execute(
            """
            create view vw_external_macro_daily as
            select series_id, vendor_name, domain, trade_date, value_numeric, frequency, unit,
                   source_version, vendor_version, rule_version, ingest_batch_id, raw_zone_path, created_at
            from std_external_macro_daily
            """
        )
        conn.execute(
            """
            insert into std_external_macro_daily values
            ('tushare.macro.cn_cpi.monthly','tushare','macro','2026-03-31',1.8,'monthly','pct','sv_tushare_old','vv_tushare','rv_tushare','batch-old','old.json','2026-04-30 00:00:00'),
            ('tushare.macro.cn_cpi.monthly','tushare','macro','2026-05-31',2.6,'monthly','pct','sv_tushare_future','vv_tushare','rv_tushare','batch-future','future.json','2026-06-01 00:00:00')
            """
        )
    finally:
        conn.close()

    context = build_dexter_research_context(
        request=AgentQueryRequest(
            question="macro as-of check",
            filters={
                "research_domain": "macro",
                "as_of_date": "2026-04-30",
                "macro_series_ids": [
                    "legacy.yield.choice.treasury.10Y",
                    "tushare.macro.cn_cpi.monthly",
                ],
            },
        ),
        duckdb_path=str(duckdb_path),
    )

    assert context["macro"]["choice_series"][0]["trade_date"] == "2026-04-29"
    assert context["macro"]["choice_series"][0]["source_version"] == "sv_choice_old"
    assert context["macro"]["choice_snapshots"][0]["trade_date"] == "2026-04-29"
    assert context["macro"]["choice_snapshots"][0]["source_version"] == "sv_snap_old"
    assert context["macro"]["tushare_series"][0]["trade_date"] == "2026-03-31"
    assert context["macro"]["tushare_series"][0]["source_version"] == "sv_tushare_old"


def test_missing_research_context_records_limitations_without_tables(tmp_path):
    context = build_dexter_research_context(
        request=AgentQueryRequest(
            question="分析股票",
            filters={"research_domain": "stock", "stock_code": "000001.SZ"},
        ),
        duckdb_path=str(tmp_path / "missing.duckdb"),
    )

    assert context["domain"] == "stock"
    assert context["quality_flag"] == "missing"
    assert context["tables_used"] == []
    assert "DuckDB database is not available" in context["limitations"][0]
