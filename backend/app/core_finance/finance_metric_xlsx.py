from __future__ import annotations

import hashlib
import posixpath
import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile, ZipInfo

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
WORKSHEET_REL_TYPE = f"{OFFICE_REL_NS}/worksheet"
CELL_REF_RE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")
PERIOD_RE = re.compile(r"(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})")
DRIVE_RE = re.compile(r"^[A-Za-z]:")
MAX_DECIMAL_DIGITS = 128
MAX_DECIMAL_LEXEME_CHARS = 256
MAX_DECIMAL_ABS_EXPONENT = 256
MAX_DECIMAL_ABS_ADJUSTED_EXPONENT = 256
XML_WHITESPACE_CODEPOINTS = frozenset((0x09, 0x0A, 0x0D, 0x20))
LEDGER_HEADERS = (
    "组合科目代码",
    "组合科目名称",
    "币种",
    "期初余额",
    "本期借方",
    "本期贷方",
    "期末余额",
)
AVERAGE_HEADERS = ("币种", "科目", "科目日均余额")
AVERAGE_BLOCKS = ((1, "l1", 3), (5, "l2", 5), (9, "l3", 7), (13, "full", 11))
EXCLUDED_AVERAGE_BLOCKS = ((17, "l1"), (21, "l2"), (25, "l3"), (29, "full"))
FORBIDDEN_ENTRY_PREFIXES = (
    "xl/vbaproject.bin",
    "xl/externallinks/",
    "xl/embeddings/",
    "xl/activex/",
)


class FinanceMetricXlsxError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "xlsx_error",
        validation_id: str | None = None,
        sheet: str | None = None,
        cell: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.validation_id = validation_id
        self.sheet = sheet
        self.cell = cell


@dataclass(frozen=True, slots=True)
class XlsxLimits:
    max_file_bytes: int = 25 * 1024 * 1024
    max_entries: int = 256
    max_total_uncompressed_bytes: int = 100 * 1024 * 1024
    max_entry_uncompressed_bytes: int = 50 * 1024 * 1024
    max_compression_ratio: int = 100
    max_xml_bytes: int = 50 * 1024 * 1024
    max_sheets: int = 16
    max_rows_per_sheet: int = 100_000
    max_columns: int = 64
    max_cells: int = 2_000_000
    max_shared_strings: int = 250_000
    max_string_bytes: int = 32 * 1024


DEFAULT_XLSX_LIMITS = XlsxLimits()


@dataclass(frozen=True, slots=True)
class RawCell:
    ref: str
    value: Decimal | str | bool | None
    raw_value: str | None
    formula: str | None
    cell_type: str | None


@dataclass(frozen=True, slots=True)
class XlsxSheet:
    name: str
    cells: dict[str, RawCell]
    max_row: int
    max_column: int


@dataclass(frozen=True, slots=True)
class XlsxWorkbook:
    sheets: dict[str, XlsxSheet]


@dataclass(frozen=True, slots=True)
class PeriodEvidence:
    evidence_id: str
    sheet: str
    cell_ref: str
    raw_text: str
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class LedgerObservation:
    source: str
    sheet: str
    row: int
    account_code: str
    account_name: str
    currency: str
    opening: Decimal
    debit: Decimal
    credit: Decimal
    ending: Decimal
    cell_refs: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class AverageObservation:
    source: str
    basis: str
    level: str
    sheet: str
    row: int
    account_code: str
    currency: str
    balance: Decimal
    cell_refs: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ExcludedCurrencyEvidence:
    sheet: str
    basis: str
    level: str
    row: int
    currency: str
    account_code: str | None
    balance: Decimal | None
    cell_ref: str
    formula: str | None


@dataclass(frozen=True, slots=True)
class SourceIssue:
    code: str
    severity: str
    message: str
    key: tuple[str, ...]
    rows: tuple[int, ...]
    validation_id: str | None = None
    cell_refs: tuple[str, ...] = ()

    @property
    def issue_id(self) -> str:
        return self.code


@dataclass(frozen=True, slots=True)
class _FileSnapshot:
    path: Path
    payload: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class FinanceMetricSourceData:
    report_month: str
    report_date: date
    ledger_sha256: str
    daily_sha256: str
    ledger: tuple[LedgerObservation, ...]
    averages: tuple[AverageObservation, ...]
    periods: tuple[PeriodEvidence, ...]
    excluded_currencies: tuple[ExcludedCurrencyEvidence, ...]
    issues: tuple[SourceIssue, ...]
    microloan_ledger_header_rows: tuple[int, ...]
    selected_microloan_ledger_header_row: int


def read_xlsx(path: str | Path, *, limits: XlsxLimits = DEFAULT_XLSX_LIMITS) -> XlsxWorkbook:
    workbook_path = Path(path)
    snapshot = _read_file_snapshot(workbook_path, limits)
    return _read_xlsx_payload(snapshot.payload, workbook_path.name, limits)


def _read_file_snapshot(path: Path, limits: XlsxLimits) -> _FileSnapshot:
    try:
        with path.open("rb") as handle:
            payload = handle.read(limits.max_file_bytes + 1)
    except OSError as exc:
        raise FinanceMetricXlsxError(f"cannot read XLSX file: {path}", code="file_read_error") from exc
    if len(payload) > limits.max_file_bytes:
        raise FinanceMetricXlsxError("XLSX file size limit exceeded", code="file_size_limit")
    return _FileSnapshot(path=path, payload=payload, sha256=hashlib.sha256(payload).hexdigest())


