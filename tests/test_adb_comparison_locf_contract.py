"""Signed LOCF balances through the real formal schema, repository and loader."""

from datetime import date
from pathlib import Path

import duckdb
import pytest

from backend.app.services import adb_analysis_service as adb


START = date(2024, 2, 28)
LATEST = date(2024, 2, 29)
END = date(2024, 3, 1)
SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "backend/app/schema_registry/duckdb/05_balance_analysis.sql"
)
SOURCE_SIDES = [
    pytest.param("bond", "asset", id="bond-asset"),
    pytest.param("bond", "liability", id="bond-liability"),
    pytest.param("interbank", "asset", id="interbank-asset"),
    pytest.param("interbank", "liability", id="interbank-liability"),
]


def _formal_db(tmp_path, source, side, rows):
    """Rows are (day, signed amount or SQL NULL, category); no loader mocks."""
    path = tmp_path / "locf-synthetic.duckdb"
    with duckdb.connect(str(path)) as conn:
        for statement in SCHEMA.read_text(encoding="utf-8").split("-- MOSS:STMT"):
            if statement.strip():
                conn.execute(statement)
        for index, (day, amount, category) in enumerate(rows):
            if source == "bond":
                conn.execute(
                    """insert into fact_formal_zqtz_balance_daily
                    (report_date, instrument_code, instrument_name, position_scope,
                     currency_basis, currency_code, market_value_amount, ytm_value,
                     coupon_rate, asset_class, bond_type, is_issuance_like,
                     source_version, rule_version)
                    values (?, ?, 'synthetic', ?, 'CNY', 'CNY', ?, 3, 3, ?, ?, ?,
                            'synthetic', 'synthetic')""",
                    [str(day), str(index), side, amount, side, category, side == "liability"],
                )
            else:
                conn.execute(
                    """insert into fact_formal_tyw_balance_daily
                    (report_date, position_id, product_type, position_side,
                     position_scope, currency_basis, currency_code, principal_amount,
                     funding_cost_rate, source_version, rule_version)
                    values (?, ?, ?, ?, ?, 'CNY', 'CNY', ?, 2, 'synthetic', 'synthetic')""",
                    [str(day), str(index), category, side, side, amount],
                )
    return path


def _category(source, *, other=False):
    if source == "bond":
        return "地方政府债" if other else "国债"
    return "卖出回购" if other else "同业存放"


def _read_comparison(path, source):
    before = path.read_bytes()
    bonds, interbank, *_ = adb._load_adb_raw_data(str(path), START, END)
    payload, *_ = adb.get_adb_comparison(str(path), START, END)
    assert path.read_bytes() == before
    return payload, bonds if source == "bond" else interbank


@pytest.mark.parametrize("source, side", SOURCE_SIDES)
@pytest.mark.parametrize("reverse_rows", [False, True], ids=["forward", "reverse"])
@pytest.mark.parametrize(
    "values",
    [(100, -100), (-100, 100), (100, 0), (0, 0)],
    ids=["positive-negative", "negative-positive", "latest-zero", "all-zero"],
)
def test_real_loader_uses_latest_balance_not_cross_day_net(
    tmp_path, source, side, reverse_rows, values
):
    rows = [(day, amount, _category(source)) for day, amount in zip((START, LATEST), values)]
    path = _formal_db(tmp_path, source, side, rows[::-1] if reverse_rows else rows)
    payload, frame = _read_comparison(path, source)
    plural = "assets" if side == "asset" else "liabilities"

    amount_column = "market_value" if source == "bond" else "amount"
    assert sorted(frame[amount_column].tolist()) == sorted(values)
    assert frame[f"{amount_column}_is_valid"].tolist() == [True, True]
    assert payload[f"total_spot_{plural}"] == values[-1]
    assert payload[f"total_avg_{plural}"] == sum(values) / 2
    assert payload["calendar_days_inclusive"] == payload["num_days"] == 3
    assert payload["coverage_days"] == 2
    assert payload["adb_denominator_basis"] == "formal_calendar"
    assert payload["sample_filled"] is True
    assert payload["sample_fill_method"] == "observed_days_scaled_to_calendar"
    assert payload["simulated"] is False
    breakdown = payload[f"{plural}_breakdown"]
    if values != (0, 0):
        assert len(breakdown) == 1
        assert breakdown[0]["spot_balance"] == values[-1]
        assert breakdown[0]["avg_balance"] == sum(values) / 2
    else:
        assert breakdown == []


