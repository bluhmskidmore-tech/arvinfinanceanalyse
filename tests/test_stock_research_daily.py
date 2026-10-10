from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import gzip
import hashlib
import json
from types import SimpleNamespace

import duckdb
import pytest

from tests.helpers import load_module


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_market_data,
]

TARGET_DATE = "2026-09-04"
REPORT_PERIOD = "2026-06-30"
STOCK_CODE = "000001.SZ"


@pytest.fixture
def module():
    return load_module("scripts.stock_research_daily", "scripts/stock_research_daily.py")


def _universe_row(code=STOCK_CODE, name="Fixture Company"):
    return {"stock_code": code, "stock_name": name, "sector": "Fixture Sector"}


def _history(count=61, *, split=False):
    dates = []
    cursor = date.fromisoformat(TARGET_DATE)
    while len(dates) < count:
        if cursor.weekday() < 5:
            dates.append(cursor.isoformat())
        cursor -= timedelta(days=1)
    rows = []
    adjustments = []
    for index, trade_date in enumerate(reversed(dates)):
        adjusted_close = 10.0 + index / 10
        pre_split = split and index < count - 20
        close = adjusted_close * (2 if pre_split else 1)
        rows.append(
            {
                "stock_code": STOCK_CODE,
                "trade_date": trade_date,
                "close_value": close,
                "open_value": close - 0.05,
                "high_value": close + 0.05,
                "low_value": close - 0.10,
                "volume": 100_000_000.0,
                "amount_yuan": 400_000_000.0,
                "pctchange": 0.5,
                "up_limit": close * 1.1,
                "tradestatus": "TRADING",
                "vendor_version": "fixture_normalized",
            }
        )
        adjustments.append(
            {
                "stock_code": STOCK_CODE,
                "trade_date": trade_date,
                "adj_factor": 1.0 if not split or pre_split else 2.0,
            }
        )
    return rows, adjustments


def _financial_rows():
    common = {"ts_code": STOCK_CODE, "end_date": "20260630", "ann_date": "20260820"}
    return (
        [{
            **common,
            "or_yoy": 12.0,
            "tr_yoy": 99.0,
            "netprofit_yoy": 20.0,
            "dt_netprofit_yoy": 15.0,
            "roe": 0.5,
            "profit_dedt": 80_000_000.0,
        }],
        [{
            **common,
            "f_ann_date": "20260820",
            "report_type": "1",
            "n_cashflow_act": 120_000_000.0,
        }],
        [{
            **common,
            "f_ann_date": "20260820",
            "report_type": "1",
            "n_income_attr_p": 100_000_000.0,
        }],
    )


def _financial(module, rows):
    return module.financial_fields(STOCK_CODE, *rows, TARGET_DATE, REPORT_PERIOD)


def _snapshot():
    observations, adjustments = _history()
    return {
        "universe": [_universe_row()],
        "observations": observations,
        "adjustments": adjustments,
        "market_gate": {
            "as_of_date": TARGET_DATE,
            "state": "OFF",
            "market_state": "OFF",
            "exposure_cap": 0,
            "reason": "Fixture gate remains authoritative",
        },
    }


def _vendor_data():
    indicator, cashflow, income = _financial_rows()
    return {
        "daily_basic": [{
            "ts_code": STOCK_CODE,
            "trade_date": "20260904",
            "pe_ttm": 12.0,
            "pb": 1.2,
            "turnover_rate": 0.5,
            "volume_ratio": 1.6,
            "total_mv": 12.5,
            "circ_mv": 10.0,
        }],
        "moneyflow": [{
            "ts_code": STOCK_CODE,
            "trade_date": "20260904",
            "net_mf_amount": -2.25,
        }],
        "fina_indicator": indicator,
        "cashflow": cashflow,
        "income": income,
    }


def _fixture_database(tmp_path, *, universe_date=TARGET_DATE, observation_date=TARGET_DATE):
    path = tmp_path / "isolated-research-fixture.duckdb"
    with duckdb.connect(str(path)) as conn:
        conn.execute(
            "create table choice_stock_universe "
            "(as_of_date varchar, stock_code varchar, stock_name varchar)"
        )
        conn.execute(
            "create table choice_stock_daily_observation "
            "(trade_date varchar, stock_code varchar, close_value double, open_value double, "
            "high_value double, low_value double, volume double, amount double, pctchange double, "
            "tradestatus varchar, vendor_version varchar)"
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?, ?)",
            [(universe_date, f"00000{index}.SZ", f"Fixture {index}") for index in range(1, 5)],
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (observation_date, "000001.SZ", 10, 9.9, 10.1, 9.8, 20, 12.5, 0.5,
                 "TRADING", "vv_choice_stock_fixture"),
                (observation_date, "000002.SZ", 10, 9.9, 10.1, 9.8, 20, 12.5, 0.5,
                 "TRADING", "vv_choice_tushare_stock_fixture"),
                (observation_date, "000003.SZ", 10, 9.9, 10.1, 9.8, 20, 12.5, 0.5,
                 "TRADING", "unregistered_vendor"),
                ("2026-09-07", "000001.SZ", 999, 999, 999, 999, 99, 99, 99,
                 "TRADING", "vv_choice_stock_fixture"),
            ],
        )
    return path


