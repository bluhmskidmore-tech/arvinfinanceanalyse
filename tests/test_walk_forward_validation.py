"""walk-forward 切割框架的最小测试：切割正确性 + 无未来数据泄漏。

主体测试跑在合成执行历史上，不接触 DuckDB。文件末尾的「引擎级断言」一组会调用真实
回测引擎（`run_portfolio_backtest`）但仍只用合成行与合成价格路径，同样不接触 DuckDB。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta

import pytest

from backend.app.core_finance.portfolio_backtest import run_portfolio_backtest
from backend.app.core_finance.portfolio_paths import position_path_key
from scripts.run_walk_forward_validation import (
    BacktestRunner,
    _dedupe_execution_rows,
    _metrics_view,
    analyze_schedule,
)
from scripts.walk_forward_core import (
    DEFAULT_MIN_WINDOWS_FOR_VERDICT,
    ScheduleConfig,
    WalkForwardLeakageError,
    WalkForwardWindow,
    add_months,
    build_segments,
    build_windows,
    chain_returns,
    decay_ratio,
    oos_verdict,
    parameter_drift,
    score_from_metrics,
    select_parameter,
    select_training_rows,
    select_validation_rows,
    sign_consistency,
    slice_rows_by_signal_date,
    window_crosses_dates,
    windows_are_disjoint,
)

SCHEDULE = ScheduleConfig(label="test_6t_2v_2s", train_months=6, valid_months=2, step_months=2)
ERA_CUT = "2026-01-05"


def _synthetic_rows(
    start: str,
    end: str,
    *,
    step_days: int = 7,
    horizon_days: int = 28,
    signal_kind: str = "stock_candidate",
) -> list[dict[str, object]]:
    """每 step_days 一个信号，20d 退出日固定为信号日 + horizon_days。"""
    rows: list[dict[str, object]] = []
    cursor = date.fromisoformat(start)
    last = date.fromisoformat(end)
    index = 0
    while cursor <= last:
        rows.append(
            {
                "signal_date": cursor.isoformat(),
                "entry_date": (cursor + timedelta(days=1)).isoformat(),
                "exit_date_20d": (cursor + timedelta(days=horizon_days)).isoformat(),
                "return_20d_net_adj": 0.01,
                "stock_code": f"{index % 7:06d}.SZ",
                "signal_kind": signal_kind,
            }
        )
        cursor += timedelta(days=step_days)
        index += 1
    return rows


def _signal_dates(rows: Sequence[Mapping[str, object]]) -> list[str]:
    return [str(row["signal_date"]) for row in rows]


# --------------------------------------------------------------- 切割正确性


def test_windows_are_contiguous_and_month_aligned() -> None:
    rows = _synthetic_rows("2024-09-02", "2025-12-30")
    windows, segments = build_windows(_signal_dates(rows), schedule=SCHEDULE)

    assert len(segments) == 1
    assert windows, "6/2/2 schedule should fit inside a 16-month segment"
    for window in windows:
        assert window.train_start < window.train_end < window.valid_start <= window.valid_end
        # 训练末日与验证首日必须严格相邻，中间不能留缝也不能重叠。
        assert date.fromisoformat(window.valid_start) - date.fromisoformat(window.train_end) == timedelta(days=1)
        assert add_months(window.train_start, SCHEDULE.train_months).isoformat() == window.valid_start
        assert add_months(window.valid_start, SCHEDULE.valid_months) - timedelta(days=1) == date.fromisoformat(
            window.valid_end
        )


def test_validation_windows_are_disjoint_when_step_equals_valid_length() -> None:
    rows = _synthetic_rows("2024-09-02", "2025-12-30")
    windows, _segments = build_windows(_signal_dates(rows), schedule=SCHEDULE)

    assert windows_are_disjoint(windows) is True

    overlapping = ScheduleConfig(label="overlap", train_months=6, valid_months=2, step_months=1)
    overlapped_windows, _ = build_windows(_signal_dates(rows), schedule=overlapping)
    assert windows_are_disjoint(overlapped_windows) is False


def test_segments_split_on_forced_cut_and_data_gap() -> None:
    rows = _synthetic_rows("2025-10-01", "2025-12-30") + _synthetic_rows("2026-03-18", "2026-05-20")
    segments = build_segments(_signal_dates(rows), forced_cut_dates=(ERA_CUT,), max_gap_days=45)

    assert len(segments) == 2
    assert segments[0].end_date < ERA_CUT <= segments[1].start_date
    assert "forced_cut:2026-01-05" in segments[1].start_reason
    assert "data_gap:" in segments[1].start_reason


def test_windows_never_cross_forced_cut_date() -> None:
    """两代数据边界必须是硬边界：任何窗口都不得跨越。"""
    rows = _synthetic_rows("2025-06-02", "2025-12-30") + _synthetic_rows("2026-01-06", "2026-12-28")
    windows, segments = build_windows(
        _signal_dates(rows),
        schedule=SCHEDULE,
        forced_cut_dates=(ERA_CUT,),
        max_gap_days=45,
    )

    assert len(segments) == 2
    assert windows, "each side of the cut should still be able to produce windows"
    for window in windows:
        assert window_crosses_dates(window, (ERA_CUT,)) == []
        assert (window.valid_end < ERA_CUT) or (ERA_CUT <= window.train_start)


def test_windows_never_reach_back_into_the_previous_segment() -> None:
    """数据空洞造成的段边界同样是硬边界：后段窗口不得取到前段的行。"""
    early = _synthetic_rows("2025-01-06", "2025-03-24")
    late = _synthetic_rows("2025-05-12", "2026-04-27")
    rows = early + late
    windows, segments = build_windows(
        _signal_dates(rows),
        schedule=SCHEDULE,
        forced_cut_dates=(),
        max_gap_days=45,
    )

    assert len(segments) == 2
    late_windows = [window for window in windows if window.segment_id == segments[1].segment_id]
    assert late_windows
    early_dates = {str(row["signal_date"]) for row in early}
    for window in late_windows:
        assert window.train_start > segments[0].end_date
        sliced = select_training_rows(rows, window, purge=False)
        assert not (early_dates & {str(row["signal_date"]) for row in sliced})


def test_segment_end_in_same_month_as_cut_does_not_leak_next_segment() -> None:
    """对抗构造：段末信号日与强制切割点同月。

    cut=2025-07-10、前段最后信号日 2025-07-07（同月）时，仅用
    `month_key(valid_end) <= last_month` 约束会放行验证区间 2025-06-01~2025-07-31，
    其验证切片会吃进 cut 之后（属于后段）的行。窗口生成必须把验证末日夹在段实际边界内。
    """
    cut = "2025-07-10"
    early = _synthetic_rows("2024-12-02", "2025-07-09")
    late = _synthetic_rows(cut, "2025-12-30", step_days=3)
    rows = early + late
    windows, segments = build_windows(
        _signal_dates(rows),
        schedule=SCHEDULE,
        forced_cut_dates=(cut,),
        max_gap_days=45,
    )

    assert len(segments) == 2
    assert segments[0].end_date == "2025-07-07"
    assert segments[1].start_date == cut
    # 段末与 cut 同月：last_month 相同，仅靠月粒度无法拦住跨界。
    assert segments[0].end_date[:7] == cut[:7]

    early_windows = [window for window in windows if window.segment_id == segments[0].segment_id]
    assert early_windows, "前段必须仍能产出窗口，否则该断言变成空转"
    late_dates = {str(row["signal_date"]) for row in late}
    for window in windows:
        assert window_crosses_dates(window, (cut,)) == []
        assert window.valid_end < cut or window.train_start >= cut
        validation_dates = {
            str(row["signal_date"]) for row in select_validation_rows(rows, window)
        }
        training_dates = {
            str(row["signal_date"]) for row in select_training_rows(rows, window, purge=False)
        }
        if window.segment_id == segments[0].segment_id:
            assert not (late_dates & validation_dates), f"{window.window_id} 验证切片吃进了后段行"
            assert not (late_dates & training_dates), f"{window.window_id} 训练切片吃进了后段行"

    clamped = [window for window in early_windows if window.valid_end_clamped]
    assert clamped, "该构造必须触发验证末日夹取路径"
    # 夹到 cut 前一日（同时也是后段首个信号日的前一日）
    assert all(window.valid_end == "2025-07-09" for window in clamped)


def test_analyze_schedule_fails_fast_on_crossing_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """双保险第二层：即使窗口生成被改坏，编排侧也必须拒绝出报告而不是只记一笔。"""
    crossing_window = WalkForwardWindow(
        window_id="S1W1",
        segment_id="S1",
        train_start="2025-01-01",
        train_end="2025-06-30",
        valid_start="2025-07-01",
        valid_end="2025-08-31",
    )
    monkeypatch.setattr(
        "scripts.run_walk_forward_validation.build_windows",
        lambda *_args, **_kwargs: ([crossing_window], []),
    )

    with pytest.raises(WalkForwardLeakageError) as excinfo:
        analyze_schedule(
            runner=None,
            usable_rows=_synthetic_rows("2025-01-06", "2025-08-25"),
            schedule=SCHEDULE,
            objective="sharpe",
            risk_per_trade_grid=(0.005,),
            forced_cut_dates=("2025-07-10",),
            max_gap_days=45,
            min_windows=3,
            purge=True,
            detailed=False,
        )

    assert "S1W1" in str(excinfo.value)


def test_slice_is_inclusive_and_drops_rows_without_signal_date() -> None:
    rows = [
        {"signal_date": "2025-03-01"},
        {"signal_date": "2025-04-30"},
        {"signal_date": "2025-05-01"},
        {"signal_date": None},
        {},
    ]
    sliced = slice_rows_by_signal_date(rows, "2025-03-01", "2025-04-30")

    assert [row["signal_date"] for row in sliced] == ["2025-03-01", "2025-04-30"]


def test_validation_slice_only_contains_window_signal_dates() -> None:
    rows = _synthetic_rows("2024-09-02", "2025-12-30", step_days=3)
    windows, _segments = build_windows(_signal_dates(rows), schedule=SCHEDULE)

    for window in windows:
        validation_rows = select_validation_rows(rows, window)
        assert validation_rows, f"{window.window_id} should contain synthetic signals"
        for row in validation_rows:
            assert window.valid_start <= str(row["signal_date"]) <= window.valid_end


def test_training_slice_only_contains_training_signal_dates() -> None:
    rows = _synthetic_rows("2024-09-02", "2025-12-30", step_days=3)
    windows, _segments = build_windows(_signal_dates(rows), schedule=SCHEDULE)

    for window in windows:
        training_rows = select_training_rows(rows, window)
        assert training_rows
        for row in training_rows:
            assert window.train_start <= str(row["signal_date"]) <= window.train_end


# ------------------------------------------------------------------- 防泄漏


def test_training_rows_are_purged_of_unrealized_outcomes() -> None:
    """选参时刻(验证窗首日)尚未兑现的训练行必须被剔除。"""
    rows = _synthetic_rows("2024-09-02", "2025-12-30", step_days=3, horizon_days=28)
    windows, _segments = build_windows(_signal_dates(rows), schedule=SCHEDULE)
    window = windows[0]

    purged = select_training_rows(rows, window, purge=True)
    unpurged = select_training_rows(rows, window, purge=False)

    assert len(purged) < len(unpurged), "28 天持有期必然让训练窗尾部有未兑现行"
    for row in purged:
        assert str(row["exit_date_20d"]) <= window.train_end
        assert str(row["exit_date_20d"]) < window.selection_date
    leaked = [row for row in unpurged if str(row["exit_date_20d"]) > window.train_end]
    assert leaked, "fixture 必须真的包含跨界行，否则该断言无效"


def test_training_rows_exclude_rows_without_outcome_date_when_purging() -> None:
    window = WalkForwardWindow(
        window_id="W1",
        segment_id="S1",
        train_start="2025-01-01",
        train_end="2025-06-30",
        valid_start="2025-07-01",
        valid_end="2025-08-31",
    )
    rows = [
        {"signal_date": "2025-02-01", "exit_date_20d": "2025-03-01"},
        {"signal_date": "2025-02-02", "exit_date_20d": None},
        {"signal_date": "2025-06-20", "exit_date_20d": "2025-07-18"},
    ]

    purged = select_training_rows(rows, window, purge=True)

    assert [row["signal_date"] for row in purged] == ["2025-02-01"]


def test_parameter_selection_is_immune_to_future_rows() -> None:
    """核心防泄漏断言：抹掉/篡改选参时刻之后的所有行，选参结果必须不变。"""
    rows = _synthetic_rows("2024-09-02", "2025-12-30", step_days=3)
    windows, _segments = build_windows(_signal_dates(rows), schedule=SCHEDULE)
    window = windows[0]
    grid = (0.0025, 0.005, 0.0075, 0.01)

    def _fake_backtest(sliced: Sequence[Mapping[str, object]], parameter: float) -> dict[str, object]:
        """确定性伪引擎：分数只依赖切片内容与参数。"""
        signature = sum(hash(str(row["signal_date"])) % 97 for row in sliced)
        return {
            "daily_sharpe": (signature % 11) / 10.0 + parameter * 37.0,
            "cagr": 0.1,
            "max_drawdown": 0.2,
        }

    def _select(source_rows: Sequence[Mapping[str, object]]):
        training_rows = select_training_rows(source_rows, window, purge=True)
        scores = {
            parameter: score_from_metrics(_fake_backtest(training_rows, parameter), objective="sharpe")
            for parameter in grid
        }
        return select_training_rows(source_rows, window, purge=True), select_parameter(
            scores, objective="sharpe"
        )

    baseline_rows, baseline_selection = _select(rows)
    assert baseline_selection.status == "selected"

    # 1) 删除 train_end 之后的一切
    truncated = [row for row in rows if str(row["signal_date"]) <= window.train_end]
    truncated_rows, truncated_selection = _select(truncated)
    assert truncated_rows == baseline_rows
    assert truncated_selection.selected == baseline_selection.selected

    # 2) 把未来行的收益换成极端值（若泄漏，分数必然改变）
    poisoned = [
        dict(row, return_20d_net_adj=-9.99)
        if str(row["signal_date"]) > window.train_end
        else row
        for row in rows
    ]
    poisoned_rows, poisoned_selection = _select(poisoned)
    assert poisoned_rows == baseline_rows
    assert poisoned_selection.selected == baseline_selection.selected


def test_validation_slice_is_immune_to_out_of_window_rows() -> None:
    rows = _synthetic_rows("2024-09-02", "2025-12-30", step_days=3)
    windows, _segments = build_windows(_signal_dates(rows), schedule=SCHEDULE)
    window = windows[1]

    baseline = select_validation_rows(rows, window)
    poisoned = [
        dict(row, return_20d_net_adj=42.0)
        if not (window.valid_start <= str(row["signal_date"]) <= window.valid_end)
        else row
        for row in rows
    ]

    assert select_validation_rows(poisoned, window) == baseline


# ---------------------------------------------------------------- 统计与判定


def test_select_parameter_prefers_smaller_parameter_on_ties() -> None:
    selection = select_parameter({0.0025: 1.0, 0.005: 1.0, 0.01: 0.5}, objective="sharpe")

    assert selection.status == "selected"
    assert selection.selected == 0.0025


def test_select_parameter_reports_missing_scores() -> None:
    assert select_parameter({0.005: None}, objective="sharpe").status == "no_valid_score"
    assert select_parameter({}, objective="sharpe").status == "no_candidates"


def test_calmar_objective_requires_positive_drawdown() -> None:
    assert score_from_metrics({"cagr": 0.2, "max_drawdown": 0.1}, objective="calmar") == pytest.approx(2.0)
    assert score_from_metrics({"cagr": 0.2, "max_drawdown": 0.0}, objective="calmar") is None


def test_chain_returns_compounds() -> None:
    assert chain_returns([0.1, -0.1]) == pytest.approx(-0.01)


def test_decay_ratio_flags_non_positive_in_sample() -> None:
    assert decay_ratio(0.05, 0.10)["ratio"] == pytest.approx(0.5)
    assert decay_ratio(0.05, -0.10)["status"] == "is_non_positive"
    assert decay_ratio(None, 0.10)["status"] == "unavailable"


def test_sign_consistency_ignores_missing_windows() -> None:
    result = sign_consistency([0.01, -0.02, None, 0.03])

    assert result["observed_windows"] == 3
    assert result["positive_windows"] == 2
    assert result["positive_ratio"] == pytest.approx(2 / 3)


def test_parameter_drift_counts_switches() -> None:
    drift = parameter_drift([0.005, 0.005, 0.01, 0.0025])

    assert drift["distinct_values"] == 3
    assert drift["mode_value"] == 0.005
    assert drift["switch_count"] == 2
    assert drift["switch_rate"] == pytest.approx(2 / 3)


def test_verdict_requires_minimum_window_count() -> None:
    verdict, reason = oos_verdict(
        window_count=2,
        excess_values=[0.01, 0.02],
        chain_excess=0.03,
        min_windows=DEFAULT_MIN_WINDOWS_FOR_VERDICT,
    )

    assert verdict == "insufficient_windows"
    assert "自由度不足" in reason


def test_verdict_supported_and_weakened() -> None:
    supported, _ = oos_verdict(
        window_count=3,
        excess_values=[0.01, 0.02, -0.001],
        chain_excess=0.03,
        min_windows=3,
    )
    weakened, _ = oos_verdict(
        window_count=3,
        excess_values=[-0.01, -0.02, 0.001],
        chain_excess=-0.03,
        min_windows=3,
    )

    assert supported == "oos_supported"
    assert weakened == "oos_weakened"


# ------------------------------------------------------- 加载器扇出（行数守恒）


def _loader_row(signal_date: str, stock_code: str, ema10: float | None) -> dict[str, object]:
    return {
        "signal_date": signal_date,
        "stock_code": stock_code,
        "signal_kind": "stock_candidate",
        "entry_date": "2025-03-04",
        "exit_date_20d": "2025-04-01",
        "return_20d_net_adj": 0.01,
        "ema10": ema10,
    }


def test_dedupe_conserves_rows_and_collapses_ema10_fanout() -> None:
    """共享加载器 ema10 join 扇出：编排侧去重后行数必须等于去重键数。"""
    rows = [
        _loader_row("2025-03-03", "000001.SZ", 9.0),
        _loader_row("2025-03-03", "000001.SZ", None),
        _loader_row("2025-03-03", "000001.SZ", 8.5),
        _loader_row("2025-03-03", "000001.SZ", 9.5),
        _loader_row("2025-03-03", "000002.SZ", 7.0),
        _loader_row("2025-03-04", "000001.SZ", 9.2),
    ]

    deduped, stats = _dedupe_execution_rows(rows)

    distinct_keys = {
        (str(row["signal_date"]), str(row["stock_code"]), str(row["signal_kind"])) for row in rows
    }
    assert len(deduped) == len(distinct_keys) == 3
    assert stats["loaded_rows"] == stats["deduped_rows"] + stats["removed_rows"]
    assert stats["loaded_rows"] == len(rows)
    assert stats["removed_rows"] == 3
    assert stats["duplicate_keys"] == 1
    assert stats["ema10_conflict_keys"] == 1
    assert stats["max_multiplicity"] == 4
    assert stats["removed_rows_by_kind"] == {"stock_candidate": 3}
    # 取舍：ema10 非空且最小者（止损距离最大 ⇒ 同键候选中仓位最保守的一档）。
    kept = next(row for row in deduped if row["stock_code"] == "000001.SZ" and row["signal_date"] == "2025-03-03")
    assert kept["ema10"] == 8.5
    # 未重复的行原样保留、顺序不变。
    assert [(row["signal_date"], row["stock_code"]) for row in deduped] == [
        ("2025-03-03", "000001.SZ"),
        ("2025-03-03", "000002.SZ"),
        ("2025-03-04", "000001.SZ"),
    ]


def test_dedupe_is_noop_without_fanout() -> None:
    rows = [_loader_row("2025-03-03", "000001.SZ", 9.0), _loader_row("2025-03-04", "000002.SZ", None)]

    deduped, stats = _dedupe_execution_rows(rows)

    assert deduped == rows
    assert stats["removed_rows"] == 0
    assert stats["duplicate_keys"] == 0


# ------------------------------------------------- 引擎级断言（真实回测引擎）

ENGINE_GRID = (0.0025, 0.005, 0.0075, 0.01)


def _engine_row(
    *,
    signal_date: str,
    entry_date: str,
    exit_date: str,
    stock_code: str,
    ema10: float,
    return_net: float,
    rank: int = 1,
) -> dict[str, object]:
    return {
        "signal_date": signal_date,
        "stock_code": stock_code,
        "stock_name": stock_code,
        "signal_kind": "stock_candidate",
        "candidate_rank": rank,
        "market_state": "HOT",
        "entry_date": entry_date,
        "entry_price": 10.0,
        "signal_close": 10.0,
        "entry_executable": True,
        "entry_block_reason": None,
        "ema10": ema10,
        "exit_date_20d": exit_date,
        "return_20d_net_adj": return_net,
        "daily_amount": 300_000_000.0,
    }


def _engine_path(
    start_date: str,
    *,
    bars: int,
    base: float = 10.0,
    drift: float = 0.01,
    halted_dates: Sequence[str] = (),
) -> list[dict[str, object]]:
    """合成价格路径：逐日一根 bar，指定日期停牌（引擎按 `halted` 跳过卖出）。"""
    rows: list[dict[str, object]] = []
    cursor = date.fromisoformat(start_date)
    price = base
    for _index in range(bars):
        trade_date = cursor.isoformat()
        rows.append(
            {
                "trade_date": trade_date,
                "open": round(price, 6),
                "high": round(price * 1.01, 6),
                "low": round(price * 0.99, 6),
                "close": round(price, 6),
                "volume": 1_000_000.0,
                "halted": trade_date in set(halted_dates),
            }
        )
        price *= 1.0 + drift
        cursor += timedelta(days=1)
    return rows


def _calendar(start_date: str, end_date: str) -> list[dict[str, object]]:
    cursor = date.fromisoformat(start_date)
    last = date.fromisoformat(end_date)
    rows: list[dict[str, object]] = []
    while cursor <= last:
        rows.append({"trade_date": cursor.isoformat(), "market_state": "HOT"})
        cursor += timedelta(days=1)
    return rows


def _engine_runner(
    price_paths: Mapping[str, Sequence[Mapping[str, object]]],
    calendar: Sequence[Mapping[str, object]],
) -> BacktestRunner:
    return BacktestRunner(
        price_paths=price_paths,
        market_state_rows=list(calendar),
        exposure_rows=[{"trade_date": row["trade_date"], "exposure": 1.0} for row in calendar],
        benchmark_rows=[],
        mode="path",
        initial_capital=100.0,
        max_positions=3,
    )


def test_scoped_price_paths_exclude_other_slices() -> None:
    calendar = _calendar("2026-06-01", "2026-07-15")
    paths = {
        position_path_key("000001.SZ", "2026-06-01"): _engine_path("2026-06-01", bars=21),
        position_path_key("000002.SZ", "2026-06-20"): _engine_path("2026-06-20", bars=21),
    }
    runner = _engine_runner(paths, calendar)
    rows = [
        _engine_row(
            signal_date="2026-05-31",
            entry_date="2026-06-01",
            exit_date="2026-06-20",
            stock_code="000001.SZ",
            ema10=9.0,
            return_net=0.05,
        )
    ]

    scoped = runner._scoped_price_paths(rows)

    assert set(scoped) == {position_path_key("000001.SZ", "2026-06-01")}


def test_training_price_paths_are_truncated_at_train_end() -> None:
    """WF-2：第 20 根 bar 停牌会把路径退出顺延到 train_end 之后，训练时间轴必须被截住。"""
    train_end = "2026-06-20"
    entry_date = "2026-06-01"
    halted_bar = "2026-06-20"  # 名义 20d 退出那根 bar 停牌 -> 顺延到 06-21
    path_key = position_path_key("000001.SZ", entry_date)
    calendar = _calendar("2026-06-01", "2026-06-30")
    paths = {path_key: _engine_path(entry_date, bars=21, halted_dates=(halted_bar,))}
    rows = [
        _engine_row(
            signal_date="2026-05-31",
            entry_date=entry_date,
            exit_date=train_end,
            stock_code="000001.SZ",
            ema10=9.0,
            return_net=0.05,
        )
    ]
    runner = _engine_runner(paths, calendar)

    untruncated = runner._scoped_price_paths(rows)
    truncated = runner._scoped_price_paths(rows, cutoff_date=train_end)

    assert max(str(bar["trade_date"]) for bar in untruncated[path_key]) == "2026-06-21"
    assert max(str(bar["trade_date"]) for bar in truncated[path_key]) == train_end

    def _timeline_end(scoped: Mapping[str, Sequence[Mapping[str, object]]]) -> str:
        result = run_portfolio_backtest(
            rows,
            list(calendar),
            variant="fixed_20d",
            exposure_rows=[{"trade_date": row["trade_date"], "exposure": 1.0} for row in calendar],
            initial_capital=100.0,
            max_positions=3,
            mode="path",
            price_paths=scoped,
        )
        return max(str(item["date"]) for item in result.equity_curve)

    # fixture 必须真的越界，否则断言空转
    assert _timeline_end(untruncated) == "2026-06-21" > train_end
    assert _timeline_end(truncated) == train_end

    # 编排侧的训练调用把 cutoff 传到了引擎：时间轴少一天、打分随之改变
    plain = runner.run(rows, sizing="risk_budget", risk_per_trade=0.005)
    cut = runner.run(
        rows,
        sizing="risk_budget",
        risk_per_trade=0.005,
        path_cutoff_date=train_end,
    )
    assert cut.sample_days == plain.sample_days - 1
    assert cut.cumulative_return != plain.cumulative_return


def _immunity_fixture() -> tuple[
    WalkForwardWindow,
    list[dict[str, object]],
    dict[str, list[dict[str, object]]],
    list[dict[str, object]],
]:
    """训练期跨到 train_end 的持仓 + train_end 之后的执行行/路径 bar。"""
    window = WalkForwardWindow(
        window_id="S1W1",
        segment_id="S1",
        train_start="2026-06-01",
        train_end="2026-07-31",
        valid_start="2026-08-01",
        valid_end="2026-09-30",
    )
    rows: list[dict[str, object]] = []
    paths: dict[str, list[dict[str, object]]] = {}

    # 训练期内、结果已兑现的持仓
    for index, (signal_date, entry_date, code, ema10, drift) in enumerate(
        (
            ("2026-05-31", "2026-06-01", "000001.SZ", 9.0, 0.01),
            ("2026-06-01", "2026-06-02", "000002.SZ", 8.0, -0.005),
            ("2026-06-02", "2026-06-03", "000003.SZ", 9.5, 0.004),
        )
    ):
        path = _engine_path(entry_date, bars=21, drift=drift)
        exit_date = str(path[19]["trade_date"])
        rows.append(
            _engine_row(
                signal_date=signal_date,
                entry_date=entry_date,
                exit_date=exit_date,
                stock_code=code,
                ema10=ema10,
                return_net=0.02 * (index + 1) - 0.03,
                rank=index + 1,
            )
        )
        paths[position_path_key(code, entry_date)] = path

    # 训练期尾部持仓：第 20/21 根 bar 停牌，未截断时路径退出会落到 train_end 之后
    tail_entry = "2026-07-11"
    tail_path = _engine_path(
        tail_entry,
        bars=26,
        drift=0.006,
        halted_dates=("2026-07-30", "2026-07-31"),
    )
    rows.append(
        _engine_row(
            signal_date="2026-07-10",
            entry_date=tail_entry,
            exit_date="2026-07-30",
            stock_code="000004.SZ",
            ema10=9.2,
            return_net=0.03,
        )
    )
    paths[position_path_key("000004.SZ", tail_entry)] = tail_path

    # 验证期（train_end 之后）的行：训练不得看见
    future_entry = "2026-08-06"
    rows.append(
        _engine_row(
            signal_date="2026-08-05",
            entry_date=future_entry,
            exit_date="2026-08-25",
            stock_code="000005.SZ",
            ema10=9.1,
            return_net=0.04,
        )
    )
    paths[position_path_key("000005.SZ", future_entry)] = _engine_path(future_entry, bars=21)

    return window, rows, paths, _calendar("2026-06-01", "2026-09-30")


def _train_scores(
    rows: Sequence[Mapping[str, object]],
    paths: Mapping[str, Sequence[Mapping[str, object]]],
    calendar: Sequence[Mapping[str, object]],
    window: WalkForwardWindow,
    *,
    cutoff: bool,
) -> tuple[dict[float, float | None], object]:
    runner = _engine_runner(paths, calendar)
    training_rows = select_training_rows(rows, window, purge=True)
    assert training_rows, "fixture 必须有可用训练行"
    scores = {
        param: score_from_metrics(
            _metrics_view(
                runner.run(
                    training_rows,
                    sizing="risk_budget",
                    risk_per_trade=param,
                    path_cutoff_date=window.train_end if cutoff else None,
                )
            ),
            objective="sharpe",
        )
        for param in ENGINE_GRID
    }
    return scores, select_parameter(scores, objective="sharpe")


def _poison(
    rows: Sequence[Mapping[str, object]],
    paths: Mapping[str, Sequence[Mapping[str, object]]],
    train_end: str,
) -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]]]:
    """篡改 train_end 之后的一切：执行行收益/ema10 与窗外路径价格。"""
    poisoned_rows = [
        dict(row, return_20d_net_adj=-9.99, ema10=0.01, entry_price=999.0)
        if str(row["signal_date"]) > train_end
        else dict(row)
        for row in rows
    ]
    poisoned_rows.append(
        _engine_row(
            signal_date="2026-09-01",
            entry_date="2026-09-02",
            exit_date="2026-09-22",
            stock_code="000009.SZ",
            ema10=0.01,
            return_net=-9.99,
        )
    )
    poisoned_paths = {
        key: [
            dict(bar, open=1_000_000.0, close=1_000_000.0, high=1_000_000.0, low=1_000_000.0)
            if str(bar["trade_date"]) > train_end
            else dict(bar)
            for bar in bars
        ]
        for key, bars in paths.items()
    }
    poisoned_paths[position_path_key("000009.SZ", "2026-09-02")] = _engine_path("2026-09-02", bars=21)
    return poisoned_rows, poisoned_paths


def test_real_engine_parameter_selection_is_immune_to_future_rows() -> None:
    """WF-4：真实引擎路径上的未来行免疫——选参与训练分数必须逐字节不变。"""
    window, rows, paths, calendar = _immunity_fixture()
    poisoned_rows, poisoned_paths = _poison(rows, paths, window.train_end)

    baseline_scores, baseline_selection = _train_scores(
        rows, paths, calendar, window, cutoff=True
    )
    poisoned_scores, poisoned_selection = _train_scores(
        poisoned_rows, poisoned_paths, calendar, window, cutoff=True
    )

    assert baseline_selection.status == "selected"
    assert repr(sorted(poisoned_scores.items())) == repr(sorted(baseline_scores.items()))
    assert poisoned_selection == baseline_selection

    # fixture 敏感性：去掉路径截断后，窗外价格确实会改变训练分数——
    # 说明上面的"不变"来自截断机制而非构造不敏感。
    leaky_baseline, _ = _train_scores(rows, paths, calendar, window, cutoff=False)
    leaky_poisoned, _ = _train_scores(
        poisoned_rows, poisoned_paths, calendar, window, cutoff=False
    )
    assert repr(sorted(leaky_poisoned.items())) != repr(sorted(leaky_baseline.items()))
