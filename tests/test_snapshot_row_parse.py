"""Focused contract tests for backend.app.repositories.snapshot_row_parse."""

from __future__ import annotations

from decimal import Decimal

import pytest
import xlrd
from xlrd import xldate

from backend.app.repositories import snapshot_row_parse as snapshot_row_parse_mod
from backend.app.repositories.currency_codes import normalize_currency_code
from backend.app.repositories.snapshot_row_parse import (
    _cell_to_iso_date,
    _decimal,
    _decimal_required,
    _normalize_id,
    _text,
    parse_tyw_snapshot_rows_from_bytes,
    parse_zqtz_snapshot_rows_from_bytes,
)
from tests.helpers import ROOT


class _FakeSheet:
    def __init__(self, rows: list[list[object]]):
        self._rows = rows
        self.nrows = len(rows)
        self.ncols = max((len(row) for row in rows), default=0)

    def cell_value(self, rowx: int, colx: int) -> object:
        row = self._rows[rowx]
        if colx >= len(row):
            return ""
        return row[colx]


class _FakeBook:
    def __init__(self, rows: list[list[object]]):
        self.datemode = 0
        self._sheet = _FakeSheet(rows)

    def sheet_by_index(self, index: int) -> _FakeSheet:
        assert index == 0
        return self._sheet


def test_text_helper():
    assert _text({"k": "  x "}, "k") == "x"
    assert _text({"k": None}, "k") == ""
    assert _text({}, "missing") == ""


def test_normalize_id_strips_excel_float_suffix():
    assert _normalize_id("12345.0") == "12345"
    assert _normalize_id("-12.0") == "-12"
    assert _normalize_id("12.5") == "12.5"
    assert _normalize_id(42) == "42"
    assert _normalize_id("abc.0") == "abc.0"


def test_decimal_and_required():
    assert _decimal(None) is None
    assert _decimal("") is None
    assert _decimal("1,234.5") == Decimal("1234.5")
    assert _decimal("not-a-number") is None
    with pytest.raises(ValueError, match="ZQTZ required amount invalid"):
        _decimal_required("bad", family="ZQTZ", header="面值", row_number=3, headers=["面值"])
    assert (
        _decimal_required("2", family="ZQTZ", header="面值", row_number=3, headers=["面值"])
        == Decimal("2")
    )
    assert _decimal(3.125) == Decimal("3.125")
    assert _decimal(-1) == Decimal("-1")


def test_cell_to_iso_date_string_and_excel_serial():
    zqtz_path = ROOT / "sample_data" / "smoke-runtime" / "ZQTZSHOW-20251231.xls"
    book = xlrd.open_workbook(file_contents=zqtz_path.read_bytes())
    assert _cell_to_iso_date(book, "2025-12-20") == "2025-12-20"
    assert _cell_to_iso_date(book, None) is None
    serial = xldate.xldate_from_date_tuple((2025, 6, 15), book.datemode)
    assert _cell_to_iso_date(book, serial) == "2025-06-15"


def test_cell_to_iso_date_non_date_string_returns_none():
    zqtz_path = ROOT / "sample_data" / "smoke-runtime" / "ZQTZSHOW-20251231.xls"
    book = xlrd.open_workbook(file_contents=zqtz_path.read_bytes())
    assert _cell_to_iso_date(book, "nope") is None
    # Dash pattern but wrong positions: implementation only checks length and '-' slots, not calendar validity
    assert _cell_to_iso_date(book, "bad-not-iso") is None


def test_cell_to_iso_date_invalid_excel_serial_returns_none():
    zqtz_path = ROOT / "sample_data" / "smoke-runtime" / "ZQTZSHOW-20251231.xls"
    book = xlrd.open_workbook(file_contents=zqtz_path.read_bytes())
    assert _cell_to_iso_date(book, 1e308) is None


def test_currency_mapping_matches_normalize_currency_code():
    assert normalize_currency_code("人民币") == "CNY"
    assert normalize_currency_code("usd") == "USD"