def test_validate_date_accepts_iso_calendar_date(module):
    assert module.validate_date(TARGET_DATE) == TARGET_DATE


@pytest.mark.parametrize("value", ["2026-02-30", "2026-13-01", "2026-09-04junk", ""])
def test_validate_date_rejects_invalid_or_ambiguous_dates(module, value):
    with pytest.raises(ValueError):
        module.validate_date(value)


def test_daily_rows_require_exact_date_and_reject_conflicting_natural_keys(module):
    row = {"ts_code": STOCK_CODE, "trade_date": "20260904", "total_mv": 12.5}
    result = module.normalize_daily_rows([row], TARGET_DATE, "daily_basic")
    assert result[STOCK_CODE]["total_mv"] == 12.5
    with pytest.raises(ValueError):
        module.normalize_daily_rows([{**row, "trade_date": "20260903"}], TARGET_DATE, "daily_basic")
    with pytest.raises(ValueError):
        module.normalize_daily_rows([row, {**row, "total_mv": 13.0}], TARGET_DATE, "daily_basic")


def test_technical_metrics_use_target_adjustment_basis_across_split(module):
    rows, adjustments = _history(split=True)
    stock = module.technical_stock(_universe_row(), rows, adjustments, TARGET_DATE)
    assert stock["close"] == pytest.approx(16.0)
    assert stock["ma20"] == pytest.approx(15.05)
    assert stock["ma60"] == pytest.approx(13.05)
    assert stock["return20"] == pytest.approx(16.0 / 14.0 - 1)
    assert stock["pct_change"] == pytest.approx(0.005)
    assert stock["amount_yuan"] == 400_000_000.0
    assert stock["technical_pass"] is True
    assert stock["fail_reasons"] == []


def test_short_history_keeps_unavailable_metrics_null(module):
    rows, adjustments = _history(count=20)
    stock = module.technical_stock(_universe_row(), rows, adjustments, TARGET_DATE)
    assert stock["ma20"] == pytest.approx(10.95)
    assert stock["ma60"] is None
    assert stock["return20"] is None
    assert stock["technical_pass"] is False
    assert stock["fail_reasons"]


def test_incomplete_adjustment_window_does_not_fabricate_returns(module):
    rows, adjustments = _history()
    adjustments.pop(-10)
    stock = module.technical_stock(_universe_row(), rows, adjustments, TARGET_DATE)
    assert stock["ma20"] is None
    assert stock["ma60"] is None
    assert stock["return20"] is None
    assert stock["technical_pass"] is False


def test_future_price_cannot_enter_asof_technical_window(module):
    rows, adjustments = _history()
    rows.append({**rows[-1], "trade_date": "2026-09-07", "close_value": 999.0})
    adjustments.append({**adjustments[-1], "trade_date": "2026-09-07"})
    with pytest.raises(ValueError, match="future"):
        module.technical_stock(_universe_row(), rows, adjustments, TARGET_DATE)


@pytest.mark.parametrize("change", [{"tradestatus": "SUSPENDED"}, {"amount_yuan": 1.0}])
def test_nontradable_or_illiquid_stock_retains_facts_with_failure_reasons(module, change):
    rows, adjustments = _history()
    rows[-1].update(change)
    stock = module.technical_stock(_universe_row(), rows, adjustments, TARGET_DATE)
    assert stock["close"] == pytest.approx(16.0)
    assert stock["technical_pass"] is False
    assert stock["fail_reasons"]


def test_financial_units_and_same_period_cash_quality(module):
    financial = _financial(module, _financial_rows())
    assert financial["report_period"] == REPORT_PERIOD
    assert financial["ann_date"] == "2026-08-20"
    assert financial["revenue_yoy"] == pytest.approx(0.12)
    assert financial["profit_yoy"] == pytest.approx(0.20)
    assert financial["deducted_profit_yoy"] == pytest.approx(0.15)
    assert financial["roe"] == pytest.approx(0.005)
    assert financial["deducted_profit_yuan"] == 80_000_000.0
    assert financial["ocf_yuan"] == 120_000_000.0
    assert financial["parent_profit_yuan"] == 100_000_000.0
    assert financial["ocf_to_parent_profit"] == pytest.approx(1.2)
    assert financial["financial_coverage"] == "complete"
    assert financial["financial_status"] == "growth_cash_supported"


def test_consolidated_cash_quality_keeps_parent_support_and_records_counterevidence(module):
    rows = _financial_rows()
    rows[1][0]["comp_type"] = "1"
    rows[2][0].update(comp_type="1", n_income=200_000_000.0, minority_gain=100_000_000.0)
    financial = _financial(module, rows)
    assert financial["consolidated_profit_yuan"] == 200_000_000.0
    assert financial["minority_profit_yuan"] == 100_000_000.0
    assert financial["ocf_to_consolidated_profit"] == pytest.approx(0.6)
    assert financial["ocf_to_parent_profit"] == pytest.approx(1.2)
    assert financial["financial_coverage"] == "complete"
    assert financial["financial_status"] == "growth_cash_supported"
    assert "ocf_parent_ratio_supported_but_consolidated_ratio_below_one" in financial["notes"]


