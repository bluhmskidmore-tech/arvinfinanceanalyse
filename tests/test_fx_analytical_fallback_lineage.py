"""MS-010: actual synthetic DuckDB reads and bounded analytical FX regressions.

The duplicate-date helper checks supply an explicit order: the fact SQL has no
revision ordering for equal dates. No provider, real input, or ingestion is used.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.fx_rates import FxRateUnavailableError, get_usd_cny_rate
from backend.app.repositories.duckdb_read_context import DuckDBReadSelection, duckdb_read_scope
from backend.app.services import macro_vendor_service as service

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]

TARGET = date(2026, 10, 6)
USD_NAME = "中间价:美元兑人民币"


def _row(day, value, tag, *, series_id="SYN_USD", name=USD_NAME, quality="ok",
         frequency="daily", unit="CNY/USD"):
    return {
        "group_key": "middle_rate",
        "series_id": series_id,
        "series_name": name,
        "trade_date": str(day),
        "value_numeric": value,
        "frequency": frequency,
        "unit": unit,
        "source_version": f"sv_synthetic_{tag}",
        "vendor_version": f"vv_synthetic_{tag}",
        "quality_flag": quality,
    }


def _seed(path: Path, rows, *, active_series=None, catalog_policy=True):
    with duckdb.connect(str(path)) as conn:
        conn.execute("""create table fact_choice_macro_daily (
            series_id varchar, series_name varchar, trade_date varchar,
            value_numeric double, frequency varchar, unit varchar,
            source_version varchar, vendor_version varchar, quality_flag varchar)
        """)
        conn.execute("""create table phase1_macro_vendor_catalog (
            series_id varchar, series_name varchar, frequency varchar, unit varchar)
        """)
        if catalog_policy:
            for field in ("refresh_tier", "fetch_mode", "fetch_granularity", "policy_note"):
                conn.execute(f"alter table phase1_macro_vendor_catalog add column {field} varchar")
        seen = set()
        for row in rows:
            conn.execute("insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         [row[key] for key in ("series_id", "series_name", "trade_date", "value_numeric",
                                              "frequency", "unit", "source_version", "vendor_version",
                                              "quality_flag")])
            if row["series_id"] in seen:
                continue
            seen.add(row["series_id"])
            conn.execute("""insert into phase1_macro_vendor_catalog
                (series_id, series_name, frequency, unit) values (?, ?, ?, ?)
            """, [row["series_id"], row["series_name"], "catalog-frequency", "catalog-unit"])
        if catalog_policy:
            conn.execute("""update phase1_macro_vendor_catalog set refresh_tier='stable',
                fetch_mode='date_slice', fetch_granularity='single', policy_note='synthetic policy'
            """)
        if active_series is not None:
            conn.execute("create table choice_market_snapshot (series_id varchar)")
            for series_id in active_series:
                conn.execute("insert into choice_market_snapshot values (?)", [series_id])
    return path


def _point(envelope):
    return envelope["result"]["groups"][0]["series"][0]


def _warnings(envelope):
    return envelope["result_meta"]["filters_applied"].get("warnings", [])


def _fallback_rows(*, age=1, invalid=0.0, prefix="usd"):
    return [
        _row(TARGET, invalid, f"{prefix}_invalid", frequency="invalid-frequency", unit="invalid-unit"),
        _row(TARGET - timedelta(days=age), 7.2, f"{prefix}_selected"),
        _row(TARGET - timedelta(days=age + 1), 7.1, f"{prefix}_older"),
    ]


@pytest.mark.parametrize("snapshot", [False, True])
@pytest.mark.parametrize("age", [1, 31])
@pytest.mark.parametrize("invalid", [0.0, -1.0])
def test_fallback_uses_whole_selected_observation(tmp_path, snapshot, age, invalid):
    rows = _fallback_rows(age=age, invalid=invalid)
    path = _seed(tmp_path / "fx.duckdb", rows, active_series=["SYN_USD"] if snapshot else None)
    envelope = service.fx_analytical_envelope(str(path))
    point = _point(envelope)
    for key in ("trade_date", "value_numeric", "source_version", "vendor_version", "frequency", "unit"):
        assert point[key] == rows[1][key], key
    assert point["quality_flag"] == "warning"
    assert point["latest_change"] is None
    assert point["refresh_tier"] == "stable"
    assert point["fetch_mode"] == "date_slice"
    assert point["fetch_granularity"] == "single"
    assert point["policy_note"] == "synthetic policy"
    meta = envelope["result_meta"]
    assert meta["source_version"] == rows[1]["source_version"]
    assert meta["vendor_version"] == rows[1]["vendor_version"]
    assert meta["basis"] == "analytical" and meta["formal_use_allowed"] is False
    assert meta["quality_flag"] == "warning"
    # Catalog fallback mode is deliberately not redefined by rate substitution.
    assert meta["fallback_mode"] == "none"
    assert len(point["recent_points"]) == 3
    for recent, raw in zip(point["recent_points"], rows, strict=True):
        assert recent == {key: raw[key] for key in recent}
    expected = "analytical LOCF" if age <= 30 else "stale fallback beyond 30 days"
    assert any(expected in warning and "SYN_USD" in warning for warning in _warnings(envelope))
    assert any("latest_change" in warning and "fallback" in warning for warning in _warnings(envelope))


@pytest.mark.parametrize("contract", ["delta", "diagnostic", "aggregate_lineage"])
def test_fallback_independent_contract_failures(tmp_path, contract):
    envelope = service.fx_analytical_envelope(str(_seed(tmp_path / "fx.duckdb", _fallback_rows())))
    if contract == "delta":
        assert _point(envelope)["latest_change"] is None
    elif contract == "diagnostic":
        assert any("analytical LOCF" in warning for warning in _warnings(envelope))
    else:
        assert envelope["result_meta"]["source_version"] == "sv_synthetic_usd_selected"
        assert envelope["result_meta"]["vendor_version"] == "vv_synthetic_usd_selected"


@pytest.mark.parametrize("latest,previous,change", [(7.2, 7.1, 0.1), (7.1, 7.1, 0.0), (7.0, 7.1, -0.1)])
@pytest.mark.parametrize("quality", ["ok", "warning"])
@pytest.mark.parametrize("snapshot", [False, True])
def test_valid_latest_keeps_arithmetic_including_warning_quality(tmp_path, latest, previous, change, quality, snapshot):
    rows = [_row(TARGET, latest, "latest", quality=quality), _row(TARGET - timedelta(days=1), previous, "previous")]
    path = _seed(tmp_path / "fx.duckdb", rows, active_series=["SYN_USD"] if snapshot else None)
    envelope = service.fx_analytical_envelope(str(path))
    point = _point(envelope)
    for key in ("trade_date", "value_numeric", "source_version", "vendor_version", "frequency", "unit", "quality_flag"):
        assert point[key] == rows[0][key], key
    assert point["latest_change"] == pytest.approx(change)
    assert _warnings(envelope) == []


def test_one_valid_point_is_null_without_claiming_fallback(tmp_path):
    path = _seed(tmp_path / "fx.duckdb", [_row(TARGET, 7.2, "only")], catalog_policy=False)
    envelope = service.fx_analytical_envelope(str(path))
    point = _point(envelope)
    assert point["latest_change"] is None
    assert point["quality_flag"] == "ok"
    assert _warnings(envelope) == []
    assert point["refresh_tier"] is None and point["policy_note"] is None
    assert service.load_fx_analytical_payload(str(path)).model_dump(mode="json") == envelope["result"]


@pytest.mark.parametrize("name,latest,previous,group", [
    ("中间价:欧元兑人民币", 0.0, -1.0, "middle_rate"),
    ("人民币指数:synthetic", -1.0, 0.0, "fx_index"),
    ("synthetic C-Swap", 0.0, 0.0, "fx_swap_curve"),
    ("synthetic 外汇掉期", -2.0, -1.0, "fx_swap_curve"),
])
def test_non_usd_retains_existing_zero_negative_values(tmp_path, name, latest, previous, group):
    rows = [_row(TARGET, latest, "latest", name=name), _row(TARGET - timedelta(days=1), previous, "previous", name=name)]
    envelope = service.fx_analytical_envelope(str(_seed(tmp_path / "fx.duckdb", rows)))
    point = _point(envelope)
    assert point["group_key"] == group
    assert point["value_numeric"] == latest and point["latest_change"] == latest - previous
    assert point["source_version"] == rows[0]["source_version"]
    assert _warnings(envelope) == []


@pytest.mark.parametrize("invalid", [0.0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_all_invalid_usd_remains_explicit_error(tmp_path, invalid):
    path = _seed(tmp_path / "invalid.duckdb", [_row(TARGET, invalid, "invalid")])
    with pytest.raises(FxRateUnavailableError, match="analytical fallback unavailable.*no valid input"):
        service.fx_analytical_envelope(str(path))


def _resolved_row(rows):
    result = service._resolve_fx_analytical_latest_row(rows)
    # Also lets the exact behavioral assertions run against the frozen old
    # helper's row-only return before the private interface is repaired.
    return result[0] if isinstance(result, tuple) else result


@pytest.mark.parametrize("invalid", [0.0, -1.0, float("nan"), float("inf"), float("-inf")])
def test_same_date_invalid_first_selects_exact_valid_row_metadata(invalid):
    rows = [_row(TARGET, invalid, "invalid"), _row(TARGET, 7.2, "selected", frequency="weekly", unit="selected-unit")]
    selected = _resolved_row(rows)
    for key in ("trade_date", "value_numeric", "source_version", "vendor_version", "frequency", "unit"):
        assert selected[key] == rows[1][key], key
    assert selected["quality_flag"] == "warning"


@pytest.mark.parametrize("age", [0, 1, 31])
@pytest.mark.parametrize("equal_values", [False, True])
def test_duplicate_dates_retain_existing_selector_order(age, equal_values):
    chosen_day = TARGET - timedelta(days=age)
    first = _row(chosen_day, 7.2, "first_revision")
    second = _row(chosen_day, 7.2 if equal_values else 7.3, "second_revision")
    rows = ([first, second] if age == 0 else [_row(TARGET, 0.0, "invalid"), first, second])
    expected = first if age == 0 else second
    rate, observed, _ = get_usd_cny_rate(
        [(date.fromisoformat(row["trade_date"]), Decimal(str(row["value_numeric"]))) for row in rows],
        TARGET, allow_stale_fallback=True)
    assert (float(rate), str(observed)) == (expected["value_numeric"], expected["trade_date"])
    selected = _resolved_row(rows)
    assert selected["source_version"] == expected["source_version"]
    assert selected["vendor_version"] == expected["vendor_version"]
    assert selected["value_numeric"] == expected["value_numeric"]


def test_same_date_substitution_suppresses_delta_with_explicit_warning(tmp_path, monkeypatch):
    rows = [_row(TARGET, 0.0, "invalid"), _row(TARGET, 7.2, "selected")]
    path = _seed(tmp_path / "fx.duckdb", rows)
    # SQL has no tie precedence: inject only the returned ordering here, leaving
    # the catalog, grouping, selector, envelope and all other service work real.
    ordered = [tuple(row[key] for key in ("series_id", "series_name", "trade_date", "value_numeric",
               "frequency", "unit", "source_version", "vendor_version", "quality_flag")) + (index,)
               for index, row in enumerate(rows, 1)]
    monkeypatch.setattr(service, "_load_choice_macro_recent_rows", lambda conn, tables: ordered)
    envelope = service.fx_analytical_envelope(str(path))
    assert _point(envelope)["latest_change"] is None
    assert _point(envelope)["quality_flag"] == "warning"
    assert any("SYN_USD" in warning and "latest_change" in warning and "fallback" in warning
               for warning in _warnings(envelope))


@pytest.mark.parametrize("state", ["absent", "no_schema", "empty", "query_failure", "open_failure"])
def test_existing_empty_and_query_failure_contracts(tmp_path, state):
    path = tmp_path / "fx.duckdb"
    if state == "open_failure":
        path.write_text("synthetic invalid database", encoding="utf-8")
    elif state == "no_schema":
        with duckdb.connect(str(path)):
            pass
    elif state in {"empty", "query_failure"}:
        _seed(path, [])
        if state == "query_failure":
            with duckdb.connect(str(path)) as conn:
                conn.execute("alter table fact_choice_macro_daily drop column value_numeric")
    if state.endswith("failure"):
        with pytest.raises(service.FxAnalyticalReadError, match="DuckDB query failed surface=fx_analytical"):
            service.fx_analytical_envelope(str(path))
    else:
        envelope = service.fx_analytical_envelope(str(path))
        assert envelope["result"]["groups"] == []
        assert envelope["result_meta"]["vendor_version"] == "vv_none"
        assert _warnings(envelope) == []
        assert envelope["result_meta"]["source_version"] == "sv_fx_analytical_empty"


def test_distinct_selected_generations_keep_selected_observation_lineage(tmp_path):
    active = _seed(tmp_path / "active.duckdb", _fallback_rows(prefix="active"))
    snapshots = {tag: _seed(tmp_path / f"{tag}.duckdb", _fallback_rows(prefix=tag)) for tag in ("G1", "G2")}
    for tag in ("G1", "G2", "G1"):
        with duckdb_read_scope(DuckDBReadSelection(active, snapshots[tag], tag), required_online=True):
            envelope = service.fx_analytical_envelope(str(active))
        assert _point(envelope)["source_version"] == f"sv_synthetic_{tag}_selected"
        assert _point(envelope)["vendor_version"] == f"vv_synthetic_{tag}_selected"
        assert envelope["result_meta"]["source_version"] == f"sv_synthetic_{tag}_selected"


def test_formal_selector_stays_strict_while_analytical_fallback_is_allowed():
    target = date(2026, 9, 29)  # A publication business day, outside October holiday.
    rows = [(target, Decimal("0")), (target - timedelta(days=1), Decimal("7.2"))]
    with pytest.raises(FxRateUnavailableError, match="missing official input row"):
        get_usd_cny_rate(rows, target)
    rate, observed, warnings = get_usd_cny_rate(rows, target, allow_stale_fallback=True)
    assert rate == Decimal("7.2") and observed == target - timedelta(days=1)
    assert len(warnings) == 1 and "analytical LOCF" in warnings[0]
