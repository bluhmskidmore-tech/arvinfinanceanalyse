"""宏观 toolkit 三个已审计确认数学错误修复的回归测试。

覆盖：
1. backtest_cn.py：收益口径统一为简单收益复利（原对数收益 log_ret 与 calc_metrics
   的 (1+r).cumprod() 简单收益复利口径混用，导致年化/夏普/Calmar/回撤/净值全线偏差）。
2. regime_switch_cn.py：波动率分位数阈值改为扩展窗口（原全样本 vol.quantile() 会用
   未来数据污染历史时点的状态标签，属前视偏差）。
3. performance_metrics_cn.py：风险平价权重改为按「资产」列 merge 读取（原按列名模糊
   匹配 + iloc[-1]，几乎总是匹配不到真实权重列而静默回落等权）。

仅测试纯函数/独立函数，不触发 akshare/Wind 网络请求：
- 三个脚本均已有 `if __name__ == "__main__":` 主流程守卫，importlib 动态加载
  （`spec.loader.exec_module`）只执行模块顶层代码（import、常量、函数定义），不会调用
  main() 从而不会触发拉数。
- backtest_cn.py 在模块顶层 `from scipy.optimize import minimize`，其在 toolkit 注册表中
  被标注为可选依赖（optional_dependencies=("matplotlib", "scipy")）。若当前测试环境未安装
  scipy，本文件会注入一个最小占位模块使其可被 import；被测函数（calc_metrics /
  run_backtest）完全不依赖 scipy.optimize.minimize，占位模块不影响断言的正确性。
"""

from __future__ import annotations

import importlib.util
import sys
import types

import numpy as np
import pandas as pd
import pytest

from backend.app.core_finance.macro.toolkit import get_toolkit_script
from backend.app.core_finance.macro.toolkit.runner import TOOLKIT_ROOT

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_macro_toolkit,
]


def _ensure_scipy_optimize_stub() -> None:
    try:
        import scipy.optimize  # noqa: F401

        return
    except ModuleNotFoundError:
        pass

    def _stub_minimize(_objective, w0, **_kwargs):
        # 最小占位实现：不做真实优化，直接回退到初始权重（等权），
        # 并标记 success=False，使 calc_rp_weights 按其既有的失败回退逻辑返回 w0。
        # 本测试文件只断言收益口径（简单收益 vs 对数收益），不断言风险平价优化结果，
        # 因此该占位不影响任何断言的正确性。
        return types.SimpleNamespace(x=np.asarray(w0), success=False)

    scipy_stub = types.ModuleType("scipy")
    optimize_stub = types.ModuleType("scipy.optimize")
    optimize_stub.minimize = _stub_minimize
    scipy_stub.optimize = optimize_stub
    sys.modules.setdefault("scipy", scipy_stub)
    sys.modules.setdefault("scipy.optimize", optimize_stub)


