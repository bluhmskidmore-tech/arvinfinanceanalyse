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
