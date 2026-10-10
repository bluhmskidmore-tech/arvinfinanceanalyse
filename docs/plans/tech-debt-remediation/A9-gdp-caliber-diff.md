# A9 · MACRO-P1-02：GDP 现价当季值 growth 口径修复对比报告

状态：已实现，**合并需 owner 签核**（growth 信号口径变化）。

## 问题

`backend/app/core_finance/macro_bond_linkage.py` 的 `GROWTH_INDICATORS` 含
`EMM00619381`（中国:GDP:现价:当季值，权重 0.8）。该序列是**未季调的名义
现价水平值**，但评分函数 `_score_latest_delta` 对所有 growth 序列统一取
`points[-1] - points[-2]` 相邻差分。对季度水平序列这等于环比：中国名义
GDP 呈 Q1 谷、Q4 峰的固定季节形态，每年 Q1 的相邻差分必然为大幅负值，
growth 信号被季节性系统性拉低（与真实同比增长无关）。

## 修复口径

按序列配置差分阶数 `_SEASONAL_DIFF_LAG_BY_SERIES = {"EMM00619381": 4}`：
GDP 现价当季值改用**同季上年（四期）差分**；其余序列（如工业增加值当月
同比，已是同比口径）保持 lag=1 不变。

选四期差分而非同比百分比的依据：现有评分结构是"绝对差分 / 差分历史标准
差"的无量纲归一（`_normalize_signal` + `_bounded_score`），四期差分可原样
复用 winsorize 与 dispersion 逻辑，不引入除法与量纲切换；`macro_history`
的有序 `(date, value)` 点列结构天然支持按索引取 lag。归一化后信号无量纲，
水平序列的长期增长趋势项由差分历史标准差吸收。

历史不足（≤4 期）时该序列返回 `None`，走既有降级路径：记
`Indicator score unavailable` warning、从加权中剔除，growth 退化为由其余
指标决定。contributing_factors 新增 `diff_lag` 字段披露口径。

## 改前 / 改后同输入对比（实测）

Fixture：13 个季度（2023Q1–2026Q1），季节形态 Q1 谷 / Q4 峰，同季逐年
+10（同比恒为正增长）；期末点为 2026Q1 = 310（同比 +10，+3.3%）。
工业增加值配平（delta=0），growth_score 完全由 GDP 决定。
探针命令：`.venv\Scripts\python.exe <probe>`（等价逻辑已固化进
`tests/test_macro_caliber_fixes.py`）。

| 量 | 改前（相邻差分） | 改后（同季上年差分） |
| --- | --- | --- |
| 对比基期 `previous_date` | 2025-12-31（上季，Q4 峰） | 2025-03-31（同季上年） |
| `delta`（winsorize 后） | **-38.0**（310 − 348） | **+10.0**（310 − 300） |
| `normalized_signal` | -1.378329 | +2.5 |
| GDP 因子 `score` | **-0.597445**（强衰退伪信号） | **+0.848284**（与真实同比一致） |
| `growth_score`（GDP 0.8 + 工业 1.0 加权） | -0.265531 | +0.377015 |
| composite 中 growth 贡献（权重 0.2） | -0.053106 | +0.075403 |

同输入下 growth 信号方向由负翻正，composite 贡献差 +0.128509。真实同比
为正的 Q1 期末不再输出衰退方向的 growth 信号。

## 影响面

- `growth_score` 仅在期末点为 Q1/季节谷时发生方向级变化；非季节序列
  （lag=1）行为逐位不变（`tests/test_macro_caliber_fixes.py::test_non_seasonal_growth_series_keeps_adjacent_diff`）。
- `compute_macro_environment_score` 的消费方（macro_toolkit 环境评分、
  transmission growth 轴 `_build_domestic_growth_inflation_axis`）随
  growth_score 数值联动，无 schema 变化；contributing_factors 为字典扩展
  （新增 `diff_lag`），向后兼容。
- GDP 历史 ≤4 期的调用将从"参与打分"变为"降级剔除 + warning"，这是
  口径上更诚实的行为（2 个点的水平序列本就无法给出有意义的增长信号）。

## 验证

- `python -m pytest tests -k "macro_bond_linkage or cycle or yield_curve_shape or macro_caliber" -q` → 178 passed
- `python -m pytest tests/test_macro_partial_capabilities_honesty.py tests/test_credit_spread_percentile.py tests/test_rate_turning_point_capability.py -q` → 22 passed
- 新增测试：`tests/test_macro_caliber_fixes.py`（GDP 4 例，另含 A9 同批
  政策利率交集 2 例、percentile_1y 窗口 3 例）
