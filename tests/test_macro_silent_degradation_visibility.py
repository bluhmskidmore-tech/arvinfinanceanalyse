from __future__ import annotations

import logging
from datetime import date, timedelta

import duckdb
import pytest

import backend.app.api.routes.macro_toolkit as macro_toolkit_route
from backend.app.core_finance.macro.crisis_score import compute_crisis_score_payload
from backend.app.core_finance.macro.toolkit.system_sources import (
    clear_system_macro_source_cache,
    load_series_by_alias,
    load_system_macro_frame,
)

_SYSTEM_SOURCE_TABLES = (
    "fact_choice_macro_daily",
    "choice_market_snapshot",
    "std_external_macro_daily",
    "fact_commodity_futures_daily",
    "fx_daily_mid",
    "fact_formal_yield_curve_daily",
)

_CRISIS_HISTORY_START = date(2025, 12, 12)
_CRISIS_HISTORY_DAYS = 120


@pytest.fixture(autouse=True)
def _reset_system_source_state():
    clear_system_macro_source_cache()
    yield
    clear_system_macro_source_cache()


def _crisis_history_values(offset: int) -> dict[str, float]:
    stress = max(0.0, (offset - 89) / 30)
    alternating = -1 if offset % 2 else 1
    gov_5y = 2.20 + offset * 0.0005
    return {
        "hs300": 4100 + offset * 1.5 + alternating * stress * 140,
        "usdcny": 7.05 + offset * 0.0005 + alternating * stress * 0.08,
        "nanhua": 980 + offset * 0.8 + alternating * stress * 50,
        "gov_5y": gov_5y,
        "aa_5y": gov_5y + 0.48 + stress * 0.80,
        "dr007": 1.75 + stress * 0.70,
        "reverse_repo_7d": 1.72,
    }


def _crisis_series_data(*, include_nanhua: bool) -> dict[str, list[tuple[date, float]]]:
    fields = ["hs300", "usdcny", "gov_5y", "aa_5y", "dr007", "reverse_repo_7d"]
    if include_nanhua:
        fields.append("nanhua")
    series_data: dict[str, list[tuple[date, float]]] = {field: [] for field in fields}
    for offset in range(_CRISIS_HISTORY_DAYS):
        trade_date = _CRISIS_HISTORY_START + timedelta(days=offset)
        values = _crisis_history_values(offset)
        for field in fields:
            series_data[field].append((trade_date, values[field]))
    return series_data


