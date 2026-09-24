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


def _disclosure(
    num_days: int,
    *,
    discarded: list[dict] | None = None,
    missing_treasury: list[str] | None = None,
) -> dict[str, str] | None:
    return campisi_svc._decision_window_disclosure(
        pnl_window={"start": "2026-01-01", "end": "2026-01-31", "kind": "monthly_period"},
        curve_window={"start": "2026-01-01", "end": "2026-01-31", "kind": "curve_displacement"},
        num_days=num_days,
        curve_alignment={
            "threshold_days": campisi_svc._DECISION_CURVE_STALENESS_THRESHOLD_DAYS,
            "max_in_use_deviation_days": 0,
            "discarded": list(discarded or []),
            "missing_treasury": list(missing_treasury or []),
        },
    )


@pytest.mark.parametrize(
    ("num_days", "expected_level"),
    [
        (0, None),
        # 月度对齐窗口（约 28-31 天）是常态口径：必须披露，但严重度是 info。
        (1, "info"),
        (30, "info"),
        (45, "info"),
        # 显式长窗口请求相对月度期间属口径错配，仍升级 warning（保留 45 天语义）。
        (46, "warning"),
        (91, "warning"),
    ],
)
def test_decision_window_disclosure_levels_by_span_with_aligned_curves(
    num_days: int,
    expected_level: str | None,
) -> None:
    disclosure = _disclosure(num_days)
    if expected_level is None:
        assert disclosure is None
        return
    assert disclosure is not None
    assert disclosure["level"] == expected_level
    assert ("口径错配" in disclosure["message"]) is (expected_level == "warning")
    assert f"{num_days} 天" in disclosure["message"]
    # 窗口声明前提必须是月度期间，不得再出现"单日"错误前提。
    assert "月度期间" in disclosure["message"]
    assert "单日" not in disclosure["message"]


def test_decision_window_disclosure_escalates_on_curve_staleness_guard() -> None:
    """分级由曲线解析偏差驱动：默认 30 天窗口配上被弃用的陈旧曲线必须是 warning。

    此前分级仅键在 num_days（默认路径恒为 30），曲线跳月的危险月份与健康月份
    拿到同样的 info 级披露。
    """
    discarded = [
        {
            "label": "期初国债曲线",
            "requested": "2026-01-29",
            "target": "2026-01-31",
            "resolved": "2025-12-31",
            "deviation_days": 31,
        }
    ]
    disclosure = _disclosure(30, discarded=discarded)
    assert disclosure is not None
    assert disclosure["level"] == "warning"
    assert "陈旧守卫" in disclosure["message"]
    assert "期初国债曲线" in disclosure["message"]
    assert "31 天" in disclosure["message"]
    assert "residual_noise" in disclosure["message"]
    # 弃用披露不依赖窗口跨度：零跨度窗口同样必须升级。
    zero_span = _disclosure(0, discarded=discarded)
    assert zero_span is not None
    assert zero_span["level"] == "warning"


def test_decision_window_disclosure_escalates_on_missing_treasury_side() -> None:
    disclosure = _disclosure(30, missing_treasury=["期末国债曲线"])
    assert disclosure is not None
    assert disclosure["level"] == "warning"
    assert "期末国债曲线" in disclosure["message"]
    assert "residual_noise" in disclosure["message"]


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

    # pnl_window 声明月度期间语义：fact_formal_pnl_fi 一行是报告月流量，不是单日。
    expected_pnl_window = {"start": "2026-01-01", "end": "2026-01-31", "kind": "monthly_period"}
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
    # 曲线对齐、无陈旧弃用时窗口披露保持 info 级，且前提是月度期间而不是单日。
    disclosure = result["window_disclosure"]
    assert disclosure["level"] == "info"
    assert "30 天" in disclosure["message"]
    assert "月度期间" in disclosure["message"]
    assert "单日" not in disclosure["message"]
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


