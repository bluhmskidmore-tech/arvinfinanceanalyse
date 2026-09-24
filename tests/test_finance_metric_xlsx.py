from __future__ import annotations

import hashlib
import io
import re
import struct
import warnings
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data_input" / "pnl_总账对账-日均"
CELL_REF = re.compile(r"([A-Z]+)([1-9][0-9]*)")


def _module():
    try:
        from backend.app.core_finance import finance_metric_xlsx
    except ImportError:
        pytest.fail("finance metric XLSX parser is not implemented")
    return finance_metric_xlsx


def _inline(ref: str, value: str, *, formula: str | None = None) -> str:
    formula_xml = f"<f>{escape(formula)}</f>" if formula is not None else ""
    return (
        f'<c r="{ref}" t="inlineStr">{formula_xml}'
        f'<is><t xml:space="preserve">{escape(value)}</t></is></c>'
    )


def _shared(ref: str, index: int) -> str:
    return f'<c r="{ref}" t="s"><v>{index}</v></c>'


def _number(ref: str, value: str | None, *, formula: str | None = None) -> str:
    formula_xml = f"<f>{escape(formula)}</f>" if formula is not None else ""
    value_xml = f"<v>{escape(value)}</v>" if value is not None else ""
    return f'<c r="{ref}">{formula_xml}{value_xml}</c>'


def _sheet_xml(cells: dict[str, str], *, dimension: str = "A1") -> bytes:
    rows: dict[int, list[tuple[str, str]]] = {}
    for ref, cell_xml in cells.items():
        match = CELL_REF.fullmatch(ref)
        assert match is not None
        rows.setdefault(int(match.group(2)), []).append((ref, cell_xml))
    row_xml = "".join(
        f'<row r="{row}">' + "".join(cell for _ref, cell in sorted(items)) + "</row>"
        for row, items in sorted(rows.items())
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/><sheetData>{row_xml}</sheetData></worksheet>'
    ).encode()


def _write_xlsx(
    path: Path,
    sheets: dict[str, dict[str, str]],
    *,
    shared_strings: tuple[str, ...] = (),
    relationship_target: str | None = None,
    target_mode: str | None = None,
    relationship_type: str = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
    extra_entries: tuple[tuple[str, bytes], ...] = (),
    workbook_prefix: bytes = b"",
    workbook_payload: bytes | None = None,
) -> Path:
    workbook_sheets = []
    relationships = []
    sheet_entries: list[tuple[str, bytes]] = []
    for index, (name, cells) in enumerate(sheets.items(), start=1):
        workbook_sheets.append(f'<sheet name={quoteattr(name)} sheetId="{index}" r:id="rId{index}"/>')
        target = relationship_target if index == 1 and relationship_target is not None else f"worksheets/sheet{index}.xml"
        mode = f' TargetMode="{target_mode}"' if index == 1 and target_mode is not None else ""
        relationships.append(
            f'<Relationship Id="rId{index}" '
            f'Type={quoteattr(relationship_type)} '
            f'Target={quoteattr(target)}{mode}/>'
        )
        sheet_entries.append((f"xl/worksheets/sheet{index}.xml", _sheet_xml(cells, dimension="A1:XFD1048576")))

    workbook = workbook_payload or (
        workbook_prefix
        + (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{"".join(workbook_sheets)}</sheets></workbook>'
        ).encode()
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{"".join(relationships)}</Relationships>'
    ).encode()
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    ).encode()
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>'
    ).encode()

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for name, payload in sheet_entries:
            archive.writestr(name, payload)
        if shared_strings:
            items = "".join(f"<si><t>{escape(value)}</t></si>" for value in shared_strings)
            archive.writestr(
                "xl/sharedStrings.xml",
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    f"{items}</sst>"
                ).encode(),
            )
        for name, payload in extra_entries:
            archive.writestr(name, payload)
    return path


def _ledger_cells(*, header_row: int = 8) -> dict[str, str]:
    cells = {
        "A5": _inline("A5", "会计期间： 2026-06-01--2026-06-30 币种： CNX"),
    }
    for column, label in zip(
        "ABCDEFG",
        ("组合科目代码", "组合科目名称", "币种", "期初余额", "本期借方", "本期贷方", "期末余额"),
        strict=True,
    ):
        ref = f"{column}{header_row}"
        cells[ref] = _inline(ref, label)
    data_row = header_row + 1
    cells.update(
        {
            f"A{data_row}": _number(f"A{data_row}", "10101000001"),
            f"B{data_row}": _inline(f"B{data_row}", "现金"),
            f"C{data_row}": _inline(f"C{data_row}", "CNX"),
            f"D{data_row}": _number(f"D{data_row}", "393899032.07"),
            f"E{data_row}": _number(f"E{data_row}", "1.20"),
            f"F{data_row}": _number(f"F{data_row}", "2.30"),
            f"G{data_row}": _number(f"G{data_row}", "354538784.38"),
        }
    )
    return cells