@pytest.mark.parametrize("denominator", [None, 0.0, -10_000_000.0])
def test_consolidated_cash_ratio_requires_positive_denominator_without_changing_old_coverage(module, denominator):
    rows = _financial_rows()
    rows[1][0]["comp_type"] = "1"
    rows[2][0].update(comp_type="1", n_income=denominator)
    financial = _financial(module, rows)
    assert financial["consolidated_profit_yuan"] == denominator
    assert financial["minority_profit_yuan"] is None
    assert financial["ocf_to_consolidated_profit"] is None
    assert financial["financial_coverage"] == "complete"
    assert financial["financial_status"] == "growth_cash_supported"
    assert "ocf_parent_ratio_supported_but_consolidated_ratio_below_one" not in financial["notes"]


def test_missing_consolidated_fields_do_not_derive_minority_profit_or_change_old_support(module):
    financial = _financial(module, _financial_rows())
    assert financial["consolidated_profit_yuan"] is None
    assert financial["minority_profit_yuan"] is None
    assert financial["ocf_to_consolidated_profit"] is None
    assert financial["financial_coverage"] == "complete"
    assert financial["financial_status"] == "growth_cash_supported"


@pytest.mark.parametrize("cash_type,income_type", [(None, "1"), ("1", None), (None, None), ("", "1")])
def test_consolidated_cash_ratio_requires_known_company_types_without_changing_old_support(module,
                                                                                           cash_type, income_type):
    rows = _financial_rows()
    rows[1][0]["comp_type"] = cash_type
    rows[2][0].update(comp_type=income_type, n_income=200_000_000.0, minority_gain=100_000_000.0)
    financial = _financial(module, rows)
    assert financial["consolidated_profit_yuan"] == 200_000_000.0
    assert financial["minority_profit_yuan"] == 100_000_000.0
    assert financial["ocf_to_consolidated_profit"] is None
    assert financial["ocf_to_parent_profit"] == pytest.approx(1.2)
    assert financial["financial_coverage"] == "complete"
    assert financial["financial_status"] == "growth_cash_supported"
    assert "consolidated_cash_ratio_company_type_missing" in financial["notes"]


@pytest.mark.parametrize("change", [
    {"end_date": "20260331"},
    {"ann_date": "20260905"},
    {"f_ann_date": "20260905"},
    {"report_type": "6"},
    {"comp_type": "2"},
])
def test_consolidated_cash_quality_preserves_report_date_type_and_company_boundaries(module, change):
    rows = _financial_rows()
    rows[1][0]["comp_type"] = "1"
    rows[2][0].update(comp_type="1", n_income=200_000_000.0, minority_gain=100_000_000.0)
    rows[2][0].update(change)
    financial = _financial(module, rows)
    assert financial["consolidated_profit_yuan"] is None
    assert financial["minority_profit_yuan"] is None
    assert financial["ocf_to_consolidated_profit"] is None
    assert financial["ocf_to_parent_profit"] is None
    assert financial["financial_status"] == "insufficient_data"
    assert financial["notes"]


def test_financial_supported_discovery_includes_rank_21_without_changing_shortlist_or_off_gate(module):
    snapshot = _snapshot()
    base_observations, base_adjustments = snapshot["observations"], snapshot["adjustments"]
    snapshot.update(universe=[], observations=[], adjustments=[])
    data = {name: [] for name in _vendor_data()}
    base_data = _vendor_data()
    for index in range(1, 45):
        code = f"{index:06d}.SZ"
        snapshot["universe"].append(_universe_row(code))
        snapshot["observations"].extend({**row, "stock_code": code,
                                         "amount_yuan": 100_000_000.0 if index == 44 else row["amount_yuan"]}
                                        for row in base_observations)
        snapshot["adjustments"].extend({**row, "stock_code": code} for row in base_adjustments)
        for name, rows in base_data.items():
            if index == 43 and name == "cashflow":
                continue
            for row in rows:
                copied = {**row, "ts_code": code}
                if index <= 20 and name == "fina_indicator":
                    copied["dt_netprofit_yoy"] = -15.0
                data[name].append(copied)
    original = deepcopy((snapshot, data))
    result = module.build_result(snapshot, data, TARGET_DATE, "2026-09-04T19:00:00+08:00")
    assert (snapshot, data) == original
    assert [stock["code"] for stock in result["shortlist"]] == [f"{index:06d}.SZ" for index in range(1, 21)]
    discovered = result["financial_supported_candidates"]
    assert [stock["code"] for stock in discovered] == [f"{index:06d}.SZ" for index in range(21, 41)]
    assert [stock["technical_rank"] for stock in discovered] == list(range(21, 41))
    assert result["quality"]["financial_supported_count"] == 22
    assert result["quality"]["technical_pass_count"] == 43
    assert result["quality"]["shortlist_count"] == 20
    assert all(stock["research_status"] == "observation_only" for stock in discovered)
    assert all("market_gate_OFF" in stock["fail_reasons"] for stock in discovered)
    assert result["market_gate"]["state"] == "OFF"
    assert result["formal_use_allowed"] is False
    assert result["rules"]["execution_allowed"] is False
    assert result["rules"]["financial_supported_candidates_limit"] == 20
    assert result["rules"]["financial_research_extension_version"] == 1
    assert "research_discovery_only" in result["rules"]["financial_supported_candidates_use"]
    assert result["schema_version"] == 1


