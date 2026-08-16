"""模型一（GARCH 波动率预测，仅观察口径）审计修复的回归测试。

被测脚本: backend/app/core_finance/macro/toolkit/scripts/garch_multi_asset.py

对应审计修复：
1. 波动率状态阈值改为尽调笔记的绝对年化阈值：低波动(<15%) / 中波动(15%-30%) /
   高波动(>30%)，并映射笔记的策略建议。原实现用资产自身条件波动率历史分位数
   (25/75/90) 分段，导致 gold 年化 24.13% 被标"高波动"、copper 11.65% 被标"中波动"。
2. 持久性按模型族计算：EGARCH 取 log 方差 AR 系数 beta；GARCH/GJR/TARCH 取
   alpha+beta+0.5*gamma。原实现对 EGARCH 也用 alpha+beta+0.5*gamma，
   gold (EGARCH/t) 持久性被虚报为 1.2865（真实平稳性度量应为 beta=0.9669）。
3. 新增笔记参数约束校验：omega>0, alpha>=0, beta>=0, 持久性<1；
   EGARCH 参数在 log 方差空间，omega/alpha 允许为负，仅要求 |beta|<1。
4. TARCH 菜单项改为真正的 power=1 绝对值形式；原实现与 GJR-GARCH 规格完全相同，
   BIC 选优菜单中同一模型被重复拟合、标签失真。
5. 样本外滚动预测在两次参数重估之间改用固定参数 + 最新数据逐日更新条件方差；
   原实现 20 天内重复输出同一预测值（不随新收益更新），扭曲样本外相关性。

仅测试纯函数与模型构建接线，不拉取行情数据：脚本有 `if __name__ == '__main__'`
守卫，exec_module 只执行顶层定义，不会调用 main()。
"""

from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest

from backend.app.core_finance.macro.toolkit import get_toolkit_script
from backend.app.core_finance.macro.toolkit.runner import TOOLKIT_ROOT