def _read_xlsx_payload(payload: bytes, display_name: str, limits: XlsxLimits) -> XlsxWorkbook:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            entries = _validate_archive(archive, limits)
            shared_strings = _load_shared_strings(archive, entries, limits)
            workbook_root = _read_xml(archive, "xl/workbook.xml", entries, limits)
            workbook_relationships = _relationship_map(
                archive,
                "xl/_rels/workbook.xml.rels",
                entries,
                limits,
            )
            _validate_all_relationships(archive, entries, limits)
            sheet_nodes = workbook_root.findall(f".//{{{MAIN_NS}}}sheet")
            if len(sheet_nodes) > limits.max_sheets:
                raise FinanceMetricXlsxError("XLSX sheet count limit exceeded")

            sheets: dict[str, XlsxSheet] = {}
            total_cells = 0
            for sheet_node in sheet_nodes:
                name = str(sheet_node.attrib.get("name") or "")
                relationship_id = sheet_node.attrib.get(f"{{{OFFICE_REL_NS}}}id")
                if not name or not relationship_id or relationship_id not in workbook_relationships:
                    raise FinanceMetricXlsxError(
                        "invalid workbook sheet relationship",
                        code="invalid_sheet_relationship",
                    )
                target, target_mode, relationship_type = workbook_relationships[relationship_id]
                if relationship_type != WORKSHEET_REL_TYPE:
                    raise FinanceMetricXlsxError(
                        "workbook sheet relationship must use the worksheet type",
                        code="invalid_sheet_relationship",
                    )
                if target_mode:
                    raise FinanceMetricXlsxError(
                        "external workbook relationship is forbidden",
                        code="invalid_sheet_relationship",
                    )
                entry_name = _resolve_relationship_target("xl", target)
                if entry_name not in entries:
                    raise FinanceMetricXlsxError(
                        "workbook sheet relationship target is missing",
                        code="invalid_sheet_relationship",
                    )
                sheet, cell_count = _parse_sheet(
                    archive,
                    entry_name,
                    name,
                    shared_strings,
                    entries,
                    limits,
                )
                total_cells += cell_count
                if total_cells > limits.max_cells:
                    raise FinanceMetricXlsxError("XLSX cell count limit exceeded")
                if name in sheets:
                    raise FinanceMetricXlsxError(f"duplicate workbook sheet name: {name}")
                sheets[name] = sheet
            return XlsxWorkbook(sheets=sheets)
    except FinanceMetricXlsxError:
        raise
    except (BadZipFile, OSError, RuntimeError, ElementTree.ParseError, ValueError) as exc:
        raise FinanceMetricXlsxError(
            f"corrupt XLSX archive: {display_name}",
            code="corrupt_xlsx",
        ) from exc


def parse_finance_metric_sources(
    ledger_path: str | Path,
    daily_path: str | Path,
    *,
    requested_month: str | None = None,
    limits: XlsxLimits = DEFAULT_XLSX_LIMITS,
) -> FinanceMetricSourceData:
    ledger_file = Path(ledger_path)
    daily_file = Path(daily_path)
    ledger_snapshot = _read_file_snapshot(ledger_file, limits)
    daily_snapshot = _read_file_snapshot(daily_file, limits)
    ledger_workbook = _read_xlsx_payload(ledger_snapshot.payload, ledger_file.name, limits)
    daily_workbook = _read_xlsx_payload(daily_snapshot.payload, daily_file.name, limits)
    ledger_sheet = _required_sheet(ledger_workbook, "综本")
    annual_sheet = _required_sheet(daily_workbook, "年")
    monthly_sheet = _required_sheet(daily_workbook, "月")
    microloan_sheet = _required_sheet(daily_workbook, "微贷")

    main_ledger, ledger_period, ledger_issues = _parse_main_ledger(ledger_sheet)
    annual_rows, annual_excluded, annual_period = _parse_main_average_sheet(
        annual_sheet,
        basis="ytd_average",
        evidence_id="daily_ytd",
    )
    monthly_rows, monthly_excluded, monthly_period = _parse_main_average_sheet(
        monthly_sheet,
        basis="month_average",
        evidence_id="daily_month",
    )
    (
        microloan_averages,
        microloan_ledger,
        microloan_periods,
        microloan_headers,
        selected_microloan_header,
        microloan_issues,
    ) = _parse_microloan_sheet(microloan_sheet)

    periods = (ledger_period, annual_period, monthly_period, *microloan_periods)
    report_month, report_date = _validate_periods(periods, requested_month)
    all_ledger = [*main_ledger, *microloan_ledger]
    all_averages = [*annual_rows, *monthly_rows, *microloan_averages]
    issues = [
        *ledger_issues,
        *microloan_issues,
        *_average_duplicate_issues(all_averages),
        *_currency_issues(all_ledger, all_averages),
    ]
    return FinanceMetricSourceData(
        report_month=report_month,
        report_date=report_date,
        ledger_sha256=ledger_snapshot.sha256,
        daily_sha256=daily_snapshot.sha256,
        ledger=tuple(all_ledger),
        averages=tuple(all_averages),
        periods=periods,
        excluded_currencies=tuple((*annual_excluded, *monthly_excluded)),
        issues=tuple(issues),
        microloan_ledger_header_rows=microloan_headers,
        selected_microloan_ledger_header_row=selected_microloan_header,
    )


def normalize_account_code(value: Any) -> str:
    if value is None or isinstance(value, bool):
        raise FinanceMetricXlsxError("account code is missing or invalid")
    if isinstance(value, Decimal):
        if not value.is_finite() or value != value.to_integral_value():
            raise FinanceMetricXlsxError("account code must be an integer")
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
    elif isinstance(value, int):
        text = str(value)
    else:
        text = str(value).strip().replace("\u00a0", "")
        if re.fullmatch(r"\d+\.0+", text):
            text = text.split(".", 1)[0]
    if not text or not text.isdigit():
        raise FinanceMetricXlsxError("account code must contain digits only")
    return text


