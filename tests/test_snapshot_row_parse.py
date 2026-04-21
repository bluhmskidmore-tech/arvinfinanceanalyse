"""Focused contract tests for backend.app.repositories.snapshot_row_parse."""

from __future__ import annotations

from decimal import Decimal

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
    assert _decimal_required("bad") == Decimal("0")
    assert _decimal_required("2") == Decimal("2")
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
    path = ROOT / "sample_data" / "smoke-runtime" / "ZQTZSHOW-20251231.xls"
    source_file = path.name

    def _stub(value: object) -> str:
        return f"stub:{value!r}"

    monkeypatch.setattr(snapshot_row_parse_mod, "normalize_currency_code", _stub)
    rows = parse_zqtz_snapshot_rows_from_bytes(
        file_bytes=path.read_bytes(),
        ingest_batch_id="ib-currency",
        source_version="sv",
        source_file=source_file,
        rule_version="rv",
    )
    assert rows
    assert str(rows[0]["currency_code"]).startswith("stub:")


def test_tyw_parse_calls_normalize_currency_code(monkeypatch):
    path = ROOT / "sample_data" / "smoke-runtime" / "TYWLSHOW-20251231.xls"
    source_file = path.name

    def _stub(value: object) -> str:
        return f"tyw:{value!r}"

    monkeypatch.setattr(snapshot_row_parse_mod, "normalize_currency_code", _stub)
    rows = parse_tyw_snapshot_rows_from_bytes(
        file_bytes=path.read_bytes(),
        ingest_batch_id="ib-tyw-curr",
        source_version="sv",
        source_file=source_file,
        rule_version="rv",
    )
    assert rows
    assert str(rows[0]["currency_code"]).startswith("tyw:")


def test_parse_zqtz_smoke_workbook_currency_and_issuance_flag():
    path = ROOT / "sample_data" / "smoke-runtime" / "ZQTZSHOW-20251231.xls"
    source_file = path.name
    rows = parse_zqtz_snapshot_rows_from_bytes(
        file_bytes=path.read_bytes(),
        ingest_batch_id="ib-contract",
        source_version="sv",
        source_file=source_file,
        rule_version="rv",
    )
    assert rows
    row = rows[0]
    assert row["ingest_batch_id"] == "ib-contract"
    assert row["source_version"] == "sv"
    assert row["rule_version"] == "rv"
    assert isinstance(row["trace_id"], str) and row["trace_id"]
    assert row["report_date"]
    assert row["instrument_code"]
    assert row["currency_code"]  # normalized via normalize_currency_code
    assert "is_issuance_like" in row
    assert row["next_call_date"] is None or isinstance(row["next_call_date"], str)
    issuance_rows = [x for x in rows if "发行类债" in str(x.get("asset_class", ""))]
    if issuance_rows:
        assert all(bool(x["is_issuance_like"]) for x in issuance_rows[:5])


def test_parse_tyw_smoke_workbook_liability_product_and_optional_none():
    path = ROOT / "sample_data" / "smoke-runtime" / "TYWLSHOW-20251231.xls"
    source_file = path.name
    rows = parse_tyw_snapshot_rows_from_bytes(
        file_bytes=path.read_bytes(),
        ingest_batch_id="ib-tyw",
        source_version="sv2",
        source_file=source_file,
        rule_version="rv2",
    )
    assert rows
    r = rows[0]
    assert r["ingest_batch_id"] == "ib-tyw"
    assert r["report_date"]
    assert r["position_id"]
    assert r["currency_code"] is not None  # may be "" if blank in sheet
    assert r["special_account_type"] is None or isinstance(r["special_account_type"], str)

    liability_types = snapshot_row_parse_mod._LIABILITY_PRODUCTS
    found = [row for row in rows if str(row.get("product_type", "")) in liability_types]
    if found:
        assert all(row["position_side"] == "liability" for row in found[:5])
    non_liab = next((row for row in rows if str(row.get("product_type", "")) not in liability_types), None)
    if non_liab is not None:
        assert non_liab["position_side"] == "asset"


def test_parse_zqtz_prefers_source_file_report_date_over_stale_sheet_date():
    path = ROOT / "data_input" / "ZQTZSHOW-2025.11.20.xls"
    rows = parse_zqtz_snapshot_rows_from_bytes(
        file_bytes=path.read_bytes(),
        ingest_batch_id="ib-zqtz-date-drift",
        source_version="sv-zqtz-date-drift",
        source_file=path.name,
        rule_version="rv-zqtz-date-drift",
    )
    assert rows
    assert {row["report_date"] for row in rows} == {"2025-11-20"}


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
            "issuer_name": "发行人A",
            "industry_name": "金融业",
            "rating": "AAA",
            "currency_code": "CNY",
            "face_value_native": Decimal("100"),
            "market_value_native": Decimal("100"),
            "amortized_cost_native": Decimal("90"),
            "accrued_interest_native": Decimal("5"),
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
