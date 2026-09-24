"""模型七（再平衡策略 rebalance_cn.py）NaN 传播 bug 的回归测试。

生产 bug（2026-08-11 产物）：DuckDB 中商品期货序列（gold/copper/crude_oil）的
起始日期晚于股指（前导缺失），直接 concat 的价格面板前段含 NaN。权重递推
``new_val / new_val.sum()`` 在首个含 NaN 的交易日整行变 NaN 并传播到整个回测期：

- 时间再平衡（月度/季度）：换手率 ``|target - drifted_w|`` 为 NaN → 总成本 /
  净收益 / 年化收益 / 波动 / 累计全为 NaN（夏普因 ``NaN > 0`` 为 False 落到 0.0，
  再平衡次数 ``len(turnover)`` 不受影响，故 CSV 呈现"有次数但指标全空"）。
- 阈值再平衡：偏离比较 ``NaN > threshold`` 恒为 False → 永不触发，
  产物与"不再平衡"行完全一致。
- 不再平衡：组合日收益 ``(ret * weights.shift(1)).sum(axis=1)`` 被 pandas
  skipna 吃成几乎全 0 → 波动坍缩到 0.09% 量级，夏普 ≈ (0 - 1.5%) / 0.086% ≈ -18。

修复：新增 ``align_prices``（前值填充中途/尾部缺口 + 丢弃前导缺失行），
``load_prices`` 在三年窗口截取后调用，使回测窗口收敛到共同可用区间。

本文件用合成小样本 DataFrame 直接测脚本内函数，不触发 akshare/DuckDB 拉数：
rebalance_cn.py 有 ``if __name__ == "__main__":`` 主流程守卫，importlib 动态加载
只执行模块顶层定义，不会调用 main()。
"""

from __future__ import annotations

import importlib.util
import math

import numpy as np
import pandas as pd
import pytest

from backend.app.core_finance.macro.toolkit import get_toolkit_script
from backend.app.core_finance.macro.toolkit.runner import TOOLKIT_ROOT

TARGET_WEIGHTS = {"hs300": 0.6, "gold": 0.4}
METRIC_FIELDS = ("年化收益%", "年化波动%", "夏普比率", "平均换手率%", "总交易成本%", "累计收益%")