def test_zqtz_parse_calls_normalize_currency_code(monkeypatch):
    def _stub(value: object) -> str:
        return f"stub:{value!r}"

    monkeypatch.setattr(snapshot_row_parse_mod, "normalize_currency_code", _stub)
    rows = _parse_synthetic_amount_sheet(
        monkeypatch, "zqtz", _synthetic_amount_sheet("zqtz")
    )
    assert rows[0]["currency_code"] == "stub:'人民币'"


def test_tyw_parse_calls_normalize_currency_code(monkeypatch):
    def _stub(value: object) -> str:
        return f"tyw:{value!r}"

    monkeypatch.setattr(snapshot_row_parse_mod, "normalize_currency_code", _stub)
    rows = _parse_synthetic_amount_sheet(
        monkeypatch, "tyw", _synthetic_amount_sheet("tyw")
    )
    assert rows[0]["currency_code"] == "tyw:'人民币'"


def test_parse_zqtz_synthetic_workbook_currency_and_issuance_flag(monkeypatch):
    rows = _parse_synthetic_amount_sheet(
        monkeypatch, "zqtz", _synthetic_amount_sheet("zqtz")
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["ingest_batch_id"] == "ib-synthetic"
    assert row["source_version"] == "sv-synthetic"
    assert row["rule_version"] == "rv-synthetic"
    assert isinstance(row["trace_id"], str) and row["trace_id"]
    assert row["report_date"] == "2025-12-31"
    assert row["instrument_code"] == "SYNTHETIC-ID"
    assert row["currency_code"] == "CNY"
    assert row["sub_type"] == row["business_type_primary"]
    assert row["next_call_date"] is None
    assert row["asset_class"] == "发行类债"
    assert row["is_issuance_like"] is True


def test_parse_tyw_synthetic_workbook_liability_product_and_optional_none(monkeypatch):
    sheet_rows = _synthetic_amount_sheet("tyw")
    sheet_rows.append(["SYNTHETIC-ASSET", "200", "0", "", "美元", "买入返售", ""])
    rows = _parse_synthetic_amount_sheet(monkeypatch, "tyw", sheet_rows)
    assert len(rows) == 2
    liability, asset = rows
    assert liability["ingest_batch_id"] == "ib-synthetic"
    assert liability["report_date"] == "2025-12-31"
    assert liability["position_id"] == "SYNTHETIC-ID"
    assert liability["currency_code"] == "CNY"
    assert liability["special_account_type"] is None
    assert liability["position_side"] == "liability"
    assert asset["currency_code"] == "USD"
    assert asset["position_side"] == "asset"


def test_parse_zqtz_rejects_source_file_report_date_conflicting_with_sheet_date():
    path = ROOT / "data_input" / "ZQTZSHOW-2025.11.20.xls"
    with pytest.raises(ValueError, match="source date mismatch: file=2025-11-20, sheet=2025-11-19"):
        parse_zqtz_snapshot_rows_from_bytes(
            file_bytes=path.read_bytes(),
            ingest_batch_id="ib-zqtz-date-drift",
            source_version="sv-zqtz-date-drift",
            source_file=path.name,
            rule_version="rv-zqtz-date-drift",
        )


def test_parse_zqtz_maps_value_date_and_customer_attribute(monkeypatch):
    rows = [
        [],
        [
            snapshot_row_parse_mod.ZQTZ_BOND_CODE,
            snapshot_row_parse_mod.ZQTZ_BOND_NAME,
            snapshot_row_parse_mod.ZQTZ_PORTFOLIO,
            snapshot_row_parse_mod.ZQTZ_COST_CENTER,
            snapshot_row_parse_mod.ZQTZ_BUSINESS_KIND,
            snapshot_row_parse_mod.ZQTZ_ACCOUNT_CATEGORY,
            snapshot_row_parse_mod.ZQTZ_ASSET_CLASS,
            snapshot_row_parse_mod.ZQTZ_ISSUER,
            snapshot_row_parse_mod.ZQTZ_INDUSTRY,
            snapshot_row_parse_mod.ZQTZ_RATING,
            snapshot_row_parse_mod.ZQTZ_CURRENCY,
            snapshot_row_parse_mod.ZQTZ_FACE_VALUE,
            snapshot_row_parse_mod.ZQTZ_FAIR_VALUE,
            snapshot_row_parse_mod.ZQTZ_AMORTIZED,
            snapshot_row_parse_mod.ZQTZ_ACCRUED,
            snapshot_row_parse_mod.ZQTZ_INTEREST_RECEIVABLE_PAYABLE,
            snapshot_row_parse_mod.ZQTZ_COUPON,
            snapshot_row_parse_mod.ZQTZ_YTM,
            snapshot_row_parse_mod.ZQTZ_MATURITY,
            snapshot_row_parse_mod.ZQTZ_INTEREST_MODE,
            snapshot_row_parse_mod.ZQTZ_OVERDUE_DAYS,
            snapshot_row_parse_mod.ZQTZ_CUSTOMER_ATTRIBUTE,
            snapshot_row_parse_mod.ZQTZ_VALUE_DATE,
        ],
        [
            "240001.IB",
            "债券A",
            "组合A",
            "CC100",
            "国债",
            "可供出售债券",
            "债券类",
            "发行人A",
            "金融业",
            "AAA",
            "人民币",
            "100",
            "100",
            "90",
            "5",
            "1234.56",
            "2.50",
            "2.40",
            "2027-12-31",
            "固定",
            "12",
            "内部客户",
            "2024-01-05",
        ],
    ]

    monkeypatch.setattr(
        snapshot_row_parse_mod.xlrd,
        "open_workbook",
        lambda **kwargs: _FakeBook(rows),
    )

    parsed = parse_zqtz_snapshot_rows_from_bytes(
        file_bytes=b"fake",
        ingest_batch_id="ib-extra",
        source_version="sv-extra",
        source_file="ZQTZSHOW-20251231.xls",
        rule_version="rv-extra",
    )

    assert parsed == [
        {
            "report_date": "2025-12-31",
            "instrument_code": "240001.IB",
            "instrument_name": "债券A",
            "portfolio_name": "组合A",
            "cost_center": "CC100",
            "account_category": "可供出售债券",
            "asset_class": "债券类",
            "bond_type": "国债",
            "business_type_primary": "",
            "sub_type": "",
            "issuer_name": "发行人A",
            "industry_name": "金融业",
            "rating": "AAA",
            "currency_code": "CNY",
            "face_value_native": Decimal("100"),
            "market_value_native": Decimal("100"),
            "amortized_cost_native": Decimal("90"),
            "accrued_interest_native": Decimal("5"),
            "interest_receivable_payable": Decimal("1234.56"),
            "coupon_rate": Decimal("2.5"),
            "ytm_value": Decimal("2.4"),
            "maturity_date": "2027-12-31",
            "next_call_date": None,
            "overdue_days": 12,
            "is_issuance_like": False,
            "interest_mode": "固定",
            "value_date": "2024-01-05",
            "customer_attribute": "内部客户",
            "source_version": "sv-extra",
            "rule_version": "rv-extra",
            "ingest_batch_id": "ib-extra",
            "trace_id": parsed[0]["trace_id"],
        }
    ]


# Source layouts observed in the archive have 44, 45, and 46 columns with
# 应收/应付利息 at index 28. Synthetic rows isolate successful parsing
# from copied source files with unresolved required amount blanks.
@pytest.mark.parametrize("ncols", [44, 45, 46])
def test_parse_zqtz_reads_interest_receivable_payable_across_layout_widths(
    monkeypatch: pytest.MonkeyPatch, ncols: int
) -> None:
    template = _synthetic_amount_sheet("zqtz")
    headers = [""] * ncols
    values = [""] * ncols
    for index, (header, value) in enumerate(zip(template[1], template[2])):
        target = 28 if header == snapshot_row_parse_mod.ZQTZ_INTEREST_RECEIVABLE_PAYABLE else index
        headers[target] = header
        values[target] = "1234.56" if target == 28 else value
    monkeypatch.setattr(
        snapshot_row_parse_mod.xlrd,
        "open_workbook",
        lambda **kwargs: _FakeBook([[], headers, values]),
    )
    rows = parse_zqtz_snapshot_rows_from_bytes(
        file_bytes=b"synthetic",
        ingest_batch_id="ib-irp-layout",
        source_version="sv-irp-layout",
        source_file="ZQTZSHOW-20251231.xls",
        rule_version="rv-irp-layout",
    )
    assert len(rows) == 1
    assert rows[0]["interest_receivable_payable"] == Decimal("1234.56")


def _zqtz_minimal_sheet(interest_header: str, interest_cell: object) -> list[list[object]]:
    return [
        [],
        [
            snapshot_row_parse_mod.ZQTZ_BOND_CODE,
            snapshot_row_parse_mod.ZQTZ_ACCRUED,
            interest_header,
            snapshot_row_parse_mod.ZQTZ_FACE_VALUE,
            snapshot_row_parse_mod.ZQTZ_FAIR_VALUE,
            snapshot_row_parse_mod.ZQTZ_AMORTIZED,
            snapshot_row_parse_mod.ZQTZ_MATURITY,
        ],
        ["240001.IB", "5", interest_cell, "100", "0", "0", ""],
    ]


@pytest.mark.parametrize(
    "interest_header",
    [
        "应收/应付利息",  # ASCII slash: the only spelling present in the archive
        "应收／应付利息",  # full-width slash U+FF0F
        " 应收 / 应付利息 ",  # padded and inner-spaced
    ],
)
def test_parse_zqtz_resolves_interest_receivable_header_variants(
    monkeypatch,
    interest_header: str,
) -> None:
    monkeypatch.setattr(
        snapshot_row_parse_mod.xlrd,
        "open_workbook",
        lambda **kwargs: _FakeBook(_zqtz_minimal_sheet(interest_header, "1234.56")),
    )

    parsed = parse_zqtz_snapshot_rows_from_bytes(
        file_bytes=b"fake",
        ingest_batch_id="ib-irp",
        source_version="sv-irp",
        source_file="ZQTZSHOW-20251231.xls",
        rule_version="rv-irp",
    )

    assert parsed[0]["interest_receivable_payable"] == Decimal("1234.56")


def test_parse_zqtz_keeps_blank_interest_receivable_null_not_zero(monkeypatch) -> None:
    monkeypatch.setattr(
        snapshot_row_parse_mod.xlrd,
        "open_workbook",
        lambda **kwargs: _FakeBook(_zqtz_minimal_sheet("应收/应付利息", "")),
    )

    parsed = parse_zqtz_snapshot_rows_from_bytes(
        file_bytes=b"fake",
        ingest_batch_id="ib-irp-blank",
        source_version="sv-irp-blank",
        source_file="ZQTZSHOW-20251231.xls",
        rule_version="rv-irp-blank",
    )

    assert parsed[0]["interest_receivable_payable"] is None
    assert parsed[0]["accrued_interest_native"] == Decimal("5")


def test_parse_zqtz_without_interest_receivable_column_yields_null(monkeypatch) -> None:
    rows = [
        [],
        [
            snapshot_row_parse_mod.ZQTZ_BOND_CODE,
            snapshot_row_parse_mod.ZQTZ_FACE_VALUE,
            snapshot_row_parse_mod.ZQTZ_FAIR_VALUE,
            snapshot_row_parse_mod.ZQTZ_AMORTIZED,
            snapshot_row_parse_mod.ZQTZ_ACCRUED,
            snapshot_row_parse_mod.ZQTZ_MATURITY,
        ],
        ["240001.IB", "100", "0", "0", "0", ""],
    ]
    monkeypatch.setattr(
        snapshot_row_parse_mod.xlrd,
        "open_workbook",
        lambda **kwargs: _FakeBook(rows),
    )

    parsed = parse_zqtz_snapshot_rows_from_bytes(
        file_bytes=b"fake",
        ingest_batch_id="ib-irp-missing",
        source_version="sv-irp-missing",
        source_file="ZQTZSHOW-20251231.xls",
        rule_version="rv-irp-missing",
    )

    assert parsed[0]["interest_receivable_payable"] is None


@pytest.mark.parametrize("invalid_maturity", ["bad-date", "2030-99-99", "2030-01-01junk", 1e308])
def test_parse_zqtz_rejects_nonblank_invalid_maturity_date(
    monkeypatch: pytest.MonkeyPatch,
    invalid_maturity: object,
) -> None:
    rows = _zqtz_minimal_sheet("应收/应付利息", "")
    rows[2][-1] = invalid_maturity
    monkeypatch.setattr(
        snapshot_row_parse_mod.xlrd,
        "open_workbook",
        lambda **kwargs: _FakeBook(rows),
    )

    with pytest.raises(ValueError, match="ZQTZ maturity_date invalid.*row=3"):
        parse_zqtz_snapshot_rows_from_bytes(
            file_bytes=b"fake",
            ingest_batch_id="ib-invalid-maturity",
            source_version="sv-invalid-maturity",
            source_file="ZQTZSHOW-20251231.xls",
            rule_version="rv-invalid-maturity",
        )


def test_parse_zqtz_rejects_missing_maturity_date_column(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _zqtz_minimal_sheet("应收/应付利息", "")
    rows[1].pop()
    rows[2].pop()
    monkeypatch.setattr(
        snapshot_row_parse_mod.xlrd,
        "open_workbook",
        lambda **kwargs: _FakeBook(rows),
    )

    with pytest.raises(ValueError, match="ZQTZ required column missing: maturity_date"):
        parse_zqtz_snapshot_rows_from_bytes(
            file_bytes=b"fake",
            ingest_batch_id="ib-missing-maturity-column",
            source_version="sv-missing-maturity-column",
            source_file="ZQTZSHOW-20251231.xls",
            rule_version="rv-missing-maturity-column",
        )


def test_parse_zqtz_rejects_ambiguous_maturity_date_column(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _zqtz_minimal_sheet("应收/应付利息", "")
    rows[1].append(snapshot_row_parse_mod.ZQTZ_MATURITY)
    rows[2].append("")
    monkeypatch.setattr(
        snapshot_row_parse_mod.xlrd,
        "open_workbook",
        lambda **kwargs: _FakeBook(rows),
    )

    with pytest.raises(ValueError, match="ZQTZ required column ambiguous: maturity_date"):
        parse_zqtz_snapshot_rows_from_bytes(
            file_bytes=b"fake",
            ingest_batch_id="ib-ambiguous-maturity-column",
            source_version="sv-ambiguous-maturity-column",
            source_file="ZQTZSHOW-20251231.xls",
            rule_version="rv-ambiguous-maturity-column",
        )


_REQUIRED_AMOUNT_COLUMNS = (
    ("zqtz", snapshot_row_parse_mod.ZQTZ_FACE_VALUE, 2),
    ("zqtz", snapshot_row_parse_mod.ZQTZ_FAIR_VALUE, 3),
    ("zqtz", snapshot_row_parse_mod.ZQTZ_AMORTIZED, 4),
    ("zqtz", snapshot_row_parse_mod.ZQTZ_ACCRUED, 5),
    ("tyw", snapshot_row_parse_mod.TYW_PRINCIPAL, 2),
    ("tyw", snapshot_row_parse_mod.TYW_ACCRUED, 3),
)


def _synthetic_amount_sheet(family: str) -> list[list[object]]:
    if family == "zqtz":
        return [
            [],
            [
                snapshot_row_parse_mod.ZQTZ_BOND_CODE,
                snapshot_row_parse_mod.ZQTZ_FACE_VALUE,
                snapshot_row_parse_mod.ZQTZ_FAIR_VALUE,
                snapshot_row_parse_mod.ZQTZ_AMORTIZED,
                snapshot_row_parse_mod.ZQTZ_ACCRUED,
                snapshot_row_parse_mod.ZQTZ_INTEREST_RECEIVABLE_PAYABLE,
                snapshot_row_parse_mod.ZQTZ_CURRENCY,
                snapshot_row_parse_mod.ZQTZ_BUSINESS_KIND,
                snapshot_row_parse_mod.ZQTZ_BUSINESS_TYPE1,
                snapshot_row_parse_mod.ZQTZ_ASSET_CLASS,
                snapshot_row_parse_mod.ZQTZ_MATURITY,
            ],
            ["SYNTHETIC-ID", "100", "101", "99", "0", "", "人民币", "发行类债", "发行类债", "发行类债", ""],
        ]
    return [
        [],
        [
            snapshot_row_parse_mod.TYW_SERIAL,
            snapshot_row_parse_mod.TYW_PRINCIPAL,
            snapshot_row_parse_mod.TYW_ACCRUED,
            snapshot_row_parse_mod.TYW_RATE,
            snapshot_row_parse_mod.TYW_CURRENCY,
            snapshot_row_parse_mod.TYW_PRODUCT,
            snapshot_row_parse_mod.TYW_SPECIAL_ACCOUNT,
        ],
        ["SYNTHETIC-ID", "100", "0", "", "人民币", "同业拆入", ""],
    ]


def _parse_synthetic_amount_sheet(
    monkeypatch: pytest.MonkeyPatch, family: str, rows: list[list[object]]
) -> list[dict[str, object]]:
    monkeypatch.setattr(
        snapshot_row_parse_mod.xlrd,
        "open_workbook",
        lambda **kwargs: _FakeBook(rows),
    )
    parser = (
        parse_zqtz_snapshot_rows_from_bytes
        if family == "zqtz"
        else parse_tyw_snapshot_rows_from_bytes
    )
    return parser(
        file_bytes=b"synthetic",
        ingest_batch_id="ib-synthetic",
        source_version="sv-synthetic",
        source_file=f"{'ZQTZSHOW' if family == 'zqtz' else 'TYWLSHOW'}-20251231.xls",
        rule_version="rv-synthetic",
    )


@pytest.mark.parametrize(("family", "header", "column"), _REQUIRED_AMOUNT_COLUMNS)
@pytest.mark.parametrize("invalid_value", ["", "bad-private", "NaN", "Infinity", float("nan"), float("inf")])
def test_required_snapshot_amount_rejects_missing_invalid_and_nonfinite(
    monkeypatch: pytest.MonkeyPatch,
    family: str,
    header: str,
    column: int,
    invalid_value: object,
) -> None:
    rows = _synthetic_amount_sheet(family)
    rows[2][column - 1] = invalid_value
    with pytest.raises(ValueError) as exc:
        _parse_synthetic_amount_sheet(monkeypatch, family, rows)
    message = str(exc.value)
    assert family.upper() in message
    assert header in message
    assert "row=3" in message
    assert f"column={column}" in message
    assert "SYNTHETIC-ID" not in message
    assert "bad-private" not in message


@pytest.mark.parametrize("family", ["zqtz", "tyw"])
def test_snapshot_amount_explicit_zero_and_optional_blank_are_preserved(
    monkeypatch: pytest.MonkeyPatch, family: str
) -> None:
    parsed = _parse_synthetic_amount_sheet(
        monkeypatch, family, _synthetic_amount_sheet(family)
    )
    assert len(parsed) == 1
    if family == "zqtz":
        assert parsed[0]["accrued_interest_native"] == Decimal("0")
        assert parsed[0]["interest_receivable_payable"] is None
    else:
        assert parsed[0]["accrued_interest_native"] == Decimal("0")
        assert parsed[0]["funding_cost_rate"] is None



@pytest.mark.parametrize(
    ("family", "header", "column"),
    [
        ("zqtz", snapshot_row_parse_mod.ZQTZ_FAIR_VALUE, 3),
        ("tyw", snapshot_row_parse_mod.TYW_PRINCIPAL, 2),
    ],
)
def test_snapshot_amount_missing_header_reports_location(
    monkeypatch: pytest.MonkeyPatch, family: str, header: str, column: int
) -> None:
    rows = _synthetic_amount_sheet(family)
    del rows[1][column - 1]
    del rows[2][column - 1]
    with pytest.raises(ValueError) as exc:
        _parse_synthetic_amount_sheet(monkeypatch, family, rows)
    message = str(exc.value)
    assert family.upper() in message
    assert f"header={header}" in message
    assert "row=3, column=missing" in message
    assert "SYNTHETIC-ID" not in message


@pytest.mark.parametrize("family", ["zqtz", "tyw"])
def test_snapshot_parser_skips_entirely_empty_separator_row(
    monkeypatch: pytest.MonkeyPatch, family: str
) -> None:
    rows = _synthetic_amount_sheet(family)
    rows.insert(2, [""] * len(rows[1]))
    parsed = _parse_synthetic_amount_sheet(monkeypatch, family, rows)
    assert len(parsed) == 1