def _validate_archive(archive: ZipFile, limits: XlsxLimits) -> dict[str, ZipInfo]:
    infos = archive.infolist()
    if len(infos) > limits.max_entries:
        raise FinanceMetricXlsxError("XLSX entry count limit exceeded")
    entries: dict[str, ZipInfo] = {}
    casefold_names: set[str] = set()
    total_uncompressed = 0
    for info in infos:
        _validate_entry_name(info.orig_filename)
        name = info.filename
        folded = name.casefold()
        if name in entries or folded in casefold_names:
            raise FinanceMetricXlsxError(f"duplicate ZIP entry: {name}")
        entries[name] = info
        casefold_names.add(folded)
        if info.flag_bits & 0x1:
            raise FinanceMetricXlsxError(f"encrypted ZIP entry is forbidden: {name}")
        lower_name = name.lower()
        if any(lower_name == prefix or lower_name.startswith(prefix) for prefix in FORBIDDEN_ENTRY_PREFIXES):
            raise FinanceMetricXlsxError(f"forbidden XLSX content: {name}")
        if info.file_size > limits.max_entry_uncompressed_bytes:
            raise FinanceMetricXlsxError("XLSX entry size limit exceeded")
        if lower_name.endswith((".xml", ".rels")) and info.file_size > limits.max_xml_bytes:
            raise FinanceMetricXlsxError("XLSX XML size limit exceeded")
        total_uncompressed += info.file_size
        if total_uncompressed > limits.max_total_uncompressed_bytes:
            raise FinanceMetricXlsxError("XLSX total uncompressed size limit exceeded")
        if info.file_size:
            if info.compress_size == 0 or info.file_size / info.compress_size > limits.max_compression_ratio:
                raise FinanceMetricXlsxError("XLSX compression ratio limit exceeded")
    try:
        corrupt_entry = archive.testzip()
    except (BadZipFile, RuntimeError, OSError) as exc:
        raise FinanceMetricXlsxError("corrupt XLSX archive") from exc
    if corrupt_entry is not None:
        raise FinanceMetricXlsxError(f"corrupt XLSX entry: {corrupt_entry}")
    for required in ("xl/workbook.xml", "xl/_rels/workbook.xml.rels"):
        if required not in entries:
            raise FinanceMetricXlsxError(f"corrupt XLSX archive: missing {required}")
    return entries


def _validate_entry_name(name: str) -> None:
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or name.startswith("/")
        or DRIVE_RE.match(name)
        or any(part in {"", ".", ".."} for part in name.rstrip("/").split("/"))
    ):
        raise FinanceMetricXlsxError(f"unsafe ZIP entry: {name}")


def _read_xml(
    archive: ZipFile,
    entry_name: str,
    entries: dict[str, ZipInfo],
    limits: XlsxLimits,
) -> ElementTree.Element:
    if entry_name not in entries:
        raise FinanceMetricXlsxError(f"corrupt XLSX archive: missing {entry_name}")
    if entries[entry_name].file_size > limits.max_xml_bytes:
        raise FinanceMetricXlsxError("XLSX XML size limit exceeded")
    payload = archive.read(entry_name)
    if _contains_forbidden_xml_declaration(payload):
        raise FinanceMetricXlsxError(
            f"DOCTYPE or ENTITY is forbidden in {entry_name}",
            code="unsafe_xml",
        )
    try:
        return ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise FinanceMetricXlsxError(f"corrupt XML entry: {entry_name}") from exc


def _contains_forbidden_xml_declaration(payload: bytes) -> bool:
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        return True
    encoding = _sniff_xml_encoding(payload)
    try:
        decoded = payload.decode(encoding)
    except UnicodeDecodeError:
        return True
    if "\x00" in decoded:
        return True
    upper_text = decoded.upper()
    return "<!DOCTYPE" in upper_text or "<!ENTITY" in upper_text


def _sniff_xml_encoding(payload: bytes) -> str:
    if payload.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        return "utf-32"
    if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "utf-16"
    for encoding, width, byte_order in (
        ("utf-32-le", 4, "little"),
        ("utf-32-be", 4, "big"),
        ("utf-16-le", 2, "little"),
        ("utf-16-be", 2, "big"),
    ):
        offset = 0
        while offset + width <= len(payload):
            code_point = int.from_bytes(payload[offset : offset + width], byte_order)
            if code_point in XML_WHITESPACE_CODEPOINTS:
                offset += width
                continue
            if code_point == ord("<"):
                return encoding
            break
    return "utf-8-sig"


def _load_shared_strings(
    archive: ZipFile,
    entries: dict[str, ZipInfo],
    limits: XlsxLimits,
) -> tuple[str, ...]:
    entry_name = "xl/sharedStrings.xml"
    if entry_name not in entries:
        return ()
    root = _read_xml(archive, entry_name, entries, limits)
    items = root.findall(f"{{{MAIN_NS}}}si")
    if len(items) > limits.max_shared_strings:
        raise FinanceMetricXlsxError("XLSX shared string count limit exceeded")
    strings = tuple(_xml_text(item) for item in items)
    for value in strings:
        _validate_string(value, limits)
    return strings


