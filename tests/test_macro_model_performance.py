"""模型五（夏普比率与索提诺比率绩效评估）审计回归测试。

覆盖两部分：

一、本次审计修复的缺陷（backtest_cn.py load_prices 资产入池守卫）：
- 原缺陷：债券ETF在系统源无数据时（Wind 兼容接口 404 + akshare 备用返回 0 条），
  空序列仍被加入资产池，合并后形成全 NaN 的 bond_gov 列。该列使风险平价 60 日
  滚动窗口 ``ret_win.dropna()`` 整表清空（len==0 < 20），``calc_rp_weights`` 从未
  执行，风险平价被静默钉死在等权——产物中「风险平价」与「买持等权」两行所有
  指标（含胜率、累计收益、逐年收益）完全相同；同时等权类策略含 1/6 权重的
  0 收益幽灵资产，整体收益/波动被系统性压低。
- 修复：Wind 路径与 akshare 备用路径均跳过空序列；窗口截取后全 NaN 的列剔除。

二、笔记口径锁定（防止后续改动悄悄漂移）：
- performance_metrics_cn.calc_metrics：算术年化（日均值×252）、波动 std(ddof=1)×√252、
  夏普 (R_p−R_f)/σ_p（R_f=1.5%）、索提诺分母=负收益子样本 std(ddof=1)×√252
  （目标收益取 0，即仅取 r<0 子样本；非全样本半偏差口径）、最大回撤 cumprod/cummax、
  Calmar=年化收益/|最大回撤|。
- 评级分档：sharpe>=1.0 优秀 / >=0.5 良好 / 其余 需优化（笔记原文「>1.0 优秀；
  0.5-1.0 良好；<0.5 需优化」，实现与笔记仅在 sharpe 恰等于 1.0 的零测度点归档
  不同，本测试锁定现行闭区间约定）。
- backtest_cn.calc_metrics：几何年化（CAGR），与 performance 脚本的算术年化口径
  不同属两产物既有差异；calc_annual_returns 年度分解与累计收益复利闭合。

仅测试纯函数/独立函数，不触发真实数据源：
- 脚本以 importlib 文件方式加载（非包上下文），只执行顶层定义，不调用 main()；
- load_prices 测试通过注入假 WindPy 模块与替换模块内 ak 属性，完全隔离系统源。

运行：.venv\\Scripts\\python.exe -m pytest tests/test_macro_model_performance.py -q
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

pytestmark = pytest.mark.unit

RF = 0.015
ANN = 252


def _load_toolkit_script(name: str, monkeypatch: pytest.MonkeyPatch, module_alias: str):
    monkeypatch.syspath_prepend(str(TOOLKIT_ROOT))
    script = get_toolkit_script(name)
    spec = importlib.util.spec_from_file_location(module_alias, script.path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ============================================================
# 一、performance_metrics_cn.calc_metrics 口径锁定
# ============================================================


def _sample_returns(seed: int = 20260811, n: int = 120, mu: float = 5e-4, sigma: float = 0.01) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(mu, sigma, n), index=pd.bdate_range("2025-01-01", periods=n))


def test_performance_calc_metrics_matches_manual_recalc(monkeypatch) -> None:
    perf = _load_toolkit_script("performance_metrics_cn", monkeypatch, "_m5_perf_metrics")
    r = _sample_returns()
    m = perf.calc_metrics(r, "样本资产")
    assert m is not None

    ann_ret = float(r.mean()) * ANN
    ann_vol = float(r.std()) * ANN**0.5  # pandas 默认 ddof=1
    sharpe = (ann_ret - RF) / ann_vol
    neg = r[r < 0]
    downside = float(neg.std()) * ANN**0.5  # 负收益子样本 std（ddof=1）
    sortino = (ann_ret - RF) / downside
    cum = (1 + r).cumprod()
    max_dd = float(((cum - cum.cummax()) / cum.cummax()).min())
    calmar = ann_ret / abs(max_dd)

    assert m["年化收益%"] == pytest.approx(ann_ret * 100, abs=6e-3)
    assert m["年化波动%"] == pytest.approx(ann_vol * 100, abs=6e-3)
    assert m["最大回撤%"] == pytest.approx(max_dd * 100, abs=6e-3)
    assert m["夏普比率"] == pytest.approx(sharpe, abs=6e-5)
    assert m["索提诺比率"] == pytest.approx(sortino, abs=6e-5)
    assert m["Calmar比率"] == pytest.approx(calmar, abs=6e-5)


def test_performance_sortino_uses_negative_subsample_not_full_sample_semideviation(monkeypatch) -> None:
    """锁定索提诺分母口径：目标收益取 0 的负收益子样本 std，
    而非学术全样本半偏差 sqrt(mean(min(r,0)^2))。两者对同一样本结果不同。"""
    perf = _load_toolkit_script("performance_metrics_cn", monkeypatch, "_m5_perf_sortino")
    r = _sample_returns(seed=7)
    m = perf.calc_metrics(r, "样本资产")
    assert m is not None

    ann_ret = float(r.mean()) * ANN
    semidev = float(np.sqrt((np.minimum(r, 0) ** 2).mean())) * ANN**0.5
    sortino_semidev = (ann_ret - RF) / semidev
    assert abs(m["索提诺比率"] - sortino_semidev) > 1e-3


def _returns_with_target_sharpe(target: float, seed: int = 11, n: int = 160) -> pd.Series:
    """均值平移构造：夏普 = (mean*252 - RF) / (std*sqrt(252)) 精确等于 target（浮点误差内）。"""
    rng = np.random.default_rng(seed)
    base = pd.Series(rng.normal(0.0, 0.01, n), index=pd.bdate_range("2024-06-03", periods=n))
    ann_vol = float(base.std()) * ANN**0.5
    desired_mean = (RF + target * ann_vol) / ANN
    return base - float(base.mean()) + desired_mean


@pytest.mark.parametrize(
    ("target_sharpe", "expected_rating"),
    [
        (1.2, "优秀"),
        (0.75, "良好"),
        # 中证500 实测夏普 0.4805 逼近 0.5 边界：0.48 必须仍落在「需优化」档
        (0.48, "需优化"),
        (0.2, "需优化"),
    ],
)
def test_performance_rating_bands(monkeypatch, target_sharpe: float, expected_rating: str) -> None:
    perf = _load_toolkit_script("performance_metrics_cn", monkeypatch, "_m5_perf_rating")
    r = _returns_with_target_sharpe(target_sharpe)
    m = perf.calc_metrics(r, "样本资产")
    assert m is not None
    assert m["夏普比率"] == pytest.approx(target_sharpe, abs=6e-5)
    assert m["评级"] == expected_rating


# ============================================================
# 二、backtest_cn.calc_metrics / calc_annual_returns 口径锁定
# ============================================================


def test_backtest_calc_metrics_uses_geometric_annualization(monkeypatch) -> None:
    """回测年化口径是 CAGR（(1+累计)^(1/年数)-1），显式区别于 performance 脚本的算术年化。
    同时覆盖无负收益边界：索提诺（空负收益子样本）与 Calmar（零回撤）按实现约定落 0。"""
    bt = _load_toolkit_script("backtest_cn", monkeypatch, "_m5_backtest_cagr")
    # 全正收益、有波动：0.0005 与 0.0015 交替
    values = [0.0005, 0.0015] * (ANN // 2)
    ret = pd.Series(values, index=pd.bdate_range("2025-01-01", periods=ANN))
    m = bt.calc_metrics(ret, "全正收益")

    total = float(np.prod(1 + np.array(values)) - 1)
    assert m["累计收益%"] == pytest.approx(total * 100, abs=6e-3)
    # 恰好 1 年：CAGR == 累计收益
    assert m["年化收益%"] == pytest.approx(total * 100, abs=6e-3)
    # 若误用算术年化会得到 mean*252=25.2%，与 CAGR（约 28.6%）显著不同
    assert abs(m["年化收益%"] - float(np.mean(values)) * ANN * 100) > 3.0
    # 无负收益：索提诺子样本为空 → 0；净值单调上行零回撤 → Calmar 0，胜率 100
    assert m["索提诺比率"] == 0
    assert m["Calmar比率"] == 0
    assert m["最大回撤%"] == 0.0
    assert m["胜率%"] == 100.0


def test_backtest_calc_metrics_matches_manual_recalc(monkeypatch) -> None:
    bt = _load_toolkit_script("backtest_cn", monkeypatch, "_m5_backtest_manual")
    rng = np.random.default_rng(3)
    ret = pd.Series(rng.normal(6e-4, 0.009, 2 * ANN), index=pd.bdate_range("2024-01-01", periods=2 * ANN))
    m = bt.calc_metrics(ret, "样本策略")

    cum = (1 + ret).cumprod()
    total = float(cum.iloc[-1] - 1)
    years = len(ret) / ANN
    annual = (1 + total) ** (1 / years) - 1
    vol = float(ret.std()) * ANN**0.5
    sharpe = (annual - RF) / vol
    neg = ret[ret < 0]
    sortino = (annual - RF) / (float(neg.std()) * ANN**0.5)
    max_dd = float(((cum - cum.cummax()) / cum.cummax()).min())
    calmar = annual / abs(max_dd)

    assert m["年化收益%"] == pytest.approx(annual * 100, abs=6e-3)
    assert m["年化波动%"] == pytest.approx(vol * 100, abs=6e-3)
    assert m["夏普比率"] == pytest.approx(sharpe, abs=6e-4)
    assert m["索提诺比率"] == pytest.approx(sortino, abs=6e-4)
    assert m["最大回撤%"] == pytest.approx(max_dd * 100, abs=6e-3)
    assert m["Calmar比率"] == pytest.approx(calmar, abs=6e-4)
    assert m["累计收益%"] == pytest.approx(total * 100, abs=6e-3)


def test_backtest_annual_decomposition_closes_to_cumulative(monkeypatch) -> None:
    """年度分解（日历年内复利）必须与全期累计收益复利闭合（2 位小数舍入容差内）。"""
    bt = _load_toolkit_script("backtest_cn", monkeypatch, "_m5_backtest_annual")
    rng = np.random.default_rng(9)
    idx = pd.bdate_range("2024-01-02", "2025-12-31")
    ret_df = pd.DataFrame(
        {
            "策略A": rng.normal(5e-4, 0.008, len(idx)),
            "策略B": rng.normal(2e-4, 0.012, len(idx)),
        },
        index=idx,
    )
    annual = bt.calc_annual_returns(ret_df)
    assert annual["年份"].tolist() == [2024, 2025]
    for col in ("策略A", "策略B"):
        closure = float(np.prod(1 + annual[col].values / 100.0) - 1) * 100
        cumulative = float((1 + ret_df[col]).prod() - 1) * 100
        assert closure == pytest.approx(cumulative, abs=0.05)


# ============================================================
# 三、load_prices 资产入池守卫（本次修复的核心回归）
# ============================================================

_CORE_INDEX_SYMBOLS = {"sh000300", "sh000905"}
_CORE_FUTURES_SYMBOLS = {"AU0", "CU0", "SC0"}


def _price_frame(dates: pd.DatetimeIndex, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100.0 * np.cumprod(1 + rng.normal(3e-4, 0.008, len(dates)))
    return pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": close})


def _fake_ak(core_dates: pd.DatetimeIndex, bond_frame: pd.DataFrame) -> types.SimpleNamespace:
    def stock_zh_index_daily(symbol: str) -> pd.DataFrame:
        assert symbol in _CORE_INDEX_SYMBOLS
        return _price_frame(core_dates, seed=hash(symbol) % 1000)

    def futures_main_sina(symbol: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        assert symbol in _CORE_FUTURES_SYMBOLS
        frame = _price_frame(core_dates, seed=hash(symbol) % 1000)
        frame["日期"] = frame["date"]
        frame["收盘价"] = frame["close"]
        return frame

    def fund_etf_hist_em(
        symbol: str,
        period: str = "daily",
        start_date: str | None = None,
        end_date: str | None = None,
        adjust: str = "",
    ) -> pd.DataFrame:
        return bond_frame.copy()

    return types.SimpleNamespace(
        stock_zh_index_daily=stock_zh_index_daily,
        futures_main_sina=futures_main_sina,
        fund_etf_hist_em=fund_etf_hist_em,
    )


def _fake_windpy_module(error_code: int = 1) -> types.ModuleType:
    module = types.ModuleType("WindPy")

    class _FakeWind:
        def start(self, *args, **kwargs):
            return types.SimpleNamespace(ErrorCode=error_code)

    module.w = _FakeWind()
    return module


def _empty_bond_frame() -> pd.DataFrame:
    # 模拟系统源 akshare shim 对无数据别名的返回：空表但列齐全
    return pd.DataFrame(columns=["date", "close", "日期", "收盘"])


def _bond_frame(dates: pd.DatetimeIndex) -> pd.DataFrame:
    rng = np.random.default_rng(510)
    close = 102.0 * np.cumprod(1 + rng.normal(5e-5, 0.0008, len(dates)))
    frame = pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "close": close})
    frame["日期"] = frame["date"]
    frame["收盘"] = frame["close"]
    return frame


def _run_load_prices(monkeypatch: pytest.MonkeyPatch, bond_frame: pd.DataFrame, alias: str) -> pd.DataFrame:
    bt = _load_toolkit_script("backtest_cn", monkeypatch, alias)
    core_dates = pd.bdate_range("2024-01-02", periods=160)
    monkeypatch.setattr(bt, "ak", _fake_ak(core_dates, bond_frame))
    monkeypatch.setitem(sys.modules, "WindPy", _fake_windpy_module(error_code=1))
    return bt.load_prices()


def test_load_prices_skips_empty_bond_etf_series(monkeypatch) -> None:
    """回归：债券ETF备用接口返回 0 条时，不得把空序列加入资产池形成全 NaN 列。
    （原缺陷使风险平价滚动窗口 dropna 清空、优化被静默禁用，风险平价≡买持等权。）"""
    prices = _run_load_prices(monkeypatch, _empty_bond_frame(), "_m5_load_prices_empty_bond")
    assert "bond_gov" not in prices.columns
    assert set(prices.columns) == {"hs300", "csi500", "gold", "copper", "crude_oil"}
    # 资产池内不允许存在任何全 NaN 列，且每个交易日核心资产齐全
    assert prices.notna().all().all()


def test_load_prices_drops_bond_column_entirely_outside_window(monkeypatch) -> None:
    """回归：债券ETF序列非空、但历史全部早于回测窗口时，窗口内全 NaN 列必须被剔除。"""
    stale_bond = _bond_frame(pd.bdate_range("2018-01-02", periods=100))
    prices = _run_load_prices(monkeypatch, stale_bond, "_m5_load_prices_stale_bond")
    assert "bond_gov" not in prices.columns
    assert prices.notna().all().all()


def test_load_prices_keeps_bond_etf_with_valid_data(monkeypatch) -> None:
    """守卫不过度剔除：债券ETF在窗口内有有效数据时应正常入池。"""
    valid_bond = _bond_frame(pd.bdate_range("2024-01-02", periods=160))
    prices = _run_load_prices(monkeypatch, valid_bond, "_m5_load_prices_valid_bond")
    assert "bond_gov" in prices.columns
    assert prices["bond_gov"].notna().all()


def test_calc_rp_weights_differentiates_heteroscedastic_assets(monkeypatch) -> None:
    """数据可用时风险平价必须真实分化：低波动资产权重高于高波动资产，且显著偏离等权。"""
    bt = _load_toolkit_script("backtest_cn", monkeypatch, "_m5_rp_weights")
    rng = np.random.default_rng(42)
    ret_window = pd.DataFrame(
        {
            "hs300": rng.normal(0, 0.020, 120),
            "csi500": rng.normal(0, 0.012, 120),
            "gold": rng.normal(0, 0.005, 120),
        }
    )
    weights = bt.calc_rp_weights(ret_window, list(ret_window.columns))
    assert weights.sum() == pytest.approx(1.0, abs=1e-6)
    assert weights[2] > weights[0] + 0.05  # 低波动 gold 权重应明显高于高波动 hs300
    assert float(np.max(np.abs(weights - 1.0 / 3.0))) > 0.03  # 显著偏离等权