def _daily_sheet_cells(period_text: str) -> dict[str, str]:
    cells = {f"{column}2": _inline(f"{column}2", period_text) for column in ("A", "E", "I", "M")}
    for start in ("A", "E", "I", "M", "Q", "U", "Y", "AC"):
        start_number = _column_number(start)
        for offset, label in enumerate(("币种", "科目", "科目日均余额")):
            column = _column_name(start_number + offset)
            ref = f"{column}4"
            cells[ref] = _inline(ref, label)
    blocks = (
        ("A", "CNX", "101", "10.01"),
        ("E", "CNX", "10101", "20.02"),
        ("I", "CNX", "1010101", "30.03"),
        ("M", "CNX", "10101000001", "9007199254740993.27"),
        ("Q", "CNY", "101", "11"),
        ("U", "CNY", "10101", "22"),
        ("Y", "CNY", "1010101", "33"),
        ("AC", "CNY", "10101000001", "44"),
    )
    for start, currency, code, amount in blocks:
        start_number = _column_number(start)
        refs = [_column_name(start_number + offset) + "5" for offset in range(3)]
        cells[refs[0]] = _inline(refs[0], currency)
        cells[refs[1]] = _number(refs[1], code)
        cells[refs[2]] = _number(refs[2], amount)
    return cells


def _microloan_cells() -> dict[str, str]:
    cells = {
        "A2": _inline("A2", "日期： 2026-01-01 至 2026-06-30"),
        "E2": _inline("E2", "日期： 2026-06-01 至 2026-06-30"),
    }
    for start in ("A", "E"):
        start_number = _column_number(start)
        for offset, label in enumerate(("币种", "科目", "科目日均余额")):
            column = _column_name(start_number + offset)
            ref = f"{column}3"
            cells[ref] = _inline(ref, label)
    for start, amount in (("A", "101.01"), ("E", "202.02")):
        start_number = _column_number(start)
        refs = [_column_name(start_number + offset) + "4" for offset in range(3)]
        cells[refs[0]] = _inline(refs[0], "CNX")
        cells[refs[1]] = _number(refs[1], "122")
        cells[refs[2]] = _number(refs[2], amount)

    _add_microloan_ledger_block(cells, period_row=5, header_row=6, data_row=7, code="999", ending="1")
    _add_microloan_ledger_block(cells, period_row=11, header_row=12, data_row=13, code="122", ending="303.03")
    return cells


def _add_microloan_ledger_block(
    cells: dict[str, str],
    *,
    period_row: int,
    header_row: int,
    data_row: int,
    code: str,
    ending: str,
) -> None:
    cells[f"I{period_row}"] = _inline(
        f"I{period_row}",
        "会计期间： 2026-06-01--2026-06-30 币种： CNX",
    )
    for column, label in zip(
        "IJKLMNO",
        ("组合科目代码", "组合科目名称", "币种", "期初余额", "本期借方", "本期贷方", "期末余额"),
        strict=True,
    ):
        ref = f"{column}{header_row}"
        cells[ref] = _inline(ref, label)
    cells.update(
        {
            f"I{data_row}": _number(f"I{data_row}", code),
            f"J{data_row}": _inline(f"J{data_row}", "微贷"),
            f"K{data_row}": _inline(f"K{data_row}", "CNX"),
            f"L{data_row}": _number(f"L{data_row}", "1"),
            f"M{data_row}": _number(f"M{data_row}", "2"),
            f"N{data_row}": _number(f"N{data_row}", "3"),
            f"O{data_row}": _number(f"O{data_row}", ending),
        }
    )


def _write_source_pair(
    tmp_path: Path,
    *,
    mutate_ledger: Callable[[dict[str, str]], None] | None = None,
    mutate_daily: Callable[[dict[str, dict[str, str]]], None] | None = None,
) -> tuple[Path, Path]:
    ledger_cells = _ledger_cells()
    daily_sheets = {
        "年": _daily_sheet_cells("日期： 2026-01-01 至 2026-06-30"),
        "月": _daily_sheet_cells("日期： 2026-06-01 至 2026-06-30"),
        "微贷": _microloan_cells(),
    }
    if mutate_ledger is not None:
        mutate_ledger(ledger_cells)
    if mutate_daily is not None:
        mutate_daily(daily_sheets)
    ledger = _write_xlsx(tmp_path / "总账对账202606.xlsx", {"综本": ledger_cells})
    daily = _write_xlsx(tmp_path / "日均202606.xlsx", daily_sheets)
    return ledger, daily


def _column_number(column: str) -> int:
    value = 0
    for char in column:
        value = value * 26 + ord(char) - 64
    return value


def _column_name(number: int) -> str:
    output = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        output = chr(65 + remainder) + output
    return output


def _with_formula(cell_xml: str, formula: str = "1") -> str:
    return cell_xml.replace(">", f"><f>{escape(formula)}</f>", 1)