def _relationship_map(
    archive: ZipFile,
    entry_name: str,
    entries: dict[str, ZipInfo],
    limits: XlsxLimits,
) -> dict[str, tuple[str, str | None, str]]:
    root = _read_xml(archive, entry_name, entries, limits)
    relationships: dict[str, tuple[str, str | None, str]] = {}
    for item in root.findall(f"{{{PACKAGE_REL_NS}}}Relationship"):
        relationship_id = str(item.attrib.get("Id") or "")
        target = str(item.attrib.get("Target") or "")
        target_mode = item.attrib.get("TargetMode")
        relationship_type = str(item.attrib.get("Type") or "")
        if not relationship_id or not target or relationship_id in relationships:
            raise FinanceMetricXlsxError("invalid or duplicate relationship")
        relationships[relationship_id] = (target, target_mode, relationship_type)
    return relationships


def _validate_all_relationships(
    archive: ZipFile,
    entries: dict[str, ZipInfo],
    limits: XlsxLimits,
) -> None:
    for entry_name in entries:
        if not entry_name.endswith(".rels"):
            continue
        if entry_name == "_rels/.rels":
            base = ""
        elif "/_rels/" in entry_name:
            base = entry_name.split("/_rels/", 1)[0]
        else:
            raise FinanceMetricXlsxError(f"unsafe relationship entry: {entry_name}")
        for target, target_mode, _relationship_type in _relationship_map(
            archive,
            entry_name,
            entries,
            limits,
        ).values():
            if str(target_mode or "").lower() == "external":
                raise FinanceMetricXlsxError("external relationship target is forbidden")
            _resolve_relationship_target(base, target)


def _resolve_relationship_target(base: str, target: str) -> str:
    if not target or "\x00" in target or "\\" in target or "://" in target or DRIVE_RE.match(target):
        raise FinanceMetricXlsxError(f"unsafe relationship target: {target}")
    if target.startswith("/"):
        normalized = posixpath.normpath(target.lstrip("/"))
    else:
        normalized = posixpath.normpath(posixpath.join(base, target))
    if normalized in {"", ".", ".."} or normalized.startswith("../") or normalized.startswith("/"):
        raise FinanceMetricXlsxError(f"unsafe relationship target: {target}")
    return normalized


def _parse_sheet(
    archive: ZipFile,
    entry_name: str,
    name: str,
    shared_strings: tuple[str, ...],
    entries: dict[str, ZipInfo],
    limits: XlsxLimits,
) -> tuple[XlsxSheet, int]:
    root = _read_xml(archive, entry_name, entries, limits)
    cells: dict[str, RawCell] = {}
    max_row = 0
    max_column = 0
    row_count = 0
    for row_node in root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"):
        row_count += 1
        if row_count > limits.max_rows_per_sheet:
            raise FinanceMetricXlsxError("XLSX row count limit exceeded")
        row_text = str(row_node.attrib.get("r") or "")
        if not row_text.isdigit() or int(row_text) < 1 or int(row_text) > limits.max_rows_per_sheet:
            raise FinanceMetricXlsxError("XLSX row index limit exceeded")
        row_number = int(row_text)
        max_row = max(max_row, row_number)
        for cell_node in row_node.findall(f"{{{MAIN_NS}}}c"):
            ref = str(cell_node.attrib.get("r") or "")
            match = CELL_REF_RE.fullmatch(ref)
            if match is None or int(match.group(2)) != row_number:
                raise FinanceMetricXlsxError(f"invalid XLSX cell reference: {ref}")
            column_number = _column_number(match.group(1))
            if column_number > limits.max_columns:
                raise FinanceMetricXlsxError("XLSX column limit exceeded")
            if ref in cells:
                raise FinanceMetricXlsxError(f"duplicate XLSX cell: {ref}")
            if len(cells) + 1 > limits.max_cells:
                raise FinanceMetricXlsxError("XLSX cell count limit exceeded")
            cells[ref] = _parse_cell(cell_node, ref, name, shared_strings, limits)
            max_column = max(max_column, column_number)
    return XlsxSheet(name=name, cells=cells, max_row=max_row, max_column=max_column), len(cells)


def _parse_cell(
    cell_node: ElementTree.Element,
    ref: str,
    sheet_name: str,
    shared_strings: tuple[str, ...],
    limits: XlsxLimits,
) -> RawCell:
    cell_type = cell_node.attrib.get("t")
    value_node = cell_node.find(f"{{{MAIN_NS}}}v")
    formula_node = cell_node.find(f"{{{MAIN_NS}}}f")
    raw_value = value_node.text if value_node is not None else None
    formula = _xml_text(formula_node) if formula_node is not None else None
    if formula is not None:
        _validate_string(formula, limits)

    if cell_type == "s":
        try:
            index = int(str(raw_value))
            if index < 0:
                raise IndexError(index)
            value: Decimal | str | bool | None = shared_strings[index]
        except (TypeError, ValueError, IndexError) as exc:
            raise FinanceMetricXlsxError(
                f"invalid shared string reference at {ref}",
                code="invalid_shared_string",
                cell=ref,
            ) from exc
    elif cell_type == "inlineStr":
        inline = cell_node.find(f"{{{MAIN_NS}}}is")
        value = _xml_text(inline) if inline is not None else ""
    elif cell_type in {"str", "e", "d"}:
        value = raw_value or ""
    elif cell_type == "b":
        if raw_value not in {"0", "1"}:
            raise FinanceMetricXlsxError(f"invalid boolean cell at {ref}")
        value = raw_value == "1"
    elif raw_value is None:
        value = None
    else:
        numeric_lexeme = raw_value.strip()
        if len(numeric_lexeme) > MAX_DECIMAL_LEXEME_CHARS:
            raise FinanceMetricXlsxError(
                f"numeric cell exceeds resource limits at {ref}",
                code="numeric_resource_limit",
                sheet=sheet_name,
                cell=ref,
            )
        try:
            value = Decimal(numeric_lexeme)
        except (InvalidOperation, AttributeError) as exc:
            raise FinanceMetricXlsxError(
                f"invalid numeric cell at {ref}",
                code="invalid_numeric",
                sheet=sheet_name,
                cell=ref,
            ) from exc
        if not value.is_finite():
            raise FinanceMetricXlsxError(
                f"non-finite numeric cell at {ref}",
                code="invalid_numeric",
                sheet=sheet_name,
                cell=ref,
            )
        decimal_tuple = value.as_tuple()
        exponent = decimal_tuple.exponent
        if (
            len(decimal_tuple.digits) > MAX_DECIMAL_DIGITS
            or abs(exponent) > MAX_DECIMAL_ABS_EXPONENT
            or abs(value.adjusted()) > MAX_DECIMAL_ABS_ADJUSTED_EXPONENT
        ):
            raise FinanceMetricXlsxError(
                f"numeric cell exceeds resource limits at {ref}",
                code="numeric_resource_limit",
                sheet=sheet_name,
                cell=ref,
            )
    if isinstance(value, str):
        _validate_string(value, limits)
    return RawCell(ref=ref, value=value, raw_value=raw_value, formula=formula, cell_type=cell_type)