@pytest.mark.parametrize("source, side", SOURCE_SIDES)
@pytest.mark.parametrize("reverse_rows", [False, True], ids=["forward", "reverse"])
def test_locf_sums_latest_day_per_category_independent_of_row_order(
    tmp_path, source, side, reverse_rows
):
    target, other = _category(source), _category(source, other=True)
    rows = [
        (LATEST, -40, target),
        (START, 30, other),
        (START, 100, target),
        (LATEST, 10, other),
        (LATEST, -60, target),
    ]
    path = _formal_db(tmp_path, source, side, rows[::-1] if reverse_rows else rows)
    payload, _ = _read_comparison(path, source)
    plural = "assets" if side == "asset" else "liabilities"
    assert payload[f"total_spot_{plural}"] == -90
    assert payload[f"total_avg_{plural}"] == 20
    assert sorted(
        (row["spot_balance"], row["avg_balance"])
        for row in payload[f"{plural}_breakdown"]
    ) == [(-100, 0), (10, 20)]


@pytest.mark.parametrize("source, side", SOURCE_SIDES)
@pytest.mark.parametrize(
    "end_state, expected_spot, expected_coverage",
    [("missing", -100, 2), ("invalid-same", -100, 2),
     ("valid-zero", 0, 3), ("different-category", 50, 3)],
)
def test_source_end_snapshot_and_invalid_amount_keep_existing_contract(
    tmp_path, source, side, end_state, expected_spot, expected_coverage
):
    category = _category(source)
    rows = [(START, 100, category), (LATEST, -100, category)]
    if end_state == "invalid-same":
        rows.append((END, None, category))
    elif end_state == "valid-zero":
        rows.append((END, 0, category))
    elif end_state == "different-category":
        rows.append((END, 50, _category(source, other=True)))
    path = _formal_db(tmp_path, source, side, rows)
    payload, frame = _read_comparison(path, source)
    plural = "assets" if side == "asset" else "liabilities"

    assert payload[f"total_spot_{plural}"] == expected_spot
    assert payload["coverage_days"] == expected_coverage
    assert payload["num_days"] == 3
    expected_average = 50 / 3 if end_state == "different-category" else 0
    assert payload[f"total_avg_{plural}"] == expected_average
    if end_state == "invalid-same":
        column = "market_value" if source == "bond" else "amount"
        assert frame[f"{column}_is_valid"].tolist() == [True, True, False]


@pytest.mark.parametrize("source, side", SOURCE_SIDES)
@pytest.mark.parametrize("observation", ["empty", "invalid", "outside-window"])
def test_no_valid_observations_remain_unavailable(tmp_path, source, side, observation):
    category = _category(source)
    rows = []
    if observation == "invalid":
        rows = [(START, None, category), (END, None, category)]
    elif observation == "outside-window":
        rows = [(date(2024, 2, 27), 100, category), (date(2024, 3, 2), -100, category)]
    path = _formal_db(tmp_path, source, side, rows)
    payload, _ = _read_comparison(path, source)
    plural = "assets" if side == "asset" else "liabilities"
    assert payload[f"total_spot_{plural}"] is None
    assert payload[f"total_avg_{plural}"] is None
    assert payload[f"{plural}_breakdown"] == []
    assert payload["coverage_days"] == 0
    assert payload["spot_unavailable_reason"] == "no_data"