def _load_rebalance_module(monkeypatch: pytest.MonkeyPatch, module_alias: str):
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    script = get_toolkit_script("rebalance_cn")
    spec = importlib.util.spec_from_file_location(module_alias, script.path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_panel(n_days: int = 160, seed: int = 11) -> pd.DataFrame:
    """两资产合成价格面板（无缺失），日收益量级 ~1%。"""
    dates = pd.bdate_range("2024-01-02", periods=n_days)
    rng = np.random.default_rng(seed)
    hs300 = 100.0 * np.cumprod(1 + rng.normal(0.0004, 0.010, n_days))
    gold = 50.0 * np.cumprod(1 + rng.normal(0.0002, 0.012, n_days))
    return pd.DataFrame({"hs300": hs300, "gold": gold}, index=dates)


def _panel_with_leading_gap(n_days: int = 160, gap: int = 60) -> pd.DataFrame:
    """复现生产形态：一列（商品）前 ``gap`` 个交易日为 NaN（序列起始晚于股指）。"""
    prices = _synthetic_panel(n_days=n_days)
    prices.iloc[:gap, prices.columns.get_loc("gold")] = np.nan
    return prices


# ============================================================
# align_prices：日历对齐本体
# ============================================================


def test_align_prices_drops_leading_gap_and_ffills_interior_and_tail(monkeypatch) -> None:
    """前导缺失整行丢弃（窗口收敛到共同可用区间）；中途/尾部缺口前值填充。"""
    rebalance_cn = _load_rebalance_module(monkeypatch, "_rebalance_cn_align")

    prices = _panel_with_leading_gap(n_days=120, gap=30)
    interior_pos = 60
    prices.iloc[interior_pos, prices.columns.get_loc("hs300")] = np.nan  # 中途单日停牌
    prices.iloc[-1, prices.columns.get_loc("gold")] = np.nan  # 尾部未更新

    aligned = rebalance_cn.align_prices(prices)

    assert aligned.notna().all().all()
    # 前导缺失行被丢弃：起点 = gold 首个有效日
    assert aligned.index[0] == prices.index[30]
    assert len(aligned) == 120 - 30
    # 中途缺口沿用最近收盘价
    assert aligned.iloc[interior_pos - 30]["hs300"] == prices.iloc[interior_pos - 1]["hs300"]
    # 尾部缺口沿用最近收盘价
    assert aligned.iloc[-1]["gold"] == prices.iloc[-2]["gold"]


# ============================================================
# 核心回归：前导缺失面板经对齐后，全管线指标必须有限且量级合理
# ============================================================


def test_aligned_pipeline_produces_finite_percent_magnitude_metrics(monkeypatch) -> None:
    """生产 NaN 场景的端到端回归：含前导缺失的面板，经 align_prices 后跑
    月度再平衡 → 组合收益 → 绩效评估，所有指标字段必须有限，且年化收益/波动
    为百分数量级、夏普落在 [-5, 5] 合理区间。"""
    rebalance_cn = _load_rebalance_module(monkeypatch, "_rebalance_cn_pipeline")

    raw = _panel_with_leading_gap(n_days=160, gap=60)
    aligned = rebalance_cn.align_prices(raw)

    weights, rebal_dates, turnover = rebalance_cn.rebalance_time(
        aligned, TARGET_WEIGHTS, freq="M"
    )
    assert weights.notna().all().all()
    assert all(math.isfinite(t) for t in turnover)

    port_ret = rebalance_cn.calculate_portfolio_return(aligned, weights)
    assert port_ret.notna().all()

    metrics = rebalance_cn.evaluate_strategy(port_ret, turnover, "月度再平衡")
    for field in METRIC_FIELDS:
        assert math.isfinite(metrics[field]), f"{field} 应为有限数值，实际 {metrics[field]}"

    assert metrics["再平衡次数"] == len(rebal_dates) > 0
    # 日波动 ~1% 的合成数据，年化波动应为百分数量级（而不是坍缩到 <1%）
    assert 3.0 < metrics["年化波动%"] < 40.0
    assert -5.0 < metrics["夏普比率"] < 5.0


def test_unaligned_leading_gap_reproduces_nan_metrics_mechanism(monkeypatch) -> None:
    """反证（区分力）：不经 align_prices 直接喂含前导缺失的面板，权重递推变 NaN、
    时间再平衡换手率为 NaN、绩效指标为 NaN——正是修复前生产产物的形态。
    若未来有人加固 rebalance_time 内部的 NaN 处理，本测试会失败以提示同步更新。"""
    rebalance_cn = _load_rebalance_module(monkeypatch, "_rebalance_cn_unaligned")

    raw = _panel_with_leading_gap(n_days=160, gap=60)

    weights, _dates, turnover = rebalance_cn.rebalance_time(raw, TARGET_WEIGHTS, freq="M")
    assert weights.isna().any().any()
    assert any(math.isnan(t) for t in turnover)

    port_ret = rebalance_cn.calculate_portfolio_return(raw, weights)
    metrics = rebalance_cn.evaluate_strategy(port_ret, turnover, "月度再平衡")
    assert math.isnan(metrics["年化收益%"])
    assert math.isnan(metrics["总交易成本%"])

    # 阈值触发：NaN > threshold 恒为 False → 一次都不触发
    _w, threshold_dates, _t = rebalance_cn.rebalance_threshold(raw, TARGET_WEIGHTS, 0.05)
    assert len(threshold_dates) == 0


# ============================================================
# 时间再平衡：触发次数与窗口自洽、再平衡日回到目标权重
# ============================================================


def test_rebalance_time_counts_match_calendar_window(monkeypatch) -> None:
    """2024-01-02 ~ 2024-12-31 整年窗口：月度应触发 11 次（2 月~12 月各首个交易日），
    季度应触发 3 次（Q2/Q3/Q4 首个交易日）；再平衡日权重必须重置回目标权重。"""
    rebalance_cn = _load_rebalance_module(monkeypatch, "_rebalance_cn_counts")

    dates = pd.bdate_range("2024-01-02", "2024-12-31")
    rng = np.random.default_rng(7)
    prices = pd.DataFrame(
        {
            "hs300": 100.0 * np.cumprod(1 + rng.normal(0.0003, 0.01, len(dates))),
            "gold": 50.0 * np.cumprod(1 + rng.normal(0.0002, 0.012, len(dates))),
        },
        index=dates,
    )

    w_m, dates_m, turn_m = rebalance_cn.rebalance_time(prices, TARGET_WEIGHTS, freq="M")
    assert len(dates_m) == 11
    assert all(math.isfinite(t) for t in turn_m)

    w_q, dates_q, _turn_q = rebalance_cn.rebalance_time(prices, TARGET_WEIGHTS, freq="Q")
    assert len(dates_q) == 3

    target = [TARGET_WEIGHTS[c] for c in prices.columns]
    for d in dates_m:
        np.testing.assert_allclose(w_m.loc[d].values.astype(float), target)
    for d in dates_q:
        np.testing.assert_allclose(w_q.loc[d].values.astype(float), target)


# ============================================================
# 阈值再平衡：漂移超阈值时确实触发并回到目标权重
# ============================================================


def test_rebalance_threshold_triggers_on_persistent_drift(monkeypatch) -> None:
    """构造单边强趋势（一资产 +1%/日、另一资产走平）使权重持续漂移，
    阈值 5% 应至少触发一次；触发日权重重置回目标，换手率有限且为正。"""
    rebalance_cn = _load_rebalance_module(monkeypatch, "_rebalance_cn_threshold")

    dates = pd.bdate_range("2024-01-02", periods=120)
    trend = 100.0 * np.cumprod(np.full(len(dates), 1.01))
    flat = np.full(len(dates), 50.0)
    prices = pd.DataFrame({"hs300": trend, "gold": flat}, index=dates)
    target = {"hs300": 0.5, "gold": 0.5}

    weights, trigger_dates, turnover = rebalance_cn.rebalance_threshold(prices, target, 0.05)

    assert len(trigger_dates) >= 1
    assert all(math.isfinite(t) and t > 0 for t in turnover)
    for d in trigger_dates:
        np.testing.assert_allclose(weights.loc[d].values.astype(float), [0.5, 0.5])
    assert weights.notna().all().all()


# ============================================================
# evaluate_strategy：年化/夏普/成本口径
# ============================================================


def test_evaluate_strategy_magnitudes_and_cost_accounting(monkeypatch) -> None:
    """合成日收益（σ=1%）下：年化波动应接近 1% * sqrt(252) ≈ 15.9%（百分数量级），
    夏普落在合理区间；空换手表成本为 0；给定换手表时
    总交易成本% = Σ换手 × 单边成本 0.2% × 100。"""
    rebalance_cn = _load_rebalance_module(monkeypatch, "_rebalance_cn_eval")

    rng = np.random.default_rng(23)
    ret = pd.Series(rng.normal(0.0004, 0.01, 504))

    no_rebal = rebalance_cn.evaluate_strategy(ret, [], "不再平衡")
    assert no_rebal["再平衡次数"] == 0
    assert no_rebal["总交易成本%"] == 0.0
    assert no_rebal["平均换手率%"] == 0.0
    assert 10.0 < no_rebal["年化波动%"] < 22.0
    assert -5.0 < no_rebal["夏普比率"] < 5.0
    for field in METRIC_FIELDS:
        assert math.isfinite(no_rebal[field])

    with_turnover = rebalance_cn.evaluate_strategy(ret, [0.1, 0.2], "月度再平衡")
    assert with_turnover["再平衡次数"] == 2
    assert with_turnover["总交易成本%"] == pytest.approx(0.3 * 0.002 * 100)
    assert with_turnover["平均换手率%"] == pytest.approx(15.0)