def _validate_string(value: str, limits: XlsxLimits) -> None:
    if len(value.encode("utf-8")) > limits.max_string_bytes:
        raise FinanceMetricXlsxError("XLSX string byte limit exceeded")


def _xml_text(node: ElementTree.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext())


def _required_sheet(workbook: XlsxWorkbook, name: str) -> XlsxSheet:
    try:
        return workbook.sheets[name]
    except KeyError as exc:
        raise FinanceMetricXlsxError(f"required sheet is missing: {name}") from exc


def _parse_main_ledger(
    sheet: XlsxSheet,
) -> tuple[list[LedgerObservation], PeriodEvidence, list[SourceIssue]]:
    header_row, columns = _find_ledger_header(sheet, start_column=1)
    period = _find_period(
        sheet,
        evidence_id="ledger",
        columns=range(1, 8),
        rows=range(1, header_row),
    )
    rows = _parse_ledger_rows(
        sheet,
        source="main",
        header_row=header_row,
        columns=columns,
        expected_code_length=11,
    )
    issues = _ledger_duplicate_issues(rows)
    return rows, period, issues


def _find_ledger_header(sheet: XlsxSheet, *, start_column: int) -> tuple[int, dict[str, int]]:
    for row in range(1, min(sheet.max_row, 50) + 1):
        values = {
            _cell_text(sheet.cells.get(f"{_column_name(column)}{row}")): column
            for column in range(start_column, min(sheet.max_column, start_column + 11) + 1)
        }
        if all(header in values for header in LEDGER_HEADERS):
            columns = {header: values[header] for header in LEDGER_HEADERS}
            for column in columns.values():
                _reject_control_formula(
                    sheet.cells.get(f"{_column_name(column)}{row}"),
                    sheet,
                )
            return row, columns
    raise FinanceMetricXlsxError(f"required ledger header is missing in sheet {sheet.name}")


def _parse_ledger_rows(
    sheet: XlsxSheet,
    *,
    source: str,
    header_row: int,
    columns: dict[str, int],
    expected_code_length: int,
    end_row: int | None = None,
) -> list[LedgerObservation]:
    rows: list[LedgerObservation] = []
    final_row = sheet.max_row if end_row is None else end_row
    for row in range(header_row + 1, final_row + 1):
        cells = {header: sheet.cells.get(f"{_column_name(column)}{row}") for header, column in columns.items()}
        if all(_is_blank(cell) for cell in cells.values()):
            continue
        if _is_blank(cells["组合科目代码"]):
            raise FinanceMetricXlsxError(f"ledger account code is missing at row {row}")
        for header, cell in cells.items():
            if cell is not None and cell.formula is not None:
                raise FinanceMetricXlsxError(
                    f"formula is forbidden in consumed ledger cell {cell.ref} ({header})",
                    code="formula_in_data_cell",
                    sheet=sheet.name,
                    cell=cell.ref,
                )
        account_code = _business_account_code(cells["组合科目代码"], expected_code_length, source)
        currency = _required_text(cells["币种"], f"{source} ledger currency at row {row}")
        rows.append(
            LedgerObservation(
                source=source,
                sheet=sheet.name,
                row=row,
                account_code=account_code,
                account_name=_cell_text(cells["组合科目名称"]),
                currency=currency,
                opening=_required_decimal(
                    cells["期初余额"],
                    f"ledger opening numeric at row {row}",
                    sheet=sheet.name,
                ),
                debit=_required_decimal(
                    cells["本期借方"],
                    f"ledger debit numeric at row {row}",
                    sheet=sheet.name,
                ),
                credit=_required_decimal(
                    cells["本期贷方"],
                    f"ledger credit numeric at row {row}",
                    sheet=sheet.name,
                ),
                ending=_required_decimal(
                    cells["期末余额"],
                    f"ledger ending numeric at row {row}",
                    sheet=sheet.name,
                ),
                cell_refs=tuple(
                    (header, cell.ref)
                    for header, cell in cells.items()
                    if cell is not None
                ),
            )
        )
    return rows


def _ledger_duplicate_issues(rows: list[LedgerObservation]) -> list[SourceIssue]:
    grouped: dict[tuple[str, str, str], list[LedgerObservation]] = {}
    for row in rows:
        grouped.setdefault((row.source, row.account_code, row.currency), []).append(row)
    return [
        SourceIssue(
            code="duplicate_ledger_observation",
            severity="warning",
            message="duplicate ledger observations are preserved for validation",
            key=key,
            rows=tuple(item.row for item in observations),
            validation_id="ledger.duplicate_full_code",
            cell_refs=tuple(
                dict(item.cell_refs).get(LEDGER_HEADERS[0], "")
                for item in observations
            ),
        )
        for key, observations in grouped.items()
        if len(observations) > 1
    ]