def _load_garch_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    script = get_toolkit_script("garch_multi_asset")
    spec = importlib.util.spec_from_file_location("garch_multi_asset_under_test", script.path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def garch_mod(monkeypatch: pytest.MonkeyPatch):
    return _load_garch_module(monkeypatch)


# ============================================================
# 修复1：波动率状态按笔记绝对年化阈值 15% / 30%
# ============================================================


def test_classify_vol_regime_matches_note_thresholds(garch_mod):
    # 2026-08-11 产物中的真实年化波动率样本（%）
    assert garch_mod.classify_vol_regime(11.645080)[0] == "低波动"  # copper（原被误标"中波动"）
    assert garch_mod.classify_vol_regime(15.378212)[0] == "中波动"  # hs300
    assert garch_mod.classify_vol_regime(24.131066)[0] == "中波动"  # gold（原被误标"高波动"）
    assert garch_mod.classify_vol_regime(24.274619)[0] == "中波动"  # csi500
    assert garch_mod.classify_vol_regime(63.491167)[0] == "高波动"  # crude_oil


def test_classify_vol_regime_boundary_semantics(garch_mod):
    # 笔记定义：低(<15) / 中(15-30) / 高(>30)，边界 15 与 30 归中波动
    assert garch_mod.classify_vol_regime(14.999)[0] == "低波动"
    assert garch_mod.classify_vol_regime(15.0)[0] == "中波动"
    assert garch_mod.classify_vol_regime(30.0)[0] == "中波动"
    assert garch_mod.classify_vol_regime(30.001)[0] == "高波动"


def test_classify_vol_regime_actions_follow_note_strategies(garch_mod):
    low_action = garch_mod.classify_vol_regime(10.0)[1]
    mid_action = garch_mod.classify_vol_regime(20.0)[1]
    high_action = garch_mod.classify_vol_regime(40.0)[1]
    assert "卖权" in low_action and "均值回归" in low_action
    assert "趋势跟踪" in mid_action and "风险平价" in mid_action
    assert "CTA" in high_action and "尾部对冲" in high_action and "降仓" in high_action


# ============================================================
# 修复2：持久性按模型族计算
# ============================================================


def test_persistence_is_model_aware(garch_mod):
    garch_params = {"alpha[1]": 0.213562, "beta[1]": 0.652895, "gamma[1]": 0.0}
    assert garch_mod.compute_persistence("GARCH", garch_params) == pytest.approx(0.866457, abs=1e-6)

    gjr_params = {"alpha[1]": 0.180679, "beta[1]": 0.873244, "gamma[1]": -0.142396}
    assert garch_mod.compute_persistence("GJR-GARCH", gjr_params) == pytest.approx(0.982725, abs=1e-6)

    # gold (EGARCH/t) 回归样本：持久性应为 beta=0.9669，而不是旧口径的
    # alpha+beta+0.5*gamma = 0.2754+0.9669+0.5*0.0883 ≈ 1.2865
    egarch_params = {"alpha[1]": 0.275416, "beta[1]": 0.966915, "gamma[1]": 0.088337}
    assert garch_mod.compute_persistence("EGARCH", egarch_params) == pytest.approx(0.966915, abs=1e-6)
    assert garch_mod.compute_persistence("EGARCH", egarch_params) < 1.0


# ============================================================
# 修复3：笔记参数约束校验
# ============================================================


def test_check_constraints_garch_family(garch_mod):
    ok = {"omega": 0.1, "alpha[1]": 0.1, "beta[1]": 0.85, "gamma[1]": 0.0}
    assert garch_mod.check_constraints("GARCH", ok, 0.95) == "通过"

    nonstationary = {"omega": 0.1, "alpha[1]": 0.2, "beta[1]": 0.85, "gamma[1]": 0.0}
    assert "持久性>=1" in garch_mod.check_constraints("GARCH", nonstationary, 1.05)

    bad_omega = {"omega": 0.0, "alpha[1]": 0.1, "beta[1]": 0.8, "gamma[1]": 0.0}
    assert "omega<=0" in garch_mod.check_constraints("GARCH", bad_omega, 0.9)

    bad_alpha = {"omega": 0.1, "alpha[1]": -0.01, "beta[1]": 0.8, "gamma[1]": 0.0}
    assert "alpha<0" in garch_mod.check_constraints("GARCH", bad_alpha, 0.79)

    # crude_oil (GJR/t) 回归样本：gamma<0 但 alpha+gamma>=0 且持久性<1，应通过
    crude = {"omega": 0.154445, "alpha[1]": 0.180679, "beta[1]": 0.873244, "gamma[1]": -0.142396}
    assert garch_mod.check_constraints("GJR-GARCH", crude, 0.982725) == "通过"

    neg_arch = {"omega": 0.1, "alpha[1]": 0.05, "beta[1]": 0.8, "gamma[1]": -0.1}
    assert "alpha+gamma<0" in garch_mod.check_constraints("GJR-GARCH", neg_arch, 0.8)


def test_check_constraints_egarch_log_space(garch_mod):
    # EGARCH 的 omega/alpha 在 log 方差空间可为负，属合法参数
    legal = {"omega": -0.05, "alpha[1]": 0.2, "beta[1]": 0.97}
    assert garch_mod.check_constraints("EGARCH", legal, 0.97) == "通过"

    explosive = {"omega": 0.05, "alpha[1]": 0.2, "beta[1]": 1.01}
    assert "|beta|>=1" in garch_mod.check_constraints("EGARCH", explosive, 1.01)


# ============================================================
# 修复4：TARCH 菜单项为真正的 power=1 形式，区别于 GJR-GARCH
# ============================================================


def test_tarch_menu_entry_is_true_power_one(garch_mod):
    assert garch_mod.MODELS["TARCH"].get("power") == 1.0
    assert "power" not in garch_mod.MODELS["GJR-GARCH"]

    r = pd.Series(
        np.random.default_rng(0).standard_normal(60),
        index=pd.date_range("2024-01-01", periods=60),
    )
    tarch = garch_mod._build_arch_model(r, garch_mod.MODELS["TARCH"], "normal")
    gjr = garch_mod._build_arch_model(r, garch_mod.MODELS["GJR-GARCH"], "normal")
    assert tarch.volatility.power == 1.0
    assert gjr.volatility.power == 2.0


# ============================================================
# 修复5：固定参数 + 最新数据的逐日条件方差更新机制
# ============================================================


def _simulate_garch_returns(n: int, omega: float = 0.1, alpha: float = 0.2, beta: float = 0.75) -> pd.Series:
    rng = np.random.default_rng(42)
    z = rng.standard_normal(n)
    var = np.empty(n)
    ret = np.empty(n)
    var[0] = omega / (1.0 - alpha - beta)
    ret[0] = np.sqrt(var[0]) * z[0]
    for t in range(1, n):
        var[t] = omega + alpha * ret[t - 1] ** 2 + beta * var[t - 1]
        ret[t] = np.sqrt(var[t]) * z[t]
    return pd.Series(ret, index=pd.date_range("2020-01-01", periods=n, freq="D"))


def test_fixed_param_forecast_updates_with_new_data(garch_mod):
    """样本外修复的核心机制：参数固定时，一步预测必须随最新收益更新。

    旧实现在两次重估之间重复输出同一预测值；新实现用 model.fix(params) 在
    最新数据上过滤条件方差，因此对刚发生的大冲击必须立即反应。
    """
    returns = _simulate_garch_returns(500)
    vol_params = garch_mod.MODELS["GARCH"]
    fitted = garch_mod._build_arch_model(returns.iloc[:450], vol_params, "normal").fit(
        disp="off", show_warning=False
    )
    assert float(fitted.params["alpha[1]"]) > 0.01  # 确认拟合出真实的 ARCH 反应系数

    calm = returns.copy()
    calm.iloc[479] = 0.0
    shocked = returns.copy()
    shocked.iloc[479] = 8.0 * float(returns.std())

    def one_step_var(series: pd.Series) -> float:
        fixed = garch_mod._build_arch_model(series.iloc[:480], vol_params, "normal").fix(fitted.params)
        return float(fixed.forecast(horizon=1).variance.values[-1, 0])

    var_calm = one_step_var(calm)
    var_shocked = one_step_var(shocked)
    assert var_shocked > var_calm * 1.5
