"""Parse zqtz / tyw archived workbooks into standardized snapshot row dicts (no preview tables)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import xlrd

from backend.app.repositories.currency_codes import normalize_currency_code
from backend.app.services.source_rules import describe_source_file

ZQTZ_BOND_CODE = "债券代号"
ZQTZ_BOND_NAME = "债券名称"
ZQTZ_DATE = "日期"
ZQTZ_BUSINESS_KIND = "业务种类"
ZQTZ_BUSINESS_TYPE1 = "业务种类1"
ZQTZ_ACCOUNT_CATEGORY = "账户类别"
ZQTZ_PORTFOLIO = "投资组合"
ZQTZ_COST_CENTER = "成本中心"
ZQTZ_ASSET_CLASS = "资产分类"
ZQTZ_INDUSTRY = "交易对手行业大类"
ZQTZ_RATING = "授信客户债券评级"
ZQTZ_ISSUER = "授信客户名称"
ZQTZ_FAIR_VALUE = "公允价值"
ZQTZ_AMORTIZED = "摊余成本"
ZQTZ_ACCRUED = "应计利息"
ZQTZ_FACE_VALUE = "面值"
ZQTZ_INTEREST_MODE = "计息方式"
ZQTZ_COUPON = "利率"
ZQTZ_YTM = "到期收益率"
ZQTZ_MATURITY = "到期日"
ZQTZ_NEXT_CALL = "下一行权日/逾期资产到期日"
ZQTZ_OVERDUE_DAYS = "本金逾期天数"
ZQTZ_CURRENCY = "币种"

TYW_SERIAL = "流水号"
TYW_PRODUCT = "产品类型"
TYW_COUNTERPARTY = "对手方名称"
TYW_PORTFOLIO = "投资组合"
TYW_ACCOUNT_TYPE = "账户类型"
TYW_SPECIAL_ACCOUNT = "特殊账户类型"
TYW_CORE_CUSTOMER = "核心客户类型"
TYW_CURRENCY = "币种"
TYW_PRINCIPAL = "金额"
TYW_ACCRUED = "应计利息"
TYW_RATE = "利率"
TYW_MATURITY = "到期日"
TYW_PLEDGED = "质押债券号"

_LIABILITY_PRODUCTS = frozenset({"同业拆入", "同业存放", "卖出回购证券", "卖出回购票据"})


def _text(row: dict[str, object], key: str) -> str:
    value = row.get(key, "")
    if value is None:
        return ""
    return str(value).strip()


def _normalize_id(value: object) -> str:
    raw = _text({"v": value}, "v")
    if raw.endswith(".0") and raw[:-2].replace("-", "").isdigit():
        return raw[:-2]
    return raw


def _cell_to_iso_date(book: xlrd.Book, value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            y, m, d, *_ = xlrd.xldate.xldate_as_tuple(float(value), book.datemode)
            return date(int(y), int(m), int(d)).isoformat()
        except xlrd.XLDateError:
            return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


def _decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(float(value)))
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def _decimal_required(value: object) -> Decimal:
    parsed = _decimal(value)
    return parsed if parsed is not None else Decimal("0")


def parse_zqtz_snapshot_rows_from_bytes(
    *,
    file_bytes: bytes,
    ingest_batch_id: str,
    source_version: str,
    source_file: str,
    rule_version: str,
) -> list[dict[str, object]]:
    book = xlrd.open_workbook(file_contents=file_bytes)
    sheet = book.sheet_by_index(0)
    headers = [str(sheet.cell_value(1, column)).strip() for column in range(sheet.ncols)]
    metadata = describe_source_file(source_file)
    rows_out: list[dict[str, object]] = []

    for row_index in range(2, sheet.nrows):
        raw_row = {
            headers[column]: sheet.cell_value(row_index, column)
            for column in range(sheet.ncols)
            if headers[column]
        }
        report_cell = raw_row.get(ZQTZ_DATE)
        report_date = _cell_to_iso_date(book, report_cell) or metadata.report_date
        if not report_date:
            continue

        business_kind = _text(raw_row, ZQTZ_BUSINESS_KIND)
        business_one = _text(raw_row, ZQTZ_BUSINESS_TYPE1)
        account_category = _text(raw_row, ZQTZ_ACCOUNT_CATEGORY)
        asset_class = _text(raw_row, ZQTZ_ASSET_CLASS)
        issuance_markers = (business_kind, business_one, account_category, asset_class)
        is_issuance_like = any("发行类债" in marker or marker == "发行类债劵" for marker in issuance_markers)

        overdue_raw = _decimal(_text(raw_row, ZQTZ_OVERDUE_DAYS) or raw_row.get(ZQTZ_OVERDUE_DAYS))
        overdue_days = int(overdue_raw) if overdue_raw is not None else None

        rows_out.append(
            {
                "report_date": report_date,
                "instrument_code": _normalize_id(raw_row.get(ZQTZ_BOND_CODE)),
                "instrument_name": _text(raw_row, ZQTZ_BOND_NAME),
                "portfolio_name": _text(raw_row, ZQTZ_PORTFOLIO),
                "cost_center": _text(raw_row, ZQTZ_COST_CENTER),
                "account_category": account_category,
                "asset_class": asset_class,
                "bond_type": business_kind or business_one,
                "issuer_name": _text(raw_row, ZQTZ_ISSUER) or None,
                "industry_name": _text(raw_row, ZQTZ_INDUSTRY) or None,
                "rating": _text(raw_row, ZQTZ_RATING) or None,
                "currency_code": normalize_currency_code(raw_row.get(ZQTZ_CURRENCY)),
                "face_value_native": _decimal_required(raw_row.get(ZQTZ_FACE_VALUE)),
                "market_value_native": _decimal_required(raw_row.get(ZQTZ_FAIR_VALUE)),
                "amortized_cost_native": _decimal_required(raw_row.get(ZQTZ_AMORTIZED)),
                "accrued_interest_native": _decimal_required(raw_row.get(ZQTZ_ACCRUED)),
                "coupon_rate": _decimal(raw_row.get(ZQTZ_COUPON)),
                "ytm_value": _decimal(raw_row.get(ZQTZ_YTM)),
                "maturity_date": _cell_to_iso_date(book, raw_row.get(ZQTZ_MATURITY)),
                "next_call_date": _cell_to_iso_date(book, raw_row.get(ZQTZ_NEXT_CALL)),
                "overdue_days": overdue_days,
                "is_issuance_like": bool(is_issuance_like),
                "interest_mode": _text(raw_row, ZQTZ_INTEREST_MODE),
                "source_version": source_version,
                "rule_version": rule_version,
                "ingest_batch_id": ingest_batch_id,
                "trace_id": str(uuid4()),
            }
        )

    return rows_out


def parse_tyw_snapshot_rows_from_bytes(
    *,
    file_bytes: bytes,
    ingest_batch_id: str,
    source_version: str,
    source_file: str,
    rule_version: str,
) -> list[dict[str, object]]:
    book = xlrd.open_workbook(file_contents=file_bytes)
    sheet = book.sheet_by_index(0)
    headers = [str(sheet.cell_value(1, column)).strip() for column in range(sheet.ncols)]
    metadata = describe_source_file(source_file)
    report_date = metadata.report_date
    if not report_date:
        return []

    rows_out: list[dict[str, object]] = []

    for row_index in range(2, sheet.nrows):
        raw_row = {
            headers[column]: sheet.cell_value(row_index, column)
            for column in range(sheet.ncols)
            if headers[column]
        }
        product_type = _text(raw_row, TYW_PRODUCT)
        position_side = "liability" if product_type in _LIABILITY_PRODUCTS else "asset"

        rows_out.append(
            {
                "report_date": report_date,
                "position_id": _normalize_id(raw_row.get(TYW_SERIAL)),
                "product_type": product_type,
                "position_side": position_side,
                "counterparty_name": _text(raw_row, TYW_COUNTERPARTY),
                "account_type": _text(raw_row, TYW_ACCOUNT_TYPE) or None,
                "special_account_type": _text(raw_row, TYW_SPECIAL_ACCOUNT) or None,
                "core_customer_type": _text(raw_row, TYW_CORE_CUSTOMER) or None,
                "currency_code": normalize_currency_code(raw_row.get(TYW_CURRENCY)),
                "principal_native": _decimal_required(raw_row.get(TYW_PRINCIPAL)),
                "accrued_interest_native": _decimal_required(raw_row.get(TYW_ACCRUED)),
                "funding_cost_rate": _decimal(raw_row.get(TYW_RATE)),
                "maturity_date": _cell_to_iso_date(book, raw_row.get(TYW_MATURITY)),
                "pledged_bond_code": _text(raw_row, TYW_PLEDGED) or None,
                "source_version": source_version,
                "rule_version": rule_version,
                "ingest_batch_id": ingest_batch_id,
                "trace_id": str(uuid4()),
            }
        )

    return rows_out
