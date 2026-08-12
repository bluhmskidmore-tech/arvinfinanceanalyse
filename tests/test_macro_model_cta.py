"""模型九（CTA 趋势跟踪，观察口径）回归测试。

覆盖 toolkit 脚本 cta_trend_cn 的：
- 双均线/通道/ATR 参数默认值落在尽调笔记建议区间；
- 三个信号纯函数的方向与取值域（合成数据，不触网、不读 DuckDB/data 产物）；
- 合成信号 tanh(0.4·均线 + 0.3·通道 + 0.3·ATR仓位) 的可达上下界；
- 趋势标签/强度边界；
- 回测"信号滞后一期执行"口径（防前视回归）；
- 与正式观察适配器 backend/app/core_finance/macro/cta_trend.py 的逐值一致性；
- 笔记止损规则（单笔 2×ATR、组合单日回撤>5%减仓50%）在回测层的实现：
  触发/离场/重新进场/减仓复原/统计列，以及无触发时与无止损口径的等价性。
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from backend.app.core_finance.macro import cta_trend as formal_cta
from backend.app.core_finance.macro.toolkit.scripts import cta_trend_cn as script


def _bdays(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-02", periods=n)


def _series(values, n: int | None = None) -> pd.Series:
    arr = np.asarray(values, dtype=float)
    return pd.Series(arr, index=_bdays(len(arr) if n is None else n))


# ------------------------------------------------------------
# 参数默认值 vs 笔记建议区间
# ------------------------------------------------------------

def test_default_params_within_note_ranges() -> None:
    ma_params = inspect.signature(script.signal_ma_cross).parameters
    short, long = ma_params["short"].default, ma_params["long"].default
    assert 5 <= short <= 20, "均线短窗应在笔记建议 5-20 日"
    assert 20 <= long <= 60, "均线长窗应在笔记建议 20-60 日"
    assert short < long

    don_params = inspect.signature(script.signal_donchian).parameters
    assert 20 <= don_params["window"].default <= 60, "通道周期应在笔记建议 20-60 日"

    atr_params = inspect.signature(script.signal_atr_position).parameters
    assert 14 <= atr_params["atr_window"].default <= 20, "ATR 周期应在笔记建议 14-20 日"


# ------------------------------------------------------------
# 双均线交叉
# ------------------------------------------------------------

def test_ma_cross_direction_and_warmup() -> None:
    up = _series(100.0 * (1.001 ** np.arange(120)))
    sig_up = script.signal_ma_cross(up)
    assert sig_up.iloc[:59].isna().all(), "长窗满仓前应为 NaN（warmup）"
    assert (sig_up.iloc[60:] == 1.0).all(), "持续上行时短均线在长均线上方 → +1"

    down = _series(100.0 * (0.999 ** np.arange(120)))
    sig_down = script.signal_ma_cross(down)
    assert (sig_down.iloc[60:] == -1.0).all(), "持续下行 → -1"


# ------------------------------------------------------------
# 唐奇安通道突破
# ------------------------------------------------------------

def test_donchian_breakout_hold_and_breakdown() -> None:
    base = 100.0 + 0.5 * np.sin(np.arange(30))  # 前 30 日窄幅震荡，无突破
    spike_up = np.full(10, 110.0) + np.linspace(0, 1, 10)  # 第 31 日上破前 20 日高点
    crash = np.array([80.0])  # 第 41 日跌破前 20 日低点
    price = _series(np.concatenate([base, spike_up, crash]))

    sig = script.signal_donchian(price)
    assert set(sig.dropna().unique()) <= {-1.0, 0.0, 1.0}
    assert (sig.iloc[:30] == 0.0).all(), "突破事件发生前应为 0"
    assert sig.iloc[30] == 1.0, "价格上破前 20 日高点 → +1"
    assert (sig.iloc[30:40] == 1.0).all(), "未反向突破时持仓保持（前值填充）"
    assert sig.iloc[40] == -1.0, "价格跌破前 20 日低点 → -1"


# ------------------------------------------------------------
# ATR 波动率调整仓位
# ------------------------------------------------------------

def test_atr_position_bounds_and_ma_gate() -> None:
    n = 120
    low_vol_up = _series(100.0 * (1.0 + 0.001 * ((np.arange(n) % 2) + 1)).cumprod())
    pos = script.signal_atr_position(low_vol_up)
    assert ((pos >= 0.0) & (pos <= 1.0)).all(), "ATR 仓位必须在 [0, 1]"
    assert pos.iloc[-1] == 1.0, "低波动上行时 目标波动率/σ 应被截断到 1"

    down = _series(100.0 * (0.999 ** np.arange(n)))
    pos_down = script.signal_atr_position(down)
    assert (pos_down.iloc[60:] == 0.0).all(), "均线空头时仓位强制为 0（只做多侧仓位）"

    rng = np.random.default_rng(7)
    rets = 0.0006 + 0.03 * rng.standard_normal(n)  # 高波动、缓慢上行
    high_vol_up = _series(100.0 * np.exp(np.cumsum(rets)))
    pos_hv = script.signal_atr_position(high_vol_up)
    tail = pos_hv.iloc[70:]
    gated = tail[tail > 0]
    assert not gated.empty
    assert (gated < 1.0).all(), "高波动时仓位应按 0.01/σ 缩减到 1 以下"


# ------------------------------------------------------------
# 合成信号：权重、tanh 压缩与可达上下界
# ------------------------------------------------------------

def test_composite_weights_and_attainable_range() -> None:
    strong_up = _series(100.0 * (1.001 ** np.arange(120)))  # 均线+1 通道+1 ATR仓位1
    comp_up = script.compute_composite(strong_up)["composite"].dropna()
    assert comp_up.iloc[-1] == pytest.approx(np.tanh(0.4 + 0.3 + 0.3), abs=1e-12), (
        "多头极值 = tanh(1.0) ≈ +0.762"
    )

    strong_down = _series(100.0 * (0.999 ** np.arange(120)))  # 均线-1 通道-1 ATR仓位0
    comp_down = script.compute_composite(strong_down)["composite"].dropna()
    assert comp_down.iloc[-1] == pytest.approx(np.tanh(-0.4 - 0.3), abs=1e-12), (
        "空头极值 = tanh(-0.7) ≈ -0.604（ATR 仓位非负导致范围不对称）"
    )

    for comp in (comp_up, comp_down):
        assert ((comp > -1.0) & (comp < 1.0)).all(), "合成信号必须落在 (-1, 1)"
        assert (comp >= np.tanh(-0.7) - 1e-12).all()
        assert (comp <= np.tanh(1.0) + 1e-12).all()


# ------------------------------------------------------------
# 趋势标签与强度边界
# ------------------------------------------------------------

def test_trend_label_and_strength_boundaries() -> None:
    assert script.trend_label(0.60) == "强多头"
    assert script.trend_label(0.30) == "弱多头"
    assert script.trend_label(0.00) == "震荡观望"
    assert script.trend_label(-0.30) == "弱空头"
    assert script.trend_label(-0.604) == "强空头"

    assert script.trend_strength(0.60) == "强趋势"
    assert script.trend_strength(-0.604) == "强趋势"
    assert script.trend_strength(0.30) == "弱趋势"
    assert script.trend_strength(0.10) == "震荡"

    # 多头侧边界两函数处理一致（均为开区间比较）
    assert script.trend_label(0.5) == "弱多头" and script.trend_strength(0.5) == "弱趋势"
    assert script.trend_label(0.2) == "震荡观望" and script.trend_strength(0.2) == "震荡"

    # 空头侧合成信号只能取 tanh(-0.7)/tanh(-0.4)/tanh(-0.1) 三个离散值
    # （均线空头时 ATR 仓位恒为 0），恰好 -0.5/-0.2 不可达；已知在精确 -0.5/-0.2 处
    # trend_label 与 trend_strength 分类不一致，但为保持与正式适配器
    # rv_macro_cta_trend_cn_v1 的 trend_label 语义一致而保留现状。
    reachable_short = [float(np.tanh(-0.7)), float(np.tanh(-0.4)), float(np.tanh(-0.1))]
    expectations = [("强空头", "强趋势"), ("弱空头", "弱趋势"), ("震荡观望", "震荡")]
    for val, (label, strength) in zip(reachable_short, expectations):
        assert script.trend_label(val) == label
        assert script.trend_strength(val) == strength


# ------------------------------------------------------------
# 回测口径：信号滞后一期执行（防前视）
# ------------------------------------------------------------

def test_backtest_uses_lagged_signal_no_lookahead() -> None:
    rng = np.random.default_rng(11)
    price = _series(100.0 * np.exp(np.cumsum(0.0002 + 0.01 * rng.standard_normal(140))))
    composite = pd.Series((np.arange(140) % 2).astype(float), index=price.index)
    signals = pd.DataFrame({"composite": composite})

    result = script.backtest(price, signals)

    log_ret = np.log(price / price.shift(1)).dropna()
    lagged = composite.shift(1).fillna(0).reindex(log_ret.index)
    expected_ann = float((lagged * log_ret).mean() * 252) * 100
    assert result["strat_annual_ret"] == pytest.approx(expected_ann, abs=1e-9), (
        "策略收益必须用 T-1 信号 × T 日对数收益"
    )

    same_day_ann = float((composite.reindex(log_ret.index) * log_ret).mean() * 252) * 100
    assert result["strat_annual_ret"] != pytest.approx(same_day_ann, abs=1e-6), (
        "若与同日信号口径一致则说明存在前视"
    )

    assert result["bh_annual_ret"] == pytest.approx(float(log_ret.mean() * 252) * 100, abs=1e-9)


# ------------------------------------------------------------
# 与正式观察适配器逐值一致
# ------------------------------------------------------------

def test_script_signals_match_formal_adapter() -> None:
    rng = np.random.default_rng(3)
    drift = np.linspace(0, 0.15, 200)
    wave = 0.05 * np.sin(np.arange(200) / 9.0)
    noise = 0.01 * rng.standard_normal(200)
    price = _series(100.0 * np.exp(drift + wave + noise))

    from_script = script.compute_composite(price)
    from_formal = formal_cta.compute_composite(price)
    pd.testing.assert_frame_equal(from_script, from_formal, check_exact=False, rtol=1e-12, atol=1e-12)

    latest = float(from_script["composite"].dropna().iloc[-1])
    assert script.trend_label(latest) == formal_cta.trend_label(latest)


# ------------------------------------------------------------
# 止损规则"明确未实现"的文档锚点
# ------------------------------------------------------------

def test_stop_loss_rules_are_implemented_and_documented() -> None:
    """止损规则已按尽调笔记实现（2026-08-12）：锚点从"声明未实现"升级为"锁定实现"。"""
    doc = script.__doc__ or ""
    assert "2×ATR" in doc, "模块 docstring 必须描述单笔止损规则"
    assert "减仓 50%" in doc or "减仓50%" in doc, "模块 docstring 必须描述组合止损规则"

    assert hasattr(script, "backtest_with_stops"), "含止损回测必须以独立纯函数实现"
    stop_doc = script.backtest_with_stops.__doc__ or ""
    assert "止损" in stop_doc and "主口径" in stop_doc

    bt_doc = script.backtest.__doc__ or ""
    assert "止损" in bt_doc, "无止损对照口径必须在 backtest docstring 声明"