@pytest.mark.parametrize("ann_date", [None, "20260905"])
def test_missing_or_future_announcement_never_uses_report_end_date(module, ann_date):
    rows = _financial_rows()
    for dataset in rows:
        dataset[0]["ann_date"] = ann_date
    financial = _financial(module, rows)
    assert financial["ann_date"] is None
    assert financial["revenue_yoy"] is None
    assert financial["ocf_yuan"] is None
    assert financial["parent_profit_yuan"] is None
    assert financial["ocf_to_parent_profit"] is None
    assert financial["financial_coverage"] == "missing"
    assert financial["financial_status"] == "insufficient_data"
    assert financial["notes"]


def test_future_actual_announcement_cannot_replace_available_cashflow(module):
    rows = _financial_rows()
    rows[1].append({**rows[1][0], "f_ann_date": "20260905", "n_cashflow_act": 999_000_000.0})
    financial = _financial(module, rows)
    assert financial["ocf_yuan"] == 120_000_000.0
    assert financial["ocf_to_parent_profit"] == pytest.approx(1.2)


def test_future_indicator_revision_cannot_replace_available_growth(module):
    rows = _financial_rows()
    rows[0].append({**rows[0][0], "ann_date": "20260905", "or_yoy": 999.0})
    financial = _financial(module, rows)
    assert financial["ann_date"] == "2026-08-20"
    assert financial["revenue_yoy"] == pytest.approx(0.12)


@pytest.mark.parametrize("dataset_index", [1, 2])
def test_cash_ratio_excludes_nonconsolidated_statement_type(module, dataset_index):
    rows = _financial_rows()
    rows[dataset_index][0]["report_type"] = "2"
    financial = _financial(module, rows)
    assert financial["ocf_to_parent_profit"] is None
    assert financial["financial_coverage"] == "partial"
    assert financial["notes"]


def test_cash_ratio_requires_matching_report_period(module):
    rows = _financial_rows()
    rows[2][0]["end_date"] = "20260331"
    financial = _financial(module, rows)
    assert financial["ocf_yuan"] == 120_000_000.0
    assert financial["parent_profit_yuan"] is None
    assert financial["ocf_to_parent_profit"] is None
    assert financial["financial_status"] == "insufficient_data"


def test_zero_parent_profit_does_not_emit_infinite_cash_ratio(module):
    rows = _financial_rows()
    rows[2][0]["n_income_attr_p"] = 0.0
    financial = _financial(module, rows)
    assert financial["parent_profit_yuan"] == 0.0
    assert financial["ocf_to_parent_profit"] is None


@pytest.mark.parametrize("roe, coverage", [(None, "partial"), (0.0, "complete")])
def test_missing_or_zero_roe_cannot_be_growth_cash_supported(module, roe, coverage):
    rows = _financial_rows()
    rows[0][0]["roe"] = roe
    financial = _financial(module, rows)
    assert financial["financial_coverage"] == coverage
    assert financial["financial_status"] != "growth_cash_supported"


def test_research_export_preserves_off_gate_and_normalizes_vendor_units(module):
    snapshot = _snapshot()
    original = deepcopy(snapshot)
    result = module.build_result(snapshot, _vendor_data(), TARGET_DATE, "2026-09-04T19:00:00+08:00")
    assert snapshot == original
    assert result["formal_use_allowed"] is False
    for key, value in original["market_gate"].items():
        assert result["market_gate"][key] == value
    stock = result["stocks"][0]
    assert stock["technical_pass"] is True
    assert "market_gate_OFF" in stock["fail_reasons"]
    assert "observation_only" in stock["research_status"]
    assert stock["total_mv_yuan"] == 125_000.0
    assert stock["circ_mv_yuan"] == 100_000.0
    assert stock["net_mf_amount_yuan"] == -22_500.0
    assert stock["turnover_rate"] == pytest.approx(0.005)
    assert stock["volume_ratio"] == 1.6


def test_research_export_retains_universe_stock_without_daily_or_financial_rows(module):
    snapshot = _snapshot()
    missing_code = "600001.SH"
    snapshot["universe"].append(_universe_row(missing_code, "Missing Inputs"))
    result = module.build_result(snapshot, _vendor_data(), TARGET_DATE, "2026-09-04T19:00:00+08:00")
    assert len(result["stocks"]) == 2
    missing = next(stock for stock in result["stocks"] if stock["code"] == missing_code)
    assert missing["close"] is None
    assert missing["revenue_yoy"] is None
    assert missing["technical_pass"] is False
    assert missing["fail_reasons"]


def test_market_session_gap_does_not_extend_stock_technical_windows(module):
    snapshot = _snapshot()
    snapshot["sessions"] = [row["trade_date"] for row in snapshot["observations"]]
    snapshot["observations"].pop(-10)
    result = module.build_result(snapshot, _vendor_data(), TARGET_DATE, "2026-09-04T19:00:00+08:00")
    stock = result["stocks"][0]
    assert stock["ma20"] is None
    assert stock["ma60"] is None
    assert stock["return20"] is None
    assert stock["technical_pass"] is False