def _average_duplicate_issues(rows: list[AverageObservation]) -> list[SourceIssue]:
    grouped: dict[tuple[str, str, str, str, str], list[AverageObservation]] = {}
    for row in rows:
        key = (row.source, row.basis, row.level, row.account_code, row.currency)
        grouped.setdefault(key, []).append(row)
    return [
        SourceIssue(
            code="duplicate_daily_observation",
            severity="warning",
            message="duplicate daily observations are preserved for validation",
            key=key,
            rows=tuple(item.row for item in observations),
            validation_id="daily.duplicate_account_code",
            cell_refs=tuple(
                dict(item.cell_refs).get("account_code", "")
                for item in observations
            ),
        )
        for key, observations in grouped.items()
        if len(observations) > 1
    ]


def _currency_issues(
    ledger_rows: list[LedgerObservation],
    average_rows: list[AverageObservation],
) -> list[SourceIssue]:
    issues = [
        SourceIssue(
            code="non_cnx_currency",
            severity="warning",
            message="non-CNX ledger observation is preserved for downstream validation",
            key=(row.source, row.account_code, row.currency),
            rows=(row.row,),
            validation_id="currency.cnx_only",
            cell_refs=(dict(row.cell_refs).get(LEDGER_HEADERS[2], ""),),
        )
        for row in ledger_rows
        if row.currency != "CNX"
    ]
    issues.extend(
        SourceIssue(
            code="non_cnx_currency",
            severity="warning",
            message="non-CNX average observation is preserved for downstream validation",
            key=(row.source, row.basis, row.level, row.account_code, row.currency),
            rows=(row.row,),
            validation_id="currency.cnx_only",
            cell_refs=(dict(row.cell_refs).get("currency", ""),),
        )
        for row in average_rows
        if row.currency != "CNX"
    )
    return issues


def _parse_main_average_sheet(
    sheet: XlsxSheet,
    *,
    basis: str,
    evidence_id: str,
) -> tuple[list[AverageObservation], list[ExcludedCurrencyEvidence], PeriodEvidence]:
    header_row = _find_average_header(sheet, starts=(1, 5, 9, 13))
    period = _main_average_period(sheet, header_row, evidence_id)
    rows = _parse_average_blocks(sheet, header_row, basis=basis, source="main", blocks=AVERAGE_BLOCKS)
    excluded = _parse_excluded_average_blocks(sheet, header_row, basis=basis)
    return rows, excluded, period


def _find_average_header(sheet: XlsxSheet, *, starts: tuple[int, ...]) -> int:
    for row in range(1, min(sheet.max_row, 20) + 1):
        if all(
            tuple(_cell_text(sheet.cells.get(f"{_column_name(start + offset)}{row}")) for offset in range(3))
            == AVERAGE_HEADERS
            for start in starts
        ):
            for start in starts:
                for offset in range(3):
                    _reject_control_formula(
                        sheet.cells.get(f"{_column_name(start + offset)}{row}"),
                        sheet,
                    )
            return row
    raise FinanceMetricXlsxError(f"required average header is missing in sheet {sheet.name}")


def _main_average_period(sheet: XlsxSheet, header_row: int, evidence_id: str) -> PeriodEvidence:
    periods: list[PeriodEvidence] = []
    for start, _level, _length in AVERAGE_BLOCKS:
        try:
            periods.append(
                _find_period(
                    sheet,
                    evidence_id=evidence_id,
                    columns=(start,),
                    rows=range(1, header_row),
                )
            )
        except FinanceMetricXlsxError as exc:
            if exc.code != "missing_period":
                raise
            raise FinanceMetricXlsxError(
                f"{sheet.name} period banner is missing at column {_column_name(start)}",
                code="missing_period_banner",
                sheet=sheet.name,
            ) from exc
    first = periods[0]
    if any((item.start, item.end) != (first.start, first.end) for item in periods[1:]):
        raise FinanceMetricXlsxError(
            f"{sheet.name} period banners do not match",
            code="period_banner_conflict",
            sheet=sheet.name,
        )
    return first


def _parse_average_blocks(
    sheet: XlsxSheet,
    header_row: int,
    *,
    basis: str,
    source: str,
    blocks: tuple[tuple[int, str, int], ...],
) -> list[AverageObservation]:
    rows: list[AverageObservation] = []
    for start, level, code_length in blocks:
        for row in range(header_row + 1, sheet.max_row + 1):
            currency_cell = sheet.cells.get(f"{_column_name(start)}{row}")
            code_cell = sheet.cells.get(f"{_column_name(start + 1)}{row}")
            balance_cell = sheet.cells.get(f"{_column_name(start + 2)}{row}")
            if all(_is_blank(cell) for cell in (currency_cell, code_cell, balance_cell)):
                continue
            for cell in (currency_cell, code_cell, balance_cell):
                if cell is not None and cell.formula is not None:
                    raise FinanceMetricXlsxError(
                        f"formula is forbidden in consumed daily cell {cell.ref}",
                        code="formula_in_data_cell",
                        sheet=sheet.name,
                        cell=cell.ref,
                    )
            currency = _required_text(currency_cell, f"daily currency at row {row}")
            account_code = _business_account_code(code_cell, code_length, source)
            rows.append(
                AverageObservation(
                    source=source,
                    basis=basis,
                    level=level,
                    sheet=sheet.name,
                    row=row,
                    account_code=account_code,
                    currency=currency,
                    balance=_required_decimal(
                        balance_cell,
                        f"daily balance numeric at row {row}",
                        sheet=sheet.name,
                    ),
                    cell_refs=(
                        ("currency", currency_cell.ref if currency_cell else ""),
                        ("account_code", code_cell.ref if code_cell else ""),
                        ("balance", balance_cell.ref if balance_cell else ""),
                    ),
                )
            )
    return rows


