"""Report prose must use the supplied run's evidence, without accessing storage."""

from copy import deepcopy
import json

import pytest

from scripts.run_walk_forward_validation import (
    _rectification_notes,
    _report_gap_accounting,
    _report_header,
)
from tests.helpers import ROOT


@pytest.fixture
def historical_payload():
    return json.loads(
        (ROOT / "docs/strategy-reports/walk-forward-20260905.json").read_text(
            encoding="utf-8"
        )
    )


def test_report_header_keeps_the_payload_engine_version(historical_payload):
    text = "\n".join(_report_header(historical_payload, historical_payload["schedules"][0]))
    assert "引擎 `pbt_v2_path_mode`" in text
    assert "pbt_v3" not in text


def test_report_notes_do_not_invent_an_earlier_run(historical_payload):
    text = "\n".join(_rectification_notes(historical_payload))
    assert "5847" in text and "5833" in text and "5610" in text
    assert "5560" not in text and "4311" not in text
    assert "783" not in text and "768" not in text
    assert "逐字不变" not in text and "首版一致" not in text
    assert "PENDING" in text


def test_report_notes_use_new_counts_and_retain_conflicts(historical_payload):
    payload = deepcopy(historical_payload)
    payload["dedupe"].update(
        loaded_rows=20,
        deduped_rows=13,
        removed_rows=7,
        duplicate_keys=3,
        ema10_conflict_keys=2,
        removed_rows_by_kind={"synthetic_kind": 7},
    )
    payload["usable_row_count"] = 9
    text = "\n".join(_rectification_notes(payload))
    assert "20" in text and "13" in text and "7" in text
    assert "ema10_conflict_keys=2" in text
    assert "取值完全一致" not in text
    assert "stock_candidate 783" not in text


def test_zero_adjustment_gaps_do_not_claim_a_coverage_cliff(historical_payload):
    historical_payload["missing_price_path_rows"] = 0
    text = "\n".join(_report_gap_accounting(historical_payload))
    assert "覆盖悬崖" not in text
    assert "孤立补载日" not in text
    assert "4 倍键" not in text
    assert "去重不改任何计算" not in text
    assert "未观测到复权缺失" in text


def test_adjustment_gap_counts_are_disclosed_without_inventing_cause(historical_payload):
    historical_payload["missing_price_path_rows"] = 0
    historical_payload["disclosure"]["adjusted_return_missing_block"].update(
        rows=2, min_signal_date="2026-06-01", max_signal_date="2026-06-02"
    )
    historical_payload["disclosure"]["adjustment_factor_coverage"].update(
        rows_with_uncovered_target=1,
        uncovered_target_date_count=1,
        rows_after_dense_coverage_end=1,
    )
    text = "\n".join(_report_gap_accounting(historical_payload))
    assert "2 行有" in text
    assert "1 行的 20d 目标日" in text
    assert "覆盖悬崖" not in text
    assert "孤立补载日" not in text
