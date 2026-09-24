"""M10 宏观领先指标（compute_leading_indicator）单测。

覆盖：
- 严格 6/6 共同可计算月对齐（最新共同月）
- 主窗 12 个月 / shadow 24 个月
- 合法 0 按公式评分；无共同月时禁止部分重归一主结论
- observation_only / formal_use_allowed 边界
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

import pytest
from backend.app.core_finance.macro.leading_indicator import compute_leading_indicator

pytestmark = pytest.mark.unit

REPORT_DATE = date(2026, 7, 20)


def _month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def _full_month_row(
    year: int,
    month: int,
    *,
    pmi: float = 50.0,
    m2_yoy: float = 8.0,
    social_financing_yoy: float = 8.0,
    term_spread_10y_1y: float = 60.0,
    credit_spread_aaa_3y: float = 40.0,
    brent_oil: float = 80.0,
    trade_day: int | None = None,
) -> dict[str, object]:
    """一行同时承载六腿真实观测，source_date 均落在该月。"""
    end = _month_end(year, month)
    trade = date(year, month, trade_day) if trade_day is not None else end
    source = date(year, month, 1)
    return {
        "trade_date": trade,
        "pmi": pmi,
        "pmi_source_date": source,
        "m2_yoy": m2_yoy,
        "m2_yoy_source_date": source,
        "social_financing_yoy": social_financing_yoy,
        "social_financing_yoy_source_date": source,
        "term_spread_10y_1y": term_spread_10y_1y,
        "term_spread_10y_1y_source_date": trade,
        "credit_spread_aaa_3y": credit_spread_aaa_3y,
        "credit_spread_aaa_3y_source_date": trade,
        "brent_oil": brent_oil,
        "brent_oil_source_date": trade,
    }


def _history_rows(
    as_of: tuple[int, int],
    *,
    months: int = 24,
    m2_base: float = 8.0,
    sf_base: float = 8.0,
    oil_base: float = 80.0,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for delta in range(0, months + 1):
        year, month = _shift_month(as_of[0], as_of[1], -delta)
        rows.append(
            _full_month_row(
                year,
                month,
                pmi=50.0 + (delta % 3),
                m2_yoy=m2_base + (0.1 if delta else 4.0),
                social_financing_yoy=sf_base + (0.1 if delta else 2.0),
                brent_oil=oil_base + (1.0 if delta else 4.0),
            )
        )
    return rows


class TestCommonMonthAlignment:
    def test_july_report_selects_june_common_month_and_excludes_july_market(self) -> None:
        rows = _history_rows((2026, 6), months=14)
        # July market-only legs (no July PMI/M2/SF) — must not enter June score.
        rows.insert(
            0,
            {
                "trade_date": date(2026, 7, 15),
                "pmi": 51.0,
                "pmi_source_date": date(2026, 6, 1),  # ffill from June
                "m2_yoy": 12.0,
                "m2_yoy_source_date": date(2026, 6, 1),
                "social_financing_yoy": 10.0,
                "social_financing_yoy_source_date": date(2026, 6, 1),
                "term_spread_10y_1y": 90.0,
                "term_spread_10y_1y_source_date": date(2026, 7, 15),
                "credit_spread_aaa_3y": 20.0,
                "credit_spread_aaa_3y_source_date": date(2026, 7, 15),
                "brent_oil": 95.0,
                "brent_oil_source_date": date(2026, 7, 15),
            },
        )
        # Ensure June itself has authentic six legs (already from history helper).
        result = compute_leading_indicator(rows, REPORT_DATE)

        assert result["as_of_month"] == "2026-06"
        assert result["alignment_policy"] == "latest_common_computable_month"
        assert result["alignment_lag_months"] == 1
        assert result["available_component_count"] == 6
        assert result["component_count"] == 6
        assert result["lei_index"] is not None
        assert result["observation_only"] is True
        assert result["formal_use_allowed"] is False

        used = {e["component"]: e for e in result["component_evidence"] if e["used"]}
        assert set(used) == {
            "pmi",
            "m2_yoy",
            "social_financing_yoy",
            "term_spread",
            "credit_spread",
            "commodity",
        }
        assert all(e["source_month"] == "2026-06" for e in used.values())
        # June term/credit/oil — not July 90/20/95
        assert Decimal(str(used["term_spread"]["value"])) == Decimal("60")
        assert Decimal(str(used["credit_spread"]["value"])) == Decimal("40")
        assert Decimal(str(used["commodity"]["value"])) == Decimal("84")

        latest = {e["component"]: e for e in result["latest_available_component_evidence"]}
        assert latest["term_spread"]["source_month"] == "2026-07"
        assert Decimal(str(latest["term_spread"]["value"])) == Decimal("90")
        assert latest["credit_spread"]["source_month"] == "2026-07"
        assert latest["commodity"]["source_month"] == "2026-07"

        assert "LEI_AS_OF_MONTH_LAGGED" in result["warnings"]
        assert "LEI_NEWER_COMPONENT_DATA_EXCLUDED" in result["warnings"]
        assert "LEI_UNIT_CONTRACT_UNFROZEN" in result["warnings"]
        assert "PIT_METADATA_UNAVAILABLE" in result["warnings"]
        assert "LEI_LOOKBACK_UNGOVERNED" not in result["warnings"]
        assert "LEI_NO_COMMON_COMPUTABLE_MONTH" not in result["warnings"]

    def test_daily_legs_use_last_in_month_observation(self) -> None:
        rows = [
            _full_month_row(2026, 6, term_spread_10y_1y=55.0, credit_spread_aaa_3y=45.0, trade_day=10),
            _full_month_row(2026, 6, term_spread_10y_1y=70.0, credit_spread_aaa_3y=30.0, trade_day=28),
            _full_month_row(2026, 5),
        ]
        # Duplicate monthly macro on both June rows with same source_date.
        result = compute_leading_indicator(rows, date(2026, 6, 30))
        assert result["as_of_month"] == "2026-06"
        used = {e["component"]: e for e in result["component_evidence"] if e["used"]}
        assert Decimal(str(used["term_spread"]["value"])) == Decimal("70")
        assert Decimal(str(used["credit_spread"]["value"])) == Decimal("30")
        assert used["term_spread"]["source_date"] == "2026-06-28"

    def test_ffill_cross_month_is_not_a_real_observation(self) -> None:
        rows = [
            {
                "trade_date": date(2026, 7, 31),
                "pmi": 51.0,
                "pmi_source_date": date(2026, 6, 1),
                "m2_yoy": 12.0,
                "m2_yoy_source_date": date(2026, 6, 1),
                "social_financing_yoy": 10.0,
                "social_financing_yoy_source_date": date(2026, 6, 1),
                "term_spread_10y_1y": 60.0,
                "term_spread_10y_1y_source_date": date(2026, 6, 30),
                "credit_spread_aaa_3y": 40.0,
                "credit_spread_aaa_3y_source_date": date(2026, 6, 30),
                "brent_oil": 84.0,
                "brent_oil_source_date": date(2026, 6, 30),
            },
            _full_month_row(2026, 6, pmi=51.0, m2_yoy=12.0, social_financing_yoy=10.0, brent_oil=84.0),
            _full_month_row(2026, 5),
        ]
        result = compute_leading_indicator(rows, date(2026, 7, 31))
        assert result["as_of_month"] == "2026-06"
        # July row does not create a July PMI/M2/SF observation.
        latest_months = {
            e["component"]: e["source_month"] for e in result["latest_available_component_evidence"]
        }
        assert latest_months["pmi"] == "2026-06"
        assert latest_months["m2_yoy"] == "2026-06"

    def test_no_common_month_returns_unavailable_without_partial_lei(self) -> None:
        rows = [
            {
                "trade_date": date(2026, 6, 30),
                "pmi": 51.0,
                "pmi_source_date": date(2026, 6, 1),
                "m2_yoy": 8.0,
                "m2_yoy_source_date": date(2026, 6, 1),
                "social_financing_yoy": 9.0,
                "social_financing_yoy_source_date": date(2026, 6, 1),
                "term_spread_10y_1y": 60.0,
                "term_spread_10y_1y_source_date": date(2026, 6, 30),
                "credit_spread_aaa_3y": None,
                "credit_spread_aaa_3y_source_date": None,
                "brent_oil": 80.0,
                "brent_oil_source_date": date(2026, 6, 30),
            }
        ]
        result = compute_leading_indicator(rows, REPORT_DATE)
        assert result["data_status"] == "unavailable"
        assert result["lei_index"] is None
        assert result["economic_state"] == "数据不足"
        assert result["trend"] == "数据不足"
        assert result["as_of_month"] is None
        assert result["alignment_policy"] == "latest_common_computable_month"
        assert "LEI_NO_COMMON_COMPUTABLE_MONTH" in result["warnings"]
        assert result["observation_only"] is True
        assert result["formal_use_allowed"] is False
        # 禁止部分重归一主结论
        assert result["pmi_score"] is None
        assert result["available_component_count"] == 0


class TestLookbackWindows:
    def test_primary_history_is_12_complete_months_before_as_of(self) -> None:
        rows = _history_rows((2026, 6), months=30, m2_base=8.0, oil_base=80.0)
        # Inflate month -13 so that unbounded history would change the mean, but
        # the 12-month primary window must ignore it.
        old_year, old_month = _shift_month(2026, 6, -13)
        for row in rows:
            if row["trade_date"].year == old_year and row["trade_date"].month == old_month:
                row["m2_yoy"] = 100.0
                row["brent_oil"] = 200.0
                break

        result = compute_leading_indicator(rows, REPORT_DATE)
        assert result["as_of_month"] == "2026-06"
        assert result["lookback_months"] == 12
        assert result["history_window"]["start_month"] == "2025-06"
        assert result["history_window"]["end_month"] == "2026-05"
        assert result["history_samples"]["m2_yoy"]["total"] == 12
        assert result["history_samples"]["m2_yoy"]["used"] == 12
        assert result["history_samples"]["commodity"]["total"] == 12

        # Primary current m2 = 12 (from helper: as_of gets +4.0), history months ≈ 8.1
        # Score must match 12-month mean, not the poisoned -13 month.
        assert Decimal(str(result["m2_score"])) == Decimal("69.5")

        shadow = result["shadow_24m"]
        assert shadow["shadow"] is True
        assert shadow["lookback_months"] == 24
        assert shadow["history_samples"]["m2_yoy"]["total"] == 24
        # Shadow includes the poisoned month → different history-dependent score.
        assert shadow["component_scores"]["m2_yoy"] != result["m2_score"]
        assert shadow["lei_index"] is not None
        assert shadow["economic_state"]
        assert "history_samples" in shadow

    def test_missing_history_months_stay_none_and_reduce_used_not_total(self) -> None:
        rows = [
            _full_month_row(2026, 6, m2_yoy=12.0, social_financing_yoy=10.0, brent_oil=84.0),
            # gap: 2026-05 absent
            _full_month_row(2026, 4, m2_yoy=8.0, social_financing_yoy=6.0, brent_oil=80.0),
        ]
        result = compute_leading_indicator(rows, REPORT_DATE)
        assert result["as_of_month"] == "2026-06"
        assert result["history_samples"]["m2_yoy"] == {"used": 1, "total": 12}
        assert result["history_samples"]["social_financing_yoy"] == {"used": 1, "total": 12}
        assert result["history_samples"]["commodity"] == {"used": 1, "total": 12}
        assert "M2_HISTORY_MISSING_MONTHS" in result["warnings"]
        assert Decimal(str(result["m2_score"])) == Decimal("70")

    def test_rows_after_as_of_month_do_not_affect_primary_or_shadow(self) -> None:
        rows = _history_rows((2026, 6), months=24)
        rows.insert(
            0,
            {
                "trade_date": date(2026, 7, 20),
                "pmi": 99.0,
                "pmi_source_date": date(2026, 6, 1),
                "m2_yoy": 99.0,
                "m2_yoy_source_date": date(2026, 6, 1),
                "social_financing_yoy": 99.0,
                "social_financing_yoy_source_date": date(2026, 6, 1),
                "term_spread_10y_1y": 200.0,
                "term_spread_10y_1y_source_date": date(2026, 7, 20),
                "credit_spread_aaa_3y": 1.0,
                "credit_spread_aaa_3y_source_date": date(2026, 7, 20),
                "brent_oil": 200.0,
                "brent_oil_source_date": date(2026, 7, 20),
            },
        )
        result = compute_leading_indicator(rows, REPORT_DATE)
        assert result["as_of_month"] == "2026-06"
        used = {e["component"]: e for e in result["component_evidence"] if e["used"]}
        assert Decimal(str(used["term_spread"]["value"])) == Decimal("60")
        assert Decimal(str(used["commodity"]["value"])) == Decimal("84")
        # Shadow shares the same current legs.
        assert result["shadow_24m"]["component_scores"]["term_spread"] == result["term_spread_score"]
        assert result["shadow_24m"]["component_scores"]["commodity"] != 100.0


class TestPmiZeroNotTreatedAsMissing:
    """PMI 真实值为 0 不应被误判为缺失。"""

    def test_pmi_zero_is_scored_not_defaulted_to_neutral(self) -> None:
        rows = [
            _full_month_row(2026, 6, pmi=0.0),
            _full_month_row(2026, 5),
        ]
        result = compute_leading_indicator(rows, REPORT_DATE)
        assert result["as_of_month"] == "2026-06"
        assert Decimal(str(result["pmi_score"])) == Decimal("0")
        assert Decimal(str(result["pmi_score"])) != Decimal("50")

    def test_pmi_none_prevents_common_month(self) -> None:
        rows = [
            {
                **_full_month_row(2026, 6),
                "pmi": None,
                "pmi_source_date": None,
            }
        ]
        result = compute_leading_indicator(rows, REPORT_DATE)
        assert result["data_status"] == "unavailable"
        assert result["lei_index"] is None
        assert "LEI_NO_COMMON_COMPUTABLE_MONTH" in result["warnings"]
        assert result["observation_only"] is True
        assert result["formal_use_allowed"] is False
