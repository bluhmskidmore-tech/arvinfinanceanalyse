"""Parse zqtz / tyw archived workbooks into standardized snapshot row dicts (no preview tables)."""

from __future__ import annotations

import logging
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import xlrd

from backend.app.core_finance.safe_decimal import _THOUSANDS_SEPARATOR_RE
from backend.app.core_finance.source_rules import describe_source_file
from backend.app.repositories.currency_codes import normalize_currency_code

logger = logging.getLogger(__name__)

ZQTZ_BOND_CODE = "债券代号"
ZQTZ_BOND_NAME = "债券名称"
ZQTZ_DATE = "日期"
ZQTZ_BUSINESS_KIND = "业务种类"
ZQTZ_BUSINESS_TYPE1 = "业务种类1"
ZQTZ_SUB_TYPE = "子类型"
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
ZQTZ_INTEREST_RECEIVABLE_PAYABLE = "应收/应付利息"
ZQTZ_FACE_VALUE = "面值"
ZQTZ_INTEREST_MODE = "计息方式"
ZQTZ_COUPON = "利率"
ZQTZ_YTM = "到期收益率"
ZQTZ_MATURITY = "到期日"
ZQTZ_NEXT_CALL = "下一行权日/逾期资产到期日"
ZQTZ_OVERDUE_DAYS = "本金逾期天数"
ZQTZ_CUSTOMER_ATTRIBUTE = "授信客户属性"
ZQTZ_VALUE_DATE = "起息日"
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


def _normalized_header(header: str) -> str:
    """Fold full-width punctuation and any inner whitespace onto one comparable key."""
    return "".join(unicodedata.normalize("NFKC", header).split())


def _resolve_header(headers: list[str], canonical: str) -> str | None:
    """Return the sheet header matching `canonical` allowing width/whitespace variants."""
    target = _normalized_header(canonical)
    for header in headers:
        if header and _normalized_header(header) == target:
            return header
    return None


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
    text = str(value).strip()
    if "," in text:
        if not _THOUSANDS_SEPARATOR_RE.fullmatch(text):
            return None
        text = text.replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except (TypeError, ValueError, ArithmeticError):
        logger.exception("_decimal: failed to convert %r", type(value).__name__)
        return None


def _decimal_required(
    value: object,
    *,
    family: str,
    header: str,
    row_number: int,
    headers: list[str],
) -> Decimal:
    parsed = _decimal(value)
    if parsed is None or not parsed.is_finite():
        column = headers.index(header) + 1 if header in headers else "missing"
        raise ValueError(
            f"{family} required amount invalid: header={header}, "
            f"row={row_number}, column={column}"
        )
    return parsed