def _seed_february_jump_month_sample(db_path) -> None:
    """复刻生产结构性坏月模式：曲线只有月末观测，持仓日频。

    旧默认推导（end−30 天）会把期初锚到 2026-01-29，曲线 on-or-before 回退到
    2025-12-31（跳月）；对齐后期初必须锚到 PnL 报告月上月末 2026-01-31。
    """
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            insert into fact_formal_pnl_fi values
            ('2026-02-28', 'BOND_FEB', 'FIOA', '5010', 'bond_investment', 'FVTPL', 'CNY',
             10.0, 0.0, 0.0, 0.0, -10.0, 'sv_formal', 'rv_formal', 'batch1', 'trace-feb')
            """
        )
        for report_date in ("2026-01-29", "2026-01-31"):
            conn.execute(
                """
                insert into fact_formal_bond_analytics_daily values
                (?, 'BOND_FEB', 'Bond Feb', 'FIOA', '5010', 'bond', 'treasury', 'treasury',
                 'Issuer F', 'Gov', 'AAA', 'FVTPL', 'CNY',
                 1000.0, 1000.0, 1000.0, 0.0, 0.03, 0.02, '2031-01-01', 5.0, '5Y',
                 2.0, 2.0, 0.0, 2.0, false, 0.0, 'sv_bond', 'rv_bond', 'batch1', 'trace-feb-a')
                """,
                [report_date],
            )
        curve_rows = []
        for trade_date, rate in (("2025-12-31", 1.0), ("2026-01-31", 2.0), ("2026-02-28", 3.0)):
            for tenor in ("1Y", "3Y", "5Y", "7Y", "10Y", "30Y"):
                curve_rows.append((trade_date, "treasury", tenor, rate, "formal", "vv", "sv_curve", "rv_curve"))
        conn.executemany(
            "insert into fact_formal_yield_curve_daily values (?, ?, ?, ?, ?, ?, ?, ?)",
            curve_rows,
        )
    finally:
        conn.close()


def test_decision_grade_default_window_aligns_to_prior_month_end_not_lookback(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """二月跳月模式：默认路径期初必须锚定 PnL 报告月上月末，且与 lookback_days 无关。

    若仍按 end−30 天推导，期初曲线会跳月取 2025-12-31（Δy=0.02），
    rate_level_effect = -2*1000*0.02 = -40（虚增一倍）；对齐后 Δy=0.01 → -20。
    """
    db_path = tmp_path / "decision_grade_feb_alignment.duckdb"
    _create_decision_grade_tables(db_path)
    _seed_february_jump_month_sample(db_path)
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    envelope = campisi_svc.campisi_decision_grade_envelope(end_date="2026-02-28")
    filters = envelope["result_meta"]["filters_applied"]
    result = envelope["result"]

    assert filters["resolved_start_date"] == "2026-01-31"
    assert filters["resolved_end_date"] == "2026-02-28"
    assert result["pnl_window"] == {"start": "2026-02-01", "end": "2026-02-28", "kind": "monthly_period"}
    assert result["curve_window"]["start"] == "2026-01-31"
    assert result["formal_pnl_view"]["components"]["rate_level_effect"] == pytest.approx(-20.0)
    assert result["formal_pnl_view"]["components"]["residual_noise"] == pytest.approx(0.0)
    assert result["formal_pnl_view"]["closure"]["status"] == "closed"
    assert result["residual_diagnostics"]["stale_curve_discarded_count"] == 0
    assert result["window_disclosure"]["level"] == "info"
    assert not any("陈旧守卫" in warning for warning in result["warnings"])

    # lookback_days 不再参与默认推导：不同取值必须得到完全相同的窗口与效应。
    for lookback in (2, 90):
        alt = campisi_svc.campisi_decision_grade_envelope(end_date="2026-02-28", lookback_days=lookback)
        assert alt["result_meta"]["filters_applied"]["resolved_start_date"] == "2026-01-31"
        assert alt["result"]["formal_pnl_view"]["components"]["rate_level_effect"] == pytest.approx(-20.0)

    fallback = campisi_svc.campisi_decision_grade_envelope(end_date="2026-03-05")
    fallback_meta = fallback["result_meta"]
    assert fallback_meta["requested_report_date"] == "2026-03-05"
    assert fallback_meta["resolved_report_date"] == "2026-02-28"
    assert fallback_meta["fallback_mode"] == "latest_snapshot"
    assert fallback_meta["fallback_date"] == "2026-02-28"


def test_decision_grade_explicit_dates_keep_resolution_and_guard_stale_curves(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """显式 start/end 的日期解析语义不变（不被上月末对齐覆盖）。

    显式复刻旧滚动窗口（start=2026-01-29）时，曲线解析跳月到 2025-12-31、
    偏离声明窗口端点 29 天，陈旧守卫必须拦截并计入残差，而不是静默采用。
    """
    db_path = tmp_path / "decision_grade_explicit_dates.duckdb"
    _create_decision_grade_tables(db_path)
    _seed_february_jump_month_sample(db_path)
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    envelope = campisi_svc.campisi_decision_grade_envelope(
        start_date="2026-01-29",
        end_date="2026-02-28",
    )
    filters = envelope["result_meta"]["filters_applied"]
    result = envelope["result"]

    # 显式日期照常解析为持仓锚定日，不改写成上月末。
    assert filters["requested_start_date"] == "2026-01-29"
    assert filters["resolved_start_date"] == "2026-01-29"
    assert result["curve_window"]["start"] == "2026-01-29"
    # 陈旧守卫对显式路径同样生效：跳月曲线按缺失处理，市场效应进入残差。
    assert result["residual_diagnostics"]["stale_curve_discarded_count"] == 1
    assert result["formal_pnl_view"]["components"]["rate_level_effect"] == pytest.approx(0.0)
    assert result["formal_pnl_view"]["components"]["selection_proxy"] == pytest.approx(0.0)
    assert result["formal_pnl_view"]["components"]["residual_noise"] == pytest.approx(-20.0)
    assert result["window_disclosure"]["level"] == "warning"
    assert any("陈旧守卫" in warning for warning in result["warnings"])


def _seed_staleness_boundary_sample(db_path, *, start_curve_date: str) -> None:
    _seed_decision_grade_sample(db_path, with_curves=False)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        curve_rows = []
        for trade_date, rate in ((start_curve_date, 2.0), ("2026-01-31", 3.0)):
            for tenor in ("1Y", "3Y", "5Y", "7Y", "10Y", "30Y"):
                curve_rows.append((trade_date, "treasury", tenor, rate, "formal", "vv", "sv_curve", "rv_curve"))
                curve_rows.append((trade_date, "aaa_credit", tenor, rate, "formal", "vv", "sv_curve", "rv_curve"))
        conn.executemany(
            "insert into fact_formal_yield_curve_daily values (?, ?, ?, ?, ?, ?, ?, ?)",
            curve_rows,
        )
    finally:
        conn.close()


def test_curve_staleness_guard_allows_deviation_within_threshold(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """偏离 6 天（≤7 天阈值）：曲线按只读 fallback 采用，效应照常计算。"""
    db_path = tmp_path / "decision_grade_guard_6d.duckdb"
    _create_decision_grade_tables(db_path)
    _seed_staleness_boundary_sample(db_path, start_curve_date="2025-12-26")
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    result = campisi_svc.campisi_decision_grade_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]

    # 与曲线精确命中的基准场景同值：rate_level=-20、residual=0（见 test_campisi_decision_grade）。
    assert result["formal_pnl_view"]["components"]["rate_level_effect"] == pytest.approx(-20.0)
    assert result["formal_pnl_view"]["components"]["residual_noise"] == pytest.approx(0.0)
    assert result["residual_diagnostics"]["stale_curve_discarded_count"] == 0
    assert result["residual_diagnostics"]["stale_curve_fallback_count"] >= 1
    assert result["window_disclosure"]["level"] == "info"
    assert any("只读 fallback" in warning for warning in result["warnings"])
    assert not any("陈旧守卫" in warning for warning in result["warnings"])


def test_curve_staleness_guard_discards_deviation_beyond_threshold(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """偏离 8 天（>7 天阈值）：该侧曲线按缺失处理，市场效应进入残差并升级披露。"""
    db_path = tmp_path / "decision_grade_guard_8d.duckdb"
    _create_decision_grade_tables(db_path)
    _seed_staleness_boundary_sample(db_path, start_curve_date="2025-12-24")
    monkeypatch.setattr(
        campisi_svc,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=str(db_path), governance_path=str(tmp_path)),
    )

    result = campisi_svc.campisi_decision_grade_envelope(
        start_date="2026-01-01",
        end_date="2026-01-31",
    )["result"]

    components = result["formal_pnl_view"]["components"]
    # 与缺曲线场景同值：市场效应清零，未解释缺口 83 落入残差而不是选券代理。
    assert components["rate_level_effect"] == pytest.approx(0.0)
    assert components["selection_proxy"] == pytest.approx(0.0)
    assert components["residual_noise"] == pytest.approx(83.0)
    # 期初国债 + 期初 AAA 信用两侧被弃用。
    assert result["residual_diagnostics"]["stale_curve_discarded_count"] == 2
    assert result["residual_diagnostics"]["missing_curve_count"] > 0
    assert result["window_disclosure"]["level"] == "warning"
    assert result["window_disclosure"]["message"] in result["warnings"]
    assert any("陈旧守卫" in warning for warning in result["warnings"])


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
    # pnl_window 始终声明 anchor_end 报告月的月度期间，与显式请求的曲线窗口无关。
    assert result["pnl_window"] == {"start": "2026-01-01", "end": "2026-01-31", "kind": "monthly_period"}
    assert result["num_days"] > campisi_svc._DECISION_WINDOW_MISMATCH_THRESHOLD_DAYS
    assert result["window_disclosure"]["level"] == "warning"
    assert result["window_disclosure"]["message"] in result["warnings"]
    assert any("口径错配" in warning for warning in result["warnings"])
    assert any("selection_proxy" in warning for warning in result["warnings"])
