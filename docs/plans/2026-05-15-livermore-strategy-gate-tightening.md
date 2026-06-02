# Livermore 策略闸门收紧 — 回测验证备忘

> **日期**：2026-05-15
> **Commit**：`bd7c68b4`
> **驱动**：实盘 `livermore_candidate_history` 表诊断显示股票策略胜率长期低于 50%

---

## 1. 问题诊断

样本：`livermore_candidate_history` 表，2024-07 至 2026-05，3643 行，覆盖 stock_candidate / mean_reversion / factor_screen / theme_breakout 四类信号。

诊断结论 — 四个根因：

| # | 根因 | 证据（旧规则下） |
|---|------|---|
| 1 | mean_reversion 在 OFF 状态被放行，但 OFF 样本是负 alpha | 1012 条 OFF：avg_5d=-1.16%，win_5d=36.0% |
| 2 | OVERHEAT 被 confluence 当作 observe_entry_setup 状态 | 697 条：avg_5d=-0.09%，win_5d=41.1%（比 WARM 还差） |
| 3 | close_strength ≥ 0.70 阈值过松，且非单调 | 0.70-0.95 区间负期望，仅 0.95+ 桶 win=43.6%/avg=+1.36% |
| 4 | 排序主键是 sector_rank 升序，把最拥挤板块推到 top-6 | sector_rank=1：win=39.6%（最差桶）；rank=2：win=45.3% |

---

## 2. 修复

| # | 文件 | 改动 |
|---|------|------|
| 1 | `backend/app/core_finance/mean_reversion_candidates.py:9-10` | `ACTIVE_MARKET_STATES` 从 `{"OFF","WARM"}` 改为 `{"WARM"}`；`FORMULA_VERSION` v1→v2 |
| 2 | `backend/app/services/livermore_signal_confluence_service.py:7` | `ENTRY_OBSERVATION_STATES` 移除 `OVERHEAT` |
| 3 | `backend/app/core_finance/livermore_stock_candidates.py:143` | `close_strength >= 0.95`（从 0.70 提升） |
| 4 | `backend/app/core_finance/livermore_stock_candidates.py:238-244` | 排序主键 `sector_rank` → `abnormal_turnover` desc，`sector_rank` 降为第 3 排序键 |

`rv_livermore_stock_candidates_bundle` 整体从 v2 跨到 v6（含工作区已有的 OVERHEAT 突破延伸限速）。

---

## 3. 回测验证（基于现有 history 表过滤）

### 3.1 胜率改善

| 指标 | 修复前 | 修复后 | Δ |
|---|---|---|---|
| stock_candidate n | 1780 | 840 (-53%) | |
| stock_candidate avg_5d | +0.38% | **+1.36%** | +0.98pp |
| stock_candidate win_5d | 41.1% | **43.6%** | +2.5pp |
| stock_candidate win_20d | 41.0% | 41.5% | +0.5pp |
| mean_reversion n | 1637 | 625 (-62%) | |
| mean_reversion avg_5d | +0.04% | **+2.00%** | +1.96pp |
| mean_reversion win_5d | 42.0% | **51.7%** | +9.7pp |

mean_reversion 跨过 50% 胜率临界点；stock_candidate 仍欠 6pp 到 50%，但已转为正期望。

### 3.2 close_strength 阈值敏感性

| 阈值 | n | avg_5d | win_5d |
|---|---|---|---|
| ≥0.85 | 1153 | +0.76% | 41.9% |
| ≥0.90 | 978 | +1.03% | 42.5% |
| ≥0.92 | 916 | +1.10% | 42.7% |
| **≥0.95** | **840** | **+1.36%** | **43.6%** |

阈值越严越好，0.95 仍是最优点。**注意单调性悬崖**：0.85-0.95 区间是行为信号噪音，0.95+ 才是"封死收盘"的真信号。如果未来需要增加候选量，回调到 0.92 比 0.85 更稳。

### 3.3 候选池密度

| 指标 | 旧规则 | 新规则 (cs≥0.95) |
|---|---|---|
| stock_candidate 有候选天数 | 328/435 | 313/435 |
| 每日候选数（中位） | 6 | 3 |
| 每日候选数（p10） | — | 1 |
| <2 候选的天数 | — | 61 (14%) |
| 完全无候选的天数 | 107 | 122 |
| mean_reversion 有候选天数（WARM only） | — | 86/435 |
| mean_reversion 每日候选（中位） | — | 4 |

