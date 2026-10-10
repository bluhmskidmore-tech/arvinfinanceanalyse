"""模型三 风险平价 + 模型四 风险预算（观察口径脚本 risk_parity_cn.py）回归测试。

对照尽调笔记定义锁定：
- RC_i = w_i·(Σw)_i/σ_p，Euler 分解 Σ RC_i = σ_p
- 模型三：目标 RC_1=...=RC_n，目标函数为风险贡献偏差平方和，SLSQP，约束 Σw=1、w≥0
- 模型四：min Σ(RC_i/b_i - 1)² 的等价实现 min Σ(RC_i/σ_p - b_i)²，
  贡献占比收敛到预算 b_i；预算高不等于权重高（低波动资产承担同等预算需要更高权重）
- BUDGET_MAP：四个美林时钟象限齐全，每行资产键与 ASSETS 一致且预算合计 1.0
- 求解未收敛必须抛 RuntimeError（不静默落盘错误权重）
- CSV 输出为中文列名（资产/权重/贡献/年化波动率）

仅使用合成协方差，不读取 data/ 产物，不触碰 DuckDB。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.app.core_finance.macro.toolkit.scripts import risk_parity_cn as rp_script


def _cov_from_vol_corr(vols: np.ndarray, corr: np.ndarray) -> np.ndarray:
    return corr * np.outer(vols, vols)


def _sample_cov_5() -> np.ndarray:
    """5 资产合成协方差：波动率量级贴近脚本宇宙（股指/贵金属/工业品/能源）。"""
    vols = np.array([0.20, 0.26, 0.25, 0.18, 0.45])
    corr = np.full((5, 5), 0.30)
    np.fill_diagonal(corr, 1.0)
    return _cov_from_vol_corr(vols, corr)


def _rc_share(w: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """独立参考实现：RC 占比 = w_i·(Σw)_i/σ_p²。"""
    w = np.asarray(w, dtype=float)
    sig = float(np.sqrt(w @ cov @ w))
    return w * (cov @ w) / sig / sig


def test_risk_contributions_formula_and_euler_sum() -> None:
    cov = _sample_cov_5()
    w = np.array([0.25, 0.15, 0.20, 0.30, 0.10])
    rc, sig = rp_script.risk_contributions(w, cov)

    expected_sig = float(np.sqrt(w @ cov @ w))
    assert abs(sig - expected_sig) < 1e-15
    np.testing.assert_allclose(rc, w * (cov @ w) / expected_sig, atol=1e-15)
    # Euler 分解：绝对贡献之和恰为组合波动率，占比之和恒为 1（与是否收敛无关）
    assert abs(float(np.sum(rc)) - sig) < 1e-12
    assert abs(float(np.sum(rc / sig)) - 1.0) < 1e-12


def test_risk_parity_equalizes_risk_contributions() -> None:
    cov = _sample_cov_5()
    w = rp_script.solve_risk_parity(cov)

    assert abs(float(np.sum(w)) - 1.0) < 1e-8
    assert (w > 0).all()
    np.testing.assert_allclose(_rc_share(w, cov), np.full(5, 0.2), atol=1e-5)
    # 方向性：等相关下波动率最高的资产（原油档 45%）权重最低，最低波动资产权重最高
    assert int(np.argmin(w)) == 4
    assert int(np.argmax(w)) == 3


def test_risk_budget_contributions_converge_to_budget() -> None:
    cov = _sample_cov_5()
    budget = [0.20, 0.15, 0.20, 0.15, 0.30]  # 当前产物使用的“过热”象限预算
    w = rp_script.solve_risk_budget(cov, budget)

    assert abs(float(np.sum(w)) - 1.0) < 1e-8
    assert (w > 0).all()
    np.testing.assert_allclose(_rc_share(w, cov), np.array(budget), atol=1e-5)


def test_risk_budget_accepts_unnormalized_budget() -> None:
    cov = _sample_cov_5()
    w_pct = rp_script.solve_risk_budget(cov, [20, 15, 20, 15, 30])
    w_frac = rp_script.solve_risk_budget(cov, [0.20, 0.15, 0.20, 0.15, 0.30])
    np.testing.assert_allclose(w_pct, w_frac, atol=1e-6)


def test_risk_budget_note_example_low_vol_asset_gets_higher_weight() -> None:
    """笔记应用示例的本质：同为 40% 预算，低波动“债券类”资产权重应远高于高波动“股票类”。"""
    vols = np.array([0.20, 0.05, 0.30])  # 股票 / 债券 / 商品
    corr = np.array([[1.0, -0.1, 0.2], [-0.1, 1.0, 0.0], [0.2, 0.0, 1.0]])
    cov = _cov_from_vol_corr(vols, corr)
    budget = [0.40, 0.40, 0.20]
    w = rp_script.solve_risk_budget(cov, budget)

    np.testing.assert_allclose(_rc_share(w, cov), np.array(budget), atol=1e-5)
    assert w[1] > w[0]  # 债券预算相同但波动低 → 资金权重更高
    assert w[1] > 0.5  # 与笔记量级一致（示例为债券权重约 60%）
    assert w[2] < w[0]


def test_budget_map_rows_are_valid_budgets() -> None:
    assert set(rp_script.BUDGET_MAP) == {"复苏", "过热", "滞胀", "衰退"}
    asset_keys = set(rp_script.ASSETS)
    for phase, row in rp_script.BUDGET_MAP.items():
        assert set(row) == asset_keys, phase
        assert abs(sum(row.values()) - 1.0) < 1e-12, phase
        assert all(v > 0 for v in row.values()), phase
    # 锁定当前产物对应的“过热”预算（20/15/20/15/30）
    assert rp_script.BUDGET_MAP["过热"] == {
        "hs300": 0.20,
        "csi500": 0.15,
        "gold": 0.20,
        "copper": 0.15,
        "crude_oil": 0.30,
    }


def test_solvers_raise_on_degenerate_covariance() -> None:
    zero_cov = np.zeros((3, 3))
    with pytest.raises(RuntimeError, match="risk parity"):
        rp_script.solve_risk_parity(zero_cov)
    with pytest.raises(RuntimeError, match="risk budget"):
        rp_script.solve_risk_budget(zero_cov, [0.5, 0.3, 0.2])


def test_save_csv_uses_chinese_columns_and_percent_units(tmp_path, monkeypatch) -> None:
    cov = _sample_cov_5()
    vol = np.sqrt(np.diag(cov))
    w_rp = rp_script.solve_risk_parity(cov)
    rc_rp, sig_rp = rp_script.risk_contributions(w_rp, cov)
    budget = [0.20, 0.15, 0.20, 0.15, 0.30]
    w_rb = rp_script.solve_risk_budget(cov, budget)
    rc_rb, sig_rb = rp_script.risk_contributions(w_rb, cov)

    out_csv = tmp_path / "risk_parity_results.csv"
    monkeypatch.setattr(rp_script, "CSV_OUT", str(out_csv))
    asset_names = [info["name"] for info in rp_script.ASSETS.values()]
    rp_script.save_csv(asset_names, w_rp, w_rb, rc_rp, sig_rp, rc_rb, sig_rb, vol)

    df = pd.read_csv(out_csv, encoding="utf-8-sig")
    assert list(df.columns) == ["资产", "风险平价权重%", "风险预算权重%", "风险平价贡献%", "风险预算贡献%", "年化波动率%"]
    assert list(df["资产"]) == ["沪深300", "中证500", "黄金期货", "铜期货", "原油期货"]
    # 百分比口径：权重列合计 100，贡献列合计 100（4 位小数舍入容差）
    assert abs(df["风险平价权重%"].sum() - 100.0) < 1e-3
    assert abs(df["风险预算权重%"].sum() - 100.0) < 1e-3
    assert abs(df["风险平价贡献%"].sum() - 100.0) < 1e-3
    assert abs(df["风险预算贡献%"].sum() - 100.0) < 1e-3
    np.testing.assert_allclose(df["风险预算贡献%"].to_numpy(), np.array(budget) * 100, atol=1e-2)