def test_read_xlsx_preserves_decimal_formula_inline_and_shared_string(tmp_path: Path) -> None:
    module = _module()
    path = _write_xlsx(
        tmp_path / "cells.xlsx",
        {
            "综本": {
                "A1": _shared("A1", 0),
                "B1": _inline("B1", "内联文本"),
                "C1": _number("C1", "9007199254740993.27"),
                "D1": _number("D1", "123.45", formula="C1/2"),
            }
        },
        shared_strings=("共享文本",),
    )

    workbook = module.read_xlsx(path)
    cells = workbook.sheets["综本"].cells

    assert cells["A1"].value == "共享文本"
    assert cells["B1"].value == "内联文本"
    assert cells["C1"].value == Decimal("9007199254740993.27")
    assert cells["C1"].raw_value == "9007199254740993.27"
    assert cells["D1"].value == Decimal("123.45")
    assert cells["D1"].formula == "C1/2"


def test_read_xlsx_preserves_bounded_high_precision_decimal(tmp_path: Path) -> None:
    module = _module()
    raw_value = (
        "1234567890123456789012345678901234567890."
        "1234567890123456789012345678901234567890"
    )
    path = _write_xlsx(
        tmp_path / "high-precision.xlsx",
        {"Only": {"A1": _number("A1", raw_value)}},
    )

    workbook = module.read_xlsx(path)

    assert workbook.sheets["Only"].cells["A1"].value == Decimal(raw_value)


@pytest.mark.parametrize(
    "raw_value",
    [
        "1e999999999",
        "1e-999999999",
        "1" * 129,
    ],
)
def test_read_xlsx_rejects_decimal_resource_limits(tmp_path: Path, raw_value: str) -> None:
    module = _module()
    path = _write_xlsx(
        tmp_path / "decimal-resource-limit.xlsx",
        {"Only": {"A1": _number("A1", raw_value)}},
    )

    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.read_xlsx(path)

    assert exc_info.value.code == "numeric_resource_limit"
    assert exc_info.value.sheet == "Only"
    assert exc_info.value.cell == "A1"