def test_snapshot_reads_exact_date_universe_without_losing_missing_stock(module, tmp_path):
    path = _fixture_database(tmp_path)
    original_bytes = path.read_bytes()
    snapshot = module.load_moss_snapshot(path, TARGET_DATE)
    assert path.read_bytes() == original_bytes
    assert len(snapshot["universe"]) == 4
    assert {row["stock_code"] for row in snapshot["universe"]} == {
        "000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ",
    }
    assert {str(row["trade_date"]) for row in snapshot["observations"]} == {TARGET_DATE}
    assert snapshot["market_gate"]["state"] == "PENDING_DATA"
    result = module.build_result(snapshot, {}, TARGET_DATE, "2026-09-04T19:00:00+08:00")
    assert result["universe_count"] == 4
    missing = next(stock for stock in result["stocks"] if stock["code"] == "000004.SZ")
    assert missing["close"] is None
    assert missing["technical_pass"] is False


def test_snapshot_honors_the_selected_immutable_read_database(module, tmp_path, monkeypatch):
    from backend.app.repositories.duckdb_read_context import DuckDBReadSelection, duckdb_read_scope

    active = _fixture_database(tmp_path)
    selected_root = tmp_path / "selected"
    selected_root.mkdir()
    selected = _fixture_database(selected_root)
    with duckdb.connect(str(selected)) as conn:
        conn.execute("delete from choice_stock_universe where stock_code = '000004.SZ'")
    active_before = active.read_bytes()
    selected_before = selected.read_bytes()
    original_connect = duckdb.connect
    opens: list[str] = []

    def connect(database: str, *, read_only: bool):
        assert read_only is True
        opens.append(database)
        return original_connect(database, read_only=read_only)

    monkeypatch.setattr(duckdb, "connect", connect)
    selection = DuckDBReadSelection(str(active), str(selected), "research-selected")
    with duckdb_read_scope(selection, required_online=True):
        snapshot = module.load_moss_snapshot(active, TARGET_DATE)
    assert {row["stock_code"] for row in snapshot["universe"]} == {"000001.SZ", "000002.SZ", "000003.SZ"}
    assert opens == [str(selected.resolve())]
    assert snapshot["source"] == str(selected.resolve())
    assert active.read_bytes() == active_before
    assert selected.read_bytes() == selected_before


def test_snapshot_refuses_active_fallback_when_online_selection_is_required(module, tmp_path):
    from backend.app.repositories.duckdb_read_context import DuckDBOnlineReadRequiredError, duckdb_read_scope

    target = _fixture_database(tmp_path)
    before = target.read_bytes()
    with duckdb_read_scope(None, required_online=True, active_path=str(target)):
        with pytest.raises(DuckDBOnlineReadRequiredError):
            module.load_moss_snapshot(target, TARGET_DATE)
    assert target.read_bytes() == before


def test_snapshot_normalizes_native_tushare_and_unknown_vendor_units(module, tmp_path):
    snapshot = module.load_moss_snapshot(_fixture_database(tmp_path), TARGET_DATE)
    observed = {row["stock_code"]: row for row in snapshot["observations"]}
    assert observed["000001.SZ"]["amount_yuan"] == 12.5
    assert observed["000001.SZ"]["volume_shares"] == 20.0
    assert observed["000002.SZ"]["amount_yuan"] == 12_500.0
    assert observed["000002.SZ"]["volume_shares"] == 2_000.0
    assert observed["000003.SZ"]["amount_yuan"] is None
    assert observed["000003.SZ"]["volume_shares"] is None


@pytest.mark.parametrize("missing_dataset", ["universe", "observations"])
def test_snapshot_rejects_absent_target_date_instead_of_using_latest(module, tmp_path, missing_dataset):
    path = _fixture_database(
        tmp_path,
        universe_date="2026-09-03" if missing_dataset == "universe" else TARGET_DATE,
        observation_date="2026-09-03" if missing_dataset == "observations" else TARGET_DATE,
    )
    with pytest.raises(ValueError, match="exact-date"):
        module.load_moss_snapshot(path, TARGET_DATE)


def test_vendor_archive_retains_raw_duplicates_and_records_usable_row_count(module, tmp_path, monkeypatch):
    payload = {
        "code": 0,
        "data": {
            "fields": ["ts_code", "ann_date", "end_date", "n_cashflow_act"],
            "items": [
                [STOCK_CODE, "20260820", "20260630", 120_000_000.0],
                [STOCK_CODE, "20260820", "20260630", 120_000_000.0],
            ],
        },
    }
    response = SimpleNamespace(status_code=200, json=lambda: payload, raise_for_status=lambda: None)
    monkeypatch.setattr("requests.post", lambda *_args, **_kwargs: response)
    sources = []
    archive = module.VendorArchive(tmp_path, "fixture-secret-never-archive", sources)
    rows = archive.fetch("cashflow_vip", module.FIELDS["cashflow"], {"period": "20260630"})
    assert len(rows) == 1
    entry = sources[0]
    assert entry["status"] == "success"
    assert entry["row_count"] == 2
    assert entry["identical_duplicate_row_count"] == 1
    assert entry["usable_distinct_row_count"] == 1
    raw = (tmp_path / entry["relative_path"]).read_bytes()
    assert len(json.loads(raw)["data"]["items"]) == 2
    assert hashlib.sha256(raw).hexdigest() == entry["sha256"]


