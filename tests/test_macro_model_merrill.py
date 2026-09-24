"""模型八：美林投资时钟（中国版）toolkit 脚本回归测试。

审计范围（2026-08-11）：backend/app/core_finance/macro/toolkit/scripts/merrill_clock_cn.py
（observation-only 口径，不入正式财务口径）。

覆盖点：
- 增长动量按行有效权重归一（修复系统源全 NaN 列静默稀释；与能力路径
  core_finance.macro.merrill_clock 同口径，对应 2026-07-19 审计 C-1/M-1）。
- 通胀动量权重为仓库既定口径 CPI×0.4 + PPI×0.6（尽调笔记原文为 CPI×0.6 +
  PPI×0.4；两处偏离是有意的且与能力模块一致，见脚本 docstring）。
- 四象限判定与笔记定义自洽；资产偏好得分在象限原型点上的排序与笔记映射。

纯单元测试：不连 DuckDB、不发网络请求、不写真实产物目录。
"""

from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest

from backend.app.core_finance.macro.merrill_clock import (
    compute_growth_momentum as capability_growth_momentum,
)
from backend.app.core_finance.macro.toolkit import get_toolkit_script


def _load_script_module(monkeypatch, tmp_path):
    """以与既有测试相同的 spec 方式加载 toolkit 脚本（隔离输出目录）。"""
    monkeypatch.setenv("MOSS_MACRO_TOOLKIT_OUTPUT_DIR", str(tmp_path / "toolkit_output"))
    script = get_toolkit_script("merrill_clock_cn")
    monkeypatch.syspath_prepend(str(script.path.parent.parent))
    spec = importlib.util.spec_from_file_location("_merrill_clock_cn_under_audit", script.path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _system_source_like_frame(periods: int = 24) -> pd.DataFrame:
    """模拟系统源兼容层返回的帧形态。

    - electricity / freight：请求了但系统源未收录 → 全 NaN 列；
    - pmi：序列 2025-06 才落库 → 前段 NaN；
    - 其余增长分量全程有值。
    """
    index = pd.date_range("2024-07-01", periods=periods, freq="MS")
    pmi = [np.nan] * 11 + [49.5 + i * 0.1 for i in range(periods - 11)]
    return pd.DataFrame(
        {
            "pmi": pmi,
            "industrial_va": [3.0 + i * 0.1 for i in range(periods)],
            "pmi_new_orders": [48.0 + i * 0.2 for i in range(periods)],
            "electricity": [np.nan] * periods,
            "freight": [np.nan] * periods,
        },
        index=index,
    )


def test_growth_momentum_ignores_all_nan_series_and_renormalizes(monkeypatch, tmp_path) -> None:
    """全 NaN 列不得稀释增长动量；权重按行内非 NaN 分量归一。"""
    legacy = _load_script_module(monkeypatch, tmp_path)
    frame = _system_source_like_frame()

    growth = legacy.compute_growth_momentum(frame)

    # 1) 与"只保留真实有数据的列"的帧结果一致：全 NaN 列没有任何影响。
    growth_without_missing = legacy.compute_growth_momentum(
        frame[["pmi", "industrial_va", "pmi_new_orders"]]
    )
    pd.testing.assert_series_equal(growth, growth_without_missing)

    # 2) 尾行（pmi 有值）：(0.30*pmi + 0.25*iva + 0.25*no) / 0.80。
    m_pmi = legacy.compute_momentum(frame["pmi"])
    m_iva = legacy.compute_momentum(frame["industrial_va"])
    m_no = legacy.compute_momentum(frame["pmi_new_orders"])
    expected_tail = (0.30 * m_pmi.iloc[-1] + 0.25 * m_iva.iloc[-1] + 0.25 * m_no.iloc[-1]) / 0.80
    assert growth.iloc[-1] == pytest.approx(expected_tail)

    # 3) pmi 尚无有效动量的早期行：(0.25*iva + 0.25*no) / 0.50，而不是被 /1.0 稀释。
    early = 5  # pmi 全 NaN 且 iva/no 动量已就绪的行
    assert np.isnan(m_pmi.iloc[early])
    expected_early = (0.25 * m_iva.iloc[early] + 0.25 * m_no.iloc[early]) / 0.50
    assert growth.iloc[early] == pytest.approx(expected_early)


def test_growth_momentum_all_nan_rows_stay_nan(monkeypatch, tmp_path) -> None:
    """整行无有效分量必须输出 NaN，不得伪装成零动量落入衰退/滞胀。"""
    legacy = _load_script_module(monkeypatch, tmp_path)
    index = pd.date_range("2025-01-01", periods=8, freq="MS")
    frame = pd.DataFrame(
        {name: [np.nan] * len(index) for name in legacy.GROWTH_WEIGHTS},
        index=index,
    )

    growth = legacy.compute_growth_momentum(frame)

    assert growth.isna().all()


def test_growth_momentum_matches_capability_module(monkeypatch, tmp_path) -> None:
    """脚本与能力路径 core_finance.macro.merrill_clock 增长口径逐点一致。"""
    legacy = _load_script_module(monkeypatch, tmp_path)
    frame = _system_source_like_frame()

    pd.testing.assert_series_equal(
        legacy.compute_growth_momentum(frame),
        capability_growth_momentum(frame),
    )


def test_inflation_momentum_repo_weights_and_cpi_fallback(monkeypatch, tmp_path) -> None:
    """通胀动量 = CPI×0.4 + PPI×0.6（仓库既定口径）；缺 PPI 列退化为纯 CPI。

    尽调笔记原文为 CPI×0.6 + PPI×0.4；本仓库两处实现（脚本与能力模块）
    一致采用 PPI 0.6，属于有记录的定义偏离，本测试固化现口径。
    """
    legacy = _load_script_module(monkeypatch, tmp_path)
    index = pd.date_range("2024-01-01", periods=18, freq="MS")
    frame = pd.DataFrame(
        {
            "cpi_yoy": [0.5 + i * 0.05 for i in range(len(index))],
            "ppi_yoy": [-1.0 + i * 0.15 for i in range(len(index))],
        },
        index=index,
    )

    inflation = legacy.compute_inflation_momentum(frame)
    expected = (
        0.4 * legacy.compute_momentum(frame["cpi_yoy"])
        + 0.6 * legacy.compute_momentum(frame["ppi_yoy"])
    )
    pd.testing.assert_series_equal(inflation, expected)

    cpi_only = legacy.compute_inflation_momentum(frame[["cpi_yoy"]])
    pd.testing.assert_series_equal(cpi_only, legacy.compute_momentum(frame["cpi_yoy"]))


def test_regime_label_matches_note_quadrants(monkeypatch, tmp_path) -> None:
    """四象限判定与笔记定义一致（0 轴切割），并复核当期产物点。"""
    legacy = _load_script_module(monkeypatch, tmp_path)

    assert legacy.get_regime_label(0.5, -0.5) == "复苏"
    assert legacy.get_regime_label(0.5, 0.5) == "过热"
    assert legacy.get_regime_label(-0.5, 0.5) == "滞胀"
    assert legacy.get_regime_label(-0.5, -0.5) == "衰退"

    # 2026-06 产物点（修复后 g=+0.228, i=+0.836）：增长↑通胀↑ → 过热。
    assert legacy.get_regime_label(0.228, 0.836) == "过热"

    # 边界归属约定：动量恰为 0 落在"减速/通胀↓"一侧。
    assert legacy.get_regime_label(0.0, 0.5) == "滞胀"
    assert legacy.get_regime_label(0.5, 0.0) == "复苏"
    assert legacy.get_regime_label(0.0, 0.0) == "衰退"


def test_asset_scores_match_note_ranking_in_archetypes(monkeypatch, tmp_path) -> None:
    """流动性中性（l=0）时象限原型点的资产排序对照笔记映射。

    笔记（四资产，不含黄金）：过热 商品>股>现金>债；滞胀 现金>商品>债>股；
    衰退 债>现金>股>商品；复苏 股>债>现金>商品。
    线性打分下"现金>商品"无法同时在复苏与滞胀两个对跖象限成立，
    复苏象限的现金/商品顺序与笔记不符是已知设计局限（见审计报告），
    此处固化当前行为以侦测未来口径变化。
    """
    legacy = _load_script_module(monkeypatch, tmp_path)

    overheat = legacy.compute_asset_scores(1.0, 1.0, 0.0)
    assert overheat["商品"] > overheat["股票"] > overheat["现金"] > overheat["债券"]

    stagflation = legacy.compute_asset_scores(-1.0, 1.0, 0.0)
    assert stagflation["现金"] > stagflation["商品"] > stagflation["债券"] > stagflation["股票"]

    recession = legacy.compute_asset_scores(-1.0, -1.0, 0.0)
    assert recession["债券"] > recession["现金"] > recession["股票"] > recession["商品"]

    recovery = legacy.compute_asset_scores(1.0, -1.0, 0.0)
    assert recovery["股票"] > recovery["债券"]
    # 与笔记的偏离（笔记：现金>商品）——当前实现为 商品>现金。
    assert recovery["商品"] > recovery["现金"]

    # 得分必须压缩在 [-1, +1]。
    for scores in (overheat, stagflation, recession, recovery):
        for value in scores.values():
            assert -1.0 <= value <= 1.0