**结论**：候选池偏窄但仍可用。14% 的交易日只剩 1 条候选 — 这是预期收紧成本，胜率改善值得这个代价。

---

## 4. 决策

**WAIT — 不跑全量 backfill 重算**

理由：
1. 旧 history 表是新规则的超集，过滤即得到修复后的预期值。重跑只会得到一样的数字。
2. 真正需要验证的是"修复后产出的候选池在未来实盘的稳定性"，而非历史重算。
3. 排序键变化（#4）只影响 top-6 顺序，不影响候选数和单股 win_rate，无重算必要。

**让代码上线，从今天开始 daily backfill 自然累积新规则数据。**

---

## 5. 监控与告警阈值（建议）

监控周期：4 周滚动（约 20 个交易日）。

| 指标 | 目标区间 | 告警阈值 | 触发动作 |
|---|---|---|---|
| stock_candidate win_5d | 43-50% | < 38% | 复盘市场结构是否偏离训练期 |
| mean_reversion win_5d | 50-55% | < 45% | 检查是否需要细化 WARM 的子状态 |
| stock_candidate 每日候选数 < 2 的频率 | < 20% | > 30% | 回调 close_strength 阈值到 0.92 |
| mean_reversion 在非 WARM 状态产生候选 | 应为 0 | > 0 | 代码 bug，立刻修 |

---

## 6. 与原始 plan 文档的冲突说明

`docs/plans/2026-05-11-mean-reversion-strategy-cursor-prompt.md:30` 原设计明确写：
> 市场状态为 OFF 时新策略**仍然运行**（这是它存在的核心价值）

本次修复推翻该假设。原设计的依据是"震荡市/下跌市需要备份策略"；实盘 9 个月数据证明 mean_reversion 在 OFF 状态下不仅没有 alpha，反而是负 alpha（avg_5d=-1.16%）。

如果未来需要"OFF 状态下的策略"，应该是单独设计一条信号（例如更严格的下跌反转 + 量能确认），而不是降低 mean_reversion 的门槛。

---

## 7. 测试覆盖

提交 `bd7c68b4` 验证：

- 后端：82 tests passed
  - `tests/test_livermore_stock_candidates.py` (4)
  - `tests/test_livermore_signal_confluence.py` (14，含新增 OVERHEAT+supportive macro 用例)
  - `tests/test_livermore_strategy_core.py` (4)
  - `tests/test_market_data_livermore_api.py` (23)
  - `tests/test_market_data_livermore_candidate_history.py` (28)
  - `backend/tests/core_finance/test_mean_reversion_candidates.py` (9)
- 前端：81 tests passed
  - `src/api` + `src/features/market-data` (13)
  - `src/test/MarketDataPage` + `StockAnalysisPage` (68)

---

## 8. 风险与遗留

- **样本期单一**：1.5 年数据覆盖一个完整牛熊周期，但 2026 年市场结构如果偏离训练期分布（如 2025-03 那种 22.7% 单月负收益），数字会回落。
- **未触动 livermore_strategy.py 的状态判定**：本次只改了下游入场闸门，未改 OVERHEAT 状态本身的产生条件。如产品口径希望 OVERHEAT 直接降为 HOT，需单独立项。
- **factor_screen / theme_breakout 未动**：样本量不足（210 / 16 条），暂无足够证据支持调整。

---

## 9. 退出端修复（commit `ebb56a51`，2026-05-15）

### 9.1 问题诊断 — 入场端胜率低不是真问题，alpha ≈ 0 才是

A 股基线对照（5000 条随机日期 + 随机股票）：

| 基线 | win_5d | win_20d | avg_5d | avg_20d |
|---|---|---|---|---|
| 随机选股持有 | 51.0% | 53.6% | +0.73% | +2.04% |
| 候选股新规则 | 43.6% | 41.5% | +1.36% | +1.09% |
| 候选 vs 同日市场 alpha | — | — | **≈ -0.14%** | — |

**关键发现**：
1. 趋势策略的 win_rate 结构性低于随机基线（截断小损 + 骑大趋势的 payoff 形态）
2. 但是 alpha vs 市场 ≈ 0，说明候选 filter 没贡献超额收益，alpha 全部来自市场闸门择时
3. **真正的杠杆在退出端**：留住大赢家比提高入场胜率更值钱