def test_vendor_error_never_archives_credential_echo(module, tmp_path, monkeypatch):
    token = "fixture-secret-never-archive"
    payload = {"code": -2001, "msg": f"Invalid token: {token}", "data": None}
    response = SimpleNamespace(status_code=200, json=lambda: payload, raise_for_status=lambda: None)
    monkeypatch.setattr("requests.post", lambda *_args, **_kwargs: response)
    sources = []
    archive = module.VendorArchive(tmp_path, token, sources)
    assert archive.fetch("income_vip", module.FIELDS["income"], {"period": "20260630"}) == []
    entry = sources[0]
    assert entry["status"] == "failed"
    assert "[REDACTED]" in entry["error"]
    assert token not in json.dumps(sources)
    raw = (tmp_path / entry["relative_path"]).read_bytes()
    assert token.encode() not in raw
    assert "[REDACTED]" in json.loads(raw)["msg"]
    assert hashlib.sha256(raw).hexdigest() == entry["sha256"]


def _calendar_fixture():
    snapshot = _snapshot()
    snapshot["sessions"] = [row["trade_date"] for row in snapshot["observations"]]
    start = date.fromisoformat(min(snapshot["sessions"]))
    end = date.fromisoformat(TARGET_DATE)
    rows = [{"exchange": "SSE", "cal_date": (start + timedelta(days=offset)).strftime("%Y%m%d"),
             "is_open": int((start + timedelta(days=offset)).weekday() < 5)}
            for offset in range((end - start).days + 1)]
    return snapshot, rows


def test_calendar_detects_whole_market_missing_session(module):
    snapshot, calendar = _calendar_fixture()
    snapshot["sessions"].pop(-10)
    with pytest.raises(ValueError, match="whole-market session gaps"):
        module.validate_market_sessions(snapshot, calendar, TARGET_DATE)


@pytest.mark.parametrize("bad_calendar", ["missing_day", "duplicate", "future_day", "wrong_exchange"])
def test_calendar_rejects_incomplete_or_wrong_contract(module, bad_calendar):
    snapshot, calendar = _calendar_fixture()
    if bad_calendar == "missing_day":
        calendar.pop(10)
    elif bad_calendar == "duplicate":
        calendar.append(dict(calendar[0]))
    elif bad_calendar == "future_day":
        calendar.append({"exchange": "SSE", "cal_date": "20260907", "is_open": 1})
    else:
        calendar[0]["exchange"] = "SZSE"
    with pytest.raises(ValueError):
        module.validate_market_sessions(snapshot, calendar, TARGET_DATE)


def test_calendar_verified_window_is_disclosed(module):
    snapshot, calendar = _calendar_fixture()
    data = _vendor_data()
    data["trade_cal"] = calendar
    result = module.build_result(snapshot, data, TARGET_DATE, "2026-09-04T19:00:00+08:00")
    assert result["datasets"]["trade_cal"]["status"] == "complete"
    assert result["rules"]["market_calendar"]["open_session_count"] == 61


def test_compressed_moss_snapshot_is_replayable_and_hashes_real_bytes(module, tmp_path):
    snapshot, _ = _calendar_fixture()
    sources = []
    entry = module.archive_moss_snapshot(snapshot, tmp_path, sources)
    archived = (tmp_path / entry["relative_path"]).read_bytes()
    assert entry["sha256"] == hashlib.sha256(archived).hexdigest()
    replayed = json.loads(gzip.decompress(archived))
    before = module.build_result(snapshot, _vendor_data(), TARGET_DATE, "fixture")
    after = module.build_result(replayed, _vendor_data(), TARGET_DATE, "fixture")
    assert before["stocks"] == after["stocks"]


def test_identical_business_rows_with_different_update_flags_are_merged(module):
    indicator, cashflow, income = _financial_rows()
    cashflow[0]["update_flag"] = "0"
    cashflow.append({**cashflow[0], "update_flag": "1"})
    result = module.financial_fields(STOCK_CODE, indicator, cashflow, income, TARGET_DATE, REPORT_PERIOD)
    assert result["ocf_yuan"] == 120_000_000.0
    assert result["cashflow_update_flag"] == "1"


def test_quarter_end_uses_latest_announced_previous_period(module):
    indicator, cashflow, income = _financial_rows()
    future = {**indicator[0], "end_date": "20260930", "ann_date": "20261020", "or_yoy": 99.0}
    result = module.financial_fields(STOCK_CODE, indicator + [future], cashflow, income,
                                     "2026-09-30", "2026-09-30")
    assert result["report_period"] == "2026-06-30"
    assert result["queried_report_periods"] == ["2026-09-30", "2026-06-30"]
    assert result["revenue_yoy"] == pytest.approx(0.12)
    assert result["ocf_to_parent_profit"] == pytest.approx(1.2)


def test_newly_announced_period_never_borrows_old_period_cash_or_profit(module):
    indicator, cashflow, income = _financial_rows()
    new = {**indicator[0], "end_date": "20260930", "ann_date": "20261020", "or_yoy": 30.0}
    result = module.financial_fields(STOCK_CODE, indicator + [new], cashflow, income,
                                     "2026-10-21", "2026-09-30")
    assert result["report_period"] == "2026-09-30"
    assert result["revenue_yoy"] == pytest.approx(0.30)
    assert result["ocf_yuan"] is None
    assert result["parent_profit_yuan"] is None
    assert result["ocf_to_parent_profit"] is None
    assert result["financial_coverage"] == "partial"