@pytest.mark.parametrize("raw_value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_read_xlsx_rejects_non_finite_numeric_cells_globally(tmp_path: Path, raw_value: str) -> None:
    module = _module()
    path = _write_xlsx(
        tmp_path / "non-finite.xlsx",
        {"Only": {"A1": _number("A1", raw_value)}},
    )

    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.read_xlsx(path)

    assert exc_info.value.code == "invalid_numeric"
    assert exc_info.value.sheet == "Only"
    assert exc_info.value.cell == "A1"


def test_read_xlsx_ignores_untrusted_dimension(tmp_path: Path) -> None:
    module = _module()
    path = _write_xlsx(tmp_path / "dimension.xlsx", {"Only": {"A1": _number("A1", "1")}})

    workbook = module.read_xlsx(path, limits=module.XlsxLimits(max_rows_per_sheet=1, max_columns=1, max_cells=1))

    assert workbook.sheets["Only"].max_row == 1
    assert workbook.sheets["Only"].max_column == 1


def test_normalize_account_code_never_uses_float() -> None:
    module = _module()

    assert module.normalize_account_code(Decimal("10101000001")) == "10101000001"
    assert module.normalize_account_code(Decimal("1.22E+2")) == "122"
    assert module.normalize_account_code(" 00122.0\u00a0") == "00122"
    with pytest.raises(module.FinanceMetricXlsxError, match="account code"):
        module.normalize_account_code(Decimal("122.5"))


def test_parse_sources_discovers_headers_periods_microloan_and_exclusions(tmp_path: Path) -> None:
    module = _module()
    ledger, daily = _write_source_pair(tmp_path)

    parsed = module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    main_ledger = [row for row in parsed.ledger if row.source == "main"]
    microloan_ledger = [row for row in parsed.ledger if row.source == "microloan"]
    assert main_ledger[0].account_code == "10101000001"
    assert main_ledger[0].opening == Decimal("393899032.07")
    assert [(row.account_code, row.ending) for row in microloan_ledger] == [("122", Decimal("303.03"))]
    assert parsed.microloan_ledger_header_rows == (6, 12)
    assert parsed.selected_microloan_ledger_header_row == 12
    assert {period.evidence_id for period in parsed.periods} == {
        "ledger",
        "daily_ytd",
        "daily_month",
        "microloan_ytd",
        "microloan_month",
        "microloan_ledger",
    }
    assert {period.end for period in parsed.periods} == {date(2026, 6, 30)}
    assert len([row for row in parsed.averages if row.source == "main"]) == 8
    assert len([row for row in parsed.averages if row.source == "microloan"]) == 2
    assert len(parsed.excluded_currencies) == 8
    assert parsed.report_month == "202606"
    assert parsed.report_date == date(2026, 6, 30)
    assert parsed.ledger_sha256 == hashlib.sha256(ledger.read_bytes()).hexdigest()
    assert parsed.daily_sha256 == hashlib.sha256(daily.read_bytes()).hexdigest()


def test_parse_sources_reads_and_hashes_each_source_from_one_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    ledger, daily = _write_source_pair(tmp_path)
    expected_hashes = {
        ledger.resolve(): hashlib.sha256(ledger.read_bytes()).hexdigest(),
        daily.resolve(): hashlib.sha256(daily.read_bytes()).hexdigest(),
    }
    original_open = io.open
    open_counts: Counter[Path] = Counter()

    def tracked_open(file: object, *args: object, **kwargs: object):
        try:
            resolved = Path(file).resolve()  # type: ignore[arg-type]
        except TypeError:
            resolved = None
        if resolved in expected_hashes:
            open_counts[resolved] += 1
        return original_open(file, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(io, "open", tracked_open)

    parsed = module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    assert open_counts == Counter({ledger.resolve(): 1, daily.resolve(): 1})
    assert parsed.ledger_sha256 == expected_hashes[ledger.resolve()]
    assert parsed.daily_sha256 == expected_hashes[daily.resolve()]


@pytest.mark.parametrize("missing", ["ledger_sheet", "daily_sheet", "header"])
def test_parse_sources_requires_canonical_sheets_and_headers(tmp_path: Path, missing: str) -> None:
    module = _module()
    ledger_cells = _ledger_cells()
    daily_sheets = {
        "年": _daily_sheet_cells("日期： 2026-01-01 至 2026-06-30"),
        "月": _daily_sheet_cells("日期： 2026-06-01 至 2026-06-30"),
        "微贷": _microloan_cells(),
    }
    ledger_sheets = {"综本": ledger_cells}
    if missing == "ledger_sheet":
        ledger_sheets = {"人民币": ledger_cells}
    elif missing == "daily_sheet":
        daily_sheets.pop("月")
    else:
        daily_sheets["年"].pop("M4")
    ledger = _write_xlsx(tmp_path / "ledger.xlsx", ledger_sheets)
    daily = _write_xlsx(tmp_path / "daily.xlsx", daily_sheets)

    with pytest.raises(module.FinanceMetricXlsxError, match="sheet|header"):
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")


def test_parse_sources_rejects_formula_in_consumed_ledger_cell(tmp_path: Path) -> None:
    module = _module()

    def mutate(cells: dict[str, str]) -> None:
        cells["D9"] = _number("D9", "393899032.07", formula="1+1")

    ledger, daily = _write_source_pair(tmp_path, mutate_ledger=mutate)
    with pytest.raises(module.FinanceMetricXlsxError, match="formula"):
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")


def test_parse_sources_rejects_formula_in_consumed_daily_cell(tmp_path: Path) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        sheets["年"]["C5"] = _number("C5", "10.01", formula="1+1")

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    with pytest.raises(module.FinanceMetricXlsxError, match="formula"):
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")


@pytest.mark.parametrize(
    "control_cell",
    [
        "ledger_header",
        "ledger_period",
        "daily_header",
        "daily_period",
        "microloan_average_header",
        "microloan_period",
        "microloan_ledger_header",
        "microloan_ledger_period",
    ],
)
def test_parse_sources_rejects_formula_in_control_flow_cell(
    tmp_path: Path,
    control_cell: str,
) -> None:
    module = _module()

    def mutate_ledger(cells: dict[str, str]) -> None:
        ref = "A8" if control_cell == "ledger_header" else "A5"
        if control_cell.startswith("ledger_"):
            cells[ref] = _with_formula(cells[ref])

    def mutate_daily(sheets: dict[str, dict[str, str]]) -> None:
        annual, _monthly, microloan = sheets.values()
        targets = {
            "daily_header": (annual, "A4"),
            "daily_period": (annual, "A2"),
            "microloan_average_header": (microloan, "A3"),
            "microloan_period": (microloan, "E2"),
            "microloan_ledger_header": (microloan, "I12"),
            "microloan_ledger_period": (microloan, "I11"),
        }
        target = targets.get(control_cell)
        if target is not None:
            cells, ref = target
            cells[ref] = _with_formula(cells[ref])

    ledger, daily = _write_source_pair(
        tmp_path,
        mutate_ledger=mutate_ledger,
        mutate_daily=mutate_daily,
    )

    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")
    assert exc_info.value.code == "formula_in_control_cell"


def test_parse_sources_ignores_formula_in_excluded_cny_block(tmp_path: Path) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        sheets["年"]["S5"] = _number("S5", "11", formula="1+1")

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    parsed = module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    assert any(row.cell_ref == "S5" for row in parsed.excluded_currencies)


@pytest.mark.parametrize("bad_value", [None, "not-a-number"])
def test_parse_sources_rejects_missing_or_invalid_ledger_amount(tmp_path: Path, bad_value: str | None) -> None:
    module = _module()

    def mutate(cells: dict[str, str]) -> None:
        cells["D9"] = _number("D9", bad_value) if bad_value is None else _inline("D9", bad_value)

    ledger, daily = _write_source_pair(tmp_path, mutate_ledger=mutate)
    with pytest.raises(module.FinanceMetricXlsxError, match="numeric"):
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")


@pytest.mark.parametrize("bad_value", ["NaN", "sNaN", "Infinity", "-Infinity"])
def test_parse_sources_rejects_non_finite_ledger_amount(tmp_path: Path, bad_value: str) -> None:
    module = _module()

    def mutate(cells: dict[str, str]) -> None:
        cells["D9"] = _number("D9", bad_value)

    ledger, daily = _write_source_pair(tmp_path, mutate_ledger=mutate)
    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    assert exc_info.value.code == "invalid_numeric"
    assert exc_info.value.sheet == "综本"
    assert exc_info.value.cell == "D9"


@pytest.mark.parametrize("bad_value", [None, "not-a-number"])
def test_parse_sources_rejects_missing_or_invalid_daily_amount(tmp_path: Path, bad_value: str | None) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        sheets["年"]["C5"] = _number("C5", bad_value) if bad_value is None else _inline("C5", bad_value)

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    with pytest.raises(module.FinanceMetricXlsxError, match="numeric"):
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")


def test_parse_sources_preserves_non_cnx_observations_and_currency_issues(tmp_path: Path) -> None:
    module = _module()

    def mutate_ledger(cells: dict[str, str]) -> None:
        cells["C9"] = _inline("C9", "CNY")

    def mutate_daily(sheets: dict[str, dict[str, str]]) -> None:
        sheets["年"]["A5"] = _inline("A5", "CNY")
        sheets["微贷"]["K13"] = _inline("K13", "CNY")

    ledger, daily = _write_source_pair(
        tmp_path,
        mutate_ledger=mutate_ledger,
        mutate_daily=mutate_daily,
    )
    parsed = module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    assert any(row.source == "main" and row.currency == "CNY" for row in parsed.ledger)
    assert any(row.source == "microloan" and row.currency == "CNY" for row in parsed.ledger)
    assert any(row.source == "main" and row.currency == "CNY" for row in parsed.averages)
    currency_issues = [issue for issue in parsed.issues if issue.code == "non_cnx_currency"]
    assert len(currency_issues) == 3
    assert all(issue.validation_id == "currency.cnx_only" for issue in currency_issues)
    assert all(issue.cell_refs for issue in currency_issues)


def test_parse_sources_rejects_scientific_account_code_lexeme(tmp_path: Path) -> None:
    module = _module()

    def mutate(cells: dict[str, str]) -> None:
        cells["A9"] = _number("A9", "1.0101E+10")

    ledger, daily = _write_source_pair(tmp_path, mutate_ledger=mutate)
    with pytest.raises(module.FinanceMetricXlsxError, match="scientific account code"):
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")


def test_parse_sources_preserves_duplicate_ledger_rows_and_issue(tmp_path: Path) -> None:
    module = _module()

    def mutate(cells: dict[str, str]) -> None:
        for column in "ABCDEFG":
            source = f"{column}9"
            cells[f"{column}10"] = cells[source].replace(source, f"{column}10")

    ledger, daily = _write_source_pair(tmp_path, mutate_ledger=mutate)
    parsed = module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    assert len([row for row in parsed.ledger if row.source == "main"]) == 2
    duplicate = next(issue for issue in parsed.issues if issue.code == "duplicate_ledger_observation")
    assert duplicate.rows == (9, 10)
    assert duplicate.validation_id == "ledger.duplicate_full_code"
    assert duplicate.cell_refs == ("A9", "A10")


def test_parse_sources_preserves_duplicate_daily_observation_and_issue(tmp_path: Path) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        for column in "ABC":
            source = f"{column}5"
            sheets["年"][f"{column}6"] = sheets["年"][source].replace(source, f"{column}6")

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    parsed = module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    duplicates = [
        row
        for row in parsed.averages
        if row.source == "main"
        and row.basis == "ytd_average"
        and row.level == "l1"
        and row.account_code == "101"
    ]
    assert [row.row for row in duplicates] == [5, 6]
    issue = next(item for item in parsed.issues if item.code == "duplicate_daily_observation")
    assert issue.rows == (5, 6)
    assert issue.cell_refs == ("B5", "B6")


def test_parse_sources_requires_all_six_period_banners(tmp_path: Path) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        sheets["微贷"].pop("E2")

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")
    assert exc_info.value.code == "missing_period"


def test_parse_sources_rejects_one_source_period_from_another_month(tmp_path: Path) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        sheets["微贷"]["E2"] = _inline("E2", "日期： 2026-05-01 至 2026-05-31")

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")
    assert exc_info.value.code == "source_period_mismatch"
    assert exc_info.value.cell == "E2"


def test_requested_month_rejects_source_periods_from_another_month(tmp_path: Path) -> None:
    module = _module()
    ledger, daily = _write_source_pair(tmp_path)

    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="202605")
    assert exc_info.value.code == "source_period_mismatch"


def test_invalid_requested_month_is_structural_error(tmp_path: Path) -> None:
    module = _module()
    ledger, daily = _write_source_pair(tmp_path)

    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="2026-06")
    assert exc_info.value.code == "invalid_requested_month"


