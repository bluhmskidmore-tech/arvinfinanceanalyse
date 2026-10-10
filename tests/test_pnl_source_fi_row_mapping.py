"""Lock FI 源表列名 → 正式 PnL 字段映射，尤其是 T损益516 的符号翻转。

`_parse_fi_rows` 是把源文件「T损益516」翻转为 `fair_value_change_516` 的唯一环节。
既有 refresh/API 测试会 monkeypatch 掉整个解析函数，foundation 套件也不断言
原始单元格到字段值的映射，因此这里直接调用 `_parse_fi_rows`。

输入是真实 FI 列名的 .xls（xlrd 2.x 只读 BIFF，不能用 openpyxl 写 xlsx）。
"""

from __future__ import annotations

import struct
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.core_finance.pnl import build_formal_pnl_fi_fact_rows, normalize_fi_pnl_records
from backend.app.services.pnl_source_service import PnlSourceSnapshot, _parse_fi_rows

# 与 data_input/pnl/FI损益*.xls 表头一致（xlrd 读到的 strip 后列名）。
FI_HEADERS = [
    "债券代码",
    "债券名称",
    "投资组合",
    "成本中心",
    "投资类型",
    "债券分类",
    "币种",
    "利息514",
    "T损益516",
    "投资收益517",
]


def _biff_record(record_id: int, data: bytes) -> bytes:
    return struct.pack("<HH", record_id, len(data)) + data


def _write_fi_xls(path: Path, headers: list[str], data_rows: list[list[object]]) -> None:
    """Write a BIFF2 .xls that xlrd 2.x can open with GBK 中文表头.

    BIFF2 LABEL/NUMBER 在 3 字节 XF 之后才是单元格载荷；仓库未引入 xlwt，
    因此测试内联这个最小写出器，而不是改生产依赖。
    """
    parts = [
        _biff_record(0x0009, struct.pack("<HH", 0x0004, 0x0010)),
        _biff_record(0x0042, struct.pack("<H", 936)),
    ]
    xf = b"\x00\x00\x00"
    for row_index, row in enumerate([headers, *data_rows]):
        for column_index, value in enumerate(row):
            if value is None or value == "":
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                payload = struct.pack("<HH", row_index, column_index) + xf + struct.pack("<d", float(value))
                parts.append(_biff_record(0x0003, payload))
                continue
            encoded = str(value).encode("gbk")
            payload = struct.pack("<HH", row_index, column_index) + xf + bytes([len(encoded)]) + encoded
            parts.append(_biff_record(0x0004, payload))
    parts.append(_biff_record(0x000A, b""))
    path.write_bytes(b"".join(parts))


def _parse_fi_table(
    tmp_path: Path,
    data_rows: list[dict[str, object]],
    *,
    headers: list[str] = FI_HEADERS,
    report_date: str = "2025-12-31",
) -> list[dict[str, object]]:
    path = tmp_path / ("FI损益" + report_date[:7].replace("-", "") + ".xls")
    table_rows = [[row.get(header, "") for header in headers] for row in data_rows]
    _write_fi_xls(path, headers, table_rows)
    snapshot = PnlSourceSnapshot(
        source_family="pnl",
        report_date=report_date,
        path=path,
        source_version="sv_test_fi_row_mapping",
        ingest_batch_id="ib_test_fi_row_mapping",
        created_at="2026-01-01T00:00:00+00:00",
    )
    return _parse_fi_rows(snapshot)


@pytest.mark.parametrize("report_date", ["2000-01-31", "2024-12-31", "2026-07-31", "2100-12-31"])
@pytest.mark.parametrize("source_amount", [-106, 106])
@pytest.mark.parametrize("currency,rate", [("CNY", "1"), ("USD", "7")])
def test_fi_source_516_517_formal_rules_apply_to_all_dates(
    tmp_path: Path, report_date: str, source_amount: int, currency: str, rate: str
) -> None:
    parsed = _parse_fi_table(
        tmp_path,
        [
            {
                "债券代码": "GOV-" + invest_type,
                "债券名称": "国债",
                "投资组合": "FI Desk",
                "成本中心": "CC100",
                "投资类型": invest_type,
                "债券分类": "国债",
                "币种": currency,
                "利息514": 0,
                "T损益516": source_amount,
                "投资收益517": source_amount,
            }
            for invest_type in ("H", "A", "T")
        ],
        report_date=report_date,
    )
    formal = build_formal_pnl_fi_fact_rows(normalize_fi_pnl_records(
        parsed, fx_rates_by_currency={"USD": (Decimal(rate), "fx-test")}
    ))
    for row in formal:
        expected_516 = -Decimal(source_amount) * Decimal(rate) if row.invest_type_std == "T" else Decimal(0)
        expected_517 = -Decimal(source_amount) / Decimal("1.06") * Decimal(rate)
        assert row.report_date.isoformat() == report_date
        assert row.fair_value_change_516 == expected_516
        assert row.capital_gain_517 == expected_517
        assert row.total_pnl == expected_516 + expected_517


