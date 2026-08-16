"""模型二 DCC-GARCH（观察口径脚本 dcc_garch_cn.py）回归测试。

对照尽调笔记定义锁定：
- Q_t = (1-α-β)·Q̄ + α·ε_{t-1}·ε'_{t-1} + β·Q_{t-1}
- R_t = diag(Q_t)^{-1/2}·Q_t·diag(Q_t)^{-1/2}
- 参数档 α=0.05, β=0.93（慢速调整）
- 平均相关系数 = 全部两两配对等权平均（不含对角线）
- 预警阈值 >0.70 黄色预警 / >0.85 红色预警（严格大于）

仅使用合成价格数据，不读取 data/ 产物，不触碰 DuckDB。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.core_finance.macro.toolkit.scripts import dcc_garch_cn as dcc_script


def _synthetic_log_returns(
    n_days: int = 300,
    n_assets: int = 4,
    common_weight: float = 0.6,
    seed: int = 11,
) -> pd.DataFrame:
    """共同因子驱动的合成对数收益（百分比口径，同脚本 main 的 *100）。"""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2025-01-02", periods=n_days)
    common = rng.normal(0.0, 1.0, size=n_days)
    data = {
        f"asset{i}": common_weight * common + (1.0 - common_weight) * rng.normal(0.0, 1.0, size=n_days)
        for i in range(n_assets)
    }
    return pd.DataFrame(data, index=idx)


def _reference_dcc_pair_paths(log_ret: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """独立参考实现：按笔记公式逐步递推 Q_t/R_t，返回配对相关时序。"""
    std_resid = pd.DataFrame(
        {col: dcc_script._garch_standardize(log_ret[col]) for col in log_ret.columns}
    ).dropna()
    eps = std_resid.values.astype(float)
    n_obs, n_assets = eps.shape
    alpha = dcc_script.DCC_ALPHA
    beta = dcc_script.DCC_BETA

    q_bar = np.zeros((n_assets, n_assets))
    for t in range(n_obs):
        q_bar += np.outer(eps[t], eps[t])
    q_bar /= n_obs

    def normalize(q: np.ndarray) -> np.ndarray:
        d = np.sqrt(np.diag(q))
        return q / np.outer(d, d)

    cols = std_resid.columns.tolist()
    keys = [f"{cols[i]}_{cols[j]}" for i in range(n_assets) for j in range(i + 1, n_assets)]
    rows = []
    q_t = q_bar.copy()
    rows.append(normalize(q_t))
    for t in range(1, n_obs):
        q_t = (1.0 - alpha - beta) * q_bar + alpha * np.outer(eps[t - 1], eps[t - 1]) + beta * q_t
        rows.append(normalize(q_t))

    records = {
        key: [rows[t][i, j] for t in range(n_obs)]
        for key, (i, j) in zip(
            keys,
            [(i, j) for i in range(n_assets) for j in range(i + 1, n_assets)],
        )
    }
    return pd.DataFrame(records, index=std_resid.index), keys


def test_dcc_parameters_match_notes_slow_profile() -> None:
    assert dcc_script.DCC_ALPHA == 0.05
    assert dcc_script.DCC_BETA == 0.93
    assert dcc_script.DCC_ALPHA + dcc_script.DCC_BETA < 1.0


def test_dcc_recursion_matches_notes_formula() -> None:
    log_ret = _synthetic_log_returns()
    pair_series, avg_series, latest_corr = dcc_script.compute_dcc(log_ret)
    expected, keys = _reference_dcc_pair_paths(log_ret)

    assert set(pair_series) == set(keys)
    for key in keys:
        np.testing.assert_allclose(
            pair_series[key].values, expected[key].values, atol=1e-10, err_msg=key
        )
    # 最新相关矩阵与配对时序末值一致（资产名 asset0..assetN 不含下划线，split 安全）
    for key in keys:
        a, b = key.split("_", 1)
        assert abs(float(latest_corr.loc[a, b]) - float(pair_series[key].iloc[-1])) < 1e-12


def test_correlations_bounded_and_matrix_valid() -> None:
    log_ret = _synthetic_log_returns(seed=23)
    pair_series, avg_series, latest_corr = dcc_script.compute_dcc(log_ret)

    for key, series in pair_series.items():
        values = series.values
        assert np.isfinite(values).all(), key
        assert (np.abs(values) <= 1.0 + 1e-12).all(), key

    mat = latest_corr.values
    np.testing.assert_allclose(np.diag(mat), 1.0, atol=1e-12)
    np.testing.assert_allclose(mat, mat.T, atol=1e-12)


def test_avg_corr_is_equal_weight_pair_mean_excluding_diagonal() -> None:
    log_ret = _synthetic_log_returns(n_assets=5, seed=31)
    pair_series, avg_series, _ = dcc_script.compute_dcc(log_ret)

    n_assets = log_ret.shape[1]
    assert len(pair_series) == n_assets * (n_assets - 1) // 2  # 仅上三角，不含对角线

    pair_df = pd.DataFrame(pair_series)
    np.testing.assert_allclose(avg_series.values, pair_df.mean(axis=1).values, atol=1e-12)


def test_warning_thresholds_strictly_match_notes() -> None:
    classify = dcc_script.classify_warning
    assert classify(0.30) == "正常"
    assert classify(0.70) == "正常"  # 阈值为严格大于
    assert classify(0.7001) == "黄色预警"
    assert classify(0.85) == "黄色预警"
    assert classify(0.8501) == "红色预警"
    assert classify(0.95) == "红色预警"
    assert classify(-0.40) == "正常"


def test_common_factor_strength_moves_average_correlation() -> None:
    strong = _synthetic_log_returns(common_weight=0.9, seed=7)
    weak = _synthetic_log_returns(common_weight=0.05, seed=7)
    _, avg_strong, _ = dcc_script.compute_dcc(strong)
    _, avg_weak, _ = dcc_script.compute_dcc(weak)
    assert float(avg_strong.iloc[-1]) > float(avg_weak.iloc[-1])
    assert float(avg_strong.iloc[-1]) > 0.6
    assert float(avg_weak.iloc[-1]) < 0.3