@pytest.mark.parametrize("failure", ["missing_banner", "inconsistent_banner"])
def test_parse_sources_requires_four_matching_main_daily_period_banners(tmp_path: Path, failure: str) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        if failure == "missing_banner":
            sheets["年"].pop("E2")
        else:
            sheets["年"]["M2"] = _inline("M2", "日期： 2026-01-01 至 2026-05-31")

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")
    expected_code = "missing_period_banner" if failure == "missing_banner" else "period_banner_conflict"
    assert exc_info.value.code == expected_code


@pytest.mark.parametrize("failure", ["ytd_start", "month_start"])
def test_parse_sources_preserves_business_period_gaps_for_task4(tmp_path: Path, failure: str) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        if failure == "ytd_start":
            text = "日期： 2026-02-01 至 2026-06-30"
            for column in ("A", "E", "I", "M"):
                sheets["年"][f"{column}2"] = _inline(f"{column}2", text)
        else:
            text = "日期： 2026-06-02 至 2026-06-30"
            for column in ("A", "E", "I", "M"):
                sheets["月"][f"{column}2"] = _inline(f"{column}2", text)

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    parsed = module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    assert parsed.report_date == date(2026, 6, 30)
    assert len(parsed.periods) == 6


def test_parse_sources_rejects_period_not_ending_at_requested_month_end(tmp_path: Path) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        text = "日期： 2026-06-01 至 2026-06-29"
        for column in ("A", "E", "I", "M"):
            sheets["月"][f"{column}2"] = _inline(f"{column}2", text)

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")
    assert exc_info.value.code == "source_period_mismatch"