def test_latest_indicator_conflict_does_not_silently_fall_back_to_old_period(module):
    indicator, cashflow, income = _financial_rows()
    new = {**indicator[0], "end_date": "20260930", "ann_date": "20261020", "or_yoy": 30.0}
    conflicting = {**new, "or_yoy": 31.0}
    result = module.financial_fields(STOCK_CODE, indicator + [new, conflicting], cashflow, income,
                                     "2026-10-21", "2026-09-30")
    assert result["report_period"] == "2026-09-30"
    assert result["revenue_yoy"] is None
    assert "fina_indicator:conflicting_report_versions" in result["notes"]


def test_missing_adjustments_degrade_overall_status_without_masking_data_gap(module):
    snapshot = _snapshot()
    snapshot["adjustments"] = []
    result = module.build_result(snapshot, _vendor_data(), TARGET_DATE, "fixture")
    assert result["status"] == "degraded"
    assert result["quality"]["technical_pass_count"] == 0
    assert result["quality"]["technical_data_gap_stock_count"] == 1
    reasons = result["quality"]["technical_data_gap_reason_counts"]
    assert reasons["target_date_adjustment_missing"] == 1
    assert reasons["historical_adjustment_missing_or_nonpositive"] == 1
    assert any("technical data gaps" in warning for warning in result["warnings"])


def test_normal_st_and_liquidity_rejections_are_not_technical_data_gaps(module):
    snapshot = _snapshot()
    snapshot["universe"][0]["stock_name"] = "ST Fixture"
    snapshot["observations"][-1]["amount_yuan"] = 100_000_000
    result = module.build_result(snapshot, _vendor_data(), TARGET_DATE, "fixture")
    assert result["quality"]["technical_pass_count"] == 0
    assert result["quality"]["technical_data_gap_stock_count"] == 0
    assert result["quality"]["technical_data_gap_reason_counts"] == {}
    assert result["status"] == "ready"


def _fetch_financial_page_fixture(module, tmp_path, monkeypatch, financial_response):
    snapshot, calendar = _calendar_fixture()
    calls = []
    token = "fixture-secret-never-archive"

    def post(_url, *, json, timeout):
        assert timeout == 45
        endpoint, params = json["api_name"], json["params"]
        if endpoint == "trade_cal":
            fields = ["exchange", "cal_date", "is_open"]
            payload = {"code": 0, "data": {"fields": fields,
                       "items": [[row[field] for field in fields] for row in calendar]}}
        elif endpoint in {"daily_basic", "moneyflow"}:
            payload = {"code": 0, "data": {"fields": [], "items": []}}
        else:
            calls.append((endpoint, dict(params)))
            payload = financial_response(endpoint, params, token)
        return SimpleNamespace(status_code=200, json=lambda: payload, raise_for_status=lambda: None)

    monkeypatch.setattr("requests.post", post)
    sources = []
    archive = module.VendorArchive(tmp_path, token, sources)
    data = module.fetch_vendor_data(archive, snapshot, TARGET_DATE, module.DEFAULT_MIN_AMOUNT)
    return data, sources, calls, token


def _cashflow_page(items):
    return {"code": 0, "data": {"fields": ["ts_code", "ann_date", "end_date", "report_type",
                                           "n_cashflow_act", "update_flag"], "items": items}}


