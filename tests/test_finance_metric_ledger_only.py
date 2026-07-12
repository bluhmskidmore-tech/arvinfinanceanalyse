from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.app.core_finance.finance_metric_xlsx import FinanceMetricXlsxError


SOURCE_DIR = Path(__file__).resolve().parents[1] / "data_input" / "pnl_总账对账-日均"


def test_parse_ledger_only_source_preserves_month_end_and_hash_evidence() -> None:
    from backend.app.core_finance.finance_metric_xlsx import (
        parse_finance_metric_ledger_only_source,
    )

    source = parse_finance_metric_ledger_only_source(
        SOURCE_DIR / "总账对账202606.xlsx",
        requested_month="202606",
    )

    assert source.report_month == "202606"
    assert source.report_date == date(2026, 6, 30)
    assert len(source.ledger_sha256) == 64
    assert source.ledger
    assert {row.source for row in source.ledger} == {"main"}
    assert source.period.end == source.report_date


def test_parse_ledger_only_source_rejects_requested_month_mismatch() -> None:
    from backend.app.core_finance.finance_metric_xlsx import (
        parse_finance_metric_ledger_only_source,
    )

    with pytest.raises(FinanceMetricXlsxError) as exc_info:
        parse_finance_metric_ledger_only_source(
            SOURCE_DIR / "总账对账202606.xlsx",
            requested_month="202605",
        )

    assert exc_info.value.code == "source_period_mismatch"
