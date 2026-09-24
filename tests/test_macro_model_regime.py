"""模型十（市场状态转换 regime_switch_cn.py）审计回归测试。

对照宏观策略尽调笔记锁定以下契约（与脚本头部注释一致，均为观察口径）：
1. 指标口径：20日滚动年化波动率（对数收益 std(ddof=1)*sqrt(252)）与 lag-1
   自相关，须与手工重算一致。
2. 状态机判定优先级与阈值（笔记二分口径的刻意扩展）：
   高波动(vol>扩展75分位) > 趋势市(AC>0.10 且 Hurst>0.55)
   > 震荡市(AC<-0.10 或 Hurst<0.45) > 弱趋势/弱震荡(±0.10 中性带按符号)；
   任一输入 NaN → 未知。
3. compute_regime 输出的逐日状态与「指标列 + 截至当日扩展分位阈值」手推
   结果一致（规则自洽、无前视）。
4. 策略映射覆盖笔记要求：震荡→均值回归、趋势→动量/突破，且全部状态有映射。
5. regime_stats 占比含"未知"（样本预热期）后合计恰为 100%，对应 CSV
   四列占比（趋势/震荡/高波动/未知）的闭合口径。

仅测试纯函数，不触发 akshare/DuckDB 拉数：importlib 动态加载只执行模块
顶层（import、常量、函数定义）；main() 有 __main__ 守卫不会执行。
"""

from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest

from backend.app.core_finance.macro.toolkit import get_toolkit_script
from backend.app.core_finance.macro.toolkit.runner import TOOLKIT_ROOT