def _seed_crisis_history_without_nanhua(path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
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
        rows: list[tuple[object, ...]] = []
        for offset in range(_CRISIS_HISTORY_DAYS):
            trade_date = (_CRISIS_HISTORY_START + timedelta(days=offset)).strftime("%Y-%m-%d")
            values = _crisis_history_values(offset)
            rows.extend(
                [
                    ("CA.CSI300", "CSI 300 close", trade_date, values["hs300"], "daily", "index"),
                    ("EMM00058124", "USD/CNY spot", trade_date, values["usdcny"], "daily", "CNY/USD"),
                    (
                        "legacy.yield.choice.treasury.5Y",
                        "China treasury yield 5Y",
                        trade_date,
                        values["gov_5y"],
                        "daily",
                        "%",
                    ),
                    (
                        "legacy.yield.choice.aa_credit.5Y",
                        "China AA credit yield 5Y",
                        trade_date,
                        values["aa_5y"],
                        "daily",
                        "%",
                    ),
                    ("CA.DR007", "DR007", trade_date, values["dr007"], "daily", "%"),
                    ("M001", "Open market reverse repo 7D", trade_date, values["reverse_repo_7d"], "daily", "%"),
                ]
            )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (
              ?, ?, ?, ?, ?, ?,
              'sv_crisis_degraded_test', 'vv_choice_crisis_degraded_test',
              'rv_choice_macro_thin_slice_v1', 'ok', 'crisis-degraded-test'
            )
            """,
            rows,
        )
    finally:
        conn.close()


def test_missing_system_tables_warn_and_return_empty_frame(tmp_path, caplog) -> None:
    duckdb_path = tmp_path / "empty-tables.duckdb"
    duckdb.connect(str(duckdb_path)).close()

    with caplog.at_level(logging.WARNING):
        frame = load_system_macro_frame(duckdb_path)

    assert frame.empty
    warning_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    for table_name in _SYSTEM_SOURCE_TABLES:
        assert any(table_name in message for message in warning_messages), table_name


def test_missing_system_tables_warn_only_once_per_table(tmp_path, caplog) -> None:
    duckdb_path = tmp_path / "empty-tables.duckdb"
    duckdb.connect(str(duckdb_path)).close()

    with caplog.at_level(logging.WARNING):
        first = load_system_macro_frame(duckdb_path)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        second = load_system_macro_frame(duckdb_path)

    assert first.empty
    assert second.empty
    repeated = [record for record in caplog.records if "system macro source table" in record.getMessage()]
    assert repeated == []


def test_missing_duckdb_file_warns_once_across_alias_lookups(tmp_path, caplog) -> None:
    missing_path = tmp_path / "absent.duckdb"

    with caplog.at_level(logging.WARNING):
        hs300 = load_series_by_alias("sh000300", duckdb_path=missing_path)
        copper = load_series_by_alias("CU0", duckdb_path=missing_path)

    assert hs300.empty
    assert copper.empty
    missing_warnings = [
        record
        for record in caplog.records
        if "duckdb file" in record.getMessage() and str(missing_path) in record.getMessage()
    ]
    assert len(missing_warnings) == 1


def test_degraded_crisis_score_payload_marks_data_status() -> None:
    report_date = _CRISIS_HISTORY_START + timedelta(days=_CRISIS_HISTORY_DAYS - 1)

    payload = compute_crisis_score_payload(
        _crisis_series_data(include_nanhua=False),
        report_date=report_date,
    )

    assert payload["data_status"] == "degraded"
    assert "COMMODITY_VOL_UNAVAILABLE" in payload["warnings"]
    assert "NANHUA_MISSING" in payload["warnings"]
    assert payload["crisis_score"] is not None
    assert payload["available_component_count"] == 4
    assert payload["component_count"] == 5
    assert payload["report_date"] == report_date.isoformat()

    complete = compute_crisis_score_payload(
        _crisis_series_data(include_nanhua=True),
        report_date=report_date,
    )
    assert complete["data_status"] == "complete"


def test_degraded_crisis_score_surfaces_in_capability_card(tmp_path) -> None:
    duckdb_path = tmp_path / "crisis-degraded.duckdb"
    _seed_crisis_history_without_nanhua(duckdb_path)
    report_date = _CRISIS_HISTORY_START + timedelta(days=_CRISIS_HISTORY_DAYS - 1)

    raw_result = macro_toolkit_route._run_capability(
        "crisis_score_cn",
        lambda: macro_toolkit_route._compute_crisis_score_capability(duckdb_path, report_date),
    )
    definition = next(
        item for item in macro_toolkit_route._CAPABILITY_DEFINITIONS if item["key"] == "crisis_score_cn"
    )
    card = macro_toolkit_route._capability_result_card(definition, raw_result)

    assert card["status"] == "degraded"
    assert card["result"]["data_status"] == "degraded"
    assert "COMMODITY_VOL_UNAVAILABLE" in card["warnings"]
    assert "NANHUA_MISSING" in card["warnings"]
    assert card["result"]["report_date"]
    assert "NANHUA_MISSING" in card["input_evidence"]["missing_inputs"]
    nanhua_input = next(item for item in card["input_evidence"]["inputs"] if item["field"] == "nanhua")
    assert nanhua_input["available"] is False
    assert card["score"] is not None