@pytest.mark.parametrize("failure", ["non_three_digit", "missing_currency"])
def test_parse_sources_rejects_invalid_last_microloan_ledger_block(tmp_path: Path, failure: str) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        if failure == "non_three_digit":
            sheets["微贷"]["I13"] = _number("I13", "12201")
        elif failure == "missing_currency":
            sheets["微贷"]["K13"] = _inline("K13", "")

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    with pytest.raises(module.FinanceMetricXlsxError):
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")


def test_parse_sources_rejects_microloan_content_after_first_empty_ledger_row(tmp_path: Path) -> None:
    module = _module()

    def mutate(sheets: dict[str, dict[str, str]]) -> None:
        microloan = list(sheets.values())[2]
        for column in "IJKLMNO":
            empty_ref = f"{column}14"
            microloan[empty_ref] = _inline(empty_ref, "")
            source_ref = f"{column}13"
            trailing_ref = f"{column}15"
            microloan[trailing_ref] = microloan[source_ref].replace(source_ref, trailing_ref)

    ledger, daily = _write_source_pair(tmp_path, mutate_daily=mutate)
    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    assert exc_info.value.code == "microloan_trailing_content"


def test_parse_sources_rejects_ambiguous_period_candidates(tmp_path: Path) -> None:
    module = _module()

    def mutate(cells: dict[str, str]) -> None:
        cells["A4"] = _inline(
            "A4",
            "浼氳鏈熼棿锛?2026-05-01--2026-05-31 甯佺锛?CNX",
        )

    ledger, daily = _write_source_pair(tmp_path, mutate_ledger=mutate)
    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    assert exc_info.value.code == "ambiguous_period"


def test_parse_sources_rejects_conflicting_periods_in_one_control_cell(tmp_path: Path) -> None:
    module = _module()

    def mutate(cells: dict[str, str]) -> None:
        cells["A5"] = _inline(
            "A5",
            "会计期间：2026-05-01--2026-05-31；"
            "更正期间：2026-06-01--2026-06-30 币种：CNX",
        )

    ledger, daily = _write_source_pair(tmp_path, mutate_ledger=mutate)
    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    assert exc_info.value.code == "ambiguous_period"
    assert exc_info.value.cell == "A5"


def test_default_xlsx_limits_are_strict() -> None:
    module = _module()
    limits = module.DEFAULT_XLSX_LIMITS

    assert limits.max_file_bytes == 25 * 1024 * 1024
    assert limits.max_entries == 256
    assert limits.max_total_uncompressed_bytes == 100 * 1024 * 1024
    assert limits.max_entry_uncompressed_bytes == 50 * 1024 * 1024
    assert limits.max_compression_ratio == 100
    assert limits.max_xml_bytes == 50 * 1024 * 1024
    assert limits.max_sheets == 16
    assert limits.max_rows_per_sheet == 100_000
    assert limits.max_columns == 64
    assert limits.max_cells == 2_000_000
    assert limits.max_shared_strings == 250_000
    assert limits.max_string_bytes == 32 * 1024