def _zqtz_maturity_date(
    book: xlrd.Book,
    value: object,
    *,
    row_number: int,
    column_number: int,
) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, str):
        raw_text = value.strip()
        try:
            parsed = date.fromisoformat(raw_text).isoformat()
        except ValueError:
            try:
                parsed = datetime.fromisoformat(raw_text).date().isoformat()
            except ValueError:
                parsed = None
    else:
        parsed = None if isinstance(value, bool) else _cell_to_iso_date(book, value)
    try:
        if parsed is None:
            raise ValueError("date could not be parsed")
        date.fromisoformat(parsed)
    except ValueError as exc:
        raise ValueError(
            f"ZQTZ maturity_date invalid: row={row_number}, column={column_number}"
        ) from exc
    return parsed


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
    if ZQTZ_MATURITY not in headers:
        raise ValueError("ZQTZ required column missing: maturity_date")
    if headers.count(ZQTZ_MATURITY) != 1:
        raise ValueError("ZQTZ required column ambiguous: maturity_date")
    maturity_column = headers.index(ZQTZ_MATURITY) + 1
    metadata = describe_source_file(source_file)
    interest_receivable_header = _resolve_header(headers, ZQTZ_INTEREST_RECEIVABLE_PAYABLE)
    rows_out: list[dict[str, object]] = []

    for row_index in range(2, sheet.nrows):
        raw_row = {
            headers[column]: sheet.cell_value(row_index, column)
            for column in range(sheet.ncols)
            if headers[column]
        }
        if not any(_text(raw_row, header) for header in headers):
            continue
        report_cell = raw_row.get(ZQTZ_DATE)
        sheet_date = _cell_to_iso_date(book, report_cell)
        if metadata.report_date and sheet_date and metadata.report_date != sheet_date:
            raise ValueError(
                f"ZQTZ source date mismatch: file={metadata.report_date}, sheet={sheet_date}, "
                f"row={row_index + 1}; verify the source before materialization."
            )
        report_date = metadata.report_date or sheet_date
        if not report_date:
            continue

        business_kind = _text(raw_row, ZQTZ_BUSINESS_KIND)
        business_one = _text(raw_row, ZQTZ_BUSINESS_TYPE1)
        sub_type_cell = _text(raw_row, ZQTZ_SUB_TYPE)
        sub_type_value = (sub_type_cell or business_one).strip()
        account_category = _text(raw_row, ZQTZ_ACCOUNT_CATEGORY)
        asset_class = _text(raw_row, ZQTZ_ASSET_CLASS)
        issuance_markers = (business_kind, business_one, account_category, asset_class)
        # Human: caliber-issuance_exclusion-justified -- known duplicate of the
        # canonical issuance/liability check in
        # backend/app/core_finance/config/classification_rules.py::is_bond_liability.
        # NOTE: this flag IS formal-facing -- downstream balance/ADB/liability
        # services consume is_issuance_like for asset/liability scope splits,
        # which is exactly why this dual-caliber shim must stay registered here.
        # Unifying it with the canonical helper is tracked under PRD Q-PRD-5's
        # reconciliation-gate cadence; this marker only closes the audit-scan blind spot.
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
                "business_type_primary": business_one,
                "sub_type": sub_type_value,
                "issuer_name": _text(raw_row, ZQTZ_ISSUER) or None,
                "industry_name": _text(raw_row, ZQTZ_INDUSTRY) or None,
                "rating": _text(raw_row, ZQTZ_RATING) or None,
                "currency_code": normalize_currency_code(raw_row.get(ZQTZ_CURRENCY)),
                "face_value_native": _decimal_required(
                    raw_row.get(ZQTZ_FACE_VALUE),
                    family="ZQTZ",
                    header=ZQTZ_FACE_VALUE,
                    row_number=row_index + 1,
                    headers=headers,
                ),
                "market_value_native": _decimal_required(
                    raw_row.get(ZQTZ_FAIR_VALUE),
                    family="ZQTZ",
                    header=ZQTZ_FAIR_VALUE,
                    row_number=row_index + 1,
                    headers=headers,
                ),
                "amortized_cost_native": _decimal_required(
                    raw_row.get(ZQTZ_AMORTIZED),
                    family="ZQTZ",
                    header=ZQTZ_AMORTIZED,
                    row_number=row_index + 1,
                    headers=headers,
                ),
                "accrued_interest_native": _decimal_required(
                    raw_row.get(ZQTZ_ACCRUED),
                    family="ZQTZ",
                    header=ZQTZ_ACCRUED,
                    row_number=row_index + 1,
                    headers=headers,
                ),
                "interest_receivable_payable": (
                    _decimal(raw_row.get(interest_receivable_header))
                    if interest_receivable_header
                    else None
                ),
                "coupon_rate": _decimal(raw_row.get(ZQTZ_COUPON)),
                "ytm_value": _decimal(raw_row.get(ZQTZ_YTM)),
                "maturity_date": _zqtz_maturity_date(
                    book,
                    raw_row.get(ZQTZ_MATURITY),
                    row_number=row_index + 1,
                    column_number=maturity_column,
                ),
                "next_call_date": _cell_to_iso_date(book, raw_row.get(ZQTZ_NEXT_CALL)),
                "overdue_days": overdue_days,
                "is_issuance_like": bool(is_issuance_like),
                "interest_mode": _text(raw_row, ZQTZ_INTEREST_MODE),
                "value_date": _cell_to_iso_date(book, raw_row.get(ZQTZ_VALUE_DATE)),
                "customer_attribute": _text(raw_row, ZQTZ_CUSTOMER_ATTRIBUTE),
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
        if not any(_text(raw_row, header) for header in headers):
            continue
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
                "principal_native": _decimal_required(
                    raw_row.get(TYW_PRINCIPAL),
                    family="TYW",
                    header=TYW_PRINCIPAL,
                    row_number=row_index + 1,
                    headers=headers,
                ),
                "accrued_interest_native": _decimal_required(
                    raw_row.get(TYW_ACCRUED),
                    family="TYW",
                    header=TYW_ACCRUED,
                    row_number=row_index + 1,
                    headers=headers,
                ),
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
