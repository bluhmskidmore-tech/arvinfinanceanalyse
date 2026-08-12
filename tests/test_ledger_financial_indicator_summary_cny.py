"""CNY 口径经营指标情况表专项测试。

与 tests/test_ledger_financial_indicator_summary.py 解耦维护（该文件由并行变更
持有），本文件只覆盖两件事：

1. 真实总账数据上 CNY 口径两项恒等校验（net_profit_identity / balance_identity）
   的结果冻结：2026-08 验证 202603 请求覆盖的 7 个月份 gap 均为 0.00 元。
   注意：CNY 只有恒等自洽性证据；财务指标工作簿仅提供 CNX 基准，CNY 不存在
   可核对的工作簿数值。
2. service 按 currency 参数过滤 canonical 事实行（CNY 请求只聚合 CNY 行）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.services import ledger_pnl_service
from tests.helpers import ROOT


def _real_ledger_source_dir() -> Path | None:
    ledger_token = "\u603b\u8d26\u5bf9\u8d26"
    average_token = "\u65e5\u5747"
    data_input = ROOT / "data_input"
    if not data_input.exists():
        return None
    for path in data_input.iterdir():
        if path.is_dir() and ledger_token in path.name and average_token in path.name:
            return path
    return None


def test_real_202603_cny_identity_checks_all_pass():
    """CNY 202603：覆盖月份的两项恒等校验全部通过，gap 精确为 0 元。"""
    source_dir = _real_ledger_source_dir()
    if source_dir is None:
        pytest.skip("real ledger source directory is unavailable")

    envelope = ledger_pnl_service.ledger_pnl_financial_indicator_summary_envelope(
        source_dir=str(source_dir),
        report_month="202603",
        currency="CNY",
    )
    payload = envelope["result"]
    assert payload["data_status"] == "ready"
    assert payload["currency_basis"] == "CNY"

    checks = payload["quality_checks"]
    assert {check["month"] for check in checks} == {
        "202501", "202502", "202503", "202512", "202601", "202602", "202603",
    }
    assert {check["check_id"] for check in checks} == {
        "net_profit_identity",
        "balance_identity",
    }
    assert len(checks) == 14
    for check in checks:
        context = (check["check_id"], check["month"])
        assert check["passed"] is True, context
        assert Decimal(check["gap_yuan"]) == 0, context


@dataclass
class _FakePair:
    month_key: str
    report_date: date
    ledger_path: Path
    avg_path: Path
    source_version: str


class _FakeFact:
    def __init__(self, account_code: str, currency: str, ending_balance: str):
        self.account_code = account_code
        self.currency = currency
        self.ending_balance = Decimal(ending_balance)


def _mixed_currency_facts() -> list[_FakeFact]:
    """CNX 与 CNY 各自借贷闭合，但收入余额量级不同（-900 vs -300）。"""
    return [
        _FakeFact("50101001", "CNX", "-900"),
        _FakeFact("12201001", "CNX", "900"),
        _FakeFact("50101001", "CNY", "-300"),
        _FakeFact("12201001", "CNY", "300"),
    ]


def test_summary_envelope_filters_facts_by_currency(monkeypatch):
    fake_pairs = [
        _FakePair(
            "202601",
            date(2026, 1, 31),
            Path("总账对账202601.xlsx"),
            Path("日均202601.xlsx"),
            "sv_fake",
        ),
    ]
    facts = _mixed_currency_facts()
    monkeypatch.setattr(
        ledger_pnl_service,
        "discover_source_pairs",
        lambda _dir: fake_pairs,
    )
    # 按 pair 加载 facts 的入口当前是 _cached_ledger_only_facts；若被重命名，
    # 这里会以 AttributeError 显式失败，需同步更新 monkeypatch 目标。
    monkeypatch.setattr(
        ledger_pnl_service,
        "_cached_ledger_only_facts",
        lambda _pair: facts,
    )

    def january_revenue(currency: str) -> str | None:
        envelope = ledger_pnl_service.ledger_pnl_financial_indicator_summary_envelope(
            source_dir="unused",
            report_month="202601",
            currency=currency,
        )
        payload = envelope["result"]
        assert payload["data_status"] == "ready"
        assert payload["currency_basis"] == currency
        meta = envelope["result_meta"]
        assert meta["filters_applied"]["currency_basis"] == currency
        # 每个币种子集各自借贷闭合 → 两项恒等校验均应通过。
        assert all(check["passed"] for check in payload["quality_checks"])
        rows_by_id = {
            row["row_id"]: row
            for section in payload["sections"]
            for row in section["rows"]
        }
        return rows_by_id["fin.mother_revenue"]["values"][0]["current"]

    # CNY 请求只聚合 CNY 行：营业收入 300 元；CNX 请求只聚合 CNX 行：900 元。
    assert january_revenue("CNY") == "0.0000030000"
    assert january_revenue("CNX") == "0.0000090000"