@pytest.mark.parametrize(
    ("limit_name", "limit_value"),
    [
        ("max_file_bytes", 1),
        ("max_entries", 1),
        ("max_total_uncompressed_bytes", 1),
        ("max_entry_uncompressed_bytes", 1),
        ("max_compression_ratio", 1),
        ("max_xml_bytes", 1),
        ("max_sheets", 0),
        ("max_rows_per_sheet", 0),
        ("max_columns", 1),
        ("max_cells", 1),
        ("max_shared_strings", 0),
        ("max_string_bytes", 1),
    ],
)
def test_read_xlsx_enforces_configurable_resource_limits(
    tmp_path: Path,
    limit_name: str,
    limit_value: int,
) -> None:
    module = _module()
    path = _write_xlsx(
        tmp_path / f"{limit_name}.xlsx",
        {"Only": {"A1": _shared("A1", 0), "B1": _number("B1", "1")}},
        shared_strings=("shared-value",),
    )

    with pytest.raises(module.FinanceMetricXlsxError, match="limit"):
        module.read_xlsx(path, limits=module.XlsxLimits(**{limit_name: limit_value}))


@pytest.mark.parametrize(
    "entry_name",
    ["../escape.xml", "/absolute.xml", "C:/absolute.xml", "xl\\backslash.xml"],
)
def test_read_xlsx_rejects_unsafe_zip_entry_names(tmp_path: Path, entry_name: str) -> None:
    module = _module()
    path = _write_xlsx(
        tmp_path / "unsafe-entry.xlsx",
        {"Only": {"A1": _number("A1", "1")}},
        extra_entries=((entry_name, b"x"),),
    )
    if "\\" in entry_name:
        normalized = entry_name.replace("\\", "/").encode()
        payload = path.read_bytes().replace(normalized, entry_name.encode())
        path.write_bytes(payload)

    with pytest.raises(module.FinanceMetricXlsxError, match="unsafe ZIP entry"):
        module.read_xlsx(path)


@pytest.mark.parametrize(
    "entry_name",
    ["xl/vbaProject.bin", "xl/externalLinks/externalLink1.xml", "xl/embeddings/oleObject1.bin", "xl/activeX/activeX1.xml"],
)
def test_read_xlsx_rejects_forbidden_active_content(tmp_path: Path, entry_name: str) -> None:
    module = _module()
    path = _write_xlsx(
        tmp_path / "active-content.xlsx",
        {"Only": {"A1": _number("A1", "1")}},
        extra_entries=((entry_name, b"x"),),
    )

    with pytest.raises(module.FinanceMetricXlsxError, match="forbidden XLSX content"):
        module.read_xlsx(path)


def test_read_xlsx_rejects_duplicate_entries(tmp_path: Path) -> None:
    module = _module()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        path = _write_xlsx(
            tmp_path / "duplicate.xlsx",
            {"Only": {"A1": _number("A1", "1")}},
            extra_entries=(("xl/workbook.xml", b"duplicate"),),
        )

    with pytest.raises(module.FinanceMetricXlsxError, match="duplicate ZIP entry"):
        module.read_xlsx(path)


@pytest.mark.parametrize(
    ("target", "target_mode"),
    [("../../escape.xml", None), ("https://example.test/book.xml", "External")],
)
def test_read_xlsx_rejects_unsafe_relationship_target(
    tmp_path: Path,
    target: str,
    target_mode: str | None,
) -> None:
    module = _module()
    path = _write_xlsx(
        tmp_path / "unsafe-relationship.xlsx",
        {"Only": {"A1": _number("A1", "1")}},
        relationship_target=target,
        target_mode=target_mode,
    )

    with pytest.raises(module.FinanceMetricXlsxError, match="relationship"):
        module.read_xlsx(path)


def test_read_xlsx_rejects_non_worksheet_sheet_relationship_type(tmp_path: Path) -> None:
    module = _module()
    path = _write_xlsx(
        tmp_path / "wrong-relationship-type.xlsx",
        {"Only": {"A1": _number("A1", "1")}},
        relationship_type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
    )

    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.read_xlsx(path)
    assert exc_info.value.code == "invalid_sheet_relationship"


def test_read_xlsx_rejects_negative_shared_string_index(tmp_path: Path) -> None:
    module = _module()
    path = _write_xlsx(
        tmp_path / "negative-shared-string.xlsx",
        {"Only": {"A1": _shared("A1", -1)}},
        shared_strings=("must-not-be-selected",),
    )

    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.read_xlsx(path)
    assert exc_info.value.code == "invalid_shared_string"


def test_read_xlsx_rejects_doctype_and_entity(tmp_path: Path) -> None:
    module = _module()
    path = _write_xlsx(
        tmp_path / "doctype.xlsx",
        {"Only": {"A1": _number("A1", "1")}},
        workbook_prefix=b'<!DOCTYPE workbook [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>',
    )

    with pytest.raises(module.FinanceMetricXlsxError, match="DOCTYPE|ENTITY"):
        module.read_xlsx(path)


