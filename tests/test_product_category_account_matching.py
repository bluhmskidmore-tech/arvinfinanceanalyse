from __future__ import annotations

from datetime import date
from decimal import Decimal, DecimalException, Inexact, Rounded, localcontext
from typing import cast

import pytest

from backend.app.core_finance import product_category_pnl as core


def _row(
    code: str | None,
    amount: str,
    *,
    currency: str = "CNX",
    report_date: date = date(2026, 2, 28),
) -> core.CanonicalFactRow:
    value = Decimal(amount)
    return core.CanonicalFactRow(
        report_date=report_date,
        account_code=cast(str, code),
        currency=currency,
        account_name="synthetic account",
        beginning_balance=Decimal("0"),
        ending_balance=value * 9,
        monthly_pnl=value * 3,
        daily_avg_balance=value,
        annual_avg_balance=value * 2,
        days_in_period=report_date.day,
    )


@pytest.mark.parametrize(
    ("patterns", "currency", "exact_expected", "prefix_expected"),
    [
        ([" 140 "], "CNX", "120", "125"),
        (["14"], "CNX", "11", "136"),
        (["140", "140", "-14004", "14"], "CNX", "244", "376"),
        (["14", "- 140", "14004"], "CNX", "-102", "21"),
        (["0"], "CNX", "17", "49"),
        ([None, "", "-", " -  ", "-missing"], "CNX", "0", "0"),
        (["140"], "CNY", "40", "42"),
        (["140"], "USD", "90", "90"),
        (["140"], " CNX", "99", "99"),
        (["140"], "cnx", "0", "0"),
    ],
)
@pytest.mark.parametrize("exact", [True, False])
@pytest.mark.parametrize("field_name", ["daily_avg_balance", "monthly_pnl"])
def test_prepared_matches_preserve_hand_calculated_pattern_semantics(
    patterns: list[str | None],
    currency: str,
    exact_expected: str,
    prefix_expected: str,
    exact: bool,
    field_name: str,
) -> None:
    rows = [
        _row(None, "1000"),
        _row("  ", "1000"),
        _row("140", "100"),
        _row(" 140 ", "20"),
        _row("14004", "7"),
        _row("1400401", "3"),
        _row("14005", "-5"),
        _row("14", "11"),
        _row("0140", "13"),
        _row("140", "40", currency="CNY"),
        _row(" 14004 ", "2", currency="CNY"),
        _row("140", "99", currency=" CNX"),
        _row("140", "90", currency="USD"),
        _row("0", "17"),
        _row("000", "19"),
    ]
    # Extra longer patterns catch accidental double matches of a short code.
    index = core._index_account_rows(rows, [*patterns, "14004000000001"])
    expected = Decimal(exact_expected if exact else prefix_expected)
    if field_name == "monthly_pnl":
        expected *= 3
    assert core._calculate_sum(
        rows, cast(list[str], patterns), field_name, currency, exact=exact, account_rows=index
    ) == expected
    assert core._calculate_sum(
        rows, cast(list[str], patterns), field_name, currency, exact=exact
    ) == expected


def test_prefix_matches_preserve_interleaved_decimal_addition_order() -> None:
    rows = [_row("51401", "100000"), _row("51402", "1"), _row("51401", "-100000")]
    index = core._index_account_rows(rows, ["514"])
    with localcontext() as context:
        context.prec = 5
        # In source order, 100000 + 1 rounds before cancellation, giving zero.
        # Grouping by account first would incorrectly retain the 1.
        assert core._calculate_sum(
            rows, ["514"], "daily_avg_balance", "CNX", exact=False, account_rows=index
        ) == Decimal("0")


def test_prepared_matches_preserve_pattern_addition_order() -> None:
    rows = [_row("1", "100000"), _row("2", "1"), _row("3", "100000")]
    index = core._index_account_rows(rows, ["1", "2", "3"])
    with localcontext() as context:
        context.prec = 5
        assert core._calculate_sum(
            rows, ["1", "2", "-3"], "daily_avg_balance", "CNX", exact=True, account_rows=index
        ) == Decimal("0")
        assert core._calculate_sum(
            rows, ["1", "-3", "2"], "daily_avg_balance", "CNX", exact=True, account_rows=index
        ) == Decimal("1")


@pytest.mark.parametrize("signal", [Inexact, Rounded])
def test_prepared_matches_preserve_decimal_traps(signal: type[DecimalException]) -> None:
    rows = [_row("51401", "100000"), _row("51402", "1"), _row("51401", "-100000")]
    index = core._index_account_rows(rows, ["514"])
    outcomes = []
    for account_rows in (None, index):
        with localcontext() as context:
            context.prec = 5
            context.clear_flags()
            context.traps[signal] = True
            with pytest.raises(signal):
                core._calculate_sum(
                    rows, ["514"], "daily_avg_balance", "CNX", exact=False, account_rows=account_rows
                )
            outcomes.append(dict(context.flags))
    assert outcomes[0] == outcomes[1]


