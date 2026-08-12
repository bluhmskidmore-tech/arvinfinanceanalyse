from __future__ import annotations

from types import SimpleNamespace

import duckdb
import pytest

from backend.app.services import campisi_attribution_service as campisi_svc
from tests.test_campisi_decision_grade import (
    _create_decision_grade_tables,
    _seed_decision_grade_sample,
)


def _seed_decision_grade_long_window_sample(db_path) -> None:
    _seed_decision_grade_sample(db_path)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_bond_analytics_daily
            select
                date '2025-11-01' as report_date,
                instrument_code,
                instrument_name,
                portfolio_name,
                cost_center,
                asset_class_raw,
                asset_class_std,
                bond_type,
                issuer_name,
                industry_name,
                rating,
                accounting_class,
                currency_code,
                face_value,
                market_value,
                amortized_cost,
                accrued_interest,
                coupon_rate,
                ytm,
                maturity_date,
                years_to_maturity,
                tenor_bucket,
                macaulay_duration,
                modified_duration,
                convexity,
                dv01,
                is_credit,
                spread_dv01,
                source_version,
                rule_version,
                ingest_batch_id,
                trace_id
            from fact_formal_bond_analytics_daily
            where report_date = date '2026-01-01'
            """
        )
        conn.execute(
            """
            insert into fact_formal_zqtz_balance_daily
            select
                date '2025-11-01' as report_date,
                instrument_code,
                instrument_name,
                portfolio_name,
                cost_center,
                account_category,
                asset_class,
                bond_type,
                issuer_name,
                industry_name,
                rating,
                invest_type_std,
                accounting_basis,
                position_scope,
                currency_basis,
                currency_code,
                face_value_amount,
                market_value_amount,
                amortized_cost_amount,
                accrued_interest_amount,
                coupon_rate,
                ytm_value,
                maturity_date,
                interest_mode,
                is_issuance_like,
                source_version,
                rule_version,
                ingest_batch_id,
                trace_id
            from fact_formal_zqtz_balance_daily
            where report_date = date '2026-01-01'
            """
        )
        curve_rows = []
        for tenor in ("1Y", "3Y", "5Y", "7Y", "10Y", "30Y"):
            curve_rows.append(("2025-11-01", "treasury", tenor, 1.5, "formal", "vv", "sv_curve", "rv_curve"))
            curve_rows.append(("2025-11-01", "aaa_credit", tenor, 1.5, "formal", "vv", "sv_curve", "rv_curve"))
        conn.executemany(
            """
            insert into fact_formal_yield_curve_daily values
            (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            curve_rows,
        )
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("num_days", "expected_level"),
    [
        (0, None),
        # 默认 lookback_days=30 的最常见路径：必须落在披露内，而不是 45 天盲区。
        (1, "info"),
        (30, "info"),
        (45, "info"),
        (46, "warning"),
        (91, "warning"),
    ],
)
def test_decision_window_disclosure_covers_every_span_beyond_single_day(
    num_days: int,
    expected_level: str | None,
) -> None:
    disclosure = campisi_svc._decision_window_disclosure(
        anchor_start="2026-01-01",
        anchor_end="2026-01-31",
        num_days=num_days,
    )
    if expected_level is None:
        assert disclosure is None
        return
    assert disclosure is not None
    assert disclosure["level"] == expected_level
    assert ("口径错配" in disclosure["message"]) is (expected_level == "warning")
    assert f"{num_days} 天" in disclosure["message"]


def test_decision_grade_declares_pnl_and_curve_windows_with_info_level_disclosure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "decision_grade_windows.duckdb"
    _create_decision_grade_tables(db_path)
    _seed_decision_grade_sample(db_path)
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    envelope = campisi_svc.campisi_decision_grade_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    filters = envelope["result_meta"]["filters_applied"]
    result = envelope["result"]

    expected_pnl_window = {"start": "2026-01-31", "end": "2026-01-31", "kind": "single_day"}
    expected_curve_window = {
        "start": "2026-01-01",
        "end": "2026-01-31",
        "kind": "curve_displacement",
    }
    assert filters["pnl_window"] == expected_pnl_window
    assert filters["curve_window"] == expected_curve_window
    assert result["pnl_window"] == expected_pnl_window
    assert result["curve_window"] == expected_curve_window
    assert result["num_days"] == 30
    # 30 天曲线位移 vs 单日 PnL 本身就是失真，必须披露；只是严重度停留在 info 级。
    disclosure = result["window_disclosure"]
    assert disclosure["level"] == "info"
    assert "30 天" in disclosure["message"]
    assert "selection_proxy" in disclosure["message"]
    assert not any("口径错配" in warning for warning in result["warnings"])
    # info 级披露不得混进 warning 列表，否则质量信号会被常态化噪音淹没。
    assert disclosure["message"] not in result["warnings"]


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        (None, None),
        ("2020-01-01", "2020-06-30"),
        (None, "2020-01-01"),
    ],
)
def test_decision_grade_degrades_gracefully_when_anchor_dates_are_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    start_date: str | None,
    end_date: str | None,
) -> None:
    """锚定日期解析为空时必须走优雅空载分支，而不是让窗口声明抛 ValueError 冒泡成 500。"""
    db_path = tmp_path / "decision_grade_no_anchor.duckdb"
    _create_decision_grade_tables(db_path)
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    envelope = campisi_svc.campisi_decision_grade_envelope(
        start_date=start_date,
        end_date=end_date,
    )

    assert envelope["result_meta"]["quality_flag"] == "warning"
    # 空载分支不得声明窗口（无锚定日期可声明），但必须保留请求参数供追溯。
    filters = envelope["result_meta"]["filters_applied"]
    assert "pnl_window" not in filters
    assert "curve_window" not in filters
    assert filters["requested_end_date"] == end_date
    # 前端契约把 formal_pnl_view.closure 声明为必填并直接解引用 closure.difference，
    # 空载 payload 缺该键会在页面上抛 TypeError。
    closure = envelope["result"]["formal_pnl_view"]["closure"]
    assert closure["status"] == "warning"
    assert closure["difference"] == 0.0
    assert closure["difference_ratio"] is None
    assert closure["basis"] == "fact_formal_pnl_fi.total_pnl"


def test_decision_grade_warns_when_curve_window_exceeds_pnl_window_threshold(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "decision_grade_window_mismatch.duckdb"
    _create_decision_grade_tables(db_path)
    _seed_decision_grade_long_window_sample(db_path)
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    envelope = campisi_svc.campisi_decision_grade_envelope(
        start_date="2025-11-01",
        end_date="2026-01-31",
    )
    result = envelope["result"]

    assert result["curve_window"]["start"] == "2025-11-01"
    assert result["curve_window"]["end"] == "2026-01-31"
    assert result["pnl_window"]["start"] == "2026-01-31"
    assert result["num_days"] > campisi_svc._DECISION_WINDOW_MISMATCH_THRESHOLD_DAYS
    assert result["window_disclosure"]["level"] == "warning"
    assert result["window_disclosure"]["message"] in result["warnings"]
    assert any("口径错配" in warning for warning in result["warnings"])
    assert any("selection_proxy" in warning for warning in result["warnings"])