@pytest.mark.parametrize(("encoding", "declaration"), [("utf-16", "UTF-16"), ("utf-32", "UTF-32")])
def test_read_xlsx_rejects_multibyte_internal_entity(
    tmp_path: Path,
    encoding: str,
    declaration: str,
) -> None:
    module = _module()
    workbook_text = (
        f'<?xml version="1.0" encoding="{declaration}"?>'
        '<!DOCTYPE workbook [<!ENTITY injected "Only">]>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="&injected;" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    path = _write_xlsx(
        tmp_path / f"entity-{encoding}.xlsx",
        {"Only": {"A1": _number("A1", "1")}},
        workbook_payload=workbook_text.encode(encoding),
    )

    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.read_xlsx(path)
    assert exc_info.value.code == "unsafe_xml"


@pytest.mark.parametrize(
    "encoding",
    ["utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"],
)
def test_read_xlsx_rejects_bomless_multibyte_entity_after_leading_whitespace(
    tmp_path: Path,
    encoding: str,
) -> None:
    module = _module()
    workbook_text = (
        " \t\r\n"
        '<!DOCTYPE workbook [<!ENTITY injected "Only">]>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="&injected;" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    path = _write_xlsx(
        tmp_path / f"bomless-entity-{encoding}.xlsx",
        {"Only": {"A1": _number("A1", "1")}},
        workbook_payload=workbook_text.encode(encoding),
    )

    with pytest.raises(module.FinanceMetricXlsxError) as exc_info:
        module.read_xlsx(path)

    assert exc_info.value.code == "unsafe_xml"


def test_read_xlsx_rejects_corrupt_archive(tmp_path: Path) -> None:
    module = _module()
    path = tmp_path / "corrupt.xlsx"
    path.write_bytes(b"not a zip archive")

    with pytest.raises(module.FinanceMetricXlsxError, match="corrupt"):
        module.read_xlsx(path)


def test_read_xlsx_rejects_encrypted_entry(tmp_path: Path) -> None:
    module = _module()
    path = _write_xlsx(tmp_path / "encrypted.xlsx", {"Only": {"A1": _number("A1", "1")}})
    payload = bytearray(path.read_bytes())
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        cursor = 0
        while (cursor := payload.find(signature, cursor)) >= 0:
            flags = struct.unpack_from("<H", payload, cursor + flag_offset)[0]
            struct.pack_into("<H", payload, cursor + flag_offset, flags | 1)
            cursor += 4
    path.write_bytes(payload)

    with pytest.raises(module.FinanceMetricXlsxError, match="encrypted"):
        module.read_xlsx(path)


def test_real_202606_sources_preserve_expected_ooxml_evidence() -> None:
    module = _module()
    ledger = SOURCE_DIR / "总账对账202606.xlsx"
    daily = SOURCE_DIR / "日均202606.xlsx"
    if not ledger.is_file() or not daily.is_file():
        pytest.skip("real 202606 source pair is unavailable")

    parsed = module.parse_finance_metric_sources(ledger, daily, requested_month="202606")

    main_ledger = [row for row in parsed.ledger if row.source == "main"]
    microloan_ledger = [row for row in parsed.ledger if row.source == "microloan"]
    assert len(main_ledger) == 1944
    assert main_ledger[0].opening == Decimal("393899032.07")
    assert main_ledger[0].ending == Decimal("354538784.38")
    assert parsed.microloan_ledger_header_rows == (6, 32)
    assert parsed.selected_microloan_ledger_header_row == 32
    assert len(microloan_ledger) == 17
    assert len(parsed.periods) == 6
    assert {period.end for period in parsed.periods} == {date(2026, 6, 30)}
    assert parsed.excluded_currencies
    assert parsed.report_month == "202606"
    assert parsed.report_date == date(2026, 6, 30)
    assert parsed.ledger_sha256 == hashlib.sha256(ledger.read_bytes()).hexdigest()
    assert parsed.daily_sha256 == hashlib.sha256(daily.read_bytes()).hexdigest()

    main_average_counts = Counter(
        (row.basis, row.level)
        for row in parsed.averages
        if row.source == "main"
    )
    assert main_average_counts == Counter(
        {
            ("ytd_average", "l1"): 105,
            ("ytd_average", "l2"): 331,
            ("ytd_average", "l3"): 412,
            ("ytd_average", "full"): 2112,
            ("month_average", "l1"): 105,
            ("month_average", "l2"): 331,
            ("month_average", "l3"): 412,
            ("month_average", "full"): 2112,
        }
    )
    microloan_averages = {
        (row.basis, row.account_code): row.balance
        for row in parsed.averages
        if row.source == "microloan"
    }
    assert microloan_averages[("ytd_average", "122")] == Decimal("10345562340.6")
    assert microloan_averages[("month_average", "122")] == Decimal("9933470976.84")
    assert next(row.ending for row in microloan_ledger if row.account_code == "122") == Decimal(
        "9999721766.72"
    )