def _load_regime_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    script = get_toolkit_script("regime_switch_cn")
    spec = importlib.util.spec_from_file_location("_audit_regime_switch_cn", script.path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _synthetic_price(n: int = 360, seed: int = 11) -> pd.Series:
    """AR(1) 正自相关收益 + 后段放大波动：保证高波动/趋势/震荡/未知均可出现。"""
    rng = np.random.default_rng(seed)
    rets = np.zeros(n)
    phi = 0.35
    for i in range(1, n):
        scale = 0.006 if i < int(n * 0.7) else 0.03
        rets[i] = phi * rets[i - 1] + rng.normal(0.0002, scale)
    price = 100.0 * np.exp(np.cumsum(rets))
    return pd.Series(price, index=pd.bdate_range("2022-01-03", periods=n))


# ============================================================
# 1. 指标口径：年化波动率与一阶自相关 vs 手工重算
# ============================================================


def test_rolling_vol_and_autocorr_match_hand_computation(monkeypatch) -> None:
    rs = _load_regime_module(monkeypatch)
    price = _synthetic_price()
    ret = np.log(price / price.shift(1))

    vol = rs.rolling_volatility(ret, 20)
    autocorr = rs.rolling_autocorr(ret, 20)

    last20 = ret.dropna().iloc[-20:]
    expected_vol = float(last20.std(ddof=1) * np.sqrt(252))
    x = last20.to_numpy()
    expected_ac = float(np.corrcoef(x[1:], x[:-1])[0, 1])

    assert float(vol.iloc[-1]) == pytest.approx(expected_vol, rel=1e-12)
    assert float(autocorr.iloc[-1]) == pytest.approx(expected_ac, rel=1e-9)


# ============================================================
# 2. 状态判定：优先级与阈值逐条核对
# ============================================================


def test_classify_regime_priority_and_thresholds(monkeypatch) -> None:
    rs = _load_regime_module(monkeypatch)
    hi = 0.20  # 模拟截至当日的扩展窗口 75 分位阈值

    # 优先级1：高波动优先于趋势条件（即使 AC/Hurst 双双满足趋势）
    assert rs.classify_regime(0.30, hi, 0.30, 0.70) == "高波动"
    # 优先级2：趋势市需要 AC>0.10 与 Hurst>0.55 双确认
    assert rs.classify_regime(0.10, hi, 0.15, 0.60) == "趋势市"
    assert rs.classify_regime(0.10, hi, 0.15, 0.50) == "弱趋势"  # Hurst 不足→退中性带
    # 优先级3：震荡市单指标即触发（AC 或 Hurst）
    assert rs.classify_regime(0.10, hi, -0.15, 0.60) == "震荡市"
    assert rs.classify_regime(0.10, hi, 0.05, 0.40) == "震荡市"
    # 优先级4：±0.10 中性带内按自相关符号细分
    assert rs.classify_regime(0.10, hi, 0.05, 0.50) == "弱趋势"
    assert rs.classify_regime(0.10, hi, -0.05, 0.50) == "弱震荡"
    # 任一输入 NaN → 未知
    assert rs.classify_regime(float("nan"), hi, 0.10, 0.50) == "未知"
    assert rs.classify_regime(0.10, hi, float("nan"), 0.50) == "未知"
    assert rs.classify_regime(0.10, hi, 0.10, float("nan")) == "未知"


# ============================================================
# 3. compute_regime 逐日规则自洽（含预热期"未知"）
# ============================================================


def test_compute_regime_rules_self_consistent_and_warmup_unknown(monkeypatch) -> None:
    rs = _load_regime_module(monkeypatch)
    price = _synthetic_price()
    reg = rs.compute_regime(price)

    thr_hi = reg["vol"].expanding(min_periods=60).quantile(0.75)

    for i in range(len(reg)):
        label = reg["regime"].iloc[i]
        if np.isnan(thr_hi.iloc[i]):
            assert label == "未知", f"第{i}日：阈值预热期应为未知"
            continue
        v = reg["vol"].iloc[i]
        ac = reg["autocorr"].iloc[i]
        h = reg["hurst"].iloc[i]
        if np.isnan(v) or np.isnan(ac) or np.isnan(h):
            expected = "未知"
        elif v > thr_hi.iloc[i]:
            expected = "高波动"
        elif ac > 0.10 and h > 0.55:
            expected = "趋势市"
        elif ac < -0.10 or h < 0.45:
            expected = "震荡市"
        elif ac > 0:
            expected = "弱趋势"
        else:
            expected = "弱震荡"
        assert label == expected, f"第{i}日：{label} != 手推 {expected}"

    labels = set(reg["regime"])
    assert "高波动" in labels  # 后段放大波动应触发高波动态
    assert "未知" in labels    # 预热期必须存在


# ============================================================
# 4. 策略建议映射对照笔记
# ============================================================


def test_strategy_mapping_matches_note_and_covers_all_states(monkeypatch) -> None:
    rs = _load_regime_module(monkeypatch)
    mapping = rs.REGIME_STRATEGY
    # 笔记：震荡市→均值回归；趋势市→动量跟踪、突破策略
    assert "均值回归" in mapping["震荡市"]
    assert ("动量" in mapping["趋势市"]) or ("趋势跟踪" in mapping["趋势市"])
    assert "防御" in mapping["高波动"]
    # 状态机全部输出值都要有策略映射（含扩展态与未知）
    assert set(mapping) >= {"趋势市", "弱趋势", "震荡市", "弱震荡", "高波动", "未知"}


# ============================================================
# 5. 占比统计闭合（CSV 四列口径）
# ============================================================


def test_regime_stats_include_unknown_and_sum_to_100(monkeypatch) -> None:
    rs = _load_regime_module(monkeypatch)
    price = _synthetic_price()
    reg = rs.compute_regime(price)

    stats = rs.regime_stats(reg["regime"])
    assert set(stats) == {"趋势市", "弱趋势", "震荡市", "弱震荡", "高波动", "未知"}
    assert sum(stats.values()) == pytest.approx(100.0, abs=1e-9)
    assert stats["未知"] > 0  # 预热期计入分母并单独披露
