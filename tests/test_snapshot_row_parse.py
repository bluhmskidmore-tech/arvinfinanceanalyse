"""Focused contract tests for backend.app.repositories.snapshot_row_parse."""

from __future__ import annotations

from decimal import Decimal

import xlrd
from xlrd import xldate

from backend.app.repositories import snapshot_row_parse as snapshot_row_parse_mod
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


def test_text_helper():
    assert _text({"k": "  x "}, "k") == "x"
    assert _text({"k": None}, "k") == ""
    assert _text({}, "missing") == ""


def test_normalize_id_strips_excel_float_suffix():
    assert _normalize_id("12345.0") == "12345"
    assert _normalize_id("-12.0") == "-12"
    assert _normalize_id("12.5") == "12.5"
    assert _normalize_id(42) == "42"


def test_decimal_and_required():
    assert _decimal(None) is None
    assert _decimal("") is None
    assert _decimal("1,234.5") == Decimal("1234.5")
    assert _decimal("not-a-number") is None
    assert _decimal_required("bad") == Decimal("0")
    assert _decimal_required("2") == Decimal("2")


def test_cell_to_iso_date_string_and_excel_serial():
    zqtz_path = ROOT / "sample_data" / "smoke-runtime" / "ZQTZSHOW-20251231.xls"
    book = xlrd.open_workbook(file_contents=zqtz_path.read_bytes())
    assert _cell_to_iso_date(book, "2025-12-20") == "2025-12-20"
    assert _cell_to_iso_date(book, None) is None
    serial = xldate.xldate_from_date_tuple((2025, 6, 15), book.datemode)
    assert _cell_to_iso_date(book, serial) == "2025-06-15"


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