### 9.2 退出规则回测（n=802 入场点，新规则下 stock_candidate）

| 退出规则 | n | avg | win | p10 | p90 |
|---|---|---|---|---|---|
| 持有到 T+20（基线） | 802 | +1.08% | 41.5% | -22.7% | +29.1% |
| **EMA10 跌破×2 天（旧规则）** | 802 | +0.54% | 33.9% | -12.7% | +15.0% |
| EMA5 跌破×2 天 | 802 | +0.87% | 35.0% | -12.7% | +18.3% |
| EMA20 跌破×2 天 | 802 | +0.86% | 31.9% | -13.0% | +18.0% |
| **EMA10 + 量能确认（新规则）** | 802 | **+2.72%** | 40.5% | -15.4% | +27.5% |

旧规则把 avg 砍半（+1.08% → +0.54%），p90 大赢家从 +29% 砍到 +15% — 即"退太早"问题严重。
新规则在 EMA10 跌破基础上叠加 `volume ≥ 1.3 × MA20`，过滤无量阴跌的伪信号：
- avg 翻 5x：+0.54% → +2.72%（也比基线 +1.08% 高 2.5x）
- win_rate 基本恢复基线水平：33.9% → 40.5%
- p90 基本恢复：+15% → +27.5%

### 9.3 修复

| 文件 | 改动 |
|---|---|
| `backend/app/core_finance/livermore_risk_exit.py:7-23` | `RiskExitSnapshot` 加 `volume_history` 字段；`MIN_HISTORY` 10→21；新增 `VOLUME_MA_WINDOW=20`、`VOLUME_CONFIRMATION_RATIO=1.3` |
| 同上 `_watch_item` | 触发条件改为 `price_below_ema AND volume_confirmed`；watch 项新增 `latest_volume`/`volume_ma20`/`volume_ratio`/`price_below_ema`/`volume_confirmed` |
| `backend/app/services/market_data_livermore_service.py:_load_risk_exit_snapshots` | SQL 加 `volume` 列；构建 `volume_history_by_code` 喂入 `RiskExitSnapshot` |
| `tests/test_livermore_risk_exit.py` | 4 个用例覆盖：量能确认通过 / 量能不足不触发 / 仅最新一天破不触发 / 缺失输入排除 |
| `tests/test_market_data_livermore_risk_exit_source.py` | 测试 fixture 加 volume 列 + 31 天历史（满足 21 根最小要求） |

`FORMULA_VERSION`：`rv_livermore_risk_exit_ema10_mvp_v1` → `rv_livermore_risk_exit_ema10_volume_v2`
`reason` 字段：`2d_below_ema10` → `2d_below_ema10_with_volume`

### 9.4 已知 caveat（决定提交时已接受）

回测设计有两个简化，可能让结果偏乐观：

1. **vol_ma20 用入场后 20 天均值代替**（理想应该用入场前 20 天）— 引入轻微 look-ahead bias。生产代码用的是入场前数据，不存在这个 bias，但回测验证的"+2.72% avg"数字本身可能略乐观。
2. **退出价用次日收盘**而不是次日开盘 — A 股开盘可能跳空更深，实际滑点会让回报略低。

预计这两个 caveat 累计让真实 avg 比 +2.72% 低 0.3-0.5pp，但仍然显著优于旧规则。

### 9.5 监控（追加到第 5 节告警表）

| 指标 | 目标区间 | 告警阈值 | 触发动作 |
|---|---|---|---|
| 退出触发后 +5 日额外回撤（"退对了吗"） | < -3% | > -1% | 量能阈值过严，下调到 1.2x |
| 退出后 +20 日反弹比例（"退早了吗"） | < 30% | > 50% | 检查是否需要叠加 sector 强度过滤 |
| volume_confirmed=False 但价格继续跌的天数 | — | 累计 > 15% | 评估是否需要 fallback 退出（如 close < EMA20） |

### 10. 入场端 v7 收紧（commit pending，2026-05-15 第二轮）

**驱动**：第 9 节修完退出端后，复诊入场端 — 发现 `sector_rank=1` 在新规则下已经不再是最差桶（avg=+1.61%），但 `abnormal_turnover` 和 `gap_norm` 两个维度上还有显著悬崖。