def _parse_excluded_average_blocks(
    sheet: XlsxSheet,
    header_row: int,
    *,
    basis: str,
) -> list[ExcludedCurrencyEvidence]:
    excluded: list[ExcludedCurrencyEvidence] = []
    for start, level in EXCLUDED_AVERAGE_BLOCKS:
        headers = tuple(
            _cell_text(sheet.cells.get(f"{_column_name(start + offset)}{header_row}"))
            for offset in range(3)
        )
        if headers != AVERAGE_HEADERS:
            continue
        for offset in range(3):
            _reject_control_formula(
                sheet.cells.get(f"{_column_name(start + offset)}{header_row}"),
                sheet,
            )
        for row in range(header_row + 1, sheet.max_row + 1):
            currency_cell = sheet.cells.get(f"{_column_name(start)}{row}")
            code_cell = sheet.cells.get(f"{_column_name(start + 1)}{row}")
            balance_cell = sheet.cells.get(f"{_column_name(start + 2)}{row}")
            if _cell_text(currency_cell) != "CNY":
                continue
            account_code: str | None = None
            if not _is_blank(code_cell):
                try:
                    account_code = normalize_account_code(code_cell.value if code_cell else None)
                except FinanceMetricXlsxError:
                    account_code = None
            balance = balance_cell.value if balance_cell and isinstance(balance_cell.value, Decimal) else None
            excluded.append(
                ExcludedCurrencyEvidence(
                    sheet=sheet.name,
                    basis=basis,
                    level=level,
                    row=row,
                    currency="CNY",
                    account_code=account_code,
                    balance=balance,
                    cell_ref=balance_cell.ref if balance_cell else "",
                    formula=balance_cell.formula if balance_cell else None,
                )
            )
    return excluded


def _parse_microloan_sheet(
    sheet: XlsxSheet,
) -> tuple[
    list[AverageObservation],
    list[LedgerObservation],
    tuple[PeriodEvidence, PeriodEvidence, PeriodEvidence],
    tuple[int, ...],
    int,
    list[SourceIssue],
]:
    average_header = _find_average_header(sheet, starts=(1, 5))
    ytd_period = _find_period(
        sheet,
        evidence_id="microloan_ytd",
        columns=(1,),
        rows=range(1, average_header),
    )
    month_period = _find_period(
        sheet,
        evidence_id="microloan_month",
        columns=(5,),
        rows=range(1, average_header),
    )
    average_rows = _parse_average_blocks(
        sheet,
        average_header,
        basis="ytd_average",
        source="microloan",
        blocks=((1, "l1", 3),),
    )
    average_rows.extend(
        _parse_average_blocks(
            sheet,
            average_header,
            basis="month_average",
            source="microloan",
            blocks=((5, "l1", 3),),
        )
    )

    header_rows: list[int] = []
    columns: dict[str, int] | None = None
    for row in range(1, sheet.max_row + 1):
        if _cell_text(sheet.cells.get(f"I{row}")) != LEDGER_HEADERS[0]:
            continue
        actual = tuple(_cell_text(sheet.cells.get(f"{_column_name(9 + offset)}{row}")) for offset in range(7))
        if actual == LEDGER_HEADERS:
            for offset in range(7):
                _reject_control_formula(
                    sheet.cells.get(f"{_column_name(9 + offset)}{row}"),
                    sheet,
                )
            header_rows.append(row)
    if not header_rows:
        raise FinanceMetricXlsxError("required microloan ledger header is missing")
    selected_header = header_rows[-1]
    columns = {header: 9 + offset for offset, header in enumerate(LEDGER_HEADERS)}
    ledger_period = _find_period(
        sheet,
        evidence_id="microloan_ledger",
        columns=(9,),
        rows=range(max(1, selected_header - 8), selected_header),
        reverse=True,
    )
    ledger_rows = _parse_ledger_rows(
        sheet,
        source="microloan",
        header_row=selected_header,
        columns=columns,
        expected_code_length=3,
        end_row=_microloan_ledger_end_row(sheet, selected_header),
    )
    if not ledger_rows:
        raise FinanceMetricXlsxError("microloan ledger last block has no observations")
    issues = _ledger_duplicate_issues(ledger_rows)
    return (
        average_rows,
        ledger_rows,
        (ytd_period, month_period, ledger_period),
        tuple(header_rows),
        selected_header,
        issues,
    )


def _microloan_ledger_end_row(sheet: XlsxSheet, header_row: int) -> int:
    for row in range(header_row + 1, sheet.max_row + 1):
        cells = [sheet.cells.get(f"{_column_name(column)}{row}") for column in range(9, 16)]
        if any(_cell_has_content(cell) for cell in cells):
            continue
        for trailing_row in range(row + 1, sheet.max_row + 1):
            trailing_cells = [
                sheet.cells.get(f"{_column_name(column)}{trailing_row}")
                for column in range(9, 16)
            ]
            first_content = next(
                (cell for cell in trailing_cells if _cell_has_content(cell)),
                None,
            )
            if first_content is not None:
                raise FinanceMetricXlsxError(
                    "microloan ledger contains content after its first empty row",
                    code="microloan_trailing_content",
                    sheet=sheet.name,
                    cell=first_content.ref,
                )
        return row - 1
    return sheet.max_row