def _load_toolkit_script(name: str, monkeypatch: pytest.MonkeyPatch, module_alias: str):
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    script = get_toolkit_script(name)
    spec = importlib.util.spec_from_file_location(module_alias, script.path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ============================================================
# 问题1（P0）：backtest_cn.py 收益口径统一——简单收益复利
# ============================================================


def test_backtest_calc_metrics_matches_simple_return_compounding_by_hand(monkeypatch) -> None:
    """calc_metrics 本身按简单收益复利实现（(1+r).cumprod()）。这里手算期望值，
    确认其口径未被破坏；这是问题1修复的“下游一致性”基准。"""
    _ensure_scipy_optimize_stub()
    backtest_cn = _load_toolkit_script("backtest_cn", monkeypatch, "_fixed_backtest_cn_metrics")

    simple_returns = [0.02, -0.01, 0.03, -0.015]
    ret = pd.Series(simple_returns)

    expected_cum = 1.0
    for r in simple_returns:
        expected_cum *= 1 + r
    expected_total_ret = expected_cum - 1.0

    years = len(simple_returns) / 252
    expected_annual_ret = (1 + expected_total_ret) ** (1 / years) - 1

    metrics = backtest_cn.calc_metrics(ret, "测试策略")

    assert metrics["累计收益%"] == pytest.approx(round(expected_total_ret * 100, 2))
    assert metrics["年化收益%"] == pytest.approx(round(expected_annual_ret * 100, 2))


def test_backtest_run_backtest_portfolio_return_uses_simple_return_not_log_return(monkeypatch) -> None:
    """回归核心断言：run_backtest 输出的组合收益序列必须来自简单收益 pct_change()，
    而不是对数收益 log(p/p.shift(1))；否则会与 calc_metrics 的简单收益复利口径冲突。

    用两资产等权买持组合验证：因买持等权权重不变（turnover=0，交易成本恒为0），
    其每日收益应精确等于 prices.pct_change() 的等权均值。
    """
    _ensure_scipy_optimize_stub()
    backtest_cn = _load_toolkit_script("backtest_cn", monkeypatch, "_fixed_backtest_cn_runret")

    dates = pd.bdate_range("2024-01-01", periods=140)
    rng = np.random.default_rng(42)
    price = 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, size=len(dates)))
    prices = pd.DataFrame({"hs300": price, "csi500": price * 1.01}, index=dates)

    ret_df, _regime_series = backtest_cn.run_backtest(prices)

    simple_ret = prices.pct_change()
    log_ret = np.log(prices / prices.shift(1))

    bh = ret_df["买持等权"]
    expected_simple = simple_ret.mean(axis=1).reindex(bh.index)
    expected_log = log_ret.mean(axis=1).reindex(bh.index)

    pd.testing.assert_series_equal(bh, expected_simple, check_names=False)
    # 反证：若未修复（仍用对数收益），两者会有实质性差异；确保测试有区分力。
    assert (bh - expected_log).abs().max() > 1e-6


# ============================================================
# 问题2（P0）：regime_switch_cn.py 波动率分位数改为扩展窗口，消除前视偏差
# ============================================================