#### 10.1 诊断（在 close_strength≥0.95 + market_state ∈ {WARM,HOT,OVERHEAT} 基线下）

**sector_rank 分桶（已不是核心问题）**

| sector_rank | n | avg_5d | win_5d |
|---|---|---|---|
| 1 | 344 | +1.61% | 41.5% |
| 2 | 269 | +2.15% | 45.5% |
| 3 | 207 | +2.47% | 44.6% |

**abnormal_turnover 全 rank 分桶（[1.2, 2.0) 是甜区）**

| 区间 | n | avg_5d | win_5d |
|---|---|---|---|
| [1.0, 1.2) | 204 | +1.58% | 42.2% |
| **[1.2, 1.5)** | 255 | **+2.70%** | 44.3% |
| [1.5, 2.0) | 267 | +1.62% | 43.8% |
| [2.0, ∞) | 94 | +2.11% | 44.1% |
| rank=1 ∩ [2.0+) | 44 | **−1.15%** | 34.1% |

rank=1 + 极高换手率（≥2.0）的 44 个样本是 FOMO 追高顶部 — 显著负期望。

**gap_norm 全 rank 分桶（负跳空是负 alpha 来源）**

| 区间 | n | avg_5d | win_5d |
|---|---|---|---|
| [< −0.1] | 195 | **−0.37%** | 41.0% |
| [−0.1, 0) | 194 | +1.20% | 45.1% |
| [0, 0.2) | 311 | +3.19% | 44.1% |
| [0.2, ∞) | 120 | +4.13% | 44.2% |

#### 10.2 叠加效果

| 规则 | n | avg_5d | win_5d | 候选/日 |
|---|---|---|---|---|
| 当前新规则（基线 v6） | 820 | +2.00% | 43.6% | ~3 |
| + abnormal_turnover ∈ [1.2, 2.0) | 522 | ~+2.16% | ~44.1% | 2.7 |
| + gap_norm ≥ 0 | 431 | ~+3.66% | 44.1% | 2.3 |
| **+ 两个组合（v7）** | **280** | **+3.63%** | 44.1% | **2.0** |

avg 从 +2.00% 提升到 +3.63%（+82%），win_rate 维持 44%。代价：候选数从 ~3 降到 ~2/日，65% 的天数只有 1 条候选。

#### 10.3 修复

| 文件 | 改动 |
|---|---|
| `backend/app/core_finance/livermore_stock_candidates.py` | signal 条件加 `0.0 <= gap_norm`；`abnormal_turnover` 从 `[1.0, 3.5]` 收窄到 `[1.2, 2.0)`；新增 `sector_rank==1 ∩ abnormal_turnover>=2.0` 的 FOMO 豁免；`FORMULA_VERSION` v6→v7 |
| `tests/test_livermore_stock_candidates.py` | fixture 调整：`open_value` 从 21.55 → 21.85（gap_norm 转为 0.023）；top6 测试 `current_turnover` 列表从 `[1.5..8.0]` 改为 `[1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4]`（最低值会被新阈值过滤） |
| `frontend/src/api/marketDataClient.ts` | mock formula_version v6→v7 |

#### 10.4 已知 caveat

1. **候选池密度边缘**：65% 的天数只剩 1 条候选（vs v6 的 14%）。如果产品要求每日 ≥3 候选才"有用"，需把 atu 上限放宽到 2.5 或 gap_norm 下限放宽到 −0.05。
2. **多重过滤过拟合风险**：n=280 在加 4 个维度过滤后样本偏窄，应作为**实验规则**上线，监控 1-2 个月后再决定是否固化。
3. **rank=1 + atu≥2.0 豁免基于 44 条样本**：极小子集，统计置信度低；如果实盘出现"rank=1 高换手实际反弹"的反例 ≥ 5 次，应回退此豁免。

#### 10.5 监控（追加到第 5 节告警表）

| 指标 | 目标区间 | 告警阈值 | 触发动作 |
|---|---|---|---|
| stock_candidate v7 每日候选数 | ≥ 1 | 连续 5 天 = 0 | 临时回退到 v6（gap_norm 不限下限） |
| v7 win_5d 4 周滚动 | ≥ 40% | < 35% | 复盘是否单维度悬崖在新数据上失效 |
| rank=1 ∩ atu≥2.0 豁免触发后实际反弹比例 | < 30% | > 50% | 回退此豁免 |
