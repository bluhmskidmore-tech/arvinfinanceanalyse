from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.app.core_finance.finance_metric_xlsx import FinanceMetricXlsxError
from tests.synthetic_ledger_pnl_fixture import (
    SYNTHETIC_REPORT_MONTH,
    write_synthetic_ledger_workbook,
)


@pytest.fixture
def synthetic_ledger_path(tmp_path: Path) -> Path:
    path = tmp_path / f"总账对账{SYNTHETIC_REPORT_MONTH}.xlsx"
    write_synthetic_ledger_workbook(path, SYNTHETIC_REPORT_MONTH)
    return path


def test_parse_ledger_only_source_preserves_month_end_and_hash_evidence(
    synthetic_ledger_path: Path,
) -> None:
    from backend.app.core_finance.finance_metric_xlsx import (
        parse_finance_metric_ledger_only_source,
    )

    source = parse_finance_metric_ledger_only_source(
        synthetic_ledger_path,
        requested_month=SYNTHETIC_REPORT_MONTH,
    )

    assert source.report_month == SYNTHETIC_REPORT_MONTH
    assert source.report_date == date(2025, 3, 31)
    assert len(source.ledger_sha256) == 64
    assert source.ledger
    assert {row.source for row in source.ledger} == {"main"}
    assert source.period.end == source.report_date


def test_parse_ledger_only_source_rejects_requested_month_mismatch(
    synthetic_ledger_path: Path,
) -> None:
    from backend.app.core_finance.finance_metric_xlsx import (
        parse_finance_metric_ledger_only_source,
    )

    with pytest.raises(FinanceMetricXlsxError) as exc_info:
        parse_finance_metric_ledger_only_source(
            synthetic_ledger_path,
            requested_month="202502",
        )

    assert exc_info.value.code == "source_period_mismatch"
