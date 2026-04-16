"""Regression: `docs/data_contracts.md` §4.8 must remain a readable normative contract (see acceptance_tests.md 3.6B)."""

from __future__ import annotations

import re

from tests.helpers import ROOT


def _section_48_fx_daily_mid(text: str) -> str:
    match = re.search(
        r"### 4\.8 fx_daily_mid\s+(.*?)\n### 4\.9 ",
        text,
        flags=re.DOTALL,
    )
    assert match is not None, "docs/data_contracts.md must contain section 4.8 before 4.9"
    return match.group(1)


def test_fx_daily_mid_contract_section_is_complete_and_not_corrupted():
    path = ROOT / "docs" / "data_contracts.md"
    text = path.read_text(encoding="utf-8")
    section = _section_48_fx_daily_mid(text)

    assert "???" not in section, "section 4.8 must not contain corrupted placeholder markers"
    assert "fx_mid_materialize.py" in section
    assert "canonical grain" in section
    assert "(trade_date, base_currency, quote_currency)" in section
    for field in (
        "`trade_date`",
        "`base_currency`",
        "`quote_currency`",
        "`mid_rate`",
        "`is_carry_forward`",
        "`vendor_series_code`",
        "`observed_trade_date`",
    ):
        assert field in section, f"missing expected field mention: {field}"

    assert "BALANCE_ANALYSIS_FX_SOURCE_RUNBOOK.md" in section
    assert "fail closed" in section