def _find_period(
    sheet: XlsxSheet,
    *,
    evidence_id: str,
    columns: range | tuple[int, ...],
    rows: range,
    reverse: bool = False,
) -> PeriodEvidence:
    row_candidates = list(rows)
    if reverse:
        row_candidates.reverse()
    matches: list[PeriodEvidence] = []
    for row in row_candidates:
        for column in columns:
            ref = f"{_column_name(column)}{row}"
            cell = sheet.cells.get(ref)
            raw_text = _cell_text(cell).replace("\u00a0", " ")
            period_matches = tuple(PERIOD_RE.finditer(raw_text))
            if not period_matches:
                continue
            _reject_control_formula(cell, sheet)
            for match in period_matches:
                try:
                    start = date.fromisoformat(match.group(1))
                    end = date.fromisoformat(match.group(2))
                except ValueError as exc:
                    raise FinanceMetricXlsxError(
                        f"invalid period evidence at {sheet.name}!{ref}",
                        code="invalid_period",
                        sheet=sheet.name,
                        cell=ref,
                    ) from exc
                matches.append(
                    PeriodEvidence(
                        evidence_id=evidence_id,
                        sheet=sheet.name,
                        cell_ref=ref,
                        raw_text=raw_text,
                        start=start,
                        end=end,
                    )
                )
    if not matches:
        raise FinanceMetricXlsxError(
            f"required period evidence is missing: {evidence_id}",
            code="missing_period",
            sheet=sheet.name,
        )
    if len({(item.start, item.end) for item in matches}) > 1:
        raise FinanceMetricXlsxError(
            f"conflicting period evidence candidates: {evidence_id}",
            code="ambiguous_period",
            sheet=sheet.name,
            cell=matches[0].cell_ref,
        )
    return matches[0]


def _validate_periods(
    periods: tuple[PeriodEvidence, ...],
    requested_month: str | None,
) -> tuple[str, date]:
    if len(periods) != 6:
        raise FinanceMetricXlsxError(
            "six source period evidences are required",
            code="missing_period",
        )
    if requested_month is None:
        ledger_period = next(
            (period for period in periods if period.evidence_id == "ledger"),
            periods[0],
        )
        report_date = ledger_period.end
        return f"{report_date.year:04d}{report_date.month:02d}", report_date
    if not re.fullmatch(r"\d{6}", requested_month):
        raise FinanceMetricXlsxError(
            "requested period month must be YYYYMM",
            code="invalid_requested_month",
        )
    try:
        requested_year = int(requested_month[:4])
        requested_number = int(requested_month[4:])
        report_date = date(
            requested_year,
            requested_number,
            monthrange(requested_year, requested_number)[1],
        )
    except ValueError as exc:
        raise FinanceMetricXlsxError(
            "requested period month is invalid",
            code="invalid_requested_month",
        ) from exc
    mismatched_period = next((period for period in periods if period.end != report_date), None)
    if mismatched_period is not None:
        raise FinanceMetricXlsxError(
            f"source period {mismatched_period.evidence_id} does not end on requested month-end",
            code="source_period_mismatch",
            sheet=mismatched_period.sheet,
            cell=mismatched_period.cell_ref,
        )
    return requested_month, report_date


def _business_account_code(cell: RawCell | None, expected_length: int, source: str) -> str:
    if cell is None or cell.value is None:
        raise FinanceMetricXlsxError(f"{source} account code is missing")
    if cell.cell_type not in {"s", "inlineStr", "str"} and cell.raw_value and "e" in cell.raw_value.lower():
        raise FinanceMetricXlsxError(f"scientific account code lexeme is forbidden at {cell.ref}")
    account_code = normalize_account_code(cell.value)
    if len(account_code) != expected_length:
        prefix = "microloan " if source == "microloan" else ""
        raise FinanceMetricXlsxError(
            f"{prefix}account code at {cell.ref} must contain exactly {expected_length} digits"
        )
    return account_code


def _required_decimal(
    cell: RawCell | None,
    context: str,
    *,
    sheet: str | None = None,
) -> Decimal:
    if cell is None or not isinstance(cell.value, Decimal) or not cell.value.is_finite():
        raise FinanceMetricXlsxError(
            f"{context} is missing or invalid numeric data",
            code="invalid_numeric",
            sheet=sheet,
            cell=cell.ref if cell is not None else None,
        )
    return cell.value


def _reject_control_formula(cell: RawCell | None, sheet: XlsxSheet) -> None:
    if cell is None or cell.formula is None:
        return
    raise FinanceMetricXlsxError(
        f"formula is forbidden in control-flow cell {sheet.name}!{cell.ref}",
        code="formula_in_control_cell",
        sheet=sheet.name,
        cell=cell.ref,
    )


def _required_text(cell: RawCell | None, context: str) -> str:
    value = _cell_text(cell).strip()
    if not value:
        raise FinanceMetricXlsxError(f"{context} is missing")
    return value


def _cell_text(cell: RawCell | None) -> str:
    if cell is None or cell.value is None:
        return ""
    if isinstance(cell.value, str):
        return cell.value.strip()
    if isinstance(cell.value, Decimal):
        return format(cell.value, "f")
    return str(cell.value)


def _is_blank(cell: RawCell | None) -> bool:
    return cell is None or cell.value is None or (isinstance(cell.value, str) and not cell.value.strip())


def _cell_has_content(cell: RawCell | None) -> bool:
    return cell is not None and (cell.formula is not None or not _is_blank(cell))


def _column_number(column: str) -> int:
    value = 0
    for char in column:
        value = value * 26 + ord(char) - 64
    return value


def _column_name(number: int) -> str:
    if number < 1:
        raise FinanceMetricXlsxError("column number must be positive")
    output = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        output = chr(65 + remainder) + output
    return output