def _build_two_regime_price_series(n_low: int = 200, n_high: int = 200, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    low_vol_ret = rng.normal(0.0002, 0.003, size=n_low)
    high_vol_ret = rng.normal(0.0002, 0.05, size=n_high)
    rets = np.concatenate([low_vol_ret, high_vol_ret])
    price = 100 * np.cumprod(1 + rets)
    dates = pd.bdate_range("2015-01-01", periods=len(rets))
    return pd.Series(price, index=dates)


def test_regime_classification_of_past_unaffected_by_future_high_vol_data(monkeypatch) -> None:
    """核心断言：前半段（低波动）的状态标签，在截断样本（只含前半段）与全样本
    （前半段+后半段高波动）下必须一致。若仍用全样本 vol.quantile()（旧实现），
    后半段的高波动会拉高历史分位数阈值，导致前半段的“高波动”判定结果发生变化，
    即前视偏差；扩展窗口分位数（新实现）应使前半段标签与是否追加未来数据无关。
    """
    regime_switch_cn = _load_toolkit_script("regime_switch_cn", monkeypatch, "_fixed_regime_switch_cn")

    n_low = 200
    full_price = _build_two_regime_price_series(n_low=n_low, n_high=200)
    truncated_price = full_price.iloc[:n_low]

    full_regime = regime_switch_cn.compute_regime(full_price)
    truncated_regime = regime_switch_cn.compute_regime(truncated_price)

    front_full = full_regime["regime"].iloc[:n_low]
    front_truncated = truncated_regime["regime"]

    # 扩展窗口 min_periods=60，之前的点应统一为"未知"，从有效样本区间开始对比。
    warmup = 60
    assert front_full.iloc[warmup:].equals(front_truncated.iloc[warmup:])

    # 前半段应确实产生过有效分类（非全部"未知"），否则该测试无法反映真实场景。
    assert (front_truncated.iloc[warmup:] != "未知").any()


def test_regime_pre_warmup_points_marked_unknown_instead_of_hard_classified(monkeypatch) -> None:
    """min_periods 之前样本不足时应标记为"未知"，而不是套用不可靠的分位数硬分类。"""
    regime_switch_cn = _load_toolkit_script(
        "regime_switch_cn", monkeypatch, "_fixed_regime_switch_cn_warmup"
    )

    price = _build_two_regime_price_series(n_low=80, n_high=0, seed=3)
    regime_df = regime_switch_cn.compute_regime(price)

    # vol_window=20/hurst_window=60 warmup 之前必为 NaN/未知；min_periods=60 前也应为"未知"。
    assert (regime_df["regime"].iloc[:60] == "未知").all()


# ============================================================
# 问题3（P0）：performance_metrics_cn.py 按「资产」列 merge 读取风险平价权重
# ============================================================


def test_performance_metrics_reads_risk_parity_weights_by_asset_column_not_equal_weight(
    tmp_path, monkeypatch
) -> None:
    """构造符合 risk_parity_cn.py 真实输出格式的长表 CSV（每资产一行，
    列含「资产」「风险平价权重%」及其它无关列），断言 load_risk_parity_weights
    解析出的权重与 CSV 一致，而不是回落等权。"""
    performance_metrics_cn = _load_toolkit_script(
        "performance_metrics_cn", monkeypatch, "_fixed_performance_metrics_cn"
    )

    asset_names = ["沪深300", "中证500", "黄金期货", "铜期货", "原油期货"]
    weights_pct = [30.0, 20.0, 25.0, 15.0, 10.0]

    rp_df = pd.DataFrame(
        {
            "资产": asset_names,
            "风险平价权重%": weights_pct,
            "风险预算权重%": [22.0, 18.0, 20.0, 15.0, 25.0],  # 模拟真实长表中的其它权重列
            "风险平价贡献%": [20.0] * 5,
            "年化波动率%": [12.0, 18.0, 10.0, 22.0, 30.0],
        }
    )
    rp_csv_path = tmp_path / "risk_parity_results.csv"
    rp_df.to_csv(rp_csv_path, index=False, encoding="utf-8-sig")

    eq_w = np.ones(len(asset_names)) / len(asset_names)
    rp_w, rp_label = performance_metrics_cn.load_risk_parity_weights(
        str(rp_csv_path), asset_names, eq_w
    )

    expected = np.array(weights_pct) / 100.0
    np.testing.assert_allclose(rp_w, expected)
    assert rp_label == "风险平价组合"
    # 反证：不应等于等权兜底，说明确实解析出了真实权重。
    assert not np.allclose(rp_w, eq_w)


def test_performance_metrics_falls_back_to_equal_weight_with_warning_when_csv_missing(
    tmp_path, monkeypatch, capsys
) -> None:
    """CSV 不存在时应回落等权并打印明确警告（不是静默回落）。"""
    performance_metrics_cn = _load_toolkit_script(
        "performance_metrics_cn", monkeypatch, "_fixed_performance_metrics_cn_missing"
    )

    asset_names = ["沪深300", "中证500"]
    eq_w = np.ones(len(asset_names)) / len(asset_names)
    missing_path = str(tmp_path / "does_not_exist.csv")

    rp_w, rp_label = performance_metrics_cn.load_risk_parity_weights(missing_path, asset_names, eq_w)

    np.testing.assert_allclose(rp_w, eq_w)
    assert rp_label == "风险平价(等权替代)"
    captured = capsys.readouterr()
    assert "警告" in captured.out


def test_performance_metrics_falls_back_when_csv_missing_asset(tmp_path, monkeypatch, capsys) -> None:
    """CSV 存在但缺少某个资产的权重行时，应回落等权并给出明确警告，而不是
    用部分匹配的权重继续计算。"""
    performance_metrics_cn = _load_toolkit_script(
        "performance_metrics_cn", monkeypatch, "_fixed_performance_metrics_cn_partial"
    )

    asset_names = ["沪深300", "中证500", "黄金期货"]
    rp_df = pd.DataFrame(
        {
            "资产": ["沪深300", "中证500"],  # 缺黄金期货
            "风险平价权重%": [60.0, 40.0],
        }
    )
    rp_csv_path = tmp_path / "risk_parity_results.csv"
    rp_df.to_csv(rp_csv_path, index=False, encoding="utf-8-sig")

    eq_w = np.ones(len(asset_names)) / len(asset_names)
    rp_w, rp_label = performance_metrics_cn.load_risk_parity_weights(
        str(rp_csv_path), asset_names, eq_w
    )

    np.testing.assert_allclose(rp_w, eq_w)
    assert rp_label == "风险平价(等权替代)"
    captured = capsys.readouterr()
    assert "警告" in captured.out