def test_parse_fi_rows_flips_t_pnl_516_and_passes_514_517_through(tmp_path: Path) -> None:
    rows = _parse_fi_table(
        tmp_path,
        [
            {
                "债券代码": "240001.IB",
                "债券名称": "正数516",
                "投资组合": "FIOA",
                "成本中心": "5010",
                "投资类型": "交易性金融资产",
                "债券分类": "国债",
                "币种": "CNY",
                "利息514": 12.5,
                "T损益516": 100.0,
                "投资收益517": 1.75,
            },
            {
                "债券代码": "240002.IB",
                "债券名称": "负数516",
                "投资组合": "FIOA",
                "成本中心": "5010",
                "投资类型": "交易性金融资产",
                "债券分类": "国债",
                "币种": "CNY",
                "利息514": -8.25,
                "T损益516": -50.0,
                "投资收益517": -2.5,
            },
            {
                "债券代码": "240003.IB",
                "债券名称": "零值516",
                "投资组合": "FIOA",
                "成本中心": "5010",
                "投资类型": "交易性金融资产",
                "债券分类": "国债",
                "币种": "CNY",
                "利息514": 0.0,
                "T损益516": 0.0,
                "投资收益517": 0.0,
            },
        ],
    )

    by_code = {row["instrument_code"]: row for row in rows}
    assert by_code["240001.IB"]["interest_income_514"] == Decimal("12.5")
    assert by_code["240001.IB"]["fair_value_change_516"] == Decimal("-100")
    assert by_code["240001.IB"]["capital_gain_517"] == Decimal("1.75")

    assert by_code["240002.IB"]["interest_income_514"] == Decimal("-8.25")
    assert by_code["240002.IB"]["fair_value_change_516"] == Decimal("50")
    assert by_code["240002.IB"]["capital_gain_517"] == Decimal("-2.5")

    assert by_code["240003.IB"]["interest_income_514"] == Decimal("0")
    assert by_code["240003.IB"]["fair_value_change_516"] == Decimal("0")
    assert by_code["240003.IB"]["capital_gain_517"] == Decimal("0")


def test_parse_fi_rows_maps_empty_amount_cells_to_zero(tmp_path: Path) -> None:
    [row] = _parse_fi_table(
        tmp_path,
        [
            {
                "债券代码": "240010.IB",
                "利息514": "",
                "T损益516": "",
                "投资收益517": "",
            }
        ],
    )

    assert row["interest_income_514"] == Decimal("0")
    assert row["fair_value_change_516"] == Decimal("0")
    assert row["capital_gain_517"] == Decimal("0")


def test_parse_fi_rows_maps_missing_amount_columns_to_zero(tmp_path: Path) -> None:
    [row] = _parse_fi_table(
        tmp_path,
        [{"债券代码": "240011.IB"}],
        headers=["债券代码"],
    )

    assert row["interest_income_514"] == Decimal("0")
    assert row["fair_value_change_516"] == Decimal("0")
    assert row["capital_gain_517"] == Decimal("0")


@pytest.mark.parametrize("column", ["利息514", "T损益516", "投资收益517"])
def test_parse_fi_rows_rejects_thousands_separator_in_amount_cells(
    tmp_path: Path, column: str
) -> None:
    with pytest.raises(ValueError, match="1,234.56"):
        _parse_fi_table(
            tmp_path,
            [
                {
                    "债券代码": "240012.IB",
                    "利息514": 1.0,
                    "T损益516": 2.0,
                    "投资收益517": 3.0,
                    column: "1,234.56",
                }
            ],
        )


def test_parse_fi_rows_skips_rows_without_instrument_code(tmp_path: Path) -> None:
    rows = _parse_fi_table(
        tmp_path,
        [
            {
                "债券代码": "",
                "利息514": 9.0,
                "T损益516": 8.0,
                "投资收益517": 7.0,
            },
            {
                "债券代码": "240013.IB",
                "利息514": 4.0,
                "T损益516": 5.0,
                "投资收益517": 6.0,
            },
        ],
    )

    assert [row["instrument_code"] for row in rows] == ["240013.IB"]
    assert rows[0]["interest_income_514"] == Decimal("4")
    assert rows[0]["fair_value_change_516"] == Decimal("-5")
    assert rows[0]["capital_gain_517"] == Decimal("6")