def _config() -> list[dict[str, object]]:
    return [
        {
            "id": "assets",
            "name": "synthetic assets",
            "side": "asset",
            "level": 0,
            "scale_accounts": ["120"],
            "pnl_accounts": ["502", "50204", "-50204"],
            "ftp_rate_pct": "1.60",
            "children": [],
        }
    ]


@pytest.mark.parametrize(
    ("report_date", "view", "expected_cash", "expected_scale"),
    [
        (date(2026, 1, 31), "monthly", "12", "200"),
        (date(2026, 2, 28), "monthly", "18", "300"),
        (date(2026, 2, 28), "qtd", "30", None),
        (date(2026, 2, 28), "ytd", "30", None),
        (date(2026, 2, 28), "year_to_report_month_end", "30", None),
    ],
)
def test_calculation_keeps_period_currency_and_decimal_outputs(
    monkeypatch: pytest.MonkeyPatch,
    report_date: date,
    view: str,
    expected_cash: str,
    expected_scale: str | None,
) -> None:
    january, february = date(2026, 1, 31), date(2026, 2, 28)
    facts = {
        january: [
            _row("120", "100", report_date=january),
            _row("12001", "9999", report_date=january),
            _row("5020401", "4", report_date=january),
            _row("120", "50", currency="CNY", report_date=january),
            _row("5020401", "2", currency="CNY", report_date=january),
        ],
        february: [
            _row("120", "300", report_date=february),
            _row("5020401", "6", report_date=february),
            _row("120", "150", currency="CNY", report_date=february),
            _row("5020401", "3", currency="CNY", report_date=february),
        ],
        # Other years and future months must not leak into cumulative views.
        date(2025, 12, 31): [_row("5020401", "9999")],
        date(2026, 3, 31): [_row("5020401", "9999")],
    }
    result = core.calculate_read_model(facts, report_date, view, _config())
    row = result["rows"][0]
    scale = Decimal(expected_scale) if expected_scale else Decimal("14600") / Decimal("59")
    cny_scale = Decimal(expected_scale) / 2 if expected_scale else Decimal("7300") / Decimal("59")
    assert row["cnx_scale"] == scale
    assert row["cny_scale"] == cny_scale
    assert row["foreign_scale"] == scale - cny_scale
    assert row["cnx_cash"] == Decimal(expected_cash)
    assert row["cny_cash"] == Decimal(expected_cash) / 2
    assert row["report_date"] == report_date.isoformat()
    assert row["view"] == view

    # Re-run the full formula pipeline with the retained scan implementation.
    # This checks every amount, rate, total and null field, not just headlines.
    monkeypatch.setattr(core, "_index_account_rows", lambda *_args: None)
    reference = core.calculate_read_model(facts, report_date, view, _config())
    assert result == reference


def test_matching_index_is_rebuilt_after_source_or_config_changes() -> None:
    report_date = date(2026, 2, 28)
    rows = [_row("5020401", "1")]
    config = _config()
    first = core.calculate_read_model({report_date: rows}, report_date, "monthly", config)
    rows[0].monthly_pnl = Decimal("7")
    second = core.calculate_read_model({report_date: rows}, report_date, "monthly", config)
    config[0]["pnl_accounts"] = ["-50204"]
    third = core.calculate_read_model({report_date: rows}, report_date, "monthly", config)
    assert [result["rows"][0]["cnx_cash"] for result in (first, second, third)] == [
        Decimal("3"), Decimal("7"), Decimal("-7")
    ]


def test_parent_cash_uses_children_and_preserves_liability_signs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_date = date(2026, 2, 28)
    parent = _config()[0]
    child = dict(parent, id="child", level=1, pnl_accounts=["502"])
    parent.update(children=["child"], pnl_accounts=["502", "502"])
    liability = dict(
        child, id="liabilities", side="liability", level=0,
        scale_accounts=["234"], pnl_accounts=["522"],
    )
    facts = {report_date: [
        _row("120", "100"), _row("50204", "4"),
        _row("120", "50", currency="CNY"), _row("50204", "2", currency="CNY"),
        _row("234", "-50"), _row("52206", "-2"),
        _row("234", "-20", currency="CNY"), _row("52206", "-1", currency="CNY"),
    ]}
    config = [parent, child, liability]
    result = core.calculate_read_model(facts, report_date, "monthly", config)
    assert result["asset_total"]["cnx_cash"] == Decimal("12")
    assert result["liability_total"]["cnx_cash"] == Decimal("-6")
    assert result["liability_total"]["cnx_scale"] == Decimal("-50")
    assert result["grand_total"]["cnx_cash"] == Decimal("6")
    assert result["grand_total"]["cny_cash"] == Decimal("3")
    monkeypatch.setattr(core, "_index_account_rows", lambda *_args: None)
    assert result == core.calculate_read_model(facts, report_date, "monthly", config)