def test_financial_pagination_advances_raw_rows_and_requires_terminal_empty_page(module, tmp_path, monkeypatch):
    row = [STOCK_CODE, "20260820", "20260630", "1", 120_000_000.0, "0"]

    def response(endpoint, params, _token):
        if endpoint == "cashflow_vip" and params["period"] == "20260630":
            return _cashflow_page({0: [row, row], 2: [[*row[:-1], "1"]], 3: []}[params["offset"]])
        return _cashflow_page([])

    data, sources, calls, token = _fetch_financial_page_fixture(module, tmp_path, monkeypatch, response)
    pages = [entry for entry in sources if entry["endpoint"] == "cashflow_vip"
             and entry["params"]["period"] == "20260630"]
    assert [entry["params"]["offset"] for entry in pages] == [0, 2, 3]
    assert [entry["row_count"] for entry in pages] == [2, 1, 0]
    assert all(entry["params"]["limit"] == 2000 for entry in pages)
    assert all(entry["params"]["report_type"] == "1" for entry in pages)
    assert all(entry["pagination_complete"] for entry in pages)
    assert pages[0]["usable_distinct_row_count"] == 1
    chosen = module._financial_record(STOCK_CODE, data["cashflow"], TARGET_DATE, REPORT_PERIOD, "cashflow", [])
    assert chosen["update_flag"] == "1"
    assert chosen["n_cashflow_act"] == 120_000_000.0
    assert module.financial_fields(STOCK_CODE, [], data["cashflow"], [], TARGET_DATE,
                                   REPORT_PERIOD)["financial_coverage"] == "partial"
    assert not any(endpoint == "cashflow" and params["period"] == "20260630"
                   for endpoint, params in calls)
    for entry in sources:
        raw = (tmp_path / entry["relative_path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
        assert token.encode() not in raw


@pytest.mark.parametrize("failure", ["repeat_page", "ignored_limit"])
def test_financial_pagination_stops_ignored_parameters_as_partial(module, tmp_path, monkeypatch, failure):
    row = [STOCK_CODE, "20260820", "20260630", "1", 120_000_000.0, "0"]

    def response(endpoint, params, _token):
        if endpoint == "cashflow_vip" and params["period"] == "20260630":
            return _cashflow_page([row] * (2001 if failure == "ignored_limit" else 2))
        return _cashflow_page([])

    data, sources, calls, _ = _fetch_financial_page_fixture(module, tmp_path, monkeypatch, response)
    pages = [entry for entry in sources if entry["endpoint"] == "cashflow_vip"
             and entry["params"]["period"] == "20260630"]
    assert len(pages) == (1 if failure == "ignored_limit" else 2)
    assert pages[-1]["status"] == "failed"
    assert pages[-1]["possible_truncation"] is True
    assert not any(entry["pagination_complete"] for entry in pages)
    assert len(data["cashflow"]) == (0 if failure == "ignored_limit" else 1)
    assert not any(endpoint == "cashflow" and params["period"] == "20260630"
                   for endpoint, params in calls)


def test_financial_pagination_caps_requests_when_vendor_never_returns_empty(module, tmp_path, monkeypatch):
    def response(endpoint, params, _token):
        if endpoint == "cashflow_vip" and params["period"] == "20260630":
            return _cashflow_page([[f"{params['offset']:06d}.SZ", "20260820", "20260630",
                                   "1", 120_000_000.0, "0"]])
        return _cashflow_page([])

    _data, sources, _calls, _token = _fetch_financial_page_fixture(module, tmp_path, monkeypatch, response)
    pages = [entry for entry in sources if entry["endpoint"] == "cashflow_vip"
             and entry["params"]["period"] == "20260630"]
    assert len(pages) == 100
    assert pages[-1]["params"]["offset"] == 99
    assert pages[-1]["status"] == "failed"
    assert pages[-1]["possible_truncation"] is True
    assert "100-page safety bound" in pages[-1]["error"]
    assert not any(entry["pagination_complete"] for entry in pages)


@pytest.mark.parametrize("failure", ["permission", "transport"])
def test_financial_pagination_stops_failed_period_and_redacts_secret(module, tmp_path, monkeypatch, failure):
    import requests

    def response(_endpoint, _params, token):
        if failure == "transport":
            raise requests.ConnectionError(f"fixture connection error: {token}")
        return {"code": -2001, "msg": f"fixture permission denied: {token}", "data": None}

    data, sources, calls, token = _fetch_financial_page_fixture(module, tmp_path, monkeypatch, response)
    assert len(calls) == 6
    assert all(params["offset"] == 0 for _endpoint, params in calls)
    assert all(endpoint.endswith("_vip") for endpoint, _params in calls)
    assert all(data[name] == [] for name in ("cashflow", "income", "fina_indicator"))
    failed = [entry for entry in sources if entry["status"] == "failed"]
    assert len(failed) == 6
    assert all(not entry["pagination_complete"] for entry in failed)
    assert all(entry["error_kind"] == ("transport" if failure == "transport" else "vendor_or_contract")
               for entry in failed)
    assert token not in json.dumps(sources)
    for entry in sources:
        assert token.encode() not in (tmp_path / entry["relative_path"]).read_bytes()


def test_sparse_financial_duplicate_selects_real_dominating_source_without_mutation(module):
    complete = {"ts_code": "601952.SH", "ann_date": "20260819", "end_date": "20260630",
                "roe": 2.0237, "profit_dedt": 116075734.56, "dt_netprofit_yoy": -33.85,
                "netprofit_yoy": -32.4827, "or_yoy": -5.5936, "fixture_zero": 0.0}
    sparse = {**complete, "profit_dedt": None, "dt_netprofit_yoy": None, "fixture_zero": None}
    rows = [sparse, complete]
    before = deepcopy(rows)
    notes = []
    selected = module._financial_record("601952.SH", rows, TARGET_DATE, REPORT_PERIOD,
                                        "fina_indicator", notes)
    assert selected is complete
    assert selected["profit_dedt"] == 116075734.56
    assert selected["dt_netprofit_yoy"] == -33.85
    assert selected["fixture_zero"] == 0.0
    assert rows == before
    assert notes == ["fina_indicator:sparse_duplicate_reconciled"]


@pytest.mark.parametrize("conflict_field, conflict_value", [("roe", 0.6), ("update_flag", "1")])
def test_sparse_financial_duplicate_rejects_nonnull_value_or_metadata_conflict(module, conflict_field,
                                                                           conflict_value):
    complete = {**_financial_rows()[0][0], "update_flag": "0"}
    sparse = {**complete, "profit_dedt": None, conflict_field: conflict_value}
    notes = []
    assert module._financial_record(STOCK_CODE, [sparse, complete], TARGET_DATE, REPORT_PERIOD,
                                     "fina_indicator", notes) == {}
    assert notes == ["fina_indicator:conflicting_report_versions"]


def test_complementary_financial_duplicates_without_a_dominating_source_are_not_combined(module):
    complete = _financial_rows()[0][0]
    first = {**complete, "profit_dedt": None}
    second = {**complete, "dt_netprofit_yoy": None}
    notes = []
    assert module._financial_record(STOCK_CODE, [first, second], TARGET_DATE, REPORT_PERIOD,
                                     "fina_indicator", notes) == {}
    assert notes == ["fina_indicator:conflicting_report_versions"]
