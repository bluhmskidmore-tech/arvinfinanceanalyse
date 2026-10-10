"""Small, synthetic source workbooks for ingestion and parser regression tests.

All amounts, positions and counterparties below are invented. These fixtures
exercise source layout and classification rules; they are not business goldens.
"""

from __future__ import annotations

import io
import re
import struct
from pathlib import Path


def _xls_bytes(rows: list[list[str]]) -> bytes:
    """Encode a single BIFF8 worksheet without an Excel writer dependency."""
    def record(code: int, payload: bytes = b"") -> bytes:
        return struct.pack("<HH", code, len(payload)) + payload

    def bof(kind: int) -> bytes:
        return record(0x0809, struct.pack("<HHHHII", 0x0600, kind, 0x0DBB, 1996, 0x41, 6))

    strings = list(dict.fromkeys(cell for row in rows for cell in row))
    indices = {value: index for index, value in enumerate(strings)}
    sst = struct.pack("<II", sum(map(len, rows)), len(strings)) + b"".join(
        struct.pack("<HB", len(value), 1) + value.encode("utf-16le") for value in strings
    )
    globals_before_sheet = (
        bof(0x0005)
        + record(0x0042, struct.pack("<H", 1200))
        + record(0x0022, struct.pack("<H", 0))
        + record(0x00E0, bytes(20))
        + record(0x00FC, sst)
    )
    sheet_name = b"Fixture"
    boundsheet_size = 4 + 8 + len(sheet_name)
    sheet_offset = len(globals_before_sheet) + boundsheet_size + 4
    boundsheet = record(
        0x0085, struct.pack("<IBBBB", sheet_offset, 0, 0, len(sheet_name), 0) + sheet_name
    )
    cells = b"".join(
        record(0x00FD, struct.pack("<HHHI", row_index, column, 0, indices[value]))
        for row_index, row in enumerate(rows)
        for column, value in enumerate(row)
    )
    dimensions = record(0x0200, struct.pack("<IIHHH", 0, len(rows), 0, max(map(len, rows)), 0))
    return globals_before_sheet + boundsheet + record(0x000A) + bof(0x0010) + dimensions + cells + record(0x000A)


def business_input_bytes(source_file: str, *, sheet_date: str | None = None) -> bytes:
    """Return an explicitly synthetic workbook in the named source layout."""
    if source_file.startswith("ZQTZSHOW"):
        date_digits = re.sub(r"\D", "", source_file)
        report_date = sheet_date or f"{date_digits[:4]}-{date_digits[4:6]}-{date_digits[6:8]}"
        headers = [
            "债券代号", "债券名称", "日期", "业务种类", "业务种类1", "账户类别",
            "资产分类", "投资组合", "成本中心", "币种", "面值", "公允价值",
            "摊余成本", "应计利息", "应收/应付利息", "到期日", "利率", "到期收益率",
        ]
        # Three primary groups and the SA/J0 prefix rules are deliberate. The
        # same bond in AC and OCI proves that position keys are not full grains.
        positions = [
            ("SYNTH-BOND-1", "国债", "债券", "AC"),
            ("SYNTH-BOND-2", "金融债", "债券", "AC"),
            ("SA-SYNTH-1", "其他债券", "基金", "AC"),
            ("J0-SYNTH-1", "其他债券", "资管计划", "AC"),
            # Preserve the legacy source spelling exercised by the workbook contract.
            ("SYNTH-ISSUE-1", "金融债", "发行类债劵", "AC"),
            ("SYNTH-BOND-1", "国债", "债券", "OCI"),
        ]
        rows = [["Synthetic ZQTZ"], headers]
        for code, business, asset_class, account in positions:
            rows.append([
                code, "合成测试债券", report_date, business, business, account, asset_class,
                "合成组合", "TEST-CC", "人民币", "1000", "1010", "1000", "10", "0",
                "2030-12-31", "3", "3",
            ])
        return _xls_bytes(rows)

    if source_file.startswith("TYWLSHOW"):
        headers = [
            "流水号", "产品类型", "对手方名称", "投资组合", "账户类型", "特殊账户类型",
            "核心客户类型", "会计类型_银保监会", "会计类型_人行", "托管账户名称",
            "币种", "金额", "应计利息", "利率", "到期日",
        ]
        products = ["存放同业", "拆放同业", "买入返售证券", "同业存放", "同业拆入", "卖出回购证券"]
        rows = [["Synthetic TYW"], headers]
        for index, product in enumerate(products, start=1):
            rows.append([
                f"SYNTH-TYW-{index}", product, "合成测试机构", "合成组合", "普通", "", "银行",
                "银行类金融机构", "银行类金融机构", "", "人民币", "1000", "10", "2", "2030-12-31",
            ])
        return _xls_bytes(rows)

    if source_file.startswith("FI"):
        return _xls_bytes([
            ["债券代码", "债券名称", "投资组合", "成本中心", "投资类型", "债券分类", "币种", "利息514", "T损益516", "投资收益517"],
            ["SYNTH-FI-CNY", "合成人民币债券", "合成组合", "TEST-CC", "H", "国债", "人民币", "10", "-2", "3"],
            ["SYNTH-FI-USD", "合成美元债券", "合成组合", "TEST-CC", "T", "金融债", "美元", "20", "-4", "6"],
        ])

    if source_file.startswith("非标"):
        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Synthetic non-standard PnL"])
        worksheet.append(["科目号", "资产代码", "借贷标识", "产品类型", "金额", "账务日期", "币种"])
        worksheet.append(["5140101", "SYNTH-NONSTD-1", "贷", "资管计划", "10", "2025-12-31", "人民币"])
        worksheet.append(["5140101", "SYNTH-NONSTD-2", "借", "资管计划", "2", "2025-12-31", "人民币"])
        output = io.BytesIO()
        workbook.save(output)
        workbook.close()
        return output.getvalue()

    raise ValueError(f"No synthetic business fixture layout for {source_file!r}")


def write_business_input(path: Path, *, sheet_date: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(business_input_bytes(path.name, sheet_date=sheet_date))
    return path
