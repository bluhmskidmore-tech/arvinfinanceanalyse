"""模型就绪度新鲜度判定的月度容差回归。

月度产物（美林时钟系）按"内容月份不早于基准日上月即 current"判定；
日度产物保持精确相等口径不变。
"""

from __future__ import annotations

import pytest

from backend.app.services.macro_toolkit_service import (
    _is_monthly_cadence_artifact,
    _macro_monthly_output_freshness,
    _macro_output_health_status,
)

pytestmark = pytest.mark.unit


def _monthly_status(content_date: str | None, reference_date: str | None) -> str:
    return _macro_output_health_status(
        name="merrill_clock_latest.csv",
        content_date=content_date,
        content_date_min=content_date,
        content_date_max=content_date,
        content_date_invalid_count=0,
        has_content_date_column=True,
        modified_date="2026-08-12",
        reference_date=reference_date,
    )


def test_monthly_artifact_registry() -> None:
    assert _is_monthly_cadence_artifact("merrill_clock_latest.csv")
    assert _is_monthly_cadence_artifact("merrill_clock_history.csv")
    assert not _is_monthly_cadence_artifact("crisis_score_latest.csv")
    assert not _is_monthly_cadence_artifact("final_signal.csv")


def test_monthly_freshness_tolerance_boundaries() -> None:
    # 基准 2026-08-12：7 月（上月）与 8 月（当月）内容为 current。
    assert _macro_monthly_output_freshness("2026-07-01", "2026-08-12") == "current"
    assert _macro_monthly_output_freshness("2026-08-01", "2026-08-12") == "current"
    # 6 月内容早于上月：7 月数据该发布未入库，判 stale。
    assert _macro_monthly_output_freshness("2026-06-01", "2026-08-12") == "stale"
    # 未来月份判 future；跨年边界正确（2026-01 的上月是 2025-12）。
    assert _macro_monthly_output_freshness("2026-09-01", "2026-08-12") == "future"
    assert _macro_monthly_output_freshness("2025-12-01", "2026-01-15") == "current"
    assert _macro_monthly_output_freshness("2025-11-01", "2026-01-15") == "stale"
    # 退化输入。
    assert _macro_monthly_output_freshness(None, "2026-08-12") == "unknown"
    assert _macro_monthly_output_freshness("2026-07-01", None) == "present"
    assert _macro_monthly_output_freshness("not-a-date", "2026-08-12") == "unknown"


def test_monthly_artifact_routes_through_health_status() -> None:
    assert _monthly_status("2026-07-01", "2026-08-12") == "current"
    assert _monthly_status("2026-06-01", "2026-08-12") == "stale"


def test_daily_artifact_keeps_exact_match_semantics() -> None:
    # 日度产物（非月度清单内）仍要求内容日期与基准日精确相等。
    status = _macro_output_health_status(
        name="crisis_score_latest.csv",
        content_date="2026-08-11",
        content_date_min="2026-08-11",
        content_date_max="2026-08-11",
        content_date_invalid_count=0,
        has_content_date_column=True,
        modified_date="2026-08-12",
        reference_date="2026-08-12",
    )
    assert status == "stale"
    status_current = _macro_output_health_status(
        name="crisis_score_latest.csv",
        content_date="2026-08-12",
        content_date_min="2026-08-12",
        content_date_max="2026-08-12",
        content_date_invalid_count=0,
        has_content_date_column=True,
        modified_date="2026-08-12",
        reference_date="2026-08-12",
    )
    assert status_current == "current"
